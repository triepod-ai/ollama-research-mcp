#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "httpx>=0.25.0",
#   "python-dotenv>=1.0.0",
# ]
# ///

"""
Connection pooling manager for TTS providers.
Provides reusable HTTP connections to reduce latency and resource usage.
"""

import os
import threading
from functools import lru_cache
from typing import Optional, Dict, Any
from pathlib import Path

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

class ConnectionPoolManager:
    """Manages HTTP connection pools for TTS providers."""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        """Singleton pattern for connection pool manager."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize connection pool manager."""
        if hasattr(self, '_initialized') and self._initialized:
            return
        
        # Load environment variables
        if load_dotenv:
            env_path = Path.home() / "brainpods" / ".env"
            if env_path.exists():
                load_dotenv(env_path)
        
        self._pools: Dict[str, httpx.Client] = {}
        self._initialized = True
    
    def get_openai_client(self) -> Optional[Any]:
        """Get cached OpenAI client with connection pooling."""
        if not HTTPX_AVAILABLE:
            # Fallback to standard OpenAI client without pooling
            try:
                from openai import OpenAI
                api_key = os.getenv("OPENAI_API_KEY")
                if api_key:
                    return OpenAI(api_key=api_key)
            except ImportError:
                pass
            return None
        
        pool_key = "openai"
        
        if pool_key not in self._pools:
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                return None
            
            try:
                from openai import OpenAI
                
                # Create HTTP client with connection pooling
                http_client = httpx.Client(
                    limits=httpx.Limits(
                        max_connections=5,
                        max_keepalive_connections=2
                    ),
                    timeout=30.0
                )
                
                # Create OpenAI client with pooled HTTP client
                client = OpenAI(
                    api_key=api_key,
                    http_client=http_client
                )
                
                self._pools[pool_key] = client
                
            except ImportError:
                return None
        
        return self._pools.get(pool_key)
    
    def get_elevenlabs_client(self) -> Optional[httpx.Client]:
        """Get cached HTTP client for ElevenLabs API with connection pooling."""
        if not HTTPX_AVAILABLE:
            return None
        
        pool_key = "elevenlabs"
        
        if pool_key not in self._pools:
            api_key = os.getenv("ELEVENLABS_API_KEY")
            if not api_key:
                return None
            
            # Create HTTP client with connection pooling
            client = httpx.Client(
                limits=httpx.Limits(
                    max_connections=5,
                    max_keepalive_connections=2
                ),
                timeout=30.0,
                headers={
                    "Accept": "audio/mpeg",
                    "Content-Type": "application/json",
                    "xi-api-key": api_key
                }
            )
            
            self._pools[pool_key] = client
        
        return self._pools.get(pool_key)
    
    def cleanup(self):
        """Cleanup all connection pools."""
        for client in self._pools.values():
            try:
                if hasattr(client, 'close'):
                    client.close()
            except Exception:
                pass  # Ignore cleanup errors
        
        self._pools.clear()
    
    def __del__(self):
        """Cleanup connections on deletion."""
        self.cleanup()

# Global connection pool manager instance
@lru_cache(maxsize=1)
def get_connection_pool() -> ConnectionPoolManager:
    """Get the global connection pool manager instance."""
    return ConnectionPoolManager()

def cleanup_connection_pools():
    """Cleanup all connection pools (for testing/shutdown)."""
    pool_manager = get_connection_pool()
    pool_manager.cleanup()

def main():
    """Main entry point for testing connection pools."""
    import sys
    
    pool_manager = get_connection_pool()
    
    print("Testing connection pools...")
    
    # Test OpenAI client
    openai_client = pool_manager.get_openai_client()
    if openai_client:
        print("✓ OpenAI client with connection pooling available")
    else:
        print("✗ OpenAI client not available (missing API key or httpx)")
    
    # Test ElevenLabs client
    elevenlabs_client = pool_manager.get_elevenlabs_client()
    if elevenlabs_client:
        print("✓ ElevenLabs client with connection pooling available")
    else:
        print("✗ ElevenLabs client not available (missing API key or httpx)")
    
    print(f"HTTPX available: {HTTPX_AVAILABLE}")
    print("Connection pool test complete")

if __name__ == "__main__":
    main()
