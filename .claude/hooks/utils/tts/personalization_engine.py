#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "python-dotenv>=1.0.0",
# ]
# ///

"""
Phase 3 TTS Personalization Engine
Context-aware message generation with voice personality profiles and user preference learning.

Features:
- Time-based message adaptation
- Project-specific terminology integration
- Voice personality profiles (Professional, Friendly, Efficient)
- User preference learning and pattern recognition
- Dynamic name inclusion probability
- Context-aware greeting and interaction patterns
"""

import json
import os
import random
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set, Any, Tuple
from dotenv import load_dotenv

# Load environment variables
env_path = Path.home() / "brainpods" / ".env"
if env_path.exists():
    load_dotenv(env_path)

class PersonalityProfile(Enum):
    """Voice personality profiles with distinct characteristics."""
    PROFESSIONAL = "professional"
    FRIENDLY = "friendly" 
    EFFICIENT = "efficient"
    CUSTOM = "custom"

class MessageContext(Enum):
    """Context types for message personalization."""
    ERROR = "error"
    SUCCESS = "success"
    WARNING = "warning"
    INFORMATION = "information"
    COMPLETION = "completion"
    PERMISSION = "permission"
    STARTUP = "startup"
    SHUTDOWN = "shutdown"

class TimeOfDay(Enum):
    """Time periods for time-aware personalization."""
    EARLY_MORNING = "early_morning"    # 5-9 AM
    MORNING = "morning"                # 9-12 PM  
    AFTERNOON = "afternoon"            # 12-5 PM
    EVENING = "evening"                # 5-9 PM
    NIGHT = "night"                    # 9 PM-5 AM

@dataclass
class PersonalitySettings:
    """Settings for a personality profile."""
    formality: str = "medium"          # low, medium, high
    enthusiasm: str = "medium"         # low, medium, high
    verbosity: str = "medium"          # minimal, concise, medium, verbose
    humor: str = "none"               # none, subtle, medium, high
    name_frequency: float = 0.3       # 0.0-1.0 probability of including name
    greeting_style: str = "professional"  # professional, casual, none
    
    # Personality-specific phrases and patterns
    success_phrases: List[str] = field(default_factory=list)
    error_phrases: List[str] = field(default_factory=list)
    transition_phrases: List[str] = field(default_factory=list)

@dataclass
class UserProfile:
    """User profile with learned preferences and patterns."""
    name: str = ""
    preferred_personality: PersonalityProfile = PersonalityProfile.PROFESSIONAL
    timezone_offset: int = 0           # Hours from UTC
    active_hours: Tuple[int, int] = (9, 17)  # Active work hours
    project_contexts: Dict[str, Dict] = field(default_factory=dict)
    
    # Learning data
    skip_patterns: List[str] = field(default_factory=list)  # Messages user tends to skip
    preferred_times: Dict[str, float] = field(default_factory=dict)  # Time preferences by category
    voice_preferences: Dict[str, str] = field(default_factory=dict)  # Voice per context
    interaction_history: deque = field(default_factory=lambda: deque(maxlen=100))
    
    # Statistics
    total_messages: int = 0
    messages_per_hour: Dict[int, int] = field(default_factory=dict)
    skip_rate_by_category: Dict[str, float] = field(default_factory=dict)

@dataclass
class PersonalizationContext:
    """Context information for message personalization."""
    user_profile: UserProfile
    current_time: datetime
    project_name: Optional[str] = None
    hook_type: str = ""
    tool_name: str = ""
    message_category: MessageContext = MessageContext.INFORMATION
    operation_type: str = ""
    attention_level: str = "normal"    # focused, normal, distracted
    recent_activity: List[str] = field(default_factory=list)

