"""Execution agent for carrying out tasks."""

from typing import Dict, List, Optional
from datetime import datetime
import time
import math
import json
import random
import asyncio
from datetime import datetime
from unittest.mock import MagicMock
from typing import Dict, List, Optional, Any

from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from langchain.memory import ConversationBufferMemory
from langchain_core.language_models.llms import BaseLLM

from .protocols import AgentRole, AgentMessage, TaskResult
from .config import AgentConfig
from memory import MemoryManager

class ExecutorAgent:
    """Execution agent for carrying out tasks."""
    
    def __init__(self, 
                 memory_manager: Optional[MemoryManager] = None, 
                 config: Optional[AgentConfig] = None,
                 llm: Optional[Any] = None):
        """Initialize executor agent.
        
        Args:
            memory_manager: Optional memory manager for context
            config: Optional agent configuration
            llm: Optional language model (for testing)
        """
        self.memory_manager = memory_manager
        self.config = config or AgentConfig()
        self.memory = ConversationBufferMemory(
            memory_key="execution_history",
            return_messages=True
        )
        self._llm = llm
        
        # Set up execution chain
        self.execution_chain = self._setup_execution_chain()
        
    def _setup_execution_chain(self) -> LLMChain:
        """Set up the execution chain with LangChain.
        
        Returns:
            Configured execution chain
        """
        prompt = PromptTemplate(
            template="""You are an execution agent that carries out tasks.

Previous execution history:
{execution_history}

Current task:
{task}

Success criteria:
{criteria}

Think through the execution:
1. What steps need to be taken?
2. How to verify each step?
3. What could go wrong?

Your response should be in JSON format:
{
    "execution_plan": [
        {
            "step": "Step description",
            "verification": "How to verify this step"
        }
    ],
    "success_criteria": {
        "step_criteria": ["criteria1", "criteria2"],
        "overall_criteria": "Final verification"
    }
}

Response:""",
            input_variables=["task", "criteria", "execution_history"]
        )
        
        if not self._llm:
            raise ValueError("LLM must be provided for execution chain")
            
        return LLMChain(
            llm=self._llm,
            prompt=prompt,
            memory=self.memory
        )
        
    def _verify_success(self, result: Dict, criteria: Dict) -> bool:
        """Verify task success against criteria.
        
        Args:
            result: Task execution result
            criteria: Success criteria
            
        Returns:
            True if criteria are met
        """
        try:
            # Handle empty criteria case
            if not criteria:
                return True
                
            # Check for artifacts
            if not result or "artifacts" not in result:
                return False
                
            artifacts = result["artifacts"]
            if not isinstance(artifacts, dict):
                return False
                
            # Parse execution plan from artifacts
            execution_plan = artifacts.get("execution_plan", "{}")
            if isinstance(execution_plan, str):
                try:
                    execution_plan = json.loads(execution_plan)
                except json.JSONDecodeError:
                    return False
                    
                if not isinstance(execution_plan, dict):
                    return False
                
            # Check success criteria
            success_criteria = execution_plan.get("success_criteria", {})
            if not success_criteria:
                return False
                
            # Check step criteria
            if criteria.get("step_criteria"):
                if success_criteria.get("step_criteria") != criteria.get("step_criteria"):
                    return False
                    
            # Check overall criteria
            if criteria.get("overall_criteria"):
                if success_criteria.get("overall_criteria") != criteria.get("overall_criteria"):
                    return False
                    
            return True
            
        except Exception:
            return False
            
    def _calculate_delay(self, attempt: int) -> float:
        """Calculate exponential backoff delay.
        
        Args:
            attempt: Current attempt number (0-based)
            
        Returns:
            Delay in seconds
        """
        delay = min(
            self.config.retry_delay * (2 ** attempt),
            self.config.max_retry_delay
        )
        # Add jitter
        jitter = delay * 0.1  # 10% jitter
        return delay + (random.random() * jitter)
        
    async def execute_task(self, task: Dict) -> TaskResult:
        """Execute a task according to plan.
        
        Args:
            task: Task specification with subtasks and criteria
            
        Returns:
            TaskResult: Task execution result with success status, message, and artifacts
        """
        last_error = None
        for attempt in range(self.config.max_retries):
            try:
                # Get relevant context if memory manager exists
                context = ""
                if self.memory_manager:
                    memories = self.memory_manager.retrieve_context(
                        query=str(task),
                        time_range="1d"  # Last day
                    )
                    if memories:
                        context = "\nRelevant context:\n" + "\n".join(
                            f"- {m['content']}" for m in memories
                        )
                
                # Generate execution plan
                result = await self.execution_chain.apredict(
                    task=str(task["subtasks"]) + context,
                    criteria=str(task["criteria"])
                )
                
                # Execute plan
                execution_result = {
                    "success": True,
                    "message": "Task executed successfully",
                    "artifacts": {
                        "execution_plan": result,
                        "attempt": attempt + 1
                    }
                }
                
                # Verify success
                if self._verify_success(execution_result, task["criteria"]):
                    # Store success in memory if manager exists
                    if self.memory_manager:
                        self.memory_manager.store_memory(
                            content=str(execution_result),
                            metadata={
                                "type": "task_execution",
                                "success": True,
                                "timestamp": datetime.now().isoformat()
                            }
                        )
                    
                    return TaskResult(
                        success=True,
                        message="Task completed successfully",
                        artifacts=execution_result["artifacts"]
                    )
                
                # Success criteria not met
                last_error = Exception("Success criteria not met")
                raise last_error
                
            except Exception as e:
                last_error = e
                error_msg = f"Attempt {attempt + 1} failed: {str(e)}"
                
                # Store error in memory if manager exists
                if self.memory_manager:
                    self.memory_manager.store_memory(
                        content=error_msg,
                        metadata={
                            "type": "task_error",
                            "attempt": attempt + 1,
                            "timestamp": datetime.now().isoformat()
                        }
                    )
                
                if attempt < self.config.max_retries - 1:
                    # Calculate and apply backoff delay
                    delay = self._calculate_delay(attempt)
                    await asyncio.sleep(delay)
                    continue
        
        # All retries failed
        return TaskResult(
            success=False,
            message=f"Task failed after {self.config.max_retries} attempts",
            artifacts={
                "last_error": str(last_error),
                "attempts": self.config.max_retries
            },
            error=str(last_error)
        )
