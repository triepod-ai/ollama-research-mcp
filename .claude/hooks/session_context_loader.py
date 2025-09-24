#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "redis>=4.0.0",
#     "python-dotenv",
# ]
# ///
"""
Session Context Loader Hook

SINGLE PURPOSE: Load and inject project context into Claude sessions.

- Loads PROJECT_STATUS.md, git status, recent commits
- Generates context injection text for Claude
- NO TTS notifications, NO observability events, NO complex decisions
- Used for: startup, resume (not clear - fresh sessions don't need old context)
"""

import sys
import json
import os
import subprocess
from pathlib import Path

# Add utils to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'utils'))

from session_helpers import get_project_name, get_project_status, get_git_status, format_git_summary
from relationship_tracker import get_parent_session_id, build_session_path, calculate_session_depth

import glob
from datetime import datetime, timedelta


def get_latest_handoff_context(project_name: str) -> str:
    """Retrieve the most recent handoff context with automatic fallback."""
    try:
        # Import fallback storage
        from utils.fallback_storage import get_fallback_storage
        fallback = get_fallback_storage()
        
        # Use fallback storage which handles Redis and local storage automatically
        return fallback.get_latest_session_handoff(project_name)
        
    except Exception as e:
        print(f"Warning: Could not retrieve handoff context: {e}", file=sys.stderr)
        # Final fallback to file-based retrieval
        return get_file_fallback_handoff()


def get_file_fallback_handoff() -> str:
    """Fallback to file-based handoff retrieval."""
    try:
        import glob
        import re
        from datetime import datetime
        
        # Look for handoff files with timestamp pattern: handoff_YYYYMMDD_HHMMSS.md
        handoff_files = glob.glob("handoff_*.md")
        if handoff_files:
            # Parse timestamps from filenames and sort by actual timestamp
            file_timestamps = []
            for filepath in handoff_files:
                filename = os.path.basename(filepath)
                match = re.search(r'handoff_(\d{8}_\d{6})\.md$', filename)
                if match:
                    timestamp_str = match.group(1)
                    try:
                        timestamp = datetime.strptime(timestamp_str, '%Y%m%d_%H%M%S')
                        file_timestamps.append((timestamp, filepath))
                    except ValueError:
                        continue
            
            if file_timestamps:
                # Sort by timestamp (most recent first) and get the latest
                file_timestamps.sort(reverse=True)
                latest_file = file_timestamps[0][1]
                with open(latest_file, 'r') as f:
                    return f.read()
            else:
                # Fallback to modification time if no valid timestamps found
                handoff_files.sort(key=os.path.getmtime, reverse=True)
                with open(handoff_files[0], 'r') as f:
                    return f.read()
    except Exception:
        pass
    
    return ""


