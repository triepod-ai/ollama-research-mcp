#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "python-dotenv>=1.0.0",
# ]
# ///

"""
Phase 3.3.2 Audio Stream Management & Queue Processing System
Unified audio stream management integrating advanced queue, playback coordination, and health monitoring.

Features:
- Unified audio stream lifecycle management from queue to completion
- Intelligent stream scheduling with priority-based processing
- Real-time stream analytics and performance monitoring
- Adaptive streaming with automatic quality adjustment
- Stream conflict resolution and resource management
- Integration with all Phase 3.3 systems (queue, coordinator, health monitor)
- Advanced stream policies and SLA management
"""

import asyncio
import json
import os
import threading
import time
from collections import deque, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Callable, Any, Tuple, Union
from concurrent.futures import ThreadPoolExecutor, Future
from dotenv import load_dotenv

# Load environment variables
env_path = Path.home() / "brainpods" / ".env"
if env_path.exists():
    load_dotenv(env_path)

# Import Phase 3.3.2 components
try:
    from advanced_priority_queue import (
        get_advanced_queue,
        AdvancedTTSMessage,
        AdvancedPriority,
        MessageType,
        QueueState
    )
    QUEUE_AVAILABLE = True
except ImportError:
    QUEUE_AVAILABLE = False

try:
    from playback_coordinator import (
        get_playback_coordinator,
        PlaybackCoordinator,
        ProviderType,
        PlaybackState,
        StreamPriority
    )
    COORDINATOR_AVAILABLE = True
except ImportError:
    COORDINATOR_AVAILABLE = False

try:
    from provider_health_monitor import (
        get_health_monitor,
        ProviderHealthMonitor,
        LoadBalancingStrategy,
        ProviderCapability
    )
    HEALTH_MONITOR_AVAILABLE = True
except ImportError:
    HEALTH_MONITOR_AVAILABLE = False

# Import Phase 2 coordination
try:
    from observability import get_observability, EventCategory, EventPriority
    OBSERVABILITY_AVAILABLE = True
except ImportError:
    OBSERVABILITY_AVAILABLE = False

class StreamPolicy(Enum):
    """Stream processing policies."""
    BEST_EFFORT = "best_effort"         # Process when resources available
    GUARANTEED = "guaranteed"           # Ensure processing within SLA
    REAL_TIME = "real_time"             # Minimize latency, bypass queue
    BATCH_OPTIMIZED = "batch_optimized" # Optimize for throughput
    COST_OPTIMIZED = "cost_optimized"   # Minimize cost per stream

class StreamQuality(Enum):
    """Audio stream quality levels."""
    LOW = "low"                         # Basic quality, fastest processing
    STANDARD = "standard"               # Good quality, balanced
    HIGH = "high"                       # High quality, may be slower
    PREMIUM = "premium"                 # Maximum quality, slowest

class StreamLifecycleStage(Enum):
    """Stages in stream lifecycle."""
    QUEUED = "queued"                   # In priority queue
    SCHEDULED = "scheduled"             # Scheduled for processing
    PROCESSING = "processing"           # Being converted to audio
    STREAMING = "streaming"             # Audio being played
    COMPLETED = "completed"             # Successfully completed
    FAILED = "failed"                   # Failed to process/play
    CANCELLED = "cancelled"             # Cancelled by user/system
    PREEMPTED = "preempted"             # Interrupted by higher priority

@dataclass
class StreamRequest:
    """Represents a complete stream request with policies."""
    message: AdvancedTTSMessage
    request_id: str
    policy: StreamPolicy = StreamPolicy.BEST_EFFORT
    quality: StreamQuality = StreamQuality.STANDARD
    
    # SLA requirements
    max_queue_time_ms: Optional[int] = None  # Max time in queue
    max_total_time_ms: Optional[int] = None  # Max end-to-end time
    preferred_provider: Optional[str] = None
    
    # Callbacks
    on_scheduled: Optional[Callable] = None
    on_started: Optional[Callable] = None
    on_completed: Optional[Callable] = None
    on_failed: Optional[Callable] = None
    
    # Tracking
    created_at: datetime = field(default_factory=datetime.now)
    scheduled_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # Stream metadata
    estimated_duration_ms: int = 3000
    actual_duration_ms: Optional[int] = None
    provider_used: Optional[str] = None
    quality_achieved: Optional[StreamQuality] = None
    
    def age_ms(self) -> int:
        """Get age of request in milliseconds."""
        return int((datetime.now() - self.created_at).total_seconds() * 1000)
    
    def is_sla_violated(self) -> bool:
        """Check if SLA requirements are violated."""
        current_time = datetime.now()
        
        # Check queue time SLA
        if self.max_queue_time_ms and not self.started_at:
            queue_time = (current_time - self.created_at).total_seconds() * 1000
            if queue_time > self.max_queue_time_ms:
                return True
        
        # Check total time SLA
        if self.max_total_time_ms and not self.completed_at:
            total_time = (current_time - self.created_at).total_seconds() * 1000
            if total_time > self.max_total_time_ms:
                return True
        
        return False

