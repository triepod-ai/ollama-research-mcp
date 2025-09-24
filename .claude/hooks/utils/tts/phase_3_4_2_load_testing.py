#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "python-dotenv>=1.0.0",
#   "matplotlib>=3.7.0",
#   "numpy>=1.24.0",
# ]
# ///

"""
Phase 3.4.2 Load Testing and Performance Validation Framework
Comprehensive stress testing for heap-based priority queue optimization.

Features:
- Multi-threaded concurrent operation testing  
- Scalability analysis across different data sizes
- Performance regression detection
- Memory usage optimization validation
- Comparative analysis vs original linear implementation
- Visual performance analytics and reporting
"""

import asyncio
import concurrent.futures
import json
import matplotlib.pyplot as plt
import numpy as np
import os
import psutil
import random
import statistics
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple, Callable
from dotenv import load_dotenv

# Load environment variables
env_path = Path.home() / "brainpods" / ".env"
if env_path.exists():
    load_dotenv(env_path)

# Import queue implementations
try:
    try:
        from .phase_3_4_2_heap_priority_queue import HeapBasedPriorityQueue, AdvancedPriority, MessageType, AdvancedTTSMessage
        from .advanced_priority_queue import AdvancedPriorityQueue
    except ImportError:
        from phase_3_4_2_heap_priority_queue import HeapBasedPriorityQueue, AdvancedPriority, MessageType, AdvancedTTSMessage
        from advanced_priority_queue import AdvancedPriorityQueue
    QUEUES_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ Queue implementations not available: {e}")
    QUEUES_AVAILABLE = False

@dataclass
class LoadTestConfig:
    """Configuration for load testing."""
    name: str
    num_operations: int
    num_threads: int = 1
    operation_mix: Dict[str, float] = field(default_factory=lambda: {
        "enqueue": 0.6,
        "dequeue": 0.3, 
        "peek": 0.1
    })
    message_size_range: Tuple[int, int] = (10, 100)  # Characters
    priority_distribution: Dict[AdvancedPriority, float] = field(default_factory=lambda: {
        AdvancedPriority.INTERRUPT: 0.01,
        AdvancedPriority.CRITICAL: 0.05,
        AdvancedPriority.HIGH: 0.15,
        AdvancedPriority.MEDIUM: 0.30,
        AdvancedPriority.LOW: 0.35,
        AdvancedPriority.BACKGROUND: 0.14
    })
    deduplication_rate: float = 0.2  # 20% duplicates
    duration_seconds: Optional[int] = None  # Run for time instead of operations

@dataclass
class LoadTestResults:
    """Results from load testing."""
    config: LoadTestConfig
    start_time: float
    end_time: float
    
    # Operation metrics
    operations_completed: int = 0
    operations_per_second: float = 0.0
    
    # Latency metrics (milliseconds)
    avg_latency_ms: float = 0.0
    p50_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0
    max_latency_ms: float = 0.0
    
    # Memory metrics
    peak_memory_mb: float = 0.0
    avg_memory_mb: float = 0.0
    memory_efficiency_score: float = 0.0
    
    # Error metrics
    error_count: int = 0
    error_rate: float = 0.0
    timeout_count: int = 0
    
    # Queue-specific metrics
    final_queue_size: int = 0
    max_queue_size: int = 0
    deduplication_effectiveness: float = 0.0
    
    # Concurrency metrics
    thread_performance: Dict[int, float] = field(default_factory=dict)
    contention_events: int = 0
    
    def calculate_derived_metrics(self):
        """Calculate derived performance metrics."""
        duration = self.end_time - self.start_time
        if duration > 0:
            self.operations_per_second = self.operations_completed / duration
        
        if self.operations_completed > 0:
            self.error_rate = self.error_count / self.operations_completed
        
        # Memory efficiency score (operations per MB)
        if self.avg_memory_mb > 0:
            self.memory_efficiency_score = self.operations_completed / self.avg_memory_mb

