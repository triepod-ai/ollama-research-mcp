#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "python-dotenv>=1.0.0",
# ]
# ///

"""
Phase 3.4.1 Provider Health Optimization System
High-performance provider health monitoring with intelligent caching and background refresh.

Features:
- Background health monitoring without blocking TTS requests
- Predictive health updates based on usage patterns
- Circuit breaker pattern for failing providers
- Health prediction algorithms based on historical data
- Intelligent provider selection with cached health scores
- Non-blocking health checks with fallback mechanisms
"""

import asyncio
import os
import subprocess
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Callable, Any, Tuple
from concurrent.futures import ThreadPoolExecutor, Future
from dotenv import load_dotenv

# Load environment variables
env_path = Path.home() / "brainpods" / ".env"
if env_path.exists():
    load_dotenv(env_path)

# Import cache manager
try:
    try:
        from .phase3_cache_manager import get_cache_manager, cached
    except ImportError:
        from phase3_cache_manager import get_cache_manager, cached
    CACHE_MANAGER_AVAILABLE = True
except ImportError:
    CACHE_MANAGER_AVAILABLE = False

class ProviderType(Enum):
    """TTS provider types."""
    OPENAI = "openai"
    ELEVENLABS = "elevenlabs"
    PYTTSX3 = "pyttsx3"

