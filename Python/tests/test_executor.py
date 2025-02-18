"""Tests for executor agent."""

import pytest
from unittest.mock import Mock, AsyncMock
import json
from datetime import datetime

from ..agents.executor import ExecutorAgent
from ..agents.config import AgentConfig
from ..memory import MemoryManager

@pytest.fixture
def memory_manager():
    """Create mock memory manager."""
    manager = Mock(spec=MemoryManager)
    manager.store_memory = Mock()
    manager.retrieve_context = Mock(return_value=[])
    return manager

import json
import pytest
from unittest.mock import MagicMock
from typing import List, Optional, Any, Dict, Sequence
from langchain_core.language_models import BaseLLM
from langchain_core.outputs import LLMResult, Generation

class MockLLM(BaseLLM):
    """Mock LLM for testing."""
    
    @property
    def _llm_type(self) -> str:
        """Return identifier for this LLM."""
        return "mock"
    
    def _generate(self, prompts: List[str], stop: Optional[List[str]] = None, run_manager=None, **kwargs) -> LLMResult:
        """Mock generate method."""
        return LLMResult(generations=[[Generation(text=json.dumps({
            "execution_plan": [{
                "step": "Test step",
                "verification": "Step complete"
            }],
            "success_criteria": {
                "step_criteria": ["complete"],
                "overall_criteria": "success"
            }
        }))]])
        
    async def _agenerate(self, prompts: List[str], stop: Optional[List[str]] = None, run_manager=None, **kwargs) -> LLMResult:
        """Mock async generate method."""
        return self._generate(prompts, stop, run_manager, **kwargs)

@pytest.fixture
def mock_llm():
    """Create mock LLM."""
    return MockLLM()

@pytest.fixture
def executor_agent(memory_manager, mock_llm):
    """Create executor agent with mock dependencies."""
    return ExecutorAgent(memory_manager=memory_manager, llm=mock_llm)

@pytest.mark.asyncio
async def test_execute_task_success(executor_agent):
    """Test successful task execution."""
    # Mock execution chain
    executor_agent.execution_chain.apredict = AsyncMock(return_value=json.dumps({
        "execution_plan": [{
            "step": "Test step",
            "verification": "Step complete"
        }],
        "success_criteria": {
            "step_criteria": ["complete"],
            "overall_criteria": "success"
        }
    }))
    
    task = {
        "subtasks": ["Test step"],
        "criteria": {
            "step_criteria": ["complete"],
            "overall_criteria": "success"
        }
    }
    
    result = await executor_agent.execute_task(task)
    
    assert result.success
    assert "Task completed successfully" in result.message
    assert "execution_plan" in result.artifacts
    
    # Verify memory storage
    executor_agent.memory_manager.store_memory.assert_called_once()
    call_args = executor_agent.memory_manager.store_memory.call_args[1]
    assert call_args["metadata"]["type"] == "task_execution"
    assert call_args["metadata"]["success"] is True

@pytest.mark.asyncio
async def test_execute_task_retry_success(executor_agent):
    """Test task execution with retry success."""
    # Mock execution chain to fail twice then succeed
    executor_agent.execution_chain.apredict = AsyncMock(side_effect=[
        Exception("First attempt failed"),
        Exception("Second attempt failed"),
        json.dumps({
            "execution_plan": [{
                "step": "Test step",
                "verification": "Step complete"
            }],
            "success_criteria": {
                "step_criteria": ["complete"],
                "overall_criteria": "success"
            }
        })
    ])
    
    task = {
        "subtasks": ["Test step"],
        "criteria": {
            "step_criteria": ["complete"],
            "overall_criteria": "success"
        }
    }
    
    result = await executor_agent.execute_task(task)
    
    assert result.success
    assert result.artifacts["attempt"] == 3
    
    # Verify error storage
    assert executor_agent.memory_manager.store_memory.call_count == 3
    error_calls = [
        call for call in executor_agent.memory_manager.store_memory.call_args_list
        if call[1]["metadata"]["type"] == "task_error"
    ]
    assert len(error_calls) == 2

@pytest.mark.asyncio
async def test_execute_task_all_retries_failed(executor_agent):
    """Test task execution with all retries failing."""
    # Mock execution chain to always fail
    error_msg = "Test error"
    executor_agent.execution_chain.apredict = AsyncMock(
        side_effect=Exception(error_msg)
    )
    
    task = {
        "subtasks": ["Test step"],
        "criteria": {
            "step_criteria": ["complete"],
            "overall_criteria": "success"
        }
    }
    
    result = await executor_agent.execute_task(task)
    
    assert not result.success
    assert error_msg in result.error
    assert result.artifacts["attempts"] == executor_agent.config.max_retries
    
    # Verify error storage
    assert executor_agent.memory_manager.store_memory.call_count == 3
    for call in executor_agent.memory_manager.store_memory.call_args_list:
        assert call[1]["metadata"]["type"] == "task_error"

@pytest.mark.asyncio
async def test_execute_task_criteria_not_met(executor_agent):
    """Test task execution with unmet criteria."""
    # Mock execution chain with invalid result
    executor_agent.execution_chain.apredict = AsyncMock(return_value=json.dumps({
        "execution_plan": [{
            "step": "Test step",
            "verification": "Step complete"
        }],
        "success_criteria": {
            "step_criteria": ["wrong"],
            "overall_criteria": "failure"
        }
    }))
    
    task = {
        "subtasks": ["Test step"],
        "criteria": {
            "step_criteria": ["complete"],
            "overall_criteria": "success"
        }
    }
    
    result = await executor_agent.execute_task(task)
    
    assert not result.success
    assert "criteria not met" in result.error.lower()
    
    # Verify error storage
    executor_agent.memory_manager.store_memory.assert_called()
    call_args = executor_agent.memory_manager.store_memory.call_args[1]
    assert call_args["metadata"]["type"] == "task_error"

def test_verify_success():
    """Test success verification logic."""
    mock_llm = MockLLM()
    executor = ExecutorAgent(llm=mock_llm)
    
    # Test successful verification
    result = {
        "artifacts": {
            "output": "Step complete and successful"
        }
    }
    criteria = {
        "step_criteria": ["complete"],
        "overall_criteria": "successful"
    }
    assert executor._verify_success(result, criteria)
    
    # Test failed verification
    result = {
        "artifacts": {
            "output": "Step failed"
        }
    }
    assert not executor._verify_success(result, criteria)
    
    # Test empty criteria
    assert executor._verify_success(result, {})
    
    # Test invalid result format
    assert not executor._verify_success(None, criteria)

def test_calculate_delay():
    """Test exponential backoff delay calculation."""
    config = AgentConfig(
        retry_delay=1.0,
        max_retry_delay=30.0
    )
    mock_llm = MockLLM()
    executor = ExecutorAgent(config=config, llm=mock_llm)
    
    # Test initial delay
    delay = executor._calculate_delay(0)
    assert 0.9 <= delay <= 1.1  # Account for jitter
    
    # Test exponential increase
    delay = executor._calculate_delay(1)
    assert 1.8 <= delay <= 2.2
    
    # Test maximum delay
    delay = executor._calculate_delay(10)
    assert delay <= config.max_retry_delay * 1.1
