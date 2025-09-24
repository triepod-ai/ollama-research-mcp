#!/usr/bin/env python3
"""
Claude Agent Runner - Direct Agent Execution System

KISS-compliant script that executes Claude Code agents directly using the Codex CLI,
eliminating Task tool dependencies while maintaining identical JSON I/O interface.

## Purpose
Provides direct agent execution for hooks and standalone scripts without requiring
Claude Code's internal Task tool. Enables seamless migration from Task tool usage
to subprocess-based agent invocation.

## Architecture
Input JSON → Agent Discovery → YAML Parsing → Prompt Building → Codex Execution → JSON Extraction → Output

## Core Features
- **Agent Discovery**: Automatically finds agent definitions in .claude/agents/ directories
- **YAML Parsing**: Extracts frontmatter metadata (name, tools, description) from agent files  
- **Prompt Construction**: Builds comprehensive Codex prompts with agent context and user input
- **Codex Integration**: Executes 'codex exec --full-auto' for non-interactive analysis
- **Smart JSON Extraction**: Parses JSON from Codex markdown output with multiple fallback methods
- **Error Handling**: Returns structured error responses for all failure modes

## Usage Examples
    # Command line
    echo '{"session_summary": "...", "working_dir": "..."}' | python3 claude_agent_runner.py codex-session-analyzer
    
    # From Python
    result = subprocess.run(
        ["python3", "claude_agent_runner.py", "agent-name"],
        input=json.dumps(input_data),
        capture_output=True,
        text=True
    )
    response = json.loads(result.stdout)

## Agent File Format
    ---
    name: agent-name
    description: Agent description
    tools: [Bash, Read, Write]
    ---
    # Agent Instructions
    Agent behavior and task description...

## JSON Response Format
    {
      "achievements": ["list of accomplishments"],
      "next_steps": ["list of recommended actions"], 
      "blockers": ["list of obstacles"],
      "insights": ["list of insights learned"],
      "session_metrics": {"key": "value pairs"}
    }

## Error Handling
All errors return consistent JSON structure with error field and fallback data.
Supports multiple JSON extraction methods for robust Codex output parsing.

## Dependencies
- Python 3.8+ (stdlib only)
- Codex CLI installed and available in PATH
- Agent definitions in .claude/agents/ directory structure

Created: 2025-07-28
Component: Multi-Agent Observability System - Direct Agent Execution
"""

import json
import os
import subprocess
import sys
import tempfile
import yaml
from pathlib import Path
from typing import Dict, Any, Optional


def find_agent_file(agent_name: str) -> Optional[Path]:
    """Find agent definition file in .claude/agents/ directory."""
    # Start from the current working directory and walk up to find .claude/agents/
    current_dir = Path.cwd()
    
    while current_dir != current_dir.parent:
        agents_dir = current_dir / ".claude" / "agents"
        if agents_dir.exists():
            agent_file = agents_dir / f"{agent_name}.md"
            if agent_file.exists():
                return agent_file
        current_dir = current_dir.parent
    
    # Also check relative to this script's location
    script_dir = Path(__file__).parent.parent.parent
    agents_dir = script_dir / ".claude" / "agents"
    agent_file = agents_dir / f"{agent_name}.md"
    if agent_file.exists():
        return agent_file
    
    return None


def parse_agent_definition(agent_file: Path) -> Dict[str, Any]:
    """Parse agent definition file and extract frontmatter and content."""
    content = agent_file.read_text()
    
    # Split frontmatter and content
    if content.startswith('---\n'):
        parts = content.split('---\n', 2)
        if len(parts) >= 3:
            frontmatter_text = parts[1]
            agent_content = parts[2].strip()
        else:
            frontmatter_text = ""
            agent_content = content
    else:
        frontmatter_text = ""
        agent_content = content
    
    # Parse frontmatter as YAML
    frontmatter = {}
    if frontmatter_text.strip():
        try:
            frontmatter = yaml.safe_load(frontmatter_text)
        except yaml.YAMLError:
            frontmatter = {}
    
    return {
        'frontmatter': frontmatter or {},
        'content': agent_content
    }


