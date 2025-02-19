"""Tests for planner agent."""

import pytest
from unittest.mock import Mock, AsyncMock
import json
from datetime import datetime

from ..agents.planner import PlannerAgent
from ..memory import MemoryManager

@pytest.fixture
def memory_manager():
    """Create mock memory manager."""
    manager = Mock(spec=MemoryManager)
    manager.store_memory = Mock()
    manager.retrieve_context = Mock(return_value=[])
    return manager

@pytest.fixture
def planner_agent(memory_manager):
    """Create planner agent with mock memory manager."""
    return PlannerAgent(memory_manager)

def test_create_plan_success(planner_agent):
    """Test successful plan creation."""
    # Mock planning chain
    planner_agent.planning_chain.predict = Mock(return_value=json.dumps({
        "subtasks": [{
            "id": "test-1",
            "description": "Test step",
            "success_criteria": "Step complete"
        }],
        "criteria": {
            "overall_success": "All steps done",
            "timeout": 300
        }
    }))
    
    plan = planner_agent.create_plan("Test task")
    
    assert "subtasks" in plan
    assert "criteria" in plan
    assert len(plan["subtasks"]) > 0
    assert "overall_success" in plan["criteria"]
    
    # Verify memory storage
    planner_agent.memory_manager.store_memory.assert_called_once()
    call_args = planner_agent.memory_manager.store_memory.call_args[1]
    assert call_args["metadata"]["type"] == "task_plan"
    assert call_args["metadata"]["task"] == "Test task"

def test_create_plan_with_context(planner_agent):
    """Test plan creation with memory context."""
    # Mock memory retrieval
    planner_agent.memory_manager.retrieve_context.return_value = [{
        "content": "Previous similar task"
    }]
    
    # Mock planning chain
    planner_agent.planning_chain.predict = Mock(return_value=json.dumps({
        "subtasks": [{
            "id": "test-1",
            "description": "Test step",
            "success_criteria": "Step complete"
        }],
        "criteria": {
            "overall_success": "All steps done",
            "timeout": 300
        }
    }))
    
    plan = planner_agent.create_plan("Test task")
    
    assert "subtasks" in plan
    assert "criteria" in plan
    
    # Verify context retrieval
    planner_agent.memory_manager.retrieve_context.assert_called_once_with(
        query="Test task",
        time_range="7d"
    )

def test_create_plan_error_handling(planner_agent):
    """Test error handling in plan creation."""
    # Mock planning chain to raise exception
    error_msg = "Test error"
    planner_agent.planning_chain.predict = Mock(
        side_effect=Exception(error_msg)
    )
    
    plan = planner_agent.create_plan("Test task")
    
    assert "subtasks" in plan
    assert "criteria" in plan
    assert len(plan["subtasks"]) == 1
    assert error_msg in plan["subtasks"][0]["description"]
    assert plan["criteria"]["timeout"] == 60  # Error timeout

def test_create_plan_without_memory_manager():
    """Test plan creation without memory manager."""
    planner = PlannerAgent()  # No memory manager
    
    # Mock planning chain
    planner.planning_chain.predict = Mock(return_value=json.dumps({
        "subtasks": [{
            "id": "test-1",
            "description": "Test step",
            "success_criteria": "Step complete"
        }],
        "criteria": {
            "overall_success": "All steps done",
            "timeout": 300
        }
    }))
    
    plan = planner.create_plan("Test task")
    
    assert "subtasks" in plan
    assert "criteria" in plan
    # Should work without memory operations
