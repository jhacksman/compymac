"""Tests for librarian agent."""

import pytest
import time
from datetime import datetime, timedelta
from unittest.mock import Mock

from memory.librarian import LibrarianAgent
from memory.message_types import MemoryMetadata, MemoryResponse
from memory.venice_client import VeniceClient
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
    client.retrieve_context.return_value = MemoryResponse(
        action="retrieve_context",
        success=True,
        memories=[]
    )
    return client


@pytest.fixture(scope="function")
def librarian(mock_venice_client):
    """Create librarian agent fixture."""
    return LibrarianAgent(mock_venice_client)


@pytest.mark.asyncio
async def test_store_memory_basic(librarian):
    """Test basic memory storage."""
    metadata = MemoryMetadata(timestamp=datetime.now().timestamp())
    
    memory_id = await librarian.store_memory(
        "test content",
        metadata
    )
    
    assert memory_id == "test_id"
    assert len(librarian.recent_memories) == 1
    assert librarian.recent_memories[0]["content"] == "test content"


@pytest.mark.asyncio
async def test_store_memory_with_surprise(librarian):
    """Test memory storage with surprise-based filtering."""
    metadata = MemoryMetadata(
        timestamp=datetime.now().timestamp(),
        importance=0.3
    )
    
    # Store with high surprise score
    memory_id = await librarian.store_memory(
        "surprising content",
        metadata,
        surprise_score=0.8
    )
    
    assert memory_id == "test_id"
    assert librarian.recent_memories[0]["metadata"].importance == 0.8


@pytest.mark.asyncio
async def test_retrieve_memories_basic(librarian, mock_venice_client):
    """Test basic memory retrieval."""
    # Setup mock response
    mock_venice_client.retrieve_context.return_value = MemoryResponse(
        action="retrieve_context",
        success=True,
        memories=[{
            "id": "test_id",
            "content": "test content",
            "metadata": {
                "timestamp": time.time(),
                "importance": 0.5
            }
        }]
    )
    
    # Retrieve memories
    memories = await librarian.retrieve_memories("test query")
    
    assert len(memories) == 1
    assert memories[0]["content"] == "test content"


@pytest.mark.asyncio
async def test_retrieve_memories_with_importance(librarian, mock_venice_client):
    """Test memory retrieval with importance filtering."""
    # Setup mock response with varying importance
    mock_venice_client.retrieve_context.return_value = MemoryResponse(
        action="retrieve_context",
        success=True,
        memories=[
            {
                "id": "test_1",
                "content": "important content",
                "metadata": {
                    "timestamp": time.time(),
                    "importance": 0.8
                }
            },
            {
                "id": "test_2",
                "content": "less important content",
                "metadata": {
                    "timestamp": time.time(),
                    "importance": 0.3
                }
            }
        ]
    )
    
    # Retrieve with importance filter
    memories = await librarian.retrieve_memories(
        "test query",
        min_importance=0.5
    )
    
    assert len(memories) == 1
    assert memories[0]["content"] == "important content"


@pytest.mark.asyncio
async def test_retrieve_memories_with_time_range(librarian, mock_venice_client):
    """Test memory retrieval with time filtering."""
    now = time.time()
    old_time = now - 60*60*24*2  # 2 days ago
    
    # Setup mock response with varying timestamps
    mock_venice_client.retrieve_context.return_value = MemoryResponse(
        action="retrieve_context",
        success=True,
        memories=[
            {
                "id": "test_1",
                "content": "new content",
                "metadata": {
                    "timestamp": now,
                    "importance": 0.5
                }
            },
            {
                "id": "test_2",
                "content": "old content",
                "metadata": {
                    "timestamp": old_time,
                    "importance": 0.5
                }
            }
        ]
    )
    
    # Retrieve with time range
    memories = await librarian.retrieve_memories(
        "test query",
        time_range=timedelta(days=1)
    )
    
    assert len(memories) == 1
    assert memories[0]["content"] == "new content"


@pytest.mark.asyncio
async def test_get_recent_memories(librarian):
    """Test getting recent memories."""
    # Add some test memories
    now = time.time()
    librarian.recent_memories = [
        {
            "id": "test_1",
            "content": "content 1",
            "metadata": {
                "timestamp": now,
                "importance": 0.8
            }
        },
        {
            "id": "test_2",
            "content": "content 2",
            "metadata": {
                "timestamp": now,
                "importance": 0.3
            }
        }
    ]
    
    # Get with importance filter
    memories = await librarian.get_recent_memories(min_importance=0.5)
    assert len(memories) == 1
    assert memories[0]["content"] == "content 1"
    
    # Get with limit
    memories = await librarian.get_recent_memories(limit=1)
    assert len(memories) == 1
    assert memories[0]["content"] == "content 2"