class PersonalizationEngine:
    """Advanced personalization engine for TTS messages."""
    
    def __init__(self):
        """Initialize the personalization engine."""
        self.user_profile = self._load_user_profile()
        self.personality_profiles = self._load_personality_profiles()
        self.project_context = self._load_project_context()
        self.time_context = TimeContext()
        self.learning_engine = UserPreferenceLearning(self.user_profile)
        
        # Personalization cache
        self.message_cache = {}
        self.context_cache = {}
        
        # Statistics
        self.stats = {
            "messages_personalized": 0,
            "name_inclusions": 0,
            "personality_applications": 0,
            "cache_hits": 0
        }
    
    def _load_user_profile(self) -> UserProfile:
        """Load user profile from environment and saved data."""
        profile_path = Path.home() / "brainpods" / ".claude" / "user_profile.json"
        
        # Create default profile
        profile = UserProfile(
            name=os.getenv("ENGINEER_NAME", os.getenv("USER", "Developer")),
            preferred_personality=PersonalityProfile(os.getenv("TTS_PERSONALITY", "professional"))
        )
        
        # Load saved profile if exists
        if profile_path.exists():
            try:
                with open(profile_path, 'r') as f:
                    data = json.load(f)
                    
                profile.name = data.get("name", profile.name)
                profile.preferred_personality = PersonalityProfile(data.get("preferred_personality", "professional"))
                profile.timezone_offset = data.get("timezone_offset", 0)
                profile.active_hours = tuple(data.get("active_hours", [9, 17]))
                profile.project_contexts = data.get("project_contexts", {})
                profile.skip_patterns = data.get("skip_patterns", [])
                profile.preferred_times = data.get("preferred_times", {})
                profile.voice_preferences = data.get("voice_preferences", {})
                profile.total_messages = data.get("total_messages", 0)
                profile.messages_per_hour = data.get("messages_per_hour", {})
                profile.skip_rate_by_category = data.get("skip_rate_by_category", {})
                
            except (json.JSONDecodeError, KeyError) as e:
                print(f"Warning: Could not load user profile: {e}")
        
        return profile
    
    def _load_personality_profiles(self) -> Dict[PersonalityProfile, PersonalitySettings]:
        """Load personality profile configurations."""
        return {
            PersonalityProfile.PROFESSIONAL: PersonalitySettings(
                formality="high",
                enthusiasm="low", 
                verbosity="concise",
                humor="none",
                name_frequency=0.2,
                greeting_style="professional",
                success_phrases=[
                    "Operation completed successfully",
                    "Task finished",
                    "Execution complete",
                    "Process successful"
                ],
                error_phrases=[
                    "An error has occurred",
                    "Operation failed",
                    "Error encountered",
                    "Issue detected"
                ],
                transition_phrases=[
                    "Proceeding to next step",
                    "Continuing",
                    "Moving forward"
                ]
            ),
            
            PersonalityProfile.FRIENDLY: PersonalitySettings(
                formality="low",
                enthusiasm="high",
                verbosity="conversational", 
                humor="subtle",
                name_frequency=0.6,
                greeting_style="casual",
                success_phrases=[
                    "Great! That worked perfectly",
                    "Awesome, we got it done",
                    "Nice! Operation successful",
                    "Perfect! All set"
                ],
                error_phrases=[
                    "Oops, we hit a snag",
                    "Hmm, something went wrong",
                    "Uh oh, got an error here",
                    "Looks like we have an issue"
                ],
                transition_phrases=[
                    "Alright, let's keep going",
                    "Moving on to the next thing",
                    "Okay, next up"
                ]
            ),
            
            PersonalityProfile.EFFICIENT: PersonalitySettings(
                formality="medium",
                enthusiasm="low",
                verbosity="minimal",
                humor="none", 
                name_frequency=0.1,
                greeting_style="none",
                success_phrases=[
                    "Done",
                    "Complete",
                    "Success",
                    "Finished"
                ],
                error_phrases=[
                    "Error",
                    "Failed",
                    "Issue",
                    "Problem"
                ],
                transition_phrases=[
                    "Next",
                    "Continuing", 
                    "Proceeding"
                ]
            )
        }
    
    def _load_project_context(self) -> Dict[str, Any]:
        """Load project-specific context information."""
        # Try to detect project from current directory
        cwd = Path.cwd()
        project_name = cwd.name
        
        # Check for common project files
        project_type = "general"
        project_tech_stack = []
        
        if (cwd / "package.json").exists():
            project_type = "javascript"
            project_tech_stack.extend(["Node.js", "JavaScript"])
            
            # Read package.json for more context
            try:
                with open(cwd / "package.json", 'r') as f:
                    package_data = json.load(f)
                    deps = package_data.get("dependencies", {})
                    if "react" in deps:
                        project_tech_stack.append("React")
                    if "typescript" in deps or "ts-node" in deps:
                        project_tech_stack.append("TypeScript")
                    if "express" in deps:
                        project_tech_stack.append("Express")
                        
            except (json.JSONDecodeError, IOError):
                pass
        
        elif (cwd / "requirements.txt").exists() or (cwd / "pyproject.toml").exists():
            project_type = "python"
            project_tech_stack.extend(["Python"])
            
        elif (cwd / "Cargo.toml").exists():
            project_type = "rust" 
            project_tech_stack.extend(["Rust"])
            
        elif (cwd / "go.mod").exists():
            project_type = "go"
            project_tech_stack.extend(["Go"])
        
        return {
            "name": project_name,
            "type": project_type,
            "tech_stack": project_tech_stack,
            "path": str(cwd)
        }
    
    def personalize_message(self, base_message: str, context: PersonalizationContext) -> str:
        """
        Apply comprehensive personalization to a message.
        
        Args:
            base_message: Original message text
            context: Personalization context information
            
        Returns:
            Personalized message text
        """
        # Check cache first
        cache_key = self._get_cache_key(base_message, context)
        if cache_key in self.message_cache:
            self.stats["cache_hits"] += 1
            return self.message_cache[cache_key]
        
        # Apply personalization pipeline
        personalized = base_message
        
        # Stage 1: Apply personality profile
        personalized = self._apply_personality_profile(personalized, context)
        
        # Stage 2: Add time-based adaptation
        personalized = self._apply_time_context(personalized, context)
        
        # Stage 3: Add project-specific terminology
        personalized = self._apply_project_context(personalized, context)
        
        # Stage 4: Apply learned user preferences
        personalized = self._apply_user_preferences(personalized, context)
        
        # Stage 5: Dynamic name inclusion
        personalized = self._apply_name_inclusion(personalized, context)
        
        # Stage 6: Context-aware greetings and transitions
        personalized = self._apply_contextual_enhancements(personalized, context)
        
        # Cache result
        self.message_cache[cache_key] = personalized
        
        # Update statistics
        self.stats["messages_personalized"] += 1
        if context.user_profile.name.lower() in personalized.lower():
            self.stats["name_inclusions"] += 1
        
        return personalized
    
    def _apply_personality_profile(self, message: str, context: PersonalizationContext) -> str:
        """Apply personality profile characteristics to message."""
        personality = context.user_profile.preferred_personality
        settings = self.personality_profiles[personality]
        
        # Replace generic phrases with personality-specific ones
        if context.message_category == MessageContext.SUCCESS:
            for generic, specific in zip(
                ["success", "completed", "done", "finished"],
                settings.success_phrases
            ):
                if generic in message.lower():
                    # Randomly select from personality phrases
                    replacement = random.choice(settings.success_phrases)
                    message = message.lower().replace(generic, replacement.lower())
                    break
        
        elif context.message_category == MessageContext.ERROR:
            for generic, specific in zip(
                ["error", "failed", "issue", "problem"],
                settings.error_phrases
            ):
                if generic in message.lower():
                    replacement = random.choice(settings.error_phrases)
                    message = message.lower().replace(generic, replacement.lower())
                    break
        
        # Adjust verbosity based on personality
        if settings.verbosity == "minimal":
            # Remove unnecessary words
            words_to_remove = ["please", "kindly", "just", "simply", "basically"]
            for word in words_to_remove:
                message = message.replace(f" {word} ", " ")
                message = message.replace(f"{word.title()} ", "")
        
        elif settings.verbosity == "verbose":
            # Add descriptive words
            if "completed" in message.lower():
                message = message.replace("completed", "successfully completed")
            if "error" in message.lower():
                message = message.replace("error", "unexpected error")
        
        self.stats["personality_applications"] += 1
        return message
    
    def _apply_time_context(self, message: str, context: PersonalizationContext) -> str:
        """Apply time-based message adaptations."""
        time_period = self._get_time_period(context.current_time)
        
        # Add time-appropriate greetings for certain message types
        if context.message_category in [MessageContext.STARTUP, MessageContext.COMPLETION]:
            personality = context.user_profile.preferred_personality
            settings = self.personality_profiles[personality]
            
            if settings.greeting_style != "none":
                greeting = self._get_time_appropriate_greeting(time_period, personality)
                if greeting:
                    # Add greeting with small probability to avoid spam
                    if random.random() < 0.3:
                        message = f"{greeting} {message}"
        
        # Adjust urgency based on time
        if time_period == TimeOfDay.NIGHT:
            # Reduce urgency for non-critical messages at night
            if context.message_category not in [MessageContext.ERROR]:
                message = message.replace("immediately", "when convenient")
                message = message.replace("urgent", "important")
        
        return message
    
    def _apply_project_context(self, message: str, context: PersonalizationContext) -> str:
        """Apply project-specific terminology and context."""
        project = self.project_context
        
        # Add project name for relevant operations
        if context.project_name and random.random() < 0.2:
            if context.message_category == MessageContext.COMPLETION:
                message = f"{message} for {context.project_name}"
        
        # Use project-specific technical terms
        if project["type"] == "javascript" and "React" in project["tech_stack"]:
            message = message.replace("component", "React component")
        elif project["type"] == "python":
            message = message.replace("script", "Python script")
        elif project["type"] == "rust":
            message = message.replace("build", "Rust build")
        
        return message
    
    def _apply_user_preferences(self, message: str, context: PersonalizationContext) -> str:
        """Apply learned user preferences and patterns."""
        profile = context.user_profile
        
        # Skip patterns that user tends to ignore
        for pattern in profile.skip_patterns:
            if pattern.lower() in message.lower():
                # User typically skips these messages, make them more concise
                message = message[:min(len(message), 80)]
                break
        
        # Apply preferred voice characteristics based on learning
        category_str = context.message_category.value
        if category_str in profile.voice_preferences:
            # This could influence voice selection in the TTS provider
            pass
        
        return message
    
    def _apply_name_inclusion(self, message: str, context: PersonalizationContext) -> str:
        """Apply dynamic name inclusion based on context."""
        profile = context.user_profile
        personality = self.personality_profiles[profile.preferred_personality]
        
        # Calculate dynamic name probability
        base_probability = personality.name_frequency
        
        # Adjust based on message importance
        if context.message_category == MessageContext.ERROR:
            name_probability = min(base_probability * 2, 0.8)
        elif context.message_category == MessageContext.SUCCESS:
            name_probability = base_probability * 1.5
        elif context.message_category == MessageContext.COMPLETION:
            name_probability = base_probability * 0.8
        else:
            name_probability = base_probability
        
        # Adjust based on time of day
        time_period = self._get_time_period(context.current_time)
        if time_period == TimeOfDay.EARLY_MORNING:
            name_probability *= 1.5  # More personal in morning
        elif time_period == TimeOfDay.NIGHT:
            name_probability *= 0.5  # Less personal at night
        
        # Adjust based on attention level
        if context.attention_level == "focused":
            name_probability *= 0.5  # Less distraction when focused
        elif context.attention_level == "distracted":
            name_probability *= 1.5  # More personal to get attention
        
        # Apply name inclusion
        if profile.name and random.random() < name_probability:
            # Choose inclusion style based on personality
            if personality.formality == "high":
                message = f"{profile.name}, {message.lower()}"
            elif personality.formality == "low":
                greetings = ["Hey", "Hi", "Yo", ""]
                greeting = random.choice(greetings)
                if greeting:
                    message = f"{greeting} {profile.name}, {message.lower()}"
                else:
                    message = f"{profile.name}, {message.lower()}"
            else:
                message = f"{profile.name}, {message.lower()}"
        
        return message
    
    def _apply_contextual_enhancements(self, message: str, context: PersonalizationContext) -> str:
        """Apply context-aware enhancements and transitions."""
        personality = self.personality_profiles[context.user_profile.preferred_personality]
        
        # Add transitions for sequential operations
        if len(context.recent_activity) > 0:
            last_activity = context.recent_activity[-1]
            if context.hook_type == "post_tool_use" and "completed" in last_activity:
                # Add transition phrase
                if random.random() < 0.3:
                    transition = random.choice(personality.transition_phrases)
                    message = f"{transition}. {message}"
        
        # Add context-appropriate emphasis
        if context.message_category == MessageContext.ERROR:
            if personality.enthusiasm != "low":
                message = message.replace("error", "⚠️ error")
        elif context.message_category == MessageContext.SUCCESS:
            if personality.enthusiasm == "high":
                message = message.replace("success", "✅ success")
        
        return message
    
    def _get_cache_key(self, message: str, context: PersonalizationContext) -> str:
        """Generate cache key for message personalization."""
        key_components = [
            message[:50],  # First 50 chars of message
            context.user_profile.preferred_personality.value,
            context.message_category.value,
            str(context.current_time.hour),  # Hour for time-based caching
            context.hook_type,
            context.tool_name
        ]
        return "|".join(key_components)
    
    def _get_time_period(self, current_time: datetime) -> TimeOfDay:
        """Determine time period from current time."""
        hour = current_time.hour
        
        if 5 <= hour < 9:
            return TimeOfDay.EARLY_MORNING
        elif 9 <= hour < 12:
            return TimeOfDay.MORNING
        elif 12 <= hour < 17:
            return TimeOfDay.AFTERNOON
        elif 17 <= hour < 21:
            return TimeOfDay.EVENING
        else:
            return TimeOfDay.NIGHT
    
    def _get_time_appropriate_greeting(self, time_period: TimeOfDay, personality: PersonalityProfile) -> Optional[str]:
        """Get appropriate greeting for time and personality."""
        greetings = {
            TimeOfDay.EARLY_MORNING: {
                PersonalityProfile.PROFESSIONAL: "Good morning.",
                PersonalityProfile.FRIENDLY: "Good morning!",
                PersonalityProfile.EFFICIENT: None
            },
            TimeOfDay.MORNING: {
                PersonalityProfile.PROFESSIONAL: None,
                PersonalityProfile.FRIENDLY: "Morning!",
                PersonalityProfile.EFFICIENT: None
            },
            TimeOfDay.AFTERNOON: {
                PersonalityProfile.PROFESSIONAL: "Good afternoon.",
                PersonalityProfile.FRIENDLY: "Afternoon!",
                PersonalityProfile.EFFICIENT: None
            },
            TimeOfDay.EVENING: {
                PersonalityProfile.PROFESSIONAL: "Good evening.",
                PersonalityProfile.FRIENDLY: "Evening!",
                PersonalityProfile.EFFICIENT: None
            },
            TimeOfDay.NIGHT: {
                PersonalityProfile.PROFESSIONAL: None,
                PersonalityProfile.FRIENDLY: "Working late?",
                PersonalityProfile.EFFICIENT: None
            }
        }
        
        return greetings.get(time_period, {}).get(personality)
    
    def save_user_profile(self):
        """Save user profile to disk."""
        profile_path = Path.home() / "brainpods" / ".claude" / "user_profile.json"
        profile_path.parent.mkdir(parents=True, exist_ok=True)
        
        profile_data = {
            "name": self.user_profile.name,
            "preferred_personality": self.user_profile.preferred_personality.value,
            "timezone_offset": self.user_profile.timezone_offset,
            "active_hours": list(self.user_profile.active_hours),
            "project_contexts": self.user_profile.project_contexts,
            "skip_patterns": self.user_profile.skip_patterns,
            "preferred_times": self.user_profile.preferred_times,
            "voice_preferences": self.user_profile.voice_preferences,
            "total_messages": self.user_profile.total_messages,
            "messages_per_hour": self.user_profile.messages_per_hour,
            "skip_rate_by_category": self.user_profile.skip_rate_by_category,
            "last_updated": datetime.now().isoformat()
        }
        
        try:
            with open(profile_path, 'w') as f:
                json.dump(profile_data, f, indent=2)
        except IOError as e:
            print(f"Warning: Could not save user profile: {e}")
    
    def get_statistics(self) -> Dict:
        """Get personalization statistics."""
        return {
            **self.stats.copy(),
            "user_profile": {
                "name": self.user_profile.name,
                "personality": self.user_profile.preferred_personality.value,
                "total_messages": self.user_profile.total_messages,
                "cache_size": len(self.message_cache)
            },
            "project_context": self.project_context
        }

