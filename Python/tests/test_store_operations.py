"""Tests for memory store operations."""

import pytest
from datetime import datetime

from memory.message_types import MemoryMetadata, MemoryResponse
from memory.venice_client import VeniceClient
from memory.librarian import LibrarianAgent
from memory.exceptions import MemoryError


def test_store_basic_memory(librarian):
    """Test basic memory storage."""
    content = "test content"
    metadata = MemoryMetadata(
        timestamp=datetime.now().timestamp(),
        importance=0.5,
        tags=["test"]
    )
    
    memory_id = librarian.store_memory(content, metadata)
    
    assert memory_id is not None
    assert len(librarian.recent_memories) == 1
    stored = librarian.recent_memories[0]
    assert stored["content"] == content
    assert stored["metadata"]["importance"] == 0.5
    assert "test" in stored["metadata"]["tags"]


def test_store_memory_with_surprise(librarian):
    """Test memory storage with surprise-based filtering."""
    content = "surprising content"
    metadata = MemoryMetadata(
        timestamp=datetime.now().timestamp(),
        importance=0.3
    )
    
    memory_id = librarian.store_memory(
        content,
        metadata,
        surprise_score=0.8
    )
    
    assert memory_id is not None
    stored = librarian.recent_memories[0]
    assert stored["metadata"]["importance"] >= 0.8  # Importance updated by surprise


def test_store_memory_error_handling(librarian):
    """Test error handling during memory storage."""
    with pytest.raises(MemoryError) as exc_info:
        librarian.store_memory(
            "test content",
            MemoryMetadata(timestamp=None)  # Invalid timestamp
        )
    
    assert "Invalid timestamp format" in str(exc_info.value)


def test_store_memory_context_window(librarian):
    """Test context window management during storage."""
    # Fill context window
    for i in range(librarian.max_context_tokens // 4 + 1):
        librarian.store_memory(
            f"content {i}",
            MemoryMetadata(timestamp=datetime.now().timestamp())
        )
    
    # Verify oldest memory was pruned
    assert len(librarian.recent_memories) == librarian.max_context_tokens // 4
    assert "content 0" not in [m["content"] for m in librarian.recent_memories]
    assert f"content {librarian.max_context_tokens // 4}" in [
        m["content"] for m in librarian.recent_memories
    ]
