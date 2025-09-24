#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "python-dotenv>=1.0.0",
# ]
# ///

"""
TTS Performance Monitor

Tracks and reports performance metrics for both SimpleTTSQueue and complex queue systems.
Provides real-time monitoring and historical analysis.
"""

import json
import os
import time
import statistics
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict

@dataclass
class PerformanceMetric:
    """Single performance measurement."""
    timestamp: float
    queue_type: str  # "simple" or "complex"
    operation: str   # "add_message", "process_message", "route_request"
    duration_ms: float
    success: bool
    message_length: int
    priority: str
    error_message: Optional[str] = None

class PerformanceMonitor:
    """Monitors and tracks TTS queue performance."""
    
    def __init__(self, log_file: Path = None):
        """Initialize performance monitor."""
        self.log_file = log_file or Path("/tmp/tts_performance.jsonl")
        self.session_metrics: List[PerformanceMetric] = []
        self.enabled = os.getenv("TTS_PERFORMANCE_MONITORING", "true").lower() == "true"
        
        # Performance thresholds
        self.thresholds = {
            "latency_ms": 1.0,      # <1ms target
            "success_rate": 99.9,   # >99.9% success rate
            "error_rate": 0.1,      # <0.1% error rate
        }
    
    def record_metric(self, queue_type: str, operation: str, duration_ms: float, 
                     success: bool, message_length: int, priority: str = "medium",
                     error_message: Optional[str] = None):
        """Record a performance metric."""
        if not self.enabled:
            return
        
        metric = PerformanceMetric(
            timestamp=time.time(),
            queue_type=queue_type,
            operation=operation,
            duration_ms=duration_ms,
            success=success,
            message_length=message_length,
            priority=priority,
            error_message=error_message
        )
        
        # Add to session metrics
        self.session_metrics.append(metric)
        
        # Append to log file
        try:
            with open(self.log_file, "a") as f:
                json.dump(asdict(metric), f)
                f.write("\n")
        except Exception as e:
            # Don't fail on logging errors
            pass
    
    def get_session_stats(self) -> Dict[str, Any]:
        """Get statistics for current session."""
        if not self.session_metrics:
            return {"error": "No metrics collected"}
        
        # Separate by queue type
        simple_metrics = [m for m in self.session_metrics if m.queue_type == "simple"]
        complex_metrics = [m for m in self.session_metrics if m.queue_type == "complex"]
        
        stats = {
            "session_start": min(m.timestamp for m in self.session_metrics),
            "session_duration_seconds": time.time() - min(m.timestamp for m in self.session_metrics),
            "total_operations": len(self.session_metrics),
        }
        
        # Simple queue stats
        if simple_metrics:
            durations = [m.duration_ms for m in simple_metrics]
            successes = [m.success for m in simple_metrics]
            
            stats["simple_queue"] = {
                "operations": len(simple_metrics),
                "avg_latency_ms": statistics.mean(durations),
                "min_latency_ms": min(durations),
                "max_latency_ms": max(durations),
                "median_latency_ms": statistics.median(durations),
                "success_rate": sum(successes) / len(successes) * 100,
                "error_rate": (len(successes) - sum(successes)) / len(successes) * 100,
                "throughput_ops_per_sec": len(simple_metrics) / (time.time() - min(m.timestamp for m in simple_metrics)) if len(simple_metrics) > 1 else 0
            }
        
        # Complex queue stats
        if complex_metrics:
            durations = [m.duration_ms for m in complex_metrics]
            successes = [m.success for m in complex_metrics]
            
            stats["complex_queue"] = {
                "operations": len(complex_metrics),
                "avg_latency_ms": statistics.mean(durations),
                "min_latency_ms": min(durations),
                "max_latency_ms": max(durations),
                "median_latency_ms": statistics.median(durations),
                "success_rate": sum(successes) / len(successes) * 100,
                "error_rate": (len(successes) - sum(successes)) / len(successes) * 100,
                "throughput_ops_per_sec": len(complex_metrics) / (time.time() - min(m.timestamp for m in complex_metrics)) if len(complex_metrics) > 1 else 0
            }
        
        # Performance comparison
        if simple_metrics and complex_metrics:
            simple_avg = statistics.mean([m.duration_ms for m in simple_metrics])
            complex_avg = statistics.mean([m.duration_ms for m in complex_metrics])
            stats["performance_improvement"] = complex_avg / simple_avg if simple_avg > 0 else 0
        
        return stats
    
    def check_thresholds(self) -> Dict[str, Any]:
        """Check if current performance meets thresholds."""
        stats = self.get_session_stats()
        results = {"overall_status": "PASS", "checks": []}
        
        # Check simple queue performance if available
        if "simple_queue" in stats:
            simple_stats = stats["simple_queue"]
            
            # Latency check
            latency_pass = simple_stats["avg_latency_ms"] < self.thresholds["latency_ms"]
            results["checks"].append({
                "metric": "simple_queue_latency",
                "target": f"<{self.thresholds['latency_ms']}ms",
                "actual": f"{simple_stats['avg_latency_ms']:.3f}ms",
                "status": "PASS" if latency_pass else "FAIL"
            })
            
            # Success rate check
            success_pass = simple_stats["success_rate"] >= self.thresholds["success_rate"]
            results["checks"].append({
                "metric": "simple_queue_success_rate",
                "target": f"≥{self.thresholds['success_rate']}%",
                "actual": f"{simple_stats['success_rate']:.1f}%",
                "status": "PASS" if success_pass else "FAIL"
            })
            
            # Error rate check
            error_pass = simple_stats["error_rate"] <= self.thresholds["error_rate"]
            results["checks"].append({
                "metric": "simple_queue_error_rate",
                "target": f"≤{self.thresholds['error_rate']}%",
                "actual": f"{simple_stats['error_rate']:.1f}%",
                "status": "PASS" if error_pass else "FAIL"
            })
            
            if not (latency_pass and success_pass and error_pass):
                results["overall_status"] = "FAIL"
        
        return results
    
    def load_historical_data(self, hours: int = 24) -> List[PerformanceMetric]:
        """Load historical performance data."""
        if not self.log_file.exists():
            return []
        
        cutoff_time = time.time() - (hours * 3600)
        metrics = []
        
        try:
            with open(self.log_file, "r") as f:
                for line in f:
                    try:
                        data = json.loads(line.strip())
                        if data["timestamp"] >= cutoff_time:
                            metric = PerformanceMetric(**data)
                            metrics.append(metric)
                    except (json.JSONDecodeError, KeyError, TypeError):
                        continue
        except Exception:
            return []
        
        return metrics
    
    def generate_report(self, hours: int = 24) -> str:
        """Generate a performance report."""
        historical_data = self.load_historical_data(hours)
        session_stats = self.get_session_stats()
        threshold_checks = self.check_thresholds()
        
        report = f"""
TTS Performance Monitor Report
=====================================
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Period: Last {hours} hours

Current Session Statistics:
--------------------------
"""
        
        if "error" not in session_stats:
            if "simple_queue" in session_stats:
                simple = session_stats["simple_queue"]
                report += f"""
SimpleTTSQueue Performance:
  Operations: {simple['operations']}
  Average Latency: {simple['avg_latency_ms']:.3f}ms
  Median Latency: {simple['median_latency_ms']:.3f}ms
  Min/Max Latency: {simple['min_latency_ms']:.3f}ms / {simple['max_latency_ms']:.3f}ms
  Success Rate: {simple['success_rate']:.1f}%
  Error Rate: {simple['error_rate']:.1f}%
  Throughput: {simple['throughput_ops_per_sec']:.1f} ops/sec
"""
            
            if "complex_queue" in session_stats:
                complex = session_stats["complex_queue"]
                report += f"""
Complex Queue Performance:
  Operations: {complex['operations']}
  Average Latency: {complex['avg_latency_ms']:.3f}ms
  Median Latency: {complex['median_latency_ms']:.3f}ms
  Min/Max Latency: {complex['min_latency_ms']:.3f}ms / {complex['max_latency_ms']:.3f}ms
  Success Rate: {complex['success_rate']:.1f}%
  Error Rate: {complex['error_rate']:.1f}%
  Throughput: {complex['throughput_ops_per_sec']:.1f} ops/sec
"""
            
            if "performance_improvement" in session_stats:
                report += f"""
Performance Comparison:
  SimpleTTSQueue is {session_stats['performance_improvement']:.1f}x faster than complex queue
"""
        else:
            report += "  No session data available\n"
        
        # Threshold checks
        report += f"""
Threshold Checks:
-----------------
Overall Status: {threshold_checks['overall_status']}

"""
        
        for check in threshold_checks['checks']:
            status_symbol = "✓" if check['status'] == "PASS" else "✗"
            report += f"{status_symbol} {check['metric']}: {check['actual']} (target: {check['target']})\n"
        
        # Historical data summary
        if historical_data:
            simple_historical = [m for m in historical_data if m.queue_type == "simple"]
            complex_historical = [m for m in historical_data if m.queue_type == "complex"]
            
            report += f"""
Historical Data ({hours} hours):
-------------------------------
Total Operations: {len(historical_data)}
SimpleTTSQueue Operations: {len(simple_historical)}
Complex Queue Operations: {len(complex_historical)}
"""
            
            if simple_historical:
                durations = [m.duration_ms for m in simple_historical]
                successes = [m.success for m in simple_historical]
                report += f"""
SimpleTTSQueue Historical Performance:
  Average Latency: {statistics.mean(durations):.3f}ms
  Success Rate: {sum(successes) / len(successes) * 100:.1f}%
"""
        else:
            report += "\nNo historical data available\n"
        
        return report

