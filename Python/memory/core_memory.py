"""Core memory module for immediate context processing.

This module implements the short-term/working memory component that focuses on
processing the current input using standard attention mechanisms.
"""

import torch
import torch.nn as nn
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

from .message_types import MemoryMetadata
from .exceptions import MemoryError


@dataclass
class CoreMemoryConfig:
    """Configuration for core memory module."""
    context_size: int = 4096  # Venice.ai default
    hidden_size: int = 768
    num_attention_heads: int = 12
    attention_dropout: float = 0.1
    max_position_embeddings: int = 4096


class CoreMemory(nn.Module):
    """Core memory module for immediate context processing."""
    
    def __init__(self, config: CoreMemoryConfig):
        """Initialize core memory module.
        
        Args:
            config: Configuration for the module
        """
        super().__init__()
        self.config = config
        
        # Token embeddings for current context
        self.token_embedding = nn.Embedding(
            config.context_size,
            config.hidden_size
        )
        
        # Position embeddings
        self.position_embedding = nn.Embedding(
            config.max_position_embeddings,
            config.hidden_size
        )
        
        # Multi-head attention for processing current context
        self.attention = nn.MultiheadAttention(
            embed_dim=config.hidden_size,
            num_heads=config.num_attention_heads,
            dropout=config.attention_dropout,
            batch_first=True
        )
        
        # Layer normalization
        self.layer_norm = nn.LayerNorm(config.hidden_size)
        
        # Current context state
        self.current_context: List[Dict] = []
        self.context_embeddings: Optional[torch.Tensor] = None
        
    def reset_context(self):
        """Reset the current context state."""
        self.current_context = []
        self.context_embeddings = None
        
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
        
        # Reset embeddings since context changed
        self.context_embeddings = None
        
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
            return self.current_context
            
        return self.current_context[-window_size:]
        
    def process_context(
        self,
        query: Optional[str] = None
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """Process current context through attention mechanism.
        
        Args:
            query: Optional query to focus attention
            
        Returns:
            Tuple of (context_embeddings, attention_weights)
            
        Raises:
            MemoryError: If no context is available
        """
        if not self.current_context:
            raise MemoryError("No context available to process")
            
        # Generate or get context embeddings
        if self.context_embeddings is None:
            # Convert context to token IDs (simplified for example)
            token_ids = torch.arange(len(self.current_context))
            
            # Get token embeddings
            self.context_embeddings = self.token_embedding(token_ids)
            
            # Add position embeddings
            positions = torch.arange(len(self.current_context))
            position_embeddings = self.position_embedding(positions)
            self.context_embeddings = self.context_embeddings + position_embeddings
            
        # Process through attention
        if query is not None:
            # Use query to generate attention mask (simplified)
            query_embedding = self.token_embedding(
                torch.tensor([0])  # Placeholder query token ID
            )
            context_output, attention_weights = self.attention(
                query=query_embedding.unsqueeze(0),
                key=self.context_embeddings.unsqueeze(0),
                value=self.context_embeddings.unsqueeze(0)
            )
        else:
            # Self-attention if no query
            context_output, attention_weights = self.attention(
                query=self.context_embeddings.unsqueeze(0),
                key=self.context_embeddings.unsqueeze(0),
                value=self.context_embeddings.unsqueeze(0)
            )
            
        # Apply layer norm
        context_output = self.layer_norm(context_output)
        
        return context_output.squeeze(0), attention_weights.squeeze(0)
        
    def summarize_context(self) -> str:
        """Generate a summary of current context.
        
        Returns:
            Summary string of current context
            
        Raises:
            MemoryError: If no context is available
        """
        if not self.current_context:
            raise MemoryError("No context available to summarize")
            
        # Process context
        context_output, _ = self.process_context()
        
        # For now, just return the most recent content
        # In practice, you would use the processed embeddings
        # to generate a proper summary
        return self.current_context[-1]["content"]
