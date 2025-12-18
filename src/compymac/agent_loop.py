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
"""

import json
import logging
from dataclasses import dataclass, field

from compymac.harness import EventLog, EventType, Harness
from compymac.llm import LLMClient
from compymac.types import Message, ToolCall, ToolResult

logger = logging.getLogger(__name__)


@dataclass
class AgentConfig:
    """Configuration for the agent loop."""
    max_steps: int = 50
    max_tool_calls_per_step: int = 10
    system_prompt: str = ""
    stop_on_error: bool = False


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
    ):
        self.harness = harness
        self.llm_client = llm_client
        self.config = config or AgentConfig()
        self.state = AgentState()
        self._event_log = self.harness.get_event_log()

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
        Run a single step of the agent loop.

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

        # Get tool schemas from harness
        tools = self.harness.get_tool_schemas()

        # Call LLM
        self._event_log.log_event(
            EventType.LLM_REQUEST,
            tool_call_id=f"step_{self.state.step_count}",
            message_count=len(self.state.messages),
        )

        # Convert Message objects to dicts for API serialization
        messages_for_api = [msg.to_dict() for msg in self.state.messages]

        response = self.llm_client.chat(
            messages=messages_for_api,
            tools=tools if tools else None,
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

        # If no tool calls, return text response
        if not response.tool_calls:
            self._event_log.log_event(
                EventType.AGENT_TURN_END,
                tool_call_id=f"step_{self.state.step_count}",
                has_tool_calls=False,
            )
            return response.content, []

        # Execute tool calls through harness
        tool_results = []
        for tool_call in response.tool_calls:
            self.state.tool_call_count += 1

            # Execute through harness
            result = self.harness.execute(tool_call)
            tool_results.append(result)

            # Add tool result to messages
            self.state.messages.append(Message(
                role="tool",
                content=result.content,
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

        return None, tool_results

    def run(self, user_input: str) -> str:
        """
        Run the agent loop until completion or max steps.

        Returns the final text response from the agent.
        """
        self.add_user_message(user_input)

        while self.state.step_count < self.config.max_steps:
            text_response, tool_results = self.run_step()

            # If we got a text response with no tool calls, we're done
            if text_response is not None and not tool_results:
                self.state.is_complete = True
                self.state.final_response = text_response
                return text_response

            # If we hit max tool calls, stop
            if self.state.tool_call_count >= self.config.max_steps * self.config.max_tool_calls_per_step:
                logger.warning("Max tool calls reached")
                break

        # If we exit the loop without a final response, return last content
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
