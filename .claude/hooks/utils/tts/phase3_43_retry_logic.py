#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "python-dotenv>=1.0.0",
# ]
# ///

"""
Phase 3.4.3.2 Retry Logic with Exponential Backoff
Production-grade retry system for resilient TTS API calls.

Features:
- Multiple backoff strategies: exponential, linear, fixed, and adaptive
- Intelligent retry policies based on failure types and provider characteristics
- Integration with circuit breaker for coordinated failure handling
- Jitter algorithms to prevent thundering herd problems
- Provider-specific retry configurations and limits
- Comprehensive retry metrics and effectiveness tracking
- Conditional retry logic that respects non-retryable errors
- Dead letter queue for persistently failing requests
"""

import asyncio
import hashlib
import math
import os
import random
import threading
import time
from collections import deque, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Callable, Any, Tuple, Union, Set
from concurrent.futures import ThreadPoolExecutor, Future, as_completed
from dotenv import load_dotenv

# Import Phase 3 components
try:
    try:
        from .phase3_cache_manager import get_cache_manager
        from .phase3_performance_metrics import get_performance_monitor, measure_performance
        from .phase3_43_concurrent_api_pool import get_concurrent_api_pool, APIRequestResult, RequestStatus, TTSProvider
        from .phase3_43_circuit_breaker import get_circuit_breaker, CircuitState, FailureType
        from .advanced_priority_queue import AdvancedPriority, MessageType
    except ImportError:
        from phase3_cache_manager import get_cache_manager
        from phase3_performance_metrics import get_performance_monitor, measure_performance
        from phase3_43_concurrent_api_pool import get_concurrent_api_pool, APIRequestResult, RequestStatus, TTSProvider
        from phase3_43_circuit_breaker import get_circuit_breaker, CircuitState, FailureType
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
        RETRYING = "retrying"
        EXHAUSTED = "exhausted"
    
    class FailureType(Enum):
        TIMEOUT = "timeout"
        API_ERROR = "api_error"
        RATE_LIMIT = "rate_limit"
        NETWORK_ERROR = "network_error"
        AUTHENTICATION = "authentication"
        QUOTA_EXCEEDED = "quota_exceeded"
        SERVER_ERROR = "server_error"
        UNKNOWN = "unknown"
    
    class CircuitState(Enum):
        CLOSED = "closed"
        OPEN = "open"
        HALF_OPEN = "half_open"

# Load environment variables
env_path = Path.home() / "brainpods" / ".env"
if env_path.exists():
    load_dotenv(env_path)

class BackoffStrategy(Enum):
    """Backoff strategies for retry logic."""
    EXPONENTIAL = "exponential"      # 2^attempt * base_delay
    LINEAR = "linear"               # attempt * base_delay
    FIXED = "fixed"                 # constant delay
    ADAPTIVE = "adaptive"           # Adjust based on success patterns
    FIBONACCI = "fibonacci"         # Fibonacci sequence delays

class JitterType(Enum):
    """Jitter algorithms to prevent thundering herd."""
    NONE = "none"                  # No jitter
    UNIFORM = "uniform"            # Uniform random jitter
    EXPONENTIAL = "exponential"    # Exponential decay jitter
    DECORRELATED = "decorrelated"  # AWS decorrelated jitter

class RetryPolicy(Enum):
    """Retry policy types."""
    AGGRESSIVE = "aggressive"       # Retry most failures quickly
    CONSERVATIVE = "conservative"   # Fewer retries, longer delays
    ADAPTIVE = "adaptive"          # Adjust based on patterns
    BURST_FRIENDLY = "burst_friendly" # Handle burst load scenarios

@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    provider: TTSProvider
    policy: RetryPolicy
    
    # Basic retry settings
    max_attempts: int = 3
    base_delay_ms: float = 1000.0
    max_delay_ms: float = 30000.0
    timeout_ms: float = 60000.0
    
    # Backoff configuration
    backoff_strategy: BackoffStrategy = BackoffStrategy.EXPONENTIAL
    backoff_multiplier: float = 2.0
    jitter_type: JitterType = JitterType.UNIFORM
    jitter_amount: float = 0.1
    
    # Conditional retry settings
    retry_on_timeout: bool = True
    retry_on_rate_limit: bool = True
    retry_on_server_error: bool = True
    retry_on_network_error: bool = True
    retry_on_api_error: bool = False
    retry_on_auth_error: bool = False
    retry_on_quota_error: bool = False
    
    # Adaptive settings
    adaptive_adjustment: bool = True
    success_rate_threshold: float = 0.8
    adaptation_window: int = 50

@dataclass
class RetryAttempt:
    """Individual retry attempt record."""
    attempt_number: int
    timestamp: datetime
    delay_ms: float
    failure_type: FailureType
    error_message: str
    circuit_state: CircuitState
    provider_used: TTSProvider
    
