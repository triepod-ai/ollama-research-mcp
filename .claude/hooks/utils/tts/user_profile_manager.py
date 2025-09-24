#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "python-dotenv>=1.0.0",
# ]
# ///

"""
Phase 3 TTS User Profile Management System
Advanced user profile management with analytics, multi-user support, and learning insights.

Features:
- Multi-user profile management
- Advanced analytics and usage insights
- Profile validation and integrity checking
- Import/export capabilities
- Learning pattern analysis
- Performance optimization
"""

import json
import os
import hashlib
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set, Any, Tuple, Union
from dotenv import load_dotenv

# Import personalization components
try:
    from .personalization_engine import UserProfile, PersonalityProfile, PersonalizationEngine
    PERSONALIZATION_AVAILABLE = True
except ImportError:
    PERSONALIZATION_AVAILABLE = False

# Load environment variables
env_path = Path.home() / "brainpods" / ".env"
if env_path.exists():
    load_dotenv(env_path)

class ProfileValidationError(Exception):
    """Exception raised when profile validation fails."""
    pass

class ProfileAnalytics(Enum):
    """Types of profile analytics available."""
    USAGE_PATTERNS = "usage_patterns"
    LEARNING_INSIGHTS = "learning_insights"
    PERFORMANCE_METRICS = "performance_metrics"
    PREFERENCE_TRENDS = "preference_trends"
    INTERACTION_ANALYSIS = "interaction_analysis"

@dataclass
class ProfileMetrics:
    """Comprehensive profile metrics and analytics."""
    total_interactions: int = 0
    active_days: int = 0
    average_daily_messages: float = 0.0
    peak_usage_hours: List[int] = field(default_factory=list)
    most_active_day: str = ""
    
    # Learning metrics
    adaptation_score: float = 0.0    # How well system has adapted to user
    preference_stability: float = 0.0  # How stable user preferences are
    learning_rate: float = 0.0       # How quickly user patterns change
    
    # Efficiency metrics
    message_reduction_ratio: float = 0.0  # Avg reduction through personalization
    skip_rate: float = 0.0              # Percentage of messages skipped
    engagement_score: float = 0.0        # Overall engagement with TTS
    
    # Quality metrics
    error_rate: float = 0.0             # Rate of TTS errors/issues
    satisfaction_score: float = 0.0      # Derived satisfaction metric
    response_time_ms: float = 0.0       # Average TTS response time

@dataclass
class LearningInsights:
    """Insights derived from user learning patterns."""
    dominant_patterns: List[str] = field(default_factory=list)
    emerging_preferences: List[str] = field(default_factory=list)
    declining_preferences: List[str] = field(default_factory=list)
    anomalies: List[str] = field(default_factory=list)
    
    # Behavioral insights
    attention_patterns: Dict[str, float] = field(default_factory=dict)
    productivity_correlations: Dict[str, float] = field(default_factory=dict)
    context_preferences: Dict[str, Dict] = field(default_factory=dict)
    
    # Predictive insights
    next_likely_actions: List[str] = field(default_factory=list)
    optimal_timing_windows: Dict[str, Tuple[int, int]] = field(default_factory=dict)
    suggested_personality_adjustments: Dict[str, str] = field(default_factory=dict)

