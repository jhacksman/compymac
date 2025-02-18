"""Core memory module for immediate context processing.

This module implements the short-term/working memory component that focuses on
processing the current input using Venice.ai API with dynamic encoding and
surprise-based filtering.
"""

from typing import Dict, List, Optional, Union
from dataclasses import dataclass
from datetime import datetime
import math

import torch
import torch.nn as nn
from transformers import AutoModel, AutoTokenizer, AutoConfig

from .message_types import MemoryMetadata, MemoryRequest, MemoryResponse
from .exceptions import MemoryError
from .venice_client import VeniceClient
from .librarian import LibrarianAgent


@dataclass
class CoreMemoryConfig:
    """Configuration for core memory module."""
    context_size: int = 4096  # Transformer context window
    window_size: int = 100  # Number of recent items to keep
    surprise_threshold: float = 0.5  # Threshold for surprise-based filtering
    model_name: str = "facebook/bart-base"  # Base transformer model
    hidden_size: int = 768  # Hidden size for transformer
    num_attention_heads: int = 12  # Number of attention heads


class CoreMemory(nn.Module):
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
        super().__init__()
        self.config = config
        self.venice_client = venice_client
        self.librarian = LibrarianAgent(venice_client)
        
        # Initialize transformer components
        self.tokenizer = AutoTokenizer.from_pretrained(config.model_name)
        self.transformer = AutoModel.from_pretrained(config.model_name)
        
        # Attention components
        self.query_proj = nn.Linear(config.hidden_size, config.hidden_size)
        self.key_proj = nn.Linear(config.hidden_size, config.hidden_size)
        self.value_proj = nn.Linear(config.hidden_size, config.hidden_size)
        
        # Current context state
        self.current_context: List[Dict] = []
        
        # Move model to GPU if available
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.to(self.device)
        
    def reset_context(self):
        """Reset the current context state."""
        self.current_context = []
        
    def add_to_context(
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
            
        # Encode content
        inputs = self.tokenizer(
            content,
            padding=True,
            truncation=True,
            max_length=self.config.context_size,
            return_tensors="pt"
        ).to(self.device)
        
        # Get content embeddings
        with torch.no_grad():
            outputs = self.transformer(**inputs)
            embeddings = outputs.last_hidden_state[:, 0, :]  # Use [CLS] token
            
        # Compute surprise score if not provided
        if surprise_score is None:
            # Project query and memory
            query = self.query_proj(embeddings)
            keys = self.key_proj(torch.stack([
                self.transformer(**self.tokenizer(
                    item["content"],
                    padding=True,
                    truncation=True,
                    max_length=self.config.context_size,
                    return_tensors="pt"
                ).to(self.device)).last_hidden_state[:, 0, :]
                for item in self.current_context[-self.config.window_size:]
            ]) if self.current_context else torch.empty(0, self.config.hidden_size).to(self.device))
            
            if keys.size(0) > 0:
                attention_scores = torch.matmul(query, keys.transpose(-2, -1))
                attention_scores = attention_scores / math.sqrt(self.config.hidden_size)
                max_attention = torch.max(attention_scores).item()
                surprise_score = 1.0 - max_attention
            else:
                surprise_score = 1.0  # First item is surprising
            
        # Apply surprise-based filtering
        if surprise_score > self.config.surprise_threshold:
            # Store important memories via librarian
            self.librarian.store_memory(
                content=content,
                metadata=metadata,
                surprise_score=surprise_score
            )
            
        # Add to context with embeddings
        self.current_context.append({
            "content": content,
            "metadata": metadata,
            "surprise_score": surprise_score,
            "embeddings": embeddings
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
        
    def process_context(
        self,
        query: Optional[str] = None,
        min_importance: Optional[float] = None
    ) -> List[Dict]:
        """Process current context through transformer attention.
        
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
        
        # Encode context items
        context_texts = [item["content"] for item in recent_context]
        context_encodings = self.tokenizer(
            context_texts,
            padding=True,
            truncation=True,
            max_length=self.config.context_size,
            return_tensors="pt"
        ).to(self.device)
        
        # Get context embeddings
        with torch.no_grad():
            context_outputs = self.transformer(**context_encodings)
            context_embeddings = context_outputs.last_hidden_state[:, 0, :]  # Use [CLS] token
        
        if query is not None:
            # Encode query
            query_encoding = self.tokenizer(
                query,
                padding=True,
                truncation=True,
                max_length=self.config.context_size,
                return_tensors="pt"
            ).to(self.device)
            
            # Get query embedding
            with torch.no_grad():
                query_outputs = self.transformer(**query_encoding)
                query_embedding = query_outputs.last_hidden_state[:, 0, :]  # Use [CLS] token
            
            # Compute attention scores
            query_proj = self.query_proj(query_embedding)
            key_proj = self.key_proj(context_embeddings)
            
            attention_scores = torch.matmul(query_proj, key_proj.transpose(-2, -1))
            attention_scores = attention_scores / math.sqrt(self.config.hidden_size)
            attention_weights = torch.softmax(attention_scores, dim=-1)
            
            # Filter by attention weights and importance
            filtered_context = []
            for idx, (item, weight) in enumerate(zip(recent_context, attention_weights[0])):
                importance = item["metadata"].importance if hasattr(item["metadata"], "importance") else 0.0
                if weight > 0.1 and (min_importance is None or importance >= min_importance):
                    filtered_context.append(item)
            
            return filtered_context
        
        # Return recent context if no query
        return recent_context
        
    def summarize_context(self) -> str:
        """Generate a summary of current context using transformer model.
        
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
            
            # Encode context
            context_encoding = self.tokenizer(
                context_str,
                padding=True,
                truncation=True,
                max_length=self.config.context_size,
                return_tensors="pt"
            ).to(self.device)
            
            # Generate summary using transformer
            with torch.no_grad():
                outputs = self.transformer.generate(
                    **context_encoding,
                    max_length=200,
                    num_beams=4,
                    length_penalty=2.0,
                    early_stopping=True
                )
                
            summary = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
            return summary
            
        except Exception as e:
            raise MemoryError(f"Failed to summarize context: {str(e)}")
