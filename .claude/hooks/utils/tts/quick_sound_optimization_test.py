#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "pygame>=2.0.0",
#   "python-dotenv>=1.0.0",
# ]
# ///

"""
Quick Sound Effects Optimization Test
Simple performance validation for Phase 3.4.2 O(1) optimization.
"""

import os
import statistics
import time
from typing import List

# Set environment to prevent excessive pre-computation
os.environ["SOUND_EFFECTS_MAX_PRECOMPUTE"] = "100"
os.environ["SOUND_EFFECTS_BATCH_SIZE"] = "25"

# Import components
try:
    from phase3_sound_effects_optimizer import (
        get_sound_effects_optimizer, get_optimized_sound_effect, OptimizationLevel
    )
    from sound_effects_engine import (
        SoundContext, SoundTiming, MessageType, AdvancedPriority
    )
    DEPENDENCIES_AVAILABLE = True
except ImportError:
    DEPENDENCIES_AVAILABLE = False
    print("⚠️ Dependencies not available")

def simple_performance_test():
    """Simple O(1) performance test."""
    print("🚀 Quick Sound Effects Optimization Test")
    print("=" * 60)
    
    if not DEPENDENCIES_AVAILABLE:
        print("❌ Dependencies not available")
        return
    
    # Get optimizer (this will create pre-computed cache)
    print("📋 Initializing optimizer...")
    optimizer = get_sound_effects_optimizer()
    
    print(f"✅ Optimizer initialized")
    print(f"  Pre-computed Effects: {len(optimizer.pre_computed_cache) if hasattr(optimizer, 'pre_computed_cache') else 'N/A'}")
    
    # Create test contexts
    print("\n⚡ Testing O(1) Performance...")
    
    # Test contexts for different scenarios
    test_contexts = [
        SoundContext(
            priority=AdvancedPriority.CRITICAL,
            message_type=MessageType.ERROR,
            hook_type="notification_with_tts",
            tool_name="bash",
            timing=SoundTiming.PRE_TTS
        ),
        SoundContext(
            priority=AdvancedPriority.MEDIUM,
            message_type=MessageType.SUCCESS,
            hook_type="post_tool_use", 
            tool_name="edit",
            timing=SoundTiming.PRE_TTS
        ),
        SoundContext(
            priority=AdvancedPriority.HIGH,
            message_type=MessageType.WARNING,
            hook_type="subagent_stop",
            tool_name="todowrit",
            timing=SoundTiming.PRE_TTS
        )
    ]
    
    # Performance test
    retrieval_times = []
    successful_retrievals = 0
    
    # Run multiple iterations
    for iteration in range(3):
        print(f"  Iteration {iteration + 1}/3:")
        
        for i, context in enumerate(test_contexts):
            # Measure retrieval time
            start_time = time.perf_counter()
            effect = optimizer.get_optimized_sound_effect(context)
            end_time = time.perf_counter()
            
            retrieval_time_ms = (end_time - start_time) * 1000
            retrieval_times.append(retrieval_time_ms)
            
            if effect is not None:
                successful_retrievals += 1
            
            print(f"    Context {i+1}: {retrieval_time_ms:.3f}ms {'✅' if effect else '❌'}")
    
    # Calculate statistics
    if retrieval_times:
        avg_time = statistics.mean(retrieval_times)
        min_time = min(retrieval_times)
        max_time = max(retrieval_times)
        
        print(f"\n📊 Performance Results:")
        print(f"  Average Time: {avg_time:.3f}ms")
        print(f"  Min Time: {min_time:.3f}ms")
        print(f"  Max Time: {max_time:.3f}ms")
        print(f"  Success Rate: {successful_retrievals}/{len(test_contexts) * 3} ({successful_retrievals/(len(test_contexts)*3):.1%})")
        
        # Check target achievement
        target_met = avg_time < 1.0
        print(f"  Target (<1ms): {'🎯 ACHIEVED' if target_met else '🔄 Needs improvement'}")
        
        # Performance assessment
        if target_met:
            print(f"\n✅ Phase 3.4.2 O(1) optimization SUCCESS!")
            print(f"   Sound effects retrieval optimized to {avg_time:.3f}ms average")
        else:
            improvement = ((50.0 - avg_time) / 50.0) * 100  # vs 50ms baseline
            print(f"\n🔄 Phase 3.4.2 optimization shows {improvement:.1f}% improvement")
            print(f"   Current: {avg_time:.3f}ms, Target: <1.0ms")
    
    # Test cache integration
    print(f"\n🗂️ Cache Integration Test:")
    cache_manager = optimizer.cache_manager if hasattr(optimizer, 'cache_manager') and optimizer.cache_manager else None
    
    if cache_manager:
        stats = cache_manager.get_global_stats()
        sound_layer_stats = cache_manager.get_layer_stats("sound_effects")
        
        print(f"  Cache Manager: ✅ Available")
        print(f"  Global Hit Rate: {stats['global']['global_hit_rate']:.1%}")
        print(f"  Sound Layer Hits: {sound_layer_stats.hits if sound_layer_stats else 0}")
        print(f"  Sound Layer Misses: {sound_layer_stats.misses if sound_layer_stats else 0}")
    else:
        print(f"  Cache Manager: ❌ Not available")
    
    # Get optimization report
    print(f"\n📋 Optimization Report:")
    report = optimizer.get_optimization_report()
    
    perf_metrics = report["performance_metrics"]
    print(f"  Cache Hit Rate: {perf_metrics['hit_rate']:.1%}")
    print(f"  Performance Improvement: {perf_metrics['performance_improvement']:.1%}")
    print(f"  Target Achievement: {perf_metrics['target_achievement']}")
    
    opt_details = report["optimization_details"]
    print(f"  Pre-computed Effects: {opt_details['pre_computed_effects']}")
    print(f"  Cache Utilization: {opt_details['utilization_rate']:.1%}")
    
    if report["recommendations"]:
        print(f"  Recommendations:")
        for rec in report["recommendations"]:
            print(f"    • {rec}")
    
    print(f"\n🏁 Quick test completed!")

if __name__ == "__main__":
    simple_performance_test()