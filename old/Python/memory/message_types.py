"""Message types for memory system."""
from dataclasses import dataclass, asdict
from typing import Optional, List, Dict, Any
from datetime import datetime

@dataclass
class MemoryMetadata:
    """Metadata for memory entries."""
    timestamp: float
    importance: float = 0.0
    context_ids: List[str] = None
    tags: List[str] = None
    source: Optional[str] = None
    task_id: Optional[str] = None
    
    def __post_init__(self):
        """Initialize default values."""
        if self.context_ids is None:
            self.context_ids = []
        if self.tags is None:
            self.tags = []
            
    def to_dict(self) -> Dict[str, Any]:
        """Convert metadata to dictionary.
        
        Returns:
            Dictionary representation of metadata
        """
        return asdict(self)

@dataclass
class MemoryResponse:
    """Response from memory operations."""
    action: str
    success: bool
    memory_id: Optional[str] = None
    memories: Optional[List[Dict[str, Any]]] = None
    error: Optional[str] = None
    summary: Optional[str] = None
    embedding: Optional[List[float]] = None
