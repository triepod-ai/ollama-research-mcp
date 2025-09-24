#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "python-dotenv>=1.0.0",
# ]
# ///

"""
Phase 3.4.2 Cache Validation Framework
Comprehensive testing and validation system for message processing cache.

Features:
- Performance benchmarking with statistical analysis
- Cache effectiveness validation across different scenarios
- Quality preservation testing with processing comparison
- Integration testing with existing TTS components
- Load testing with realistic message patterns
- Cache warming validation and pattern recognition accuracy
"""

import json
import os
import random
import statistics
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from dotenv import load_dotenv

# Import Phase 3.4.2 components
from phase3_42_message_processing_cache import (
    MessageProcessingCache, 
    get_message_processing_cache,
    process_message_cached,
    process_message_with_cache_metrics
)
from transcript_processor import ProcessingLevel, TranscriptProcessor
from personalization_engine import PersonalizationEngine

# Load environment variables
env_path = Path.home() / "brainpods" / ".env"
if env_path.exists():
    load_dotenv(env_path)

@dataclass
class ValidationTestResult:
    """Result of a validation test."""
    test_name: str
    success: bool
    metrics: Dict[str, Any]
    execution_time_ms: float
    details: str = ""
    error_message: Optional[str] = None

@dataclass 
class PerformanceBenchmarkResult:
    """Result of performance benchmarking."""
    test_scenario: str
    total_messages: int
    total_time_ms: float
    average_time_per_message_ms: float
    messages_per_second: float
    cache_hit_rate: float
    processing_speedup: float
    memory_usage_mb: float

@dataclass
class QualityComparisonResult:
    """Result of quality comparison between cached and uncached processing."""
    original_message: str
    cached_result: str
    uncached_result: str
    results_identical: bool
    semantic_similarity: float
    quality_preserved: bool
    processing_time_difference_ms: float

