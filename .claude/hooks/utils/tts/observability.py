#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "python-dotenv>=1.0.0",
# ]
# ///

"""
Project Observability module for event logging and basic hook coordination.
Delegates all TTS functionality to the sophisticated speak command system.
"""

import json
import os
from collections import deque, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional
from enum import Enum

from dotenv import load_dotenv

# Load environment variables
env_path = Path.home() / "brainpods" / ".env"
if env_path.exists():
    load_dotenv(env_path)

class EventPriority(Enum):
    """Event priority levels for logging and coordination."""
    CRITICAL = 1    # Errors, security blocks
    HIGH = 2        # Slow ops, large files, permissions
    MEDIUM = 3      # Notable successes, completions
    LOW = 4         # Regular operations
    MINIMAL = 5     # Rarely spoken events

class EventCategory(Enum):
    """Categories of events for pattern recognition."""
    ERROR = "error"
    SECURITY = "security"
    PERMISSION = "permission"
    PERFORMANCE = "performance"
    FILE_OPERATION = "file_operation"
    COMMAND_EXECUTION = "command_execution"
    COMPLETION = "completion"
    GENERAL = "general"

@dataclass
class ObservabilityEvent:
    """Represents an observability event with metadata."""
    message: str
    priority: EventPriority
    category: EventCategory
    timestamp: datetime = field(default_factory=datetime.now)
    hook_type: str = ""
    tool_name: str = ""
    metadata: Dict = field(default_factory=dict)
    
    def age_seconds(self) -> float:
        """Get age of event in seconds."""
        return (datetime.now() - self.timestamp).total_seconds()

class ProjectObservability:
    """Manages project-specific event logging and basic hook coordination."""
    
    def __init__(self):
        """Initialize the observability system."""
        self.event_queue: deque[ObservabilityEvent] = deque(maxlen=100)
        self.event_counts: Dict[EventCategory, int] = defaultdict(int)
        
        # Basic hook coordination state (TTS coordination handled by speak command)
        self.coordination_state = {
            "active_hook": None,
            "last_event_time": None,
            "session_context": {},
        }
        
        # Configuration
        self.max_queue_age = 30  # seconds
    
    def should_notify(self, event: ObservabilityEvent) -> bool:
        """Basic event filtering - detailed TTS logic handled by speak command."""
        # Always notify critical events
        if event.priority == EventPriority.CRITICAL:
            return True
        
        # Check if TTS is enabled at all
        if os.getenv('TTS_ENABLED', 'true').lower() != 'true':
            return False
        
        # Let speak command handle detailed filtering and rate limiting
        return True
    
    def log_event(self, event: ObservabilityEvent) -> None:
        """Log event to project observability queue."""
        self.event_queue.append(event)
        self.event_counts[event.category] += 1
        
        # Update coordination state
        self.coordination_state["last_event_time"] = datetime.now()
        
        # Clean old events
        self._clean_old_events()
    
    def _clean_old_events(self):
        """Remove events older than max age from queue."""
        while self.event_queue and self.event_queue[0].age_seconds() > self.max_queue_age:
            self.event_queue.popleft()
    
    def get_statistics(self) -> Dict:
        """Get current observability statistics."""
        return {
            "total_events": sum(self.event_counts.values()),
            "events_by_category": dict(self.event_counts),
            "queue_size": len(self.event_queue),
            "active_hook": self.coordination_state.get("active_hook"),
            "last_event_time": self.coordination_state.get("last_event_time").isoformat() if self.coordination_state.get("last_event_time") else None,
        }
    
    def update_session_context(self, key: str, value: any) -> None:
        """Update session-level context for coordination."""
        self.coordination_state["session_context"][key] = {
            "value": value,
            "timestamp": datetime.now()
        }

# Global instance
_observability = None

def get_observability() -> ProjectObservability:
    """Get or create the global observability instance."""
    global _observability
    if _observability is None:
        _observability = ProjectObservability()
    return _observability

def create_event(
    message: str,
    priority: int,
    category: str,
    hook_type: str = "",
    tool_name: str = "",
    metadata: Optional[Dict] = None
) -> ObservabilityEvent:
    """Create an observability event with proper typing."""
    return ObservabilityEvent(
        message=message,
        priority=EventPriority(priority),
        category=EventCategory(category),
        hook_type=hook_type,
        tool_name=tool_name,
        metadata=metadata or {}
    )

def should_speak_event(
    message: str,
    priority: int,
    category: str,
    hook_type: str = "",
    tool_name: str = "",
    metadata: Optional[Dict] = None
) -> bool:
    """Check if an event should be spoken - delegates detailed logic to speak command."""
    obs = get_observability()
    event = create_event(
        message=message,
        priority=priority,
        category=category,
        hook_type=hook_type,
        tool_name=tool_name,
        metadata=metadata
    )
    
    # Log the event for observability
    obs.log_event(event)
    
    # Basic should-notify check - speak command handles detailed coordination
    return obs.should_notify(event)

def should_speak_event_coordinated(
    message: str,
    priority: int,
    category: str,
    hook_type: str,
    tool_name: str = "",
    metadata: Optional[Dict] = None,
    operation_id: str = None
) -> bool:
    """Enhanced coordination-aware event processing - simplified for speak command integration."""
    obs = get_observability()
    
    # Update session context
    obs.update_session_context("current_event", {
        "hook_type": hook_type,
        "tool_name": tool_name,
        "priority": priority
    })
    
    # Add operation_id to metadata for tracking
    if not metadata:
        metadata = {}
    if operation_id:
        metadata["operation_id"] = operation_id
    
    event = create_event(
        message=message,
        priority=priority,
        category=category,
        hook_type=hook_type,
        tool_name=tool_name,
        metadata=metadata
    )
    
    obs.log_event(event)
    return obs.should_notify(event)

if __name__ == "__main__":
    # Test the observability system
    obs = get_observability()
    
    # Test events
    test_events = [
        ("Error: File not found", 1, "error", "post_tool_use", "Read"),
        ("Permission needed for Bash", 2, "permission", "notification", "Bash"),
        ("File write completed", 3, "file_operation", "post_tool_use", "Write"),
        ("Command executed", 4, "command_execution", "post_tool_use", "Bash"),
        ("Task completed", 3, "completion", "stop", ""),
    ]
    
    for message, priority, category, hook, tool in test_events:
        should_notify = should_speak_event(message, priority, category, hook, tool)
        print(f"Event: {message[:30]}... Should notify: {should_notify}")
    
    print("\nStatistics:")
    print(json.dumps(obs.get_statistics(), indent=2))