"""Long-term memory management for CompyMac.

This module implements neural memory mechanism for storing information beyond
context window, with support for periodic summarization and sliding context.
"""

import torch
import torch.nn as nn
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import time
from datetime import datetime, timedelta

from .message_types import MemoryMetadata, MemoryRequest, MemoryResponse
from .exceptions import MemoryError
from .venice_client import VeniceClient

# Type alias for memory entries
Memory = Dict[str, any]

@dataclass
class LongTermMemoryConfig:
    """Configuration for long-term memory module."""
    max_memories: int = 1000
    summary_threshold: int = 100  # Messages before summarization
    context_window_size: int = 10  # Recent messages to keep in full
    embedding_size: int = 768
    memory_dropout: float = 0.1


class LongTermMemory(nn.Module):
    """Long-term memory module for storing historical information."""
    
    def __init__(
        self,
        config: LongTermMemoryConfig,
        venice_client: VeniceClient
    ):
        """Initialize long-term memory module.
        
        Args:
            config: Configuration for the module
            venice_client: Client for Venice.ai API
        """
        super().__init__()
        self.config = config
        self.venice_client = venice_client
        
        # Memory storage
        self.recent_context: List[Dict] = []
        
        # Neural components (using smaller dimensions to reduce memory)
        hidden_size = config.embedding_size // 4  # Reduce dimension
        self.memory_transform = nn.Sequential(
            nn.Linear(config.embedding_size, hidden_size),
            nn.ReLU(),
            nn.Dropout(config.memory_dropout),
            nn.Linear(hidden_size, config.embedding_size)
        )
        
        # Context window
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
            response = await self.venice_client.store_memory(content, metadata)
            if not response.success:
                raise MemoryError(f"Failed to store memory: {response.error}")
                
            memory_id = response.memory_id
            if not memory_id:
                raise MemoryError("No memory ID returned from Venice.ai")
                
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
            # Get memories from Venice.ai
            response = await self.venice_client.retrieve_context(
                query=query,
                context_id=context_id,
                time_range=time_range.total_seconds() if time_range else None,
                limit=limit
            )
            
            if not response.success:
                raise MemoryError(f"Failed to retrieve memories: {response.error}")
                
            # Get filtered recent context
            recent_memories = [
                memory for memory in self.recent_context
                if self._matches_filters(
                    memory,
                    context_id=context_id,
                    time_range=time_range
                )
            ]
            
            # Combine with retrieved memories
            all_memories = []
            seen_ids = set()
            
            # Add recent context first (deduplicated)
            for memory in recent_memories:
                if memory["id"] not in seen_ids:
                    all_memories.append(memory)
                    seen_ids.add(memory["id"])
                    
            # Add retrieved memories (deduplicated)
            if response.memories:
                for memory in response.memories:
                    if memory["id"] not in seen_ids:
                        all_memories.append(memory)
                        seen_ids.add(memory["id"])
                        
            # Apply limit
            if limit is not None:
                all_memories = all_memories[:limit]
                
            return all_memories
            
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
        
        # Store summary with metadata
        summary_metadata = MemoryMetadata(
            timestamp=datetime.now().timestamp(),
            importance=1.0,  # High importance for summaries
            context_ids=[],  # Don't propagate context IDs to avoid cycles
            tags=["summary"],
            source="summarization"
        )
        
        # Update recent context first to prevent recursion
        self.recent_context = self.recent_context[-self.config.context_window_size:]
        
        # Store summary after updating context
        await self.venice_client.store_memory(summary_content, summary_metadata)
