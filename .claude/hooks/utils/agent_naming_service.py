#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.8"
# dependencies = [
#     "python-dotenv",
#     "anthropic",
#     "openai",
#     "requests>=2.28.0",
# ]
# ///

import os
import sys
import json
import time
import hashlib
import uuid
import requests
from typing import Dict, Any, Optional, Tuple
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


class AgentNamingService:
    """
    LLM-powered agent naming service for the multi-agent observability system.
    
    Generates memorable, contextually appropriate names for agents and sessions
    using LLM providers with UUID fallback for reliability.
    """
    
    def __init__(self):
        self.server_url = os.getenv('OBSERVABILITY_SERVER_URL', 'http://localhost:4000')
        self.cache_ttl = 86400  # 24 hours cache
        self.max_retries = 2
        self.retry_delay = 1.0  # seconds
        
        # Name generation patterns by agent type
        self.name_patterns = {
            'analyzer': ['Detective', 'Scout', 'Sherlock', 'Watson', 'Inspector', 'Sage'],
            'reviewer': ['Guardian', 'Sentinel', 'Watchdog', 'Auditor', 'Overseer', 'Judge'],
            'debugger': ['Mechanic', 'Doctor', 'Fixer', 'Healer', 'Resolver', 'Phoenix'],
            'tester': ['Validator', 'Examiner', 'Prober', 'Checker', 'Verifier', 'QA-Bot'],
            'builder': ['Architect', 'Craftsman', 'Creator', 'Maker', 'Engineer', 'Constructor'],
            'deployer': ['Captain', 'Navigator', 'Pilot', 'Commander', 'Admiral', 'Launcher'],
            'optimizer': ['Turbo', 'Flash', 'Rocket', 'Bolt', 'Swift', 'Accelerator'],
            'security': ['Shield', 'Fortress', 'Guardian', 'Protector', 'Vault', 'Defender'],
            'writer': ['Scribe', 'Author', 'Narrator', 'Poet', 'Chronicle', 'Documentarian'],
            'generator': ['Factory', 'Forge', 'Workshop', 'Studio', 'Lab', 'Inventor'],
            'data-processor': ['Analyst', 'Calculator', 'Processor', 'Transformer', 'Pipeline', 'Aggregator'],
            'storage': ['Vault', 'Archive', 'Repository', 'Cache', 'Store', 'Keeper'],
            'monitor': ['Watchman', 'Observer', 'Sentinel', 'Tracker', 'Monitor', 'Eye'],
            'api-handler': ['Gateway', 'Bridge', 'Connector', 'Interface', 'Portal', 'Hub'],
            'ui-developer': ['Designer', 'Artist', 'Painter', 'Stylist', 'Beautifier', 'Composer'],
            'generic': ['Helper', 'Assistant', 'Worker', 'Agent', 'Bot', 'Utility']
        }
        
        self.role_prefixes = {
            'analyzer': 'Data',
            'reviewer': 'Code',
            'debugger': 'Bug',
            'tester': 'Test',
            'builder': 'Build',
            'deployer': 'Deploy',
            'optimizer': 'Speed',
            'security': 'Secure',
            'writer': 'Doc',
            'generator': 'Content',
            'data-processor': 'Data',
            'storage': 'Memory',
            'monitor': 'Watch',
            'api-handler': 'API',
            'ui-developer': 'UI',
            'generic': 'Task'
        }

    def _get_cache_key(self, agent_type: str, context: str) -> str:
        """Generate cache key for name lookup."""
        combined = f"{agent_type}:{context}"
        return hashlib.sha256(combined.encode()).hexdigest()[:16]

    def _get_cached_name(self, cache_key: str) -> Optional[str]:
        """Get cached name from server database."""
        try:
            response = requests.get(
                f"{self.server_url}/api/agent-names/{cache_key}",
                timeout=2
            )
            if response.status_code == 200:
                data = response.json()
                if data.get('success') and data.get('data'):
                    return data['data']['name']
        except Exception:
            pass
        return None

    def _cache_name(self, cache_key: str, name: str) -> bool:
        """Cache generated name in server database."""
        try:
            response = requests.post(
                f"{self.server_url}/api/agent-names",
                json={
                    'cache_key': cache_key,
                    'name': name,
                    'ttl': self.cache_ttl
                },
                timeout=2
            )
            return response.status_code == 200
        except Exception:
            return False

    def _generate_fallback_name(self, agent_type: str) -> str:
        """Generate fallback name using predefined patterns."""
        personalities = self.name_patterns.get(agent_type, self.name_patterns['generic'])
        prefix = self.role_prefixes.get(agent_type, 'Agent')
        
        # Use simple deterministic selection based on time
        personality_index = int(time.time()) % len(personalities)
        personality = personalities[personality_index]
        
        # Generate short UUID suffix for uniqueness
        suffix = str(uuid.uuid4())[:8].upper()
        
        return f"{prefix}{personality}-{suffix}"

    def _call_anthropic_api(self, prompt: str) -> Optional[str]:
        """Call Anthropic API for name generation."""
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            return None
        
        try:
            import anthropic
            
            client = anthropic.Anthropic(api_key=api_key)
            
            message = client.messages.create(
                model="claude-3-5-haiku-20241022",  # Fast model
                max_tokens=50,
                temperature=0.8,
                messages=[{"role": "user", "content": prompt}]
            )
            
            return message.content[0].text.strip()
        except Exception:
            return None

    def _call_openai_api(self, prompt: str) -> Optional[str]:
        """Call OpenAI API for name generation."""
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return None
        
        try:
            from openai import OpenAI
            
            client = OpenAI(api_key=api_key)
            
            response = client.chat.completions.create(
                model="gpt-4o-mini",  # Fast, capable model
                messages=[{"role": "user", "content": prompt}],
                max_tokens=50,
                temperature=0.8
            )
            
            return response.choices[0].message.content.strip()
        except Exception:
            return None

    def _generate_with_llm(self, agent_type: str, context: str) -> Optional[str]:
        """Generate agent name using LLM with retry logic."""
        # Create context-aware prompt
        prompt = self._create_naming_prompt(agent_type, context)
        
        for attempt in range(self.max_retries):
            # Try Anthropic first (preferred for creative naming)
            name = self._call_anthropic_api(prompt)
            if name and self._validate_name(name):
                return self._clean_name(name)
            
            # Fallback to OpenAI
            name = self._call_openai_api(prompt)
            if name and self._validate_name(name):
                return self._clean_name(name)
            
            # Wait before retry
            if attempt < self.max_retries - 1:
                time.sleep(self.retry_delay * (attempt + 1))
        
        return None

    def _create_naming_prompt(self, agent_type: str, context: str) -> str:
        """Create context-aware naming prompt for LLM."""
        personality_options = self.name_patterns.get(agent_type, self.name_patterns['generic'])
        role_prefix = self.role_prefixes.get(agent_type, 'Agent')
        
        prompt = f"""Generate a memorable, professional name for an AI coding agent.

Agent Type: {agent_type}
Context: {context}
Role: {role_prefix}

Requirements:
- Format: [Role][Personality]-[Variant] (e.g., "CodeReviewer-Alpha", "DataDetective-Pro", "BuildCrafter-Max")
- Use one of these personalities: {', '.join(personality_options)}
- Keep total length under 20 characters
- Make it distinctive and memorable
- Use professional, tech-friendly language
- Avoid generic terms like "Agent" or "Bot"

Examples:
- CodeGuardian-Pro
- DataScout-Alpha  
- BugHealer-Max
- TestValidator-Prime
- UIArtist-Nova

Generate ONE name only (no quotes, explanations, or formatting):"""

        return prompt

    def _validate_name(self, name: str) -> bool:
        """Validate generated name meets requirements."""
        if not name or len(name) > 25 or len(name) < 5:
            return False
        
        # Check for unwanted characters or patterns
        unwanted = ['agent', 'bot', 'ai', 'assistant', 'system']
        name_lower = name.lower()
        
        if any(unwanted_term in name_lower for unwanted_term in unwanted):
            return False
        
        # Must contain hyphen for proper format
        if '-' not in name:
            return False
        
        # Must be alphanumeric with hyphens only
        allowed_chars = set('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-')
        if not all(c in allowed_chars for c in name):
            return False
        
        return True

    def _clean_name(self, name: str) -> str:
        """Clean and format the generated name."""
        # Remove quotes, extra spaces, and unwanted characters
        name = name.strip().strip('"').strip("'").strip()
        
        # Take only the first line if multiple
        name = name.split('\n')[0].strip()
        
        # Ensure proper capitalization (title case for each part)
        parts = name.split('-')
        cleaned_parts = []
        for part in parts:
            if part:
                cleaned_parts.append(part.strip().title())
        
        return '-'.join(cleaned_parts)

    def generate_agent_name(self, agent_type: str = "generic", context: str = "", 
                          session_id: str = "", force_new: bool = False) -> str:
        """
        Generate or retrieve a memorable name for an agent.
        
        Args:
            agent_type: Type of agent (analyzer, reviewer, debugger, etc.)
            context: Additional context for naming (task description, etc.)
            session_id: Session ID for consistent naming within session
            force_new: Skip cache and generate new name
            
        Returns:
            str: Generated agent name (never None, falls back to UUID)
        """
        # Normalize agent_type
        agent_type = agent_type.lower().strip() or "generic"
        context = context.strip()[:100]  # Limit context length
        
        # Check cache first (unless forced to generate new)
        if not force_new:
            cache_key = self._get_cache_key(agent_type, context)
            cached_name = self._get_cached_name(cache_key)
            if cached_name:
                return cached_name
        
        # Try LLM generation
        llm_name = self._generate_with_llm(agent_type, context)
        if llm_name:
            # Cache successful generation
            if not force_new:
                cache_key = self._get_cache_key(agent_type, context)
                self._cache_name(cache_key, llm_name)
            return llm_name
        
        # Fallback to pattern-based naming
        fallback_name = self._generate_fallback_name(agent_type)
        
        # Cache fallback name too
        if not force_new:
            cache_key = self._get_cache_key(agent_type, context)
            self._cache_name(cache_key, fallback_name)
        
        return fallback_name

    def generate_session_name(self, session_type: str = "main", 
                            agent_count: int = 1, context: str = "") -> str:
        """
        Generate memorable name for a session.
        
        Args:
            session_type: Type of session (main, subagent, wave, etc.)
            agent_count: Number of agents in session
            context: Session context or description
            
        Returns:
            str: Generated session name
        """
        session_patterns = {
            'main': ['Mission', 'Quest', 'Journey', 'Adventure', 'Expedition'],
            'subagent': ['Task', 'Operation', 'Assignment', 'Job', 'Work'],
            'wave': ['Campaign', 'Initiative', 'Drive', 'Push', 'Surge'],
            'continuation': ['Chapter', 'Phase', 'Stage', 'Episode', 'Part']
        }
        
        patterns = session_patterns.get(session_type, session_patterns['main'])
        pattern = patterns[int(time.time()) % len(patterns)]
        
        # Generate unique identifier
        identifier = str(uuid.uuid4())[:8].upper()
        
        return f"{pattern}-{identifier}"


