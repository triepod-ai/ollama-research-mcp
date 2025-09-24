#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "psutil>=5.9.0",
# ]
# ///

"""
Adaptive Cleanup System for TTS Resources
Manages memory and resource cleanup based on system load and usage patterns.
"""

import time
import gc
import threading
from dataclasses import dataclass
from typing import Dict, List, Optional, Callable
from pathlib import Path

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

@dataclass
class SystemMetrics:
    """Current system resource metrics."""
    memory_percent: float
    cpu_percent: float
    process_memory_mb: float
    available_memory_mb: float

@dataclass
class CleanupStrategy:
    """Cleanup strategy configuration."""
    name: str
    memory_threshold: float  # Memory usage percentage to trigger
    cpu_threshold: float     # CPU usage percentage to consider
    interval_seconds: int    # Cleanup interval
    aggressive: bool         # Whether to use aggressive cleanup

class AdaptiveCleanupManager:
    """Manages adaptive cleanup based on system resources and usage patterns."""
    
    def __init__(self, cache_dir: Optional[str] = None):
        self.cache_dir = Path(cache_dir) if cache_dir else Path("tts_output")
        
        if PSUTIL_AVAILABLE:
            try:
                self.process = psutil.Process()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                self.process = None
        else:
            self.process = None
        
        self.cleanup_callbacks: List[Callable] = []
        self.last_cleanup = time.time()
        self.cleanup_stats = {
            "total_cleanups": 0,
            "memory_cleanups": 0,
            "cache_cleanups": 0,
            "emergency_cleanups": 0
        }
        
        # Cleanup strategies
        self.strategies = {
            "conservative": CleanupStrategy("conservative", 70.0, 60.0, 300, False),
            "balanced": CleanupStrategy("balanced", 60.0, 50.0, 180, False),
            "aggressive": CleanupStrategy("aggressive", 50.0, 40.0, 60, True),
            "emergency": CleanupStrategy("emergency", 85.0, 80.0, 30, True)
        }
        
        self._cleanup_thread = None
        self._stop_cleanup = False
        
    def start_adaptive_cleanup(self):
        """Start adaptive cleanup in background thread."""
        if self._cleanup_thread and self._cleanup_thread.is_alive():
            return
            
        self._stop_cleanup = False
        self._cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        self._cleanup_thread.start()
        
    def stop_adaptive_cleanup(self):
        """Stop adaptive cleanup thread."""
        self._stop_cleanup = True
        if self._cleanup_thread:
            self._cleanup_thread.join(timeout=5.0)
    
    def get_system_metrics(self) -> SystemMetrics:
        """Get current system resource metrics."""
        if not PSUTIL_AVAILABLE or not self.process:
            # Return default values when psutil is not available
            return SystemMetrics(
                memory_percent=50.0,
                cpu_percent=25.0,
                process_memory_mb=100.0,
                available_memory_mb=2048.0
            )
        
        try:
            # Memory metrics
            memory = psutil.virtual_memory()
            process_memory = self.process.memory_info().rss / 1024 / 1024
            
            # CPU metrics
            cpu_percent = psutil.cpu_percent(interval=0.1)
            
            return SystemMetrics(
                memory_percent=memory.percent,
                cpu_percent=cpu_percent,
                process_memory_mb=process_memory,
                available_memory_mb=memory.available / 1024 / 1024
            )
        except (psutil.NoSuchProcess, psutil.AccessDenied, AttributeError):
            return SystemMetrics(50.0, 25.0, 100.0, 2048.0)
    
    def _select_cleanup_strategy(self, metrics: SystemMetrics) -> CleanupStrategy:
        """Select appropriate cleanup strategy based on system metrics."""
        # Emergency cleanup for critical resource usage
        if (metrics.memory_percent > 85 or 
            metrics.cpu_percent > 90 or 
            metrics.process_memory_mb > 500):
            return self.strategies["emergency"]
        
        # Aggressive cleanup for high resource usage
        elif (metrics.memory_percent > 75 or 
              metrics.cpu_percent > 70 or 
              metrics.process_memory_mb > 300):
            return self.strategies["aggressive"]
        
        # Balanced cleanup for moderate usage
        elif (metrics.memory_percent > 60 or 
              metrics.cpu_percent > 50):
            return self.strategies["balanced"]
        
        # Conservative cleanup for low usage
        else:
            return self.strategies["conservative"]
    
    def _cleanup_loop(self):
        """Main cleanup loop running in background."""
        while not self._stop_cleanup:
            try:
                metrics = self.get_system_metrics()
                strategy = self._select_cleanup_strategy(metrics)
                
                current_time = time.time()
                time_since_last = current_time - self.last_cleanup
                
                # Check if cleanup should be performed
                if (time_since_last >= strategy.interval_seconds or
                    metrics.memory_percent >= strategy.memory_threshold or
                    metrics.process_memory_mb > 400):
                    
                    self._perform_cleanup(strategy, metrics)
                
                # Sleep based on current strategy
                time.sleep(min(strategy.interval_seconds, 60))
                
            except Exception:
                time.sleep(60)  # Fallback interval on error
    
    def _perform_cleanup(self, strategy: CleanupStrategy, metrics: SystemMetrics):
        """Perform cleanup based on strategy and current metrics."""
        cleanup_actions = []
        
        try:
            # 1. Cache cleanup
            if self.cache_dir.exists():
                cleaned_cache = self._cleanup_cache(strategy.aggressive)
                if cleaned_cache > 0:
                    cleanup_actions.append(f"cache:{cleaned_cache}")
                    self.cleanup_stats["cache_cleanups"] += 1
            
            # 2. Memory cleanup
            if metrics.memory_percent > strategy.memory_threshold:
                self._cleanup_memory(strategy.aggressive)
                cleanup_actions.append("memory:gc")
                self.cleanup_stats["memory_cleanups"] += 1
            
            # 3. Custom cleanup callbacks
            for callback in self.cleanup_callbacks:
                try:
                    callback(strategy, metrics)
                    cleanup_actions.append("callback")
                except Exception:
                    pass
            
            # Update stats
            self.cleanup_stats["total_cleanups"] += 1
            if strategy.name == "emergency":
                self.cleanup_stats["emergency_cleanups"] += 1
            
            self.last_cleanup = time.time()
                
        except Exception:
            pass
    
    def _cleanup_cache(self, aggressive: bool = False) -> int:
        """Clean up cache files based on age and size."""
        if not self.cache_dir.exists():
            return 0
        
        current_time = time.time()
        files_removed = 0
        
        # Age thresholds
        max_age_hours = 6 if aggressive else 24
        keep_recent_count = 10 if aggressive else 50
        max_age_seconds = max_age_hours * 3600
        
        try:
            # Get all cache files with timestamps
            cache_files = []
            for file_path in self.cache_dir.glob("*.mp3"):
                if file_path.is_file():
                    stat = file_path.stat()
                    cache_files.append((file_path, stat.st_mtime, stat.st_size))
            
            # Sort by modification time (newest first)
            cache_files.sort(key=lambda x: x[1], reverse=True)
            
            # Keep most recent files
            files_to_check = cache_files[keep_recent_count:]
            
            # Remove old files
            for file_path, mtime, size in files_to_check:
                age = current_time - mtime
                if age > max_age_seconds:
                    try:
                        file_path.unlink()
                        files_removed += 1
                    except OSError:
                        pass
                        
        except Exception:
            pass
        
        return files_removed
    
    def _cleanup_memory(self, aggressive: bool = False) -> bool:
        """Perform memory cleanup."""
        # Force garbage collection
        if aggressive:
            # Multiple GC passes for thorough cleanup
            for _ in range(3):
                gc.collect()
        else:
            gc.collect()
        
        return True
    
    def force_cleanup(self, strategy_name: str = "aggressive"):
        """Force immediate cleanup with specified strategy."""
        strategy = self.strategies.get(strategy_name, self.strategies["balanced"])
        metrics = self.get_system_metrics()
        self._perform_cleanup(strategy, metrics)
    
    def get_cleanup_stats(self) -> Dict:
        """Get cleanup statistics and current status."""
        metrics = self.get_system_metrics()
        current_strategy = self._select_cleanup_strategy(metrics)
        
        cache_count = 0
        cache_size_mb = 0
        if self.cache_dir.exists():
            try:
                for file_path in self.cache_dir.glob("*.mp3"):
                    if file_path.is_file():
                        cache_count += 1
                        cache_size_mb += file_path.stat().st_size / 1024 / 1024
            except Exception:
                pass
        
        return {
            "system_metrics": {
                "memory_percent": metrics.memory_percent,
                "cpu_percent": metrics.cpu_percent,
                "process_memory_mb": metrics.process_memory_mb,
                "available_memory_mb": metrics.available_memory_mb
            },
            "current_strategy": current_strategy.name,
            "cache_info": {
                "file_count": cache_count,
                "total_size_mb": cache_size_mb
            },
            "cleanup_stats": self.cleanup_stats.copy(),
            "time_since_last_cleanup": time.time() - self.last_cleanup,
            "psutil_available": PSUTIL_AVAILABLE
        }