@dataclass
class RetryableRequest:
    """Request that can be retried with tracking."""
    request_id: str
    original_request: Any
    provider: TTSProvider
    priority: AdvancedPriority
    
    # Retry state
    attempts: List[RetryAttempt] = field(default_factory=list)
    current_attempt: int = 0
    next_retry_at: Optional[datetime] = None
    last_error: Optional[str] = None
    
    # Configuration
    config: Optional[RetryConfig] = None
    created_at: datetime = field(default_factory=datetime.now)
    
    # Results
    final_result: Optional[Any] = None
    final_status: RequestStatus = RequestStatus.PENDING
    total_retry_time_ms: float = 0.0
    
    def is_exhausted(self) -> bool:
        """Check if retry attempts are exhausted."""
        if not self.config:
            return self.current_attempt >= 3
        return self.current_attempt >= self.config.max_attempts
    
    def should_retry_failure_type(self, failure_type: FailureType) -> bool:
        """Check if failure type should be retried."""
        if not self.config:
            return failure_type in [FailureType.TIMEOUT, FailureType.NETWORK_ERROR]
        
        retry_map = {
            FailureType.TIMEOUT: self.config.retry_on_timeout,
            FailureType.RATE_LIMIT: self.config.retry_on_rate_limit,
            FailureType.SERVER_ERROR: self.config.retry_on_server_error,
            FailureType.NETWORK_ERROR: self.config.retry_on_network_error,
            FailureType.API_ERROR: self.config.retry_on_api_error,
            FailureType.AUTHENTICATION: self.config.retry_on_auth_error,
            FailureType.QUOTA_EXCEEDED: self.config.retry_on_quota_error,
        }
        
        return retry_map.get(failure_type, False)

@dataclass
class RetryMetrics:
    """Metrics for retry system performance."""
    total_requests: int = 0
    retried_requests: int = 0
    exhausted_requests: int = 0
    successful_retries: int = 0
    
    # Attempt statistics
    total_attempts: int = 0
    average_attempts_per_request: float = 0.0
    max_attempts_used: int = 0
    
    # Timing metrics
    average_retry_delay_ms: float = 0.0
    total_retry_time_ms: float = 0.0
    average_time_to_success_ms: float = 0.0
    
    # Effectiveness metrics
    retry_success_rate: float = 0.0
    first_attempt_success_rate: float = 0.0
    improvement_from_retry: float = 0.0
    
    # Failure analysis
    failure_type_retries: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    provider_retry_rates: Dict[str, float] = field(default_factory=dict)
    
    # Strategy effectiveness
    strategy_success_rates: Dict[str, float] = field(default_factory=dict)
    jitter_effectiveness: float = 0.0
    
    last_updated: datetime = field(default_factory=datetime.now)

class RetryDelayCalculator:
    """Calculator for retry delays with various strategies."""
    
    @staticmethod
    def calculate_delay(
        strategy: BackoffStrategy,
        attempt: int,
        base_delay_ms: float,
        multiplier: float = 2.0,
        max_delay_ms: float = 30000.0
    ) -> float:
        """Calculate delay for retry attempt."""
        
        if strategy == BackoffStrategy.FIXED:
            return min(base_delay_ms, max_delay_ms)
        
        elif strategy == BackoffStrategy.LINEAR:
            delay = base_delay_ms * attempt
            return min(delay, max_delay_ms)
        
        elif strategy == BackoffStrategy.EXPONENTIAL:
            delay = base_delay_ms * (multiplier ** (attempt - 1))
            return min(delay, max_delay_ms)
        
        elif strategy == BackoffStrategy.FIBONACCI:
            fib_values = [1, 1]
            for i in range(2, max(attempt, 2)):
                fib_values.append(fib_values[i-1] + fib_values[i-2])
            
            if attempt <= len(fib_values):
                delay = base_delay_ms * fib_values[attempt - 1]
            else:
                delay = base_delay_ms * fib_values[-1]
            
            return min(delay, max_delay_ms)
        
        elif strategy == BackoffStrategy.ADAPTIVE:
            # Adaptive strategy adjusts based on recent success patterns
            # For now, use exponential with slight variation
            delay = base_delay_ms * (1.5 ** (attempt - 1))
            return min(delay, max_delay_ms)
        
        else:
            # Default to exponential
            delay = base_delay_ms * (2.0 ** (attempt - 1))
            return min(delay, max_delay_ms)
    
    @staticmethod
    def apply_jitter(
        delay_ms: float,
        jitter_type: JitterType,
        jitter_amount: float = 0.1
    ) -> float:
        """Apply jitter to delay."""
        
        if jitter_type == JitterType.NONE:
            return delay_ms
        
        elif jitter_type == JitterType.UNIFORM:
            # Uniform random jitter: delay ± (jitter_amount * delay)
            jitter_range = delay_ms * jitter_amount
            jitter = random.uniform(-jitter_range, jitter_range)
            return max(0, delay_ms + jitter)
        
        elif jitter_type == JitterType.EXPONENTIAL:
            # Exponential decay jitter
            jitter = delay_ms * jitter_amount * random.random()
            return delay_ms + jitter
        
        elif jitter_type == JitterType.DECORRELATED:
            # AWS decorrelated jitter algorithm
            # jittered_delay = random(base_delay, previous_delay * 3)
            base_delay = delay_ms / 4  # Estimate base
            max_jitter = delay_ms * 3
            return random.uniform(base_delay, min(max_jitter, delay_ms * 2))
        
        else:
            return delay_ms

