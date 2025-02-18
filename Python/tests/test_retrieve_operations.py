"""Tests for memory retrieve operations."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock

from memory.message_types import MemoryMetadata, MemoryResponse
from memory.venice_client import VeniceClient
from memory.librarian import LibrarianAgent
from memory.exceptions import MemoryError


@pytest_asyncio.fixture(scope="function")
async def mock_venice_client():
    """Create mock Venice client."""
    client = Mock(spec=VeniceClient)
    client.retrieve_context = AsyncMock(return_value=MemoryResponse(
        action="retrieve_context",
        success=True,
        memories=[{
            "id": "test_id",
            "content": "test content",
            "metadata": {
                "timestamp": datetime.now().timestamp(),
                "importance": 0.8,
                "context_ids": []
            }
        }]
    ))
    return client


@pytest_asyncio.fixture(scope="function")
async def librarian(mock_venice_client):
    """Create librarian fixture."""
    return LibrarianAgent(mock_venice_client)


def test_basic_memory_retrieval(librarian):
    """Test basic memory retrieval."""
    query = "test query"
    memories = librarian.retrieve_memories(query)
    
    assert len(memories) == 1
    assert memories[0]["content"] == "test content"
    assert memories[0]["metadata"]["importance"] == 0.8


def test_hybrid_retrieval(librarian, mock_venice_client):
    """Test hybrid retrieval with vector and time-based filtering."""
    now = datetime.now()
    old_time = now - timedelta(days=2)
    
    # Setup mock response with multiple memories
    mock_venice_client.retrieve_context.return_value = MemoryResponse(
        action="retrieve_context",
        success=True,
        memories=[
            {
                "id": "recent_important",
                "content": "recent important content",
                "metadata": {
                    "timestamp": now.timestamp(),
                    "importance": 0.9,
                    "context_ids": []
                }
            },
            {
                "id": "old_important",
                "content": "old important content",
                "metadata": {
                    "timestamp": old_time.timestamp(),
                    "importance": 0.8,
                    "context_ids": []
                }
            }
        ]
    )
    
    # Test retrieval with time range
    memories = librarian.retrieve_memories(
        "test query",
        time_range=timedelta(days=1)
    )
    
    assert len(memories) == 1
    assert memories[0]["id"] == "recent_important"
    
    # Test retrieval with importance
    memories = librarian.retrieve_memories(
        "test query",
        min_importance=0.85
    )
    
    assert len(memories) == 1
    assert memories[0]["id"] == "recent_important"


def test_context_based_retrieval(librarian, mock_venice_client):
    """Test retrieval with context filtering."""
    context_id = "task_123"
    
    # Setup mock response with context-specific memories
    mock_venice_client.retrieve_context.return_value = MemoryResponse(
        action="retrieve_context",
        success=True,
        memories=[{
            "id": "context_specific",
            "content": "context specific content",
            "metadata": {
                "timestamp": datetime.now().timestamp(),
                "importance": 0.7,
                "context_ids": [context_id]
            }
        }]
    )
    
    memories = librarian.retrieve_memories(
        "test query",
        context_id=context_id
    )
    
    assert len(memories) == 1
    assert memories[0]["id"] == "context_specific"
    assert context_id in memories[0]["metadata"]["context_ids"]


def test_retrieval_error_handling(librarian, mock_venice_client):
    """Test error handling during retrieval."""
    mock_venice_client.retrieve_context.return_value = MemoryResponse(
        action="retrieve_context",
        success=False,
        error="API Error"
    )
    
    with pytest.raises(MemoryError) as exc_info:
        librarian.retrieve_memories("test query")
    
    assert "Failed to retrieve memories" in str(exc_info.value)


def test_empty_retrieval_results(librarian, mock_venice_client):
    """Test handling of empty retrieval results."""
    mock_venice_client.retrieve_context.return_value = MemoryResponse(
        action="retrieve_context",
        success=True,
        memories=[]
    )
    
    memories = librarian.retrieve_memories("test query")
    
    assert len(memories) == 0
