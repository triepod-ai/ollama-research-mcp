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
Session Resume Detector Hook

SINGLE PURPOSE: Smart TTS notifications for meaningful resume sessions.

- Only handles 'resume' session types
- Checks if there's significant work context (modified files, project status)
- Sends contextual TTS message only when meaningful work is present
- NO context loading, NO observability events, NO startup handling
"""

import sys
import json
import os

# Add utils to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'utils'))

from session_helpers import get_project_name, get_project_status, get_git_status
from tts.coordinated_speak import notify_tts_coordinated


def should_notify_for_resume(project_status: str, git_info: dict) -> bool:
    """Determine if resume session has meaningful context worth notifying about."""
    modified_files = git_info["modified_count"]
    recent_commits = len(git_info["recent_commits"])
    has_project_status = bool(project_status)
    
    # Notify if there's active work or significant project context
    return modified_files > 5 or recent_commits > 0 or has_project_status


def format_resume_message(project_name: str, git_info: dict) -> str:
    """Format contextual resume message based on work state."""
    base_msg = f"Continuing work on {project_name}"
    
    context_hints = []
    
    if git_info["modified_count"] > 0:
        context_hints.append(f"{git_info['modified_count']} modified files")
    
    if len(git_info["recent_commits"]) > 0:
        context_hints.append(f"{len(git_info['recent_commits'])} recent commits")
    
    if context_hints:
        return f"{base_msg} - {', '.join(context_hints[:2])}"
    
    return base_msg


def main():
    """Main resume detector execution - single focused purpose."""
    try:
        # Read input data from stdin
        input_data = json.loads(sys.stdin.read())
        source = input_data.get('source', 'resume')
        
        # Only handle resume sessions
        if source != 'resume':
            print(f"Resume detector skipped for {source} session", file=sys.stderr)
            return
        
        # Load context to check if notification is warranted
        project_name = get_project_name()
        project_status = get_project_status()
        git_info = get_git_status()
        
        # Check if this resume session has meaningful context
        if not should_notify_for_resume(project_status, git_info):
            print("Resume notification skipped - no significant work context", file=sys.stderr)
            return
        
        # Format and send contextual message
        message = format_resume_message(project_name, git_info)
        
        notify_tts_coordinated(
            message=message,
            priority="normal",
            hook_type="session_resume",
            tool_name="SessionResume"
        )
        
        print(f"Resume notification sent: {message}", file=sys.stderr)
        
    except Exception as e:
        print(f"Resume detector error: {e}", file=sys.stderr)
        # Don't exit with error - TTS failure shouldn't break session start


if __name__ == "__main__":
    main()