#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.8"
# dependencies = []
# ///

"""
Async wrapper for send_event.py to prevent timeout notifications.
Spawns send_event.py in background and exits immediately.
"""

import sys
import subprocess
import os
from pathlib import Path

def main():
    """Spawn send_event.py in background with all arguments."""
    # Get the directory containing this script
    script_dir = Path(__file__).parent
    send_event_script = script_dir / "send_event.py"
    
    # Build command with all arguments passed to this script
    cmd = [sys.executable, str(send_event_script)] + sys.argv[1:]
    
    # Read stdin data
    stdin_data = sys.stdin.read()
    
    # Spawn in background, passing stdin data
    subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True
    ).communicate(stdin_data)
    
    # Exit immediately - this prevents timeout
    sys.exit(0)

if __name__ == '__main__':
    main()