#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""
PreToolUse notification hook with speak command integration.
Provides context-aware TTS notifications before tool execution.
Integrated with Multi-Agent Observability System.
"""

import json
import os
import sys
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

# Import observability system for event logging
try:
    from utils.tts.observability import should_speak_event_coordinated, EventCategory, EventPriority
    OBSERVABILITY_AVAILABLE = True
except ImportError:
    OBSERVABILITY_AVAILABLE = False

# Import coordinated TTS for queue-based notifications
try:
    from utils.tts.coordinated_speak import notify_tts_coordinated
    COORDINATED_TTS_AVAILABLE = True
except ImportError:
    COORDINATED_TTS_AVAILABLE = False

# Log directory for events
PROJECT_ROOT = Path(__file__).parent.parent.parent
LOG_DIR = PROJECT_ROOT / "logs" / "hooks" / "pre_tool_use"

def extract_tool_info(hook_input: str) -> tuple[str, Dict[str, Any]]:
    """Extract tool and parameter information from hook input."""
    try:
        data = json.loads(hook_input)
        tool = data.get('tool', 'unknown')
        parameters = data.get('parameters', {})
        return tool, parameters
    except Exception:
        return 'unknown', {}

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
        "Bash": "command execution",
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
    
    return tool_mapping.get(raw_tool_name, raw_tool_name.lower())

def detect_complex_operation(tool: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
    """Detect if this is a complex operation that needs special handling."""
    complexity_info = {
        "is_complex": False,
        "is_long_running": False,
        "is_risky": False,
        "estimated_duration": "quick",
        "risk_level": "low",
        "operation_type": "simple"
    }
    
    # Task tool is always complex (subagent delegation)
    if tool == 'Task':
        complexity_info.update({
            "is_complex": True,
            "is_long_running": True,
            "estimated_duration": "10-30 seconds",
            "operation_type": "subagent_delegation",
            "description": parameters.get('description', 'complex task')
        })
        return complexity_info
    
    # Multi-file operations are complex
    elif tool == 'MultiEdit':
        edits_count = len(parameters.get('edits', []))
        if edits_count > 5:
            complexity_info.update({
                "is_complex": True,
                "is_long_running": True,
                "estimated_duration": f"{edits_count * 2} seconds",
                "operation_type": "bulk_edit"
            })
    
    # Bash commands can be risky or long-running
    elif tool == 'Bash':
        command = parameters.get('command', '')
        
        # Risky commands
        risky_patterns = ['rm -rf', 'rm -r', 'del /f', 'format', 'dd if=', 'chmod -R 777', 
                         'curl | bash', 'wget | sh', ':(){:|:&};:', 'shutdown', 'reboot']
        for pattern in risky_patterns:
            if pattern in command.lower():
                complexity_info.update({
                    "is_risky": True,
                    "risk_level": "high",
                    "operation_type": "dangerous_command"
                })
                break
        
        # Long-running commands
        long_patterns = ['npm install', 'yarn install', 'pip install', 'apt-get', 'brew install',
                        'docker build', 'make', 'cargo build', 'mvn', 'gradle', 'webpack',
                        'pytest', 'npm test', 'yarn test']
        for pattern in long_patterns:
            if pattern in command.lower():
                complexity_info.update({
                    "is_long_running": True,
                    "estimated_duration": "30+ seconds",
                    "operation_type": "build_or_install"
                })
                break
    
    # Large file operations
    elif tool in ['Read', 'Edit', 'Write']:
        file_path = parameters.get('file_path', '')
        # Check if it's a large file by extension or path patterns
        large_file_patterns = ['.log', '.sql', '.csv', 'node_modules', 'dist/', 'build/']
        for pattern in large_file_patterns:
            if pattern in file_path:
                complexity_info["is_long_running"] = True
                complexity_info["estimated_duration"] = "5-10 seconds"
                break
    
    # Web operations can be slow
    elif tool in ['WebFetch', 'WebSearch']:
        complexity_info.update({
            "is_long_running": True,
            "estimated_duration": "3-10 seconds",
            "operation_type": "network_operation"
        })
    
    # MCP operations might be slow
    elif tool.startswith('mcp__'):
        # Memory operations can be complex
        if 'memory' in tool or 'qdrant' in tool or 'chroma' in tool:
            complexity_info.update({
                "is_complex": True,
                "is_long_running": True,
                "estimated_duration": "5-15 seconds",
                "operation_type": "memory_operation"
            })
        else:
            complexity_info["is_long_running"] = True
            complexity_info["estimated_duration"] = "3-10 seconds"
    
    return complexity_info

def generate_notification_message(tool: str, parameters: Dict[str, Any]) -> str:
    """Generate context-aware notification message based on tool and parameters."""
    
    # First check for complex operations
    complexity = detect_complex_operation(tool, parameters)
    
    # Special handling for Task tool (subagent delegation)
    if tool == 'Task':
        description = parameters.get('description', 'a task')
        prompt = parameters.get('prompt', '')
        
        # Try to identify the type of subagent from the prompt
        if 'code review' in prompt.lower() or 'review' in description.lower():
            return "Delegating to code reviewer agent for comprehensive analysis"
        elif 'debug' in prompt.lower() or 'error' in prompt.lower():
            return "Delegating to debugger agent to investigate the issue"
        elif 'test' in prompt.lower():
            return "Delegating to test runner agent"
        elif 'data' in prompt.lower() or 'sql' in prompt.lower():
            return "Delegating to data scientist agent for analysis"
        else:
            return f"Delegating complex task to specialized agent: {description[:50]}"
    
    # Add duration info for long-running operations
    duration_prefix = ""
    if complexity["is_long_running"]:
        duration_prefix = f"Starting {complexity['estimated_duration']} operation: "
    
    # Add warning for risky operations
    risk_prefix = ""
    if complexity["is_risky"]:
        risk_prefix = "⚠️ CAUTION: "
    
    base_message = ""
    
    if tool == 'Read':
        file_path = parameters.get('file_path', 'a file')
        filename = Path(file_path).name if file_path != 'a file' else 'a file'
        base_message = f"Claude is about to read {filename}"
    
    elif tool == 'Edit':
        file_path = parameters.get('file_path', 'a file')
        filename = Path(file_path).name if file_path != 'a file' else 'a file'
        base_message = f"Claude is about to edit {filename}"
    
    elif tool == 'Write':
        file_path = parameters.get('file_path', 'a new file')
        filename = Path(file_path).name if file_path != 'a new file' else 'a new file'
        base_message = f"Claude is creating {filename}"
    
    elif tool == 'MultiEdit':
        file_path = parameters.get('file_path', 'a file')
        filename = Path(file_path).name if file_path != 'a file' else 'a file'
        edits_count = len(parameters.get('edits', []))
        if edits_count > 10:
            base_message = f"Claude is making {edits_count} bulk changes to {filename}"
        else:
            base_message = f"Claude is making {edits_count} changes to {filename}"
    
    elif tool == 'Bash':
        command = parameters.get('command', 'a command')
        # Extract just the main command for brevity
        main_command = command.split()[0] if command.split() else 'command'
        
        # Context-aware messages for common commands
        if main_command in ['ls', 'dir']:
            base_message = "Claude is listing directory contents"
        elif main_command in ['cd']:
            base_message = "Claude is changing directories"
        elif main_command in ['chmod', 'chown']:
            base_message = "Claude is modifying file permissions"
        elif main_command in ['python3', 'python']:
            script_name = command.split()[1] if len(command.split()) > 1 else "a Python script"
            base_message = f"Claude is running {script_name}"
        elif main_command in ['npm', 'yarn']:
            subcommand = command.split()[1] if len(command.split()) > 1 else ""
            if subcommand == 'install':
                base_message = "Claude is installing dependencies"
            elif subcommand == 'test':
                base_message = "Claude is running the test suite"
            elif subcommand == 'build':
                base_message = "Claude is building the project"
            else:
                base_message = f"Claude is running {main_command} {subcommand}"
        elif main_command in ['git']:
            subcommand = command.split()[1] if len(command.split()) > 1 else ""
            if subcommand in ['commit', 'push']:
                base_message = f"Claude is performing git {subcommand}"
            else:
                base_message = "Claude is using Git"
        elif main_command in ['grep', 'find']:
            base_message = "Claude is searching for files or patterns"
        elif main_command in ['make', 'build']:
            base_message = "Claude is building the project"
        elif main_command in ['test', 'pytest']:
            base_message = "Claude is running tests"
        elif 'rm' in command:
            # Special handling for remove commands
            base_message = f"Claude is deleting files with: {command[:30]}"
        else:
            base_message = f"Claude is about to run {main_command}"
    
    elif tool == 'Grep':
        pattern = parameters.get('pattern', 'a pattern')
        base_message = f"Claude is searching for {pattern}"
    
    elif tool == 'LS':
        path = parameters.get('path', 'directory')
        dirname = Path(path).name if path != 'directory' else 'directory'
        base_message = f"Claude is listing contents of {dirname}"
    
    elif tool == 'Glob':
        pattern = parameters.get('pattern', 'files')
        base_message = f"Claude is finding files matching {pattern}"
    
    elif tool == 'TodoWrite':
        todos = parameters.get('todos', [])
        if todos:
            pending_count = sum(1 for t in todos if t.get('status') == 'pending')
            base_message = f"Claude is updating task list ({pending_count} pending tasks)"
        else:
            base_message = "Claude is updating the task list"
    
    elif tool == 'WebFetch':
        url = parameters.get('url', 'a website')
        domain = url.split('/')[2] if url.startswith('http') and len(url.split('/')) > 2 else 'a website'
        base_message = f"Claude is fetching content from {domain}"
    
    elif tool == 'WebSearch':
        query = parameters.get('query', 'information')
        base_message = f"Claude is searching the web for {query}"
    
    elif tool.startswith('mcp__'):
        # MCP tools with better context
        friendly_name = parse_mcp_tool_name(tool)
        
        # Add specific context for memory operations
        if 'store' in tool or 'save' in tool:
            base_message = f"Claude is storing data in {friendly_name}"
        elif 'retrieve' in tool or 'get' in tool or 'find' in tool:
            base_message = f"Claude is retrieving data from {friendly_name}"
        elif 'list' in tool:
            base_message = f"Claude is listing items in {friendly_name}"
        else:
            base_message = f"Claude is using {friendly_name}"
    
    else:
        friendly_name = parse_mcp_tool_name(tool)
        base_message = f"Claude is about to use {friendly_name}"
    
    # Combine prefixes with base message
    return f"{risk_prefix}{duration_prefix}{base_message}"

def should_notify(tool: str, parameters: Dict[str, Any]) -> bool:
    """Determine if this tool use should trigger a notification."""
    
    # Check complexity first - always notify for complex operations
    complexity = detect_complex_operation(tool, parameters)
    if complexity["is_complex"] or complexity["is_long_running"] or complexity["is_risky"]:
        return True
    
    # Always notify for Task tool (subagent delegation)
    if tool == 'Task':
        return True
    
    # Always notify for potentially dangerous operations
    high_risk_tools = ['Bash', 'Edit', 'Write', 'MultiEdit', 'WebFetch']
    if tool in high_risk_tools:
        return True
    
    # Notify for file operations
    file_tools = ['Read']
    if tool in file_tools:
        file_path = parameters.get('file_path', '')
        # Skip notifications for very common system files
        skip_files = ['/tmp/', '/var/tmp/', '.cache/', '__pycache__']
        if any(skip in file_path for skip in skip_files):
            return False
        return True
    
    # Notify for search operations only if they seem significant
    search_tools = ['Grep', 'Glob']
    if tool in search_tools:
        # Only notify for specific patterns or important searches
        pattern = parameters.get('pattern', '')
        if len(pattern) > 3:  # Skip very short patterns
            return True
        return False
    
    # Skip routine directory listings
    if tool == 'LS':
        return False
    
    # Always notify for MCP operations
    if tool.startswith('mcp__'):
        return True
    
    # Notify for web operations
    web_tools = ['WebFetch', 'WebSearch']
    if tool in web_tools:
        return True
    
    # Notify for task management
    if tool == 'TodoWrite':
        return True
    
    # Default: don't notify for unknown tools
    return False

def determine_priority(tool: str, parameters: Dict[str, Any]) -> str:
    """Determine the priority level for TTS notification based on complexity and risk."""
    
    # Get complexity information
    complexity = detect_complex_operation(tool, parameters)
    
    # Critical priority for risky operations
    if complexity["is_risky"] and complexity["risk_level"] == "high":
        return "error"  # Use error priority for critical warnings
    
    # High priority for complex or long-running operations
    if complexity["is_complex"] or (complexity["is_long_running"] and complexity["estimated_duration"] != "3-10 seconds"):
        return "important"
    
    # High priority for Task tool (subagent delegation)
    if tool == 'Task':
        return "important"
    
    # High priority for potentially dangerous operations
    if tool in ['Bash', 'Write', 'MultiEdit']:
        command = parameters.get('command', '')
        if tool == 'Bash' and any(dangerous in command.lower() for dangerous in ['rm', 'del', 'format', 'shutdown']):
            return "error"  # Escalate to error priority for very dangerous commands
        return "important"
    
    # Normal priority for most operations
    return "normal"

def determine_category(tool: str) -> str:
    """Determine the event category for observability."""
    
    if tool == 'Task':
        return "completion"  # Subagent delegation is a completion-type event
    elif tool in ['Bash']:
        return "command_execution"
    elif tool in ['Read', 'Write', 'Edit', 'MultiEdit', 'Glob', 'Grep']:
        return "file_operation"
    elif tool in ['WebFetch', 'WebSearch']:
        return "performance"  # Web operations might be slow
    elif tool.startswith('mcp__'):
        return "performance"  # MCP operations might be slow
    else:
        return "general"

def notify_tts(message: str, priority: str = "normal", tool_name: str = "") -> bool:
    """
    Standardized TTS notification using coordinated speak or fallback to direct speak.
    Follows LLM Integration Guide patterns for consistent voice notifications.
    """
    # Use coordinated TTS if available
    if COORDINATED_TTS_AVAILABLE:
        return notify_tts_coordinated(
            message=message,
            priority=priority,
            hook_type="pre_tool_use",
            tool_name=tool_name
        )
    
    # Fallback to direct speak command
    try:
        # Skip TTS if disabled
        if os.getenv('TTS_ENABLED', 'true').lower() != 'true':
            return False
        
        # Get engineer name for personalization
        engineer_name = os.getenv('ENGINEER_NAME', 'Developer')
        
        # Format message based on priority (following speak command patterns)
        if priority == "important":
            personalized_message = f"{engineer_name}, Important: {message}"
        elif priority == "error":
            personalized_message = f"{engineer_name}, Error: {message}"
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

def log_tool_event(tool: str, parameters: Dict[str, Any], should_notify_result: bool) -> None:
    """Log tool event to observability system."""
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        
        # Create daily log file
        log_file = LOG_DIR / f"pre_tool_use_{datetime.now().strftime('%Y%m%d')}.jsonl"
        
        log_entry = {
            "tool": tool,
            "parameters": parameters,
            "should_notify": should_notify_result,
            "timestamp": datetime.now().isoformat(),
            "project": "multi-agent-observability-system",
            "user": os.getenv("USER", "unknown"),
        }
        
        with open(log_file, "a") as f:
            f.write(json.dumps(log_entry) + "\n")
    except Exception:
        # Silently fail logging
        pass

def main():
    """Main hook execution."""
    
    # Read hook input from stdin
    try:
        hook_input = sys.stdin.read().strip()
        if not hook_input:
            sys.exit(0)
    except Exception:
        sys.exit(0)
    
    # Extract tool information
    tool, parameters = extract_tool_info(hook_input)
    
    # Determine if we should notify
    should_notify_result = should_notify(tool, parameters)
    
    # Log the event for observability
    log_tool_event(tool, parameters, should_notify_result)
    
    # Generate and send notification if needed
    if should_notify_result:
        message = generate_notification_message(tool, parameters)
        priority = determine_priority(tool, parameters)
        category = determine_category(tool)
        
        # Get complexity information for metadata
        complexity = detect_complex_operation(tool, parameters)
        
        # Use observability system if available for coordination
        if OBSERVABILITY_AVAILABLE:
            # Map priority to numeric values
            priority_map = {
                "error": 1,     # CRITICAL
                "important": 2, # HIGH
                "normal": 3     # MEDIUM
            }
            
            should_speak = should_speak_event_coordinated(
                message=message,
                priority=priority_map.get(priority, 3),
                category=category,
                hook_type="pre_tool_use",
                tool_name=tool,
                metadata={
                    "parameters": parameters,
                    "complexity": complexity,
                    "estimated_duration": complexity.get("estimated_duration", "unknown"),
                    "operation_type": complexity.get("operation_type", "simple")
                }
            )
            
            if should_speak:
                notify_tts(message, priority, tool)
        else:
            # Fallback to direct TTS
            notify_tts(message, priority, tool)
    
    # Always exit successfully (don't block tool execution)
    sys.exit(0)

if __name__ == '__main__':
    main()