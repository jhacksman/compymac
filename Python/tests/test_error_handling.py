"""Tests for error handling in the agent system."""

import pytest
from unittest.mock import MagicMock, AsyncMock
from typing import Dict

from ..agents.protocols import AgentRole, AgentMessage, TaskResult
from ..agents.manager import AgentManager
from ..memory import MemoryManager
from .test_agents.conftest import MockLLM

@pytest.fixture
def mock_llm():
    """Create mock LLM."""
    return MockLLM()

@pytest.fixture
def mock_memory_manager():
    """Create mock memory manager."""
    manager = MagicMock(spec=MemoryManager)
    manager.store_memory = AsyncMock()
    return manager

@pytest.fixture
def agent_manager(mock_memory_manager, mock_llm):
    """Create agent manager with mocks."""
    return AgentManager(memory_manager=mock_memory_manager, llm=mock_llm)

@pytest.mark.asyncio
async def test_retry_mechanism(mock_llm):
    """Test that tasks are retried up to 3 times before failing."""
    memory_manager = MagicMock(spec=MemoryManager)
    memory_manager.store_memory = AsyncMock()
    
    executor = MagicMock()
    executor.execute_task = AsyncMock(side_effect=[
        TaskResult(success=False, message="First attempt failed", artifacts={}),
        TaskResult(success=False, message="Second attempt failed", artifacts={}),
        TaskResult(success=True, message="Third attempt succeeded", artifacts={"result": "success"})
    ])
    
    manager = AgentManager(memory_manager=memory_manager, executor=executor, llm=mock_llm)
    
    task = {"type": "test", "action": "retry_test"}
    result = await manager.execute_task(task)
    
    assert result.success
    assert executor.execute_task.call_count == 3
    assert "succeeded" in result.message.lower()

@pytest.mark.asyncio
async def test_failure_after_max_retries(mock_llm):
    """Test that task fails after max retries (3 attempts)."""
    memory_manager = MagicMock(spec=MemoryManager)
    memory_manager.store_memory = AsyncMock()
    
    executor = MagicMock()
    executor.execute_task = AsyncMock(return_value=TaskResult(
        success=False,
        message="Task failed",
        artifacts={},
        error="Test error"
    ))
    
    manager = AgentManager(memory_manager=memory_manager, executor=executor, llm=mock_llm)
    
    task = {"type": "test", "action": "fail_test"}
    result = await manager.execute_task(task)
    
    assert not result.success
    assert executor.execute_task.call_count == 3
    assert "failed after 3 attempts" in result.message.lower()
    assert result.error == "Test error"

@pytest.mark.asyncio
async def test_error_message_formatting(mock_llm):
    """Test that error messages are properly formatted."""
    memory_manager = MagicMock(spec=MemoryManager)
    memory_manager.store_memory = AsyncMock()
    
    executor = MagicMock()
    executor.execute_task = AsyncMock(side_effect=Exception("Test exception"))
    
    manager = AgentManager(memory_manager=memory_manager, executor=executor, llm=mock_llm)
    
    task = {"type": "test", "action": "error_test"}
    result = await manager.execute_task(task)
    
    assert not result.success
    assert "failed" in result.message.lower()
    assert "test exception" in result.error.lower()

@pytest.mark.asyncio
async def test_task_result_reporting(mock_llm):
    """Test that task results are properly reported."""
    memory_manager = MagicMock(spec=MemoryManager)
    memory_manager.store_memory = AsyncMock()
    
    executor = MagicMock()
    executor.execute_task = AsyncMock(return_value=TaskResult(
        success=True,
        message="Task completed",
        artifacts={"result": "test"}
    ))
    
    manager = AgentManager(memory_manager=memory_manager, executor=executor, llm=mock_llm)
    
    task = {"type": "test", "action": "success_test"}
    result = await manager.execute_task(task)
    
    assert result.success
    assert "completed" in result.message.lower()
    assert result.artifacts["result"] == "test"
    assert memory_manager.store_memory.called
