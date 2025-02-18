"""Tests for memory store operations."""

import pytest
import pytest_asyncio
from datetime import datetime
from unittest.mock import Mock, AsyncMock

from memory.message_types import MemoryMetadata, MemoryResponse
from memory.venice_client import VeniceClient
from memory.librarian import LibrarianAgent
from memory.exceptions import MemoryError


@pytest_asyncio.fixture(scope="function")
async def mock_venice_client():
    """Create mock Venice client."""
    client = Mock(spec=VeniceClient)
    client.store_memory = AsyncMock(return_value=MemoryResponse(
        action="store_memory",
        success=True,
        memory_id="test_id"
    ))
    return client


@pytest_asyncio.fixture(scope="function")
async def librarian(mock_venice_client):
    """Create librarian fixture."""
    return LibrarianAgent(mock_venice_client)


@pytest.mark.asyncio
async def test_store_basic_memory(librarian):
    """Test basic memory storage."""
    content = "test content"
    metadata = MemoryMetadata(
        timestamp=datetime.now().timestamp(),
        importance=0.5,
        tags=["test"]
    )
    
    memory_id = await librarian.store_memory(content, metadata)
    
    assert memory_id == "test_id"
    assert len(librarian.recent_memories) == 1
    stored = librarian.recent_memories[0]
    assert stored["content"] == content
    assert stored["metadata"].importance == 0.5
    assert "test" in stored["metadata"].tags


@pytest.mark.asyncio
async def test_store_memory_with_surprise(librarian):
    """Test memory storage with surprise-based filtering."""
    content = "surprising content"
    metadata = MemoryMetadata(
        timestamp=datetime.now().timestamp(),
        importance=0.3
    )
    
    memory_id = await librarian.store_memory(
        content,
        metadata,
        surprise_score=0.8
    )
    
    assert memory_id == "test_id"
    stored = librarian.recent_memories[0]
    assert stored["metadata"].importance >= 0.8  # Importance updated by surprise


@pytest.mark.asyncio
async def test_store_memory_error_handling(librarian, mock_venice_client):
    """Test error handling during memory storage."""
    mock_venice_client.store_memory.return_value = MemoryResponse(
        action="store_memory",
        success=False,
        error="API Error"
    )
    
    with pytest.raises(MemoryError) as exc_info:
        await librarian.store_memory(
            "test content",
            MemoryMetadata(timestamp=datetime.now().timestamp())
        )
    
    assert "Failed to store memory" in str(exc_info.value)


@pytest.mark.asyncio
async def test_store_memory_context_window(librarian):
    """Test context window management during storage."""
    # Fill context window
    for i in range(librarian.max_context_tokens // 4 + 1):
        await librarian.store_memory(
            f"content {i}",
            MemoryMetadata(timestamp=datetime.now().timestamp())
        )
    
    # Verify oldest memory was pruned
    assert len(librarian.recent_memories) == librarian.max_context_tokens // 4
    assert "content 0" not in [m["content"] for m in librarian.recent_memories]
    assert f"content {librarian.max_context_tokens // 4}" in [
        m["content"] for m in librarian.recent_memories
    ]
