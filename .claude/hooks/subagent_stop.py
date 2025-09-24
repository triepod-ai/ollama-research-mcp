#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "python-dotenv",
#     "redis>=4.0.0",
#     "requests>=2.28.0",
# ]
# ///

import argparse
import json
import os
import sys
import subprocess
import re
import requests
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional
from utils.constants import ensure_session_log_dir
from utils.relationship_tracker import (
    update_relationship_completion, notify_parent_completion, cleanup_spawn_markers
)
from utils.agent_naming_service import generate_agent_name

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv is optional

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

# Import coordinated TTS for queue-based notifications
try:
    from utils.tts.coordinated_speak import notify_tts_coordinated
    COORDINATED_TTS_AVAILABLE = True
except ImportError:
    COORDINATED_TTS_AVAILABLE = False

# Import observability system for event logging
try:
    from utils.tts.observability import should_speak_event_coordinated
    OBSERVABILITY_AVAILABLE = True
except ImportError:
    OBSERVABILITY_AVAILABLE = False


def get_agent_id_from_start(session_id: str) -> Optional[str]:
    """Try to retrieve the agent ID from the start hook's temporary file."""
    try:
        log_dir = ensure_session_log_dir(session_id)
        # Look for agent ID files
        for file in log_dir.glob("current_agent_*.txt"):
            with open(file, 'r') as f:
                agent_id = f.read().strip()
            # Clean up the temporary file
            file.unlink(missing_ok=True)
            return agent_id
    except Exception:
        pass
    return None


def extract_agent_name_from_transcript(transcript_path: str) -> Optional[str]:
    """Extract agent name from transcript file by analyzing recent messages."""
    try:
        if not os.path.exists(transcript_path):
            return None
            
        with open(transcript_path, 'r') as f:
            lines = f.readlines()
        
        # Look at the last 10 lines for agent invocations
        recent_lines = lines[-10:] if len(lines) > 10 else lines
        
        for line in reversed(recent_lines):
            try:
                data = json.loads(line.strip())
                message_content = ""
                
                # Extract content from various message structures
                if 'message' in data:
                    if 'content' in data['message']:
                        if isinstance(data['message']['content'], list):
                            for item in data['message']['content']:
                                if isinstance(item, dict):
                                    # Task tool invocation
                                    if item.get('name') == 'Task' and 'input' in item:
                                        input_data = item['input']
                                        if 'subagent_type' in input_data:
                                            return input_data['subagent_type']
                                    
                                    # Text content
                                    if 'text' in item:
                                        message_content += item['text'] + " "
                                    
                                    # Tool result content
                                    if item.get('type') == 'tool_result' and 'content' in item:
                                        if isinstance(item['content'], str):
                                            message_content += item['content'] + " "
                        elif isinstance(data['message']['content'], str):
                            message_content = data['message']['content']
                
                # Look for @-mention patterns
                at_mentions = re.findall(r'@([a-z0-9-]+(?:-[a-z0-9]+)*)', message_content.lower())
                if at_mentions:
                    # Return the most specific agent name (longest)
                    return max(at_mentions, key=len)
                
                # Look for "Use X agent" or "Ask X to" patterns
                agent_patterns = [
                    r'use\s+(?:the\s+)?([a-z0-9-]+(?:-[a-z0-9]+)*)\s+(?:sub)?agent',
                    r'ask\s+([a-z0-9-]+(?:-[a-z0-9]+)*)\s+to',
                    r'([a-z0-9-]+(?:-[a-z0-9]+)*)\s+(?:sub)?agent\s+to',
                    r'invoke\s+(?:the\s+)?([a-z0-9-]+(?:-[a-z0-9]+)*)\s+(?:sub)?agent'
                ]
                
                for pattern in agent_patterns:
                    matches = re.findall(pattern, message_content.lower())
                    if matches:
                        return matches[0]
                        
            except (json.JSONDecodeError, KeyError, TypeError):
                continue
                
    except Exception:
        pass
    
    return None


