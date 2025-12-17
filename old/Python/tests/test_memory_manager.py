"""Tests for memory manager."""

import pytest
from unittest.mock import Mock, MagicMock
from datetime import datetime, timezone
from typing import Dict, List, Any

from ..memory.manager import MemoryManager
from ..memory.venice_api import VeniceAPI
from ..memory.exceptions import ContextWindowExceededError, VeniceAPIError
from ..memory.protocol import MemoryMessage

@pytest.fixture
def venice_api():
    """Create mock Venice API with synchronous methods."""
    client = Mock(spec=VeniceAPI)
    
    # Configure mock to return synchronous values
    client.store_memory.return_value = {
        "id": "test_id",
        "content": "test memory",
        "metadata": {"importance": "high"},
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    
    client.retrieve_context.return_value = [{
        "id": "test_id",
        "content": "test memory",
        "metadata": {"importance": "high"},
        "timestamp": datetime.now(timezone.utc).isoformat()
    }]
    
    client.update_memory.return_value = {
        "id": "test_id",
        "content": "updated memory",
        "metadata": {"importance": "high"},
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    
    return client

@pytest.fixture
def memory_manager(venice_api):
    return MemoryManager(venice_api, max_tokens=1000)

def test_store_memory_success(memory_manager, venice_api):
    """Test successful memory storage."""
    mock_memory = MemoryMessage.create(
        role="assistant",
        content="test memory",
        importance="high"
    )
    mock_memory["id"] = "test_id"
    venice_api.store_memory.return_value = mock_memory
    
    result = memory_manager.store_memory(
        "test memory",
        {"importance": "high"}
    )
    
    assert result == mock_memory
    assert memory_manager.context_window[-1] == mock_memory
    venice_api.store_memory.assert_called_once_with(
        "test memory",
        {"importance": "high"}
    )

def test_store_memory_with_task_id(memory_manager, venice_api):
    """Test memory storage with task ID."""
    mock_memory = {
        "id": "test_id",
        "content": "test memory",
        "metadata": {
            "importance": "high",
            "task_id": "task_123"
        },
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    venice_api.store_memory.return_value = mock_memory
    
    result = memory_manager.store_memory(
        "test memory",
        {"importance": "high"},
        task_id="task_123"
    )
    
    assert result == mock_memory
    venice_api.store_memory.assert_called_once_with(
        "test memory",
        {"importance": "high", "task_id": "task_123"}
    )

def test_retrieve_context_success(memory_manager, venice_api):
    """Test successful context retrieval."""
    mock_memories = [{
        "id": "test_id",
        "content": "test memory",
        "metadata": {"importance": "high"},
        "timestamp": datetime.now(timezone.utc).isoformat()
    }]
    venice_api.retrieve_context.return_value = mock_memories
    
    result = memory_manager.retrieve_context(
        "test query",
        task_id="task_123",
        time_range="1d"
    )
    
    assert result == mock_memories
    venice_api.retrieve_context.assert_called_once_with(
        "test query",
        {"task_id": "task_123", "time_range": "1d"}
    )

def test_update_memory_success(memory_manager, venice_api):
    """Test successful memory update."""
    mock_memory = {
        "id": "test_id",
        "content": "updated memory",
        "metadata": {"importance": "high"},
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    venice_api.update_memory.return_value = mock_memory
    
    # Add memory to context window
    memory_manager.context_window.append({
        "id": "test_id",
        "content": "old memory"
    })
    
    result = memory_manager.update_memory(
        "test_id",
        {"content": "updated memory"}
    )
    
    assert result == mock_memory
    assert memory_manager.context_window[-1] == mock_memory
    venice_api.update_memory.assert_called_once_with(
        "test_id",
        {"content": "updated memory"}
    )

def test_delete_memory_success(memory_manager, venice_api):
    """Test successful memory deletion."""
    # Add memory to context window
    memory_manager.context_window.append({
        "id": "test_id",
        "content": "test memory"
    })
    
    memory_manager.delete_memory("test_id")
    
    assert len(memory_manager.context_window) == 0
    venice_api.delete_memory.assert_called_once_with("test_id")

def test_context_window_pruning(memory_manager, venice_api):
    """Test context window pruning when limit exceeded."""
    # Create a memory that will exceed token limit
    long_content = "x" * 4000  # Will be ~1000 tokens
    mock_memory = {
        "id": "test_id",
        "content": long_content,
        "metadata": {"importance": "high"},
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    venice_api.store_memory.return_value = mock_memory
    
    # Add some memories to context window
    memory_manager.context_window = [
        {"id": "old_1", "content": "old memory 1"},
        {"id": "old_2", "content": "old memory 2"}
    ]
    
    result = memory_manager.store_memory(
        long_content,
        {"importance": "high"}
    )
    
    assert result == mock_memory
    assert len(memory_manager.context_window) == 1
    assert memory_manager.context_window[0] == mock_memory
