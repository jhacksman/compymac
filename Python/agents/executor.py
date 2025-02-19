"""Execution agent for carrying out tasks."""

from typing import Dict, List, Optional, Any
from datetime import datetime
import json
import asyncio

from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from langchain.memory import ConversationBufferMemory
from langchain_core.language_models.llms import BaseLLM

from .protocols import AgentRole, AgentMessage, TaskResult
from .config import AgentConfig
from .retry_handler import RetryHandler
from ..memory import MemoryManager
from ..memory.error_logger import ErrorLogger

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
        self.retry_handler = RetryHandler()
        self.error_logger = ErrorLogger(memory_manager) if memory_manager else None
        
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
                
            # Parse execution result
            if "artifacts" not in result:
                return False
                
            execution_result = json.loads(result["artifacts"].get("execution_plan", "{}"))
            if not execution_result:
                return False
                
            # Check step criteria
            result_criteria = execution_result.get("success_criteria", {})
            if not result_criteria:
                return False
                
            # Verify step criteria match if specified
            if criteria.get("step_criteria") and result_criteria.get("step_criteria") != criteria.get("step_criteria"):
                return False
                
            # Verify overall criteria match if specified
            if criteria.get("overall_criteria") and result_criteria.get("overall_criteria") != criteria.get("overall_criteria"):
                return False
                
            return True
            
        except Exception:
            return False
            
    async def _log_error(self, error: Exception, context: Dict[str, Any]) -> None:
        """Log error to memory system.
        
        Args:
            error: Exception that occurred
            context: Error context
        """
        if self.error_logger:
            await self.error_logger.log_error(error, context)
        
    async def execute_task(self, task: Dict) -> TaskResult:
        """Execute a task according to plan.
        
        Args:
            task: Task specification with subtasks and criteria
            
        Returns:
            Task execution result
        """
        async def execute_with_context():
            # Get relevant context if memory manager exists
            context = ""
            if self.memory_manager:
                memories = await self.memory_manager.retrieve_context(
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
                    "execution_plan": result
                }
            }
            
            # Verify success
            if not self._verify_success(execution_result, task["criteria"]):
                raise Exception("Success criteria not met")
                
            # Store success in memory if manager exists
            if self.memory_manager:
                await self.memory_manager.store_memory(
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
            
        try:
            return await self.retry_handler.execute_with_retry(execute_with_context)
        except Exception as e:
            # Log error
            await self._log_error(e, {
                "task": task,
                "type": "task_execution_error"
            })
            
            return TaskResult(
                success=False,
                message=f"Task failed: {str(e)}",
                artifacts={
                    "error": str(e)
                },
                error=str(e)
            )
