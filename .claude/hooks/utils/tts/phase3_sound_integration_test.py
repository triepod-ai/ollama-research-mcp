#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "pygame>=2.0.0",
#   "python-dotenv>=1.0.0",
# ]
# ///

"""
Phase 3.3 Sound Effects Integration Test
Comprehensive test of sound effects integration with TTS coordination system.

Tests:
- Sound effect engine initialization and operation
- Contextual sound selection based on message types and priorities
- Integration with existing TTS messaging structures
- Performance and caching validation
- Error handling and fallback behavior
"""

import time
import sys
import os
from pathlib import Path

# Add current directory to path for imports
sys.path.append(str(Path(__file__).parent))

# Import sound effects system
try:
    from sound_effects_engine import (
        get_sound_effects_engine,
        SoundEffectsEngine,
        play_contextual_sound_effect,
        SoundContext,
        SoundTiming,
        SoundTheme,
        AdvancedPriority,
        MessageType
    )
    SOUND_ENGINE_AVAILABLE = True
except ImportError as e:
    print(f"❌ Sound effects engine not available: {e}")
    SOUND_ENGINE_AVAILABLE = False

def create_test_message_context(priority: AdvancedPriority, message_type: MessageType, content: str):
    """Create a test message context for sound effect testing."""
    return {
        'priority': priority,
        'message_type': message_type,
        'content': content,
        'hook_type': 'test',
        'tool_name': 'SoundIntegrationTest'
    }

def test_sound_engine_initialization():
    """Test sound effects engine initialization."""
    print("🔧 Testing Sound Engine Initialization...")
    
    if not SOUND_ENGINE_AVAILABLE:
        print("❌ Sound engine not available")
        return False
    
    engine = get_sound_effects_engine()
    status = engine.get_status()
    
    print(f"  Engine Enabled: {status['enabled']}")
    print(f"  Engine Initialized: {status['initialized']}")
    print(f"  Sound Library Size: {status['sound_count']}")
    print(f"  Cached Sounds: {status['cached_sounds']}")
    
    return status['enabled'] and status['initialized']

def test_contextual_sound_selection():
    """Test contextual sound selection based on message types."""
    print("\n🎯 Testing Contextual Sound Selection...")
    
    if not SOUND_ENGINE_AVAILABLE:
        print("❌ Sound engine not available")
        return False
    
    engine = get_sound_effects_engine()
    
    test_contexts = [
        {
            'priority': AdvancedPriority.CRITICAL,
            'message_type': MessageType.ERROR,
            'description': 'Critical error message',
            'expected_sound': 'error_tone'
        },
        {
            'priority': AdvancedPriority.MEDIUM,
            'message_type': MessageType.SUCCESS,
            'description': 'Success completion',
            'expected_sound': 'success_chime'
        },
        {
            'priority': AdvancedPriority.HIGH,
            'message_type': MessageType.WARNING,
            'description': 'Warning notification',
            'expected_sound': 'warning_beep'
        },
        {
            'priority': AdvancedPriority.LOW,
            'message_type': MessageType.INFO,
            'description': 'Information update',
            'expected_sound': 'info_click'
        },
        {
            'priority': AdvancedPriority.INTERRUPT,
            'message_type': MessageType.INTERRUPT,
            'description': 'Interrupt alert',
            'expected_sound': 'interrupt_alert'
        }
    ]
    
    selection_results = []
    
    for test_ctx in test_contexts:
        context = SoundContext(
            priority=test_ctx['priority'],
            message_type=test_ctx['message_type'],
            hook_type='test',
            tool_name='ContextTest'
        )
        
        selected_effect = engine.select_sound_effect(context)
        
        if selected_effect:
            print(f"  ✅ {test_ctx['description']}: Selected '{selected_effect.name}'")
            selection_results.append((test_ctx['expected_sound'], selected_effect.name))
        else:
            print(f"  ❌ {test_ctx['description']}: No sound effect selected")
            selection_results.append((test_ctx['expected_sound'], None))
    
    # Calculate accuracy
    correct_selections = sum(1 for expected, actual in selection_results if expected == actual)
    accuracy = correct_selections / len(selection_results) if selection_results else 0
    
    print(f"  📊 Selection Accuracy: {accuracy:.1%} ({correct_selections}/{len(selection_results)})")
    
    return accuracy >= 0.8  # 80% accuracy threshold

