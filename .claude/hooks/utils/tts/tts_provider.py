#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "python-dotenv>=1.0.0",
# ]
# ///

"""
TTS provider selection logic for Claude Code hooks.
Intelligently selects the best available TTS provider based on API keys and preferences.
"""

import os
import subprocess
import sys
from pathlib import Path
from typing import Optional, List, Callable
from dotenv import load_dotenv

class TTSProvider:
    """Manages TTS provider selection and execution."""
    
    def __init__(self):
        """Initialize TTS provider with environment configuration."""
        # Load environment variables
        env_path = Path.home() / "brainpods" / ".env"
        if env_path.exists():
            load_dotenv(env_path)
        
        self.tts_enabled = os.getenv("TTS_ENABLED", "true").lower() == "true"
        self.provider_preference = os.getenv("TTS_PROVIDER", "auto")
        self.utils_dir = Path(__file__).parent
        
    def get_available_providers(self) -> List[str]:
        """Get list of available TTS providers based on API keys."""
        providers = []
        
        # Check for API keys
        if os.getenv("ELEVENLABS_API_KEY"):
            providers.append("elevenlabs")
        if os.getenv("OPENAI_API_KEY"):
            providers.append("openai")
        
        # pyttsx3 is always available as offline fallback
        providers.append("pyttsx3")
        
        return providers
    
    def select_provider(self) -> Optional[str]:
        """Select the best available TTS provider."""
        if not self.tts_enabled:
            return None
        
        available = self.get_available_providers()
        
        # If specific provider requested, check if available
        if self.provider_preference != "auto":
            if self.provider_preference in available:
                return self.provider_preference
            else:
                print(f"Requested provider '{self.provider_preference}' not available, falling back", file=sys.stderr)
        
        # Auto selection priority: OpenAI > ElevenLabs > pyttsx3 (95% cost savings)
        priority = ["openai", "elevenlabs", "pyttsx3"]
        
        for provider in priority:
            if provider in available:
                return provider
        
        return None
    
    def speak(self, text: str, provider: Optional[str] = None) -> bool:
        """
        Speak text using the selected or specified provider.
        
        Args:
            text: Text to speak
            provider: Optional specific provider to use
            
        Returns:
            True if successful, False otherwise
        """
        if not self.tts_enabled:
            return False
        
        # Select provider if not specified
        if not provider:
            provider = self.select_provider()
        
        if not provider:
            print("No TTS provider available", file=sys.stderr)
            return False
        
        # Get provider script path
        script_map = {
            "elevenlabs": self.utils_dir / "elevenlabs_tts.py",
            "openai": self.utils_dir / "openai_tts.py",
            "pyttsx3": self.utils_dir / "pyttsx3_tts.py",
        }
        
        script_path = script_map.get(provider)
        if not script_path or not script_path.exists():
            print(f"TTS provider script not found: {provider}", file=sys.stderr)
            return False
        
        # Execute TTS script using python3 with system packages
        try:
            result = subprocess.run(
                [sys.executable, str(script_path), text],
                capture_output=True,
                text=True,
                timeout=30  # 30 second timeout
            )
            
            if result.returncode != 0:
                print(f"TTS provider {provider} failed: {result.stderr}", file=sys.stderr)
                return False
            
            return True
            
        except subprocess.TimeoutExpired:
            print(f"TTS provider {provider} timed out", file=sys.stderr)
            return False
        except Exception as e:
            print(f"TTS provider {provider} error: {e}", file=sys.stderr)
            return False
    
    def speak_with_fallback(self, text: str) -> bool:
        """
        Attempt to speak text with automatic fallback to other providers.
        
        Args:
            text: Text to speak
            
        Returns:
            True if any provider succeeded, False if all failed
        """
        if not self.tts_enabled:
            return False
        
        # Get provider order
        providers = self.get_available_providers()
        
        # Try each provider in order
        for provider in providers:
            if self.speak(text, provider):
                return True
        
        return False

def main():
    """Main entry point for testing."""
    import random
    
    # Test messages
    if len(sys.argv) > 1:
        text = " ".join(sys.argv[1:])
    else:
        messages = [
            "TTS provider selection is working!",
            "Intelligent voice synthesis active.",
            "Multi-provider TTS ready.",
        ]
        text = random.choice(messages)
    
    # Create provider and speak
    tts = TTSProvider()
    
    print(f"Available providers: {tts.get_available_providers()}")
    print(f"Selected provider: {tts.select_provider()}")
    
    success = tts.speak_with_fallback(text)
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()