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
    # Structured context schema fields (from game plan)
    contract_goal: str = ""  # What the user wants accomplished
    current_plan: list[str] = field(default_factory=list)  # Current plan steps
    repo_facts: dict[str, str] = field(default_factory=dict)  # Known repo info (build cmd, test cmd, etc)
    open_questions: list[str] = field(default_factory=list)  # Unresolved questions

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "files_created": self.files_created[-5:],  # Keep last 5
            "files_modified": self.files_modified[-5:],
            "files_read": self.files_read[-10:],
            "commands_executed": self.commands_executed[-5:],
            "errors_encountered": self.errors_encountered[-3:],
            "user_requirements": self.user_requirements,
            "decisions_made": self.decisions_made[-5:],
        }
        # Add structured context schema fields if populated
        if self.contract_goal:
            result["contract_goal"] = self.contract_goal
        if self.current_plan:
            result["current_plan"] = self.current_plan
        if self.repo_facts:
            result["repo_facts"] = self.repo_facts
        if self.open_questions:
            result["open_questions"] = self.open_questions
        return result

    def to_string(self) -> str:
        """Convert facts to a compact string representation."""
        parts = []
        # Structured context schema fields first (highest priority)
        if self.contract_goal:
            parts.append(f"Goal: {self.contract_goal}")
        if self.current_plan:
            parts.append(f"Plan: {' -> '.join(self.current_plan[:5])}")
        if self.open_questions:
            parts.append(f"Open questions: {'; '.join(self.open_questions[-3:])}")
        if self.repo_facts:
            repo_info = [f"{k}: {v}" for k, v in list(self.repo_facts.items())[:5]]
            parts.append(f"Repo: {', '.join(repo_info)}")
        # Original facts
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

    # Structured context schema setters
    def set_contract_goal(self, goal: str) -> None:
        """Set the contract/goal for the current task."""
        self.state.facts.contract_goal = goal
        logger.debug(f"Set contract goal: {goal[:100]}...")

    def set_current_plan(self, plan_steps: list[str]) -> None:
        """Set the current plan steps."""
        self.state.facts.current_plan = plan_steps
        logger.debug(f"Set plan with {len(plan_steps)} steps")

    def add_plan_step(self, step: str) -> None:
        """Add a step to the current plan."""
        self.state.facts.current_plan.append(step)

    def complete_plan_step(self, step_index: int) -> None:
        """Mark a plan step as complete by removing it."""
        if 0 <= step_index < len(self.state.facts.current_plan):
            completed = self.state.facts.current_plan.pop(step_index)
            logger.debug(f"Completed plan step: {completed}")

    def set_repo_facts(self, facts: dict[str, str]) -> None:
        """Set known repo facts (build cmd, test cmd, lint cmd, etc)."""
        self.state.facts.repo_facts = facts
        logger.debug(f"Set repo facts: {list(facts.keys())}")

    def add_repo_fact(self, key: str, value: str) -> None:
        """Add a single repo fact."""
        self.state.facts.repo_facts[key] = value

    def add_open_question(self, question: str) -> None:
        """Add an open question that needs resolution."""
        self.state.facts.open_questions.append(question)
        logger.debug(f"Added open question: {question[:50]}...")

    def resolve_question(self, question_index: int) -> None:
        """Resolve an open question by removing it."""
        if 0 <= question_index < len(self.state.facts.open_questions):
            resolved = self.state.facts.open_questions.pop(question_index)
            logger.debug(f"Resolved question: {resolved[:50]}...")


