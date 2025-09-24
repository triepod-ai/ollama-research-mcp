#!/usr/bin/env python3
"""
Coordinated TTS module for hooks.
Provides queue-based TTS notifications to prevent audio overlap.
Falls back to direct speak command if queue coordinator is unavailable.
"""

import json
import os
import socket
import subprocess
import sys
from pathlib import Path
from typing import Dict, Optional, Any


def send_queued_speak(content: str, priority: str = "medium", 
                     message_type: str = "info", hook_type: str = "",
                     tool_name: str = "", metadata: Optional[Dict] = None) -> bool:
    """
    Send a speak request to the queue coordinator.
    
    Args:
        content: Message content to speak
        priority: Priority level (low, medium, high, critical, interrupt)
        message_type: Type of message (info, warning, error, success, interrupt)
        hook_type: Hook that triggered this (pre_tool_use, post_tool_use, stop, etc.)
        tool_name: Tool name if applicable
        metadata: Additional metadata
        
    Returns:
        True if successfully queued, False otherwise
    """
    socket_path = Path("/tmp/tts_queue_coordinator.sock")
    
    # Check if coordinator is running
    if not socket_path.exists():
        return False
        
    try:
        # Connect to coordinator
        client_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        client_socket.settimeout(1.0)  # 1 second timeout
        client_socket.connect(str(socket_path))
        
        # Prepare request
        request = {
            "action": "speak",
            "content": content,
            "priority": priority,
            "message_type": message_type,
            "hook_type": hook_type,
            "tool_name": tool_name,
            "metadata": metadata or {}
        }
        
        # Send request
        client_socket.send(json.dumps(request).encode() + b'\n')
        
        # Receive response
        response_data = b""
        while True:
            chunk = client_socket.recv(4096)
            if not chunk:
                break
            response_data += chunk
            if b'\n' in response_data:
                break
                
        response = json.loads(response_data.decode())
        
        return response.get("status") == "success"
        
    except (socket.timeout, ConnectionRefusedError, OSError):
        # Coordinator not available or not responding
        return False
    except Exception:
        # Any other error
        return False
    finally:
        try:
            client_socket.close()
        except:
            pass


def notify_tts_coordinated(message: str, priority: str = "normal",
                          hook_type: str = "", tool_name: str = "",
                          metadata: Optional[Dict] = None) -> bool:
    """
    Send a coordinated TTS notification using the queue system.
    Falls back to direct speak command if coordinator is unavailable.
    
    Args:
        message: The message to speak
        priority: Priority level (normal, important, error)
        hook_type: Hook that triggered this notification
        tool_name: Tool name if applicable
        metadata: Additional metadata
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Skip TTS if disabled
        if os.getenv('TTS_ENABLED', 'true').lower() != 'true':
            return False
        
        # Get engineer name for personalization
        engineer_name = os.getenv('ENGINEER_NAME', 'Developer')
        
        # Format message based on priority (following speak command patterns)
        if priority == "error":
            personalized_message = f"{engineer_name}, Error: {message}"
            queue_priority = "critical"
            message_type = "error"
        elif priority == "important":
            personalized_message = f"{engineer_name}, Important: {message}"
            queue_priority = "high"
            message_type = "warning"
        else:
            personalized_message = f"{engineer_name}, {message}"
            queue_priority = "medium"
            message_type = "info"
        
        # Try to use queue coordinator first
        if send_queued_speak(
            content=personalized_message,
            priority=queue_priority,
            message_type=message_type,
            hook_type=hook_type,
            tool_name=tool_name,
            metadata=metadata
        ):
            return True
        
        # Fallback to simple lock mechanism if coordinator unavailable
        try:
            from .simple_lock_coordinator import speak_with_simple_lock
            
            # Use simple lock to prevent overlap
            timeout_map = {
                "error": 45.0,
                "important": 30.0,
                "normal": 20.0
            }
            timeout = timeout_map.get(priority, 20.0)
            
            return speak_with_simple_lock(personalized_message, timeout=timeout)
            
        except ImportError:
            # Final fallback to direct speak command
            subprocess.Popen(
                ['speak', personalized_message],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            return True
        
    except Exception:
        # Silently fail - don't disrupt the hook
        return False


def is_coordinator_available() -> bool:
    """
    Check if the TTS queue coordinator is available.
    
    Returns:
        True if coordinator is running and responsive, False otherwise
    """
    socket_path = Path("/tmp/tts_queue_coordinator.sock")
    return socket_path.exists()


# For backward compatibility
notify_tts = notify_tts_coordinated