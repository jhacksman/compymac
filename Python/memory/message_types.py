"""Message types for memory operations."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Union
from datetime import datetime


@dataclass
class MemoryMetadata:
    """Metadata for memory entries."""
    timestamp: float
    importance: Optional[float] = None
    context_ids: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    source: Optional[str] = None
    task_id: Optional[int] = None  # Added for task-based filtering
    
    def __post_init__(self):
        """Initialize default values."""
        if self.context_ids is None:
            self.context_ids = []
        if self.tags is None:
            self.tags = []
            
    def asdict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "timestamp": self.timestamp,
            "importance": self.importance,
            "context_ids": self.context_ids,
            "tags": self.tags,
            "source": self.source,
            "task_id": self.task_id
        }


@dataclass
class MemoryRequest:
    """Request for memory operations."""
    action: str
    content: Optional[str] = None
    metadata: Optional[Dict] = None
    memory_id: Optional[str] = None
    query: Optional[str] = None
    filters: Optional[Dict] = None


@dataclass
class MemoryResponse:
    """Response from memory operations."""
    action: str
    success: bool
    memory_id: Optional[str] = None
    memories: Optional[List[Dict]] = None
    error: Optional[str] = None
    embedding: Optional[List[float]] = None
    summary: Optional[str] = None
