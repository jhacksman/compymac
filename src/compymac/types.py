"""
Core types for the agent system.

These types represent the fundamental data structures that flow through
the agent loop. They are intentionally simple - complexity here would
obscure the baseline constraints we're trying to understand.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any


class Role(str, Enum):
    """Message roles in the conversation."""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


@dataclass
class Message:
    """
    A single message in the conversation history.

    This is the fundamental unit of context. Messages accumulate in the
    session until they exceed the context budget, at which point the
    oldest messages are truncated (not summarized - that would be an
    improvement over the baseline).
    """
    role: Role
    content: str
    name: str | None = None
    tool_call_id: str | None = None
    tool_calls: list[dict[str, Any]] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to OpenAI API format."""
        result: dict[str, Any] = {
            "role": self.role.value,
            "content": self.content,
        }
        if self.name is not None:
            result["name"] = self.name
        if self.tool_call_id is not None:
            result["tool_call_id"] = self.tool_call_id
        if self.tool_calls is not None:
            result["tool_calls"] = self.tool_calls
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Message":
        """Create from OpenAI API format."""
        return cls(
            role=Role(data["role"]),
            content=data.get("content", ""),
            name=data.get("name"),
            tool_call_id=data.get("tool_call_id"),
            tool_calls=data.get("tool_calls"),
        )


@dataclass
class ToolCall:
    """
    A request from the LLM to execute a tool.

    This is the ONLY way the agent can affect the world. The agent cannot
    directly modify files, make HTTP requests, or perform any other action
    except by emitting a tool call that the runtime executes.
    """
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class ToolResult:
    """
    The result of executing a tool.

    This becomes a tool message in the conversation history, providing
    the agent with feedback about what happened when the tool was executed.
    """
    tool_call_id: str
    content: str
    success: bool = True
    error: str | None = None


@dataclass
class TruncationEvent:
    """
    Records when context truncation occurs.

    This makes information loss observable. In the baseline, we use naive
    truncation (drop oldest messages) rather than summarization. This event
    logs what was lost so we can understand the constraint's impact.
    """
    messages_dropped: int
    tokens_dropped: int
    oldest_dropped_content: str
    reason: str = "context_budget_exceeded"


@dataclass
class LoopState:
    """
    The current state of the agent loop.

    This captures where we are in the turn-based processing cycle.
    """
    step: int = 0
    max_steps: int = 10
    waiting_for_user: bool = False
    finished: bool = False
    final_response: str | None = None
    error: str | None = None
