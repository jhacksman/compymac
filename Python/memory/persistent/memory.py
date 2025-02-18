"""Persistent memory module for CompyMac.

This module implements time-independent background knowledge storage with 
task-specific contexts using Venice.ai API.
"""

from typing import Dict, List, Optional
from datetime import datetime

from ..message_types import MemoryMetadata
from ..venice_client import VeniceClient
from ..librarian import LibrarianAgent
from .config import PersistentMemoryConfig
from ..exceptions import MemoryError


class PersistentMemory:
    """Persistent memory module for fixed knowledge storage."""
    
    def __init__(
        self,
        config: PersistentMemoryConfig,
        venice_client: VeniceClient
    ):
        """Initialize persistent memory module.
        
        Args:
            config: Configuration for the module
            venice_client: Client for Venice.ai API
        """
        self.config = config
        self.librarian = LibrarianAgent(venice_client)
        
        # Memory storage
        self.memory_chunks: List[Dict] = []
        self.current_chunk_index = 0
        
    async def store_knowledge(
        self,
        content: str,
        metadata: MemoryMetadata,
        task_id: Optional[int] = None,
        surprise_score: float = 0.0
    ) -> str:
        """Store new knowledge in persistent memory.
        
        Args:
            content: Knowledge content to store
            metadata: Associated metadata
            task_id: Optional task context ID
            surprise_score: Score indicating how surprising/novel the content is
            
        Returns:
            ID of stored knowledge
            
        Raises:
            MemoryError: If storage fails
        """
        try:
            # Add task context
            if task_id is not None:
                metadata.context_ids = [f"task_{task_id}"]
                metadata.task_id = task_id  # Add task_id directly to metadata
                
            # Store via librarian with surprise-based filtering
            memory_id = await self.librarian.store_memory(
                content=content,
                metadata=metadata,
                surprise_score=surprise_score
            )
            
            # Add to current chunk
            memory_entry = {
                "id": memory_id,
                "content": content,
                "metadata": metadata,
                "task_id": task_id,
                "timestamp": datetime.now().timestamp()
            }
            
            # Check if current chunk is full
            if len(self.memory_chunks) == 0 or \
               len(self.memory_chunks[-1]) >= self.config.memory_chunk_size:
                # Create new chunk
                self.memory_chunks.append([])
                self.current_chunk_index = len(self.memory_chunks) - 1
                
            # Add to current chunk
            self.memory_chunks[self.current_chunk_index].append(memory_entry)
            
            return memory_id
            
        except Exception as e:
            raise MemoryError(f"Failed to store knowledge: {str(e)}")
            
    async def retrieve_knowledge(
        self,
        query: str,
        task_id: Optional[int] = None,
        limit: Optional[int] = None,
        min_importance: Optional[float] = None
    ) -> List[Dict]:
        """Retrieve relevant knowledge based on query.
        
        Args:
            query: Search query
            task_id: Optional task context ID
            limit: Maximum number of results
            min_importance: Minimum importance score filter
            
        Returns:
            List of relevant knowledge entries
            
        Raises:
            MemoryError: If retrieval fails
        """
        try:
            # Get knowledge via librarian with hybrid ranking
            memories = await self.librarian.retrieve_memories(
                query=query,
                context_id=f"task_{task_id}" if task_id is not None else None,
                limit=limit,
                min_importance=min_importance
            )
            
            # Filter by task ID if specified
            if task_id is not None:
                memories = [
                    memory for memory in memories
                    if memory.get("task_id") == task_id or 
                    f"task_{task_id}" in memory.get("metadata", {}).get("context_ids", [])
                ]
            
            return memories
            
        except Exception as e:
            raise MemoryError(f"Failed to retrieve knowledge: {str(e)}")
            
    def _get_memory_chunk(self, chunk_index: int) -> List[Dict]:
        """Get a specific memory chunk.
        
        Args:
            chunk_index: Index of chunk to retrieve
            
        Returns:
            List of knowledge entries in chunk
            
        Raises:
            MemoryError: If chunk index is invalid
        """
        if chunk_index >= len(self.memory_chunks):
            raise MemoryError(f"Invalid chunk index: {chunk_index}")
            
        return self.memory_chunks[chunk_index]
