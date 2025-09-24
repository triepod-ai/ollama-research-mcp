#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "python-dotenv>=1.0.0",
# ]
# ///

"""
Phase 3.3.2 Provider Health Monitoring & Load Balancing System
Advanced health monitoring, load balancing, and provider optimization for TTS systems.

Features:
- Real-time provider health monitoring with multiple check types
- Dynamic load balancing with intelligent routing algorithms
- Provider performance analytics and optimization recommendations
- API health checks with timeout and retry logic
- Failure prediction and proactive provider switching
- Historical performance tracking and trend analysis
- Integration with playback coordinator for seamless operation
"""

import asyncio
import json
import os
import subprocess
import time
import threading
import requests
from collections import deque, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv

# Load environment variables
env_path = Path.home() / "brainpods" / ".env"
if env_path.exists():
    load_dotenv(env_path)

class HealthCheckType(Enum):
    """Types of health checks performed."""
    API_PING = "api_ping"           # Basic API connectivity
    AUDIO_GENERATION = "audio_gen"  # Test actual TTS generation
    LATENCY_TEST = "latency"        # Response time measurement
    QUOTA_CHECK = "quota"           # API quota/rate limit status
    VOICE_LIST = "voice_list"       # Available voices check

class ProviderCapability(Enum):
    """Provider capability levels."""
    BASIC = "basic"                 # Basic TTS functionality
    ADVANCED = "advanced"           # Multiple voices, effects
    PREMIUM = "premium"             # Real-time, streaming, emotions
    ENTERPRISE = "enterprise"       # Full API, custom models

class LoadBalancingStrategy(Enum):
    """Load balancing strategies."""
    ROUND_ROBIN = "round_robin"     # Simple rotation
    WEIGHTED_ROUND_ROBIN = "weighted_round_robin"  # Based on capacity
    LEAST_CONNECTIONS = "least_connections"        # Least active requests
    PERFORMANCE_BASED = "performance_based"        # Best performing provider
    INTELLIGENT = "intelligent"     # ML-based routing
    FAILOVER_ONLY = "failover_only" # Only use backup on failure

@dataclass
class HealthCheckResult:
    """Result of a health check operation."""
    check_type: HealthCheckType
    success: bool
    latency_ms: float
    error_message: str = ""
    response_data: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def is_acceptable_latency(self, threshold_ms: float = 5000) -> bool:
        """Check if latency is acceptable."""
        return self.latency_ms <= threshold_ms

