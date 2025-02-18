"""Message types for memory operations."""

from dataclasses import dataclass
from typing import Dict, List, Optional
from datetime import datetime


@dataclass
class MemoryMetadata:
    """Metadata for memory entries."""
    timestamp: float
    importance: Optional[float] = None
    context_ids: List[str] = None
    tags: List[str] = None
    source: Optional[str] = None
    
    def __post_init__(self):
        """Initialize default values."""
        if self.context_ids is None:
            self.context_ids = []
        if self.tags is None:
            self.tags = []


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
