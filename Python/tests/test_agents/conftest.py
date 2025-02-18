"""Common test fixtures."""

import pytest
import json
from unittest.mock import MagicMock, AsyncMock
from typing import Dict, Any, List, Optional
import json

from langchain_core.language_models.llms import BaseLLM
from langchain_core.outputs import Generation, LLMResult
from langchain_core.runnables import RunnableConfig

from ...memory import MemoryManager
from ...agents import ExecutorAgent, PlannerAgent, ReflectorAgent
from ...agents.manager import ManagerAgent
from ...agents.protocols import AgentRole, AgentMessage, TaskResult

@pytest.fixture
def memory_manager():
    """Create mock memory manager."""
    manager = MagicMock(spec=MemoryManager)
    manager.store_memory = MagicMock()
    manager.retrieve_context = MagicMock(return_value=[])
    manager.store_memory.return_value = None
    manager.retrieve_context.return_value = []
    manager.store_memory.return_value = None
    manager.retrieve_context.return_value = []
    manager.store_memory.call_args = None
    manager.retrieve_context.call_args = None
    return manager

@pytest.fixture
def mock_agents(memory_manager, mock_llm):
    """Create mock agents."""
    executor = MagicMock(spec=ExecutorAgent)
    executor.execute_task = AsyncMock(return_value=TaskResult(
        success=True,
        message="Task completed",
        artifacts={"result": "test", "status": "success"}
    ))

    planner = MagicMock(spec=PlannerAgent)
    planner.create_plan = AsyncMock(return_value=TaskResult(
        success=True,
        message="Task completed",
        artifacts={"steps": [{"id": 1, "action": "test"}], "validation": {"is_valid": True}}
    ))
    planner.handle_feedback = AsyncMock(return_value=TaskResult(
        success=True,
        message="Message delivered",
        artifacts={"status": "delivered"}
    ))
    planner.validate_plan = AsyncMock(return_value=TaskResult(
        success=True,
        message="Plan valid",
        artifacts={"validation": {"is_valid": True}}
    ))

    reflector = MagicMock(spec=ReflectorAgent)
    reflector.analyze_execution = AsyncMock(return_value=TaskResult(
        success=True,
        message="Analysis complete",
        artifacts={"insights": ["test"]}
    ))
    reflector.analyze_failure = AsyncMock(return_value=TaskResult(
        success=True,
        message="Analysis complete",
        artifacts={"root_cause": "test error"}
    ))
    reflector.suggest_improvements = AsyncMock(return_value=TaskResult(
        success=True,
        message="Improvements suggested",
        artifacts={"suggestions": ["retry"]}
    ))
    reflector.evaluate_performance = AsyncMock(return_value=TaskResult(
        success=True,
        message="Evaluation complete",
        artifacts={"metrics": {"success_rate": 0.8}}
    ))

    return ManagerAgent(
        memory_manager=memory_manager,
        executor=executor,
        planner=planner,
        reflector=reflector,
        llm=mock_llm
    )

from langchain_core.language_models.llms import BaseLLM

from langchain_core.runnables import Runnable

class MockLLM(BaseLLM, Runnable):
    """Mock LLM for testing."""
    
    def _get_response_for_prompt(self, prompt: str) -> Dict:
        """Get appropriate response based on prompt content."""
        # Extract task and type from input
        task = None
        input_type = None
        if isinstance(prompt, dict):
            prompt_dict = prompt
            task = prompt_dict.get("task", "")
            input_type = prompt_dict.get("type", "")
        else:
            try:
                prompt_dict = json.loads(prompt) if isinstance(prompt, str) else {}
                task = prompt_dict.get("task", "")
                input_type = prompt_dict.get("type", "")
            except:
                task = str(prompt)
        
        prompt_str = str(task).lower()
        input_type = str(input_type).lower()
        
        # Reflector agent responses
        if input_type == "analyze_failure" or "error" in prompt_str:
            return {
                "success": True,
                "message": "Analysis complete",
                "artifacts": {
                    "root_cause": "test error",
                    "severity": "high",
                    "recommendations": ["retry", "validate input"],
                    "suggestions": ["retry", "add validation"],
                    "insights": ["good throughput", "high latency"]
                }
            }
        elif input_type == "suggest_improvements" or "improve" in prompt_str:
            return {
                "success": True,
                "message": "Improvements suggested",
                "artifacts": {
                    "root_cause": "test error",
                    "severity": "high",
                    "recommendations": ["retry", "validate input"],
                    "suggestions": ["retry", "add validation"],
                    "insights": ["good throughput", "high latency"]
                }
            }
        elif input_type == "evaluate_performance" or "metrics" in prompt_str:
            return {
                "success": True,
                "message": "Evaluation complete",
                "artifacts": {
                    "root_cause": "test error",
                    "severity": "high",
                    "recommendations": ["retry", "validate input"],
                    "suggestions": ["retry", "add validation"],
                    "insights": ["good throughput", "high latency"]
                }
            }
            
        # Message handling responses
        elif "handle_message" in prompt_str or "message" in prompt_str:
            return {
                "success": True,
                "message": "Message delivered",
                "artifacts": {
                    "status": "delivered",
                    "recipient": "test",
                    "timestamp": "2024-02-17T02:13:08Z",
                    "metadata": {
                        "tags": ["message", "delivered"]
                    }
                }
            }
            
        # Planner agent responses
        elif "create_plan" in prompt_str or "plan" in prompt_str:
            return {
                "success": True,
                "message": "Plan created successfully",
                "artifacts": {
                    "steps": [
                        {
                            "id": 1,
                            "action": "test",
                            "success_criteria": "Test complete"
                        }
                    ],
                    "validation": {"is_valid": True}
                }
            }
        elif "handle_feedback" in prompt_str or "feedback" in prompt_str:
            return {
                "success": True,
                "message": "Plan updated",
                "artifacts": {
                    "revised_steps": [
                        {
                            "id": 1,
                            "action": "test",
                            "success_criteria": "Test complete"
                        }
                    ]
                }
            }
            
        # Default task execution response
        else:
            return {
                "success": True,
                "message": "Task executed successfully",
                "artifacts": {
                    "result": "test",
                    "status": "success"
                }
            }
    
    def _generate(self, prompts: List[str], stop: Optional[List[str]] = None, **kwargs) -> LLMResult:
        """Mock generate call."""
        responses = []
        for prompt in prompts:
            response = self._get_response_for_prompt(prompt)
            responses.append([Generation(text=json.dumps(response))])
        return LLMResult(generations=responses)
        
    async def _agenerate(self, prompts: List[str], stop: Optional[List[str]] = None, **kwargs) -> LLMResult:
        """Mock async generate call."""
        return self._generate(prompts, stop, **kwargs)
        
    def invoke(self, input: Dict[str, Any], config: Optional[RunnableConfig] = None, **kwargs) -> str:
        """Mock invoke call."""
        prompt = json.dumps(input) if isinstance(input, dict) else str(input)
        response = self._get_response_for_prompt(prompt)
        return json.dumps(response)
        
    async def ainvoke(self, input: Dict[str, Any], config: Optional[RunnableConfig] = None, **kwargs) -> str:
        """Mock async invoke call."""
        return self.invoke(input, config, **kwargs)
        
    @property
    def _llm_type(self) -> str:
        """Return LLM type."""
        return "mock"

@pytest.fixture
def mock_llm():
    """Create mock LLM."""
    return MockLLM()
