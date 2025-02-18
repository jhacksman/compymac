"""Tests for persistent memory module."""

import pytest
import pytest_asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock

from memory.persistent.memory import PersistentMemory
from memory.persistent.config import PersistentMemoryConfig
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
    
    # Return test memory for task-based retrieval
    async def mock_retrieve_context(**kwargs):
        context_id = kwargs.get("context_id")
        query = kwargs.get("query", "")
        
        # Default test memory
        test_memory = {
            "id": "test_id",
            "content": "test content",
            "metadata": {
                "timestamp": datetime.now().timestamp(),
                "importance": 0.5,
                "context_ids": []
            }
        }
        
        # Task-specific memory
        if context_id and context_id.startswith("task_"):
            task_id = int(context_id.split("_")[1])
            test_memory.update({
                "content": "task-specific content",
                "metadata": {
                    "timestamp": datetime.now().timestamp(),
                    "importance": 0.5,
                    "context_ids": [f"task_{task_id}"],
                    "task_id": task_id
                }
            })
            
        return MemoryResponse(
            action="retrieve_context",
            success=True,
            memories=[test_memory]
        )
    
    client.retrieve_context = AsyncMock(side_effect=mock_retrieve_context)
    return client


@pytest_asyncio.fixture(scope="function")
async def persistent_memory(mock_venice_client):
    """Create persistent memory fixture."""
    config = PersistentMemoryConfig(
        memory_chunk_size=3  # Small size for testing
    )
    return PersistentMemory(config, mock_venice_client)


@pytest.mark.asyncio
async def test_store_knowledge_basic(persistent_memory):
    """Test basic knowledge storage."""
    metadata = MemoryMetadata(timestamp=datetime.now().timestamp())
    
    memory_id = await persistent_memory.store_knowledge(
        "test content",
        metadata
    )
    
    assert memory_id == "test_id"
    assert len(persistent_memory.memory_chunks) == 1
    assert len(persistent_memory.memory_chunks[0]) == 1
    assert persistent_memory.memory_chunks[0][0]["content"] == "test content"


@pytest.mark.asyncio
async def test_store_knowledge_with_task(persistent_memory):
    """Test knowledge storage with task context."""
    metadata = MemoryMetadata(timestamp=datetime.now().timestamp())
    task_id = 123
    
    memory_id = await persistent_memory.store_knowledge(
        "test content",
        metadata,
        task_id=task_id
    )
    
    assert memory_id == "test_id"
    stored_memory = persistent_memory.memory_chunks[0][0]
    assert stored_memory["task_id"] == task_id
    assert "task_123" in stored_memory["metadata"].context_ids


@pytest.mark.asyncio
async def test_store_knowledge_with_surprise(persistent_memory):
    """Test knowledge storage with surprise score."""
    metadata = MemoryMetadata(
        timestamp=datetime.now().timestamp(),
        importance=0.3
    )
    
    memory_id = await persistent_memory.store_knowledge(
        "surprising content",
        metadata,
        surprise_score=0.8
    )
    
    assert memory_id == "test_id"
    stored_memory = persistent_memory.memory_chunks[0][0]
    assert stored_memory["content"] == "surprising content"


@pytest.mark.asyncio
async def test_store_knowledge_chunks(persistent_memory):
    """Test knowledge storage with chunking."""
    metadata = MemoryMetadata(timestamp=datetime.now().timestamp())
    
    # Fill first chunk
    for i in range(3):
        await persistent_memory.store_knowledge(
            f"content {i}",
            metadata
        )
        
    # Add one more to create new chunk
    await persistent_memory.store_knowledge("overflow content", metadata)
    
    assert len(persistent_memory.memory_chunks) == 2
    assert len(persistent_memory.memory_chunks[0]) == 3
    assert len(persistent_memory.memory_chunks[1]) == 1
    assert persistent_memory.memory_chunks[1][0]["content"] == "overflow content"


@pytest.mark.asyncio
async def test_retrieve_knowledge_basic(persistent_memory, mock_venice_client):
    """Test basic knowledge retrieval."""
    # Setup mock response
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
    await persistent_memory.store_knowledge("test content", metadata)
    
    memories = await persistent_memory.retrieve_knowledge("test query")
    
    assert len(memories) == 1
    assert memories[0]["content"] == "test content"


@pytest.mark.asyncio
async def test_retrieve_knowledge_with_importance(persistent_memory, mock_venice_client):
    """Test knowledge retrieval with importance filter."""
    # Setup mock response
    mock_venice_client.retrieve_context.return_value = MemoryResponse(
        action="retrieve_context",
        success=True,
        memories=[
            {
                "id": "test_1",
                "content": "important content",
                "metadata": {
                    "timestamp": datetime.now().timestamp(),
                    "importance": 0.8
                }
            },
            {
                "id": "test_2",
                "content": "less important content",
                "metadata": {
                    "timestamp": datetime.now().timestamp(),
                    "importance": 0.3
                }
            }
        ]
    )
    
    # Retrieve with importance filter
    memories = await persistent_memory.retrieve_knowledge(
        "test query",
        min_importance=0.5
    )
    
    assert len(memories) == 1
    assert memories[0]["content"] == "important content"


@pytest.mark.asyncio
async def test_retrieve_knowledge_with_task(persistent_memory, mock_venice_client):
    """Test knowledge retrieval with task context."""
    task_id = 123
    metadata = MemoryMetadata(timestamp=datetime.now().timestamp())
    
    # Store with task context
    await persistent_memory.store_knowledge(
        "task-specific content",
        metadata,
        task_id=task_id
    )
    
    # Retrieve with task context
    memories = await persistent_memory.retrieve_knowledge(
        "test query",
        task_id=task_id
    )
    
    assert len(memories) == 1
