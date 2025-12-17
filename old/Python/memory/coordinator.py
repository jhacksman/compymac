"""Memory coordination system for CompyMac."""

from typing import Dict, Any, Optional
from datetime import datetime
import json

from .manager import MemoryManager
from .venice_api import VeniceAPI
from .message_types import MemoryMetadata

class MemoryCoordinator:
    """Coordinates memory operations across different tiers."""
    
    def __init__(self, 
                 memory_manager: Optional[MemoryManager] = None,
                 venice_api: Optional[VeniceAPI] = None,
                 importance_threshold: float = 0.8):
        """Initialize memory coordinator.
        
        Args:
            memory_manager: Optional memory manager instance
            venice_api: Optional Venice.ai API client
            importance_threshold: Threshold for long-term storage
        """
        self.memory_manager = memory_manager or MemoryManager()
        self.venice_api = venice_api or VeniceAPI()
        self.importance_threshold = importance_threshold
        
    def store_task_result(self, result: Dict[str, Any], metadata: Dict[str, Any]) -> None:
        """Store task result in appropriate memory tier.
        
        Args:
            result: Task execution result
            metadata: Result metadata including importance score
        """
        # Always store in medium-term memory
        self.memory_manager.store_memory(
            content=json.dumps(result),
            metadata=MemoryMetadata(
                timestamp=datetime.now().timestamp(),
                importance=metadata.get("importance", 0.0),
                tags=["task_result"],
                **{k:v for k,v in metadata.items() if k not in ["importance", "tags"]}
            )
        )
        
        # Store important results in long-term memory via Venice.ai
        if metadata.get("importance", 0) > self.importance_threshold:
            self.venice_api.store_memory(
                content=json.dumps(result),
                metadata=MemoryMetadata(
                    timestamp=datetime.now().timestamp(),
                    importance=metadata.get("importance", 0.9),
                    tags=["important_result"],
                    **{k:v for k,v in metadata.items() if k not in ["importance", "tags"]}
                )
            )
            
    def snapshot_context(self) -> Dict[str, Any]:
        """Create snapshot of current context.
        
        Returns:
            Context snapshot as dictionary
        """
        # Get current context from memory manager
        context = self.memory_manager.get_context()
        
        # Create snapshot
        snapshot = {
            "timestamp": datetime.now().isoformat(),
            "context": context,
            "metadata": MemoryMetadata(
                timestamp=datetime.now().timestamp(),
                tags=["context_snapshot"]
            )
        }
        
        # Store snapshot in medium-term memory
        self.memory_manager.store_memory(
            content=json.dumps({
                "timestamp": snapshot["timestamp"],
                "context": snapshot["context"],
                "metadata": snapshot["metadata"].asdict()
            }),
            metadata=snapshot["metadata"]
        )
        
        return snapshot
        
    def retrieve_context(self, query: str, time_range: str = "1d") -> Dict[str, Any]:
        """Retrieve context based on query.
        
        Args:
            query: Search query
            time_range: Time range to search (e.g. "1d" for last day)
            
        Returns:
            Retrieved context
        """
        # Search medium-term memory first
        medium_term = self.memory_manager.retrieve_context(
            query=query,
            time_range=time_range
        )
        
        # Search long-term memory if needed
        long_term = {}
        if not medium_term:
            long_term = self.venice_api.search_memories(
                query=query,
                time_range=time_range
            )
            
        return {
            "medium_term": medium_term,
            "long_term": long_term
        }