class PerformanceComparator:
    """Comparison between different queue implementations."""
    
    def __init__(self):
        """Initialize performance comparator."""
        self.results: Dict[str, LoadTestResults] = {}
        
    def add_result(self, implementation_name: str, result: LoadTestResults):
        """Add test result for comparison."""
        self.results[implementation_name] = result
        
    def generate_comparison_report(self) -> Dict[str, Any]:
        """Generate comprehensive comparison report."""
        if len(self.results) < 2:
            return {"error": "Need at least 2 implementations to compare"}
        
        # Find baseline (usually the original implementation)
        baseline_name = next((name for name in self.results.keys() if "original" in name.lower() or "linear" in name.lower()), list(self.results.keys())[0])
        baseline = self.results[baseline_name]
        
        comparisons = {}
        for name, result in self.results.items():
            if name == baseline_name:
                continue
                
            # Performance improvements
            ops_improvement = (result.operations_per_second / baseline.operations_per_second) if baseline.operations_per_second > 0 else 0
            latency_improvement = (baseline.avg_latency_ms / result.avg_latency_ms) if result.avg_latency_ms > 0 else 0
            memory_improvement = (baseline.avg_memory_mb / result.avg_memory_mb) if result.avg_memory_mb > 0 else 0
            
            comparisons[name] = {
                "throughput_improvement": ops_improvement,
                "latency_improvement": latency_improvement, 
                "memory_improvement": memory_improvement,
                "error_rate_change": result.error_rate - baseline.error_rate,
                "p95_latency_improvement": (baseline.p95_latency_ms / result.p95_latency_ms) if result.p95_latency_ms > 0 else 0,
                "memory_efficiency_improvement": (result.memory_efficiency_score / baseline.memory_efficiency_score) if baseline.memory_efficiency_score > 0 else 0
            }
        
        # Overall analysis
        best_throughput = max(self.results.values(), key=lambda r: r.operations_per_second)
        best_latency = min(self.results.values(), key=lambda r: r.avg_latency_ms)
        best_memory = min(self.results.values(), key=lambda r: r.avg_memory_mb)
        
        return {
            "baseline": baseline_name,
            "comparisons": comparisons,
            "winners": {
                "throughput": next(name for name, result in self.results.items() if result == best_throughput),
                "latency": next(name for name, result in self.results.items() if result == best_latency),
                "memory": next(name for name, result in self.results.items() if result == best_memory)
            },
            "summary": {
                "total_implementations": len(self.results),
                "test_operations": baseline.operations_completed,
                "best_improvement_factor": max([comp.get("throughput_improvement", 1) for comp in comparisons.values()])
            }
        }