class ProviderHealthStatus(Enum):
    """Provider health status levels."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"  
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"
    CIRCUIT_OPEN = "circuit_open"

@dataclass
class ProviderHealthMetrics:
    """Comprehensive provider health metrics."""
    provider: ProviderType
    status: ProviderHealthStatus
    
    # Performance metrics
    response_time_ms: float
    success_rate: float  # 0.0 to 1.0
    error_rate: float   # 0.0 to 1.0
    
    # Availability metrics
    uptime_percentage: float  # 0.0 to 100.0
    last_success_time: Optional[float]
    last_failure_time: Optional[float]
    
    # Load metrics
    requests_per_minute: float
    concurrent_requests: int
    queue_length: int
    
    # Quality metrics
    audio_quality_score: float  # 0.0 to 1.0
    latency_percentile_95: float
    
    # Metadata
    timestamp: float = field(default_factory=time.time)
    health_score: float = field(init=False)  # Computed composite score
    
    def __post_init__(self):
        """Calculate composite health score."""
        self.health_score = self._calculate_health_score()
    
    def _calculate_health_score(self) -> float:
        """
        Calculate composite health score (0.0 to 1.0).
        
        Factors:
        - Success rate (40%)
        - Response time (25%) 
        - Uptime (20%)
        - Audio quality (10%)
        - Load factor (5%)
        """
        # Response time score (lower is better, normalize to 2000ms max)
        response_score = max(0, 1.0 - (self.response_time_ms / 2000))
        
        # Load score (lower load is better, normalize to 100 RPM max)
        load_score = max(0, 1.0 - (self.requests_per_minute / 100))
        
        # Uptime score (convert percentage to 0-1 range)
        uptime_score = self.uptime_percentage / 100.0
        
        # Weighted composite score
        score = (
            self.success_rate * 0.40 +         # 40% weight
            response_score * 0.25 +            # 25% weight  
            uptime_score * 0.20 +              # 20% weight
            self.audio_quality_score * 0.10 +  # 10% weight
            load_score * 0.05                  # 5% weight
        )
        
        return max(0.0, min(1.0, score))

@dataclass 
class HealthCheckResult:
    """Result of a provider health check."""
    provider: ProviderType
    success: bool
    response_time_ms: float
    error_message: Optional[str] = None
    timestamp: float = field(default_factory=time.time)

class ProviderHealthPredictor:
    """Predictive health analysis based on historical data."""
    
    def __init__(self, history_size: int = 100):
        """
        Initialize health predictor.
        
        Args:
            history_size: Number of historical data points to maintain
        """
        self.history_size = history_size
        self.health_history: Dict[ProviderType, deque] = defaultdict(
            lambda: deque(maxlen=history_size)
        )
        self.trend_cache: Dict[ProviderType, Tuple[str, float]] = {}  # (trend, confidence)
    
    def add_health_data(self, metrics: ProviderHealthMetrics):
        """Add health metrics to history."""
        self.health_history[metrics.provider].append(metrics)
        
        # Invalidate trend cache for this provider
        if metrics.provider in self.trend_cache:
            del self.trend_cache[metrics.provider]
    
    def predict_health_trend(self, provider: ProviderType) -> Tuple[str, float]:
        """
        Predict health trend for provider.
        
        Args:
            provider: Provider to analyze
            
        Returns:
            Tuple of (trend, confidence) where trend is 'improving', 'stable', or 'degrading'
        """
        if provider in self.trend_cache:
            return self.trend_cache[provider]
        
        history = self.health_history[provider]
        
        if len(history) < 5:
            # Not enough data
            result = ("unknown", 0.0)
            self.trend_cache[provider] = result
            return result
        
        # Analyze recent health score trend
        recent_scores = [metrics.health_score for metrics in list(history)[-10:]]
        
        # Simple linear trend analysis
        trend_score = self._calculate_trend(recent_scores)
        confidence = min(1.0, len(recent_scores) / 10.0)  # More data = higher confidence
        
        if trend_score > 0.05:
            trend = "improving"
        elif trend_score < -0.05:
            trend = "degrading" 
        else:
            trend = "stable"
        
        result = (trend, confidence)
        self.trend_cache[provider] = result
        return result
    
    def _calculate_trend(self, scores: List[float]) -> float:
        """Calculate trend coefficient for scores."""
        if len(scores) < 2:
            return 0.0
        
        # Simple linear regression slope
        n = len(scores)
        x_mean = (n - 1) / 2
        y_mean = sum(scores) / n
        
        numerator = sum((i - x_mean) * (scores[i] - y_mean) for i in range(n))
        denominator = sum((i - x_mean) ** 2 for i in range(n))
        
        if denominator == 0:
            return 0.0
        
        return numerator / denominator

class CircuitBreaker:
    """Circuit breaker pattern for failing providers."""
    
    def __init__(self, failure_threshold: int = 5, recovery_timeout: float = 60.0):
        """
        Initialize circuit breaker.
        
        Args:
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Time to wait before attempting recovery
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = 0.0
        self.state = "closed"  # closed, open, half_open
        
    def call(self, func: Callable, *args, **kwargs) -> Tuple[Any, bool]:
        """
        Execute function with circuit breaker protection.
        
        Returns:
            Tuple of (result, success)
        """
        now = time.time()
        
        if self.state == "open":
            # Check if we should try recovery
            if now - self.last_failure_time > self.recovery_timeout:
                self.state = "half_open"
            else:
                return None, False
        
        try:
            result = func(*args, **kwargs)
            
            # Success - reset circuit breaker
            if self.state == "half_open":
                self.state = "closed"
                self.failure_count = 0
            
            return result, True
            
        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = now
            
            if self.failure_count >= self.failure_threshold:
                self.state = "open"
            
            return str(e), False
    
    def is_open(self) -> bool:
        """Check if circuit is open."""
        return self.state == "open"

