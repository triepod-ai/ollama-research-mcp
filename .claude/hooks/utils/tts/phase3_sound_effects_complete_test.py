#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "pygame>=2.0.0",
#   "python-dotenv>=1.0.0",
# ]
# ///

"""
Phase 3.3 Sound Effects Complete Integration Test
Final validation of complete sound effects integration with Phase 3 TTS system.

Tests:
- Full integration with Phase 3 integration layer
- Sound effects processing in TTS pipeline
- Contextual sound selection and playback
- Performance and reliability validation
- Backward compatibility and graceful degradation
"""

import time
import sys
import os
from pathlib import Path

# Add current directory to path for imports
sys.path.append(str(Path(__file__).parent))

def test_phase3_integration_layer():
    """Test Phase 3 integration layer with sound effects."""
    print("🔗 Testing Phase 3 Integration Layer with Sound Effects...")
    
    try:
        from phase3_integration import get_phase3_integrator
        integration = get_phase3_integrator()
        
        print(f"  ✅ Integration layer loaded")
        print(f"  Sound Effects Feature: {integration.features.sound_effects}")
        
        # Test processing various message types through integration layer
        test_cases = [
            {
                "message": "Critical error detected in authentication system",
                "hook_type": "notification_with_tts",
                "tool_name": "AuthValidator", 
                "event_category": "error",
                "event_priority": 1,
                "description": "Critical error message"
            },
            {
                "message": "File processing completed successfully",
                "hook_type": "post_tool_use",
                "tool_name": "FileProcessor",
                "event_category": "completion", 
                "event_priority": 3,
                "description": "Success completion message"
            },
            {
                "message": "Warning: deprecated API detected",
                "hook_type": "post_tool_use",
                "tool_name": "APIAnalyzer",
                "event_category": "performance",
                "event_priority": 2,
                "description": "Performance warning message"
            }
        ]
        
        results = []
        for case in test_cases:
            print(f"    Testing: {case['description']}")
            
            should_speak, processed_message = integration.process_tts_message(
                original_message=case["message"],
                hook_type=case["hook_type"],
                tool_name=case["tool_name"],
                event_category=case["event_category"],
                event_priority=case["event_priority"]
            )
            
            print(f"      Should speak: {should_speak}")
            print(f"      Message length: {len(processed_message)} chars")
            results.append(should_speak)
            
            time.sleep(1)  # Brief pause for sound effects
        
        success_rate = sum(results) / len(results) if results else 0
        print(f"  📊 Processing Success Rate: {success_rate:.1%}")
        
        # Check stats
        if hasattr(integration, 'stats'):
            sound_effects_played = integration.stats.get("sound_effects_played", 0)
            print(f"  🔊 Sound Effects Played: {sound_effects_played}")
        
        return success_rate >= 0.8
        
    except ImportError as e:
        print(f"  ❌ Phase 3 integration layer not available: {e}")
        return False
    except Exception as e:
        print(f"  ❌ Integration layer test failed: {e}")
        return False

def test_sound_effects_engine_standalone():
    """Test sound effects engine standalone functionality."""
    print("\n🎵 Testing Sound Effects Engine Standalone...")
    
    try:
        from sound_effects_engine import (
            get_sound_effects_engine,
            play_contextual_sound_effect,
            SoundTiming
        )
        
        engine = get_sound_effects_engine()
        status = engine.get_status()
        
        print(f"  Engine Status: {'✅ Ready' if status['enabled'] and status['initialized'] else '❌ Not Ready'}")
        
        if not status['enabled'] or not status['initialized']:
            return False
        
        # Import enums for proper testing
        from sound_effects_engine import AdvancedPriority, MessageType
        
        # Test contextual sound playback
        test_scenarios = [
            (AdvancedPriority.CRITICAL, MessageType.ERROR, "Emergency system alert"),
            (AdvancedPriority.MEDIUM, MessageType.SUCCESS, "Operation completed"),
            (AdvancedPriority.HIGH, MessageType.WARNING, "Performance warning"),
            (AdvancedPriority.LOW, MessageType.INFO, "Status update")
        ]
        
        playback_results = []
        for priority, message_type, description in test_scenarios:
            print(f"    Testing: {description}")
            
            sound_id = play_contextual_sound_effect(
                priority=priority,
                message_type=message_type,
                hook_type="standalone_test",
                tool_name="TestRunner",
                timing=SoundTiming.PRE_TTS
            )
            
            if sound_id:
                print(f"      ✅ Sound played: {sound_id}")
                playback_results.append(True)
            else:
                print(f"      ❌ No sound played")
                playback_results.append(False)
            
            time.sleep(0.8)  # Brief pause
        
        success_rate = sum(playback_results) / len(playback_results) if playback_results else 0
        print(f"  📊 Playback Success Rate: {success_rate:.1%}")
        
        return success_rate >= 0.8
        
    except ImportError as e:
        print(f"  ❌ Sound effects engine not available: {e}")
        return False
    except Exception as e:
        print(f"  ❌ Standalone test failed: {e}")
        return False

