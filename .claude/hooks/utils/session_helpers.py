#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
Session Helper Utilities

Shared utilities for focused session hooks following KISS principle.
Each function has a single, clear responsibility.
"""

import subprocess
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime


def get_project_name() -> str:
    """Get project name from git root directory, regardless of current working directory."""
    import os
    current_dir = os.getcwd()
    
    # Walk up the directory tree to find git root
    while current_dir != "/":
        if os.path.exists(os.path.join(current_dir, ".git")):
            # Found git root, return its basename
            return os.path.basename(current_dir)
        current_dir = os.path.dirname(current_dir)
    
    # Fallback: if no git root found, use current directory
    return Path.cwd().name


def get_project_status() -> Optional[str]:
    """Load PROJECT_STATUS.md content if it exists."""
    status_file = Path("PROJECT_STATUS.md")
    if not status_file.exists():
        return None
    
    content = status_file.read_text()
    # Truncate if too long for context injection
    if len(content) > 500:
        return content[:500] + "..."
    return content


def get_git_status() -> Dict[str, Any]:
    """Get git repository status information."""
    result = {
        "status_lines": [],
        "recent_commits": [],
        "branch": "main",
        "modified_count": 0
    }
    
    if not Path(".git").exists():
        return result
    
    try:
        # Get git status
        git_status = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True, text=True, timeout=5
        )
        if git_status.returncode == 0:
            status_lines = [line for line in git_status.stdout.strip().split('\n') if line.strip()]
            result["status_lines"] = status_lines
            result["modified_count"] = len(status_lines)
        
        # Get recent commits
        git_log = subprocess.run(
            ["git", "log", "--oneline", "-5"],
            capture_output=True, text=True, timeout=5
        )
        if git_log.returncode == 0:
            result["recent_commits"] = git_log.stdout.strip().split('\n')
        
        # Get current branch
        git_branch = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True, text=True, timeout=5
        )
        if git_branch.returncode == 0:
            result["branch"] = git_branch.stdout.strip() or "main"
            
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    
    return result


def create_rate_limit_file(session_type: str) -> Path:
    """Create rate limiting file path for session type."""
    return Path(f"/tmp/claude_session_{session_type}_last.txt")


def is_rate_limited(session_type: str, cooldown_seconds: int = 30) -> bool:
    """Check if session type is rate limited."""
    rate_file = create_rate_limit_file(session_type)
    
    if not rate_file.exists():
        return False
    
    try:
        last_time = float(rate_file.read_text().strip())
        return (datetime.now().timestamp() - last_time) < cooldown_seconds
    except (ValueError, FileNotFoundError):
        return False


def update_rate_limit(session_type: str) -> None:
    """Update rate limit timestamp for session type."""
    rate_file = create_rate_limit_file(session_type)
    rate_file.write_text(str(datetime.now().timestamp()))


def format_git_summary(git_info: Dict[str, Any]) -> str:
    """Format git information for display."""
    modified_count = git_info["modified_count"]
    recent_count = len(git_info["recent_commits"])
    branch = git_info["branch"]
    
    parts = [f"Branch: {branch}"]
    if modified_count > 0:
        parts.append(f"{modified_count} modified files")
    if recent_count > 0:
        parts.append(f"{recent_count} recent commits")
    
    return " | ".join(parts)