# Global performance monitor instance
_monitor = PerformanceMonitor()

def record_performance(queue_type: str, operation: str, duration_ms: float, 
                      success: bool, message_length: int, priority: str = "medium",
                      error_message: Optional[str] = None):
    """Record a performance metric (global function for easy import)."""
    _monitor.record_metric(queue_type, operation, duration_ms, success, 
                          message_length, priority, error_message)

def get_monitor() -> PerformanceMonitor:
    """Get the global performance monitor instance."""
    return _monitor

def main():
    """CLI interface for performance monitoring."""
    import argparse
    
    parser = argparse.ArgumentParser(description="TTS Performance Monitor")
    parser.add_argument("--report", action="store_true", help="Generate performance report")
    parser.add_argument("--check", action="store_true", help="Check performance thresholds")
    parser.add_argument("--session", action="store_true", help="Show current session stats")
    parser.add_argument("--hours", type=int, default=24, help="Hours of historical data to include")
    parser.add_argument("--clear", action="store_true", help="Clear historical data")
    
    args = parser.parse_args()
    
    monitor = get_monitor()
    
    if args.clear:
        if monitor.log_file.exists():
            monitor.log_file.unlink()
            print("Performance data cleared")
        else:
            print("No performance data to clear")
    
    elif args.report:
        print(monitor.generate_report(args.hours))
    
    elif args.check:
        checks = monitor.check_thresholds()
        print(f"Performance Status: {checks['overall_status']}")
        for check in checks['checks']:
            status_symbol = "✓" if check['status'] == "PASS" else "✗"
            print(f"{status_symbol} {check['metric']}: {check['actual']} (target: {check['target']})")
    
    elif args.session:
        stats = monitor.get_session_stats()
        print(json.dumps(stats, indent=2))
    
    else:
        print("Use --help for available options")

if __name__ == "__main__":
    main()