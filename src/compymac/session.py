"""
Session - The fundamental unit of state.

A session owns all conversation state. When the session ends, ALL state
is discarded. This is a fundamental constraint of LLM-based agents:
there is no persistence between sessions unless explicitly implemented
as an improvement.

This baseline implementation has NO persistence. Each session starts
completely fresh with no memory of previous sessions.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from compymac.types import Message, Role, ToolCall, ToolResult, TruncationEvent


@dataclass
class Session:
    """
    A single agent session.

    The session is the fundamental unit of state. It owns:
    - The conversation history (messages)
    - Any pending tool calls
    - Truncation events (for observability)

    When the session ends (via close()), all state is discarded.
    There is no persistence - this is the baseline constraint.
    """

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=datetime.utcnow)
    system_prompt: str = ""
    messages: list[Message] = field(default_factory=list)
    pending_tool_calls: list[ToolCall] = field(default_factory=list)
    truncation_events: list[TruncationEvent] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    _closed: bool = field(default=False, repr=False)

    def __post_init__(self) -> None:
        """Initialize the session with a system message if provided."""
        if self.system_prompt and not self.messages:
            self.messages.append(Message(
                role=Role.SYSTEM,
                content=self.system_prompt,
            ))

    def add_user_message(self, content: str) -> Message:
        """Add a user message to the conversation."""
        self._check_not_closed()
        message = Message(role=Role.USER, content=content)
        self.messages.append(message)
        return message

    def add_assistant_message(
        self,
        content: str,
        tool_calls: list[dict[str, Any]] | None = None,
    ) -> Message:
        """Add an assistant message to the conversation."""
        self._check_not_closed()
        message = Message(
            role=Role.ASSISTANT,
            content=content,
            tool_calls=tool_calls,
        )
        self.messages.append(message)
        return message

    def add_tool_result(self, result: ToolResult) -> Message:
        """Add a tool result message to the conversation."""
        self._check_not_closed()
        message = Message(
            role=Role.TOOL,
            content=result.content,
            tool_call_id=result.tool_call_id,
        )
        self.messages.append(message)
        return message

    def record_truncation(self, event: TruncationEvent) -> None:
        """Record that truncation occurred (for observability)."""
        self.truncation_events.append(event)

    def get_messages(self) -> list[Message]:
        """Get all messages in the conversation."""
        return list(self.messages)

    def get_message_dicts(self) -> list[dict[str, Any]]:
        """Get all messages as dicts (for API calls)."""
        return [m.to_dict() for m in self.messages]

    def close(self) -> None:
        """
        Close the session and discard all state.

        This is the fundamental constraint: when a session ends,
        everything is lost. There is no persistence in the baseline.
        """
        self._closed = True
        self.messages.clear()
        self.pending_tool_calls.clear()
        self.metadata.clear()

    def _check_not_closed(self) -> None:
        """Raise an error if the session is closed."""
        if self._closed:
            raise RuntimeError(
                f"Session {self.id} is closed. "
                "All state has been discarded (this is the baseline constraint)."
            )

    @property
    def is_closed(self) -> bool:
        """Check if the session is closed."""
        return self._closed

    @property
    def message_count(self) -> int:
        """Number of messages in the conversation."""
        return len(self.messages)

    @property
    def total_truncations(self) -> int:
        """Total number of truncation events that occurred."""
        return len(self.truncation_events)

    @property
    def tokens_lost_to_truncation(self) -> int:
        """Total tokens lost to truncation (for observability)."""
        return sum(e.tokens_dropped for e in self.truncation_events)
