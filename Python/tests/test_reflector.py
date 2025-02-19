"""Tests for reflector agent."""

import pytest
from unittest.mock import Mock, AsyncMock
import json
from datetime import datetime

from ..agents.reflector import ReflectorAgent
from ..agents.protocols import TaskResult
from ..memory import MemoryManager

@pytest.fixture
def memory_manager():
    """Create mock memory manager."""
    manager = Mock(spec=MemoryManager)
    manager.store_memory = Mock()
    manager.retrieve_context = Mock(return_value=[])
    return manager

@pytest.fixture
def reflector_agent(memory_manager, mock_llm):
    """Create reflector agent with mock memory manager and LLM."""
    return ReflectorAgent(memory_manager, llm=mock_llm)

def test_analyze_execution_success(reflector_agent):
    """Test successful execution analysis."""
    # Mock reflection chain
    reflector_agent.reflection_chain.predict = Mock(return_value=json.dumps({
        "analysis": {
            "success": True,
            "key_observations": ["Task completed"],
            "improvement_areas": ["Performance"]
        },
        "recommendations": [{
            "type": "performance_improvement",
            "description": "Optimize step X",
            "priority": 3
        }],
        "learning_outcomes": [
            "Process works well"
        ]
    }))
    
    result = TaskResult(
        success=True,
        message="Task completed",
        artifacts={"output": "test"}
    )
    
    analysis = reflector_agent.analyze_execution(result)
    
    assert "analysis" in analysis
    assert "recommendations" in analysis
    assert "learning_outcomes" in analysis
    assert analysis["analysis"]["success"] is True
    
    # Verify memory storage
    reflector_agent.memory_manager.store_memory.assert_called_once()
    call_args = reflector_agent.memory_manager.store_memory.call_args[1]
    assert call_args["metadata"]["type"] == "task_reflection"
    assert call_args["metadata"]["success"] is True

def test_analyze_execution_with_context(reflector_agent):
    """Test execution analysis with memory context."""
    # Mock memory retrieval
    reflector_agent.memory_manager.retrieve_context.return_value = [{
        "content": "Previous similar execution"
    }]
    
    # Mock reflection chain
    reflector_agent.reflection_chain.predict = Mock(return_value=json.dumps({
        "analysis": {
            "success": True,
            "key_observations": ["Task completed"],
            "improvement_areas": []
        },
        "recommendations": [],
        "learning_outcomes": []
    }))
    
    result = TaskResult(
        success=True,
        message="Task completed",
        artifacts={}
    )
    
    analysis = reflector_agent.analyze_execution(result)
    
    assert "analysis" in analysis
    
    # Verify context retrieval
    reflector_agent.memory_manager.retrieve_context.assert_called_once_with(
        query="Task completed",
        time_range="7d"
    )

def test_analyze_execution_error_handling(reflector_agent):
    """Test error handling in execution analysis."""
    # Mock reflection chain to raise exception
    error_msg = "Test error"
    reflector_agent.reflection_chain.predict = Mock(
        side_effect=Exception(error_msg)
    )
    
    result = TaskResult(
        success=False,
        message="Task failed",
        artifacts={},
        error="Some error"
    )
    
    analysis = reflector_agent.analyze_execution(result)
    
    assert "analysis" in analysis
    assert not analysis["analysis"]["success"]
    assert error_msg in analysis["analysis"]["key_observations"][0]
    assert len(analysis["recommendations"]) == 1
    assert analysis["recommendations"][0]["priority"] == 5

def test_analyze_execution_without_memory_manager(mock_llm):
    """Test execution analysis without memory manager."""
    reflector = ReflectorAgent(llm=mock_llm)  # No memory manager
    
    # Mock reflection chain
    reflector.reflection_chain.predict = Mock(return_value=json.dumps({
        "analysis": {
            "success": True,
            "key_observations": ["Task completed"],
            "improvement_areas": []
        },
        "recommendations": [],
        "learning_outcomes": []
    }))
    
    result = TaskResult(
        success=True,
        message="Task completed",
        artifacts={}
    )
    
    analysis = reflector.analyze_execution(result)
    
    assert "analysis" in analysis
    # Should work without memory operations