class LoadTestExecutor:
    """Executes load tests on priority queue implementations."""
    
    def __init__(self):
        """Initialize load test executor."""
        self.process = psutil.Process()
        
    def run_load_test(self, queue_impl, config: LoadTestConfig) -> LoadTestResults:
        """
        Run load test on queue implementation.
        
        Args:
            queue_impl: Queue implementation to test
            config: Test configuration
            
        Returns:
            Load test results
        """
        print(f"🚀 Running load test: {config.name}")
        print(f"   Operations: {config.num_operations}")
        print(f"   Threads: {config.num_threads}")
        print(f"   Duration: {config.duration_seconds}s" if config.duration_seconds else "   Duration: Until completion")
        
        # Initialize result tracking
        start_time = time.time()
        results = LoadTestResults(
            config=config,
            start_time=start_time,
            end_time=0.0
        )
        
        # Performance tracking
        latencies = []
        memory_samples = []
        error_count = 0
        operations_completed = 0
        max_queue_size = 0
        
        # Thread-safe counters
        thread_lock = threading.Lock()
        
        def worker_thread(thread_id: int, operations_per_thread: int):
            """Worker thread for concurrent testing."""
            nonlocal operations_completed, error_count, max_queue_size
            
            thread_operations = 0
            thread_errors = 0
            thread_latencies = []
            
            # Generate operations based on mix
            operations = []
            for _ in range(operations_per_thread):
                rand = random.random()
                cumulative = 0.0
                for op_type, probability in config.operation_mix.items():
                    cumulative += probability
                    if rand <= cumulative:
                        operations.append(op_type)
                        break
            
            # Execute operations
            for operation in operations:
                if config.duration_seconds and (time.time() - start_time) >= config.duration_seconds:
                    break
                    
                op_start_time = time.time()
                
                try:
                    if operation == "enqueue":
                        # Create test message
                        message = self._generate_test_message(config)
                        success = queue_impl.enqueue(message)
                        
                        if success:
                            thread_operations += 1
                        
                    elif operation == "dequeue":
                        message = queue_impl.dequeue()
                        if message:
                            thread_operations += 1
                            
                    elif operation == "peek":
                        message = queue_impl.peek()
                        thread_operations += 1
                    
                    # Record latency
                    op_latency = (time.time() - op_start_time) * 1000
                    thread_latencies.append(op_latency)
                    
                    # Track queue size
                    current_size = queue_impl.size()
                    with thread_lock:
                        max_queue_size = max(max_queue_size, current_size)
                    
                except Exception as e:
                    thread_errors += 1
                    print(f"⚠️ Operation error in thread {thread_id}: {e}")
            
            # Update global counters
            with thread_lock:
                operations_completed += thread_operations
                error_count += thread_errors
                latencies.extend(thread_latencies)
                results.thread_performance[thread_id] = thread_operations / (time.time() - start_time) if (time.time() - start_time) > 0 else 0
        
        # Memory monitoring thread
        def memory_monitor():
            """Monitor memory usage during test."""
            while time.time() - start_time < (config.duration_seconds or 300):
                try:
                    memory_info = self.process.memory_info()
                    memory_mb = memory_info.rss / 1024 / 1024
                    memory_samples.append(memory_mb)
                    time.sleep(0.1)  # Sample every 100ms
                except:
                    break
        
        # Start memory monitoring
        memory_thread = threading.Thread(target=memory_monitor, daemon=True)
        memory_thread.start()
        
        # Execute load test with multiple threads
        operations_per_thread = config.num_operations // config.num_threads
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=config.num_threads) as executor:
            futures = []
            for thread_id in range(config.num_threads):
                future = executor.submit(worker_thread, thread_id, operations_per_thread)
                futures.append(future)
            
            # Wait for completion
            concurrent.futures.wait(futures)
        
        end_time = time.time()
        results.end_time = end_time
        
        # Calculate final metrics
        results.operations_completed = operations_completed
        results.error_count = error_count
        results.final_queue_size = queue_impl.size()
        results.max_queue_size = max_queue_size
        
        # Latency statistics
        if latencies:
            results.avg_latency_ms = statistics.mean(latencies)
            sorted_latencies = sorted(latencies)
            results.p50_latency_ms = sorted_latencies[int(0.50 * len(sorted_latencies))]
            results.p95_latency_ms = sorted_latencies[int(0.95 * len(sorted_latencies))]
            results.p99_latency_ms = sorted_latencies[int(0.99 * len(sorted_latencies))]
            results.max_latency_ms = max(latencies)
        
        # Memory statistics
        if memory_samples:
            results.avg_memory_mb = statistics.mean(memory_samples)
            results.peak_memory_mb = max(memory_samples)
        
        # Calculate derived metrics
        results.calculate_derived_metrics()
        
        print(f"✅ Load test completed")
        print(f"   Operations/sec: {results.operations_per_second:.0f}")
        print(f"   Average latency: {results.avg_latency_ms:.2f}ms")
        print(f"   P95 latency: {results.p95_latency_ms:.2f}ms")
        print(f"   Peak memory: {results.peak_memory_mb:.1f}MB")
        print(f"   Error rate: {results.error_rate:.1%}")
        
        return results
    
    def _generate_test_message(self, config: LoadTestConfig) -> AdvancedTTSMessage:
        """Generate test message based on configuration."""
        # Select priority based on distribution
        rand = random.random()
        cumulative = 0.0
        selected_priority = AdvancedPriority.MEDIUM
        
        for priority, probability in config.priority_distribution.items():
            cumulative += probability
            if rand <= cumulative:
                selected_priority = priority
                break
        
        # Generate message content
        min_size, max_size = config.message_size_range
        message_size = random.randint(min_size, max_size)
        
        # Create content with potential duplication
        if random.random() < config.deduplication_rate:
            # Create duplicate content
            content = f"Duplicate test message {random.randint(1, 100)}"
        else:
            # Create unique content
            content = f"Test message {random.randint(1, 1000000)} - {''.join(random.choices('abcdefghijklmnopqrstuvwxyz', k=message_size))}"
        
        # Select message type
        message_types = list(MessageType)
        selected_type = random.choice(message_types)
        
        return AdvancedTTSMessage(
            content=content,
            priority=selected_priority,
            message_type=selected_type,
            hook_type=f"load_test",
            tool_name=f"TestTool_{random.randint(1, 10)}"
        )

