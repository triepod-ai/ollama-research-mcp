#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "python-dotenv>=1.0.0",
# ]
# ///

"""
Phase 3.5 Unified TTS Orchestrator
Complete integration of all Phase 3 advanced TTS components for optimal performance.

Features:
- Unified interface integrating all Phase 3.1-3.4 components
- Intelligent message flow from input to audio output
- Automatic streaming vs traditional TTS selection
- Advanced transcript processing with personalization
- Provider load balancing and health monitoring
- Real-time performance optimization and adaptation
- Comprehensive error handling and fallback strategies
- Full backward compatibility with existing hook systems
"""

import asyncio
import json
import os
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Callable, Any, Union, Tuple
from concurrent.futures import ThreadPoolExecutor, Future
from dotenv import load_dotenv

# Import all Phase 3 components
try:
    try:
        from .transcript_processor import (
            get_transcript_processor,
            TranscriptProcessor,
            process_transcript_for_tts
        )
    except ImportError:
        from transcript_processor import (
            get_transcript_processor,
            TranscriptProcessor,
            process_transcript_for_tts
        )
    TRANSCRIPT_PROCESSOR_AVAILABLE = True
except ImportError:
    TRANSCRIPT_PROCESSOR_AVAILABLE = False

try:
    try:
        from .personalization_engine import (
            get_personalization_engine,
            PersonalizationEngine,
            personalize_tts_message
        )
    except ImportError:
        from personalization_engine import (
            get_personalization_engine,
            PersonalizationEngine,
            personalize_tts_message
        )
    PERSONALIZATION_ENGINE_AVAILABLE = True
except ImportError:
    PERSONALIZATION_ENGINE_AVAILABLE = False

try:
    try:
        from .advanced_priority_queue import (
            get_advanced_queue,
            AdvancedTTSMessage,
            AdvancedPriority,
            MessageType
        )
    except ImportError:
        from advanced_priority_queue import (
            get_advanced_queue,
            AdvancedTTSMessage,
            AdvancedPriority,
            MessageType
        )
    ADVANCED_QUEUE_AVAILABLE = True
except ImportError:
    ADVANCED_QUEUE_AVAILABLE = False

try:
    try:
        from .playback_coordinator import (
            get_playback_coordinator,
            PlaybackCoordinator,
            play_tts_message_with_streaming
        )
    except ImportError:
        from playback_coordinator import (
            get_playback_coordinator,
            PlaybackCoordinator,
            play_tts_message_with_streaming
        )
    PLAYBACK_COORDINATOR_AVAILABLE = True
except ImportError:
    PLAYBACK_COORDINATOR_AVAILABLE = False

try:
    try:
        from .provider_health_monitor import (
            get_health_monitor,
            select_best_provider,
            get_provider_health_status
        )
    except ImportError:
        from provider_health_monitor import (
            get_health_monitor,
            select_best_provider,
            get_provider_health_status
        )
    PROVIDER_HEALTH_AVAILABLE = True
except ImportError:
    PROVIDER_HEALTH_AVAILABLE = False

try:
    try:
        from .streaming_coordinator import (
            get_streaming_coordinator,
            submit_streaming_tts_request
        )
    except ImportError:
        from streaming_coordinator import (
            get_streaming_coordinator,
            submit_streaming_tts_request
        )
    STREAMING_COORDINATOR_AVAILABLE = True
except ImportError:
    STREAMING_COORDINATOR_AVAILABLE = False

try:
    try:
        from .openai_streaming_client import (
            get_streaming_client,
            StreamingQuality,
            create_streaming_session
        )
    except ImportError:
        from openai_streaming_client import (
            get_streaming_client,
            StreamingQuality,
            create_streaming_session
        )
    STREAMING_CLIENT_AVAILABLE = True
except ImportError:
    STREAMING_CLIENT_AVAILABLE = False
    # Define fallback StreamingQuality
    from enum import Enum
    class StreamingQuality(Enum):
        ULTRA_LOW_LATENCY = "ultra_low"
        LOW_LATENCY = "low_latency"
        BALANCED = "balanced"
        HIGH_QUALITY = "high_quality"
        ADAPTIVE = "adaptive"

