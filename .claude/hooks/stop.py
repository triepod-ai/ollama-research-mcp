#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "python-dotenv",
# ]
# ///

"""
Enhanced stop hook for Claude Code with insightful summaries.
Provides personalized TTS announcement when tasks are completed.
"""

import json
import os
import sys
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

# Import utilities
from utils.constants import ensure_session_log_dir
from utils.http_client import send_event_to_server, create_hook_event

# Import coordinated TTS for queue-based notifications
try:
    from utils.tts.coordinated_speak import notify_tts_coordinated
    COORDINATED_TTS_AVAILABLE = True
except ImportError:
    COORDINATED_TTS_AVAILABLE = False

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv is optional


def analyze_session_activity(session_id: str) -> Dict[str, Any]:
    """
    Analyze recent session activity to generate a summary.
    
    Args:
        session_id: The Claude session ID
        
    Returns:
        Dictionary with analysis results
    """
    analysis = {
        "tools_used": set(),
        "files_modified": set(),
        "commands_run": [],
        "last_prompt": None,
        "key_actions": [],
        "test_results": None,
        "errors_encountered": False
    }
    
    try:
        # Get session log directory
        log_dir = Path.home() / ".claude" / "sessions" / session_id
        if not log_dir.exists():
            return analysis
        
        # Read pre_tool_use log for tool usage
        pre_tool_log = log_dir / "pre_tool_use.json"
        if pre_tool_log.exists():
            with open(pre_tool_log, 'r') as f:
                try:
                    events = json.load(f)
                    # Get last 10 events for analysis
                    recent_events = events[-10:] if len(events) > 10 else events
                    
                    for event in recent_events:
                        tool_name = event.get("tool_name", "")
                        tool_input = event.get("tool_input", {})
                        
                        analysis["tools_used"].add(tool_name)
                        
                        # Track file modifications
                        if tool_name in ["Write", "Edit", "MultiEdit"]:
                            file_path = tool_input.get("file_path")
                            if file_path:
                                # Store relative path to preserve directory info
                                path_obj = Path(file_path)
                                if "hooks" in path_obj.parts:
                                    # Keep hook directory info
                                    analysis["files_modified"].add(f"hooks/{path_obj.name}")
                                else:
                                    analysis["files_modified"].add(path_obj.name)
                        
                        # Track commands
                        elif tool_name == "Bash":
                            command = tool_input.get("command", "")
                            if command:
                                analysis["commands_run"].append(command[:50])
                                # Check for test commands
                                if any(test_cmd in command.lower() for test_cmd in ["npm test", "pytest", "jest", "test"]):
                                    analysis["test_results"] = "tests run"
                        
                        # Track key actions
                        elif tool_name == "TodoWrite":
                            analysis["key_actions"].append("managed tasks")
                        elif tool_name == "WebSearch":
                            analysis["key_actions"].append("searched web")
                        elif tool_name == "Task":
                            analysis["key_actions"].append("delegated to sub-agent")
                
                except (json.JSONDecodeError, ValueError):
                    pass
        
        # Read user_prompt_submit log for last prompt
        prompt_log = log_dir / "user_prompt_submit.json"
        if prompt_log.exists():
            with open(prompt_log, 'r') as f:
                try:
                    prompts = json.load(f)
                    if prompts:
                        last_prompt_data = prompts[-1]
                        analysis["last_prompt"] = last_prompt_data.get("prompt", "")[:100]
                except (json.JSONDecodeError, ValueError):
                    pass
        
        # Read post_tool_use log for errors
        post_tool_log = log_dir / "post_tool_use.json"
        if post_tool_log.exists():
            with open(post_tool_log, 'r') as f:
                try:
                    events = json.load(f)
                    for event in events[-5:]:  # Check last 5 results
                        result = event.get("tool_result", {})
                        if isinstance(result, dict) and result.get("error"):
                            analysis["errors_encountered"] = True
                            break
                except (json.JSONDecodeError, ValueError):
                    pass
        
    except Exception as e:
        print(f"Error analyzing session: {e}", file=sys.stderr)
    
    return analysis


