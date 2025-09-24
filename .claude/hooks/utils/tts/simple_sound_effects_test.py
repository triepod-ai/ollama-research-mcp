#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "pygame>=2.0.0",
#   "python-dotenv>=1.0.0",
# ]
# ///

"""
Simple Sound Effects Test
Quick validation that sound effects are working correctly with proper enum usage.
"""

import sys
import time
from pathlib import Path

# Add current directory to path
sys.path.append(str(Path(__file__).parent))

def test_sound_effects_with_enums():
    """Test sound effects using proper enum values."""
    print("🎵 Testing Sound Effects with Proper Enums...")
    
    try:
        from sound_effects_engine import (
            get_sound_effects_engine,
            play_contextual_sound_effect,
            AdvancedPriority,
            MessageType,
            SoundTiming
        )
        
        engine = get_sound_effects_engine()
        
        print(f"  Engine Status: {'✅' if engine.enabled and engine.initialized else '❌'}")
        
        if not engine.enabled or not engine.initialized:
            return False
        
        # Test with proper enum values
        test_cases = [
            (AdvancedPriority.CRITICAL, MessageType.ERROR, "Critical Error"),
            (AdvancedPriority.MEDIUM, MessageType.SUCCESS, "Success Message"),
            (AdvancedPriority.HIGH, MessageType.WARNING, "Warning Message"),
            (AdvancedPriority.LOW, MessageType.INFO, "Info Message")
        ]
        
        results = []
        for priority, msg_type, description in test_cases:
            print(f"    Testing: {description}")
            
            sound_id = play_contextual_sound_effect(
                priority=priority,
                message_type=msg_type,
                hook_type="enum_test",
                tool_name="EnumTest",
                timing=SoundTiming.PRE_TTS
            )
            
            if sound_id:
                print(f"      ✅ Sound played: {sound_id}")
                results.append(True)
                time.sleep(0.8)  # Brief pause
            else:
                print(f"      ❌ No sound played")
                results.append(False)
        
        success_rate = sum(results) / len(results) if results else 0
        print(f"  📊 Success Rate: {success_rate:.1%}")
        
        return success_rate >= 0.8
        
    except Exception as e:
        print(f"  ❌ Test failed: {e}")
        return False

def test_phase3_integration():
    """Test Phase 3 integration layer."""
    print("\n🔗 Testing Phase 3 Integration...")
    
    try:
        from phase3_integration import get_phase3_integrator
        
        integrator = get_phase3_integrator()
        
        print(f"  ✅ Integration layer loaded")
        print(f"  Sound Effects Feature: {integrator.features.sound_effects}")
        
        # Test message processing
        should_speak, processed = integrator.process_tts_message(
            original_message="Test error message with sound effects",
            hook_type="test",
            tool_name="TestTool",
            event_category="error",
            event_priority=1
        )
        
        print(f"  Should Speak: {should_speak}")
        print(f"  Message Length: {len(processed)}")
        
        # Check if sound effects were played
        sound_effects_count = integrator.stats.get("sound_effects_played", 0)
        print(f"  🔊 Sound Effects Played: {sound_effects_count}")
        
        return should_speak and sound_effects_count > 0
        
    except Exception as e:
        print(f"  ❌ Integration test failed: {e}")
        return False

def main():
    """Run simple sound effects validation."""
    print("🧪 Simple Sound Effects Validation Test")
    print("=" * 50)
    
    test1 = test_sound_effects_with_enums()
    test2 = test_phase3_integration()
    
    if test1 and test2:
        print("\n✅ SOUND EFFECTS INTEGRATION SUCCESSFUL!")
        print("🎵 All systems operational")
        return True
    else:
        print("\n⚠️ Some issues detected")
        if test1:
            print("✅ Sound Effects Engine: Working")
        else:
            print("❌ Sound Effects Engine: Issues")
            
        if test2:
            print("✅ Phase 3 Integration: Working")
        else:
            print("❌ Phase 3 Integration: Issues")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)