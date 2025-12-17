"""
Tests for ContextManager - fixed budget with naive truncation.

These tests verify the core constraint: when context exceeds the
budget, oldest messages are dropped (not summarized).
"""


from compymac.config import ContextConfig
from compymac.context import ContextManager
from compymac.session import Session


class TestTokenEstimation:
    """Test token estimation (approximate, but enforced)."""

    def test_estimate_tokens_basic(self) -> None:
        """Token estimation should work for basic text."""
        config = ContextConfig(chars_per_token=4.0)
        cm = ContextManager(config)

        assert cm.estimate_tokens("hello") == 1
        assert cm.estimate_tokens("hello world") == 2
        assert cm.estimate_tokens("a" * 100) == 25

    def test_estimate_respects_config(self) -> None:
        """Token estimation should respect chars_per_token config."""
        config = ContextConfig(chars_per_token=2.0)
        cm = ContextManager(config)

        assert cm.estimate_tokens("hello") == 2


class TestBudgetCalculation:
    """Test budget calculation."""

    def test_empty_session_full_budget(self) -> None:
        """Empty session should have full budget available."""
        config = ContextConfig(token_budget=1000, reserved_for_response=100)
        cm = ContextManager(config)
        session = Session()

        budget = cm.calculate_budget(session.get_messages())

        assert budget.total_budget == 900
        assert budget.used == 0
        assert budget.available == 900

    def test_messages_consume_budget(self) -> None:
        """Messages should consume budget."""
        config = ContextConfig(
            token_budget=1000,
            reserved_for_response=100,
            chars_per_token=1.0,
        )
        cm = ContextManager(config)
        session = Session()
        session.add_user_message("a" * 100)

        budget = cm.calculate_budget(session.get_messages())

        assert budget.used > 100


class TestNaiveTruncation:
    """Test the core constraint: naive truncation drops oldest messages."""

    def test_truncation_drops_oldest_first(self) -> None:
        """When budget exceeded, oldest messages should be dropped first."""
        config = ContextConfig(
            token_budget=80,
            reserved_for_response=20,
            chars_per_token=1.0,
        )
        cm = ContextManager(config)
        session = Session(system_prompt="System")

        session.add_user_message("First user message - oldest")
        session.add_assistant_message("First assistant")
        session.add_user_message("Second user message")
        session.add_assistant_message("Second assistant")
        session.add_user_message("Third user message - newest")

        messages, budget = cm.build_context(session)

        assert session.total_truncations >= 1

        contents = [m["content"] for m in messages]
        assert "System" in contents
        assert "newest" in " ".join(contents)

    def test_system_message_preserved(self) -> None:
        """System message should never be truncated."""
        config = ContextConfig(
            token_budget=100,
            reserved_for_response=20,
            chars_per_token=1.0,
        )
        cm = ContextManager(config)
        session = Session(system_prompt="Important system prompt")

        for i in range(10):
            session.add_user_message(f"Message {i} " * 10)

        messages, _ = cm.build_context(session)

        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == "Important system prompt"

    def test_truncation_event_recorded(self) -> None:
        """Truncation should record an event for observability."""
        config = ContextConfig(
            token_budget=100,
            reserved_for_response=20,
            chars_per_token=1.0,
        )
        cm = ContextManager(config)
        session = Session()

        for _i in range(10):
            session.add_user_message("x" * 50)

        assert session.total_truncations == 0

        cm.build_context(session)

        assert session.total_truncations > 0
        assert session.tokens_lost_to_truncation > 0

    def test_no_truncation_when_within_budget(self) -> None:
        """No truncation should occur when within budget."""
        config = ContextConfig(
            token_budget=10000,
            reserved_for_response=1000,
            chars_per_token=4.0,
        )
        cm = ContextManager(config)
        session = Session()
        session.add_user_message("Hello")
        session.add_assistant_message("Hi there!")

        cm.build_context(session)

        assert session.total_truncations == 0


class TestContextBuilding:
    """Test context building for API calls."""

    def test_build_context_returns_dicts(self) -> None:
        """build_context should return messages as dicts."""
        cm = ContextManager()
        session = Session()
        session.add_user_message("Hello")

        messages, _ = cm.build_context(session)

        assert isinstance(messages, list)
        assert isinstance(messages[0], dict)
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "Hello"

    def test_build_context_includes_budget_info(self) -> None:
        """build_context should return budget information."""
        cm = ContextManager()
        session = Session()
        session.add_user_message("Hello")

        _, budget = cm.build_context(session)

        assert budget.total_budget > 0
        assert budget.used > 0
        assert budget.available >= 0
