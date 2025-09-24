#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "redis>=4.0.0",
#     "requests>=2.28.0",
#     "python-dotenv",
# ]
# ///

import argparse
import json
import os
import sys
import re
import requests
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional
from utils.constants import ensure_session_log_dir
from utils.relationship_tracker import (
    get_parent_session_id, extract_agent_context, create_spawn_marker,
    register_session_relationship, calculate_session_depth, build_session_path,
    cleanup_spawn_markers
)
from utils.agent_naming_service import generate_agent_name, generate_session_name

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
    print("Warning: Redis not available, agent metrics will not be tracked", file=sys.stderr)


def generate_agent_id() -> str:
    """Generate a unique agent execution ID."""
    import random
    import string
    timestamp = int(datetime.now().timestamp() * 1000)
    random_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
    return f"ag_{timestamp}_{random_suffix}"


def extract_agent_from_transcript(transcript_path: str) -> Optional[str]:
    """Extract agent information from current session transcript."""
    try:
        if not os.path.exists(transcript_path):
            return None
            
        with open(transcript_path, 'r') as f:
            lines = f.readlines()
        
        # Look at recent lines for agent invocation patterns
        recent_lines = lines[-5:] if len(lines) > 5 else lines
        
        for line in reversed(recent_lines):
            try:
                data = json.loads(line.strip())
                
                # Check for Task tool with subagent_type
                if 'message' in data and 'content' in data['message']:
                    content = data['message']['content']
                    if isinstance(content, list):
                        for item in content:
                            if isinstance(item, dict) and item.get('name') == 'Task':
                                if 'input' in item and 'subagent_type' in item['input']:
                                    return item['input']['subagent_type']
                
            except (json.JSONDecodeError, KeyError):
                continue
                
    except Exception:
        pass
    
    return None


def extract_agent_info(input_data: Dict[str, Any]) -> Dict[str, Any]:
    """Extract agent information from the input data."""
    info = {
        "agent_name": "unknown",
        "task_description": "",
        "tools_granted": [],
        "context_size": 0,
        "source": "unknown"
    }
    
    # Enhanced agent name extraction
    agent_name = None
    
    # Strategy 1: Direct field extraction
    agent_fields = ['agent_name', 'subagent_name', 'subagent_type', 'agent', 'name', 'type']
    for field in agent_fields:
        if field in input_data and input_data[field]:
            agent_name = input_data[field]
            break
    
    # Strategy 2: Extract from transcript
    if not agent_name or agent_name == "unknown":
        transcript_path = input_data.get('transcript_path')
        if transcript_path:
            extracted_name = extract_agent_from_transcript(transcript_path)
            if extracted_name:
                agent_name = extracted_name
    
    # Strategy 3: Parse from any text fields for @mentions or agent patterns
    if not agent_name or agent_name == "unknown":
        for key, value in input_data.items():
            if isinstance(value, str):
                # Look for @-mentions
                at_mentions = re.findall(r'@([a-z0-9-]+(?:-[a-z0-9]+)*)', value.lower())
                if at_mentions:
                    agent_name = at_mentions[0]  # Take the first match
                    break
                
                # Look for agent patterns
                agent_patterns = [
                    r'use\s+(?:the\s+)?([a-z0-9-]+(?:-[a-z0-9]+)*)\s+(?:sub)?agent',
                    r'ask\s+([a-z0-9-]+(?:-[a-z0-9]+)*)\s+to'
                ]
                
                for pattern in agent_patterns:
                    matches = re.findall(pattern, value.lower())
                    if matches:
                        agent_name = matches[0]
                        break
                if agent_name:
                    break
    
    # Set the final agent name
    if agent_name:
        info['agent_name'] = agent_name
    
    # Extract task description
    desc_fields = ['task_description', 'description', 'task', 'prompt', 'instruction']
    for field in desc_fields:
        if field in input_data and input_data[field]:
            info['task_description'] = str(input_data[field])[:200]
            break
    
    # Extract tools granted
    if 'tools' in input_data:
        if isinstance(input_data['tools'], list):
            info['tools_granted'] = input_data['tools']
        elif isinstance(input_data['tools'], str):
            info['tools_granted'] = [tool.strip() for tool in input_data['tools'].split(',')]
    
    # Calculate context size
    info['context_size'] = len(json.dumps(input_data))
    
    # Determine source
    if 'wave_number' in input_data:
        info['source'] = 'wave_orchestration'
    elif 'parent_task_id' in input_data:
        info['source'] = 'nested_agent'
    elif 'auto_activated' in input_data and input_data['auto_activated']:
        info['source'] = 'auto_activation'
    else:
        info['source'] = 'user_command'
    
    return info


def send_to_redis(agent_id: str, agent_info: Dict[str, Any]) -> bool:
    """Send agent start data with automatic fallback support."""
    try:
        # Import fallback storage
        from utils.fallback_storage import get_fallback_storage
        fallback = get_fallback_storage()
        
        # Prepare agent data
        agent_data = {
            "agent_id": agent_id,
            "agent_name": agent_info['agent_name'],
            "agent_type": agent_info.get('agent_type', 'generic'),
            "task_description": agent_info['task_description'],
            "tools_granted": agent_info['tools_granted'],
            "context_size": agent_info['context_size'],
            "source": agent_info['source'],
            "session_id": agent_info.get('session_id', ''),
            "source_app": agent_info.get('source_app', '')
        }
        
        # Use fallback storage which handles Redis and local storage automatically
        return fallback.store_agent_execution(agent_id, agent_data)
        
    except Exception as e:
        print(f"Agent storage error: {e}", file=sys.stderr)
        return False


