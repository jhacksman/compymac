"""Tests for manager agent."""
import pytest
import json
from unittest.mock import Mock, AsyncMock
from datetime import datetime

from agents.manager import AgentManager
from memory.message_types import MemoryMetadata

@pytest.fixture
def memory_manager():
    """Create mock memory manager."""
    manager = Mock()
    manager.store_memory = AsyncMock()
    manager.retrieve_memories = AsyncMock(return_value=[])
    return manager

@pytest.fixture
def manager_agent(memory_manager, mock_llm):
    """Create manager agent with mock memory manager and LLM."""
    return AgentManager(memory_manager, llm=mock_llm)

@pytest.mark.asyncio
async def test_delegate_task(manager_agent):
    """Test task delegation to appropriate agent."""
    # Set mock LLM response
    manager_agent.llm._response = {
        "agent": "executor",
        "task": "Execute test task",
        "parameters": {"priority": "high"}
    }
    
    result = await manager_agent.delegate_task("Test task")
    
    assert result["success"]
    assert result["agent"] == "executor"
    assert "task" in result

@pytest.mark.asyncio
async def test_coordinate_agents(manager_agent):
    """Test agent coordination."""
    # Set mock LLM response for coordination
    manager_agent.llm._response = {
        "coordination_plan": [
            {"agent": "planner", "action": "create_plan"},
            {"agent": "executor", "action": "execute_task"}
        ],
        "success": True
    }
    
    result = await manager_agent.coordinate_agents(
        ["planner", "executor"],
        "Test coordination"
    )
    
    assert result["success"]
    assert len(result["coordination_plan"]) == 2