# Load environment variables
env_path = Path.home() / "brainpods" / ".env"
if env_path.exists():
    load_dotenv(env_path)

class ProcessingMode(Enum):
    """TTS processing modes."""
    TRADITIONAL = "traditional"        # Standard TTS pipeline
    STREAMING = "streaming"            # Real-time streaming TTS
    HYBRID = "hybrid"                  # Intelligent mode selection
    INTELLIGENT = "intelligent"       # AI-driven optimization

class OptimizationLevel(Enum):
    """Optimization levels for TTS processing."""
    MINIMAL = "minimal"                # Basic functionality only
    STANDARD = "standard"              # Standard optimizations
    ADVANCED = "advanced"              # All Phase 3 features
    MAXIMUM = "maximum"                # Aggressive optimization

class IntegrationStrategy(Enum):
    """Integration strategies for component coordination."""
    SEQUENTIAL = "sequential"          # Process components in order
    PARALLEL = "parallel"              # Parallel processing where possible
    ADAPTIVE = "adaptive"              # Adapt based on conditions
    PERFORMANCE = "performance"        # Optimize for speed
    QUALITY = "quality"                # Optimize for quality

@dataclass
class TTSRequest:
    """Unified TTS request with all Phase 3 capabilities."""
    content: str
    hook_type: str = "unified"
    tool_name: str = "Phase3Orchestrator"
    priority: str = "normal"
    message_type: str = "info"
    
    # Processing options
    processing_mode: ProcessingMode = ProcessingMode.INTELLIGENT
    optimization_level: OptimizationLevel = OptimizationLevel.ADVANCED
    integration_strategy: IntegrationStrategy = IntegrationStrategy.ADAPTIVE
    
    # Personalization options
    enable_personalization: bool = True
    user_context: Optional[Dict[str, Any]] = None
    
    # Streaming options
    force_streaming: bool = False
    streaming_quality: Optional[StreamingQuality] = None
    max_latency_ms: float = 2000.0
    
    # Provider options
    preferred_provider: Optional[str] = None
    fallback_providers: List[str] = field(default_factory=list)
    
    # Callback options
    progress_callback: Optional[Callable] = None
    completion_callback: Optional[Callable] = None
    
    # Metadata
    request_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    timeout_seconds: float = 30.0
    
    def to_advanced_message(self) -> Optional['AdvancedTTSMessage']:
        """Convert to AdvancedTTSMessage for queue processing."""
        if not ADVANCED_QUEUE_AVAILABLE:
            return None
        
        priority_map = {
            "interrupt": AdvancedPriority.INTERRUPT,
            "critical": AdvancedPriority.CRITICAL,
            "high": AdvancedPriority.HIGH,
            "normal": AdvancedPriority.MEDIUM,
            "low": AdvancedPriority.LOW,
            "background": AdvancedPriority.BACKGROUND
        }
        
        type_map = {
            "info": MessageType.INFO,
            "warning": MessageType.WARNING,
            "error": MessageType.ERROR,
            "success": MessageType.SUCCESS
        }
        
        return AdvancedTTSMessage(
            content=self.content,
            priority=priority_map.get(self.priority, AdvancedPriority.MEDIUM),
            message_type=type_map.get(self.message_type, MessageType.INFO),
            hook_type=self.hook_type,
            tool_name=self.tool_name,
            metadata=self.metadata
        )

@dataclass
class TTSResponse:
    """Unified TTS response with processing details."""
    request_id: str
    success: bool
    stream_id: Optional[str] = None
    processing_time_ms: float = 0.0
    provider_used: Optional[str] = None
    mode_used: ProcessingMode = ProcessingMode.TRADITIONAL
    
    # Processing stages completed
    transcript_processed: bool = False
    personalization_applied: bool = False
    streaming_used: bool = False
    
    # Quality metrics
    latency_ms: float = 0.0
    quality_score: float = 0.0
    efficiency_ratio: float = 0.0
    
    # Error information
    error_message: str = ""
    fallback_used: bool = False
    
    # Processing details
    processing_stages: List[str] = field(default_factory=list)
    performance_metrics: Dict[str, Any] = field(default_factory=dict)
    
    def get_summary(self) -> Dict[str, Any]:
        """Get response summary."""
        return {
            "request_id": self.request_id,
            "success": self.success,
            "processing_time_ms": self.processing_time_ms,
            "provider_used": self.provider_used,
            "mode_used": self.mode_used.value,
            "latency_ms": self.latency_ms,
            "streaming_used": self.streaming_used,
            "stages_completed": len(self.processing_stages),
            "error": self.error_message if not self.success else None
        }