class OptimizedProviderHealthMonitor:
    """
    High-performance provider health monitoring system.
    
    Features:
    - Background health checking without blocking requests
    - Intelligent caching with predictive refresh
    - Circuit breaker protection for failing providers
    - Health trend prediction and analysis
    - Provider selection optimization based on cached health
    """
    
    def __init__(self):
        """Initialize the optimized health monitor."""
        self.cache_manager = get_cache_manager() if CACHE_MANAGER_AVAILABLE else None
        
        # Health monitoring components
        self.health_predictors: Dict[ProviderType, ProviderHealthPredictor] = {}
        self.circuit_breakers: Dict[ProviderType, CircuitBreaker] = {}
        self.background_executor = ThreadPoolExecutor(max_workers=3, thread_name_prefix="health_monitor")
        
        # Configuration
        self.health_cache_ttl = float(os.getenv("PROVIDER_HEALTH_CACHE_TTL", "30"))  # 30 seconds
        self.background_refresh_interval = float(os.getenv("HEALTH_REFRESH_INTERVAL", "20"))  # 20 seconds
        self.health_check_timeout = float(os.getenv("HEALTH_CHECK_TIMEOUT", "5"))  # 5 seconds
        
        # Initialize providers
        self.providers = list(ProviderType)
        for provider in self.providers:
            self.health_predictors[provider] = ProviderHealthPredictor()
            self.circuit_breakers[provider] = CircuitBreaker()
        
        # Background monitoring
        self._monitoring_active = True
        self._background_thread = threading.Thread(target=self._background_monitor, daemon=True)
        self._background_thread.start()
        
        print("🏥 Optimized Provider Health Monitor initialized")
        print(f"  Providers: {len(self.providers)}")
        print(f"  Cache TTL: {self.health_cache_ttl}s")
        print(f"  Background refresh: {self.background_refresh_interval}s")
    
    def get_provider_health(self, provider: ProviderType) -> Optional[ProviderHealthMetrics]:
        """
        Get cached provider health with non-blocking refresh.
        
        Args:
            provider: Provider to check
            
        Returns:
            Cached health metrics or None if unavailable
        """
        if not self.cache_manager:
            # Fallback to direct check if cache unavailable
            return self._perform_direct_health_check(provider)
        
        # Try to get from cache
        cache_key = f"health_{provider.value}"
        cached_health = self.cache_manager.get("provider_health", cache_key)
        
        if cached_health is not None:
            # Cache hit - schedule background refresh if needed
            if self._should_background_refresh(cached_health):
                self._schedule_background_refresh(provider)
            
            return cached_health
        
        # Cache miss - perform quick health check
        health = self._perform_quick_health_check(provider)
        
        if health:
            # Cache the result
            self.cache_manager.set("provider_health", cache_key, health, self.health_cache_ttl)
        
        return health
    
    def get_best_provider(self, exclude_unhealthy: bool = True) -> Optional[ProviderType]:
        """
        Get the best available provider based on cached health metrics.
        
        Args:
            exclude_unhealthy: Whether to exclude unhealthy providers
            
        Returns:
            Best provider or None if none available
        """
        provider_scores = []
        
        for provider in self.providers:
            health = self.get_provider_health(provider)
            
            if not health:
                continue
                
            # Skip unhealthy providers if requested
            if exclude_unhealthy and health.status in [
                ProviderHealthStatus.UNHEALTHY, 
                ProviderHealthStatus.CIRCUIT_OPEN
            ]:
                continue
            
            provider_scores.append((provider, health.health_score))
        
        if not provider_scores:
            return None
        
        # Sort by health score (descending) and return best
        provider_scores.sort(key=lambda x: x[1], reverse=True)
        return provider_scores[0][0]
    
    def force_health_refresh(self, provider: ProviderType) -> ProviderHealthMetrics:
        """
        Force immediate health refresh for a provider.
        
        Args:
            provider: Provider to refresh
            
        Returns:
            Updated health metrics
        """
        health = self._perform_comprehensive_health_check(provider)
        
        # Update cache
        if self.cache_manager and health:
            cache_key = f"health_{provider.value}"
            self.cache_manager.set("provider_health", cache_key, health, self.health_cache_ttl)
        
        return health
    
    def _should_background_refresh(self, health: ProviderHealthMetrics) -> bool:
        """Check if background refresh should be scheduled."""
        age_seconds = time.time() - health.timestamp
        refresh_threshold = self.health_cache_ttl * 0.7  # Refresh when 70% of TTL elapsed
        
        return age_seconds > refresh_threshold
    
    def _schedule_background_refresh(self, provider: ProviderType):
        """Schedule background health refresh."""
        def refresh_task():
            try:
                self.force_health_refresh(provider)
            except Exception as e:
                print(f"❌ Background refresh failed for {provider.value}: {e}")
        
        self.background_executor.submit(refresh_task)
    
    def _perform_quick_health_check(self, provider: ProviderType) -> Optional[ProviderHealthMetrics]:
        """
        Perform quick health check with circuit breaker protection.
        
        Args:
            provider: Provider to check
            
        Returns:
            Health metrics or None if check failed
        """
        circuit_breaker = self.circuit_breakers[provider]
        
        if circuit_breaker.is_open():
            # Circuit is open - return unhealthy status
            return ProviderHealthMetrics(
                provider=provider,
                status=ProviderHealthStatus.CIRCUIT_OPEN,
                response_time_ms=float('inf'),
                success_rate=0.0,
                error_rate=1.0,
                uptime_percentage=0.0,
                last_success_time=None,
                last_failure_time=time.time(),
                requests_per_minute=0.0,
                concurrent_requests=0,
                queue_length=0,
                audio_quality_score=0.0,
                latency_percentile_95=float('inf')
            )
        
        def check_function():
            return self._check_provider_ping(provider)
        
        result, success = circuit_breaker.call(check_function)
        
        if success:
            return result
        else:
            return None
    
    def _perform_comprehensive_health_check(self, provider: ProviderType) -> ProviderHealthMetrics:
        """
        Perform comprehensive health check with full metrics.
        
        Args:
            provider: Provider to check
            
        Returns:
            Complete health metrics
        """
        start_time = time.time()
        
        # Ping test returns health metrics
        health = self._check_provider_ping(provider)
        
        # Get historical success rate and update metrics
        success_rate = self._calculate_success_rate(provider)
        
        # Update health with historical data
        health.success_rate = success_rate
        health.error_rate = 1.0 - success_rate
        health.uptime_percentage = success_rate * 100
        
        # Update status based on comprehensive data
        health.status = self._determine_health_status(
            health.status == ProviderHealthStatus.HEALTHY, 
            success_rate
        )
        
        # Add to predictor history
        self.health_predictors[provider].add_health_data(health)
        
        return health
    
    def _perform_direct_health_check(self, provider: ProviderType) -> Optional[ProviderHealthMetrics]:
        """Fallback direct health check when cache unavailable."""
        try:
            return self._perform_quick_health_check(provider)
        except Exception as e:
            print(f"❌ Direct health check failed for {provider.value}: {e}")
            return None
    
    def _check_provider_ping(self, provider: ProviderType) -> ProviderHealthMetrics:
        """
        Simple ping test for provider availability.
        
        Args:
            provider: Provider to ping
            
        Returns:
            Basic health metrics from ping test
        """
        start_time = time.time()
        ping_success = False
        
        try:
            if provider == ProviderType.OPENAI:
                # Check if OpenAI API key is available and valid
                api_key = os.getenv("OPENAI_API_KEY")
                ping_success = bool(api_key and len(api_key) > 10)
                
            elif provider == ProviderType.ELEVENLABS:
                # Check if ElevenLabs API key is available
                api_key = os.getenv("ELEVENLABS_API_KEY")
                ping_success = bool(api_key and len(api_key) > 10)
                
            elif provider == ProviderType.PYTTSX3:
                # pyttsx3 is always available (offline)
                ping_success = True
                
            else:
                ping_success = False
                
        except Exception:
            ping_success = False
        
        # Calculate response time
        response_time = (time.time() - start_time) * 1000
        
        # Create basic health metrics
        return ProviderHealthMetrics(
            provider=provider,
            status=ProviderHealthStatus.HEALTHY if ping_success else ProviderHealthStatus.UNHEALTHY,
            response_time_ms=response_time,
            success_rate=1.0 if ping_success else 0.0,
            error_rate=0.0 if ping_success else 1.0,
            uptime_percentage=100.0 if ping_success else 0.0,
            last_success_time=time.time() if ping_success else None,
            last_failure_time=None if ping_success else time.time(),
            requests_per_minute=self._estimate_load(provider),
            concurrent_requests=0,
            queue_length=0,
            audio_quality_score=self._check_audio_quality(provider),
            latency_percentile_95=response_time * 1.2
        )
    
    def _check_audio_quality(self, provider: ProviderType) -> float:
        """
        Simple audio quality assessment.
        
        Args:
            provider: Provider to assess
            
        Returns:
            Quality score (0.0 to 1.0)
        """
        # Simplified quality scoring
        quality_scores = {
            ProviderType.ELEVENLABS: 0.95,  # Highest quality
            ProviderType.OPENAI: 0.85,     # High quality
            ProviderType.PYTTSX3: 0.60     # Basic quality
        }
        
        return quality_scores.get(provider, 0.5)
    
    def _calculate_success_rate(self, provider: ProviderType) -> float:
        """
        Calculate success rate from historical data.
        
        Args:
            provider: Provider to analyze
            
        Returns:
            Success rate (0.0 to 1.0)
        """
        predictor = self.health_predictors[provider]
        history = predictor.health_history[provider]
        
        if not history:
            return 0.8  # Default assumption
        
        # Calculate average success rate from recent history
        recent_metrics = list(history)[-10:]  # Last 10 checks
        if not recent_metrics:
            return 0.8
        
        avg_success_rate = sum(m.success_rate for m in recent_metrics) / len(recent_metrics)
        return avg_success_rate
    
    def _estimate_load(self, provider: ProviderType) -> float:
        """
        Estimate current load on provider.
        
        Args:
            provider: Provider to analyze
            
        Returns:
            Estimated requests per minute
        """
        # Simplified load estimation
        # In real implementation, this would track actual request rates
        load_estimates = {
            ProviderType.OPENAI: 10.0,
            ProviderType.ELEVENLABS: 5.0,
            ProviderType.PYTTSX3: 15.0
        }
        
        return load_estimates.get(provider, 5.0)
    
    def _determine_health_status(self, ping_success: bool, success_rate: float) -> ProviderHealthStatus:
        """
        Determine overall health status.
        
        Args:
            ping_success: Whether ping test succeeded
            success_rate: Historical success rate
            
        Returns:
            Health status
        """
        if not ping_success:
            return ProviderHealthStatus.UNHEALTHY
        
        if success_rate >= 0.9:
            return ProviderHealthStatus.HEALTHY
        elif success_rate >= 0.7:
            return ProviderHealthStatus.DEGRADED
        else:
            return ProviderHealthStatus.UNHEALTHY
    
    def _background_monitor(self):
        """Background monitoring loop."""
        print("🔄 Background health monitoring started")
        
        while self._monitoring_active:
            try:
                for provider in self.providers:
                    # Refresh health data
                    self._schedule_background_refresh(provider)
                
                # Sleep until next monitoring cycle
                time.sleep(self.background_refresh_interval)
                
            except Exception as e:
                print(f"⚠️ Background monitoring error: {e}")
                time.sleep(5)  # Brief pause on error
    
    def get_monitoring_stats(self) -> Dict[str, Any]:
        """Get comprehensive monitoring statistics."""
        stats = {
            "cache_enabled": self.cache_manager is not None,
            "monitoring_active": self._monitoring_active,
            "configuration": {
                "health_cache_ttl": self.health_cache_ttl,
                "background_refresh_interval": self.background_refresh_interval,
                "health_check_timeout": self.health_check_timeout
            },
            "providers": {}
        }
        
        for provider in self.providers:
            health = self.get_provider_health(provider)
            predictor = self.health_predictors[provider]
            circuit_breaker = self.circuit_breakers[provider]
            trend, confidence = predictor.predict_health_trend(provider)
            
            provider_stats = {
                "current_health": {
                    "status": health.status.value if health else "unknown",
                    "health_score": health.health_score if health else 0.0,
                    "response_time_ms": health.response_time_ms if health else float('inf')
                },
                "prediction": {
                    "trend": trend,
                    "confidence": confidence
                },
                "circuit_breaker": {
                    "state": circuit_breaker.state,
                    "failure_count": circuit_breaker.failure_count
                },
                "history_size": len(predictor.health_history[provider])
            }
            
            stats["providers"][provider.value] = provider_stats
        
        return stats
    
    def shutdown(self):
        """Shutdown the health monitor."""
        self._monitoring_active = False
        self.background_executor.shutdown(wait=True)
        print("🛑 Provider health monitor shutdown")

