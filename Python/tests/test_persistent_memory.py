"""Tests for persistent memory module."""

import pytest
import pytest_asyncio
import torch
from datetime import datetime
from unittest.mock import Mock, AsyncMock

from memory.persistent.memory import PersistentMemory
from memory.persistent.config import PersistentMemoryConfig
from memory.message_types import MemoryMetadata, MemoryResponse
from memory.venice_client import VeniceClient
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
    client.retrieve_context = AsyncMock(return_value=MemoryResponse(
        action="retrieve_context",
        success=True,
        memories=[]  # No memories by default
    ))
    return client


@pytest_asyncio.fixture(scope="function")
async def persistent_memory(mock_venice_client):
    """Create persistent memory fixture."""
    config = PersistentMemoryConfig(
        hidden_size=32,  # Small size for tests
        intermediate_size=64,
        num_attention_heads=2,
        max_position_embeddings=4,
        task_embedding_size=32,  # Match hidden size
        max_tasks=5,
        memory_chunk_size=2
    )
    memory = PersistentMemory(config, mock_venice_client)
    yield memory
    # Cleanup
    memory.memory_chunks.clear()
    del memory.knowledge_transform
    del memory.knowledge_attention
    torch.cuda.empty_cache()


@pytest.mark.asyncio
async def test_store_knowledge_basic(persistent_memory):
    """Test basic knowledge storage."""
    metadata = MemoryMetadata(timestamp=datetime.now().timestamp())
    
    knowledge_id = await persistent_memory.store_knowledge(
        "test knowledge",
        metadata
    )
    
    assert knowledge_id == "test_id"
    assert len(persistent_memory.memory_chunks) == 1
    assert len(persistent_memory.memory_chunks[0]) == 1
    assert persistent_memory.memory_chunks[0][0]["content"] == "test knowledge"


@pytest.mark.asyncio
async def test_store_knowledge_with_task(persistent_memory):
    """Test knowledge storage with task context."""
    metadata = MemoryMetadata(timestamp=datetime.now().timestamp())
    task_id = 1
    
    knowledge_id = await persistent_memory.store_knowledge(
        "task knowledge",
        metadata,
        task_id=task_id
    )
    
    assert knowledge_id == "test_id"
    assert persistent_memory.memory_chunks[0][0]["task_id"] == task_id


@pytest.mark.asyncio
async def test_store_knowledge_chunks(persistent_memory):
    """Test knowledge storage with chunking."""
    metadata = MemoryMetadata(timestamp=datetime.now().timestamp())
    
    # Add knowledge entries up to chunk size
    for i in range(3):  # Should create 2 chunks
        await persistent_memory.store_knowledge(
            f"knowledge {i}",
            metadata
        )
        
    assert len(persistent_memory.memory_chunks) == 2
    assert len(persistent_memory.memory_chunks[0]) == 2  # First chunk full
    assert len(persistent_memory.memory_chunks[1]) == 1  # Second chunk partial


@pytest.mark.asyncio
async def test_retrieve_knowledge_basic(persistent_memory, mock_venice_client):
    """Test basic knowledge retrieval."""
    # Setup mock response
    mock_venice_client.retrieve_context = AsyncMock(
        return_value=MemoryResponse(
            action="retrieve_context",
            success=True,
            memories=[{
                "id": "test_id",
                "content": "test knowledge",
                "metadata": {
                    "timestamp": datetime.now().timestamp()
                }
            }]
        )
    )
    
    memories = await persistent_memory.retrieve_knowledge("test query")
    
    assert len(memories) == 1
    assert memories[0]["content"] == "test knowledge"


@pytest.mark.asyncio
async def test_retrieve_knowledge_with_task(
    persistent_memory,
    mock_venice_client
):
    """Test knowledge retrieval with task context."""
    # Setup mock response
    mock_venice_client.retrieve_context = AsyncMock(
        return_value=MemoryResponse(
            action="retrieve_context",
            success=True,
            memories=[{
                "id": "test_id_1",
                "content": "task knowledge 1",
                "metadata": {
                    "timestamp": datetime.now().timestamp()
                }
            }, {
                "id": "test_id_2",
                "content": "task knowledge 2",
                "metadata": {
                    "timestamp": datetime.now().timestamp()
                }
            }]
        )
    )
    
    memories = await persistent_memory.retrieve_knowledge(
        "test query",
        task_id=1
    )
    
    assert len(memories) == 2
    assert all("task knowledge" in m["content"] for m in memories)


def test_get_task_embedding(persistent_memory):
    """Test task embedding generation."""
    task_id = 2
    embedding = persistent_memory.get_task_embedding(task_id)
    
    assert isinstance(embedding, torch.Tensor)
    assert embedding.shape == (1, persistent_memory.config.task_embedding_size)
    
    # Test invalid task ID
    with pytest.raises(MemoryError):
        persistent_memory.get_task_embedding(100)  # Invalid ID


def test_memory_chunk_access(persistent_memory):
    """Test memory chunk access."""
    # Add test chunks
    persistent_memory.memory_chunks = [[
        {
            "id": "test_1",
            "content": "chunk 1 content"
        }
    ], [
        {
            "id": "test_2",
            "content": "chunk 2 content"
        }
    ]]
    
    chunk = persistent_memory._get_memory_chunk(0)
    assert len(chunk) == 1
    assert chunk[0]["content"] == "chunk 1 content"
    
    # Test invalid chunk index
    with pytest.raises(MemoryError):
        persistent_memory._get_memory_chunk(100)