def test_sound_playback_integration():
    """Test integrated sound playback with TTS messages."""
    print("\n🎵 Testing Sound Playback Integration...")
    
    if not SOUND_ENGINE_AVAILABLE:
        print("❌ Sound engine not available")
        return False
    
    playback_results = []
    
    test_scenarios = [
        {
            'priority': AdvancedPriority.CRITICAL,
            'message_type': MessageType.ERROR,
            'content': 'Critical system error detected',
            'timing': SoundTiming.PRE_TTS,
            'description': 'Pre-TTS error notification'
        },
        {
            'priority': AdvancedPriority.MEDIUM,
            'message_type': MessageType.SUCCESS,
            'content': 'Operation completed successfully',
            'timing': SoundTiming.POST_TTS,
            'description': 'Post-TTS success confirmation'
        },
        {
            'priority': AdvancedPriority.HIGH,
            'message_type': MessageType.WARNING,
            'content': 'Warning: deprecated API usage detected',
            'timing': SoundTiming.PRE_TTS,
            'description': 'Pre-TTS warning alert'
        }
    ]
    
    for scenario in test_scenarios:
        print(f"  Testing: {scenario['description']}")
        
        # Play contextual sound effect
        sound_id = play_contextual_sound_effect(
            priority=scenario['priority'],
            message_type=scenario['message_type'],
            hook_type='test',
            tool_name='IntegrationTest',
            timing=scenario['timing']
        )
        
        if sound_id:
            print(f"    ✅ Sound played with ID: {sound_id}")
            playback_results.append(True)
            time.sleep(1)  # Brief pause for audio to complete
        else:
            print(f"    ❌ Failed to play sound")
            playback_results.append(False)
    
    success_rate = sum(playback_results) / len(playback_results) if playback_results else 0
    print(f"  📊 Playback Success Rate: {success_rate:.1%}")
    
    return success_rate >= 0.8

def test_performance_and_caching():
    """Test sound effect performance and caching behavior."""
    print("\n⚡ Testing Performance and Caching...")
    
    if not SOUND_ENGINE_AVAILABLE:
        print("❌ Sound engine not available")
        return False
    
    engine = get_sound_effects_engine()
    
    # Test selection performance
    start_time = time.time()
    
    for i in range(10):
        context = SoundContext(
            priority=AdvancedPriority.MEDIUM,
            message_type=MessageType.INFO,
            hook_type='performance_test',
            tool_name=f'PerfTest{i}'
        )
        engine.select_sound_effect(context)
    
    selection_time = (time.time() - start_time) * 1000
    avg_selection_time = selection_time / 10
    
    print(f"  ⏱️  Average Selection Time: {avg_selection_time:.2f}ms")
    
    # Test caching effectiveness
    initial_analytics = engine.get_analytics()
    
    # Play the same sound effect multiple times
    for i in range(5):
        play_contextual_sound_effect(
            priority=AdvancedPriority.MEDIUM,
            message_type=MessageType.SUCCESS,
            hook_type='cache_test',
            tool_name='CacheTest'
        )
        time.sleep(0.2)  # Brief pause
    
    final_analytics = engine.get_analytics()
    
    cache_hits = final_analytics['cache_hits'] - initial_analytics['cache_hits']
    cache_misses = final_analytics['cache_misses'] - initial_analytics['cache_misses']
    
    print(f"  💾 Cache Hits: {cache_hits}")
    print(f"  💾 Cache Misses: {cache_misses}")
    
    if cache_hits + cache_misses > 0:
        cache_hit_rate = cache_hits / (cache_hits + cache_misses)
        print(f"  📊 Cache Hit Rate: {cache_hit_rate:.1%}")
        
        return avg_selection_time < 50 and cache_hit_rate >= 0.6  # 50ms selection, 60% cache hit rate
    
    return avg_selection_time < 50