@dataclass
class ProviderPerformanceProfile:
    """Detailed provider performance profile."""
    provider_name: str
    capability_level: ProviderCapability
    
    # Health metrics
    health_score: float = 0.0  # 0-100 composite health score
    uptime_percentage: float = 0.0
    success_rate: float = 0.0
    
    # Performance metrics  
    average_latency: float = 0.0
    p95_latency: float = 0.0
    p99_latency: float = 0.0
    throughput_rpm: float = 0.0  # Requests per minute
    
    # Resource metrics
    current_load: int = 0
    max_concurrent: int = 5
    queue_depth: int = 0
    
    # Cost metrics
    cost_per_request: float = 0.0
    monthly_usage: float = 0.0
    quota_remaining: Optional[int] = None
    
    # Recent performance history
    recent_checks: deque = field(default_factory=lambda: deque(maxlen=100))
    latency_history: deque = field(default_factory=lambda: deque(maxlen=1000))
    error_history: deque = field(default_factory=lambda: deque(maxlen=50))
    
    # Availability tracking
    last_successful_check: Optional[datetime] = None
    last_failed_check: Optional[datetime] = None
    consecutive_failures: int = 0
    total_checks: int = 0
    
    def update_from_check(self, result: HealthCheckResult):
        """Update profile from health check result."""
        self.recent_checks.append(result)
        self.total_checks += 1
        
        if result.success:
            self.last_successful_check = result.timestamp
            self.consecutive_failures = 0
            self.latency_history.append(result.latency_ms)
        else:
            self.last_failed_check = result.timestamp
            self.consecutive_failures += 1
            self.error_history.append({
                "timestamp": result.timestamp.isoformat(),
                "check_type": result.check_type.value,
                "error": result.error_message,
                "latency": result.latency_ms
            })
        
        # Recalculate metrics
        self._recalculate_metrics()
    
    def _recalculate_metrics(self):
        """Recalculate performance metrics from recent data."""
        if not self.recent_checks:
            return
        
        # Success rate from recent checks
        successful_checks = sum(1 for check in self.recent_checks if check.success)
        self.success_rate = (successful_checks / len(self.recent_checks)) * 100
        
        # Latency metrics from successful checks
        if self.latency_history:
            sorted_latencies = sorted(self.latency_history)
            self.average_latency = sum(sorted_latencies) / len(sorted_latencies)
            
            # Percentiles
            if len(sorted_latencies) > 1:
                p95_idx = int(len(sorted_latencies) * 0.95)
                p99_idx = int(len(sorted_latencies) * 0.99)
                self.p95_latency = sorted_latencies[p95_idx]
                self.p99_latency = sorted_latencies[p99_idx]
        
        # Uptime from recent 24h (approximate)
        now = datetime.now()
        recent_24h_checks = [
            check for check in self.recent_checks 
            if (now - check.timestamp).total_seconds() <= 86400
        ]
        
        if recent_24h_checks:
            successful_24h = sum(1 for check in recent_24h_checks if check.success)
            self.uptime_percentage = (successful_24h / len(recent_24h_checks)) * 100
        
        # Composite health score
        self.health_score = self._calculate_health_score()
    
    def _calculate_health_score(self) -> float:
        """Calculate composite health score (0-100)."""
        # Base score from success rate
        base_score = self.success_rate
        
        # Penalty for high latency
        if self.average_latency > 5000:  # >5s
            base_score *= 0.5
        elif self.average_latency > 2000:  # >2s
            base_score *= 0.8
        
        # Penalty for consecutive failures
        if self.consecutive_failures >= 5:
            base_score *= 0.1
        elif self.consecutive_failures >= 3:
            base_score *= 0.5
        
        # Bonus for consistent low latency
        if self.average_latency < 1000 and self.p95_latency < 2000:
            base_score = min(100, base_score * 1.1)
        
        # Load factor (prefer providers with capacity)
        if self.max_concurrent > 0:
            load_factor = 1.0 - (self.current_load / self.max_concurrent)
            base_score *= (0.5 + 0.5 * load_factor)  # 50% base + 50% load factor
        
        return max(0.0, min(100.0, base_score))
    
    def get_routing_priority(self) -> float:
        """Get routing priority for load balancing (higher = better)."""
        # Combine health score with load balancing factors
        priority = self.health_score
        
        # Prefer providers with lower current load
        if self.max_concurrent > 0:
            load_factor = 1.0 - (self.current_load / self.max_concurrent)
            priority *= (0.7 + 0.3 * load_factor)  # Weight 70% health, 30% load
        
        # Prefer faster providers for real-time applications
        if self.average_latency > 0:
            speed_factor = max(0.1, 1.0 - (self.average_latency / 10000))  # 10s baseline
            priority *= (0.8 + 0.2 * speed_factor)  # Weight 80% existing, 20% speed
        
        # Cost factor (if cost is a consideration)
        # Lower cost gets slight preference
        if self.cost_per_request > 0:
            # Normalize cost factor (assuming $0.01 per request as baseline)
            cost_factor = max(0.5, 1.0 - (self.cost_per_request / 0.01))
            priority *= (0.95 + 0.05 * cost_factor)  # Small weight for cost
        
        return priority
    
    def is_available(self) -> bool:
        """Check if provider is currently available."""
        return (
            self.health_score > 20 and  # Minimum health threshold
            self.consecutive_failures < 5 and  # Not too many recent failures
            self.current_load < self.max_concurrent and  # Has capacity
            (self.quota_remaining is None or self.quota_remaining > 10)  # Has quota
        )
    
    def get_status_summary(self) -> Dict[str, Any]:
        """Get status summary for monitoring."""
        return {
            "provider": self.provider_name,
            "health_score": round(self.health_score, 1),
            "success_rate": round(self.success_rate, 1),
            "uptime_percentage": round(self.uptime_percentage, 1),
            "average_latency": round(self.average_latency, 1),
            "current_load": self.current_load,
            "max_concurrent": self.max_concurrent,
            "consecutive_failures": self.consecutive_failures,
            "is_available": self.is_available(),
            "routing_priority": round(self.get_routing_priority(), 1),
            "last_check": self.recent_checks[-1].timestamp.isoformat() if self.recent_checks else None,
        }

