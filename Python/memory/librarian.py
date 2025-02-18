"""Librarian agent for memory orchestration.

This module implements a service layer for managing memory operations,
retrieval, and organization using Venice.ai API.
"""

from typing import Dict, List, Optional
from datetime import datetime, timedelta

from .message_types import MemoryMetadata, MemoryResponse
from .venice_client import VeniceClient
from .exceptions import MemoryError


class LibrarianAgent:
    """Service layer for memory orchestration."""
    
    def __init__(self, venice_client: VeniceClient):
        """Initialize librarian agent.
        
        Args:
            venice_client: Client for Venice.ai API
        """
        self.venice_client = venice_client
        self.recent_memories: List[Dict] = []
        self.importance_threshold = 0.5
        self.max_context_tokens = 4096  # Venice.ai default
        
    async def store_memory(
        self,
        content: str,
        metadata: MemoryMetadata,
        surprise_score: float = 0.0
    ) -> str:
        """Store memory with surprise-based filtering.
        
        Args:
            content: Memory content to store
            metadata: Associated metadata
            surprise_score: Score indicating how surprising/novel the content is
            
        Returns:
            ID of stored memory
            
        Raises:
            MemoryError: If storage fails
        """
        try:
            # Apply surprise-based filtering
            if surprise_score > self.importance_threshold:
                metadata.importance = max(metadata.importance or 0.0, surprise_score)
                
            # Store in Venice.ai
            response = await self.venice_client.store_memory(content, metadata)
            if not response.success:
                raise MemoryError(f"Failed to store memory: {response.error}")
                
            memory_id = response.memory_id
            if not memory_id:
                raise MemoryError("No memory ID returned from Venice.ai")
                
            # Add to recent memories
            self.recent_memories.append({
                "id": memory_id,
                "content": content,
                "metadata": metadata,
                "timestamp": datetime.now().timestamp()
            })
            
            # Maintain context window size
            while len(self.recent_memories) > self.max_context_tokens // 4:  # Rough estimate
                self.recent_memories.pop(0)
                
            return memory_id
            
        except Exception as e:
            raise MemoryError(f"Failed to store memory: {str(e)}")
            
    async def retrieve_memories(
        self,
        query: str,
        context_id: Optional[str] = None,
        time_range: Optional[timedelta] = None,
        limit: Optional[int] = None,
        min_importance: Optional[float] = None
    ) -> List[Dict]:
        """Retrieve memories with hybrid ranking.
        
        Args:
            query: Search query
            context_id: Optional context ID filter
            time_range: Optional time range filter
            limit: Maximum number of memories to return
            min_importance: Minimum importance score filter
            
        Returns:
            List of relevant memories
            
        Raises:
            MemoryError: If retrieval fails
        """
        try:
            # Get memories from Venice.ai
            response = await self.venice_client.retrieve_context(
                query=query,
                context_id=context_id,
                time_range=time_range.total_seconds() if time_range else None,
                limit=None  # Get all memories first, then filter
            )
            
            if not response.success:
                raise MemoryError(f"Failed to retrieve memories: {response.error}")
                
            memories = response.memories or []
            
            # Filter by time range if specified
            if time_range:
                now = datetime.now().timestamp()
                cutoff = now - time_range.total_seconds()
                filtered_memories = []
                for memory in memories:
                    metadata = memory.get("metadata")
                    if isinstance(metadata, dict):
                        if metadata.get("timestamp", 0) >= cutoff:
                            filtered_memories.append(memory)
                    elif hasattr(metadata, "timestamp"):
                        if metadata.timestamp >= cutoff:
                            filtered_memories.append(memory)
                memories = filtered_memories
                
            # Filter by context ID if specified
            if context_id:
                filtered_memories = []
                for memory in memories:
                    metadata = memory.get("metadata")
                    if isinstance(metadata, dict):
                        if context_id in metadata.get("context_ids", []):
                            filtered_memories.append(memory)
                    elif hasattr(metadata, "context_ids"):
                        if context_id in metadata.context_ids:
                            filtered_memories.append(memory)
                memories = filtered_memories
                
            # Filter by importance if specified
            if min_importance is not None:
                filtered_memories = []
                for memory in memories:
                    metadata = memory.get("metadata")
                    if isinstance(metadata, dict):
                        if metadata.get("importance", 0.0) >= min_importance:
                            filtered_memories.append(memory)
                    elif hasattr(metadata, "importance"):
                        if metadata.importance >= min_importance:
                            filtered_memories.append(memory)
                memories = filtered_memories
                
            # Sort by hybrid score (importance + recency)
            now = datetime.now().timestamp()
            for memory in memories:
                metadata = memory.get("metadata")
                if isinstance(metadata, dict):
                    memory_time = metadata.get("timestamp", now)
                    importance = metadata.get("importance", 0.0) or 0.0
                elif hasattr(metadata, "timestamp"):
                    memory_time = metadata.timestamp
                    importance = getattr(metadata, "importance", 0.0) or 0.0
                else:
                    memory_time = now
                    importance = 0.0
                    
                time_diff = now - memory_time
                recency_score = 1.0 / (1.0 + time_diff / 86400)  # Decay over days
                memory["_score"] = importance + recency_score
                
            memories.sort(key=lambda x: x["_score"], reverse=True)
            
            # Apply limit after all filtering
            if limit is not None:
                memories = memories[:limit]
                
            # Remove scoring field
            for memory in memories:
                memory.pop("_score", None)
                
            return memories
            
        except Exception as e:
            raise MemoryError(f"Failed to retrieve memories: {str(e)}")
            
    def get_recent_memories(
        self,
        limit: Optional[int] = None,
        min_importance: Optional[float] = None
    ) -> List[Dict]:
        """Get recent memories from context window.
        
        Args:
            limit: Maximum number of memories to return
            min_importance: Minimum importance score filter
            
        Returns:
            List of recent memories
        """
        memories = self.recent_memories
        
        # Apply importance filter
        if min_importance is not None:
            memories = [
                memory for memory in memories
                if memory.get("metadata", {}).get("importance", 0.0) >= min_importance
            ]
            
        # Apply limit
        if limit is not None:
            memories = memories[-limit:]
            
        return memories
