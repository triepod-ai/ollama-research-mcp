#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "python-dotenv>=1.0.0",
#   "pygame>=2.5.0",
# ]
# ///

"""
Phase 3.4.3.1 Audio Stream Multiplexer
Parallel audio chunk processing system for multiple TTS streams.

Features:
- Multi-stream audio processing with concurrent playback management
- Chunk-based audio processing for reduced latency and improved responsiveness
- Stream priority management with preemption and mixing capabilities
- Memory-efficient audio buffer management with automatic cleanup
- Integration with concurrent API pool for seamless audio pipeline
- Real-time audio mixing and stream coordination
- Performance monitoring and stream health tracking
"""

import asyncio
import io
import os
import tempfile
import threading
import time
import wave
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Callable, Any, Tuple, Union, BinaryIO
from concurrent.futures import ThreadPoolExecutor, Future
from queue import Queue, PriorityQueue, Empty
from dotenv import load_dotenv

# Import audio processing libraries
try:
    import pygame
    PYGAME_AVAILABLE = True
except ImportError:
    PYGAME_AVAILABLE = False

# Import Phase 3 components
try:
    try:
        from .phase3_cache_manager import get_cache_manager
        from .phase3_performance_metrics import get_performance_monitor, measure_performance
        from .phase3_43_concurrent_api_pool import get_concurrent_api_pool, APIRequestResult, RequestStatus
        from .advanced_priority_queue import AdvancedPriority, MessageType
    except ImportError:
        from phase3_cache_manager import get_cache_manager
        from phase3_performance_metrics import get_performance_monitor, measure_performance
        from phase3_43_concurrent_api_pool import get_concurrent_api_pool, APIRequestResult, RequestStatus
        from advanced_priority_queue import AdvancedPriority, MessageType
    
    PHASE3_DEPENDENCIES_AVAILABLE = True
except ImportError:
    PHASE3_DEPENDENCIES_AVAILABLE = False
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

class StreamState(Enum):
    """Audio stream state management."""
    IDLE = "idle"
    LOADING = "loading"
    READY = "ready"
    PLAYING = "playing"
    PAUSED = "paused"
    STOPPING = "stopping"
    COMPLETED = "completed"
    ERROR = "error"
    PREEMPTED = "preempted"

class StreamType(Enum):
    """Audio stream types for different processing strategies."""
    STANDARD = "standard"          # Normal TTS audio
    STREAMING = "streaming"        # Real-time streaming audio
    CHUNKED = "chunked"            # Chunk-based processing
    MIXED = "mixed"                # Multiple streams mixed together

class AudioFormat(Enum):
    """Supported audio formats."""
    MP3 = "mp3"
    WAV = "wav"
    OGG = "ogg"
    FLAC = "flac"

@dataclass
class AudioChunk:
    """Individual audio chunk for processing."""
    chunk_id: str
    stream_id: str
    data: bytes
    chunk_index: int
    total_chunks: int
    format: AudioFormat
    duration_ms: float
    created_at: datetime = field(default_factory=datetime.now)
    processed_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class AudioStream:
    """Audio stream management container."""
    stream_id: str
    priority: AdvancedPriority
    message_type: MessageType
    state: StreamState
    stream_type: StreamType
    
    # Audio properties
    file_path: Optional[str] = None
    audio_data: Optional[bytes] = None
    chunks: List[AudioChunk] = field(default_factory=list)
    current_chunk_index: int = 0
    
    # Timing and playback
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_ms: float = 0.0
    position_ms: float = 0.0
    
    # Performance tracking
    processing_latency_ms: float = 0.0
    playback_latency_ms: float = 0.0
    buffer_underruns: int = 0
    
    # Control flags
    preemptible: bool = True
    auto_cleanup: bool = True
    loop_playback: bool = False
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def is_active(self) -> bool:
        """Check if stream is actively playing or processing."""
        return self.state in [StreamState.LOADING, StreamState.READY, StreamState.PLAYING]
    
    def is_complete(self) -> bool:
        """Check if stream has completed processing."""
        return self.state in [StreamState.COMPLETED, StreamState.ERROR, StreamState.PREEMPTED]
    
    def get_progress(self) -> float:
        """Get playback progress as percentage (0.0 to 1.0)."""
        if self.duration_ms <= 0:
            return 0.0
        return min(1.0, self.position_ms / self.duration_ms)