class TimeContext:
    """Helper class for time-based context analysis."""
    
    def __init__(self):
        self.timezone_offset = int(os.getenv("TTS_TIMEZONE_OFFSET", "0"))
    
    def get_current_time(self) -> datetime:
        """Get current time with timezone adjustment."""
        return datetime.now() + timedelta(hours=self.timezone_offset)
    
    def is_work_hours(self, user_profile: UserProfile, current_time: datetime) -> bool:
        """Check if current time is within user's work hours."""
        hour = current_time.hour
        start, end = user_profile.active_hours
        return start <= hour < end

class UserPreferenceLearning:
    """Learning engine for user preferences and patterns."""
    
    def __init__(self, user_profile: UserProfile):
        self.user_profile = user_profile
        self.learning_buffer = deque(maxlen=50)
    
    def record_interaction(self, message: str, category: str, response_type: str):
        """Record user interaction for learning."""
        interaction = {
            "timestamp": datetime.now().isoformat(),
            "message": message,
            "category": category,
            "response": response_type,  # "spoken", "skipped", "interrupted"
            "time_of_day": datetime.now().hour
        }
        
        self.learning_buffer.append(interaction)
        self.user_profile.interaction_history.append(interaction)
        
        # Update learning patterns
        self._update_skip_patterns()
        self._update_time_preferences()
    
    def _update_skip_patterns(self):
        """Update patterns for messages user tends to skip."""
        # Simple pattern learning - in production, use more sophisticated ML
        skip_count = defaultdict(int)
        total_count = defaultdict(int)
        
        for interaction in self.user_profile.interaction_history:
            message_words = set(interaction["message"].lower().split())
            total_count[interaction["category"]] += 1
            
            if interaction["response"] == "skipped":
                skip_count[interaction["category"]] += 1
                
                # Track words in skipped messages
                for word in message_words:
                    if len(word) > 3:  # Skip short words
                        if word not in self.user_profile.skip_patterns:
                            # Simple heuristic: if word appears in >50% of skipped messages
                            skip_ratio = skip_count.get(word, 0) / max(total_count.get(word, 1), 1)
                            if skip_ratio > 0.5:
                                self.user_profile.skip_patterns.append(word)
    
    def _update_time_preferences(self):
        """Update time-based preferences."""
        for interaction in self.user_profile.interaction_history:
            category = interaction["category"]
            hour = interaction.get("time_of_day", 12)
            response = interaction["response"]
            
            # Track response rates by time
            time_key = f"{category}_{hour}"
            if time_key not in self.user_profile.preferred_times:
                self.user_profile.preferred_times[time_key] = 0.5
            
            # Adjust preference based on response
            if response == "spoken":
                self.user_profile.preferred_times[time_key] = min(1.0, 
                    self.user_profile.preferred_times[time_key] + 0.1)
            elif response == "skipped":
                self.user_profile.preferred_times[time_key] = max(0.0,
                    self.user_profile.preferred_times[time_key] - 0.1)

