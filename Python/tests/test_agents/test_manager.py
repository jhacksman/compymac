"""Tests for agent manager."""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from typing import Dict, List, Optional

from ...agents import AgentManager
from ...agents.executor import ExecutorAgent
from ...agents.planner import PlannerAgent
from ...agents.reflector import ReflectorAgent
from ...agents.protocols import AgentRole, AgentMessage, TaskResult
from ...memory import MemoryManager

from .conftest import memory_manager, mock_llm

@pytest.fixture
def agent_manager(memory_manager, mock_llm):
    """Create agent manager with mock dependencies."""
    executor = ExecutorAgent(memory_manager=memory_manager, llm=mock_llm)
    planner = PlannerAgent(memory_manager=memory_manager, llm=mock_llm)
    reflector = ReflectorAgent(memory_manager=memory_manager, llm=mock_llm)
    return AgentManager(
        memory_manager=memory_manager,
        executor=executor,
        planner=planner,
        reflector=reflector
    )

@pytest.mark.asyncio
async def test_delegate_task(agent_manager):
    """Test task delegation to appropriate agent."""
    task = {
        "type": "research",
        "query": "test query",
        "context": {}
    }
    
    result = await agent_manager.delegate_task(task)
    
    assert result.success
    assert "task completed" in result.message.lower()
    
    # Verify memory storage
    assert agent_manager.memory_manager.store_memory.call_count >= 1
    call_args = agent_manager.memory_manager.store_memory.call_args[1]
    assert call_args["metadata"]["type"] == "task_delegation"

@pytest.mark.asyncio
async def test_handle_agent_message(agent_manager):
    """Test handling messages between agents."""
    message = AgentMessage(
        sender=AgentRole.EXECUTOR,
        recipient=AgentRole.PLANNER,
        content="test message",
        metadata={"importance": 0.5}
    )
    
    result = await agent_manager.handle_message(message)
    
    assert result.success
    assert "message delivered" in result.message.lower()
    
    # Verify memory storage
    assert agent_manager.memory_manager.store_memory.call_count >= 1
    call_args = agent_manager.memory_manager.store_memory.call_args[1]
    assert call_args["metadata"]["type"] == "agent_message"

@pytest.mark.asyncio
async def test_coordinate_agents(agent_manager):
    """Test agent coordination for complex tasks."""
    task = {
        "type": "complex_task",
        "subtasks": [
            {"type": "research", "query": "test"},
            {"type": "execute", "action": "test"}
        ],
        "context": {}
    }
    
    result = await agent_manager.coordinate_task(task)
    
    assert result.success
    assert "task completed" in result.message.lower()
    
    # Verify memory storage
    assert agent_manager.memory_manager.store_memory.call_count >= 2
    call_args = agent_manager.memory_manager.store_memory.call_args_list[0][1]
    assert call_args["metadata"]["type"] == "task_coordination"