def extract_tools_from_transcript(transcript_path: str) -> list:
    """Extract tools used from recent transcript entries."""
    tools_used = set()
    
    try:
        if not os.path.exists(transcript_path):
            return []
            
        with open(transcript_path, 'r') as f:
            lines = f.readlines()
        
        # Look at the last 20 lines for tool usage
        recent_lines = lines[-20:] if len(lines) > 20 else lines
        
        for line in reversed(recent_lines):
            try:
                data = json.loads(line.strip())
                
                # Check for tool usage in message content
                if 'message' in data and 'content' in data['message']:
                    content = data['message']['content']
                    
                    if isinstance(content, list):
                        for item in content:
                            if isinstance(item, dict) and 'name' in item:
                                tools_used.add(item['name'])
                            elif isinstance(item, dict) and 'type' in item:
                                if item['type'] == 'tool_use' and 'name' in item:
                                    tools_used.add(item['name'])
                                    
                # Check system messages for tool completion
                if data.get('type') == 'system' and 'content' in data:
                    content = data['content']
                    # Look for patterns like "Read" completed, "Bash" completed, etc.
                    tool_pattern = r'\b([A-Z][a-zA-Z]+)\b.*completed'
                    matches = re.findall(tool_pattern, content)
                    tools_used.update(matches)
                    
            except (json.JSONDecodeError, KeyError, TypeError):
                continue
                
    except Exception:
        pass
    
    return list(tools_used)


