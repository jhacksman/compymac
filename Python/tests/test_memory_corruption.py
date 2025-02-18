"""Tests for memory corruption handling."""

import pytest
import json
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
    """Create librarian fixture."""
    return LibrarianAgent(mock_venice_client)


def test_invalid_metadata_handling(librarian, mock_venice_client):
    """Test handling of invalid metadata."""
    # Test missing required fields
    with pytest.raises(MemoryError) as exc_info:
        librarian.store_memory(
            "test content",
            None  # Missing metadata
        )
    assert "metadata" in str(exc_info.value).lower()
    
    # Test invalid timestamp
    with pytest.raises(MemoryError) as exc_info:
        librarian.store_memory(
            "test content",
            MemoryMetadata(
                timestamp="invalid",  # Invalid timestamp
                tags=["test"]
            )
        )
    assert "timestamp" in str(exc_info.value).lower()
    
    # Test malformed metadata in response
    mock_venice_client.retrieve_context.return_value = MemoryResponse(
        action="retrieve_context",
        success=True,
        memories=[{
            "id": "test_id",
            "content": "test content",
            "metadata": "invalid"  # Invalid metadata format
        }]
    )
    
    memories = librarian.retrieve_memories("test query")
    assert len(memories) == 0  # Invalid memories filtered out


def test_corrupted_content_recovery(librarian, mock_venice_client):
    """Test recovery from corrupted content."""
    # Test handling of corrupted JSON content
    mock_venice_client.retrieve_context.return_value = MemoryResponse(
        action="retrieve_context",
        success=True,
        memories=[{
            "id": "test_id",
            "content": b"\x80invalid utf-8",  # Corrupted content
            "metadata": {
                "timestamp": datetime.now().timestamp()
            }
        }]
    )
    
    memories = librarian.retrieve_memories("test query")
    assert len(memories) == 0  # Corrupted content filtered
    
    # Test partial content corruption
    mock_venice_client.retrieve_context.return_value = MemoryResponse(
        action="retrieve_context",
        success=True,
        memories=[
            {
                "id": "valid_id",
                "content": "valid content",
                "metadata": {
                    "timestamp": datetime.now().timestamp()
                }
            },
            {
                "id": "corrupt_id",
                "content": None,  # Missing content
                "metadata": {
                    "timestamp": datetime.now().timestamp()
                }
            }
        ]
    )
    
    memories = librarian.retrieve_memories("test query")
    assert len(memories) == 1  # Only valid content retained
    assert memories[0]["id"] == "valid_id"


def test_index_rebuilding(librarian, mock_venice_client):
    """Test index rebuilding after corruption."""
    # Simulate index corruption by returning invalid index data
    mock_venice_client.retrieve_context.return_value = MemoryResponse(
        action="retrieve_context",
        success=False,
        error="Index corruption detected"
    )
    
    # Attempt retrieval with corrupted index
    memories = librarian.retrieve_memories("test query")
    assert len(memories) == 0
    
    # Verify system remains functional after index failure
    mock_venice_client.retrieve_context.return_value = MemoryResponse(
        action="retrieve_context",
        success=True,
        memories=[{
            "id": "new_id",
            "content": "recovered content",
            "metadata": {
                "timestamp": datetime.now().timestamp()
            }
        }]
    )
    
    memories = librarian.retrieve_memories("test query")
    assert len(memories) == 1
    assert memories[0]["content"] == "recovered content"


def test_metadata_sanitization(librarian):
    """Test metadata sanitization and validation."""
    # Test sanitization of malicious metadata
    metadata = MemoryMetadata(
        timestamp=datetime.now().timestamp(),
        tags=["<script>alert('xss')</script>"],  # Potentially malicious
        context_ids=["valid_context"]
    )
    
    memory_id = librarian.store_memory(
        "test content",
        metadata
    )
    
    assert memory_id == "test_id"
    stored = librarian.recent_memories[0]
    assert "<script>" not in stored["metadata"].tags[0]


def test_memory_repair(librarian, mock_venice_client):
    """Test memory repair mechanisms."""
    # Store initial valid memory
    initial_metadata = MemoryMetadata(
        timestamp=datetime.now().timestamp(),
        importance=0.8,
        tags=["test"]
    )
    
    librarian.store_memory(
        "initial content",
        initial_metadata
    )
    
    # Simulate memory corruption during update
    mock_venice_client.update_memory.side_effect = json.JSONDecodeError(
        "Invalid JSON",
        doc="corrupted",
        pos=0
    )
    
    # Attempt update with corrupted memory
    with pytest.raises(MemoryError) as exc_info:
        librarian.update_memory(
            "test_id",
            "updated content",
            initial_metadata
        )
    
    assert "corrupted" in str(exc_info.value).lower()
    
    # Verify original memory preserved
    assert librarian.recent_memories[0]["content"] == "initial content"