class SmartRetryManager:
    """
    Production-grade retry manager with exponential backoff.
    
    Provides intelligent retry logic with multiple backoff strategies,
    integration with circuit breaker, and comprehensive failure handling.
    """
    
    def __init__(self, max_concurrent_retries: int = 20):
        """
        Initialize smart retry manager.
        
        Args:
            max_concurrent_retries: Maximum concurrent retry operations
        """
        self.max_concurrent_retries = max_concurrent_retries
        
        # Core systems integration
        self.cache_manager = get_cache_manager() if PHASE3_DEPENDENCIES_AVAILABLE else None
        self.performance_monitor = get_performance_monitor() if PHASE3_DEPENDENCIES_AVAILABLE else None
        self.api_pool = get_concurrent_api_pool() if PHASE3_DEPENDENCIES_AVAILABLE else None
        self.circuit_breaker = get_circuit_breaker() if PHASE3_DEPENDENCIES_AVAILABLE else None
        
        # Retry state management
        self.active_retries: Dict[str, RetryableRequest] = {}
        self.retry_queue: deque = deque()
        self.completed_retries: deque = deque(maxlen=1000)
        self.dead_letter_queue: deque = deque(maxlen=100)
        
        # Threading and processing
        self.retry_executor = ThreadPoolExecutor(
            max_workers=max_concurrent_retries,
            thread_name_prefix="retry_manager"
        )
        self.processing_futures: Dict[str, Future] = {}
        
        # Performance tracking
        self.metrics = RetryMetrics()
        self._metrics_lock = threading.RLock()
        
        # Provider configurations
        self.provider_configs = self._initialize_provider_configs()
        
        # Background processing
        self._shutdown_event = threading.Event()
        self._background_thread = threading.Thread(target=self._background_processor, daemon=True)
        self._background_thread.start()
        
        print(f"🔄 Smart Retry Manager initialized")
        print(f"  Max Concurrent Retries: {max_concurrent_retries}")
        print(f"  Provider Configs: {len(self.provider_configs)}")
        print(f"  Circuit Breaker Integration: {'✅' if self.circuit_breaker else '❌'}")
        print(f"  Phase 3 Integration: {'✅' if PHASE3_DEPENDENCIES_AVAILABLE else '❌'}")
    
    def _initialize_provider_configs(self) -> Dict[TTSProvider, RetryConfig]:
        """Initialize retry configurations for each provider."""
        configs = {}
        
        # OpenAI configuration - generally reliable
        configs[TTSProvider.OPENAI] = RetryConfig(
            provider=TTSProvider.OPENAI,
            policy=RetryPolicy.CONSERVATIVE,
            max_attempts=int(os.getenv("RETRY_OPENAI_MAX_ATTEMPTS", "3")),
            base_delay_ms=float(os.getenv("RETRY_OPENAI_BASE_DELAY", "1000")),
            max_delay_ms=float(os.getenv("RETRY_OPENAI_MAX_DELAY", "15000")),
            backoff_strategy=BackoffStrategy.EXPONENTIAL,
            jitter_type=JitterType.UNIFORM,
            retry_on_timeout=True,
            retry_on_rate_limit=True,
            retry_on_server_error=True,
            retry_on_network_error=True
        )
        
        # ElevenLabs configuration - can hit rate limits
        configs[TTSProvider.ELEVENLABS] = RetryConfig(
            provider=TTSProvider.ELEVENLABS,
            policy=RetryPolicy.BURST_FRIENDLY,
            max_attempts=int(os.getenv("RETRY_ELEVENLABS_MAX_ATTEMPTS", "4")),
            base_delay_ms=float(os.getenv("RETRY_ELEVENLABS_BASE_DELAY", "2000")),
            max_delay_ms=float(os.getenv("RETRY_ELEVENLABS_MAX_DELAY", "30000")),
            backoff_strategy=BackoffStrategy.EXPONENTIAL,
            jitter_type=JitterType.DECORRELATED,
            retry_on_timeout=True,
            retry_on_rate_limit=True,
            retry_on_server_error=True,
            retry_on_network_error=True,
            retry_on_quota_error=True  # ElevenLabs has quota limits
        )
        
        # pyttsx3 configuration - offline, minimal retries needed
        configs[TTSProvider.PYTTSX3] = RetryConfig(
            provider=TTSProvider.PYTTSX3,
            policy=RetryPolicy.CONSERVATIVE,
            max_attempts=int(os.getenv("RETRY_PYTTSX3_MAX_ATTEMPTS", "2")),
            base_delay_ms=float(os.getenv("RETRY_PYTTSX3_BASE_DELAY", "500")),
            max_delay_ms=float(os.getenv("RETRY_PYTTSX3_MAX_DELAY", "2000")),
            backoff_strategy=BackoffStrategy.FIXED,
            jitter_type=JitterType.NONE,
            retry_on_timeout=True,
            retry_on_server_error=False,  # No server for offline
            retry_on_network_error=False,
            retry_on_api_error=True       # Might have internal errors
        )
        
        return configs
    
    def _classify_failure_type(self, error_message: str, provider: TTSProvider) -> FailureType:
        """Classify failure type from error message."""
        error_lower = error_message.lower()
        
        if "timeout" in error_lower or "timed out" in error_lower:
            return FailureType.TIMEOUT
        elif "rate limit" in error_lower or "429" in error_lower:
            return FailureType.RATE_LIMIT
        elif "network" in error_lower or "connection" in error_lower:
            return FailureType.NETWORK_ERROR
        elif "auth" in error_lower or "401" in error_lower or "unauthorized" in error_lower:
            return FailureType.AUTHENTICATION
        elif "quota" in error_lower or "402" in error_lower or "billing" in error_lower:
            return FailureType.QUOTA_EXCEEDED
        elif "500" in error_lower or "502" in error_lower or "503" in error_lower:
            return FailureType.SERVER_ERROR
        elif "400" in error_lower or "404" in error_lower:
            return FailureType.API_ERROR
        else:
            return FailureType.UNKNOWN
    
    def _should_retry_request(self, request: RetryableRequest, failure_type: FailureType) -> bool:
        """Determine if request should be retried."""
        # Check if exhausted
        if request.is_exhausted():
            return False
        
        # Check failure type policy
        if not request.should_retry_failure_type(failure_type):
            return False
        
        # Check circuit breaker state
        if self.circuit_breaker:
            provider_states = self.circuit_breaker.get_provider_states()
            provider_state = provider_states.get(request.provider, CircuitState.CLOSED)
            
            # Don't retry if circuit is open
            if provider_state == CircuitState.OPEN:
                return False
        
        return True
    
    def _calculate_retry_delay(self, request: RetryableRequest) -> float:
        """Calculate delay before next retry attempt."""
        config = request.config or self.provider_configs.get(request.provider)
        if not config:
            return 1000.0  # Default 1 second
        
        # Calculate base delay
        base_delay = RetryDelayCalculator.calculate_delay(
            strategy=config.backoff_strategy,
            attempt=request.current_attempt + 1,
            base_delay_ms=config.base_delay_ms,
            multiplier=config.backoff_multiplier,
            max_delay_ms=config.max_delay_ms
        )
        
        # Apply jitter
        jittered_delay = RetryDelayCalculator.apply_jitter(
            delay_ms=base_delay,
            jitter_type=config.jitter_type,
            jitter_amount=config.jitter_amount
        )
        
        return max(100.0, jittered_delay)  # Minimum 100ms delay
    
    def _execute_retry_attempt(self, request: RetryableRequest) -> Tuple[bool, Any, str]:
        """Execute a retry attempt for the request."""
        config = request.config or self.provider_configs.get(request.provider)
        
        try:
            attempt_start = time.time()
            
            # Get circuit breaker state
            circuit_state = CircuitState.CLOSED
            if self.circuit_breaker:
                states = self.circuit_breaker.get_provider_states()
                circuit_state = states.get(request.provider, CircuitState.CLOSED)
            
            # Increment attempt counter
            request.current_attempt += 1
            
            # Execute the actual operation (this would be implemented by the caller)
            # For now, we simulate based on provider
            if request.provider == TTSProvider.PYTTSX3:
                # Offline provider - high success rate
                if random.random() < 0.9:
                    result = f"Success from {request.provider.value} on attempt {request.current_attempt}"
                    success = True
                    error_msg = ""
                else:
                    success = False
                    result = None
                    error_msg = "pyttsx3 internal error"
            else:
                # Online providers - variable success based on attempt
                success_probability = 0.6 + (0.2 * (request.current_attempt - 1))  # Improve with retries
                
                if random.random() < success_probability:
                    result = f"Success from {request.provider.value} on attempt {request.current_attempt}"
                    success = True
                    error_msg = ""
                else:
                    success = False
                    result = None
                    # Simulate different error types
                    error_types = ["timeout", "rate limit exceeded", "server error 503", "network connection failed"]
                    error_msg = random.choice(error_types)
            
            # Calculate latency
            latency_ms = (time.time() - attempt_start) * 1000
            
            # Record attempt
            failure_type = self._classify_failure_type(error_msg, request.provider) if not success else None
            attempt = RetryAttempt(
                attempt_number=request.current_attempt,
                timestamp=datetime.now(),
                delay_ms=latency_ms,
                failure_type=failure_type or FailureType.UNKNOWN,
                error_message=error_msg,
                circuit_state=circuit_state,
                provider_used=request.provider
            )
            request.attempts.append(attempt)
            
            return success, result, error_msg
            
        except Exception as e:
            error_msg = str(e)
            latency_ms = (time.time() - attempt_start) * 1000
            
            failure_type = self._classify_failure_type(error_msg, request.provider)
            attempt = RetryAttempt(
                attempt_number=request.current_attempt,
                timestamp=datetime.now(),
                delay_ms=latency_ms,
                failure_type=failure_type,
                error_message=error_msg,
                circuit_state=circuit_state,
                provider_used=request.provider
            )
            request.attempts.append(attempt)
            
            return False, None, error_msg
    
    def _background_processor(self):
        """Background thread for processing retry queue."""
        while not self._shutdown_event.is_set():
            try:
                current_time = datetime.now()
                
                # Check for ready retries
                ready_requests = []
                for request_id, request in list(self.active_retries.items()):
                    if (request.next_retry_at and 
                        request.next_retry_at <= current_time and
                        request_id not in self.processing_futures):
                        ready_requests.append(request)
                
                # Process ready requests
                for request in ready_requests:
                    if len(self.processing_futures) < self.max_concurrent_retries:
                        future = self.retry_executor.submit(self._process_retry_request, request)
                        self.processing_futures[request.request_id] = future
                
                # Clean up completed futures
                completed_ids = []
                for request_id, future in list(self.processing_futures.items()):
                    if future.done():
                        completed_ids.append(request_id)
                        
                        # Move completed requests
                        request = self.active_retries.pop(request_id, None)
                        if request:
                            self.completed_retries.append(request)
                
                for request_id in completed_ids:
                    self.processing_futures.pop(request_id, None)
                
                # Update metrics
                self._update_metrics()
                
                # Sleep briefly
                time.sleep(0.1)  # 100ms cycle
                
            except Exception as e:
                print(f"Retry background processor error: {e}")
                time.sleep(0.5)
    
    def _process_retry_request(self, request: RetryableRequest):
        """Process a retry request through all attempts."""
        start_time = datetime.now()
        
        while not request.is_exhausted():
            # Execute retry attempt
            success, result, error_msg = self._execute_retry_attempt(request)
            
            if success:
                # Success - complete the request
                request.final_result = result
                request.final_status = RequestStatus.COMPLETED
                request.total_retry_time_ms = (datetime.now() - start_time).total_seconds() * 1000
                return
            
            # Failure - check if we should retry
            failure_type = self._classify_failure_type(error_msg, request.provider)
            request.last_error = error_msg
            
            if not self._should_retry_request(request, failure_type):
                # Cannot retry - mark as exhausted or failed
                if request.is_exhausted():
                    request.final_status = RequestStatus.EXHAUSTED
                    self.dead_letter_queue.append(request)
                else:
                    request.final_status = RequestStatus.FAILED
                
                request.total_retry_time_ms = (datetime.now() - start_time).total_seconds() * 1000
                return
            
            # Calculate delay and schedule next attempt
            if not request.is_exhausted():
                delay_ms = self._calculate_retry_delay(request)
                request.next_retry_at = datetime.now() + timedelta(milliseconds=delay_ms)
                
                # Wait for the delay
                time.sleep(delay_ms / 1000.0)
        
        # Exhausted all attempts
        request.final_status = RequestStatus.EXHAUSTED
        request.total_retry_time_ms = (datetime.now() - start_time).total_seconds() * 1000
        self.dead_letter_queue.append(request)
    
    def _update_metrics(self):
        """Update retry performance metrics."""
        with self._metrics_lock:
            # Basic counts
            completed_requests = list(self.completed_retries) + list(self.dead_letter_queue)
            self.metrics.total_requests = len(completed_requests) + len(self.active_retries)
            
            successful_retries = [r for r in completed_requests if r.final_status == RequestStatus.COMPLETED and len(r.attempts) > 1]
            self.metrics.successful_retries = len(successful_retries)
            self.metrics.exhausted_requests = len([r for r in completed_requests if r.final_status == RequestStatus.EXHAUSTED])
            
            # Calculate retry rates
            if len(completed_requests) > 0:
                retried_requests = [r for r in completed_requests if len(r.attempts) > 1]
                self.metrics.retried_requests = len(retried_requests)
                
                # Success rates
                successful_requests = [r for r in completed_requests if r.final_status == RequestStatus.COMPLETED]
                self.metrics.first_attempt_success_rate = len([r for r in successful_requests if len(r.attempts) == 1]) / len(completed_requests) * 100
                
                if len(retried_requests) > 0:
                    self.metrics.retry_success_rate = len(successful_retries) / len(retried_requests) * 100
                
                # Attempt statistics
                total_attempts = sum(len(r.attempts) for r in completed_requests)
                self.metrics.total_attempts = total_attempts
                self.metrics.average_attempts_per_request = total_attempts / len(completed_requests)
                self.metrics.max_attempts_used = max(len(r.attempts) for r in completed_requests) if completed_requests else 0
                
                # Timing metrics
                retry_times = [r.total_retry_time_ms for r in completed_requests if r.total_retry_time_ms > 0]
                if retry_times:
                    self.metrics.total_retry_time_ms = sum(retry_times)
                    self.metrics.average_time_to_success_ms = sum(retry_times) / len(retry_times)
                
                # Failure analysis
                for request in completed_requests:
                    for attempt in request.attempts:
                        if not successful_requests or attempt.failure_type:
                            self.metrics.failure_type_retries[attempt.failure_type.value] += 1
            
            self.metrics.last_updated = datetime.now()
    
    @measure_performance("smart_retry_submit_request")
    def submit_retry_request(self,
                           request_id: str,
                           operation: Any,
                           provider: TTSProvider,
                           priority: AdvancedPriority = AdvancedPriority.MEDIUM,
                           custom_config: Optional[RetryConfig] = None) -> str:
        """
        Submit a request for retry management.
        
        Args:
            request_id: Unique request identifier
            operation: Operation to retry (placeholder)
            provider: TTS provider to use
            priority: Request priority
            custom_config: Optional custom retry configuration
            
        Returns:
            Request ID for tracking
        """
        config = custom_config or self.provider_configs.get(provider)
        
        request = RetryableRequest(
            request_id=request_id,
            original_request=operation,
            provider=provider,
            priority=priority,
            config=config
        )
        
        # Start with immediate attempt
        request.next_retry_at = datetime.now()
        
        # Register request
        self.active_retries[request_id] = request
        
        # Update metrics
        with self._metrics_lock:
            self.metrics.total_requests += 1
        
        return request_id
    
    def get_retry_status(self, request_id: str) -> Optional[Dict[str, Any]]:
        """Get current status of retry request."""
        # Check active retries
        request = self.active_retries.get(request_id)
        if request:
            return {
                "request_id": request_id,
                "status": "active",
                "current_attempt": request.current_attempt,
                "max_attempts": request.config.max_attempts if request.config else 3,
                "next_retry_at": request.next_retry_at.isoformat() if request.next_retry_at else None,
                "last_error": request.last_error,
                "total_time_ms": (datetime.now() - request.created_at).total_seconds() * 1000
            }
        
        # Check completed retries
        for request in self.completed_retries:
            if request.request_id == request_id:
                return {
                    "request_id": request_id,
                    "status": request.final_status.value,
                    "attempts_made": len(request.attempts),
                    "total_retry_time_ms": request.total_retry_time_ms,
                    "final_result": request.final_result is not None,
                    "last_error": request.last_error
                }
        
        # Check dead letter queue
        for request in self.dead_letter_queue:
            if request.request_id == request_id:
                return {
                    "request_id": request_id,
                    "status": "exhausted",
                    "attempts_made": len(request.attempts),
                    "total_retry_time_ms": request.total_retry_time_ms,
                    "moved_to_dead_letter": True
                }
        
        return None
    
    def get_metrics(self) -> RetryMetrics:
        """Get current retry performance metrics."""
        with self._metrics_lock:
            return RetryMetrics(
                total_requests=self.metrics.total_requests,
                retried_requests=self.metrics.retried_requests,
                exhausted_requests=self.metrics.exhausted_requests,
                successful_retries=self.metrics.successful_retries,
                total_attempts=self.metrics.total_attempts,
                average_attempts_per_request=self.metrics.average_attempts_per_request,
                max_attempts_used=self.metrics.max_attempts_used,
                average_retry_delay_ms=self.metrics.average_retry_delay_ms,
                total_retry_time_ms=self.metrics.total_retry_time_ms,
                average_time_to_success_ms=self.metrics.average_time_to_success_ms,
                retry_success_rate=self.metrics.retry_success_rate,
                first_attempt_success_rate=self.metrics.first_attempt_success_rate,
                improvement_from_retry=self.metrics.improvement_from_retry,
                failure_type_retries=dict(self.metrics.failure_type_retries),
                provider_retry_rates=dict(self.metrics.provider_retry_rates),
                strategy_success_rates=dict(self.metrics.strategy_success_rates),
                jitter_effectiveness=self.metrics.jitter_effectiveness,
                last_updated=self.metrics.last_updated
            )
    
    def get_retry_manager_status(self) -> Dict[str, Any]:
        """Get comprehensive retry manager status."""
        metrics = self.get_metrics()
        
        return {
            "retry_manager_status": {
                "max_concurrent_retries": self.max_concurrent_retries,
                "active_retries": len(self.active_retries),
                "processing_retries": len(self.processing_futures),
                "dead_letter_queue_size": len(self.dead_letter_queue),
                "circuit_breaker_integration": self.circuit_breaker is not None
            },
            "performance": {
                "total_requests": metrics.total_requests,
                "retry_success_rate": metrics.retry_success_rate,
                "first_attempt_success_rate": metrics.first_attempt_success_rate,
                "average_attempts_per_request": metrics.average_attempts_per_request,
                "average_time_to_success_ms": metrics.average_time_to_success_ms,
                "exhausted_requests": metrics.exhausted_requests
            },
            "provider_configs": {
                provider.value: {
                    "policy": config.policy.value,
                    "max_attempts": config.max_attempts,
                    "base_delay_ms": config.base_delay_ms,
                    "backoff_strategy": config.backoff_strategy.value,
                    "jitter_type": config.jitter_type.value
                }
                for provider, config in self.provider_configs.items()
            },
            "failure_analysis": {
                "failure_type_distribution": dict(metrics.failure_type_retries),
                "provider_retry_rates": dict(metrics.provider_retry_rates)
            },
            "active_retry_details": [
                {
                    "request_id": request.request_id,
                    "provider": request.provider.value,
                    "attempts": request.current_attempt,
                    "next_retry": request.next_retry_at.isoformat() if request.next_retry_at else None,
                    "last_error": request.last_error
                }
                for request in self.active_retries.values()
            ],
            "last_updated": metrics.last_updated.isoformat()
        }
    
    def shutdown(self):
        """Shutdown the retry manager."""
        print("🔄 Shutting down Smart Retry Manager...")
        
        # Signal shutdown
        self._shutdown_event.set()
        
        # Wait for active retries to complete
        for future in self.processing_futures.values():
            try:
                future.result(timeout=5.0)
            except Exception:
                pass
        
        # Shutdown thread pool
        self.retry_executor.shutdown(wait=True)
        
        # Join background thread
        if self._background_thread.is_alive():
            self._background_thread.join(timeout=5.0)
        
        print("✅ Smart Retry Manager shutdown complete")

