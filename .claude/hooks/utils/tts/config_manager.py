#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "python-dotenv>=1.0.0",
# ]
# ///

"""
Configuration management system for TTS providers.
Provides validated configuration loading and management.
Part of Phase 1 TTS System Improvements.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Dict, Any, List

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

class TTSError(Exception):
    """Base exception for TTS operations."""
    def __init__(self, message: str, provider: str, error_code: str = None):
        self.message = message
        self.provider = provider
        self.error_code = error_code
        super().__init__(f"[{provider}] {message}")

class TTSConfigurationError(TTSError):
    """Configuration-related errors."""
    pass

@dataclass
class TTSConfiguration:
    """Validated TTS configuration with defaults and validation."""
    
    # Core settings
    tts_enabled: bool = True
    provider_preference: str = "auto"
    
    # API Keys
    openai_api_key: Optional[str] = None
    elevenlabs_api_key: Optional[str] = None
    
    # OpenAI settings
    openai_voice: str = "nova"
    openai_model: str = "tts-1"
    openai_speed: float = 1.0
    
    # ElevenLabs settings
    elevenlabs_voice_id: str = "21m00Tcm4TlvDq8ikWAM"  # Rachel
    elevenlabs_model_id: str = "eleven_turbo_v2_5"
    elevenlabs_stability: float = 0.5
    elevenlabs_similarity_boost: float = 0.5
    
    # pyttsx3 settings
    pyttsx3_voice_id: Optional[str] = None
    pyttsx3_rate: int = 200
    pyttsx3_volume: float = 0.9
    
    # Advanced settings
    connection_timeout: float = 30.0
    max_connections: int = 5
    max_keepalive_connections: int = 2
    audio_buffer_ms: int = 100
    
    # Environment paths
    env_paths: List[Path] = field(default_factory=lambda: [
        Path.home() / "brainpods" / ".env",
        Path.home() / ".bash_aliases",
        Path.cwd() / ".env"
    ])
    
    @classmethod
    def from_environment(cls) -> 'TTSConfiguration':
        """
        Create configuration from environment with validation.
        
        Returns:
            Validated TTSConfiguration instance
            
        Raises:
            TTSConfigurationError: If configuration is invalid
        """
        # Load environment variables from all possible sources
        if load_dotenv:
            config = cls()
            for env_path in config.env_paths:
                if env_path.exists():
                    load_dotenv(env_path)
        
        # Create configuration from environment
        config = cls(
            # Core settings
            tts_enabled=os.getenv("TTS_ENABLED", "true").lower() == "true",
            provider_preference=os.getenv("TTS_PROVIDER", "auto"),
            
            # API Keys
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            elevenlabs_api_key=os.getenv("ELEVENLABS_API_KEY"),
            
            # OpenAI settings
            openai_voice=os.getenv("OPENAI_TTS_VOICE", "nova"),
            openai_model=os.getenv("OPENAI_TTS_MODEL", "tts-1"),
            openai_speed=float(os.getenv("OPENAI_TTS_SPEED", "1.0")),
            
            # ElevenLabs settings
            elevenlabs_voice_id=os.getenv("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM"),
            elevenlabs_model_id=os.getenv("ELEVENLABS_MODEL_ID", "eleven_turbo_v2_5"),
            elevenlabs_stability=float(os.getenv("ELEVENLABS_STABILITY", "0.5")),
            elevenlabs_similarity_boost=float(os.getenv("ELEVENLABS_SIMILARITY_BOOST", "0.5")),
            
            # pyttsx3 settings
            pyttsx3_voice_id=os.getenv("PYTTSX3_VOICE_ID"),
            pyttsx3_rate=int(os.getenv("PYTTSX3_RATE", "200")),
            pyttsx3_volume=float(os.getenv("PYTTSX3_VOLUME", "0.9")),
            
            # Advanced settings
            connection_timeout=float(os.getenv("TTS_CONNECTION_TIMEOUT", "30.0")),
            max_connections=int(os.getenv("TTS_MAX_CONNECTIONS", "5")),
            max_keepalive_connections=int(os.getenv("TTS_MAX_KEEPALIVE_CONNECTIONS", "2")),
            audio_buffer_ms=int(os.getenv("TTS_AUDIO_BUFFER_MS", "100")),
        )
        
        # Validate configuration
        config._validate()
        return config
    
    def _validate(self) -> None:
        """
        Validate configuration values.
        
        Raises:
            TTSConfigurationError: If any configuration value is invalid
        """
        # Validate provider preference
        valid_providers = ["auto", "openai", "elevenlabs", "pyttsx3"]
        if self.provider_preference not in valid_providers:
            raise TTSConfigurationError(
                f"Invalid provider preference: {self.provider_preference}. Must be one of: {valid_providers}",
                "configuration",
                "INVALID_PROVIDER"
            )
        
        # Validate OpenAI settings
        valid_openai_voices = ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]
        if self.openai_voice not in valid_openai_voices:
            raise TTSConfigurationError(
                f"Invalid OpenAI voice: {self.openai_voice}. Must be one of: {valid_openai_voices}",
                "configuration",
                "INVALID_OPENAI_VOICE"
            )
        
        valid_openai_models = ["tts-1", "tts-1-hd"]
        if self.openai_model not in valid_openai_models:
            raise TTSConfigurationError(
                f"Invalid OpenAI model: {self.openai_model}. Must be one of: {valid_openai_models}",
                "configuration",
                "INVALID_OPENAI_MODEL"
            )
        
        if not (0.25 <= self.openai_speed <= 4.0):
            raise TTSConfigurationError(
                f"Invalid OpenAI speed: {self.openai_speed}. Must be between 0.25 and 4.0",
                "configuration",
                "INVALID_OPENAI_SPEED"
            )
        
        # Validate ElevenLabs settings
        if not (0.0 <= self.elevenlabs_stability <= 1.0):
            raise TTSConfigurationError(
                f"Invalid ElevenLabs stability: {self.elevenlabs_stability}. Must be between 0.0 and 1.0",
                "configuration",
                "INVALID_ELEVENLABS_STABILITY"
            )
        
        if not (0.0 <= self.elevenlabs_similarity_boost <= 1.0):
            raise TTSConfigurationError(
                f"Invalid ElevenLabs similarity boost: {self.elevenlabs_similarity_boost}. Must be between 0.0 and 1.0",
                "configuration",
                "INVALID_ELEVENLABS_SIMILARITY_BOOST"
            )
        
        # Validate pyttsx3 settings
        if not (50 <= self.pyttsx3_rate <= 400):
            raise TTSConfigurationError(
                f"Invalid pyttsx3 rate: {self.pyttsx3_rate}. Must be between 50 and 400",
                "configuration",
                "INVALID_PYTTSX3_RATE"
            )
        
        if not (0.0 <= self.pyttsx3_volume <= 1.0):
            raise TTSConfigurationError(
                f"Invalid pyttsx3 volume: {self.pyttsx3_volume}. Must be between 0.0 and 1.0",
                "configuration",
                "INVALID_PYTTSX3_VOLUME"
            )
        
        # Validate advanced settings
        if self.connection_timeout <= 0:
            raise TTSConfigurationError(
                f"Invalid connection timeout: {self.connection_timeout}. Must be positive",
                "configuration",
                "INVALID_TIMEOUT"
            )
        
        if self.max_connections <= 0:
            raise TTSConfigurationError(
                f"Invalid max connections: {self.max_connections}. Must be positive",
                "configuration",
                "INVALID_MAX_CONNECTIONS"
            )
        
        if self.max_keepalive_connections < 0 or self.max_keepalive_connections > self.max_connections:
            raise TTSConfigurationError(
                f"Invalid max keepalive connections: {self.max_keepalive_connections}. Must be between 0 and {self.max_connections}",
                "configuration",
                "INVALID_KEEPALIVE_CONNECTIONS"
            )
    
    def get_available_providers(self) -> List[str]:
        """
        Get list of available providers based on API keys and configuration.
        
        Returns:
            List of available provider names
        """
        providers = []
        
        # Check for API keys
        if self.openai_api_key:
            providers.append("openai")
        
        if self.elevenlabs_api_key:
            providers.append("elevenlabs")
        
        # pyttsx3 is always available as offline fallback
        providers.append("pyttsx3")
        
        return providers
    
    def select_optimal_provider(self) -> Optional[str]:
        """
        Select the optimal provider based on availability and preferences.
        
        Returns:
            Selected provider name or None if TTS is disabled
        """
        if not self.tts_enabled:
            return None
        
        available = self.get_available_providers()
        
        # If specific provider requested, check if available
        if self.provider_preference != "auto":
            if self.provider_preference in available:
                return self.provider_preference
        
        # Auto selection priority: OpenAI > pyttsx3 (optimized for cost/performance)
        priority = ["openai", "pyttsx3"]
        
        for provider in priority:
            if provider in available:
                return provider
        
        return None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary for serialization."""
        return {
            "tts_enabled": self.tts_enabled,
            "provider_preference": self.provider_preference,
            "openai_voice": self.openai_voice,
            "openai_model": self.openai_model,
            "openai_speed": self.openai_speed,
            "elevenlabs_voice_id": self.elevenlabs_voice_id,
            "elevenlabs_model_id": self.elevenlabs_model_id,
            "elevenlabs_stability": self.elevenlabs_stability,
            "elevenlabs_similarity_boost": self.elevenlabs_similarity_boost,
            "pyttsx3_rate": self.pyttsx3_rate,
            "pyttsx3_volume": self.pyttsx3_volume,
            "connection_timeout": self.connection_timeout,
            "max_connections": self.max_connections,
            "max_keepalive_connections": self.max_keepalive_connections,
            "audio_buffer_ms": self.audio_buffer_ms,
            "available_providers": self.get_available_providers(),
            "selected_provider": self.select_optimal_provider(),
        }