def test_error_handling_and_fallbacks():
    """Test error handling and fallback behavior."""
    print("\n🛡️ Testing Error Handling and Fallbacks...")
    
    if not SOUND_ENGINE_AVAILABLE:
        print("❌ Sound engine not available")
        return False
    
    engine = get_sound_effects_engine()
    
    # Test with invalid/missing sound effects
    test_results = []
    
    # Test with non-existent sound effect
    try:
        fake_effect = engine.sound_library.get('non_existent_sound')
        if fake_effect:
            print("  ❌ Non-existent sound effect should be None")
            test_results.append(False)
        else:
            print("  ✅ Non-existent sound effect correctly returned None")
            test_results.append(True)
    except Exception as e:
        print(f"  ⚠️  Exception handling non-existent sound: {e}")
        test_results.append(True)  # Exception is acceptable
    
    # Test with disabled sound effects
    original_enabled = engine.enabled
    engine.enabled = False
    
    sound_id = play_contextual_sound_effect(
        priority=AdvancedPriority.MEDIUM,
        message_type=MessageType.INFO,
        hook_type='disabled_test'
    )
    
    if sound_id is None:
        print("  ✅ Disabled sound effects correctly return None")
        test_results.append(True)
    else:
        print("  ❌ Disabled sound effects should return None")
        test_results.append(False)
    
    # Restore original state
    engine.enabled = original_enabled
    
    return all(test_results)

def run_comprehensive_integration_test():
    """Run comprehensive integration test suite."""
    print("🧪 Phase 3.3 Sound Effects Integration Test Suite")
    print("=" * 60)
    
    test_results = []
    
    # Test 1: Engine initialization
    test_results.append(test_sound_engine_initialization())
    
    # Test 2: Contextual selection
    test_results.append(test_contextual_sound_selection())
    
    # Test 3: Playback integration
    test_results.append(test_sound_playback_integration())
    
    # Test 4: Performance and caching
    test_results.append(test_performance_and_caching())
    
    # Test 5: Error handling
    test_results.append(test_error_handling_and_fallbacks())
    
    # Calculate overall success rate
    passed_tests = sum(test_results)
    total_tests = len(test_results)
    success_rate = passed_tests / total_tests if total_tests > 0 else 0
    
    print(f"\n📊 Integration Test Results:")
    print(f"  Tests Passed: {passed_tests}/{total_tests}")
    print(f"  Success Rate: {success_rate:.1%}")
    
    if success_rate >= 0.8:
        print("✅ Phase 3.3 Sound Effects Integration: SUCCESSFUL")
        return True
    else:
        print("❌ Phase 3.3 Sound Effects Integration: NEEDS IMPROVEMENT")
        return False

def show_final_analytics():
    """Show final analytics and status."""
    if not SOUND_ENGINE_AVAILABLE:
        return
    
    print(f"\n📈 Final System Status:")
    engine = get_sound_effects_engine()
    
    status = engine.get_status()
    print(f"  Sound Library: {status['sound_count']} effects")
    print(f"  Active Channels: {status['active_channels']}")
    print(f"  Master Volume: {status['master_volume']}")
    
    analytics = engine.get_analytics()
    print(f"\n📊 Session Analytics:")
    print(f"  Sounds Played: {analytics['sounds_played']}")
    print(f"  Cache Hit Rate: {analytics['cache_hits']/(analytics['cache_hits']+analytics['cache_misses']):.1%}" if (analytics['cache_hits']+analytics['cache_misses']) > 0 else "  Cache Hit Rate: N/A")
    print(f"  Average Selection Time: {analytics['average_selection_time']:.2f}ms")
    print(f"  Playback Errors: {analytics['playback_errors']}")

if __name__ == "__main__":
    if "--test" in sys.argv:
        success = run_comprehensive_integration_test()
        show_final_analytics()
        
        print(f"\n{'✅ INTEGRATION SUCCESSFUL' if success else '❌ INTEGRATION NEEDS WORK'}")
        sys.exit(0 if success else 1)
    
    else:
        print("Phase 3.3 Sound Effects Integration Test")
        print("Usage: python phase3_sound_integration_test.py --test")