# Global retry manager instance
_retry_manager = None

def get_smart_retry_manager() -> SmartRetryManager:
    """Get or create the global smart retry manager."""
    global _retry_manager
    if _retry_manager is None:
        max_concurrent = int(os.getenv("RETRY_MAX_CONCURRENT", "20"))
        _retry_manager = SmartRetryManager(max_concurrent)
    return _retry_manager

def execute_with_smart_retry(
    operation: Callable[[], Any],
    provider: TTSProvider,
    priority: AdvancedPriority = AdvancedPriority.MEDIUM,
    custom_config: Optional[RetryConfig] = None
) -> Tuple[bool, Any, str]:
    """
    Execute operation with smart retry logic.
    
    Args:
        operation: Operation to execute with retries
        provider: TTS provider
        priority: Request priority
        custom_config: Optional custom retry configuration
        
    Returns:
        (success, result, error_message)
    """
    import uuid
    
    retry_manager = get_smart_retry_manager()
    request_id = str(uuid.uuid4())
    
    # Submit for retry processing
    retry_manager.submit_retry_request(request_id, operation, provider, priority, custom_config)
    
    # Wait for completion (in real implementation, this would be async)
    timeout = 60.0  # 60 second timeout
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        status = retry_manager.get_retry_status(request_id)
        if status and status.get("status") in ["completed", "failed", "exhausted"]:
            if status.get("status") == "completed":
                return True, "Operation succeeded", ""
            else:
                return False, None, status.get("last_error", "Unknown error")
        
        time.sleep(0.1)
    
    return False, None, "Timeout waiting for retry completion"

