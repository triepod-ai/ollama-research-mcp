#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "openai>=1.0.0",
#   "python-dotenv>=1.0.0",
#   "pygame>=2.5.0",
#   "httpx>=0.25.0",
# ]
# ///

"""
Optimized OpenAI TTS provider with connection pooling and improved error handling.
Part of Phase 1 TTS System Improvements.
"""

import os
import sys
import tempfile
from pathlib import Path
from typing import Optional, Literal

from dotenv import load_dotenv

# Import connection pool manager
try:
    from .connection_pool import get_connection_pool
    CONNECTION_POOL_AVAILABLE = True
except ImportError:
    CONNECTION_POOL_AVAILABLE = False

# Voice options
VoiceType = Literal["alloy", "echo", "fable", "onyx", "nova", "shimmer"]

class TTSError(Exception):
    """Base exception for TTS operations."""
    def __init__(self, message: str, provider: str, error_code: str = None):
        self.message = message
        self.provider = provider
        self.error_code = error_code
        super().__init__(f"[{provider}] {message}")

class TTSProviderError(TTSError):
    """Provider-specific errors."""
    pass

class TTSConfigurationError(TTSError):
    """Configuration-related errors."""
    pass

def validate_openai_config(voice: VoiceType, model: str, speed: float) -> None:
    """
    Validate OpenAI TTS configuration parameters.
    
    Args:
        voice: Voice to validate
        model: Model to validate
        speed: Speed to validate
        
    Raises:
        TTSConfigurationError: If any parameter is invalid
    """
    valid_voices = ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]
    if voice not in valid_voices:
        raise TTSConfigurationError(f"Invalid voice: {voice}", "openai", "INVALID_VOICE")
    
    valid_models = ["tts-1", "tts-1-hd"]
    if model not in valid_models:
        raise TTSConfigurationError(f"Invalid model: {model}", "openai", "INVALID_MODEL")
    
    if not (0.25 <= speed <= 4.0):
        raise TTSConfigurationError(f"Invalid speed: {speed} (must be between 0.25 and 4.0)", "openai", "INVALID_SPEED")

def get_openai_client():
    """Get OpenAI client with connection pooling if available."""
    if CONNECTION_POOL_AVAILABLE:
        pool_manager = get_connection_pool()
        client = pool_manager.get_openai_client()
        if client:
            return client
    
    # Fallback to standard client
    try:
        from openai import OpenAI
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise TTSConfigurationError("OpenAI API key not found in environment", "openai", "MISSING_API_KEY")
        return OpenAI(api_key=api_key)
    except ImportError as e:
        raise TTSProviderError(f"OpenAI library not available: {e}", "openai", "IMPORT_ERROR")

def speak_with_openai_optimized(
    text: str, 
    voice: VoiceType = "nova",
    model: str = "tts-1",
    speed: float = 1.0
) -> bool:
    """
    Convert text to speech using OpenAI's TTS API with optimized connection handling.
    
    Args:
        text: Text to convert to speech
        voice: Voice to use (alloy, echo, fable, onyx, nova, shimmer)
        model: TTS model to use (tts-1 or tts-1-hd)
        speed: Speech speed (0.25 to 4.0)
        
    Returns:
        True if successful, False otherwise
        
    Raises:
        TTSError: For various TTS-related errors
    """
    try:
        # Load environment variables
        env_path = Path.home() / "brainpods" / ".env"
        if env_path.exists():
            load_dotenv(env_path)
        
        # Validate configuration
        validate_openai_config(voice, model, speed)
        
        # Get optimized client
        client = get_openai_client()
        
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
            # Write response content to file
            for chunk in response.iter_bytes():
                tmp_file.write(chunk)
        
        # Play the audio using pygame
        import pygame
        pygame.mixer.init()
        pygame.mixer.music.load(tmp_path)
        pygame.mixer.music.play()
        
        # Wait for playback to complete
        while pygame.mixer.music.get_busy():
            pygame.time.Clock().tick(10)
        
        # Add small buffer to ensure audio fully completes
        pygame.time.wait(100)  # 100ms buffer
        
        # Cleanup
        pygame.mixer.quit()
        os.unlink(tmp_path)
        
        return True
        
    except TTSError:
        # Re-raise TTS errors
        raise
    except Exception as e:
        raise TTSProviderError(f"OpenAI TTS error: {e}", "openai", "EXECUTION_ERROR")

