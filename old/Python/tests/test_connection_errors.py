"""Tests for connection error handling."""

import pytest
import pytest_asyncio
import asyncio
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
async def test_venice_api_timeout_handling(librarian, mock_venice_client):
    """Test handling of Venice.ai API timeouts."""
    # Simulate API timeout
    mock_venice_client.store_memory = AsyncMock(side_effect=asyncio.TimeoutError)
    
    with pytest.raises(MemoryError) as exc_info:
        await librarian.store_memory(
            "timeout test content",
            MemoryMetadata(timestamp=datetime.now().timestamp())
        )
    
    assert "timeout" in str(exc_info.value).lower()
    
    # Verify system remains functional after timeout
    mock_venice_client.store_memory = AsyncMock(return_value=MemoryResponse(
        action="store_memory",
        success=True,
        memory_id="recovery_id"
    ))
    
    memory_id = await librarian.store_memory(
        "recovery test content",
        MemoryMetadata(timestamp=datetime.now().timestamp())
    )
    
    assert memory_id == "recovery_id"


@pytest.mark.asyncio
async def test_reconnection_strategies(librarian, mock_venice_client):
    """Test reconnection strategies after connection failures."""
    # Simulate connection failures with recovery
    failure_count = 0
    
    async def failing_store(*args, **kwargs):
        nonlocal failure_count
        if failure_count < 2:
            failure_count += 1
            raise ConnectionError("Connection failed")
        return MemoryResponse(
            action="store_memory",
            success=True,
            memory_id="reconnected_id"
        )
    
    mock_venice_client.store_memory = AsyncMock(side_effect=failing_store)
    
    # Should succeed after retries
    memory_id = await librarian.store_memory(
        "reconnection test content",
        MemoryMetadata(timestamp=datetime.now().timestamp())
    )
    
    assert memory_id == "reconnected_id"
    assert failure_count == 2  # Verified retries occurred


@pytest.mark.asyncio
async def test_data_consistency_during_failures(librarian, mock_venice_client):
    """Test data consistency during connection failures."""
    # Store initial data
    await librarian.store_memory(
        "initial content",
        MemoryMetadata(timestamp=datetime.now().timestamp())
    )
    
    # Simulate partial failure during batch operation
    batch_size = 5
    success_responses = [
        MemoryResponse(
            action="store_memory",
            success=True,
            memory_id=f"batch_{i}"
        )
        for i in range(batch_size)
    ]
    
    mock_venice_client.store_memory = AsyncMock(side_effect=[
        *success_responses[:3],
        ConnectionError("Connection lost"),
        *success_responses[3:]
    ])
    
    # Attempt batch operation
    batch_results = []
    for i in range(batch_size):
        try:
            memory_id = await librarian.store_memory(
                f"batch content {i}",
                MemoryMetadata(timestamp=datetime.now().timestamp())
            )
            batch_results.append(memory_id)
        except MemoryError:
            continue
    
    # Verify partial success handled properly
    assert len(batch_results) == 3  # First three succeeded
    assert all(id.startswith("batch_") for id in batch_results)


@pytest.mark.asyncio
async def test_error_recovery_sequence(librarian, mock_venice_client):
    """Test full error recovery sequence."""
    # Setup error sequence
    responses = [
        ConnectionError("Initial failure"),
        asyncio.TimeoutError(),
        MemoryResponse(
            action="store_memory",
            success=False,
            error="API Error"
        ),
        MemoryResponse(
            action="store_memory",
            success=True,
            memory_id="recovered_id"
        )
    ]
    
    mock_venice_client.store_memory = AsyncMock(side_effect=responses)
    
    # Attempt operation until success
    retry_count = 0
    memory_id = None
    
    while retry_count < len(responses):
        try:
            memory_id = await librarian.store_memory(
                "recovery sequence test",
                MemoryMetadata(timestamp=datetime.now().timestamp())
            )
            break
        except (MemoryError, ConnectionError, asyncio.TimeoutError):
            retry_count += 1
            await asyncio.sleep(0.1)  # Brief delay between retries
    
    assert memory_id == "recovered_id"
    assert retry_count == 3  # Verified all error types handled


@pytest.mark.asyncio
async def test_partial_response_handling(librarian, mock_venice_client):
    """Test handling of partial API responses."""
    # Simulate partial/malformed responses
    mock_venice_client.retrieve_context.side_effect = [
        MemoryResponse(
            action="retrieve_context",
            success=True,
            memories=None  # Missing memories
        ),
        MemoryResponse(
            action="retrieve_context",
            success=True,
            memories=[{
                "id": "partial_1",
                "content": "partial content",
                "metadata": None  # Missing metadata
            }]
        ),
        MemoryResponse(
            action="retrieve_context",
            success=True,
            memories=[{
                "id": "complete_1",
                "content": "complete content",
                "metadata": {
                    "timestamp": datetime.now().timestamp()
                }
            }]
        )
    ]
    
    # Test handling of missing memories
    memories = await librarian.retrieve_memories("test query")
    assert len(memories) == 0  # Safely handled None memories
    
    # Test handling of missing metadata
    memories = await librarian.retrieve_memories("test query")
    assert len(memories) == 1
    assert memories[0]["id"] == "partial_1"
    
    # Test complete response
    memories = await librarian.retrieve_memories("test query")
    assert len(memories) == 1
    assert memories[0]["id"] == "complete_1"
    assert "timestamp" in memories[0]["metadata"]
