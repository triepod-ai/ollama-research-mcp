#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "openai>=1.0.0",
#   "python-dotenv>=1.0.0",
#   "pygame>=2.5.0",
# ]
# ///

"""
OpenAI TTS provider for Claude Code hooks.
Uses OpenAI's text-to-speech API with multiple voice options.
"""

import os
import sys
import tempfile
from pathlib import Path
from typing import Optional, Literal

from dotenv import load_dotenv

# Voice options
VoiceType = Literal["alloy", "echo", "fable", "onyx", "nova", "shimmer"]

def speak_with_openai(
    text: str, 
    voice: VoiceType = "nova",
    model: str = "tts-1",
    speed: float = 1.0
) -> bool:
    """
    Convert text to speech using OpenAI's TTS API.
    
    Args:
        text: Text to convert to speech
        voice: Voice to use (alloy, echo, fable, onyx, nova, shimmer)
        model: TTS model to use (tts-1 or tts-1-hd)
        speed: Speech speed (0.25 to 4.0)
        
    Returns:
        True if successful, False otherwise
    """
    try:
        from openai import OpenAI
        import pygame
        
        # Load environment variables
        env_path = Path.home() / "brainpods" / ".env"
        if env_path.exists():
            load_dotenv(env_path)
        
        # Get API key
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            print("OpenAI API key not found in environment", file=sys.stderr)
            return False
        
        # Initialize OpenAI client
        client = OpenAI(api_key=api_key)
        
        # Create speech
        response = client.audio.speech.create(
            model=model,
            voice=voice,
            input=text,
            speed=speed
        )
        
        # Save to temporary file and play
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp_file:
            tmp_path = tmp_file.name
            response.stream_to_file(tmp_path)
        
        # Play the audio using pygame
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
        print(f"OpenAI TTS error: {e}", file=sys.stderr)
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
            "OpenAI text-to-speech is operational!",
            "High-quality voice synthesis ready.",
            "Claude Code audio feedback enabled.",
            "Neural voice synthesis active.",
        ]
        text = random.choice(messages)
    
    # Get voice preference from environment or use default
    voice = os.getenv("OPENAI_TTS_VOICE", "nova")
    
    # Speak the text
    success = speak_with_openai(text, voice=voice)
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()