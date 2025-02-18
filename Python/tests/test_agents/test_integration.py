"""Integration tests for agent system."""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from typing import Dict, List, Optional

from ...agents.manager import ManagerAgent
from ...agents.executor import ExecutorAgent
from ...agents.planner import PlannerAgent
from ...agents.reflector import ReflectorAgent
from ...agents.protocols import AgentRole, AgentMessage, TaskResult
from ...memory import MemoryManager

from .conftest import memory_manager, mock_llm

@pytest.fixture
def agent_system(memory_manager, mock_llm):
    """Create complete agent system."""
    # Create mock agents
    executor = MagicMock(spec=ExecutorAgent)
    executor.execute_task = AsyncMock(return_value=TaskResult(
        success=True,
        message="Task executed successfully",
        artifacts={"result": "test"}
    ))

    planner = MagicMock(spec=PlannerAgent)
    planner.create_plan = AsyncMock(return_value=TaskResult(
        success=True,
        message="Plan created successfully",
        artifacts={"steps": [{"id": 1, "action": "test"}]}
    ))

    reflector = MagicMock(spec=ReflectorAgent)
    reflector.analyze_execution = AsyncMock(return_value=TaskResult(
        success=True,
        message="Analysis complete",
        artifacts={"insights": ["test"]}
    ))

    # Create manager with mock agents
    manager = AgentManager(
        memory_manager=memory_manager,
        executor=executor,
        planner=planner,
        reflector=reflector
    )
    return manager

@pytest.mark.asyncio
async def test_end_to_end_task_execution(agent_system):
    """Test complete task lifecycle."""
    task = {
        "type": "research",
        "query": "test query",
        "context": {}
    }
    
    result = await agent_system.execute_task(task)
    
    assert result.success
    assert "task executed" in result.message.lower()
    
    # Verify agent interactions
    agent_system.planner.create_plan.assert_called_once()
    agent_system.executor.execute_task.assert_called_once()
    agent_system.reflector.analyze_execution.assert_called_once()

@pytest.mark.asyncio
async def test_error_recovery_flow(agent_system):
    """Test error recovery process."""
    task = {
        "type": "complex_task",
        "steps": [
            {"type": "research", "query": "test"},
            {"type": "execute", "action": "test"}
        ]
    }
    
    # Set up mock responses
    agent_system.executor.execute_task.side_effect = [
        TaskResult(success=False, message="First attempt failed", artifacts={}, error="First attempt failed"),
        TaskResult(success=True, message="Task completed", artifacts={"status": "success"})
    ]

    agent_system.reflector.analyze_failure = AsyncMock(return_value=TaskResult(
        success=True,
        message="Analysis complete",
        artifacts={"root_cause": "test error"}
    ))

    agent_system.reflector.suggest_improvements = AsyncMock(return_value=TaskResult(
        success=True,
        message="Improvements suggested",
        artifacts={"suggestions": ["retry"]}
    ))

    result = await agent_system.execute_task(task)
    
    assert result.success
    assert "task completed" in result.message.lower()
    
    # Verify error analysis
    agent_system.reflector.analyze_failure.assert_called_once()
    
    # Verify improvements
    agent_system.reflector.suggest_improvements.assert_called_once()

@pytest.mark.asyncio
async def test_agent_communication(agent_system):
    """Test communication between agents."""
    task = {
        "type": "multi_step",
        "steps": [
            {"type": "plan", "details": "test"},
            {"type": "execute", "details": "test"},
            {"type": "reflect", "details": "test"}
        ]
    }
    
    result = await agent_system.execute_task(task)
    
    assert result.success
    assert "task executed" in result.message.lower()
    
    # Verify agent interactions
    assert agent_system.planner.create_plan.call_count > 0
    assert agent_system.executor.execute_task.call_count > 0
    assert agent_system.reflector.analyze_execution.call_count > 0
