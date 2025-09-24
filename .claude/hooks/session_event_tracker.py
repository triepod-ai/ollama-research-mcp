#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "requests>=2.28.0",
#     "python-dotenv",
# ]
# ///
"""
Session Event Tracker Hook

SINGLE PURPOSE: Send observability events for all session types.

- Always sends event to observability server (all session types need tracking)
- Simple event payload creation
- NO TTS notifications, NO context loading, NO rate limiting
- Used for: startup, resume, clear (observability needs all data)
"""

import sys
import json
import os
from datetime import datetime

# Add utils to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'utils'))

from session_helpers import get_project_name, get_project_status, get_git_status
from constants import ensure_session_log_dir
from http_client import send_event_to_server


def create_session_event(session_id: str, source: str, project_name: str) -> dict:
    """Create simple session tracking event."""
    return {
        "source_app": project_name,
        "session_id": session_id,
        "hook_event_type": "SessionTracking",
        "timestamp": datetime.now().isoformat(),
        "payload": {
            "source": source,
            "project_name": project_name,
            "event_purpose": "session_tracking"
        }
    }


def main():
    """Main event tracker execution - single focused purpose."""
    try:
        # Read input data from stdin
        input_data = json.loads(sys.stdin.read())
        session_id = input_data.get('session_id', 'unknown')
        source = input_data.get('source', 'startup')
        
        # Ensure session log directory exists
        ensure_session_log_dir(session_id)
        
        # Get project name
        project_name = get_project_name()
        
        # Create and send tracking event
        event = create_session_event(session_id, source, project_name)
        send_event_to_server(event)
        
        print(f"Session tracking event sent: {source} for {project_name}", file=sys.stderr)
        
    except Exception as e:
        print(f"Event tracker error: {e}", file=sys.stderr)
        # Don't exit with error - event tracking failure shouldn't break session start


if __name__ == "__main__":
    main()