@dataclass
class StreamAnalytics:
    """Analytics for stream processing."""
    total_requests: int = 0
    completed_requests: int = 0
    failed_requests: int = 0
    cancelled_requests: int = 0
    preempted_requests: int = 0
    
    # Performance metrics
    average_queue_time_ms: float = 0.0
    average_processing_time_ms: float = 0.0
    average_total_time_ms: float = 0.0
    p95_queue_time_ms: float = 0.0
    p95_processing_time_ms: float = 0.0
    p95_total_time_ms: float = 0.0
    
    # Quality metrics
    sla_compliance_rate: float = 100.0
    success_rate: float = 100.0
    preemption_rate: float = 0.0
    
    # Resource utilization
    queue_utilization: float = 0.0
    provider_utilization: Dict[str, float] = field(default_factory=dict)
    concurrent_streams_peak: int = 0
    
    # Cost metrics
    total_cost: float = 0.0
    cost_per_request: float = 0.0
    cost_by_provider: Dict[str, float] = field(default_factory=dict)

class AudioStreamManager:
    """Unified audio stream management system."""
    
    def __init__(self):
        """Initialize the audio stream manager."""
        # Core components
        self.queue = None
        self.coordinator = None
        self.health_monitor = None
        self.observability = None
        
        # Initialize components if available
        if QUEUE_AVAILABLE:
            self.queue = get_advanced_queue()
        if COORDINATOR_AVAILABLE:
            self.coordinator = get_playback_coordinator()
        if HEALTH_MONITOR_AVAILABLE:
            self.health_monitor = get_health_monitor()
        if OBSERVABILITY_AVAILABLE:
            self.observability = get_observability()
        
        # Stream management
        self.active_requests: Dict[str, StreamRequest] = {}
        self.completed_requests: deque[StreamRequest] = deque(maxlen=1000)
        self.request_history: deque[Dict[str, Any]] = deque(maxlen=5000)
        
        # Processing control
        self.manager_active = False
        self.processor_thread: Optional[threading.Thread] = None
        self.scheduler_thread: Optional[threading.Thread] = None
        self.analytics_thread: Optional[threading.Thread] = None
        
        # Configuration
        self.max_concurrent_streams = int(os.getenv("TTS_MAX_CONCURRENT_STREAMS", "10"))
        self.scheduling_interval_ms = int(os.getenv("TTS_SCHEDULING_INTERVAL_MS", "100"))
        self.analytics_interval_s = int(os.getenv("TTS_ANALYTICS_INTERVAL_S", "30"))
        
        # Quality policies
        self.quality_settings = {
            StreamQuality.LOW: {
                "max_latency_ms": 1000,
                "provider_preference": ["pyttsx3", "openai", "elevenlabs"],
                "timeout_multiplier": 0.5
            },
            StreamQuality.STANDARD: {
                "max_latency_ms": 3000,
                "provider_preference": ["openai", "pyttsx3", "elevenlabs"],
                "timeout_multiplier": 1.0
            },
            StreamQuality.HIGH: {
                "max_latency_ms": 5000,
                "provider_preference": ["elevenlabs", "openai", "pyttsx3"],
                "timeout_multiplier": 1.5
            },
            StreamQuality.PREMIUM: {
                "max_latency_ms": 10000,
                "provider_preference": ["elevenlabs"],
                "timeout_multiplier": 2.0
            }
        }
        
        # Analytics
        self.analytics = StreamAnalytics()
        self.analytics_history: deque[StreamAnalytics] = deque(maxlen=100)  # Last 100 snapshots
        
        # SLA monitoring
        self.sla_violations: deque[Dict[str, Any]] = deque(maxlen=100)
        self.performance_alerts: deque[Dict[str, Any]] = deque(maxlen=50)
        
        # Locks for thread safety
        self.manager_lock = threading.RLock()
    
    def start(self):
        """Start the audio stream manager."""
        with self.manager_lock:
            if self.manager_active:
                return
            
            self.manager_active = True
            
            # Start dependent systems
            if self.coordinator:
                self.coordinator.start()
            if self.health_monitor:
                self.health_monitor.start_monitoring()
            
            # Start manager threads
            self._start_processor_thread()
            self._start_scheduler_thread()
            self._start_analytics_thread()
    
    def stop(self):
        """Stop the audio stream manager and cleanup."""
        with self.manager_lock:
            if not self.manager_active:
                return
                
            self.manager_active = False
            
            # Cancel all active requests
            self._cancel_all_active_requests("system_shutdown")
            
            # Stop threads
            self._stop_threads()
            
            # Stop dependent systems
            if self.coordinator:
                self.coordinator.stop()
            if self.health_monitor:
                self.health_monitor.stop_monitoring()
    
    def submit_request(self, 
                      message: AdvancedTTSMessage,
                      policy: StreamPolicy = StreamPolicy.BEST_EFFORT,
                      quality: StreamQuality = StreamQuality.STANDARD,
                      max_queue_time_ms: Optional[int] = None,
                      max_total_time_ms: Optional[int] = None,
                      preferred_provider: Optional[str] = None,
                      **callbacks) -> str:
        """
        Submit a TTS request for processing.
        
        Args:
            message: The TTS message to process
            policy: Stream processing policy
            quality: Desired quality level  
            max_queue_time_ms: Maximum time to wait in queue
            max_total_time_ms: Maximum end-to-end time
            preferred_provider: Preferred TTS provider
            **callbacks: Event callbacks (on_scheduled, on_started, on_completed, on_failed)
            
        Returns:
            Request ID for tracking
        """
        request_id = f"req_{int(time.time()*1000)}_{hash(message.content) % 10000}"
        
        # Create stream request
        request = StreamRequest(
            message=message,
            request_id=request_id,
            policy=policy,
            quality=quality,
            max_queue_time_ms=max_queue_time_ms,
            max_total_time_ms=max_total_time_ms,
            preferred_provider=preferred_provider,
            estimated_duration_ms=self._estimate_duration(message.content),
            **callbacks
        )
        
        with self.manager_lock:
            # Add to active requests
            self.active_requests[request_id] = request
            
            # Add to appropriate queue based on policy
            if policy == StreamPolicy.REAL_TIME:
                # Bypass queue for real-time processing
                self._schedule_immediate_processing(request)
            else:
                # Add to priority queue
                if self.queue:
                    self.queue.enqueue(message)
                
            # Update analytics
            self.analytics.total_requests += 1
            
            # Log request
            self._log_request_event(request, "submitted")
        
        return request_id
    
    def cancel_request(self, request_id: str, reason: str = "user_cancelled") -> bool:
        """Cancel a specific request."""
        with self.manager_lock:
            request = self.active_requests.get(request_id)
            if not request:
                return False
            
            # Cancel based on current stage
            success = self._cancel_request_internal(request, reason)
            
            if success:
                self.analytics.cancelled_requests += 1
                self._log_request_event(request, "cancelled", {"reason": reason})
            
            return success
    
    def get_request_status(self, request_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a specific request."""
        with self.manager_lock:
            request = self.active_requests.get(request_id)
            if not request:
                # Check completed requests
                for completed_req in self.completed_requests:
                    if completed_req.request_id == request_id:
                        return self._request_to_status(completed_req)
                return None
            
            return self._request_to_status(request)
    
    def get_queue_status(self) -> Dict[str, Any]:
        """Get comprehensive queue and processing status."""
        with self.manager_lock:
            status = {
                "manager_active": self.manager_active,
                "active_requests": len(self.active_requests),
                "completed_requests": len(self.completed_requests),
                
                # Queue status
                "queue_size": self.queue.size() if self.queue else 0,
                "queue_state": self.queue.state.value if self.queue else "unavailable",
                
                # Processing status
                "concurrent_streams": self._count_processing_requests(),
                "max_concurrent_streams": self.max_concurrent_streams,
                
                # Component status
                "coordinator_active": self.coordinator.running if self.coordinator else False,
                "health_monitor_active": self.health_monitor.monitoring_active if self.health_monitor else False,
                
                # Performance metrics
                "analytics": self._get_current_analytics(),
                "sla_compliance": self.analytics.sla_compliance_rate,
                "success_rate": self.analytics.success_rate,
                
                # Recent activity
                "recent_completions": len([r for r in self.completed_requests if r.completed_at and (datetime.now() - r.completed_at).total_seconds() < 300]),
                "recent_failures": len([r for r in self.completed_requests if not r.completed_at and r.request_id not in self.active_requests]),
            }
            
            return status
    
    def get_performance_report(self, hours: int = 24) -> Dict[str, Any]:
        """Get detailed performance report for specified time period."""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        # Filter requests within time period
        recent_requests = [
            req for req in self.completed_requests
            if req.created_at >= cutoff_time
        ]
        
        if not recent_requests:
            return {"message": "No requests in specified time period"}
        
        # Calculate metrics
        completed = [req for req in recent_requests if req.completed_at]
        failed = [req for req in recent_requests if not req.completed_at and req.request_id not in self.active_requests]
        
        # Timing analysis
        queue_times = [
            (req.started_at - req.created_at).total_seconds() * 1000
            for req in completed if req.started_at
        ]
        processing_times = [
            req.actual_duration_ms for req in completed 
            if req.actual_duration_ms
        ]
        total_times = [
            (req.completed_at - req.created_at).total_seconds() * 1000
            for req in completed
        ]
        
        # SLA analysis
        sla_violations = [req for req in recent_requests if req.is_sla_violated()]
        
        report = {
            "time_period_hours": hours,
            "total_requests": len(recent_requests),
            "completed": len(completed),
            "failed": len(failed),
            "success_rate": (len(completed) / len(recent_requests)) * 100 if recent_requests else 0,
            
            "timing_metrics": {
                "average_queue_time_ms": sum(queue_times) / len(queue_times) if queue_times else 0,
                "average_processing_time_ms": sum(processing_times) / len(processing_times) if processing_times else 0,
                "average_total_time_ms": sum(total_times) / len(total_times) if total_times else 0,
                "p95_total_time_ms": sorted(total_times)[int(len(total_times) * 0.95)] if total_times else 0,
            },
            
            "sla_compliance": {
                "violations": len(sla_violations),
                "compliance_rate": ((len(recent_requests) - len(sla_violations)) / len(recent_requests)) * 100 if recent_requests else 100,
                "violation_reasons": [req.request_id for req in sla_violations]
            },
            
            "provider_usage": self._analyze_provider_usage(recent_requests),
            "quality_distribution": self._analyze_quality_distribution(recent_requests),
            "policy_distribution": self._analyze_policy_distribution(recent_requests),
        }
        
        return report
    
    # Internal methods
    
    def _start_processor_thread(self):
        """Start the request processor thread."""
        self.processor_thread = threading.Thread(
            target=self._processor_loop,
            daemon=True,
            name="tts_stream_processor"
        )
        self.processor_thread.start()
    
    def _start_scheduler_thread(self):
        """Start the request scheduler thread."""
        self.scheduler_thread = threading.Thread(
            target=self._scheduler_loop,
            daemon=True,
            name="tts_stream_scheduler"
        )
        self.scheduler_thread.start()
    
    def _start_analytics_thread(self):
        """Start the analytics collection thread."""
        self.analytics_thread = threading.Thread(
            target=self._analytics_loop,
            daemon=True,
            name="tts_stream_analytics"
        )
        self.analytics_thread.start()
    
    def _stop_threads(self):
        """Stop all manager threads."""
        threads = [self.processor_thread, self.scheduler_thread, self.analytics_thread]
        
        for thread in threads:
            if thread and thread.is_alive():
                thread.join(timeout=2.0)
    
    def _processor_loop(self):
        """Main request processing loop."""
        while self.manager_active:
            try:
                # Process next message from queue
                if self.queue:
                    message = self.queue.dequeue()
                    if message:
                        self._process_message(message)
                    else:
                        time.sleep(0.05)  # Brief sleep if no messages
                else:
                    time.sleep(0.1)
                    
            except Exception as e:
                self._log_error("processor_loop", str(e))
                time.sleep(1)
    
    def _scheduler_loop(self):
        """Request scheduler loop for SLA monitoring and optimization."""
        while self.manager_active:
            try:
                with self.manager_lock:
                    # Check for SLA violations
                    self._check_sla_violations()
                    
                    # Optimize processing order
                    self._optimize_processing_order()
                    
                    # Handle preemptions if needed
                    self._handle_preemption_requests()
                
                time.sleep(self.scheduling_interval_ms / 1000)
                
            except Exception as e:
                self._log_error("scheduler_loop", str(e))
                time.sleep(1)
    
    def _analytics_loop(self):
        """Analytics collection and reporting loop."""
        while self.manager_active:
            try:
                # Collect current analytics
                current_analytics = self._calculate_current_analytics()
                self.analytics_history.append(current_analytics)
                
                # Check performance thresholds
                self._check_performance_alerts()
                
                # Generate reports if needed
                self._generate_periodic_reports()
                
                time.sleep(self.analytics_interval_s)
                
            except Exception as e:
                self._log_error("analytics_loop", str(e))
                time.sleep(5)
    
    def _process_message(self, message: AdvancedTTSMessage):
        """Process a message from the queue."""
        # Find corresponding request
        request = self._find_request_for_message(message)
        if not request:
            # Orphaned message - create minimal request
            request_id = f"orphan_{int(time.time()*1000)}"
            request = StreamRequest(
                message=message,
                request_id=request_id,
                policy=StreamPolicy.BEST_EFFORT,
                quality=StreamQuality.STANDARD
            )
            self.active_requests[request_id] = request
        
        # Update request state
        request.scheduled_at = datetime.now()
        
        # Select provider based on policy and quality
        provider = self._select_provider_for_request(request)
        if not provider:
            self._handle_request_failure(request, "No provider available")
            return
        
        # Execute callback
        if request.on_scheduled:
            try:
                request.on_scheduled(request)
            except Exception:
                pass
        
        # Start processing
        self._start_request_processing(request, provider)
    
    def _select_provider_for_request(self, request: StreamRequest) -> Optional[str]:
        """Select best provider for a specific request."""
        # Check preferred provider first
        if request.preferred_provider:
            if self.health_monitor:
                monitor_status = self.health_monitor.get_monitoring_status()
                provider_status = monitor_status["providers"].get(request.preferred_provider)
                if provider_status and provider_status["is_available"]:
                    return request.preferred_provider
        
        # Use quality-based selection
        quality_settings = self.quality_settings.get(request.quality, {})
        provider_preferences = quality_settings.get("provider_preference", ["openai", "pyttsx3", "elevenlabs"])
        
        # Check health monitor if available
        if self.health_monitor:
            selected = None
            for preferred_provider in provider_preferences:
                monitor_status = self.health_monitor.get_monitoring_status()
                provider_status = monitor_status["providers"].get(preferred_provider)
                if provider_status and provider_status["is_available"]:
                    selected = preferred_provider
                    break
            
            if selected:
                return selected
        
        # Fallback to first available provider
        return provider_preferences[0] if provider_preferences else "pyttsx3"
    
    def _start_request_processing(self, request: StreamRequest, provider: str):
        """Start processing a request with selected provider."""
        request.started_at = datetime.now()
        request.provider_used = provider
        
        # Execute callback
        if request.on_started:
            try:
                request.on_started(request)
            except Exception:
                pass
        
        # Use coordinator if available
        if self.coordinator:
            callback = lambda stream, success, error: self._handle_processing_completion(request, success, error)
            stream_id = self.coordinator.play_message(request.message, callback)
            
            if stream_id:
                request.message.metadata["stream_id"] = stream_id
                self._log_request_event(request, "processing_started", {"provider": provider, "stream_id": stream_id})
            else:
                self._handle_request_failure(request, "Failed to start playback")
        else:
            # Fallback: simulate processing
            self._simulate_processing(request, provider)
    
    def _handle_processing_completion(self, request: StreamRequest, success: bool, error: str):
        """Handle completion of processing."""
        with self.manager_lock:
            request.completed_at = datetime.now()
            
            if success:
                # Calculate actual duration
                if request.started_at:
                    duration_ms = int((request.completed_at - request.started_at).total_seconds() * 1000)
                    request.actual_duration_ms = duration_ms
                
                request.quality_achieved = request.quality  # Assume requested quality achieved
                
                # Execute callback
                if request.on_completed:
                    try:
                        request.on_completed(request)
                    except Exception:
                        pass
                
                # Update analytics
                self.analytics.completed_requests += 1
                
                # Move to completed
                self._move_to_completed(request)
                
                self._log_request_event(request, "completed", {
                    "duration_ms": request.actual_duration_ms,
                    "provider": request.provider_used
                })
                
            else:
                self._handle_request_failure(request, error)
    
    def _handle_request_failure(self, request: StreamRequest, error: str):
        """Handle request failure."""
        with self.manager_lock:
            request.message.metadata["failure_reason"] = error
            
            # Execute callback
            if request.on_failed:
                try:
                    request.on_failed(request, error)
                except Exception:
                    pass
            
            # Update analytics
            self.analytics.failed_requests += 1
            
            # Move to completed (as failed)
            self._move_to_completed(request)
            
            self._log_request_event(request, "failed", {"error": error})
    
    def _move_to_completed(self, request: StreamRequest):
        """Move request from active to completed."""
        if request.request_id in self.active_requests:
            del self.active_requests[request.request_id]
        self.completed_requests.append(request)
    
    def _cancel_request_internal(self, request: StreamRequest, reason: str) -> bool:
        """Internal request cancellation logic."""
        # Stop any active processing
        if self.coordinator and request.message.metadata.get("stream_id"):
            stream_id = request.message.metadata["stream_id"]
            self.coordinator.stop_stream(stream_id, reason)
        
        # Update request
        request.message.metadata["cancellation_reason"] = reason
        
        # Execute callback
        if request.on_failed:
            try:
                request.on_failed(request, f"Cancelled: {reason}")
            except Exception:
                pass
        
        # Move to completed
        self._move_to_completed(request)
        return True
    
    def _cancel_all_active_requests(self, reason: str):
        """Cancel all active requests."""
        for request in list(self.active_requests.values()):
            self._cancel_request_internal(request, reason)
    
    def _estimate_duration(self, text: str) -> int:
        """Estimate duration in milliseconds."""
        # Rough estimate: 150 words per minute
        word_count = len(text.split())
        duration_seconds = max(1.0, word_count / 2.5)
        return int(duration_seconds * 1000)
    
    def _schedule_immediate_processing(self, request: StreamRequest):
        """Schedule request for immediate processing (bypass queue)."""
        # Add to processing queue immediately
        if self.coordinator and self.coordinator.running:
            provider = self._select_provider_for_request(request)
            if provider:
                self._start_request_processing(request, provider)
            else:
                self._handle_request_failure(request, "No provider available for real-time processing")
    
    def _simulate_processing(self, request: StreamRequest, provider: str):
        """Simulate processing when coordinator is not available."""
        def simulate():
            time.sleep(request.estimated_duration_ms / 1000)
            self._handle_processing_completion(request, True, "")
        
        threading.Thread(target=simulate, daemon=True).start()
    
    def _find_request_for_message(self, message: AdvancedTTSMessage) -> Optional[StreamRequest]:
        """Find the request corresponding to a message."""
        # Simple matching by content hash - in production use better matching
        content_hash = hash(message.content) % 10000
        
        for request in self.active_requests.values():
            if hash(request.message.content) % 10000 == content_hash:
                return request
        
        return None
    
    def _count_processing_requests(self) -> int:
        """Count requests currently being processed."""
        return len([r for r in self.active_requests.values() if r.started_at and not r.completed_at])
    
    def _check_sla_violations(self):
        """Check for SLA violations and handle them."""
        violations = []
        
        for request in self.active_requests.values():
            if request.is_sla_violated():
                violations.append(request)
        
        for request in violations:
            violation_info = {
                "request_id": request.request_id,
                "age_ms": request.age_ms(),
                "max_queue_time": request.max_queue_time_ms,
                "max_total_time": request.max_total_time_ms,
                "timestamp": datetime.now().isoformat()
            }
            
            self.sla_violations.append(violation_info)
            
            # Handle violation based on policy
            if request.policy == StreamPolicy.GUARANTEED:
                # Try to prioritize or find alternative processing
                self._handle_sla_violation(request)
    
    def _handle_sla_violation(self, request: StreamRequest):
        """Handle SLA violation for a request."""
        # Try to boost priority or find alternative processing
        if self.queue and hasattr(request.message, 'priority'):
            # Boost priority
            if request.message.priority.value > 0:
                new_priority = type(request.message.priority)(request.message.priority.value - 1)
                request.message.priority = new_priority
    
    def _optimize_processing_order(self):
        """Optimize processing order based on policies and SLAs."""
        # This would implement intelligent scheduling
        # For now, just log the optimization attempt
        pass
    
    def _handle_preemption_requests(self):
        """Handle preemption requests for high-priority streams."""
        # Check for high-priority requests that should preempt current processing
        high_priority_requests = [
            r for r in self.active_requests.values()
            if r.policy == StreamPolicy.REAL_TIME or 
               (hasattr(r.message, 'priority') and r.message.priority.value <= 1)
        ]
        
        if high_priority_requests and self.coordinator:
            # Consider preempting lower priority streams
            pass
    
    def _calculate_current_analytics(self) -> StreamAnalytics:
        """Calculate current analytics snapshot."""
        # This would calculate comprehensive analytics
        # Return current analytics for now
        return self.analytics
    
    def _check_performance_alerts(self):
        """Check for performance threshold violations."""
        # Check success rate
        if self.analytics.success_rate < 90:
            alert = {
                "type": "low_success_rate",
                "value": self.analytics.success_rate,
                "threshold": 90,
                "timestamp": datetime.now().isoformat()
            }
            self.performance_alerts.append(alert)
        
        # Check SLA compliance
        if self.analytics.sla_compliance_rate < 95:
            alert = {
                "type": "sla_compliance",
                "value": self.analytics.sla_compliance_rate,
                "threshold": 95,
                "timestamp": datetime.now().isoformat()
            }
            self.performance_alerts.append(alert)
    
    def _generate_periodic_reports(self):
        """Generate periodic performance reports."""
        # This would generate and store periodic reports
        pass
    
    def _request_to_status(self, request: StreamRequest) -> Dict[str, Any]:
        """Convert request to status dictionary."""
        return {
            "request_id": request.request_id,
            "created_at": request.created_at.isoformat(),
            "policy": request.policy.value,
            "quality": request.quality.value,
            "scheduled_at": request.scheduled_at.isoformat() if request.scheduled_at else None,
            "started_at": request.started_at.isoformat() if request.started_at else None,
            "completed_at": request.completed_at.isoformat() if request.completed_at else None,
            "age_ms": request.age_ms(),
            "estimated_duration_ms": request.estimated_duration_ms,
            "actual_duration_ms": request.actual_duration_ms,
            "provider_used": request.provider_used,
            "quality_achieved": request.quality_achieved.value if request.quality_achieved else None,
            "sla_violated": request.is_sla_violated(),
            "message": {
                "content": request.message.content[:100] + "..." if len(request.message.content) > 100 else request.message.content,
                "priority": request.message.priority.name if hasattr(request.message, 'priority') else None,
                "type": request.message.message_type.name if hasattr(request.message, 'message_type') else None,
            }
        }
    
    def _get_current_analytics(self) -> Dict[str, Any]:
        """Get current analytics as dictionary."""
        return {
            "total_requests": self.analytics.total_requests,
            "completed_requests": self.analytics.completed_requests,
            "failed_requests": self.analytics.failed_requests,
            "success_rate": self.analytics.success_rate,
            "sla_compliance_rate": self.analytics.sla_compliance_rate,
            "average_queue_time_ms": self.analytics.average_queue_time_ms,
            "average_processing_time_ms": self.analytics.average_processing_time_ms,
            "average_total_time_ms": self.analytics.average_total_time_ms,
        }
    
    def _analyze_provider_usage(self, requests: List[StreamRequest]) -> Dict[str, Any]:
        """Analyze provider usage from request list."""
        provider_counts = defaultdict(int)
        for req in requests:
            if req.provider_used:
                provider_counts[req.provider_used] += 1
        
        total = len(requests)
        return {
            provider: {"count": count, "percentage": (count / total) * 100 if total > 0 else 0}
            for provider, count in provider_counts.items()
        }
    
    def _analyze_quality_distribution(self, requests: List[StreamRequest]) -> Dict[str, Any]:
        """Analyze quality distribution from request list."""
        quality_counts = defaultdict(int)
        for req in requests:
            quality_counts[req.quality.value] += 1
        
        total = len(requests)
        return {
            quality: {"count": count, "percentage": (count / total) * 100 if total > 0 else 0}
            for quality, count in quality_counts.items()
        }
    
    def _analyze_policy_distribution(self, requests: List[StreamRequest]) -> Dict[str, Any]:
        """Analyze policy distribution from request list."""
        policy_counts = defaultdict(int)
        for req in requests:
            policy_counts[req.policy.value] += 1
        
        total = len(requests)
        return {
            policy: {"count": count, "percentage": (count / total) * 100 if total > 0 else 0}
            for policy, count in policy_counts.items()
        }
    
    def _log_request_event(self, request: StreamRequest, event: str, metadata: Dict[str, Any] = None):
        """Log request event for tracking."""
        event_data = {
            "timestamp": datetime.now().isoformat(),
            "request_id": request.request_id,
            "event": event,
            "policy": request.policy.value,
            "quality": request.quality.value,
            "metadata": metadata or {}
        }
        
        self.request_history.append(event_data)
    
    def _log_error(self, context: str, error: str):
        """Log error for debugging."""
        error_entry = {
            "timestamp": datetime.now().isoformat(),
            "context": context,
            "error": error,
            "active_requests": len(self.active_requests)
        }
        
        # Log to file if needed
        error_log = Path.home() / "brainpods" / ".claude-logs" / "hooks" / "stream_manager_errors.jsonl"
        error_log.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            with open(error_log, "a") as f:
                f.write(json.dumps(error_entry) + "\n")
        except Exception:
            pass

# Global stream manager instance
_stream_manager = None

def get_stream_manager() -> AudioStreamManager:
    """Get or create the global audio stream manager."""
    global _stream_manager
    if _stream_manager is None:
        _stream_manager = AudioStreamManager()
    return _stream_manager

def start_audio_stream_management():
    """Start the global audio stream management system."""
    manager = get_stream_manager()
    manager.start()

def stop_audio_stream_management():
    """Stop the global audio stream management system."""
    manager = get_stream_manager()
    manager.stop()

def submit_tts_request(
    message: AdvancedTTSMessage,
    policy: StreamPolicy = StreamPolicy.BEST_EFFORT,
    quality: StreamQuality = StreamQuality.STANDARD,
    **kwargs
) -> str:
    """Submit a TTS request through the stream manager."""
    manager = get_stream_manager()
    if not manager.manager_active:
        manager.start()
    return manager.submit_request(message, policy, quality, **kwargs)

def get_tts_queue_status() -> Dict[str, Any]:
    """Get TTS queue and processing status."""
    manager = get_stream_manager()
    return manager.get_queue_status()

def get_tts_performance_report(hours: int = 24) -> Dict[str, Any]:
    """Get TTS performance report."""
    manager = get_stream_manager()
    return manager.get_performance_report(hours)

if __name__ == "__main__":
    # Test the audio stream manager
    import sys
    
    if "--test" in sys.argv:
        print("🎵 Testing Audio Stream Manager")
        print("=" * 50)
        
        # Create and start manager
        manager = get_stream_manager()
        manager.start()
        
        print("✅ Stream manager started")
        
        # Create test message if components are available
        if QUEUE_AVAILABLE:
            from advanced_priority_queue import AdvancedTTSMessage, AdvancedPriority, MessageType
            
            test_message = AdvancedTTSMessage(
                content="Testing audio stream manager system",
                priority=AdvancedPriority.HIGH,
                message_type=MessageType.INFO,
                hook_type="test",
                tool_name="StreamTest"
            )
            
            print(f"\n🎤 Submitting test request...")
            request_id = manager.submit_request(
                test_message,
                policy=StreamPolicy.BEST_EFFORT,
                quality=StreamQuality.STANDARD,
                max_total_time_ms=10000
            )
            
            print(f"✅ Request submitted: {request_id}")
            
            # Wait and check status
            time.sleep(2)
            status = manager.get_request_status(request_id)
            print(f"📊 Request status: {json.dumps(status, indent=2) if status else 'Not found'}")
            
            # Get queue status
            queue_status = manager.get_queue_status()
            print(f"📊 Queue status: {json.dumps(queue_status, indent=2)}")
            
            # Wait for completion
            time.sleep(5)
            
            # Get final report
            report = manager.get_performance_report(1)
            print(f"📈 Performance report: {json.dumps(report, indent=2)}")
        
        # Cleanup
        manager.stop()
        print("✅ Stream manager stopped")
        
    else:
        print("Audio Stream Manager - Phase 3.3.2")
        print("Usage: python audio_stream_manager.py --test")