def extract_subagent_info(input_data: Dict[str, Any]) -> Dict[str, Any]:
    """Extract comprehensive information about the subagent execution."""
    info = {
        "agent_id": None,
        "agent_name": "unknown agent",
        "agent_type": "generic",
        "task_description": "",
        "duration": None,
        "duration_ms": 0,
        "result_summary": "",
        "error_occurred": False,
        "status": "success",
        "files_affected": 0,
        "tests_run": 0,
        "tools_used": [],
        "tool_calls": {},
        "token_usage": {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "estimated_cost": 0.0
        },
        "success_indicators": [],
        "performance_metrics": {},
        "code_reviewed": False,
        "output_metrics": {
            "files_created": 0,
            "files_modified": 0,
            "lines_added": 0,
            "lines_removed": 0,
            "tests_passed": 0,
            "tests_failed": 0
        }
    }
    
    # Enhanced agent name extraction with multiple strategies
    agent_name = None
    
    # Strategy 1: Direct field extraction
    agent_fields = ['agent_name', 'subagent_name', 'subagent_type', 'agent', 'name', 'type']
    for field in agent_fields:
        if field in input_data and input_data[field]:
            agent_name = input_data[field]
            break
    
    # Strategy 2: Extract from transcript if available
    if not agent_name or agent_name == "unknown":
        transcript_path = input_data.get('transcript_path')
        if transcript_path:
            extracted_name = extract_agent_name_from_transcript(transcript_path)
            if extracted_name:
                agent_name = extracted_name
                
            # Also extract tools used from transcript
            transcript_tools = extract_tools_from_transcript(transcript_path)
            if transcript_tools:
                info['tools_used'].extend(transcript_tools)
    
    # Strategy 3: Parse from task description or prompt
    if not agent_name or agent_name == "unknown":
        desc_text = ""
        desc_fields = ['task_description', 'description', 'task', 'prompt']
        for field in desc_fields:
            if field in input_data and input_data[field]:
                desc_text = str(input_data[field]).lower()
                break
        
        if desc_text:
            # Look for agent patterns in description
            agent_patterns = [
                r'@([a-z0-9-]+(?:-[a-z0-9]+)*)',
                r'use\s+(?:the\s+)?([a-z0-9-]+(?:-[a-z0-9]+)*)\s+(?:sub)?agent',
                r'([a-z0-9-]+(?:-[a-z0-9]+)*)\s+(?:sub)?agent\s+to'
            ]
            
            for pattern in agent_patterns:
                matches = re.findall(pattern, desc_text)
                if matches:
                    agent_name = matches[0]
                    break
    
    # Set the final agent name
    if agent_name:
        info['agent_name'] = agent_name
    else:
        # Last fallback: try to derive from any string fields
        for key, value in input_data.items():
            if isinstance(value, str) and len(value) > 0 and len(value) < 50:
                # Check if it looks like an agent name
                if re.match(r'^[a-z0-9-]+(?:-[a-z0-9]+)*$', value.lower()):
                    info['agent_name'] = value.lower()
                    break
    
    # Generate memorable display name using the naming service
    context = info.get('task_description', '') or ''
    session_id = input_data.get('session_id', '')
    info['display_name'] = generate_agent_name(info['agent_type'], context, session_id)
    
    # Get task description
    desc_fields = ['task_description', 'description', 'task', 'prompt']
    for field in desc_fields:
        if field in input_data and input_data[field]:
            info['task_description'] = str(input_data[field])[:100]  # Limit length
            break
    
    # Get duration if available
    if 'duration' in input_data:
        info['duration'] = input_data['duration']
        info['duration_ms'] = int(input_data['duration'] * 1000)
    elif 'start_time' in input_data and 'end_time' in input_data:
        try:
            start = datetime.fromisoformat(input_data['start_time'])
            end = datetime.fromisoformat(input_data['end_time'])
            info['duration'] = (end - start).total_seconds()
            info['duration_ms'] = int((end - start).total_seconds() * 1000)
        except:
            pass
    
    # Enhanced agent type classification with more specific patterns
    agent_name_lower = info['agent_name'].lower()
    
    # Analysis and data processing agents
    if 'screenshot' in agent_name_lower or 'analyzer' in agent_name_lower or 'analysis' in agent_name_lower:
        info['agent_type'] = 'analyzer'
    elif 'data' in agent_name_lower or 'metrics' in agent_name_lower or 'statistics' in agent_name_lower:
        info['agent_type'] = 'data-processor'
    
    # Development and debugging agents
    elif 'debug' in agent_name_lower or 'troubleshoot' in agent_name_lower or 'fix' in agent_name_lower:
        info['agent_type'] = 'debugger'
    elif 'build' in agent_name_lower or 'compile' in agent_name_lower or 'package' in agent_name_lower:
        info['agent_type'] = 'builder'
    elif 'deploy' in agent_name_lower or 'release' in agent_name_lower or 'publish' in agent_name_lower:
        info['agent_type'] = 'deployer'
    
    # Quality and testing agents
    elif 'review' in agent_name_lower or 'quality' in agent_name_lower or 'audit' in agent_name_lower:
        info['agent_type'] = 'reviewer'
    elif 'test' in agent_name_lower or 'validate' in agent_name_lower or 'verify' in agent_name_lower:
        info['agent_type'] = 'tester'
    elif 'lint' in agent_name_lower or 'format' in agent_name_lower or 'style' in agent_name_lower:
        info['agent_type'] = 'linter'
    
    # Documentation and content agents
    elif 'document' in agent_name_lower or 'write' in agent_name_lower or 'author' in agent_name_lower:
        info['agent_type'] = 'writer'
    elif 'translate' in agent_name_lower or 'localize' in agent_name_lower:
        info['agent_type'] = 'translator'
    elif 'lesson' in agent_name_lower or 'generator' in agent_name_lower or 'create' in agent_name_lower:
        info['agent_type'] = 'generator'
    
    # System and infrastructure agents
    elif 'performance' in agent_name_lower or 'optimize' in agent_name_lower or 'speed' in agent_name_lower:
        info['agent_type'] = 'optimizer'
    elif 'security' in agent_name_lower or 'scanner' in agent_name_lower or 'vulnerability' in agent_name_lower:
        info['agent_type'] = 'security'
    elif 'monitor' in agent_name_lower or 'watch' in agent_name_lower or 'observe' in agent_name_lower:
        info['agent_type'] = 'monitor'
    elif 'config' in agent_name_lower or 'setup' in agent_name_lower or 'install' in agent_name_lower:
        info['agent_type'] = 'configurator'
    
    # Data and context management agents
    elif 'session' in agent_name_lower or 'context' in agent_name_lower or 'state' in agent_name_lower:
        info['agent_type'] = 'context'
    elif 'git' in agent_name_lower or 'collector' in agent_name_lower or 'gather' in agent_name_lower:
        info['agent_type'] = 'collector'
    elif 'cache' in agent_name_lower or 'store' in agent_name_lower or 'save' in agent_name_lower:
        info['agent_type'] = 'storage'
    elif 'search' in agent_name_lower or 'find' in agent_name_lower or 'query' in agent_name_lower:
        info['agent_type'] = 'searcher'
    
    # API and integration agents
    elif 'api' in agent_name_lower or 'endpoint' in agent_name_lower or 'service' in agent_name_lower:
        info['agent_type'] = 'api-handler'
    elif 'sync' in agent_name_lower or 'integrate' in agent_name_lower or 'connect' in agent_name_lower:
        info['agent_type'] = 'integrator'
    
    # UI and frontend agents
    elif 'ui' in agent_name_lower or 'frontend' in agent_name_lower or 'component' in agent_name_lower:
        info['agent_type'] = 'ui-developer'
    elif 'design' in agent_name_lower or 'layout' in agent_name_lower or 'style' in agent_name_lower:
        info['agent_type'] = 'designer'
    
    # Machine learning and AI agents
    elif 'ml' in agent_name_lower or 'model' in agent_name_lower or 'train' in agent_name_lower:
        info['agent_type'] = 'ml-engineer'
    elif 'predict' in agent_name_lower or 'classify' in agent_name_lower or 'recommend' in agent_name_lower:
        info['agent_type'] = 'predictor'
    
    # Database and data management agents
    elif 'database' in agent_name_lower or 'db' in agent_name_lower or 'sql' in agent_name_lower:
        info['agent_type'] = 'database-admin'
    elif 'migrate' in agent_name_lower or 'backup' in agent_name_lower or 'restore' in agent_name_lower:
        info['agent_type'] = 'data-manager'
    
    # Default fallback - only if no patterns match
    # This should rarely happen with the comprehensive patterns above
    
    # Extract tools used if available (deduplicate with transcript tools)
    if 'tools_used' in input_data and isinstance(input_data['tools_used'], list):
        info['tools_used'].extend(input_data['tools_used'])
    elif 'tools' in input_data and isinstance(input_data['tools'], list):
        info['tools_used'].extend(input_data['tools'])
    
    # Deduplicate tools list
    info['tools_used'] = list(set(info['tools_used']))
    
    # Extract token usage if available
    if 'token_usage' in input_data:
        if isinstance(input_data['token_usage'], dict):
            info['token_usage'] = {
                "input_tokens": input_data['token_usage'].get('input_tokens', 0),
                "output_tokens": input_data['token_usage'].get('output_tokens', 0),
                "total_tokens": input_data['token_usage'].get('total_tokens', 0),
                "estimated_cost": input_data['token_usage'].get('estimated_cost', 0.0)
            }
        elif isinstance(input_data['token_usage'], (int, float)):
            total = int(input_data['token_usage'])
            info['token_usage']['total_tokens'] = total
            # Estimate cost based on typical pricing (adjust as needed)
            info['token_usage']['estimated_cost'] = total * 0.000002
    
    # Count tool calls if available
    if 'tool_calls' in input_data and isinstance(input_data['tool_calls'], dict):
        info['tool_calls'] = input_data['tool_calls']
    elif info['tools_used']:
        # Create tool call counts from tools_used list
        for tool in info['tools_used']:
            info['tool_calls'][tool] = info['tool_calls'].get(tool, 0) + 1
    
    # Analyze result/output for comprehensive summary information
    result_fields = ['result', 'output', 'response', 'stdout']
    for field in result_fields:
        if field in input_data and input_data[field]:
            result = str(input_data[field]).lower()
            
            # Check for errors
            error_indicators = ['error', 'failed', 'exception', 'traceback', 'stderr']
            if any(error in result for error in error_indicators):
                info['error_occurred'] = True
                info['status'] = 'failure'
            
            # Extract test information
            test_patterns = [
                r'(\d+)\s*test[s]?\s*(pass|passed|ran|executed)',
                r'test[s]?\s*passed:\s*(\d+)',
                r'(\d+)\s*passing'
            ]
            for pattern in test_patterns:
                test_match = re.search(pattern, result)
                if test_match:
                    info['tests_run'] = int(test_match.group(1))
                    break
            
            # Check for file operations
            file_patterns = [
                r'(\d+)\s*file[s]?\s*(modified|changed|updated|created)',
                r'(modified|created|updated):\s*(\d+)\s*file[s]?',
                r'(\d+)\s*file[s]?\s*processed'
            ]
            for pattern in file_patterns:
                file_match = re.search(pattern, result)
                if file_match:
                    try:
                        info['files_affected'] = int(file_match.group(1) if file_match.group(1).isdigit() else file_match.group(2))
                    except (IndexError, ValueError):
                        pass
                    break
            
            # Check for code review completion
            review_indicators = ['review complete', 'review finished', 'analysis complete', 'scan complete']
            if any(indicator in result for indicator in review_indicators):
                info['code_reviewed'] = True
            
            # Extract success indicators
            success_patterns = ['completed successfully', 'finished successfully', 'passed', 'success']
            info['success_indicators'] = [indicator for indicator in success_patterns if indicator in result]
            
            # Extract performance metrics
            perf_patterns = {
                'response_time': r'response time:\s*([\d.]+)\s*(ms|seconds?)',
                'memory_usage': r'memory usage:\s*([\d.]+)\s*(mb|kb|gb)',
                'lines_processed': r'processed\s*(\d+)\s*lines?',
                'items_processed': r'processed\s*(\d+)\s*items?'
            }
            
            for metric, pattern in perf_patterns.items():
                match = re.search(pattern, result, re.IGNORECASE)
                if match:
                    try:
                        value = float(match.group(1))
                        unit = match.group(2) if len(match.groups()) > 1 else ''
                        info['performance_metrics'][metric] = {'value': value, 'unit': unit}
                    except (ValueError, IndexError):
                        pass
            
            # Get a brief summary
            if len(result) > 50:
                # Try to find a summary line
                summary_patterns = [
                    r'summary:\s*(.{1,150})',
                    r'result:\s*(.{1,150})',
                    r'completed:\s*(.{1,150})',
                    r'finished:\s*(.{1,150})',
                    r'analysis:\s*(.{1,150})'
                ]
                for pattern in summary_patterns:
                    match = re.search(pattern, result, re.IGNORECASE)
                    if match:
                        info['result_summary'] = match.group(1).strip()
                        break
                
                # If no structured summary found, take first meaningful line
                if not info['result_summary']:
                    lines = result.split('\n')
                    for line in lines:
                        line = line.strip()
                        if len(line) > 20 and not line.startswith(('debug:', 'info:', 'warning:')):
                            info['result_summary'] = line[:150]
                            break
    
    return info