class ProfileManager:
    """Advanced user profile management system."""
    
    def __init__(self):
        """Initialize the profile manager."""
        self.profiles_dir = Path.home() / "brainpods" / ".claude" / "profiles"
        self.profiles_dir.mkdir(parents=True, exist_ok=True)
        
        self.active_profile_id = None
        self.profiles_cache = {}
        self.analytics_cache = {}
        
        # Load configuration
        self.config = self._load_config()
        
        # Initialize current user profile
        self.current_profile = self._initialize_current_profile()
    
    def _load_config(self) -> Dict:
        """Load profile manager configuration."""
        return {
            "auto_backup": True,
            "max_profiles": 10,
            "analytics_retention_days": 90,
            "cache_size": 5,
            "validation_level": "strict",  # strict, normal, minimal
            "learning_sensitivity": 0.5,   # 0.0-1.0, how quickly to adapt
        }
    
    def _initialize_current_profile(self) -> Optional[str]:
        """Initialize profile for current user."""
        user_name = os.getenv("ENGINEER_NAME", os.getenv("USER", "default"))
        profile_id = self._generate_profile_id(user_name)
        
        # Check if profile exists
        if self.profile_exists(profile_id):
            self.active_profile_id = profile_id
            return profile_id
        else:
            # Create new profile
            return self.create_profile(user_name)
    
    def _generate_profile_id(self, user_name: str) -> str:
        """Generate unique profile ID from user name."""
        # Create hash of user name + machine info for uniqueness
        machine_info = f"{os.getenv('USER', '')}{os.getenv('HOSTNAME', '')}"
        profile_data = f"{user_name}{machine_info}"
        return hashlib.md5(profile_data.encode()).hexdigest()[:12]
    
    def create_profile(self, user_name: str, personality: str = "professional") -> str:
        """
        Create a new user profile.
        
        Args:
            user_name: Name of the user
            personality: Initial personality profile
            
        Returns:
            Profile ID
        """
        if not PERSONALIZATION_AVAILABLE:
            raise ProfileValidationError("Personalization engine not available")
        
        profile_id = self._generate_profile_id(user_name)
        
        # Check if profile already exists
        if self.profile_exists(profile_id):
            raise ProfileValidationError(f"Profile already exists for user: {user_name}")
        
        # Create new user profile
        try:
            personality_enum = PersonalityProfile(personality)
        except ValueError:
            personality_enum = PersonalityProfile.PROFESSIONAL
        
        user_profile = UserProfile(
            name=user_name,
            preferred_personality=personality_enum
        )
        
        # Save profile
        self._save_profile(profile_id, user_profile)
        
        # Set as active
        self.active_profile_id = profile_id
        
        return profile_id
    
    def load_profile(self, profile_id: str) -> UserProfile:
        """
        Load a user profile by ID.
        
        Args:
            profile_id: Profile identifier
            
        Returns:
            UserProfile object
        """
        if not PERSONALIZATION_AVAILABLE:
            raise ProfileValidationError("Personalization engine not available")
        
        # Check cache first
        if profile_id in self.profiles_cache:
            return self.profiles_cache[profile_id]
        
        profile_path = self.profiles_dir / f"{profile_id}.json"
        
        if not profile_path.exists():
            raise ProfileValidationError(f"Profile not found: {profile_id}")
        
        try:
            with open(profile_path, 'r') as f:
                data = json.load(f)
            
            # Validate profile data
            self._validate_profile_data(data)
            
            # Create UserProfile object
            user_profile = UserProfile(
                name=data.get("name", "Unknown"),
                preferred_personality=PersonalityProfile(data.get("preferred_personality", "professional")),
                timezone_offset=data.get("timezone_offset", 0),
                active_hours=tuple(data.get("active_hours", [9, 17])),
                project_contexts=data.get("project_contexts", {}),
                skip_patterns=data.get("skip_patterns", []),
                preferred_times=data.get("preferred_times", {}),
                voice_preferences=data.get("voice_preferences", {}),
                total_messages=data.get("total_messages", 0),
                messages_per_hour=data.get("messages_per_hour", {}),
                skip_rate_by_category=data.get("skip_rate_by_category", {})
            )
            
            # Cache profile
            if len(self.profiles_cache) >= self.config["cache_size"]:
                # Remove oldest entry
                oldest_key = next(iter(self.profiles_cache))
                del self.profiles_cache[oldest_key]
            
            self.profiles_cache[profile_id] = user_profile
            
            return user_profile
            
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            raise ProfileValidationError(f"Invalid profile data: {e}")
    
    def save_profile(self, profile_id: str, user_profile: UserProfile):
        """
        Save a user profile.
        
        Args:
            profile_id: Profile identifier
            user_profile: UserProfile object to save
        """
        self._save_profile(profile_id, user_profile)
        
        # Update cache
        self.profiles_cache[profile_id] = user_profile
        
        # Auto-backup if enabled
        if self.config["auto_backup"]:
            self._create_backup(profile_id)
    
    def _save_profile(self, profile_id: str, user_profile: UserProfile):
        """Internal method to save profile to disk."""
        profile_path = self.profiles_dir / f"{profile_id}.json"
        
        profile_data = {
            "profile_id": profile_id,
            "name": user_profile.name,
            "preferred_personality": user_profile.preferred_personality.value,
            "timezone_offset": user_profile.timezone_offset,
            "active_hours": list(user_profile.active_hours),
            "project_contexts": user_profile.project_contexts,
            "skip_patterns": user_profile.skip_patterns,
            "preferred_times": user_profile.preferred_times,
            "voice_preferences": user_profile.voice_preferences,
            "total_messages": user_profile.total_messages,
            "messages_per_hour": user_profile.messages_per_hour,
            "skip_rate_by_category": user_profile.skip_rate_by_category,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "version": "1.0"
        }
        
        try:
            with open(profile_path, 'w') as f:
                json.dump(profile_data, f, indent=2)
        except IOError as e:
            raise ProfileValidationError(f"Could not save profile: {e}")
    
    def profile_exists(self, profile_id: str) -> bool:
        """Check if a profile exists."""
        profile_path = self.profiles_dir / f"{profile_id}.json"
        return profile_path.exists()
    
    def list_profiles(self) -> List[Dict[str, str]]:
        """
        List all available profiles.
        
        Returns:
            List of profile information dictionaries
        """
        profiles = []
        
        for profile_file in self.profiles_dir.glob("*.json"):
            try:
                with open(profile_file, 'r') as f:
                    data = json.load(f)
                
                profiles.append({
                    "id": data.get("profile_id", profile_file.stem),
                    "name": data.get("name", "Unknown"),
                    "personality": data.get("preferred_personality", "professional"),
                    "created_at": data.get("created_at", ""),
                    "updated_at": data.get("updated_at", ""),
                    "total_messages": data.get("total_messages", 0)
                })
                
            except (json.JSONDecodeError, IOError):
                continue
        
        return sorted(profiles, key=lambda x: x["updated_at"], reverse=True)
    
    def delete_profile(self, profile_id: str):
        """
        Delete a profile.
        
        Args:
            profile_id: Profile identifier
        """
        if profile_id == self.active_profile_id:
            raise ProfileValidationError("Cannot delete active profile")
        
        profile_path = self.profiles_dir / f"{profile_id}.json"
        
        if profile_path.exists():
            # Create backup before deletion
            self._create_backup(profile_id, suffix="_deleted")
            
            # Remove profile file
            profile_path.unlink()
            
            # Remove from cache
            if profile_id in self.profiles_cache:
                del self.profiles_cache[profile_id]
        else:
            raise ProfileValidationError(f"Profile not found: {profile_id}")
    
    def analyze_profile(self, profile_id: str, analytics_type: ProfileAnalytics = ProfileAnalytics.USAGE_PATTERNS) -> Dict:
        """
        Analyze a user profile and generate insights.
        
        Args:
            profile_id: Profile identifier
            analytics_type: Type of analytics to perform
            
        Returns:
            Analytics results dictionary
        """
        # Check cache first
        cache_key = f"{profile_id}_{analytics_type.value}"
        if cache_key in self.analytics_cache:
            cache_entry = self.analytics_cache[cache_key]
            # Check if cache is still valid (1 hour)
            if datetime.now() - cache_entry["timestamp"] < timedelta(hours=1):
                return cache_entry["data"]
        
        user_profile = self.load_profile(profile_id)
        
        if analytics_type == ProfileAnalytics.USAGE_PATTERNS:
            analysis = self._analyze_usage_patterns(user_profile)
        elif analytics_type == ProfileAnalytics.LEARNING_INSIGHTS:
            analysis = self._analyze_learning_insights(user_profile)
        elif analytics_type == ProfileAnalytics.PERFORMANCE_METRICS:
            analysis = self._analyze_performance_metrics(user_profile)
        elif analytics_type == ProfileAnalytics.PREFERENCE_TRENDS:
            analysis = self._analyze_preference_trends(user_profile)
        elif analytics_type == ProfileAnalytics.INTERACTION_ANALYSIS:
            analysis = self._analyze_interactions(user_profile)
        else:
            analysis = {"error": "Unknown analytics type"}
        
        # Cache results
        self.analytics_cache[cache_key] = {
            "timestamp": datetime.now(),
            "data": analysis
        }
        
        return analysis
    
    def _analyze_usage_patterns(self, profile: UserProfile) -> Dict:
        """Analyze user usage patterns."""
        if not profile.messages_per_hour:
            return {"no_data": True}
        
        # Calculate peak usage hours
        peak_hours = sorted(profile.messages_per_hour.items(), key=lambda x: x[1], reverse=True)[:3]
        peak_hours = [int(hour) for hour, count in peak_hours]
        
        # Calculate average daily messages
        total_messages = sum(profile.messages_per_hour.values())
        active_hours = len([h for h in profile.messages_per_hour.values() if h > 0])
        avg_daily = total_messages / max(active_hours / 24, 1)
        
        return {
            "total_messages": profile.total_messages,
            "peak_usage_hours": peak_hours,
            "average_daily_messages": round(avg_daily, 2),
            "most_active_hour": max(profile.messages_per_hour, key=profile.messages_per_hour.get) if profile.messages_per_hour else 12,
            "usage_distribution": profile.messages_per_hour,
            "skip_rates": profile.skip_rate_by_category
        }
    
    def _analyze_learning_insights(self, profile: UserProfile) -> LearningInsights:
        """Analyze learning patterns and generate insights."""
        insights = LearningInsights()
        
        # Analyze skip patterns
        if profile.skip_patterns:
            insights.dominant_patterns = profile.skip_patterns[:5]
        
        # Analyze preference trends
        if profile.preferred_times:
            # Find emerging preferences (recently improved times)
            recent_preferences = []
            for time_category, preference_score in profile.preferred_times.items():
                if preference_score > 0.7:  # High preference
                    recent_preferences.append(time_category)
            
            insights.emerging_preferences = recent_preferences[:3]
        
        # Generate context preferences
        insights.context_preferences = {
            "personality": profile.preferred_personality.value,
            "active_hours": profile.active_hours,
            "skip_rate": sum(profile.skip_rate_by_category.values()) / max(len(profile.skip_rate_by_category), 1)
        }
        
        # Suggest personality adjustments
        if hasattr(profile, 'skip_rate_by_category'):
            overall_skip_rate = sum(profile.skip_rate_by_category.values()) / max(len(profile.skip_rate_by_category), 1)
            
            if overall_skip_rate > 0.5:  # High skip rate
                insights.suggested_personality_adjustments = {
                    "verbosity": "Consider reducing message verbosity",
                    "frequency": "Consider reducing notification frequency"
                }
            elif overall_skip_rate < 0.1:  # Low skip rate
                insights.suggested_personality_adjustments = {
                    "engagement": "User is highly engaged, consider more detailed messages"
                }
        
        return insights
    
    def _analyze_performance_metrics(self, profile: UserProfile) -> ProfileMetrics:
        """Analyze profile performance metrics."""
        metrics = ProfileMetrics()
        
        metrics.total_interactions = profile.total_messages
        
        # Calculate skip rate
        if profile.skip_rate_by_category:
            metrics.skip_rate = sum(profile.skip_rate_by_category.values()) / len(profile.skip_rate_by_category)
        
        # Calculate engagement score (inverse of skip rate)
        metrics.engagement_score = max(0, 1.0 - metrics.skip_rate)
        
        # Calculate peak usage hours
        if profile.messages_per_hour:
            sorted_hours = sorted(profile.messages_per_hour.items(), key=lambda x: x[1], reverse=True)
            metrics.peak_usage_hours = [int(hour) for hour, count in sorted_hours[:3]]
        
        # Estimate adaptation score based on profile completeness
        completeness_factors = [
            len(profile.skip_patterns) > 0,
            len(profile.preferred_times) > 0,
            len(profile.voice_preferences) > 0,
            profile.total_messages > 10
        ]
        metrics.adaptation_score = sum(completeness_factors) / len(completeness_factors)
        
        # Calculate learning rate (how much preferences change)
        if profile.preferred_times:
            preference_variance = sum((p - 0.5) ** 2 for p in profile.preferred_times.values()) / len(profile.preferred_times)
            metrics.learning_rate = min(1.0, preference_variance)
        
        return metrics
    
    def _analyze_preference_trends(self, profile: UserProfile) -> Dict:
        """Analyze preference trends over time."""
        trends = {
            "personality_stability": 1.0,  # How often personality changes
            "time_preferences": profile.preferred_times,
            "category_preferences": profile.skip_rate_by_category,
            "voice_preferences": profile.voice_preferences,
        }
        
        # Analyze skip pattern evolution
        if profile.skip_patterns:
            trends["skip_patterns_count"] = len(profile.skip_patterns)
            trends["dominant_skip_categories"] = profile.skip_patterns[:3]
        
        return trends
    
    def _analyze_interactions(self, profile: UserProfile) -> Dict:
        """Analyze interaction patterns and behavior."""
        return {
            "total_interactions": profile.total_messages,
            "interaction_distribution": profile.messages_per_hour,
            "response_patterns": profile.skip_rate_by_category,
            "learned_patterns": len(profile.skip_patterns),
            "adaptation_indicators": {
                "has_time_preferences": len(profile.preferred_times) > 0,
                "has_skip_patterns": len(profile.skip_patterns) > 0,
                "has_voice_preferences": len(profile.voice_preferences) > 0
            }
        }
    
    def _validate_profile_data(self, data: Dict):
        """Validate profile data integrity."""
        required_fields = ["name", "preferred_personality"]
        
        if self.config["validation_level"] == "strict":
            for field in required_fields:
                if field not in data:
                    raise ProfileValidationError(f"Missing required field: {field}")
            
            # Validate personality
            try:
                PersonalityProfile(data["preferred_personality"])
            except ValueError:
                raise ProfileValidationError(f"Invalid personality: {data['preferred_personality']}")
        
        # Validate numeric fields
        numeric_fields = ["timezone_offset", "total_messages"]
        for field in numeric_fields:
            if field in data and not isinstance(data[field], (int, float)):
                raise ProfileValidationError(f"Invalid numeric value for {field}")
    
    def _create_backup(self, profile_id: str, suffix: str = "_backup"):
        """Create a backup of a profile."""
        if not self.config["auto_backup"]:
            return
        
        profile_path = self.profiles_dir / f"{profile_id}.json"
        backup_path = self.profiles_dir / f"{profile_id}{suffix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        if profile_path.exists():
            try:
                import shutil
                shutil.copy2(profile_path, backup_path)
            except IOError:
                pass  # Backup failed, but don't error
    
    def export_profile(self, profile_id: str, export_path: Optional[Path] = None) -> Path:
        """
        Export a profile to a file.
        
        Args:
            profile_id: Profile identifier
            export_path: Optional export file path
            
        Returns:
            Path to exported file
        """
        profile = self.load_profile(profile_id)
        
        if not export_path:
            export_path = Path.cwd() / f"tts_profile_{profile.name}_{datetime.now().strftime('%Y%m%d')}.json"
        
        export_data = {
            "profile": asdict(profile),
            "export_info": {
                "exported_at": datetime.now().isoformat(),
                "version": "1.0",
                "exported_by": "TTS Profile Manager"
            }
        }
        
        with open(export_path, 'w') as f:
            json.dump(export_data, f, indent=2)
        
        return export_path
    
    def import_profile(self, import_path: Path) -> str:
        """
        Import a profile from a file.
        
        Args:
            import_path: Path to profile file
            
        Returns:
            Profile ID of imported profile
        """
        if not import_path.exists():
            raise ProfileValidationError(f"Import file not found: {import_path}")
        
        try:
            with open(import_path, 'r') as f:
                data = json.load(f)
            
            # Validate import data
            if "profile" not in data:
                raise ProfileValidationError("Invalid import file format")
            
            profile_data = data["profile"]
            
            # Generate new profile ID to avoid conflicts
            profile_id = self._generate_profile_id(profile_data.get("name", "imported"))
            
            # Create UserProfile
            user_profile = UserProfile(
                name=profile_data.get("name", "Imported User"),
                preferred_personality=PersonalityProfile(profile_data.get("preferred_personality", "professional")),
                timezone_offset=profile_data.get("timezone_offset", 0),
                active_hours=tuple(profile_data.get("active_hours", [9, 17])),
                project_contexts=profile_data.get("project_contexts", {}),
                skip_patterns=profile_data.get("skip_patterns", []),
                preferred_times=profile_data.get("preferred_times", {}),
                voice_preferences=profile_data.get("voice_preferences", {}),
                total_messages=profile_data.get("total_messages", 0),
                messages_per_hour=profile_data.get("messages_per_hour", {}),
                skip_rate_by_category=profile_data.get("skip_rate_by_category", {})
            )
            
            # Save imported profile
            self.save_profile(profile_id, user_profile)
            
            return profile_id
            
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            raise ProfileValidationError(f"Import failed: {e}")
    
    def get_current_profile(self) -> Optional[UserProfile]:
        """Get the current active profile."""
        if self.active_profile_id:
            return self.load_profile(self.active_profile_id)
        return None
    
    def switch_profile(self, profile_id: str):
        """Switch to a different profile."""
        if not self.profile_exists(profile_id):
            raise ProfileValidationError(f"Profile not found: {profile_id}")
        
        self.active_profile_id = profile_id
    
    def get_statistics(self) -> Dict:
        """Get profile manager statistics."""
        profiles = self.list_profiles()
        
        return {
            "total_profiles": len(profiles),
            "active_profile": self.active_profile_id,
            "cache_size": len(self.profiles_cache),
            "analytics_cache_size": len(self.analytics_cache),
            "profiles_directory": str(self.profiles_dir),
            "recent_profiles": profiles[:5] if profiles else []
        }

