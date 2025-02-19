"""Tests for memory update operations."""

import pytest
from datetime import datetime
from unittest.mock import Mock

from memory.message_types import MemoryMetadata, MemoryResponse
from memory.venice_client import VeniceClient
from memory.librarian import LibrarianAgent
from memory.exceptions import MemoryError


@pytest.fixture(scope="function")
def mock_venice_client():
    """Create mock Venice client."""
    client = Mock(spec=VeniceClient)
    client.update_memory.return_value = MemoryResponse(
        action="update_memory",
        success=True,
        memory_id="test_id"
    )
    return client


@pytest.fixture(scope="function")
def librarian(mock_venice_client):
    """Create librarian fixture."""
    return LibrarianAgent(mock_venice_client)


@pytest.mark.asyncio
async def test_update_memory_content(librarian, mock_venice_client):
    """Test updating memory content."""
    # First store a memory
    original_content = "original content"
    metadata = MemoryMetadata(timestamp=datetime.now().timestamp())
    memory_id = await librarian.store_memory(original_content, metadata)
    
    # Update the content
    updated_content = "updated content"
    await librarian.update_memory(
        memory_id,
        content=updated_content,
        metadata=metadata
    )
    
    # Verify update in recent memories
    updated = next(
        (m for m in librarian.recent_memories if m["id"] == memory_id),
        None
    )
    assert updated is not None
    assert updated["content"] == updated_content


@pytest.mark.asyncio
async def test_update_memory_metadata(librarian, mock_venice_client):
    """Test updating memory metadata."""
    # Store initial memory
    content = "test content"
    initial_metadata = MemoryMetadata(
        timestamp=datetime.now().timestamp(),
        importance=0.5,
        tags=["initial"]
    )
    memory_id = await librarian.store_memory(content, initial_metadata)
    
    # Update metadata
    updated_metadata = MemoryMetadata(
        timestamp=datetime.now().timestamp(),
        importance=0.8,
        tags=["updated"]
    )
    await librarian.update_memory(
        memory_id,
        content=content,
        metadata=updated_metadata
    )
    
    # Verify metadata update
    updated = next(
        (m for m in librarian.recent_memories if m["id"] == memory_id),
        None
    )
    assert updated is not None
    assert updated["metadata"].importance == 0.8
    assert "updated" in updated["metadata"].tags


@pytest.mark.asyncio
async def test_update_memory_error_handling(librarian, mock_venice_client):
    """Test error handling during memory updates."""
    mock_venice_client.update_memory.return_value = MemoryResponse(
        action="update_memory",
        success=False,
        error="API Error"
    )
    
    with pytest.raises(MemoryError) as exc_info:
        await librarian.update_memory(
            "test_id",
            content="test content",
            metadata=MemoryMetadata(timestamp=datetime.now().timestamp())
        )
    
    assert "Failed to update memory" in str(exc_info.value)


@pytest.mark.asyncio
async def test_update_nonexistent_memory(librarian, mock_venice_client):
    """Test updating a nonexistent memory."""
    mock_venice_client.update_memory.return_value = MemoryResponse(
        action="update_memory",
        success=False,
        error="Memory not found"
    )
    
    with pytest.raises(MemoryError) as exc_info:
        await librarian.update_memory(
            "nonexistent_id",
            content="test content",
            metadata=MemoryMetadata(timestamp=datetime.now().timestamp())
        )
    
    assert "Memory not found" in str(exc_info.value)


@pytest.mark.asyncio
async def test_update_memory_context_window(librarian, mock_venice_client):
    """Test context window management during updates."""
    # Fill context window
    memories = []
    for i in range(librarian.max_context_tokens // 4):
        memory_id = await librarian.store_memory(
            f"content {i}",
            MemoryMetadata(timestamp=datetime.now().timestamp())
        )
        memories.append(memory_id)
    
    # Update last memory
    last_memory_id = memories[-1]
    await librarian.update_memory(
        last_memory_id,
        content="updated content",
        metadata=MemoryMetadata(timestamp=datetime.now().timestamp())
    )
    
    # Verify context window maintained
    assert len(librarian.recent_memories) == librarian.max_context_tokens // 4
    updated = next(
        (m for m in librarian.recent_memories if m["id"] == last_memory_id),
        None
    )
    assert updated is not None
    assert updated["content"] == "updated content"
