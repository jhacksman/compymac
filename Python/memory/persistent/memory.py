"""Persistent memory module for CompyMac.

This module implements time-independent background knowledge storage with 
task-specific contexts using Venice.ai API.
"""

from typing import Dict, List, Optional
from datetime import datetime

from ..message_types import MemoryMetadata
from ..venice_client import VeniceClient
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
        self.venice_client = venice_client
        
        # Memory storage
        self.memory_chunks: List[Dict] = []
        self.current_chunk_index = 0
        
    async def store_knowledge(
        self,
        content: str,
        metadata: MemoryMetadata,
        task_id: Optional[int] = None
    ) -> str:
        """Store new knowledge in persistent memory.
        
        Args:
            content: Knowledge content to store
            metadata: Associated metadata
            task_id: Optional task context ID
            
        Returns:
            ID of stored knowledge
            
        Raises:
            MemoryError: If storage fails
        """
        try:
            # Add task context
            if task_id is not None:
                metadata.context_ids = [f"task_{task_id}"]
                
            # Store in Venice.ai
            response = await self.venice_client.store_memory(
                content=content,
                metadata=metadata
            )
            
            if not response.success:
                raise MemoryError(f"Failed to store knowledge: {response.error}")
                
            memory_id = response.memory_id
            if not memory_id:
                raise MemoryError("No memory ID returned from Venice.ai")
                
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
        limit: Optional[int] = None
    ) -> List[Dict]:
        """Retrieve relevant knowledge based on query.
        
        Args:
            query: Search query
            task_id: Optional task context ID
            limit: Maximum number of results
            
        Returns:
            List of relevant knowledge entries
            
        Raises:
            MemoryError: If retrieval fails
        """
        try:
            # Get knowledge from Venice.ai
            response = await self.venice_client.retrieve_context(
                query=query,
                context_id=str(task_id) if task_id is not None else None,
                limit=limit
            )
            
            if not response.success:
                raise MemoryError(
                    f"Failed to retrieve knowledge: {response.error}"
                )
                
            return response.memories or []
            
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
