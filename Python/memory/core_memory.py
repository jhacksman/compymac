"""Core memory module for immediate context processing.

This module implements the short-term/working memory component that focuses on
processing the current input using Venice.ai API.
"""

from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime

from .message_types import MemoryMetadata, MemoryRequest, MemoryResponse
from .exceptions import MemoryError
from .venice_client import VeniceClient


@dataclass
class CoreMemoryConfig:
    """Configuration for core memory module."""
    context_size: int = 4096  # Venice.ai default
    window_size: int = 100  # Number of recent items to keep


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
        self.venice_client = venice_client
        
        # Current context state
        self.current_context: List[Dict] = []
        
    def reset_context(self):
        """Reset the current context state."""
        self.current_context = []
        
    def add_to_context(
        self,
        content: str,
        metadata: MemoryMetadata
    ) -> None:
        """Add new content to current context.
        
        Args:
            content: Content to add
            metadata: Associated metadata
            
        Raises:
            MemoryError: If context size would exceed limit
        """
        # Check context size limit
        if len(self.current_context) >= self.config.context_size:
            raise MemoryError(
                f"Context size limit ({self.config.context_size}) exceeded"
            )
            
        # Add to context
        self.current_context.append({
            "content": content,
            "metadata": metadata
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
        query: Optional[str] = None
    ) -> List[Dict]:
        """Process current context through Venice.ai API.
        
        Args:
            query: Optional query to focus attention
            
        Returns:
            List of relevant context items
            
        Raises:
            MemoryError: If no context is available
        """
        if not self.current_context:
            raise MemoryError("No context available to process")
            
        # Use Venice.ai to process context
        if query is not None:
            response = await self.venice_client.retrieve_context(
                query=query,
                limit=self.config.window_size
            )
            
            if not response.success:
                raise MemoryError(f"Failed to process context: {response.error}")
                
            return response.memories or []
            
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
