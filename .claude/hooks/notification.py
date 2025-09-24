#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""
Enhanced notification hook for Claude Code with TTS support.
Tracks user interactions and permissions with optional audio feedback.
Integrated with Multi-Agent Observability System.
"""

import json
import os
import sys
import random
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

# Phase 2: Import observability system for coordinated TTS
try:
    from utils.tts.observability import (
        should_speak_event_coordinated, 
        get_observability,
        EventCategory,
        EventPriority
    )
    OBSERVABILITY_AVAILABLE = True
except ImportError:
    OBSERVABILITY_AVAILABLE = False

# Import coordinated TTS for queue-based notifications
try:
    from utils.tts.coordinated_speak import notify_tts_coordinated
    COORDINATED_TTS_AVAILABLE = True
except ImportError:
    COORDINATED_TTS_AVAILABLE = False

# Log directory for notifications - adapted for observability system
PROJECT_ROOT = Path(__file__).parent.parent.parent
LOG_DIR = PROJECT_ROOT / "logs" / "hooks" / "notifications"
DEBUG_LOG_DIR = PROJECT_ROOT / "logs" / "hooks" / "debug"

def extract_tool_name(notification_data: Dict[str, Any], debug_enabled: bool = False) -> str:
    """Extract tool name from multiple sources with MCP parsing."""
    
    # Priority order for tool name extraction:
    # 1. Environment variable TOOL_NAME
    # 2. notification_data tool_name field
    # 3. Parse from notification_data structure
    # 4. Extract from message content
    
    # Check environment variable first
    tool_name = os.getenv("TOOL_NAME", "").strip()
    if tool_name:
        return parse_mcp_tool_name(tool_name)
    
    # Check notification data
    tool_name = notification_data.get("tool_name", "").strip()
    if tool_name:
        return parse_mcp_tool_name(tool_name)
    
    # Check for tool info in nested structure
    tool_info = notification_data.get("tool_info", {})
    if isinstance(tool_info, dict):
        tool_name = tool_info.get("tool_name", "").strip()
        if tool_name:
            return parse_mcp_tool_name(tool_name)
    
    # Try to extract from message content
    message = notification_data.get("message", "")
    if "permission" in message.lower():
        # Look for patterns like "permission to use X"
        import re
        match = re.search(r'permission to use (\w+)', message.lower())
        if match:
            return parse_mcp_tool_name(match.group(1))
    
    # Check for specific notification types
    notification_type = notification_data.get("type", "")
    if "tool" in notification_type.lower():
        return parse_mcp_tool_name(notification_type)
    
    return "a tool"  # Fallback

def parse_mcp_tool_name(raw_tool_name: str) -> str:
    """Parse MCP tool names into friendly format."""
    if not raw_tool_name or raw_tool_name.strip() == "":
        return "a tool"
    
    # Handle MCP tool names like mcp__chroma__chroma_list_collections
    if raw_tool_name.startswith("mcp__"):
        parts = raw_tool_name.split("__")
        if len(parts) >= 3:
            server = parts[1]  # e.g., "chroma"
            action = parts[2]  # e.g., "chroma_list_collections"
            
            # Convert snake_case to readable format
            action_words = action.replace("_", " ").title()
            server_name = server.title()
            
            # Remove redundant server name from action if present
            if action_words.lower().startswith(server.lower()):
                action_words = action_words[len(server):].strip()
            
            return f"{server_name} {action_words}".strip()
        elif len(parts) == 2:
            # Simple MCP tool like mcp__chroma
            return parts[1].title()
    
    # Handle standard tools
    tool_mapping = {
        "Bash": "Bash command",
        "Read": "file reading",
        "Write": "file writing", 
        "Edit": "file editing",
        "MultiEdit": "multiple file editing",
        "Grep": "text search",
        "Glob": "file pattern matching",
        "Task": "sub-agent task",
        "TodoWrite": "todo management",
        "WebFetch": "web content fetching",
        "WebSearch": "web search",
    }
    
    return tool_mapping.get(raw_tool_name, raw_tool_name)

def log_debug_info(debug_info: Dict[str, Any]) -> None:
    """Log debug information for troubleshooting."""
    try:
        DEBUG_LOG_DIR.mkdir(parents=True, exist_ok=True)
        debug_file = DEBUG_LOG_DIR / f"tool_name_debug_{datetime.now().strftime('%Y%m%d')}.jsonl"
        
        with open(debug_file, "a") as f:
            debug_entry = {
                "timestamp": datetime.now().isoformat(),
                **debug_info
            }
            f.write(json.dumps(debug_entry) + "\n")
    except Exception:
        # Silently fail debug logging
        pass

def get_notification_info() -> Dict[str, Any]:
    """Extract notification information from environment."""
    # Try to read from stdin if available
    notification_data = {}
    stdin_content = ""
    if not sys.stdin.isatty():
        try:
            stdin_content = sys.stdin.read()
            if stdin_content.strip():
                notification_data = json.loads(stdin_content)
        except:
            pass
    
    # Debug logging to understand what we're receiving
    debug_enabled = os.getenv('TTS_DEBUG', 'false').lower() == 'true'
    
    # Extract tool name from multiple sources
    tool_name = extract_tool_name(notification_data, debug_enabled)
    
    info = {
        "notification_type": os.getenv("NOTIFICATION_TYPE", notification_data.get("type", "unknown")),
        "message": notification_data.get("message", ""),
        "tool_name": tool_name,
        "timestamp": datetime.now().isoformat(),
        "project": "multi-agent-observability-system",
        "user": os.getenv("USER", "unknown"),
    }
    
    if debug_enabled:
        debug_info = {
            "env_tool_name": os.getenv("TOOL_NAME", "NOT_SET"),
            "notification_data": notification_data,
            "stdin_content": stdin_content[:200] if stdin_content else "EMPTY",
            "extracted_tool_name": tool_name,
        }
        log_debug_info(debug_info)
    
    return info

def should_speak(info: Dict[str, Any], analysis: Dict[str, Any]) -> bool:
    """Determine if this notification should trigger TTS with Phase 2 coordination."""
    
    # Phase 2: Use observability system if available
    if OBSERVABILITY_AVAILABLE:
        return should_speak_with_observability(info, analysis)
    
    # Fallback to original logic if observability unavailable
    return should_speak_legacy(info, analysis)

def should_speak_with_observability(info: Dict[str, Any], analysis: Dict[str, Any]) -> bool:
    """Phase 2: Use observability system for coordinated TTS decisions."""
    
    # Map notification to observability categories
    category = map_notification_to_category(analysis)
    priority = map_notification_to_priority(info, analysis)
    tool_name = info.get("tool_name", "")
    message = info.get("message", "")
    
    # Create metadata for coordination
    metadata = {
        "type": info.get("type", "notification"),
        "notification_type": info.get("notification_type", ""),
        "analysis": analysis
    }
    
    # Use coordinated TTS decision system
    return should_speak_event_coordinated(
        message=message,
        priority=priority.value,
        category=category.value,
        hook_type="notification",
        tool_name=tool_name,
        metadata=metadata
    )

def should_speak_legacy(info: Dict[str, Any], analysis: Dict[str, Any]) -> bool:
    """Legacy TTS decision logic for fallback compatibility."""
    # Skip generic waiting messages
    message = info.get("message", "").lower()
    if "waiting" in message and "continue" in message:
        return False
    
    # Always speak permission requests
    if analysis.get("category") == "permission_request":
        return True
    
    # Speak high-risk tool notifications
    if analysis.get("high_risk_tool"):
        return True
    
    # Speak idle timeouts
    if analysis.get("category") == "idle_timeout":
        return True
    
    # Observability session notifications - check priority in notification data
    notification_data = info.get("priority", "")
    if notification_data in ["subagent_complete", "memory_confirmed", "memory_failed", "error", "important"]:
        return True
    
    # Observability session type - always speak
    if info.get("type") == "observability_session":
        return True
    
    # Intelligent tool notification filtering
    return should_notify_for_tool(info, analysis)

# Simple in-memory cache for frequency limiting (resets per hook process)
_notification_cache = {}
_cache_timeout = 60  # seconds

def check_notification_frequency(tool_name: str, message: str) -> bool:
    """Check if this notification should be throttled based on frequency."""
    import time
    
    # Create a simple cache key
    cache_key = f"{tool_name}:{hash(message[:100])}"  # Use first 100 chars of message
    current_time = time.time()
    
    # Check if we've seen this notification recently
    if cache_key in _notification_cache:
        last_time = _notification_cache[cache_key]
        if current_time - last_time < _cache_timeout:
            # Too recent, throttle this notification
            return False
    
    # Allow notification and update cache
    _notification_cache[cache_key] = current_time
    
    # Clean up old cache entries (simple cleanup)
    cutoff_time = current_time - _cache_timeout * 2
    keys_to_remove = [k for k, v in _notification_cache.items() if v < cutoff_time]
    for key in keys_to_remove:
        del _notification_cache[key]
    
    return True

def should_notify_for_tool(info: Dict[str, Any], analysis: Dict[str, Any]) -> bool:
    """Intelligent filtering for tool notifications with frequency control."""
    
    tool_name = info.get("tool_name", "").lower()
    message = info.get("message", "").lower()
    
    # Check frequency limiting to prevent spam
    if not check_notification_frequency(tool_name, message):
        return False
    
    # Tool categorization for notification decisions
    
    # ALWAYS notify: Security-critical operations
    security_critical_tools = ["bash", "command", "file writing", "file editing", "webfetch", "websearch"]
    if any(critical in tool_name for critical in security_critical_tools):
        return True
    
    # PERMISSION notify: File operations requesting permission
    file_operation_tools = ["file reading", "file writing", "file editing", "multiple file editing"]
    if any(file_op in tool_name for file_op in file_operation_tools):
        # Only notify if it's a permission request
        if "permission" in message or analysis.get("category") == "permission_request":
            return True
    
    # CONTEXT notify: Database/MCP operations with important context
    mcp_tools = ["chroma", "qdrant", "redis", "memory", "list collections", "store"]
    if any(mcp in tool_name for mcp in mcp_tools):
        # Notify for permission requests, errors, or confirmations
        if ("permission" in message or "error" in message or "failed" in message or 
            "timeout" in message or "confirmed" in message or "completed" in message):
            return True
    
    # NEVER notify: Routine operations that don't require attention
    routine_tools = ["text search", "file pattern matching", "ls", "grep", "glob"]
    if any(routine in tool_name for routine in routine_tools):
        # Only notify if explicit permission request (not just usage)
        return "permission" in message and "requested" in message
    
    # SUB-AGENT notify: Task delegation operations
    if "sub-agent" in tool_name or "task" in tool_name:
        return True
    
    # Default: Notify for any explicit permission requests
    if "permission" in message or analysis.get("category") == "permission_request":
        return True
    
    # Skip other notifications
    return False

def map_notification_to_category(analysis: Dict[str, Any]) -> 'EventCategory':
    """Map notification analysis to observability event category."""
    if not OBSERVABILITY_AVAILABLE:
        return None
    
    category = analysis.get("category", "general")
    
    if category == "permission_request":
        return EventCategory.PERMISSION
    elif category == "idle_timeout":
        return EventCategory.GENERAL
    elif "error" in category.lower():
        return EventCategory.ERROR
    elif analysis.get("high_risk_tool"):
        return EventCategory.SECURITY
    else:
        return EventCategory.GENERAL

def map_notification_to_priority(info: Dict[str, Any], analysis: Dict[str, Any]) -> 'EventPriority':
    """Map notification info to observability event priority."""
    if not OBSERVABILITY_AVAILABLE:
        return None
    
    # High priority for permission requests and errors
    if analysis.get("category") == "permission_request":
        return EventPriority.HIGH
    elif analysis.get("high_risk_tool"):
        return EventPriority.HIGH
    elif "error" in info.get("message", "").lower():
        return EventPriority.CRITICAL
    
    # Observability session priorities
    obs_priority = info.get("priority", "")
    if obs_priority in ["error", "important"]:
        return EventPriority.HIGH
    elif obs_priority in ["subagent_complete", "memory_failed"]:
        return EventPriority.MEDIUM
    elif obs_priority == "memory_confirmed":
        return EventPriority.LOW
    
    # Default priority
    return EventPriority.MEDIUM

def generate_tts_message(info: Dict[str, Any], analysis: Dict[str, Any]) -> str:
    """Generate appropriate TTS message with AI enhancement."""
    
    # Try AI-enhanced message generation first
    smart_message = generate_smart_tts_message(info, analysis)
    if smart_message:
        return smart_message
    
    # Fall back to original logic
    return generate_basic_tts_message(info, analysis)

def generate_smart_tts_message(info: Dict[str, Any], analysis: Dict[str, Any]) -> Optional[str]:
    """Generate AI-enhanced TTS message using smart processor integration."""
    try:
        # Check if AI processing is enabled and available
        if not os.getenv('SMART_TTS_ENABLED', 'true').lower() == 'true':
            return None
        
        message = info.get("message", "")
        tool_name = info.get("tool_name", "")
        
        if not message:
            return None
        
        # Skip smart processing for very short messages
        if len(message) < 50:
            return None
        
        # Create context for AI processing
        context_type = determine_ai_context_type(info, analysis)
        
        # Prepare input for AI processing following LLM Integration Guide patterns
        ai_input = f"Claude Code Tool Notification: {message}"
        if tool_name and tool_name != "a tool":
            ai_input += f" (Tool: {tool_name})"
        
        # Use smart processor directly (following integration guide patterns)
        smart_processor_path = "/home/bryan/bin/speak-app/tts/smart_processor.py"
        if not os.path.exists(smart_processor_path):
            return None
        
        # Call smart processor to get enhanced message
        cmd = [
            "python3", smart_processor_path, 
            "--context", context_type,
            ai_input
        ]
        
        # Execute smart processor and capture output
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True, 
            timeout=10,
            cwd=os.path.dirname(smart_processor_path)
        )
        
        if result.returncode == 0 and result.stdout.strip():
            # Extract the processed text from stdout
            processed_text = result.stdout.strip()
            
            # Basic validation - ensure it's not just the original text
            if processed_text and processed_text != ai_input:
                return processed_text
        
        return None
        
    except Exception as e:
        # Silently fail and fall back to basic message generation
        return None

def determine_ai_context_type(info: Dict[str, Any], analysis: Dict[str, Any]) -> str:
    """Determine the context type for AI processing."""
    
    tool_name = info.get("tool_name", "").lower()
    message = info.get("message", "").lower()
    
    if analysis.get("category") == "permission_request":
        return "permission"
    elif "error" in message or "failed" in message:
        return "error"
    elif "warning" in message:
        return "warning"
    elif any(critical in tool_name for critical in ["bash", "command", "editing", "writing"]):
        return "security"
    elif any(mcp in tool_name for mcp in ["chroma", "qdrant", "redis"]):
        return "database"
    elif "build" in message or "test" in message:
        return "build"
    else:
        return "general"

def generate_basic_tts_message(info: Dict[str, Any], analysis: Dict[str, Any]) -> str:
    """Generate basic TTS message (original logic)."""
    notification_type = info.get("notification_type", "")
    message = info.get("message", "")
    
    # Permission requests
    if analysis.get("category") == "permission_request":
        tool = info.get("tool_name", "a tool")
        # Ensure we have a meaningful tool name
        if tool in ["", "a tool", "tool"]:
            tool = "a tool"
        
        # Add personalization sometimes
        engineer_name = os.getenv('ENGINEER_NAME', 'Developer')
        if random.random() < 0.3:
            return f"Hey {engineer_name}, Claude needs permission to use {tool}"
        return f"Permission requested for {tool}"
    
    # Idle timeout
    if analysis.get("category") == "idle_timeout":
        return "Claude has been idle for over a minute"
    
    # High-risk tools
    if analysis.get("high_risk_tool"):
        tool = info.get("tool_name", "tool")
        return f"High-risk operation: {tool} requires attention"
    
    # Generic notification with message
    if message:
        # Truncate long messages
        if len(message) > 100:
            message = message[:97] + "..."
        return f"Notification: {message}"
    
    # Fallback
    return "Claude Code notification"

def notify_tts(message: str, priority: str = "normal") -> bool:
    """
    Standardized TTS notification using coordinated speak or fallback to direct speak.
    Follows LLM Integration Guide patterns for consistent voice notifications.
    """
    # Use coordinated TTS if available
    if COORDINATED_TTS_AVAILABLE:
        return notify_tts_coordinated(
            message=message,
            priority=priority,
            hook_type="notification"
        )
    
    # Fallback to direct speak command
    try:
        # Skip TTS if disabled
        if os.getenv('TTS_ENABLED', 'true').lower() != 'true':
            return False
        
        # Get engineer name for personalization
        engineer_name = os.getenv('ENGINEER_NAME', 'Developer')
        
        # Format message based on priority (following speak command patterns)
        if priority == "subagent_complete":
            personalized_message = f"{engineer_name}, Sub-agent completed: {message}"
        elif priority == "memory_confirmed":
            personalized_message = f"{engineer_name}, Memory operation confirmed: {message}"
        elif priority == "memory_failed":
            personalized_message = f"{engineer_name}, Memory operation failed: {message}"
        elif priority == "error":
            personalized_message = f"{engineer_name}, Error: {message}"
        elif priority == "important":
            personalized_message = f"{engineer_name}, Important: {message}"
        else:
            personalized_message = f"{engineer_name}, {message}"
        
        # Use speak command (non-blocking) - let speak handle voice selection and coordination
        subprocess.Popen(
            ['speak', personalized_message],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        
        return True
        
    except Exception:
        # Silently fail - don't disrupt the hook
        return False

# Voice selection logic removed - delegated to speak command's sophisticated coordination system

def determine_notification_priority(info: Dict[str, Any], analysis: Dict[str, Any]) -> str:
    """Determine the priority level for voice selection."""
    
    # Observability session priority override - use priority from notification data
    if info.get("type") == "observability_session" and info.get("priority"):
        return info.get("priority")
    
    # Check for specific priority indicators
    if analysis.get("category") == "permission_request":
        return "important"
    elif analysis.get("category") == "idle_timeout":
        return "normal"
    elif analysis.get("high_risk_tool"):
        return "important"
    elif "error" in info.get("message", "").lower():
        return "error"
    elif "subagent" in info.get("notification_type", "").lower():
        return "subagent_complete"
    elif "memory" in info.get("message", "").lower():
        if "failed" in info.get("message", "").lower():
            return "memory_failed"
        else:
            return "memory_confirmed"
    
    return "normal"

# Context determination logic removed - delegated to speak command's intelligent context awareness

def speak_notification(text: str) -> bool:
    """Legacy function for backward compatibility."""
    return notify_tts(text, "normal")

def log_notification(info: Dict[str, Any]) -> None:
    """Log notification event to file."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    
    # Create daily log file
    log_file = LOG_DIR / f"notifications_{datetime.now().strftime('%Y%m%d')}.jsonl"
    
    with open(log_file, "a") as f:
        f.write(json.dumps(info) + "\n")