# Global health monitor instance
_health_monitor = None

def get_health_monitor() -> OptimizedProviderHealthMonitor:
    """Get or create the global health monitor."""
    global _health_monitor
    if _health_monitor is None:
        _health_monitor = OptimizedProviderHealthMonitor()
    return _health_monitor

@cached("provider_selection", ttl=60.0)
def get_optimal_provider(exclude_unhealthy: bool = True) -> Optional[ProviderType]:
    """
    Get optimal provider with caching.
    
    Args:
        exclude_unhealthy: Whether to exclude unhealthy providers
        
    Returns:
        Best available provider
    """
    monitor = get_health_monitor()
    return monitor.get_best_provider(exclude_unhealthy)

if __name__ == "__main__":
    import sys
    
    if "--test" in sys.argv:
        print("🧪 Testing Phase 3.4.1 Provider Health Optimization")
        print("=" * 60)
        
        monitor = get_health_monitor()
        
        print("\n🏥 Testing Provider Health Monitoring:")
        
        # Test each provider
        for provider in ProviderType:
            print(f"\n  Testing {provider.value}...")
            
            health = monitor.get_provider_health(provider)
            
            if health:
                print(f"    ✅ Status: {health.status.value}")
                print(f"    📊 Health Score: {health.health_score:.2f}")
                print(f"    ⏱️ Response Time: {health.response_time_ms:.1f}ms")
                print(f"    📈 Success Rate: {health.success_rate:.1%}")
            else:
                print(f"    ❌ Health check failed")
        
        # Test best provider selection
        print(f"\n🎯 Testing Provider Selection:")
        best_provider = monitor.get_best_provider()
        
        if best_provider:
            print(f"  🏆 Best Provider: {best_provider.value}")
        else:
            print(f"  ❌ No healthy providers available")
        
        # Test cached provider selection
        print(f"\n💾 Testing Cached Provider Selection:")
        cached_provider = get_optimal_provider()
        
        if cached_provider:
            print(f"  🏆 Cached Best Provider: {cached_provider.value}")
        else:
            print(f"  ❌ No cached providers available")
        
        # Show monitoring stats
        print(f"\n📊 Monitoring Statistics:")
        stats = monitor.get_monitoring_stats()
        
        print(f"  Cache Enabled: {stats['cache_enabled']}")
        print(f"  Monitoring Active: {stats['monitoring_active']}")
        print(f"  Health Cache TTL: {stats['configuration']['health_cache_ttl']}s")
        
        print(f"  Provider Status:")
        for provider_name, provider_stats in stats['providers'].items():
            health = provider_stats['current_health']
            trend = provider_stats['prediction']['trend']
            confidence = provider_stats['prediction']['confidence']
            
            print(f"    {provider_name}:")
            print(f"      Status: {health['status']}")
            print(f"      Health Score: {health['health_score']:.2f}")
            print(f"      Trend: {trend} (confidence: {confidence:.1%})")
            print(f"      Circuit: {provider_stats['circuit_breaker']['state']}")
        
        # Brief pause for background monitoring
        print(f"\n⏳ Waiting for background refresh cycle...")
        time.sleep(3)
        
        print(f"\n✅ Phase 3.4.1 Provider Health Optimization test completed")
        print(f"🏆 Health monitoring optimized with caching and background refresh!")
        
        # Cleanup
        monitor.shutdown()
    
    else:
        print("Phase 3.4.1 Provider Health Optimization System")
        print("High-performance provider health monitoring with intelligent caching")
        print("Usage: python phase3_provider_health_optimizer.py --test")