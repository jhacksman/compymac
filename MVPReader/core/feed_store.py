"""
Unified Feed Store
Manages storage and retrieval of feed events from all sources
"""

import sqlite3
import json
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from pathlib import Path

from .models import FeedEvent, Source, EventType


class FeedStore:
    """
    Stores and manages feed events using SQLite
    Implements retention policies and deduplication
    """
    
    def __init__(self, db_path: str = None):
        """
        Initialize feed store
        
        Args:
            db_path: Path to SQLite database file
        """
        if db_path is None:
            db_path = Path.home() / ".mvpreader" / "feed_store.db"
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        
        self.db_path = str(db_path)
        self._init_db()
    
    def _init_db(self):
        """Initialize database schema"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id TEXT PRIMARY KEY,
                source TEXT NOT NULL,
                event_type TEXT NOT NULL,
                content TEXT NOT NULL,
                author TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                channel TEXT,
                url TEXT,
                mentions_user INTEGER DEFAULT 0,
                relevance_score REAL DEFAULT 0.0,
                tags TEXT,
                processed INTEGER DEFAULT 0,
                raw_data TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_timestamp 
            ON events(timestamp)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_source 
            ON events(source)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_processed 
            ON events(processed)
        """)
        
        conn.commit()
        conn.close()
    
    def add_event(self, event: FeedEvent) -> bool:
        """
        Add an event to the store
        
        Args:
            event: FeedEvent to add
            
        Returns:
            True if added, False if duplicate
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO events (
                    id, source, event_type, content, author, timestamp,
                    channel, url, mentions_user, relevance_score, tags,
                    processed, raw_data
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                event.id,
                event.source.value,
                event.event_type.value,
                event.content,
                event.author,
                event.timestamp.isoformat(),
                event.channel,
                event.url,
                1 if event.mentions_user else 0,
                event.relevance_score,
                json.dumps(event.tags),
                1 if event.processed else 0,
                json.dumps(event.raw_data)
            ))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
        finally:
            conn.close()
    
    def add_events(self, events: List[FeedEvent]) -> int:
        """
        Add multiple events
        
        Args:
            events: List of FeedEvents
            
        Returns:
            Number of events added
        """
        count = 0
        for event in events:
            if self.add_event(event):
                count += 1
        return count
    
    def get_recent_events(
        self, 
        hours: int = 48, 
        source: Optional[Source] = None,
        processed: Optional[bool] = None
    ) -> List[FeedEvent]:
        """
        Get recent events
        
        Args:
            hours: Number of hours to look back
            source: Filter by source (optional)
            processed: Filter by processed status (optional)
            
        Returns:
            List of FeedEvents
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
        
        query = "SELECT * FROM events WHERE timestamp >= ?"
        params = [cutoff]
        
        if source:
            query += " AND source = ?"
            params.append(source.value)
        
        if processed is not None:
            query += " AND processed = ?"
            params.append(1 if processed else 0)
        
        query += " ORDER BY timestamp DESC"
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        
        return [self._row_to_event(row) for row in rows]
    
    def mark_processed(self, event_ids: List[str]):
        """Mark events as processed"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        placeholders = ','.join('?' * len(event_ids))
        cursor.execute(
            f"UPDATE events SET processed = 1 WHERE id IN ({placeholders})",
            event_ids
        )
        
        conn.commit()
        conn.close()
    
    def cleanup_old_events(self, hours: int = 48):
        """
        Remove events older than specified hours
        
        Args:
            hours: Age threshold in hours
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
        cursor.execute("DELETE FROM events WHERE timestamp < ?", (cutoff,))
        
        conn.commit()
        conn.close()
    
    def get_event_count(self, source: Optional[Source] = None) -> int:
        """Get count of events, optionally filtered by source"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if source:
            cursor.execute(
                "SELECT COUNT(*) FROM events WHERE source = ?",
                (source.value,)
            )
        else:
            cursor.execute("SELECT COUNT(*) FROM events")
        
        count = cursor.fetchone()[0]
        conn.close()
        return count
    
    def _row_to_event(self, row: tuple) -> FeedEvent:
        """Convert database row to FeedEvent"""
        return FeedEvent(
            id=row[0],
            source=Source(row[1]),
            event_type=EventType(row[2]),
            content=row[3],
            author=row[4],
            timestamp=datetime.fromisoformat(row[5]),
            channel=row[6],
            url=row[7],
            mentions_user=bool(row[8]),
            relevance_score=row[9],
            tags=json.loads(row[10]) if row[10] else [],
            processed=bool(row[11]),
            raw_data=json.loads(row[12]) if row[12] else {}
        )
