#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "python-dotenv>=1.0.0",
# ]
# ///

"""
Phase 3 TTS Message Aggregator
Intelligent multi-message aggregation to prevent audio spam during batch operations.

Features:
- Batch operation detection
- Intelligent message clustering and summarization
- Context-aware aggregation timing
- Integration with Phase 2 coordination system
"""

import asyncio
import json
import os
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set, Callable, Any
from dotenv import load_dotenv

# Import Phase 2 coordination system
try:
    from .observability import TTSEvent, EventCategory, EventPriority, get_observability
    OBSERVABILITY_AVAILABLE = True
except ImportError:
    OBSERVABILITY_AVAILABLE = False

# Load environment variables
env_path = Path.home() / "brainpods" / ".env"
if env_path.exists():
    load_dotenv(env_path)

class AggregationType(Enum):
    """Types of message aggregation strategies."""
    NONE = "none"                    # No aggregation
    COUNT_SUMMARY = "count_summary"  # "Completed 5 operations"
    STATUS_SUMMARY = "status_summary" # "3 succeeded, 2 failed"
    BATCH_SUMMARY = "batch_summary"   # "Processed 10 files"
    ERROR_SUMMARY = "error_summary"   # "2 errors occurred"
    PROGRESSIVE = "progressive"       # Real-time updates with final summary

class AggregationDecision(Enum):
    """Decision outcomes for message aggregation."""
    SPEAK_IMMEDIATELY = "speak_immediately"  # Speak this message now
    WAIT_FOR_MORE = "wait_for_more"         # Wait for more messages to aggregate
    AGGREGATE_NOW = "aggregate_now"         # Create summary and speak
    DISCARD = "discard"                     # Don't speak (redundant)

@dataclass
class MessagePattern:
    """Pattern matching for similar messages."""
    template: str                    # Pattern template (e.g., "File {name} processed")
    category: EventCategory
    hook_type: str
    tool_name: str
    similarity_threshold: float = 0.8
    
    def matches(self, message: str, event: 'TTSEvent') -> bool:
        """Check if message matches this pattern."""
        if event.category != self.category:
            return False
        if event.hook_type != self.hook_type:
            return False
        if event.tool_name != self.tool_name:
            return False
        
        # Simple pattern matching - in production, use more sophisticated NLP
        template_words = set(self.template.lower().split())
        message_words = set(message.lower().split())
        
        # Remove variable parts (words in {})
        template_words = {word for word in template_words if not word.startswith('{')}
        
        if not template_words:
            return False
        
        overlap = len(template_words.intersection(message_words))
        similarity = overlap / len(template_words)
        
        return similarity >= self.similarity_threshold

@dataclass 
class MessageCluster:
    """Cluster of similar messages for aggregation."""
    pattern: MessagePattern
    messages: List['AggregatedMessage'] = field(default_factory=list)
    first_timestamp: datetime = field(default_factory=datetime.now)
    last_timestamp: datetime = field(default_factory=datetime.now)
    operation_id: Optional[str] = None
    
    def add_message(self, message: 'AggregatedMessage'):
        """Add a message to this cluster."""
        self.messages.append(message)
        self.last_timestamp = datetime.now()
        
        # Try to extract operation_id if not set
        if not self.operation_id and message.event.metadata:
            self.operation_id = message.event.metadata.get("operation_id")
    
    def should_aggregate(self, max_age_seconds: float = 5.0, min_messages: int = 3) -> bool:
        """Determine if cluster should be aggregated now."""
        age = (datetime.now() - self.first_timestamp).total_seconds()
        return len(self.messages) >= min_messages or age >= max_age_seconds
    
    def create_summary(self) -> str:
        """Create aggregated summary of messages in cluster."""
        if not self.messages:
            return ""
        
        # Group by success/failure
        successes = []
        failures = []
        warnings = []
        
        for msg in self.messages:
            message_lower = msg.original_message.lower()
            if any(word in message_lower for word in ["error", "failed", "exception"]):
                failures.append(msg)
            elif any(word in message_lower for word in ["warning", "deprecated"]):
                warnings.append(msg)
            else:
                successes.append(msg)
        
        # Create summary based on pattern and results
        total = len(self.messages)
        
        if self.pattern.category == EventCategory.FILE_OPERATION:
            summary = f"Processed {total} files"
            if failures:
                summary += f" with {len(failures)} errors"
            elif warnings:
                summary += f" with {len(warnings)} warnings"
            else:
                summary += " successfully"
                
        elif self.pattern.category == EventCategory.COMMAND_EXECUTION:
            summary = f"Executed {total} commands"
            if failures:
                summary += f", {len(failures)} failed"
            else:
                summary += " successfully"
                
        elif self.pattern.category == EventCategory.ERROR:
            summary = f"{total} errors occurred"
            
        else:
            # Generic summary
            if failures:
                summary = f"Completed {len(successes)} operations, {len(failures)} failed"
            else:
                summary = f"Completed {total} operations successfully"
        
        return summary

