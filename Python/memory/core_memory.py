"""Core memory module for immediate context processing.

This module implements the short-term/working memory component that focuses on
processing the current input using Venice.ai API with dynamic encoding and
surprise-based filtering.
"""

from typing import Dict, List, Optional, Union
from dataclasses import dataclass
from datetime import datetime
import math
import asyncio

from .message_types import MemoryMetadata, MemoryRequest, MemoryResponse
from .exceptions import MemoryError
from .venice_client import VeniceClient
from .librarian import LibrarianAgent
from .db import MemoryDB


@dataclass
class CoreMemoryConfig:
    """Configuration for core memory module."""
    context_size: int = 4096  # Context window size
    window_size: int = 100  # Number of recent items to keep
    surprise_threshold: float = 0.5  # Threshold for surprise-based filtering
    min_similarity: float = 0.7  # Minimum similarity threshold for retrieval


class CoreMemory:
    """Core memory module for immediate context processing."""
    
    def __init__(
        self,
        config: CoreMemoryConfig,
        venice_client: VeniceClient,
        memory_db: MemoryDB
    ):
        """Initialize core memory module.
        
        Args:
            config: Configuration for the module
            venice_client: Client for Venice.ai API
            memory_db: Database connection for memory storage
        """
        self.config = config
        self.venice_client = venice_client
        self.librarian = LibrarianAgent(venice_client)
        self.memory_db = memory_db
        
        # Current context state
        self.current_context: List[Dict] = []
        
    def reset_context(self):
        """Reset the current context state."""
        self.current_context = []
        
    async def add_to_context(
        self,
        content: str,
        metadata: MemoryMetadata,
        surprise_score: Optional[float] = None
    ) -> None:
        """Add new content to current context with dynamic encoding.
        
        Args:
            content: Content to add
            metadata: Associated metadata
            surprise_score: Optional score indicating content novelty
            
        Raises:
            MemoryError: If context size would exceed limit
        """
        try:
            # Check context size limit
            if len(self.current_context) >= self.config.context_size:
                raise MemoryError(
                    f"Context size limit ({self.config.context_size}) exceeded"
                )
            # Get embedding from Venice.ai
            embedding_response = await self.venice_client.get_embedding(content)
            if not embedding_response.success:
                raise MemoryError(f"Failed to get embedding: {embedding_response.error}")
            
            if not embedding_response.embedding:
                raise MemoryError("No embedding returned from Venice.ai")
                
            embedding = embedding_response.embedding
        except Exception as e:
            raise MemoryError(f"Failed to process content: {str(e)}")
        
        # Compute surprise score if not provided
        if surprise_score is None:
            if self.current_context:
                # Get similar memories to compute surprise
                similar_memories = self.memory_db.retrieve_similar(
                    embedding=embedding,
                    limit=1,
                    memory_type='stm',
                    min_similarity=self.config.min_similarity
                )
                surprise_score = 1.0 - similar_memories[0]['similarity'] if similar_memories else 1.0
            else:
                surprise_score = 1.0  # First item is surprising
            
        # Store memory regardless of surprise score
        memory_id = self.memory_db.store_memory(
            content=content,
            embedding=embedding,
            metadata=metadata if isinstance(metadata, dict) else {},
            memory_type='stm',
            surprise_score=float(surprise_score),
            tags=['short_term']
        )
        
        # Store via librarian only if surprising enough
        if surprise_score > self.config.surprise_threshold:
            await self.librarian.store_memory(
                content=content,
                metadata=metadata,
                surprise_score=float(surprise_score)
            )
            
        # Add to context
        self.current_context.append({
            "id": memory_id,
            "content": content,
            "metadata": metadata if isinstance(metadata, dict) else {},
            "surprise_score": float(surprise_score),
            "embedding": embedding
        })
        
    def get_context_window(
        self,
        window_size: Optional[int] = None
    ) -> List[Dict]:
        """Get the most recent context window.
        
        Args:
            window_size: Optional size limit for context window
            
        Returns:
            List of context items up to window_size
        """
        if window_size is None:
            window_size = self.config.window_size
            
        return self.current_context[-window_size:]
        
    async def process_context(
        self,
        query: Optional[str] = None,
        min_importance: Optional[float] = None
    ) -> List[Dict]:
        """Process current context using Venice.ai embeddings.
        
        Args:
            query: Optional query to focus attention
            min_importance: Minimum importance score filter
            
        Returns:
            List of relevant context items
            
        Raises:
            MemoryError: If no context is available
        """
        if not self.current_context:
            raise MemoryError("No context available to process")
            
        # Get recent context window
        recent_context = self.current_context[-self.config.window_size:]
        
        if query is not None:
            # Get query embedding from Venice.ai
            query_response = await self.venice_client.get_embedding(query)
            if not query_response.success:
                raise MemoryError(f"Failed to get query embedding: {query_response.error}")
                
            if not query_response.embedding:
                raise MemoryError("No embedding returned from Venice.ai")
            
            # Get similar memories from database
            similar_memories = self.memory_db.retrieve_similar(
                embedding=query_response.embedding,
                limit=self.config.window_size,
                memory_type='stm',
                min_similarity=self.config.min_similarity
            )
            
            # Filter by importance if needed
            if min_importance is not None:
                similar_memories = [
                    mem for mem in similar_memories
                    if float(mem['metadata'].get('importance', 0.0)) >= min_importance
                ]
            
            return similar_memories
        
        # Return recent context if no query
        return recent_context
        
    async def summarize_context(self) -> str:
        """Generate a summary of current context using Venice.ai.
        
        Returns:
            Summary string of current context
            
        Raises:
            MemoryError: If no context is available
        """
        if not self.current_context:
            raise MemoryError("No context available to summarize")
            
        try:
            # Combine context into single string
            context_str = "\n".join(
                entry["content"] for entry in self.current_context
            )
            
            # Use Venice.ai to generate summary
            summary_response = await self.venice_client.generate_summary(context_str)
            if not summary_response.success:
                raise MemoryError(f"Failed to generate summary: {summary_response.error}")
                
            if not summary_response.summary:
                raise MemoryError("No summary returned from Venice.ai")
            
            return summary_response.summary
            
        except Exception as e:
            raise MemoryError(f"Failed to summarize context: {str(e)}")
