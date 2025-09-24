#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "python-dotenv>=1.0.0",
# ]
# ///

"""
Phase 3.4.1 Performance Metrics and Analytics System
Comprehensive performance monitoring for Phase 3 TTS optimization infrastructure.

Features:
- Real-time performance metrics collection
- Cache analytics and efficiency monitoring
- Latency percentile tracking (P50, P90, P95, P99)
- Memory usage optimization monitoring
- Provider performance analytics
- Historical trend analysis and predictions
- Performance regression detection
- Automated optimization recommendations
"""

import asyncio
import json
import os
import psutil
import statistics
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple, Callable
from dotenv import load_dotenv

# Load environment variables
env_path = Path.home() / "brainpods" / ".env"
if env_path.exists():
    load_dotenv(env_path)

# Import cache manager
try:
    try:
        from .phase3_cache_manager import get_cache_manager
    except ImportError:
        from phase3_cache_manager import get_cache_manager
    CACHE_MANAGER_AVAILABLE = True
except ImportError:
    CACHE_MANAGER_AVAILABLE = False

class MetricType(Enum):
    """Types of performance metrics."""
    LATENCY = "latency"
    THROUGHPUT = "throughput"
    ERROR_RATE = "error_rate"
    CACHE_HIT_RATE = "cache_hit_rate"
    MEMORY_USAGE = "memory_usage"
    CPU_USAGE = "cpu_usage"
    PROVIDER_HEALTH = "provider_health"
    QUEUE_SIZE = "queue_size"

class PerformanceLevel(Enum):
    """Performance level classifications."""
    EXCELLENT = "excellent"    # Top 10% performance
    GOOD = "good"             # Above average performance
    AVERAGE = "average"       # Baseline performance
    POOR = "poor"            # Below average performance
    CRITICAL = "critical"     # Performance degradation requiring attention