class CacheValidationFramework:
    """
    Comprehensive validation framework for Phase 3.4.2 message processing cache.
    
    Validates cache effectiveness, performance improvements, and quality preservation.
    """
    
    def __init__(self):
        """Initialize the validation framework."""
        self.cache = get_message_processing_cache()
        
        # Initialize uncached processors for comparison
        self.transcript_processor = TranscriptProcessor()
        self.personalization_engine = PersonalizationEngine()
        
        # Test data sets
        self.test_messages = self._generate_test_datasets()
        
        # Validation results storage
        self.test_results: List[ValidationTestResult] = []
        self.benchmark_results: List[PerformanceBenchmarkResult] = []
        self.quality_results: List[QualityComparisonResult] = []
        
        print("🧪 Phase 3.4.2 Cache Validation Framework initialized")
        print(f"  Test Datasets: {len(self.test_messages)} message categories")
        print(f"  Validation Components: Cache, Quality, Performance, Integration")
        
    def _generate_test_datasets(self) -> Dict[str, List[Tuple[str, Dict[str, Any]]]]:
        """Generate comprehensive test datasets for validation."""
        datasets = {
            "exact_duplicates": [
                ("File processing completed successfully", {"category": "success", "hook_type": "post_tool_use"}),
                ("File processing completed successfully", {"category": "success", "hook_type": "post_tool_use"}),
                ("Error: File not found", {"category": "error", "tool_name": "Read"}),
                ("Error: File not found", {"category": "error", "tool_name": "Read"}),
            ],
            
            "semantic_similarities": [
                ("File processing completed successfully", {"category": "success"}),
                ("File processing finished successfully", {"category": "success"}),  # Same meaning
                ("Data processing completed successfully", {"category": "success"}),  # Similar structure
                ("Image processing completed successfully", {"category": "success"}),  # Template match
            ],
            
            "template_patterns": [
                ("Build started for project myapp", {"category": "information"}),
                ("Build completed for project webapp", {"category": "success"}),
                ("Build failed for project backend", {"category": "error"}),
                ("Test started for module auth", {"category": "information"}),
                ("Test passed for module database", {"category": "success"}),
                ("Test failed for module validation", {"category": "error"}),
            ],
            
            "technical_variations": [
                ("API call to /users returned 200", {"category": "success", "tool_name": "http"}),
                ("API call to /posts returned 404", {"category": "error", "tool_name": "http"}),
                ("Database query executed successfully", {"category": "success", "tool_name": "sql"}),
                ("Database connection failed", {"category": "error", "tool_name": "sql"}),
                ("File read operation completed", {"category": "success", "tool_name": "Read"}),
                ("File write operation failed", {"category": "error", "tool_name": "Write"}),
            ],
            
            "personalization_contexts": [
                ("Task completed", {"category": "success", "hook_type": "stop"}),
                ("Task completed", {"category": "success", "hook_type": "subagent_stop"}),
                ("Permission required", {"category": "permission", "hook_type": "notification"}),
                ("Operation finished", {"category": "completion", "hook_type": "post_tool_use"}),
            ],
            
            "edge_cases": [
                ("", {"category": "information"}),  # Empty message
                ("A", {"category": "information"}),  # Single character
                ("Very long message " * 100, {"category": "information"}),  # Very long message
                ("Message with\nnewlines\nand\ttabs", {"category": "information"}),  # Special characters
                ("Message with 💡 emojis 🚀 and symbols ⭐", {"category": "information"}),  # Unicode
            ],
            
            "realistic_scenarios": [
                ("Started development server on port 3000", {"category": "information", "hook_type": "post_tool_use", "tool_name": "Bash"}),
                ("Compilation completed with 0 errors and 2 warnings", {"category": "success", "hook_type": "post_tool_use", "tool_name": "Bash"}),
                ("Git commit created: 'fix: resolve authentication bug'", {"category": "success", "hook_type": "post_tool_use", "tool_name": "Bash"}),
                ("Package installation failed: npm ERR! peer dependency", {"category": "error", "hook_type": "post_tool_use", "tool_name": "Bash"}),
                ("Test suite completed: 25 passed, 3 failed, 2 skipped", {"category": "warning", "hook_type": "post_tool_use", "tool_name": "Bash"}),
            ]
        }
        
        return datasets
    
    def run_cache_effectiveness_validation(self) -> ValidationTestResult:
        """Validate cache effectiveness across different message types."""
        start_time = time.time()
        
        try:
            print("\n🎯 Testing Cache Effectiveness...")
            
            # Clear cache for clean test
            self.cache.clear_cache()
            
            total_tests = 0
            cache_hits = 0
            effectiveness_metrics = defaultdict(list)
            
            for dataset_name, messages in self.test_messages.items():
                print(f"  Testing {dataset_name}...")
                
                for message, context in messages:
                    total_tests += 1
                    
                    # First call - should be cache miss
                    result1, metrics1 = process_message_with_cache_metrics(message, context)
                    
                    # Second call - should be cache hit (if caching is effective)
                    result2, metrics2 = process_message_with_cache_metrics(message, context)
                    
                    # Check for cache hit improvement
                    hit_rate_improvement = metrics2["cache_effectiveness"] - metrics1["cache_effectiveness"]
                    if hit_rate_improvement > 0:
                        cache_hits += 1
                    
                    effectiveness_metrics[dataset_name].append({
                        "message": message[:50],
                        "hit_rate_improvement": hit_rate_improvement,
                        "cache_effective": hit_rate_improvement > 0
                    })
            
            # Calculate overall effectiveness
            overall_effectiveness = cache_hits / total_tests if total_tests > 0 else 0
            
            # Get final cache statistics
            cache_stats = self.cache.get_cache_statistics()
            final_hit_rate = cache_stats["processing_cache_metrics"]["hit_metrics"]["hit_rate"]
            
            execution_time = (time.time() - start_time) * 1000
            
            success = final_hit_rate >= 0.8  # 80% target hit rate
            
            result = ValidationTestResult(
                test_name="Cache Effectiveness Validation",
                success=success,
                metrics={
                    "total_tests": total_tests,
                    "cache_hits": cache_hits,
                    "overall_effectiveness": overall_effectiveness,
                    "final_hit_rate": final_hit_rate,
                    "target_hit_rate": 0.8,
                    "dataset_breakdown": dict(effectiveness_metrics)
                },
                execution_time_ms=execution_time,
                details=f"Achieved {final_hit_rate:.1%} hit rate (target: 80%+)"
            )
            
            self.test_results.append(result)
            return result
            
        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            return ValidationTestResult(
                test_name="Cache Effectiveness Validation",
                success=False,
                metrics={},
                execution_time_ms=execution_time,
                error_message=str(e)
            )
    
    def run_performance_benchmarking(self) -> ValidationTestResult:
        """Run comprehensive performance benchmarking."""
        start_time = time.time()
        
        try:
            print("\n⚡ Running Performance Benchmarking...")
            
            benchmark_scenarios = [
                ("Small Dataset", 100),
                ("Medium Dataset", 500),
                ("Large Dataset", 1000)
            ]
            
            for scenario_name, message_count in benchmark_scenarios:
                print(f"  Benchmarking {scenario_name} ({message_count} messages)...")
                
                # Generate test messages
                test_messages = []
                all_messages = []
                for messages in self.test_messages.values():
                    all_messages.extend(messages)
                
                for _ in range(message_count):
                    message, context = random.choice(all_messages)
                    test_messages.append((message, context))
                
                # Clear cache for clean benchmark
                self.cache.clear_cache()
                
                # Benchmark processing
                bench_start = time.time()
                
                for message, context in test_messages:
                    process_message_cached(message, context, personalize=True)
                
                bench_time = (time.time() - bench_start) * 1000
                
                # Get performance metrics
                cache_stats = self.cache.get_cache_statistics()
                hit_metrics = cache_stats["processing_cache_metrics"]["hit_metrics"]
                perf_metrics = cache_stats["processing_cache_metrics"]["performance_metrics"]
                
                benchmark_result = PerformanceBenchmarkResult(
                    test_scenario=scenario_name,
                    total_messages=message_count,
                    total_time_ms=bench_time,
                    average_time_per_message_ms=bench_time / message_count,
                    messages_per_second=(message_count / bench_time) * 1000,
                    cache_hit_rate=hit_metrics["hit_rate"],
                    processing_speedup=perf_metrics["processing_speedup"],
                    memory_usage_mb=cache_stats["cache_manager_stats"]["global"]["total_memory_mb"]
                )
                
                self.benchmark_results.append(benchmark_result)
                
                print(f"    Time: {bench_time:.1f}ms | Rate: {benchmark_result.messages_per_second:.1f} msg/s | Hit Rate: {hit_metrics['hit_rate']:.1%}")
            
            # Validate performance requirements
            avg_speedup = statistics.mean([r.processing_speedup for r in self.benchmark_results])
            max_messages_per_second = max([r.messages_per_second for r in self.benchmark_results])
            
            execution_time = (time.time() - start_time) * 1000
            
            success = avg_speedup > 0 and max_messages_per_second > 100  # Performance targets
            
            result = ValidationTestResult(
                test_name="Performance Benchmarking",
                success=success,
                metrics={
                    "benchmark_count": len(self.benchmark_results),
                    "average_speedup": avg_speedup,
                    "max_messages_per_second": max_messages_per_second,
                    "benchmark_results": [r.__dict__ for r in self.benchmark_results]
                },
                execution_time_ms=execution_time,
                details=f"Average speedup: {avg_speedup:.1%}, Max rate: {max_messages_per_second:.1f} msg/s"
            )
            
            self.test_results.append(result)
            return result
            
        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            return ValidationTestResult(
                test_name="Performance Benchmarking",
                success=False,
                metrics={},
                execution_time_ms=execution_time,
                error_message=str(e)
            )
    
    def run_quality_preservation_validation(self) -> ValidationTestResult:
        """Validate that caching preserves processing quality."""
        start_time = time.time()
        
        try:
            print("\n🔍 Testing Quality Preservation...")
            
            # Test quality preservation across different message types
            quality_test_messages = [
                ("Complex message with technical terms like API, JSON, and HTTP", {"category": "information"}),
                ("Error in file /path/to/config.json at line 42", {"category": "error"}),
                ("Build completed successfully with warnings", {"category": "success"}),
                ("Permission denied for user authentication", {"category": "permission"}),
                ("```python\ndef hello():\n    print('world')\n```", {"category": "information"}),
            ]
            
            total_quality_tests = 0
            quality_preserved_count = 0
            
            for message, context in quality_test_messages:
                total_quality_tests += 1
                
                # Clear cache to ensure clean comparison
                self.cache.clear_cache()
                
                # Process with cached system
                cached_start = time.time()
                cached_result = process_message_cached(message, context, personalize=False)  # Skip personalization for direct comparison
                cached_time = (time.time() - cached_start) * 1000
                
                # Process with uncached system
                uncached_start = time.time()
                processed_result = self.transcript_processor.process_for_speech(message, context)
                uncached_result = processed_result.processed
                uncached_time = (time.time() - uncached_start) * 1000
                
                # Compare results
                results_identical = cached_result == uncached_result
                
                # Calculate semantic similarity (simple word overlap for now)
                cached_words = set(cached_result.lower().split())
                uncached_words = set(uncached_result.lower().split())
                
                if len(cached_words) == 0 and len(uncached_words) == 0:
                    semantic_similarity = 1.0
                elif len(cached_words) == 0 or len(uncached_words) == 0:
                    semantic_similarity = 0.0
                else:
                    overlap = len(cached_words.intersection(uncached_words))
                    union = len(cached_words.union(uncached_words))
                    semantic_similarity = overlap / union if union > 0 else 0.0
                
                # Quality preserved if results are identical or highly similar
                quality_preserved = results_identical or semantic_similarity >= 0.9
                
                if quality_preserved:
                    quality_preserved_count += 1
                
                quality_result = QualityComparisonResult(
                    original_message=message,
                    cached_result=cached_result,
                    uncached_result=uncached_result,
                    results_identical=results_identical,
                    semantic_similarity=semantic_similarity,
                    quality_preserved=quality_preserved,
                    processing_time_difference_ms=cached_time - uncached_time
                )
                
                self.quality_results.append(quality_result)
                
                print(f"    Quality preserved: {'✅' if quality_preserved else '❌'} (Similarity: {semantic_similarity:.1%})")
            
            # Calculate overall quality preservation
            quality_preservation_rate = quality_preserved_count / total_quality_tests if total_quality_tests > 0 else 0
            
            execution_time = (time.time() - start_time) * 1000
            
            success = quality_preservation_rate >= 0.95  # 95% quality preservation target
            
            result = ValidationTestResult(
                test_name="Quality Preservation Validation",
                success=success,
                metrics={
                    "total_tests": total_quality_tests,
                    "quality_preserved_count": quality_preserved_count,
                    "quality_preservation_rate": quality_preservation_rate,
                    "target_preservation_rate": 0.95,
                    "quality_results": [r.__dict__ for r in self.quality_results]
                },
                execution_time_ms=execution_time,
                details=f"Quality preserved in {quality_preservation_rate:.1%} of tests (target: 95%+)"
            )
            
            self.test_results.append(result)
            return result
            
        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            return ValidationTestResult(
                test_name="Quality Preservation Validation",
                success=False,
                metrics={},
                execution_time_ms=execution_time,
                error_message=str(e)
            )
    
    def run_integration_testing(self) -> ValidationTestResult:
        """Test integration with existing TTS components."""
        start_time = time.time()
        
        try:
            print("\n🔗 Testing Integration with TTS Components...")
            
            integration_tests = [
                {
                    "test_name": "Cache Manager Integration",
                    "test_func": lambda: self.cache.cache_manager.get_global_stats() is not None
                },
                {
                    "test_name": "Transcript Processor Integration",
                    "test_func": lambda: hasattr(self.cache, 'transcript_processor') and self.cache.transcript_processor is not None
                },
                {
                    "test_name": "Personalization Engine Integration", 
                    "test_func": lambda: hasattr(self.cache, 'personalization_engine') and self.cache.personalization_engine is not None
                },
                {
                    "test_name": "Message Pattern Recognition",
                    "test_func": lambda: len(self.cache.message_patterns) >= 5
                },
                {
                    "test_name": "Cache Layer Creation",
                    "test_func": lambda: "message_processing" in self.cache.cache_manager.get_cache_layers() and "personalization" in self.cache.cache_manager.get_cache_layers()
                },
                {
                    "test_name": "Fingerprint Generation",
                    "test_func": lambda: self.cache._generate_content_fingerprint("test message") is not None
                },
                {
                    "test_name": "Cache Key Generation",
                    "test_func": lambda: self.cache.cache_manager.generate_cache_key("test", "key") is not None
                }
            ]
            
            passed_tests = 0
            total_tests = len(integration_tests)
            test_details = []
            
            for test in integration_tests:
                try:
                    test_passed = test["test_func"]()
                    if test_passed:
                        passed_tests += 1
                    
                    test_details.append({
                        "test_name": test["test_name"],
                        "passed": test_passed,
                        "status": "✅" if test_passed else "❌"
                    })
                    
                    print(f"    {test['test_name']}: {'✅' if test_passed else '❌'}")
                    
                except Exception as e:
                    test_details.append({
                        "test_name": test["test_name"],
                        "passed": False,
                        "status": "❌",
                        "error": str(e)
                    })
                    print(f"    {test['test_name']}: ❌ (Error: {str(e)})")
            
            execution_time = (time.time() - start_time) * 1000
            
            success = passed_tests == total_tests
            
            result = ValidationTestResult(
                test_name="Integration Testing",
                success=success,
                metrics={
                    "total_tests": total_tests,
                    "passed_tests": passed_tests,
                    "success_rate": passed_tests / total_tests,
                    "test_details": test_details
                },
                execution_time_ms=execution_time,
                details=f"Passed {passed_tests}/{total_tests} integration tests"
            )
            
            self.test_results.append(result)
            return result
            
        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            return ValidationTestResult(
                test_name="Integration Testing",
                success=False,
                metrics={},
                execution_time_ms=execution_time,
                error_message=str(e)
            )
    
    def run_load_testing(self) -> ValidationTestResult:
        """Run load testing with realistic message patterns."""
        start_time = time.time()
        
        try:
            print("\n🏋️ Running Load Testing...")
            
            # Generate realistic load test data
            load_test_patterns = [
                "File {filename} processed successfully",
                "Error: Failed to connect to {service}",
                "Build {status} for project {project}",
                "{count} tests {result}",
                "API call to {endpoint} returned {status_code}",
                "Permission {action} for {resource}",
                "{operation} completed in {time}ms"
            ]
            
            # Generate load test messages
            load_messages = []
            for _ in range(2000):  # 2000 messages for load test
                pattern = random.choice(load_test_patterns)
                
                # Fill in template variables
                message = pattern.format(
                    filename=random.choice(["config.json", "main.py", "index.js", "app.tsx"]),
                    service=random.choice(["database", "api", "cache", "auth-service"]),
                    status=random.choice(["started", "completed", "failed"]),
                    project=random.choice(["frontend", "backend", "mobile-app"]),
                    count=random.randint(1, 50),
                    result=random.choice(["passed", "failed", "skipped"]),
                    endpoint=random.choice(["/users", "/posts", "/auth", "/health"]),
                    status_code=random.choice([200, 404, 500, 201]),
                    action=random.choice(["granted", "denied", "required"]),
                    resource=random.choice(["file", "database", "network"]),
                    operation=random.choice(["compilation", "deployment", "backup"]),
                    time=random.randint(50, 5000)
                )
                
                context = {
                    "category": random.choice(["success", "error", "information", "warning"]),
                    "hook_type": random.choice(["post_tool_use", "notification", "stop"]),
                    "tool_name": random.choice(["Bash", "Read", "Write", "Edit"])
                }
                
                load_messages.append((message, context))
            
            # Clear cache and run load test
            self.cache.clear_cache()
            
            load_start = time.time()
            
            for message, context in load_messages:
                process_message_cached(message, context, personalize=True)
            
            load_time = (time.time() - load_start) * 1000
            
            # Get load test metrics
            cache_stats = self.cache.get_cache_statistics()
            hit_metrics = cache_stats["processing_cache_metrics"]["hit_metrics"]
            
            messages_per_second = len(load_messages) / (load_time / 1000)
            
            execution_time = (time.time() - start_time) * 1000
            
            # Load test success criteria
            success = (
                messages_per_second >= 50 and  # At least 50 messages per second
                hit_metrics["hit_rate"] >= 0.7 and  # At least 70% cache hit rate under load
                load_time < 60000  # Complete within 60 seconds
            )
            
            result = ValidationTestResult(
                test_name="Load Testing",
                success=success,
                metrics={
                    "total_messages": len(load_messages),
                    "load_time_ms": load_time,
                    "messages_per_second": messages_per_second,
                    "cache_hit_rate": hit_metrics["hit_rate"],
                    "memory_usage_mb": cache_stats["cache_manager_stats"]["global"]["total_memory_mb"],
                    "target_rate": 50,
                    "target_hit_rate": 0.7
                },
                execution_time_ms=execution_time,
                details=f"Processed {len(load_messages)} messages at {messages_per_second:.1f} msg/s with {hit_metrics['hit_rate']:.1%} hit rate"
            )
            
            self.test_results.append(result)
            return result
            
        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            return ValidationTestResult(
                test_name="Load Testing",
                success=False,
                metrics={},
                execution_time_ms=execution_time,
                error_message=str(e)
            )
    
    def run_comprehensive_validation(self) -> Dict[str, Any]:
        """Run all validation tests and return comprehensive results."""
        print("🧪 Starting Phase 3.4.2 Comprehensive Cache Validation")
        print("=" * 70)
        
        validation_start = time.time()
        
        # Run all validation tests
        validation_tests = [
            self.run_cache_effectiveness_validation,
            self.run_performance_benchmarking,
            self.run_quality_preservation_validation,
            self.run_integration_testing,
            self.run_load_testing
        ]
        
        for test_func in validation_tests:
            try:
                result = test_func()
                print(f"  {result.test_name}: {'✅ PASSED' if result.success else '❌ FAILED'}")
                if result.error_message:
                    print(f"    Error: {result.error_message}")
                else:
                    print(f"    {result.details}")
            except Exception as e:
                print(f"  {test_func.__name__}: ❌ FAILED (Exception: {str(e)})")
        
        total_validation_time = (time.time() - validation_start) * 1000
        
        # Generate comprehensive report
        passed_tests = sum(1 for result in self.test_results if result.success)
        total_tests = len(self.test_results)
        
        final_cache_stats = self.cache.get_cache_statistics()
        
        validation_summary = {
            "validation_overview": {
                "total_tests": total_tests,
                "passed_tests": passed_tests,
                "success_rate": passed_tests / total_tests if total_tests > 0 else 0,
                "total_validation_time_ms": total_validation_time,
                "validation_timestamp": datetime.now().isoformat()
            },
            "test_results": [result.__dict__ for result in self.test_results],
            "performance_benchmarks": [result.__dict__ for result in self.benchmark_results],
            "quality_comparisons": [result.__dict__ for result in self.quality_results],
            "final_cache_statistics": final_cache_stats,
            "requirements_validation": {
                "target_hit_rate_80_percent": final_cache_stats["processing_cache_metrics"]["hit_metrics"]["hit_rate"] >= 0.8,
                "processing_speedup_achieved": final_cache_stats["processing_cache_metrics"]["performance_metrics"]["processing_speedup"] > 0,
                "quality_preservation_95_percent": len([r for r in self.quality_results if r.quality_preserved]) / len(self.quality_results) >= 0.95 if self.quality_results else False,
                "integration_complete": passed_tests >= 4,  # At least 4 out of 5 tests should pass
                "phase_3_4_2_complete": passed_tests == total_tests
            }
        }
        
        return validation_summary
    
    def generate_validation_report(self, save_to_file: bool = True) -> str:
        """Generate a comprehensive validation report."""
        validation_results = self.run_comprehensive_validation()
        
        print(f"\n📊 Validation Results Summary:")
        print(f"  Tests Passed: {validation_results['validation_overview']['passed_tests']}/{validation_results['validation_overview']['total_tests']}")
        print(f"  Success Rate: {validation_results['validation_overview']['success_rate']:.1%}")
        print(f"  Total Time: {validation_results['validation_overview']['total_validation_time_ms']:.1f}ms")
        
        print(f"\n🎯 Requirements Validation:")
        requirements = validation_results['requirements_validation']
        for requirement, achieved in requirements.items():
            status = "✅" if achieved else "❌"
            print(f"  {status} {requirement.replace('_', ' ').title()}")
        
        # Final performance metrics
        cache_metrics = validation_results['final_cache_statistics']['processing_cache_metrics']
        print(f"\n🏆 Final Performance Metrics:")
        print(f"  Cache Hit Rate: {cache_metrics['hit_metrics']['hit_rate']:.1%}")
        print(f"  Processing Speedup: {cache_metrics['performance_metrics']['processing_speedup']:.1%}")
        print(f"  Memory Usage: {validation_results['final_cache_statistics']['cache_manager_stats']['global']['total_memory_mb']:.2f}MB")
        
        all_requirements_met = all(requirements.values())
        print(f"\n{'🎉 ALL PHASE 3.4.2 REQUIREMENTS MET!' if all_requirements_met else '⚠️  Some requirements need attention'}")
        
        if save_to_file:
            report_path = Path(__file__).parent / "phase3_42_validation_report.json"
            with open(report_path, 'w') as f:
                json.dump(validation_results, f, indent=2, default=str)
            print(f"\n📄 Validation report saved to: {report_path}")
        
        return json.dumps(validation_results, indent=2, default=str)

