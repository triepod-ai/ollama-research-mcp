#!/usr/bin/env python3
"""
Simple file-based lock coordinator for TTS notifications.
Provides basic coordination when the main TTS queue coordinator is not available.
"""

import fcntl
import os
import time
import subprocess
from pathlib import Path
from typing import Optional

class SimpleTTSLock:
    """Simple file-based lock to prevent TTS overlap."""
    
    def __init__(self, timeout: float = 30.0):
        """Initialize the lock with a timeout."""
        self.lock_file = Path("/tmp/simple_tts_lock")
        self.timeout = timeout
        self.lock_fd = None
        
    def acquire(self, wait: bool = True, max_wait: float = 5.0) -> bool:
        """
        Acquire the TTS lock.
        
        Args:
            wait: Whether to wait for the lock if it's held
            max_wait: Maximum time to wait for the lock
            
        Returns:
            True if lock acquired, False otherwise
        """
        try:
            # Create lock file if it doesn't exist
            self.lock_file.touch(exist_ok=True)
            
            # Open the lock file
            self.lock_fd = open(self.lock_file, 'w')
            
            if wait:
                # Try to acquire lock with timeout
                start_time = time.time()
                while time.time() - start_time < max_wait:
                    try:
                        fcntl.flock(self.lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                        return True
                    except IOError:
                        # Lock is held, wait a bit
                        time.sleep(0.1)
                return False
            else:
                # Try to acquire lock immediately
                fcntl.flock(self.lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return True
                
        except Exception:
            # If anything goes wrong, don't block
            return False
    
    def release(self):
        """Release the TTS lock."""
        try:
            if self.lock_fd:
                fcntl.flock(self.lock_fd, fcntl.LOCK_UN)
                self.lock_fd.close()
                self.lock_fd = None
        except Exception:
            # Silently fail
            pass
    
    def __enter__(self):
        """Context manager entry."""
        self.acquire()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.release()


def speak_with_simple_lock(message: str, timeout: float = 30.0) -> bool:
    """
    Speak a message using simple file-based locking to prevent overlap.
    
    Args:
        message: Message to speak
        timeout: Maximum time to hold the lock
        
    Returns:
        True if message was spoken, False otherwise
    """
    try:
        # Skip if TTS is disabled
        if os.getenv('TTS_ENABLED', 'true').lower() != 'true':
            return False
        
        lock = SimpleTTSLock(timeout=timeout)
        
        # Try to acquire lock
        if lock.acquire(wait=True, max_wait=5.0):
            try:
                # Speak the message
                process = subprocess.Popen(
                    ['speak', message],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                
                # Wait for completion (with timeout)
                try:
                    process.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    # Kill if it takes too long
                    process.kill()
                    
            finally:
                # Always release the lock
                lock.release()
                
            return True
        else:
            # Couldn't acquire lock, skip this message
            return False
            
    except Exception:
        # On any error, fail silently
        return False


def is_simple_lock_available() -> bool:
    """Check if we can use the simple lock mechanism."""
    try:
        lock_file = Path("/tmp/simple_tts_lock")
        # Try to create and write to the file
        lock_file.touch(exist_ok=True)
        return True
    except Exception:
        return False


# For backward compatibility
def notify_tts_with_lock(message: str, priority: str = "normal") -> bool:
    """
    Notify with TTS using simple locking mechanism.
    
    Args:
        message: Message to speak
        priority: Priority level (affects timeout)
        
    Returns:
        True if spoken, False otherwise
    """
    # Adjust timeout based on priority
    timeout_map = {
        "error": 45.0,     # Give more time for critical messages
        "important": 30.0,
        "normal": 20.0
    }
    
    timeout = timeout_map.get(priority, 20.0)
    
    return speak_with_simple_lock(message, timeout=timeout)


if __name__ == "__main__":
    # Test the simple lock mechanism
    print("Testing simple TTS lock mechanism...")
    
    # Test sequential messages
    messages = [
        "Testing message one",
        "Testing message two", 
        "Testing message three"
    ]
    
    for i, msg in enumerate(messages):
        print(f"Speaking message {i+1}...")
        success = speak_with_simple_lock(msg, timeout=10.0)
        print(f"Result: {'Success' if success else 'Failed'}")
        
    print("\nTest complete!")