def send_to_observability_server(agent_id: str, agent_info: Dict[str, Any]) -> bool:
    """Send agent start event to the observability server."""
    try:
        server_url = os.getenv('OBSERVABILITY_SERVER_URL', 'http://localhost:4000')
        
        # Send to /api/agents/start endpoint
        response = requests.post(
            f"{server_url}/api/agents/start",
            json={
                "agent_id": agent_id,
                **agent_info
            },
            timeout=2
        )
        
        return response.status_code == 200
        
    except Exception as e:
        print(f"Observability server error: {e}", file=sys.stderr)
        return False


def main():
    try:
        # Parse command line arguments
        parser = argparse.ArgumentParser()
        parser.add_argument('--no-redis', action='store_true', help='Skip Redis storage')
        parser.add_argument('--no-server', action='store_true', help='Skip server notification')
        parser.add_argument('--no-relationships', action='store_true', help='Skip relationship tracking')
        args = parser.parse_args()
        
        # Read JSON input from stdin
        input_data = json.load(sys.stdin)
        
        # Extract required fields
        session_id = input_data.get("session_id", "")
        
        # Clean up expired spawn markers periodically
        cleanup_spawn_markers()
        
        # RELATIONSHIP TRACKING: Detect parent session
        parent_session_id = None
        if not args.no_relationships:
            parent_session_id = get_parent_session_id()
            
        # Ensure session log directory exists
        log_dir = ensure_session_log_dir(session_id)
        log_path = log_dir / "subagent_start.json"
        
        # Generate agent ID
        agent_id = generate_agent_id()
        
        # Extract agent information
        agent_info = extract_agent_info(input_data)
        
        # Generate memorable display name using the naming service
        # Determine agent type from agent name patterns
        agent_type = "generic"
        agent_name_lower = agent_info['agent_name'].lower()
        
        if 'analyzer' in agent_name_lower or 'analysis' in agent_name_lower:
            agent_type = 'analyzer'
        elif 'review' in agent_name_lower:
            agent_type = 'reviewer'
        elif 'debug' in agent_name_lower:
            agent_type = 'debugger'
        elif 'test' in agent_name_lower:
            agent_type = 'tester'
        elif 'build' in agent_name_lower:
            agent_type = 'builder'
        
        # Generate the display name
        context = agent_info.get('task_description', '') or ''
        agent_info['display_name'] = generate_agent_name(agent_type, context, session_id)
        
        # RELATIONSHIP TRACKING: Extract comprehensive agent context
        relationship_context = {}
        if not args.no_relationships:
            relationship_context = extract_agent_context(input_data)
            
            if parent_session_id:
                # Calculate session hierarchy information
                depth_level = calculate_session_depth(parent_session_id)
                session_path = build_session_path(parent_session_id, session_id)
                
                # Create spawn marker for child session discovery
                spawn_context = {
                    "parent_session_id": parent_session_id,
                    "child_session_id": session_id,
                    "agent_id": agent_id,
                    "depth_level": depth_level,
                    "session_path": session_path,
                    **relationship_context
                }
                create_spawn_marker(session_id, spawn_context)
                
                # Register relationship with server
                relationship_metadata = {
                    "relationship_type": "parent/child",
                    "depth_level": depth_level,
                    "session_path": session_path,
                    **relationship_context
                }
                
                if register_session_relationship(parent_session_id, session_id, relationship_metadata):
                    print(f"Session relationship registered: {parent_session_id} -> {session_id}", file=sys.stderr)
                else:
                    print(f"Failed to register session relationship", file=sys.stderr)
        
        # Create enhanced log entry with relationship context
        log_entry = {
            "agent_id": agent_id,
            "timestamp": datetime.now().isoformat(),
            "session_id": session_id,
            "parent_session_id": parent_session_id,
            "relationship_context": relationship_context,
            **agent_info,
            "input_data": input_data
        }
        
        # Read existing log data or initialize empty list
        if log_path.exists():
            with open(log_path, 'r') as f:
                try:
                    log_data = json.load(f)
                except (json.JSONDecodeError, ValueError):
                    log_data = []
        else:
            log_data = []
        
        # Append new entry
        log_data.append(log_entry)
        
        # Write back to file
        with open(log_path, 'w') as f:
            json.dump(log_data, f, indent=2)
        
        # Send to Redis unless disabled
        if not args.no_redis:
            redis_success = send_to_redis(agent_id, agent_info)
            if redis_success:
                print(f"Agent {agent_id} marked as started in Redis", file=sys.stderr)
        
        # Send to observability server unless disabled
        if not args.no_server:
            server_success = send_to_observability_server(agent_id, agent_info)
            if server_success:
                print(f"Agent {agent_info['display_name']} ({agent_id}) start event sent to server", file=sys.stderr)
        
        # Store agent ID in a temporary file for the stop hook to use
        agent_id_file = log_dir / f"current_agent_{os.getpid()}.txt"
        with open(agent_id_file, 'w') as f:
            f.write(agent_id)
        
        # Output enhanced response with relationship info
        response = {
            "agent_id": agent_id,
            "parent_session_id": parent_session_id,
            "relationship_tracked": parent_session_id is not None and not args.no_relationships
        }
        print(json.dumps(response))
        
        sys.exit(0)
        
    except json.JSONDecodeError:
        # Handle JSON decode errors gracefully
        sys.exit(0)
    except Exception as e:
        # Log error but don't fail the hook
        print(f"Error in subagent_start hook: {e}", file=sys.stderr)
        sys.exit(0)


if __name__ == "__main__":
    main()