@dataclass
class PerformanceMetric:
    """Single performance metric data point."""
    metric_type: MetricType
    value: float
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Validate metric data."""
        if self.value < 0:
            raise ValueError(f"Metric value cannot be negative: {self.value}")

@dataclass
class PerformanceSnapshot:
    """Comprehensive performance snapshot."""
    timestamp: float = field(default_factory=time.time)
    
    # Latency metrics (milliseconds)
    avg_latency_ms: float = 0.0
    p50_latency_ms: float = 0.0
    p90_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0
    
    # Throughput metrics
    requests_per_second: float = 0.0
    messages_processed: int = 0
    
    # Cache metrics
    cache_hit_rate: float = 0.0
    cache_memory_mb: float = 0.0
    cache_efficiency_score: float = 0.0
    
    # System metrics
    memory_usage_mb: float = 0.0
    cpu_usage_percent: float = 0.0
    
    # Error metrics
    error_rate: float = 0.0
    timeout_rate: float = 0.0
    
    # Performance level
    overall_performance_level: PerformanceLevel = PerformanceLevel.AVERAGE
    performance_score: float = 0.0  # 0.0 to 1.0
    
    def __post_init__(self):
        """Calculate overall performance score."""
        self.performance_score = self._calculate_performance_score()
        self.overall_performance_level = self._determine_performance_level()
    
    def _calculate_performance_score(self) -> float:
        """Calculate composite performance score."""
        # Performance scoring weights
        latency_score = max(0, 1.0 - (self.avg_latency_ms / 1000))  # Target: <1s
        throughput_score = min(1.0, self.requests_per_second / 100)  # Target: 100 RPS
        cache_score = self.cache_hit_rate  # Already 0-1
        error_score = max(0, 1.0 - self.error_rate)  # Lower error rate is better
        
        # Weighted composite score
        score = (
            latency_score * 0.35 +      # 35% weight on latency
            throughput_score * 0.25 +   # 25% weight on throughput
            cache_score * 0.20 +        # 20% weight on cache efficiency
            error_score * 0.20          # 20% weight on error rate
        )
        
        return max(0.0, min(1.0, score))
    
    def _determine_performance_level(self) -> PerformanceLevel:
        """Determine performance level from score."""
        if self.performance_score >= 0.9:
            return PerformanceLevel.EXCELLENT
        elif self.performance_score >= 0.7:
            return PerformanceLevel.GOOD
        elif self.performance_score >= 0.5:
            return PerformanceLevel.AVERAGE
        elif self.performance_score >= 0.3:
            return PerformanceLevel.POOR
        else:
            return PerformanceLevel.CRITICAL

@dataclass
class PerformanceTrend:
    """Performance trend analysis."""
    metric_type: MetricType
    trend_direction: str  # "improving", "stable", "degrading"
    trend_magnitude: float  # Rate of change
    confidence: float  # 0.0 to 1.0
    prediction_window_minutes: int
    predicted_value: Optional[float] = None

class PerformanceAnalyzer:
    """Advanced performance analysis and trend prediction."""
    
    def __init__(self, history_size: int = 1000):
        """
        Initialize performance analyzer.
        
        Args:
            history_size: Number of historical data points to maintain
        """
        self.history_size = history_size
        self.metrics_history: Dict[MetricType, deque] = defaultdict(
            lambda: deque(maxlen=history_size)
        )
        self.trend_cache: Dict[MetricType, PerformanceTrend] = {}
    
    def add_metric(self, metric: PerformanceMetric):
        """Add performance metric to history."""
        self.metrics_history[metric.metric_type].append(metric)
        
        # Invalidate trend cache for this metric type
        if metric.metric_type in self.trend_cache:
            del self.trend_cache[metric.metric_type]
    
    def analyze_trend(self, metric_type: MetricType, 
                     window_minutes: int = 30) -> PerformanceTrend:
        """
        Analyze performance trend for a metric type.
        
        Args:
            metric_type: Type of metric to analyze
            window_minutes: Analysis window in minutes
            
        Returns:
            Performance trend analysis
        """
        if metric_type in self.trend_cache:
            return self.trend_cache[metric_type]
        
        history = self.metrics_history[metric_type]
        
        if len(history) < 5:
            # Not enough data for trend analysis
            trend = PerformanceTrend(
                metric_type=metric_type,
                trend_direction="unknown",
                trend_magnitude=0.0,
                confidence=0.0,
                prediction_window_minutes=window_minutes
            )
            self.trend_cache[metric_type] = trend
            return trend
        
        # Filter recent data within window
        cutoff_time = time.time() - (window_minutes * 60)
        recent_metrics = [m for m in history if m.timestamp >= cutoff_time]
        
        if len(recent_metrics) < 3:
            # Not enough recent data
            trend = PerformanceTrend(
                metric_type=metric_type,
                trend_direction="insufficient_data",
                trend_magnitude=0.0,
                confidence=0.0,
                prediction_window_minutes=window_minutes
            )
            self.trend_cache[metric_type] = trend
            return trend
        
        # Calculate trend
        values = [m.value for m in recent_metrics]
        timestamps = [m.timestamp for m in recent_metrics]
        
        trend_magnitude = self._calculate_trend_slope(timestamps, values)
        confidence = min(1.0, len(recent_metrics) / 20.0)  # More data = higher confidence
        
        # Determine trend direction
        if abs(trend_magnitude) < 0.01:  # Threshold for stability
            trend_direction = "stable"
        elif trend_magnitude > 0:
            trend_direction = "increasing"  # May be good or bad depending on metric
        else:
            trend_direction = "decreasing"
        
        # Make prediction
        if len(values) > 1:
            predicted_value = values[-1] + (trend_magnitude * window_minutes)
        else:
            predicted_value = None
        
        trend = PerformanceTrend(
            metric_type=metric_type,
            trend_direction=trend_direction,
            trend_magnitude=trend_magnitude,
            confidence=confidence,
            prediction_window_minutes=window_minutes,
            predicted_value=predicted_value
        )
        
        self.trend_cache[metric_type] = trend
        return trend
    
    def _calculate_trend_slope(self, timestamps: List[float], values: List[float]) -> float:
        """Calculate trend slope using linear regression."""
        if len(timestamps) < 2:
            return 0.0
        
        n = len(timestamps)
        
        # Normalize timestamps to start from 0
        min_time = min(timestamps)
        x = [(t - min_time) / 60 for t in timestamps]  # Convert to minutes
        y = values
        
        # Calculate linear regression slope
        x_mean = sum(x) / n
        y_mean = sum(y) / n
        
        numerator = sum((x[i] - x_mean) * (y[i] - y_mean) for i in range(n))
        denominator = sum((x[i] - x_mean) ** 2 for i in range(n))
        
        if denominator == 0:
            return 0.0
        
        return numerator / denominator
    
    def get_percentiles(self, metric_type: MetricType, 
                       window_minutes: int = 60) -> Dict[str, float]:
        """
        Calculate performance percentiles for a metric.
        
        Args:
            metric_type: Type of metric
            window_minutes: Analysis window
            
        Returns:
            Dictionary of percentiles (P50, P90, P95, P99)
        """
        history = self.metrics_history[metric_type]
        
        # Filter recent data
        cutoff_time = time.time() - (window_minutes * 60)
        recent_values = [m.value for m in history if m.timestamp >= cutoff_time]
        
        if not recent_values:
            return {
                "p50": 0.0,
                "p90": 0.0, 
                "p95": 0.0,
                "p99": 0.0
            }
        
        sorted_values = sorted(recent_values)
        
        return {
            "p50": self._percentile(sorted_values, 50),
            "p90": self._percentile(sorted_values, 90),
            "p95": self._percentile(sorted_values, 95),
            "p99": self._percentile(sorted_values, 99)
        }
    
    def _percentile(self, sorted_values: List[float], percentile: float) -> float:
        """Calculate percentile value."""
        if not sorted_values:
            return 0.0
        
        k = (len(sorted_values) - 1) * percentile / 100
        f = int(k)
        c = k - f
        
        if f + 1 < len(sorted_values):
            return sorted_values[f] * (1 - c) + sorted_values[f + 1] * c
        else:
            return sorted_values[f]

class Phase3PerformanceMonitor:
    """
    Comprehensive performance monitoring system for Phase 3 TTS infrastructure.
    
    Features:
    - Real-time metrics collection and analysis
    - Performance trend prediction and regression detection
    - Cache efficiency monitoring and optimization recommendations
    - System resource utilization tracking
    - Automated performance alerts and recommendations
    """
    
    def __init__(self):
        """Initialize the performance monitor."""
        self.cache_manager = get_cache_manager() if CACHE_MANAGER_AVAILABLE else None
        self.analyzer = PerformanceAnalyzer()
        
        # Performance data
        self.current_snapshot: Optional[PerformanceSnapshot] = None
        self.snapshot_history = deque(maxlen=1440)  # 24 hours of minute-level snapshots
        
        # Monitoring configuration
        self.snapshot_interval = float(os.getenv("PERF_SNAPSHOT_INTERVAL", "60"))  # 60 seconds
        self.alert_thresholds = {
            MetricType.LATENCY: 1000.0,        # 1s max latency
            MetricType.ERROR_RATE: 0.05,       # 5% max error rate
            MetricType.CACHE_HIT_RATE: 0.8,    # 80% min hit rate
            MetricType.MEMORY_USAGE: 1024.0,   # 1GB max memory
            MetricType.CPU_USAGE: 80.0         # 80% max CPU
        }
        
        # System monitoring
        self.process = psutil.Process()
        
        # Monitoring state
        self._monitoring_active = True
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()
        
        print("📊 Phase 3 Performance Monitor initialized")
        print(f"  Snapshot interval: {self.snapshot_interval}s")
        print(f"  Cache manager: {'✅' if self.cache_manager else '❌'}")
    
    def record_latency(self, latency_ms: float, operation: str = "tts_request"):
        """Record latency metric."""
        metric = PerformanceMetric(
            metric_type=MetricType.LATENCY,
            value=latency_ms,
            metadata={"operation": operation}
        )
        self.analyzer.add_metric(metric)
    
    def record_throughput(self, requests_per_second: float):
        """Record throughput metric."""
        metric = PerformanceMetric(
            metric_type=MetricType.THROUGHPUT,
            value=requests_per_second
        )
        self.analyzer.add_metric(metric)
    
    def record_error_rate(self, error_rate: float):
        """Record error rate metric."""
        metric = PerformanceMetric(
            metric_type=MetricType.ERROR_RATE,
            value=error_rate
        )
        self.analyzer.add_metric(metric)
    
    def get_current_snapshot(self) -> PerformanceSnapshot:
        """Get current performance snapshot."""
        if self.current_snapshot is None:
            self.current_snapshot = self._create_snapshot()
        return self.current_snapshot
    
    def get_performance_trends(self) -> Dict[str, PerformanceTrend]:
        """Get performance trends for all metric types."""
        trends = {}
        for metric_type in MetricType:
            trend = self.analyzer.analyze_trend(metric_type)
            trends[metric_type.value] = trend
        return trends
    
    def get_performance_report(self) -> Dict[str, Any]:
        """Generate comprehensive performance report."""
        current = self.get_current_snapshot()
        trends = self.get_performance_trends()
        
        # Calculate cache statistics
        cache_stats = {}
        if self.cache_manager:
            global_stats = self.cache_manager.get_global_stats()
            cache_stats = {
                "global_hit_rate": global_stats["global"]["global_hit_rate"],
                "total_memory_mb": global_stats["global"]["total_memory_mb"],
                "layers": {
                    name: {
                        "hit_rate": layer["hit_rate"],
                        "size": layer["size"],
                        "memory_mb": layer["memory_usage_mb"]
                    }
                    for name, layer in global_stats["layers"].items()
                }
            }
        
        # Performance recommendations
        recommendations = self._generate_recommendations(current, trends)
        
        # Alert status
        alerts = self._check_performance_alerts(current)
        
        report = {
            "timestamp": current.timestamp,
            "performance_snapshot": {
                "overall_score": current.performance_score,
                "performance_level": current.overall_performance_level.value,
                "latency": {
                    "avg_ms": current.avg_latency_ms,
                    "p95_ms": current.p95_latency_ms,
                    "p99_ms": current.p99_latency_ms
                },
                "throughput": {
                    "requests_per_second": current.requests_per_second,
                    "messages_processed": current.messages_processed
                },
                "cache": {
                    "hit_rate": current.cache_hit_rate,
                    "memory_mb": current.cache_memory_mb,
                    "efficiency_score": current.cache_efficiency_score
                },
                "system": {
                    "memory_mb": current.memory_usage_mb,
                    "cpu_percent": current.cpu_usage_percent
                },
                "errors": {
                    "error_rate": current.error_rate,
                    "timeout_rate": current.timeout_rate
                }
            },
            "trends": {
                metric: {
                    "direction": trend.trend_direction,
                    "magnitude": trend.trend_magnitude,
                    "confidence": trend.confidence,
                    "predicted_value": trend.predicted_value
                }
                for metric, trend in trends.items()
            },
            "cache_statistics": cache_stats,
            "recommendations": recommendations,
            "alerts": alerts,
            "monitoring_config": {
                "snapshot_interval": self.snapshot_interval,
                "alert_thresholds": {k.value: v for k, v in self.alert_thresholds.items()}
            }
        }
        
        return report
    
    def _create_snapshot(self) -> PerformanceSnapshot:
        """Create current performance snapshot."""
        # Get latency percentiles
        latency_percentiles = self.analyzer.get_percentiles(MetricType.LATENCY)
        
        # Calculate averages from recent metrics
        recent_throughput = self._get_recent_average(MetricType.THROUGHPUT, 300)  # 5 minutes
        recent_errors = self._get_recent_average(MetricType.ERROR_RATE, 300)
        
        # Get cache statistics
        cache_hit_rate = 0.0
        cache_memory_mb = 0.0
        cache_efficiency = 0.0
        
        if self.cache_manager:
            stats = self.cache_manager.get_global_stats()
            cache_hit_rate = stats["global"]["global_hit_rate"]
            cache_memory_mb = stats["global"]["total_memory_mb"]
            cache_efficiency = min(1.0, cache_hit_rate * 1.2)  # Efficiency factor
        
        # Get system metrics
        memory_info = self.process.memory_info()
        memory_mb = memory_info.rss / 1024 / 1024  # Convert to MB
        cpu_percent = self.process.cpu_percent()
        
        # Create snapshot
        snapshot = PerformanceSnapshot(
            avg_latency_ms=self._get_recent_average(MetricType.LATENCY, 300),
            p50_latency_ms=latency_percentiles["p50"],
            p90_latency_ms=latency_percentiles["p90"],
            p95_latency_ms=latency_percentiles["p95"],
            p99_latency_ms=latency_percentiles["p99"],
            requests_per_second=recent_throughput,
            messages_processed=len(self.analyzer.metrics_history[MetricType.THROUGHPUT]),
            cache_hit_rate=cache_hit_rate,
            cache_memory_mb=cache_memory_mb,
            cache_efficiency_score=cache_efficiency,
            memory_usage_mb=memory_mb,
            cpu_usage_percent=cpu_percent,
            error_rate=recent_errors,
            timeout_rate=self._get_recent_average(MetricType.ERROR_RATE, 300, lambda m: m.metadata.get("timeout", False))
        )
        
        return snapshot
    
    def _get_recent_average(self, metric_type: MetricType, window_seconds: int, 
                          filter_func: Optional[Callable] = None) -> float:
        """Get average value for recent metrics."""
        history = self.analyzer.metrics_history[metric_type]
        cutoff_time = time.time() - window_seconds
        
        recent_metrics = [m for m in history if m.timestamp >= cutoff_time]
        
        if filter_func:
            recent_metrics = [m for m in recent_metrics if filter_func(m)]
        
        if not recent_metrics:
            return 0.0
        
        return sum(m.value for m in recent_metrics) / len(recent_metrics)
    
    def _generate_recommendations(self, snapshot: PerformanceSnapshot, 
                                trends: Dict[str, PerformanceTrend]) -> List[str]:
        """Generate performance optimization recommendations."""
        recommendations = []
        
        # Latency recommendations
        if snapshot.avg_latency_ms > 500:
            recommendations.append("High latency detected. Consider enabling provider health caching.")
        
        if snapshot.p99_latency_ms > 2000:
            recommendations.append("P99 latency is high. Implement request timeout optimization.")
        
        # Cache recommendations
        if snapshot.cache_hit_rate < 0.8:
            recommendations.append(f"Cache hit rate is {snapshot.cache_hit_rate:.1%}. Review cache TTL settings.")
        
        # Memory recommendations
        if snapshot.memory_usage_mb > 512:
            recommendations.append("High memory usage. Consider implementing memory pool optimization.")
        
        # Trend-based recommendations
        latency_trend = trends.get("latency")
        if latency_trend and latency_trend.trend_direction == "increasing" and latency_trend.confidence > 0.7:
            recommendations.append("Latency trend is increasing. Monitor for performance regression.")
        
        error_trend = trends.get("error_rate")
        if error_trend and error_trend.trend_direction == "increasing" and error_trend.confidence > 0.5:
            recommendations.append("Error rate trend is increasing. Check provider health status.")
        
        return recommendations
    
    def _check_performance_alerts(self, snapshot: PerformanceSnapshot) -> List[Dict[str, Any]]:
        """Check for performance alerts."""
        alerts = []
        
        # Latency alert
        if snapshot.avg_latency_ms > self.alert_thresholds[MetricType.LATENCY]:
            alerts.append({
                "type": "latency",
                "level": "warning",
                "message": f"Average latency {snapshot.avg_latency_ms:.1f}ms exceeds threshold {self.alert_thresholds[MetricType.LATENCY]}ms",
                "value": snapshot.avg_latency_ms,
                "threshold": self.alert_thresholds[MetricType.LATENCY]
            })
        
        # Error rate alert
        if snapshot.error_rate > self.alert_thresholds[MetricType.ERROR_RATE]:
            alerts.append({
                "type": "error_rate",
                "level": "error",
                "message": f"Error rate {snapshot.error_rate:.1%} exceeds threshold {self.alert_thresholds[MetricType.ERROR_RATE]:.1%}",
                "value": snapshot.error_rate,
                "threshold": self.alert_thresholds[MetricType.ERROR_RATE]
            })
        
        # Cache hit rate alert
        if snapshot.cache_hit_rate < self.alert_thresholds[MetricType.CACHE_HIT_RATE]:
            alerts.append({
                "type": "cache_hit_rate",
                "level": "warning",
                "message": f"Cache hit rate {snapshot.cache_hit_rate:.1%} below threshold {self.alert_thresholds[MetricType.CACHE_HIT_RATE]:.1%}",
                "value": snapshot.cache_hit_rate,
                "threshold": self.alert_thresholds[MetricType.CACHE_HIT_RATE]
            })
        
        return alerts
    
    def _monitor_loop(self):
        """Background monitoring loop."""
        print("🔄 Performance monitoring started")
        
        while self._monitoring_active:
            try:
                # Create new snapshot
                self.current_snapshot = self._create_snapshot()
                self.snapshot_history.append(self.current_snapshot)
                
                # Sleep until next snapshot
                time.sleep(self.snapshot_interval)
                
            except Exception as e:
                print(f"⚠️ Performance monitoring error: {e}")
                time.sleep(5)  # Brief pause on error
    
    def shutdown(self):
        """Shutdown the performance monitor."""
        self._monitoring_active = False
        print("🛑 Performance monitor shutdown")

# Global performance monitor instance
_performance_monitor = None

def get_performance_monitor() -> Phase3PerformanceMonitor:
    """Get or create the global performance monitor."""
    global _performance_monitor
    if _performance_monitor is None:
        _performance_monitor = Phase3PerformanceMonitor()
    return _performance_monitor

def measure_performance(operation: str = "tts_request"):
    """
    Decorator for measuring operation performance.
    
    Args:
        operation: Name of the operation being measured
        
    Returns:
        Decorated function with performance measurement
    """
    def decorator(func: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            monitor = get_performance_monitor()
            
            start_time = time.time()
            
            try:
                result = func(*args, **kwargs)
                
                # Record successful operation
                latency_ms = (time.time() - start_time) * 1000
                monitor.record_latency(latency_ms, operation)
                
                return result
                
            except Exception as e:
                # Record error
                latency_ms = (time.time() - start_time) * 1000
                monitor.record_latency(latency_ms, operation)
                monitor.record_error_rate(1.0)  # Single error event
                
                raise e
        
        return wrapper
    return decorator

if __name__ == "__main__":
    import sys
    
    if "--test" in sys.argv:
        print("🧪 Testing Phase 3.4.1 Performance Metrics System")
        print("=" * 60)
        
        monitor = get_performance_monitor()
        
        print("\n📊 Testing Performance Metrics Collection:")
        
        # Simulate some performance data
        import random
        
        for i in range(20):
            # Simulate varying latencies
            latency = random.uniform(50, 300)
            monitor.record_latency(latency, "test_operation")
            
            # Simulate throughput
            throughput = random.uniform(5, 15)
            monitor.record_throughput(throughput)
            
            # Simulate occasional errors
            if random.random() < 0.1:  # 10% error rate
                monitor.record_error_rate(1.0)
            
            time.sleep(0.1)  # Brief pause
        
        print("  ✅ Recorded 20 performance data points")
        
        # Test performance snapshot
        print("\n📈 Testing Performance Snapshot:")
        snapshot = monitor.get_current_snapshot()
        
        print(f"  Performance Score: {snapshot.performance_score:.2f}")
        print(f"  Performance Level: {snapshot.overall_performance_level.value}")
        print(f"  Average Latency: {snapshot.avg_latency_ms:.1f}ms")
        print(f"  P95 Latency: {snapshot.p95_latency_ms:.1f}ms")
        print(f"  Cache Hit Rate: {snapshot.cache_hit_rate:.1%}")
        print(f"  Memory Usage: {snapshot.memory_usage_mb:.1f}MB")
        print(f"  Error Rate: {snapshot.error_rate:.1%}")
        
        # Test trend analysis
        print("\n📊 Testing Trend Analysis:")
        trends = monitor.get_performance_trends()
        
        for metric_type, trend in trends.items():
            if trend.confidence > 0:
                print(f"  {metric_type}:")
                print(f"    Trend: {trend.trend_direction}")
                print(f"    Confidence: {trend.confidence:.1%}")
                print(f"    Magnitude: {trend.trend_magnitude:.3f}")
        
        # Test performance decorator
        print("\n🎯 Testing Performance Decorator:")
        
        @measure_performance("decorated_function")
        def test_function(duration: float):
            """Test function with performance measurement."""
            time.sleep(duration)
            return f"Completed in {duration}s"
        
        result1 = test_function(0.1)
        result2 = test_function(0.05)
        print(f"  ✅ Decorated function results: {result1}, {result2}")
        
        # Test comprehensive report
        print("\n📋 Testing Comprehensive Performance Report:")
        report = monitor.get_performance_report()
        
        print(f"  Overall Score: {report['performance_snapshot']['overall_score']:.2f}")
        print(f"  Performance Level: {report['performance_snapshot']['performance_level']}")
        
        print(f"  Latency Metrics:")
        latency = report['performance_snapshot']['latency']
        print(f"    Average: {latency['avg_ms']:.1f}ms")
        print(f"    P95: {latency['p95_ms']:.1f}ms")
        
        if report['recommendations']:
            print(f"  Recommendations:")
            for rec in report['recommendations']:
                print(f"    • {rec}")
        
        if report['alerts']:
            print(f"  Alerts:")
            for alert in report['alerts']:
                print(f"    🚨 {alert['level'].upper()}: {alert['message']}")
        
        print("\n✅ Phase 3.4.1 Performance Metrics System test completed")
        print("📊 Performance monitoring and analytics operational!")
        
        # Cleanup
        monitor.shutdown()
    
    else:
        print("Phase 3.4.1 Performance Metrics and Analytics System")
        print("Comprehensive performance monitoring for Phase 3 TTS optimization")
        print("Usage: python phase3_performance_metrics.py --test")