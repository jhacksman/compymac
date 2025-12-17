"""
Agent Loop - The turn-based runtime.

This is the core execution loop that defines how the agent processes
input and produces output. The loop is:

1. Build context (with truncation if needed)
2. Call LLM
3. If LLM returns tool calls: execute tools, add results, goto 2
4. If LLM returns final response: return to user, wait for next input

The loop has a hard max_steps limit to prevent runaway execution.
This is an operational constraint that exists in real agent systems.
"""

import logging
from dataclasses import dataclass, field

from compymac.config import AgentConfig, LoopConfig
from compymac.context import ContextManager
from compymac.llm import LLMClient, LLMError
from compymac.session import Session
from compymac.tools import ToolRegistry
from compymac.types import LoopState

logger = logging.getLogger(__name__)


@dataclass
class StepResult:
    """Result of a single step in the agent loop."""
    step_number: int
    action: str
    content: str | None = None
    tool_calls_made: int = 0
    tokens_used: int = 0
    truncation_occurred: bool = False


@dataclass
class LoopResult:
    """Final result of running the agent loop."""
    success: bool
    response: str | None
    steps_taken: int
    step_results: list[StepResult] = field(default_factory=list)
    error: str | None = None
    stopped_reason: str = "completed"


class AgentLoop:
    """
    The turn-based agent execution loop.

    This loop embodies the fundamental constraint of turn-based processing:
    the agent processes one turn, produces a response, and waits for the
    next input. There is no background processing or continuous execution.

    The loop also enforces the max_steps constraint to prevent runaway
    execution - a safety measure that exists in real agent systems.
    """

    def __init__(
        self,
        session: Session,
        llm: LLMClient,
        tools: ToolRegistry,
        context_manager: ContextManager,
        config: LoopConfig | None = None,
    ) -> None:
        """Initialize the agent loop."""
        self.session = session
        self.llm = llm
        self.tools = tools
        self.context_manager = context_manager
        self.config = config or LoopConfig.from_env()
        self.state = LoopState(max_steps=self.config.max_steps)

    def run(self, user_input: str) -> LoopResult:
        """
        Run the agent loop for a single user turn.

        This is the main entry point. It:
        1. Adds the user message to the session
        2. Runs the loop until completion or max_steps
        3. Returns the final result

        Args:
            user_input: The user's message

        Returns:
            LoopResult with the agent's response
        """
        self.session.add_user_message(user_input)

        self.state = LoopState(max_steps=self.config.max_steps)
        step_results: list[StepResult] = []

        while not self.state.finished and self.state.step < self.state.max_steps:
            self.state.step += 1
            logger.info(f"Agent loop step {self.state.step}/{self.state.max_steps}")

            try:
                step_result = self._execute_step()
                step_results.append(step_result)

                if step_result.action == "final_response":
                    self.state.finished = True
                    self.state.final_response = step_result.content

            except LLMError as e:
                logger.error(f"LLM error at step {self.state.step}: {e}")
                self.state.finished = True
                self.state.error = str(e)
                return LoopResult(
                    success=False,
                    response=None,
                    steps_taken=self.state.step,
                    step_results=step_results,
                    error=str(e),
                    stopped_reason="llm_error",
                )
            except Exception as e:
                logger.error(f"Unexpected error at step {self.state.step}: {e}")
                self.state.finished = True
                self.state.error = str(e)
                return LoopResult(
                    success=False,
                    response=None,
                    steps_taken=self.state.step,
                    step_results=step_results,
                    error=str(e),
                    stopped_reason="unexpected_error",
                )

        if self.state.step >= self.state.max_steps and not self.state.finished:
            logger.warning(f"Agent loop hit max_steps limit ({self.state.max_steps})")
            return LoopResult(
                success=False,
                response=self.state.final_response,
                steps_taken=self.state.step,
                step_results=step_results,
                error="Max steps exceeded",
                stopped_reason="max_steps_exceeded",
            )

        return LoopResult(
            success=True,
            response=self.state.final_response,
            steps_taken=self.state.step,
            step_results=step_results,
            stopped_reason="completed",
        )

    def _execute_step(self) -> StepResult:
        """Execute a single step of the agent loop."""
        truncation_before = self.session.total_truncations
        messages, budget = self.context_manager.build_context(
            self.session,
            tools=self.tools.get_schemas() if len(self.tools) > 0 else None,
        )
        truncation_occurred = self.session.total_truncations > truncation_before

        tool_schemas = self.tools.get_schemas() if len(self.tools) > 0 else None
        response = self.llm.chat(messages, tools=tool_schemas)

        if response.has_tool_calls:
            self.session.add_assistant_message(
                content=response.content,
                tool_calls=[
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": str(tc.arguments),
                        },
                    }
                    for tc in response.tool_calls
                ],
            )

            for tool_call in response.tool_calls:
                logger.info(f"Executing tool: {tool_call.name}")
                result = self.tools.execute(tool_call)
                self.session.add_tool_result(result)

            return StepResult(
                step_number=self.state.step,
                action="tool_calls",
                content=response.content,
                tool_calls_made=len(response.tool_calls),
                tokens_used=budget.used,
                truncation_occurred=truncation_occurred,
            )
        else:
            self.session.add_assistant_message(content=response.content)

            return StepResult(
                step_number=self.state.step,
                action="final_response",
                content=response.content,
                tool_calls_made=0,
                tokens_used=budget.used,
                truncation_occurred=truncation_occurred,
            )

    @classmethod
    def create(
        cls,
        system_prompt: str = "",
        config: AgentConfig | None = None,
        tools: ToolRegistry | None = None,
    ) -> "AgentLoop":
        """
        Factory method to create an AgentLoop with all dependencies.

        This is the recommended way to create an AgentLoop for typical use.
        """
        config = config or AgentConfig.from_env()

        session = Session(system_prompt=system_prompt)
        llm = LLMClient(config.llm)
        context_manager = ContextManager(config.context)
        tools = tools or ToolRegistry()

        return cls(
            session=session,
            llm=llm,
            tools=tools,
            context_manager=context_manager,
            config=config.loop,
        )
