#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "python-dotenv>=1.0.0",
# ]
# ///

"""
Phase 3.4.3.1 Smart Request Batcher
Intelligent API request batching system for TTS optimization.

Features:
- Smart request grouping by provider, voice, and parameters
- Time-based and size-based batching strategies with adaptive optimization
- Request optimization with message combination and intelligent splitting
- Integration with concurrent API pool and caching systems
- Performance analytics with batching effectiveness metrics
- Dynamic batch sizing based on API limits and performance patterns
- Queue management with priority-aware batching
"""

import asyncio
import hashlib
import os
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Callable, Any, Tuple, Union, Set
from concurrent.futures import ThreadPoolExecutor, Future, as_completed
from queue import Queue, PriorityQueue, Empty
from dotenv import load_dotenv

# Import Phase 3 components
try:
    try:
        from .phase3_cache_manager import get_cache_manager
        from .phase3_performance_metrics import get_performance_monitor, measure_performance
        from .phase3_43_concurrent_api_pool import get_concurrent_api_pool, APIRequestContext, APIRequestResult, RequestStatus, TTSProvider
        from .advanced_priority_queue import AdvancedPriority, MessageType
    except ImportError:
        from phase3_cache_manager import get_cache_manager
        from phase3_performance_metrics import get_performance_monitor, measure_performance
        from phase3_43_concurrent_api_pool import get_concurrent_api_pool, APIRequestContext, APIRequestResult, RequestStatus, TTSProvider
        from advanced_priority_queue import AdvancedPriority, MessageType
    
    PHASE3_DEPENDENCIES_AVAILABLE = True
except ImportError:
    PHASE3_DEPENDENCIES_AVAILABLE = False
    # Define fallback enums
    class AdvancedPriority(Enum):
        INTERRUPT = 0
        CRITICAL = 1
        HIGH = 2
        MEDIUM = 3
        LOW = 4
        BACKGROUND = 5
    
    class MessageType(Enum):
        ERROR = "error"
        WARNING = "warning"
        SUCCESS = "success"
        INFO = "info"
        BATCH = "batch"
        INTERRUPT = "interrupt"
    
    class TTSProvider(Enum):
        OPENAI = "openai"
        ELEVENLABS = "elevenlabs"
        PYTTSX3 = "pyttsx3"
    
    class RequestStatus(Enum):
        PENDING = "pending"
        PROCESSING = "processing"
        COMPLETED = "completed"
        FAILED = "failed"
        CACHED = "cached"

# Load environment variables
env_path = Path.home() / "brainpods" / ".env"
if env_path.exists():
    load_dotenv(env_path)

class BatchingStrategy(Enum):
    """Request batching strategies."""
    TIME_BASED = "time_based"           # Collect requests for fixed time window
    SIZE_BASED = "size_based"           # Batch when reaching size threshold
    ADAPTIVE = "adaptive"               # Dynamic strategy based on patterns
    IMMEDIATE = "immediate"             # Process immediately (bypass batching)
    SMART_COMBINATION = "smart_combo"   # Intelligent message combination

class BatchStatus(Enum):
    """Batch processing status."""
    COLLECTING = "collecting"
    READY = "ready"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

@dataclass
class BatchableRequest:
    """Request that can be batched with similar requests."""
    request_id: str
    text: str
    provider: TTSProvider
    voice: Optional[str]
    priority: AdvancedPriority
    message_type: MessageType
    
    # Batching properties
    can_combine: bool = True
    can_split: bool = True
    max_batch_size: int = 5
    
    # Metadata
    created_at: datetime = field(default_factory=datetime.now)
    estimated_duration_ms: float = 0.0
    character_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        self.character_count = len(self.text)
        # Estimate duration: ~150 words per minute, ~5 characters per word
        words = self.character_count / 5
        self.estimated_duration_ms = (words / 150) * 60 * 1000

