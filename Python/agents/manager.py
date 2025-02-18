"""Manager agent for orchestrating the agent system."""

from typing import Dict, List, Optional, Any
from datetime import datetime
import asyncio
import json

from langchain.agents import AgentExecutor, LLMSingleActionAgent
from langchain.memory import ConversationBufferMemory
from langchain.prompts import PromptTemplate
from langchain.tools import Tool
from langchain.chains import LLMChain
from langchain_core.language_models.llms import BaseLLM

from ..memory import MemoryManager
from .protocols import AgentRole, AgentMessage, TaskResult
from .config import AgentConfig
from .planner import PlannerAgent
from .executor import ExecutorAgent
from .reflector import ReflectorAgent

class AgentManager:
    """Manager agent for orchestrating the system."""
    
    def __init__(self,
                 memory_manager: Optional[MemoryManager] = None,
                 executor: Optional[ExecutorAgent] = None,
                 planner: Optional[PlannerAgent] = None,
                 reflector: Optional[ReflectorAgent] = None,
                 config: Optional[AgentConfig] = None,
                 llm: Optional[BaseLLM] = None):
        """Initialize manager agent.
        
        Args:
            memory_manager: Optional memory manager instance
            executor: Optional executor agent instance
            planner: Optional planner agent instance
            reflector: Optional reflector agent instance
            config: Optional agent configuration
            llm: Optional LLM instance
        """
        self.memory_manager = memory_manager or MemoryManager()
        self._llm = llm
        self.executor = executor or ExecutorAgent(memory_manager=self.memory_manager, llm=self._llm)
        self.planner = planner or PlannerAgent(memory_manager=self.memory_manager, llm=self._llm)
        self.reflector = reflector or ReflectorAgent(memory_manager=self.memory_manager, llm=self._llm)
        self.config = config or AgentConfig()
        self.memory = ConversationBufferMemory(
            memory_key="chat_history",
            return_messages=True
        )
        self.tools = self._setup_tools()
        if self._llm:
            self.agent_executor = self._setup_agent_executor()
        
    def _setup_tools(self) -> List[Tool]:
        """Set up available tools for the agent.
        
        Returns:
            List of available tools
        """
        return [
            Tool(
                name="plan_task",
                func=self.planner.create_plan,
                description="Create a plan for executing a task"
            ),
            Tool(
                name="execute_task",
                func=self.executor.execute_task,
                description="Execute a planned task"
            ),
            Tool(
                name="analyze_execution",
                func=self.reflector.analyze_execution,
                description="Analyze task execution results"
            ),
            Tool(
                name="search_memory",
                func=self.memory_manager.retrieve_context,
                description="Search memory for relevant context"
            )
        ]
        
    def _setup_agent_executor(self) -> AgentExecutor:
        """Set up the agent executor with LangChain.
        
        Returns:
            Configured agent executor
        """
        prompt = PromptTemplate(
            template="""You are a manager agent coordinating task execution.
            
Previous conversation:
{chat_history}

Current task: {input}
Available tools: {tools}

Think through the steps needed:
1. Plan the task
2. Execute the plan
3. Analyze results
4. Learn from execution

What would you like to do?

Response should be in the format:
Thought: Consider what needs to be done
Action: The tool to use
Action Input: The input for the tool
""",
            input_variables=["input", "chat_history", "tools"]
        )
        
        if not self._llm:
            raise ValueError("LLM must be provided for agent executor")
            
        llm_chain = prompt | self._llm
        
        agent = llm_chain | (lambda x: {
            "action": x.split("\nAction:")[1].split("\nAction Input:")[0].strip(),
            "action_input": x.split("\nAction Input:")[1].strip()
        })
        
        # Create a runnable dict for tools
        tool_map = {tool.name: tool.func for tool in self.tools}
        
        return agent | tool_map
        
    async def delegate_task(self, task: Dict) -> TaskResult:
        """Delegate task to appropriate agent.
        
        Args:
            task: Task specification
            
        Returns:
            Task execution result
        """
        try:
            # Create plan
            plan = await self.planner.create_plan(json.dumps(task))
            if not plan.success:
                return plan
                
            # Execute plan
            result = await self.executor.execute_task(plan.artifacts)
            
            # Store delegation in memory
            self.memory_manager.store_memory(
                content=json.dumps({
                    "task": task,
                    "plan": plan.artifacts,
                    "result": result.artifacts
                }),
                metadata={
                    "type": "task_delegation",
                    "success": result.success,
                    "timestamp": datetime.now().isoformat()
                }
            )
            
            return TaskResult(
                success=True,
                message="Task completed",
                artifacts={
                    "plan": plan.artifacts,
                    "execution": result.artifacts,
                    "status": "success"
                }
            )
            
        except Exception as e:
            return TaskResult(
                success=False,
                message=f"Task delegation failed: {str(e)}",
                artifacts={},
                error=str(e)
            )
            
    async def handle_message(self, message: AgentMessage) -> TaskResult:
        """Handle message between agents.
        
        Args:
            message: Agent message
            
        Returns:
            Message handling result
        """
        try:
            # Route message to recipient
            if message.recipient == AgentRole.PLANNER:
                await self.planner.handle_feedback(message)
            elif message.recipient == AgentRole.EXECUTOR:
                await self.executor.execute_task(json.loads(message.content))
            elif message.recipient == AgentRole.REFLECTOR:
                await self.reflector.analyze_failure(json.loads(message.content))
            else:
                return TaskResult(
                    success=False,
                    message=f"Unknown recipient: {message.recipient}",
                    artifacts={},
                    error=f"Unknown recipient: {message.recipient}"
                )
            
            # Store message in memory
            self.memory_manager.store_memory(
                content=json.dumps({
                    "sender": message.sender.value,
                    "recipient": message.recipient.value,
                    "content": message.content,
                    "metadata": message.metadata
                }),
                metadata={
                    "type": "agent_message",
                    "sender": message.sender.value,
                    "recipient": message.recipient.value,
                    "timestamp": datetime.now().isoformat()
                }
            )
                
            return TaskResult(
                success=True,
                message="Message delivered",
                artifacts={"status": "delivered"}
            )
            
        except Exception as e:
            return TaskResult(
                success=False,
                message=f"Message handling failed: {str(e)}",
                artifacts={},
                error=str(e)
            )
            
    async def coordinate_task(self, task: Dict) -> TaskResult:
        """Coordinate complex task execution.
        
        Args:
            task: Complex task specification
            
        Returns:
            Task coordination result
        """
        try:
            results = []
            
            # Store initial coordination in memory
            self.memory_manager.store_memory(
                content=json.dumps({
                    "task": task,
                    "status": "started"
                }),
                metadata={
                    "type": "task_coordination",
                    "timestamp": datetime.now().isoformat()
                }
            )
            
            # Create plan for overall task
            plan = await self.planner.create_plan(json.dumps(task))
            if not plan.success:
                return plan
            
            # Execute each subtask
            for subtask in task["subtasks"]:
                result = await self.delegate_task(subtask)
                results.append(result)
                if not result.success:
                    break
            
            success = all(r.success for r in results)
            
            # Store final coordination in memory
            self.memory_manager.store_memory(
                content=json.dumps({
                    "task": task,
                    "plan": plan.artifacts,
                    "results": [r.artifacts for r in results]
                }),
                metadata={
                    "type": "task_coordination",
                    "success": success,
                    "timestamp": datetime.now().isoformat()
                }
            )
            
            return TaskResult(
                success=success,
                message="Task completed",
                artifacts={
                    "plan": plan.artifacts,
                    "results": [r.artifacts for r in results]
                }
            )
            
        except Exception as e:
            return TaskResult(
                success=False,
                message=f"Task coordination failed: {str(e)}",
                artifacts={},
                error=str(e)
            )
            
    async def execute_task(self, task: Dict) -> TaskResult:
        """Execute a task using the agent system.
        
        Args:
            task: Task specification
            
        Returns:
            Task execution result
        """
        max_retries = 3
        last_error = None
        
        try:
            # Create plan
            plan = await self.planner.create_plan(json.dumps(task))
            if not plan.success:
                return plan
                
            # Execute plan with retry
            for attempt in range(max_retries):
                result = await self.executor.execute_task(plan.artifacts)
                if result.success:
                    # Analyze success
                    analysis = await self.reflector.analyze_execution(result)
                    
                    # Store success in memory
                    self.memory_manager.store_memory(
                        content=json.dumps({
                            "task": task,
                            "plan": plan.artifacts,
                            "execution": result.artifacts,
                            "analysis": analysis.artifacts
                        }),
                        metadata={
                            "type": "task_result",
                            "success": True,
                            "timestamp": datetime.now().isoformat()
                        }
                    )
                    
                    return TaskResult(
                        success=True,
                        message=result.message,  # Use the original success message
                        artifacts={
                            "plan": plan.artifacts,
                            "execution": result.artifacts,
                            "analysis": analysis.artifacts,
                            "result": result.artifacts.get("result", "success")
                        }
                    )
                    
                # Analyze failure
                analysis = await self.reflector.analyze_failure(result.artifacts)
                if analysis.success:
                    # Get improvements
                    improvements = await self.reflector.suggest_improvements(analysis.artifacts)
                    if improvements.success:
                        # Update plan
                        message = AgentMessage(
                            sender=AgentRole.REFLECTOR,
                            recipient=AgentRole.PLANNER,
                            content=json.dumps(improvements.artifacts),
                            metadata={"type": "improvement_suggestions"}
                        )
                        await self.planner.handle_feedback(message)
                        
                        # Get updated plan
                        plan = await self.planner.create_plan(json.dumps(task))
                        if not plan.success:
                            return plan
                            
                last_error = result.error
                
            # All attempts failed
            error_msg = f"Task failed after {max_retries} attempts: {last_error}"
            
            # Store error in memory
            self.memory_manager.store_memory(
                content=json.dumps({
                    "task": task,
                    "error": error_msg,
                    "attempts": max_retries
                }),
                metadata={
                    "type": "task_error",
                    "success": False,
                    "timestamp": datetime.now().isoformat()
                }
            )
            
            return TaskResult(
                success=False,
                message=error_msg,
                artifacts={"result": None},
                error=last_error
            )
            
        except Exception as e:
            error_msg = f"Task failed after {max_retries} attempts: {str(e)}"
            
            # Store error in memory
            self.memory_manager.store_memory(
                content=json.dumps({
                    "task": task,
                    "error": error_msg,
                    "attempts": max_retries
                }),
                metadata={
                    "type": "task_error",
                    "success": False,
                    "timestamp": datetime.now().isoformat()
                }
            )
            
            return TaskResult(
                success=False,
                message=error_msg,
                artifacts={"result": None},
                error=str(e)
            )
        """Execute a task using the agent system.
        
        Args:
            task: Task description
            
        Returns:
            Task execution result
        """
        try:
            # Execute task with agent
            result = await self.agent_executor.arun(
                input=task,
                return_intermediate_steps=True
            )
            
            # Store task result in memory
            self.memory_manager.store_memory(
                content=str(result),
                metadata={
                    "type": "task_result",
                    "task": task,
                    "timestamp": datetime.now().isoformat()
                }
            )
            
            return TaskResult(
                success=True,
                message="Task completed successfully",
                artifacts={"result": result}
            )
            
        except Exception as e:
            error_msg = f"Task execution failed: {str(e)}"
            
            # Store error in memory
            self.memory_manager.store_memory(
                content=error_msg,
                metadata={
                    "type": "task_error",
                    "task": task,
                    "timestamp": datetime.now().isoformat()
                }
            )
            
            return TaskResult(
                success=False,
                message=error_msg,
                artifacts={},
                error=str(e)
            )
