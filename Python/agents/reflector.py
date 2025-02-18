"""Reflection agent for monitoring and improving system performance."""

from typing import Dict, List, Optional
from datetime import datetime
import json

from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from langchain.memory import ConversationBufferMemory
from langchain_core.language_models.llms import BaseLLM

from .protocols import AgentRole, AgentMessage, TaskResult
from ..memory import MemoryManager

class ReflectorAgent:
    """Reflection agent for monitoring and improving system performance."""
    
    def __init__(self, memory_manager: Optional[MemoryManager] = None, llm: Optional[BaseLLM] = None):
        """Initialize reflection agent.
        
        Args:
            memory_manager: Optional memory manager for context
            llm: Optional LLM instance
        """
        self.memory_manager = memory_manager
        self._llm = llm
        self.memory = ConversationBufferMemory(
            memory_key="reflection_history",
            return_messages=True
        )
        
        # Set up reflection chain
        self.reflection_chain = self._setup_reflection_chain()
        
    def _setup_reflection_chain(self) -> LLMChain:
        """Set up the reflection chain with LangChain.
        
        Returns:
            Configured reflection chain
        """
        prompt = PromptTemplate(
            template="""You are a reflection agent that analyzes task execution and suggests improvements.

Previous reflections:
{reflection_history}

Current execution result:
{result}

Think through the following:
1. Was the task successful? Why or why not?
2. What could be improved?
3. Are there any patterns to learn from?
4. Should we adjust our strategy?

Your response should be in JSON format:
{{
    "success": true,
    "message": "Analysis complete",
    "artifacts": {{
        "analysis": {{
            "success": true,
            "key_observations": ["Observation 1", "Observation 2"],
            "improvement_areas": ["Area 1", "Area 2"]
        }},
        "recommendations": [
            {{
                "type": "strategy_change",
                "description": "Suggested improvement",
                "priority": 1
            }}
        ],
        "learning_outcomes": [
            "Lesson learned"
        ]
    }}
}}

Response:""",
            input_variables=["result", "reflection_history"]
        )
        
        chain = prompt | self._llm
        return chain
        
    async def analyze_execution(self, result: TaskResult) -> TaskResult:
        """Analyze task execution.
        
        Args:
            result: Task execution result
            
        Returns:
            Analysis result
        """
        try:
            # Store result in memory if manager exists
            if self.memory_manager:
                self.memory_manager.store_memory(
                    content=json.dumps(result.artifacts),
                    metadata={
                        "type": "execution_analysis",
                        "success": result.success,
                        "timestamp": datetime.now().isoformat()
                    }
                )
            
            # Generate analysis
            analysis = await self.reflection_chain.ainvoke({
                "result": json.dumps(result.artifacts),
                "reflection_history": ""
            })
            
            return TaskResult(
                success=True,
                message="Analysis complete",
                artifacts=analysis
            )
            
        except Exception as e:
            return TaskResult(
                success=False,
                message=f"Analysis failed: {str(e)}",
                artifacts={},
                error=str(e)
            )
            
    async def analyze_failure(self, error: Dict) -> TaskResult:
        """Analyze task failure.
        
        Args:
            error: Error information
            
        Returns:
            Analysis result
        """
        try:
            # Store error in memory if manager exists
            if self.memory_manager:
                metadata = {
                    "type": "failure_analysis",
                    "timestamp": datetime.now().isoformat(),
                    "tags": ["failure_analysis", "error"]
                }
                self.memory_manager.store_memory(
                    content=json.dumps(error),
                    metadata=metadata
                )
            
            # Generate analysis
            result = await self._llm.ainvoke({
                "task": json.dumps(error),
                "type": "analyze_failure"
            })
            
            # Parse JSON response
            response = json.loads(result)
            
            # Extract artifacts from response
            artifacts = response.get("artifacts", {})
            
            # Return task result with artifacts
            return TaskResult(
                success=True,
                message="Analysis complete",
                artifacts=artifacts
            )
            
        except Exception as e:
            return TaskResult(
                success=False,
                message=f"Analysis failed: {str(e)}",
                artifacts={},
                error=str(e)
            )
            
    async def suggest_improvements(self, context: Dict) -> Dict:
        """Suggest improvements based on context.
        
        Args:
            context: Current context
            
        Returns:
            Improvement suggestions
        """
        try:
            # Store context in memory if manager exists
            if self.memory_manager:
                metadata = {
                    "type": "improvement_suggestions",
                    "timestamp": datetime.now().isoformat(),
                    "tags": ["improvements", "suggestions"]
                }
                self.memory_manager.store_memory(
                    content=json.dumps(context),
                    metadata=metadata
                )
            
            # Generate suggestions
            result = await self._llm.ainvoke({
                "task": json.dumps(context),
                "type": "suggest_improvements"
            })
            
            # Parse JSON response
            response = json.loads(result)
            
            # Extract artifacts from response
            artifacts = response.get("artifacts", {})
            
            # Return task result with artifacts
            return TaskResult(
                success=True,
                message="Improvements suggested",
                artifacts=artifacts
            )
            
        except Exception as e:
            return TaskResult(
                success=False,
                message=f"Failed to suggest improvements: {str(e)}",
                artifacts={},
                error=str(e)
            )
            
    async def evaluate_performance(self, metrics: Dict) -> Dict:
        """Evaluate agent performance.
        
        Args:
            metrics: Performance metrics
            
        Returns:
            Evaluation result
        """
        try:
            # Store metrics in memory if manager exists
            if self.memory_manager:
                metadata = {
                    "type": "performance_evaluation",
                    "timestamp": datetime.now().isoformat(),
                    "tags": ["performance", "metrics"]
                }
                self.memory_manager.store_memory(
                    content=json.dumps(metrics),
                    metadata=metadata
                )
            
            # Generate evaluation
            result = await self._llm.ainvoke({
                "task": json.dumps(metrics),
                "type": "evaluate_performance"
            })
            
            # Parse JSON response
            response = json.loads(result)
            
            # Extract artifacts from response
            artifacts = response.get("artifacts", {})
            
            # Return task result with artifacts
            return TaskResult(
                success=True,
                message="Evaluation complete",
                artifacts=artifacts
            )
            
        except Exception as e:
            return TaskResult(
                success=False,
                message=f"Evaluation failed: {str(e)}",
                artifacts={},
                error=str(e)
            )
        try:
            # Get relevant context if memory manager exists
            context = ""
            if self.memory_manager:
                memories = self.memory_manager.retrieve_context(
                    query=result.message,
                    time_range="7d"  # Last week
                )
                if memories:
                    context = "\nRelevant context:\n" + "\n".join(
                        f"- {m['content']}" for m in memories
                    )
            
            # Generate reflection
            reflection_input = {
                "success": result.success,
                "message": result.message,
                "error": result.error,
                "artifacts": result.artifacts,
                "context": context
            }
            
            result = self.reflection_chain.predict(
                result=json.dumps(reflection_input, indent=2)
            )
            
            # Parse JSON response
            analysis = json.loads(result)
            
            # Store reflection in memory if manager exists
            if self.memory_manager:
                self.memory_manager.store_memory(
                    content=json.dumps(analysis, indent=2),
                    metadata={
                        "type": "task_reflection",
                        "success": reflection_input["success"],
                        "timestamp": datetime.now().isoformat()
                    }
                )
            
            return TaskResult(
                success=True,
                message="Analysis complete",
                artifacts=analysis
            )
            
        except Exception as e:
            # Return minimal valid analysis on error
            return TaskResult(
                success=False,
                message=f"Analysis failed: {str(e)}",
                artifacts={
                    "analysis": {
                        "success": False,
                        "key_observations": [f"Error in reflection: {str(e)}"],
                        "improvement_areas": ["Error handling"]
                    },
                    "recommendations": [{
                        "type": "error_prevention",
                        "description": "Implement better error handling in reflection",
                        "priority": 5
                    }],
                    "learning_outcomes": [
                        "Need to improve reflection system robustness"
                    ]
                },
                error=str(e)
            )