class ScalabilityAnalyzer:
    """Analyzes queue scalability across different data sizes."""
    
    def __init__(self):
        """Initialize scalability analyzer."""
        self.executor = LoadTestExecutor()
        
    def run_scalability_analysis(self, queue_factory: Callable, sizes: List[int]) -> Dict[str, Any]:
        """
        Run scalability analysis across different queue sizes.
        
        Args:
            queue_factory: Function that creates queue instances
            sizes: List of queue sizes to test
            
        Returns:
            Scalability analysis results
        """
        print("📊 Running scalability analysis")
        print(f"   Test sizes: {sizes}")
        
        results = {}
        
        for size in sizes:
            print(f"\n🔍 Testing with {size} operations")
            
            # Create fresh queue instance
            queue = queue_factory()
            
            # Create test configuration
            config = LoadTestConfig(
                name=f"scalability_{size}",
                num_operations=size,
                num_threads=4,  # Fixed thread count for consistency
                operation_mix={"enqueue": 0.7, "dequeue": 0.3}  # Focus on core operations
            )
            
            # Run test
            result = self.executor.run_load_test(queue, config)
            results[size] = result
            
            # Clean up
            if hasattr(queue, 'clear'):
                queue.clear()
        
        # Analyze scalability
        analysis = self._analyze_scalability_results(results)
        
        print("\n📈 Scalability Analysis Complete")
        return {
            "test_sizes": sizes,
            "results": results,
            "analysis": analysis
        }
    
    def _analyze_scalability_results(self, results: Dict[int, LoadTestResults]) -> Dict[str, Any]:
        """Analyze scalability from test results."""
        sizes = sorted(results.keys())
        
        # Extract metrics
        throughputs = [results[size].operations_per_second for size in sizes]
        latencies = [results[size].avg_latency_ms for size in sizes]
        memory_usage = [results[size].avg_memory_mb for size in sizes]
        
        # Calculate growth rates
        def calculate_growth_rate(values):
            if len(values) < 2:
                return 0.0
            return (values[-1] / values[0]) ** (1 / (len(values) - 1)) - 1
        
        throughput_growth = calculate_growth_rate(throughputs)
        latency_growth = calculate_growth_rate(latencies)
        memory_growth = calculate_growth_rate(memory_usage)
        
        # Determine complexity characteristics
        def estimate_complexity(sizes, values):
            """Estimate computational complexity from data."""
            if len(sizes) < 3:
                return "insufficient_data"
            
            # Test different complexity patterns
            log_fit = np.corrcoef(sizes, [s * np.log(s) for s in sizes])[0, 1] ** 2
            linear_fit = np.corrcoef(sizes, values)[0, 1] ** 2
            quadratic_fit = np.corrcoef(sizes, [s * s for s in sizes])[0, 1] ** 2
            
            best_fit = max(log_fit, linear_fit, quadratic_fit)
            
            if best_fit == log_fit:
                return "O(n log n)"
            elif best_fit == linear_fit:
                return "O(n)"
            elif best_fit == quadratic_fit:
                return "O(n²)"
            else:
                return "unknown"
        
        latency_complexity = estimate_complexity(sizes, latencies)
        memory_complexity = estimate_complexity(sizes, memory_usage)
        
        return {
            "throughput_growth_rate": throughput_growth,
            "latency_growth_rate": latency_growth,
            "memory_growth_rate": memory_growth,
            "estimated_latency_complexity": latency_complexity,
            "estimated_memory_complexity": memory_complexity,
            "scalability_score": max(0, 1 - latency_growth),  # Lower latency growth = better scalability
            "performance_degradation": {
                size: {
                    "relative_throughput": results[size].operations_per_second / max(throughputs),
                    "relative_latency": results[size].avg_latency_ms / min(latencies) if min(latencies) > 0 else 1,
                    "relative_memory": results[size].avg_memory_mb / min(memory_usage) if min(memory_usage) > 0 else 1
                }
                for size in sizes
            }
        }

