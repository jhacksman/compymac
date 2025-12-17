"""
Tests for Session - the fundamental unit of state.

These tests verify the core constraint: when a session ends,
all state is discarded.
"""

import pytest

from compymac.session import Session
from compymac.types import Role, ToolResult


class TestSessionBasics:
    """Test basic session operations."""

    def test_session_creates_with_unique_id(self) -> None:
        """Each session should have a unique ID."""
        s1 = Session()
        s2 = Session()
        assert s1.id != s2.id

    def test_session_with_system_prompt(self) -> None:
        """System prompt should be added as first message."""
        session = Session(system_prompt="You are helpful.")
        messages = session.get_messages()
        assert len(messages) == 1
        assert messages[0].role == Role.SYSTEM
        assert messages[0].content == "You are helpful."

    def test_add_user_message(self) -> None:
        """User messages should be added to history."""
        session = Session()
        session.add_user_message("Hello")
        messages = session.get_messages()
        assert len(messages) == 1
        assert messages[0].role == Role.USER
        assert messages[0].content == "Hello"

    def test_add_assistant_message(self) -> None:
        """Assistant messages should be added to history."""
        session = Session()
        session.add_assistant_message("Hi there!")
        messages = session.get_messages()
        assert len(messages) == 1
        assert messages[0].role == Role.ASSISTANT

    def test_add_tool_result(self) -> None:
        """Tool results should be added as tool messages."""
        session = Session()
        result = ToolResult(
            tool_call_id="call_123",
            content="File contents here",
            success=True,
        )
        session.add_tool_result(result)
        messages = session.get_messages()
        assert len(messages) == 1
        assert messages[0].role == Role.TOOL
        assert messages[0].tool_call_id == "call_123"


class TestSessionClosure:
    """Test the fundamental constraint: session closure discards all state."""

    def test_close_discards_messages(self) -> None:
        """Closing a session should discard all messages."""
        session = Session(system_prompt="System")
        session.add_user_message("User message")
        session.add_assistant_message("Assistant message")

        assert session.message_count == 3

        session.close()

        assert session.message_count == 0
        assert session.is_closed

    def test_close_discards_metadata(self) -> None:
        """Closing a session should discard metadata."""
        session = Session()
        session.metadata["key"] = "value"

        session.close()

        assert "key" not in session.metadata

    def test_cannot_add_messages_after_close(self) -> None:
        """Adding messages to a closed session should raise an error."""
        session = Session()
        session.close()

        with pytest.raises(RuntimeError, match="closed"):
            session.add_user_message("Hello")

    def test_cannot_add_assistant_after_close(self) -> None:
        """Adding assistant messages to a closed session should raise."""
        session = Session()
        session.close()

        with pytest.raises(RuntimeError, match="closed"):
            session.add_assistant_message("Hi")


class TestSessionTruncationTracking:
    """Test that truncation events are tracked for observability."""

    def test_truncation_events_recorded(self) -> None:
        """Truncation events should be recorded."""
        from compymac.types import TruncationEvent

        session = Session()
        event = TruncationEvent(
            messages_dropped=5,
            tokens_dropped=1000,
            oldest_dropped_content="Old message...",
        )
        session.record_truncation(event)

        assert session.total_truncations == 1
        assert session.tokens_lost_to_truncation == 1000

    def test_multiple_truncations_accumulated(self) -> None:
        """Multiple truncation events should accumulate."""
        from compymac.types import TruncationEvent

        session = Session()
        session.record_truncation(TruncationEvent(
            messages_dropped=3,
            tokens_dropped=500,
            oldest_dropped_content="First",
        ))
        session.record_truncation(TruncationEvent(
            messages_dropped=2,
            tokens_dropped=300,
            oldest_dropped_content="Second",
        ))

        assert session.total_truncations == 2
        assert session.tokens_lost_to_truncation == 800
