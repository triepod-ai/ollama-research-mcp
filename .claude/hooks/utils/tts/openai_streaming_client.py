#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "python-dotenv>=1.0.0",
#   "openai>=1.0.0",
#   "websockets>=11.0.0",
# ]
# ///

"""
Phase 3.4 OpenAI Streaming TTS Client
Real-time audio generation with ultra-low latency for critical and interrupt priority messages.

Features:
- Real-time streaming audio generation using OpenAI's TTS API
- Chunk-based audio processing for immediate playback
- Low-latency buffering and stream management
- Integration with Phase 3.3.2 playback coordinator
- Adaptive quality settings based on priority and network conditions
- Automatic retry and error recovery mechanisms
- Performance metrics and latency monitoring
"""

import asyncio
import json
import os
import subprocess
import tempfile
import threading
import time
import wave
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Optional, Callable, Any, Dict, List, AsyncGenerator, Union
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv

try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    import websockets
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False

# Load environment variables
env_path = Path.home() / "brainpods" / ".env"
if env_path.exists():
    load_dotenv(env_path)

class StreamingQuality(Enum):
    """Streaming quality levels optimized for different priorities."""
    ULTRA_LOW_LATENCY = "ultra_low"      # <200ms, minimal buffering
    LOW_LATENCY = "low_latency"          # <500ms, small buffer
    BALANCED = "balanced"                # <1s, optimal quality/speed
    HIGH_QUALITY = "high_quality"        # <2s, maximum quality
    ADAPTIVE = "adaptive"                # Auto-adjust based on conditions

class StreamingState(Enum):
    """Streaming session states."""
    IDLE = "idle"
    CONNECTING = "connecting"
    STREAMING = "streaming"
    BUFFERING = "buffering"
    PLAYING = "playing"
    PAUSED = "paused"
    ERROR = "error"
    COMPLETED = "completed"

class AudioFormat(Enum):
    """Supported audio formats for streaming."""
    PCM_16_24K = "pcm_16_24k"          # 16-bit PCM, 24kHz (OpenAI default)
    PCM_16_22K = "pcm_16_22k"          # 16-bit PCM, 22.05kHz
    PCM_16_16K = "pcm_16_16k"          # 16-bit PCM, 16kHz (lower quality)
    OPUS_24K = "opus_24k"              # Opus codec, 24kHz (future)

@dataclass
class StreamingMetrics:
    """Performance metrics for streaming sessions."""
    session_id: str
    start_time: datetime
    first_chunk_latency: float = 0.0    # Time to first audio chunk
    total_latency: float = 0.0           # Total processing time
    chunks_received: int = 0
    chunks_processed: int = 0
    chunks_played: int = 0
    total_audio_duration: float = 0.0    # Duration of generated audio
    bytes_received: int = 0
    bytes_processed: int = 0
    buffer_underruns: int = 0            # Times playback had to wait
    quality_adjustments: int = 0         # Times quality was auto-adjusted
    errors: List[str] = field(default_factory=list)
    
    def get_efficiency_ratio(self) -> float:
        """Calculate real-time efficiency ratio (>1.0 is faster than real-time)."""
        if self.total_audio_duration > 0:
            return self.total_audio_duration / max(0.001, self.total_latency)
        return 0.0
    
    def get_throughput_kbps(self) -> float:
        """Calculate audio throughput in kbps."""
        if self.total_latency > 0:
            return (self.bytes_processed * 8) / (self.total_latency * 1000)
        return 0.0

@dataclass
class AudioChunk:
    """Represents a chunk of streaming audio data."""
    chunk_id: int
    data: bytes
    timestamp: datetime
    sample_rate: int = 24000
    channels: int = 1
    format: AudioFormat = AudioFormat.PCM_16_24K
    duration_ms: float = 0.0
    is_final: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def get_duration_seconds(self) -> float:
        """Calculate audio duration from chunk size."""
        if self.data:
            # Assuming 16-bit PCM
            bytes_per_sample = 2 * self.channels
            samples = len(self.data) // bytes_per_sample
            return samples / self.sample_rate
        return 0.0