class ToolOutputSummarizer:
    """
    Summarizes large tool outputs to reduce context bloat.

    Tool outputs are often the biggest source of context pressure:
    - File reads can be thousands of lines
    - Grep results can return hundreds of matches
    - Shell output can be verbose

    This summarizer applies heuristics to compress outputs while
    preserving the most important information.
    """

    # Maximum characters for different output types
    MAX_FILE_CONTENT = 8000  # ~2000 tokens
    MAX_GREP_RESULTS = 4000  # ~1000 tokens
    MAX_SHELL_OUTPUT = 4000  # ~1000 tokens
    MAX_GENERIC_OUTPUT = 6000  # ~1500 tokens

    @classmethod
    def summarize(cls, tool_name: str, output: str) -> str:
        """
        Summarize tool output based on tool type.

        Args:
            tool_name: Name of the tool that produced the output
            output: Raw tool output

        Returns:
            Summarized output (may be unchanged if already small)
        """
        if not output:
            return output

        # Route to appropriate summarizer based on tool
        if tool_name in ("Read", "fs_read_file"):
            return cls._summarize_file_content(output)
        elif tool_name == "grep":
            return cls._summarize_grep_results(output)
        elif tool_name in ("bash", "bash_output"):
            return cls._summarize_shell_output(output)
        elif tool_name == "glob":
            return cls._summarize_glob_results(output)
        elif tool_name in ("web_search", "web_get_contents"):
            return cls._summarize_web_content(output)
        else:
            return cls._summarize_generic(output)

    @classmethod
    def _summarize_file_content(cls, content: str) -> str:
        """Summarize file content, keeping structure visible."""
        if len(content) <= cls.MAX_FILE_CONTENT:
            return content

        lines = content.split('\n')
        total_lines = len(lines)

        # Keep first 50 lines and last 20 lines
        head_lines = 50
        tail_lines = 20

        if total_lines <= head_lines + tail_lines:
            return content

        head = '\n'.join(lines[:head_lines])
        tail = '\n'.join(lines[-tail_lines:])
        omitted = total_lines - head_lines - tail_lines

        return f"{head}\n\n[... {omitted} lines omitted ...]\n\n{tail}"

    @classmethod
    def _summarize_grep_results(cls, content: str) -> str:
        """Summarize grep results, keeping unique files and sample matches."""
        if len(content) <= cls.MAX_GREP_RESULTS:
            return content

        lines = content.split('\n')

        # For files_with_matches mode, just truncate the list
        if not any(':' in line and len(line.split(':')) >= 2 for line in lines[:10]):
            # Looks like just file paths
            if len(lines) > 50:
                return '\n'.join(lines[:50]) + f"\n\n[... {len(lines) - 50} more files ...]"
            return content

        # For content mode, group by file and show samples
        files_seen: dict[str, list[str]] = {}
        for line in lines:
            if ':' in line:
                parts = line.split(':', 2)
                if len(parts) >= 2:
                    file_path = parts[0]
                    if file_path not in files_seen:
                        files_seen[file_path] = []
                    if len(files_seen[file_path]) < 3:  # Keep max 3 matches per file
                        files_seen[file_path].append(line)

        # Build summary
        result_lines = []
        for file_path, matches in list(files_seen.items())[:20]:  # Max 20 files
            result_lines.extend(matches)
            if len(files_seen[file_path]) > 3:
                result_lines.append(f"  [... {len(files_seen[file_path]) - 3} more matches in {file_path} ...]")

        if len(files_seen) > 20:
            result_lines.append(f"\n[... {len(files_seen) - 20} more files with matches ...]")

        return '\n'.join(result_lines)

    @classmethod
    def _summarize_shell_output(cls, content: str) -> str:
        """Summarize shell output, keeping errors and key info."""
        if len(content) <= cls.MAX_SHELL_OUTPUT:
            return content

        lines = content.split('\n')

        # Prioritize error lines
        error_lines = [line for line in lines if any(e in line.lower() for e in ['error', 'failed', 'exception', 'warning'])]

        # Keep first 30 and last 20 lines
        head_lines = 30
        tail_lines = 20

        head = '\n'.join(lines[:head_lines])
        tail = '\n'.join(lines[-tail_lines:])
        omitted = len(lines) - head_lines - tail_lines

        result = f"{head}\n\n[... {omitted} lines omitted ...]"

        # Add error summary if there were errors in omitted section
        omitted_errors = [line for line in lines[head_lines:-tail_lines] if line in error_lines]
        if omitted_errors:
            result += f"\n[Errors in omitted section: {len(omitted_errors)} error lines]"

        result += f"\n\n{tail}"
        return result

    @classmethod
    def _summarize_glob_results(cls, content: str) -> str:
        """Summarize glob results, grouping by directory."""
        if len(content) <= cls.MAX_GENERIC_OUTPUT:
            return content

        lines = content.split('\n')
        if len(lines) <= 100:
            return content

        # Group by directory
        dirs: dict[str, int] = {}
        for line in lines:
            if '/' in line:
                dir_path = '/'.join(line.split('/')[:-1])
                dirs[dir_path] = dirs.get(dir_path, 0) + 1

        # Show first 50 files and directory summary
        result = '\n'.join(lines[:50])
        result += f"\n\n[... {len(lines) - 50} more files ...]\n"
        result += "\nFiles by directory:\n"
        for dir_path, count in sorted(dirs.items(), key=lambda x: -x[1])[:10]:
            result += f"  {dir_path}: {count} files\n"

        return result

    @classmethod
    def _summarize_web_content(cls, content: str) -> str:
        """Summarize web content, keeping structure."""
        if len(content) <= cls.MAX_GENERIC_OUTPUT:
            return content

        # For web content, keep first portion with note about truncation
        truncated = content[:cls.MAX_GENERIC_OUTPUT]
        # Try to end at a sentence boundary
        last_period = truncated.rfind('.')
        if last_period > cls.MAX_GENERIC_OUTPUT * 0.8:
            truncated = truncated[:last_period + 1]

        return truncated + f"\n\n[... content truncated, {len(content) - len(truncated)} chars omitted ...]"

    @classmethod
    def _summarize_generic(cls, content: str) -> str:
        """Generic summarization for unknown tool types."""
        if len(content) <= cls.MAX_GENERIC_OUTPUT:
            return content

        # Simple head/tail truncation
        head_chars = int(cls.MAX_GENERIC_OUTPUT * 0.7)
        tail_chars = int(cls.MAX_GENERIC_OUTPUT * 0.25)

        head = content[:head_chars]
        tail = content[-tail_chars:]
        omitted = len(content) - head_chars - tail_chars

        return f"{head}\n\n[... {omitted} chars omitted ...]\n\n{tail}"
