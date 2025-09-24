#!/usr/bin/env python3
"""
Local Fallback Storage for Claude Code Hooks

Provides offline operation when Redis is unavailable by using local SQLite database
and JSON file storage with automatic sync-back capability.
"""

import os
import json
import sqlite3
import time
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta
import hashlib

class FallbackStorage:
    def __init__(self, storage_dir: Optional[str] = None):
        self.storage_dir = Path(storage_dir or os.path.expanduser("~/.claude/fallback"))
        self.db_path = self.storage_dir / "storage.db"
        self.handoffs_dir = self.storage_dir / "handoffs"
        self.sync_dir = self.storage_dir / "sync"
        
        # Configuration
        self.config = {
            'enabled': os.getenv('CLAUDE_FALLBACK_ENABLED', 'true').lower() == 'true',
            'retention_days': int(os.getenv('CLAUDE_FALLBACK_RETENTION_DAYS', '30')),
            'redis_timeout': int(os.getenv('CLAUDE_REDIS_TIMEOUT', '2')),
            'sync_enabled': os.getenv('CLAUDE_SYNC_ENABLED', 'true').lower() == 'true'
        }
        
        # Initialize storage
        if self.config['enabled']:
            self._initialize_storage()
    
    def _initialize_storage(self):
        """Initialize local storage directories and database"""
        try:
            # Create directories
            self.storage_dir.mkdir(parents=True, exist_ok=True)
            self.handoffs_dir.mkdir(parents=True, exist_ok=True)
            self.sync_dir.mkdir(parents=True, exist_ok=True)
            
            # Initialize database
            self._init_database()
            
        except Exception as e:
            print(f"Warning: Failed to initialize fallback storage: {e}", flush=True)
    
    def _init_database(self):
        """Initialize SQLite database with required tables"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('PRAGMA journal_mode = WAL')
            conn.execute('PRAGMA synchronous = NORMAL')
            
            # Agent executions table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS agent_executions (
                    agent_id TEXT PRIMARY KEY,
                    agent_name TEXT NOT NULL,
                    agent_type TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'active',
                    start_time INTEGER NOT NULL,
                    end_time INTEGER,
                    duration_ms INTEGER,
                    session_id TEXT,
                    task_description TEXT,
                    tools_granted TEXT,
                    token_usage TEXT,
                    performance_metrics TEXT,
                    source_app TEXT,
                    progress INTEGER DEFAULT 0,
                    created_at INTEGER DEFAULT (strftime('%s', 'now')),
                    updated_at INTEGER DEFAULT (strftime('%s', 'now'))
                )
            ''')
            
            # Session handoffs table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS session_handoffs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_name TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    session_id TEXT,
                    handoff_content TEXT NOT NULL,
                    metadata TEXT,
                    created_at INTEGER DEFAULT (strftime('%s', 'now'))
                )
            ''')
            
            # Sync queue table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS sync_queue (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    operation_type TEXT NOT NULL,
                    redis_key TEXT NOT NULL,
                    redis_value TEXT,
                    redis_score REAL,
                    hash_field TEXT,
                    ttl_seconds INTEGER,
                    created_at INTEGER DEFAULT (strftime('%s', 'now')),
                    sync_status TEXT DEFAULT 'pending',
                    sync_attempts INTEGER DEFAULT 0,
                    last_sync_attempt INTEGER
                )
            ''')
            
            # Create indexes
            conn.execute('CREATE INDEX IF NOT EXISTS idx_agent_executions_status ON agent_executions(status)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_agent_executions_session_id ON agent_executions(session_id)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_session_handoffs_project ON session_handoffs(project_name)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_sync_queue_status ON sync_queue(sync_status)')
            
            conn.commit()
    
    def test_redis_connection(self) -> bool:
        """Test if Redis is available"""
        try:
            import redis
            r = redis.Redis(host='localhost', port=6379, db=0, 
                          decode_responses=True, socket_timeout=self.config['redis_timeout'])
            r.ping()
            return True
        except:
            return False
    
    def execute_with_fallback(self, redis_operation, fallback_operation=None):
        """Execute operation with Redis, fall back to local storage if needed"""
        if not self.config['enabled']:
            return redis_operation()
        
        try:
            # Test Redis connection first
            if self.test_redis_connection():
                return redis_operation()
            else:
                if fallback_operation:
                    return fallback_operation()
                else:
                    # Store operation for later sync
                    return None
        except Exception as e:
            print(f"Redis operation failed, using fallback: {e}", flush=True)
            if fallback_operation:
                return fallback_operation()
            return None
    
    # Session Handoff Methods
    def save_session_handoff(self, project_name: str, handoff_content: str, 
                           session_id: Optional[str] = None, metadata: Optional[Dict] = None) -> bool:
        """Save session handoff with fallback support"""
        def redis_operation():
            import redis
            r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            redis_key = f"handoff:project:{project_name}:{timestamp}"
            r.setex(redis_key, 86400 * 30, handoff_content)  # 30 days TTL
            return True
        
        def fallback_operation():
            return self._save_handoff_to_local(project_name, handoff_content, session_id, metadata)
        
        result = self.execute_with_fallback(redis_operation, fallback_operation)
        
        # Always save to local storage for backup
        self._save_handoff_to_local(project_name, handoff_content, session_id, metadata)
        
        # Queue sync operation
        if self.config['sync_enabled']:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            redis_key = f"handoff:project:{project_name}:{timestamp}"
            self._queue_sync_operation('setex', redis_key, handoff_content, ttl_seconds=86400 * 30)
        
        return result is not False
    
    def _save_handoff_to_local(self, project_name: str, handoff_content: str,
                             session_id: Optional[str] = None, metadata: Optional[Dict] = None) -> bool:
        """Save handoff to local storage"""
        try:
            # Save to database
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('''
                    INSERT INTO session_handoffs 
                    (project_name, timestamp, session_id, handoff_content, metadata)
                    VALUES (?, ?, ?, ?, ?)
                ''', (
                    project_name,
                    datetime.now().isoformat(),
                    session_id,
                    handoff_content,
                    json.dumps(metadata) if metadata else None
                ))
                conn.commit()
            
            # Also save to JSON file for easy access
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{project_name}_{timestamp}.json"
            filepath = self.handoffs_dir / filename
            latest_path = self.handoffs_dir / f"latest_{project_name}.json"
            
            handoff_data = {
                'project_name': project_name,
                'timestamp': datetime.now().isoformat(),
                'session_id': session_id,
                'handoff_content': handoff_content,
                'metadata': metadata
            }
            
            with open(filepath, 'w') as f:
                json.dump(handoff_data, f, indent=2)
            
            with open(latest_path, 'w') as f:
                json.dump(handoff_data, f, indent=2)
            
            return True
        except Exception as e:
            print(f"Error saving handoff to local storage: {e}", flush=True)
            return False
    
    def get_latest_session_handoff(self, project_name: str) -> str:
        """Get latest session handoff with fallback support"""
        def redis_operation():
            import redis
            r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
            
            # Search for handoff keys
            pattern = f"handoff:project:{project_name}:*"
            keys = r.keys(pattern)
            
            if keys:
                # Sort by timestamp and get most recent
                keys.sort(reverse=True)
                return r.get(keys[0]) or ""
            return ""
        
        def fallback_operation():
            return self._get_handoff_from_local(project_name)
        
        result = self.execute_with_fallback(redis_operation, fallback_operation)
        return result or ""
    
    def _get_handoff_from_local(self, project_name: str) -> str:
        """Get handoff from local storage"""
        try:
            # Try latest file first
            latest_path = self.handoffs_dir / f"latest_{project_name}.json"
            if latest_path.exists():
                with open(latest_path, 'r') as f:
                    data = json.load(f)
                    return data.get('handoff_content', '')
            
            # Fall back to database
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute('''
                    SELECT handoff_content FROM session_handoffs 
                    WHERE project_name = ? 
                    ORDER BY created_at DESC 
                    LIMIT 1
                ''', (project_name,))
                
                row = cursor.fetchone()
                return row[0] if row else ""
                
        except Exception as e:
            print(f"Error getting handoff from local storage: {e}", flush=True)
            return ""
    
    # Agent Execution Methods
    def store_agent_execution(self, agent_id: str, agent_data: Dict) -> bool:
        """Store agent execution with fallback support"""
        def redis_operation():
            import redis
            r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
            
            # Store in Redis
            start_data = {
                'agent_id': agent_id,
                'agent_name': agent_data.get('agent_name', 'unknown'),
                'start_time': datetime.now().isoformat(),
                'task_description': agent_data.get('task_description', ''),
                'tools_granted': agent_data.get('tools_granted', []),
                'context_size': agent_data.get('context_size', 0)
            }
            
            r.setex(f"agent:active:{agent_id}", 300, json.dumps(start_data))
            r.sadd("agents:active", agent_id)
            r.zadd("agents:timeline", {agent_id: time.time()})
            return True
        
        def fallback_operation():
            return self._store_agent_to_local(agent_id, agent_data)
        
        result = self.execute_with_fallback(redis_operation, fallback_operation)
        
        # Always store to local storage
        self._store_agent_to_local(agent_id, agent_data)
        
        # Queue sync operations
        if self.config['sync_enabled']:
            start_data = {
                'agent_id': agent_id,
                'agent_name': agent_data.get('agent_name', 'unknown'),
                'start_time': datetime.now().isoformat(),
                'task_description': agent_data.get('task_description', ''),
                'tools_granted': agent_data.get('tools_granted', []),
                'context_size': agent_data.get('context_size', 0)
            }
            
            self._queue_sync_operation('setex', f"agent:active:{agent_id}", 
                                     json.dumps(start_data), ttl_seconds=300)
            self._queue_sync_operation('sadd', "agents:active", agent_id)
            self._queue_sync_operation('zadd', "agents:timeline", agent_id, redis_score=time.time())
        
        return result is not False
    
    def _store_agent_to_local(self, agent_id: str, agent_data: Dict) -> bool:
        """Store agent execution to local database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('''
                    INSERT OR REPLACE INTO agent_executions 
                    (agent_id, agent_name, agent_type, status, start_time, session_id, 
                     task_description, tools_granted, source_app)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    agent_id,
                    agent_data.get('agent_name', 'unknown'),
                    agent_data.get('agent_type', 'generic'),
                    'active',
                    int(time.time() * 1000),  # milliseconds
                    agent_data.get('session_id', ''),
                    agent_data.get('task_description', ''),
                    json.dumps(agent_data.get('tools_granted', [])),
                    agent_data.get('source_app', '')
                ))
                conn.commit()
            return True
        except Exception as e:
            print(f"Error storing agent to local storage: {e}", flush=True)
            return False
    
    def update_agent_execution(self, agent_id: str, updates: Dict) -> bool:
        """Update agent execution with fallback support"""
        def redis_operation():
            import redis
            r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
            
            # Remove from active agents if completed
            if updates.get('status') in ['complete', 'failed']:
                r.srem('agents:active', agent_id)
                r.delete(f"agent:active:{agent_id}")
            
            return True
        
        def fallback_operation():
            return self._update_agent_local(agent_id, updates)
        
        result = self.execute_with_fallback(redis_operation, fallback_operation)
        
        # Always update local storage
        self._update_agent_local(agent_id, updates)
        
        # Queue sync operations
        if self.config['sync_enabled'] and updates.get('status') in ['complete', 'failed']:
            self._queue_sync_operation('srem', 'agents:active', agent_id)
            self._queue_sync_operation('del', f"agent:active:{agent_id}")
        
        return result is not False
    
    def _update_agent_local(self, agent_id: str, updates: Dict) -> bool:
        """Update agent execution in local database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Build dynamic update query
                set_clauses = []
                values = []
                
                for field, value in updates.items():
                    if field in ['status', 'end_time', 'duration_ms', 'token_usage', 'performance_metrics', 'progress']:
                        set_clauses.append(f"{field} = ?")
                        if field in ['token_usage', 'performance_metrics']:
                            values.append(json.dumps(value) if value else None)
                        else:
                            values.append(value)
                
                if set_clauses:
                    query = f"UPDATE agent_executions SET {', '.join(set_clauses)}, updated_at = strftime('%s', 'now') WHERE agent_id = ?"
                    values.append(agent_id)
                    conn.execute(query, values)
                    conn.commit()
                
            return True
        except Exception as e:
            print(f"Error updating agent in local storage: {e}", flush=True)
            return False
    
    # Sync Queue Methods
    def _queue_sync_operation(self, operation_type: str, redis_key: str, redis_value: str = None,
                            redis_score: float = None, hash_field: str = None, ttl_seconds: int = None):
        """Queue operation for later sync to Redis"""
        if not self.config['sync_enabled']:
            return
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('''
                    INSERT INTO sync_queue 
                    (operation_type, redis_key, redis_value, redis_score, hash_field, ttl_seconds)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (operation_type, redis_key, redis_value, redis_score, hash_field, ttl_seconds))
                conn.commit()
        except Exception as e:
            print(f"Error queuing sync operation: {e}", flush=True)
    
    def get_pending_sync_operations(self, limit: int = 100) -> List[Dict]:
        """Get pending sync operations"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute('''
                    SELECT * FROM sync_queue 
                    WHERE sync_status = 'pending' AND sync_attempts < 3
                    ORDER BY created_at 
                    LIMIT ?
                ''', (limit,))
                
                columns = [description[0] for description in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]
        except Exception as e:
            print(f"Error getting pending sync operations: {e}", flush=True)
            return []
    
    # Utility Methods
    def cleanup_old_data(self):
        """Clean up old data based on retention policy"""
        if not self.config['enabled']:
            return
        
        try:
            cutoff_time = int((datetime.now() - timedelta(days=self.config['retention_days'])).timestamp())
            
            with sqlite3.connect(self.db_path) as conn:
                # Clean up old agent executions
                conn.execute('DELETE FROM agent_executions WHERE created_at < ?', (cutoff_time,))
                
                # Clean up old handoffs
                conn.execute('DELETE FROM session_handoffs WHERE created_at < ?', (cutoff_time,))
                
                # Clean up synced operations older than 1 day
                day_ago = int((datetime.now() - timedelta(days=1)).timestamp())
                conn.execute('DELETE FROM sync_queue WHERE sync_status = "synced" AND created_at < ?', (day_ago,))
                
                conn.commit()
            
            # Clean up old handoff files
            if self.handoffs_dir.exists():
                cutoff_time_dt = datetime.now() - timedelta(days=self.config['retention_days'])
                for file_path in self.handoffs_dir.iterdir():
                    if file_path.is_file() and not file_path.name.startswith('latest_'):
                        if datetime.fromtimestamp(file_path.stat().st_mtime) < cutoff_time_dt:
                            try:
                                file_path.unlink()
                            except:
                                pass  # Ignore file deletion errors
                                
        except Exception as e:
            print(f"Error during cleanup: {e}", flush=True)
    
    def get_storage_stats(self) -> Dict:
        """Get storage statistics"""
        stats = {
            'enabled': self.config['enabled'],
            'redis_available': False,
            'storage_dir': str(self.storage_dir),
            'total_size_mb': 0,
            'record_counts': {},
            'pending_sync_operations': 0
        }
        
        if not self.config['enabled']:
            return stats
        
        try:
            # Test Redis connection
            stats['redis_available'] = self.test_redis_connection()
            
            # Get database size
            if self.db_path.exists():
                stats['total_size_mb'] = round(self.db_path.stat().st_size / (1024 * 1024), 2)
            
            # Get record counts
            with sqlite3.connect(self.db_path) as conn:
                for table in ['agent_executions', 'session_handoffs', 'sync_queue']:
                    cursor = conn.execute(f'SELECT COUNT(*) FROM {table}')
                    stats['record_counts'][table] = cursor.fetchone()[0]
                
                # Get pending sync operations
                cursor = conn.execute('SELECT COUNT(*) FROM sync_queue WHERE sync_status = "pending"')
                stats['pending_sync_operations'] = cursor.fetchone()[0]
                
            # Add handoffs directory size
            if self.handoffs_dir.exists():
                total_size = sum(f.stat().st_size for f in self.handoffs_dir.rglob('*') if f.is_file())
                stats['total_size_mb'] += round(total_size / (1024 * 1024), 2)
                
        except Exception as e:
            print(f"Error getting storage stats: {e}", flush=True)
        
        return stats
    
    def is_enabled(self) -> bool:
        """Check if fallback storage is enabled"""
        return self.config['enabled']


# Global instance
_fallback_storage = None

def get_fallback_storage() -> FallbackStorage:
    """Get global fallback storage instance"""
    global _fallback_storage
    if _fallback_storage is None:
        _fallback_storage = FallbackStorage()
    return _fallback_storage