def generate_context_rich_message(info: Dict[str, Any]) -> str:
    """Generate a context-rich announcement based on subagent information."""
    
    # Use display name if available, otherwise use agent name
    display_name = info.get('display_name', info['agent_name'])
    agent_name = info['agent_name'].lower()
    
    # Base message
    if 'code review' in agent_name or 'reviewer' in agent_name:
        if info['error_occurred']:
            message = "Code review found issues that need attention"
        elif info['files_affected'] > 0:
            message = f"Code review completed for {info['files_affected']} files"
        else:
            message = "Code review completed successfully"
    
    elif 'test' in agent_name or 'qa' in agent_name:
        if info['tests_run'] > 0:
            if info['error_occurred']:
                message = f"Test run completed with failures: {info['tests_run']} tests"
            else:
                message = f"All {info['tests_run']} tests passed"
        else:
            message = "Test agent completed"
    
    elif 'debug' in agent_name:
        if info['error_occurred']:
            message = "Debugger found and fixed issues"
        else:
            message = "Debugging completed, no issues found"
    
    elif 'data' in agent_name or 'analyst' in agent_name:
        message = "Data analysis completed"
        if info['result_summary']:
            message += f": {info['result_summary'][:50]}"
    
    else:
        # Generic completion message
        if info['task_description']:
            task = info['task_description'][:50]
            message = f"Agent completed: {task}"
        else:
            message = f"{display_name} completed successfully"
    
    # Add duration if available
    if info['duration']:
        if info['duration'] < 60:
            duration_str = f"{int(info['duration'])} seconds"
        else:
            duration_str = f"{info['duration']/60:.1f} minutes"
        message += f" in {duration_str}"
    
    return message