@dataclass
class AggregatedMessage:
    """Individual message being tracked for aggregation."""
    original_message: str
    event: 'TTSEvent'
    timestamp: datetime = field(default_factory=datetime.now)
    pattern: Optional[MessagePattern] = None
    cluster_id: Optional[str] = None

class MessageAggregator:
    """Intelligent message aggregator for TTS optimization."""
    
    def __init__(self):
        """Initialize the message aggregator."""
        self.buffer_duration = float(os.getenv("TTS_AGGREGATION_BUFFER_SECONDS", "5.0"))
        self.min_cluster_size = int(os.getenv("TTS_MIN_CLUSTER_SIZE", "3"))
        self.max_cluster_size = int(os.getenv("TTS_MAX_CLUSTER_SIZE", "10"))
        self.max_buffer_age = float(os.getenv("TTS_MAX_BUFFER_AGE", "10.0"))
        
        # Message tracking
        self.message_buffer: deque[AggregatedMessage] = deque(maxlen=100)
        self.active_clusters: Dict[str, MessageCluster] = {}
        self.patterns = self._load_aggregation_patterns()
        
        # Statistics
        self.stats = {
            "messages_processed": 0,
            "clusters_created": 0,
            "messages_aggregated": 0,
            "aggregation_ratio": 0.0
        }
        
        # Phase 2 integration
        if OBSERVABILITY_AVAILABLE:
            self.observability = get_observability()
        else:
            self.observability = None
    
    def _load_aggregation_patterns(self) -> List[MessagePattern]:
        """Load common message patterns for aggregation."""
        return [
            # File operations
            MessagePattern(
                template="File {filename} processed",
                category=EventCategory.FILE_OPERATION,
                hook_type="post_tool_use",
                tool_name="Write"
            ),
            MessagePattern(
                template="Reading file {filename}",
                category=EventCategory.FILE_OPERATION,
                hook_type="post_tool_use", 
                tool_name="Read"
            ),
            MessagePattern(
                template="Created {filename}",
                category=EventCategory.FILE_OPERATION,
                hook_type="post_tool_use",
                tool_name="Write"
            ),
            
            # Command executions
            MessagePattern(
                template="Command {command} executed",
                category=EventCategory.COMMAND_EXECUTION,
                hook_type="post_tool_use",
                tool_name="Bash"
            ),
            MessagePattern(
                template="Running {command}",
                category=EventCategory.COMMAND_EXECUTION,
                hook_type="pre_tool_use",
                tool_name="Bash"
            ),
            
            # Errors
            MessagePattern(
                template="Error in {operation}",
                category=EventCategory.ERROR,
                hook_type="post_tool_use",
                tool_name=""  # Any tool
            ),
            
            # General operations
            MessagePattern(
                template="Operation {operation} completed",
                category=EventCategory.COMPLETION,
                hook_type="post_tool_use",
                tool_name=""
            ),
        ]
    
    def should_aggregate_message(self, message: str, event: 'TTSEvent') -> AggregationDecision:
        """
        Determine if and how a message should be aggregated.
        
        Args:
            message: The TTS message text
            event: TTSEvent with metadata
            
        Returns:
            AggregationDecision indicating what to do with the message
        """
        # Always speak critical messages immediately
        if event.priority == EventPriority.CRITICAL:
            return AggregationDecision.SPEAK_IMMEDIATELY
        
        # Check for matching patterns
        matching_pattern = self._find_matching_pattern(message, event)
        
        if not matching_pattern:
            return AggregationDecision.SPEAK_IMMEDIATELY
        
        # Add to buffer
        aggregated_msg = AggregatedMessage(
            original_message=message,
            event=event,
            pattern=matching_pattern
        )
        self.message_buffer.append(aggregated_msg)
        
        # Check for existing cluster or create new one
        cluster_key = self._get_cluster_key(matching_pattern, event)
        
        if cluster_key in self.active_clusters:
            cluster = self.active_clusters[cluster_key]
            cluster.add_message(aggregated_msg)
            aggregated_msg.cluster_id = cluster_key
            
            # Check if cluster should be aggregated now
            if cluster.should_aggregate(self.buffer_duration, self.min_cluster_size):
                return AggregationDecision.AGGREGATE_NOW
            else:
                return AggregationDecision.WAIT_FOR_MORE
                
        else:
            # Create new cluster
            cluster = MessageCluster(
                pattern=matching_pattern,
                operation_id=event.metadata.get("operation_id") if event.metadata else None
            )
            cluster.add_message(aggregated_msg)
            self.active_clusters[cluster_key] = cluster
            aggregated_msg.cluster_id = cluster_key
            
            # For new clusters, wait for more messages unless it's been too long
            return AggregationDecision.WAIT_FOR_MORE
    
    def _find_matching_pattern(self, message: str, event: 'TTSEvent') -> Optional[MessagePattern]:
        """Find a pattern that matches the given message and event."""
        for pattern in self.patterns:
            if pattern.matches(message, event):
                return pattern
        return None
    
    def _get_cluster_key(self, pattern: MessagePattern, event: 'TTSEvent') -> str:
        """Generate a unique key for clustering similar messages."""
        # Include operation_id if available for better clustering
        operation_id = ""
        if event.metadata and event.metadata.get("operation_id"):
            operation_id = event.metadata["operation_id"]
        
        return f"{pattern.hook_type}:{pattern.tool_name}:{pattern.category.value}:{operation_id}"
    
    def create_aggregated_message(self, cluster_key: str) -> Optional[str]:
        """
        Create an aggregated message from a cluster.
        
        Args:
            cluster_key: Key identifying the cluster to aggregate
            
        Returns:
            Aggregated message string or None if cluster doesn't exist
        """
        if cluster_key not in self.active_clusters:
            return None
        
        cluster = self.active_clusters[cluster_key]
        summary = cluster.create_summary()
        
        # Update statistics
        self.stats["clusters_created"] += 1
        self.stats["messages_aggregated"] += len(cluster.messages)
        self._update_aggregation_ratio()
        
        # Remove cluster
        del self.active_clusters[cluster_key]
        
        return summary
    
    def process_expired_clusters(self) -> List[str]:
        """
        Process clusters that have exceeded maximum age.
        
        Returns:
            List of aggregated messages from expired clusters
        """
        expired_messages = []
        expired_keys = []
        
        current_time = datetime.now()
        
        for cluster_key, cluster in self.active_clusters.items():
            age = (current_time - cluster.first_timestamp).total_seconds()
            
            if age >= self.max_buffer_age:
                # Cluster has expired, aggregate it
                summary = cluster.create_summary()
                if summary:
                    expired_messages.append(summary)
                expired_keys.append(cluster_key)
        
        # Remove expired clusters
        for key in expired_keys:
            del self.active_clusters[key]
        
        return expired_messages
    
    def force_aggregate_all(self) -> List[str]:
        """
        Force aggregation of all active clusters.
        
        Returns:
            List of all aggregated messages
        """
        aggregated_messages = []
        
        for cluster_key in list(self.active_clusters.keys()):
            summary = self.create_aggregated_message(cluster_key)
            if summary:
                aggregated_messages.append(summary)
        
        return aggregated_messages
    
    def clean_buffer(self):
        """Clean old messages from buffer."""
        current_time = datetime.now()
        cutoff_time = current_time - timedelta(seconds=self.max_buffer_age * 2)
        
        # Remove old messages
        while (self.message_buffer and 
               self.message_buffer[0].timestamp < cutoff_time):
            self.message_buffer.popleft()
    
    def _update_aggregation_ratio(self):
        """Update aggregation ratio statistics."""
        if self.stats["messages_processed"] > 0:
            self.stats["aggregation_ratio"] = (
                self.stats["messages_aggregated"] / 
                self.stats["messages_processed"]
            )
    
    def get_statistics(self) -> Dict:
        """Get aggregation statistics."""
        return {
            **self.stats.copy(),
            "active_clusters": len(self.active_clusters),
            "buffer_size": len(self.message_buffer),
            "patterns_loaded": len(self.patterns)
        }
    
    def reset_statistics(self):
        """Reset aggregation statistics."""
        self.stats = {
            "messages_processed": 0,
            "clusters_created": 0,
            "messages_aggregated": 0,
            "aggregation_ratio": 0.0
        }

