#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.8"
# dependencies = []
# ///

"""
Enhanced HTTP client with retry logic and better error handling.
"""

import json
import os
import sys
import time
from typing import Dict, Any, Optional, Tuple
import urllib.request
import urllib.parse
import urllib.error

# Configuration
DEFAULT_SERVER_URL = "http://localhost:4000"
DEFAULT_TIMEOUT = 2.0  # Reduced from 5.0
MAX_RETRIES = 2
RETRY_DELAY = 0.5

def get_server_url() -> str:
    """Get the observability server URL from environment or use default."""
    return os.environ.get("OBSERVABILITY_SERVER_URL", DEFAULT_SERVER_URL)

def get_timeout() -> float:
    """Get HTTP timeout from environment or use default."""
    try:
        return float(os.environ.get("OBSERVABILITY_HTTP_TIMEOUT", str(DEFAULT_TIMEOUT)))
    except ValueError:
        return DEFAULT_TIMEOUT

def send_event_with_retry(event_data: Dict[str, Any], max_retries: int = MAX_RETRIES) -> Tuple[bool, Optional[str]]:
    """
    Send event with retry logic and better error handling.
    
    Returns:
        Tuple of (success, error_message)
    """
    server_url = get_server_url()
    endpoint = f"{server_url}/events"
    timeout = get_timeout()
    
    for attempt in range(max_retries + 1):
        try:
            # Prepare the request
            json_data = json.dumps(event_data).encode('utf-8')
            
            req = urllib.request.Request(
                endpoint,
                data=json_data,
                headers={
                    'Content-Type': 'application/json',
                    'User-Agent': 'Claude-Hooks/1.0'
                },
                method='POST'
            )
            
            # Send with reduced timeout
            with urllib.request.urlopen(req, timeout=timeout) as response:
                if response.status == 200:
                    return True, None
                else:
                    return False, f"Server returned status {response.status}"
                    
        except urllib.error.URLError as e:
            if hasattr(e, 'reason') and 'timed out' in str(e.reason):
                error_msg = "timeout"
            else:
                error_msg = f"connection error: {e.reason}"
            
            # Don't retry on last attempt
            if attempt < max_retries:
                time.sleep(RETRY_DELAY)
                continue
            
            return False, error_msg
            
        except Exception as e:
            return False, f"unexpected error: {str(e)}"
    
    return False, "max retries exceeded"

def send_event_async(event_data: Dict[str, Any]) -> bool:
    """
    Send event asynchronously by spawning a subprocess.
    This prevents blocking the main hook execution.
    """
    try:
        import subprocess
        
        # Create a minimal script to send the event
        script = f"""
import json
import urllib.request

data = {json.dumps(event_data)}
req = urllib.request.Request(
    '{get_server_url()}/events',
    data=json.dumps(data).encode('utf-8'),
    headers={{'Content-Type': 'application/json'}},
    method='POST'
)
try:
    urllib.request.urlopen(req, timeout=2)
except:
    pass
"""
        
        # Run in background
        subprocess.Popen(
            [sys.executable, '-c', script],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        
        return True
        
    except Exception:
        return False

def test_server_health() -> Tuple[bool, Optional[str]]:
    """
    Quick health check with very short timeout.
    
    Returns:
        Tuple of (is_healthy, error_message)
    """
    server_url = get_server_url()
    
    try:
        req = urllib.request.Request(f"{server_url}/health", method='GET')
        with urllib.request.urlopen(req, timeout=0.5) as response:
            return response.status == 200, None
    except Exception as e:
        return False, str(e)

# Re-export original functions for compatibility
from utils.http_client import create_hook_event, send_tool_use_event, send_user_prompt_event

def send_event_to_server(event_data: Dict[str, Any], timeout: Optional[float] = None) -> bool:
    """
    Enhanced event sending with retry and async fallback.
    Compatible with original interface.
    """
    # Quick health check first
    is_healthy, _ = test_server_health()
    
    if not is_healthy:
        # Server appears down, use async send to avoid blocking
        return send_event_async(event_data)
    
    # Try synchronous send with retry
    success, error = send_event_with_retry(event_data)
    
    if not success and "timeout" in str(error):
        # On timeout, try async as last resort
        return send_event_async(event_data)
    
    return success