def get_recent_summaries(project_name: str, max_sessions: int = 3) -> dict:
    """Load recent session summaries from ~/.claude/summaries/ for this project."""
    try:
        summaries_dir = os.path.expanduser("~/.claude/summaries")
        if not os.path.exists(summaries_dir):
            return {}
        
        # Find all summary files for this project
        pattern = os.path.join(summaries_dir, f"{project_name}_*_*.md")
        files = glob.glob(pattern)
        
        if not files:
            return {}
        
        # Parse filenames to extract type and timestamp
        file_info = []
        for filepath in files:
            filename = os.path.basename(filepath)
            # For pattern: project-name_type_YYYYMMDD_HHMMSS.md
            # We need to extract the last two parts: type and timestamp
            # Remove .md extension first
            name_without_ext = filename[:-3]  # Remove .md
            # Find the last occurrence of underscore followed by 8 digits
            parts = name_without_ext.split('_')
            if len(parts) >= 3:
                # The timestamp should be the last two parts joined with underscore
                timestamp_str = f"{parts[-2]}_{parts[-1]}"
                summary_type = parts[-3]  # The part before the date
                try:
                    # Parse timestamp (format: YYYYMMDD_HHMMSS)
                    timestamp = datetime.strptime(timestamp_str, '%Y%m%d_%H%M%S')
                    file_info.append((timestamp, summary_type, filepath))
                except ValueError:
                    continue
        
        if not file_info:
            return {}
        
        # Sort by timestamp (most recent first)
        file_info.sort(reverse=True)
        
        # Group by session (same timestamp)
        sessions = {}
        for timestamp, summary_type, filepath in file_info:
            session_key = timestamp.strftime('%Y%m%d_%H%M%S')
            if session_key not in sessions:
                sessions[session_key] = {}
            sessions[session_key][summary_type] = filepath
        
        # Load content from most recent sessions
        result = {
            'blockers': [],
            'actions': [],
            'insights': [],
            'achievements': []
        }
        
        sessions_loaded = 0
        for session_key in sorted(sessions.keys(), reverse=True):
            if sessions_loaded >= max_sessions:
                break
            
            session_files = sessions[session_key]
            
            # Load action items
            if 'actions' in session_files:
                try:
                    with open(session_files['actions'], 'r') as f:
                        content = f.read()
                        # Extract action items (looking for "**Task N**:" pattern)
                        for line in content.split('\n'):
                            if line.startswith('**Task') and ':' in line:
                                task = line.split(':', 1)[1].strip()
                                if task and task not in result['actions']:
                                    result['actions'].append(task)
                            elif line.startswith('**Blocker') and ':' in line:
                                blocker = line.split(':', 1)[1].strip()
                                if blocker and blocker not in result['blockers']:
                                    result['blockers'].append(blocker)
                except Exception:
                    pass
            
            # Load insights
            if 'insights' in session_files:
                try:
                    with open(session_files['insights'], 'r') as f:
                        content = f.read()
                        # Extract insights (looking for "- " pattern after "## Key Insights")
                        in_insights = False
                        for line in content.split('\n'):
                            if '## Key Insights' in line:
                                in_insights = True
                            elif in_insights and line.startswith('- '):
                                insight = line[2:].strip()
                                if insight and insight not in result['insights']:
                                    result['insights'].append(insight)
                            elif line.startswith('##') and in_insights:
                                break  # End of insights section
                except Exception:
                    pass
            
            # Load achievements from analysis files
            if 'analysis' in session_files:
                try:
                    with open(session_files['analysis'], 'r') as f:
                        content = f.read()
                        # Extract achievements (looking for "- " pattern after "## Achievements")
                        in_achievements = False
                        for line in content.split('\n'):
                            if '## Achievements' in line:
                                in_achievements = True
                            elif in_achievements and line.startswith('- '):
                                achievement = line[2:].strip()
                                if achievement and achievement not in result['achievements']:
                                    result['achievements'].append(achievement)
                            elif line.startswith('##') and in_achievements:
                                break  # End of achievements section
                except Exception:
                    pass
            
            sessions_loaded += 1
        
        # Limit items per category to preserve context space
        result['blockers'] = result['blockers'][:3]
        result['actions'] = result['actions'][:5]
        result['insights'] = result['insights'][:3]
        result['achievements'] = result['achievements'][:3]
        
        return result
        
    except Exception as e:
        print(f"Warning: Could not load summaries: {e}", file=sys.stderr)
        return {}


def generate_context_injection(project_name: str, project_status: str, git_info: dict, handoff_context: str = "", summaries: dict = None, session_id: str = "") -> str:
    """Generate context to inject into Claude's session."""
    parts = []
    
    # Project overview with session information
    parent_session_id = get_parent_session_id()
    if parent_session_id:
        depth = calculate_session_depth(parent_session_id)
        session_path = build_session_path(parent_session_id, session_id)
        parts.append(f"# {project_name} - Child Session Context (Depth: {depth})")
        parts.append(f"**Session Hierarchy**: {session_path}")
        parts.append(f"**Parent Session**: {parent_session_id}")
    else:
        parts.append(f"# {project_name} - Root Session Context")
    
    parts.append("")
    
    # Previous session handoff context (priority - load first)
    if handoff_context:
        parts.append("## Previous Session Handoff")
        parts.append("```")
        parts.append(handoff_context)
        parts.append("```")
        parts.append("")
    
    # Previous session insights from summaries
    if summaries and any(summaries.values()):
        parts.append("## Previous Session Insights")
        
        # Active blockers (highest priority)
        if summaries.get('blockers'):
            parts.append("### ⚠️ Active Blockers")
            for blocker in summaries['blockers']:
                parts.append(f"- {blocker}")
            parts.append("")
        
        # Pending actions
        if summaries.get('actions'):
            parts.append("### 📋 Pending Actions (from recent sessions)")
            for i, action in enumerate(summaries['actions'], 1):
                parts.append(f"{i}. {action}")
            parts.append("")
        
        # Recent achievements
        if summaries.get('achievements'):
            parts.append("### ✅ Recent Achievements")
            for achievement in summaries['achievements']:
                parts.append(f"- {achievement}")
            parts.append("")
        
        # Key insights
        if summaries.get('insights'):
            parts.append("### 💡 Key Insights")
            for insight in summaries['insights']:
                parts.append(f"- {insight}")
            parts.append("")
    
    # Recent git activity
    if git_info["recent_commits"]:
        parts.append("## Recent Changes")
        for commit in git_info["recent_commits"][:3]:
            parts.append(f"- {commit}")
        parts.append("")
    
    # Current modifications
    if git_info["modified_count"] > 0:
        parts.append("## Modified Files")
        for status_line in git_info["status_lines"][:5]:
            # Extract filename from git status format
            filename = status_line[3:] if len(status_line) > 3 else status_line
            parts.append(f"- {filename}")
        parts.append("")
    
    # Project status summary
    if project_status:
        parts.append("## Current Project Status")
        parts.append(project_status)
        parts.append("")
    
    # Session relationship context
    if parent_session_id:
        parts.append("## Session Relationship Context")
        parts.append(f"This is a child session spawned from parent session `{parent_session_id}`.")
        parts.append(f"Depth level: {calculate_session_depth(parent_session_id)}")
        parts.append(f"Session path: {build_session_path(parent_session_id, session_id)}")
        parts.append("All activities in this session are automatically tracked and related to the parent session.")
        parts.append("")
    
    # Agent monitoring note
    parts.append("## Agent Monitoring Active")
    if parent_session_id:
        parts.append("This child session includes comprehensive observability for all agent activities, with parent/child relationship tracking, TTS notifications, and real-time event tracking enabled.")
    else:
        parts.append("This root session includes comprehensive observability for all agent activities, with TTS notifications and real-time event tracking enabled.")
    
    return "\n".join(parts)


