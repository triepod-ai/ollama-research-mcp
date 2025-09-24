#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "requests>=2.31.0",
#   "pygame>=2.5.0",
#   "python-dotenv>=1.0.0",
# ]
# ///

"""
ElevenLabs TTS provider for Claude Code hooks.
High-quality AI voice synthesis with multiple voice options.
"""

import os
import sys
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

def speak_with_elevenlabs(text: str, voice_id: Optional[str] = None) -> bool:
    """
    Convert text to speech using ElevenLabs API.
    
    Args:
        text: Text to convert to speech
        voice_id: Optional voice ID (defaults to Rachel)
        
    Returns:
        True if successful, False otherwise
    """
    try:
        import requests
        import tempfile
        import pygame
        from pathlib import Path as PathLib
        
        # Load environment variables
        env_path = Path.home() / "brainpods" / ".env"
        if env_path.exists():
            load_dotenv(env_path)
        
        # Get API key
        api_key = os.getenv("ELEVENLABS_API_KEY")
        if not api_key:
            print("ElevenLabs API key not found in environment", file=sys.stderr)
            return False
        
        # Default to Rachel voice if not specified
        if not voice_id:
            voice_id = os.getenv("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")
        
        # ElevenLabs API endpoint
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
        
        headers = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": api_key
        }
        
        data = {
            "text": text,
            "model_id": "eleven_monolingual_v1",
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.5
            }
        }
        
        # Make API request
        response = requests.post(url, json=data, headers=headers)
        
        if response.status_code != 200:
            print(f"ElevenLabs API error: {response.status_code} - {response.text}", file=sys.stderr)
            return False
        
        # Save audio to temporary file and play
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp_file:
            tmp_file.write(response.content)
            tmp_path = tmp_file.name
        
        # Play using pygame
        pygame.mixer.init()
        pygame.mixer.music.load(tmp_path)
        pygame.mixer.music.play()
        
        # Wait for playback to complete
        while pygame.mixer.music.get_busy():
            pygame.time.Clock().tick(10)
        
        # Cleanup
        pygame.mixer.quit()
        os.unlink(tmp_path)
        
        return True
        
    except Exception as e:
        print(f"ElevenLabs TTS error: {e}", file=sys.stderr)
        return False

def main():
    """Main entry point for standalone usage."""
    import random
    
    # Get text from command line or use default
    if len(sys.argv) > 1:
        text = " ".join(sys.argv[1:])
    else:
        # Fun default messages
        messages = [
            "Hello! Claude Code TTS is now active.",
            "ElevenLabs integration successful!",
            "Ready to provide audio feedback for your coding session.",
            "Voice synthesis online and operational.",
        ]
        text = random.choice(messages)
    
    # Speak the text
    success = speak_with_elevenlabs(text)
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()