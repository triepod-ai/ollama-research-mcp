#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.8"
# dependencies = [
#     "python-dotenv",
# ]
# ///

"""
Generic event sender hook for Claude Code.
Sends custom events to the observability server.
"""

import argparse
import json
import sys
from pathlib import Path
from utils.constants import ensure_session_log_dir
from utils.http_client import send_event_to_server, create_hook_event

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv is optional

import subprocess
import time


def extract_project_name_from_cwd(cwd: str) -> str:
    """Extract project name from current working directory path."""
    if not cwd:
        return "unknown-project"
    
    # Get the directory name from the path
    project_path = Path(cwd)
    project_name = project_path.name
    
    # Handle common patterns
    if project_name in ['', '.', '..']:
        return "unknown-project"
    
    # Clean up the project name
    project_name = project_name.replace('_', '-').replace(' ', '-').lower()
    
    return project_name


def create_rich_context_for_tts(input_data: dict, event_type: str) -> dict:
    """Create rich context for speak-ai-summary from hook input data."""
    try:
        # Extract core information
        tool_name = input_data.get('tool_name', 'Unknown')
        cwd = input_data.get('cwd', '')
        project_name = extract_project_name_from_cwd(cwd)
        
        # Create base rich context structure
        rich_context = {
            "tool_name": tool_name,
            "context": {},
            "metrics": {
                "severity": "normal",
                "duration_ms": 0,
                "success": True
            },
            "project_context": {
                "name": project_name,
                "path": cwd
            },
            "error_info": {
                "has_error": False,
                "error_message": ""
            },
            "summary": f"{tool_name} executed in {project_name}"
        }
        
        # Enrich context based on tool type and input
        tool_input = input_data.get('tool_input', {})
        
        if isinstance(tool_input, dict):
            # File operations
            if 'file_path' in tool_input:
                file_path = tool_input['file_path']
                rich_context["context"]["file_name"] = Path(file_path).name
                rich_context["context"]["file_type"] = Path(file_path).suffix.lstrip('.')
                rich_context["summary"] = f"Updated {Path(file_path).name} in {project_name}"
            
            # Command operations
            elif 'command' in tool_input:
                command = tool_input['command']
                rich_context["context"]["command_type"] = command.split()[0] if command else "command"
                rich_context["summary"] = f"Ran {rich_context['context']['command_type']} command in {project_name}"
            
            # Search operations
            elif 'pattern' in tool_input:
                pattern = tool_input['pattern']
                rich_context["context"]["search_pattern"] = pattern[:50]
                rich_context["summary"] = f"Searched for '{pattern[:20]}' in {project_name}"
            
            # MCP operations
            elif tool_name.startswith('mcp__'):
                server_parts = tool_name.split('__')
                if len(server_parts) >= 2:
                    server_name = server_parts[1]
                    rich_context["context"]["mcp_server"] = server_name
                    
                    # Extract operation details for common MCP operations
                    if 'collection_name' in tool_input:
                        collection = tool_input['collection_name']
                        rich_context["summary"] = f"Updated {server_name} collection '{collection}' in {project_name}"
                    else:
                        rich_context["summary"] = f"Completed {server_name} operation in {project_name}"
        
        # Handle user prompts
        if 'prompt' in input_data:
            prompt = input_data['prompt']
            rich_context["summary"] = f"New request in {project_name}: {prompt[:30]}..."
            rich_context["context"]["prompt_length"] = len(prompt)
        
        # Handle session events
        if event_type == "SessionStart":
            rich_context["summary"] = f"Started session in {project_name}"
            rich_context["metrics"]["severity"] = "notable"
        elif event_type == "Stop":
            rich_context["summary"] = f"Session completed in {project_name}"
            rich_context["metrics"]["severity"] = "notable"
        elif event_type == "SubagentStop":
            rich_context["summary"] = f"Sub-agent completed task in {project_name}"
            rich_context["metrics"]["severity"] = "normal"
        
        return rich_context
        
    except Exception as e:
        # If rich context creation fails, return minimal context
        return {
            "tool_name": input_data.get('tool_name', 'Unknown'),
            "summary": f"Operation completed in {extract_project_name_from_cwd(input_data.get('cwd', ''))}",
            "project_context": {"name": extract_project_name_from_cwd(input_data.get('cwd', ''))}
        }


def trigger_ai_tts(rich_context: dict) -> bool:
    """Trigger AI-powered TTS using speak-ai-summary with rich context."""
    try:
        # Path to speak-ai-summary script
        speak_ai_summary_path = "/home/bryan/bin/speak-app/speak-ai-summary"
        
        if not Path(speak_ai_summary_path).exists():
            return False
        
        # Convert rich context to JSON
        context_json = json.dumps(rich_context)
        
        # Execute speak-ai-summary in background (truly non-blocking)
        process = subprocess.Popen(
            [speak_ai_summary_path],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True
        )
        
        # Send rich context in a non-blocking way
        try:
            process.stdin.write(context_json)
            process.stdin.close()
        except:
            pass  # If stdin write fails, just continue
        
        # Don't wait for completion - let it run in background
        
        return True
        
    except Exception as e:
        # Log error but don't fail the hook
        print(f"AI TTS trigger failed: {e}", file=sys.stderr)
        return False