class ProviderHealthMonitor:
    """Advanced provider health monitoring system."""
    
    def __init__(self):
        """Initialize the health monitor."""
        self.providers: Dict[str, ProviderPerformanceProfile] = {}
        self.load_balancing_strategy = LoadBalancingStrategy.INTELLIGENT
        self.monitoring_active = False
        self.monitor_thread: Optional[threading.Thread] = None
        self.executor = ThreadPoolExecutor(max_workers=6, thread_name_prefix="health_monitor")
        
        # Configuration
        self.check_interval = int(os.getenv("TTS_HEALTH_CHECK_INTERVAL", "60"))  # seconds
        self.check_timeout = int(os.getenv("TTS_HEALTH_CHECK_TIMEOUT", "10"))  # seconds
        self.failure_threshold = int(os.getenv("TTS_FAILURE_THRESHOLD", "3"))
        self.recovery_threshold = int(os.getenv("TTS_RECOVERY_THRESHOLD", "2"))
        
        # Health check configurations per provider
        self.provider_configs = {
            "openai": {
                "api_endpoint": "https://api.openai.com/v1/models",
                "audio_endpoint": "https://api.openai.com/v1/audio/speech",
                "test_voice": "nova",
                "capability": ProviderCapability.ADVANCED,
                "cost_per_request": 0.000015,  # $0.015 per 1K characters
                "max_concurrent": 5
            },
            "elevenlabs": {
                "api_endpoint": "https://api.elevenlabs.io/v1/voices",
                "audio_endpoint": "https://api.elevenlabs.io/v1/text-to-speech",
                "test_voice": "21m00Tcm4TlvDq8ikWAM",  # Rachel
                "capability": ProviderCapability.PREMIUM,
                "cost_per_request": 0.0003,  # ~$0.30 per 1K characters
                "max_concurrent": 3
            },
            "pyttsx3": {
                "api_endpoint": None,  # Local/offline
                "capability": ProviderCapability.BASIC,
                "cost_per_request": 0.0,
                "max_concurrent": 1
            }
        }
        
        # Initialize providers
        self._initialize_providers()
        
        # Load balancing state
        self.round_robin_index = 0
        self.request_counts = defaultdict(int)
        self.routing_history = deque(maxlen=1000)
        
        # Analytics
        self.monitoring_stats = {
            "total_checks": 0,
            "successful_checks": 0,
            "failed_checks": 0,
            "average_check_duration": 0.0,
            "providers_monitored": 0,
            "routing_decisions": 0,
        }
    
    def _initialize_providers(self):
        """Initialize provider performance profiles."""
        for provider_name, config in self.provider_configs.items():
            self.providers[provider_name] = ProviderPerformanceProfile(
                provider_name=provider_name,
                capability_level=config["capability"],
                max_concurrent=config["max_concurrent"],
                cost_per_request=config["cost_per_request"]
            )
    
    def start_monitoring(self):
        """Start the health monitoring system."""
        if self.monitoring_active:
            return
        
        self.monitoring_active = True
        self.monitor_thread = threading.Thread(
            target=self._monitoring_loop,
            daemon=True,
            name="tts_health_monitor"
        )
        self.monitor_thread.start()
    
    def stop_monitoring(self):
        """Stop the health monitoring system."""
        self.monitoring_active = False
        
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=5)
        
        self.executor.shutdown(wait=True, timeout=10)
    
    def _monitoring_loop(self):
        """Main monitoring loop."""
        while self.monitoring_active:
            try:
                start_time = time.time()
                
                # Run health checks for all providers
                self._run_health_checks()
                
                # Update monitoring stats
                check_duration = time.time() - start_time
                self.monitoring_stats["average_check_duration"] = (
                    self.monitoring_stats["average_check_duration"] * 0.9 + 
                    check_duration * 0.1
                )
                
                # Wait for next check cycle
                time.sleep(self.check_interval)
                
            except Exception as e:
                print(f"Health monitoring error: {e}")
                time.sleep(min(self.check_interval, 30))  # Shorter retry on error
    
    def _run_health_checks(self):
        """Run health checks for all providers."""
        futures = []
        
        for provider_name in self.providers.keys():
            future = self.executor.submit(self._check_provider_health, provider_name)
            futures.append((provider_name, future))
        
        # Process results
        for provider_name, future in futures:
            try:
                results = future.result(timeout=self.check_timeout + 5)
                for result in results:
                    self.providers[provider_name].update_from_check(result)
                    
                    # Update global stats
                    self.monitoring_stats["total_checks"] += 1
                    if result.success:
                        self.monitoring_stats["successful_checks"] += 1
                    else:
                        self.monitoring_stats["failed_checks"] += 1
                        
            except Exception as e:
                # Create failure result for timeout/error
                failure_result = HealthCheckResult(
                    check_type=HealthCheckType.API_PING,
                    success=False,
                    latency_ms=self.check_timeout * 1000,
                    error_message=f"Health check failed: {str(e)}"
                )
                self.providers[provider_name].update_from_check(failure_result)
                self.monitoring_stats["failed_checks"] += 1
    
    def _check_provider_health(self, provider_name: str) -> List[HealthCheckResult]:
        """Perform comprehensive health check for a provider."""
        config = self.provider_configs.get(provider_name, {})
        results = []
        
        # API Ping Test
        if config.get("api_endpoint"):
            ping_result = self._api_ping_check(provider_name, config)
            results.append(ping_result)
        
        # Audio Generation Test (less frequent)
        if random.choice([True, False, False]):  # 1/3 probability
            if config.get("audio_endpoint"):
                audio_result = self._audio_generation_check(provider_name, config)
                results.append(audio_result)
        
        # For pyttsx3 (offline provider)
        if provider_name == "pyttsx3":
            offline_result = self._offline_provider_check(provider_name)
            results.append(offline_result)
        
        return results
    
    def _api_ping_check(self, provider_name: str, config: Dict) -> HealthCheckResult:
        """Perform API ping health check."""
        start_time = time.time()
        
        try:
            headers = {}
            if provider_name == "openai":
                api_key = os.getenv("OPENAI_API_KEY")
                if api_key:
                    headers["Authorization"] = f"Bearer {api_key}"
            elif provider_name == "elevenlabs":
                api_key = os.getenv("ELEVENLABS_API_KEY")  
                if api_key:
                    headers["xi-api-key"] = api_key
            
            response = requests.get(
                config["api_endpoint"],
                headers=headers,
                timeout=self.check_timeout
            )
            
            latency = (time.time() - start_time) * 1000
            
            if response.status_code == 200:
                return HealthCheckResult(
                    check_type=HealthCheckType.API_PING,
                    success=True,
                    latency_ms=latency,
                    response_data={"status_code": response.status_code},
                    metadata={"provider": provider_name}
                )
            else:
                return HealthCheckResult(
                    check_type=HealthCheckType.API_PING,
                    success=False,
                    latency_ms=latency,
                    error_message=f"HTTP {response.status_code}: {response.text[:100]}",
                    metadata={"provider": provider_name}
                )
                
        except requests.exceptions.Timeout:
            return HealthCheckResult(
                check_type=HealthCheckType.API_PING,
                success=False,
                latency_ms=self.check_timeout * 1000,
                error_message="Request timeout",
                metadata={"provider": provider_name}
            )
        except Exception as e:
            return HealthCheckResult(
                check_type=HealthCheckType.API_PING,
                success=False,
                latency_ms=(time.time() - start_time) * 1000,
                error_message=str(e),
                metadata={"provider": provider_name}
            )
    
    def _audio_generation_check(self, provider_name: str, config: Dict) -> HealthCheckResult:
        """Test actual audio generation capability."""
        start_time = time.time()
        test_text = "Health check test."
        
        try:
            # Use speak command to test actual generation
            cmd = ["speak", "--provider", provider_name, test_text]
            
            # Add voice if configured
            if config.get("test_voice"):
                cmd.extend(["--voice", config["test_voice"]])
            
            # Run with timeout
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.check_timeout,
                env={**os.environ, "TTS_TEST_MODE": "true"}  # Signal test mode
            )
            
            latency = (time.time() - start_time) * 1000
            
            if result.returncode == 0:
                return HealthCheckResult(
                    check_type=HealthCheckType.AUDIO_GENERATION,
                    success=True,
                    latency_ms=latency,
                    metadata={"provider": provider_name, "test_text": test_text}
                )
            else:
                return HealthCheckResult(
                    check_type=HealthCheckType.AUDIO_GENERATION,
                    success=False,
                    latency_ms=latency,
                    error_message=f"Generation failed: {result.stderr[:100]}",
                    metadata={"provider": provider_name}
                )
                
        except subprocess.TimeoutExpired:
            return HealthCheckResult(
                check_type=HealthCheckType.AUDIO_GENERATION,
                success=False,
                latency_ms=self.check_timeout * 1000,
                error_message="Audio generation timeout",
                metadata={"provider": provider_name}
            )
        except Exception as e:
            return HealthCheckResult(
                check_type=HealthCheckType.AUDIO_GENERATION,
                success=False,
                latency_ms=(time.time() - start_time) * 1000,
                error_message=str(e),
                metadata={"provider": provider_name}
            )
    
    def _offline_provider_check(self, provider_name: str) -> HealthCheckResult:
        """Check offline provider (pyttsx3) availability."""
        start_time = time.time()
        
        try:
            # Simple import test
            import pyttsx3
            engine = pyttsx3.init()
            engine.stop()  # Cleanup
            
            latency = (time.time() - start_time) * 1000
            
            return HealthCheckResult(
                check_type=HealthCheckType.API_PING,
                success=True,
                latency_ms=latency,
                metadata={"provider": provider_name, "type": "offline"}
            )
            
        except Exception as e:
            return HealthCheckResult(
                check_type=HealthCheckType.API_PING,
                success=False,
                latency_ms=(time.time() - start_time) * 1000,
                error_message=f"pyttsx3 unavailable: {str(e)}",
                metadata={"provider": provider_name}
            )
    
    def select_provider(self, message_priority: str = "normal", preferred_capability: Optional[ProviderCapability] = None) -> Optional[str]:
        """Select best provider using configured load balancing strategy."""
        available_providers = [
            name for name, profile in self.providers.items()
            if profile.is_available()
        ]
        
        if not available_providers:
            return None
        
        # Filter by capability if specified
        if preferred_capability:
            capable_providers = [
                name for name in available_providers
                if self.providers[name].capability_level.value >= preferred_capability.value
            ]
            if capable_providers:
                available_providers = capable_providers
        
        # Apply load balancing strategy
        selected_provider = self._apply_load_balancing_strategy(available_providers, message_priority)
        
        if selected_provider:
            # Update routing stats
            self.monitoring_stats["routing_decisions"] += 1
            self.request_counts[selected_provider] += 1
            self.routing_history.append({
                "provider": selected_provider,
                "timestamp": datetime.now().isoformat(),
                "strategy": self.load_balancing_strategy.value,
                "priority": message_priority,
                "available_count": len(available_providers)
            })
            
            # Update provider load
            self.providers[selected_provider].current_load += 1
        
        return selected_provider
    
    def _apply_load_balancing_strategy(self, available_providers: List[str], message_priority: str) -> Optional[str]:
        """Apply the configured load balancing strategy."""
        if not available_providers:
            return None
        
        if self.load_balancing_strategy == LoadBalancingStrategy.ROUND_ROBIN:
            # Simple round robin
            provider = available_providers[self.round_robin_index % len(available_providers)]
            self.round_robin_index += 1
            return provider
        
        elif self.load_balancing_strategy == LoadBalancingStrategy.LEAST_CONNECTIONS:
            # Provider with least current load
            return min(available_providers, key=lambda p: self.providers[p].current_load)
        
        elif self.load_balancing_strategy == LoadBalancingStrategy.PERFORMANCE_BASED:
            # Best performing provider
            return max(available_providers, key=lambda p: self.providers[p].health_score)
        
        elif self.load_balancing_strategy == LoadBalancingStrategy.INTELLIGENT:
            # Intelligent routing based on multiple factors
            provider_scores = [
                (provider, self.providers[provider].get_routing_priority())
                for provider in available_providers
            ]
            provider_scores.sort(key=lambda x: x[1], reverse=True)
            
            # Add randomization for providers with similar scores
            top_providers = [p for p, score in provider_scores[:2]]  # Top 2
            return random.choice(top_providers) if len(top_providers) > 1 else provider_scores[0][0]
        
        else:
            # Default to first available
            return available_providers[0]
    
    def release_provider(self, provider_name: str):
        """Release provider load after request completion."""
        if provider_name in self.providers:
            profile = self.providers[provider_name]
            if profile.current_load > 0:
                profile.current_load -= 1
    
    def get_monitoring_status(self) -> Dict[str, Any]:
        """Get comprehensive monitoring status."""
        return {
            "monitoring_active": self.monitoring_active,
            "load_balancing_strategy": self.load_balancing_strategy.value,
            "check_interval": self.check_interval,
            "providers": {
                name: profile.get_status_summary()
                for name, profile in self.providers.items()
            },
            "monitoring_stats": dict(self.monitoring_stats),
            "recent_routing": list(self.routing_history)[-10:],  # Last 10 routing decisions
        }
    
    def set_load_balancing_strategy(self, strategy: LoadBalancingStrategy):
        """Change load balancing strategy."""
        self.load_balancing_strategy = strategy
    
    def get_provider_recommendations(self) -> Dict[str, Any]:
        """Get optimization recommendations for providers."""
        recommendations = {
            "actions": [],
            "warnings": [],
            "optimizations": []
        }
        
        for name, profile in self.providers.items():
            # Check for unhealthy providers
            if profile.health_score < 50:
                recommendations["warnings"].append({
                    "provider": name,
                    "issue": "Low health score",
                    "score": profile.health_score,
                    "suggestion": "Check provider configuration and API keys"
                })
            
            # Check for high latency
            if profile.average_latency > 5000:
                recommendations["warnings"].append({
                    "provider": name,
                    "issue": "High latency",
                    "latency": profile.average_latency,
                    "suggestion": "Consider reducing usage or checking network"
                })
            
            # Check for capacity issues
            if profile.current_load >= profile.max_concurrent * 0.8:
                recommendations["actions"].append({
                    "provider": name,
                    "issue": "High load",
                    "load": f"{profile.current_load}/{profile.max_concurrent}",
                    "suggestion": "Consider increasing concurrent limits or load balancing"
                })
            
            # Optimization suggestions
            if profile.success_rate > 95 and profile.average_latency < 2000:
                recommendations["optimizations"].append({
                    "provider": name,
                    "opportunity": "Excellent performance - consider increasing usage",
                    "metrics": {
                        "success_rate": profile.success_rate,
                        "latency": profile.average_latency
                    }
                })
        
        return recommendations

