"""Tests for planner agent."""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from typing import Dict, List, Optional

from ...agents.planner import PlannerAgent
from ...agents.protocols import AgentRole, AgentMessage, TaskResult
from ...memory import MemoryManager

from .conftest import memory_manager, mock_llm

@pytest.fixture
def planner_agent(memory_manager, mock_llm):
    """Create planner agent with mock dependencies."""
    return PlannerAgent(memory_manager=memory_manager, llm=mock_llm)

@pytest.mark.asyncio
async def test_create_plan(planner_agent):
    """Test plan creation for task."""
    task = {
        "type": "research",
        "query": "test query",
        "context": {}
    }
    
    result = await planner_agent.create_plan(task)
    
    assert result.success
    assert "plan created" in result.message.lower()
    assert "steps" in result.artifacts
    
    # Verify memory storage
    planner_agent.memory_manager.store_memory.assert_called_once()
    call_args = planner_agent.memory_manager.store_memory.call_args[1]
    assert call_args["metadata"]["type"] == "plan_creation"

@pytest.mark.asyncio
async def test_handle_feedback(planner_agent):
    """Test handling feedback from other agents."""
    feedback = AgentMessage(
        sender=AgentRole.EXECUTOR,
        recipient=AgentRole.PLANNER,
        content="step 1 failed",
        metadata={"step_id": 1}
    )
    
    result = await planner_agent.handle_feedback(feedback)
    
    assert result.success
    assert "plan updated" in result.message.lower()
    assert "revised_steps" in result.artifacts
    
    # Verify memory storage
    planner_agent.memory_manager.store_memory.assert_called_once()
    call_args = planner_agent.memory_manager.store_memory.call_args[1]
    assert call_args["metadata"]["type"] == "plan_revision"

@pytest.mark.asyncio
async def test_validate_plan(planner_agent):
    """Test plan validation."""
    plan = {
        "steps": [
            {"id": 1, "action": "test"},
            {"id": 2, "action": "verify"}
        ],
        "success_criteria": {
            "all_steps_complete": True
        }
    }
    
    result = await planner_agent.validate_plan(plan)
    
    assert result.success
    assert "plan valid" in result.message.lower()
    
    # Verify memory storage
    planner_agent.memory_manager.store_memory.assert_called_once()
    call_args = planner_agent.memory_manager.store_memory.call_args[1]
    assert call_args["metadata"]["type"] == "plan_validation"
