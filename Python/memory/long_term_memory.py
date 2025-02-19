"""Long-term memory management for CompyMac.

This module implements memory management for storing information beyond
context window using Venice.ai API with dynamic encoding and surprise-based
filtering through the librarian agent.
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import time
from datetime import datetime, timedelta
import asyncio

from .message_types import MemoryMetadata, MemoryRequest, MemoryResponse
from .exceptions import MemoryError
from .venice_client import VeniceClient
from .librarian import LibrarianAgent
from .db import MemoryDB

# Type alias for memory entries
Memory = Dict[str, Any]

@dataclass
class LongTermMemoryConfig:
    """Configuration for long-term memory module."""
    max_memories: int = 1000
    summary_threshold: int = 100  # Messages before summarization
    context_window_size: int = 10  # Recent messages to keep in full
    surprise_threshold: float = 0.5  # Threshold for surprise-based filtering
    min_similarity: float = 0.7  # Minimum similarity threshold for retrieval


class LongTermMemory:
    """Long-term memory module for storing historical information."""
    
    def __init__(
        self,
        config: LongTermMemoryConfig,
        venice_client: VeniceClient,
        memory_db: MemoryDB
    ):
        """Initialize long-term memory module.
        
        Args:
            config: Configuration for the module
            venice_client: Client for Venice.ai API
            memory_db: Database connection for memory storage
        """
        self.config = config
        self.librarian = LibrarianAgent(venice_client)
        self.venice_client = venice_client
        self.memory_db = memory_db
        
        # Recent context
        self.recent_context: List[Dict] = []
        
    async def store_memory(
        self,
        content: str,
        metadata: MemoryMetadata,
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
            # Store in Venice.ai
            # Get embedding from Venice.ai
            embedding_response = await self.venice_client.get_embedding(content)
            if not embedding_response.success:
                raise MemoryError(f"Failed to get embedding: {embedding_response.error}")
            
            # Store in database
            memory_id = self.memory_db.store_memory(
                content=content,
                embedding=embedding_response.embedding,
                metadata=metadata,
                memory_type='ltm',
                context_ids=context_ids
            )
            if not memory_id:
                raise MemoryError("Failed to store memory in database")
                
            # Add to recent context
            self.recent_context.append({
                "id": memory_id,
                "content": content,
                "metadata": metadata,
                "context_ids": context_ids or []
            })
            
            # Maintain context window size
            if len(self.recent_context) > self.config.context_window_size:
                # Summarize and store older context
                await self._summarize_context()
                
            return memory_id
            
        except Exception as e:
            raise MemoryError(f"Failed to store memory: {str(e)}")
            
    async def retrieve_context(
        self,
        query: str,
        context_id: Optional[str] = None,
        time_range: Optional[timedelta] = None,
        limit: Optional[int] = None
    ) -> List[Dict]:
        """Retrieve relevant memories based on context.
        
        Args:
            query: Search query to match memories
            context_id: Optional context ID filter
            time_range: Optional time range filter
            limit: Maximum number of memories to return
            
        Returns:
            List of relevant memories
            
        Raises:
            MemoryError: If retrieval fails
        """
        try:
            # Get embedding for query
            query_response = await self.venice_client.get_embedding(query)
            if not query_response.success:
                raise MemoryError(f"Failed to get query embedding: {query_response.error}")
            
            # Get similar memories from database
            similar_memories = self.memory_db.retrieve_similar(
                embedding=query_response.embedding,
                limit=limit or 10,
                min_similarity=self.config.min_similarity
            )
            
            # Filter by context and time if needed
            filtered_memories = [
                memory for memory in similar_memories
                if self._matches_filters(
                    memory,
                    context_id=context_id,
                    time_range=time_range
                )
            ]
            
            # Apply limit
            if limit is not None:
                filtered_memories = filtered_memories[:limit]
                
            return filtered_memories
            
        except Exception as e:
            raise MemoryError(f"Failed to retrieve memories: {str(e)}")
            
    def _matches_filters(
        self,
        memory: Dict,
        context_id: Optional[str] = None,
        time_range: Optional[timedelta] = None
    ) -> bool:
        """Check if memory matches retrieval filters.
        
        Args:
            memory: Memory to check
            context_id: Optional context ID filter
            time_range: Optional time range filter
            
        Returns:
            True if memory matches filters
        """
        if context_id and memory["context_ids"]:
            if context_id not in memory["context_ids"]:
                return False
                
        if time_range:
            memory_time = memory["metadata"].timestamp
            cutoff = datetime.now().timestamp() - time_range.total_seconds()
            if memory_time < cutoff:
                return False
                
        return True
        
    async def _summarize_context(self) -> None:
        """Summarize and store older context items."""
        if len(self.recent_context) <= self.config.context_window_size:
            return
            
        # Get items to summarize
        to_summarize = self.recent_context[:-self.config.context_window_size]
        
        # Create summary using Venice.ai
        summary_content = "\n".join(
            memory["content"] for memory in to_summarize
        )
        
        # Generate summary using Venice.ai
        summary_response = await self.venice_client.generate_summary(summary_content)
        if not summary_response.success:
            raise MemoryError(f"Failed to generate summary: {summary_response.error}")
            
        # Store summary with metadata
        summary_metadata = MemoryMetadata(
            timestamp=datetime.now().timestamp(),
            importance=1.0,  # High importance for summaries
            tags=["summary"],
            source="summarization"
        )
        
        # Update recent context first to prevent recursion
        self.recent_context = self.recent_context[-self.config.context_window_size:]
        
        # Store summary in database
        await self.store_memory(
            content=summary_response.summary or "",
            metadata=summary_metadata
        )
