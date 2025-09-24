#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "pygame>=2.0.0",
#   "python-dotenv>=1.0.0",
# ]
# ///

"""
Phase 3.3 Sound Effects Engine
Advanced sound effects and audio enhancement system for TTS coordination.

Features:
- Contextual sound effect selection based on message type and priority
- Pre/post TTS sound effect integration with existing playback coordinator
- Sound effect library management with customizable themes
- Volume normalization and audio processing
- Integration with Phase 3 advanced coordination systems
- Efficient audio caching and resource management
"""

import os
import pygame
import threading
import time
import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Callable
from dotenv import load_dotenv

# Import Phase 3 components
try:
    try:
        from .advanced_priority_queue import AdvancedTTSMessage, AdvancedPriority, MessageType
    except ImportError:
        from advanced_priority_queue import AdvancedTTSMessage, AdvancedPriority, MessageType
    ADVANCED_QUEUE_AVAILABLE = True
except ImportError:
    ADVANCED_QUEUE_AVAILABLE = False
    # Define fallback enums
    class AdvancedPriority(Enum):
        INTERRUPT = 0
        CRITICAL = 1
        HIGH = 2
        MEDIUM = 3
        LOW = 4
        BACKGROUND = 5
    
    class MessageType(Enum):
        ERROR = "error"
        WARNING = "warning"
        SUCCESS = "success"
        INFO = "info"
        BATCH = "batch"
        INTERRUPT = "interrupt"

# Load environment variables
env_path = Path.home() / "brainpods" / ".env"
if env_path.exists():
    load_dotenv(env_path)

class SoundTheme(Enum):
    """Sound effect themes."""
    MINIMAL = "minimal"          # Subtle, non-intrusive sounds
    PROFESSIONAL = "professional" # Business-appropriate notifications
    GAMING = "gaming"            # Engaging, dynamic sounds  
    RETRO = "retro"             # Classic computer sounds
    NATURE = "nature"           # Organic, calming sounds
    CUSTOM = "custom"           # User-defined sound set

class SoundTiming(Enum):
    """When to play sound effects relative to TTS."""
    PRE_TTS = "pre_tts"         # Before TTS message
    POST_TTS = "post_tts"       # After TTS message
    CONCURRENT = "concurrent"    # During TTS (background)
    REPLACE_TTS = "replace_tts"  # Instead of TTS (sound only)

class AudioFormat(Enum):
    """Supported audio formats."""
    WAV = "wav"
    MP3 = "mp3"
    OGG = "ogg"
    FLAC = "flac"

@dataclass
class SoundEffect:
    """Represents a sound effect with metadata."""
    name: str
    file_path: Path
    theme: SoundTheme
    volume: float = 1.0              # 0.0-1.0
    duration_ms: Optional[int] = None
    loop_count: int = 0              # 0 = play once, -1 = infinite
    fade_in_ms: int = 0
    fade_out_ms: int = 0
    priority_boost: float = 0.0      # Adjust priority for this effect
    
    # Contextual usage
    message_types: List[MessageType] = field(default_factory=list)
    priority_levels: List[AdvancedPriority] = field(default_factory=list)
    hook_types: List[str] = field(default_factory=list)
    tool_patterns: List[str] = field(default_factory=list)
    
    # Metadata
    description: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    usage_count: int = 0
    last_used: Optional[datetime] = None

@dataclass
class SoundContext:
    """Context information for sound effect selection."""
    message: Optional[AdvancedTTSMessage] = None
    priority: AdvancedPriority = AdvancedPriority.MEDIUM
    message_type: MessageType = MessageType.INFO
    hook_type: str = ""
    tool_name: str = ""
    timing: SoundTiming = SoundTiming.PRE_TTS
    theme_override: Optional[SoundTheme] = None
    volume_override: Optional[float] = None
    disable_effects: bool = False

@dataclass
class PlaybackRequest:
    """Request to play sound effect with TTS coordination."""
    sound_effect: SoundEffect
    context: SoundContext
    timing: SoundTiming
    callback: Optional[Callable] = None
    request_id: str = field(default_factory=lambda: f"sound_{int(time.time()*1000)}")
    created_at: datetime = field(default_factory=datetime.now)

