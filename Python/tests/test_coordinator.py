"""Tests for memory coordinator."""

import json
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta

from ..memory.coordinator import MemoryCoordinator
from ..memory.manager import MemoryManager
from ..memory.venice_api import VeniceAPI
from ..memory.message_types import MemoryMetadata

@pytest.fixture
def memory_manager():
    """Create mock memory manager."""
    manager = MagicMock(spec=MemoryManager)
    manager.store_memory = MagicMock()
    manager.get_context = MagicMock(return_value={})
    manager.retrieve_context = MagicMock(return_value={})
    return manager

@pytest.fixture
def venice_api():
    """Create mock Venice.ai API client."""
    api = MagicMock(spec=VeniceAPI)
    api.store_memory = MagicMock()
    api.search_memories = MagicMock(return_value={})
    return api

@pytest.fixture
def coordinator(memory_manager, venice_api):
    """Create memory coordinator with mock dependencies."""
    return MemoryCoordinator(
        memory_manager=memory_manager,
        venice_api=venice_api
    )

def test_store_task_result_medium_term(coordinator):
    """Test storing task result in medium-term memory."""
    result = {"status": "success"}
    metadata = {"importance": 0.5}
    
    coordinator.store_task_result(result, metadata)
    
    # Verify stored in medium-term only
    coordinator.memory_manager.store_memory.assert_called_once()
    coordinator.venice_api.store_memory.assert_not_called()
    
    # Verify metadata
    call_args = coordinator.memory_manager.store_memory.call_args[1]
    stored_metadata = call_args["metadata"]
    assert "task_result" in stored_metadata.tags
    assert stored_metadata.importance == 0.5
    assert "timestamp" in stored_metadata

def test_store_task_result_long_term(coordinator):
    """Test storing important task result in long-term memory."""
    result = {"status": "success"}
    metadata = {"importance": 0.9}
    
    coordinator.store_task_result(result, metadata)
    
    # Verify stored in both tiers
    coordinator.memory_manager.store_memory.assert_called_once()
    coordinator.venice_api.store_memory.assert_called_once()
    
    # Verify Venice.ai metadata
    call_args = coordinator.venice_api.store_memory.call_args[1]
    stored_metadata = call_args["metadata"]
    assert "important_result" in stored_metadata.tags
    assert stored_metadata.importance == 0.9
    assert "timestamp" in stored_metadata

def test_snapshot_context(coordinator):
    """Test creating context snapshot."""
    context = {"key": "value"}
    coordinator.memory_manager.get_context.return_value = context
    
    snapshot = coordinator.snapshot_context()
    
    # Verify snapshot stored
    coordinator.memory_manager.store_memory.assert_called_once()
    
    # Verify snapshot content
    assert snapshot["context"] == context
    assert "context_snapshot" in snapshot["metadata"].tags
    assert "timestamp" in snapshot

def test_retrieve_context_medium_term(coordinator):
    """Test retrieving context from medium-term memory."""
    medium_term = {"result": "found"}
    coordinator.memory_manager.retrieve_context.return_value = medium_term
    
    result = coordinator.retrieve_context("test query")
    
    # Verify searched medium-term only
    coordinator.memory_manager.retrieve_context.assert_called_once()
    coordinator.venice_api.search_memories.assert_not_called()
    
    # Verify result
    assert result["medium_term"] == medium_term
    assert result["long_term"] == {}

def test_retrieve_context_long_term(coordinator):
    """Test retrieving context from long-term memory."""
    long_term = {"result": "found"}
    coordinator.memory_manager.retrieve_context.return_value = {}
    coordinator.venice_api.search_memories.return_value = long_term
    
    result = coordinator.retrieve_context("test query")
    
    # Verify searched both tiers
    coordinator.memory_manager.retrieve_context.assert_called_once()
    coordinator.venice_api.search_memories.assert_called_once()
    
    # Verify result
    assert result["medium_term"] == {}
    assert result["long_term"] == long_term

def test_retrieve_context_time_range(coordinator):
    """Test retrieving context with time range."""
    coordinator.retrieve_context("test", time_range="7d")
    
    # Verify time range passed
    coordinator.memory_manager.retrieve_context.assert_called_with(
        query="test",
        time_range="7d"
    )