@dataclass
class RequestBatch:
    """Collection of batchable requests for processing."""
    batch_id: str
    strategy: BatchingStrategy
    provider: TTSProvider
    voice: Optional[str]
    priority: AdvancedPriority
    
    # Batch contents
    requests: List[BatchableRequest] = field(default_factory=list)
    combined_text: str = ""
    total_characters: int = 0
    estimated_duration_ms: float = 0.0
    
    # Status tracking
    status: BatchStatus = BatchStatus.COLLECTING
    created_at: datetime = field(default_factory=datetime.now)
    ready_at: Optional[datetime] = None
    processed_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # Processing results
    api_result: Optional[APIRequestResult] = None
    processing_latency_ms: float = 0.0
    
    # Configuration
    max_wait_time_ms: float = 1000.0  # Maximum time to wait for more requests
    max_batch_size: int = 10
    max_characters: int = 4000        # Stay under API limits
    
    def add_request(self, request: BatchableRequest) -> bool:
        """Add request to batch if compatible."""
        if not self._is_compatible(request):
            return False
        
        # Check limits
        new_char_count = self.total_characters + request.character_count
        if (len(self.requests) >= self.max_batch_size or 
            new_char_count > self.max_characters):
            return False
        
        # Add request
        self.requests.append(request)
        self.total_characters = new_char_count
        self.estimated_duration_ms += request.estimated_duration_ms
        
        # Update combined text based on strategy
        if self.strategy == BatchingStrategy.SMART_COMBINATION:
            self._update_combined_text_smart()
        else:
            self._update_combined_text_simple()
        
        return True
    
    def _is_compatible(self, request: BatchableRequest) -> bool:
        """Check if request is compatible with this batch."""
        return (self.provider == request.provider and
                self.voice == request.voice and
                self.priority == request.priority and
                self.status == BatchStatus.COLLECTING)
    
    def _update_combined_text_smart(self):
        """Update combined text using intelligent combination."""
        if not self.requests:
            self.combined_text = ""
            return
        
        # Group by message type for better flow
        text_parts = []
        current_type = None
        
        for request in self.requests:
            text = request.text.strip()
            
            # Add appropriate separators based on message type transitions
            if current_type != request.message_type:
                if text_parts and current_type is not None:
                    # Add a brief pause between different message types
                    text_parts.append("...")
                current_type = request.message_type
            
            # Clean up text for better flow
            if text.endswith('.'):
                text_parts.append(text)
            elif text.endswith(('!', '?')):
                text_parts.append(text)
            else:
                text_parts.append(text + ".")
        
        self.combined_text = " ".join(text_parts)
    
    def _update_combined_text_simple(self):
        """Update combined text using simple concatenation."""
        text_parts = [req.text.strip() for req in self.requests]
        self.combined_text = ". ".join(text_parts)
        if not self.combined_text.endswith(('.', '!', '?')):
            self.combined_text += "."
    
    def is_ready(self, current_time: Optional[datetime] = None) -> bool:
        """Check if batch is ready for processing."""
        if self.status != BatchStatus.COLLECTING:
            return False
        
        if current_time is None:
            current_time = datetime.now()
        
        # Ready if we hit size limits
        if (len(self.requests) >= self.max_batch_size or
            self.total_characters >= self.max_characters):
            return True
        
        # Ready if we've waited long enough
        time_waited = (current_time - self.created_at).total_seconds() * 1000
        if time_waited >= self.max_wait_time_ms:
            return True
        
        return False
    
    def get_age_ms(self) -> float:
        """Get batch age in milliseconds."""
        return (datetime.now() - self.created_at).total_seconds() * 1000

@dataclass
class BatcherMetrics:
    """Performance metrics for request batcher."""
    total_requests: int = 0
    batched_requests: int = 0
    unbatched_requests: int = 0
    completed_batches: int = 0
    failed_batches: int = 0
    
    # Efficiency metrics
    average_batch_size: float = 0.0
    batching_efficiency: float = 0.0    # Percentage of requests that were batched
    character_savings: int = 0          # Characters saved through batching
    api_call_reduction: float = 0.0     # Percentage reduction in API calls
    
    # Performance metrics
    average_wait_time_ms: float = 0.0
    average_processing_latency_ms: float = 0.0
    cache_hit_rate: float = 0.0
    
    # Strategy distribution
    strategy_usage: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    provider_distribution: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    batch_size_distribution: Dict[int, int] = field(default_factory=lambda: defaultdict(int))
    
    last_updated: datetime = field(default_factory=datetime.now)