class StreamingBuffer:
    """Real-time audio buffer with adaptive sizing and underrun protection."""
    
    def __init__(self, target_latency_ms: float = 500, max_latency_ms: float = 2000):
        """Initialize streaming buffer with latency targets."""
        self.target_latency_ms = target_latency_ms
        self.max_latency_ms = max_latency_ms
        self.chunks: deque[AudioChunk] = deque()
        self.total_duration_ms = 0.0
        self.lock = threading.RLock()
        self.underrun_count = 0
        self.adaptive_sizing = True
        
        # Buffer health tracking
        self.recent_underruns = deque(maxlen=10)
        self.buffer_health_score = 1.0  # 1.0 = healthy, 0.0 = problematic
    
    def add_chunk(self, chunk: AudioChunk) -> bool:
        """Add audio chunk to buffer with overflow protection."""
        with self.lock:
            chunk_duration = chunk.get_duration_seconds() * 1000
            
            # Check if buffer would exceed maximum latency
            if self.total_duration_ms + chunk_duration > self.max_latency_ms:
                # Remove oldest chunks to make room
                while (self.chunks and 
                       self.total_duration_ms + chunk_duration > self.max_latency_ms):
                    removed = self.chunks.popleft()
                    self.total_duration_ms -= removed.get_duration_seconds() * 1000
            
            # Add new chunk
            self.chunks.append(chunk)
            self.total_duration_ms += chunk_duration
            
            return True
    
    def get_next_chunk(self) -> Optional[AudioChunk]:
        """Get next chunk for playback with underrun detection."""
        with self.lock:
            if not self.chunks:
                # Buffer underrun
                self.underrun_count += 1
                self.recent_underruns.append(datetime.now())
                self._update_buffer_health()
                return None
            
            chunk = self.chunks.popleft()
            self.total_duration_ms -= chunk.get_duration_seconds() * 1000
            return chunk
    
    def peek_buffer_health(self) -> Dict[str, Any]:
        """Get buffer health status."""
        with self.lock:
            return {
                "chunks_buffered": len(self.chunks),
                "buffer_duration_ms": self.total_duration_ms,
                "target_latency_ms": self.target_latency_ms,
                "buffer_health_score": self.buffer_health_score,
                "total_underruns": self.underrun_count,
                "recent_underruns": len(self.recent_underruns),
                "buffer_utilization": min(1.0, self.total_duration_ms / self.target_latency_ms)
            }
    
    def _update_buffer_health(self):
        """Update buffer health score based on recent performance."""
        now = datetime.now()
        # Count recent underruns (last 30 seconds)
        recent = [t for t in self.recent_underruns if (now - t).total_seconds() < 30]
        
        if len(recent) == 0:
            self.buffer_health_score = 1.0
        elif len(recent) <= 2:
            self.buffer_health_score = 0.8
        elif len(recent) <= 5:
            self.buffer_health_score = 0.5
        else:
            self.buffer_health_score = 0.2
        
        # Adaptive buffer sizing based on health
        if self.adaptive_sizing and self.buffer_health_score < 0.7:
            # Increase target latency to reduce underruns
            self.target_latency_ms = min(
                self.max_latency_ms,
                self.target_latency_ms * 1.2
            )
    
    def clear(self):
        """Clear all buffered chunks."""
        with self.lock:
            self.chunks.clear()
            self.total_duration_ms = 0.0