class Phase3UnifiedOrchestrator:
    """Unified orchestrator for all Phase 3 TTS components."""
    
    def __init__(self):
        """Initialize the unified orchestrator."""
        self.active_requests: Dict[str, TTSRequest] = {}
        self.request_counter = 0
        self.requests_lock = threading.RLock()
        
        # Component instances
        self.transcript_processor = None
        self.personalization_engine = None
        self.advanced_queue = None
        self.playback_coordinator = None
        self.health_monitor = None
        self.streaming_coordinator = None
        self.streaming_client = None
        
        # Configuration
        self.enable_intelligent_routing = os.getenv("TTS_INTELLIGENT_ROUTING", "true").lower() == "true"
        self.enable_streaming_auto_detection = os.getenv("TTS_STREAMING_AUTO_DETECT", "true").lower() == "true"
        self.enable_performance_monitoring = os.getenv("TTS_PERFORMANCE_MONITORING", "true").lower() == "true"
        self.max_concurrent_requests = int(os.getenv("TTS_MAX_CONCURRENT", "10"))
        
        # Performance tracking
        self.performance_metrics = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "streaming_requests": 0,
            "traditional_requests": 0,
            "avg_processing_time": 0.0,
            "avg_latency": 0.0,
            "component_availability": {},
            "provider_usage": {},
        }
        
        # Threading
        self.executor = ThreadPoolExecutor(
            max_workers=self.max_concurrent_requests + 5,
            thread_name_prefix="phase3_orchestrator"
        )
        self.running = False
        self.monitor_thread: Optional[threading.Thread] = None
        
        # Initialize components
        self._initialize_components()
        
        # Start background monitoring
        self.start()
    
    def _initialize_components(self):
        """Initialize all Phase 3 components."""
        # Transcript Processor (Phase 3.1)
        if TRANSCRIPT_PROCESSOR_AVAILABLE:
            try:
                self.transcript_processor = get_transcript_processor()
                self.performance_metrics["component_availability"]["transcript_processor"] = True
            except Exception as e:
                print(f"Warning: Transcript processor unavailable: {e}")
                self.performance_metrics["component_availability"]["transcript_processor"] = False
        
        # Personalization Engine (Phase 3.2)
        if PERSONALIZATION_ENGINE_AVAILABLE:
            try:
                self.personalization_engine = get_personalization_engine()
                self.performance_metrics["component_availability"]["personalization_engine"] = True
            except Exception as e:
                print(f"Warning: Personalization engine unavailable: {e}")
                self.performance_metrics["component_availability"]["personalization_engine"] = False
        
        # Advanced Queue (Phase 3.3.1)
        if ADVANCED_QUEUE_AVAILABLE:
            try:
                self.advanced_queue = get_advanced_queue()
                self.performance_metrics["component_availability"]["advanced_queue"] = True
            except Exception as e:
                print(f"Warning: Advanced queue unavailable: {e}")
                self.performance_metrics["component_availability"]["advanced_queue"] = False
        
        # Playback Coordinator (Phase 3.3.2)
        if PLAYBACK_COORDINATOR_AVAILABLE:
            try:
                self.playback_coordinator = get_playback_coordinator()
                self.performance_metrics["component_availability"]["playback_coordinator"] = True
            except Exception as e:
                print(f"Warning: Playback coordinator unavailable: {e}")
                self.performance_metrics["component_availability"]["playback_coordinator"] = False
        
        # Provider Health Monitor (Phase 3.3.2)
        if PROVIDER_HEALTH_AVAILABLE:
            try:
                self.health_monitor = get_health_monitor()
                if not self.health_monitor.monitoring_active:
                    self.health_monitor.start_monitoring()
                self.performance_metrics["component_availability"]["health_monitor"] = True
            except Exception as e:
                print(f"Warning: Health monitor unavailable: {e}")
                self.performance_metrics["component_availability"]["health_monitor"] = False
        
        # Streaming Coordinator (Phase 3.4)
        if STREAMING_COORDINATOR_AVAILABLE:
            try:
                self.streaming_coordinator = get_streaming_coordinator()
                if not self.streaming_coordinator.running:
                    self.streaming_coordinator.start()
                self.performance_metrics["component_availability"]["streaming_coordinator"] = True
            except Exception as e:
                print(f"Warning: Streaming coordinator unavailable: {e}")
                self.performance_metrics["component_availability"]["streaming_coordinator"] = False
        
        # Streaming Client (Phase 3.4)
        if STREAMING_CLIENT_AVAILABLE:
            try:
                self.streaming_client = get_streaming_client()
                self.performance_metrics["component_availability"]["streaming_client"] = True
            except Exception as e:
                print(f"Warning: Streaming client unavailable: {e}")
                self.performance_metrics["component_availability"]["streaming_client"] = False
    
    def start(self):
        """Start the orchestrator."""
        if self.running:
            return
        
        self.running = True
        
        # Start performance monitoring
        if self.enable_performance_monitoring:
            self.monitor_thread = threading.Thread(
                target=self._performance_monitor_loop,
                daemon=True,
                name="phase3_performance_monitor"
            )
            self.monitor_thread.start()
    
    def stop(self):
        """Stop the orchestrator."""
        self.running = False
        
        # Stop monitoring thread
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=3)
        
        # Stop component systems
        if self.streaming_coordinator and self.streaming_coordinator.running:
            self.streaming_coordinator.stop()
        
        if self.health_monitor and self.health_monitor.monitoring_active:
            self.health_monitor.stop_monitoring()
        
        # Shutdown executor
        self.executor.shutdown(wait=True, timeout=10)
    
    async def process_tts_request(self, request: TTSRequest) -> TTSResponse:
        """Process a TTS request through the complete Phase 3 pipeline."""
        start_time = time.time()
        
        # Generate request ID
        if not request.request_id:
            request.request_id = f"phase3_req_{int(time.time() * 1000)}_{self.request_counter}"
            self.request_counter += 1
        
        # Initialize response
        response = TTSResponse(
            request_id=request.request_id,
            success=False
        )
        
        try:
            # Track active request
            with self.requests_lock:
                self.active_requests[request.request_id] = request
            
            self.performance_metrics["total_requests"] += 1
            
            # Stage 1: Intelligent Processing Mode Selection
            processing_mode = await self._select_processing_mode(request)
            response.mode_used = processing_mode
            response.processing_stages.append("mode_selection")
            
            # Stage 2: Transcript Processing (Phase 3.1)
            processed_content = await self._process_transcript(request)
            if processed_content != request.content:
                response.transcript_processed = True
                response.processing_stages.append("transcript_processing")
            
            # Stage 3: Personalization (Phase 3.2)
            personalized_content = await self._apply_personalization(request, processed_content)
            if personalized_content != processed_content:
                response.personalization_applied = True
                response.processing_stages.append("personalization")
            
            # Stage 4: Provider Selection and Load Balancing (Phase 3.3.2)
            selected_provider = await self._select_provider(request)
            response.provider_used = selected_provider
            response.processing_stages.append("provider_selection")
            
            # Stage 5: TTS Generation (Traditional vs Streaming)
            stream_id = None
            if processing_mode == ProcessingMode.STREAMING:
                stream_id = await self._process_streaming_request(request, personalized_content)
                response.streaming_used = True
                response.processing_stages.append("streaming_generation")
            elif processing_mode == ProcessingMode.HYBRID:
                stream_id = await self._process_hybrid_request(request, personalized_content)
                response.processing_stages.append("hybrid_processing")
            else:
                stream_id = await self._process_traditional_request(request, personalized_content)
                response.processing_stages.append("traditional_generation")
            
            if stream_id:
                response.stream_id = stream_id
                response.success = True
                self.performance_metrics["successful_requests"] += 1
            else:
                response.error_message = "Failed to generate audio"
                self.performance_metrics["failed_requests"] += 1
            
            # Update performance metrics
            self.performance_metrics["provider_usage"][selected_provider] = \
                self.performance_metrics["provider_usage"].get(selected_provider, 0) + 1
            
            if response.streaming_used:
                self.performance_metrics["streaming_requests"] += 1
            else:
                self.performance_metrics["traditional_requests"] += 1
            
        except Exception as e:
            response.error_message = str(e)
            response.success = False
            self.performance_metrics["failed_requests"] += 1
        
        finally:
            # Calculate timing
            processing_time = (time.time() - start_time) * 1000
            response.processing_time_ms = processing_time
            
            # Update average processing time
            total_requests = self.performance_metrics["total_requests"]
            current_avg = self.performance_metrics["avg_processing_time"]
            self.performance_metrics["avg_processing_time"] = (
                current_avg * (total_requests - 1) + processing_time
            ) / total_requests
            
            # Cleanup active request
            with self.requests_lock:
                if request.request_id in self.active_requests:
                    del self.active_requests[request.request_id]
            
            # Execute completion callback
            if request.completion_callback:
                try:
                    request.completion_callback(response)
                except Exception:
                    pass  # Don't fail on callback errors
        
        return response
    
    async def _select_processing_mode(self, request: TTSRequest) -> ProcessingMode:
        """Intelligently select the optimal processing mode."""
        if request.processing_mode != ProcessingMode.INTELLIGENT:
            return request.processing_mode
        
        # Intelligent mode selection based on multiple factors
        factors = {
            "priority": 0.0,
            "content_length": 0.0,
            "latency_requirement": 0.0,
            "streaming_availability": 0.0,
            "system_load": 0.0
        }
        
        # Priority factor (higher priority prefers streaming)
        priority_weights = {
            "interrupt": 1.0,
            "critical": 0.8,
            "high": 0.6,
            "normal": 0.3,
            "low": 0.1,
            "background": 0.0
        }
        factors["priority"] = priority_weights.get(request.priority, 0.3)
        
        # Content length factor (shorter content suits streaming better)
        content_length = len(request.content)
        if content_length < 50:
            factors["content_length"] = 1.0
        elif content_length < 150:
            factors["content_length"] = 0.7
        elif content_length < 300:
            factors["content_length"] = 0.4
        else:
            factors["content_length"] = 0.1
        
        # Latency requirement factor
        if request.max_latency_ms < 500:
            factors["latency_requirement"] = 1.0
        elif request.max_latency_ms < 1000:
            factors["latency_requirement"] = 0.8
        elif request.max_latency_ms < 2000:
            factors["latency_requirement"] = 0.5
        else:
            factors["latency_requirement"] = 0.2
        
        # Streaming system availability
        if (self.streaming_coordinator and self.streaming_coordinator.running and 
            self.streaming_client):
            factors["streaming_availability"] = 1.0
        else:
            factors["streaming_availability"] = 0.0
        
        # System load factor (prefer streaming when traditional is loaded)
        active_count = len(self.active_requests)
        if active_count < 3:
            factors["system_load"] = 0.3
        elif active_count < 7:
            factors["system_load"] = 0.6
        else:
            factors["system_load"] = 0.9
        
        # Calculate weighted score
        streaming_score = (
            factors["priority"] * 0.25 +
            factors["content_length"] * 0.2 +
            factors["latency_requirement"] * 0.25 +
            factors["streaming_availability"] * 0.2 +
            factors["system_load"] * 0.1
        )
        
        # Decision thresholds
        if request.force_streaming or streaming_score > 0.7:
            return ProcessingMode.STREAMING
        elif streaming_score > 0.4:
            return ProcessingMode.HYBRID
        else:
            return ProcessingMode.TRADITIONAL
    
    async def _process_transcript(self, request: TTSRequest) -> str:
        """Process transcript for optimal TTS generation."""
        if not self.transcript_processor or not TRANSCRIPT_PROCESSOR_AVAILABLE:
            return request.content
        
        try:
            processed = process_transcript_for_tts(
                content=request.content,
                context={
                    "hook_type": request.hook_type,
                    "tool_name": request.tool_name,
                    "priority": request.priority
                }
            )
            return processed
        except Exception:
            return request.content
    
    async def _apply_personalization(self, request: TTSRequest, content: str) -> str:
        """Apply personalization to the content."""
        if (not request.enable_personalization or 
            not self.personalization_engine or 
            not PERSONALIZATION_ENGINE_AVAILABLE):
            return content
        
        try:
            personalized = personalize_tts_message(
                content=content,
                context={
                    "hook_type": request.hook_type,
                    "tool_name": request.tool_name,
                    "priority": request.priority,
                    "user_context": request.user_context
                }
            )
            return personalized
        except Exception:
            return content
    
    async def _select_provider(self, request: TTSRequest) -> Optional[str]:
        """Select optimal provider using health monitoring."""
        if request.preferred_provider:
            return request.preferred_provider
        
        if not PROVIDER_HEALTH_AVAILABLE:
            return "openai"  # Default fallback
        
        try:
            selected = select_best_provider(
                message_priority=request.priority,
                capability="advanced" if request.optimization_level == OptimizationLevel.ADVANCED else "basic"
            )
            return selected or "openai"
        except Exception:
            return "openai"
    
    async def _process_streaming_request(self, request: TTSRequest, content: str) -> Optional[str]:
        """Process request using streaming TTS."""
        if not STREAMING_COORDINATOR_AVAILABLE or not self.streaming_coordinator:
            return None
        
        try:
            # Create advanced message
            advanced_message = request.to_advanced_message()
            if not advanced_message:
                return None
            
            # Update content with processed version
            advanced_message.content = content
            
            # Submit streaming request
            stream_id = submit_streaming_tts_request(
                message=advanced_message,
                priority=request.priority,
                callback=request.progress_callback
            )
            
            return stream_id
        except Exception:
            return None
    
    async def _process_hybrid_request(self, request: TTSRequest, content: str) -> Optional[str]:
        """Process request using hybrid approach."""
        # Try streaming first, fallback to traditional
        stream_id = await self._process_streaming_request(request, content)
        if stream_id:
            return stream_id
        
        # Fallback to traditional
        return await self._process_traditional_request(request, content)
    
    async def _process_traditional_request(self, request: TTSRequest, content: str) -> Optional[str]:
        """Process request using traditional TTS pipeline."""
        if not PLAYBACK_COORDINATOR_AVAILABLE or not self.playback_coordinator:
            return None
        
        try:
            # Create advanced message
            advanced_message = request.to_advanced_message()
            if not advanced_message:
                return None
            
            # Update content with processed version
            advanced_message.content = content
            
            # Use playback coordinator
            stream_id = play_tts_message_with_streaming(
                message=advanced_message,
                force_streaming=False
            )
            
            return stream_id
        except Exception:
            return None
    
    def _performance_monitor_loop(self):
        """Background performance monitoring loop."""
        while self.running:
            try:
                # Update component availability
                self._update_component_availability()
                
                # Log performance metrics periodically
                if self.performance_metrics["total_requests"] % 100 == 0 and self.performance_metrics["total_requests"] > 0:
                    self._log_performance_summary()
                
                time.sleep(30)  # Check every 30 seconds
            except Exception as e:
                print(f"Performance monitoring error: {e}")
                time.sleep(10)
    
    def _update_component_availability(self):
        """Update component availability status."""
        # This could be expanded to do actual health checks
        pass
    
    def _log_performance_summary(self):
        """Log performance summary."""
        metrics = self.performance_metrics
        success_rate = metrics["successful_requests"] / max(1, metrics["total_requests"])
        streaming_rate = metrics["streaming_requests"] / max(1, metrics["total_requests"])
        
        print(f"📊 Phase 3 Performance Summary:")
        print(f"  Total Requests: {metrics['total_requests']}")
        print(f"  Success Rate: {success_rate:.2%}")
        print(f"  Streaming Usage: {streaming_rate:.2%}")
        print(f"  Avg Processing Time: {metrics['avg_processing_time']:.1f}ms")
    
    def get_status(self) -> Dict[str, Any]:
        """Get comprehensive orchestrator status."""
        return {
            "running": self.running,
            "active_requests": len(self.active_requests),
            "component_availability": dict(self.performance_metrics["component_availability"]),
            "performance_metrics": dict(self.performance_metrics),
            "configuration": {
                "intelligent_routing": self.enable_intelligent_routing,
                "streaming_auto_detection": self.enable_streaming_auto_detection,
                "performance_monitoring": self.enable_performance_monitoring,
                "max_concurrent": self.max_concurrent_requests
            }
        }
    
    def get_active_requests(self) -> List[Dict[str, Any]]:
        """Get list of active requests."""
        with self.requests_lock:
            return [
                {
                    "request_id": req.request_id,
                    "content_preview": req.content[:50] + "..." if len(req.content) > 50 else req.content,
                    "priority": req.priority,
                    "processing_mode": req.processing_mode.value,
                    "age_seconds": (datetime.now() - req.created_at).total_seconds()
                }
                for req in self.active_requests.values()
            ]