def notify_tts(message: str, priority: str = "normal") -> bool:
    """Send TTS notification using coordinated system or fallback."""
    
    # Use coordinated TTS if available
    if COORDINATED_TTS_AVAILABLE:
        return notify_tts_coordinated(
            message=message,
            priority=priority,
            hook_type="subagent_stop",
            tool_name="subagent"
        )
    
    # Fallback to direct speak command
    try:
        # Skip TTS if disabled
        if os.getenv('TTS_ENABLED', 'true').lower() != 'true':
            return False
        
        # Get engineer name for personalization
        engineer_name = os.getenv('ENGINEER_NAME', 'Developer')
        personalized_message = f"{engineer_name}, {message}"
        
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

def send_metrics_to_redis(agent_info: Dict[str, Any]) -> bool:
    """Send agent metrics with automatic fallback support."""
    try:
        # Import fallback storage
        from utils.fallback_storage import get_fallback_storage
        fallback = get_fallback_storage()
        
        # Update agent execution status
        agent_id = agent_info.get('agent_id')
        if agent_id:
            updates = {
                'status': agent_info.get('status', 'complete'),
                'end_time': int(datetime.now().timestamp() * 1000),
                'duration_ms': agent_info.get('duration_ms', 0),
                'token_usage': agent_info.get('token_usage', {}),
                'performance_metrics': agent_info.get('performance_metrics', {}),
                'progress': 100
            }
            fallback.update_agent_execution(agent_id, updates)
        
        return True
        
    except Exception as e:
        print(f"Agent metrics error: {e}", file=sys.stderr)
        return False


