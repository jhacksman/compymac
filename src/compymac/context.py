"""
Context Manager - Fixed-budget prompt builder.

This is where the fundamental context window constraint is enforced.
When the conversation exceeds the token budget, we use NAIVE TRUNCATION
(drop oldest messages) rather than summarization.

Summarization would be an improvement over the baseline - it would
preserve more information. But the baseline must honestly represent
the constraint: when context is full, information is LOST.
"""

import logging
from dataclasses import dataclass
from typing import Any

from compymac.config import ContextConfig
from compymac.session import Session
from compymac.types import Message, Role, TruncationEvent

logger = logging.getLogger(__name__)


@dataclass
class ContextBudget:
    """Tracks token budget usage."""
    total_budget: int
    used: int
    available: int

    @property
    def utilization(self) -> float:
        """Percentage of budget used."""
        return self.used / self.total_budget if self.total_budget > 0 else 0.0


class ContextManager:
    """
    Manages the context window with a fixed token budget.

    The key constraint: when context exceeds the budget, we truncate
    by dropping the oldest messages (after the system message).
    This is NAIVE truncation - information is lost, not summarized.

    This makes the information loss observable and explicit, which is
    important for understanding the baseline constraint.
    """

    def __init__(self, config: ContextConfig | None = None) -> None:
        """Initialize with configuration."""
        self.config = config or ContextConfig.from_env()

    def estimate_tokens(self, text: str) -> int:
        """
        Estimate token count from text.

        This is a rough approximation (chars / 4). A real implementation
        would use a proper tokenizer, but the important thing is that
        the budget is ENFORCED, not that the estimate is perfect.
        """
        return int(len(text) / self.config.chars_per_token)

    def estimate_message_tokens(self, message: Message) -> int:
        """Estimate tokens for a single message."""
        tokens = self.estimate_tokens(message.content)
        tokens += 4
        if message.name:
            tokens += self.estimate_tokens(message.name)
        if message.tool_calls:
            tokens += self.estimate_tokens(str(message.tool_calls))
        return tokens

    def calculate_budget(self, messages: list[Message]) -> ContextBudget:
        """Calculate current budget usage."""
        used = sum(self.estimate_message_tokens(m) for m in messages)
        return ContextBudget(
            total_budget=self.config.available_budget,
            used=used,
            available=max(0, self.config.available_budget - used),
        )

    def build_context(
        self,
        session: Session,
        tools: list[dict[str, Any]] | None = None,
    ) -> tuple[list[dict[str, Any]], ContextBudget]:
        """
        Build the context for an LLM call, enforcing the token budget.

        If the context exceeds the budget, the oldest messages (after
        the system message) are dropped. This is naive truncation -
        information is lost, and we record this in the session.

        Args:
            session: The current session with conversation history
            tools: Optional tool definitions (count against budget)

        Returns:
            Tuple of (messages for API, budget info)
        """
        messages = session.get_messages()

        tool_tokens = 0
        if tools:
            tool_tokens = self.estimate_tokens(str(tools))

        available_for_messages = self.config.available_budget - tool_tokens

        system_message: Message | None = None
        conversation_messages: list[Message] = []

        for msg in messages:
            if msg.role == Role.SYSTEM and system_message is None:
                system_message = msg
            else:
                conversation_messages.append(msg)

        system_tokens = 0
        if system_message:
            system_tokens = self.estimate_message_tokens(system_message)

        available_for_conversation = available_for_messages - system_tokens

        kept_messages: list[Message] = []
        kept_tokens = 0
        dropped_messages: list[Message] = []
        dropped_tokens = 0

        for msg in reversed(conversation_messages):
            msg_tokens = self.estimate_message_tokens(msg)
            if kept_tokens + msg_tokens <= available_for_conversation:
                kept_messages.insert(0, msg)
                kept_tokens += msg_tokens
            else:
                dropped_messages.insert(0, msg)
                dropped_tokens += msg_tokens

        if dropped_messages:
            oldest_content = dropped_messages[0].content[:200] + "..." if len(dropped_messages[0].content) > 200 else dropped_messages[0].content
            event = TruncationEvent(
                messages_dropped=len(dropped_messages),
                tokens_dropped=dropped_tokens,
                oldest_dropped_content=oldest_content,
                reason="context_budget_exceeded",
            )
            session.record_truncation(event)
            logger.warning(
                f"Context truncation: dropped {len(dropped_messages)} messages "
                f"(~{dropped_tokens} tokens). Information has been LOST."
            )

        final_messages: list[Message] = []
        if system_message:
            final_messages.append(system_message)
        final_messages.extend(kept_messages)

        total_used = system_tokens + kept_tokens + tool_tokens
        budget = ContextBudget(
            total_budget=self.config.available_budget,
            used=total_used,
            available=self.config.available_budget - total_used,
        )

        return [m.to_dict() for m in final_messages], budget

    def can_fit_message(self, session: Session, content: str) -> bool:
        """Check if a new message would fit in the current context."""
        budget = self.calculate_budget(session.get_messages())
        new_tokens = self.estimate_tokens(content) + 4
        return new_tokens <= budget.available
