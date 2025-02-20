"""Planning agent for task decomposition."""

from typing import Dict, List, Optional
from datetime import datetime
import json

from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from langchain.memory import ConversationBufferMemory
from langchain_core.language_models.llms import BaseLLM
from langchain_core.runnables import RunnableSequence

from .protocols import AgentRole, AgentMessage, TaskResult
from .config import AgentConfig
from memory import MemoryManager

class PlannerAgent:
    """Planning agent for task decomposition."""
    
    def __init__(self, 
                 memory_manager: Optional[MemoryManager] = None, 
                 llm: Optional[BaseLLM] = None,
                 config: Optional[AgentConfig] = None):
        """Initialize planner agent.
        
        Args:
            memory_manager: Optional memory manager for context
            llm: Optional LLM instance
            config: Optional agent configuration
        """
        self.memory_manager = memory_manager
        self._llm = llm
        self.config = config or AgentConfig()
        self.memory = ConversationBufferMemory(
            memory_key="planning_history",
            return_messages=True
        )
        
        # Set up planning chain
        self.planning_chain = self._setup_planning_chain()
        
    async def handle_feedback(self, feedback: AgentMessage) -> TaskResult:
        """Handle feedback from other agents.
        
        Args:
            feedback: Feedback message
            
        Returns:
            Task execution result
        """
        try:
            # Store feedback in memory if manager exists
            if self.memory_manager:
                await self.memory_manager.store_memory(
                    content=json.dumps({
                        "sender": feedback.sender.value,
                        "content": feedback.content,
                        "metadata": feedback.metadata
                    }),
                    metadata={
                        "type": "plan_revision",
                        "timestamp": datetime.now().isoformat()
                    }
                )
            
            # Process feedback
            result = await self._llm.ainvoke({
                "task": feedback.content,
                "type": "handle_feedback"
            })
            
            # Parse JSON response
            response = json.loads(result)
            
            return TaskResult(
                success=True,
                message="Plan updated",
                artifacts={
                    "revised_steps": response.get("artifacts", {}).get("revised_steps", []),
                    "validation": response.get("artifacts", {}).get("validation", {})
                }
            )
            
        except Exception as e:
            return TaskResult(
                success=False,
                message=f"Error processing feedback: {str(e)}",
                artifacts={},
                error=str(e)
            )
            
    async def validate_plan(self, plan: Dict) -> TaskResult:
        """Validate execution plan.
        
        Args:
            plan: Execution plan
            
        Returns:
            Validation result
        """
        try:
            # Store plan in memory if manager exists
            if self.memory_manager:
                await self.memory_manager.store_memory(
                    content=json.dumps(plan),
                    metadata={
                        "type": "plan_validation",
                        "timestamp": datetime.now().isoformat()
                    }
                )
            
            # Get validation result from chain
            result = await self.planning_chain.ainvoke({"task": json.dumps(plan)})
            
            # Return task result
            return TaskResult(
                success=True,
                message=result.get("message", "Plan validation complete"),
                artifacts=result.get("artifacts", {})
            )
            
        except Exception as e:
            return TaskResult(
                success=False,
                message=f"Error validating plan: {str(e)}",
                artifacts={},
                error=str(e)
            )
            
    def _setup_planning_chain(self) -> LLMChain:
        """Set up the planning chain with LangChain.
        
        Returns:
            Configured planning chain
        """
        if not self._llm:
            raise ValueError("LLM must be provided for planning chain")
        prompt = PromptTemplate(
            template="""You are a planning agent that decomposes tasks into subtasks.

Current task: {task}

Think through how to break this task down:
1. What are the main steps needed?
2. What needs to be verified at each step?
3. How will we know when we're done?

Your response should be in JSON format:
{{
    "success": true,
    "message": "Plan created successfully",
    "artifacts": {{
        "steps": [
            {{
                "id": 1,
                "action": "First step to take",
                "success_criteria": "How to verify this step"
            }}
        ],
        "validation": {{
            "is_valid": true
        }}
    }}
}}

Response:""",
            input_variables=["task"]
        )
        
        return LLMChain(
            llm=self._llm,
            prompt=prompt,
            memory=self.memory
        )
        
    async def create_plan(self, task: str) -> TaskResult:
        """Create execution plan for task.
        
        Args:
            task: Task description
            
        Returns:
            Task execution result
        """
        try:
            # Process task input
            task_str = task if isinstance(task, str) else json.dumps(task)
            
            # Get planning history
            planning_history = ""
            if self.memory_manager:
                memories = await self.memory_manager.retrieve_context(
                    query=task_str,
                    time_range="7d"  # Last week
                )
                if memories:
                    planning_history = "\n".join(
                        f"- {m['content']}" for m in memories
                    )
            
            # Generate plan
            result = await self.planning_chain.ainvoke({"task": task_str})
            
            # Store plan in memory if manager exists
            if self.memory_manager:
                await self.memory_manager.store_memory(
                    content=json.dumps(result),
                    metadata={
                        "type": "plan_creation",
                        "task": task_str,
                        "timestamp": datetime.now().isoformat()
                    }
                )
            
            # Return task result
            return TaskResult(
                success=True,
                message=result.get("message", "Plan created"),
                artifacts=result.get("artifacts", {})
            )
            
        except Exception as e:
            return TaskResult(
                success=False,
                message=f"Error creating plan: {str(e)}",
                artifacts={},
                error=str(e)
            )
