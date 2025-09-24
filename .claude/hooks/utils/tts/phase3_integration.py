#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "python-dotenv>=1.0.0",
# ]
# ///

"""
Phase 3 TTS Integration Layer
Unified integration layer that connects Phase 3 advanced features with existing hook system.

Features:
- Seamless integration with Phase 2 coordination
- Transcript processing pipeline
- Message personalization with user profiles
- Message aggregation for batch operations
- Performance optimization with caching
- Backward compatibility and graceful fallback
"""

import os
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Any, Tuple, Union
from dotenv import load_dotenv

# Import Phase 3.3.2 Advanced Systems (Primary)
try:
    from .audio_stream_manager import (
        get_stream_manager,
        submit_tts_request,
        StreamPolicy,
        StreamQuality,
        get_tts_queue_status
    )
    STREAM_MANAGER_AVAILABLE = True
except ImportError:
    STREAM_MANAGER_AVAILABLE = False

# Import Phase 3.3 Sound Effects System  
try:
    from .sound_effects_engine import (
        get_sound_effects_engine,
        play_contextual_sound_effect,
        SoundTiming,
        SoundTheme
    )
    SOUND_EFFECTS_AVAILABLE = True
except ImportError:
    SOUND_EFFECTS_AVAILABLE = False

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
    from .playback_coordinator import (
        get_playback_coordinator,
        play_tts_message
    )
    COORDINATOR_AVAILABLE = True
except ImportError:
    COORDINATOR_AVAILABLE = False

try:
    from .provider_health_monitor import (
        get_health_monitor,
        select_best_provider
    )
    HEALTH_MONITOR_AVAILABLE = True
except ImportError:
    HEALTH_MONITOR_AVAILABLE = False

# Import Phase 3.1/3.2 Components (Secondary)
try:
    from .transcript_processor import (
        process_message_with_metrics, 
        ProcessingLevel,
        ProcessedText
    )
    TRANSCRIPT_PROCESSOR_AVAILABLE = True
except ImportError:
    TRANSCRIPT_PROCESSOR_AVAILABLE = False

try:
    from .personalization_engine import (
        personalize_tts_message,
        PersonalizationContext,
        PersonalizationEngine,
        MessageContext
    )
    PERSONALIZATION_AVAILABLE = True
except ImportError:
    PERSONALIZATION_AVAILABLE = False

try:
    from .message_aggregator import (
        should_aggregate_tts_message,
        AggregationDecision
    )
    MESSAGE_AGGREGATOR_AVAILABLE = True
except ImportError:
    MESSAGE_AGGREGATOR_AVAILABLE = False
    # Fallback for type hints when message aggregator is not available
    class AggregationDecision:
        SPEAK_IMMEDIATELY = "speak_immediately"
        WAIT_FOR_MORE = "wait_for_more"
        DISCARD = "discard"

try:
    from .user_profile_manager import (
        get_current_user_profile,
        ProfileManager
    )
    PROFILE_MANAGER_AVAILABLE = True
except ImportError:
    PROFILE_MANAGER_AVAILABLE = False

# Import Phase 2 coordination system
try:
    from .observability import (
        should_speak_event_coordinated,
        EventCategory,
        EventPriority,
        get_observability
    )
    PHASE2_COORDINATION_AVAILABLE = True
except ImportError:
    PHASE2_COORDINATION_AVAILABLE = False

# Load environment variables
env_path = Path.home() / "brainpods" / ".env"
if env_path.exists():
    load_dotenv(env_path)

class Phase3Features:
    """Control which Phase 3 features are enabled."""
    def __init__(self):
        # Phase 3.3.2 Advanced Features
        self.advanced_queue_system = os.getenv("PHASE3_ADVANCED_QUEUE", "true").lower() == "true"
        self.playback_coordination = os.getenv("PHASE3_PLAYBACK_COORD", "true").lower() == "true"
        self.provider_health_monitoring = os.getenv("PHASE3_HEALTH_MONITOR", "true").lower() == "true"
        self.stream_management = os.getenv("PHASE3_STREAM_MANAGER", "true").lower() == "true"
        
        # Phase 3.3 Sound Effects
        self.sound_effects = os.getenv("PHASE3_SOUND_EFFECTS", "true").lower() == "true"
        
        # Phase 3.1/3.2 Legacy Features
        self.transcript_processing = os.getenv("PHASE3_TRANSCRIPT_PROCESSING", "true").lower() == "true"
        self.personalization = os.getenv("PHASE3_PERSONALIZATION", "true").lower() == "true"
        self.message_aggregation = os.getenv("PHASE3_MESSAGE_AGGREGATION", "true").lower() == "true"
        self.user_profiles = os.getenv("PHASE3_USER_PROFILES", "true").lower() == "true"
        self.performance_optimization = os.getenv("PHASE3_PERFORMANCE_OPT", "true").lower() == "true"