def is_continue_session() -> bool:
    """Detect if this is a continue session that should skip context loading."""
    # Primary: Check environment variable for user control
    if os.environ.get('CLAUDE_SKIP_CONTEXT') == 'true':
        return True
    
    # Secondary: Check for continue session indicator
    if os.environ.get('CLAUDE_CONTINUE_SESSION') == 'true':
        return True
    
    # Tertiary: Try parent process detection (may not work in all environments)
    try:
        parent_pid = os.getppid()
        cmdline_path = f"/proc/{parent_pid}/cmdline"
        
        if os.path.exists(cmdline_path):
            with open(cmdline_path, 'rb') as f:
                cmdline = f.read().decode('utf-8', errors='ignore')
                # Claude Code arguments are null-separated
                args = cmdline.split('\0')
                # Only check for Claude continue flags, not bash -c
                # Look specifically for Claude executable with continue flag
                if len(args) > 0:
                    executable = args[0]
                    if 'claude' in executable.lower():
                        # This is a Claude process, check for continue flags
                        return '--continue' in args or '-c' in args
                # Not a Claude process, ignore
                return False
    except Exception:
        pass
    
    return False


def main():
    """Main context loader execution - single focused purpose."""
    try:
        # Read input data from stdin
        input_data = json.loads(sys.stdin.read())
        source = input_data.get('source', 'startup')
        
        # Check if this is a continue session (claude -c)
        if is_continue_session():
            print("Continue session - no context loading needed")
            return
        
        # Only load context for sessions that need it (not fresh 'clear' sessions)
        if source in ['clear', 'continue']:
            print(f"{source.title()} session - no context loading needed")
            return
        
        # Extract session ID from input data
        session_id = input_data.get('session_id', '')
        
        # Load project context
        project_name = get_project_name()
        project_status = get_project_status()
        git_info = get_git_status()
        
        # Load previous session handoff context from Redis
        handoff_context = get_latest_handoff_context(project_name)
        
        # Load recent session summaries
        summaries = get_recent_summaries(project_name)
        
        # Generate and output context injection with session relationship context
        context_injection = generate_context_injection(project_name, project_status, git_info, handoff_context, summaries, session_id)
        print(context_injection)
        
        # Simple success indicator to stderr
        git_summary = format_git_summary(git_info)
        handoff_indicator = f" + handoff ({len(handoff_context)} chars)" if handoff_context else ""
        summaries_indicator = f" + {sum(len(v) for v in summaries.values())} insights" if summaries and any(summaries.values()) else ""
        print(f"Context loaded for {project_name}: {git_summary}{handoff_indicator}{summaries_indicator}", file=sys.stderr)
        
    except Exception as e:
        print(f"Context loader error: {e}", file=sys.stderr)
        # Don't exit with error - context loading failure shouldn't break session start
        

if __name__ == "__main__":
    main()