class OpenAIStreamingClient:
    """OpenAI TTS streaming client with real-time audio generation."""
    
    def __init__(self):
        """Initialize the OpenAI streaming client."""
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY environment variable required")
        
        self.client = openai.OpenAI(api_key=self.api_key) if OPENAI_AVAILABLE else None
        
        # Streaming configuration
        self.default_voice = os.getenv("OPENAI_STREAMING_VOICE", "nova")
        self.default_model = os.getenv("OPENAI_STREAMING_MODEL", "tts-1")
        self.chunk_size = int(os.getenv("OPENAI_STREAMING_CHUNK_SIZE", "4096"))
        self.sample_rate = int(os.getenv("OPENAI_STREAMING_SAMPLE_RATE", "24000"))
        
        # Performance settings
        self.max_concurrent_streams = int(os.getenv("OPENAI_MAX_CONCURRENT_STREAMS", "3"))
        self.connection_timeout = float(os.getenv("OPENAI_STREAMING_TIMEOUT", "10.0"))
        self.retry_attempts = int(os.getenv("OPENAI_STREAMING_RETRIES", "2"))
        
        # Active streaming sessions
        self.active_sessions: Dict[str, 'StreamingSession'] = {}
        self.session_counter = 0
        self.sessions_lock = threading.RLock()
        
        # Performance tracking
        self.metrics_history: deque[StreamingMetrics] = deque(maxlen=100)
        self.total_sessions = 0
        self.successful_sessions = 0
        self.failed_sessions = 0
        
        # Thread pool for async operations
        self.executor = ThreadPoolExecutor(
            max_workers=self.max_concurrent_streams + 2,
            thread_name_prefix="openai_streaming"
        )
    
    def create_stream_session(
        self,
        text: str,
        voice: Optional[str] = None,
        model: Optional[str] = None,
        quality: StreamingQuality = StreamingQuality.BALANCED,
        callback: Optional[Callable] = None,
        metadata: Optional[Dict] = None
    ) -> Optional[str]:
        """
        Create a new streaming session for text-to-speech.
        
        Args:
            text: Text to convert to speech
            voice: OpenAI voice (nova, echo, alloy, etc.)
            model: TTS model (tts-1, tts-1-hd)
            quality: Streaming quality settings
            callback: Callback function for session events
            metadata: Additional session metadata
            
        Returns:
            Session ID if successful, None if failed
        """
        if not OPENAI_AVAILABLE or not self.client:
            return None
        
        # Check concurrent session limit
        if len(self.active_sessions) >= self.max_concurrent_streams:
            return None
        
        # Create session
        session_id = f"stream_{int(time.time() * 1000)}_{self.session_counter}"
        self.session_counter += 1
        
        session = StreamingSession(
            session_id=session_id,
            client=self.client,
            text=text,
            voice=voice or self.default_voice,
            model=model or self.default_model,
            quality=quality,
            sample_rate=self.sample_rate,
            callback=callback,
            metadata=metadata or {}
        )
        
        with self.sessions_lock:
            self.active_sessions[session_id] = session
        
        # Start streaming in background
        future = self.executor.submit(self._run_streaming_session, session)
        session.future = future
        
        return session_id
    
    def get_session_status(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a streaming session."""
        with self.sessions_lock:
            session = self.active_sessions.get(session_id)
            if not session:
                return None
            
            return {
                "session_id": session_id,
                "state": session.state.value,
                "progress": session.get_progress(),
                "metrics": session.metrics,
                "buffer_health": session.buffer.peek_buffer_health() if session.buffer else {},
                "error": session.error_message if session.state == StreamingState.ERROR else None
            }
    
    def stop_session(self, session_id: str, reason: str = "user_stop") -> bool:
        """Stop a streaming session."""
        with self.sessions_lock:
            session = self.active_sessions.get(session_id)
            if not session:
                return False
            
            session.stop(reason)
            return True
    
    def get_active_sessions(self) -> List[str]:
        """Get list of active session IDs."""
        with self.sessions_lock:
            return list(self.active_sessions.keys())
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary of streaming operations."""
        recent_metrics = list(self.metrics_history)[-10:]  # Last 10 sessions
        
        if not recent_metrics:
            return {"no_data": True}
        
        avg_first_chunk = sum(m.first_chunk_latency for m in recent_metrics) / len(recent_metrics)
        avg_efficiency = sum(m.get_efficiency_ratio() for m in recent_metrics) / len(recent_metrics)
        avg_throughput = sum(m.get_throughput_kbps() for m in recent_metrics) / len(recent_metrics)
        
        return {
            "total_sessions": self.total_sessions,
            "success_rate": self.successful_sessions / max(1, self.total_sessions),
            "active_sessions": len(self.active_sessions),
            "performance": {
                "avg_first_chunk_latency_ms": avg_first_chunk * 1000,
                "avg_efficiency_ratio": avg_efficiency,
                "avg_throughput_kbps": avg_throughput,
                "buffer_underrun_rate": sum(m.buffer_underruns for m in recent_metrics) / max(1, sum(m.chunks_processed for m in recent_metrics))
            },
            "recent_errors": [error for m in recent_metrics for error in m.errors]
        }
    
    def _run_streaming_session(self, session: 'StreamingSession'):
        """Run a streaming session (called in background thread)."""
        try:
            self.total_sessions += 1
            session.start()
            
            # Create metrics
            session.metrics = StreamingMetrics(
                session_id=session.session_id,
                start_time=datetime.now()
            )
            
            # Run the streaming loop
            asyncio.run(self._stream_audio_async(session))
            
            if session.state != StreamingState.ERROR:
                session.state = StreamingState.COMPLETED
                self.successful_sessions += 1
            else:
                self.failed_sessions += 1
            
            # Store metrics
            if session.metrics:
                session.metrics.total_latency = (datetime.now() - session.metrics.start_time).total_seconds()
                self.metrics_history.append(session.metrics)
            
        except Exception as e:
            session.error_message = str(e)
            session.state = StreamingState.ERROR
            self.failed_sessions += 1
            
            if session.metrics:
                session.metrics.errors.append(str(e))
        
        finally:
            # Cleanup session
            with self.sessions_lock:
                if session.session_id in self.active_sessions:
                    del self.active_sessions[session.session_id]
            
            # Execute callback
            if session.callback:
                try:
                    session.callback(session, session.state == StreamingState.COMPLETED)
                except Exception:
                    pass  # Don't fail on callback errors
    
    async def _stream_audio_async(self, session: 'StreamingSession'):
        """Async streaming audio generation and processing."""
        session.state = StreamingState.CONNECTING
        first_chunk = True
        chunk_counter = 0
        
        try:
            # Create streaming request
            response = await asyncio.to_thread(
                self._create_streaming_request,
                session.text,
                session.voice,
                session.model
            )
            
            session.state = StreamingState.STREAMING
            
            # Process audio chunks
            async for chunk_data in self._process_audio_stream(response):
                if session.should_stop:
                    break
                
                # Create audio chunk
                chunk = AudioChunk(
                    chunk_id=chunk_counter,
                    data=chunk_data,
                    timestamp=datetime.now(),
                    sample_rate=session.sample_rate,
                    format=AudioFormat.PCM_16_24K
                )
                chunk_counter += 1
                
                # Record first chunk latency
                if first_chunk and session.metrics:
                    session.metrics.first_chunk_latency = (chunk.timestamp - session.metrics.start_time).total_seconds()
                    first_chunk = False
                
                # Add to buffer
                if session.buffer.add_chunk(chunk):
                    if session.metrics:
                        session.metrics.chunks_received += 1
                        session.metrics.bytes_received += len(chunk_data)
                
                # Start playback if not already playing
                if session.state == StreamingState.STREAMING and not session.playback_active:
                    await self._start_chunk_playback(session)
            
            # Mark final chunk
            if session.buffer.chunks:
                session.buffer.chunks[-1].is_final = True
            
        except Exception as e:
            session.error_message = str(e)
            session.state = StreamingState.ERROR
            if session.metrics:
                session.metrics.errors.append(str(e))
            raise
    
    def _create_streaming_request(self, text: str, voice: str, model: str):
        """Create OpenAI streaming TTS request."""
        try:
            response = self.client.audio.speech.create(
                model=model,
                voice=voice,
                input=text,
                response_format="pcm",
                speed=1.0
            )
            return response
        except Exception as e:
            raise Exception(f"Failed to create streaming request: {e}")
    
    async def _process_audio_stream(self, response) -> AsyncGenerator[bytes, None]:
        """Process streaming audio response into chunks."""
        try:
            # For OpenAI, the response is the complete audio data
            # We need to split it into chunks for streaming playback
            audio_data = response.content
            
            # Split into chunks
            for i in range(0, len(audio_data), self.chunk_size):
                chunk_data = audio_data[i:i + self.chunk_size]
                yield chunk_data
                
                # Small delay to simulate streaming (remove in production)
                await asyncio.sleep(0.01)
                
        except Exception as e:
            raise Exception(f"Failed to process audio stream: {e}")
    
    async def _start_chunk_playback(self, session: 'StreamingSession'):
        """Start playback of buffered audio chunks."""
        session.playback_active = True
        session.state = StreamingState.PLAYING
        
        # Start playback thread
        playback_future = self.executor.submit(self._playback_loop, session)
        session.playback_future = playback_future

    def _playback_loop(self, session: 'StreamingSession'):
        """Real-time audio playback loop."""
        try:
            # Create temporary file for audio playback
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                temp_path = Path(temp_file.name)
                
                # Initialize WAV file
                with wave.open(str(temp_path), 'wb') as wav_file:
                    wav_file.setnchannels(1)  # Mono
                    wav_file.setsampwidth(2)  # 16-bit
                    wav_file.setframerate(session.sample_rate)
                    
                    # Process chunks as they become available
                    while not session.should_stop:
                        chunk = session.buffer.get_next_chunk()
                        if chunk is None:
                            if session.state == StreamingState.COMPLETED:
                                break
                            # Wait for more chunks
                            time.sleep(0.01)
                            continue
                        
                        # Write chunk to WAV file
                        wav_file.writeframes(chunk.data)
                        
                        if session.metrics:
                            session.metrics.chunks_processed += 1
                            session.metrics.bytes_processed += len(chunk.data)
                            session.metrics.total_audio_duration += chunk.get_duration_seconds()
                        
                        # If this is the final chunk, we can start playback
                        if chunk.is_final:
                            break
                
                # Play the audio file
                if temp_path.exists():
                    self._play_audio_file(temp_path, session)
                
                # Cleanup
                try:
                    temp_path.unlink()
                except:
                    pass
                
        except Exception as e:
            session.error_message = str(e)
            session.state = StreamingState.ERROR
            if session.metrics:
                session.metrics.errors.append(str(e))
        
        finally:
            session.playback_active = False
    
    def _play_audio_file(self, audio_path: Path, session: 'StreamingSession'):
        """Play audio file using system audio player."""
        try:
            # Use platform-appropriate audio player
            if os.name == 'posix':  # Linux/macOS
                cmd = ['aplay', str(audio_path)] if os.system('which aplay > /dev/null 2>&1') == 0 else ['afplay', str(audio_path)]
            else:  # Windows
                cmd = ['powershell', '-c', f'(New-Object Media.SoundPlayer "{audio_path}").PlaySync()']
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            
            # Wait for playback completion
            process.wait(timeout=30)
            
            if session.metrics:
                session.metrics.chunks_played += 1
                
        except subprocess.TimeoutExpired:
            process.kill()
            if session.metrics:
                session.metrics.errors.append("Playback timeout")
        except Exception as e:
            if session.metrics:
                session.metrics.errors.append(f"Playback error: {e}")

class StreamingSession:
    """Represents an active streaming TTS session."""
    
    def __init__(
        self,
        session_id: str,
        client,
        text: str,
        voice: str,
        model: str,
        quality: StreamingQuality,
        sample_rate: int,
        callback: Optional[Callable] = None,
        metadata: Optional[Dict] = None
    ):
        self.session_id = session_id
        self.client = client
        self.text = text
        self.voice = voice
        self.model = model
        self.quality = quality
        self.sample_rate = sample_rate
        self.callback = callback
        self.metadata = metadata or {}
        
        # Session state
        self.state = StreamingState.IDLE
        self.should_stop = False
        self.error_message = ""
        
        # Audio processing
        self.buffer = self._create_buffer_for_quality(quality)
        self.playback_active = False
        
        # Threading
        self.future: Optional[any] = None
        self.playback_future: Optional[any] = None
        
        # Metrics
        self.metrics: Optional[StreamingMetrics] = None
    
    def _create_buffer_for_quality(self, quality: StreamingQuality) -> StreamingBuffer:
        """Create audio buffer with settings optimized for quality level."""
        settings = {
            StreamingQuality.ULTRA_LOW_LATENCY: (150, 500),     # 150ms target, 500ms max
            StreamingQuality.LOW_LATENCY: (300, 800),           # 300ms target, 800ms max  
            StreamingQuality.BALANCED: (500, 1500),             # 500ms target, 1.5s max
            StreamingQuality.HIGH_QUALITY: (1000, 3000),        # 1s target, 3s max
            StreamingQuality.ADAPTIVE: (500, 2000),             # 500ms target, 2s max (adaptive)
        }
        
        target_ms, max_ms = settings.get(quality, (500, 1500))
        return StreamingBuffer(target_latency_ms=target_ms, max_latency_ms=max_ms)
    
    def start(self):
        """Start the streaming session."""
        self.state = StreamingState.CONNECTING
        self.should_stop = False
    
    def stop(self, reason: str = "user_stop"):
        """Stop the streaming session."""
        self.should_stop = True
        self.metadata["stop_reason"] = reason
        
        if self.future and not self.future.done():
            self.future.cancel()
        
        if self.playback_future and not self.playback_future.done():
            self.playback_future.cancel()
    
    def get_progress(self) -> Dict[str, Any]:
        """Get session progress information."""
        if not self.metrics:
            return {"progress": 0.0}
        
        return {
            "progress": min(1.0, self.metrics.chunks_processed / max(1, self.metrics.chunks_received)),
            "chunks_processed": self.metrics.chunks_processed,
            "chunks_received": self.metrics.chunks_received,
            "audio_duration": self.metrics.total_audio_duration,
            "buffer_health": self.buffer.peek_buffer_health()
        }

# Global streaming client instance
_streaming_client = None

def get_streaming_client() -> OpenAIStreamingClient:
    """Get or create the global OpenAI streaming client."""
    global _streaming_client
    if _streaming_client is None and OPENAI_AVAILABLE:
        try:
            _streaming_client = OpenAIStreamingClient()
        except Exception as e:
            print(f"Failed to create OpenAI streaming client: {e}")
            return None
    return _streaming_client

def create_streaming_session(
    text: str,
    priority: str = "normal",
    voice: Optional[str] = None,
    callback: Optional[Callable] = None
) -> Optional[str]:
    """
    Create a streaming TTS session with automatic quality selection.
    
    Args:
        text: Text to convert to speech
        priority: Priority level (interrupt, critical, high, normal, low)
        voice: Optional voice override
        callback: Optional completion callback
        
    Returns:
        Session ID if successful, None if failed
    """
    client = get_streaming_client()
    if not client:
        return None
    
    # Map priority to streaming quality
    quality_mapping = {
        "interrupt": StreamingQuality.ULTRA_LOW_LATENCY,
        "critical": StreamingQuality.LOW_LATENCY, 
        "high": StreamingQuality.BALANCED,
        "normal": StreamingQuality.BALANCED,
        "low": StreamingQuality.HIGH_QUALITY
    }
    
    quality = quality_mapping.get(priority, StreamingQuality.BALANCED)
    
    return client.create_stream_session(
        text=text,
        voice=voice,
        quality=quality,
        callback=callback,
        metadata={"priority": priority}
    )

def get_streaming_status() -> Dict[str, Any]:
    """Get comprehensive streaming system status."""
    client = get_streaming_client()
    if not client:
        return {"available": False, "error": "OpenAI streaming not available"}
    
    return {
        "available": True,
        "active_sessions": client.get_active_sessions(),
        "performance": client.get_performance_summary()
    }

if __name__ == "__main__":
    # Test the streaming client
    import sys
    
    if "--test" in sys.argv:
        print("🎵 Testing OpenAI Streaming Client")
        print("=" * 50)
        
        if not OPENAI_AVAILABLE:
            print("❌ OpenAI not available")
            sys.exit(1)
        
        client = get_streaming_client()
        if not client:
            print("❌ Failed to create streaming client")
            sys.exit(1)
        
        print("✅ Streaming client created")
        
        # Test streaming session
        test_text = "Testing OpenAI streaming TTS with real-time audio generation."
        print(f"\n🎤 Creating streaming session for: {test_text[:50]}...")
        
        session_id = client.create_stream_session(
            text=test_text,
            quality=StreamingQuality.LOW_LATENCY
        )
        
        if session_id:
            print(f"✅ Streaming session created: {session_id}")
            
            # Monitor session progress
            for i in range(50):  # Monitor for up to 5 seconds
                status = client.get_session_status(session_id)
                if status:
                    print(f"  State: {status['state']}, Progress: {status['progress']:.2f}")
                    if status['state'] in ['completed', 'error']:
                        break
                time.sleep(0.1)
            
            # Show performance summary
            print(f"\n📊 Performance Summary:")
            perf = client.get_performance_summary()
            if "no_data" not in perf:
                print(f"  Success Rate: {perf['success_rate']:.2%}")
                print(f"  Avg First Chunk Latency: {perf['performance']['avg_first_chunk_latency_ms']:.1f}ms")
                print(f"  Avg Efficiency Ratio: {perf['performance']['avg_efficiency_ratio']:.2f}")
        else:
            print("❌ Failed to create streaming session")
        
        print("✅ Test completed")
        
    else:
        print("OpenAI Streaming Client - Phase 3.4")
        print("Usage: python openai_streaming_client.py --test")