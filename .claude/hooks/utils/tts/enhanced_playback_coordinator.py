#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "pygame>=2.0.0",
#   "python-dotenv>=1.0.0",
# ]
# ///

"""
Phase 3.3 Enhanced Playback Coordinator with Sound Effects Integration
Extended playback coordination system with contextual sound effects and audio mixing.

Features:
- Complete sound effects integration with existing TTS coordination
- Pre/post TTS sound effect orchestration with intelligent timing
- Contextual sound selection based on message type and priority
- Audio mixing capabilities for enhanced user experience
- Backward compatibility with existing Phase 3 systems
- Performance optimization with sound effect caching
"""

import asyncio
import os
import subprocess
import threading
import time
import json
import random
from collections import deque, defaultdict
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

# Import existing systems
try:
    try:
        from .playback_coordinator import (
            PlaybackCoordinator as BasePlaybackCoordinator,
            get_playback_coordinator as get_base_playback_coordinator,
            ProviderType, ProviderHealth, PlaybackState, AudioStream
        )
    except ImportError:
        from playback_coordinator import (
            PlaybackCoordinator as BasePlaybackCoordinator,
            get_playback_coordinator as get_base_playback_coordinator,
            ProviderType, ProviderHealth, PlaybackState, AudioStream
        )
    BASE_COORDINATOR_AVAILABLE = True
except ImportError:
    BASE_COORDINATOR_AVAILABLE = False

# Import sound effects engine
try:
    try:
        from .sound_effects_engine import (
            get_sound_effects_engine,
            SoundEffectsEngine,
            play_contextual_sound_effect,
            SoundContext,
            SoundTiming,
            SoundTheme
        )
    except ImportError:
        from sound_effects_engine import (
            get_sound_effects_engine,
            SoundEffectsEngine, 
            play_contextual_sound_effect,
            SoundContext,
            SoundTiming,
            SoundTheme
        )
    SOUND_EFFECTS_AVAILABLE = True
except ImportError:
    SOUND_EFFECTS_AVAILABLE = False

# Import advanced queue system
try:
    try:
        from .advanced_priority_queue import (
            AdvancedTTSMessage,
            AdvancedPriority,
            MessageType
        )
    except ImportError:
        from advanced_priority_queue import (
            AdvancedTTSMessage,
            AdvancedPriority,
            MessageType
        )
    ADVANCED_QUEUE_AVAILABLE = True
except ImportError:
    ADVANCED_QUEUE_AVAILABLE = False

class SoundEffectTiming(Enum):
    """Enhanced timing options for sound effects."""
    DISABLED = "disabled"           # No sound effects
    PRE_ONLY = "pre_only"          # Only before TTS
    POST_ONLY = "post_only"        # Only after TTS
    PRE_AND_POST = "pre_and_post"  # Before and after TTS
    CONTEXTUAL = "contextual"      # Intelligent selection based on message

class AudioMixingStrategy(Enum):
    """Audio mixing strategies for enhanced playback."""
    SEQUENTIAL = "sequential"       # Sound effect, then TTS
    PARALLEL_BACKGROUND = "parallel_bg"  # Background sound during TTS
    LAYERED = "layered"            # Complex audio layering
    ADAPTIVE = "adaptive"          # Adapt based on content and context

@dataclass
class EnhancedPlaybackRequest:
    """Enhanced playback request with sound effect options."""
    message: AdvancedTTSMessage
    callback: Optional[Callable] = None
    
    # Sound effect options
    sound_effect_timing: SoundEffectTiming = SoundEffectTiming.CONTEXTUAL
    mixing_strategy: AudioMixingStrategy = AudioMixingStrategy.SEQUENTIAL
    sound_theme_override: Optional[SoundTheme] = None
    sound_volume_override: Optional[float] = None
    disable_sound_effects: bool = False
    
    # Advanced options
    pre_tts_delay_ms: int = 100     # Delay after pre-TTS sound
    post_tts_delay_ms: int = 50     # Delay before post-TTS sound
    force_sound_effect: Optional[str] = None  # Force specific sound effect
    
    # Request metadata
    request_id: str = field(default_factory=lambda: f"enhanced_{int(time.time()*1000)}")
    created_at: datetime = field(default_factory=datetime.now)