class SoundEffectsEngine:
    """Advanced sound effects engine with TTS integration."""
    
    def __init__(self):
        """Initialize the sound effects engine."""
        self.initialized = False
        self.active_channels: Dict[int, str] = {}  # channel_id -> request_id
        self.sound_library: Dict[str, SoundEffect] = {}
        self.cached_sounds: Dict[str, pygame.mixer.Sound] = {}
        
        # Configuration
        self.enabled = os.getenv("TTS_SOUND_EFFECTS_ENABLED", "true").lower() == "true"
        self.default_theme = SoundTheme(os.getenv("TTS_SOUND_THEME", "minimal"))
        self.master_volume = float(os.getenv("TTS_SOUND_VOLUME", "0.7"))
        self.max_concurrent_sounds = int(os.getenv("TTS_MAX_CONCURRENT_SOUNDS", "3"))
        self.sound_effects_dir = Path(os.getenv("TTS_SOUND_EFFECTS_DIR", 
                                               Path.home() / "brainpods" / ".claude" / "hooks" / "utils" / "tts" / "sounds"))
        
        # Performance settings
        self.cache_enabled = os.getenv("TTS_SOUND_CACHE_ENABLED", "true").lower() == "true"
        self.preload_sounds = os.getenv("TTS_PRELOAD_SOUNDS", "true").lower() == "true"
        
        # Threading
        self.lock = threading.RLock()
        self.playback_thread: Optional[threading.Thread] = None
        self.running = False
        
        # Analytics
        self.analytics = {
            "sounds_played": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "playback_errors": 0,
            "average_selection_time": 0.0,
            "theme_usage": {theme.value: 0 for theme in SoundTheme},
            "message_type_usage": {mt.value: 0 for mt in MessageType},
        }
        
        # Initialize pygame mixer and sound library
        self._initialize_pygame()
        self._create_default_sound_effects()
        self._load_sound_library()
    
    def _initialize_pygame(self):
        """Initialize pygame mixer for audio playback."""
        try:
            pygame.mixer.pre_init(
                frequency=22050,    # Lower frequency for faster loading
                size=-16,          # 16-bit signed audio
                channels=2,        # Stereo
                buffer=1024        # Small buffer for low latency
            )
            pygame.mixer.init()
            
            # Set number of mixer channels
            pygame.mixer.set_num_channels(self.max_concurrent_sounds + 2)
            
            self.initialized = True
            print(f"🔊 Sound Effects Engine initialized with {pygame.mixer.get_num_channels()} channels")
            
        except Exception as e:
            print(f"⚠️  Failed to initialize pygame mixer: {e}")
            self.enabled = False
            self.initialized = False
    
    def _create_default_sound_effects(self):
        """Create default sound effect definitions (programmatically generated)."""
        # Create sounds directory if it doesn't exist
        self.sound_effects_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate default sound effects using pygame
        default_effects = self._generate_default_sounds()
        
        for effect_name, sound_data in default_effects.items():
            self._create_programmatic_sound(effect_name, **sound_data)
    
    def _generate_default_sounds(self) -> Dict[str, Dict]:
        """Generate default sound effects programmatically."""
        return {
            "success_chime": {
                "frequencies": [523, 659, 784],  # C5, E5, G5 chord
                "duration_ms": 300,
                "volume": 0.6,
                "theme": SoundTheme.MINIMAL,
                "message_types": [MessageType.SUCCESS],
                "description": "Pleasant success notification"
            },
            "error_tone": {
                "frequencies": [220, 185],  # Dissonant low tones
                "duration_ms": 500,
                "volume": 0.8,
                "theme": SoundTheme.MINIMAL,
                "message_types": [MessageType.ERROR],
                "description": "Attention-getting error sound"
            },
            "warning_beep": {
                "frequencies": [440],  # A4 tone
                "duration_ms": 200,
                "volume": 0.7,
                "theme": SoundTheme.MINIMAL,
                "message_types": [MessageType.WARNING],
                "description": "Warning notification beep"
            },
            "info_click": {
                "frequencies": [800, 1000],  # Quick high click
                "duration_ms": 100,
                "volume": 0.5,
                "theme": SoundTheme.MINIMAL,
                "message_types": [MessageType.INFO],
                "description": "Subtle information notification"
            },
            "interrupt_alert": {
                "frequencies": [1000, 800, 1000],  # Alternating alert
                "duration_ms": 150,
                "volume": 1.0,
                "theme": SoundTheme.MINIMAL,
                "message_types": [MessageType.INTERRUPT],
                "priority_levels": [AdvancedPriority.INTERRUPT, AdvancedPriority.CRITICAL],
                "description": "Urgent interrupt notification"
            },
            "batch_complete": {
                "frequencies": [392, 523, 659],  # G4, C5, E5 ascending
                "duration_ms": 400,
                "volume": 0.6,
                "theme": SoundTheme.MINIMAL,
                "message_types": [MessageType.BATCH],
                "description": "Batch operation completion"
            }
        }
    
    def _create_programmatic_sound(self, name: str, frequencies: List[int], 
                                 duration_ms: int, volume: float, theme: SoundTheme,
                                 message_types: List[MessageType], 
                                 priority_levels: Optional[List[AdvancedPriority]] = None,
                                 description: str = ""):
        """Create a sound effect programmatically using sine waves."""
        try:
            # Generate sound using pygame
            sample_rate = 22050
            duration_samples = int(sample_rate * duration_ms / 1000)
            
            # Create sound data
            import numpy as np
            t = np.linspace(0, duration_ms / 1000, duration_samples)
            
            # Combine multiple frequencies
            sound_data = np.zeros(duration_samples)
            for freq in frequencies:
                sound_data += np.sin(2 * np.pi * freq * t) / len(frequencies)
            
            # Apply envelope (fade in/out)
            envelope_samples = min(duration_samples // 10, 1000)  # 10% or 1000 samples max
            envelope = np.ones(duration_samples)
            envelope[:envelope_samples] = np.linspace(0, 1, envelope_samples)
            envelope[-envelope_samples:] = np.linspace(1, 0, envelope_samples)
            sound_data *= envelope
            
            # Scale to 16-bit range
            sound_data = (sound_data * volume * 32767).astype(np.int16)
            
            # Create stereo sound
            stereo_data = np.column_stack((sound_data, sound_data))
            
            # Create pygame sound
            pygame_sound = pygame.sndarray.make_sound(stereo_data)
            
            # Create sound effect definition
            sound_file = self.sound_effects_dir / f"{name}.wav"
            effect = SoundEffect(
                name=name,
                file_path=sound_file,
                theme=theme,
                volume=volume,
                duration_ms=duration_ms,
                message_types=message_types,
                priority_levels=priority_levels or [],
                description=description
            )
            
            # Cache the sound and add to library
            self.cached_sounds[name] = pygame_sound
            self.sound_library[name] = effect
            
            print(f"✅ Created sound effect: {name}")
            
        except ImportError:
            print(f"⚠️  NumPy not available, skipping programmatic sound generation")
        except Exception as e:
            print(f"❌ Failed to create sound effect {name}: {e}")
    
    def _load_sound_library(self):
        """Load sound effects from files in the sounds directory."""
        if not self.sound_effects_dir.exists():
            return
        
        # Load sound files
        supported_formats = ['.wav', '.mp3', '.ogg']
        for sound_file in self.sound_effects_dir.iterdir():
            if sound_file.suffix.lower() in supported_formats:
                try:
                    if self.preload_sounds:
                        pygame_sound = pygame.mixer.Sound(str(sound_file))
                        self.cached_sounds[sound_file.stem] = pygame_sound
                    
                    # Create basic sound effect definition
                    if sound_file.stem not in self.sound_library:
                        effect = SoundEffect(
                            name=sound_file.stem,
                            file_path=sound_file,
                            theme=self.default_theme,
                            description=f"Loaded from {sound_file.name}"
                        )
                        self.sound_library[sound_file.stem] = effect
                        
                except Exception as e:
                    print(f"⚠️  Failed to load sound {sound_file}: {e}")
    
    def select_sound_effect(self, context: SoundContext) -> Optional[SoundEffect]:
        """Intelligently select appropriate sound effect based on context."""
        if not self.enabled or not self.initialized or context.disable_effects:
            return None
        
        selection_start = time.time()
        
        # Try optimized O(1) selection first (Phase 3.4.2 integration)
        try:
            # Import optimizer only when needed to avoid circular imports
            try:
                from .phase3_sound_effects_optimizer import get_optimized_sound_effect
            except ImportError:
                try:
                    from phase3_sound_effects_optimizer import get_optimized_sound_effect
                except ImportError:
                    get_optimized_sound_effect = None
            
            if get_optimized_sound_effect:
                optimized_result = get_optimized_sound_effect(context)
                if optimized_result is not None:
                    # Update analytics for optimized selection
                    selection_time = (time.time() - selection_start) * 1000
                    current_avg = self.analytics["average_selection_time"]
                    total_count = self.analytics["sounds_played"] + 1
                    self.analytics["average_selection_time"] = (current_avg * (total_count - 1) + selection_time) / total_count
                    
                    theme = context.theme_override or self.default_theme
                    self.analytics["theme_usage"][theme.value] += 1
                    self.analytics["message_type_usage"][context.message_type.value] += 1
                    
                    return optimized_result
        except Exception:
            # Fall back to original selection if optimization fails
            pass
        
        # Original selection logic (fallback)
        theme = context.theme_override or self.default_theme
        
        # Filter sound effects by context
        candidates = []
        for effect in self.sound_library.values():
            if self._matches_context(effect, context, theme):
                candidates.append(effect)
        
        # Select best match
        selected = self._rank_and_select_candidates(candidates, context)
        
        # Update analytics
        selection_time = (time.time() - selection_start) * 1000
        current_avg = self.analytics["average_selection_time"]
        total_count = self.analytics["sounds_played"] + 1
        self.analytics["average_selection_time"] = (current_avg * (total_count - 1) + selection_time) / total_count
        
        if selected:
            self.analytics["theme_usage"][theme.value] += 1
            self.analytics["message_type_usage"][context.message_type.value] += 1
        
        return selected
    
    def _matches_context(self, effect: SoundEffect, context: SoundContext, theme: SoundTheme) -> bool:
        """Check if sound effect matches the given context."""
        # Theme match
        if effect.theme != theme and effect.theme != SoundTheme.CUSTOM:
            return False
        
        # Message type match
        if effect.message_types and context.message_type not in effect.message_types:
            return False
        
        # Priority level match
        if effect.priority_levels and context.priority not in effect.priority_levels:
            return False
        
        # Hook type match
        if effect.hook_types and context.hook_type not in effect.hook_types:
            return False
        
        # Tool pattern match
        if effect.tool_patterns:
            tool_match = any(pattern.lower() in context.tool_name.lower() 
                           for pattern in effect.tool_patterns)
            if not tool_match:
                return False
        
        return True
    
    def _rank_and_select_candidates(self, candidates: List[SoundEffect], 
                                  context: SoundContext) -> Optional[SoundEffect]:
        """Rank and select the best candidate from matching sound effects."""
        if not candidates:
            return None
        
        if len(candidates) == 1:
            return candidates[0]
        
        # Score each candidate
        scored_candidates = []
        for effect in candidates:
            score = self._calculate_effect_score(effect, context)
            scored_candidates.append((score, effect))
        
        # Sort by score (highest first)
        scored_candidates.sort(key=lambda x: x[0], reverse=True)
        
        return scored_candidates[0][1]
    
    def _calculate_effect_score(self, effect: SoundEffect, context: SoundContext) -> float:
        """Calculate relevance score for a sound effect given the context."""
        score = 0.0
        
        # Base score
        score += 1.0
        
        # Message type exact match bonus
        if context.message_type in effect.message_types:
            score += 2.0
        
        # Priority level match bonus  
        if context.priority in effect.priority_levels:
            score += 1.5
        
        # Hook type match bonus
        if context.hook_type in effect.hook_types:
            score += 1.0
        
        # Tool pattern match bonus
        if effect.tool_patterns:
            for pattern in effect.tool_patterns:
                if pattern.lower() in context.tool_name.lower():
                    score += 1.0
                    break
        
        # Usage history bonus (less used effects get slight preference for variety)
        if effect.usage_count < 10:
            score += 0.5
        
        # Recent usage penalty (avoid repetition)
        if effect.last_used and (datetime.now() - effect.last_used).seconds < 30:
            score -= 0.5
        
        # Priority boost from effect configuration
        score += effect.priority_boost
        
        return score
    
    def play_sound_effect(self, effect: SoundEffect, context: SoundContext, 
                         callback: Optional[Callable] = None) -> Optional[str]:
        """Play a sound effect with proper volume and timing."""
        if not self.enabled or not self.initialized:
            return None
        
        try:
            with self.lock:
                # Get or load sound
                pygame_sound = self._get_cached_sound(effect)
                if not pygame_sound:
                    return None
                
                # Calculate effective volume
                effective_volume = effect.volume * self.master_volume
                if context.volume_override is not None:
                    effective_volume = context.volume_override * self.master_volume
                
                # Find available channel
                channel = pygame.mixer.find_channel()
                if not channel:
                    print("⚠️  No available audio channels for sound effect")
                    return None
                
                # Set volume and play
                pygame_sound.set_volume(effective_volume)
                channel.play(pygame_sound, loops=effect.loop_count)
                
                # Apply fade effects
                if effect.fade_in_ms > 0:
                    # Pygame doesn't support fade-in on individual sounds easily
                    # This would require more complex implementation
                    pass
                
                # Track playback
                request_id = f"sound_{int(time.time()*1000)}_{effect.name}"
                self.active_channels[channel.get_sound()] = request_id
                
                # Update effect usage
                effect.usage_count += 1
                effect.last_used = datetime.now()
                
                # Update analytics
                self.analytics["sounds_played"] += 1
                
                # Schedule callback
                if callback:
                    def callback_when_done():
                        while channel.get_busy():
                            time.sleep(0.01)
                        callback(request_id)
                    
                    callback_thread = threading.Thread(target=callback_when_done, daemon=True)
                    callback_thread.start()
                
                return request_id
                
        except Exception as e:
            print(f"❌ Failed to play sound effect {effect.name}: {e}")
            self.analytics["playback_errors"] += 1
            return None
    
    def _get_cached_sound(self, effect: SoundEffect) -> Optional[pygame.mixer.Sound]:
        """Get sound from cache or load it."""
        # Check cache first
        if effect.name in self.cached_sounds:
            self.analytics["cache_hits"] += 1
            return self.cached_sounds[effect.name]
        
        # Load sound
        try:
            pygame_sound = pygame.mixer.Sound(str(effect.file_path))
            
            # Cache if enabled
            if self.cache_enabled:
                self.cached_sounds[effect.name] = pygame_sound
            
            self.analytics["cache_misses"] += 1
            return pygame_sound
            
        except Exception as e:
            print(f"❌ Failed to load sound {effect.file_path}: {e}")
            return None
    
    def stop_all_sounds(self):
        """Stop all currently playing sound effects."""
        try:
            pygame.mixer.stop()
            with self.lock:
                self.active_channels.clear()
        except Exception as e:
            print(f"❌ Failed to stop sounds: {e}")
    
    def get_sound_library(self) -> Dict[str, Dict[str, Any]]:
        """Get summary of available sound effects."""
        return {
            name: {
                "theme": effect.theme.value,
                "duration_ms": effect.duration_ms,
                "message_types": [mt.value for mt in effect.message_types],
                "priority_levels": [pl.value for pl in effect.priority_levels],
                "usage_count": effect.usage_count,
                "description": effect.description
            }
            for name, effect in self.sound_library.items()
        }
    
    def get_analytics(self) -> Dict[str, Any]:
        """Get sound effects analytics."""
        return dict(self.analytics)
    
    def get_status(self) -> Dict[str, Any]:
        """Get comprehensive engine status."""
        return {
            "enabled": self.enabled,
            "initialized": self.initialized,
            "sound_count": len(self.sound_library),
            "cached_sounds": len(self.cached_sounds),
            "active_channels": len(self.active_channels),
            "master_volume": self.master_volume,
            "default_theme": self.default_theme.value,
            "analytics": self.get_analytics(),
            "mixer_info": {
                "frequency": pygame.mixer.get_init()[0] if pygame.mixer.get_init() else None,
                "channels": pygame.mixer.get_num_channels() if self.initialized else 0,
            } if self.initialized else None
        }

# Global sound effects engine
_sound_engine = None

def get_sound_effects_engine() -> SoundEffectsEngine:
    """Get or create the global sound effects engine."""
    global _sound_engine
    if _sound_engine is None:
        _sound_engine = SoundEffectsEngine()
    return _sound_engine

def play_contextual_sound_effect(message: Optional[AdvancedTTSMessage] = None,
                                priority: AdvancedPriority = AdvancedPriority.MEDIUM,
                                message_type: MessageType = MessageType.INFO,
                                hook_type: str = "",
                                tool_name: str = "",
                                timing: SoundTiming = SoundTiming.PRE_TTS,
                                **kwargs) -> Optional[str]:
    """
    Play appropriate sound effect based on context.
    
    Args:
        message: Optional AdvancedTTSMessage for context
        priority: Message priority level
        message_type: Type of message
        hook_type: Hook making the request
        tool_name: Tool generating the message  
        timing: When to play relative to TTS
        **kwargs: Additional context options
        
    Returns:
        Request ID if sound was played, None otherwise
    """
    engine = get_sound_effects_engine()
    
    # Extract context from message if provided
    if message:
        priority = message.priority
        message_type = message.message_type
        hook_type = message.hook_type
        tool_name = message.tool_name
    
    # Create context
    context = SoundContext(
        message=message,
        priority=priority,
        message_type=message_type,
        hook_type=hook_type,
        tool_name=tool_name,
        timing=timing,
        **kwargs
    )
    
    # Select and play sound effect
    effect = engine.select_sound_effect(context)
    if effect:
        return engine.play_sound_effect(effect, context)
    
    return None

def get_sound_engine_status() -> Dict[str, Any]:
    """Get sound effects engine status."""
    engine = get_sound_effects_engine()
    return engine.get_status()

if __name__ == "__main__":
    # Test the sound effects engine
    import sys
    
    if "--test" in sys.argv:
        print("🔊 Testing Sound Effects Engine")
        print("=" * 50)
        
        engine = get_sound_effects_engine()
        
        print(f"✅ Engine Status:")
        status = engine.get_status()
        print(f"  Enabled: {status['enabled']}")
        print(f"  Initialized: {status['initialized']}")  
        print(f"  Sound Library: {status['sound_count']} effects")
        print(f"  Default Theme: {status['default_theme']}")
        
        if status['initialized']:
            print(f"\n🎵 Available Sound Effects:")
            library = engine.get_sound_library()
            for name, info in library.items():
                print(f"  • {name}: {info['description']}")
                print(f"    Types: {info['message_types']}, Theme: {info['theme']}")
            
            # Test sound playback
            print(f"\n🎤 Testing Sound Playback:")
            test_contexts = [
                (AdvancedPriority.CRITICAL, MessageType.ERROR, "Testing error sound"),
                (AdvancedPriority.MEDIUM, MessageType.SUCCESS, "Testing success sound"), 
                (AdvancedPriority.HIGH, MessageType.WARNING, "Testing warning sound"),
                (AdvancedPriority.LOW, MessageType.INFO, "Testing info sound")
            ]
            
            for priority, msg_type, description in test_contexts:
                print(f"  {description}...")
                request_id = play_contextual_sound_effect(
                    priority=priority,
                    message_type=msg_type,
                    hook_type="test",
                    tool_name="SoundEngineTest"
                )
                if request_id:
                    print(f"    ✅ Played with ID: {request_id}")
                    time.sleep(1)  # Brief pause between sounds
                else:
                    print(f"    ❌ Failed to play sound")
            
            # Show analytics
            print(f"\n📊 Analytics:")
            analytics = engine.get_analytics()
            for key, value in analytics.items():
                if isinstance(value, dict):
                    print(f"  {key}:")
                    for subkey, subvalue in value.items():
                        print(f"    {subkey}: {subvalue}")
                else:
                    print(f"  {key}: {value}")
        
        print(f"\n✅ Sound Effects Engine test completed")
    
    else:
        print("Sound Effects Engine - Phase 3.3")
        print("Usage: python sound_effects_engine.py --test")