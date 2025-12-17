"""Tests for memory prune operations."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock

from memory.message_types import MemoryMetadata, MemoryResponse
from memory.venice_client import VeniceClient
from memory.librarian import LibrarianAgent
from memory.exceptions import MemoryError


@pytest.fixture(scope="function")
def mock_venice_client():
    """Create mock Venice client."""
    client = Mock(spec=VeniceClient)
    client.store_memory.return_value = MemoryResponse(
        action="store_memory",
        success=True,
        memory_id="test_id"
    )
    client.delete_memory.return_value = MemoryResponse(
        action="delete_memory",
        success=True
    )
    return client


@pytest.fixture(scope="function")
def librarian(mock_venice_client):
    """Create librarian fixture."""
    agent = LibrarianAgent(mock_venice_client)
    agent.max_context_tokens = 1000  # Smaller size for testing
    return agent


def test_automatic_memory_pruning(librarian):
    """Test automatic pruning of old memories."""
    # Fill context window
    now = datetime.now()
    old_time = now - timedelta(days=7)
    
    # Add old memories
    for i in range(5):
        librarian.store_memory(
            f"old content {i}",
            MemoryMetadata(
                timestamp=old_time.timestamp(),
                importance=0.3
            )
        )
    
    # Add recent important memories
    for i in range(5):
        librarian.store_memory(
            f"important content {i}",
            MemoryMetadata(
                timestamp=now.timestamp(),
                importance=0.8
            )
        )
    
    # Add more memories to trigger pruning
    for i in range(librarian.max_context_tokens // 4):
        librarian.store_memory(
            f"new content {i}",
            MemoryMetadata(timestamp=now.timestamp())
        )
    
    # Verify old, unimportant memories were pruned first
    remaining_contents = [m["content"] for m in librarian.recent_memories]
    assert not any("old content" in content for content in remaining_contents)
    assert any("important content" in content for content in remaining_contents)


def test_context_window_size_limits(librarian):
    """Test enforcement of context window size limits."""
    now = datetime.now()
    
    # Fill context window to exactly the limit
    for i in range(librarian.max_context_tokens // 4):
        librarian.store_memory(
            f"content {i}",
            MemoryMetadata(timestamp=now.timestamp())
        )
    
    initial_size = len(librarian.recent_memories)
    assert initial_size == librarian.max_context_tokens // 4
    
    # Add one more memory
    librarian.store_memory(
        "overflow content",
        MemoryMetadata(timestamp=now.timestamp())
    )
    
    # Verify size maintained and oldest memory removed
    assert len(librarian.recent_memories) == initial_size
    assert "content 0" not in [m["content"] for m in librarian.recent_memories]
    assert "overflow content" in [m["content"] for m in librarian.recent_memories]


def test_importance_based_pruning(librarian):
    """Test that important memories are preserved during pruning."""
    now = datetime.now()
    
    # Add important memories
    important_ids = []
    for i in range(5):
        memory_id = librarian.store_memory(
            f"important content {i}",
            MemoryMetadata(
                timestamp=now.timestamp(),
                importance=0.9
            )
        )
        important_ids.append(memory_id)
    
    # Fill remaining space with less important memories
    for i in range(librarian.max_context_tokens // 4):
        librarian.store_memory(
            f"regular content {i}",
            MemoryMetadata(
                timestamp=now.timestamp(),
                importance=0.3
            )
        )
    
    # Verify important memories retained
    remaining_memories = librarian.recent_memories
    assert all(
        any(m["id"] == imp_id for m in remaining_memories)
        for imp_id in important_ids
    )


def test_memory_consolidation(librarian, mock_venice_client):
    """Test memory consolidation during pruning."""
    now = datetime.now()
    
    # Add related memories
    librarian.store_memory(
        "Python is a programming language",
        MemoryMetadata(
            timestamp=now.timestamp(),
            tags=["python", "programming"]
        )
    )
    
    librarian.store_memory(
        "Python uses indentation for blocks",
        MemoryMetadata(
            timestamp=now.timestamp(),
            tags=["python", "syntax"]
        )
    )
    
    # Trigger consolidation by filling context
    for i in range(librarian.max_context_tokens // 4):
        librarian.store_memory(
            f"filler content {i}",
            MemoryMetadata(timestamp=now.timestamp())
        )
    
    # Verify consolidated memory preserved
    remaining_memories = librarian.recent_memories
    python_memories = [
        m for m in remaining_memories
        if "python" in m.get("metadata", {}).get("tags", [])
    ]
    assert len(python_memories) > 0


def test_pruning_error_handling(librarian, mock_venice_client):
    """Test error handling during memory pruning."""
    # Setup mock to fail deletion
    mock_venice_client.delete_memory.return_value = MemoryResponse(
        action="delete_memory",
        success=False,
        error="API Error"
    )
    
    # Fill context window
    now = datetime.now()
    for i in range(librarian.max_context_tokens // 4 + 1):
        librarian.store_memory(
            f"content {i}",
            MemoryMetadata(timestamp=now.timestamp())
        )
    
    # Verify system remains functional despite pruning errors
    assert len(librarian.recent_memories) <= librarian.max_context_tokens // 4