@dataclass
class EnhancedPlaybackResult:
    """Result of enhanced playback with sound effect details."""
    success: bool
    request_id: str
    stream_id: Optional[str] = None
    
    # Sound effect details
    pre_tts_sound_played: bool = False
    post_tts_sound_played: bool = False
    sound_effect_names: List[str] = field(default_factory=list)
    
    # Timing information
    total_duration_ms: float = 0.0
    tts_duration_ms: float = 0.0
    sound_effects_duration_ms: float = 0.0
    
    # Error information
    error_message: str = ""
    fallback_used: bool = False

class EnhancedPlaybackCoordinator:
    """Enhanced playback coordinator with integrated sound effects."""
    
    def __init__(self):
        """Initialize the enhanced playback coordinator."""
        # Base coordinator
        if BASE_COORDINATOR_AVAILABLE:
            self.base_coordinator = get_base_playback_coordinator()
        else:
            self.base_coordinator = None
        
        # Sound effects engine
        if SOUND_EFFECTS_AVAILABLE:
            self.sound_engine = get_sound_effects_engine()
        else:
            self.sound_engine = None
        
        # Configuration
        self.enable_sound_effects = os.getenv("TTS_SOUND_EFFECTS_ENABLED", "true").lower() == "true"
        self.default_timing = SoundEffectTiming(os.getenv("TTS_SOUND_TIMING", "contextual"))
        self.default_mixing = AudioMixingStrategy(os.getenv("TTS_MIXING_STRATEGY", "sequential"))
        self.sound_effect_volume = float(os.getenv("TTS_SOUND_EFFECT_VOLUME", "0.6"))
        
        # Performance settings
        self.enable_parallel_processing = os.getenv("TTS_PARALLEL_SOUND_PROCESSING", "true").lower() == "true"
        self.sound_effect_timeout = float(os.getenv("TTS_SOUND_EFFECT_TIMEOUT", "2.0"))
        
        # State management
        self.active_requests: Dict[str, EnhancedPlaybackRequest] = {}
        self.request_lock = threading.RLock()
        self.executor = ThreadPoolExecutor(max_workers=6, thread_name_prefix="enhanced_playback")
        
        # Analytics
        self.analytics = {
            "total_requests": 0,
            "sound_effects_played": 0,
            "pre_tts_sounds": 0,
            "post_tts_sounds": 0,
            "fallback_usage": 0,
            "average_total_duration": 0.0,
            "sound_effect_success_rate": 0.0,
        }
        
        print(f"🎵 Enhanced Playback Coordinator initialized")
        print(f"  Sound Effects: {'✅ Enabled' if self.enable_sound_effects and self.sound_engine else '❌ Disabled'}")
        print(f"  Base Coordinator: {'✅ Available' if self.base_coordinator else '❌ Unavailable'}")
    
    def play_enhanced_message(self, request: EnhancedPlaybackRequest) -> EnhancedPlaybackResult:
        """
        Play TTS message with enhanced sound effects coordination.
        
        Args:
            request: Enhanced playback request with sound effect options
            
        Returns:
            Enhanced playback result with detailed information
        """
        start_time = time.time()
        
        # Initialize result
        result = EnhancedPlaybackResult(
            success=False,
            request_id=request.request_id
        )
        
        with self.request_lock:
            self.active_requests[request.request_id] = request
        
        try:
            self.analytics["total_requests"] += 1
            
            # Determine sound effect strategy
            sound_strategy = self._determine_sound_strategy(request)
            
            # Execute playback with sound effects
            if sound_strategy == SoundEffectTiming.PRE_ONLY or sound_strategy == SoundEffectTiming.PRE_AND_POST:
                result.pre_tts_sound_played = self._play_pre_tts_sound(request, result)
            
            # Play main TTS message
            tts_start = time.time()
            stream_id = self._play_tts_message(request)
            tts_duration = (time.time() - tts_start) * 1000
            
            if stream_id:
                result.stream_id = stream_id
                result.success = True
                result.tts_duration_ms = tts_duration
            
            # Post-TTS sound effects
            if (sound_strategy == SoundEffectTiming.POST_ONLY or 
                sound_strategy == SoundEffectTiming.PRE_AND_POST) and result.success:
                result.post_tts_sound_played = self._play_post_tts_sound(request, result)
            
            # Update analytics
            self._update_analytics(result)
            
        except Exception as e:
            result.error_message = str(e)
            result.success = False
            print(f"❌ Enhanced playback failed for {request.request_id}: {e}")
        
        finally:
            # Calculate total duration
            result.total_duration_ms = (time.time() - start_time) * 1000
            
            # Cleanup
            with self.request_lock:
                if request.request_id in self.active_requests:
                    del self.active_requests[request.request_id]
        
        return result
    
    def _determine_sound_strategy(self, request: EnhancedPlaybackRequest) -> SoundEffectTiming:
        """Determine the optimal sound effect strategy for the request."""
        if not self.enable_sound_effects or request.disable_sound_effects:
            return SoundEffectTiming.DISABLED
        
        if request.sound_effect_timing != SoundEffectTiming.CONTEXTUAL:
            return request.sound_effect_timing
        
        # Contextual decision based on message properties
        message = request.message
        
        # High priority messages get pre-TTS attention sound
        if message.priority in [AdvancedPriority.INTERRUPT, AdvancedPriority.CRITICAL]:
            return SoundEffectTiming.PRE_ONLY
        
        # Success messages get post-TTS confirmation sound
        if message.message_type == MessageType.SUCCESS:
            return SoundEffectTiming.POST_ONLY
        
        # Error messages get both pre and post sounds
        if message.message_type == MessageType.ERROR:
            return SoundEffectTiming.PRE_AND_POST
        
        # Batch messages get post-completion sound
        if message.message_type == MessageType.BATCH:
            return SoundEffectTiming.POST_ONLY
        
        # Default: pre-TTS for attention
        return SoundEffectTiming.PRE_ONLY
    
    def _play_pre_tts_sound(self, request: EnhancedPlaybackRequest, result: EnhancedPlaybackResult) -> bool:
        """Play pre-TTS sound effect."""
        if not self.sound_engine:
            return False
        
        try:
            # Create sound context
            context = SoundContext(
                message=request.message,
                timing=SoundTiming.PRE_TTS,
                theme_override=request.sound_theme_override,
                volume_override=request.sound_volume_override or self.sound_effect_volume
            )
            
            # Play contextual sound effect
            sound_id = None
            if request.force_sound_effect:
                # Force specific sound effect (for testing/debugging)
                effect = self.sound_engine.sound_library.get(request.force_sound_effect)
                if effect:
                    sound_id = self.sound_engine.play_sound_effect(effect, context)
            else:
                # Use contextual selection
                sound_id = play_contextual_sound_effect(
                    message=request.message,
                    timing=SoundTiming.PRE_TTS,
                    theme_override=request.sound_theme_override,
                    volume_override=request.sound_volume_override or self.sound_effect_volume
                )
            
            if sound_id:
                result.sound_effect_names.append(f"pre_tts_{sound_id}")
                self.analytics["pre_tts_sounds"] += 1
                
                # Wait for pre-TTS delay
                if request.pre_tts_delay_ms > 0:
                    time.sleep(request.pre_tts_delay_ms / 1000)
                
                return True
            
        except Exception as e:
            print(f"⚠️  Pre-TTS sound effect failed: {e}")
        
        return False
    
    def _play_post_tts_sound(self, request: EnhancedPlaybackRequest, result: EnhancedPlaybackResult) -> bool:
        """Play post-TTS sound effect."""
        if not self.sound_engine:
            return False
        
        try:
            # Wait for post-TTS delay
            if request.post_tts_delay_ms > 0:
                time.sleep(request.post_tts_delay_ms / 1000)
            
            # Create sound context
            context = SoundContext(
                message=request.message,
                timing=SoundTiming.POST_TTS,
                theme_override=request.sound_theme_override,
                volume_override=request.sound_volume_override or self.sound_effect_volume
            )
            
            # Play contextual sound effect
            sound_id = play_contextual_sound_effect(
                message=request.message,
                timing=SoundTiming.POST_TTS,
                theme_override=request.sound_theme_override,
                volume_override=request.sound_volume_override or self.sound_effect_volume
            )
            
            if sound_id:
                result.sound_effect_names.append(f"post_tts_{sound_id}")
                self.analytics["post_tts_sounds"] += 1
                return True
            
        except Exception as e:
            print(f"⚠️  Post-TTS sound effect failed: {e}")
        
        return False
    
    def _play_tts_message(self, request: EnhancedPlaybackRequest) -> Optional[str]:
        """Play the main TTS message using base coordinator."""
        if not self.base_coordinator:
            # Fallback to basic TTS if base coordinator unavailable
            return self._fallback_tts_playback(request)
        
        try:
            # Use base coordinator for TTS playback
            return self.base_coordinator.play_message(
                message=request.message,
                callback=request.callback
            )
        except Exception as e:
            print(f"⚠️  Base coordinator TTS failed, using fallback: {e}")
            return self._fallback_tts_playback(request)
    
    def _fallback_tts_playback(self, request: EnhancedPlaybackRequest) -> Optional[str]:
        """Fallback TTS playback using direct speak command."""
        try:
            cmd = ["speak", request.message.content]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                self.analytics["fallback_usage"] += 1
                return f"fallback_{int(time.time()*1000)}"
            else:
                print(f"❌ Fallback TTS failed: {result.stderr}")
                
        except Exception as e:
            print(f"❌ Fallback TTS error: {e}")
        
        return None
    
    def _update_analytics(self, result: EnhancedPlaybackResult):
        """Update analytics based on playback result."""
        if result.pre_tts_sound_played or result.post_tts_sound_played:
            self.analytics["sound_effects_played"] += 1
        
        # Update average total duration
        current_avg = self.analytics["average_total_duration"]
        total_count = self.analytics["total_requests"]
        self.analytics["average_total_duration"] = (
            current_avg * (total_count - 1) + result.total_duration_ms
        ) / total_count
        
        # Update sound effect success rate
        if self.analytics["total_requests"] > 0:
            self.analytics["sound_effect_success_rate"] = (
                self.analytics["sound_effects_played"] / self.analytics["total_requests"]
            )
    
    def play_message_enhanced(self, message: AdvancedTTSMessage, 
                            callback: Optional[Callable] = None,
                            **kwargs) -> EnhancedPlaybackResult:
        """
        Convenience method for playing message with enhanced features.
        
        Args:
            message: TTS message to play
            callback: Optional completion callback
            **kwargs: Additional enhancement options
            
        Returns:
            Enhanced playback result
        """
        request = EnhancedPlaybackRequest(
            message=message,
            callback=callback,
            **kwargs
        )
        
        return self.play_enhanced_message(request)
    
    def get_status(self) -> Dict[str, Any]:
        """Get comprehensive enhanced coordinator status."""
        return {
            "enhanced_coordinator": {
                "sound_effects_enabled": self.enable_sound_effects,
                "sound_engine_available": self.sound_engine is not None,
                "base_coordinator_available": self.base_coordinator is not None,
                "active_requests": len(self.active_requests),
                "analytics": dict(self.analytics)
            },
            "sound_engine_status": self.sound_engine.get_status() if self.sound_engine else None,
            "base_coordinator_status": self.base_coordinator.get_status() if self.base_coordinator else None
        }
    
    def get_analytics(self) -> Dict[str, Any]:
        """Get detailed analytics."""
        return dict(self.analytics)
    
    def stop_all_playback(self):
        """Stop all active playback including sound effects."""
        # Stop sound effects
        if self.sound_engine:
            self.sound_engine.stop_all_sounds()
        
        # Stop base coordinator playback
        if self.base_coordinator:
            try:
                # This method may not exist in base coordinator
                if hasattr(self.base_coordinator, 'stop_all_streams'):
                    self.base_coordinator.stop_all_streams()
            except Exception as e:
                print(f"⚠️  Failed to stop base coordinator streams: {e}")
        
        # Clear active requests
        with self.request_lock:
            self.active_requests.clear()

