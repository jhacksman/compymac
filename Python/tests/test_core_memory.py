"""Tests for core memory module."""

import pytest
import torch
from datetime import datetime

from memory.core_memory import CoreMemory, CoreMemoryConfig
from memory.message_types import MemoryMetadata
from memory.exceptions import MemoryError


@pytest.fixture
def core_memory():
    """Create core memory fixture."""
    config = CoreMemoryConfig(
        context_size=4,  # Small size for testing
        hidden_size=32,
        num_attention_heads=2,
        max_position_embeddings=4
    )
    return CoreMemory(config)


def test_core_memory_initialization(core_memory):
    """Test core memory initialization."""
    assert len(core_memory.current_context) == 0
    assert core_memory.context_embeddings is None
    assert isinstance(
        core_memory.token_embedding,
        torch.nn.Embedding
    )
    assert isinstance(
        core_memory.position_embedding,
        torch.nn.Embedding
    )
    assert isinstance(
        core_memory.attention,
        torch.nn.MultiheadAttention
    )


def test_add_to_context(core_memory):
    """Test adding content to context."""
    metadata = MemoryMetadata(timestamp=datetime.now().timestamp())
    
    # Add content
    core_memory.add_to_context("test content", metadata)
    assert len(core_memory.current_context) == 1
    assert core_memory.current_context[0]["content"] == "test content"
    assert core_memory.context_embeddings is None
    
    # Add more content
    core_memory.add_to_context("more content", metadata)
    assert len(core_memory.current_context) == 2
    
    # Test context size limit
    for _ in range(2):
        core_memory.add_to_context("content", metadata)
        
    with pytest.raises(MemoryError):
        core_memory.add_to_context("overflow", metadata)


def test_get_context_window(core_memory):
    """Test getting context window."""
    metadata = MemoryMetadata(timestamp=datetime.now().timestamp())
    
    # Add some content
    for i in range(3):
        core_memory.add_to_context(f"content {i}", metadata)
        
    # Get full context
    context = core_memory.get_context_window()
    assert len(context) == 3
    
    # Get limited window
    context = core_memory.get_context_window(window_size=2)
    assert len(context) == 2
    assert context[-1]["content"] == "content 2"


def test_process_context(core_memory):
    """Test processing context through attention."""
    metadata = MemoryMetadata(timestamp=datetime.now().timestamp())
    
    # Test with empty context
    with pytest.raises(MemoryError):
        core_memory.process_context()
        
    # Add content and process
    core_memory.add_to_context("test content", metadata)
    output, weights = core_memory.process_context()
    
    assert isinstance(output, torch.Tensor)
    assert isinstance(weights, torch.Tensor)
    assert output.shape[0] == 1  # One context item
    assert output.shape[1] == core_memory.config.hidden_size
    
    # Test with query
    output, weights = core_memory.process_context(query="test")
    assert isinstance(output, torch.Tensor)
    assert isinstance(weights, torch.Tensor)


def test_reset_context(core_memory):
    """Test resetting context."""
    metadata = MemoryMetadata(timestamp=datetime.now().timestamp())
    
    # Add content
    core_memory.add_to_context("test content", metadata)
    assert len(core_memory.current_context) == 1
    
    # Process to generate embeddings
    core_memory.process_context()
    assert core_memory.context_embeddings is not None
    
    # Reset
    core_memory.reset_context()
    assert len(core_memory.current_context) == 0
    assert core_memory.context_embeddings is None


def test_summarize_context(core_memory):
    """Test context summarization."""
    metadata = MemoryMetadata(timestamp=datetime.now().timestamp())
    
    # Test with empty context
    with pytest.raises(MemoryError):
        core_memory.summarize_context()
        
    # Add content and summarize
    core_memory.add_to_context("first content", metadata)
    core_memory.add_to_context("second content", metadata)
    
    summary = core_memory.summarize_context()
    assert isinstance(summary, str)
    assert len(summary) > 0