# Global adaptive cleanup manager
_cleanup_manager = None

def get_adaptive_cleanup_manager(cache_dir: Optional[str] = None) -> AdaptiveCleanupManager:
    """Get global adaptive cleanup manager."""
    global _cleanup_manager
    if _cleanup_manager is None:
        _cleanup_manager = AdaptiveCleanupManager(cache_dir)
    return _cleanup_manager

if __name__ == "__main__":
    # Demo adaptive cleanup
    print("Adaptive Cleanup System Demo")
    print("=" * 40)
    
    manager = AdaptiveCleanupManager()
    
    # Show current system metrics
    metrics = manager.get_system_metrics()
    print(f"Memory Usage: {metrics.memory_percent:.1f}%")
    print(f"CPU Usage: {metrics.cpu_percent:.1f}%")
    print(f"Process Memory: {metrics.process_memory_mb:.1f}MB")
    
    # Show recommended strategy
    strategy = manager._select_cleanup_strategy(metrics)
    print(f"Recommended Strategy: {strategy.name}")
    print(f"Cleanup Interval: {strategy.interval_seconds}s")
    
    # Show cleanup stats
    stats = manager.get_cleanup_stats()
    print(f"\nCache Files: {stats['cache_info']['file_count']}")
    print(f"Cache Size: {stats['cache_info']['total_size_mb']:.1f}MB")
    print(f"psutil Available: {stats['psutil_available']}")
