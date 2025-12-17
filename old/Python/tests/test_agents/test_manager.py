"""Tests for manager agent."""
import pytest
import json
from unittest.mock import Mock, AsyncMock
from datetime import datetime

from agents.manager import AgentManager
from memory.message_types import MemoryMetadata

@pytest.mark.asyncio
async def test_delegate_task(mock_agents):
    """Test task delegation to appropriate agent."""

@pytest.mark.asyncio
async def test_delegate_task(mock_agents):
    """Test task delegation to appropriate agent."""
    task = {
        "task": "Test task",
        "type": "execution"
    }
    result = await mock_agents.delegate_task(task)
    
    assert result.success
    assert result.message == "Task completed"
    assert "plan" in result.artifacts or "execution" in result.artifacts

@pytest.mark.asyncio
async def test_coordinate_agents(mock_agents):
    """Test agent coordination."""
    task = {
        "task": "Test coordination",
        "subtasks": [
            {"task": "Plan task", "agent": "planner"},
            {"task": "Execute task", "agent": "executor"}
        ]
    }
    result = await mock_agents.coordinate_task(task)
    
    assert result.success
    assert "Task completed" in result.message
    assert result.artifacts is not None
