#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "python-dotenv>=1.0.0",
# ]
# ///

"""
Phase 3.3.2 Centralized Playback Coordination System
Manages TTS provider orchestration, load balancing, and audio stream coordination.

Features:
- Multi-provider management (OpenAI, ElevenLabs, pyttsx3) with health monitoring
- Provider load balancing and automatic failover
- Audio stream state management with preemption support
- Integration with advanced priority queue system
- Real-time playback coordination with interrupt handling
- Performance analytics and provider optimization
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

# Import advanced queue system
try:
    from advanced_priority_queue import (
        get_advanced_queue,
        AdvancedPriorityQueue,
        AdvancedTTSMessage,
        AdvancedPriority,
        MessageType,
        QueueState
    )
    ADVANCED_QUEUE_AVAILABLE = True
except ImportError:
    ADVANCED_QUEUE_AVAILABLE = False

# Import Phase 2 coordination
try:
    from observability import get_observability, EventCategory, EventPriority
    OBSERVABILITY_AVAILABLE = True
except ImportError:
    OBSERVABILITY_AVAILABLE = False

# Import Phase 3.4 streaming systems
try:
    from streaming_coordinator import (
        get_streaming_coordinator,
        StreamingCoordinator,
        submit_streaming_tts_request
    )
    STREAMING_COORDINATOR_AVAILABLE = True
except ImportError:
    STREAMING_COORDINATOR_AVAILABLE = False

try:
    from openai_streaming_client import (
        get_streaming_client,
        OpenAIStreamingClient,
        StreamingQuality
    )
    STREAMING_CLIENT_AVAILABLE = True  
except ImportError:
    STREAMING_CLIENT_AVAILABLE = False

class ProviderType(Enum):
    """TTS provider types with capabilities."""
    OPENAI = "openai"           # Neural TTS, cost-optimized
    ELEVENLABS = "elevenlabs"   # AI voices, premium quality
    PYTTSX3 = "pyttsx3"         # Offline fallback, always available

class ProviderHealth(Enum):
    """Provider health status."""
    HEALTHY = "healthy"         # Fully operational
    DEGRADED = "degraded"       # Some issues but functional
    UNHEALTHY = "unhealthy"     # Not functional
    UNKNOWN = "unknown"         # Status not determined

class PlaybackState(Enum):
    """Audio playback state."""
    IDLE = "idle"               # No active playback
    PLAYING = "playing"         # Audio currently playing
    PAUSED = "paused"           # Playback paused
    STOPPING = "stopping"      # In process of stopping
    PREEMPTING = "preempting"   # Being interrupted by higher priority

class StreamPriority(Enum):
    """Audio stream priority levels."""
    INTERRUPT = 0     # Emergency interrupts (stop everything)
    CRITICAL = 1      # Errors, security issues
    HIGH = 2          # Important notifications
    NORMAL = 3        # Regular operations
    BACKGROUND = 4    # Low priority background

@dataclass
class ProviderStatus:
    """Provider health and performance status."""
    type: ProviderType
    health: ProviderHealth = ProviderHealth.UNKNOWN
    last_success: Optional[datetime] = None
    last_failure: Optional[datetime] = None
    failure_count: int = 0
    success_count: int = 0
    average_latency: float = 0.0
    current_load: int = 0
    max_concurrent: int = 3
    api_key_valid: bool = True
    error_details: str = ""
    
    def success_rate(self) -> float:
        """Calculate success rate percentage."""
        total = self.success_count + self.failure_count
        return (self.success_count / total * 100) if total > 0 else 0.0
    
    def is_available(self) -> bool:
        """Check if provider is available for use."""
        return (
            self.health in [ProviderHealth.HEALTHY, ProviderHealth.DEGRADED] and
            self.current_load < self.max_concurrent and
            self.api_key_valid
        )
    
    def priority_score(self) -> float:
        """Calculate provider priority score for load balancing."""
        # Higher score = better choice
        base_score = {
            ProviderHealth.HEALTHY: 100,
            ProviderHealth.DEGRADED: 50,
            ProviderHealth.UNHEALTHY: 0,
            ProviderHealth.UNKNOWN: 25
        }[self.health]
        
        # Adjust for load (prefer less loaded providers)
        load_factor = max(0, 1.0 - (self.current_load / self.max_concurrent))
        
        # Adjust for success rate
        success_factor = self.success_rate() / 100
        
        # Adjust for latency (prefer faster providers)
        latency_factor = max(0, 1.0 - min(1.0, self.average_latency / 5000))  # 5s baseline
        
        return base_score * load_factor * success_factor * latency_factor

@dataclass 
class AudioStream:
    """Represents an active audio stream."""
    stream_id: str
    message: AdvancedTTSMessage
    provider: ProviderType
    priority: StreamPriority
    state: PlaybackState = PlaybackState.IDLE
    process: Optional[subprocess.Popen] = None
    future: Optional[Future] = None
    start_time: Optional[datetime] = None
    estimated_duration: float = 3.0  # seconds
    preemptable: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def age_seconds(self) -> float:
        """Get stream age in seconds."""
        if self.start_time:
            return (datetime.now() - self.start_time).total_seconds()
        return 0.0
    
    def can_preempt(self, new_priority: StreamPriority) -> bool:
        """Check if this stream can be preempted by new priority."""
        return (
            self.preemptable and 
            new_priority.value < self.priority.value and
            self.state in [PlaybackState.PLAYING, PlaybackState.PAUSED]
        )

class PlaybackCoordinator:
    """Centralized TTS playback coordination system."""
    
    def __init__(self):
        """Initialize the playback coordinator."""
        self.providers: Dict[ProviderType, ProviderStatus] = {
            ProviderType.OPENAI: ProviderStatus(
                ProviderType.OPENAI,
                max_concurrent=5,  # OpenAI can handle more concurrent requests
            ),
            ProviderType.ELEVENLABS: ProviderStatus(
                ProviderType.ELEVENLABS,
                max_concurrent=3,  # ElevenLabs has stricter limits
            ),
            ProviderType.PYTTSX3: ProviderStatus(
                ProviderType.PYTTSX3,
                health=ProviderHealth.HEALTHY,  # Always healthy (offline)
                max_concurrent=1,  # Offline, single threaded
                api_key_valid=True,  # No API key needed
            ),
        }
        
        # Active streams management
        self.active_streams: Dict[str, AudioStream] = {}
        self.stream_history: deque[AudioStream] = deque(maxlen=50)
        self.preempted_streams: deque[AudioStream] = deque(maxlen=10)
        
        # Coordination state
        self.playback_state = PlaybackState.IDLE
        self.current_priority = StreamPriority.BACKGROUND
        self.coordination_lock = threading.RLock()
        
        # Thread management
        self.executor = ThreadPoolExecutor(max_workers=8, thread_name_prefix="tts_playback")
        self.health_monitor_thread = None
        self.queue_processor_thread = None
        self.running = False
        
        # Configuration
        self.health_check_interval = 30  # seconds
        self.provider_timeout = 15  # seconds
        self.max_retry_attempts = 2
        self.preemption_fade_time = 0.5  # seconds
        
        # Voice configuration
        self.voice_config = {
            ProviderType.OPENAI: {
                "default": os.getenv("OPENAI_TTS_VOICE_DEFAULT", "nova"),
                "critical": os.getenv("OPENAI_TTS_VOICE_CRITICAL", "echo"),
                "completion": os.getenv("OPENAI_TTS_VOICE_COMPLETION", "nova"),
            },
            ProviderType.ELEVENLABS: {
                "default": os.getenv("ELEVENLABS_VOICE_DEFAULT", "21m00Tcm4TlvDq8ikWAM"),
                "critical": os.getenv("ELEVENLABS_VOICE_CRITICAL", "21m00Tcm4TlvDq8ikWAM"),
                "completion": os.getenv("ELEVENLABS_VOICE_COMPLETION", "21m00Tcm4TlvDq8ikWAM"),
            }
        }
        
        # Analytics
        self.performance_metrics = {
            "streams_processed": 0,
            "streams_successful": 0,
            "streams_failed": 0,
            "streams_preempted": 0,
            "average_latency": 0.0,
            "provider_usage": defaultdict(int),
            "error_categories": defaultdict(int),
        }
        
        # Initialize provider health
        self._initialize_providers()
        
        # Phase 3.4: Streaming integration
        self.streaming_coordinator = None
        self.streaming_client = None
        self.enable_streaming = os.getenv("TTS_ENABLE_STREAMING", "true").lower() == "true"
        self.streaming_threshold_ms = int(os.getenv("TTS_STREAMING_THRESHOLD_MS", "2000"))  # Use streaming for urgent messages
        self.hybrid_mode = os.getenv("TTS_HYBRID_MODE", "true").lower() == "true"  # Use both streaming and traditional
    
    def _initialize_providers(self):
        """Initialize provider health checks and API key validation."""
        # Check OpenAI API key
        openai_key = os.getenv("OPENAI_API_KEY")
        if openai_key and len(openai_key) > 20:
            self.providers[ProviderType.OPENAI].api_key_valid = True
            self.providers[ProviderType.OPENAI].health = ProviderHealth.UNKNOWN
        else:
            self.providers[ProviderType.OPENAI].api_key_valid = False
            self.providers[ProviderType.OPENAI].health = ProviderHealth.UNHEALTHY
            self.providers[ProviderType.OPENAI].error_details = "Missing or invalid API key"
        
        # Check ElevenLabs API key
        elevenlabs_key = os.getenv("ELEVENLABS_API_KEY")
        if elevenlabs_key and len(elevenlabs_key) > 20:
            self.providers[ProviderType.ELEVENLABS].api_key_valid = True
            self.providers[ProviderType.ELEVENLABS].health = ProviderHealth.UNKNOWN
        else:
            self.providers[ProviderType.ELEVENLABS].api_key_valid = False
            self.providers[ProviderType.ELEVENLABS].health = ProviderHealth.DEGRADED
            self.providers[ProviderType.ELEVENLABS].error_details = "Missing API key, will skip"
        
        # pyttsx3 is always available
        self.providers[ProviderType.PYTTSX3].health = ProviderHealth.HEALTHY
    
    def start(self):
        """Start the playback coordinator."""
        if self.running:
            return
        
        self.running = True
        
        # Start health monitoring
        self.health_monitor_thread = threading.Thread(
            target=self._health_monitor_loop,
            daemon=True,
            name="tts_health_monitor"
        )
        self.health_monitor_thread.start()
        
        # Start queue processing
        if ADVANCED_QUEUE_AVAILABLE:
            self.queue_processor_thread = threading.Thread(
                target=self._queue_processor_loop,
                daemon=True,
                name="tts_queue_processor"
            )
            self.queue_processor_thread.start()
        
        # Phase 3.4: Initialize streaming systems
        if self.enable_streaming:
            self._initialize_streaming_systems()
    
    def stop(self):
        """Stop the playback coordinator and cleanup resources."""
        self.running = False
        
        # Stop all active streams
        self._stop_all_streams()
        
        # Wait for threads to finish
        if self.health_monitor_thread and self.health_monitor_thread.is_alive():
            self.health_monitor_thread.join(timeout=2)
        
        if self.queue_processor_thread and self.queue_processor_thread.is_alive():
            self.queue_processor_thread.join(timeout=2)
        
        # Shutdown executor
        self.executor.shutdown(wait=True, timeout=5)
    
    def select_provider(self, message: AdvancedTTSMessage) -> Optional[ProviderType]:
        """Select best provider for message based on load balancing and health."""
        # Get available providers
        available_providers = [
            (provider_type, status) for provider_type, status in self.providers.items()
            if status.is_available()
        ]
        
        if not available_providers:
            # Fallback to pyttsx3 if available
            if self.providers[ProviderType.PYTTSX3].health == ProviderHealth.HEALTHY:
                return ProviderType.PYTTSX3
            return None
        
        # Priority-based selection for different message types
        if message.priority == AdvancedPriority.INTERRUPT:
            # For interrupts, prefer fastest available provider
            available_providers.sort(key=lambda x: x[1].average_latency)
            return available_providers[0][0]
        
        elif message.message_type == MessageType.ERROR:
            # For errors, prefer reliable provider
            reliable_providers = [
                (pt, ps) for pt, ps in available_providers 
                if ps.success_rate() > 80
            ]
            if reliable_providers:
                available_providers = reliable_providers
        
        elif message.priority in [AdvancedPriority.LOW, AdvancedPriority.BACKGROUND]:
            # For low priority, prefer cost-effective option (OpenAI)
            openai_available = next(
                ((pt, ps) for pt, ps in available_providers if pt == ProviderType.OPENAI),
                None
            )
            if openai_available and openai_available[1].is_available():
                return ProviderType.OPENAI
        
        # Default: Select best provider by priority score
        available_providers.sort(key=lambda x: x[1].priority_score(), reverse=True)
        return available_providers[0][0]
    
    def play_message(self, message: AdvancedTTSMessage, callback: Optional[Callable] = None) -> Optional[str]:
        """
        Play TTS message with full coordination and provider management.
        
        Args:
            message: The TTS message to play
            callback: Optional callback when playback completes
            
        Returns:
            Stream ID if playback started, None if failed
        """
        with self.coordination_lock:
            # Check if TTS is globally enabled
            if not self._is_tts_enabled():
                return None
            
            # Select provider
            provider = self.select_provider(message)
            if not provider:
                self._record_error("no_provider_available", "No healthy providers available")
                return None
            
            # Create stream
            stream_id = f"{provider.value}_{int(time.time()*1000)}_{random.randint(1000, 9999)}"
            priority = self._map_message_to_stream_priority(message)
            
            stream = AudioStream(
                stream_id=stream_id,
                message=message,
                provider=provider,
                priority=priority,
                estimated_duration=self._estimate_duration(message.content),
                metadata={
                    "hook_type": message.hook_type,
                    "tool_name": message.tool_name,
                    "created_at": datetime.now().isoformat(),
                    "callback": callback
                }
            )
            
            # Check for preemption
            preempted_streams = self._check_preemption(stream)
            if preempted_streams:
                self._handle_preemption(preempted_streams, stream)
            
            # Start playback
            if self._start_stream_playback(stream):
                self.active_streams[stream_id] = stream
                self._update_metrics("stream_started", provider)
                return stream_id
            else:
                self._record_error("playback_failed", f"Failed to start playback with {provider.value}")
                return None
    
    def stop_stream(self, stream_id: str, reason: str = "user_requested") -> bool:
        """Stop specific audio stream."""
        with self.coordination_lock:
            stream = self.active_streams.get(stream_id)
            if not stream:
                return False
            
            return self._stop_stream_internal(stream, reason)
    
    def stop_all_streams(self, reason: str = "coordinator_shutdown") -> int:
        """Stop all active streams."""
        with self.coordination_lock:
            return self._stop_all_streams(reason)
    
    def interrupt_current_playback(self, message: AdvancedTTSMessage) -> Optional[str]:
        """Interrupt current playback with high-priority message."""
        # Force interrupt priority
        message.priority = AdvancedPriority.INTERRUPT
        return self.play_message(message)
    
    def get_coordinator_status(self) -> Dict[str, Any]:
        """Get comprehensive coordinator status."""
        with self.coordination_lock:
            return {
                "running": self.running,
                "playback_state": self.playback_state.value,
                "current_priority": self.current_priority.value,
                "active_streams": len(self.active_streams),
                "providers": {
                    provider_type.value: {
                        "health": status.health.value,
                        "success_rate": status.success_rate(),
                        "current_load": status.current_load,
                        "average_latency": status.average_latency,
                        "api_key_valid": status.api_key_valid,
                        "is_available": status.is_available(),
                        "priority_score": status.priority_score(),
                    }
                    for provider_type, status in self.providers.items()
                },
                "performance_metrics": dict(self.performance_metrics),
                "stream_history_count": len(self.stream_history),
                "preempted_streams_count": len(self.preempted_streams),
                "streaming_status": self.get_streaming_status(),
            }
    
    def play_message_with_streaming(
        self, 
        message: AdvancedTTSMessage, 
        callback: Optional[Callable] = None,
        force_streaming: bool = False
    ) -> Optional[str]:
        """
        Play message with intelligent streaming/traditional coordination.
        
        Args:
            message: The TTS message to play
            callback: Optional callback when playback completes
            force_streaming: Force streaming even for low priority messages
            
        Returns:
            Stream ID if successful, None if failed
        """
        if not self.enable_streaming or not self.streaming_coordinator:
            # Fallback to traditional playback
            return self.play_message(message, callback)
        
        # Decide between streaming and traditional playback
        use_streaming = self._should_use_streaming(message, force_streaming)
        
        if use_streaming:
            return self._handle_streaming_playback(message, callback)
        else:
            return self.play_message(message, callback)
    
    def _should_use_streaming(self, message: AdvancedTTSMessage, force_streaming: bool = False) -> bool:
        """Determine if streaming should be used for this message."""
        if force_streaming:
            return True
        
        # Use streaming for high priority messages
        if message.priority in [AdvancedPriority.INTERRUPT, AdvancedPriority.CRITICAL]:
            return True
        
        # Use streaming for messages that need very fast response
        if message.message_type == MessageType.ERROR:
            return True
        
        # Check message length - streaming is better for longer messages
        if len(message.content) > 100:  # Characters
            return True
        
        # Check current system load
        if len(self.active_streams) == 0:  # No current playback, streaming can start immediately
            return True
        
        return False
    
    def _handle_streaming_playback(self, message: AdvancedTTSMessage, callback: Optional[Callable] = None) -> Optional[str]:
        """Handle playback through streaming coordinator."""
        try:
            # Create streaming callback wrapper
            def streaming_callback(session, success):
                if callback:
                    try:
                        # Create a dummy stream object for callback compatibility
                        dummy_stream = type('DummyStream', (), {
                            'stream_id': f"streaming_{session.session_id if hasattr(session, 'session_id') else 'unknown'}",
                            'message': message,
                            'metadata': {"streaming": True, "session": session}
                        })()
                        callback(dummy_stream, success, "" if success else "Streaming failed")
                    except Exception:
                        pass
            
            # Submit to streaming coordinator
            request_id = self.streaming_coordinator.submit_streaming_request(
                message=message,
                callback=streaming_callback
            )
            
            if request_id:
                # Track as active stream for coordinator compatibility
                stream_id = f"streaming_{request_id}"
                dummy_stream = AudioStream(
                    stream_id=stream_id,
                    message=message,
                    provider=ProviderType.OPENAI,  # Streaming typically uses OpenAI
                    priority=self._map_message_to_stream_priority(message),
                    metadata={
                        "streaming": True,
                        "streaming_request_id": request_id,
                        "callback": callback
                    }
                )
                
                # Add to active streams for monitoring
                with self.coordination_lock:
                    self.active_streams[stream_id] = dummy_stream
                
                return stream_id
            
        except Exception as e:
            self._record_error("streaming_playback_failed", str(e))
            
            # Fallback to traditional playback
            if self.hybrid_mode:
                return self.play_message(message, callback)
        
        return None
    
    def _initialize_streaming_systems(self):
        """Initialize streaming coordinator and client connections."""
        # Initialize streaming coordinator
        if STREAMING_COORDINATOR_AVAILABLE:
            try:
                self.streaming_coordinator = get_streaming_coordinator()
                if not self.streaming_coordinator.running:
                    self.streaming_coordinator.start()
            except Exception as e:
                print(f"Warning: Failed to initialize streaming coordinator: {e}")
                self.enable_streaming = False
        
        # Initialize streaming client
        if STREAMING_CLIENT_AVAILABLE:
            try:
                self.streaming_client = get_streaming_client()
            except Exception as e:
                print(f"Warning: Failed to initialize streaming client: {e}")
                self.enable_streaming = False
    
    def get_streaming_status(self) -> Dict[str, Any]:
        """Get streaming system status."""
        if not self.enable_streaming:
            return {"streaming_enabled": False}
        
        status = {
            "streaming_enabled": True,
            "hybrid_mode": self.hybrid_mode,
            "streaming_threshold_ms": self.streaming_threshold_ms,
            "coordinator_available": self.streaming_coordinator is not None,
            "client_available": self.streaming_client is not None
        }
        
        # Add coordinator status if available
        if self.streaming_coordinator:
            try:
                coord_status = self.streaming_coordinator.get_coordinator_status()
                status["coordinator_status"] = coord_status
            except Exception as e:
                status["coordinator_error"] = str(e)
        
        # Add client performance if available  
        if self.streaming_client:
            try:
                client_perf = self.streaming_client.get_performance_summary()
                status["client_performance"] = client_perf
            except Exception as e:
                status["client_error"] = str(e)
        
        return status

    # Internal methods
    
    def _is_tts_enabled(self) -> bool:
        """Check if TTS is globally enabled."""
        return os.getenv("TTS_ENABLED", "true").lower() == "true"
    
    def _map_message_to_stream_priority(self, message: AdvancedTTSMessage) -> StreamPriority:
        """Map message priority to stream priority."""
        mapping = {
            AdvancedPriority.INTERRUPT: StreamPriority.INTERRUPT,
            AdvancedPriority.CRITICAL: StreamPriority.CRITICAL,
            AdvancedPriority.HIGH: StreamPriority.HIGH,
            AdvancedPriority.MEDIUM: StreamPriority.NORMAL,
            AdvancedPriority.LOW: StreamPriority.NORMAL,
            AdvancedPriority.BACKGROUND: StreamPriority.BACKGROUND,
        }
        return mapping.get(message.priority, StreamPriority.NORMAL)
    
    def _estimate_duration(self, text: str) -> float:
        """Estimate playback duration in seconds."""
        # Rough estimate: 150 words per minute, average 5 characters per word
        word_count = len(text.split())
        return max(1.0, word_count / 2.5)  # 2.5 words per second
    
    def _check_preemption(self, new_stream: AudioStream) -> List[AudioStream]:
        """Check which streams should be preempted by new stream."""
        preempted = []
        for stream in self.active_streams.values():
            if stream.can_preempt(new_stream.priority):
                preempted.append(stream)
        return preempted
    
    def _handle_preemption(self, preempted_streams: List[AudioStream], new_stream: AudioStream):
        """Handle preemption of existing streams."""
        for stream in preempted_streams:
            self._stop_stream_internal(stream, "preempted")
            self.preempted_streams.append(stream)
            self.performance_metrics["streams_preempted"] += 1
    
    def _start_stream_playback(self, stream: AudioStream) -> bool:
        """Start actual audio playback for stream."""
        try:
            stream.start_time = datetime.now()
            stream.state = PlaybackState.PLAYING
            
            # Update provider load
            provider_status = self.providers[stream.provider]
            provider_status.current_load += 1
            
            # Create TTS command based on provider
            cmd = self._build_tts_command(stream)
            if not cmd:
                return False
            
            # Start subprocess
            stream.process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Submit to executor for monitoring
            stream.future = self.executor.submit(
                self._monitor_stream_playback, stream
            )
            
            return True
            
        except Exception as e:
            self._record_error("stream_start_failed", str(e))
            self._cleanup_failed_stream(stream)
            return False
    
    def _build_tts_command(self, stream: AudioStream) -> Optional[List[str]]:
        """Build TTS command for specific provider."""
        message = stream.message
        provider = stream.provider
        
        if provider == ProviderType.OPENAI:
            voice = self._select_voice(provider, message)
            return [
                "speak", 
                "--provider", "openai",
                "--voice", voice,
                message.content
            ]
        
        elif provider == ProviderType.ELEVENLABS:
            voice = self._select_voice(provider, message)
            return [
                "speak",
                "--provider", "elevenlabs", 
                "--voice", voice,
                message.content
            ]
        
        elif provider == ProviderType.PYTTSX3:
            return [
                "speak",
                "--provider", "pyttsx3",
                message.content
            ]
        
        return None
    
    def _select_voice(self, provider: ProviderType, message: AdvancedTTSMessage) -> str:
        """Select appropriate voice for provider and message."""
        provider_voices = self.voice_config.get(provider, {})
        
        if message.message_type == MessageType.ERROR:
            return provider_voices.get("critical", provider_voices.get("default", "nova"))
        elif message.hook_type == "stop" or message.message_type == MessageType.BATCH:
            return provider_voices.get("completion", provider_voices.get("default", "nova"))
        else:
            return provider_voices.get("default", "nova")
    
    def _monitor_stream_playback(self, stream: AudioStream):
        """Monitor stream playback in background thread."""
        try:
            # Wait for process completion
            stdout, stderr = stream.process.communicate(timeout=self.provider_timeout)
            return_code = stream.process.returncode
            
            # Calculate actual duration
            end_time = datetime.now()
            actual_duration = (end_time - stream.start_time).total_seconds()
            
            # Update provider metrics
            provider_status = self.providers[stream.provider]
            provider_status.current_load -= 1
            
            if return_code == 0:
                # Success
                stream.state = PlaybackState.IDLE
                provider_status.success_count += 1
                provider_status.last_success = end_time
                provider_status.average_latency = (
                    provider_status.average_latency * 0.8 + actual_duration * 1000 * 0.2
                )
                
                # Update provider health
                if provider_status.health == ProviderHealth.UNKNOWN:
                    provider_status.health = ProviderHealth.HEALTHY
                elif provider_status.health == ProviderHealth.DEGRADED:
                    if provider_status.success_rate() > 80:
                        provider_status.health = ProviderHealth.HEALTHY
                
                self.performance_metrics["streams_successful"] += 1
                
                # Execute callback if provided
                callback = stream.metadata.get("callback")
                if callback and callable(callback):
                    try:
                        callback(stream, True, "")
                    except Exception:
                        pass  # Don't fail on callback errors
            
            else:
                # Failure
                stream.state = PlaybackState.IDLE
                error_msg = stderr.strip() if stderr else f"Process failed with code {return_code}"
                provider_status.failure_count += 1
                provider_status.last_failure = end_time
                provider_status.error_details = error_msg
                
                # Update provider health
                if provider_status.failure_count >= 3:
                    provider_status.health = ProviderHealth.DEGRADED
                if provider_status.failure_count >= 5:
                    provider_status.health = ProviderHealth.UNHEALTHY
                
                self.performance_metrics["streams_failed"] += 1
                self._record_error("stream_playback_failed", error_msg)
                
                # Execute callback with error
                callback = stream.metadata.get("callback")
                if callback and callable(callback):
                    try:
                        callback(stream, False, error_msg)
                    except Exception:
                        pass
            
        except subprocess.TimeoutExpired:
            # Timeout - kill process and mark as failed
            stream.process.kill()
            stream.state = PlaybackState.IDLE
            
            provider_status = self.providers[stream.provider]
            provider_status.current_load -= 1
            provider_status.failure_count += 1
            provider_status.health = ProviderHealth.DEGRADED
            
            self.performance_metrics["streams_failed"] += 1
            self._record_error("stream_timeout", f"Stream timed out after {self.provider_timeout}s")
            
        except Exception as e:
            # Unexpected error
            stream.state = PlaybackState.IDLE
            provider_status = self.providers[stream.provider]
            provider_status.current_load -= 1
            provider_status.failure_count += 1
            
            self.performance_metrics["streams_failed"] += 1
            self._record_error("stream_monitor_error", str(e))
            
        finally:
            # Cleanup stream
            with self.coordination_lock:
                if stream.stream_id in self.active_streams:
                    del self.active_streams[stream.stream_id]
                
                self.stream_history.append(stream)
                
                # Update coordinator state
                if not self.active_streams:
                    self.playback_state = PlaybackState.IDLE
                    self.current_priority = StreamPriority.BACKGROUND
    
    def _stop_stream_internal(self, stream: AudioStream, reason: str) -> bool:
        """Internal stream stopping logic."""
        try:
            stream.state = PlaybackState.STOPPING
            stream.metadata["stop_reason"] = reason
            stream.metadata["stopped_at"] = datetime.now().isoformat()
            
            # Terminate process if running
            if stream.process and stream.process.poll() is None:
                stream.process.terminate()
                
                # Wait briefly for graceful termination
                try:
                    stream.process.wait(timeout=1.0)
                except subprocess.TimeoutExpired:
                    stream.process.kill()
            
            # Cancel future if active
            if stream.future and not stream.future.done():
                stream.future.cancel()
            
            # Update provider load
            provider_status = self.providers[stream.provider]
            if provider_status.current_load > 0:
                provider_status.current_load -= 1
            
            # Remove from active streams
            if stream.stream_id in self.active_streams:
                del self.active_streams[stream.stream_id]
            
            stream.state = PlaybackState.IDLE
            return True
            
        except Exception as e:
            self._record_error("stream_stop_failed", str(e))
            return False
    
    def _stop_all_streams(self, reason: str = "shutdown") -> int:
        """Stop all active streams."""
        stopped_count = 0
        
        for stream in list(self.active_streams.values()):
            if self._stop_stream_internal(stream, reason):
                stopped_count += 1
        
        self.playback_state = PlaybackState.IDLE
        self.current_priority = StreamPriority.BACKGROUND
        
        return stopped_count
    
    def _cleanup_failed_stream(self, stream: AudioStream):
        """Cleanup resources for failed stream."""
        provider_status = self.providers[stream.provider]
        if provider_status.current_load > 0:
            provider_status.current_load -= 1
        
        provider_status.failure_count += 1
        provider_status.last_failure = datetime.now()
        
        stream.state = PlaybackState.IDLE
        self.performance_metrics["streams_failed"] += 1
    
    def _health_monitor_loop(self):
        """Background health monitoring loop."""
        while self.running:
            try:
                self._perform_health_checks()
                time.sleep(self.health_check_interval)
            except Exception as e:
                self._record_error("health_monitor_error", str(e))
                time.sleep(5)  # Shorter retry on error
    
    def _perform_health_checks(self):
        """Perform provider health checks."""
        for provider_type, status in self.providers.items():
            if provider_type == ProviderType.PYTTSX3:
                # pyttsx3 is always healthy
                status.health = ProviderHealth.HEALTHY
                continue
            
            # Check API-based providers
            if not status.api_key_valid:
                status.health = ProviderHealth.UNHEALTHY
                continue
            
            # Simple health check based on recent performance
            now = datetime.now()
            
            # Check if we've had recent activity
            if status.last_success and (now - status.last_success).total_seconds() < 300:
                # Recent success within 5 minutes
                if status.success_rate() > 80:
                    status.health = ProviderHealth.HEALTHY
                elif status.success_rate() > 50:
                    status.health = ProviderHealth.DEGRADED
                else:
                    status.health = ProviderHealth.UNHEALTHY
            
            elif status.last_failure and (now - status.last_failure).total_seconds() < 60:
                # Recent failure within 1 minute
                status.health = ProviderHealth.DEGRADED
            
            # Reset failure count periodically for recovery
            if status.last_failure and (now - status.last_failure).total_seconds() > 600:
                status.failure_count = max(0, status.failure_count - 1)
    
    def _queue_processor_loop(self):
        """Background queue processing loop."""
        if not ADVANCED_QUEUE_AVAILABLE:
            return
        
        queue = get_advanced_queue()
        
        while self.running:
            try:
                # Get next message from queue
                message = queue.dequeue()
                if message:
                    # Process message through playback coordinator
                    self.play_message(message)
                else:
                    # No messages, brief sleep
                    time.sleep(0.1)
                    
            except Exception as e:
                self._record_error("queue_processor_error", str(e))
                time.sleep(1)
    
    def _update_metrics(self, metric_type: str, provider: ProviderType = None):
        """Update performance metrics."""
        self.performance_metrics["streams_processed"] += 1
        
        if provider:
            self.performance_metrics["provider_usage"][provider.value] += 1
    
    def _record_error(self, error_type: str, details: str):
        """Record error in metrics and logging."""
        self.performance_metrics["error_categories"][error_type] += 1
        
        # Log to coordinator log if needed
        error_log = Path.home() / "brainpods" / ".claude-logs" / "hooks" / "coordinator_errors.jsonl"
        error_log.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            with open(error_log, "a") as f:
                error_entry = {
                    "timestamp": datetime.now().isoformat(),
                    "error_type": error_type,
                    "details": details,
                    "active_streams": len(self.active_streams),
                    "coordinator_state": self.playback_state.value
                }
                f.write(json.dumps(error_entry) + "\n")
        except Exception:
            pass  # Don't fail on logging errors

# Global coordinator instance
_coordinator = None

def get_playback_coordinator() -> PlaybackCoordinator:
    """Get or create the global playback coordinator."""
    global _coordinator
    if _coordinator is None:
        _coordinator = PlaybackCoordinator()
    return _coordinator

def play_tts_message(message: AdvancedTTSMessage, callback: Optional[Callable] = None) -> Optional[str]:
    """Play TTS message through the coordinator."""
    coordinator = get_playback_coordinator()
    if not coordinator.running:
        coordinator.start()
    return coordinator.play_message(message, callback)

def play_tts_message_with_streaming(
    message: AdvancedTTSMessage, 
    callback: Optional[Callable] = None,
    force_streaming: bool = False
) -> Optional[str]:
    """Play TTS message with intelligent streaming/traditional coordination."""
    coordinator = get_playback_coordinator()
    if not coordinator.running:
        coordinator.start()
    return coordinator.play_message_with_streaming(message, callback, force_streaming)

def stop_all_tts_playback(reason: str = "requested") -> int:
    """Stop all TTS playback."""
    coordinator = get_playback_coordinator()
    return coordinator.stop_all_streams(reason)

def get_tts_coordinator_status() -> Dict[str, Any]:
    """Get TTS coordinator status."""
    coordinator = get_playback_coordinator()
    return coordinator.get_coordinator_status()

if __name__ == "__main__":
    # Test the playback coordinator
    import sys
    
    if "--test" in sys.argv:
        print("🎵 Testing Playback Coordinator")
        print("=" * 50)
        
        # Create test coordinator
        coordinator = get_playback_coordinator()
        coordinator.start()
        
        print("✅ Coordinator started")
        print(f"📊 Initial status: {json.dumps(coordinator.get_coordinator_status(), indent=2)}")
        
        # Create test message if advanced queue is available
        if ADVANCED_QUEUE_AVAILABLE:
            from advanced_priority_queue import AdvancedTTSMessage, AdvancedPriority, MessageType
            
            test_message = AdvancedTTSMessage(
                content="Testing playback coordinator system",
                priority=AdvancedPriority.HIGH,
                message_type=MessageType.INFO,
                hook_type="test",
                tool_name="PlaybackTest"
            )
            
            print(f"\n🎤 Playing test message...")
            stream_id = coordinator.play_message(test_message)
            
            if stream_id:
                print(f"✅ Stream started: {stream_id}")
                
                # Wait for completion
                time.sleep(5)
                
                print(f"📊 Final status: {json.dumps(coordinator.get_coordinator_status(), indent=2)}")
            else:
                print("❌ Failed to start stream")
        
        # Cleanup
        coordinator.stop()
        print("✅ Coordinator stopped")
        
    else:
        print("Playback Coordinator - Phase 3.3.2")
        print("Usage: python playback_coordinator.py --test")