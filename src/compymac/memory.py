"""
Memory Manager - Smart context management beyond naive truncation.

This module implements a two-tier memory system:
1. Working context: Recent messages always kept for conversational coherence
2. Rolling compressed memory: Older messages summarized into a single memory message

The memory message contains:
- Summary: What the user wants, what's been tried, current state/progress
- Facts: Structured data like file paths, commands, errors, decisions

This preserves task state and prevents catastrophic forgetting while
staying within context limits.
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Any

from compymac.config import ContextConfig
from compymac.types import Message

logger = logging.getLogger(__name__)


@dataclass
class MemoryFacts:
    """Structured facts extracted from conversation history."""
    files_created: list[str] = field(default_factory=list)
    files_modified: list[str] = field(default_factory=list)
    files_read: list[str] = field(default_factory=list)
    commands_executed: list[str] = field(default_factory=list)
    errors_encountered: list[str] = field(default_factory=list)
    user_requirements: list[str] = field(default_factory=list)
    decisions_made: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, list[str]]:
        return {
            "files_created": self.files_created[-5:],  # Keep last 5
            "files_modified": self.files_modified[-5:],
            "files_read": self.files_read[-10:],
            "commands_executed": self.commands_executed[-5:],
            "errors_encountered": self.errors_encountered[-3:],
            "user_requirements": self.user_requirements,
            "decisions_made": self.decisions_made[-5:],
        }

    def to_string(self) -> str:
        """Convert facts to a compact string representation."""
        parts = []
        if self.files_created:
            parts.append(f"Files created: {', '.join(self.files_created[-5:])}")
        if self.files_modified:
            parts.append(f"Files modified: {', '.join(self.files_modified[-5:])}")
        if self.files_read:
            parts.append(f"Files read: {', '.join(self.files_read[-5:])}")
        if self.commands_executed:
            parts.append(f"Commands run: {', '.join(self.commands_executed[-3:])}")
        if self.errors_encountered:
            parts.append(f"Errors: {', '.join(self.errors_encountered[-2:])}")
        if self.user_requirements:
            parts.append(f"Requirements: {'; '.join(self.user_requirements)}")
        return "\n".join(parts) if parts else "No facts recorded yet."


@dataclass
class MemoryState:
    """Current state of the memory system."""
    summary: str = ""
    facts: MemoryFacts = field(default_factory=MemoryFacts)
    compression_count: int = 0
    total_messages_compressed: int = 0

    def to_memory_message(self) -> str:
        """Generate the memory message content."""
        parts = ["[MEMORY SUMMARY - Context from earlier in this conversation]"]

        if self.summary:
            parts.append(f"\nProgress: {self.summary}")

        facts_str = self.facts.to_string()
        if facts_str != "No facts recorded yet.":
            parts.append(f"\nKey Facts:\n{facts_str}")

        if self.compression_count > 0:
            parts.append(f"\n(Compressed {self.total_messages_compressed} earlier messages)")

        return "\n".join(parts)


class MemoryManager:
    """
    Manages context with smart compression instead of naive truncation.

    When context pressure is detected:
    1. Extract facts from older messages (file paths, commands, errors)
    2. Generate a summary of what's been done
    3. Replace older messages with a single memory message
    4. Keep recent messages for conversational coherence
    """

    def __init__(
        self,
        config: ContextConfig | None = None,
        llm_client: Any = None,
        keep_recent_turns: int = 4,
        compression_threshold: float = 0.80,
        max_memory_tokens: int = 2000,
    ):
        """
        Initialize the memory manager.

        Args:
            config: Context configuration for token estimation
            llm_client: Optional LLM client for generating summaries
            keep_recent_turns: Number of recent user/assistant turns to always keep
            compression_threshold: Trigger compression when utilization exceeds this
            max_memory_tokens: Maximum tokens for the memory message
        """
        self.config = config or ContextConfig.from_env()
        self.llm_client = llm_client
        self.keep_recent_turns = keep_recent_turns
        self.compression_threshold = compression_threshold
        self.max_memory_tokens = max_memory_tokens

        self.state = MemoryState()

    def estimate_tokens(self, text: str) -> int:
        """Estimate token count from text."""
        return int(len(text) / self.config.chars_per_token)

    def estimate_message_tokens(self, message: Message) -> int:
        """Estimate tokens for a single message."""
        tokens = self.estimate_tokens(message.content)
        tokens += 4  # Role overhead
        if hasattr(message, 'name') and message.name:
            tokens += self.estimate_tokens(message.name)
        if hasattr(message, 'tool_calls') and message.tool_calls:
            tokens += self.estimate_tokens(str(message.tool_calls))
        return tokens

    def calculate_utilization(self, messages: list[Message]) -> float:
        """Calculate current context utilization."""
        total_tokens = sum(self.estimate_message_tokens(m) for m in messages)
        return total_tokens / self.config.available_budget

    def should_compress(self, messages: list[Message]) -> bool:
        """Check if compression should be triggered."""
        return self.calculate_utilization(messages) > self.compression_threshold

    def extract_facts_from_message(self, message: Message) -> None:
        """Extract structured facts from a message using heuristics."""
        content = message.content
        role = message.role if isinstance(message.role, str) else message.role.value

        # Extract file paths (common patterns)
        file_patterns = [
            r'(?:file|path|wrote to|created|modified|read)\s*[:\s]+([/\w\.\-_]+\.\w+)',
            r'`([/\w\.\-_]+\.\w+)`',
            r'"([/\w\.\-_]+\.\w+)"',
        ]
        for pattern in file_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches:
                if match.startswith('/') and len(match) > 3:
                    if 'creat' in content.lower() or 'wrote' in content.lower():
                        if match not in self.state.facts.files_created:
                            self.state.facts.files_created.append(match)
                    elif 'modif' in content.lower():
                        if match not in self.state.facts.files_modified:
                            self.state.facts.files_modified.append(match)
                    else:
                        if match not in self.state.facts.files_read:
                            self.state.facts.files_read.append(match)

        # Extract commands from shell output envelopes
        # Format: <shell-output command="..." ...> or command="..." in content
        command_match = re.search(r'<shell-output[^>]*command="([^"]+)"', content, re.DOTALL)
        if command_match:
            cmd = command_match.group(1)[:100]  # Truncate long commands
            if cmd not in self.state.facts.commands_executed:
                self.state.facts.commands_executed.append(cmd)

        # Extract errors
        error_patterns = [
            r'(?:error|failed|exception)[:\s]+(.{20,100})',
            r'Error:\s*(.{20,100})',
        ]
        for pattern in error_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches:
                error_text = match.strip()[:100]
                if error_text and error_text not in self.state.facts.errors_encountered:
                    self.state.facts.errors_encountered.append(error_text)

        # Extract user requirements from user messages
        if role == "user":
            # First user message often contains the main task
            if len(self.state.facts.user_requirements) == 0:
                # Take first 200 chars as requirement summary
                req = content[:200].strip()
                if req:
                    self.state.facts.user_requirements.append(req)

    def generate_summary_heuristic(self, messages: list[Message]) -> str:
        """Generate a summary using heuristics (no LLM call)."""
        # Count message types
        user_msgs = sum(1 for m in messages if (m.role if isinstance(m.role, str) else m.role.value) == "user")
        assistant_msgs = sum(1 for m in messages if (m.role if isinstance(m.role, str) else m.role.value) == "assistant")
        tool_msgs = sum(1 for m in messages if (m.role if isinstance(m.role, str) else m.role.value) == "tool")

        parts = []

        # Summarize activity
        if tool_msgs > 0:
            parts.append(f"Executed {tool_msgs} tool operations")

        # Look for completion indicators in recent assistant messages
        for msg in reversed(messages):
            role = msg.role if isinstance(msg.role, str) else msg.role.value
            if role == "assistant" and msg.content:
                content_lower = msg.content.lower()
                if any(word in content_lower for word in ["completed", "done", "finished", "success"]):
                    parts.append("Previous steps completed successfully")
                    break
                elif any(word in content_lower for word in ["error", "failed", "issue"]):
                    parts.append("Encountered some issues in previous steps")
                    break

        if not parts:
            parts.append(f"Processed {user_msgs} user requests with {assistant_msgs} responses")

        return ". ".join(parts) + "."

    async def generate_summary_llm(self, messages: list[Message]) -> str:
        """Generate a summary using the LLM (if available)."""
        if not self.llm_client:
            return self.generate_summary_heuristic(messages)

        # Build a prompt for summarization
        conversation_text = "\n".join([
            f"{m.role if isinstance(m.role, str) else m.role.value}: {m.content[:500]}"
            for m in messages[:20]  # Limit to avoid huge prompts
        ])

        summary_prompt = f"""Summarize this conversation in 2-3 sentences. Focus on:
