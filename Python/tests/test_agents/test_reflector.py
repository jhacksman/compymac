"""Tests for reflector agent."""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from typing import Dict, List, Optional

from ...agents.reflector import ReflectorAgent
from ...agents.protocols import AgentRole, AgentMessage, TaskResult
from ...memory import MemoryManager

from .conftest import memory_manager, mock_llm

@pytest.fixture
def reflector_agent(memory_manager, mock_llm):
    """Create reflector agent with mock dependencies."""
    return ReflectorAgent(memory_manager=memory_manager, llm=mock_llm)

@pytest.mark.asyncio
async def test_analyze_failure(reflector_agent):
    """Test failure analysis."""
    error = {
        "type": "execution_error",
        "message": "step failed",
        "context": {
            "step_id": 1,
            "action": "test"
        }
    }
    
    result = await reflector_agent.analyze_failure(error)
    
    assert result.success
    assert "analysis complete" in result.message.lower()
    assert "root_cause" in result.artifacts
    
    # Verify memory storage
    reflector_agent.memory_manager.store_memory.assert_called_once()
    call_args = reflector_agent.memory_manager.store_memory.call_args[1]
    assert "failure_analysis" in call_args["metadata"]["type"]

@pytest.mark.asyncio
async def test_suggest_improvements(reflector_agent):
    """Test improvement suggestions."""
    context = {
        "error": "step failed",
        "history": ["attempt 1", "attempt 2"],
        "success_rate": 0.5
    }
    
    result = await reflector_agent.suggest_improvements(context)
    
    assert result.success
    assert "improvements suggested" in result.message.lower()
    assert "suggestions" in result.artifacts
    
    # Verify memory storage
    reflector_agent.memory_manager.store_memory.assert_called_once()
    call_args = reflector_agent.memory_manager.store_memory.call_args[1]
    assert "improvement_suggestions" in call_args["metadata"]["type"]

@pytest.mark.asyncio
async def test_evaluate_performance(reflector_agent):
    """Test performance evaluation."""
    metrics = {
        "success_rate": 0.8,
        "average_time": 1.5,
        "error_rate": 0.1
    }
    
    result = await reflector_agent.evaluate_performance(metrics)
    
    assert result.success
    assert "evaluation complete" in result.message.lower()
    assert "insights" in result.artifacts
    
    # Verify memory storage
    reflector_agent.memory_manager.store_memory.assert_called_once()
    call_args = reflector_agent.memory_manager.store_memory.call_args[1]
    assert "performance_evaluation" in call_args["metadata"]["type"]
