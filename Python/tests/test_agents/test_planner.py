"""Tests for planner agent."""
import pytest
import json
from unittest.mock import Mock, AsyncMock
from datetime import datetime

from agents.planner import PlannerAgent
from memory.message_types import MemoryMetadata

@pytest.fixture
def memory_manager():
    """Create mock memory manager."""
    manager = Mock()
    manager.store_memory = AsyncMock()
    manager.retrieve_memories = AsyncMock(return_value=[])
    return manager

@pytest.fixture
def planner_agent(memory_manager, mock_llm):
    """Create planner agent with mock memory manager and LLM."""
    return PlannerAgent(memory_manager, llm=mock_llm)

@pytest.mark.asyncio
async def test_create_plan(planner_agent):
    """Test plan creation."""
    # Set mock LLM response
    planner_agent.llm._response = {
        "plan": {
            "steps": [
                {"description": "Step 1", "agent": "executor"},
                {"description": "Step 2", "agent": "reflector"}
            ],
            "success_criteria": ["All steps completed"]
        }
    }
    
    plan = await planner_agent.create_plan("Test task")
    
    assert len(plan["steps"]) == 2
    assert plan["success_criteria"]

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
    
    # Set mock LLM response
    planner_agent.llm._response = {
        "valid": True,
        "feedback": "Plan looks good"
    }
    
    result = await planner_agent.validate_plan(plan)
    
    assert result["valid"]
    assert "feedback" in result