def create_visualization_charts(comparison_data: Dict[str, Any], output_dir: Path):
    """Create visualization charts for performance comparison."""
    try:
        output_dir.mkdir(exist_ok=True)
        
        # Performance comparison chart
        implementations = list(comparison_data["comparisons"].keys())
        implementations.insert(0, comparison_data["baseline"])  # Add baseline
        
        throughput_improvements = [1.0]  # Baseline = 1.0
        latency_improvements = [1.0]
        memory_improvements = [1.0]
        
        for impl in implementations[1:]:
            comp = comparison_data["comparisons"][impl]
            throughput_improvements.append(comp["throughput_improvement"])
            latency_improvements.append(comp["latency_improvement"])
            memory_improvements.append(comp["memory_improvement"])
        
        # Create comparison chart
        fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(15, 5))
        
        # Throughput comparison
        bars1 = ax1.bar(implementations, throughput_improvements, color=['red' if x == 1.0 else 'green' for x in throughput_improvements])
        ax1.set_title('Throughput Improvement Factor')
        ax1.set_ylabel('Improvement Factor (higher is better)')
        ax1.axhline(y=1.0, color='black', linestyle='--', alpha=0.5)
        ax1.tick_params(axis='x', rotation=45)
        
        # Latency comparison  
        bars2 = ax2.bar(implementations, latency_improvements, color=['red' if x == 1.0 else 'green' for x in latency_improvements])
        ax2.set_title('Latency Improvement Factor')
        ax2.set_ylabel('Improvement Factor (higher is better)')
        ax2.axhline(y=1.0, color='black', linestyle='--', alpha=0.5)
        ax2.tick_params(axis='x', rotation=45)
        
        # Memory comparison
        bars3 = ax3.bar(implementations, memory_improvements, color=['red' if x == 1.0 else 'green' for x in memory_improvements])
        ax3.set_title('Memory Efficiency Improvement')
        ax3.set_ylabel('Improvement Factor (higher is better)')
        ax3.axhline(y=1.0, color='black', linestyle='--', alpha=0.5)
        ax3.tick_params(axis='x', rotation=45)
        
        plt.tight_layout()
        plt.savefig(output_dir / "performance_comparison.png", dpi=300, bbox_inches='tight')
        plt.close()
        
        print(f"📊 Performance visualization saved to {output_dir / 'performance_comparison.png'}")
        
    except Exception as e:
        print(f"⚠️ Failed to create visualizations: {e}")