# Global orchestrator instance
_orchestrator = None

def get_phase3_orchestrator() -> Phase3UnifiedOrchestrator:
    """Get or create the global Phase 3 orchestrator."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = Phase3UnifiedOrchestrator()
    return _orchestrator

async def process_unified_tts_request(
    content: str,
    hook_type: str = "unified",
    tool_name: str = "Phase3",
    priority: str = "normal",
    **kwargs
) -> TTSResponse:
    """
    Process a TTS request through the complete Phase 3 pipeline.
    
    Args:
        content: Text content to convert to speech
        hook_type: Type of hook making the request
        tool_name: Name of tool making the request
        priority: Message priority (interrupt, critical, high, normal, low, background)
        **kwargs: Additional request options
        
    Returns:
        TTSResponse with processing details
    """
    orchestrator = get_phase3_orchestrator()
    
    request = TTSRequest(
        content=content,
        hook_type=hook_type,
        tool_name=tool_name,
        priority=priority,
        **kwargs
    )
    
    return await orchestrator.process_tts_request(request)

def process_unified_tts_request_sync(
    content: str,
    hook_type: str = "unified",
    tool_name: str = "Phase3",
    priority: str = "normal",
    **kwargs
) -> TTSResponse:
    """
    Synchronous version of unified TTS request processing.
    
    Args:
        content: Text content to convert to speech
        hook_type: Type of hook making the request
        tool_name: Name of tool making the request
        priority: Message priority
        **kwargs: Additional request options
        
    Returns:
        TTSResponse with processing details
    """
    return asyncio.run(process_unified_tts_request(
        content=content,
        hook_type=hook_type,
        tool_name=tool_name,
        priority=priority,
        **kwargs
    ))

def get_orchestrator_status() -> Dict[str, Any]:
    """Get Phase 3 orchestrator status."""
    orchestrator = get_phase3_orchestrator()
    return orchestrator.get_status()

if __name__ == "__main__":
    # Test the unified orchestrator
    import sys
    
    if "--test" in sys.argv:
        print("🎼 Testing Phase 3 Unified Orchestrator")
        print("=" * 60)
        
        orchestrator = get_phase3_orchestrator()
        
        print("✅ Orchestrator initialized")
        print(f"📊 Component availability: {json.dumps(orchestrator.performance_metrics['component_availability'], indent=2)}")
        
        # Test processing request
        test_request = TTSRequest(
            content="Testing Phase 3 unified orchestrator with all advanced features.",
            hook_type="test",
            tool_name="OrchestratorTest",
            priority="high",
            processing_mode=ProcessingMode.INTELLIGENT,
            optimization_level=OptimizationLevel.ADVANCED
        )
        
        print(f"\n🎤 Processing test request...")
        response = asyncio.run(orchestrator.process_tts_request(test_request))
        
        print(f"📋 Response Summary:")
        print(json.dumps(response.get_summary(), indent=2))
        
        # Show status
        print(f"\n📊 Final Status:")
        status = orchestrator.get_status()
        print(f"  Active Requests: {status['active_requests']}")
        print(f"  Total Processed: {status['performance_metrics']['total_requests']}")
        print(f"  Success Rate: {status['performance_metrics']['successful_requests']/max(1,status['performance_metrics']['total_requests']):.2%}")
        
        # Cleanup
        orchestrator.stop()
        print("\n✅ Orchestrator test completed")
    
    else:
        print("Phase 3 Unified Orchestrator")
        print("Usage: python phase3_unified_orchestrator.py --test")