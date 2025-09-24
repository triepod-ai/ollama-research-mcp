#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "openai>=1.0.0",
#     "pyttsx3>=2.90",
#     "python-dotenv",
# ]
# ///
"""
Session Startup Notifier Hook

SINGLE PURPOSE: Send TTS notification for genuine new sessions with rate limiting.

- Only handles 'startup' session types
- 30-second rate limiting to prevent spam
- Simple TTS message formatting
- NO context loading, NO observability events, NO complex decisions
"""

import sys
import json
import os

# Add utils to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'utils'))

from session_helpers import get_project_name, is_rate_limited, update_rate_limit
from tts.coordinated_speak import notify_tts_coordinated


def format_startup_message(project_name: str) -> str:
    """Format simple startup message."""
    return f"AI agent ready for {project_name}"


def main():
    """Main startup notifier execution - single focused purpose."""
    try:
        # Read input data from stdin
        input_data = json.loads(sys.stdin.read())
        source = input_data.get('source', 'startup')
        
        # Only handle startup sessions
        if source != 'startup':
            print(f"Startup notifier skipped for {source} session", file=sys.stderr)
            return
        
        # Check rate limiting (30-second cooldown)
        if is_rate_limited('startup', cooldown_seconds=30):
            print("Startup notification rate limited (30s cooldown)", file=sys.stderr)
            return
        
        # Get project name and format message
        project_name = get_project_name()
        message = format_startup_message(project_name)
        
        # Send TTS notification
        notify_tts_coordinated(
            message=message,
            priority="normal",
            hook_type="session_startup",
            tool_name="SessionStartup"
        )
        
        # Update rate limit
        update_rate_limit('startup')
        
        print(f"Startup notification sent: {message}", file=sys.stderr)
        
    except Exception as e:
        print(f"Startup notifier error: {e}", file=sys.stderr)
        # Don't exit with error - TTS failure shouldn't break session start


if __name__ == "__main__":
    main()