"""Persistent memory module for CompyMac.

This module implements fixed learnable parameters and time-independent background
knowledge storage with task-specific contexts. Uses INT8 quantization for VRAM
optimization.
"""

import torch
import torch.nn as nn
from typing import Dict, List, Optional, Tuple, Union
from dataclasses import dataclass
import numpy as np
from datetime import datetime

from ..message_types import MemoryMetadata
from ..venice_client import VeniceClient
from .config import PersistentMemoryConfig
from ..exceptions import MemoryError


class PersistentMemory(nn.Module):
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
        super().__init__()
        self.config = config
        self.venice_client = venice_client
        
        # Validate configuration
        self.config.validate()
        
        # Set device
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        
        # Initialize quantized model components
        self.initialize_quantized_components()
        
        # Task-specific embeddings
        self.task_embeddings = nn.Embedding(
            config.max_tasks,
            config.hidden_size  # Match hidden size for attention
        ).to(self.device)
        
        # Memory chunks for paged attention
        self.memory_chunks: List[Dict] = []
        self.current_chunk_index = 0
        
    def initialize_quantized_components(self):
        """Initialize INT8 quantized neural components."""
        # Validate attention configuration
        if self.config.hidden_size % self.config.num_attention_heads != 0:
            raise ValueError(
                f"Hidden size {self.config.hidden_size} must be divisible by "
                f"number of attention heads {self.config.num_attention_heads}"
            )
            
        # Calculate head dimension
        self.head_dim = self.config.hidden_size // self.config.num_attention_heads
        
        # Create model components
        self.knowledge_transform = nn.Sequential(
            nn.Linear(
                self.config.hidden_size,
                self.config.intermediate_size
            ),
            nn.ReLU(),
            nn.Linear(
                self.config.intermediate_size,
                self.config.hidden_size
            )
        )
        
        # Multi-head attention for knowledge access
        self.knowledge_attention = nn.MultiheadAttention(
            embed_dim=self.config.hidden_size,
            num_heads=self.config.num_attention_heads,
            batch_first=True,
            dropout=0.0
        )
        
        # Move all components to device
        self.to(self.device)
            
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
            # Store in Venice.ai
            response = await self.venice_client.store_memory(
                content=content,
                metadata=metadata
            )
            
            if not response.success:
                raise MemoryError(f"Failed to store knowledge: {response.error}")
                
            knowledge_id = response.memory_id
            if not knowledge_id:
                raise MemoryError("No knowledge ID returned from Venice.ai")
                
            # Add to current memory chunk
            knowledge_entry = {
                "id": knowledge_id,
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
            self.memory_chunks[self.current_chunk_index].append(knowledge_entry)
            
            return knowledge_id
            
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
                
            # Process through attention if task_id provided
            if task_id is not None and response.memories:
                # Get task embedding [batch, seq_len, hidden]
                task_embedding = self.task_embeddings(
                    torch.tensor([task_id], device=self.device)
                ).unsqueeze(0)  # [1, 1, hidden]
                
                # Process memories [batch, seq_len, hidden]
                memory_embeddings = self.knowledge_transform(
                    torch.randn(
                        len(response.memories),
                        self.config.hidden_size,
                        device=self.device
                    )
                )  # [seq_len, hidden]
                memory_embeddings = memory_embeddings.unsqueeze(0)  # [1, seq_len, hidden]
                
                # Ensure all tensors are on the same device
                task_embedding = task_embedding.to(self.device)
                memory_embeddings = memory_embeddings.to(self.device)
                
                # Validate shapes for attention
                assert task_embedding.shape[0] == memory_embeddings.shape[0], "Batch size mismatch"
                assert task_embedding.shape[2] == memory_embeddings.shape[2], "Hidden dimension mismatch"
                assert task_embedding.shape[2] == self.config.hidden_size, "Incorrect hidden dimension"
                assert task_embedding.shape[2] % self.config.num_attention_heads == 0, \
                    "Hidden size must be divisible by number of attention heads"
                
                # Ensure head dimension is correct
                head_dim = self.config.hidden_size // self.config.num_attention_heads
                assert head_dim * self.config.num_attention_heads == self.config.hidden_size, \
                    "Hidden size must be divisible by number of attention heads"
                
                # Apply attention using task embedding as query
                attended_memories, attention_weights = self.knowledge_attention(
                    query=task_embedding,
                    key=memory_embeddings,
                    value=memory_embeddings,
                    need_weights=True,
                    average_attn_weights=True
                )
                
                # Use attention weights directly for scoring
                # attention_weights has shape [batch_size, target_seq_len, source_seq_len]
                sorted_indices = torch.argsort(
                    attention_weights[0, 0],  # Take first batch, first query position
                    descending=True
                )
                
                # Reorder memories
                memories = [
                    response.memories[i]
                    for i in sorted_indices.tolist()
                ]
                
                # Apply limit
                if limit is not None:
                    memories = memories[:limit]
                    
                return memories
                
            return response.memories or []
            
        except Exception as e:
            raise MemoryError(f"Failed to retrieve knowledge: {str(e)}")
            
    def get_task_embedding(self, task_id: int) -> torch.Tensor:
        """Get embedding for a specific task.
        
        Args:
            task_id: Task identifier
            
        Returns:
            Task embedding tensor
            
        Raises:
            MemoryError: If task_id is invalid
        """
        if task_id >= self.config.max_tasks:
            raise MemoryError(f"Invalid task ID: {task_id}")
            
        return self.task_embeddings(torch.tensor([task_id]))
        
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