def log_event(session_id: str, input_data: dict) -> bool:
    """
    Log event data to local session directory.
    
    Args:
        session_id: The Claude session ID
        input_data: The event data from stdin
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Ensure session log directory exists
        log_dir = ensure_session_log_dir(session_id)
        log_file = log_dir / 'send_event.json'
        
        # Read existing log data or initialize empty list
        if log_file.exists():
            with open(log_file, 'r') as f:
                try:
                    log_data = json.load(f)
                except (json.JSONDecodeError, ValueError):
                    log_data = []
        else:
            log_data = []
        
        # Append the new event data
        log_data.append(input_data)
        
        # Write back to file with formatting
        with open(log_file, 'w') as f:
            json.dump(log_data, f, indent=2)
        
        return True
        
    except Exception as e:
        print(f"Error logging event: {e}", file=sys.stderr)
        return False


def main():
    """Main hook execution."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Send events to observability server')
    parser.add_argument('--source-app', default='claude-code', help='Source application name')
    parser.add_argument('--event-type', default='custom_event', help='Event type')
    parser.add_argument('--summarize', action='store_true', help='Generate summary from payload')
    parser.add_argument('--add-chat', action='store_true', help='Include chat data')
    args = parser.parse_args()
    
    try:
        # Read JSON input from stdin
        input_data = json.loads(sys.stdin.read())
        
        # Extract required fields
        session_id = input_data.get('session_id', 'unknown')
        # Use command-line event type if provided, otherwise check stdin data
        event_type = args.event_type if args.event_type != 'custom_event' else input_data.get('event_type', 'custom_event')
        
        # Extract hook event name from input data for more specific typing
        hook_event_name = input_data.get('hook_event_name', event_type)
        if hook_event_name and hook_event_name != event_type:
            event_type = hook_event_name
        
        payload = input_data.get('payload', input_data)
        
        # Extract optional fields
        summary = input_data.get('summary')
        chat = input_data.get('chat') if args.add_chat else None
        
        # Generate summary if requested AND trigger AI-powered TTS
        if args.summarize and not summary:
            # First, generate basic summary for server logging
            if 'tool_name' in input_data:
                tool_name = input_data.get('tool_name', 'Unknown')
                tool_input = input_data.get('tool_input', {})
                if isinstance(tool_input, dict):
                    if 'command' in tool_input:
                        summary = f"{tool_name}: {tool_input['command'][:50]}..."
                    elif 'file_path' in tool_input:
                        summary = f"{tool_name}: {tool_input['file_path']}"
                    elif 'pattern' in tool_input:
                        summary = f"{tool_name}: {tool_input['pattern']}"
                    else:
                        summary = f"{tool_name} executed"
                else:
                    summary = f"{tool_name} executed"
            elif 'prompt' in input_data:
                summary = f"User prompt: {input_data['prompt'][:50]}..."
            elif 'message' in input_data:
                summary = f"Notification: {input_data['message'][:50]}..."
            
            # Second, create rich context and trigger AI-powered TTS
            rich_context = create_rich_context_for_tts(input_data, event_type)
            if rich_context:
                trigger_ai_tts(rich_context)
        
        # Log to local file (for debugging/backup)
        local_logged = log_event(session_id, input_data)
        
        # Create properly formatted event for server
        event = create_hook_event(
            source_app=args.source_app,
            session_id=session_id,
            hook_event_type=event_type,
            payload=payload,
            chat=chat,
            summary=summary
        )
        
        # Send to observability server
        server_sent = send_event_to_server(event)
        
        # Log success/failure for debugging
        if local_logged and server_sent:
            print(f"Event '{event_type}' logged locally and sent to server for session {session_id}", file=sys.stderr)
        elif local_logged:
            print(f"Event '{event_type}' logged locally (server unavailable) for session {session_id}", file=sys.stderr)
        elif server_sent:
            print(f"Event '{event_type}' sent to server (local logging failed) for session {session_id}", file=sys.stderr)
        else:
            print(f"Both local logging and server communication failed for event '{event_type}' in session {session_id}", file=sys.stderr)
        
        # Always exit successfully - hook should not block execution
        sys.exit(0)
        
    except json.JSONDecodeError:
        # Handle JSON decode errors gracefully
        print("Invalid JSON input to send_event hook", file=sys.stderr)
        sys.exit(0)
    except Exception as e:
        # Handle any other errors gracefully
        print(f"Error in send_event hook: {e}", file=sys.stderr)
        sys.exit(0)


if __name__ == '__main__':
    main()
