#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "python-dotenv>=1.0.0",
# ]
# ///

"""
Phase 3 TTS Transcript Processor
Intelligent text processing for optimal speech synthesis.

Features:
- Code block handling and summarization
- Technical term pronunciation optimization
- Length reduction while preserving meaning
- Context-aware processing based on hook type and tool
"""

import re
import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set
from dotenv import load_dotenv

# Load environment variables
env_path = Path.home() / "brainpods" / ".env"
if env_path.exists():
    load_dotenv(env_path)

class ProcessingLevel(Enum):
    """Processing intensity levels."""
    MINIMAL = 1     # Basic cleanup only
    STANDARD = 2    # Normal processing
    AGGRESSIVE = 3  # Maximum compression
    SMART = 4       # Context-aware processing

class MessageContext(Enum):
    """Context types for processing decisions."""
    ERROR = "error"
    SUCCESS = "success"  
    WARNING = "warning"
    INFORMATION = "information"
    COMPLETION = "completion"
    PERMISSION = "permission"

@dataclass
class ProcessingMetrics:
    """Metrics for transcript processing performance."""
    original_length: int
    processed_length: int
    reduction_ratio: float
    processing_time_ms: float
    confidence: float
    code_blocks_found: int
    technical_terms_converted: int

@dataclass
class ProcessedText:
    """Result of transcript processing."""
    original: str
    processed: str
    metrics: ProcessingMetrics
    processing_level: ProcessingLevel
    context: Optional[MessageContext] = None
    
    def __post_init__(self):
        if self.metrics.reduction_ratio == 0 and self.original and self.processed:
            self.metrics.reduction_ratio = len(self.processed) / len(self.original)

