"""Tests for memory system performance."""

import pytest
import pytest_asyncio
import asyncio
import time
from datetime import datetime
from unittest.mock import Mock, AsyncMock

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
    client.retrieve_context = AsyncMock(return_value=MemoryResponse(
        action="retrieve_context",
        success=True,
        memories=[]
    ))
    return client


@pytest_asyncio.fixture(scope="function")
async def librarian(mock_venice_client):
    """Create librarian fixture."""
    return LibrarianAgent(mock_venice_client)


@pytest.mark.asyncio
async def test_memory_retrieval_latency(librarian, mock_venice_client):
    """Test memory retrieval completes within 2 seconds."""
    # Setup test data
    mock_venice_client.retrieve_context.return_value = MemoryResponse(
        action="retrieve_context",
        success=True,
        memories=[{
            "id": f"test_{i}",
            "content": f"test content {i}",
            "metadata": {
                "timestamp": datetime.now().timestamp(),
                "importance": 0.8,
                "context_ids": []
            }
        } for i in range(100)]  # Test with 100 memories
    )
    
    # Measure retrieval time
    start_time = time.time()
    memories = await librarian.retrieve_memories("test query")
    end_time = time.time()
    
    retrieval_time = end_time - start_time
    assert retrieval_time < 2.0  # Must complete within 2 seconds
    assert len(memories) == 100


@pytest.mark.asyncio
async def test_batch_operation_performance(librarian):
    """Test performance of batch memory operations."""
    batch_size = 50
    start_time = time.time()
    
    # Perform batch storage
    for i in range(batch_size):
        await librarian.store_memory(
            f"batch content {i}",
            MemoryMetadata(timestamp=datetime.now().timestamp())
        )
    
    storage_time = time.time() - start_time
    operations_per_second = batch_size / storage_time
    
    assert operations_per_second >= 10  # At least 10 ops/second


@pytest.mark.asyncio
async def test_concurrent_operation_performance(librarian):
    """Test performance under concurrent operations."""
    # Create multiple concurrent operations
    operations = []
    for i in range(10):
        operations.append(
            librarian.store_memory(
                f"concurrent content {i}",
                MemoryMetadata(timestamp=datetime.now().timestamp())
            )
        )
    
    start_time = time.time()
    await asyncio.gather(*operations)
    concurrent_time = time.time() - start_time
    
    assert concurrent_time < 2.0  # Concurrent operations within 2 seconds


@pytest.mark.asyncio
async def test_memory_pruning_performance(librarian):
    """Test performance of memory pruning operations."""
    # Fill memory to trigger pruning
    start_time = time.time()
    
    for i in range(librarian.max_context_tokens):
        await librarian.store_memory(
            f"pruning test content {i}",
            MemoryMetadata(timestamp=datetime.now().timestamp())
        )
    
    pruning_time = time.time() - start_time
    assert pruning_time < 5.0  # Pruning should complete within 5 seconds
    assert len(librarian.recent_memories) <= librarian.max_context_tokens


@pytest.mark.asyncio
async def test_context_size_limits(librarian):
    """Test context size stays within limits."""
    # Add memories until we exceed the token limit
    for i in range(librarian.max_context_tokens + 10):
        await librarian.store_memory(
            f"context test content {i}",
            MemoryMetadata(timestamp=datetime.now().timestamp())
        )
    
    # Verify context size is maintained
    assert len(librarian.recent_memories) <= librarian.max_context_tokens
