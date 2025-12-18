"""
Harness Specification - Measured constraints from empirical probing.

This module encodes the invariants discovered through systematic testing
of the Devin harness. These constraints define the "rules of the game"
that any agent operating within the harness must respect.

All values here are empirically measured, not assumed.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any


class TruncationBehavior(Enum):
    """How different operators handle truncation."""
    CHARACTER_BASED = "character"  # Shell output: 20k chars
    LINE_BASED = "line"  # File read: ~136 lines


@dataclass(frozen=True)
class HarnessConstraints:
    """
    Measured constraints of the Devin harness.

    These values come from experiments documented in harness.md.
    """

    # Shell output truncation (Experiment 7.1, 8.3)
    shell_output_display_limit: int = 20_000  # characters
    shell_output_preserves_full: bool = True  # saved to /home/ubuntu/full_outputs/

    # File read truncation (Experiment 8.1)
    file_read_default_lines: int = 136  # approximate, may vary
    file_read_supports_pagination: bool = True  # offset/limit params

    # Parallel execution (Experiments 7.5, 7.12)
    min_parallel_calls: int = 10  # at least 10 confirmed
    parallel_dispatch: bool = True  # true concurrent, not serial

    # Schema validation (Experiment 7.2)
    pre_execution_validation: bool = True  # validates before dispatch
    schema_errors_plain_text: bool = True  # no XML envelope for schema errors

    # Error handling (Experiment 7.7)
    per_executor_error_envelopes: bool = True  # each executor has own format
    file_error_envelope: str = "commands-errored"
    shell_error_envelope: str = "shell-output"  # with return code

    # Tool result isolation (Experiment 7.3)
    xml_envelope_isolation: bool = True  # prevents prompt injection
    file_read_envelope: str = "full-file-view"
    shell_output_envelope: str = "shell-output"

    # Recovery semantics (Experiment 8.2)
    auto_retry_on_failure: bool = False  # no automatic retry
    manual_recovery_required: bool = True
    timeout_exit_code: int = 124

    # Redaction (Experiment 7.4)
    auto_redact_secret_patterns: bool = False  # no pattern-based redaction

    # Browser DOM (Experiment 7.8)
    deterministic_html_stripping: bool = True
    stable_devinid_assignment: bool = True

    # ask_smart_friend context (Experiment 7.9)
    smart_friend_has_history: bool = True  # has conversation context

    # Caching (Experiment 7.11)
    consistent_query_results: bool = True  # identical queries = identical results


# Singleton instance with measured values
HARNESS_CONSTRAINTS = HarnessConstraints()


@dataclass
class ToolEnvelope:
    """
    Envelope format for tool results.

    The harness wraps tool outputs in XML-style envelopes that
    isolate content from being interpreted as instructions.
    """
    tag: str
    attributes: dict[str, Any]
    content: str

    def render(self) -> str:
        """Render the envelope as XML-style markup."""
        attrs = " ".join(f'{k}="{v}"' for k, v in self.attributes.items())
        if attrs:
            return f"<{self.tag} {attrs}>\n{self.content}\n</{self.tag}>"
        return f"<{self.tag}>\n{self.content}\n</{self.tag}>"


def create_file_read_envelope(path: str, content: str, total_lines: int) -> ToolEnvelope:
    """Create envelope for file read results."""
    # Add line numbers like the real harness does
    lines = content.split("\n")
    numbered_lines = [f"{i+1:>6}→{line}" for i, line in enumerate(lines)]
    numbered_content = "\n".join(numbered_lines)

    return ToolEnvelope(
        tag="full-file-view",
        attributes={"path": path, "total_lines": total_lines},
        content=numbered_content,
    )


def create_shell_output_envelope(
    command: str,
    output: str,
    return_code: int,
    exec_dir: str,
    shell_id: str,
    elapsed_seconds: float,
) -> ToolEnvelope:
    """Create envelope for shell output results."""
    header = (
        f'The command `{command}` (started {elapsed_seconds:.2f}s ago) '
        f'has finished running in the directory {exec_dir} '
        f'in shell {shell_id} (return code = {return_code})\n\n'
        f'The latest output is:\n\n```\n{output}\n```'
    )

    return ToolEnvelope(
        tag="shell-output",
        attributes={},
        content=header,
    )


def create_error_envelope(error_message: str) -> ToolEnvelope:
    """Create envelope for file operation errors."""
    return ToolEnvelope(
        tag="commands-errored",
        attributes={},
        content=f"ERROR: {error_message}",
    )


def truncate_output(content: str, limit: int = HARNESS_CONSTRAINTS.shell_output_display_limit) -> tuple[str, int]:
    """
    Truncate content to display limit.

    Returns (truncated_content, chars_truncated).
    If no truncation needed, chars_truncated is 0.
    """
    if len(content) <= limit:
        return content, 0

    truncated = content[:limit]
    chars_truncated = len(content) - limit
    return truncated, chars_truncated


def truncate_lines(lines: list[str], limit: int = HARNESS_CONSTRAINTS.file_read_default_lines) -> tuple[list[str], bool]:
    """
    Truncate lines to display limit.

    Returns (truncated_lines, was_truncated).
    """
    if len(lines) <= limit:
        return lines, False

    return lines[:limit], True