class TranscriptProcessor:
    """Intelligent transcript processor for TTS optimization."""
    
    def __init__(self):
        """Initialize the transcript processor."""
        self.max_speech_length = int(os.getenv("TTS_MAX_MESSAGE_LENGTH", "200"))
        self.target_reduction = float(os.getenv("TTS_TARGET_REDUCTION", "0.6"))
        
        # Load processing dictionaries
        self.technical_terms = self._load_technical_terms()
        self.code_patterns = self._compile_code_patterns()
        self.prosody_markers = self._load_prosody_markers()
        self.common_abbreviations = self._load_abbreviations()
        
        # Processing statistics
        self.processing_stats = {
            "total_processed": 0,
            "average_reduction": 0.0,
            "code_blocks_processed": 0,
            "terms_converted": 0
        }
    
    def _load_technical_terms(self) -> Dict[str, str]:
        """Load technical terms pronunciation dictionary."""
        return {
            # Programming languages
            "javascript": "JavaScript",
            "js": "JavaScript", 
            "typescript": "TypeScript",
            "ts": "TypeScript",
            "py": "Python",
            "cpp": "C plus plus",
            "c++": "C plus plus",
            
            # File extensions
            ".py": "Python file",
            ".js": "JavaScript file", 
            ".ts": "TypeScript file",
            ".tsx": "TypeScript React file",
            ".jsx": "React file",
            ".json": "JSON file",
            ".md": "Markdown file",
            ".yml": "YAML file",
            ".yaml": "YAML file",
            
            # Common tools
            "npm": "N P M",
            "pip": "pip",
            "git": "git",
            "docker": "Docker",
            "kubectl": "kube control",
            "ssh": "S S H",
            "http": "H T T P",
            "https": "H T T P S",
            "api": "A P I",
            "rest": "REST",
            "json": "JSON",
            "xml": "X M L",
            "sql": "S Q L",
            
            # Programming concepts
            "async": "asynchronous",
            "await": "await",
            "func": "function",
            "var": "variable",
            "const": "constant",
            "let": "let",
            "if": "if",
            "else": "else",
            "for": "for loop",
            "while": "while loop",
            "try": "try block",
            "catch": "catch block",
            "finally": "finally block",
            
            # File operations
            "mkdir": "make directory",
            "rm": "remove",
            "cp": "copy",
            "mv": "move",
            "ls": "list",
            "cd": "change directory",
            "pwd": "print working directory",
            "chmod": "change mode",
            "chown": "change owner",
            
            # Status codes
            "200": "OK",
            "404": "not found", 
            "500": "server error",
            "401": "unauthorized",
            "403": "forbidden",
            
            # Units and measurements
            "kb": "kilobytes",
            "mb": "megabytes", 
            "gb": "gigabytes",
            "ms": "milliseconds",
            "sec": "seconds",
            "min": "minutes",
        }
    
    def _compile_code_patterns(self) -> Dict[str, re.Pattern]:
        """Compile regex patterns for code detection."""
        return {
            "code_blocks": re.compile(r'```[\w]*\n(.*?)\n```', re.DOTALL),
            "inline_code": re.compile(r'`([^`]+)`'),
            "file_paths": re.compile(r'[/\\]?[a-zA-Z0-9_.-]+[/\\][a-zA-Z0-9_.-]+(?:[/\\][a-zA-Z0-9_.-]+)*'),
            "urls": re.compile(r'https?://[^\s]+'),
            "version_numbers": re.compile(r'v?\d+\.\d+(?:\.\d+)?'),
            "stack_traces": re.compile(r'^\s*at\s+.*\(.*:\d+:\d+\)', re.MULTILINE),
            "log_timestamps": re.compile(r'\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}:\d{2}'),
        }
    
    def _load_prosody_markers(self) -> Dict[str, str]:
        """Load prosody enhancement markers."""
        return {
            "error": "[pitch=+20%][rate=-10%]",
            "warning": "[pitch=+10%]",
            "success": "[pitch=-5%][rate=+5%]", 
            "completion": "[pitch=-10%]",
            "question": "[pitch=+15%]",
            "emphasis": "[pitch=+10%][volume=+10%]"
        }
    
    def _load_abbreviations(self) -> Dict[str, str]:
        """Load common abbreviations for speech."""
        return {
            "etc": "etcetera",
            "e.g.": "for example",
            "i.e.": "that is",
            "vs": "versus",
            "w/": "with",
            "w/o": "without",
            "info": "information",
            "config": "configuration",
            "admin": "administrator",
            "auth": "authentication",
            "params": "parameters",
            "args": "arguments",
            "opts": "options",
            "req": "request",
            "resp": "response",
            "src": "source",
            "dest": "destination",
        }
    
    def process_for_speech(self, text: str, context: Optional[Dict] = None, level: ProcessingLevel = ProcessingLevel.SMART) -> ProcessedText:
        """
        Process text for optimal TTS synthesis.
        
        Args:
            text: Original text to process
            context: Optional context information (hook_type, tool_name, etc.)
            level: Processing intensity level
            
        Returns:
            ProcessedText with optimized content and metrics
        """
        start_time = datetime.now()
        
        if not text or not text.strip():
            return ProcessedText(
                original=text,
                processed=text,
                metrics=ProcessingMetrics(0, 0, 1.0, 0, 1.0, 0, 0),
                processing_level=level
            )
        
        # Determine message context
        message_context = self._determine_context(text, context)
        
        # Stage 1: Code block handling
        processed, code_blocks_found = self._handle_code_blocks(text, level)
        
        # Stage 2: Technical term conversion
        processed, terms_converted = self._convert_technical_terms(processed, level)
        
        # Stage 3: Length optimization
        processed = self._optimize_length(processed, message_context, level)
        
        # Stage 4: Prosody enhancement
        processed = self._add_prosody_markers(processed, message_context)
        
        # Stage 5: Final cleanup
        processed = self._final_cleanup(processed)
        
        # Calculate metrics
        end_time = datetime.now()
        processing_time = (end_time - start_time).total_seconds() * 1000
        
        metrics = ProcessingMetrics(
            original_length=len(text),
            processed_length=len(processed),
            reduction_ratio=len(processed) / len(text) if text else 1.0,
            processing_time_ms=processing_time,
            confidence=self._calculate_confidence(text, processed, level),
            code_blocks_found=code_blocks_found,
            technical_terms_converted=terms_converted
        )
        
        # Update statistics
        self._update_stats(metrics)
        
        return ProcessedText(
            original=text,
            processed=processed,
            metrics=metrics,
            processing_level=level,
            context=message_context
        )
    
    def _determine_context(self, text: str, context: Optional[Dict]) -> Optional[MessageContext]:
        """Determine message context from text and metadata."""
        text_lower = text.lower()
        
        # Check for error indicators
        error_indicators = ["error", "failed", "exception", "traceback", "crash"]
        if any(indicator in text_lower for indicator in error_indicators):
            return MessageContext.ERROR
        
        # Check for success indicators
        success_indicators = ["success", "completed", "done", "finished", "ready"]
        if any(indicator in text_lower for indicator in success_indicators):
            return MessageContext.SUCCESS
        
        # Check for warning indicators
        warning_indicators = ["warning", "caution", "deprecated", "obsolete"]
        if any(indicator in text_lower for indicator in warning_indicators):
            return MessageContext.WARNING
        
        # Check for permission indicators
        permission_indicators = ["permission", "access", "authorize", "allow", "deny"]
        if any(indicator in text_lower for indicator in permission_indicators):
            return MessageContext.PERMISSION
        
        # Check for completion indicators
        completion_indicators = ["complete", "finish", "end", "terminate"]
        if any(indicator in text_lower for indicator in completion_indicators):
            return MessageContext.COMPLETION
        
        return MessageContext.INFORMATION
    
    def _handle_code_blocks(self, text: str, level: ProcessingLevel) -> Tuple[str, int]:
        """Handle code blocks intelligently."""
        if level == ProcessingLevel.MINIMAL:
            return text, 0
        
        code_blocks_found = 0
        processed = text
        
        # Handle fenced code blocks (```)
        def replace_code_block(match):
            nonlocal code_blocks_found
            code_blocks_found += 1
            code_content = match.group(1).strip()
            
            if level == ProcessingLevel.AGGRESSIVE:
                return " Code block present. "
            elif level in [ProcessingLevel.STANDARD, ProcessingLevel.SMART]:
                # Analyze code content for intelligent summarization
                lines = code_content.split('\n')
                if len(lines) <= 3:
                    # Short code, keep simplified version
                    simple_code = code_content.replace('\n', ', ')
                    return f" Code: {simple_code} "
                else:
                    # Long code, summarize
                    return f" {len(lines)}-line code block "
        
        processed = self.code_patterns["code_blocks"].sub(replace_code_block, processed)
        
        # Handle inline code
        def replace_inline_code(match):
            code_content = match.group(1)
            if len(code_content) <= 15:
                # Short inline code, convert technical terms
                converted = self._convert_single_technical_term(code_content)
                return f" {converted} "
            else:
                # Long inline code, summarize
                return " code snippet "
        
        processed = self.code_patterns["inline_code"].sub(replace_inline_code, processed)
        
        # Handle file paths
        def replace_file_path(match):
            path = match.group(0)
            if level == ProcessingLevel.AGGRESSIVE:
                return "file path"
            else:
                # Extract just the filename for speech
                filename = Path(path).name
                return self._convert_single_technical_term(filename)
        
        processed = self.code_patterns["file_paths"].sub(replace_file_path, processed)
        
        # Handle URLs
        def replace_url(match):
            if level == ProcessingLevel.AGGRESSIVE:
                return "URL"
            else:
                return "web link"
        
        processed = self.code_patterns["urls"].sub(replace_url, processed)
        
        return processed, code_blocks_found
    
    def _convert_technical_terms(self, text: str, level: ProcessingLevel) -> Tuple[str, int]:
        """Convert technical terms to speech-friendly versions."""
        if level == ProcessingLevel.MINIMAL:
            return text, 0
        
        terms_converted = 0
        processed = text
        
        # Sort by length (longest first) to avoid partial replacements
        sorted_terms = sorted(self.technical_terms.items(), key=lambda x: len(x[0]), reverse=True)
        
        for term, replacement in sorted_terms:
            # Use word boundaries to avoid partial matches
            pattern = r'\b' + re.escape(term) + r'\b'
            if re.search(pattern, processed, re.IGNORECASE):
                processed = re.sub(pattern, replacement, processed, flags=re.IGNORECASE)
                terms_converted += 1
        
        # Convert abbreviations
        for abbrev, expansion in self.common_abbreviations.items():
            pattern = r'\b' + re.escape(abbrev) + r'\b'
            if re.search(pattern, processed, re.IGNORECASE):
                processed = re.sub(pattern, expansion, processed, flags=re.IGNORECASE)
        
        return processed, terms_converted
    
    def _convert_single_technical_term(self, term: str) -> str:
        """Convert a single technical term."""
        term_lower = term.lower()
        return self.technical_terms.get(term_lower, term)
    
    def _optimize_length(self, text: str, context: Optional[MessageContext], level: ProcessingLevel) -> str:
        """Optimize text length for speech."""
        if level == ProcessingLevel.MINIMAL or len(text) <= self.max_speech_length:
            return text
        
        processed = text
        
        # Remove redundant whitespace
        processed = re.sub(r'\s+', ' ', processed).strip()
        
        # Remove stack traces and log timestamps for aggressive processing
        if level == ProcessingLevel.AGGRESSIVE:
            processed = self.code_patterns["stack_traces"].sub('', processed)
            processed = self.code_patterns["log_timestamps"].sub('', processed)
        
        # Context-specific optimizations
        if context == MessageContext.ERROR and level in [ProcessingLevel.STANDARD, ProcessingLevel.SMART]:
            # For errors, keep the error message but summarize details
            lines = processed.split('\n')
            if len(lines) > 3:
                processed = lines[0] + f" (and {len(lines)-1} additional details)"
        
        elif context == MessageContext.SUCCESS and len(processed) > self.max_speech_length:
            # For success messages, focus on the outcome
            if "completed" in processed.lower() or "success" in processed.lower():
                processed = "Operation completed successfully"
        
        # Final length check - truncate if still too long
        if len(processed) > self.max_speech_length:
            truncated = processed[:self.max_speech_length-10]
            # Try to break at word boundary
            last_space = truncated.rfind(' ')
            if last_space > self.max_speech_length * 0.8:  # Don't break too early
                processed = truncated[:last_space] + "..."
            else:
                processed = truncated + "..."
        
        return processed
    
    def _add_prosody_markers(self, text: str, context: Optional[MessageContext]) -> str:
        """Add prosody markers for better speech synthesis."""
        if not context:
            return text
        
        # Get prosody marker for context
        marker = ""
        if context == MessageContext.ERROR:
            marker = self.prosody_markers["error"]
        elif context == MessageContext.WARNING:
            marker = self.prosody_markers["warning"] 
        elif context == MessageContext.SUCCESS:
            marker = self.prosody_markers["success"]
        elif context == MessageContext.COMPLETION:
            marker = self.prosody_markers["completion"]
        
        if marker:
            return f"{marker}{text}"
        
        return text
    
    def _final_cleanup(self, text: str) -> str:
        """Final cleanup of processed text."""
        # Remove multiple spaces
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Remove empty parentheses
        text = re.sub(r'\(\s*\)', '', text)
        
        # Clean up punctuation
        text = re.sub(r'[,\s]*\.{2,}', '...', text)  # Normalize ellipses
        text = re.sub(r'\s+([.,!?;:])', r'\1', text)  # Remove space before punctuation
        
        return text
    
    def _calculate_confidence(self, original: str, processed: str, level: ProcessingLevel) -> float:
        """Calculate confidence score for processing quality."""
        if not original:
            return 1.0
        
        base_confidence = 0.8  # Base confidence
        
        # Adjust based on processing level
        level_adjustments = {
            ProcessingLevel.MINIMAL: 0.1,
            ProcessingLevel.STANDARD: 0.0,
            ProcessingLevel.AGGRESSIVE: -0.1,
            ProcessingLevel.SMART: 0.1
        }
        
        base_confidence += level_adjustments.get(level, 0)
        
        # Adjust based on length reduction
        reduction_ratio = len(processed) / len(original)
        if 0.4 <= reduction_ratio <= 0.8:  # Optimal reduction
            base_confidence += 0.1
        elif reduction_ratio < 0.3:  # Too aggressive
            base_confidence -= 0.2
        elif reduction_ratio > 0.9:  # Minimal reduction
            base_confidence -= 0.1
        
        return max(0.0, min(1.0, base_confidence))
    
    def _update_stats(self, metrics: ProcessingMetrics):
        """Update processing statistics."""
        self.processing_stats["total_processed"] += 1
        
        # Update average reduction (running average)
        total = self.processing_stats["total_processed"]
        current_avg = self.processing_stats["average_reduction"]
        new_avg = ((current_avg * (total - 1)) + metrics.reduction_ratio) / total
        self.processing_stats["average_reduction"] = new_avg
        
        self.processing_stats["code_blocks_processed"] += metrics.code_blocks_found
        self.processing_stats["terms_converted"] += metrics.technical_terms_converted
    
    def get_statistics(self) -> Dict:
        """Get processing statistics."""
        return self.processing_stats.copy()
    
    def reset_statistics(self):
        """Reset processing statistics."""
        self.processing_stats = {
            "total_processed": 0,
            "average_reduction": 0.0,
            "code_blocks_processed": 0,
            "terms_converted": 0
        }

