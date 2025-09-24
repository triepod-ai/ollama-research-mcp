#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "python-dotenv>=1.0.0",
# ]
# ///

"""
Phase 3.4.3.2 Circuit Breaker Pattern
Production-grade circuit breaker for TTS provider failure protection.

Features:
- Multi-state circuit breaker with Open/Closed/Half-Open states
- Provider-specific failure thresholds and recovery detection
- Integration with concurrent API pool and request batcher
- Real-time health monitoring and automatic state transitions
- Fast-fail protection to prevent cascading failures
- Comprehensive metrics and alerting for circuit state changes
- Adaptive threshold adjustment based on provider patterns
- Graceful degradation with fallback provider chains
"""

import threading
import time
from collections import deque, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Callable, Any, Tuple, Union, Set
from concurrent.futures import ThreadPoolExecutor, Future
import os
from dotenv import load_dotenv

# Import Phase 3 components
try:
    try:
        from .phase3_cache_manager import get_cache_manager
        from .phase3_performance_metrics import get_performance_monitor, measure_performance
        from .phase3_43_concurrent_api_pool import get_concurrent_api_pool, APIRequestResult, RequestStatus, TTSProvider
        from .advanced_priority_queue import AdvancedPriority, MessageType
    except ImportError:
        from phase3_cache_manager import get_cache_manager
        from phase3_performance_metrics import get_performance_monitor, measure_performance
        from phase3_43_concurrent_api_pool import get_concurrent_api_pool, APIRequestResult, RequestStatus, TTSProvider
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
        CIRCUIT_OPEN = "circuit_open"

# Load environment variables
env_path = Path.home() / "brainpods" / ".env"
if env_path.exists():
    load_dotenv(env_path)

class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"        # Normal operation - requests pass through
    OPEN = "open"            # Failure state - requests fail fast
    HALF_OPEN = "half_open"  # Recovery testing - limited requests allowed

class FailureType(Enum):
    """Types of failures tracked by circuit breaker."""
    TIMEOUT = "timeout"
    API_ERROR = "api_error"
    RATE_LIMIT = "rate_limit"
    NETWORK_ERROR = "network_error"
    AUTHENTICATION = "authentication"
    QUOTA_EXCEEDED = "quota_exceeded"
    SERVER_ERROR = "server_error"
    UNKNOWN = "unknown"