def generate_summary(analysis: Dict[str, Any]) -> str:
    """
    Generate a brief, insightful summary from session analysis.
    
    Args:
        analysis: The session analysis results
        
    Returns:
        A brief summary string
    """
    # Start with the main action based on tools used
    tools = analysis["tools_used"]
    files = analysis["files_modified"]
    
    # Determine primary action
    if not tools:
        return "working on your request"
    
    # UI/Component work
    if "Magic" in tools or any("component" in str(f).lower() or ".vue" in str(f) or ".tsx" in str(f) for f in files):
        component_count = len([f for f in files if any(ext in str(f) for ext in [".vue", ".tsx", ".jsx"])])
        if component_count > 1:
            return f"building {component_count} UI components"
        elif component_count == 1:
            return "creating a UI component"
        else:
            return "working on the UI"
    
    # Documentation work
    if any(".md" in str(f) for f in files) or "updating documentation" in str(analysis.get("last_prompt", "")).lower():
        doc_count = len([f for f in files if ".md" in str(f)])
        if doc_count > 1:
            return f"updating {doc_count} docs"
        else:
            return "updating documentation"
    
    # Testing work
    if analysis["test_results"]:
        return "running tests"
    
    # Hook/Script work
    if any((".py" in str(f) and "hook" in str(f).lower()) or "hooks/" in str(f) for f in files):
        hook_count = len([f for f in files if (".py" in str(f) and "hook" in str(f).lower()) or "hooks/" in str(f)])
        if hook_count > 1:
            return f"updating {hook_count} hooks"
        else:
            return "updating hooks"
    
    # Configuration work
    if any(config_file in str(f) for f in files for config_file in [".json", ".yml", ".yaml", ".env"]):
        return "updating configuration"
    
    # Analysis work
    if "Read" in tools and "Grep" in tools and not files:
        return "analyzing your code"
    
    # File editing work
    if files:
        # Check if this is related to a specific request
        if analysis.get("last_prompt"):
            prompt_lower = analysis["last_prompt"].lower()
            if "fix" in prompt_lower or "error" in prompt_lower:
                return "fixing issues"
        
        if len(files) > 3:
            return f"updating {len(files)} files"
        elif len(files) == 1:
            file_name = str(list(files)[0])
            # Shorten long file names
            if len(file_name) > 20:
                file_name = f"...{file_name[-17:]}"
            return f"editing {file_name}"
        else:
            return "making changes"
    
    # Command execution
    if analysis["commands_run"]:
        if any("install" in cmd for cmd in analysis["commands_run"]):
            return "installing packages"
        elif any("build" in cmd for cmd in analysis["commands_run"]):
            return "building your project"
        else:
            return "running commands"
    
    # Web/Research work
    if "WebSearch" in tools or "WebFetch" in tools:
        return "researching information"
    
    # Task delegation
    if "Task" in tools:
        return "delegating tasks"
    
    # Planning work
    if "TodoWrite" in tools:
        return "organizing tasks"
    
    # Fallback based on last prompt
    if analysis.get("last_prompt"):
        prompt_lower = analysis["last_prompt"].lower()
        # Extract key action words for more natural summaries
        if "design" in prompt_lower:
            return "designing your solution"
        elif "implement" in prompt_lower:
            return "implementing features"
        elif "fix" in prompt_lower or "error" in prompt_lower:
            return "fixing issues"
        elif "analyze" in prompt_lower:
            return "analyzing requirements"
        elif "create" in prompt_lower or "build" in prompt_lower:
            return "building your solution"
        elif "update" in prompt_lower or "modify" in prompt_lower:
            return "making updates"
        elif "test" in prompt_lower:
            return "testing functionality"
        elif "document" in prompt_lower:
            return "writing documentation"
    
    # Generic fallback
    return "completing your request"


def notify_tts(message: str, priority: str = "normal") -> bool:
    """
    Send TTS notification using coordinated speak or fallback to direct speak.
    
    Args:
        message: The message to speak
        priority: Priority level for the message
        
    Returns:
        True if successful, False otherwise
    """
    # Format the completion message before checking coordination
    engineer_name = os.getenv('ENGINEER_NAME', 'Developer')
    formatted_message = f"I have finished {message}"
    
    # Use coordinated TTS if available
    if COORDINATED_TTS_AVAILABLE:
        # The coordinated function handles personalization internally
        return notify_tts_coordinated(
            message=formatted_message,
            priority=priority,
            hook_type="stop"
        )
    
    # Fallback to direct speak command
    try:
        # Skip TTS if disabled
        if os.getenv('TTS_ENABLED', 'true').lower() != 'true':
            return False
        
        # Format the completion message with personalization
        personalized_message = f"{engineer_name}, {formatted_message}"
        
        # Use speak command (non-blocking)
        subprocess.Popen(
            ['speak', personalized_message],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        
        return True
        
    except Exception:
        # Silently fail - don't disrupt the hook
        return False


def main():
    """Main entry point for stop hook."""
    try:
        # Read JSON input from stdin
        input_data = json.loads(sys.stdin.read())
        
        # Extract session information
        session_id = input_data.get('session_id', 'unknown')
        
        # Analyze session activity
        analysis = analyze_session_activity(session_id)
        
        # Generate summary
        summary = generate_summary(analysis)
        
        # Send TTS notification
        tts_sent = notify_tts(summary)
        
        # Prepare event data
        event_data = {
            "summary": summary,
            "tools_used": list(analysis["tools_used"]),
            "files_modified": list(analysis["files_modified"]),
            "errors_encountered": analysis["errors_encountered"],
            "tts_sent": tts_sent
        }
        
        # Create hook event for observability server
        event = create_hook_event(
            source_app="multi-agent-observability-system",
            session_id=session_id,
            hook_event_type="Stop",
            payload=event_data,
            summary=f"Session completed: {summary}"
        )
        
        # Send to observability server
        server_sent = send_event_to_server(event)
        
        # Log status
        if server_sent:
            print(f"Stop event sent to server: {summary}", file=sys.stderr)
        else:
            print(f"Stop event (server unavailable): {summary}", file=sys.stderr)
        
        # Always exit successfully
        sys.exit(0)
        
    except json.JSONDecodeError:
        # Handle JSON decode errors gracefully
        sys.exit(0)
    except Exception as e:
        # Log error but don't fail
        print(f"Error in stop hook: {e}", file=sys.stderr)
        sys.exit(0)


if __name__ == '__main__':
    main()