# Convenience functions for integration
def personalize_tts_message(
    message: str, 
    hook_type: str = "",
    tool_name: str = "",
    category: str = "information",
    project_name: Optional[str] = None
) -> str:
    """
    Personalize a TTS message with full context awareness.
    
    Args:
        message: Original message text
        hook_type: Type of hook triggering the message
        tool_name: Name of tool being used
        category: Message category (error, success, etc.)
        project_name: Current project name
        
    Returns:
        Personalized message text
    """
    engine = PersonalizationEngine()
    
    # Create personalization context
    context = PersonalizationContext(
        user_profile=engine.user_profile,
        current_time=engine.time_context.get_current_time(),
        project_name=project_name or engine.project_context["name"],
        hook_type=hook_type,
        tool_name=tool_name,
        message_category=MessageContext(category) if category in [e.value for e in MessageContext] else MessageContext.INFORMATION
    )
    
    return engine.personalize_message(message, context)

def get_personality_settings(personality: str = None) -> PersonalitySettings:
    """Get personality settings for a given personality type."""
    engine = PersonalizationEngine()
    
    if personality:
        try:
            profile = PersonalityProfile(personality)
            return engine.personality_profiles[profile]
        except ValueError:
            pass
    
    # Return current user's personality settings
    return engine.personality_profiles[engine.user_profile.preferred_personality]