class Phase3TtsIntegrator:
    """Unified integrator for Phase 3 TTS features with advanced systems."""
    
    def __init__(self):
        """Initialize the Phase 3 TTS integrator."""
        self.features = Phase3Features()
        self.performance_cache = {}
        
        # Phase 3.3.2 Advanced Components
        self.stream_manager = None
        self.advanced_queue = None
        self.playback_coordinator = None
        self.health_monitor = None
        
        # Phase 3.1/3.2 Legacy Components
        self.profile_manager = None
        self.personalization_engine = None
        
        # Initialize available components
        self._initialize_components()
        
        # Enhanced Statistics
        self.stats = {
            "messages_processed": 0,
            "stream_requests_submitted": 0,
            "advanced_queue_used": 0,
            "coordinator_playback_used": 0,
            "health_monitor_used": 0,
            "transcript_processing_used": 0,
            "personalization_applied": 0,
            "aggregation_decisions": 0,
            "cache_hits": 0,
            "fallback_used": 0
        }
    
    def _initialize_components(self):
        """Initialize available Phase 3 components."""
        # Initialize Phase 3.3.2 Advanced Components
        if STREAM_MANAGER_AVAILABLE and self.features.stream_management:
            try:
                self.stream_manager = get_stream_manager()
                # Start stream manager if not already started
                if not self.stream_manager.manager_active:
                    self.stream_manager.start()
            except Exception as e:
                print(f"Warning: Failed to initialize stream manager: {e}")
        
        if ADVANCED_QUEUE_AVAILABLE and self.features.advanced_queue_system:
            try:
                self.advanced_queue = get_advanced_queue()
            except Exception as e:
                print(f"Warning: Failed to initialize advanced queue: {e}")
        
        if COORDINATOR_AVAILABLE and self.features.playback_coordination:
            try:
                self.playback_coordinator = get_playback_coordinator()
                if not self.playback_coordinator.running:
                    self.playback_coordinator.start()
            except Exception as e:
                print(f"Warning: Failed to initialize playback coordinator: {e}")
        
        if HEALTH_MONITOR_AVAILABLE and self.features.provider_health_monitoring:
            try:
                self.health_monitor = get_health_monitor()
                if not self.health_monitor.monitoring_active:
                    self.health_monitor.start_monitoring()
            except Exception as e:
                print(f"Warning: Failed to initialize health monitor: {e}")
        
        # Initialize Phase 3.1/3.2 Legacy Components
        if PROFILE_MANAGER_AVAILABLE and self.features.user_profiles:
            try:
                self.profile_manager = ProfileManager()
            except Exception:
                pass
        
        if PERSONALIZATION_AVAILABLE and self.features.personalization:
            try:
                self.personalization_engine = PersonalizationEngine()
            except Exception:
                pass
    
    def process_tts_message(
        self,
        original_message: str,
        hook_type: str,
        tool_name: str = "",
        event_category: str = "general",
        event_priority: int = 3,
        metadata: Optional[Dict] = None
    ) -> Tuple[bool, str]:
        """
        Process a TTS message through Phase 3 advanced features pipeline.
        
        Args:
            original_message: Original message text
            hook_type: Type of hook (notification, post_tool_use, etc.)
            tool_name: Name of the tool being used
            event_category: Category of the event
            event_priority: Priority level (1=critical, 5=minimal)
            metadata: Additional metadata
            
        Returns:
            Tuple of (should_speak, processed_message)
        """
        start_time = time.time()
        processed_message = original_message
        should_speak = True
        
        try:
            # Step 1: Transcript Processing (Phase 3.1)
            if self.features.transcript_processing and TRANSCRIPT_PROCESSOR_AVAILABLE:
                processed_message = self._apply_transcript_processing(
                    processed_message, hook_type, tool_name
                )
                self.stats["transcript_processing_used"] += 1
            
            # Step 2: Message Aggregation Decision (Phase 3.1)
            if self.features.message_aggregation and MESSAGE_AGGREGATOR_AVAILABLE:
                aggregation_decision = self._check_message_aggregation(
                    processed_message, hook_type, tool_name, event_category, event_priority, metadata
                )
                
                if aggregation_decision == AggregationDecision.WAIT_FOR_MORE:
                    # Don't speak now, wait for aggregation
                    should_speak = False
                    self.stats["aggregation_decisions"] += 1
                elif aggregation_decision == AggregationDecision.DISCARD:
                    # Message is redundant
                    should_speak = False
                    self.stats["aggregation_decisions"] += 1
            
            # Step 3: Personalization (Phase 3.2)
            if should_speak and self.features.personalization and PERSONALIZATION_AVAILABLE:
                processed_message = self._apply_personalization(
                    processed_message, hook_type, tool_name, event_category, metadata
                )
                self.stats["personalization_applied"] += 1
            
            # Step 3.5: Sound Effects Processing (Phase 3.3)
            if should_speak and self.features.sound_effects and SOUND_EFFECTS_AVAILABLE:
                self._process_sound_effects(
                    processed_message, hook_type, tool_name, event_category, event_priority, metadata
                )
            
            # Step 4: Advanced Stream Management (Phase 3.3.2)
            if should_speak and self.stream_manager and self.features.stream_management:
                return self._process_through_stream_manager(
                    processed_message, hook_type, tool_name, event_category, event_priority, metadata
                )
            
            # Step 5: Phase 2 Coordination Check (Fallback)
            if should_speak and PHASE2_COORDINATION_AVAILABLE:
                should_speak = self._check_phase2_coordination(
                    processed_message, hook_type, tool_name, event_category, event_priority, metadata
                )
            
            # Update statistics
            self.stats["messages_processed"] += 1
            
            # Performance tracking
            processing_time = (time.time() - start_time) * 1000
            if processing_time > 100:  # Log slow operations
                print(f"Warning: Phase 3 processing took {processing_time:.1f}ms")
            
            return should_speak, processed_message
            
        except Exception as e:
            # Graceful fallback on any error
            print(f"Phase 3 processing error: {e}")
            self.stats["fallback_used"] += 1
            
            # Use Phase 2 coordination as fallback
            if PHASE2_COORDINATION_AVAILABLE:
                should_speak = self._check_phase2_coordination(
                    original_message, hook_type, tool_name, event_category, event_priority, metadata
                )
                return should_speak, original_message
            else:
                # Ultimate fallback - simple filtering
                return self._basic_filtering(original_message, event_priority), original_message
    
    def _apply_transcript_processing(self, message: str, hook_type: str, tool_name: str) -> str:
        """Apply transcript processing to optimize message for TTS."""
        try:
            # Determine processing level based on context
            if hook_type == "notification":
                level = ProcessingLevel.STANDARD
            elif hook_type in ["post_tool_use", "pre_tool_use"]:
                level = ProcessingLevel.SMART
            elif hook_type in ["stop", "subagent_stop"]:
                level = ProcessingLevel.AGGRESSIVE
            else:
                level = ProcessingLevel.STANDARD
            
            # Process message with context
            context = {
                "hook_type": hook_type,
                "tool_name": tool_name,
                "timestamp": datetime.now().isoformat()
            }
            
            result = process_message_with_metrics(message, context, level)
            
            # Use processed message if it's significantly shorter and maintains quality
            if result.metrics.confidence > 0.7 and result.metrics.reduction_ratio < 0.8:
                return result.processed
            else:
                return message
                
        except Exception as e:
            print(f"Transcript processing error: {e}")
            return message
    
    def _check_message_aggregation(
        self,
        message: str,
        hook_type: str, 
        tool_name: str,
        event_category: str,
        event_priority: int,
        metadata: Optional[Dict]
    ) -> AggregationDecision:
        """Check if message should be aggregated."""
        try:
            event_data = {
                "priority": event_priority,
                "category": event_category,
                "hook_type": hook_type,
                "tool_name": tool_name,
                "metadata": metadata or {}
            }
            
            return should_aggregate_tts_message(message, event_data)
            
        except Exception as e:
            print(f"Message aggregation error: {e}")
            return AggregationDecision.SPEAK_IMMEDIATELY
    
    def _apply_personalization(
        self,
        message: str,
        hook_type: str,
        tool_name: str,
        event_category: str,
        metadata: Optional[Dict]
    ) -> str:
        """Apply personalization to message."""
        try:
            # Get current project context
            project_name = None
            if metadata and "project_name" in metadata:
                project_name = metadata["project_name"]
            
            # Apply personalization
            return personalize_tts_message(
                message=message,
                hook_type=hook_type,
                tool_name=tool_name,
                category=event_category,
                project_name=project_name
            )
            
        except Exception as e:
            print(f"Personalization error: {e}")
            return message
    
    def _process_sound_effects(
        self,
        message: str,
        hook_type: str,
        tool_name: str,
        event_category: str,
        event_priority: int,
        metadata: Optional[Dict]
    ) -> bool:
        """Process contextual sound effects for TTS message."""
        try:
            # Map event priority to AdvancedPriority enum
            if event_priority <= 1:
                priority = AdvancedPriority.CRITICAL
            elif event_priority == 2:
                priority = AdvancedPriority.HIGH
            elif event_priority == 3:
                priority = AdvancedPriority.MEDIUM
            elif event_priority == 4:
                priority = AdvancedPriority.LOW
            else:
                priority = AdvancedPriority.BACKGROUND
            
            # Map event category to MessageType enum
            if event_category in ["error", "security"]:
                message_type = MessageType.ERROR
            elif event_category in ["permission", "performance"]:
                message_type = MessageType.WARNING
            elif event_category == "completion":
                message_type = MessageType.SUCCESS
            else:
                message_type = MessageType.INFO
            
            # Play contextual sound effect (pre-TTS)
            sound_id = play_contextual_sound_effect(
                priority=priority,
                message_type=message_type, 
                hook_type=hook_type,
                tool_name=tool_name,
                timing=SoundTiming.PRE_TTS
            )
            
            if sound_id:
                self.stats["sound_effects_played"] = self.stats.get("sound_effects_played", 0) + 1
                return True
            
        except Exception as e:
            print(f"Sound effects processing error: {e}")
        
        return False
    
    def _check_phase2_coordination(
        self,
        message: str,
        hook_type: str,
        tool_name: str,
        event_category: str,
        event_priority: int,
        metadata: Optional[Dict]
    ) -> bool:
        """Check Phase 2 coordination for TTS decision."""
        try:
            # Map string values to enum values
            category_map = {
                "error": EventCategory.ERROR,
                "security": EventCategory.SECURITY,
                "permission": EventCategory.PERMISSION,
                "performance": EventCategory.PERFORMANCE,
                "file_operation": EventCategory.FILE_OPERATION,
                "command_execution": EventCategory.COMMAND_EXECUTION,
                "completion": EventCategory.COMPLETION,
                "general": EventCategory.GENERAL
            }
            
            priority_map = {
                1: EventPriority.CRITICAL,
                2: EventPriority.HIGH,
                3: EventPriority.MEDIUM,
                4: EventPriority.LOW,
                5: EventPriority.MINIMAL
            }
            
            category_enum = category_map.get(event_category, EventCategory.GENERAL)
            priority_enum = priority_map.get(event_priority, EventPriority.MEDIUM)
            
            return should_speak_event_coordinated(
                message=message,
                priority=priority_enum.value,
                category=category_enum.value,
                hook_type=hook_type,
                tool_name=tool_name,
                metadata=metadata or {}
            )
            
        except Exception as e:
            print(f"Phase 2 coordination error: {e}")
            return self._basic_filtering(message, event_priority)
    
    def _process_through_stream_manager(
        self,
        message: str,
        hook_type: str,
        tool_name: str,
        event_category: str,
        event_priority: int,
        metadata: Optional[Dict]
    ) -> Tuple[bool, str]:
        """Process message through Phase 3.3.2 advanced stream management."""
        try:
            # Create advanced TTS message
            if ADVANCED_QUEUE_AVAILABLE:
                # Map priority and category to advanced enums
                advanced_priority = self._map_to_advanced_priority(event_priority)
                message_type = self._map_to_message_type(event_category)
                
                advanced_message = AdvancedTTSMessage(
                    content=message,
                    priority=advanced_priority,
                    message_type=message_type,
                    hook_type=hook_type,
                    tool_name=tool_name,
                    metadata=metadata or {}
                )
                
                # Select appropriate stream policy and quality
                policy = self._select_stream_policy(event_priority, event_category)
                quality = self._select_stream_quality(event_priority, hook_type)
                
                # Submit to stream manager
                request_id = self.stream_manager.submit_request(
                    message=advanced_message,
                    policy=policy,
                    quality=quality,
                    preferred_provider=self._select_preferred_provider(event_priority),
                    max_total_time_ms=self._calculate_sla_timeout(event_priority)
                )
                
                if request_id:
                    self.stats["stream_requests_submitted"] += 1
                    # Return True to indicate message was handled by stream manager
                    return True, message
                else:
                    # Stream manager couldn't handle request, fallback
                    return self._fallback_to_coordination(message, hook_type, tool_name, event_category, event_priority, metadata)
            else:
                # Advanced queue not available, try coordinator directly
                return self._fallback_to_coordinator(message, hook_type, tool_name, event_category, event_priority, metadata)
                
        except Exception as e:
            print(f"Stream manager processing error: {e}")
            # Fallback to Phase 2 coordination
            return self._fallback_to_coordination(message, hook_type, tool_name, event_category, event_priority, metadata)
    
    def _map_to_advanced_priority(self, priority: int) -> 'AdvancedPriority':
        """Map integer priority to AdvancedPriority enum."""
        mapping = {
            1: AdvancedPriority.CRITICAL,
            2: AdvancedPriority.HIGH,
            3: AdvancedPriority.MEDIUM,
            4: AdvancedPriority.LOW,
            5: AdvancedPriority.BACKGROUND
        }
        return mapping.get(priority, AdvancedPriority.MEDIUM)
    
    def _map_to_message_type(self, category: str) -> 'MessageType':
        """Map category string to MessageType enum."""
        mapping = {
            "error": MessageType.ERROR,
            "warning": MessageType.WARNING,
            "completion": MessageType.SUCCESS,
            "success": MessageType.SUCCESS,
            "general": MessageType.INFO,
            "permission": MessageType.WARNING,
            "performance": MessageType.WARNING,
        }
        return mapping.get(category, MessageType.INFO)
    
    def _select_stream_policy(self, priority: int, category: str) -> 'StreamPolicy':
        """Select appropriate stream policy based on context."""
        if priority == 1 or category == "error":  # Critical
            return StreamPolicy.REAL_TIME
        elif priority == 2:  # High priority
            return StreamPolicy.GUARANTEED
        elif category in ["completion", "success"]:
            return StreamPolicy.BATCH_OPTIMIZED
        else:
            return StreamPolicy.BEST_EFFORT
    
    def _select_stream_quality(self, priority: int, hook_type: str) -> 'StreamQuality':
        """Select appropriate stream quality based on context."""
        if priority == 1:  # Critical - need fast response
            return StreamQuality.LOW
        elif priority == 2:  # High priority - balanced
            return StreamQuality.STANDARD
        elif hook_type in ["stop", "subagent_stop"]:  # Summary messages - high quality
            return StreamQuality.HIGH
        else:
            return StreamQuality.STANDARD
    
    def _select_preferred_provider(self, priority: int) -> Optional[str]:
        """Select preferred provider based on priority."""
        if priority == 1:  # Critical - fastest response
            return "pyttsx3"  # Offline, fastest
        elif priority <= 2:  # High priority - good balance
            return "openai"  # Cost-effective, good quality
        else:
            return None  # Let health monitor decide
    
    def _calculate_sla_timeout(self, priority: int) -> int:
        """Calculate SLA timeout based on priority."""
        timeouts = {
            1: 2000,   # 2 seconds for critical
            2: 5000,   # 5 seconds for high
            3: 10000,  # 10 seconds for medium
            4: 15000,  # 15 seconds for low
            5: 30000   # 30 seconds for background
        }
        return timeouts.get(priority, 10000)
    
    def _fallback_to_coordinator(self, message: str, hook_type: str, tool_name: str, event_category: str, event_priority: int, metadata: Optional[Dict]) -> Tuple[bool, str]:
        """Fallback to playback coordinator if stream manager fails."""
        if self.playback_coordinator and self.features.playback_coordination:
            try:
                # Create basic advanced message if possible
                if ADVANCED_QUEUE_AVAILABLE:
                    advanced_message = AdvancedTTSMessage(
                        content=message,
                        priority=self._map_to_advanced_priority(event_priority),
                        message_type=self._map_to_message_type(event_category),
                        hook_type=hook_type,
                        tool_name=tool_name,
                        metadata=metadata or {}
                    )
                    
                    stream_id = self.playback_coordinator.play_message(advanced_message)
                    if stream_id:
                        self.stats["coordinator_playback_used"] += 1
                        return True, message
                
            except Exception as e:
                print(f"Coordinator fallback error: {e}")
        
        # Final fallback to Phase 2 coordination
        return self._fallback_to_coordination(message, hook_type, tool_name, event_category, event_priority, metadata)
    
    def _fallback_to_coordination(self, message: str, hook_type: str, tool_name: str, event_category: str, event_priority: int, metadata: Optional[Dict]) -> Tuple[bool, str]:
        """Fallback to Phase 2 coordination system."""
        if PHASE2_COORDINATION_AVAILABLE:
            should_speak = self._check_phase2_coordination(
                message, hook_type, tool_name, event_category, event_priority, metadata
            )
            return should_speak, message
        else:
            return self._basic_filtering(message, event_priority), message
    
    def _basic_filtering(self, message: str, priority: int) -> bool:
        """Basic filtering as ultimate fallback."""
        # Simple priority-based filtering
        if priority <= 2:  # Critical and high priority
            return True
        elif priority == 3:  # Medium priority
            return len(message) < 200  # Only if message is reasonably short
        else:  # Low priority
            return len(message) < 100  # Only if message is very short
    
    def record_user_interaction(
        self,
        message: str,
        category: str,
        response_type: str,
        hook_type: str = ""
    ):
        """Record user interaction for learning."""
        if self.features.user_profiles and PROFILE_MANAGER_AVAILABLE and self.profile_manager:
            try:
                current_profile = self.profile_manager.get_current_profile()
                if current_profile:
                    # Create learning engine for current profile
                    from .user_profile_manager import UserPreferenceLearning
                    learning = UserPreferenceLearning(current_profile)
                    learning.record_interaction(message, category, response_type)
                    
                    # Save updated profile
                    self.profile_manager.save_profile(
                        self.profile_manager.active_profile_id,
                        current_profile
                    )
                    
            except Exception as e:
                print(f"User interaction recording error: {e}")
    
    def get_component_status(self) -> Dict[str, Any]:
        """Get status of all Phase 3 components."""
        status = {
            "features_enabled": {
                # Phase 3.5 Unified Orchestrator
                "unified_orchestrator": self.features.unified_orchestrator,
                "intelligent_routing": self.features.intelligent_routing,
                "streaming_auto_detection": self.features.streaming_auto_detection,
                
                # Phase 3.3.2 Advanced Features (Fallback)
                "advanced_queue_system": self.features.advanced_queue_system,
                "playback_coordination": self.features.playback_coordination,
                "provider_health_monitoring": self.features.provider_health_monitoring,
                "stream_management": self.features.stream_management,
                
                # Phase 3.1/3.2 Legacy Features
                "transcript_processing": self.features.transcript_processing,
                "personalization": self.features.personalization,
                "message_aggregation": self.features.message_aggregation,
                "user_profiles": self.features.user_profiles,
                "performance_optimization": self.features.performance_optimization
            },
            "components_available": {
                # Phase 3.5 Unified Orchestrator
                "unified_orchestrator": UNIFIED_ORCHESTRATOR_AVAILABLE,
                
                # Phase 3.3.2 Advanced Components (Fallback)
                "stream_manager": STREAM_MANAGER_AVAILABLE,
                "advanced_queue": ADVANCED_QUEUE_AVAILABLE,
                "playback_coordinator": COORDINATOR_AVAILABLE,
                "health_monitor": HEALTH_MONITOR_AVAILABLE,
                
                # Phase 3.1/3.2 Legacy Components
                "transcript_processor": TRANSCRIPT_PROCESSOR_AVAILABLE,
                "personalization_engine": PERSONALIZATION_AVAILABLE,
                "message_aggregator": MESSAGE_AGGREGATOR_AVAILABLE,
                "profile_manager": PROFILE_MANAGER_AVAILABLE,
                "phase2_coordination": PHASE2_COORDINATION_AVAILABLE
            },
            "components_initialized": {
                # Phase 3.5 Unified Orchestrator
                "unified_orchestrator": self.unified_orchestrator is not None,
                
                # Phase 3.3.2 Advanced Components (Fallback)
                "stream_manager": self.stream_manager is not None,
                "advanced_queue": self.advanced_queue is not None,
                "playback_coordinator": self.playback_coordinator is not None,
                "health_monitor": self.health_monitor is not None,
                
                # Phase 3.1/3.2 Legacy Components
                "profile_manager": self.profile_manager is not None,
                "personalization_engine": self.personalization_engine is not None
            },
            "statistics": self.stats.copy()
        }
        
        # Add unified orchestrator status if available
        if self.unified_orchestrator:
            status["unified_orchestrator_status"] = get_orchestrator_status()
        else:
            status["advanced_system_status"] = self._get_advanced_system_status()
        
        return status
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics for Phase 3 integration."""
        if self.stats["messages_processed"] == 0:
            return {"no_data": True}
        
        total_messages = self.stats["messages_processed"]
        
        metrics = {
            "total_messages": total_messages,
            "unified_system_usage": {
                "unified_orchestrator": self.stats["unified_orchestrator_used"] / total_messages,
                "streaming_requests": self.stats["streaming_requests"] / total_messages,
                "traditional_requests": self.stats["traditional_requests"] / total_messages,
            },
            "advanced_system_usage": {
                "stream_manager": self.stats["stream_requests_submitted"] / total_messages,
                "advanced_queue": self.stats["advanced_queue_used"] / total_messages,
                "playback_coordinator": self.stats["coordinator_playback_used"] / total_messages,
                "health_monitor": self.stats["health_monitor_used"] / total_messages,
            },
            "legacy_feature_usage": {
                "transcript_processing": self.stats["transcript_processing_used"] / total_messages,
                "personalization": self.stats["personalization_applied"] / total_messages,
                "aggregation": self.stats["aggregation_decisions"] / total_messages,
            },
            "reliability": {
                "fallback_rate": self.stats["fallback_used"] / total_messages,
                "success_rate": 1.0 - (self.stats["fallback_used"] / total_messages),
                "unified_adoption": self.stats["unified_orchestrator_used"] / total_messages,
                "advanced_system_adoption": (self.stats["stream_requests_submitted"] + self.stats["coordinator_playback_used"]) / total_messages
            },
            "cache_performance": {
                "hits": self.stats["cache_hits"],
                "hit_rate": self.stats["cache_hits"] / max(total_messages, 1)
            }
        }
        
        # Add system health from unified orchestrator or legacy systems
        if self.unified_orchestrator:
            orchestrator_status = get_orchestrator_status()
            metrics["system_health"] = {
                "orchestrator_health": "healthy" if orchestrator_status["running"] else "inactive",
                "component_availability": orchestrator_status["component_availability"],
                "overall_health": "healthy" if orchestrator_status["running"] and \
                    any(orchestrator_status["component_availability"].values()) else "degraded"
            }
        else:
            metrics["system_health"] = self._get_system_health_metrics()
        
        return metrics
    
    def _get_advanced_system_status(self) -> Dict[str, Any]:
        """Get status of advanced systems."""
        status = {}
        
        # Stream Manager Status
        if self.stream_manager:
            status["stream_manager"] = self.stream_manager.get_queue_status()
        
        # Health Monitor Status
        if self.health_monitor:
            status["health_monitor"] = self.health_monitor.get_monitoring_status()
        
        # Playback Coordinator Status
        if self.playback_coordinator:
            status["playback_coordinator"] = self.playback_coordinator.get_coordinator_status()
        
        # Advanced Queue Status
        if self.advanced_queue:
            status["advanced_queue"] = {
                "size": self.advanced_queue.size(),
                "state": self.advanced_queue.state.value,
                "analytics": self.advanced_queue.get_analytics().to_dict() if hasattr(self.advanced_queue, 'get_analytics') else {}
            }
        
        return status
    
    def _get_system_health_metrics(self) -> Dict[str, Any]:
        """Get system health metrics."""
        health = {"overall_health": "unknown"}
        
        try:
            if self.stream_manager:
                queue_status = self.stream_manager.get_queue_status()
                health["stream_manager_health"] = "healthy" if queue_status.get("manager_active") else "inactive"
            
            if self.health_monitor:
                monitor_status = self.health_monitor.get_monitoring_status()
                active_providers = sum(1 for provider in monitor_status["providers"].values() if provider["is_available"])
                health["provider_health"] = "healthy" if active_providers > 0 else "degraded"
            
            # Overall health assessment
            health_indicators = [v for k, v in health.items() if k != "overall_health" and v == "healthy"]
            total_indicators = len([v for k, v in health.items() if k != "overall_health"])
            
            if len(health_indicators) == total_indicators:
                health["overall_health"] = "healthy"
            elif len(health_indicators) > total_indicators / 2:
                health["overall_health"] = "degraded"
            else:
                health["overall_health"] = "unhealthy"
                
        except Exception as e:
            health["error"] = str(e)
            health["overall_health"] = "error"
        
        return health

# Global integrator instance
_integrator = None

def get_phase3_integrator() -> Phase3TtsIntegrator:
    """Get or create the global Phase 3 integrator instance."""
    global _integrator
    if _integrator is None:
        _integrator = Phase3TtsIntegrator()
    return _integrator

def process_hook_message(
    message: str,
    hook_type: str,
    tool_name: str = "",
    category: str = "general",
    priority: int = 3,
    metadata: Optional[Dict] = None
) -> Tuple[bool, str]:
    """
    Convenient function for hooks to process TTS messages.
    
    Args:
        message: Original message text
        hook_type: Type of hook calling this
        tool_name: Name of tool being used
        category: Event category
        priority: Priority level (1-5)
        metadata: Additional context
        
    Returns:
        Tuple of (should_speak, processed_message)
    """
    integrator = get_phase3_integrator()
    return integrator.process_tts_message(
        original_message=message,
        hook_type=hook_type,
        tool_name=tool_name,
        event_category=category,
        event_priority=priority,
        metadata=metadata
    )

def record_hook_interaction(
    message: str,
    category: str,
    response: str,
    hook_type: str = ""
):
    """
    Record user interaction for learning.
    
    Args:
        message: The TTS message
        category: Message category
        response: User response (spoken, skipped, interrupted)
        hook_type: Type of hook
    """
    integrator = get_phase3_integrator()
    integrator.record_user_interaction(message, category, response, hook_type)

def get_integration_status() -> Dict[str, Any]:
    """Get complete Phase 3 integration status."""
    integrator = get_phase3_integrator()
    return integrator.get_component_status()

def main():
    """Main entry point for testing."""
    import sys
    
    # Test messages representing different hook scenarios
    test_scenarios = [
        {
            "message": "Error: File `/home/user/code.py` not found at line 42",
            "hook_type": "post_tool_use",
            "tool_name": "Read",
            "category": "error",
            "priority": 1
        },
        {
            "message": "File processing completed successfully",
            "hook_type": "post_tool_use", 
            "tool_name": "Write",
            "category": "completion",
            "priority": 3
        },
        {
            "message": "Permission required to execute sudo command",
            "hook_type": "notification",
            "tool_name": "Bash", 
            "category": "permission",
            "priority": 2
        },
        {
            "message": "Task analysis complete with 5 files processed",
            "hook_type": "subagent_stop",
            "tool_name": "",
            "category": "completion",
            "priority": 3
        },
        {
            "message": "Session ended with ```python\nprint('Hello World')\n``` execution",
            "hook_type": "stop",
            "tool_name": "",
            "category": "completion",
            "priority": 3
        }
    ]
    
    if len(sys.argv) > 1:
        # Test single message
        message = " ".join(sys.argv[1:])
        should_speak, processed = process_hook_message(
            message=message,
            hook_type="test",
            tool_name="test"
        )
        
        print(f"Original: {message}")
        print(f"Processed: {processed}")
        print(f"Should Speak: {should_speak}")
    else:
        # Run integration test suite
        print("🧪 Phase 3 Integration Test Suite")
        print("=" * 50)
        
        integrator = get_phase3_integrator()
        
        # Show component status
        status = integrator.get_component_status()
        print(f"\n🔧 Component Status:")
        
        for category, components in status["components_available"].items():
            if isinstance(components, dict):
                print(f"  {category}:")
                for name, available in components.items():
                    status_icon = "✅" if available else "❌"
                    print(f"    {status_icon} {name}")
            else:
                status_icon = "✅" if components else "❌"
                print(f"  {status_icon} {category}")
        
        print(f"\n📝 Testing Message Processing Pipeline:")
        
        for i, scenario in enumerate(test_scenarios, 1):
            print(f"\n🔍 Test {i}: {scenario['hook_type']} - {scenario['category']}")
            print(f"  Original: {scenario['message'][:50]}...")
            
            should_speak, processed = process_hook_message(**scenario)
            
            print(f"  Processed: {processed[:60]}...")
            print(f"  Should Speak: {'✅' if should_speak else '❌'}")
            
            # Simulate recording interaction
            response = "spoken" if should_speak else "skipped"
            record_hook_interaction(
                message=processed,
                category=scenario["category"],
                response=response,
                hook_type=scenario["hook_type"]
            )
        
        # Show performance metrics
        print(f"\n📊 Performance Metrics:")
        metrics = integrator.get_performance_metrics()
        
        if "no_data" not in metrics:
            print(f"  Total Messages: {metrics['total_messages']}")
            print(f"  Success Rate: {metrics['reliability']['success_rate']:.2%}")
            
            usage_rates = metrics["feature_usage_rates"]
            for feature, rate in usage_rates.items():
                print(f"  {feature.replace('_', ' ').title()}: {rate:.2%}")
        else:
            print("  No performance data available")
        
        print(f"\n📈 Final Statistics:")
        for key, value in integrator.stats.items():
            print(f"  {key.replace('_', ' ').title()}: {value}")

if __name__ == "__main__":
    main()