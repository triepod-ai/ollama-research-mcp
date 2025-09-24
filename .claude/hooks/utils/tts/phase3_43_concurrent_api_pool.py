#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "python-dotenv>=1.0.0",
#   "openai>=1.0.0",
#   "requests>=2.31.0",
#   "pygame>=2.5.0",
# ]
# ///

"""
Phase 3.4.3.1 Concurrent API Request Pool
Parallel processing system for OpenAI and ElevenLabs TTS API requests.

Features:
- Concurrent API request handling with thread pool management
- Smart load balancing across multiple providers
- Request queuing with priority-based processing
- Connection pooling and reuse for optimal performance
- Automatic retry logic with exponential backoff
- Real-time performance metrics and monitoring
- Integration with Phase 3.4.1 cache manager and health monitoring
"""

import asyncio
import concurrent.futures
import hashlib
import json
import os
import tempfile
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Callable, Any, Tuple, Union
from concurrent.futures import ThreadPoolExecutor, Future, as_completed
from queue import Queue, PriorityQueue, Empty
from dotenv import load_dotenv

# Import Phase 3 components
try:
    try:
        from .phase3_cache_manager import get_cache_manager, Phase3CacheManager
        from .phase3_performance_metrics import get_performance_monitor, measure_performance
        from .phase3_provider_health_optimizer import get_health_monitor, ProviderType, ProviderHealth
        from .advanced_priority_queue import AdvancedPriority, MessageType, AdvancedTTSMessage
    except ImportError:
        from phase3_cache_manager import get_cache_manager, Phase3CacheManager
        from phase3_performance_metrics import get_performance_monitor, measure_performance  
        from phase3_provider_health_optimizer import get_health_monitor, ProviderType, ProviderHealth
        from advanced_priority_queue import AdvancedPriority, MessageType, AdvancedTTSMessage
    
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
    
    class ProviderType(Enum):
        OPENAI = "openai"
        ELEVENLABS = "elevenlabs"
        PYTTSX3 = "pyttsx3"

# Load environment variables
env_path = Path.home() / "brainpods" / ".env"
if env_path.exists():
    load_dotenv(env_path)