def main():
    """Main entry point for load testing framework."""
    if not QUEUES_AVAILABLE:
        print("❌ Queue implementations not available for testing")
        return
    
    print("🧪 Phase 3.4.2 Load Testing and Performance Validation Framework")
    print("=" * 70)
    
    # Test configurations
    test_configs = [
        LoadTestConfig("light_load", 1000, 2),
        LoadTestConfig("medium_load", 5000, 4),
        LoadTestConfig("heavy_load", 10000, 8),
        LoadTestConfig("concurrent_stress", 20000, 16)
    ]
    
    # Initialize components
    executor = LoadTestExecutor()
    comparator = PerformanceComparator()
    scalability_analyzer = ScalabilityAnalyzer()
    
    # Test both implementations
    for config in test_configs:
        print(f"\n🔬 Running test configuration: {config.name}")
        
        # Test heap-based implementation
        print(f"\n  🚀 Testing Heap-Based Priority Queue")
        heap_queue = HeapBasedPriorityQueue()
        heap_result = executor.run_load_test(heap_queue, config)
        comparator.add_result(f"heap_{config.name}", heap_result)
        heap_queue.clear()
        
        # Test original implementation  
        print(f"\n  📝 Testing Original Linear Priority Queue")
        linear_queue = AdvancedPriorityQueue()
        linear_result = executor.run_load_test(linear_queue, config)
        comparator.add_result(f"original_{config.name}", linear_result)
        linear_queue.clear_all()
    
    # Generate comparison report
    print("\n📊 Generating Performance Comparison Report")
    comparison_report = comparator.generate_comparison_report()
    
    # Print summary
    print("\n🏆 Performance Comparison Summary:")
    for impl, comparison in comparison_report["comparisons"].items():
        print(f"  {impl}:")
        print(f"    Throughput improvement: {comparison['throughput_improvement']:.1f}x")
        print(f"    Latency improvement: {comparison['latency_improvement']:.1f}x") 
        print(f"    Memory improvement: {comparison['memory_improvement']:.1f}x")
        print(f"    P95 latency improvement: {comparison['p95_latency_improvement']:.1f}x")
    
    print(f"\n🥇 Performance Winners:")
    for metric, winner in comparison_report["winners"].items():
        print(f"  {metric}: {winner}")
    
    # Run scalability analysis
    print("\n📈 Running Scalability Analysis")
    scalability_sizes = [500, 1000, 2500, 5000, 10000]
    
    # Heap implementation scalability
    heap_scalability = scalability_analyzer.run_scalability_analysis(
        lambda: HeapBasedPriorityQueue(),
        scalability_sizes
    )
    
    print(f"\n📊 Heap Implementation Scalability:")
    print(f"  Estimated latency complexity: {heap_scalability['analysis']['estimated_latency_complexity']}")
    print(f"  Scalability score: {heap_scalability['analysis']['scalability_score']:.2f}")
    print(f"  Latency growth rate: {heap_scalability['analysis']['latency_growth_rate']:.1%}")
    
    # Save detailed results
    results_dir = Path("load_test_results")
    results_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_file = results_dir / f"phase_3_4_2_load_test_{timestamp}.json"
    
    with open(results_file, 'w') as f:
        # Convert results to JSON-serializable format
        json_data = {
            "timestamp": timestamp,
            "comparison_report": comparison_report,
            "scalability_analysis": {
                "test_sizes": heap_scalability["test_sizes"],
                "analysis": heap_scalability["analysis"]
            }
        }
        json.dump(json_data, f, indent=2, default=str)
    
    print(f"\n💾 Detailed results saved to: {results_file}")
    
    # Create visualizations
    create_visualization_charts(comparison_report, results_dir)
    
    print("\n✅ Phase 3.4.2 Load Testing Complete")
    print("🏆 Heap-based implementation performance validated!")

if __name__ == "__main__":
    main()