# Integration functions for hooks
def should_aggregate_tts_message(message: str, event_data: Dict) -> AggregationDecision:
    """
    Check if a TTS message should be aggregated.
    
    Args:
        message: TTS message text
        event_data: Event metadata (priority, category, hook_type, tool_name, etc.)
        
    Returns:
        AggregationDecision
    """
    if not OBSERVABILITY_AVAILABLE:
        return AggregationDecision.SPEAK_IMMEDIATELY
    
    # Create TTSEvent from data
    try:
        from .observability import EventPriority, EventCategory, TTSEvent
        
        event = TTSEvent(
            message=message,
            priority=EventPriority(event_data.get("priority", EventPriority.MEDIUM.value)),
            category=EventCategory(event_data.get("category", EventCategory.GENERAL.value)),
            hook_type=event_data.get("hook_type", ""),
            tool_name=event_data.get("tool_name", ""),
            metadata=event_data.get("metadata", {})
        )
    except (ValueError, KeyError):
        # Invalid event data, speak immediately
        return AggregationDecision.SPEAK_IMMEDIATELY
    
    aggregator = MessageAggregator()
    decision = aggregator.should_aggregate_message(message, event)
    
    # Update processing statistics
    aggregator.stats["messages_processed"] += 1
    
    return decision

def create_aggregated_tts_message(cluster_id: str) -> Optional[str]:
    """
    Create aggregated message for a cluster.
    
    Args:
        cluster_id: Cluster identifier
        
    Returns:
        Aggregated message text or None
    """
    aggregator = MessageAggregator()
    return aggregator.create_aggregated_message(cluster_id)

