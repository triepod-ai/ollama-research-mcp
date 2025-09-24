#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "redis>=4.0.0",
#     "requests>=2.28.0",
#     "psutil>=5.9.0"
# ]
# ///

"""
Relationship Tracker Utilities

Shared utilities for tracking session relationships in the multi-agent observability system.
Provides functions for detecting parent/child sessions, managing spawn markers, and
registering relationships with the observability server.
"""

import os
import json
import uuid
from pathlib import Path

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
from datetime import datetime
from typing import Optional, Dict, Any, List
import subprocess

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False


def get_parent_session_id() -> Optional[str]:
    """
    Multi-strategy parent session detection.
    
    Returns:
        Parent session ID if detected, None otherwise
    """
    # Strategy 1: Environment variable (most reliable)
    parent_id = os.getenv('CLAUDE_PARENT_SESSION_ID')
    if parent_id:
        return parent_id
    
    # Strategy 2: Current session context (for nested calls)
    current_session = os.getenv('CLAUDE_SESSION_ID')
    if current_session:
        # Check if there's a spawn marker indicating this is a child
        marker_dir = Path("/tmp/claude_spawn_markers")
        if marker_dir.exists():
            for marker_file in marker_dir.glob(f"*_{current_session}.json"):
                try:
                    with open(marker_file, 'r') as f:
                        marker_data = json.load(f)
                        return marker_data.get('parent_session_id')
                except (json.JSONDecodeError, IOError):
                    continue
    
    # Strategy 3: Process tree analysis (only if psutil available)
    if PSUTIL_AVAILABLE:
        try:
            current_pid = os.getpid()
            process = psutil.Process(current_pid)
            
            # Walk up the process tree looking for Claude processes
            while process.parent():
                parent_process = process.parent()
                
                # Look for Claude-like process names or environment variables
                try:
                    parent_env = parent_process.environ()
                    if 'CLAUDE_SESSION_ID' in parent_env:
                        potential_parent = parent_env['CLAUDE_SESSION_ID']
                        # Don't return our own session ID
                        if potential_parent != current_session:
                            return potential_parent
                except (psutil.AccessDenied, psutil.NoSuchProcess):
                    pass
                
                process = parent_process
                
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    
    # Strategy 4: Redis-based session tracking
    if REDIS_AVAILABLE:
        try:
            r = redis.Redis(host='localhost', port=6379, decode_responses=True)
            active_sessions = r.smembers("sessions:active")
            
            # If there's exactly one other active session, it might be the parent
            if len(active_sessions) == 2 and current_session in active_sessions:
                for session_id in active_sessions:
                    if session_id != current_session:
                        return session_id
                        
        except Exception:
            pass
    
    return None


def detect_spawn_method(input_data: Dict[str, Any]) -> str:
    """
    Detect how the subagent was spawned based on input data.
    
    Args:
        input_data: Input data from the hook
        
    Returns:
        Spawn method identifier
    """
    # Check for Task tool usage
    if 'tools' in input_data and 'Task' in str(input_data.get('tools', [])):
        return 'task_tool'
    
    # Check for @-mention patterns
    description = str(input_data.get('task_description', ''))
    if '@' in description:
        return 'at_mention'
    
    # Check for wave orchestration
    if input_data.get('wave_number') or input_data.get('wave_id'):
        return 'wave_orchestration'
    
    # Check for auto-activation flags
    if input_data.get('auto_activated'):
        return 'auto_activation'
    
    # Check for continuation flags
    if input_data.get('continuation_session'):
        return 'continuation'
    
    # Default to manual invocation
    return 'manual'


