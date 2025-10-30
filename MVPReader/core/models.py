"""
Data models for the feed aggregator
Defines common structures for events from different sources
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any, List
from enum import Enum


class EventType(Enum):
    """Types of events that can be captured"""
    MESSAGE = "message"
    MENTION = "mention"
    REPLY = "reply"
    FOLLOW = "follow"
    FAVORITE = "favorite"
    REPOST = "repost"
    NOTIFICATION = "notification"


class Source(Enum):
    """Supported data sources"""
    SLACK = "slack"
    MASTODON = "mastodon"
    BLUESKY = "bluesky"


@dataclass
class FeedEvent:
    """
    Unified representation of an event from any source
    """
    id: str
    source: Source
    event_type: EventType
    content: str
    author: str
    timestamp: datetime
    raw_data: Dict[str, Any] = field(default_factory=dict)
    
    channel: Optional[str] = None
    url: Optional[str] = None
    mentions_user: bool = False
    
    relevance_score: float = 0.0
    tags: List[str] = field(default_factory=list)
    processed: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        return {
            "id": self.id,
            "source": self.source.value,
            "event_type": self.event_type.value,
            "content": self.content,
            "author": self.author,
            "timestamp": self.timestamp.isoformat(),
            "channel": self.channel,
            "url": self.url,
            "mentions_user": self.mentions_user,
            "relevance_score": self.relevance_score,
            "tags": self.tags,
            "processed": self.processed,
            "raw_data": self.raw_data
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FeedEvent':
        """Create FeedEvent from dictionary"""
        return cls(
            id=data["id"],
            source=Source(data["source"]),
            event_type=EventType(data["event_type"]),
            content=data["content"],
            author=data["author"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            channel=data.get("channel"),
            url=data.get("url"),
            mentions_user=data.get("mentions_user", False),
            relevance_score=data.get("relevance_score", 0.0),
            tags=data.get("tags", []),
            processed=data.get("processed", False),
            raw_data=data.get("raw_data", {})
        )


@dataclass
class AISummary:
    """AI-generated summary of feed events"""
    timestamp: datetime
    highlights: List[str]
    suggestions: List[Dict[str, str]]
    event_count: int
    sources_analyzed: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "timestamp": self.timestamp.isoformat(),
            "highlights": self.highlights,
            "suggestions": self.suggestions,
            "event_count": self.event_count,
            "sources_analyzed": self.sources_analyzed
        }


@dataclass
class Feedback:
    """User feedback on AI suggestions"""
    suggestion_id: str
    vote: int  # 1 for upvote, -1 for downvote
    timestamp: datetime
    comment: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "suggestion_id": self.suggestion_id,
            "vote": self.vote,
            "timestamp": self.timestamp.isoformat(),
            "comment": self.comment
        }
