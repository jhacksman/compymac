"""Tests for persistent memory module."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock

from memory.persistent.memory import PersistentMemory
from memory.persistent.config import PersistentMemoryConfig
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
def persistent_memory(mock_venice_client):
    """Create persistent memory fixture."""
    config = PersistentMemoryConfig(
        memory_chunk_size=3  # Small size for testing
    )
    return PersistentMemory(config, mock_venice_client)


def test_store_knowledge_basic(persistent_memory):
    """Test basic knowledge storage."""
    metadata = MemoryMetadata(timestamp=datetime.now().timestamp())
    
    memory_id = persistent_memory.store_knowledge(
        "test content",
        metadata
    )
    
    assert memory_id == "test_id"
    assert len(persistent_memory.memory_chunks) == 1
    assert len(persistent_memory.memory_chunks[0]) == 1
    assert persistent_memory.memory_chunks[0][0]["content"] == "test content"


def test_store_knowledge_with_task(persistent_memory):
    """Test knowledge storage with task context."""
    metadata = MemoryMetadata(timestamp=datetime.now().timestamp())
    task_id = 123
    
    memory_id = persistent_memory.store_knowledge(
        "test content",
        metadata,
        task_id=task_id
    )
    
    assert memory_id == "test_id"
    stored_memory = persistent_memory.memory_chunks[0][0]
    assert stored_memory["task_id"] == task_id
    assert "task_123" in stored_memory["metadata"].context_ids


def test_store_knowledge_with_surprise(persistent_memory):
    """Test knowledge storage with surprise score."""
    metadata = MemoryMetadata(
        timestamp=datetime.now().timestamp(),
        importance=0.3
    )
    
    memory_id = persistent_memory.store_knowledge(
        "surprising content",
        metadata,
        surprise_score=0.8
    )
    
    assert memory_id == "test_id"
    stored_memory = persistent_memory.memory_chunks[0][0]
    assert stored_memory["content"] == "surprising content"


def test_store_knowledge_chunks(persistent_memory):
    """Test knowledge storage with chunking."""
    metadata = MemoryMetadata(timestamp=datetime.now().timestamp())
    
    # Fill first chunk
    for i in range(3):
        persistent_memory.store_knowledge(
            f"content {i}",
            metadata
        )
        
    # Add one more to create new chunk
    persistent_memory.store_knowledge("overflow content", metadata)
    
    assert len(persistent_memory.memory_chunks) == 2
    assert len(persistent_memory.memory_chunks[0]) == 3
    assert len(persistent_memory.memory_chunks[1]) == 1
    assert persistent_memory.memory_chunks[1][0]["content"] == "overflow content"


def test_retrieve_knowledge_basic(persistent_memory, mock_venice_client):
    """Test basic knowledge retrieval."""
    # Setup mock response for basic retrieval
    mock_venice_client.retrieve_context.side_effect = None  # Clear any previous side effects
    mock_venice_client.retrieve_context.return_value = MemoryResponse(
        action="retrieve_context",
        success=True,
        memories=[{
            "id": "test_id",
            "content": "test content",
            "metadata": {
                "timestamp": datetime.now().timestamp(),
                "importance": 0.5
            }
        }]
    )
    
    # Store and retrieve
    metadata = MemoryMetadata(timestamp=datetime.now().timestamp())
    persistent_memory.store_knowledge("test content", metadata)
    
    memories = persistent_memory.retrieve_knowledge("test query")
    
    assert len(memories) == 1
    assert memories[0]["content"] == "test content"


def test_retrieve_knowledge_with_importance(persistent_memory, mock_venice_client):
    """Test knowledge retrieval with importance filter."""
    # Setup mock response
    mock_venice_client.retrieve_context.side_effect = None  # Clear any previous side effects
    mock_venice_client.retrieve_context.return_value = MemoryResponse(
        action="retrieve_context",
        success=True,
        memories=[
            {
                "id": "test_1",
                "content": "important content",
                "metadata": {
                    "timestamp": datetime.now().timestamp(),
                    "importance": 0.8,
                    "context_ids": []
                }
            },
            {
                "id": "test_2",
                "content": "less important content",
                "metadata": {
                    "timestamp": datetime.now().timestamp(),
                    "importance": 0.3,
                    "context_ids": []
                }
            }
        ]
    )
    
    # Retrieve with importance filter
    memories = persistent_memory.retrieve_knowledge(
        "test query",
        min_importance=0.5
    )
    
    assert len(memories) == 1
    assert memories[0]["content"] == "important content"


def test_retrieve_knowledge_with_task(persistent_memory, mock_venice_client):
    """Test knowledge retrieval with task context."""
    task_id = 123
    metadata = MemoryMetadata(timestamp=datetime.now().timestamp())
    
    # Setup mock response for task-based retrieval
    mock_venice_client.retrieve_context.side_effect = None  # Clear any previous side effects
    mock_venice_client.retrieve_context.return_value = MemoryResponse(
        action="retrieve_context",
        success=True,
        memories=[{
            "id": "test_id",
            "content": "task-specific content",
            "metadata": {
                "timestamp": datetime.now().timestamp(),
                "importance": 0.8,
                "context_ids": [f"task_{task_id}"],
                "task_id": task_id
            }
        }]
    )
    
    # Store with task context
    persistent_memory.store_knowledge(
        "task-specific content",
        metadata,
        task_id=task_id
    )
    
    # Retrieve with task context
    memories = persistent_memory.retrieve_knowledge(
        "test query",
        task_id=task_id
    )
    
    assert len(memories) == 1