# Convenience functions
def get_current_user_profile() -> Optional[UserProfile]:
    """Get the current user's profile."""
    manager = ProfileManager()
    return manager.get_current_profile()

def analyze_current_user(analytics_type: ProfileAnalytics = ProfileAnalytics.USAGE_PATTERNS) -> Dict:
    """Analyze the current user's profile."""
    manager = ProfileManager()
    if manager.active_profile_id:
        return manager.analyze_profile(manager.active_profile_id, analytics_type)
    return {"error": "No active profile"}

def main():
    """Main entry point for testing."""
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "analyze":
        # Run analytics
        manager = ProfileManager()
        
        if not manager.active_profile_id:
            print("No active profile found")
            return
        
        print("🧪 User Profile Analysis")
        print("=" * 50)
        
        # Run all analytics types
        analytics_types = [
            ProfileAnalytics.USAGE_PATTERNS,
            ProfileAnalytics.PERFORMANCE_METRICS,
            ProfileAnalytics.LEARNING_INSIGHTS
        ]
        
        for analytics_type in analytics_types:
            print(f"\n📊 {analytics_type.value.replace('_', ' ').title()}:")
            
            results = manager.analyze_profile(manager.active_profile_id, analytics_type)
            
            if isinstance(results, dict):
                for key, value in results.items():
                    if isinstance(value, (list, dict)) and len(str(value)) > 100:
                        print(f"  {key}: [Complex data - {len(value)} items]")
                    else:
                        print(f"  {key}: {value}")
            else:
                # Handle LearningInsights object
                for field_name in ['dominant_patterns', 'emerging_preferences', 'suggested_personality_adjustments']:
                    if hasattr(results, field_name):
                        value = getattr(results, field_name)
                        print(f"  {field_name}: {value}")
    
    else:
        # Run basic test suite
        print("🧪 User Profile Manager Test Suite")
        print("=" * 50)
        
        manager = ProfileManager()
        
        print(f"\n👤 Current Profile Status:")
        print(f"  Active Profile ID: {manager.active_profile_id}")
        
        if manager.active_profile_id:
            profile = manager.get_current_profile()
            if profile:
                print(f"  Name: {profile.name}")
                print(f"  Personality: {profile.preferred_personality.value}")
                print(f"  Total Messages: {profile.total_messages}")
        
        print(f"\n📋 Available Profiles:")
        profiles = manager.list_profiles()
        for profile_info in profiles:
            print(f"  - {profile_info['name']} ({profile_info['id'][:8]}...)")
        
        print(f"\n📊 Manager Statistics:")
        stats = manager.get_statistics()
        for key, value in stats.items():
            if isinstance(value, (list, dict)) and len(str(value)) > 100:
                print(f"  {key}: [Complex data]")
            else:
                print(f"  {key}: {value}")

if __name__ == "__main__":
    main()