def get_wave_context(input_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Extract wave orchestration context if available.
    
    Args:
        input_data: Input data from the hook
        
    Returns:
        Wave context dictionary or None
    """
    wave_context = {}
    
    # Extract wave-specific fields
    wave_fields = ['wave_id', 'wave_number', 'wave_strategy', 'wave_total']
    for field in wave_fields:
        value = os.getenv(f'CLAUDE_{field.upper()}') or input_data.get(field)
        if value:
            wave_context[field] = value
    
    return wave_context if wave_context else None


def create_spawn_marker(child_session_id: str, spawn_context: Dict[str, Any]) -> bool:
    """
    Create a spawn marker file for child session discovery.
    
    Args:
        child_session_id: ID of the child session
        spawn_context: Context information about the spawn
        
    Returns:
        True if marker created successfully
    """
    try:
        marker_dir = Path("/tmp/claude_spawn_markers")
        marker_dir.mkdir(exist_ok=True)
        
        # Create marker with timestamp for cleanup
        timestamp = datetime.now().isoformat()
        marker_file = marker_dir / f"{timestamp}_{child_session_id}.json"
        
        marker_data = {
            "child_session_id": child_session_id,
            "parent_session_id": spawn_context.get('parent_session_id'),
            "spawn_method": spawn_context.get('spawn_method'),
            "agent_name": spawn_context.get('agent_name'),
            "task_description": spawn_context.get('task_description'),
            "tools_granted": spawn_context.get('tools_granted', []),
            "created_at": timestamp,
            "ttl": datetime.now().timestamp() + 3600  # 1 hour TTL
        }
        
        with open(marker_file, 'w') as f:
            json.dump(marker_data, f, indent=2)
            
        # Store in Redis if available
        if REDIS_AVAILABLE:
            try:
                r = redis.Redis(host='localhost', port=6379, decode_responses=True)
                r.setex(
                    f"spawn_marker:{child_session_id}",
                    3600,  # 1 hour TTL
                    json.dumps(marker_data)
                )
            except Exception:
                pass
        
        return True
        
    except Exception as e:
        print(f"Failed to create spawn marker: {e}")
        return False


def cleanup_spawn_markers() -> int:
    """
    Clean up expired spawn marker files.
    
    Returns:
        Number of markers cleaned up
    """
    cleaned = 0
    marker_dir = Path("/tmp/claude_spawn_markers")
    
    if not marker_dir.exists():
        return 0
    
    try:
        current_time = datetime.now().timestamp()
        
        for marker_file in marker_dir.glob("*.json"):
            try:
                with open(marker_file, 'r') as f:
                    marker_data = json.load(f)
                
                ttl = marker_data.get('ttl', 0)
                if current_time > ttl:
                    marker_file.unlink()
                    cleaned += 1
                    
            except (json.JSONDecodeError, IOError, KeyError):
                # Remove corrupted markers
                try:
                    marker_file.unlink()
                    cleaned += 1
                except:
                    pass
                    
    except Exception:
        pass
    
    return cleaned


def create_relationship_event(parent_id: str, child_id: str, context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Format relationship event payload for the server.
    
    Args:
        parent_id: Parent session ID
        child_id: Child session ID
        context: Spawn context information
        
    Returns:
        Formatted event payload
    """
    return {
        "event_type": "session_relationship",
        "parent_session_id": parent_id,
        "child_session_id": child_id,
        "relationship_type": context.get('relationship_type', 'parent/child'),
        "spawn_reason": context.get('spawn_method', 'unknown'),
        "delegation_type": context.get('delegation_type', 'sequential'),
        "spawn_context": {
            "agent_name": context.get('agent_name', 'unknown'),
            "task_description": context.get('task_description', ''),
            "spawn_method": context.get('spawn_method', 'manual'),
            "tools_granted": context.get('tools_granted', []),
            "wave_context": context.get('wave_context'),
            "timestamp": datetime.now().isoformat()
        },
        "depth_level": context.get('depth_level', 1),
        "session_path": context.get('session_path')
    }


def register_session_relationship(parent_id: str, child_id: str, metadata: Dict[str, Any]) -> bool:
    """
    Register relationship with the observability server.
    
    Args:
        parent_id: Parent session ID
        child_id: Child session ID
        metadata: Additional relationship metadata
        
    Returns:
        True if registration successful
    """
    if not REQUESTS_AVAILABLE:
        return False
    
    try:
        server_url = os.getenv('OBSERVABILITY_SERVER_URL', 'http://localhost:4000')
        
        # Create relationship payload
        relationship_data = {
            "parent_session_id": parent_id,
            "child_session_id": child_id,
            "relationship_type": metadata.get('relationship_type', 'parent/child'),
            "spawn_reason": metadata.get('spawn_method', 'subagent_delegation'),
            "delegation_type": metadata.get('delegation_type', 'sequential'),
            "spawn_metadata": {
                "agent_name": metadata.get('agent_name'),
                "task_description": metadata.get('task_description'),
                "tools_granted": metadata.get('tools_granted', []),
                "spawn_method": metadata.get('spawn_method'),
                "wave_context": metadata.get('wave_context')
            },
            "created_at": int(datetime.now().timestamp() * 1000),
            "depth_level": metadata.get('depth_level', 1),
            "session_path": metadata.get('session_path')
        }
        
        # Send to relationships endpoint
        response = requests.post(
            f"{server_url}/api/sessions/relationships",
            json=relationship_data,
            timeout=5
        )
        
        if response.status_code in [200, 201]:
            return True
        else:
            print(f"Server rejected relationship: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"Failed to register relationship with server: {e}")
        return False


def update_relationship_completion(child_id: str, completion_data: Dict[str, Any]) -> bool:
    """
    Update relationship when child session completes.
    
    Args:
        child_id: Child session ID
        completion_data: Completion information
        
    Returns:
        True if update successful
    """
    if not REQUESTS_AVAILABLE:
        return False
    
    try:
        server_url = os.getenv('OBSERVABILITY_SERVER_URL', 'http://localhost:4000')
        
        # Send completion update
        response = requests.patch(
            f"{server_url}/api/sessions/relationships/{child_id}/complete",
            json={
                "completed_at": int(datetime.now().timestamp() * 1000),
                "completion_status": completion_data.get('status', 'completed'),
                "final_metrics": completion_data.get('metrics', {}),
                "result_summary": completion_data.get('summary', '')
            },
            timeout=5
        )
        
        return response.status_code in [200, 204]
        
    except Exception as e:
        print(f"Failed to update relationship completion: {e}")
        return False


def calculate_session_depth(parent_session_id: Optional[str] = None) -> int:
    """
    Calculate the depth level of the current session.
    
    Args:
        parent_session_id: Parent session ID if known
        
    Returns:
        Session depth level (0 for root sessions)
    """
    if not parent_session_id:
        return 0
    
    # Try to get depth from Redis cache
    if REDIS_AVAILABLE:
        try:
            r = redis.Redis(host='localhost', port=6379, decode_responses=True)
            cached_depth = r.get(f"session_depth:{parent_session_id}")
            if cached_depth:
                return int(cached_depth) + 1
        except Exception:
            pass
    
    # Fallback to counting relationships (requires server API)
    if REQUESTS_AVAILABLE:
        try:
            server_url = os.getenv('OBSERVABILITY_SERVER_URL', 'http://localhost:4000')
            response = requests.get(
                f"{server_url}/api/sessions/{parent_session_id}/depth",
                timeout=3
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get('depth', 0) + 1
                
        except Exception:
            pass
    
    # Default to depth 1 if parent exists
    return 1


def build_session_path(parent_session_id: Optional[str], current_session_id: str) -> str:
    """
    Build a hierarchical session path.
    
    Args:
        parent_session_id: Parent session ID
        current_session_id: Current session ID
        
    Returns:
        Dot-separated session path
    """
    if not parent_session_id:
        return current_session_id
    
    # Try to get parent path from cache
    if REDIS_AVAILABLE:
        try:
            r = redis.Redis(host='localhost', port=6379, decode_responses=True)
            parent_path = r.get(f"session_path:{parent_session_id}")
            if parent_path:
                return f"{parent_path}.{current_session_id}"
        except Exception:
            pass
    
    # Fallback to simple parent.child format
    return f"{parent_session_id}.{current_session_id}"


def extract_agent_context(input_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract comprehensive agent context from input data.
    
    Args:
        input_data: Hook input data
        
    Returns:
        Structured agent context
    """
    # Get basic agent information
    agent_name = (
        input_data.get('agent_name') or 
        input_data.get('subagent_name') or 
        input_data.get('subagent_type') or
        'unknown'
    )
    
    task_description = (
        input_data.get('task_description') or
        input_data.get('description') or
        input_data.get('prompt') or
        ''
    )
    
    tools_granted = input_data.get('tools', [])
    if isinstance(tools_granted, str):
        tools_granted = [t.strip() for t in tools_granted.split(',')]
    
    return {
        "agent_name": agent_name,
        "task_description": task_description[:200],  # Limit length
        "tools_granted": tools_granted,
        "spawn_method": detect_spawn_method(input_data),
        "wave_context": get_wave_context(input_data),
        "context_size": len(json.dumps(input_data))
    }


def notify_parent_completion(parent_session_id: str, child_session_id: str, summary: str) -> bool:
    """
    Notify parent session of child completion.
    
    Args:
        parent_session_id: Parent session ID
        child_session_id: Child session ID
        summary: Completion summary
        
    Returns:
        True if notification sent successfully
    """
    try:
        # Use Redis pub/sub for parent notification
        if REDIS_AVAILABLE:
            r = redis.Redis(host='localhost', port=6379, decode_responses=True)
            message = {
                "child_session_id": child_session_id,
                "status": "completed",
                "summary": summary,
                "timestamp": datetime.now().isoformat()
            }
            r.publish(f"session:{parent_session_id}:children", json.dumps(message))
            return True
            
    except Exception as e:
        print(f"Failed to notify parent completion: {e}")
        
    return False