"""
AgentLoop - Turn-based agent execution against a Harness.

This module implements the core agent loop that:
1. Receives user input
2. Sends context to LLM
3. Parses tool calls from LLM response
4. Executes tools through the Harness
5. Feeds results back to LLM
6. Repeats until task complete or max steps reached

The loop is harness-agnostic - it works with Simulator, LocalHarness, or ReplayHarness.

Supports optional TraceContext for complete execution capture including:
- Every main loop iteration (even pure reasoning with no tools)
- Every LLM request/response
- Every tool call (delegated to Harness)
"""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from compymac.harness import EventLog, EventType, Harness
from compymac.llm import LLMClient
from compymac.types import Message, ToolCall, ToolResult

if TYPE_CHECKING:
    from compymac.memory import MemoryManager
    from compymac.trace_store import TraceContext, TraceStore

logger = logging.getLogger(__name__)


@dataclass
class AgentConfig:
    """Configuration for the agent loop."""
    max_steps: int = 50
    max_tool_calls_per_step: int = 10
    system_prompt: str = ""
    stop_on_error: bool = False
    use_memory: bool = False  # Enable smart memory management
    memory_compression_threshold: float = 0.80  # Compress when utilization exceeds this
    memory_keep_recent_turns: int = 4  # Number of recent turns to always keep
    trace_base_path: Path | None = None  # Base path for trace storage (enables tracing if set)
    summarize_tool_output: bool = True  # Enable tool output summarization to reduce context
    # Action-gated dialogue protocol (MUD-style)
    action_gated: bool = False  # If True, agent must call a tool every turn (no prose-only responses)
    max_invalid_moves: int = 5  # Max consecutive turns without tool calls before failing
    require_complete_tool: bool = False  # If True, agent must call 'complete' tool to finish


@dataclass
class AgentState:
    """Current state of the agent."""
    messages: list[Message] = field(default_factory=list)
    step_count: int = 0
    tool_call_count: int = 0
    is_complete: bool = False
    final_response: str = ""


