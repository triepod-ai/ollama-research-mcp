#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.8"
# dependencies = [
#     "requests",
# ]
# ///

"""
HTTP client utility for sending events to the observability server.
"""

import json
import os
import sys
from typing import Dict, Any, Optional
import urllib.request
import urllib.parse


# Default server configuration
DEFAULT_SERVER_URL = "http://localhost:4000"
DEFAULT_TIMEOUT = 5.0


def get_server_url() -> str:
    """Get the observability server URL from environment or use default."""
    return os.environ.get("OBSERVABILITY_SERVER_URL", DEFAULT_SERVER_URL)


def get_timeout() -> float:
    """Get HTTP timeout from environment or use default."""
    try:
        return float(os.environ.get("OBSERVABILITY_HTTP_TIMEOUT", str(DEFAULT_TIMEOUT)))
    except ValueError:
        return DEFAULT_TIMEOUT


def send_event_to_server(event_data: Dict[str, Any], timeout: Optional[float] = None) -> bool:
    """
    Send an event to the observability server via HTTP POST.
    
    Args:
        event_data: Dictionary containing the event data
        timeout: Optional timeout in seconds
        
    Returns:
        True if successful, False otherwise
    """
    if timeout is None:
        timeout = get_timeout()
    
    server_url = get_server_url()
    endpoint = f"{server_url}/events"
    
    try:
        # Prepare the request
        json_data = json.dumps(event_data).encode('utf-8')
        
        # Create request with headers
        req = urllib.request.Request(
            endpoint,
            data=json_data,
            headers={
                'Content-Type': 'application/json',
                'User-Agent': 'Claude-Hooks/1.0'
            },
            method='POST'
        )
        
        # Send the request
        with urllib.request.urlopen(req, timeout=timeout) as response:
            if response.status == 200:
                return True
            else:
                print(f"Server returned status {response.status}", file=sys.stderr)
                return False
                
    except Exception as e:
        # Log error but don't fail - graceful degradation
        print(f"Failed to send event to server: {e}", file=sys.stderr)
        return False


def create_hook_event(
    source_app: str,
    session_id: str,
    hook_event_type: str,
    payload: Dict[str, Any],
    chat: Optional[list] = None,
    summary: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create a properly formatted HookEvent for the server.
    
    Args:
        source_app: The source application (e.g., "claude-code")
        session_id: The Claude session ID
        hook_event_type: Type of hook event (e.g., "post_tool_use", "user_prompt_submit")
        payload: The event payload data
        chat: Optional chat data
        summary: Optional event summary
        
    Returns:
        Formatted event dictionary
    """
    import time
    import socket
    
    # Enhance session ID with process ID and timestamp for uniqueness
    # This helps distinguish between multiple Claude Code sessions
    enhanced_session_id = f"{session_id}_{os.getpid()}_{int(time.time())}"
    
    # Add hostname and user info to payload for better identification
    if "metadata" not in payload:
        payload["metadata"] = {}
    
    payload["metadata"].update({
        "original_session_id": session_id,
        "process_id": os.getpid(),
        "hostname": socket.gethostname(),
        "user": os.environ.get("USER", "unknown"),
        "timestamp": int(time.time())
    })
    
    event = {
        "source_app": source_app,
        "session_id": enhanced_session_id,
        "hook_event_type": hook_event_type,
        "payload": payload,
        "timestamp": int(time.time() * 1000)  # Milliseconds since epoch
    }
    
    if chat is not None:
        event["chat"] = chat
    
    if summary is not None:
        event["summary"] = summary
    
    return event


def extract_tool_name_from_data(tool_data: Dict[str, Any]) -> str:
    """
    Extract tool name from tool data using the same logic as post_tool_use.py.
    
    Args:
        tool_data: The tool use data from the hook
        
    Returns:
        The tool name or 'unknown' if not found
    """
    # Try multiple possible field names for tool name
    tool_name_fields = [
        'tool_name',      # Current Claude Code field
        'tool',           # Legacy field
        'name',           # Alternative field
        'toolName',       # Camel case variant
        'tool_type',      # Another possible field
        'function_name',  # Function-based tools
    ]
    
    # Check top-level fields
    for field in tool_name_fields:
        if field in tool_data and tool_data[field]:
            return tool_data[field]
    
    # Check nested structures
    # Check if tool info is nested in payload
    if 'payload' in tool_data and isinstance(tool_data['payload'], dict):
        for field in tool_name_fields:
            if field in tool_data['payload'] and tool_data['payload'][field]:
                return tool_data['payload'][field]
    
    # Check if it's in a 'request' field
    if 'request' in tool_data and isinstance(tool_data['request'], dict):
        for field in tool_name_fields:
            if field in tool_data['request'] and tool_data['request'][field]:
                return tool_data['request'][field]
    
    return 'unknown'


def send_tool_use_event(session_id: str, tool_data: Dict[str, Any]) -> bool:
    """
    Send a tool use event to the observability server.
    
    Args:
        session_id: The Claude session ID
        tool_data: The tool use data from the hook
        
    Returns:
        True if successful, False otherwise
    """
    tool_name = extract_tool_name_from_data(tool_data)
    
    event = create_hook_event(
        source_app="claude-code",
        session_id=session_id,
        hook_event_type="post_tool_use",
        payload=tool_data,
        summary=f"Tool used: {tool_name}"
    )
    
    return send_event_to_server(event)


def send_user_prompt_event(session_id: str, prompt_data: Dict[str, Any]) -> bool:
    """
    Send a user prompt event to the observability server.
    
    Args:
        session_id: The Claude session ID
        prompt_data: The prompt data from the hook
        
    Returns:
        True if successful, False otherwise
    """
    event = create_hook_event(
        source_app="claude-code",
        session_id=session_id,
        hook_event_type="user_prompt_submit",
        payload=prompt_data,
        summary=f"User prompt: {prompt_data.get('prompt', '')[:100]}..."
    )
    
    return send_event_to_server(event)


def test_server_connection() -> bool:
    """
    Test if the observability server is reachable.
    
    Returns:
        True if server is reachable, False otherwise
    """
    server_url = get_server_url()
    timeout = get_timeout()
    
    try:
        req = urllib.request.Request(server_url, method='GET')
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.status == 200
    except Exception:
        return False


if __name__ == "__main__":
    # Test the connection when run directly
    if test_server_connection():
        print("✅ Server connection OK")
        sys.exit(0)
    else:
        print("❌ Server connection failed")
        sys.exit(1)