# Convenience functions for easy integration
def process_message(text: str, context: Optional[Dict] = None, level: ProcessingLevel = ProcessingLevel.SMART) -> str:
    """
    Process a message for TTS synthesis.
    
    Args:
        text: Original message text
        context: Optional context (hook_type, tool_name, etc.)
        level: Processing level (MINIMAL, STANDARD, AGGRESSIVE, SMART)
        
    Returns:
        Processed text optimized for speech
    """
    processor = TranscriptProcessor()
    result = processor.process_for_speech(text, context, level)
    return result.processed

def process_message_with_metrics(text: str, context: Optional[Dict] = None, level: ProcessingLevel = ProcessingLevel.SMART) -> ProcessedText:
    """
    Process a message for TTS synthesis with detailed metrics.
    
    Args:
        text: Original message text
        context: Optional context (hook_type, tool_name, etc.)
        level: Processing level
        
    Returns:
        ProcessedText with complete processing information
    """
    processor = TranscriptProcessor()
    return processor.process_for_speech(text, context, level)

def main():
    """Main entry point for testing."""
    import sys
    
    # Test messages
    test_messages = [
        "Error: File `/home/user/project/src/main.py` not found at line 42",
        "```python\ndef hello_world():\n    print('Hello, World!')\n    return True\n```",
        "Successfully deployed app to https://myapp.example.com with 0 errors",
        "Warning: The npm package `left-pad@1.2.3` is deprecated", 
        "Executing `git commit -m 'fix: resolve async/await issue in api.js'`"
    ]
    
    if len(sys.argv) > 1:
        # Process command line argument
        text = " ".join(sys.argv[1:])
        result = process_message_with_metrics(text)
        print(f"Original: {result.original}")
        print(f"Processed: {result.processed}")
        print(f"Reduction: {result.metrics.reduction_ratio:.2%}")
        print(f"Confidence: {result.metrics.confidence:.2f}")
        print(f"Processing time: {result.metrics.processing_time_ms:.1f}ms")
    else:
        # Run test suite
        processor = TranscriptProcessor()
        
        print("🧪 Transcript Processor Test Suite")
        print("=" * 50)
        
        for i, message in enumerate(test_messages, 1):
            print(f"\n📝 Test {i}:")
            print(f"Original: {message}")
            
            result = processor.process_for_speech(message)
            print(f"Processed: {result.processed}")
            print(f"Reduction: {result.metrics.reduction_ratio:.2%}")
            print(f"Confidence: {result.metrics.confidence:.2f}")
            print(f"Code blocks: {result.metrics.code_blocks_found}")
            print(f"Terms converted: {result.metrics.technical_terms_converted}")
        
        print(f"\n📊 Overall Statistics:")
        stats = processor.get_statistics()
        for key, value in stats.items():
            if isinstance(value, float):
                print(f"{key}: {value:.3f}")
            else:
                print(f"{key}: {value}")

if __name__ == "__main__":
    main()