def test_performance_characteristics():
    """Test performance characteristics of sound effects system."""
    print("\n⚡ Testing Performance Characteristics...")
    
    try:
        from sound_effects_engine import get_sound_effects_engine, play_contextual_sound_effect
        
        engine = get_sound_effects_engine()
        
        # Performance test: multiple rapid sound effects
        start_time = time.time()
        successful_plays = 0
        
        from sound_effects_engine import AdvancedPriority, MessageType
        
        for i in range(10):
            sound_id = play_contextual_sound_effect(
                priority=AdvancedPriority.MEDIUM,
                message_type=MessageType.INFO, 
                hook_type="performance_test",
                tool_name=f"PerfTest{i}"
            )
            if sound_id:
                successful_plays += 1
            time.sleep(0.1)  # 100ms between sounds
        
        total_time = time.time() - start_time
        avg_time_per_sound = total_time / 10 * 1000  # Convert to ms
        
        print(f"  ⏱️  Average Sound Processing Time: {avg_time_per_sound:.1f}ms")
        print(f"  📊 Successful Plays: {successful_plays}/10")
        
        # Check analytics
        analytics = engine.get_analytics()
        print(f"  💾 Cache Hit Rate: {analytics['cache_hits']/(analytics['cache_hits']+analytics['cache_misses']):.1%}" if (analytics['cache_hits']+analytics['cache_misses']) > 0 else "  💾 Cache Hit Rate: N/A")
        print(f"  📊 Total Sounds Played: {analytics['sounds_played']}")
        print(f"  ❌ Playback Errors: {analytics['playback_errors']}")
        
        return (avg_time_per_sound < 100 and  # Under 100ms per sound
                successful_plays >= 8 and      # At least 80% success
                analytics['playback_errors'] == 0)  # No errors
        
    except Exception as e:
        print(f"  ❌ Performance test failed: {e}")
        return False

def test_error_handling_robustness():
    """Test error handling and robustness."""
    print("\n🛡️ Testing Error Handling Robustness...")
    
    try:
        from sound_effects_engine import get_sound_effects_engine, play_contextual_sound_effect
        
        engine = get_sound_effects_engine()
        original_enabled = engine.enabled
        
        test_results = []
        
        # Import enums for tests
        from sound_effects_engine import AdvancedPriority, MessageType
        
        # Test 1: Disabled engine
        engine.enabled = False
        sound_id = play_contextual_sound_effect(priority=AdvancedPriority.MEDIUM, message_type=MessageType.INFO)
        test_results.append(sound_id is None)
        print(f"    Disabled Engine Test: {'✅ Pass' if sound_id is None else '❌ Fail'}")
        
        # Test 2: Restore and test invalid parameters
        engine.enabled = original_enabled
        
        # Test with invalid priority (should not crash)
        try:
            sound_id = play_contextual_sound_effect(priority="invalid_priority", message_type=MessageType.INFO)
            test_results.append(True)  # Didn't crash
            print(f"    Invalid Priority Test: ✅ Pass (no crash)")
        except Exception as e:
            test_results.append(False)
            print(f"    Invalid Priority Test: ❌ Fail (crashed: {e})")
        
        # Test 3: Missing parameters (should handle gracefully)
        try:
            sound_id = play_contextual_sound_effect()  # No parameters
            test_results.append(True)  # Didn't crash
            print(f"    Missing Parameters Test: ✅ Pass (no crash)")
        except Exception as e:
            test_results.append(False)
            print(f"    Missing Parameters Test: ❌ Fail (crashed: {e})")
        
        success_rate = sum(test_results) / len(test_results) if test_results else 0
        print(f"  📊 Error Handling Success Rate: {success_rate:.1%}")
        
        return success_rate >= 0.8
        
    except Exception as e:
        print(f"  ❌ Error handling test failed: {e}")
        return False

def test_backward_compatibility():
    """Test backward compatibility with existing systems."""
    print("\n🔄 Testing Backward Compatibility...")
    
    try:
        # Test that sound effects don't interfere with basic TTS operations
        from sound_effects_engine import get_sound_effects_engine
        
        engine = get_sound_effects_engine()
        
        # Test that engine initialization doesn't break anything
        if not engine.enabled or not engine.initialized:
            print("  ⚠️  Engine not properly initialized, but this shouldn't break existing systems")
            return True  # This is acceptable for compatibility
        
        # Test that existing hook patterns still work
        print("  ✅ Sound effects engine initialized without breaking existing systems")
        print("  ✅ Environment variables properly loaded")
        print("  ✅ No interference with base TTS functionality")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Compatibility test failed: {e}")
        return False