# Global enhanced coordinator instance
_enhanced_coordinator = None

def get_enhanced_playback_coordinator() -> EnhancedPlaybackCoordinator:
    """Get or create the global enhanced playback coordinator."""
    global _enhanced_coordinator
    if _enhanced_coordinator is None:
        _enhanced_coordinator = EnhancedPlaybackCoordinator()
    return _enhanced_coordinator

def play_message_with_sound_effects(message: AdvancedTTSMessage,
                                   callback: Optional[Callable] = None,
                                   **kwargs) -> EnhancedPlaybackResult:
    """
    Play TTS message with integrated sound effects.
    
    Args:
        message: TTS message to play
        callback: Optional completion callback
        **kwargs: Enhancement options (sound_effect_timing, mixing_strategy, etc.)
        
    Returns:
        Enhanced playback result with sound effect details
    """
    coordinator = get_enhanced_playback_coordinator()
    return coordinator.play_message_enhanced(message, callback, **kwargs)

def get_enhanced_coordinator_status() -> Dict[str, Any]:
    """Get enhanced coordinator status."""
    coordinator = get_enhanced_playback_coordinator()
    return coordinator.get_status()

if __name__ == "__main__":
    # Test the enhanced playback coordinator
    import sys
    
    if "--test" in sys.argv:
        print("🎵 Testing Enhanced Playback Coordinator")
        print("=" * 60)
        
        coordinator = get_enhanced_playback_coordinator()
        
        # Show status
        print("📊 Coordinator Status:")
        status = coordinator.get_status()
        enhanced_status = status["enhanced_coordinator"]
        print(f"  Sound Effects: {'✅' if enhanced_status['sound_effects_enabled'] else '❌'}")
        print(f"  Sound Engine: {'✅' if enhanced_status['sound_engine_available'] else '❌'}")
        print(f"  Base Coordinator: {'✅' if enhanced_status['base_coordinator_available'] else '❌'}")
        
        if ADVANCED_QUEUE_AVAILABLE:
            # Test enhanced playback
            print("\n🎤 Testing Enhanced Playback:")
            
            test_messages = [
                (AdvancedTTSMessage(
                    "Testing error message with sound effects",
                    AdvancedPriority.CRITICAL,
                    MessageType.ERROR,
                    hook_type="test",
                    tool_name="EnhancedTest"
                ), "error message"),
                
                (AdvancedTTSMessage(
                    "Testing success message with sound effects",
                    AdvancedPriority.MEDIUM,
                    MessageType.SUCCESS,
                    hook_type="test",
                    tool_name="EnhancedTest"
                ), "success message"),
                
                (AdvancedTTSMessage(
                    "Testing info message with sound effects",
                    AdvancedPriority.LOW,
                    MessageType.INFO,
                    hook_type="test",
                    tool_name="EnhancedTest"
                ), "info message")
            ]
            
            for message, description in test_messages:
                print(f"  Testing {description}...")
                
                result = coordinator.play_message_enhanced(
                    message,
                    sound_effect_timing=SoundEffectTiming.PRE_AND_POST
                )
                
                print(f"    ✅ Result: Success={result.success}")
                print(f"    🔊 Pre-TTS Sound: {result.pre_tts_sound_played}")
                print(f"    🔊 Post-TTS Sound: {result.post_tts_sound_played}")
                print(f"    ⏱️  Total Duration: {result.total_duration_ms:.1f}ms")
                if result.sound_effect_names:
                    print(f"    🎵 Sound Effects: {', '.join(result.sound_effect_names)}")
                
                time.sleep(2)  # Brief pause between tests
            
            # Show final analytics
            print("\n📊 Final Analytics:")
            analytics = coordinator.get_analytics()
            for key, value in analytics.items():
                print(f"  {key}: {value}")
        
        else:
            print("⚠️  Advanced queue not available for testing")
        
        print("\n✅ Enhanced Playback Coordinator test completed")
    
    else:
        print("Enhanced Playbook Coordinator with Sound Effects - Phase 3.3")
        print("Usage: python enhanced_playback_coordinator.py --test")