def analyze_notification(info: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze the notification for patterns."""
    analysis = {
        "requires_attention": False,
        "category": "general",
    }
    
    notification_type = info.get("notification_type", "")
    message = info.get("message", "")
    
    if "permission" in notification_type.lower() or "permission" in message.lower():
        analysis["category"] = "permission_request"
        analysis["requires_attention"] = True
    elif "idle" in notification_type.lower() or "idle" in message.lower():
        analysis["category"] = "idle_timeout"
        analysis["idle_duration"] = "60+ seconds"
    
    # Track specific tools that commonly need permissions
    tool_name = info.get("tool_name", "")
    if tool_name in ["Bash", "Write", "Edit", "WebFetch"]:
        analysis["high_risk_tool"] = True
    
    return analysis

def announce_notification():
    """Announce that the agent needs user input."""
    try:
        # Get engineer name if available
        engineer_name = os.getenv('ENGINEER_NAME', 'Developer').strip()
        
        # Create notification message with 30% chance to include name
        if engineer_name and random.random() < 0.3:
            notification_message = f"{engineer_name}, your agent needs your input"
        else:
            notification_message = "Your agent needs your input"
        
        # Use speak command directly
        subprocess.run([
            "speak", notification_message
        ], 
        capture_output=True,  # Suppress output
        timeout=10  # 10-second timeout
        )
        
    except (subprocess.TimeoutExpired, subprocess.SubprocessError, FileNotFoundError):
        # Fail silently if TTS encounters issues
        pass
    except Exception:
        # Fail silently for any other errors
        pass

def main():
    """Main entry point for notification hook."""
    
    # Check for --notify flag
    tts_enabled = "--notify" in sys.argv
    
    # Get notification information
    info = get_notification_info()
    
    # Analyze the notification
    analysis = analyze_notification(info)
    
    # Add analysis to info
    info["analysis"] = analysis
    
    # Log the notification
    log_notification(info)
    
    # Handle TTS if enabled with intelligent voice selection
    tts_spoken = False
    if tts_enabled and should_speak(info, analysis):
        tts_message = generate_tts_message(info, analysis)
        
        # Determine priority for TTS notification
        priority = determine_notification_priority(info, analysis)
        
        tts_spoken = notify_tts(tts_message, priority)
        info["tts_spoken"] = tts_spoken
        info["tts_message"] = tts_message
        info["tts_priority"] = priority
    
    # Announce notification via TTS only if --notify flag is set
    # Skip TTS for the generic "Claude is waiting for your input" message
    if tts_enabled and info.get('message') != 'Claude is waiting for your input':
        announce_notification()
    
    # Output result
    result = {
        "logged": True,
        "notification_type": info["notification_type"],
        "analysis": analysis,
    }
    
    if tts_enabled:
        result["tts_enabled"] = True
        result["tts_spoken"] = tts_spoken
        if "tts_priority" in info:
            result["tts_priority"] = info["tts_priority"]
    
    print(json.dumps(result))
    
    # Always exit 0
    sys.exit(0)

if __name__ == "__main__":
    main()