def send_metrics_to_server(agent_info: Dict[str, Any]) -> bool:
    """Send agent completion metrics to the observability server."""
    try:
        server_url = os.getenv('OBSERVABILITY_SERVER_URL', 'http://localhost:4000')
        
        # Send to /api/agents/complete endpoint
        response = requests.post(
            f"{server_url}/api/agents/complete",
            json=agent_info,
            timeout=2
        )
        
        return response.status_code == 200
        
    except Exception as e:
        print(f"Server metrics error: {e}", file=sys.stderr)
        return False


def announce_subagent_completion(input_data: Dict[str, Any]):
    """Announce subagent completion with context-rich information."""
    try:
        # Extract subagent information
        info = extract_subagent_info(input_data)
        
        # Filter out generic agents from TTS notifications
        if info['agent_type'].lower() == 'generic':
            print(f"Skipping TTS for generic agent: {info['agent_name']}", file=sys.stderr)
            return
        
        # Generate context-rich message
        message = generate_context_rich_message(info)
        
        # Determine priority based on content
        if info['error_occurred']:
            priority = "important"
        else:
            priority = "normal"
        
        # Use observability system if available
        if OBSERVABILITY_AVAILABLE:
            should_speak = should_speak_event_coordinated(
                message=message,
                priority=2 if priority == "important" else 3,  # HIGH or MEDIUM
                category="completion",
                hook_type="subagent_stop",
                tool_name="subagent",
                metadata={"subagent_info": info}
            )
            
            if should_speak:
                notify_tts(message, priority)
        else:
            # Direct TTS notification
            notify_tts(message, priority)
        
    except Exception:
        # Fall back to simple notification on any error
        notify_tts("Subagent completed", "normal")