def main():
    """Main entry point for standalone usage."""
    import random
    import argparse
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Optimized OpenAI TTS provider for Claude Code')
    parser.add_argument('text', nargs='*', help='Text to speak')
    parser.add_argument('--voice', choices=["alloy", "echo", "fable", "onyx", "nova", "shimmer"], 
                        help='Voice to use (default: nova)')
    parser.add_argument('--model', choices=["tts-1", "tts-1-hd"], 
                        help='Model to use (default: tts-1)')
    parser.add_argument('--speed', type=float, 
                        help='Speech speed (0.25-4.0, default: 1.0)')
    parser.add_argument('--test', action='store_true', 
                        help='Test OpenAI TTS functionality')
    parser.add_argument('--list-voices', action='store_true',
                        help='List available voices')
    parser.add_argument('--test-voice', 
                        help='Test a specific voice')
    parser.add_argument('--benchmark', action='store_true',
                        help='Run performance benchmark')
    
    args = parser.parse_args()
    
    try:
        # Handle list voices
        if args.list_voices:
            voices = ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]
            print("Available OpenAI voices:")
            for voice in voices:
                print(f"  - {voice}")
            sys.exit(0)
        
        # Handle test voice
        if args.test_voice:
            if args.test_voice not in ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]:
                print(f"Invalid voice: {args.test_voice}", file=sys.stderr)
                sys.exit(1)
            
            test_text = f"Testing optimized OpenAI voice: {args.test_voice}"
            success = speak_with_openai_optimized(test_text, voice=args.test_voice)
            sys.exit(0 if success else 1)
        
        # Handle benchmark
        if args.benchmark:
            import time
            
            print("Running OpenAI TTS performance benchmark...")
            
            benchmark_texts = [
                "Performance test one",
                "Performance test two", 
                "Performance test three"
            ]
            
            total_time = 0
            success_count = 0
            
            for i, text in enumerate(benchmark_texts, 1):
                print(f"Benchmark {i}/3: {text}")
                start_time = time.time()
                
                try:
                    success = speak_with_openai_optimized(text, voice="nova")
                    if success:
                        success_count += 1
                except Exception as e:
                    print(f"Benchmark {i} failed: {e}", file=sys.stderr)
                
                elapsed = time.time() - start_time
                total_time += elapsed
                print(f"  Time: {elapsed:.2f}s")
            
            avg_time = total_time / len(benchmark_texts)
            success_rate = (success_count / len(benchmark_texts)) * 100
            
            print(f"\nBenchmark Results:")
            print(f"  Average time: {avg_time:.2f}s")
            print(f"  Success rate: {success_rate:.1f}%")
            print(f"  Connection pooling: {'Enabled' if CONNECTION_POOL_AVAILABLE else 'Disabled (fallback)'}")
            
            sys.exit(0)
        
        # Get text from command line or use default
        if args.text:
            text = " ".join(args.text)
        elif args.test:
            # Fun test messages
            messages = [
                "Optimized OpenAI text-to-speech is operational!",
                "Connection pooling enabled for better performance.",
                "Claude Code audio feedback optimized.",
                "Phase 1 improvements successfully deployed.",
            ]
            text = random.choice(messages)
        else:
            # Default message
            text = "Optimized OpenAI TTS ready."
        
        # Get parameters from args or environment
        voice = args.voice or os.getenv("OPENAI_TTS_VOICE", "nova")
        model = args.model or os.getenv("OPENAI_TTS_MODEL", "tts-1")
        speed = args.speed or float(os.getenv("OPENAI_TTS_SPEED", "1.0"))
        
        # Speak the text
        success = speak_with_openai_optimized(text, voice=voice, model=model, speed=speed)
        
        # Exit with appropriate code
        sys.exit(0 if success else 1)
        
    except TTSError as e:
        print(f"TTS Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
