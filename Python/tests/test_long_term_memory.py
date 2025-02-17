"""Tests for long-term memory management."""

import pytest
import time
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock

from memory.long_term_memory import LongTermMemoryManager
from memory.protocol import MessageMetadata
from memory.venice_api import VeniceAPI

@pytest.fixture
def mock_venice_api():
    api = Mock(spec=VeniceAPI)
    api.store_memory = AsyncMock(return_value="test_id")
    api.retrieve_context = AsyncMock(return_value=["test_id"])
    return api

@pytest.fixture
def memory_manager(mock_venice_api):
    return LongTermMemoryManager(mock_venice_api)

@pytest.mark.asyncio
async def test_store_memory_basic(memory_manager):
    """Test basic memory storage."""
    content = "Test memory content"
    metadata = MessageMetadata(
        timestamp=time.time(),
        importance=0.5,
        context_ids=["test_context"]
    )
    
    memory_id = await memory_manager.store_memory(content, metadata)
    
    assert memory_id == "test_id"
    assert memory_id in memory_manager._memories
    assert memory_manager._memories[memory_id].content == content
    assert memory_manager._memories[memory_id].metadata == metadata

@pytest.mark.asyncio
async def test_store_memory_with_context(memory_manager):
    """Test storing memory with context associations."""
    content = "Test memory with context"
    metadata = MessageMetadata(timestamp=time.time())
    context_ids = ["context1", "context2"]
    
    memory_id = await memory_manager.store_memory(
        content,
        metadata,
        context_ids=context_ids
    )
    
    # Verify context indexing
    for context_id in context_ids:
        assert memory_id in memory_manager._context_index[context_id]

@pytest.mark.asyncio
async def test_retrieve_context_basic(memory_manager):
    """Test basic context retrieval."""
    # Store a test memory first
    content = "Test retrievable content"
    metadata = MessageMetadata(timestamp=time.time())
    await memory_manager.store_memory(content, metadata)
    
    # Retrieve with basic query
    memories = await memory_manager.retrieve_context("test query")
    
    assert len(memories) == 1
    assert memories[0].content == content

@pytest.mark.asyncio
async def test_retrieve_context_with_time_range(memory_manager):
    """Test context retrieval with time filtering."""
    # Store an old memory
    old_content = "Old memory"
    old_metadata = MessageMetadata(
        timestamp=time.time() - 60*60*24*2  # 2 days ago
    )
    await memory_manager.store_memory(old_content, old_metadata)
    
    # Store a new memory
    new_content = "New memory"
    new_metadata = MessageMetadata(timestamp=time.time())
    await memory_manager.store_memory(new_content, new_metadata)
    
    # Retrieve with 1 day time range
    memories = await memory_manager.retrieve_context(
        "test",
        time_range=timedelta(days=1)
    )
    
    assert len(memories) == 1
    assert memories[0].content == new_content

@pytest.mark.asyncio
async def test_importance_calculation(memory_manager):
    """Test memory importance scoring."""
    content = "Important test content" * 10  # Longer content
    metadata = MessageMetadata(
        timestamp=time.time(),
        importance=0.8,
        context_ids=["ctx1", "ctx2", "ctx3"]
    )
    
    memory_id = await memory_manager.store_memory(content, metadata)
    memory = memory_manager._memories[memory_id]
    
    # Score should reflect high importance, multiple contexts
    assert memory.importance_score > 0.7

@pytest.mark.asyncio
async def test_retrieve_context_with_limit(memory_manager):
    """Test context retrieval with result limiting."""
    # Store multiple memories
    for i in range(5):
        content = f"Memory {i}"
        metadata = MessageMetadata(timestamp=time.time())
        await memory_manager.store_memory(content, metadata)
    
    # Retrieve with limit
    memories = await memory_manager.retrieve_context("test", limit=3)
    
    assert len(memories) <= 3