def main():
    try:
        # Parse command line arguments
        parser = argparse.ArgumentParser()
        parser.add_argument('--chat', action='store_true', help='Copy transcript to chat.json')
        parser.add_argument('--no-redis', action='store_true', help='Skip Redis storage')
        parser.add_argument('--no-server', action='store_true', help='Skip server notification')
        parser.add_argument('--no-relationships', action='store_true', help='Skip relationship tracking')
        args = parser.parse_args()
        
        # Read JSON input from stdin
        input_data = json.load(sys.stdin)

        # Extract required fields
        session_id = input_data.get("session_id", "")
        stop_hook_active = input_data.get("stop_hook_active", False)

        # Ensure session log directory exists
        log_dir = ensure_session_log_dir(session_id)
        log_path = log_dir / "subagent_stop.json"

        # Read existing log data or initialize empty list
        if log_path.exists():
            with open(log_path, 'r') as f:
                try:
                    log_data = json.load(f)
                except (json.JSONDecodeError, ValueError):
                    log_data = []
        else:
            log_data = []
        
        # Extract comprehensive agent metadata
        agent_info = extract_subagent_info(input_data)
        
        # Try to get agent_id from start hook
        agent_id = get_agent_id_from_start(session_id)
        if agent_id:
            agent_info['agent_id'] = agent_id
        
        # RELATIONSHIP TRACKING: Update relationship completion
        if not args.no_relationships:
            parent_session_id = input_data.get('parent_session_id')
            if not parent_session_id:
                # Try to extract from environment or log data
                parent_session_id = os.getenv('CLAUDE_PARENT_SESSION_ID')
            
            if parent_session_id:
                # Prepare completion data
                completion_data = {
                    "status": agent_info.get('status', 'completed'),
                    "metrics": {
                        "duration_ms": agent_info.get('duration_ms', 0),
                        "tokens_used": agent_info.get('token_usage', {}).get('total_tokens', 0),
                        "tools_used": len(agent_info.get('tools_used', [])),
                        "files_affected": agent_info.get('files_affected', 0),
                        "tests_run": agent_info.get('tests_run', 0)
                    },
                    "summary": agent_info.get('result_summary', f"{agent_info['agent_name']} completed")
                }
                
                # Update relationship completion
                if update_relationship_completion(session_id, completion_data):
                    print(f"Updated relationship completion for session {session_id}", file=sys.stderr)
                
                # Notify parent session
                summary = completion_data['summary']
                if notify_parent_completion(parent_session_id, session_id, summary):
                    print(f"Notified parent session {parent_session_id} of completion", file=sys.stderr)
            
            # Clean up spawn markers for this session
            cleanup_spawn_markers()
        
        # Enhanced log entry with agent metadata
        enhanced_entry = {
            **input_data,
            "agent_metadata": agent_info,
            "enhanced_timestamp": datetime.now().isoformat(),
            "hook_version": "enhanced_v3.0"
        }
        
        # Append enhanced data
        log_data.append(enhanced_entry)
        
        # Send metrics to Redis unless disabled
        if not args.no_redis:
            redis_success = send_metrics_to_redis(agent_info)
            if redis_success:
                print(f"Agent metrics sent to Redis", file=sys.stderr)
        
        # Send metrics to observability server unless disabled
        if not args.no_server:
            server_success = send_metrics_to_server(agent_info)
            if server_success:
                print(f"Agent metrics sent to server", file=sys.stderr)
        
        # Write back to file with formatting
        with open(log_path, 'w') as f:
            json.dump(log_data, f, indent=2)
        
        # Handle --chat switch (same as stop.py)
        if args.chat and 'transcript_path' in input_data:
            transcript_path = input_data['transcript_path']
            if os.path.exists(transcript_path):
                # Read .jsonl file and convert to JSON array
                chat_data = []
                try:
                    with open(transcript_path, 'r') as f:
                        for line in f:
                            line = line.strip()
                            if line:
                                try:
                                    chat_data.append(json.loads(line))
                                except json.JSONDecodeError:
                                    pass  # Skip invalid lines
                    
                    # Write to logs/chat.json
                    chat_file = os.path.join(log_dir, 'chat.json')
                    with open(chat_file, 'w') as f:
                        json.dump(chat_data, f, indent=2)
                except Exception:
                    pass  # Fail silently

        # Announce subagent completion via TTS with context
        announce_subagent_completion(input_data)

        sys.exit(0)

    except json.JSONDecodeError:
        # Handle JSON decode errors gracefully
        sys.exit(0)
    except Exception:
        # Handle any other errors gracefully
        sys.exit(0)


if __name__ == "__main__":
    main()