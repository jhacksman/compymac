"""Tests for core memory module."""

import pytest
import pytest_asyncio
from datetime import datetime

from memory.core_memory import CoreMemory, CoreMemoryConfig
from memory.message_types import MemoryMetadata, MemoryResponse
from memory.exceptions import MemoryError
from memory.venice_client import VeniceClient
from unittest.mock import Mock


@pytest.fixture
def mock_venice_client():
    """Create mock Venice client."""
    client = Mock(spec=VeniceClient)
    
    # Mock store_memory response
    client.store_memory.return_value = MemoryResponse(
        action="store_memory",
        success=True,
        memory_id="test_id"
    )
    
    # Mock retrieve_context response
    client.retrieve_context.return_value = MemoryResponse(
        action="retrieve_context",
        success=True,
        memories=[]
    )
    
    # Mock stream_memory to return an iterable
    def mock_stream_memory(*args, **kwargs):
        return iter(["Test summary chunk 1", "Test summary chunk 2"])
    client.stream_memory.side_effect = mock_stream_memory
    
    return client


@pytest_asyncio.fixture
async def core_memory(mock_venice_client, mock_memory_db):
    """Create core memory fixture."""
    config = CoreMemoryConfig(
        context_size=4,  # Small size for testing
        window_size=2
    )
    memory = CoreMemory(config, mock_venice_client, mock_memory_db)
    return memory


@pytest.mark.asyncio
async def test_core_memory_initialization(core_memory):
    """Test core memory initialization."""
    assert len(core_memory.current_context) == 0
    assert hasattr(core_memory, 'venice_client')


@pytest.mark.asyncio
async def test_add_to_context(core_memory):
    """Test adding content to context."""
    metadata = MemoryMetadata(timestamp=datetime.now().timestamp())
    
    # Add content
    await core_memory.add_to_context("test content", metadata)
    assert len(core_memory.current_context) == 1
    assert core_memory.current_context[0]["content"] == "test content"
    
    # Add more content
    await core_memory.add_to_context("more content", metadata)
    assert len(core_memory.current_context) == 2
    
    # Test context size limit
    for _ in range(2):
        await core_memory.add_to_context("content", metadata)
        
    with pytest.raises(MemoryError):
        await core_memory.add_to_context("overflow", metadata)


@pytest.mark.asyncio
async def test_get_context_window(core_memory):
    """Test getting context window."""
    metadata = MemoryMetadata(timestamp=datetime.now().timestamp())
    
    # Add some content
    for i in range(3):
        await core_memory.add_to_context(f"content {i}", metadata)
        
    # Get full context
    context = await core_memory.get_context_window()
    assert len(context) == 2  # Limited by window_size
    
    # Get limited window
    context = await core_memory.get_context_window(window_size=1)
    assert len(context) == 1
    assert context[-1]["content"] == "content 2"


@pytest.mark.asyncio
async def test_process_context(core_memory, mock_venice_client):
    """Test processing context through Venice.ai API."""
    metadata = MemoryMetadata(timestamp=datetime.now().timestamp())
    
    # Test with empty context
    with pytest.raises(MemoryError):
        await core_memory.process_context()
        
    # Add content and process
    await core_memory.add_to_context("test content", metadata)
    memories = await core_memory.process_context()
    
    assert isinstance(memories, list)
    
    # Test with query
    mock_venice_client.retrieve_context.return_value = MemoryResponse(
        action="retrieve_context",
        success=True,
        memories=[{
            "id": "test_id",
            "content": "test content",
            "metadata": metadata
        }]
    )
    
    memories = await core_memory.process_context(query="test")
    assert len(memories) == 1
    assert memories[0]["content"] == "test content"


@pytest.mark.asyncio
async def test_reset_context(core_memory):
    """Test resetting context."""
    metadata = MemoryMetadata(timestamp=datetime.now().timestamp())
    
    # Add content
    await core_memory.add_to_context("test content", metadata)
    assert len(core_memory.current_context) == 1
    
    # Reset
    await core_memory.reset_context()
    assert len(core_memory.current_context) == 0


@pytest.mark.asyncio
async def test_summarize_context(core_memory):
    """Test context summarization."""
    metadata = MemoryMetadata(timestamp=datetime.now().timestamp())
    
    # Test with empty context
    with pytest.raises(MemoryError):
        await core_memory.summarize_context()
        
    # Add content and summarize
    await core_memory.add_to_context("first content", metadata)
    await core_memory.add_to_context("second content", metadata)
    
    summary = await core_memory.summarize_context()
    assert isinstance(summary, str)
    assert len(summary) > 0