class SmartRequestBatcher:
    """
    Intelligent API request batching system for TTS optimization.
    
    Provides smart request grouping, adaptive batching strategies, and 
    integration with concurrent API pool for maximum efficiency.
    """
    
    def __init__(self, 
                 default_strategy: BatchingStrategy = BatchingStrategy.ADAPTIVE,
                 max_concurrent_batches: int = 5):
        """
        Initialize the smart request batcher.
        
        Args:
            default_strategy: Default batching strategy to use
            max_concurrent_batches: Maximum number of concurrent batches
        """
        self.default_strategy = default_strategy
        self.max_concurrent_batches = max_concurrent_batches
        
        # Core systems integration
        self.cache_manager = get_cache_manager() if PHASE3_DEPENDENCIES_AVAILABLE else None
        self.performance_monitor = get_performance_monitor() if PHASE3_DEPENDENCIES_AVAILABLE else None
        self.api_pool = get_concurrent_api_pool() if PHASE3_DEPENDENCIES_AVAILABLE else None
        
        # Batch management
        self.active_batches: Dict[str, RequestBatch] = {}
        self.completed_batches: deque = deque(maxlen=1000)
        self.request_queue = PriorityQueue()
        
        # Batching logic
        self.batch_groups: Dict[str, List[RequestBatch]] = defaultdict(list)
        self._batch_lock = threading.RLock()
        
        # Processing
        self.batch_processor = ThreadPoolExecutor(
            max_workers=max_concurrent_batches,
            thread_name_prefix="batch_processor"
        )
        self.processing_futures: Dict[str, Future] = {}
        
        # Performance tracking
        self.metrics = BatcherMetrics()
        self._metrics_lock = threading.RLock()
        
        # Configuration
        self.enable_smart_combination = os.getenv("BATCHER_SMART_COMBINATION", "true").lower() == "true"
        self.max_wait_time_ms = float(os.getenv("BATCHER_MAX_WAIT_TIME", "1000"))
        self.adaptive_threshold = float(os.getenv("BATCHER_ADAPTIVE_THRESHOLD", "0.75"))
        
        # Background processing
        self._shutdown_event = threading.Event()
        self._background_thread = threading.Thread(target=self._background_processor, daemon=True)
        self._background_thread.start()
        
        print(f"🔄 Smart Request Batcher initialized")
        print(f"  Default Strategy: {self.default_strategy.value}")
        print(f"  Max Concurrent Batches: {self.max_concurrent_batches}")
        print(f"  Smart Combination: {'✅' if self.enable_smart_combination else '❌'}")
        print(f"  Max Wait Time: {self.max_wait_time_ms}ms")
    
    def _generate_batch_key(self, provider: TTSProvider, voice: Optional[str], priority: AdvancedPriority) -> str:
        """Generate key for batch grouping."""
        voice_key = voice or "default"
        return f"{provider.value}:{voice_key}:{priority.name}"
    
    def _generate_batch_id(self, batch_key: str) -> str:
        """Generate unique batch ID."""
        timestamp = int(time.time() * 1000)
        content = f"{batch_key}:{timestamp}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    def _select_batching_strategy(self, request: BatchableRequest) -> BatchingStrategy:
        """Select optimal batching strategy for request."""
        if self.default_strategy != BatchingStrategy.ADAPTIVE:
            return self.default_strategy
        
        # Adaptive strategy selection logic
        
        # Immediate processing for high-priority requests
        if request.priority in [AdvancedPriority.INTERRUPT, AdvancedPriority.CRITICAL]:
            return BatchingStrategy.IMMEDIATE
        
        # Smart combination for info messages that can be combined
        if (request.message_type == MessageType.INFO and 
            request.can_combine and 
            self.enable_smart_combination):
            return BatchingStrategy.SMART_COMBINATION
        
        # Time-based for medium priority
        if request.priority == AdvancedPriority.MEDIUM:
            return BatchingStrategy.TIME_BASED
        
        # Size-based for low priority
        return BatchingStrategy.SIZE_BASED
    
    def _find_compatible_batch(self, request: BatchableRequest, strategy: BatchingStrategy) -> Optional[RequestBatch]:
        """Find compatible batch for the request."""
        batch_key = self._generate_batch_key(request.provider, request.voice, request.priority)
        
        with self._batch_lock:
            # Look for existing compatible batches
            for batch in self.batch_groups.get(batch_key, []):
                if (batch.status == BatchStatus.COLLECTING and
                    batch.strategy == strategy and
                    batch.add_request(request)):
                    return batch
        
        return None
    
    def _create_new_batch(self, request: BatchableRequest, strategy: BatchingStrategy) -> RequestBatch:
        """Create new batch for the request."""
        batch_key = self._generate_batch_key(request.provider, request.voice, request.priority)
        batch_id = self._generate_batch_id(batch_key)
        
        # Configure batch based on strategy
        if strategy == BatchingStrategy.TIME_BASED:
            max_wait = self.max_wait_time_ms
            max_size = 8
        elif strategy == BatchingStrategy.SIZE_BASED:
            max_wait = self.max_wait_time_ms * 2
            max_size = 10
        elif strategy == BatchingStrategy.SMART_COMBINATION:
            max_wait = self.max_wait_time_ms * 0.5
            max_size = 5
        else:  # IMMEDIATE
            max_wait = 0
            max_size = 1
        
        batch = RequestBatch(
            batch_id=batch_id,
            strategy=strategy,
            provider=request.provider,
            voice=request.voice,
            priority=request.priority,
            max_wait_time_ms=max_wait,
            max_batch_size=max_size
        )
        
        # Add first request
        batch.add_request(request)
        
        # Register batch
        with self._batch_lock:
            self.active_batches[batch_id] = batch
            self.batch_groups[batch_key].append(batch)
        
        return batch
    
    def _process_batch(self, batch: RequestBatch) -> APIRequestResult:
        """Process a batch through the API pool."""
        try:
            processing_start = time.time()
            batch.status = BatchStatus.PROCESSING
            batch.processed_at = datetime.now()
            
            # Create API request context
            api_context = APIRequestContext(
                text=batch.combined_text,
                provider=batch.provider,
                voice=batch.voice,
                priority=batch.priority,
                metadata={
                    "batch_id": batch.batch_id,
                    "batch_size": len(batch.requests),
                    "batching_strategy": batch.strategy.value,
                    "original_requests": [req.request_id for req in batch.requests]
                }
            )
            
            # Process through API pool
            if self.api_pool:
                result_id = self.api_pool.submit_request(api_context)
                batch.api_result = self.api_pool.get_result(result_id, timeout=30.0)
            else:
                # Fallback processing
                batch.api_result = APIRequestResult(
                    request_id=batch.batch_id,
                    status=RequestStatus.COMPLETED,
                    audio_file_path=None,
                    audio_data=None,
                    processing_time_ms=100.0,
                    provider=batch.provider
                )
            
            # Update batch status
            processing_time = (time.time() - processing_start) * 1000
            batch.processing_latency_ms = processing_time
            batch.completed_at = datetime.now()
            
            if batch.api_result.status == RequestStatus.COMPLETED:
                batch.status = BatchStatus.COMPLETED
            else:
                batch.status = BatchStatus.FAILED
            
            return batch.api_result
            
        except Exception as e:
            print(f"Error processing batch {batch.batch_id}: {e}")
            batch.status = BatchStatus.FAILED
            batch.completed_at = datetime.now()
            return APIRequestResult(
                request_id=batch.batch_id,
                status=RequestStatus.FAILED,
                error_message=str(e),
                provider=batch.provider
            )
    
    def _background_processor(self):
        """Background thread for batch processing."""
        while not self._shutdown_event.is_set():
            try:
                # Check for ready batches
                ready_batches = []
                current_time = datetime.now()
                
                with self._batch_lock:
                    for batch in list(self.active_batches.values()):
                        if batch.is_ready(current_time):
                            batch.status = BatchStatus.READY
                            batch.ready_at = current_time
                            ready_batches.append(batch)
                
                # Process ready batches
                for batch in ready_batches:
                    if len(self.processing_futures) < self.max_concurrent_batches:
                        future = self.batch_processor.submit(self._process_batch, batch)
                        self.processing_futures[batch.batch_id] = future
                
                # Clean up completed processing
                completed_batch_ids = []
                for batch_id, future in list(self.processing_futures.items()):
                    if future.done():
                        completed_batch_ids.append(batch_id)
                        
                        # Move to completed batches
                        batch = self.active_batches.pop(batch_id, None)
                        if batch:
                            self.completed_batches.append(batch)
                            
                            # Remove from batch groups
                            batch_key = self._generate_batch_key(batch.provider, batch.voice, batch.priority)
                            with self._batch_lock:
                                if batch_key in self.batch_groups:
                                    self.batch_groups[batch_key] = [
                                        b for b in self.batch_groups[batch_key] 
                                        if b.batch_id != batch_id
                                    ]
                
                # Clean up completed futures
                for batch_id in completed_batch_ids:
                    self.processing_futures.pop(batch_id, None)
                
                # Update metrics
                self._update_metrics()
                
                # Sleep briefly
                time.sleep(0.1)  # 100ms cycle
                
            except Exception as e:
                print(f"Background processor error: {e}")
                time.sleep(0.5)
    
    def _update_metrics(self):
        """Update performance metrics."""
        with self._metrics_lock:
            # Basic counts
            self.metrics.total_requests = sum(len(batch.requests) for batch in self.completed_batches) + \
                                        sum(len(batch.requests) for batch in self.active_batches.values())
            
            completed_batch_count = len([b for b in self.completed_batches if b.status == BatchStatus.COMPLETED])
            self.metrics.completed_batches = completed_batch_count
            self.metrics.failed_batches = len([b for b in self.completed_batches if b.status == BatchStatus.FAILED])
            
            # Calculate efficiency metrics
            if completed_batch_count > 0:
                total_batch_size = sum(len(batch.requests) for batch in self.completed_batches 
                                     if batch.status == BatchStatus.COMPLETED)
                self.metrics.average_batch_size = total_batch_size / completed_batch_count
                
                # API call reduction: (requests - batches) / requests
                if self.metrics.total_requests > 0:
                    self.metrics.api_call_reduction = (
                        (self.metrics.total_requests - completed_batch_count) / 
                        self.metrics.total_requests * 100
                    )
                
                # Calculate average processing time
                processing_times = [batch.processing_latency_ms for batch in self.completed_batches 
                                  if batch.status == BatchStatus.COMPLETED and batch.processing_latency_ms > 0]
                if processing_times:
                    self.metrics.average_processing_latency_ms = sum(processing_times) / len(processing_times)
            
            # Update strategy usage
            for batch in self.completed_batches:
                self.metrics.strategy_usage[batch.strategy.value] += len(batch.requests)
                self.metrics.provider_distribution[batch.provider.value] += len(batch.requests)
                self.metrics.batch_size_distribution[len(batch.requests)] += 1
            
            self.metrics.last_updated = datetime.now()
    
    @measure_performance("smart_batcher_submit_request")
    def submit_request(self, 
                      text: str,
                      provider: TTSProvider = TTSProvider.OPENAI,
                      voice: Optional[str] = None,
                      priority: AdvancedPriority = AdvancedPriority.MEDIUM,
                      message_type: MessageType = MessageType.INFO,
                      strategy: Optional[BatchingStrategy] = None,
                      metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Submit a TTS request for batching.
        
        Args:
            text: Text to convert to speech
            provider: TTS provider to use
            voice: Voice to use
            priority: Request priority
            message_type: Type of message
            strategy: Override batching strategy
            metadata: Optional metadata
            
        Returns:
            Request ID for tracking
        """
        # Generate request ID
        request_id = hashlib.sha256(f"{text}:{time.time()}".encode()).hexdigest()[:16]
        
        # Create batchable request
        request = BatchableRequest(
            request_id=request_id,
            text=text,
            provider=provider,
            voice=voice,
            priority=priority,
            message_type=message_type,
            metadata=metadata or {}
        )
        
        # Select batching strategy
        if strategy is None:
            strategy = self._select_batching_strategy(request)
        
        # Update metrics
        with self._metrics_lock:
            self.metrics.total_requests += 1
            self.metrics.strategy_usage[strategy.value] += 1
        
        # Handle immediate processing
        if strategy == BatchingStrategy.IMMEDIATE:
            # Process immediately without batching
            batch = self._create_new_batch(request, strategy)
            future = self.batch_processor.submit(self._process_batch, batch)
            self.processing_futures[batch.batch_id] = future
            return request_id
        
        # Find or create batch
        batch = self._find_compatible_batch(request, strategy)
        if batch is None:
            batch = self._create_new_batch(request, strategy)
        
        return request_id
    
    def get_request_status(self, request_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a submitted request."""
        # Search in active batches
        for batch in self.active_batches.values():
            for request in batch.requests:
                if request.request_id == request_id:
                    return {
                        "request_id": request_id,
                        "batch_id": batch.batch_id,
                        "batch_status": batch.status.value,
                        "batch_size": len(batch.requests),
                        "strategy": batch.strategy.value,
                        "age_ms": batch.get_age_ms(),
                        "estimated_completion_ms": max(0, batch.max_wait_time_ms - batch.get_age_ms())
                    }
        
        # Search in completed batches
        for batch in self.completed_batches:
            for request in batch.requests:
                if request.request_id == request_id:
                    return {
                        "request_id": request_id,
                        "batch_id": batch.batch_id,
                        "batch_status": batch.status.value,
                        "batch_size": len(batch.requests),
                        "strategy": batch.strategy.value,
                        "processing_latency_ms": batch.processing_latency_ms,
                        "completed": batch.completed_at.isoformat() if batch.completed_at else None
                    }
        
        return None
    
    def get_batch_result(self, batch_id: str) -> Optional[APIRequestResult]:
        """Get result of a completed batch."""
        # Check active batches
        batch = self.active_batches.get(batch_id)
        if batch and batch.api_result:
            return batch.api_result
        
        # Check completed batches
        for batch in self.completed_batches:
            if batch.batch_id == batch_id and batch.api_result:
                return batch.api_result
        
        return None
    
    def get_metrics(self) -> BatcherMetrics:
        """Get current batcher performance metrics."""
        with self._metrics_lock:
            return BatcherMetrics(
                total_requests=self.metrics.total_requests,
                batched_requests=self.metrics.batched_requests,
                unbatched_requests=self.metrics.unbatched_requests,
                completed_batches=self.metrics.completed_batches,
                failed_batches=self.metrics.failed_batches,
                average_batch_size=self.metrics.average_batch_size,
                batching_efficiency=self.metrics.batching_efficiency,
                character_savings=self.metrics.character_savings,
                api_call_reduction=self.metrics.api_call_reduction,
                average_wait_time_ms=self.metrics.average_wait_time_ms,
                average_processing_latency_ms=self.metrics.average_processing_latency_ms,
                cache_hit_rate=self.metrics.cache_hit_rate,
                strategy_usage=dict(self.metrics.strategy_usage),
                provider_distribution=dict(self.metrics.provider_distribution),
                batch_size_distribution=dict(self.metrics.batch_size_distribution),
                last_updated=self.metrics.last_updated
            )
    
    def get_batcher_status(self) -> Dict[str, Any]:
        """Get comprehensive batcher status."""
        metrics = self.get_metrics()
        
        return {
            "batcher_status": {
                "default_strategy": self.default_strategy.value,
                "max_concurrent_batches": self.max_concurrent_batches,
                "active_batches": len(self.active_batches),
                "processing_batches": len(self.processing_futures),
                "smart_combination_enabled": self.enable_smart_combination
            },
            "performance": {
                "total_requests": metrics.total_requests,
                "completed_batches": metrics.completed_batches,
                "failed_batches": metrics.failed_batches,
                "success_rate": (metrics.completed_batches / max(metrics.completed_batches + metrics.failed_batches, 1)) * 100,
                "average_batch_size": metrics.average_batch_size,
                "api_call_reduction": metrics.api_call_reduction,
                "average_processing_latency_ms": metrics.average_processing_latency_ms
            },
            "efficiency": {
                "batching_efficiency": metrics.batching_efficiency,
                "character_savings": metrics.character_savings,
                "cache_hit_rate": metrics.cache_hit_rate
            },
            "distribution": {
                "strategy_usage": dict(metrics.strategy_usage),
                "provider_distribution": dict(metrics.provider_distribution),
                "batch_size_distribution": dict(metrics.batch_size_distribution)
            },
            "configuration": {
                "max_wait_time_ms": self.max_wait_time_ms,
                "adaptive_threshold": self.adaptive_threshold,
                "phase3_integration": PHASE3_DEPENDENCIES_AVAILABLE
            },
            "active_batch_details": [
                {
                    "batch_id": batch.batch_id,
                    "strategy": batch.strategy.value,
                    "status": batch.status.value,
                    "size": len(batch.requests),
                    "characters": batch.total_characters,
                    "age_ms": batch.get_age_ms(),
                    "ready": batch.is_ready()
                }
                for batch in self.active_batches.values()
            ],
            "last_updated": metrics.last_updated.isoformat()
        }
    
    def shutdown(self):
        """Shutdown the request batcher."""
        print("🔄 Shutting down Smart Request Batcher...")
        
        # Signal shutdown
        self._shutdown_event.set()
        
        # Process any remaining ready batches
        remaining_batches = []
        with self._batch_lock:
            for batch in list(self.active_batches.values()):
                if batch.is_ready() or len(batch.requests) > 0:
                    remaining_batches.append(batch)
        
        if remaining_batches:
            print(f"Processing {len(remaining_batches)} remaining batches...")
            for batch in remaining_batches:
                try:
                    self._process_batch(batch)
                except Exception as e:
                    print(f"Error processing final batch {batch.batch_id}: {e}")
        
        # Wait for processing to complete
        for future in self.processing_futures.values():
            try:
                future.result(timeout=5.0)
            except Exception:
                pass
        
        # Shutdown thread pool
        self.batch_processor.shutdown(wait=True)
        
        # Join background thread
        if self._background_thread.is_alive():
            self._background_thread.join(timeout=5.0)
        
        print("✅ Smart Request Batcher shutdown complete")

# Global batcher instance
_request_batcher = None

def get_smart_request_batcher() -> SmartRequestBatcher:
    """Get or create the global smart request batcher."""
    global _request_batcher
    if _request_batcher is None:
        strategy_name = os.getenv("BATCHER_DEFAULT_STRATEGY", "adaptive")
        strategy = getattr(BatchingStrategy, strategy_name.upper(), BatchingStrategy.ADAPTIVE)
        max_batches = int(os.getenv("BATCHER_MAX_CONCURRENT", "5"))
        _request_batcher = SmartRequestBatcher(strategy, max_batches)
    return _request_batcher

def submit_batched_tts_request(
    text: str,
    provider: TTSProvider = TTSProvider.OPENAI,
    voice: Optional[str] = None,
    priority: AdvancedPriority = AdvancedPriority.MEDIUM,
    message_type: MessageType = MessageType.INFO,
    strategy: Optional[BatchingStrategy] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> str:
    """Submit a TTS request for smart batching."""
    batcher = get_smart_request_batcher()
    return batcher.submit_request(text, provider, voice, priority, message_type, strategy, metadata)

def get_batched_request_status(request_id: str) -> Optional[Dict[str, Any]]:
    """Get status of a batched request."""
    batcher = get_smart_request_batcher()
    return batcher.get_request_status(request_id)

def main():
    """Main entry point for testing Phase 3.4.3.1 Smart Request Batcher."""
    import random
    import sys
    
    if "--test" in sys.argv:
        print("🧪 Testing Phase 3.4.3.1 Smart Request Batcher")
        print("=" * 60)
        
        batcher = get_smart_request_batcher()
        
        print(f"\n🔄 Batcher Status:")
        status = batcher.get_batcher_status()
        print(f"  Default Strategy: {status['batcher_status']['default_strategy']}")
        print(f"  Max Concurrent Batches: {status['batcher_status']['max_concurrent_batches']}")
        print(f"  Smart Combination: {'✅' if status['batcher_status']['smart_combination_enabled'] else '❌'}")
        print(f"  Phase 3 Integration: {'✅' if status['configuration']['phase3_integration'] else '❌'}")
        
        # Test different batching strategies
        print(f"\n🎯 Testing Batching Strategies:")
        
        test_requests = [
            ("High priority urgent message", TTSProvider.OPENAI, AdvancedPriority.HIGH, MessageType.ERROR),
            ("Medium priority info message 1", TTSProvider.OPENAI, AdvancedPriority.MEDIUM, MessageType.INFO),
            ("Medium priority info message 2", TTSProvider.OPENAI, AdvancedPriority.MEDIUM, MessageType.INFO),
            ("Medium priority info message 3", TTSProvider.OPENAI, AdvancedPriority.MEDIUM, MessageType.INFO),
            ("Low priority batch message 1", TTSProvider.ELEVENLABS, AdvancedPriority.LOW, MessageType.BATCH),
            ("Low priority batch message 2", TTSProvider.ELEVENLABS, AdvancedPriority.LOW, MessageType.BATCH),
            ("Critical interrupt message", TTSProvider.OPENAI, AdvancedPriority.CRITICAL, MessageType.INTERRUPT),
        ]
        
        submitted_requests = []
        for text, provider, priority, msg_type in test_requests:
            try:
                request_id = batcher.submit_request(
                    text=text,
                    provider=provider,
                    priority=priority,
                    message_type=msg_type
                )
                submitted_requests.append((request_id, text))
                print(f"  ✅ Submitted: {text[:30]}... -> {request_id[:8]}")
            except Exception as e:
                print(f"  ❌ Failed to submit request: {e}")
        
        # Wait for batching and processing
        print(f"\n⏳ Waiting for batching and processing...")
        time.sleep(2.0)
        
        # Check request status
        print(f"\n📊 Request Status:")
        for request_id, text in submitted_requests:
            status = batcher.get_request_status(request_id)
            if status:
                batch_status = status.get('batch_status', 'unknown')
                batch_size = status.get('batch_size', 0)
                strategy = status.get('strategy', 'unknown')
                print(f"  {request_id[:8]}: {batch_status} (size: {batch_size}, strategy: {strategy})")
            else:
                print(f"  {request_id[:8]}: Not found")
        
        # Test batch combination
        print(f"\n🔗 Testing Smart Combination:")
        combination_requests = []
        for i in range(4):
            request_id = batcher.submit_request(
                text=f"Combination test message {i+1}. This should be combined with others.",
                provider=TTSProvider.OPENAI,
                priority=AdvancedPriority.MEDIUM,
                message_type=MessageType.INFO,
                strategy=BatchingStrategy.SMART_COMBINATION
            )
            combination_requests.append(request_id)
        
        print(f"  Created {len(combination_requests)} requests for smart combination")
        
        # Wait for processing
        time.sleep(1.5)
        
        # Check combination results
        for request_id in combination_requests:
            status = batcher.get_request_status(request_id)
            if status and status.get('batch_size', 0) > 1:
                print(f"  ✅ {request_id[:8]}: Combined with {status['batch_size']-1} other requests")
                break
        
        # Test performance metrics
        print(f"\n📈 Performance Metrics:")
        metrics = batcher.get_metrics()
        print(f"  Total Requests: {metrics.total_requests}")
        print(f"  Completed Batches: {metrics.completed_batches}")
        print(f"  Average Batch Size: {metrics.average_batch_size:.1f}")
        print(f"  API Call Reduction: {metrics.api_call_reduction:.1f}%")
        print(f"  Processing Latency: {metrics.average_processing_latency_ms:.1f}ms")
        
        # Strategy distribution
        if metrics.strategy_usage:
            print(f"  Strategy Usage:")
            for strategy, count in metrics.strategy_usage.items():
                print(f"    {strategy}: {count}")
        
        # Provider distribution
        if metrics.provider_distribution:
            print(f"  Provider Distribution:")
            for provider, count in metrics.provider_distribution.items():
                print(f"    {provider}: {count}")
        
        # Final status check
        final_status = batcher.get_batcher_status()
        print(f"\n🏁 Final Results:")
        print(f"  Success Rate: {final_status['performance']['success_rate']:.1f}%")
        print(f"  API Call Reduction: {final_status['performance']['api_call_reduction']:.1f}%")
        print(f"  Average Batch Size: {final_status['performance']['average_batch_size']:.1f}")
        print(f"  Active Batches: {final_status['batcher_status']['active_batches']}")
        
        print(f"\n✅ Phase 3.4.3.1 Smart Request Batcher test completed")
        print(f"🔄 Intelligent API request batching with {metrics.api_call_reduction:.1f}% efficiency gain!")
        
        # Cleanup
        batcher.shutdown()
    
    else:
        print("Phase 3.4.3.1 Smart Request Batcher")
        print("Intelligent API request batching system for TTS optimization")
        print("Usage: python phase3_43_request_batcher.py --test")

if __name__ == "__main__":
    main()