def build_codex_prompt(agent_definition: Dict[str, Any], user_input: Dict[str, Any]) -> str:
    """Build the prompt for codex CLI execution."""
    frontmatter = agent_definition['frontmatter']
    content = agent_definition['content']
    
    # Extract agent details
    agent_name = frontmatter.get('name', 'unknown-agent')
    description = frontmatter.get('description', 'Agent description not available')
    tools = frontmatter.get('tools', [])
    
    # Build comprehensive prompt
    prompt_parts = [
        f"# {agent_name.title()} Agent",
        f"Description: {description}",
        f"Available tools: {', '.join(tools) if tools else 'None specified'}",
        "",
        "## Agent Instructions:",
        content,
        "",
        "## User Input (JSON):",
        json.dumps(user_input, indent=2),
        "",
        "## Task:",
        "Execute the agent instructions above with the provided user input.",
        "Return a JSON response with the following structure:",
        "{",
        '  "achievements": ["list of accomplishments"],',
        '  "next_steps": ["list of recommended actions"],',
        '  "blockers": ["list of obstacles"],',
        '  "insights": ["list of insights or lessons learned"],',
        '  "session_metrics": {"key": "value pairs with session data"}',
        "}",
        "",
        "Focus on providing structured, actionable results. No philosophy or explanations."
    ]
    
    return "\n".join(prompt_parts)


def execute_with_codex(prompt: str, timeout: int = 45) -> Dict[str, Any]:
    """Execute the prompt using codex CLI and return parsed JSON response."""
    try:
        # Check if codex is available
        codex_check = subprocess.run(['which', 'codex'], capture_output=True, text=True)
        if codex_check.returncode != 0:
            return {"error": "Codex CLI not available"}
        
        # Execute codex with exec subcommand for non-interactive mode
        # Use full-auto for automatic execution without approval prompts
        codex_cmd = ['codex', 'exec', '--full-auto', prompt]
        
        result = subprocess.run(
            codex_cmd,
            capture_output=True,
            text=True,
            timeout=timeout + 5  # Add buffer to subprocess timeout
        )
        
        if result.returncode != 0:
            return {
                "error": f"Codex execution failed (exit code {result.returncode})",
                "stderr": result.stderr
            }
        
        # Try to parse JSON response
        try:
            response = json.loads(result.stdout)
            return response
        except json.JSONDecodeError:
            # If JSON parsing fails, try to extract JSON from output
            output = result.stdout.strip()
            
            # Look for JSON blocks marked with ```json
            json_blocks = []
            lines = output.split('\n')
            in_json_block = False
            current_json = []
            
            for line in lines:
                if line.strip() == '```json':
                    in_json_block = True
                    current_json = []
                elif line.strip() == '```' and in_json_block:
                    in_json_block = False
                    if current_json:
                        json_blocks.append('\n'.join(current_json))
                elif in_json_block:
                    current_json.append(line)
            
            # Try to parse each JSON block
            for json_text in json_blocks:
                try:
                    response = json.loads(json_text)
                    return response
                except json.JSONDecodeError:
                    continue
            
            # Fallback: Look for JSON-like patterns in the output
            start_idx = output.find('{')
            end_idx = output.rfind('}')
            
            if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                json_text = output[start_idx:end_idx + 1]
                try:
                    response = json.loads(json_text)
                    return response
                except json.JSONDecodeError:
                    pass
            
            # If still can't parse, return structured error with raw output
            return {
                "error": "Failed to parse JSON response from codex",
                "raw_output": output,
                "achievements": ["Agent execution completed"],
                "next_steps": ["Review raw output for insights"],
                "blockers": ["JSON parsing failed"],
                "insights": ["Codex returned non-JSON response"],
                "session_metrics": {"status": "parsing_failed"}
            }
    
    except subprocess.TimeoutExpired:
        return {"error": f"Codex execution timed out after {timeout} seconds"}
    except Exception as e:
        return {"error": f"Codex execution error: {str(e)}"}


def main():
    """Main entry point for the agent runner."""
    if len(sys.argv) != 2:
        print(json.dumps({"error": "Usage: claude_agent_runner.py <agent-name>"}))
        sys.exit(1)
    
    agent_name = sys.argv[1]
    
    # Read input JSON from stdin
    try:
        input_data = json.loads(sys.stdin.read())
    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"Invalid JSON input: {str(e)}"}))
        sys.exit(1)
    
    # Find agent definition file
    agent_file = find_agent_file(agent_name)
    if not agent_file:
        print(json.dumps({"error": f"Agent '{agent_name}' not found in .claude/agents/"}))
        sys.exit(1)
    
    # Parse agent definition
    try:
        agent_definition = parse_agent_definition(agent_file)
    except Exception as e:
        print(json.dumps({"error": f"Failed to parse agent definition: {str(e)}"}))
        sys.exit(1)
    
    # Build prompt and execute with codex
    prompt = build_codex_prompt(agent_definition, input_data)
    response = execute_with_codex(prompt)
    
    # Output JSON response
    print(json.dumps(response, indent=2))


if __name__ == "__main__":
    main()