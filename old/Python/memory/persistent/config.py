"""Configuration for persistent memory module."""

from dataclasses import dataclass
from typing import Optional, List


@dataclass
class PersistentMemoryConfig:
    """Configuration for persistent memory."""
    
    # Model parameters
    hidden_size: int = 768
    num_attention_heads: int = 12
    intermediate_size: int = 3072
    max_position_embeddings: int = 4096
    
    # Quantization settings
    quantization: str = "int8"  # Options: none, int8, int4
    
    # Task-specific settings
    task_embedding_size: int = 128
    max_tasks: int = 100
    
    # Memory settings
    max_memory_size: int = 1_000_000  # Maximum number of stored facts
    memory_chunk_size: int = 1000  # Facts per memory chunk
    
    # VRAM optimization
    vram_limit_gb: int = 64
    page_size: int = 4096  # Memory page size for attention
    
    def validate(self) -> None:
        """Validate configuration parameters."""
        if self.vram_limit_gb > 64:
            raise ValueError("VRAM limit cannot exceed 64GB")
            
        if self.quantization not in ["none", "int8", "int4"]:
            raise ValueError("Invalid quantization setting")
            
        # Calculate approximate VRAM usage
        param_bytes = 4  # Default float32
        if self.quantization == "int8":
            param_bytes = 1
        elif self.quantization == "int4":
            param_bytes = 0.5
            
        total_params = (
            self.hidden_size * self.intermediate_size +  # FFN
            self.hidden_size * self.hidden_size * self.num_attention_heads +  # Attention
            self.hidden_size * self.max_position_embeddings  # Embeddings
        )
        
        vram_gb = (total_params * param_bytes) / (1024 ** 3)
        if vram_gb > self.vram_limit_gb:
            raise ValueError(
                f"Configuration would use {vram_gb:.1f}GB VRAM, "
                f"exceeding {self.vram_limit_gb}GB limit"
            )
