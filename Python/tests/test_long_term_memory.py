"""Tests for long-term memory module."""

import pytest
import pytest_asyncio
import time
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock

from memory.long_term_memory import LongTermMemory, LongTermMemoryConfig
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
        memory_id="test_id"  # Fixed ID for tests
    ))
    client.retrieve_context = AsyncMock(return_value=MemoryResponse(
        action="retrieve_context",
        success=True,
        memories=[]  # No memories by default
    ))
    return client


@pytest_asyncio.fixture(scope="function")
async def long_term_memory(mock_venice_client):
    """Create long-term memory fixture."""
    config = LongTermMemoryConfig(
        max_memories=5,  # Even smaller for tests
        summary_threshold=3,
        context_window_size=2
    )
    memory = LongTermMemory(config, mock_venice_client)
    yield memory
    # Cleanup
    memory.recent_context.clear()


@pytest.mark.asyncio
async def test_store_memory_basic(long_term_memory):
    """Test basic memory storage."""
    metadata = MemoryMetadata(timestamp=datetime.now().timestamp())
    
    memory_id = await long_term_memory.store_memory(
        "test content",
        metadata
    )
    
    assert memory_id == "test_id"
    assert len(long_term_memory.recent_context) == 1
    assert long_term_memory.recent_context[0]["content"] == "test content"


@pytest.mark.asyncio
async def test_store_memory_with_summarization(long_term_memory):
    """Test memory storage with context summarization."""
    metadata = MemoryMetadata(timestamp=datetime.now().timestamp())
    
    # Add memories up to window size
    for i in range(3):  # Reduced test size
        await long_term_memory.store_memory(
            f"content {i}",
            metadata
        )
        
    assert len(long_term_memory.recent_context) == 2  # Window size
    assert long_term_memory.recent_context[-1]["content"] == "content 2"


@pytest.mark.asyncio
async def test_retrieve_context_basic(long_term_memory):
    """Test basic context retrieval."""
    # Store a test memory first
    content = "Test retrievable content"
    metadata = MemoryMetadata(timestamp=time.time())
    await long_term_memory.store_memory(content, metadata)
    
    # Retrieve with basic query
    memories = await long_term_memory.retrieve_context("test query")
    
    assert len(memories) == 1
    assert memories[0]["content"] == content


@pytest.mark.asyncio
async def test_retrieve_context_with_time_range(long_term_memory):
    """Test context retrieval with time filtering."""
    # Store an old memory
    old_content = "Old memory"
    old_metadata = MemoryMetadata(
        timestamp=time.time() - 60*60*24*2  # 2 days ago
    )
    await long_term_memory.store_memory(old_content, old_metadata)
    
    # Store a new memory
    new_content = "New memory"
    new_metadata = MemoryMetadata(timestamp=time.time())
    await long_term_memory.store_memory(new_content, new_metadata)
    
    # Retrieve with 1 day time range
    memories = await long_term_memory.retrieve_context(
        "test",
        time_range=timedelta(days=1)
    )
    
    assert len(memories) == 1
    assert memories[0]["content"] == new_content


@pytest.mark.asyncio
async def test_importance_calculation(long_term_memory):
    """Test memory importance scoring."""
    content = "Important test content" * 10  # Longer content
    metadata = MemoryMetadata(
        timestamp=time.time(),
        importance=0.8,
        context_ids=["ctx1", "ctx2", "ctx3"]
    )
    
    await long_term_memory.store_memory(content, metadata)
    
    # Verify memory was stored
    assert len(long_term_memory.recent_context) > 0
    stored_memory = long_term_memory.recent_context[-1]
    assert stored_memory["content"] == content


@pytest.mark.asyncio
async def test_retrieve_context_with_limit(long_term_memory):
    """Test context retrieval with result limiting."""
    # Store multiple memories
    for i in range(5):
        content = f"Memory {i}"
        metadata = MemoryMetadata(timestamp=time.time())
        await long_term_memory.store_memory(content, metadata)
    
    # Retrieve with limit
    memories = await long_term_memory.retrieve_context("test", limit=3)
    
    assert len(memories) <= 3
