"""
Harness Interface - Abstraction layer for tool execution environments.

This module defines the Harness protocol that both the simulator and
real local implementations must satisfy. This enables:
- Deterministic testing via HarnessSimulator
- Real execution via LocalHarness
- Trace replay via ReplayHarness
- Consistent event logging across all implementations
- Complete execution tracing via TraceStore integration
"""

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

from compymac.types import ToolCall, ToolResult

if TYPE_CHECKING:
    from compymac.trace_store import TraceContext


class EventType(Enum):
    """Types of events in the harness event log."""
    TOOL_CALL_RECEIVED = "tool_call_received"
    SCHEMA_VALIDATION = "schema_validation"
    TOOL_DISPATCH = "tool_dispatch"
    TOOL_EXECUTION_START = "tool_execution_start"
    TOOL_EXECUTION_END = "tool_execution_end"
    OUTPUT_TRUNCATION = "output_truncation"
    ENVELOPE_WRAP = "envelope_wrap"
    TOOL_RESULT_RETURNED = "tool_result_returned"
    ERROR = "error"
    AGENT_TURN_START = "agent_turn_start"
    AGENT_TURN_END = "agent_turn_end"
    LLM_REQUEST = "llm_request"
    LLM_RESPONSE = "llm_response"


@dataclass
class HarnessEvent:
    """A single event in the harness event log."""
    timestamp: datetime
    event_type: EventType
    tool_call_id: str
    data: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "event_type": self.event_type.value,
            "tool_call_id": self.tool_call_id,
            "data": self.data,
        }


@dataclass
class EventLog:
    """Append-only event log for harness operations."""
    events: list[HarnessEvent] = field(default_factory=list)

    def append(self, event: HarnessEvent) -> None:
        self.events.append(event)

    def log_event(
        self,
        event_type: EventType,
        tool_call_id: str = "",
        **data: Any,
    ) -> HarnessEvent:
        event = HarnessEvent(
            timestamp=datetime.now(UTC),
            event_type=event_type,
            tool_call_id=tool_call_id,
            data=data,
        )
        self.append(event)
        return event

    def get_events_for_call(self, tool_call_id: str) -> list[HarnessEvent]:
        return [e for e in self.events if e.tool_call_id == tool_call_id]

    def clear(self) -> None:
        self.events.clear()

    def save(self, path: Path) -> None:
        import json
        lines = [json.dumps(e.to_dict()) for e in self.events]
        path.write_text("\n".join(lines))

    @classmethod
    def load(cls, path: Path) -> "EventLog":
        import json
        log = cls()
        for line in path.read_text().strip().split("\n"):
            if line:
                data = json.loads(line)
                event = HarnessEvent(
                    timestamp=datetime.fromisoformat(data["timestamp"]),
                    event_type=EventType(data["event_type"]),
                    tool_call_id=data["tool_call_id"],
                    data=data["data"],
                )
                log.append(event)
        return log


@dataclass
class ToolSchema:
    """Schema for a tool's parameters."""
    name: str
    description: str
    required_params: list[str]
    optional_params: list[str]
    param_types: dict[str, str]


class Harness(ABC):
    """
    Abstract base class for harness implementations.

    All harness implementations (Simulator, Local, Replay) must implement
    this interface to ensure consistent behavior and event logging.

    Optionally supports TraceContext for complete execution capture.
    """

    @abstractmethod
    def execute(self, tool_call: ToolCall) -> ToolResult:
        """Execute a single tool call and return the result."""
        ...

    @abstractmethod
    def execute_parallel(self, tool_calls: list[ToolCall]) -> list[ToolResult]:
        """Execute multiple tool calls (potentially in parallel)."""
        ...

    @abstractmethod
    def validate_schema(self, tool_name: str, arguments: dict[str, Any]) -> tuple[bool, str | None]:
        """Validate arguments against tool schema. Returns (is_valid, error_message)."""
        ...

    @abstractmethod
    def get_event_log(self) -> EventLog:
        """Get the event log for inspection."""
        ...

    @abstractmethod
    def clear_event_log(self) -> None:
        """Clear the event log."""
        ...

    @abstractmethod
    def register_tool(
        self,
        name: str,
        schema: ToolSchema,
        handler: Callable[..., str],
    ) -> None:
        """Register a tool with the harness."""
        ...

    @abstractmethod
    def get_tool_schemas(self) -> list[dict[str, Any]]:
        """Get OpenAI-format schemas for all registered tools."""
        ...

    def set_trace_context(self, trace_context: "TraceContext | None") -> None:  # noqa: B027
        """
        Set the trace context for complete execution capture.

        When set, all tool executions will be recorded as spans in the trace.
        This is optional - harness works without tracing.
        """
        pass  # Default no-op, subclasses can override

    def get_trace_context(self) -> "TraceContext | None":
        """Get the current trace context, if any."""
        return None  # Default returns None


class HarnessConfig:
    """Configuration for harness behavior based on measured constraints."""

    # Shell output truncation (Experiment 7.1, 8.3)
    shell_output_display_limit: int = 20_000

    # File read truncation (Experiment 8.1)
    file_read_default_lines: int = 136

    # Recovery semantics (Experiment 8.2)
    auto_retry_on_failure: bool = False

    # Parallel execution (Experiments 7.5, 7.12)
    parallel_dispatch: bool = True
    min_parallel_calls: int = 10
