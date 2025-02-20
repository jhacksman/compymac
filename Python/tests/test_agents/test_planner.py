"""Tests for planner agent."""
import pytest
import json
from unittest.mock import Mock, AsyncMock
from datetime import datetime

from agents.planner import PlannerAgent
from agents.protocols import TaskResult
from memory.message_types import MemoryMetadata
from tests.conftest import MockResponse

@pytest.fixture
def memory_manager():
    """Create mock memory manager."""
    manager = Mock()
    manager.store_memory = AsyncMock()
    manager.retrieve_memories = AsyncMock(return_value=[])
    manager.retrieve_context = AsyncMock(return_value=[])
    manager.cleanup = AsyncMock()
    return manager

@pytest.fixture
def planner_agent(memory_manager, mock_llm):
    """Create planner agent with mock memory manager and LLM."""
    return PlannerAgent(memory_manager, llm=mock_llm)

@pytest.mark.asyncio
async def test_create_plan(planner_agent):
    """Test plan creation."""
    # Set mock chain response
    planner_agent.planning_chain = AsyncMock()
    planner_agent.planning_chain.ainvoke = AsyncMock(return_value={
        "success": True,
        "message": "Plan created successfully",
        "artifacts": {
            "steps": [
                {"id": 1, "action": "Step 1", "success_criteria": "Step 1 complete"},
                {"id": 2, "action": "Step 2", "success_criteria": "Step 2 complete"}
            ],
            "validation": {"is_valid": True}
        }
    })
    planner_agent.memory_manager.store_memory = AsyncMock()
    planner_agent.memory_manager.retrieve_context = AsyncMock(return_value=[])
    
    plan = await planner_agent.create_plan("Test task")
    
    assert plan is not None
    assert isinstance(plan, TaskResult)
    assert plan.success
    assert plan.artifacts is not None
    assert "steps" in plan.artifacts
    assert len(plan.artifacts["steps"]) == 2
    assert plan.artifacts["validation"]["is_valid"]

    # Clean up
    await planner_agent.memory_manager.cleanup()

@pytest.mark.asyncio
async def test_validate_plan(planner_agent):
    """Test plan validation."""
    plan = {
        "steps": [
            {"description": "Step 1", "agent": "executor"},
            {"description": "Step 2", "agent": "reflector"}
        ],
        "success_criteria": ["All steps completed"]
    }
    
    # Set mock chain response
    planner_agent.planning_chain = AsyncMock()
    planner_agent.planning_chain.ainvoke = AsyncMock(return_value={
        "success": True,
        "message": "Plan validation complete",
        "artifacts": {
            "is_valid": True,
            "feedback": "Plan looks good"
        }
    })
    planner_agent.memory_manager.store_memory = AsyncMock()
    planner_agent.memory_manager.retrieve_context = AsyncMock(return_value=[])
    
    result = await planner_agent.validate_plan(plan)
    
    assert isinstance(result, TaskResult)
    assert result.success
    assert result.artifacts is not None
    assert result.artifacts["is_valid"]
    assert "feedback" in result.artifacts
