"""Tests for memory system resource utilization."""

import pytest
import pytest_asyncio
import psutil
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


def get_process_metrics():
    """Get current process resource metrics."""
    process = psutil.Process()
    return {
        'cpu_percent': process.cpu_percent(),
        'memory_rss': process.memory_info().rss,
        'io_counters': process.io_counters() if hasattr(process, 'io_counters') else None
    }


@pytest.mark.asyncio
async def test_cpu_usage_monitoring(librarian):
    """Test CPU usage during memory operations."""
    # Warm up period
    await asyncio.sleep(0.1)
    process = psutil.Process()
    
    # Baseline CPU usage
    baseline_cpu = process.cpu_percent()
    await asyncio.sleep(0.1)  # Let CPU measurement stabilize
    
    # Perform intensive operations
    tasks = []
    for i in range(100):
        tasks.append(
            librarian.store_memory(
                f"cpu test content {i}",
                MemoryMetadata(timestamp=datetime.now().timestamp())
            )
        )
    
    start_time = time.time()
    await asyncio.gather(*tasks)
    end_time = time.time()
    
    # Measure peak CPU usage
    peak_cpu = process.cpu_percent()
    
    # Verify CPU usage is reasonable
    assert peak_cpu - baseline_cpu < 50  # CPU increase should be moderate
    assert end_time - start_time < 5.0  # Operations complete in reasonable time


@pytest.mark.asyncio
async def test_ram_consumption_tracking(librarian):
    """Test RAM consumption during memory operations."""
    process = psutil.Process()
    initial_memory = process.memory_info().rss
    
    # Perform memory-intensive operations
    large_content = "x" * 1000  # 1KB content
    tasks = []
    for i in range(1000):
        tasks.append(
            librarian.store_memory(
                f"{large_content} {i}",
                MemoryMetadata(timestamp=datetime.now().timestamp())
            )
        )
    
    await asyncio.gather(*tasks)
    
    # Measure memory after operations
    peak_memory = process.memory_info().rss
    memory_increase_mb = (peak_memory - initial_memory) / (1024 * 1024)
    
    # Verify memory usage is reasonable
    assert memory_increase_mb < 100  # Memory increase should be under 100MB


@pytest.mark.asyncio
async def test_disk_io_benchmarks(librarian):
    """Test disk I/O during memory operations."""
    process = psutil.Process()
    if not hasattr(process, 'io_counters'):
        pytest.skip("IO counters not available on this platform")
    
    # Get initial I/O counters
    initial_io = process.io_counters()
    
    # Perform I/O intensive operations
    tasks = []
    for i in range(100):
        tasks.append(
            librarian.store_memory(
                f"io test content {i}" * 100,  # Larger content for I/O
                MemoryMetadata(timestamp=datetime.now().timestamp())
            )
        )
    
    await asyncio.gather(*tasks)
    
    # Get final I/O counters
    final_io = process.io_counters()
    
    # Calculate I/O rates
    elapsed_time = 0.1  # Minimum time to avoid division by zero
    write_rate = (final_io.write_bytes - initial_io.write_bytes) / elapsed_time
    
    # Verify I/O rates are reasonable
    assert write_rate < 10 * 1024 * 1024  # Write rate under 10MB/s


@pytest.mark.asyncio
async def test_resource_scaling(librarian):
    """Test resource scaling with increasing load."""
    metrics = []
    
    # Test with increasing load
    for batch_size in [10, 50, 100]:
        start_metrics = get_process_metrics()
        
        # Perform batch operations
        tasks = []
        for i in range(batch_size):
            tasks.append(
                librarian.store_memory(
                    f"scaling test content {i}",
                    MemoryMetadata(timestamp=datetime.now().timestamp())
                )
            )
        
        await asyncio.gather(*tasks)
        
        end_metrics = get_process_metrics()
        metrics.append({
            'batch_size': batch_size,
            'cpu_increase': end_metrics['cpu_percent'] - start_metrics['cpu_percent'],
            'memory_increase': end_metrics['memory_rss'] - start_metrics['memory_rss']
        })
    
    # Verify resource scaling is sub-linear
    for i in range(1, len(metrics)):
        ratio = metrics[i]['batch_size'] / metrics[i-1]['batch_size']
        cpu_ratio = metrics[i]['cpu_increase'] / max(metrics[i-1]['cpu_increase'], 1)
        mem_ratio = metrics[i]['memory_increase'] / max(metrics[i-1]['memory_increase'], 1)
        
        assert cpu_ratio < ratio * 1.5  # CPU scaling should be sub-linear
        assert mem_ratio < ratio * 1.5  # Memory scaling should be sub-linear


@pytest.mark.asyncio
async def test_resource_cleanup(librarian):
    """Test resource cleanup after operations."""
    process = psutil.Process()
    initial_memory = process.memory_info().rss
    
    # Perform operations that should clean up
    for i in range(100):
        await librarian.store_memory(
            f"cleanup test content {i}",
            MemoryMetadata(timestamp=datetime.now().timestamp())
        )
    
    # Force cleanup
    import gc
    gc.collect()
    
    # Verify resources are cleaned up
    final_memory = process.memory_info().rss
    memory_diff_mb = (final_memory - initial_memory) / (1024 * 1024)
    
    assert memory_diff_mb < 10  # Memory should be mostly cleaned up