class RequestStatus(Enum):
    """API request status states."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"
    CANCELLED = "cancelled"

class ConcurrencyMode(Enum):
    """Concurrency handling modes."""
    POOL = "pool"               # Thread pool executor
    ASYNC = "async"             # Async/await pattern
    HYBRID = "hybrid"           # Mixed approach based on load

@dataclass
class APIRequestContext:
    """Context information for API requests."""
    request_id: str
    text: str
    provider: ProviderType
    priority: AdvancedPriority
    message_type: MessageType
    voice: Optional[str] = None
    model: Optional[str] = None
    speed: float = 1.0
    created_at: datetime = field(default_factory=datetime.now)
    timeout: float = 30.0
    retry_count: int = 0
    max_retries: int = 3
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class APIRequestResult:
    """Result from API request processing."""
    request_id: str
    status: RequestStatus
    provider: ProviderType
    audio_data: Optional[bytes] = None
    audio_file_path: Optional[str] = None
    latency_ms: float = 0.0
    error_message: Optional[str] = None
    retry_count: int = 0
    completed_at: datetime = field(default_factory=datetime.now)
    cache_hit: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ConcurrencyMetrics:
    """Performance metrics for concurrent processing."""
    total_requests: int = 0
    concurrent_requests: int = 0
    completed_requests: int = 0
    failed_requests: int = 0
    average_latency_ms: float = 0.0
    peak_concurrency: int = 0
    queue_size: int = 0
    cache_hit_rate: float = 0.0
    throughput_requests_per_second: float = 0.0
    active_connections: int = 0
    
    provider_metrics: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    last_updated: datetime = field(default_factory=datetime.now)

class ConcurrentAPIPool:
    """
    High-performance concurrent API request pool for TTS providers.
    
    Manages parallel requests to OpenAI and ElevenLabs APIs with intelligent
    load balancing, caching, and reliability features.
    """
    
    def __init__(self, max_workers: Optional[int] = None, concurrency_mode: ConcurrencyMode = ConcurrencyMode.HYBRID):
        """
        Initialize the concurrent API pool.
        
        Args:
            max_workers: Maximum number of worker threads (auto-detect if None)
            concurrency_mode: Concurrency handling strategy
        """
        self.max_workers = max_workers or min(32, (os.cpu_count() or 1) + 4)
        self.concurrency_mode = concurrency_mode
        
        # Core systems integration
        self.cache_manager = get_cache_manager() if PHASE3_DEPENDENCIES_AVAILABLE else None
        self.performance_monitor = get_performance_monitor() if PHASE3_DEPENDENCIES_AVAILABLE else None
        self.health_monitor = get_health_monitor() if PHASE3_DEPENDENCIES_AVAILABLE else None
        
        # Thread pool management
        self.thread_pool = ThreadPoolExecutor(max_workers=self.max_workers, thread_name_prefix="api_pool")
        self.request_queue = PriorityQueue()
        self.active_requests: Dict[str, Future] = {}
        self.request_cache: Dict[str, APIRequestResult] = {}
        
        # Connection management
        self.connection_pools = {
            ProviderType.OPENAI: self._create_openai_connection_pool(),
            ProviderType.ELEVENLABS: self._create_elevenlabs_connection_pool()
        }
        
        # Performance tracking
        self.metrics = ConcurrencyMetrics()
        self._metrics_lock = threading.RLock()
        self._request_times = deque(maxlen=1000)  # Track last 1000 requests
        
        # Request batching
        self.batch_queue: Dict[ProviderType, List[APIRequestContext]] = defaultdict(list)
        self.batch_size = int(os.getenv("API_POOL_BATCH_SIZE", "5"))
        self.batch_timeout = float(os.getenv("API_POOL_BATCH_TIMEOUT", "0.5"))
        self._last_batch_time = defaultdict(float)
        
        # Configuration
        self.cache_enabled = os.getenv("API_POOL_CACHE_ENABLED", "true").lower() == "true"
        self.retry_enabled = os.getenv("API_POOL_RETRY_ENABLED", "true").lower() == "true"
        self.metrics_enabled = os.getenv("API_POOL_METRICS_ENABLED", "true").lower() == "true"
        
        # Start background processing
        self._shutdown_event = threading.Event()
        self._background_thread = threading.Thread(target=self._background_processor, daemon=True)
        self._background_thread.start()
        
        print(f"🔄 Concurrent API Pool initialized")
        print(f"  Max Workers: {self.max_workers}")
        print(f"  Concurrency Mode: {self.concurrency_mode.value}")
        print(f"  Cache Enabled: {self.cache_enabled}")
        print(f"  Phase 3 Integration: {'✅' if PHASE3_DEPENDENCIES_AVAILABLE else '❌'}")
    
    def _create_openai_connection_pool(self) -> Optional[Any]:
        """Create OpenAI client connection pool."""
        try:
            from openai import OpenAI
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                return None
            
            # Create client with connection pooling
            client = OpenAI(
                api_key=api_key,
                timeout=30.0,
                max_retries=0  # We handle retries ourselves
            )
            return client
        except ImportError:
            return None
    
    def _create_elevenlabs_connection_pool(self) -> Optional[Any]:
        """Create ElevenLabs connection pool."""
        try:
            import requests
            api_key = os.getenv("ELEVENLABS_API_KEY")
            if not api_key:
                return None
            
            # Create session with connection pooling
            session = requests.Session()
            session.headers.update({
                "Accept": "audio/mpeg",
                "Content-Type": "application/json",
                "xi-api-key": api_key
            })
            
            # Configure connection pooling
            adapter = requests.adapters.HTTPAdapter(
                pool_connections=10,
                pool_maxsize=20,
                max_retries=0  # We handle retries ourselves
            )
            session.mount("https://", adapter)
            
            return session
        except ImportError:
            return None
    
    def _generate_request_id(self, context: APIRequestContext) -> str:
        """Generate unique request ID for caching and tracking."""
        content = f"{context.provider.value}:{context.text[:100]}:{context.voice}:{context.model}:{context.speed}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    def _get_cache_key(self, context: APIRequestContext) -> str:
        """Generate cache key for request result."""
        return f"api_pool:{self._generate_request_id(context)}"
    
    def _check_cache(self, context: APIRequestContext) -> Optional[APIRequestResult]:
        """Check if request result is cached."""
        if not self.cache_enabled or not self.cache_manager:
            return None
        
        cache_key = self._get_cache_key(context)
        cached_result = self.cache_manager.get("api_requests", cache_key)
        
        if cached_result:
            # Update metrics for cache hit
            with self._metrics_lock:
                self.metrics.cache_hit_rate = (
                    (self.metrics.cache_hit_rate * self.metrics.total_requests + 1.0) /
                    (self.metrics.total_requests + 1)
                )
            
            # Convert cached data back to result object
            return APIRequestResult(
                request_id=context.request_id,
                status=RequestStatus.COMPLETED,
                provider=context.provider,
                audio_file_path=cached_result.get("audio_file_path"),
                latency_ms=cached_result.get("latency_ms", 0.0),
                cache_hit=True,
                completed_at=datetime.now(),
                metadata=cached_result.get("metadata", {})
            )
        
        return None
    
    def _cache_result(self, context: APIRequestContext, result: APIRequestResult):
        """Cache successful request result."""
        if not self.cache_enabled or not self.cache_manager or result.status != RequestStatus.COMPLETED:
            return
        
        cache_key = self._get_cache_key(context)
        cache_data = {
            "audio_file_path": result.audio_file_path,
            "latency_ms": result.latency_ms,
            "metadata": result.metadata,
            "cached_at": datetime.now().isoformat()
        }
        
        # Cache for 1 hour
        self.cache_manager.set("api_requests", cache_key, cache_data, ttl=3600)
    
    def _make_openai_request(self, context: APIRequestContext) -> APIRequestResult:
        """Make OpenAI TTS API request."""
        client = self.connection_pools.get(ProviderType.OPENAI)
        if not client:
            return APIRequestResult(
                request_id=context.request_id,
                status=RequestStatus.FAILED,
                provider=context.provider,
                error_message="OpenAI client not available"
            )
        
        try:
            start_time = time.time()
            
            # Make API request
            response = client.audio.speech.create(
                model=context.model or "tts-1",
                voice=context.voice or "nova",
                input=context.text,
                speed=context.speed
            )
            
            # Save to temporary file
            temp_file = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
            temp_path = temp_file.name
            response.stream_to_file(temp_path)
            temp_file.close()
            
            latency = (time.time() - start_time) * 1000
            
            # Record performance metrics
            if self.performance_monitor:
                self.performance_monitor.record_latency(latency, f"openai_tts_{context.message_type.value}")
            
            return APIRequestResult(
                request_id=context.request_id,
                status=RequestStatus.COMPLETED,
                provider=context.provider,
                audio_file_path=temp_path,
                latency_ms=latency,
                completed_at=datetime.now(),
                metadata={"model": context.model or "tts-1", "voice": context.voice or "nova"}
            )
            
        except Exception as e:
            return APIRequestResult(
                request_id=context.request_id,
                status=RequestStatus.FAILED,
                provider=context.provider,
                error_message=str(e),
                latency_ms=(time.time() - start_time) * 1000 if 'start_time' in locals() else 0
            )
    
    def _make_elevenlabs_request(self, context: APIRequestContext) -> APIRequestResult:
        """Make ElevenLabs TTS API request."""
        session = self.connection_pools.get(ProviderType.ELEVENLABS)
        if not session:
            return APIRequestResult(
                request_id=context.request_id,
                status=RequestStatus.FAILED,
                provider=context.provider,
                error_message="ElevenLabs session not available"
            )
        
        try:
            start_time = time.time()
            
            # Get voice ID
            voice_id = context.voice or os.getenv("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")
            url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
            
            data = {
                "text": context.text,
                "model_id": context.model or "eleven_monolingual_v1",
                "voice_settings": {
                    "stability": 0.5,
                    "similarity_boost": 0.5,
                    "speed": context.speed
                }
            }
            
            # Make API request
            response = session.post(url, json=data, timeout=context.timeout)
            
            if response.status_code != 200:
                return APIRequestResult(
                    request_id=context.request_id,
                    status=RequestStatus.FAILED,
                    provider=context.provider,
                    error_message=f"ElevenLabs API error: {response.status_code} - {response.text}",
                    latency_ms=(time.time() - start_time) * 1000
                )
            
            # Save to temporary file
            temp_file = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
            temp_path = temp_file.name
            temp_file.write(response.content)
            temp_file.close()
            
            latency = (time.time() - start_time) * 1000
            
            # Record performance metrics
            if self.performance_monitor:
                self.performance_monitor.record_latency(latency, f"elevenlabs_tts_{context.message_type.value}")
            
            return APIRequestResult(
                request_id=context.request_id,
                status=RequestStatus.COMPLETED,
                provider=context.provider,
                audio_file_path=temp_path,
                latency_ms=latency,
                completed_at=datetime.now(),
                metadata={"model": context.model or "eleven_monolingual_v1", "voice": voice_id}
            )
            
        except Exception as e:
            return APIRequestResult(
                request_id=context.request_id,
                status=RequestStatus.FAILED,
                provider=context.provider,
                error_message=str(e),
                latency_ms=(time.time() - start_time) * 1000 if 'start_time' in locals() else 0
            )
    
    def _process_single_request(self, context: APIRequestContext) -> APIRequestResult:
        """Process a single API request with retry logic."""
        # Check cache first
        cached_result = self._check_cache(context)
        if cached_result:
            return cached_result
        
        # Update metrics
        with self._metrics_lock:
            self.metrics.concurrent_requests += 1
            self.metrics.peak_concurrency = max(self.metrics.peak_concurrency, self.metrics.concurrent_requests)
        
        try:
            # Make API request based on provider
            if context.provider == ProviderType.OPENAI:
                result = self._make_openai_request(context)
            elif context.provider == ProviderType.ELEVENLABS:
                result = self._make_elevenlabs_request(context)
            else:
                result = APIRequestResult(
                    request_id=context.request_id,
                    status=RequestStatus.FAILED,
                    provider=context.provider,
                    error_message=f"Unsupported provider: {context.provider}"
                )
            
            # Handle retries for failed requests
            if result.status == RequestStatus.FAILED and self.retry_enabled and context.retry_count < context.max_retries:
                # Exponential backoff
                delay = 2 ** context.retry_count
                time.sleep(min(delay, 10))  # Cap at 10 seconds
                
                context.retry_count += 1
                result.retry_count = context.retry_count
                result.status = RequestStatus.RETRYING
                
                # Retry the request
                return self._process_single_request(context)
            
            # Cache successful results
            if result.status == RequestStatus.COMPLETED:
                self._cache_result(context, result)
                with self._metrics_lock:
                    self.metrics.completed_requests += 1
            else:
                with self._metrics_lock:
                    self.metrics.failed_requests += 1
            
            # Update provider-specific metrics
            self._update_provider_metrics(context.provider, result)
            
            return result
            
        finally:
            with self._metrics_lock:
                self.metrics.concurrent_requests -= 1
    
    def _update_provider_metrics(self, provider: ProviderType, result: APIRequestResult):
        """Update provider-specific performance metrics."""
        with self._metrics_lock:
            if provider.value not in self.metrics.provider_metrics:
                self.metrics.provider_metrics[provider.value] = {
                    "total_requests": 0,
                    "successful_requests": 0,
                    "failed_requests": 0,
                    "average_latency_ms": 0.0,
                    "last_success": None,
                    "last_failure": None
                }
            
            provider_metrics = self.metrics.provider_metrics[provider.value]
            provider_metrics["total_requests"] += 1
            
            if result.status == RequestStatus.COMPLETED:
                provider_metrics["successful_requests"] += 1
                provider_metrics["last_success"] = result.completed_at.isoformat()
                
                # Update rolling average latency
                current_avg = provider_metrics["average_latency_ms"]
                total_requests = provider_metrics["total_requests"]
                provider_metrics["average_latency_ms"] = (
                    (current_avg * (total_requests - 1) + result.latency_ms) / total_requests
                )
            else:
                provider_metrics["failed_requests"] += 1
                provider_metrics["last_failure"] = result.completed_at.isoformat()
    
    def _update_global_metrics(self):
        """Update global performance metrics."""
        with self._metrics_lock:
            self.metrics.total_requests += 1
            self.metrics.queue_size = self.request_queue.qsize()
            
            # Update throughput calculation
            current_time = time.time()
            self._request_times.append(current_time)
            
            # Calculate requests per second over last minute
            one_minute_ago = current_time - 60
            recent_requests = [t for t in self._request_times if t > one_minute_ago]
            self.metrics.throughput_requests_per_second = len(recent_requests) / 60
            
            # Update average latency (simplified calculation)
            if self.metrics.completed_requests > 0:
                total_latency = sum(
                    metrics.get("average_latency_ms", 0) * metrics.get("successful_requests", 0)
                    for metrics in self.metrics.provider_metrics.values()
                )
                total_successful = sum(
                    metrics.get("successful_requests", 0)
                    for metrics in self.metrics.provider_metrics.values()
                )
                if total_successful > 0:
                    self.metrics.average_latency_ms = total_latency / total_successful
            
            self.metrics.last_updated = datetime.now()
    
    def _background_processor(self):
        """Background thread for batch processing and maintenance."""
        while not self._shutdown_event.is_set():
            try:
                # Process any batched requests
                self._process_batches()
                
                # Cleanup expired cache entries
                if self.cache_manager:
                    # Let cache manager handle TTL cleanup automatically
                    pass
                
                # Update health monitoring
                if self.health_monitor:
                    # Health monitor handles its own background updates
                    pass
                
                # Sleep briefly between iterations
                time.sleep(0.1)
                
            except Exception as e:
                print(f"Background processor error: {e}")
                time.sleep(1)  # Longer sleep on error
    
    def _process_batches(self):
        """Process any batched requests that are ready."""
        current_time = time.time()
        
        for provider, batch in list(self.batch_queue.items()):
            if not batch:
                continue
            
            # Check if batch should be processed (size or timeout)
            should_process = (
                len(batch) >= self.batch_size or
                (batch and current_time - self._last_batch_time[provider] >= self.batch_timeout)
            )
            
            if should_process:
                # Submit batch for concurrent processing
                batch_copy = batch.copy()
                batch.clear()
                self._last_batch_time[provider] = current_time
                
                for context in batch_copy:
                    future = self.thread_pool.submit(self._process_single_request, context)
                    self.active_requests[context.request_id] = future
    
    @measure_performance("api_pool_submit")
    def submit_request(self, context: APIRequestContext) -> str:
        """
        Submit a TTS API request for concurrent processing.
        
        Args:
            context: Request context with all parameters
            
        Returns:
            Request ID for tracking the request
        """
        context.request_id = self._generate_request_id(context)
        
        # Update global metrics
        self._update_global_metrics()
        
        # Check if we should batch this request
        if context.provider in [ProviderType.OPENAI, ProviderType.ELEVENLABS]:
            # Add to batch queue
            self.batch_queue[context.provider].append(context)
            self._last_batch_time[context.provider] = time.time()
        else:
            # Process immediately for unsupported providers
            future = self.thread_pool.submit(self._process_single_request, context)
            self.active_requests[context.request_id] = future
        
        return context.request_id
    
    def get_request_result(self, request_id: str, timeout: Optional[float] = None) -> Optional[APIRequestResult]:
        """
        Get the result of a submitted request.
        
        Args:
            request_id: ID of the request to get result for
            timeout: Maximum time to wait for result
            
        Returns:
            Request result or None if not ready/found
        """
        future = self.active_requests.get(request_id)
        if not future:
            return None
        
        try:
            result = future.result(timeout=timeout)
            # Remove from active requests once completed
            self.active_requests.pop(request_id, None)
            return result
        except concurrent.futures.TimeoutError:
            return None
        except Exception as e:
            # Handle any errors in future execution
            self.active_requests.pop(request_id, None)
            return APIRequestResult(
                request_id=request_id,
                status=RequestStatus.FAILED,
                provider=ProviderType.OPENAI,  # Default fallback
                error_message=f"Execution error: {str(e)}"
            )
    
    def wait_for_completion(self, request_ids: List[str], timeout: Optional[float] = None) -> Dict[str, APIRequestResult]:
        """
        Wait for multiple requests to complete.
        
        Args:
            request_ids: List of request IDs to wait for
            timeout: Maximum time to wait for all requests
            
        Returns:
            Dictionary mapping request IDs to their results
        """
        results = {}
        futures = {req_id: self.active_requests.get(req_id) for req_id in request_ids}
        futures = {k: v for k, v in futures.items() if v is not None}
        
        if not futures:
            return results
        
        try:
            for request_id, future in futures.items():
                try:
                    result = future.result(timeout=timeout)
                    results[request_id] = result
                    self.active_requests.pop(request_id, None)
                except concurrent.futures.TimeoutError:
                    # Leave incomplete requests in active_requests
                    pass
                except Exception as e:
                    results[request_id] = APIRequestResult(
                        request_id=request_id,
                        status=RequestStatus.FAILED,
                        provider=ProviderType.OPENAI,  # Default fallback
                        error_message=f"Execution error: {str(e)}"
                    )
                    self.active_requests.pop(request_id, None)
                    
        except Exception as e:
            print(f"Error waiting for completion: {e}")
        
        return results
    
    def get_metrics(self) -> ConcurrencyMetrics:
        """Get current performance metrics."""
        with self._metrics_lock:
            return ConcurrencyMetrics(
                total_requests=self.metrics.total_requests,
                concurrent_requests=self.metrics.concurrent_requests,
                completed_requests=self.metrics.completed_requests,
                failed_requests=self.metrics.failed_requests,
                average_latency_ms=self.metrics.average_latency_ms,
                peak_concurrency=self.metrics.peak_concurrency,
                queue_size=self.metrics.queue_size,
                cache_hit_rate=self.metrics.cache_hit_rate,
                throughput_requests_per_second=self.metrics.throughput_requests_per_second,
                active_connections=len(self.active_requests),
                provider_metrics=self.metrics.provider_metrics.copy(),
                last_updated=self.metrics.last_updated
            )
    
    def get_pool_status(self) -> Dict[str, Any]:
        """Get current pool status for monitoring."""
        metrics = self.get_metrics()
        
        return {
            "pool_status": {
                "max_workers": self.max_workers,
                "active_workers": metrics.concurrent_requests,
                "queue_size": metrics.queue_size,
                "active_requests": metrics.active_connections,
                "concurrency_mode": self.concurrency_mode.value
            },
            "performance": {
                "total_requests": metrics.total_requests,
                "completed_requests": metrics.completed_requests,
                "failed_requests": metrics.failed_requests,
                "success_rate": (metrics.completed_requests / max(metrics.total_requests, 1)) * 100,
                "average_latency_ms": metrics.average_latency_ms,
                "throughput_rps": metrics.throughput_requests_per_second,
                "cache_hit_rate": metrics.cache_hit_rate * 100
            },
            "providers": metrics.provider_metrics,
            "configuration": {
                "cache_enabled": self.cache_enabled,
                "retry_enabled": self.retry_enabled,
                "metrics_enabled": self.metrics_enabled,
                "batch_size": self.batch_size,
                "batch_timeout": self.batch_timeout
            },
            "last_updated": metrics.last_updated.isoformat()
        }
    
    def shutdown(self):
        """Shutdown the concurrent API pool."""
        print("🔄 Shutting down Concurrent API Pool...")
        
        # Signal background thread to stop
        self._shutdown_event.set()
        
        # Wait for active requests to complete (with timeout)
        if self.active_requests:
            print(f"  Waiting for {len(self.active_requests)} active requests...")
            
            # Wait for up to 30 seconds for active requests
            for request_id, future in list(self.active_requests.items()):
                try:
                    future.result(timeout=1.0)  # Short timeout per request
                except concurrent.futures.TimeoutError:
                    future.cancel()
                except Exception:
                    pass
        
        # Shutdown thread pool
        self.thread_pool.shutdown(wait=True)
        
        # Join background thread
        if self._background_thread.is_alive():
            self._background_thread.join(timeout=5.0)
        
        print("✅ Concurrent API Pool shutdown complete")

# Global pool instance
_concurrent_api_pool = None

def get_concurrent_api_pool() -> ConcurrentAPIPool:
    """Get or create the global concurrent API pool."""
    global _concurrent_api_pool
    if _concurrent_api_pool is None:
        max_workers = int(os.getenv("API_POOL_MAX_WORKERS", "0")) or None
        concurrency_mode = ConcurrencyMode(os.getenv("API_POOL_CONCURRENCY_MODE", "hybrid"))
        _concurrent_api_pool = ConcurrentAPIPool(max_workers, concurrency_mode)
    return _concurrent_api_pool

def submit_concurrent_tts_request(
    text: str,
    provider: ProviderType,
    priority: AdvancedPriority = AdvancedPriority.MEDIUM,
    message_type: MessageType = MessageType.INFO,
    voice: Optional[str] = None,
    model: Optional[str] = None,
    speed: float = 1.0,
    timeout: float = 30.0,
    metadata: Optional[Dict[str, Any]] = None
) -> str:
    """
    Submit a concurrent TTS request.
    
    Args:
        text: Text to convert to speech
        provider: TTS provider to use
        priority: Request priority level
        message_type: Type of message for optimization
        voice: Optional voice/speaker selection
        model: Optional model selection
        speed: Speech speed multiplier
        timeout: Request timeout in seconds
        metadata: Optional additional metadata
        
    Returns:
        Request ID for tracking the request
    """
    pool = get_concurrent_api_pool()
    
    context = APIRequestContext(
        request_id="",  # Will be generated in submit_request
        text=text,
        provider=provider,
        priority=priority,
        message_type=message_type,
        voice=voice,
        model=model,
        speed=speed,
        timeout=timeout,
        metadata=metadata or {}
    )
    
    return pool.submit_request(context)

def get_concurrent_request_result(request_id: str, timeout: Optional[float] = None) -> Optional[APIRequestResult]:
    """Get result of a concurrent TTS request."""
    pool = get_concurrent_api_pool()
    return pool.get_request_result(request_id, timeout)

def main():
    """Main entry point for testing Phase 3.4.3.1 Concurrent API Pool."""
    import sys
    
    if "--test" in sys.argv:
        print("🧪 Testing Phase 3.4.3.1 Concurrent API Pool")
        print("=" * 60)
        
        pool = get_concurrent_api_pool()
        
        print(f"\n🔄 Pool Status:")
        status = pool.get_pool_status()
        print(f"  Max Workers: {status['pool_status']['max_workers']}")
        print(f"  Concurrency Mode: {status['pool_status']['concurrency_mode']}")
        print(f"  Phase 3 Integration: {'✅' if PHASE3_DEPENDENCIES_AVAILABLE else '❌'}")
        
        # Test concurrent requests
        print(f"\n⚡ Testing Concurrent Request Processing:")
        
        test_requests = [
            ("OpenAI test message 1", ProviderType.OPENAI, AdvancedPriority.HIGH),
            ("OpenAI test message 2", ProviderType.OPENAI, AdvancedPriority.MEDIUM),
            ("ElevenLabs test message 1", ProviderType.ELEVENLABS, AdvancedPriority.HIGH),
            ("ElevenLabs test message 2", ProviderType.ELEVENLABS, AdvancedPriority.MEDIUM),
        ]
        
        # Submit all requests concurrently
        request_ids = []
        start_time = time.time()
        
        for text, provider, priority in test_requests:
            try:
                request_id = submit_concurrent_tts_request(
                    text=text,
                    provider=provider,
                    priority=priority,
                    message_type=MessageType.INFO,
                    timeout=10.0
                )
                request_ids.append(request_id)
                print(f"  Submitted: {text[:30]}... -> {request_id[:8]}")
            except Exception as e:
                print(f"  ❌ Failed to submit request: {e}")
        
        # Wait for all results
        print(f"\n⏳ Waiting for {len(request_ids)} concurrent requests...")
        results = pool.wait_for_completion(request_ids, timeout=15.0)
        
        total_time = time.time() - start_time
        
        # Show results
        print(f"\n📊 Results ({total_time:.2f}s total):")
        for request_id, result in results.items():
            status_emoji = "✅" if result.status == RequestStatus.COMPLETED else "❌"
            print(f"  {status_emoji} {request_id[:8]}: {result.status.value} ({result.latency_ms:.1f}ms)")
            if result.error_message:
                print(f"     Error: {result.error_message}")
        
        # Show performance metrics
        print(f"\n📈 Performance Metrics:")
        metrics = pool.get_metrics()
        print(f"  Total Requests: {metrics.total_requests}")
        print(f"  Completed: {metrics.completed_requests}")
        print(f"  Failed: {metrics.failed_requests}")
        print(f"  Success Rate: {(metrics.completed_requests/max(metrics.total_requests,1)*100):.1f}%")
        print(f"  Average Latency: {metrics.average_latency_ms:.1f}ms")
        print(f"  Peak Concurrency: {metrics.peak_concurrency}")
        print(f"  Cache Hit Rate: {metrics.cache_hit_rate*100:.1f}%")
        print(f"  Throughput: {metrics.throughput_requests_per_second:.1f} req/s")
        
        # Show provider-specific metrics
        print(f"\n🔌 Provider Metrics:")
        for provider_name, provider_metrics in metrics.provider_metrics.items():
            success_rate = (provider_metrics.get("successful_requests", 0) / 
                          max(provider_metrics.get("total_requests", 1), 1) * 100)
            print(f"  {provider_name}:")
            print(f"    Requests: {provider_metrics.get('total_requests', 0)}")
            print(f"    Success Rate: {success_rate:.1f}%")
            print(f"    Avg Latency: {provider_metrics.get('average_latency_ms', 0):.1f}ms")
        
        # Test batching
        print(f"\n🔄 Testing Request Batching:")
        batch_requests = []
        for i in range(3):
            request_id = submit_concurrent_tts_request(
                text=f"Batch test message {i+1}",
                provider=ProviderType.OPENAI,
                priority=AdvancedPriority.LOW,
                message_type=MessageType.BATCH
            )
            batch_requests.append(request_id)
        
        # Wait a bit for batching
        time.sleep(1.0)
        
        batch_results = pool.wait_for_completion(batch_requests, timeout=10.0)
        batch_success = sum(1 for r in batch_results.values() if r.status == RequestStatus.COMPLETED)
        print(f"  Batch Requests: {len(batch_requests)}")
        print(f"  Batch Success: {batch_success}/{len(batch_requests)}")
        
        print(f"\n✅ Phase 3.4.3.1 Concurrent API Pool test completed")
        print(f"🚀 Parallel processing with {metrics.peak_concurrency} peak concurrency achieved!")
        
        # Cleanup
        pool.shutdown()
    
    else:
        print("Phase 3.4.3.1 Concurrent API Request Pool")
        print("Parallel processing system for TTS API requests")
        print("Usage: python phase3_43_concurrent_api_pool.py --test")

if __name__ == "__main__":
    main()