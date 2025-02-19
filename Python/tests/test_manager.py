"""Tests for manager agent."""

import pytest
from unittest.mock import Mock, AsyncMock
from datetime import datetime

from ..agents import AgentManager
from ..agents.config import AgentConfig
from ..agents.protocols import TaskResult
from ..memory import MemoryManager

@pytest.fixture
def memory_manager():
    """Create mock memory manager."""
    manager = Mock(spec=MemoryManager)
    manager.store_memory = Mock()
    manager.retrieve_context = AsyncMock()
    return manager

@pytest.fixture
def manager_agent(memory_manager, mock_llm):
    """Create manager agent with mock memory manager and LLM."""
    return AgentManager(memory_manager, llm=mock_llm)

@pytest.mark.asyncio
async def test_execute_task_success(manager_agent):
    """Test successful task execution."""
    # Mock agent executor
    manager_agent.agent_executor.arun = AsyncMock(return_value={
        "output": "Task completed",
        "intermediate_steps": []
    })
    
    result = await manager_agent.execute_task("Test task")
    
    assert result.success
    assert "Task completed successfully" in result.message
    assert "result" in result.artifacts
    
    # Verify memory storage
    manager_agent.memory_manager.store_memory.assert_called_once()
    call_args = manager_agent.memory_manager.store_memory.call_args[1]
    assert call_args["metadata"]["type"] == "task_result"
    assert call_args["metadata"]["task"] == "Test task"

@pytest.mark.asyncio
async def test_execute_task_failure(manager_agent):
    """Test task execution failure."""
    # Mock agent executor to raise exception
    error_msg = "Test error"
    manager_agent.agent_executor.arun = AsyncMock(
        side_effect=Exception(error_msg)
    )
    
    result = await manager_agent.execute_task("Test task")
    
    assert not result.success
    assert error_msg in result.message
    assert error_msg == result.error
    
    # Verify error storage
    manager_agent.memory_manager.store_memory.assert_called_once()
    call_args = manager_agent.memory_manager.store_memory.call_args[1]
    assert call_args["metadata"]["type"] == "task_error"
    assert call_args["metadata"]["task"] == "Test task"

@pytest.mark.asyncio
async def test_tool_integration(manager_agent):
    """Test tool integration and usage."""
    # Mock tool responses
    manager_agent.planner.create_plan = Mock(return_value={
        "subtasks": ["step1", "step2"],
        "criteria": {"step1": "done"}
    })
    manager_agent.executor.execute_task = Mock(return_value=TaskResult(
        success=True,
        message="Executed",
        artifacts={}
    ))
    manager_agent.reflector.analyze_execution = Mock(return_value={
        "analysis": "Good",
        "recommendations": []
    })
    
    # Mock agent executor
    manager_agent.agent_executor.arun = AsyncMock(return_value={
        "output": "Task completed",
        "intermediate_steps": [
            ("plan_task", {"subtasks": ["step1"]}),
            ("execute_task", {"success": True})
        ]
    })
    
    result = await manager_agent.execute_task("Test task")
    
    assert result.success
    assert "Task completed successfully" in result.message
    
    # Verify memory storage includes tool usage
    manager_agent.memory_manager.store_memory.assert_called_once()
    call_args = manager_agent.memory_manager.store_memory.call_args[1]
    stored_content = call_args["content"]
    assert "Task completed" in stored_content