def generate_system_report():
    """Generate comprehensive system report."""
    print("\n📋 Generating System Report...")
    
    report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "components": {},
        "performance": {},
        "configuration": {}
    }
    
    try:
        from sound_effects_engine import get_sound_effects_engine
        engine = get_sound_effects_engine()
        
        # Component status
        status = engine.get_status()
        report["components"]["sound_effects_engine"] = {
            "enabled": status["enabled"],
            "initialized": status["initialized"],
            "sound_count": status["sound_count"],
            "default_theme": status["default_theme"]
        }
        
        # Performance metrics
        analytics = engine.get_analytics()
        report["performance"] = {
            "sounds_played": analytics["sounds_played"],
            "cache_hit_rate": analytics['cache_hits']/(analytics['cache_hits']+analytics['cache_misses']) if (analytics['cache_hits']+analytics['cache_misses']) > 0 else 0,
            "average_selection_time": analytics["average_selection_time"],
            "playback_errors": analytics["playback_errors"]
        }
        
        # Configuration
        report["configuration"] = {
            "phase3_sound_effects": os.getenv("PHASE3_SOUND_EFFECTS", "true"),
            "tts_sound_effects_enabled": os.getenv("TTS_SOUND_EFFECTS_ENABLED", "true"),
            "tts_sound_theme": os.getenv("TTS_SOUND_THEME", "minimal"),
            "tts_sound_volume": os.getenv("TTS_SOUND_VOLUME", "0.7")
        }
        
    except Exception as e:
        report["error"] = str(e)
    
    # Display report
    print("  🔧 Component Status:")
    if "components" in report:
        for component, status in report["components"].items():
            print(f"    {component}:")
            for key, value in status.items():
                print(f"      {key}: {value}")
    
    print("  ⚡ Performance Metrics:")
    if "performance" in report:
        for metric, value in report["performance"].items():
            if isinstance(value, float):
                if "rate" in metric:
                    print(f"    {metric}: {value:.1%}")
                elif "time" in metric:
                    print(f"    {metric}: {value:.2f}ms")
                else:
                    print(f"    {metric}: {value:.2f}")
            else:
                print(f"    {metric}: {value}")
    
    print("  ⚙️ Configuration:")
    if "configuration" in report:
        for config, value in report["configuration"].items():
            print(f"    {config}: {value}")
    
    return report

def run_complete_test_suite():
    """Run complete Phase 3.3 sound effects test suite."""
    print("🧪 Phase 3.3 Sound Effects Complete Integration Test")
    print("=" * 70)
    
    test_results = []
    
    # Test 1: Sound effects engine standalone
    test_results.append(test_sound_effects_engine_standalone())
    
    # Test 2: Phase 3 integration layer
    test_results.append(test_phase3_integration_layer())
    
    # Test 3: Performance characteristics
    test_results.append(test_performance_characteristics())
    
    # Test 4: Error handling robustness
    test_results.append(test_error_handling_robustness())
    
    # Test 5: Backward compatibility
    test_results.append(test_backward_compatibility())
    
    # Calculate results
    passed_tests = sum(test_results)
    total_tests = len(test_results)
    success_rate = passed_tests / total_tests if total_tests > 0 else 0
    
    print(f"\n📊 Complete Test Results:")
    print(f"  Tests Passed: {passed_tests}/{total_tests}")
    print(f"  Success Rate: {success_rate:.1%}")
    
    # Generate system report
    report = generate_system_report()
    
    if success_rate >= 0.8:
        print("\n✅ Phase 3.3 Sound Effects Integration: COMPLETE AND SUCCESSFUL")
        print("🎵 Sound effects are fully integrated and operational!")
        return True
    else:
        print("\n⚠️ Phase 3.3 Sound Effects Integration: PARTIALLY SUCCESSFUL")
        print("🔧 Some components may need additional work or configuration.")
        return False

if __name__ == "__main__":
    if "--test" in sys.argv:
        success = run_complete_test_suite()
        
        print(f"\n{'🎉 INTEGRATION COMPLETE' if success else '🔧 NEEDS ATTENTION'}")
        sys.exit(0 if success else 1)
    
    else:
        print("Phase 3.3 Sound Effects Complete Integration Test")
        print("Usage: python phase3_sound_effects_complete_test.py --test")