class AgentLoop:
    """
    Turn-based agent loop that executes against a Harness.

    The loop follows this pattern:
    1. User provides input
    2. Agent sends context to LLM
    3. LLM returns either text response or tool calls
    4. If tool calls: execute through Harness, add results to context, goto 2
    5. If text response: return to user (or continue if not final)
    """

    def __init__(
        self,
        harness: Harness,
        llm_client: LLMClient,
        config: AgentConfig | None = None,
        trace_context: "TraceContext | None" = None,
    ):
        self.harness = harness
        self.llm_client = llm_client
        self.config = config or AgentConfig()
        self.state = AgentState()
        self._event_log = self.harness.get_event_log()
        self._memory_manager: "MemoryManager | None" = None  # noqa: UP037
        self._trace_context: "TraceContext | None" = trace_context  # noqa: UP037
        self._trace_store: "TraceStore | None" = None  # noqa: UP037

        # Initialize tracing if base path is configured
        if self.config.trace_base_path and not self._trace_context:
            from compymac.trace_store import TraceContext, create_trace_store
            self._trace_store, _ = create_trace_store(self.config.trace_base_path)
            self._trace_context = TraceContext(self._trace_store)

        # Pass trace context to harness if available
        if self._trace_context:
            self.harness.set_trace_context(self._trace_context)

        # Initialize memory manager if enabled
        if self.config.use_memory:
            from compymac.config import ContextConfig
            from compymac.memory import MemoryManager
            self._memory_manager = MemoryManager(
                config=ContextConfig.from_env(),
                llm_client=llm_client,
                keep_recent_turns=self.config.memory_keep_recent_turns,
                compression_threshold=self.config.memory_compression_threshold,
            )

        # Initialize with system prompt if provided
        if self.config.system_prompt:
            self.state.messages.append(Message(
                role="system",
                content=self.config.system_prompt,
            ))

    def add_user_message(self, content: str) -> None:
        """Add a user message to the conversation."""
        self.state.messages.append(Message(role="user", content=content))

    def run_step(self) -> tuple[str | None, list[ToolResult]]:
        """
        Run a single step of the agent loop with optional trace capture.

        Returns (text_response, tool_results).
        - If LLM returns text: (text, [])
        - If LLM returns tool calls: (None, [results])
        """
        self.state.step_count += 1

        self._event_log.log_event(
            EventType.AGENT_TURN_START,
            tool_call_id=f"step_{self.state.step_count}",
            step=self.state.step_count,
        )

        # Start agent turn span if tracing is enabled
        turn_span_id: str | None = None
        if self._trace_context:
            from compymac.trace_store import SpanKind
            turn_span_id = self._trace_context.start_span(
                kind=SpanKind.AGENT_TURN,
                name=f"agent_turn_{self.state.step_count}",
                actor_id="agent_loop",
                attributes={
                    "step_count": self.state.step_count,
                    "message_count": len(self.state.messages),
                },
            )

        # Get tool schemas from harness
        tools = self.harness.get_tool_schemas()

        # Call LLM
        self._event_log.log_event(
            EventType.LLM_REQUEST,
            tool_call_id=f"step_{self.state.step_count}",
            message_count=len(self.state.messages),
        )

        # Process messages through memory manager if enabled
        messages_to_send = self.state.messages
        if self._memory_manager:
            messages_to_send = self._memory_manager.process_messages(self.state.messages)
            # Update state with compressed messages if compression occurred
            if len(messages_to_send) < len(self.state.messages):
                self.state.messages = messages_to_send
                self._event_log.log_event(
                    EventType.OUTPUT_TRUNCATION,  # Reuse truncation event type
                    tool_call_id=f"step_{self.state.step_count}",
                    original_count=len(self.state.messages),
                    compressed_count=len(messages_to_send),
                    memory_state=str(self._memory_manager.get_memory_state().facts.to_dict()),
                )

        # Convert Message objects to dicts for API serialization
        messages_for_api = [msg.to_dict() for msg in messages_to_send]

        # Start LLM call span if tracing is enabled
        llm_span_id: str | None = None
        llm_input_artifact_hash: str | None = None
        if self._trace_context:
            from compymac.trace_store import SpanKind

            # Store LLM input as artifact
            llm_input_data = json.dumps({
                "messages": messages_for_api,
                "tools": tools,
            }).encode()
            llm_input_artifact = self._trace_context.store_artifact(
                data=llm_input_data,
                artifact_type="llm_input",
                content_type="application/json",
                metadata={"step": self.state.step_count},
            )
            llm_input_artifact_hash = llm_input_artifact.artifact_hash

            llm_span_id = self._trace_context.start_span(
                kind=SpanKind.LLM_CALL,
                name="llm_chat",
                actor_id="llm_client",
                attributes={
                    "message_count": len(messages_for_api),
                    "has_tools": bool(tools),
                },
                input_artifact_hash=llm_input_artifact_hash,
            )

        response = self.llm_client.chat(
            messages=messages_for_api,
            tools=tools if tools else None,
        )

        # End LLM call span if tracing is enabled
        if self._trace_context and llm_span_id:
            from compymac.trace_store import SpanStatus

            # Store LLM output as artifact (including token usage for total capture)
            llm_output_data = json.dumps({
                "content": response.content,
                "tool_calls": [
                    {"id": tc.id, "name": tc.name, "arguments": tc.arguments}
                    for tc in (response.tool_calls or [])
                ],
                "usage": response.usage.to_dict(),
                "finish_reason": response.finish_reason,
            }).encode()
            llm_output_artifact = self._trace_context.store_artifact(
                data=llm_output_data,
                artifact_type="llm_output",
                content_type="application/json",
                metadata={"step": self.state.step_count},
            )

            self._trace_context.end_span(
                status=SpanStatus.OK,
                output_artifact_hash=llm_output_artifact.artifact_hash,
            )

        self._event_log.log_event(
            EventType.LLM_RESPONSE,
            tool_call_id=f"step_{self.state.step_count}",
            has_tool_calls=bool(response.tool_calls),
            content_length=len(response.content) if response.content else 0,
        )

        # Add assistant message to history
        # Convert ToolCall objects to dicts for serialization
        tool_calls_as_dicts = None
        if response.tool_calls:
            tool_calls_as_dicts = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": tc.arguments if isinstance(tc.arguments, str) else json.dumps(tc.arguments),
                    }
                }
                for tc in response.tool_calls
            ]

        self.state.messages.append(Message(
            role="assistant",
            content=response.content or "",
            tool_calls=tool_calls_as_dicts,
        ))

        # If no tool calls, this is a reasoning step - end turn span and return
        if not response.tool_calls:
            self._event_log.log_event(
                EventType.AGENT_TURN_END,
                tool_call_id=f"step_{self.state.step_count}",
                has_tool_calls=False,
            )

            # End agent turn span if tracing is enabled
            if self._trace_context and turn_span_id:
                from compymac.trace_store import SpanStatus
                self._trace_context.end_span(
                    status=SpanStatus.OK,
                )

            return response.content, []

        # Execute tool calls through harness (harness handles its own tracing)
        tool_results = []
        for tool_call in response.tool_calls:
            self.state.tool_call_count += 1

            # Execute through harness
            result = self.harness.execute(tool_call)
            tool_results.append(result)

            # Summarize tool output if enabled to reduce context bloat
            content_for_message = result.content
            if self.config.summarize_tool_output and result.content:
                from compymac.memory import ToolOutputSummarizer
                original_len = len(result.content)
                content_for_message = ToolOutputSummarizer.summarize(
                    tool_call.name, result.content
                )
                if len(content_for_message) < original_len:
                    logger.debug(
                        f"Summarized {tool_call.name} output: "
                        f"{original_len} -> {len(content_for_message)} chars"
                    )

            # Add tool result to messages
            self.state.messages.append(Message(
                role="tool",
                content=content_for_message,
                tool_call_id=result.tool_call_id,
            ))

            # Check for errors
            if not result.success and self.config.stop_on_error:
                logger.warning(f"Tool call failed: {result.error}")

        self._event_log.log_event(
            EventType.AGENT_TURN_END,
            tool_call_id=f"step_{self.state.step_count}",
            has_tool_calls=True,
            tool_call_count=len(tool_results),
        )

        # End agent turn span if tracing is enabled
        if self._trace_context and turn_span_id:
            from compymac.trace_store import SpanStatus
            self._trace_context.end_span(
                status=SpanStatus.OK,
            )

        return None, tool_results

    def run(self, user_input: str) -> str:
        """
        Run the agent loop until completion or max steps.

        Returns the final text response from the agent.

        In action-gated mode (config.action_gated=True):
        - Agent must call a tool every turn (prose-only responses are invalid)
        - If config.require_complete_tool=True, agent must call 'complete' tool to finish
        - Invalid moves trigger a corrective message and retry (up to max_invalid_moves)
        """
        self.add_user_message(user_input)
        invalid_move_count = 0

        while self.state.step_count < self.config.max_steps:
            text_response, tool_results = self.run_step()

            # Check if 'complete' tool was called (signals task completion)
            complete_called = False
            complete_answer = ""
            for _result in tool_results:
                # Check if this was a 'complete' tool call
                if hasattr(self.harness, '_completion_signaled') and self.harness._completion_signaled:
                    complete_called = True
                    complete_answer = getattr(self.harness, '_completion_answer', text_response or "")
                    # Reset the flag for potential future runs
                    self.harness._completion_signaled = False
                    break

            # In action-gated mode with require_complete_tool, only finish on 'complete' call
            if self.config.action_gated and self.config.require_complete_tool:
                if complete_called:
                    self.state.is_complete = True
                    self.state.final_response = complete_answer
                    return complete_answer

                # If no tool calls at all, this is an invalid move
                if text_response is not None and not tool_results:
                    invalid_move_count += 1
                    logger.warning(f"Invalid move {invalid_move_count}/{self.config.max_invalid_moves}: "
                                   "Agent returned text without tool call")

                    if invalid_move_count >= self.config.max_invalid_moves:
                        error_msg = (f"Failed: {invalid_move_count} consecutive invalid moves. "
                                     "Agent must call a tool each turn.")
                        self.state.final_response = error_msg
                        return error_msg

                    # Inject corrective message and continue
                    self.state.messages.append(Message(
                        role="user",
                        content=(
                            "Invalid move. You MUST choose exactly ONE action by calling a tool. "
                            "If you want to finish, call complete(final_answer=...). "
                            "Available actions: Read, Edit, bash, grep, glob, think, complete."
                        ),
                    ))
                    continue
                else:
                    # Valid tool call - reset invalid move counter
                    invalid_move_count = 0

            # Standard mode (non-action-gated) or action-gated without require_complete_tool
            elif not self.config.action_gated:
                # If we got a text response with no tool calls, we're done
                if text_response is not None and not tool_results:
                    self.state.is_complete = True
                    self.state.final_response = text_response
                    return text_response

            # Action-gated mode without require_complete_tool
            # Accept 'complete' tool OR prose-only response as completion
            else:
                if complete_called:
                    self.state.is_complete = True
                    self.state.final_response = complete_answer
                    return complete_answer

                # If no tool calls, this is an invalid move - inject corrective message
                if text_response is not None and not tool_results:
                    invalid_move_count += 1
                    logger.warning(f"Invalid move {invalid_move_count}/{self.config.max_invalid_moves}: "
                                   "Agent returned text without tool call")

                    if invalid_move_count >= self.config.max_invalid_moves:
                        error_msg = (f"Failed: {invalid_move_count} consecutive invalid moves. "
                                     "Agent must call a tool each turn.")
                        self.state.final_response = error_msg
                        return error_msg

                    # Inject corrective message and continue
                    self.state.messages.append(Message(
                        role="user",
                        content=(
                            "Invalid move. You MUST choose exactly ONE action by calling a tool. "
                            "If you want to finish, call complete(final_answer=...). "
                            "Available actions: Read, Edit, bash, grep, glob, think, complete."
                        ),
                    ))
                    continue
                else:
                    # Valid tool call - reset invalid move counter
                    invalid_move_count = 0

            # If we hit max tool calls, stop
            if self.state.tool_call_count >= self.config.max_steps * self.config.max_tool_calls_per_step:
                logger.warning("Max tool calls reached")
                break

        # If we exit the loop without a final response, return failure in action-gated mode
        if self.config.action_gated:
            error_msg = "Failed: Max steps reached without calling complete() tool."
            self.state.final_response = error_msg
            return error_msg

        # Standard mode: return last content
        for msg in reversed(self.state.messages):
            if msg.role == "assistant" and msg.content:
                self.state.final_response = msg.content
                return msg.content

        return "Agent loop completed without final response"

    def run_with_policy(
        self,
        policy: "Policy",
        initial_input: str,
    ) -> str:
        """
        Run the agent loop with a custom policy for tool call generation.

        This is useful for testing without an LLM - the policy generates
        tool calls based on the current state.
        """
        self.add_user_message(initial_input)

        while self.state.step_count < self.config.max_steps:
            self.state.step_count += 1

            # Get tool calls from policy
            tool_calls = policy.get_tool_calls(self.state)

            if not tool_calls:
                # Policy says we're done
                response = policy.get_final_response(self.state)
                self.state.is_complete = True
                self.state.final_response = response
                return response

            # Execute tool calls
            for tool_call in tool_calls:
                result = self.harness.execute(tool_call)
                self.state.messages.append(Message(
                    role="tool",
                    content=result.content,
                    tool_call_id=result.tool_call_id,
                ))

        return "Policy loop completed"

    def get_state(self) -> AgentState:
        """Get the current agent state."""
        return self.state

    def reset(self) -> None:
        """Reset the agent state for a new conversation."""
        self.state = AgentState()
        if self.config.system_prompt:
            self.state.messages.append(Message(
                role="system",
                content=self.config.system_prompt,
            ))


