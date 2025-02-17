"""Long-term memory management for CompyMac.

This module implements persistent storage and retrieval of memories with
intelligent pruning and context management.
"""

import json
import time
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta

from .exceptions import MemoryError
from .protocol import Message, MessageMetadata
from .venice_api import VeniceAPI

@dataclass
class LongTermMemory:
    """Represents a long-term memory entry."""
    id: str
    content: str
    metadata: MessageMetadata
    timestamp: float
    last_accessed: float
    importance_score: float
    context_ids: List[str]

class LongTermMemoryManager:
    """Manages long-term memory storage and retrieval."""
    
    def __init__(self, venice_api: VeniceAPI):
        self.venice_api = venice_api
        self._memories: Dict[str, LongTermMemory] = {}
        self._context_index: Dict[str, List[str]] = {}
        
    async def store_memory(
        self,
        content: str,
        metadata: MessageMetadata,
        context_ids: Optional[List[str]] = None
    ) -> str:
        """Store a new memory in long-term storage.
        
        Args:
            content: The memory content to store
            metadata: Associated metadata for the memory
            context_ids: Optional list of context IDs to associate with this memory
            
        Returns:
            The ID of the stored memory
            
        Raises:
            MemoryError: If storage fails
        """
        try:
            memory_id = await self.venice_api.store_memory(content, metadata)
            
            memory = LongTermMemory(
                id=memory_id,
                content=content,
                metadata=metadata,
                timestamp=time.time(),
                last_accessed=time.time(),
                importance_score=self._calculate_importance(content, metadata),
                context_ids=context_ids or []
            )
            
            self._memories[memory_id] = memory
            
            # Update context index
            for context_id in memory.context_ids:
                if context_id not in self._context_index:
                    self._context_index[context_id] = []
                self._context_index[context_id].append(memory_id)
                
            return memory_id
            
        except Exception as e:
            raise MemoryError(f"Failed to store memory: {str(e)}")
            
    async def retrieve_context(
        self,
        query: str,
        context_id: Optional[str] = None,
        time_range: Optional[timedelta] = None,
        limit: int = 10
    ) -> List[LongTermMemory]:
        """Retrieve relevant memories based on context.
        
        Args:
            query: Search query to match memories
            context_id: Optional context to filter memories
            time_range: Optional time range to filter memories
            limit: Maximum number of memories to return
            
        Returns:
            List of relevant memories
            
        Raises:
            MemoryError: If retrieval fails
        """
        try:
            # Get candidate memory IDs
            candidate_ids = set()
            
            if context_id and context_id in self._context_index:
                candidate_ids.update(self._context_index[context_id])
            else:
                candidate_ids.update(self._memories.keys())
                
            # Filter by time range if specified
            if time_range:
                cutoff = datetime.now() - time_range
                candidate_ids = {
                    mid for mid in candidate_ids
                    if self._memories[mid].timestamp >= cutoff.timestamp()
                }
                
            # Get semantic search results from Venice
            results = await self.venice_api.retrieve_context(
                query,
                list(candidate_ids)
            )
            
            # Update access times and return memories
            memories = []
            for memory_id in results[:limit]:
                memory = self._memories[memory_id]
                memory.last_accessed = time.time()
                memories.append(memory)
                
            return memories
            
        except Exception as e:
            raise MemoryError(f"Failed to retrieve memories: {str(e)}")
            
    def _calculate_importance(
        self,
        content: str,
        metadata: MessageMetadata
    ) -> float:
        """Calculate importance score for a memory.
        
        The score is based on:
        - Explicit importance in metadata
        - Length and complexity of content
        - Number of associated contexts
        - Recency of creation/access
        
        Returns:
            Float importance score between 0 and 1
        """
        score = 0.0
        
        # Base importance from metadata
        if metadata.importance:
            score += float(metadata.importance)
            
        # Content length (normalized)
        score += min(len(content) / 1000, 1.0) * 0.3
        
        # Context connections
        if metadata.context_ids:
            score += min(len(metadata.context_ids) / 5, 1.0) * 0.2
            
        # Recency bonus
        age = time.time() - metadata.timestamp
        recency = max(0, 1 - (age / (30 * 24 * 60 * 60)))  # 30 day scale
        score += recency * 0.2
        
        return min(score, 1.0)  # Normalize to [0,1]
