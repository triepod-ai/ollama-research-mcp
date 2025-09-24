#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "python-dotenv>=1.0.0",
# ]
# ///

"""
Phase 3.4 Streaming Coordinator
Manages real-time audio chunk processing, buffering, and integration with Phase 3.3.2 systems.

Features:
- Real-time audio chunk coordination and buffering
- Integration with playback coordinator for seamless handoff
- Priority-based stream preemption and queue management
- Adaptive quality control based on network and system conditions
- Stream health monitoring and automatic recovery
- Multi-provider streaming support (OpenAI, future ElevenLabs)
- Performance optimization and latency minimization
"""

import asyncio
import json
import os
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Callable, Any, Union, Tuple
from concurrent.futures import ThreadPoolExecutor, Future
from dotenv import load_dotenv

# Import Phase 3.3.2 systems
try:
    from .playback_coordinator import (
        get_playback_coordinator,
        PlaybackCoordinator,
        AudioStream,
        StreamPriority
    )
    PLAYBACK_COORDINATOR_AVAILABLE = True
except ImportError:
    PLAYBACK_COORDINATOR_AVAILABLE = False

try:
    from .advanced_priority_queue import (
        get_advanced_queue,
        AdvancedTTSMessage,
        AdvancedPriority,
        MessageType
    )
    ADVANCED_QUEUE_AVAILABLE = True
except ImportError:
    ADVANCED_QUEUE_AVAILABLE = False

try:
    from .openai_streaming_client import (
        get_streaming_client,
        OpenAIStreamingClient,
        StreamingQuality,
        StreamingState,
        AudioChunk
    )
    STREAMING_CLIENT_AVAILABLE = True
except ImportError:
    STREAMING_CLIENT_AVAILABLE = False

# Load environment variables
env_path = Path.home() / "brainpods" / ".env"
if env_path.exists():
    load_dotenv(env_path)

class CoordinationStrategy(Enum):
    """Strategies for coordinating streaming with existing systems."""
    PREEMPTIVE = "preemptive"           # Stop current playback, start streaming
    QUEUED = "queued"                   # Queue after current playback
    PARALLEL = "parallel"               # Allow parallel playback (careful!)
    ADAPTIVE = "adaptive"               # Auto-select based on priority and conditions

class StreamIntegrationMode(Enum):
    """Integration modes with playback coordinator."""
    DIRECT_PLAYBACK = "direct"          # Stream plays directly, bypasses coordinator
    COORDINATOR_MANAGED = "managed"     # Full integration with coordinator
    HYBRID = "hybrid"                   # Use coordinator for metadata, direct for audio
    FALLBACK = "fallback"               # Use coordinator if streaming fails

class NetworkCondition(Enum):
    """Network condition assessment."""
    EXCELLENT = "excellent"             # <100ms latency, >10Mbps
    GOOD = "good"                       # <200ms latency, >5Mbps  
    FAIR = "fair"                       # <500ms latency, >1Mbps
    POOR = "poor"                       # >500ms latency, <1Mbps
    UNKNOWN = "unknown"                 # Unable to determine

@dataclass
class StreamingRequest:
    """Request for streaming TTS generation."""
    request_id: str
    message: AdvancedTTSMessage
    priority: StreamPriority
    preferred_quality: StreamingQuality
    coordination_strategy: CoordinationStrategy
    callback: Optional[Callable] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    timeout_seconds: float = 30.0
    
    # Integration settings
    integration_mode: StreamIntegrationMode = StreamIntegrationMode.HYBRID
    allow_fallback: bool = True
    require_streaming: bool = False  # If True, don't fallback to non-streaming
    
    def is_expired(self) -> bool:
        """Check if request has expired."""
        return (datetime.now() - self.created_at).total_seconds() > self.timeout_seconds
    
    def get_age_seconds(self) -> float:
        """Get request age in seconds."""
        return (datetime.now() - self.created_at).total_seconds()

