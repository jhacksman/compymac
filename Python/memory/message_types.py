"""Message types for memory protocol layer.

This module defines the data structures and validation for memory-related operations.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class MemoryMetadata:
    """Metadata for memory entries."""
    timestamp: float
    importance: Optional[float] = None
    context_ids: List[str] = None
    tags: List[str] = None
    source: str = None
    task_id: Optional[str] = None

@dataclass
class MemoryRequest:
    """Base class for memory-related requests."""
    action: str
    metadata: MemoryMetadata
    content: Optional[str] = None
    memory_id: Optional[str] = None
    context_id: Optional[str] = None
    time_range: Optional[float] = None
    limit: Optional[int] = None

@dataclass
class MemoryResponse:
    """Base class for memory-related responses."""
    action: str
    success: bool
    memory_id: Optional[str] = None
    content: Optional[str] = None
    error: Optional[str] = None
    metadata: Optional[MemoryMetadata] = None
    memories: Optional[List[Dict]] = None

class MemoryValidationError(Exception):
    """Raised when memory request validation fails."""
    pass

def validate_memory_request(request: MemoryRequest) -> None:
    """Validate a memory request.
    
    Args:
        request: The request to validate
        
    Raises:
        MemoryValidationError: If validation fails
    """
    if not request.action:
        raise MemoryValidationError("Action is required")
        
    if not request.metadata:
        raise MemoryValidationError("Metadata is required")
        
    if not request.metadata.timestamp:
        raise MemoryValidationError("Timestamp is required in metadata")
        
    if request.action == "store_memory" and not request.content:
        raise MemoryValidationError("Content is required for store_memory action")
        
    if request.action == "update_memory" and not request.memory_id:
        raise MemoryValidationError("Memory ID is required for update_memory action")
        
    if request.action == "delete_memory" and not request.memory_id:
        raise MemoryValidationError("Memory ID is required for delete_memory action")
        
    if request.action == "retrieve_context":
        if not request.content and not request.context_id:
            raise MemoryValidationError("Either content or context_id is required for retrieve_context")
            
    if request.limit is not None and request.limit <= 0:
        raise MemoryValidationError("Limit must be positive if specified")
