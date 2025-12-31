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

    # =========================================================================
    # Gap 1: Session Persistence - Serialization/Deserialization
    # =========================================================================

    def to_dict(self) -> dict[str, Any]:
        """
        Serialize the session to a dictionary for persistence.

        This enables Gap 1: Session Persistence + Resume by allowing
        sessions to be saved to disk and restored later.
        """
        return {
            "id": self.id,
            "created_at": self.created_at.isoformat(),
            "system_prompt": self.system_prompt,
            "messages": [m.to_dict() for m in self.messages],
            "pending_tool_calls": [
                {
                    "id": tc.id,
                    "name": tc.name,
                    "arguments": tc.arguments,
                }
                for tc in self.pending_tool_calls
            ],
            "truncation_events": [
                {
                    "timestamp": te.timestamp.isoformat() if hasattr(te.timestamp, 'isoformat') else str(te.timestamp),
                    "tokens_dropped": te.tokens_dropped,
                    "reason": te.reason,
                }
                for te in self.truncation_events
            ],
            "metadata": self.metadata,
            "_closed": self._closed,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Session":
        """
        Deserialize a session from a dictionary.

        This enables Gap 1: Session Persistence + Resume by allowing
        sessions to be restored from disk.
        """
        # Parse messages
        messages = []
        for m in data.get("messages", []):
            messages.append(Message(
                role=Role(m["role"]),
                content=m.get("content", ""),
                tool_calls=m.get("tool_calls"),
                tool_call_id=m.get("tool_call_id"),
            ))

        # Parse pending tool calls
        pending_tool_calls = []
        for tc in data.get("pending_tool_calls", []):
            pending_tool_calls.append(ToolCall(
                id=tc["id"],
                name=tc["name"],
                arguments=tc["arguments"],
            ))

        # Parse truncation events
        truncation_events = []
        for te in data.get("truncation_events", []):
            truncation_events.append(TruncationEvent(
                timestamp=datetime.fromisoformat(te["timestamp"]) if isinstance(te["timestamp"], str) else te["timestamp"],
                tokens_dropped=te["tokens_dropped"],
                reason=te["reason"],
            ))

        # Create session without triggering __post_init__ system message
        session = cls.__new__(cls)
        session.id = data["id"]
        session.created_at = datetime.fromisoformat(data["created_at"])
        session.system_prompt = data.get("system_prompt", "")
        session.messages = messages
        session.pending_tool_calls = pending_tool_calls
        session.truncation_events = truncation_events
        session.metadata = data.get("metadata", {})
        session._closed = data.get("_closed", False)

        return session
