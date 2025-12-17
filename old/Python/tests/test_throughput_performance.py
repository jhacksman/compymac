"""Tests for memory system throughput performance."""

import pytest
import time
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


def test_memory_operations_per_minute(librarian):
    """Test memory operations per minute throughput."""
    operation_count = 100
    start_time = time.time()
    
    # Perform rapid memory operations
    for i in range(operation_count):
        librarian.store_memory(
            f"throughput test content {i}",
            MemoryMetadata(timestamp=datetime.now().timestamp())
        )
    
    end_time = time.time()
    
    elapsed_time = end_time - start_time
    operations_per_minute = (operation_count / elapsed_time) * 60
    
    assert operations_per_minute >= 600  # At least 10 ops/second


def test_concurrent_operation_handling(librarian):
    """Test handling of concurrent memory operations."""
    start_time = time.time()
    results = []
    
    # Storage operations
    for i in range(20):
        result = librarian.store_memory(
            f"concurrent store {i}",
            MemoryMetadata(timestamp=datetime.now().timestamp())
        )
        results.append(result)
    
    # Retrieval operations
    for i in range(20):
        result = librarian.retrieve_memories(f"concurrent query {i}")
        results.append(result)
    
    end_time = time.time()
    total_time = end_time - start_time
    
    assert total_time < 4.0  # All operations complete within 4 seconds
    assert len(results) == 40  # All operations completed


def test_queue_management(librarian):
    """Test memory operation queue management."""
    queue_size = 50
    batch_size = 10
    
    start_time = time.time()
    
    # Process in controlled batches
    for i in range(0, queue_size, batch_size):
        for j in range(batch_size):
            if i + j < queue_size:
                librarian.store_memory(
                    f"queue test content {i+j}",
                    MemoryMetadata(timestamp=datetime.now().timestamp())
                )
    
    end_time = time.time()
    total_time = end_time - start_time
    
    assert total_time < 10.0  # Batch processing completes in reasonable time


def test_sustained_throughput(librarian):
    """Test sustained throughput over time."""
    duration = 5  # Test for 5 seconds
    start_time = time.time()
    operation_count = 0
    
    while time.time() - start_time < duration:
        librarian.store_memory(
            f"sustained test content {operation_count}",
            MemoryMetadata(timestamp=datetime.now().timestamp())
        )
        operation_count += 1
    
    operations_per_second = operation_count / duration
    assert operations_per_second >= 10  # Maintain minimum throughput


def test_mixed_operation_throughput(librarian, mock_venice_client):
    """Test throughput with mixed operation types."""
    # Setup test data
    mock_venice_client.retrieve_context.return_value = MemoryResponse(
        action="retrieve_context",
        success=True,
        memories=[{
            "id": "test_id",
            "content": "test content",
            "metadata": {
                "timestamp": datetime.now().timestamp(),
                "importance": 0.8
            }
        }]
    )
    
    operation_count = 50
    start_time = time.time()
    
    # Mix of different operations
    for i in range(operation_count):
        if i % 3 == 0:
            # Store operation
            librarian.store_memory(
                f"mixed test content {i}",
                MemoryMetadata(timestamp=datetime.now().timestamp())
            )
        elif i % 3 == 1:
            # Retrieve operation
            librarian.retrieve_memories(f"mixed query {i}")
        else:
            # Update operation
            librarian.update_memory(
                "test_id",
                f"updated content {i}",
                MemoryMetadata(timestamp=datetime.now().timestamp())
            )
    
    end_time = time.time()
    total_time = end_time - start_time
    operations_per_second = operation_count / total_time
    
    assert operations_per_second >= 10  # Maintain throughput with mixed operations