# Global health monitor instance
_health_monitor = None

def get_health_monitor() -> ProviderHealthMonitor:
    """Get or create the global health monitor."""
    global _health_monitor
    if _health_monitor is None:
        _health_monitor = ProviderHealthMonitor()
    return _health_monitor

def start_health_monitoring():
    """Start the global health monitoring system."""
    monitor = get_health_monitor()
    monitor.start_monitoring()

def stop_health_monitoring():
    """Stop the global health monitoring system."""
    monitor = get_health_monitor()
    monitor.stop_monitoring()

def select_best_provider(message_priority: str = "normal", capability: str = None) -> Optional[str]:
    """Select the best provider for a request."""
    monitor = get_health_monitor()
    
    # Convert capability string to enum if provided
    preferred_capability = None
    if capability:
        try:
            preferred_capability = ProviderCapability(capability)
        except ValueError:
            pass
    
    return monitor.select_provider(message_priority, preferred_capability)

def get_provider_health_status() -> Dict[str, Any]:
    """Get comprehensive provider health status."""
    monitor = get_health_monitor()
    return monitor.get_monitoring_status()

import random  # Add missing import

if __name__ == "__main__":
    # Test the health monitoring system
    import sys
    
    if "--test" in sys.argv:
        print("🏥 Testing Provider Health Monitor")
        print("=" * 50)
        
        # Create and start monitor
        monitor = get_health_monitor()
        monitor.start_monitoring()
        
        print("✅ Health monitor started")
        
        # Run a few manual checks
        print("\n🔍 Running initial health checks...")
        monitor._run_health_checks()
        
        # Display results
        status = monitor.get_monitoring_status()
        print(f"\n📊 Provider Status:")
        for provider, info in status["providers"].items():
            print(f"  {provider}: Health={info['health_score']:.1f}, Success={info['success_rate']:.1f}%, Available={info['is_available']}")
        
        # Test provider selection
        print(f"\n🎯 Testing provider selection:")
        for i in range(5):
            selected = monitor.select_provider("normal")
            print(f"  Selection {i+1}: {selected}")
            if selected:
                monitor.release_provider(selected)
        
        # Show recommendations
        recommendations = monitor.get_provider_recommendations()
        if recommendations["warnings"] or recommendations["actions"]:
            print(f"\n⚠️  Recommendations:")
            for warning in recommendations["warnings"]:
                print(f"  Warning: {warning['provider']} - {warning['issue']}")
            for action in recommendations["actions"]:
                print(f"  Action: {action['provider']} - {action['issue']}")
        
        # Cleanup
        monitor.stop_monitoring()
        print("\n✅ Health monitor stopped")
    
    else:
        print("Provider Health Monitor - Phase 3.3.2")
        print("Usage: python provider_health_monitor.py --test")