async def run_aggregation_loop():
    """
    Background loop to process expired clusters.
    This should be run as an async task in the main application.
    """
    aggregator = MessageAggregator()
    
    while True:
        try:
            # Process expired clusters
            expired_messages = aggregator.process_expired_clusters()
            
            # For each expired message, trigger TTS through normal channels
            for message in expired_messages:
                if OBSERVABILITY_AVAILABLE and aggregator.observability:
                    # Create event for aggregated message
                    from .observability import should_speak_event_coordinated, EventPriority, EventCategory
                    
                    should_speak_event_coordinated(
                        message=message,
                        priority=EventPriority.MEDIUM.value,
                        category=EventCategory.COMPLETION.value,
                        hook_type="aggregator",
                        tool_name="batch_summary"
                    )
            
            # Clean buffer
            aggregator.clean_buffer()
            
            # Wait before next check
            await asyncio.sleep(1.0)  # Check every second
            
        except Exception as e:
            print(f"Aggregation loop error: {e}")
            await asyncio.sleep(5.0)  # Wait longer on error

def main():
    """Main entry point for testing."""
    import sys
    
    # Test message patterns
    test_messages = [
        ("File report.txt processed successfully", {"priority": 3, "category": "file_operation", "hook_type": "post_tool_use", "tool_name": "Write"}),
        ("File data.json processed successfully", {"priority": 3, "category": "file_operation", "hook_type": "post_tool_use", "tool_name": "Write"}),
        ("File config.py processed successfully", {"priority": 3, "category": "file_operation", "hook_type": "post_tool_use", "tool_name": "Write"}),
        ("Command npm install executed", {"priority": 3, "category": "command_execution", "hook_type": "post_tool_use", "tool_name": "Bash"}),
        ("Command npm test executed", {"priority": 3, "category": "command_execution", "hook_type": "post_tool_use", "tool_name": "Bash"}),
        ("Error in file processing", {"priority": 1, "category": "error", "hook_type": "post_tool_use", "tool_name": "Write"}),
    ]
    
    if len(sys.argv) > 1:
        # Test single message
        message = " ".join(sys.argv[1:])
        event_data = {"priority": 3, "category": "general", "hook_type": "test", "tool_name": "test"}
        decision = should_aggregate_tts_message(message, event_data)
        print(f"Message: {message}")
        print(f"Decision: {decision.value}")
    else:
        # Run test suite
        print("🧪 Message Aggregator Test Suite")
        print("=" * 50)
        
        aggregator = MessageAggregator()
        
        print("\n📊 Testing message aggregation patterns...")
        
        for i, (message, event_data) in enumerate(test_messages, 1):
            print(f"\n📝 Test {i}: {message}")
            
            # Create event
            try:
                if OBSERVABILITY_AVAILABLE:
                    from .observability import EventPriority, EventCategory, TTSEvent
                    
                    event = TTSEvent(
                        message=message,
                        priority=EventPriority(event_data["priority"]),
                        category=EventCategory(event_data["category"]),
                        hook_type=event_data["hook_type"],
                        tool_name=event_data["tool_name"]
                    )
                    
                    decision = aggregator.should_aggregate_message(message, event)
                    print(f"Decision: {decision.value}")
                    
                    # Check if any clusters should be aggregated
                    for cluster_key, cluster in aggregator.active_clusters.items():
                        if cluster.should_aggregate(2.0, 2):  # Lower thresholds for testing
                            summary = aggregator.create_aggregated_message(cluster_key)
                            print(f"Aggregated: {summary}")
                            
            except ImportError:
                print("⚠️  Observability not available, using fallback")
        
        # Process any remaining clusters
        remaining = aggregator.force_aggregate_all()
        if remaining:
            print(f"\n📋 Final aggregated messages:")
            for msg in remaining:
                print(f"  - {msg}")
        
        print(f"\n📊 Statistics:")
        stats = aggregator.get_statistics()
        for key, value in stats.items():
            if isinstance(value, float):
                print(f"  {key}: {value:.2f}")
            else:
                print(f"  {key}: {value}")

if __name__ == "__main__":
    main()