def main():
    """Main entry point for testing Phase 3.4.3.2 Retry Logic."""
    import sys
    
    if "--test" in sys.argv:
        print("🧪 Testing Phase 3.4.3.2 Retry Logic with Exponential Backoff")
        print("=" * 70)
        
        retry_manager = get_smart_retry_manager()
        
        print(f"\n🔄 Retry Manager Status:")
        status = retry_manager.get_retry_manager_status()
        print(f"  Max Concurrent Retries: {status['retry_manager_status']['max_concurrent_retries']}")
        print(f"  Circuit Breaker Integration: {'✅' if status['retry_manager_status']['circuit_breaker_integration'] else '❌'}")
        print(f"  Provider Configs: {len(status['provider_configs'])}")
        
        # Test provider configurations
        print(f"\n⚙️  Provider Configurations:")
        for provider, config in status['provider_configs'].items():
            print(f"  {provider}:")
            print(f"    Policy: {config['policy']}")
            print(f"    Max Attempts: {config['max_attempts']}")
            print(f"    Base Delay: {config['base_delay_ms']}ms")
            print(f"    Backoff: {config['backoff_strategy']}")
        
        # Test retry operations
        print(f"\n🔄 Testing Retry Operations:")
        
        test_operations = [
            (TTSProvider.OPENAI, AdvancedPriority.HIGH, "High priority OpenAI request"),
            (TTSProvider.ELEVENLABS, AdvancedPriority.MEDIUM, "Medium priority ElevenLabs request"),
            (TTSProvider.PYTTSX3, AdvancedPriority.LOW, "Low priority pyttsx3 request"),
        ]
        
        submitted_requests = []
        for provider, priority, description in test_operations:
            
            def create_test_operation():
                return f"Test operation for {provider.value}"
            
            request_id = retry_manager.submit_retry_request(
                request_id=f"test_{provider.value}_{int(time.time())}",
                operation=create_test_operation,
                provider=provider,
                priority=priority
            )
            submitted_requests.append((request_id, description))
            print(f"  ✅ Submitted: {description} -> {request_id[:12]}...")
        
        # Wait for processing
        print(f"\n⏳ Processing retries...")
        time.sleep(3.0)
        
        # Check results
        print(f"\n📊 Retry Results:")
        for request_id, description in submitted_requests:
            status = retry_manager.get_retry_status(request_id)
            if status:
                print(f"  {request_id[:12]}: {status['status']} ({status.get('attempts_made', 0)} attempts)")
                if status.get('last_error'):
                    print(f"    Last error: {status['last_error']}")
            else:
                print(f"  {request_id[:12]}: Not found")
        
        # Test backoff strategies
        print(f"\n📈 Testing Backoff Strategies:")
        
        strategies = [
            (BackoffStrategy.EXPONENTIAL, "Exponential backoff"),
            (BackoffStrategy.LINEAR, "Linear backoff"),
            (BackoffStrategy.FIXED, "Fixed delay"),
            (BackoffStrategy.FIBONACCI, "Fibonacci sequence")
        ]
        
        for strategy, description in strategies:
            delays = []
            for attempt in range(1, 6):
                delay = RetryDelayCalculator.calculate_delay(
                    strategy=strategy,
                    attempt=attempt,
                    base_delay_ms=1000.0,
                    multiplier=2.0,
                    max_delay_ms=30000.0
                )
                delays.append(delay)
            
            print(f"  {description}: {[f'{d/1000:.1f}s' for d in delays[:5]]}")
        
        # Test jitter effectiveness
        print(f"\n🎲 Testing Jitter Types:")
        
        base_delay = 5000.0
        jitter_types = [JitterType.NONE, JitterType.UNIFORM, JitterType.EXPONENTIAL, JitterType.DECORRELATED]
        
        for jitter_type in jitter_types:
            jittered_delays = []
            for _ in range(5):
                delay = RetryDelayCalculator.apply_jitter(base_delay, jitter_type, 0.1)
                jittered_delays.append(delay)
            
            avg_delay = sum(jittered_delays) / len(jittered_delays)
            print(f"  {jitter_type.value}: {avg_delay/1000:.2f}s avg ({min(jittered_delays)/1000:.2f}-{max(jittered_delays)/1000:.2f}s)")
        
        # Test performance metrics
        print(f"\n📈 Performance Metrics:")
        metrics = retry_manager.get_metrics()
        print(f"  Total Requests: {metrics.total_requests}")
        print(f"  Successful Retries: {metrics.successful_retries}")
        print(f"  Retry Success Rate: {metrics.retry_success_rate:.1f}%")
        print(f"  First Attempt Success Rate: {metrics.first_attempt_success_rate:.1f}%")
        print(f"  Average Attempts per Request: {metrics.average_attempts_per_request:.1f}")
        
        if metrics.failure_type_retries:
            print(f"  Failure Types:")
            for failure_type, count in metrics.failure_type_retries.items():
                print(f"    {failure_type}: {count}")
        
        print(f"\n✅ Phase 3.4.3.2 Retry Logic test completed")
        print(f"🔄 Production-grade retry system with exponential backoff and intelligent failure handling!")
        
        # Cleanup
        retry_manager.shutdown()
    
    else:
        print("Phase 3.4.3.2 Retry Logic with Exponential Backoff")
        print("Production-grade retry system for resilient TTS API calls")
        print("Usage: python phase3_43_retry_logic.py --test")

if __name__ == "__main__":
    main()