@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker."""
    provider: TTSProvider
    
    # Failure thresholds
    failure_threshold: int = 5              # Number of failures to trigger open
    recovery_threshold: int = 3             # Number of successes to recover
    timeout_threshold_ms: float = 30000.0   # Request timeout threshold
    
    # Time windows
    failure_window_ms: float = 60000.0      # Time window for failure counting
    recovery_timeout_ms: float = 30000.0    # Time before attempting recovery
    half_open_timeout_ms: float = 10000.0   # Max time in half-open state
    
    # Adaptive settings
    adaptive_thresholds: bool = True        # Enable adaptive threshold adjustment
    min_calls_for_adaptation: int = 50      # Minimum calls before adaptation
    success_rate_threshold: float = 0.85    # Success rate to maintain closed state
    
    # Provider-specific settings
    provider_specific_timeouts: Dict[str, float] = field(default_factory=dict)
    provider_priority: int = 1              # Provider priority (lower = higher priority)

@dataclass
class CallResult:
    """Result of a call through circuit breaker."""
    timestamp: datetime
    success: bool
    latency_ms: float
    failure_type: Optional[FailureType] = None
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class CircuitBreakerMetrics:
    """Metrics for circuit breaker monitoring."""
    provider: TTSProvider
    state: CircuitState
    
    # Call statistics
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    blocked_calls: int = 0
    
    # State transitions
    state_changes: int = 0
    time_in_open: float = 0.0
    time_in_half_open: float = 0.0
    last_state_change: Optional[datetime] = None
    
    # Failure analysis
    failure_types: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    average_failure_rate: float = 0.0
    current_success_rate: float = 1.0
    
    # Performance metrics
    average_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    recovery_time_ms: float = 0.0
    
    # Health indicators
    health_score: float = 1.0               # 0.0 to 1.0 health score
    reliability_score: float = 1.0          # Long-term reliability
    
    last_updated: datetime = field(default_factory=datetime.now)

class ProviderCircuitBreaker:
    """
    Circuit breaker for individual TTS provider.
    
    Implements the circuit breaker pattern with Open/Closed/Half-Open states
    to protect against provider failures and enable fast recovery.
    """
    
    def __init__(self, config: CircuitBreakerConfig):
        """
        Initialize provider circuit breaker.
        
        Args:
            config: Circuit breaker configuration
        """
        self.config = config
        self.provider = config.provider
        
        # State management
        self.state = CircuitState.CLOSED
        self.state_changed_at = datetime.now()
        self.failure_count = 0
        self.success_count = 0
        
        # Call history
        self.call_history: deque = deque(maxlen=1000)
        self.recent_failures: deque = deque(maxlen=100)
        
        # Metrics
        self.metrics = CircuitBreakerMetrics(provider=self.provider, state=self.state)
        self._metrics_lock = threading.RLock()
        
        # Recovery testing
        self.recovery_start_time: Optional[datetime] = None
        self.half_open_calls = 0
        
        # Adaptive thresholds
        self.adapted_failure_threshold = config.failure_threshold
        self.adapted_success_rate = config.success_rate_threshold
        
        print(f"🔌 Circuit breaker initialized for {self.provider.value}")
        print(f"  Failure threshold: {config.failure_threshold}")
        print(f"  Recovery threshold: {config.recovery_threshold}")
        print(f"  Adaptive thresholds: {'✅' if config.adaptive_thresholds else '❌'}")
    
    def _update_adaptive_thresholds(self):
        """Update thresholds based on historical performance."""
        if not self.config.adaptive_thresholds or len(self.call_history) < self.config.min_calls_for_adaptation:
            return
        
        # Calculate recent success rate
        recent_calls = list(self.call_history)[-50:]  # Last 50 calls
        if len(recent_calls) >= 20:
            success_rate = sum(1 for call in recent_calls if call.success) / len(recent_calls)
            
            # Adjust failure threshold based on provider reliability
            if success_rate > 0.95:
                # Very reliable provider - can tolerate more failures
                self.adapted_failure_threshold = min(
                    self.config.failure_threshold * 1.5,
                    self.config.failure_threshold + 3
                )
            elif success_rate < 0.80:
                # Unreliable provider - be more sensitive
                self.adapted_failure_threshold = max(
                    self.config.failure_threshold * 0.7,
                    self.config.failure_threshold - 2
                )
            else:
                # Normal provider - use default
                self.adapted_failure_threshold = self.config.failure_threshold
    
    def _should_trigger_open(self) -> bool:
        """Check if circuit should open based on failure patterns."""
        current_time = datetime.now()
        window_start = current_time - timedelta(milliseconds=self.config.failure_window_ms)
        
        # Count recent failures
        recent_failures = [
            call for call in self.call_history
            if call.timestamp >= window_start and not call.success
        ]
        
        # Check failure count threshold
        if len(recent_failures) >= self.adapted_failure_threshold:
            return True
        
        # Check success rate threshold
        recent_calls = [
            call for call in self.call_history
            if call.timestamp >= window_start
        ]
        
        if len(recent_calls) >= 10:  # Minimum calls for rate calculation
            success_rate = sum(1 for call in recent_calls if call.success) / len(recent_calls)
            if success_rate < self.config.success_rate_threshold:
                return True
        
        return False
    
    def _should_attempt_recovery(self) -> bool:
        """Check if circuit should attempt recovery."""
        if self.state != CircuitState.OPEN:
            return False
        
        # Check if enough time has passed since opening
        time_since_open = datetime.now() - self.state_changed_at
        return time_since_open.total_seconds() * 1000 >= self.config.recovery_timeout_ms
    
    def _should_close_from_half_open(self) -> bool:
        """Check if circuit should close from half-open state."""
        return self.success_count >= self.config.recovery_threshold
    
    def _should_open_from_half_open(self) -> bool:
        """Check if circuit should open from half-open state."""
        # Open if any failure in half-open state
        return self.failure_count > 0
    
    def _transition_to_open(self):
        """Transition circuit to open state."""
        self.state = CircuitState.OPEN
        self.state_changed_at = datetime.now()
        self.failure_count = 0
        self.success_count = 0
        
        with self._metrics_lock:
            self.metrics.state = self.state
            self.metrics.state_changes += 1
            self.metrics.last_state_change = self.state_changed_at
        
        print(f"🔴 Circuit breaker OPENED for {self.provider.value} due to failures")
    
    def _transition_to_half_open(self):
        """Transition circuit to half-open state."""
        self.state = CircuitState.HALF_OPEN
        self.state_changed_at = datetime.now()
        self.recovery_start_time = datetime.now()
        self.failure_count = 0
        self.success_count = 0
        self.half_open_calls = 0
        
        with self._metrics_lock:
            self.metrics.state = self.state
            self.metrics.state_changes += 1
            self.metrics.last_state_change = self.state_changed_at
        
        print(f"🟡 Circuit breaker HALF-OPEN for {self.provider.value} - testing recovery")
    
    def _transition_to_closed(self):
        """Transition circuit to closed state."""
        self.state = CircuitState.CLOSED
        self.state_changed_at = datetime.now()
        self.failure_count = 0
        self.success_count = 0
        
        # Calculate recovery time
        if self.recovery_start_time:
            recovery_time = (datetime.now() - self.recovery_start_time).total_seconds() * 1000
            with self._metrics_lock:
                self.metrics.recovery_time_ms = recovery_time
        
        with self._metrics_lock:
            self.metrics.state = self.state
            self.metrics.state_changes += 1
            self.metrics.last_state_change = self.state_changed_at
        
        print(f"🟢 Circuit breaker CLOSED for {self.provider.value} - service recovered")
    
    def _classify_failure(self, error_message: str, latency_ms: float) -> FailureType:
        """Classify the type of failure."""
        error_lower = error_message.lower()
        
        if latency_ms > self.config.timeout_threshold_ms:
            return FailureType.TIMEOUT
        elif "rate limit" in error_lower or "429" in error_lower:
            return FailureType.RATE_LIMIT
        elif "timeout" in error_lower:
            return FailureType.TIMEOUT
        elif "network" in error_lower or "connection" in error_lower:
            return FailureType.NETWORK_ERROR
        elif "auth" in error_lower or "401" in error_lower:
            return FailureType.AUTHENTICATION
        elif "quota" in error_lower or "402" in error_lower:
            return FailureType.QUOTA_EXCEEDED
        elif "500" in error_lower or "502" in error_lower or "503" in error_lower:
            return FailureType.SERVER_ERROR
        else:
            return FailureType.UNKNOWN
    
    def _record_call_result(self, result: CallResult):
        """Record the result of a call."""
        self.call_history.append(result)
        
        with self._metrics_lock:
            self.metrics.total_calls += 1
            
            if result.success:
                self.metrics.successful_calls += 1
                self.success_count += 1
            else:
                self.metrics.failed_calls += 1
                self.failure_count += 1
                self.recent_failures.append(result)
                if result.failure_type:
                    self.metrics.failure_types[result.failure_type.value] += 1
            
            # Update performance metrics
            if len(self.call_history) > 0:
                latencies = [call.latency_ms for call in self.call_history if call.latency_ms > 0]
                if latencies:
                    self.metrics.average_latency_ms = sum(latencies) / len(latencies)
                    self.metrics.p95_latency_ms = sorted(latencies)[int(len(latencies) * 0.95)]
            
            # Update success rate
            if self.metrics.total_calls > 0:
                self.metrics.current_success_rate = self.metrics.successful_calls / self.metrics.total_calls
            
            # Update health score
            self._calculate_health_score()
            
            self.metrics.last_updated = datetime.now()
    
    def _calculate_health_score(self):
        """Calculate provider health score based on multiple factors."""
        if len(self.call_history) < 5:
            self.metrics.health_score = 1.0
            return
        
        recent_calls = list(self.call_history)[-20:]  # Last 20 calls
        
        # Success rate component (60% weight)
        success_rate = sum(1 for call in recent_calls if call.success) / len(recent_calls)
        success_component = success_rate * 0.6
        
        # Latency component (25% weight)
        latencies = [call.latency_ms for call in recent_calls if call.success and call.latency_ms > 0]
        if latencies:
            avg_latency = sum(latencies) / len(latencies)
            # Normalize latency (good if under 2 seconds, poor if over 10 seconds)
            latency_score = max(0, min(1, (10000 - avg_latency) / 8000))
        else:
            latency_score = 0.5
        latency_component = latency_score * 0.25
        
        # State stability component (15% weight)
        if self.state == CircuitState.CLOSED:
            stability_score = 1.0
        elif self.state == CircuitState.HALF_OPEN:
            stability_score = 0.5
        else:  # OPEN
            stability_score = 0.0
        stability_component = stability_score * 0.15
        
        self.metrics.health_score = success_component + latency_component + stability_component
    
    def can_execute(self) -> bool:
        """Check if request can be executed through this circuit."""
        # Update adaptive thresholds
        self._update_adaptive_thresholds()
        
        # Handle state transitions
        if self.state == CircuitState.CLOSED:
            if self._should_trigger_open():
                self._transition_to_open()
                return False
            return True
        
        elif self.state == CircuitState.OPEN:
            if self._should_attempt_recovery():
                self._transition_to_half_open()
                return True
            return False
        
        elif self.state == CircuitState.HALF_OPEN:
            # Check timeout
            time_in_half_open = (datetime.now() - self.state_changed_at).total_seconds() * 1000
            if time_in_half_open > self.config.half_open_timeout_ms:
                self._transition_to_open()
                return False
            
            # Allow limited calls for testing
            if self.half_open_calls < 3:  # Allow up to 3 test calls
                self.half_open_calls += 1
                return True
            return False
        
        return False
    
    def record_success(self, latency_ms: float):
        """Record successful call."""
        result = CallResult(
            timestamp=datetime.now(),
            success=True,
            latency_ms=latency_ms
        )
        
        self._record_call_result(result)
        
        # Handle state transitions based on success
        if self.state == CircuitState.HALF_OPEN:
            if self._should_close_from_half_open():
                self._transition_to_closed()
    
    def record_failure(self, latency_ms: float, error_message: str = ""):
        """Record failed call."""
        failure_type = self._classify_failure(error_message, latency_ms)
        
        result = CallResult(
            timestamp=datetime.now(),
            success=False,
            latency_ms=latency_ms,
            failure_type=failure_type,
            error_message=error_message
        )
        
        self._record_call_result(result)
        
        # Handle state transitions based on failure
        if self.state == CircuitState.HALF_OPEN and self._should_open_from_half_open():
            self._transition_to_open()
    
    def record_blocked_call(self):
        """Record a call that was blocked by the circuit breaker."""
        with self._metrics_lock:
            self.metrics.blocked_calls += 1
    
    def get_metrics(self) -> CircuitBreakerMetrics:
        """Get current circuit breaker metrics."""
        with self._metrics_lock:
            return CircuitBreakerMetrics(
                provider=self.metrics.provider,
                state=self.metrics.state,
                total_calls=self.metrics.total_calls,
                successful_calls=self.metrics.successful_calls,
                failed_calls=self.metrics.failed_calls,
                blocked_calls=self.metrics.blocked_calls,
                state_changes=self.metrics.state_changes,
                time_in_open=self.metrics.time_in_open,
                time_in_half_open=self.metrics.time_in_half_open,
                last_state_change=self.metrics.last_state_change,
                failure_types=dict(self.metrics.failure_types),
                average_failure_rate=self.metrics.average_failure_rate,
                current_success_rate=self.metrics.current_success_rate,
                average_latency_ms=self.metrics.average_latency_ms,
                p95_latency_ms=self.metrics.p95_latency_ms,
                recovery_time_ms=self.metrics.recovery_time_ms,
                health_score=self.metrics.health_score,
                reliability_score=self.metrics.reliability_score,
                last_updated=self.metrics.last_updated
            )

class MultiProviderCircuitBreaker:
    """
    Multi-provider circuit breaker system for TTS resilience.
    
    Manages circuit breakers for all TTS providers with fallback chains
    and comprehensive failure protection.
    """
    
    def __init__(self):
        """Initialize multi-provider circuit breaker system."""
        # Core systems integration
        self.cache_manager = get_cache_manager() if PHASE3_DEPENDENCIES_AVAILABLE else None
        self.performance_monitor = get_performance_monitor() if PHASE3_DEPENDENCIES_AVAILABLE else None
        self.api_pool = get_concurrent_api_pool() if PHASE3_DEPENDENCIES_AVAILABLE else None
        
        # Circuit breakers for each provider
        self.circuit_breakers: Dict[TTSProvider, ProviderCircuitBreaker] = {}
        
        # Initialize provider configurations
        self._initialize_provider_configs()
        
        # Fallback chains
        self.fallback_chains = {
            TTSProvider.OPENAI: [TTSProvider.ELEVENLABS, TTSProvider.PYTTSX3],
            TTSProvider.ELEVENLABS: [TTSProvider.OPENAI, TTSProvider.PYTTSX3],
            TTSProvider.PYTTSX3: []  # No fallback for offline provider
        }
        
        # Global metrics
        self._global_metrics_lock = threading.RLock()
        
        print(f"🔌 Multi-Provider Circuit Breaker initialized")
        print(f"  Providers: {len(self.circuit_breakers)}")
        print(f"  Fallback chains configured: ✅")
        print(f"  Phase 3 integration: {'✅' if PHASE3_DEPENDENCIES_AVAILABLE else '❌'}")
    
    def _initialize_provider_configs(self):
        """Initialize circuit breaker configurations for each provider."""
        # OpenAI configuration - typically reliable
        openai_config = CircuitBreakerConfig(
            provider=TTSProvider.OPENAI,
            failure_threshold=int(os.getenv("CB_OPENAI_FAILURE_THRESHOLD", "5")),
            recovery_threshold=int(os.getenv("CB_OPENAI_RECOVERY_THRESHOLD", "3")),
            timeout_threshold_ms=float(os.getenv("CB_OPENAI_TIMEOUT_MS", "10000")),
            failure_window_ms=float(os.getenv("CB_OPENAI_WINDOW_MS", "60000")),
            recovery_timeout_ms=float(os.getenv("CB_OPENAI_RECOVERY_MS", "30000")),
            provider_priority=1
        )
        self.circuit_breakers[TTSProvider.OPENAI] = ProviderCircuitBreaker(openai_config)
        
        # ElevenLabs configuration - can be rate-limited
        elevenlabs_config = CircuitBreakerConfig(
            provider=TTSProvider.ELEVENLABS,
            failure_threshold=int(os.getenv("CB_ELEVENLABS_FAILURE_THRESHOLD", "3")),
            recovery_threshold=int(os.getenv("CB_ELEVENLABS_RECOVERY_THRESHOLD", "2")),
            timeout_threshold_ms=float(os.getenv("CB_ELEVENLABS_TIMEOUT_MS", "15000")),
            failure_window_ms=float(os.getenv("CB_ELEVENLABS_WINDOW_MS", "120000")),
            recovery_timeout_ms=float(os.getenv("CB_ELEVENLABS_RECOVERY_MS", "60000")),
            provider_priority=2
        )
        self.circuit_breakers[TTSProvider.ELEVENLABS] = ProviderCircuitBreaker(elevenlabs_config)
        
        # pyttsx3 configuration - offline, should rarely fail
        pyttsx3_config = CircuitBreakerConfig(
            provider=TTSProvider.PYTTSX3,
            failure_threshold=int(os.getenv("CB_PYTTSX3_FAILURE_THRESHOLD", "10")),
            recovery_threshold=int(os.getenv("CB_PYTTSX3_RECOVERY_THRESHOLD", "1")),
            timeout_threshold_ms=float(os.getenv("CB_PYTTSX3_TIMEOUT_MS", "5000")),
            failure_window_ms=float(os.getenv("CB_PYTTSX3_WINDOW_MS", "30000")),
            recovery_timeout_ms=float(os.getenv("CB_PYTTSX3_RECOVERY_MS", "10000")),
            provider_priority=3
        )
        self.circuit_breakers[TTSProvider.PYTTSX3] = ProviderCircuitBreaker(pyttsx3_config)
    
    def get_available_provider(self, preferred_provider: TTSProvider) -> Optional[TTSProvider]:
        """Get available provider, using fallback chain if preferred is unavailable."""
        # Check preferred provider first
        circuit = self.circuit_breakers.get(preferred_provider)
        if circuit and circuit.can_execute():
            return preferred_provider
        
        # Try fallback chain
        for fallback_provider in self.fallback_chains.get(preferred_provider, []):
            fallback_circuit = self.circuit_breakers.get(fallback_provider)
            if fallback_circuit and fallback_circuit.can_execute():
                print(f"🔄 Falling back from {preferred_provider.value} to {fallback_provider.value}")
                return fallback_provider
        
        # No available providers
        return None
    
    def execute_with_circuit_breaker(self, 
                                   provider: TTSProvider,
                                   operation: Callable[[], Any]) -> Tuple[bool, Any, Optional[str]]:
        """
        Execute operation with circuit breaker protection.
        
        Args:
            provider: TTS provider to use
            operation: Operation to execute
            
        Returns:
            (success, result, error_message)
        """
        circuit = self.circuit_breakers.get(provider)
        if not circuit:
            return False, None, f"No circuit breaker for provider {provider.value}"
        
        # Check if circuit allows execution
        if not circuit.can_execute():
            circuit.record_blocked_call()
            return False, None, f"Circuit breaker is open for {provider.value}"
        
        # Execute operation with timing
        start_time = time.time()
        try:
            result = operation()
            latency_ms = (time.time() - start_time) * 1000
            
            # Record success
            circuit.record_success(latency_ms)
            
            return True, result, None
            
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            error_message = str(e)
            
            # Record failure
            circuit.record_failure(latency_ms, error_message)
            
            return False, None, error_message
    
    def get_provider_health_scores(self) -> Dict[TTSProvider, float]:
        """Get health scores for all providers."""
        return {
            provider: circuit.metrics.health_score
            for provider, circuit in self.circuit_breakers.items()
        }
    
    def get_provider_states(self) -> Dict[TTSProvider, CircuitState]:
        """Get current states of all circuit breakers."""
        return {
            provider: circuit.state
            for provider, circuit in self.circuit_breakers.items()
        }
    
    def get_global_metrics(self) -> Dict[str, Any]:
        """Get comprehensive circuit breaker metrics."""
        with self._global_metrics_lock:
            provider_metrics = {}
            total_calls = 0
            total_blocked = 0
            total_failures = 0
            
            for provider, circuit in self.circuit_breakers.items():
                metrics = circuit.get_metrics()
                provider_metrics[provider.value] = {
                    "state": metrics.state.value,
                    "health_score": metrics.health_score,
                    "success_rate": metrics.current_success_rate,
                    "total_calls": metrics.total_calls,
                    "blocked_calls": metrics.blocked_calls,
                    "failed_calls": metrics.failed_calls,
                    "state_changes": metrics.state_changes,
                    "average_latency_ms": metrics.average_latency_ms,
                    "failure_types": dict(metrics.failure_types)
                }
                
                total_calls += metrics.total_calls
                total_blocked += metrics.blocked_calls
                total_failures += metrics.failed_calls
            
            # Calculate global health
            health_scores = [circuit.metrics.health_score for circuit in self.circuit_breakers.values()]
            global_health = sum(health_scores) / len(health_scores) if health_scores else 0.0
            
            # Available providers
            available_providers = [
                provider.value for provider, circuit in self.circuit_breakers.items()
                if circuit.state != CircuitState.OPEN
            ]
            
            return {
                "global_health_score": global_health,
                "total_calls": total_calls,
                "total_blocked_calls": total_blocked,
                "total_failed_calls": total_failures,
                "availability_rate": (total_calls - total_blocked) / max(total_calls, 1) * 100,
                "available_providers": available_providers,
                "provider_count": len(self.circuit_breakers),
                "providers": provider_metrics,
                "fallback_chains": {
                    provider.value: [fp.value for fp in fallbacks]
                    for provider, fallbacks in self.fallback_chains.items()
                }
            }
    
    def reset_circuit_breaker(self, provider: TTSProvider):
        """Reset a specific circuit breaker to closed state."""
        circuit = self.circuit_breakers.get(provider)
        if circuit:
            circuit._transition_to_closed()
            print(f"🔄 Reset circuit breaker for {provider.value}")
    
    def reset_all_circuit_breakers(self):
        """Reset all circuit breakers to closed state."""
        for provider in self.circuit_breakers:
            self.reset_circuit_breaker(provider)
        print("🔄 Reset all circuit breakers")

# Global circuit breaker instance
_circuit_breaker = None

def get_circuit_breaker() -> MultiProviderCircuitBreaker:
    """Get or create the global circuit breaker."""
    global _circuit_breaker
    if _circuit_breaker is None:
        _circuit_breaker = MultiProviderCircuitBreaker()
    return _circuit_breaker

def execute_with_fallback(preferred_provider: TTSProvider, 
                         operation_factory: Callable[[TTSProvider], Callable[[], Any]]) -> Tuple[bool, Any, Optional[str], TTSProvider]:
    """
    Execute operation with automatic fallback to available providers.
    
    Args:
        preferred_provider: Preferred TTS provider
        operation_factory: Function that creates operation for given provider
        
    Returns:
        (success, result, error_message, used_provider)
    """
    circuit_breaker = get_circuit_breaker()
    
    # Get available provider (with fallback)
    available_provider = circuit_breaker.get_available_provider(preferred_provider)
    if not available_provider:
        return False, None, "No available providers", preferred_provider
    
    # Create operation for available provider
    operation = operation_factory(available_provider)
    
    # Execute with circuit breaker protection
    success, result, error = circuit_breaker.execute_with_circuit_breaker(available_provider, operation)
    
    return success, result, error, available_provider

def main():
    """Main entry point for testing Phase 3.4.3.2 Circuit Breaker."""
    import random
    import sys
    
    if "--test" in sys.argv:
        print("🧪 Testing Phase 3.4.3.2 Circuit Breaker Pattern")
        print("=" * 60)
        
        circuit_breaker = get_circuit_breaker()
        
        print(f"\n🔌 Circuit Breaker Status:")
        states = circuit_breaker.get_provider_states()
        health_scores = circuit_breaker.get_provider_health_scores()
        
        for provider, state in states.items():
            health = health_scores[provider]
            print(f"  {provider.value}: {state.value} (health: {health:.2f})")
        
        # Test normal operation
        print(f"\n✅ Testing Normal Operation:")
        
        def mock_successful_operation():
            time.sleep(0.1)  # Simulate API call
            return "success"
        
        for provider in [TTSProvider.OPENAI, TTSProvider.ELEVENLABS, TTSProvider.PYTTSX3]:
            success, result, error = circuit_breaker.execute_with_circuit_breaker(
                provider, mock_successful_operation
            )
            print(f"  {provider.value}: {'✅' if success else '❌'} - {result or error}")
        
        # Test failure scenarios
        print(f"\n❌ Testing Failure Scenarios:")
        
        def mock_failing_operation():
            time.sleep(0.05)
            raise Exception("API timeout error")
        
        # Trigger failures for OpenAI
        print(f"  Triggering failures for OpenAI...")
        for i in range(6):  # Exceed failure threshold
            success, result, error = circuit_breaker.execute_with_circuit_breaker(
                TTSProvider.OPENAI, mock_failing_operation
            )
            if i == 0:
                print(f"    Failure {i+1}: {error}")
        
        # Check if circuit opened
        openai_state = circuit_breaker.get_provider_states()[TTSProvider.OPENAI]
        print(f"    OpenAI circuit state: {openai_state.value}")
        
        # Test fallback behavior
        print(f"\n🔄 Testing Fallback Behavior:")
        
        def create_mock_operation(provider):
            def operation():
                if provider == TTSProvider.OPENAI:
                    raise Exception("OpenAI unavailable")
                return f"Success with {provider.value}"
            return operation
        
        success, result, error, used_provider = execute_with_fallback(
            TTSProvider.OPENAI, create_mock_operation
        )
        print(f"  Preferred: OpenAI, Used: {used_provider.value}, Result: {result or error}")
        
        # Test recovery behavior
        print(f"\n🔄 Testing Recovery Behavior:")
        
        # Wait for potential recovery attempt
        time.sleep(1.0)
        
        # Try OpenAI again
        success, result, error = circuit_breaker.execute_with_circuit_breaker(
            TTSProvider.OPENAI, mock_successful_operation
        )
        print(f"  OpenAI recovery attempt: {'✅' if success else '❌'}")
        
        # Test comprehensive metrics
        print(f"\n📈 Performance Metrics:")
        metrics = circuit_breaker.get_global_metrics()
        print(f"  Global Health Score: {metrics['global_health_score']:.2f}")
        print(f"  Total Calls: {metrics['total_calls']}")
        print(f"  Blocked Calls: {metrics['total_blocked_calls']}")
        print(f"  Availability Rate: {metrics['availability_rate']:.1f}%")
        print(f"  Available Providers: {', '.join(metrics['available_providers'])}")
        
        # Provider-specific metrics
        for provider, provider_metrics in metrics['providers'].items():
            print(f"  {provider}:")
            print(f"    State: {provider_metrics['state']}")
            print(f"    Health: {provider_metrics['health_score']:.2f}")
            print(f"    Success Rate: {provider_metrics['success_rate']:.2f}")
            print(f"    Calls: {provider_metrics['total_calls']}")
            if provider_metrics['failure_types']:
                print(f"    Failure Types: {dict(provider_metrics['failure_types'])}")
        
        print(f"\n✅ Phase 3.4.3.2 Circuit Breaker test completed")
        print(f"🔌 Production-grade failure protection with automatic fallback!")
        
    else:
        print("Phase 3.4.3.2 Circuit Breaker Pattern")
        print("Production-grade circuit breaker for TTS provider failure protection")
        print("Usage: python phase3_43_circuit_breaker.py --test")

if __name__ == "__main__":
    main()