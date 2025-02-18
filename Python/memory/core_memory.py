"""Core memory module for immediate context processing.

This module implements the short-term/working memory component that focuses on
processing the current input using Venice.ai API with dynamic encoding and
surprise-based filtering.
"""

from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime

from .message_types import MemoryMetadata, MemoryRequest, MemoryResponse
from .exceptions import MemoryError
from .venice_client import VeniceClient
from .librarian import LibrarianAgent


@dataclass
class CoreMemoryConfig:
    """Configuration for core memory module."""
    context_size: int = 4096  # Venice.ai default
    window_size: int = 100  # Number of recent items to keep
    surprise_threshold: float = 0.5  # Threshold for surprise-based filtering


class CoreMemory:
    """Core memory module for immediate context processing."""
    
    def __init__(
        self,
        config: CoreMemoryConfig,
        venice_client: VeniceClient
    ):
        """Initialize core memory module.
        
        Args:
            config: Configuration for the module
            venice_client: Client for Venice.ai API
        """
        self.config = config
        self.librarian = LibrarianAgent(venice_client)
        
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
        # Check context size limit
        if len(self.current_context) >= self.config.context_size:
            raise MemoryError(
                f"Context size limit ({self.config.context_size}) exceeded"
            )
            
        # Apply surprise-based filtering
        if surprise_score is not None and surprise_score > self.config.surprise_threshold:
            # Store important memories via librarian
            await self.librarian.store_memory(
                content=content,
                metadata=metadata,
                surprise_score=surprise_score
            )
            
        # Add to context
        self.current_context.append({
            "content": content,
            "metadata": metadata,
            "surprise_score": surprise_score
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
        """Process current context through Venice.ai API with hybrid ranking.
        
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
            
        # Use librarian to process context with hybrid ranking
        if query is not None:
            memories = await self.librarian.retrieve_memories(
                query=query,
                limit=self.config.window_size,
                min_importance=min_importance
            )
            
            # Combine with recent context
            recent_context = self.current_context[-self.config.window_size:]
            all_memories = []
            seen_ids = set()
            
            # Add retrieved memories first
            for memory in memories:
                if memory["id"] not in seen_ids:
                    all_memories.append(memory)
                    seen_ids.add(memory["id"])
                    
            # Add recent context (deduplicated)
            for context_item in recent_context:
                if "id" in context_item and context_item["id"] not in seen_ids:
                    all_memories.append(context_item)
                    seen_ids.add(context_item["id"])
                    
            return all_memories
            
        # Return recent context if no query
        return self.current_context[-self.config.window_size:]
        
    def summarize_context(self) -> str:
        """Generate a summary of current context.
        
        Returns:
            Summary string of current context
            
        Raises:
            MemoryError: If no context is available
        """
        if not self.current_context:
            raise MemoryError("No context available to summarize")
            
        # For now, just return the most recent content
        return self.current_context[-1]["content"]