class Policy:
    """
    Abstract policy for generating tool calls without an LLM.

    Useful for deterministic testing and replay.
    """

    def get_tool_calls(self, state: AgentState) -> list[ToolCall]:
        """Generate tool calls based on current state. Return empty list to stop."""
        raise NotImplementedError

    def get_final_response(self, state: AgentState) -> str:
        """Generate final response when no more tool calls."""
        raise NotImplementedError


class ScriptedPolicy(Policy):
    """
    Policy that executes a predefined sequence of tool calls.

    Useful for deterministic testing.
    """

    def __init__(self, tool_calls: list[ToolCall], final_response: str = "Done"):
        self._tool_calls = list(tool_calls)
        self._index = 0
        self._final_response = final_response

    def get_tool_calls(self, state: AgentState) -> list[ToolCall]:
        if self._index >= len(self._tool_calls):
            return []

        call = self._tool_calls[self._index]
        self._index += 1
        return [call]

    def get_final_response(self, state: AgentState) -> str:
        return self._final_response


class ReplayPolicy(Policy):
    """
    Policy that replays tool calls from an event log.

    Useful for reproducing runs from traces.
    """

    def __init__(self, event_log: EventLog):
        self._event_log = event_log
        self._tool_calls = self._extract_tool_calls()
        self._index = 0

    def _extract_tool_calls(self) -> list[ToolCall]:
        """Extract tool calls from event log."""
        calls = []
        for event in self._event_log.events:
            if event.event_type == EventType.TOOL_CALL_RECEIVED:
                calls.append(ToolCall(
                    id=event.tool_call_id,
                    name=event.data.get("tool_name", ""),
                    arguments=event.data.get("arguments", {}),
                ))
        return calls

    def get_tool_calls(self, state: AgentState) -> list[ToolCall]:
        if self._index >= len(self._tool_calls):
            return []

        call = self._tool_calls[self._index]
        self._index += 1
        return [call]

    def get_final_response(self, state: AgentState) -> str:
        return "Replay complete"
