#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "python-dotenv>=1.0.0",
# ]
# ///

"""
Phase 3.3 Advanced Priority Queue System
Sophisticated 5-tier priority queue with preemption, deduplication, and analytics.

Features:
- 5-tier priority system with interrupt capability
- Priority preemption for emergency messages
- Smart message deduplication and similarity matching
- Batch processing for related low-priority messages
- Age-based priority promotion
- Dynamic queue sizing and performance analytics
- Integration with Phase 2 coordination system
"""

import os
import time
import hashlib
import threading
from collections import deque, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Any, Callable
from dotenv import load_dotenv

# Load environment variables
env_path = Path.home() / "brainpods" / ".env"
if env_path.exists():
    load_dotenv(env_path)

class AdvancedPriority(Enum):
    """Enhanced 5-tier priority system with interrupt capability."""
    INTERRUPT = 0       # Emergency interruptions (stop current playback)
    CRITICAL = 1        # Errors, security blocks (immediate)
    HIGH = 2           # Slow ops, permissions (high priority)
    MEDIUM = 3         # Notable completions (medium priority)
    LOW = 4            # Regular operations (low priority)
    BACKGROUND = 5     # Status updates, minimal priority

class QueueState(Enum):
    """Queue processing states."""
    IDLE = "idle"
    PROCESSING = "processing"
    PREEMPTING = "preempting"
    BATCH_MODE = "batch_mode"
    SUSPENDED = "suspended"

class MessageType(Enum):
    """Message type classification for better handling."""
    ERROR = "error"
    WARNING = "warning"
    SUCCESS = "success"
    INFO = "info"
    BATCH = "batch"
    INTERRUPT = "interrupt"

@dataclass
class AdvancedTTSMessage:
    """Enhanced TTS message with advanced metadata."""
    content: str
    priority: AdvancedPriority
    message_type: MessageType
    created_at: datetime = field(default_factory=datetime.now)
    hook_type: str = ""
    tool_name: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Advanced features
    message_hash: str = field(init=False)
    similarity_score: float = 0.0
    batch_group: Optional[str] = None
    promoted_count: int = 0
    max_wait_time: Optional[int] = None
    preemption_allowed: bool = True
    
    def __post_init__(self):
        """Initialize computed fields."""
        self.message_hash = self._compute_hash()
        if self.max_wait_time is None:
            # Set default max wait based on priority
            wait_times = {
                AdvancedPriority.INTERRUPT: 0,
                AdvancedPriority.CRITICAL: 5,
                AdvancedPriority.HIGH: 15,
                AdvancedPriority.MEDIUM: 30,
                AdvancedPriority.LOW: 60,
                AdvancedPriority.BACKGROUND: 120
            }
            self.max_wait_time = wait_times.get(self.priority, 60)
    
    def _compute_hash(self) -> str:
        """Compute content hash for deduplication."""
        content_normalized = self.content.lower().strip()
        # Remove common variations that don't change meaning
        content_normalized = content_normalized.replace("bryan, ", "").replace("developer, ", "")
        return hashlib.md5(content_normalized.encode()).hexdigest()[:8]
    
    def age_seconds(self) -> float:
        """Get age of message in seconds."""
        return (datetime.now() - self.created_at).total_seconds()
    
    def is_stale(self) -> bool:
        """Check if message is too old to be relevant."""
        return self.age_seconds() > self.max_wait_time
    
    def should_promote(self) -> bool:
        """Check if message should be promoted due to age."""
        age = self.age_seconds()
        # Promote after 50% of max wait time
        promote_threshold = self.max_wait_time * 0.5
        return age > promote_threshold and self.promoted_count < 2