- What the user wanted to accomplish
- What actions were taken
- Current state/progress

Conversation:
{conversation_text}

Summary:"""

        try:
            response = self.llm_client.chat(
                messages=[{"role": "user", "content": summary_prompt}],
                tools=None,
            )
            return response.content[:500]  # Cap summary length
        except Exception as e:
            logger.warning(f"LLM summarization failed: {e}, using heuristic")
            return self.generate_summary_heuristic(messages)

    def compress_messages(
        self,
        messages: list[Message],
        use_llm: bool = False,
    ) -> list[Message]:
        """
        Compress older messages into a memory message.

        Args:
            messages: Full message list
            use_llm: Whether to use LLM for summarization (default: heuristic)

        Returns:
            Compressed message list with memory message
        """
        if len(messages) <= self.keep_recent_turns * 2 + 1:
            # Not enough messages to compress
            return messages

        # Separate system message, memory message (if exists), and conversation
        system_message: Message | None = None
        conversation: list[Message] = []

        for msg in messages:
            role = msg.role if isinstance(msg.role, str) else msg.role.value
            if role == "system":
                system_message = msg
            elif msg.content.startswith("[MEMORY SUMMARY"):
                # Skip existing memory messages - they'll be replaced
                pass
            else:
                conversation.append(msg)

        # Keep recent turns
        keep_count = self.keep_recent_turns * 2  # user + assistant pairs
        if len(conversation) <= keep_count:
            return messages

        messages_to_compress = conversation[:-keep_count]
        recent_messages = conversation[-keep_count:]

        # Extract facts from messages being compressed
        for msg in messages_to_compress:
            self.extract_facts_from_message(msg)

        # Generate summary
        if use_llm and self.llm_client:
            # Would need async handling for LLM call
            summary = self.generate_summary_heuristic(messages_to_compress)
        else:
            summary = self.generate_summary_heuristic(messages_to_compress)

        # Update state
        self.state.summary = summary
        self.state.compression_count += 1
        self.state.total_messages_compressed += len(messages_to_compress)

        # Create memory message
        memory_content = self.state.to_memory_message()
        memory_message = Message(
            role="assistant",
            content=memory_content,
        )

        # Build compressed message list
        result: list[Message] = []
        if system_message:
            result.append(system_message)
        result.append(memory_message)
        result.extend(recent_messages)

        logger.info(
            f"Compressed {len(messages_to_compress)} messages into memory. "
            f"Context reduced from {len(messages)} to {len(result)} messages."
        )

        return result

    def process_messages(
        self,
        messages: list[Message],
        force_compress: bool = False,
    ) -> list[Message]:
        """
        Process messages, compressing if needed.

        Args:
            messages: Current message list
            force_compress: Force compression even if under threshold

        Returns:
            Processed message list (possibly compressed)
        """
        # Always extract facts from recent messages
        for msg in messages[-4:]:
            self.extract_facts_from_message(msg)

        # Check if compression needed
        if force_compress or self.should_compress(messages):
            return self.compress_messages(messages)

        return messages

    def get_memory_state(self) -> MemoryState:
        """Get current memory state."""
        return self.state

    def reset(self) -> None:
        """Reset memory state."""
        self.state = MemoryState()