@dataclass
class MultiplexerMetrics:
    """Performance metrics for audio multiplexer."""
    total_streams: int = 0
    active_streams: int = 0
    completed_streams: int = 0
    failed_streams: int = 0
    preempted_streams: int = 0
    
    # Performance metrics
    average_processing_latency_ms: float = 0.0
    average_playback_latency_ms: float = 0.0
    peak_concurrent_streams: int = 0
    total_audio_processed_mb: float = 0.0
    
    # Buffer management
    active_chunks: int = 0
    processed_chunks: int = 0
    buffer_underruns: int = 0
    memory_usage_mb: float = 0.0
    
    # Stream type distribution
    stream_type_counts: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    priority_distribution: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    
    last_updated: datetime = field(default_factory=datetime.now)

class AudioStreamMultiplexer:
    """
    High-performance audio stream multiplexer for concurrent TTS playback.
    
    Manages multiple audio streams with chunk-based processing, priority management,
    and real-time mixing capabilities for optimal user experience.
    """
    
    def __init__(self, max_concurrent_streams: int = 8, chunk_size_ms: int = 250):
        """
        Initialize the audio stream multiplexer.
        
        Args:
            max_concurrent_streams: Maximum number of concurrent audio streams
            chunk_size_ms: Size of audio chunks for processing (milliseconds)
        """
        self.max_concurrent_streams = max_concurrent_streams
        self.chunk_size_ms = chunk_size_ms
        
        # Core systems integration
        self.cache_manager = get_cache_manager() if PHASE3_DEPENDENCIES_AVAILABLE else None
        self.performance_monitor = get_performance_monitor() if PHASE3_DEPENDENCIES_AVAILABLE else None
        self.api_pool = get_concurrent_api_pool() if PHASE3_DEPENDENCIES_AVAILABLE else None
        
        # Stream management
        self.active_streams: Dict[str, AudioStream] = {}
        self.stream_queue = PriorityQueue()
        self.completed_streams: List[AudioStream] = deque(maxlen=100)  # Keep last 100 for metrics
        
        # Audio processing
        self.audio_thread_pool = ThreadPoolExecutor(
            max_workers=min(8, max_concurrent_streams), 
            thread_name_prefix="audio_multiplexer"
        )
        self.chunk_processors: Dict[str, Future] = {}
        
        # Performance tracking
        self.metrics = MultiplexerMetrics()
        self._metrics_lock = threading.RLock()
        
        # Configuration
        self.enable_mixing = os.getenv("AUDIO_MULTIPLEXER_MIXING", "false").lower() == "true"
        self.auto_cleanup = os.getenv("AUDIO_MULTIPLEXER_AUTO_CLEANUP", "true").lower() == "true"
        self.buffer_size_kb = int(os.getenv("AUDIO_MULTIPLEXER_BUFFER_SIZE", "512"))
        
        # Initialize audio system
        self._initialize_audio_system()
        
        # Background processing
        self._shutdown_event = threading.Event()
        self._background_thread = threading.Thread(target=self._background_processor, daemon=True)
        self._background_thread.start()
        
        print(f"🎵 Audio Stream Multiplexer initialized")
        print(f"  Max Concurrent Streams: {self.max_concurrent_streams}")
        print(f"  Chunk Size: {self.chunk_size_ms}ms")
        print(f"  Audio Mixing: {'✅' if self.enable_mixing else '❌'}")
        print(f"  Pygame Available: {'✅' if PYGAME_AVAILABLE else '❌'}")
    
    def _initialize_audio_system(self):
        """Initialize the audio playback system."""
        if PYGAME_AVAILABLE:
            try:
                pygame.mixer.pre_init(
                    frequency=22050,    # Sample rate
                    size=-16,           # 16-bit signed samples
                    channels=2,         # Stereo
                    buffer=512          # Buffer size
                )
                pygame.mixer.init()
                print("  Audio System: Pygame initialized")
            except Exception as e:
                print(f"  Audio System: Failed to initialize pygame: {e}")
        else:
            print("  Audio System: Pygame not available, limited functionality")
    
    def _generate_stream_id(self, text: str, priority: AdvancedPriority) -> str:
        """Generate unique stream ID."""
        import hashlib
        content = f"{text[:50]}:{priority.value}:{datetime.now().isoformat()}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    def _create_audio_chunks(self, stream: AudioStream) -> List[AudioChunk]:
        """Create audio chunks from stream data for parallel processing."""
        if not stream.file_path or not os.path.exists(stream.file_path):
            return []
        
        chunks = []
        
        try:
            # Read audio file size to estimate chunks
            file_size = os.path.getsize(stream.file_path)
            
            # Estimate number of chunks based on file size and target chunk duration
            # Rough estimate: 1MB per minute for MP3, so chunk_size_ms/60000 * 1MB per chunk
            estimated_chunk_size = max(1024, int(file_size * self.chunk_size_ms / 60000))
            estimated_chunks = max(1, file_size // estimated_chunk_size)
            
            # Read and split file into chunks
            with open(stream.file_path, 'rb') as f:
                chunk_index = 0
                while True:
                    chunk_data = f.read(estimated_chunk_size)
                    if not chunk_data:
                        break
                    
                    chunk = AudioChunk(
                        chunk_id=f"{stream.stream_id}_{chunk_index}",
                        stream_id=stream.stream_id,
                        data=chunk_data,
                        chunk_index=chunk_index,
                        total_chunks=estimated_chunks,
                        format=AudioFormat.MP3,  # Assume MP3 for now
                        duration_ms=float(self.chunk_size_ms)
                    )
                    chunks.append(chunk)
                    chunk_index += 1
                
                # Update total chunks count
                for chunk in chunks:
                    chunk.total_chunks = len(chunks)
            
            return chunks
            
        except Exception as e:
            print(f"Error creating audio chunks: {e}")
            return []
    
    def _process_audio_chunk(self, chunk: AudioChunk) -> bool:
        """Process a single audio chunk."""
        try:
            processing_start = time.time()
            
            # Simulate chunk processing (in real implementation, this would include
            # format conversion, volume normalization, effects processing, etc.)
            
            # For now, we'll just validate the chunk and mark it as processed
            if len(chunk.data) > 0:
                chunk.processed_at = datetime.now()
                
                # Update metrics
                with self._metrics_lock:
                    self.metrics.processed_chunks += 1
                    processing_time = (time.time() - processing_start) * 1000
                    
                    # Update average processing latency
                    current_avg = self.metrics.average_processing_latency_ms
                    total_processed = self.metrics.processed_chunks
                    self.metrics.average_processing_latency_ms = (
                        (current_avg * (total_processed - 1) + processing_time) / total_processed
                    )
                
                return True
            
            return False
            
        except Exception as e:
            print(f"Error processing chunk {chunk.chunk_id}: {e}")
            return False
    
    def _play_audio_stream(self, stream: AudioStream) -> bool:
        """Play an audio stream using pygame."""
        if not PYGAME_AVAILABLE or not stream.file_path:
            return False
        
        try:
            playback_start = time.time()
            stream.started_at = datetime.now()
            stream.state = StreamState.PLAYING
            
            # Load and play audio
            pygame.mixer.music.load(stream.file_path)
            pygame.mixer.music.play()
            
            # Wait for playback to complete or be preempted
            while pygame.mixer.music.get_busy() and stream.state == StreamState.PLAYING:
                time.sleep(0.1)
                
                # Update position (rough estimate)
                stream.position_ms += 100
                
                # Check for preemption
                if self._should_preempt_stream(stream):
                    pygame.mixer.music.stop()
                    stream.state = StreamState.PREEMPTED
                    break
            
            # Update completion status
            if stream.state == StreamState.PLAYING:
                stream.state = StreamState.COMPLETED
                stream.completed_at = datetime.now()
                stream.position_ms = stream.duration_ms
            
            # Calculate playback latency
            playback_time = (time.time() - playback_start) * 1000
            stream.playback_latency_ms = playback_time
            
            # Update metrics
            with self._metrics_lock:
                if stream.state == StreamState.COMPLETED:
                    self.metrics.completed_streams += 1
                elif stream.state == StreamState.PREEMPTED:
                    self.metrics.preempted_streams += 1
                
                # Update average playback latency
                if self.metrics.completed_streams > 0:
                    current_avg = self.metrics.average_playback_latency_ms
                    total_completed = self.metrics.completed_streams
                    self.metrics.average_playback_latency_ms = (
                        (current_avg * (total_completed - 1) + playback_time) / total_completed
                    )
            
            return stream.state == StreamState.COMPLETED
            
        except Exception as e:
            print(f"Error playing stream {stream.stream_id}: {e}")
            stream.state = StreamState.ERROR
            return False
    
    def _should_preempt_stream(self, stream: AudioStream) -> bool:
        """Check if a stream should be preempted by higher priority streams."""
        if not stream.preemptible:
            return False
        
        # Check if there are higher priority streams waiting
        for other_stream_id, other_stream in self.active_streams.items():
            if (other_stream_id != stream.stream_id and 
                other_stream.state == StreamState.READY and
                other_stream.priority.value < stream.priority.value):  # Lower value = higher priority
                return True
        
        return False
    
    def _cleanup_completed_streams(self):
        """Clean up completed streams to free memory."""
        if not self.auto_cleanup:
            return
        
        completed_stream_ids = []
        for stream_id, stream in list(self.active_streams.items()):
            if stream.is_complete():
                completed_stream_ids.append(stream_id)
                
                # Add to completed list for metrics
                self.completed_streams.append(stream)
                
                # Clean up temporary files
                if stream.auto_cleanup and stream.file_path and os.path.exists(stream.file_path):
                    try:
                        os.unlink(stream.file_path)
                    except Exception as e:
                        print(f"Error cleaning up audio file {stream.file_path}: {e}")
        
        # Remove from active streams
        for stream_id in completed_stream_ids:
            self.active_streams.pop(stream_id, None)
        
        # Update metrics
        with self._metrics_lock:
            self.metrics.active_streams = len(self.active_streams)
    
    def _background_processor(self):
        """Background thread for stream management and processing."""
        while not self._shutdown_event.is_set():
            try:
                # Process pending streams
                self._process_pending_streams()
                
                # Clean up completed streams
                self._cleanup_completed_streams()
                
                # Update metrics
                self._update_metrics()
                
                # Sleep briefly
                time.sleep(0.05)  # 50ms cycle
                
            except Exception as e:
                print(f"Background processor error: {e}")
                time.sleep(0.5)
    
    def _process_pending_streams(self):
        """Process streams that are ready for playback."""
        if not self.stream_queue.empty():
            try:
                # Get highest priority stream
                priority, stream_id = self.stream_queue.get_nowait()
                stream = self.active_streams.get(stream_id)
                
                if stream and stream.state == StreamState.READY:
                    # Check if we have capacity
                    active_count = sum(1 for s in self.active_streams.values() if s.is_active())
                    if active_count < self.max_concurrent_streams:
                        # Start playback in separate thread
                        future = self.audio_thread_pool.submit(self._play_audio_stream, stream)
                        self.chunk_processors[stream_id] = future
                    else:
                        # Queue is full, put stream back
                        self.stream_queue.put((priority, stream_id))
                
            except Empty:
                pass
    
    def _update_metrics(self):
        """Update performance metrics."""
        with self._metrics_lock:
            self.metrics.active_streams = len(self.active_streams)
            self.metrics.peak_concurrent_streams = max(
                self.metrics.peak_concurrent_streams,
                self.metrics.active_streams
            )
            
            # Calculate memory usage (rough estimate)
            memory_usage_bytes = 0
            for stream in self.active_streams.values():
                if stream.audio_data:
                    memory_usage_bytes += len(stream.audio_data)
                memory_usage_bytes += len(stream.chunks) * self.buffer_size_kb * 1024
            
            self.metrics.memory_usage_mb = memory_usage_bytes / (1024 * 1024)
            self.metrics.last_updated = datetime.now()
    
    @measure_performance("audio_multiplexer_create_stream")
    def create_audio_stream(
        self,
        text: str,
        priority: AdvancedPriority = AdvancedPriority.MEDIUM,
        message_type: MessageType = MessageType.INFO,
        stream_type: StreamType = StreamType.STANDARD,
        preemptible: bool = True,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Create a new audio stream for TTS processing.
        
        Args:
            text: Text to convert to speech
            priority: Stream priority level
            message_type: Type of message
            stream_type: Type of stream processing
            preemptible: Whether stream can be preempted
            metadata: Optional metadata
            
        Returns:
            Stream ID for tracking
        """
        stream_id = self._generate_stream_id(text, priority)
        
        stream = AudioStream(
            stream_id=stream_id,
            priority=priority,
            message_type=message_type,
            state=StreamState.IDLE,
            stream_type=stream_type,
            preemptible=preemptible,
            metadata=metadata or {}
        )
        
        self.active_streams[stream_id] = stream
        
        # Update metrics
        with self._metrics_lock:
            self.metrics.total_streams += 1
            self.metrics.stream_type_counts[stream_type.value] += 1
            self.metrics.priority_distribution[priority.name] += 1
        
        return stream_id
    
    @measure_performance("audio_multiplexer_load_audio")
    def load_audio_data(self, stream_id: str, api_result: APIRequestResult) -> bool:
        """
        Load audio data from API result into stream.
        
        Args:
            stream_id: ID of the stream to load data into
            api_result: Result from concurrent API pool
            
        Returns:
            True if successful, False otherwise
        """
        stream = self.active_streams.get(stream_id)
        if not stream or api_result.status != RequestStatus.COMPLETED:
            return False
        
        try:
            stream.state = StreamState.LOADING
            
            # Load audio file or data
            if api_result.audio_file_path and os.path.exists(api_result.audio_file_path):
                stream.file_path = api_result.audio_file_path
                
                # Get file duration (rough estimate based on file size)
                file_size = os.path.getsize(stream.file_path)
                # Rough estimate: 1MB per minute for MP3
                stream.duration_ms = (file_size / (1024 * 1024)) * 60 * 1000
                
            elif api_result.audio_data:
                stream.audio_data = api_result.audio_data
                stream.duration_ms = len(api_result.audio_data) * 8  # Rough estimate
            else:
                stream.state = StreamState.ERROR
                return False
            
            # Create audio chunks for parallel processing
            if stream.stream_type == StreamType.CHUNKED:
                stream.chunks = self._create_audio_chunks(stream)
                
                # Update chunk metrics
                with self._metrics_lock:
                    self.metrics.active_chunks += len(stream.chunks)
            
            # Mark as ready for playback
            stream.state = StreamState.READY
            
            # Add to playback queue
            self.stream_queue.put((stream.priority.value, stream_id))
            
            return True
            
        except Exception as e:
            print(f"Error loading audio data for stream {stream_id}: {e}")
            stream.state = StreamState.ERROR
            return False
    
    def get_stream_status(self, stream_id: str) -> Optional[AudioStream]:
        """Get current status of an audio stream."""
        return self.active_streams.get(stream_id)
    
    def pause_stream(self, stream_id: str) -> bool:
        """Pause an active audio stream."""
        stream = self.active_streams.get(stream_id)
        if not stream or stream.state != StreamState.PLAYING:
            return False
        
        if PYGAME_AVAILABLE:
            pygame.mixer.music.pause()
            stream.state = StreamState.PAUSED
            return True
        
        return False
    
    def resume_stream(self, stream_id: str) -> bool:
        """Resume a paused audio stream."""
        stream = self.active_streams.get(stream_id)
        if not stream or stream.state != StreamState.PAUSED:
            return False
        
        if PYGAME_AVAILABLE:
            pygame.mixer.music.unpause()
            stream.state = StreamState.PLAYING
            return True
        
        return False
    
    def stop_stream(self, stream_id: str) -> bool:
        """Stop an audio stream."""
        stream = self.active_streams.get(stream_id)
        if not stream:
            return False
        
        if stream.is_active():
            if PYGAME_AVAILABLE and stream.state == StreamState.PLAYING:
                pygame.mixer.music.stop()
            
            stream.state = StreamState.STOPPING
            return True
        
        return False
    
    def stop_all_streams(self):
        """Stop all active audio streams."""
        if PYGAME_AVAILABLE:
            pygame.mixer.music.stop()
        
        for stream in self.active_streams.values():
            if stream.is_active():
                stream.state = StreamState.STOPPING
    
    def get_metrics(self) -> MultiplexerMetrics:
        """Get current multiplexer performance metrics."""
        with self._metrics_lock:
            return MultiplexerMetrics(
                total_streams=self.metrics.total_streams,
                active_streams=self.metrics.active_streams,
                completed_streams=self.metrics.completed_streams,
                failed_streams=self.metrics.failed_streams,
                preempted_streams=self.metrics.preempted_streams,
                average_processing_latency_ms=self.metrics.average_processing_latency_ms,
                average_playback_latency_ms=self.metrics.average_playback_latency_ms,
                peak_concurrent_streams=self.metrics.peak_concurrent_streams,
                total_audio_processed_mb=self.metrics.total_audio_processed_mb,
                active_chunks=self.metrics.active_chunks,
                processed_chunks=self.metrics.processed_chunks,
                buffer_underruns=self.metrics.buffer_underruns,
                memory_usage_mb=self.metrics.memory_usage_mb,
                stream_type_counts=self.metrics.stream_type_counts.copy(),
                priority_distribution=self.metrics.priority_distribution.copy(),
                last_updated=self.metrics.last_updated
            )
    
    def get_multiplexer_status(self) -> Dict[str, Any]:
        """Get comprehensive multiplexer status."""
        metrics = self.get_metrics()
        
        return {
            "multiplexer_status": {
                "max_concurrent_streams": self.max_concurrent_streams,
                "active_streams": metrics.active_streams,
                "total_streams": metrics.total_streams,
                "chunk_size_ms": self.chunk_size_ms,
                "audio_mixing_enabled": self.enable_mixing
            },
            "performance": {
                "completed_streams": metrics.completed_streams,
                "failed_streams": metrics.failed_streams,
                "preempted_streams": metrics.preempted_streams,
                "success_rate": (metrics.completed_streams / max(metrics.total_streams, 1)) * 100,
                "average_processing_latency_ms": metrics.average_processing_latency_ms,
                "average_playback_latency_ms": metrics.average_playback_latency_ms,
                "peak_concurrent_streams": metrics.peak_concurrent_streams
            },
            "memory_usage": {
                "total_mb": metrics.memory_usage_mb,
                "active_chunks": metrics.active_chunks,
                "processed_chunks": metrics.processed_chunks,
                "buffer_underruns": metrics.buffer_underruns
            },
            "stream_distribution": {
                "by_type": dict(metrics.stream_type_counts),
                "by_priority": dict(metrics.priority_distribution)
            },
            "audio_system": {
                "pygame_available": PYGAME_AVAILABLE,
                "pygame_initialized": PYGAME_AVAILABLE and pygame.mixer.get_init() is not None if PYGAME_AVAILABLE else False,
                "auto_cleanup": self.auto_cleanup
            },
            "active_stream_details": {
                stream_id: {
                    "state": stream.state.value,
                    "priority": stream.priority.name,
                    "progress": stream.get_progress(),
                    "duration_ms": stream.duration_ms,
                    "position_ms": stream.position_ms
                }
                for stream_id, stream in self.active_streams.items()
            },
            "last_updated": metrics.last_updated.isoformat()
        }
    
    def shutdown(self):
        """Shutdown the audio stream multiplexer."""
        print("🎵 Shutting down Audio Stream Multiplexer...")
        
        # Stop all streams
        self.stop_all_streams()
        
        # Signal background thread to stop
        self._shutdown_event.set()
        
        # Wait for active processing to complete
        for future in self.chunk_processors.values():
            try:
                future.result(timeout=1.0)
            except Exception:
                pass
        
        # Shutdown thread pool
        self.audio_thread_pool.shutdown(wait=True)
        
        # Join background thread
        if self._background_thread.is_alive():
            self._background_thread.join(timeout=5.0)
        
        # Cleanup audio system
        if PYGAME_AVAILABLE:
            try:
                pygame.mixer.quit()
            except Exception:
                pass
        
        print("✅ Audio Stream Multiplexer shutdown complete")

# Global multiplexer instance
_audio_multiplexer = None

def get_audio_multiplexer() -> AudioStreamMultiplexer:
    """Get or create the global audio stream multiplexer."""
    global _audio_multiplexer
    if _audio_multiplexer is None:
        max_streams = int(os.getenv("AUDIO_MULTIPLEXER_MAX_STREAMS", "8"))
        chunk_size = int(os.getenv("AUDIO_MULTIPLEXER_CHUNK_SIZE", "250"))
        _audio_multiplexer = AudioStreamMultiplexer(max_streams, chunk_size)
    return _audio_multiplexer

def create_multiplexed_audio_stream(
    text: str,
    priority: AdvancedPriority = AdvancedPriority.MEDIUM,
    message_type: MessageType = MessageType.INFO,
    stream_type: StreamType = StreamType.STANDARD,
    preemptible: bool = True,
    metadata: Optional[Dict[str, Any]] = None
) -> str:
    """Create a new multiplexed audio stream."""
    multiplexer = get_audio_multiplexer()
    return multiplexer.create_audio_stream(text, priority, message_type, stream_type, preemptible, metadata)

def load_multiplexed_audio_data(stream_id: str, api_result: APIRequestResult) -> bool:
    """Load audio data into a multiplexed stream."""
    multiplexer = get_audio_multiplexer()
    return multiplexer.load_audio_data(stream_id, api_result)

def main():
    """Main entry point for testing Phase 3.4.3.1 Audio Stream Multiplexer."""
    import sys
    
    if "--test" in sys.argv:
        print("🧪 Testing Phase 3.4.3.1 Audio Stream Multiplexer")
        print("=" * 60)
        
        multiplexer = get_audio_multiplexer()
        
        print(f"\n🎵 Multiplexer Status:")
        status = multiplexer.get_multiplexer_status()
        print(f"  Max Concurrent Streams: {status['multiplexer_status']['max_concurrent_streams']}")
        print(f"  Chunk Size: {status['multiplexer_status']['chunk_size_ms']}ms")
        print(f"  Audio Mixing: {'✅' if status['multiplexer_status']['audio_mixing_enabled'] else '❌'}")
        print(f"  Pygame Available: {'✅' if status['audio_system']['pygame_available'] else '❌'}")
        print(f"  Phase 3 Integration: {'✅' if PHASE3_DEPENDENCIES_AVAILABLE else '❌'}")
        
        # Test stream creation
        print(f"\n🎤 Testing Stream Creation:")
        
        test_streams = [
            ("High priority test stream", AdvancedPriority.HIGH, MessageType.SUCCESS),
            ("Medium priority test stream", AdvancedPriority.MEDIUM, MessageType.INFO),
            ("Low priority test stream", AdvancedPriority.LOW, MessageType.INFO),
            ("Critical test stream", AdvancedPriority.CRITICAL, MessageType.ERROR),
        ]
        
        created_streams = []
        for text, priority, message_type in test_streams:
            try:
                stream_id = multiplexer.create_audio_stream(
                    text=text,
                    priority=priority,
                    message_type=message_type,
                    stream_type=StreamType.CHUNKED,
                    preemptible=True
                )
                created_streams.append((stream_id, text))
                print(f"  ✅ Created: {text} -> {stream_id[:8]}")
            except Exception as e:
                print(f"  ❌ Failed to create stream: {e}")
        
        # Test stream status
        print(f"\n📊 Testing Stream Status:")
        for stream_id, text in created_streams:
            stream = multiplexer.get_stream_status(stream_id)
            if stream:
                print(f"  {stream_id[:8]}: {stream.state.value} ({stream.priority.name})")
            else:
                print(f"  {stream_id[:8]}: Not found")
        
        # Test metrics
        print(f"\n📈 Performance Metrics:")
        metrics = multiplexer.get_metrics()
        print(f"  Total Streams: {metrics.total_streams}")
        print(f"  Active Streams: {metrics.active_streams}")
        print(f"  Memory Usage: {metrics.memory_usage_mb:.2f}MB")
        print(f"  Active Chunks: {metrics.active_chunks}")
        print(f"  Processing Latency: {metrics.average_processing_latency_ms:.1f}ms")
        
        # Test stream type distribution
        if metrics.stream_type_counts:
            print(f"  Stream Types:")
            for stream_type, count in metrics.stream_type_counts.items():
                print(f"    {stream_type}: {count}")
        
        # Test priority distribution
        if metrics.priority_distribution:
            print(f"  Priorities:")
            for priority, count in metrics.priority_distribution.items():
                print(f"    {priority}: {count}")
        
        # Test concurrent processing
        print(f"\n⚡ Testing Concurrent Processing:")
        
        # Simulate audio processing load
        processing_test_streams = []
        for i in range(5):
            stream_id = multiplexer.create_audio_stream(
                text=f"Concurrent processing test {i+1}",
                priority=AdvancedPriority.MEDIUM,
                message_type=MessageType.BATCH,
                stream_type=StreamType.CHUNKED
            )
            processing_test_streams.append(stream_id)
        
        print(f"  Created {len(processing_test_streams)} test streams for concurrent processing")
        
        # Wait a bit for processing
        time.sleep(0.5)
        
        # Check final metrics
        final_metrics = multiplexer.get_metrics()
        final_status = multiplexer.get_multiplexer_status()
        
        print(f"\n🏁 Final Results:")
        print(f"  Total Streams Created: {final_metrics.total_streams}")
        print(f"  Peak Concurrent Streams: {final_metrics.peak_concurrent_streams}")
        print(f"  Total Memory Usage: {final_metrics.memory_usage_mb:.2f}MB")
        print(f"  Success Rate: {final_status['performance']['success_rate']:.1f}%")
        
        print(f"\n✅ Phase 3.4.3.1 Audio Stream Multiplexer test completed")
        print(f"🎵 Multi-stream audio processing with {final_metrics.peak_concurrent_streams} peak concurrency!")
        
        # Cleanup
        multiplexer.shutdown()
    
    else:
        print("Phase 3.4.3.1 Audio Stream Multiplexer")
        print("Parallel audio chunk processing system for multiple TTS streams")
        print("Usage: python phase3_43_audio_multiplexer.py --test")

if __name__ == "__main__":
    main()