@dataclass
class QueueAnalytics:
    """Analytics data for queue performance monitoring."""
    total_messages: int = 0
    messages_by_priority: Dict[AdvancedPriority, int] = field(default_factory=lambda: defaultdict(int))
    messages_by_type: Dict[MessageType, int] = field(default_factory=lambda: defaultdict(int))
    duplicates_removed: int = 0
    messages_promoted: int = 0
    preemptions_triggered: int = 0
    batch_operations: int = 0
    average_wait_time: float = 0.0
    queue_efficiency: float = 1.0
    
    def update_efficiency(self, processed: int, total_time: float):
        """Update queue efficiency metrics."""
        if total_time > 0:
            self.queue_efficiency = processed / total_time
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert analytics to dictionary."""
        return {
            "total_messages": self.total_messages,
            "messages_by_priority": {p.name: count for p, count in self.messages_by_priority.items()},
            "messages_by_type": {t.name: count for t, count in self.messages_by_type.items()},
            "duplicates_removed": self.duplicates_removed,
            "messages_promoted": self.messages_promoted,
            "preemptions_triggered": self.preemptions_triggered,
            "batch_operations": self.batch_operations,
            "average_wait_time": self.average_wait_time,
            "queue_efficiency": self.queue_efficiency,
        }

class AdvancedPriorityQueue:
    """Advanced 5-tier priority queue with preemption and analytics."""
    
    def __init__(self):
        """Initialize the advanced priority queue."""
        self.queues: Dict[AdvancedPriority, deque] = {
            priority: deque() for priority in AdvancedPriority
        }
        self.state = QueueState.IDLE
        self.analytics = QueueAnalytics()
        
        # Deduplication and similarity tracking
        self.message_hashes: Set[str] = set()
        self.recent_content: deque = deque(maxlen=50)
        
        # Batch processing
        self.batch_groups: Dict[str, List[AdvancedTTSMessage]] = defaultdict(list)
        self.batch_threshold = int(os.getenv("TTS_BATCH_THRESHOLD", "3"))
        self.batch_timeout = int(os.getenv("TTS_BATCH_TIMEOUT", "5"))
        
        # Configuration
        self.max_queue_size = int(os.getenv("TTS_MAX_QUEUE_SIZE", "100"))
        self.similarity_threshold = float(os.getenv("TTS_SIMILARITY_THRESHOLD", "0.85"))
        self.deduplication_enabled = os.getenv("TTS_DEDUPLICATION", "true").lower() == "true"
        self.promotion_enabled = os.getenv("TTS_PRIORITY_PROMOTION", "true").lower() == "true"
        
        # Advanced deduplication configuration
        self.similarity_thresholds = {
            MessageType.ERROR: 0.9,      # High threshold for errors (less aggressive)
            MessageType.WARNING: 0.8,    # Medium threshold for warnings
            MessageType.SUCCESS: 0.7,    # Lower threshold for success (more aggressive)
            MessageType.INFO: 0.6,       # Lowest threshold for info (most aggressive)
            MessageType.BATCH: 0.9,      # High threshold for batches
            MessageType.INTERRUPT: 1.0,  # No deduplication for interrupts
        }
        
        # Contextual grouping patterns
        self.contextual_patterns = {
            'tool_file_ops': ['Read', 'Write', 'Edit', 'MultiEdit'],
            'tool_search': ['Grep', 'Glob', 'WebSearch'],
            'tool_execution': ['Bash', 'Task'],
            'tool_mcp': ['mcp__'],
        }
        
        # Threading for async operations
        self.lock = threading.RLock()
        self.preemption_callback: Optional[Callable] = None
        self.processing_callback: Optional[Callable[[AdvancedTTSMessage], None]] = None
        
        # Performance tracking
        self.last_cleanup_time = datetime.now()
        self.cleanup_interval = 30  # seconds
        
    def enqueue(self, message: AdvancedTTSMessage) -> bool:
        """
        Add message to appropriate priority queue with deduplication.
        
        Args:
            message: The TTS message to enqueue
            
        Returns:
            True if message was enqueued, False if deduplicated/rejected
        """
        with self.lock:
            self.analytics.total_messages += 1
            self.analytics.messages_by_priority[message.priority] += 1
            self.analytics.messages_by_type[message.message_type] += 1
            
            # Check for stale message
            if message.is_stale():
                return False
            
            # Deduplication check
            if self.deduplication_enabled and self._is_duplicate(message):
                self.analytics.duplicates_removed += 1
                return False
            
            # Handle interrupt priority - immediate processing
            if message.priority == AdvancedPriority.INTERRUPT:
                self._handle_interrupt(message)
                return True
            
            # Check for batch processing
            batch_key = self._get_batch_key(message)
            if batch_key and self._should_batch(message):
                self._add_to_batch(message, batch_key)
                return True
            
            # Add to appropriate priority queue
            self.queues[message.priority].append(message)
            self.message_hashes.add(message.message_hash)
            self.recent_content.append(message.content)
            
            # Cleanup if needed
            self._cleanup_if_needed()
            
            return True
    
    def dequeue(self) -> Optional[AdvancedTTSMessage]:
        """
        Get next message to process based on priority and age.
        
        Returns:
            Next message to process or None if queue is empty
        """
        with self.lock:
            # Process promotion first
            if self.promotion_enabled:
                self._process_promotions()
            
            # Process batches if ready
            batch_message = self._process_ready_batches()
            if batch_message:
                return batch_message
            
            # Get highest priority non-empty queue
            for priority in AdvancedPriority:
                if self.queues[priority]:
                    message = self.queues[priority].popleft()
                    
                    # Check if message is still valid
                    if message.is_stale():
                        continue
                    
                    self.message_hashes.discard(message.message_hash)
                    return message
            
            return None
    
    def peek(self) -> Optional[AdvancedTTSMessage]:
        """Get next message without removing it from queue."""
        with self.lock:
            for priority in AdvancedPriority:
                if self.queues[priority]:
                    return self.queues[priority][0]
            return None
    
    def size(self) -> int:
        """Get total number of messages in all queues."""
        with self.lock:
            return sum(len(queue) for queue in self.queues.values())
    
    def size_by_priority(self) -> Dict[AdvancedPriority, int]:
        """Get queue sizes by priority."""
        with self.lock:
            return {priority: len(queue) for priority, queue in self.queues.items()}
    
    def clear_priority(self, priority: AdvancedPriority) -> int:
        """Clear all messages of specific priority."""
        with self.lock:
            removed = len(self.queues[priority])
            for message in self.queues[priority]:
                self.message_hashes.discard(message.message_hash)
            self.queues[priority].clear()
            return removed
    
    def clear_all(self):
        """Clear all queues and reset state."""
        with self.lock:
            for queue in self.queues.values():
                queue.clear()
            self.message_hashes.clear()
            self.recent_content.clear()
            self.batch_groups.clear()
            self.state = QueueState.IDLE
    
    def set_preemption_callback(self, callback: Callable):
        """Set callback for handling preemption events."""
        self.preemption_callback = callback
    
    def set_processing_callback(self, callback: Callable[[AdvancedTTSMessage], None]):
        """Set callback for processing messages."""
        self.processing_callback = callback
    
    def get_analytics(self) -> QueueAnalytics:
        """Get current queue analytics."""
        with self.lock:
            # Update average wait time
            total_wait = 0
            count = 0
            for queue in self.queues.values():
                for message in queue:
                    total_wait += message.age_seconds()
                    count += 1
            
            if count > 0:
                self.analytics.average_wait_time = total_wait / count
            
            return self.analytics
    
    def get_status(self) -> Dict[str, Any]:
        """Get comprehensive queue status."""
        with self.lock:
            return {
                "state": self.state.value,
                "total_size": self.size(),
                "sizes_by_priority": {p.name: size for p, size in self.size_by_priority().items()},
                "batch_groups": len(self.batch_groups),
                "analytics": self.analytics.to_dict(),
                "configuration": {
                    "max_queue_size": self.max_queue_size,
                    "similarity_threshold": self.similarity_threshold,
                    "deduplication_enabled": self.deduplication_enabled,
                    "promotion_enabled": self.promotion_enabled,
                    "batch_threshold": self.batch_threshold,
                    "batch_timeout": self.batch_timeout,
                }
            }
    
    # Private methods
    
    def _is_duplicate(self, message: AdvancedTTSMessage) -> bool:
        """Check if message is a duplicate or too similar to recent messages with contextual awareness."""
        # Exact hash match
        if message.message_hash in self.message_hashes:
            return True
        
        # Get context-aware similarity threshold
        threshold = self.similarity_thresholds.get(message.message_type, self.similarity_threshold)
        
        # No deduplication for interrupt messages
        if message.message_type == MessageType.INTERRUPT:
            return False
        
        # Context-aware similarity check
        context_group = self._get_context_group(message)
        
        for recent_msg in list(self.queues[message.priority]):
            # Only compare within same context group for better accuracy
            recent_context = self._get_context_group(recent_msg)
            if context_group != recent_context:
                continue
                
            similarity = self._calculate_similarity(message.content, recent_msg.content)
            if similarity >= threshold:
                # Enhanced duplicate: Update metadata of existing message
                self._enhance_existing_message(recent_msg, message)
                return True
        
        # Also check recent content for cross-priority deduplication
        for recent_content in self.recent_content:
            similarity = self._calculate_similarity(message.content, recent_content)
            if similarity >= threshold:
                return True
        
        return False
    
    def _get_context_group(self, message: AdvancedTTSMessage) -> str:
        """Get contextual group for a message to improve deduplication accuracy."""
        tool_name = message.tool_name.lower()
        
        # Check tool patterns
        for pattern_name, tool_patterns in self.contextual_patterns.items():
            for pattern in tool_patterns:
                if pattern.lower() in tool_name:
                    return f"{pattern_name}:{message.message_type.value}"
        
        # Fallback to hook type + message type
        return f"{message.hook_type}:{message.message_type.value}"
    
    def _enhance_existing_message(self, existing: AdvancedTTSMessage, new: AdvancedTTSMessage):
        """Enhance existing message with information from duplicate message."""
        # Update metadata to reflect multiple occurrences
        if 'duplicate_count' not in existing.metadata:
            existing.metadata['duplicate_count'] = 1
        existing.metadata['duplicate_count'] += 1
        
        # Keep track of latest occurrence
        existing.metadata['last_duplicate'] = datetime.now().isoformat()
        
        # Merge relevant metadata
        if 'duration_ms' in new.metadata:
            # Average duration for multiple operations
            if 'avg_duration_ms' not in existing.metadata:
                existing.metadata['avg_duration_ms'] = existing.metadata.get('duration_ms', 0)
            
            count = existing.metadata['duplicate_count']
            current_avg = existing.metadata['avg_duration_ms']
            new_duration = new.metadata['duration_ms']
            existing.metadata['avg_duration_ms'] = ((current_avg * (count - 1)) + new_duration) / count
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """Calculate advanced similarity between two text strings using multiple algorithms."""
        # Normalize texts
        norm1 = self._normalize_text(text1)
        norm2 = self._normalize_text(text2)
        
        if not norm1 or not norm2:
            return 0.0
        
        # Multiple similarity algorithms
        jaccard_sim = self._jaccard_similarity(norm1, norm2)
        semantic_sim = self._semantic_similarity(norm1, norm2)
        structure_sim = self._structural_similarity(text1, text2)
        
        # Weighted combination of similarities
        combined_similarity = (
            jaccard_sim * 0.4 +      # Word overlap
            semantic_sim * 0.4 +     # Semantic meaning
            structure_sim * 0.2      # Text structure
        )
        
        return combined_similarity
    
    def _normalize_text(self, text: str) -> str:
        """Normalize text for comparison."""
        import re
        # Remove personalization prefixes
        text = re.sub(r'^(bryan|developer),?\s*', '', text.lower())
        # Remove common TTS artifacts
        text = re.sub(r'\s*completed?\s*', ' done ', text)
        text = re.sub(r'\s*finished?\s*', ' done ', text)
        text = re.sub(r'\s*successfully?\s*', ' ', text)
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        return text
    
    def _jaccard_similarity(self, text1: str, text2: str) -> float:
        """Calculate Jaccard similarity based on word sets."""
        words1 = set(text1.split())
        words2 = set(text2.split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = len(words1.intersection(words2))
        union = len(words1.union(words2))
        
        return intersection / union if union > 0 else 0.0
    
    def _semantic_similarity(self, text1: str, text2: str) -> float:
        """Calculate semantic similarity based on context and meaning."""
        # Define semantic groups
        semantic_groups = {
            'completion': {'done', 'complete', 'finished', 'ended', 'success'},
            'error': {'error', 'failed', 'failure', 'exception', 'crash'},
            'file_ops': {'read', 'write', 'edit', 'file', 'save', 'load'},
            'time': {'seconds', 'minutes', 'ms', 'milliseconds', 'time'},
            'size': {'bytes', 'kb', 'mb', 'gb', 'size', 'length'},
        }
        
        # Extract semantic features
        features1 = self._extract_semantic_features(text1, semantic_groups)
        features2 = self._extract_semantic_features(text2, semantic_groups)
        
        if not features1 or not features2:
            return 0.0
        
        # Calculate feature overlap
        common_features = features1.intersection(features2)
        total_features = features1.union(features2)
        
        return len(common_features) / len(total_features) if total_features else 0.0
    
    def _extract_semantic_features(self, text: str, semantic_groups: Dict[str, Set[str]]) -> Set[str]:
        """Extract semantic features from text."""
        words = set(text.split())
        features = set()
        
        for group_name, group_words in semantic_groups.items():
            if words.intersection(group_words):
                features.add(group_name)
        
        return features
    
    def _structural_similarity(self, text1: str, text2: str) -> float:
        """Calculate structural similarity based on text patterns."""
        # Length similarity
        len1, len2 = len(text1), len(text2)
        if len1 == 0 and len2 == 0:
            return 1.0
        length_sim = 1 - abs(len1 - len2) / max(len1, len2)
        
        # Pattern similarity (numbers, file paths, etc.)
        import re
        patterns = [
            r'\d+\.\d+',  # Decimal numbers
            r'\d+',       # Integers
            r'[/\\][\w\.]+',  # File paths
        ]
        
        pattern_matches = 0
        for pattern in patterns:
            matches1 = bool(re.search(pattern, text1))
            matches2 = bool(re.search(pattern, text2))
            if matches1 == matches2:
                pattern_matches += 1
        
        pattern_sim = pattern_matches / len(patterns)
        
        # Combined structural similarity
        return (length_sim * 0.7 + pattern_sim * 0.3)
    
    def _handle_interrupt(self, message: AdvancedTTSMessage):
        """Handle interrupt priority message - immediate preemption."""
        self.state = QueueState.PREEMPTING
        self.analytics.preemptions_triggered += 1
        
        # Trigger preemption callback if available
        if self.preemption_callback:
            try:
                self.preemption_callback(message)
            except Exception as e:
                print(f"Preemption callback error: {e}")
        
        # Add to interrupt queue for immediate processing
        self.queues[AdvancedPriority.INTERRUPT].append(message)
        self.message_hashes.add(message.message_hash)
    
    def _get_batch_key(self, message: AdvancedTTSMessage) -> Optional[str]:
        """Generate batch key for grouping similar messages."""
        if message.priority in [AdvancedPriority.INTERRUPT, AdvancedPriority.CRITICAL]:
            return None  # Don't batch high-priority messages
        
        # Batch by tool and message type
        return f"{message.tool_name}:{message.message_type.value}"
    
    def _should_batch(self, message: AdvancedTTSMessage) -> bool:
        """Determine if message should be batched."""
        return (
            message.priority in [AdvancedPriority.LOW, AdvancedPriority.BACKGROUND] and
            message.message_type in [MessageType.SUCCESS, MessageType.INFO]
        )
    
    def _add_to_batch(self, message: AdvancedTTSMessage, batch_key: str):
        """Add message to batch group."""
        message.batch_group = batch_key
        self.batch_groups[batch_key].append(message)
        
        # Check if batch is ready for processing
        if len(self.batch_groups[batch_key]) >= self.batch_threshold:
            self._process_batch(batch_key)
    
    def _process_batch(self, batch_key: str):
        """Process a batch of related messages."""
        if batch_key not in self.batch_groups:
            return
        
        messages = self.batch_groups[batch_key]
        if not messages:
            return
        
        # Create batch message
        batch_content = self._create_batch_content(messages)
        batch_message = AdvancedTTSMessage(
            content=batch_content,
            priority=messages[0].priority,  # Use first message priority
            message_type=MessageType.BATCH,
            hook_type="batch",
            tool_name=messages[0].tool_name,
            metadata={"batch_size": len(messages), "batch_key": batch_key}
        )
        
        # Add to queue and cleanup batch
        self.queues[batch_message.priority].append(batch_message)
        self.message_hashes.add(batch_message.message_hash)
        del self.batch_groups[batch_key]
        
        self.analytics.batch_operations += 1
    
    def _create_batch_content(self, messages: List[AdvancedTTSMessage]) -> str:
        """Create intelligent consolidated content from batch of messages."""
        if len(messages) == 1:
            return messages[0].content
        
        # Analyze messages for intelligent batching
        analysis = self._analyze_batch_messages(messages)
        
        # Generate context-aware batch summary
        if analysis['same_tool'] and analysis['same_operation']:
            # Same tool, same operation - count based summary
            tool_name = messages[0].tool_name
            operation = analysis['operation_type']
            count = len(messages)
            
            if analysis['has_timing']:
                avg_time = analysis['avg_duration'] / 1000  # Convert to seconds
                return f"{operation} completed {count} operations in {avg_time:.1f}s average"
            else:
                return f"{operation} completed {count} operations"
        
        elif analysis['same_tool']:
            # Same tool, different operations
            tool_name = messages[0].tool_name
            operations = analysis['operation_types']
            return f"{tool_name} completed {len(messages)} operations: {', '.join(operations)}"
        
        elif analysis['same_operation']:
            # Different tools, same operation
            operation = analysis['operation_type']
            tools = analysis['tool_names']
            return f"{operation}: {len(messages)} files processed"
        
        else:
            # Mixed batch - categorize by completion type
            success_count = sum(1 for m in messages if m.message_type == MessageType.SUCCESS)
            info_count = sum(1 for m in messages if m.message_type == MessageType.INFO)
            
            if success_count > 0 and info_count == 0:
                return f"{success_count} operations completed successfully"
            elif success_count == 0 and info_count > 0:
                return f"{info_count} status updates"
            else:
                return f"{len(messages)} operations completed"
    
    def _analyze_batch_messages(self, messages: List[AdvancedTTSMessage]) -> Dict[str, Any]:
        """Analyze batch messages to extract patterns for intelligent summarization."""
        if not messages:
            return {}
        
        analysis = {
            'same_tool': len(set(m.tool_name for m in messages)) == 1,
            'same_operation': False,
            'has_timing': False,
            'tool_names': list(set(m.tool_name for m in messages)),
            'operation_types': [],
            'operation_type': '',
            'avg_duration': 0,
            'file_count': 0,
        }
        
        # Extract operation types from content
        import re
        operation_patterns = {
            'reading': r'reading\s+file|read\s+file|file.*read',
            'writing': r'writing\s+file|wrote\s+file|file.*written',
            'editing': r'editing\s+file|edited\s+file|file.*edited',
            'searching': r'searching|found|search\s+complete',
            'processing': r'processing|processed|complete',
            'executing': r'executing|executed|running|ran',
        }
        
        operations = []
        for message in messages:
            content_lower = message.content.lower()
            for op_name, pattern in operation_patterns.items():
                if re.search(pattern, content_lower):
                    operations.append(op_name)
                    break
            else:
                operations.append('operation')
        
        analysis['operation_types'] = list(set(operations))
        analysis['same_operation'] = len(set(operations)) == 1
        if analysis['same_operation']:
            analysis['operation_type'] = operations[0]
        
        # Check for timing information
        durations = []
        for message in messages:
            if 'duration_ms' in message.metadata:
                durations.append(message.metadata['duration_ms'])
            elif 'avg_duration_ms' in message.metadata:
                durations.append(message.metadata['avg_duration_ms'])
        
        if durations:
            analysis['has_timing'] = True
            analysis['avg_duration'] = sum(durations) / len(durations)
        
        # Count file operations
        for message in messages:
            content_lower = message.content.lower()
            if 'file' in content_lower or message.tool_name in ['Read', 'Write', 'Edit', 'MultiEdit']:
                analysis['file_count'] += 1
        
        return analysis
    
    def _process_ready_batches(self) -> Optional[AdvancedTTSMessage]:
        """Process batches that have timed out."""
        current_time = datetime.now()
        
        for batch_key, messages in list(self.batch_groups.items()):
            if not messages:
                continue
            
            # Check if batch has timed out
            oldest_message = min(messages, key=lambda m: m.created_at)
            if oldest_message.age_seconds() >= self.batch_timeout:
                self._process_batch(batch_key)
                
                # Return the batch message if one was created
                for priority in [AdvancedPriority.LOW, AdvancedPriority.BACKGROUND]:
                    if self.queues[priority]:
                        last_message = self.queues[priority][-1]
                        if (hasattr(last_message, 'metadata') and 
                            last_message.metadata.get('batch_key') == batch_key):
                            return self.queues[priority].pop()
        
        return None
    
    def _process_promotions(self):
        """Process age-based priority promotions."""
        for current_priority in reversed(list(AdvancedPriority)):
            if current_priority == AdvancedPriority.INTERRUPT:
                continue  # Don't promote to interrupt
            
            queue = self.queues[current_priority]
            promoted_messages = []
            
            for message in list(queue):
                if message.should_promote():
                    # Promote to next higher priority
                    higher_priorities = [p for p in AdvancedPriority if p.value < current_priority.value]
                    if higher_priorities:
                        target_priority = max(higher_priorities, key=lambda p: p.value)
                        
                        queue.remove(message)
                        message.priority = target_priority
                        message.promoted_count += 1
                        promoted_messages.append(message)
                        
                        self.analytics.messages_promoted += 1
            
            # Add promoted messages to their new queues
            for message in promoted_messages:
                self.queues[message.priority].append(message)
    
    def _cleanup_if_needed(self):
        """Cleanup stale data periodically."""
        now = datetime.now()
        if (now - self.last_cleanup_time).total_seconds() >= self.cleanup_interval:
            self._cleanup_stale_data()
            self.last_cleanup_time = now
    
    def _cleanup_stale_data(self):
        """Remove stale messages and data structures."""
        # Clean stale messages from queues
        for priority, queue in self.queues.items():
            stale_messages = []
            for message in list(queue):
                if message.is_stale():
                    stale_messages.append(message)
            
            for message in stale_messages:
                queue.remove(message)
                self.message_hashes.discard(message.message_hash)
        
        # Clean stale batches
        stale_batches = []
        for batch_key, messages in self.batch_groups.items():
            if all(message.is_stale() for message in messages):
                stale_batches.append(batch_key)
        
        for batch_key in stale_batches:
            del self.batch_groups[batch_key]

# Global queue instance
_advanced_queue = None

def get_advanced_queue() -> AdvancedPriorityQueue:
    """Get or create the global advanced priority queue."""
    global _advanced_queue
    if _advanced_queue is None:
        _advanced_queue = AdvancedPriorityQueue()
    return _advanced_queue

# Convenience functions for integration
def enqueue_message(content: str, priority: AdvancedPriority, message_type: MessageType = MessageType.INFO, **kwargs) -> bool:
    """Enqueue a message with advanced priority queue."""
    message = AdvancedTTSMessage(
        content=content,
        priority=priority,
        message_type=message_type,
        **kwargs
    )
    return get_advanced_queue().enqueue(message)

def get_next_message() -> Optional[AdvancedTTSMessage]:
    """Get next message from advanced priority queue."""
    return get_advanced_queue().dequeue()

def get_queue_status() -> Dict[str, Any]:
    """Get comprehensive queue status."""
    return get_advanced_queue().get_status()

def main():
    """Main entry point for testing."""
    import sys
    import random
    
    queue = get_advanced_queue()
    
    if "--test-performance" in sys.argv:
        # Performance test
        print("🚀 Performance Testing Advanced Priority Queue")
        print("=" * 50)
        
        start_time = time.time()
        
        # Add test messages
        test_messages = [
            ("Error occurred", AdvancedPriority.CRITICAL, MessageType.ERROR),
            ("File processing complete", AdvancedPriority.LOW, MessageType.SUCCESS),
            ("Warning: deprecated API", AdvancedPriority.MEDIUM, MessageType.WARNING),
            ("Background task finished", AdvancedPriority.BACKGROUND, MessageType.INFO),
            ("Emergency: system halt", AdvancedPriority.INTERRUPT, MessageType.INTERRUPT),
        ]
        
        for i in range(100):
            content, priority, msg_type = random.choice(test_messages)
            message = AdvancedTTSMessage(
                content=f"{content} #{i}",
                priority=priority,
                message_type=msg_type,
                tool_name=f"Tool{i%5}",
                hook_type="test"
            )
            queue.enqueue(message)
        
        print(f"Enqueued 100 messages in {time.time() - start_time:.3f}s")
        
        # Process messages
        start_time = time.time()
        processed = 0
        while queue.size() > 0:
            message = queue.dequeue()
            if message:
                processed += 1
        
        process_time = time.time() - start_time
        print(f"Processed {processed} messages in {process_time:.3f}s")
        print(f"Rate: {processed/process_time:.1f} messages/second")
        
    else:
        # Standard test
        print("🧪 Advanced Priority Queue Test Suite")
        print("=" * 50)
        
        # Test priority ordering
        test_messages = [
            AdvancedTTSMessage("Low priority", AdvancedPriority.LOW, MessageType.INFO),
            AdvancedTTSMessage("Critical error", AdvancedPriority.CRITICAL, MessageType.ERROR),
            AdvancedTTSMessage("Medium task", AdvancedPriority.MEDIUM, MessageType.SUCCESS),
            AdvancedTTSMessage("Background info", AdvancedPriority.BACKGROUND, MessageType.INFO),
            AdvancedTTSMessage("Emergency stop", AdvancedPriority.INTERRUPT, MessageType.INTERRUPT),
        ]
        
        print("\n📝 Testing Priority Ordering:")
        for message in test_messages:
            queue.enqueue(message)
            print(f"  Enqueued: {message.priority.name} - {message.content}")
        
        print(f"\n📊 Queue Status: {queue.size()} total messages")
        sizes = queue.size_by_priority()
        for priority, size in sizes.items():
            if size > 0:
                print(f"  {priority.name}: {size} messages")
        
        print("\n🎯 Processing Messages by Priority:")
        while queue.size() > 0:
            message = queue.dequeue()
            if message:
                print(f"  Processed: {message.priority.name} - {message.content}")
        
        print("\n📈 Final Analytics:")
        analytics = queue.get_analytics()
        for key, value in analytics.to_dict().items():
            print(f"  {key}: {value}")

if __name__ == "__main__":
    main()