def main():
    """Main entry point for testing."""
    import sys
    
    # Test messages with different contexts
    test_scenarios = [
        ("File processing completed successfully", "post_tool_use", "Write", "success"),
        ("Error: File not found", "post_tool_use", "Read", "error"), 
        ("Permission required for command execution", "notification", "Bash", "permission"),
        ("Task finished", "stop", "", "completion"),
        ("Starting build process", "pre_tool_use", "Bash", "information")
    ]
    
    if len(sys.argv) > 1:
        # Test single message
        message = " ".join(sys.argv[1:])
        personalized = personalize_tts_message(message)
        print(f"Original: {message}")
        print(f"Personalized: {personalized}")
    else:
        # Run test suite
        print("🧪 Personalization Engine Test Suite")
        print("=" * 50)
        
        engine = PersonalizationEngine()
        
        print(f"\n👤 User Profile:")
        print(f"  Name: {engine.user_profile.name}")
        print(f"  Personality: {engine.user_profile.preferred_personality.value}")
        print(f"  Project: {engine.project_context['name']} ({engine.project_context['type']})")
        
        # Test different personalities
        personalities = [PersonalityProfile.PROFESSIONAL, PersonalityProfile.FRIENDLY, PersonalityProfile.EFFICIENT]
        
        for personality in personalities:
            print(f"\n🎭 Testing {personality.value.title()} Personality:")
            
            # Temporarily change personality
            original_personality = engine.user_profile.preferred_personality
            engine.user_profile.preferred_personality = personality
            
            for message, hook_type, tool_name, category in test_scenarios:
                context = PersonalizationContext(
                    user_profile=engine.user_profile,
                    current_time=datetime.now(),
                    hook_type=hook_type,
                    tool_name=tool_name,
                    message_category=MessageContext(category),
                    project_name=engine.project_context["name"]
                )
                
                personalized = engine.personalize_message(message, context)
                print(f"  {message[:30]}... → {personalized}")
            
            # Restore original personality
            engine.user_profile.preferred_personality = original_personality
        
        print(f"\n📊 Statistics:")
        stats = engine.get_statistics()
        for key, value in stats.items():
            if isinstance(value, dict):
                print(f"  {key}:")
                for subkey, subvalue in value.items():
                    print(f"    {subkey}: {subvalue}")
            else:
                print(f"  {key}: {value}")

if __name__ == "__main__":
    main()