@dataclass
class StreamingSession:
    """Active streaming session with coordination state."""
    session_id: str
    request: StreamingRequest
    streaming_session_id: Optional[str] = None  # From OpenAI client
    coordinator_stream_id: Optional[str] = None  # From playback coordinator
    
    # State management
    state: StreamingState = StreamingState.IDLE
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: str = ""
    
    # Performance tracking
    chunks_received: int = 0
    chunks_played: int = 0
    first_audio_latency: float = 0.0
    total_audio_duration: float = 0.0
    network_condition: NetworkCondition = NetworkCondition.UNKNOWN
    
    # Coordination state
    preempted_sessions: List[str] = field(default_factory=list)
    coordinator_notified: bool = False
    fallback_triggered: bool = False
    
    def get_duration_seconds(self) -> float:
        """Get total session duration."""
        if self.started_at:
            end_time = self.completed_at or datetime.now()
            return (end_time - self.started_at).total_seconds()
        return 0.0
    
    def get_efficiency_ratio(self) -> float:
        """Get efficiency ratio (audio duration / processing time)."""
        processing_time = self.get_duration_seconds()
        if processing_time > 0 and self.total_audio_duration > 0:
            return self.total_audio_duration / processing_time
        return 0.0

class StreamingCoordinator:
    """Coordinates streaming TTS with Phase 3.3.2 systems."""
    
    def __init__(self):
        """Initialize the streaming coordinator."""
        self.active_sessions: Dict[str, StreamingSession] = {}
        self.request_queue: deque[StreamingRequest] = deque()
        self.completed_sessions: deque[StreamingSession] = deque(maxlen=50)
        
        # Thread safety
        self.sessions_lock = threading.RLock()
        self.queue_lock = threading.RLock()
        
        # Configuration
        self.max_concurrent_streams = int(os.getenv("STREAMING_MAX_CONCURRENT", "2"))
        self.default_strategy = CoordinationStrategy.ADAPTIVE
        self.default_integration = StreamIntegrationMode.HYBRID
        self.enable_preemption = os.getenv("STREAMING_ENABLE_PREEMPTION", "true").lower() == "true"
        self.adaptive_quality = os.getenv("STREAMING_ADAPTIVE_QUALITY", "true").lower() == "true"
        
        # System integration
        self.playback_coordinator = None
        self.streaming_client = None
        self.advanced_queue = None
        
        # Performance and health tracking
        self.performance_metrics = {
            "total_requests": 0,
            "successful_streams": 0,
            "failed_streams": 0,
            "fallback_used": 0,
            "preemptions_performed": 0,
            "avg_first_audio_latency": 0.0,
            "avg_efficiency_ratio": 0.0,
            "network_condition_history": deque(maxlen=20)
        }
        
        # Background processing
        self.executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="stream_coord")
        self.running = False
        self.coordinator_thread: Optional[threading.Thread] = None
        self.network_monitor_thread: Optional[threading.Thread] = None
        
        # Initialize system connections
        self._initialize_system_connections()
    
    def _initialize_system_connections(self):
        """Initialize connections to other Phase 3 systems."""
        # Connect to playback coordinator
        if PLAYBACK_COORDINATOR_AVAILABLE:
            try:
                self.playback_coordinator = get_playback_coordinator()
            except Exception as e:
                print(f"Warning: Failed to connect to playback coordinator: {e}")
        
        # Connect to streaming client
        if STREAMING_CLIENT_AVAILABLE:
            try:
                self.streaming_client = get_streaming_client()
            except Exception as e:
                print(f"Warning: Failed to connect to streaming client: {e}")
        
        # Connect to advanced queue
        if ADVANCED_QUEUE_AVAILABLE:
            try:
                self.advanced_queue = get_advanced_queue()
            except Exception as e:
                print(f"Warning: Failed to connect to advanced queue: {e}")
    
    def start(self):
        """Start the streaming coordinator."""
        if self.running:
            return
        
        self.running = True
        
        # Start coordination thread
        self.coordinator_thread = threading.Thread(
            target=self._coordination_loop,
            daemon=True,
            name="streaming_coordinator"
        )
        self.coordinator_thread.start()
        
        # Start network monitoring
        self.network_monitor_thread = threading.Thread(
            target=self._network_monitor_loop,
            daemon=True,
            name="stream_network_monitor"
        )
        self.network_monitor_thread.start()
    
    def stop(self):
        """Stop the streaming coordinator."""
        self.running = False
        
        # Stop all active sessions
        with self.sessions_lock:
            for session in list(self.active_sessions.values()):
                self._stop_session_internal(session, "coordinator_shutdown")
        
        # Wait for threads
        if self.coordinator_thread and self.coordinator_thread.is_alive():
            self.coordinator_thread.join(timeout=3)
        
        if self.network_monitor_thread and self.network_monitor_thread.is_alive():
            self.network_monitor_thread.join(timeout=1)
        
        # Shutdown executor
        self.executor.shutdown(wait=True, timeout=5)
    
    def submit_streaming_request(
        self,
        message: AdvancedTTSMessage,
        priority: Optional[StreamPriority] = None,
        quality: Optional[StreamingQuality] = None,
        strategy: Optional[CoordinationStrategy] = None,
        callback: Optional[Callable] = None,
        **kwargs
    ) -> str:
        """
        Submit a request for streaming TTS generation.
        
        Args:
            message: TTS message to stream
            priority: Stream priority (auto-detected if None)
            quality: Streaming quality (adaptive if None)
            strategy: Coordination strategy (adaptive if None)
            callback: Completion callback
            **kwargs: Additional options
            
        Returns:
            Request ID for tracking
        """
        # Generate request ID
        request_id = f"stream_req_{int(time.time() * 1000)}_{len(self.request_queue)}"
        
        # Auto-detect priority if not provided
        if priority is None:
            priority = self._map_message_to_stream_priority(message)
        
        # Select quality based on priority and conditions
        if quality is None:
            quality = self._select_adaptive_quality(priority)
        
        # Select strategy based on priority and current state
        if strategy is None:
            strategy = self._select_coordination_strategy(priority)
        
        # Create request
        request = StreamingRequest(
            request_id=request_id,
            message=message,
            priority=priority,
            preferred_quality=quality,
            coordination_strategy=strategy,
            callback=callback,
            metadata=kwargs.get("metadata", {}),
            timeout_seconds=kwargs.get("timeout", 30.0),
            integration_mode=kwargs.get("integration_mode", self.default_integration),
            allow_fallback=kwargs.get("allow_fallback", True),
            require_streaming=kwargs.get("require_streaming", False)
        )
        
        # Add to queue
        with self.queue_lock:
            self.request_queue.append(request)
        
        self.performance_metrics["total_requests"] += 1
        
        return request_id
    
    def get_session_status(self, request_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a streaming request/session."""
        with self.sessions_lock:
            # Check active sessions first
            for session in self.active_sessions.values():
                if session.request.request_id == request_id:
                    return self._format_session_status(session)
            
            # Check completed sessions
            for session in self.completed_sessions:
                if session.request.request_id == request_id:
                    return self._format_session_status(session)
        
        # Check if still in queue
        with self.queue_lock:
            for request in self.request_queue:
                if request.request_id == request_id:
                    return {
                        "request_id": request_id,
                        "state": "queued",
                        "queue_position": list(self.request_queue).index(request),
                        "age_seconds": request.get_age_seconds(),
                        "expired": request.is_expired()
                    }
        
        return None
    
    def cancel_request(self, request_id: str) -> bool:
        """Cancel a streaming request."""
        # Check active sessions
        with self.sessions_lock:
            for session_id, session in self.active_sessions.items():
                if session.request.request_id == request_id:
                    self._stop_session_internal(session, "user_cancel")
                    return True
        
        # Check queue
        with self.queue_lock:
            for i, request in enumerate(self.request_queue):
                if request.request_id == request_id:
                    del self.request_queue[i]
                    return True
        
        return False
    
    def get_coordinator_status(self) -> Dict[str, Any]:
        """Get comprehensive coordinator status."""
        with self.sessions_lock, self.queue_lock:
            return {
                "running": self.running,
                "active_sessions": len(self.active_sessions),
                "queued_requests": len(self.request_queue),
                "max_concurrent": self.max_concurrent_streams,
                "system_connections": {
                    "playback_coordinator": self.playback_coordinator is not None,
                    "streaming_client": self.streaming_client is not None,
                    "advanced_queue": self.advanced_queue is not None
                },
                "configuration": {
                    "default_strategy": self.default_strategy.value,
                    "default_integration": self.default_integration.value,
                    "enable_preemption": self.enable_preemption,
                    "adaptive_quality": self.adaptive_quality
                },
                "performance_metrics": dict(self.performance_metrics),
                "active_session_details": [
                    self._format_session_status(session)
                    for session in self.active_sessions.values()
                ]
            }
    
    # Internal methods
    
    def _coordination_loop(self):
        """Main coordination loop for processing requests."""
        while self.running:
            try:
                # Process queued requests
                self._process_request_queue()
                
                # Monitor active sessions
                self._monitor_active_sessions()
                
                # Cleanup completed/failed sessions
                self._cleanup_sessions()
                
                # Brief sleep to prevent busy loop
                time.sleep(0.1)
                
            except Exception as e:
                print(f"Coordination loop error: {e}")
                time.sleep(1)  # Longer sleep on error
    
    def _process_request_queue(self):
        """Process pending streaming requests."""
        with self.queue_lock:
            if not self.request_queue:
                return
            
            # Check if we can process more requests
            if len(self.active_sessions) >= self.max_concurrent_streams:
                return
            
            # Remove expired requests
            while self.request_queue and self.request_queue[0].is_expired():
                expired = self.request_queue.popleft()
                print(f"Dropping expired streaming request: {expired.request_id}")
            
            if not self.request_queue:
                return
            
            # Get next request
            request = self.request_queue.popleft()
        
        # Process the request
        self._process_streaming_request(request)
    
    def _process_streaming_request(self, request: StreamingRequest):
        """Process a single streaming request."""
        try:
            # Create session
            session = StreamingSession(
                session_id=f"session_{request.request_id}",
                request=request,
                started_at=datetime.now()
            )
            
            # Apply coordination strategy
            if request.coordination_strategy == CoordinationStrategy.PREEMPTIVE:
                self._handle_preemptive_strategy(session)
            elif request.coordination_strategy == CoordinationStrategy.QUEUED:
                self._handle_queued_strategy(session)
            elif request.coordination_strategy == CoordinationStrategy.PARALLEL:
                self._handle_parallel_strategy(session)
            elif request.coordination_strategy == CoordinationStrategy.ADAPTIVE:
                self._handle_adaptive_strategy(session)
            
            # Start streaming session
            if self._start_streaming_session(session):
                with self.sessions_lock:
                    self.active_sessions[session.session_id] = session
            else:
                # Fallback if streaming fails
                if request.allow_fallback and not request.require_streaming:
                    self._trigger_fallback(session)
                else:
                    session.state = StreamingState.ERROR
                    session.error_message = "Streaming failed and fallback not allowed"
                    self.performance_metrics["failed_streams"] += 1
            
        except Exception as e:
            print(f"Error processing streaming request {request.request_id}: {e}")
            self.performance_metrics["failed_streams"] += 1
    
    def _start_streaming_session(self, session: StreamingSession) -> bool:
        """Start actual streaming session."""
        if not self.streaming_client:
            return False
        
        try:
            # Create streaming session callback
            def streaming_callback(stream_session, success):
                self._on_streaming_completed(session, success, stream_session)
            
            # Start streaming
            streaming_session_id = self.streaming_client.create_stream_session(
                text=session.request.message.content,
                voice=self._select_voice_for_message(session.request.message),
                quality=session.request.preferred_quality,
                callback=streaming_callback,
                metadata={
                    "coordinator_session_id": session.session_id,
                    "priority": session.request.priority.value,
                    "hook_type": session.request.message.hook_type,
                    "tool_name": session.request.message.tool_name
                }
            )
            
            if streaming_session_id:
                session.streaming_session_id = streaming_session_id
                session.state = StreamingState.STREAMING
                return True
                
        except Exception as e:
            session.error_message = str(e)
            
        return False
    
    def _handle_preemptive_strategy(self, session: StreamingSession):
        """Handle preemptive coordination strategy."""
        if not self.playback_coordinator or not self.enable_preemption:
            return
        
        # Get current playback status
        status = self.playback_coordinator.get_coordinator_status()
        active_streams = status.get("active_streams", 0)
        
        if active_streams > 0:
            # Stop current playback
            stopped = self.playback_coordinator.stop_all_streams("preempted_by_streaming")
            if stopped > 0:
                session.preempted_sessions = [f"stream_{i}" for i in range(stopped)]
                self.performance_metrics["preemptions_performed"] += 1
    
    def _handle_queued_strategy(self, session: StreamingSession):
        """Handle queued coordination strategy."""
        # Wait for current playback to complete
        # This is a simplified implementation - in practice, you'd want more sophisticated queuing
        pass
    
    def _handle_parallel_strategy(self, session: StreamingSession):
        """Handle parallel coordination strategy."""
        # Allow parallel playback (be careful with audio conflicts)
        pass
    
    def _handle_adaptive_strategy(self, session: StreamingSession):
        """Handle adaptive coordination strategy."""
        priority = session.request.priority
        
        # High priority -> preemptive
        if priority in [StreamPriority.INTERRUPT, StreamPriority.CRITICAL]:
            self._handle_preemptive_strategy(session)
        # Medium priority -> queued if busy, otherwise immediate
        elif priority == StreamPriority.HIGH:
            if self.playback_coordinator:
                status = self.playback_coordinator.get_coordinator_status()
                if status.get("active_streams", 0) > 0:
                    self._handle_queued_strategy(session)
        # Low priority -> always queued
        else:
            self._handle_queued_strategy(session)
    
    def _trigger_fallback(self, session: StreamingSession):
        """Trigger fallback to non-streaming playback."""
        if not self.playback_coordinator:
            return
        
        try:
            # Use playback coordinator for fallback
            stream_id = self.playback_coordinator.play_message(
                message=session.request.message,
                callback=lambda s, success, error="": self._on_fallback_completed(session, success, error)
            )
            
            if stream_id:
                session.coordinator_stream_id = stream_id
                session.fallback_triggered = True
                session.state = StreamingState.PLAYING  # Playing via coordinator
                self.performance_metrics["fallback_used"] += 1
                return
                
        except Exception as e:
            session.error_message = f"Fallback failed: {e}"
        
        # Ultimate fallback failure
        session.state = StreamingState.ERROR
        self.performance_metrics["failed_streams"] += 1
    
    def _monitor_active_sessions(self):
        """Monitor active streaming sessions."""
        with self.sessions_lock:
            for session in list(self.active_sessions.values()):
                if session.streaming_session_id and self.streaming_client:
                    # Get streaming status
                    status = self.streaming_client.get_session_status(session.streaming_session_id)
                    if status:
                        # Update session from streaming status
                        session.state = StreamingState(status["state"])
                        if "progress" in status:
                            progress = status["progress"]
                            session.chunks_received = progress.get("chunks_received", 0)
                            session.total_audio_duration = progress.get("audio_duration", 0.0)
                        
                        # Check for completion or error
                        if session.state in [StreamingState.COMPLETED, StreamingState.ERROR]:
                            if session.state == StreamingState.ERROR:
                                session.error_message = status.get("error", "Unknown error")
                            self._finalize_session(session)
    
    def _cleanup_sessions(self):
        """Clean up completed or failed sessions."""
        with self.sessions_lock:
            to_remove = []
            for session_id, session in self.active_sessions.items():
                if session.state in [StreamingState.COMPLETED, StreamingState.ERROR]:
                    to_remove.append(session_id)
            
            for session_id in to_remove:
                session = self.active_sessions.pop(session_id)
                self.completed_sessions.append(session)
    
    def _finalize_session(self, session: StreamingSession):
        """Finalize a completed session."""
        session.completed_at = datetime.now()
        
        # Update performance metrics
        if session.state == StreamingState.COMPLETED:
            self.performance_metrics["successful_streams"] += 1
            
            # Update latency metrics
            if session.first_audio_latency > 0:
                current_avg = self.performance_metrics["avg_first_audio_latency"]
                total_successful = self.performance_metrics["successful_streams"]
                self.performance_metrics["avg_first_audio_latency"] = (
                    current_avg * (total_successful - 1) + session.first_audio_latency
                ) / total_successful
            
            # Update efficiency metrics
            efficiency = session.get_efficiency_ratio()
            if efficiency > 0:
                current_avg = self.performance_metrics["avg_efficiency_ratio"]
                total_successful = self.performance_metrics["successful_streams"]
                self.performance_metrics["avg_efficiency_ratio"] = (
                    current_avg * (total_successful - 1) + efficiency
                ) / total_successful
        else:
            self.performance_metrics["failed_streams"] += 1
        
        # Execute callback
        if session.request.callback:
            try:
                session.request.callback(session, session.state == StreamingState.COMPLETED)
            except Exception:
                pass  # Don't fail on callback errors
    
    def _on_streaming_completed(self, session: StreamingSession, success: bool, stream_session):
        """Handle streaming session completion."""
        if success:
            session.state = StreamingState.COMPLETED
        else:
            session.state = StreamingState.ERROR
            session.error_message = "Streaming session failed"
        
        self._finalize_session(session)
    
    def _on_fallback_completed(self, session: StreamingSession, success: bool, error: str = ""):
        """Handle fallback playback completion."""
        if success:
            session.state = StreamingState.COMPLETED
        else:
            session.state = StreamingState.ERROR
            session.error_message = error or "Fallback playback failed"
        
        self._finalize_session(session)
    
    def _stop_session_internal(self, session: StreamingSession, reason: str):
        """Stop a streaming session."""
        session.request.metadata["stop_reason"] = reason
        
        # Stop streaming session
        if session.streaming_session_id and self.streaming_client:
            self.streaming_client.stop_session(session.streaming_session_id, reason)
        
        # Stop coordinator playback
        if session.coordinator_stream_id and self.playback_coordinator:
            self.playback_coordinator.stop_stream(session.coordinator_stream_id, reason)
        
        session.state = StreamingState.IDLE
        session.completed_at = datetime.now()
    
    def _network_monitor_loop(self):
        """Monitor network conditions for adaptive quality."""
        while self.running:
            try:
                # Simple network condition assessment
                # In practice, you'd want more sophisticated monitoring
                condition = self._assess_network_condition()
                self.performance_metrics["network_condition_history"].append({
                    "timestamp": datetime.now().isoformat(),
                    "condition": condition.value
                })
                
                time.sleep(10)  # Check every 10 seconds
                
            except Exception:
                time.sleep(10)
    
    def _assess_network_condition(self) -> NetworkCondition:
        """Assess current network conditions."""
        # This is a simplified implementation
        # In practice, you'd measure actual latency and bandwidth
        return NetworkCondition.GOOD
    
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
    
    def _select_adaptive_quality(self, priority: StreamPriority) -> StreamingQuality:
        """Select streaming quality based on priority and conditions."""
        if not self.adaptive_quality:
            return StreamingQuality.BALANCED
        
        # Priority-based quality selection
        quality_map = {
            StreamPriority.INTERRUPT: StreamingQuality.ULTRA_LOW_LATENCY,
            StreamPriority.CRITICAL: StreamingQuality.LOW_LATENCY,
            StreamPriority.HIGH: StreamingQuality.BALANCED,
            StreamPriority.NORMAL: StreamingQuality.BALANCED,
            StreamPriority.BACKGROUND: StreamingQuality.HIGH_QUALITY
        }
        
        base_quality = quality_map.get(priority, StreamingQuality.BALANCED)
        
        # Adjust based on network conditions
        # This is simplified - in practice you'd have more sophisticated logic
        network_history = list(self.performance_metrics["network_condition_history"])
        if network_history:
            recent_condition = network_history[-1]["condition"]
            if recent_condition in ["poor", "fair"] and base_quality == StreamingQuality.ULTRA_LOW_LATENCY:
                return StreamingQuality.LOW_LATENCY
        
        return base_quality
    
    def _select_coordination_strategy(self, priority: StreamPriority) -> CoordinationStrategy:
        """Select coordination strategy based on priority."""
        if priority in [StreamPriority.INTERRUPT, StreamPriority.CRITICAL]:
            return CoordinationStrategy.PREEMPTIVE
        else:
            return CoordinationStrategy.ADAPTIVE
    
    def _select_voice_for_message(self, message: AdvancedTTSMessage) -> str:
        """Select appropriate voice for message."""
        # Use existing voice selection logic
        if message.message_type == MessageType.ERROR:
            return os.getenv("OPENAI_TTS_VOICE_CRITICAL", "echo")
        elif message.hook_type == "stop":
            return os.getenv("OPENAI_TTS_VOICE_COMPLETION", "nova")
        else:
            return os.getenv("OPENAI_TTS_VOICE_DEFAULT", "nova")
    
    def _format_session_status(self, session: StreamingSession) -> Dict[str, Any]:
        """Format session status for external consumption."""
        return {
            "request_id": session.request.request_id,
            "session_id": session.session_id,
            "state": session.state.value,
            "priority": session.request.priority.value,
            "quality": session.request.preferred_quality.value,
            "strategy": session.request.coordination_strategy.value,
            "integration_mode": session.request.integration_mode.value,
            "started_at": session.started_at.isoformat() if session.started_at else None,
            "duration_seconds": session.get_duration_seconds(),
            "chunks_received": session.chunks_received,
            "chunks_played": session.chunks_played,
            "audio_duration": session.total_audio_duration,
            "efficiency_ratio": session.get_efficiency_ratio(),
            "network_condition": session.network_condition.value,
            "fallback_triggered": session.fallback_triggered,
            "preempted_sessions": session.preempted_sessions,
            "error_message": session.error_message if session.state == StreamingState.ERROR else None
        }

# Global coordinator instance
_coordinator = None

def get_streaming_coordinator() -> StreamingCoordinator:
    """Get or create the global streaming coordinator."""
    global _coordinator
    if _coordinator is None:
        _coordinator = StreamingCoordinator()
    return _coordinator

def start_streaming_coordination():
    """Start the global streaming coordinator."""
    coordinator = get_streaming_coordinator()
    if not coordinator.running:
        coordinator.start()

def stop_streaming_coordination():
    """Stop the global streaming coordinator."""
    coordinator = get_streaming_coordinator()
    if coordinator.running:
        coordinator.stop()

def submit_streaming_tts_request(
    message: AdvancedTTSMessage,
    priority: str = "normal",
    callback: Optional[Callable] = None,
    **kwargs
) -> str:
    """
    Submit a streaming TTS request with simplified interface.
    
    Args:
        message: TTS message to stream
        priority: Priority level string
        callback: Completion callback
        **kwargs: Additional options
        
    Returns:
        Request ID for tracking
    """
    coordinator = get_streaming_coordinator()
    if not coordinator.running:
        coordinator.start()
    
    # Convert priority string to enum
    priority_map = {
        "interrupt": StreamPriority.INTERRUPT,
        "critical": StreamPriority.CRITICAL,
        "high": StreamPriority.HIGH,
        "normal": StreamPriority.NORMAL,
        "low": StreamPriority.BACKGROUND
    }
    
    stream_priority = priority_map.get(priority, StreamPriority.NORMAL)
    
    return coordinator.submit_streaming_request(
        message=message,
        priority=stream_priority,
        callback=callback,
        **kwargs
    )

if __name__ == "__main__":
    # Test the streaming coordinator
    import sys
    
    if "--test" in sys.argv:
        print("🎵 Testing Streaming Coordinator")
        print("=" * 50)
        
        coordinator = get_streaming_coordinator()
        coordinator.start()
        
        print("✅ Streaming coordinator started")
        print(f"📊 Initial status: {json.dumps(coordinator.get_coordinator_status(), indent=2)}")
        
        # Create test message if advanced queue is available
        if ADVANCED_QUEUE_AVAILABLE:
            from advanced_priority_queue import AdvancedTTSMessage, AdvancedPriority, MessageType
            
            test_message = AdvancedTTSMessage(
                content="Testing streaming coordinator with real-time TTS generation",
                priority=AdvancedPriority.HIGH,
                message_type=MessageType.INFO,
                hook_type="test",
                tool_name="StreamingTest"
            )
            
            print(f"\n🎤 Submitting streaming request...")
            request_id = coordinator.submit_streaming_request(
                message=test_message,
                priority=StreamPriority.HIGH,
                quality=StreamingQuality.LOW_LATENCY
            )
            
            if request_id:
                print(f"✅ Request submitted: {request_id}")
                
                # Monitor progress
                for i in range(30):  # Monitor for up to 3 seconds
                    status = coordinator.get_session_status(request_id)
                    if status:
                        print(f"  State: {status['state']}, Duration: {status['duration_seconds']:.1f}s")
                        if status['state'] in ['completed', 'error']:
                            break
                    time.sleep(0.1)
                
                print(f"\n📊 Final status:")
                final_status = coordinator.get_coordinator_status()
                print(f"  Performance: {final_status['performance_metrics']}")
            else:
                print("❌ Failed to submit request")
        
        # Cleanup
        coordinator.stop()
        print("✅ Coordinator stopped")
        
    else:
        print("Streaming Coordinator - Phase 3.4")
        print("Usage: python streaming_coordinator.py --test")