# Global configuration instance
_global_config: Optional[TTSConfiguration] = None

def get_tts_config() -> TTSConfiguration:
    """
    Get the global TTS configuration instance.
    
    Returns:
        TTSConfiguration instance
        
    Raises:
        TTSConfigurationError: If configuration cannot be loaded or is invalid
    """
    global _global_config
    
    if _global_config is None:
        _global_config = TTSConfiguration.from_environment()
    
    return _global_config

def reload_tts_config() -> TTSConfiguration:
    """
    Reload the global TTS configuration from environment.
    
    Returns:
        Reloaded TTSConfiguration instance
        
    Raises:
        TTSConfigurationError: If configuration cannot be loaded or is invalid
    """
    global _global_config
    _global_config = TTSConfiguration.from_environment()
    return _global_config

def main():
    """Main entry point for testing configuration management."""
    import json
    import sys
    import argparse
    
    parser = argparse.ArgumentParser(description='TTS Configuration Management')
    parser.add_argument('--validate', action='store_true', help='Validate current configuration')
    parser.add_argument('--show', action='store_true', help='Show current configuration')
    parser.add_argument('--json', action='store_true', help='Output as JSON')
    parser.add_argument('--reload', action='store_true', help='Reload configuration from environment')
    
    args = parser.parse_args()
    
    try:
        if args.reload:
            config = reload_tts_config()
            print("Configuration reloaded successfully")
        else:
            config = get_tts_config()
        
        if args.validate:
            config._validate()
            print("✓ Configuration is valid")
        
        if args.show:
            if args.json:
                print(json.dumps(config.to_dict(), indent=2))
            else:
                print("TTS Configuration:")
                print(f"  TTS Enabled: {config.tts_enabled}")
                print(f"  Provider Preference: {config.provider_preference}")
                print(f"  Available Providers: {config.get_available_providers()}")
                print(f"  Selected Provider: {config.select_optimal_provider()}")
                print(f"  OpenAI Voice: {config.openai_voice}")
                print(f"  OpenAI Model: {config.openai_model}")
                print(f"  OpenAI Speed: {config.openai_speed}")
                print(f"  ElevenLabs Voice ID: {config.elevenlabs_voice_id}")
                print(f"  ElevenLabs Model: {config.elevenlabs_model_id}")
                print(f"  Connection Timeout: {config.connection_timeout}s")
                print(f"  Max Connections: {config.max_connections}")
        
        if not (args.validate or args.show or args.reload):
            # Default behavior - just validate
            config._validate()
            print("Configuration loaded and validated successfully")
            print(f"Available providers: {config.get_available_providers()}")
            print(f"Selected provider: {config.select_optimal_provider()}")
        
    except TTSConfigurationError as e:
        print(f"Configuration Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