# Convenience functions for direct use
def generate_agent_name(agent_type: str = "generic", context: str = "", 
                      session_id: str = "", force_new: bool = False) -> str:
    """Generate agent name using the naming service."""
    service = AgentNamingService()
    return service.generate_agent_name(agent_type, context, session_id, force_new)


def generate_session_name(session_type: str = "main", 
                        agent_count: int = 1, context: str = "") -> str:
    """Generate session name using the naming service."""
    service = AgentNamingService()
    return service.generate_session_name(session_type, agent_count, context)


def main():
    """Command line interface for testing."""
    if len(sys.argv) < 2:
        print("Usage:")
        print("  agent_naming_service.py agent <type> [context]")
        print("  agent_naming_service.py session <type> [context]") 
        print("  agent_naming_service.py test")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "agent":
        agent_type = sys.argv[2] if len(sys.argv) > 2 else "generic"
        context = sys.argv[3] if len(sys.argv) > 3 else ""
        name = generate_agent_name(agent_type, context)
        print(name)
    
    elif command == "session":
        session_type = sys.argv[2] if len(sys.argv) > 2 else "main"
        context = sys.argv[3] if len(sys.argv) > 3 else ""
        name = generate_session_name(session_type, 1, context)
        print(name)
    
    elif command == "test":
        print("Testing Agent Naming Service...")
        
        # Test different agent types
        test_types = ['analyzer', 'reviewer', 'debugger', 'tester', 'generic']
        for agent_type in test_types:
            name = generate_agent_name(agent_type, f"Testing {agent_type} agent")
            print(f"{agent_type:12} -> {name}")
        
        # Test session naming
        print("\nSession names:")
        for session_type in ['main', 'subagent', 'wave']:
            name = generate_session_name(session_type)
            print(f"{session_type:12} -> {name}")
    
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()