def main():
    """Main entry point for cache validation."""
    import sys
    
    if "--validate" in sys.argv:
        framework = CacheValidationFramework()
        framework.generate_validation_report(save_to_file=True)
        
    elif "--quick-test" in sys.argv:
        print("🧪 Running Quick Phase 3.4.2 Cache Validation")
        print("=" * 50)
        
        framework = CacheValidationFramework()
        
        # Run only essential tests
        effectiveness_result = framework.run_cache_effectiveness_validation()
        integration_result = framework.run_integration_testing()
        
        print(f"\n📊 Quick Test Results:")
        print(f"  Cache Effectiveness: {'✅' if effectiveness_result.success else '❌'}")
        print(f"  Integration Testing: {'✅' if integration_result.success else '❌'}")
        
        if effectiveness_result.success and integration_result.success:
            print(f"\n✅ Phase 3.4.2 Message Processing Cache is working correctly!")
        else:
            print(f"\n❌ Issues detected - run full validation with --validate")
    
    else:
        print("Phase 3.4.2 Cache Validation Framework")
        print("Comprehensive testing for message processing cache")
        print("Usage:")
        print("  python phase3_42_cache_validation_framework.py --validate")
        print("  python phase3_42_cache_validation_framework.py --quick-test")

if __name__ == "__main__":
    main()