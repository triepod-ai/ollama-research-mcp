#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "pyttsx3>=2.90",
# ]
# ///

"""
Offline TTS provider using pyttsx3 for Claude Code hooks.
No API required - works completely offline.
"""

import sys
import random

def speak_with_pyttsx3(text: str) -> bool:
    """
    Convert text to speech using pyttsx3 (offline).
    
    Args:
        text: Text to convert to speech
        
    Returns:
        True if successful, False otherwise
    """
    try:
        import pyttsx3
        
        # Initialize the TTS engine
        engine = pyttsx3.init()
        
        # Configure voice properties
        engine.setProperty('rate', 180)  # Speed of speech
        engine.setProperty('volume', 0.8)  # Volume level (0.0 to 1.0)
        
        # Optional: Try to use a better voice if available
        voices = engine.getProperty('voices')
        if voices:
            # Try to find a preferred voice (usually the second one is better on most systems)
            if len(voices) > 1:
                engine.setProperty('voice', voices[1].id)
        
        # Speak the text
        engine.say(text)
        engine.runAndWait()
        
        return True
        
    except Exception as e:
        print(f"pyttsx3 TTS error: {e}", file=sys.stderr)
        return False

def main():
    """Main entry point for standalone usage."""
    
    # Get text from command line or use default
    if len(sys.argv) > 1:
        text = " ".join(sys.argv[1:])
    else:
        # Fun default messages
        messages = [
            "Offline TTS is working perfectly!",
            "No internet? No problem! Local speech synthesis active.",
            "Claude Code offline voice ready.",
            "Privacy-first TTS enabled.",
        ]
        text = random.choice(messages)
    
    # Speak the text
    success = speak_with_pyttsx3(text)
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()