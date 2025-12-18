"""
Harness Simulator - Reference implementation mirroring measured constraints.

This simulator provides a controlled environment that behaves like the
Devin harness, with event logging for debugging and replay. It encodes
the constraints discovered through empirical probing.

Key features:
- Append-only event log for reproducibility
- Truncation behavior matching measured limits
- XML envelope wrapping for tool results
- Parallel dispatch semantics
- Schema validation before execution
"""

import json
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any

from compymac.harness_spec import (
    HARNESS_CONSTRAINTS,
    HarnessConstraints,
    create_error_envelope,
    create_file_read_envelope,
    create_shell_output_envelope,
    truncate_lines,
    truncate_output,
)
from compymac.types import ToolCall, ToolResult

logger = logging.getLogger(__name__)


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

    def to_json(self) -> str:
        return json.dumps(self.to_dict())


@dataclass
class EventLog:
    """
    Append-only event log for harness operations.

    This log enables:
    - Debugging: See exactly what happened
    - Replay: Reproduce runs from the log
    - Conformance testing: Compare against real harness behavior
    """
    events: list[HarnessEvent] = field(default_factory=list)

    def append(self, event: HarnessEvent) -> None:
        """Append an event to the log."""
        self.events.append(event)
        logger.debug(f"Event: {event.event_type.value} - {event.tool_call_id}")

    def log_event(
        self,
        event_type: EventType,
        tool_call_id: str,
        **data: Any,
    ) -> HarnessEvent:
        """Create and append an event."""
        event = HarnessEvent(
            timestamp=datetime.now(UTC),
            event_type=event_type,
            tool_call_id=tool_call_id,
            data=data,
        )
        self.append(event)
        return event

    def get_events_for_call(self, tool_call_id: str) -> list[HarnessEvent]:
        """Get all events for a specific tool call."""
        return [e for e in self.events if e.tool_call_id == tool_call_id]

    def to_json_lines(self) -> str:
        """Export log as JSON lines format."""
        return "\n".join(e.to_json() for e in self.events)

    def save(self, path: Path) -> None:
        """Save log to file."""
        path.write_text(self.to_json_lines())

    def clear(self) -> None:
        """Clear all events (for testing)."""
        self.events.clear()


@dataclass
class ToolSchema:
    """Schema for a tool's parameters."""
    name: str
    required_params: list[str]
    optional_params: list[str]
    param_types: dict[str, str]  # param_name -> type


@dataclass
class SimulatedTool:
    """A tool in the simulated harness."""
    name: str
    schema: ToolSchema
    handler: Callable[..., str]
    envelope_type: str = "generic"  # "file_read", "shell", "generic"


class HarnessSimulator:
    """
    Simulates the Devin harness with measured constraints.

    This simulator:
    1. Validates tool calls against schemas (pre-execution)
    2. Dispatches to tool handlers
    3. Applies truncation rules
    4. Wraps results in appropriate envelopes
    5. Logs all events for debugging/replay
    """

    def __init__(
        self,
        constraints: HarnessConstraints = HARNESS_CONSTRAINTS,
        full_output_dir: Path | None = None,
    ):
        self.constraints = constraints
        self.full_output_dir = full_output_dir or Path("/tmp/harness_simulator_outputs")
        self.full_output_dir.mkdir(parents=True, exist_ok=True)

        self.event_log = EventLog()
        self._tools: dict[str, SimulatedTool] = {}
        self._call_counter = 0

    def register_tool(self, tool: SimulatedTool) -> None:
        """Register a tool with the simulator."""
        self._tools[tool.name] = tool
        logger.info(f"Registered simulated tool: {tool.name}")

    def _generate_call_id(self) -> str:
        """Generate a unique tool call ID."""
        self._call_counter += 1
        return f"sim_call_{self._call_counter}_{int(time.time() * 1000)}"

    def _validate_schema(
        self,
        tool: SimulatedTool,
        arguments: dict[str, Any],
        call_id: str,
    ) -> tuple[bool, str | None]:
        """
        Validate arguments against tool schema.

        Returns (is_valid, error_message).
        Schema errors are plain text (no XML envelope) per Experiment 7.2.
        """
        # Check required parameters
        for param in tool.schema.required_params:
            if param not in arguments:
                error = f"Missing required parameter: {param}"
                self.event_log.log_event(
                    EventType.SCHEMA_VALIDATION,
                    call_id,
                    valid=False,
                    error=error,
                )
                return False, error

        # Check parameter types (basic validation)
        for param, value in arguments.items():
            expected_type = tool.schema.param_types.get(param)
            if expected_type == "string" and not isinstance(value, str):
                error = f"Parameter '{param}' must be a string"
                self.event_log.log_event(
                    EventType.SCHEMA_VALIDATION,
                    call_id,
                    valid=False,
                    error=error,
                )
                return False, error

        self.event_log.log_event(
            EventType.SCHEMA_VALIDATION,
            call_id,
            valid=True,
        )
        return True, None

    def _apply_truncation(
        self,
        content: str,
        call_id: str,
        truncation_type: str = "shell",
    ) -> str:
        """
        Apply truncation rules based on output type.

        Shell output: 20k character limit
        File read: ~136 line limit (handled separately)
        """
        if truncation_type == "shell":
            truncated, chars_removed = truncate_output(
                content,
                self.constraints.shell_output_display_limit,
            )

            if chars_removed > 0:
                # Save full output like the real harness does
                output_file = self.full_output_dir / f"{call_id}.txt"
                output_file.write_text(content)

                self.event_log.log_event(
                    EventType.OUTPUT_TRUNCATION,
                    call_id,
                    original_length=len(content),
                    truncated_length=len(truncated),
                    chars_removed=chars_removed,
                    full_output_path=str(output_file),
                )

                # Add truncation notice like the real harness
                truncated += f"\n\n[Output truncated. {chars_removed} characters removed. Full output saved to {output_file}]"

            return truncated

        return content

    def _wrap_envelope(
        self,
        tool: SimulatedTool,
        result: str,
        call_id: str,
        **envelope_data: Any,
    ) -> str:
        """Wrap result in appropriate XML envelope."""
        if tool.envelope_type == "file_read":
            path = envelope_data.get("path", "unknown")
            total_lines = envelope_data.get("total_lines", 0)
            envelope = create_file_read_envelope(path, result, total_lines)
            wrapped = envelope.render()
        elif tool.envelope_type == "shell":
            envelope = create_shell_output_envelope(
                command=envelope_data.get("command", ""),
                output=result,
                return_code=envelope_data.get("return_code", 0),
                exec_dir=envelope_data.get("exec_dir", "/"),
                shell_id=envelope_data.get("shell_id", "default"),
                elapsed_seconds=envelope_data.get("elapsed_seconds", 0.0),
            )
            wrapped = envelope.render()
        else:
            # Generic envelope
            wrapped = f"<tool-result name=\"{tool.name}\">\n{result}\n</tool-result>"

        self.event_log.log_event(
            EventType.ENVELOPE_WRAP,
            call_id,
            envelope_type=tool.envelope_type,
        )

        return wrapped

    def execute(self, tool_call: ToolCall) -> ToolResult:
        """
        Execute a tool call through the simulated harness.

        This follows the measured harness behavior:
        1. Log receipt of tool call
        2. Validate schema (pre-execution)
        3. Dispatch to handler
        4. Apply truncation
        5. Wrap in envelope
        6. Return result
        """
        call_id = tool_call.id or self._generate_call_id()

        # Log receipt
        self.event_log.log_event(
            EventType.TOOL_CALL_RECEIVED,
            call_id,
            tool_name=tool_call.name,
            arguments=tool_call.arguments,
        )

        # Check if tool exists
        tool = self._tools.get(tool_call.name)
        if tool is None:
            self.event_log.log_event(
                EventType.ERROR,
                call_id,
                error=f"Unknown tool: {tool_call.name}",
            )
            return ToolResult(
                tool_call_id=call_id,
                content=f"Error: Unknown tool '{tool_call.name}'",
                success=False,
                error=f"Unknown tool: {tool_call.name}",
            )

        # Schema validation (pre-execution)
        is_valid, error = self._validate_schema(tool, tool_call.arguments, call_id)
        if not is_valid:
            # Schema errors are plain text, no XML envelope
            return ToolResult(
                tool_call_id=call_id,
                content=f"Error: {error}",
                success=False,
                error=error,
            )

        # Dispatch and execute
        self.event_log.log_event(
            EventType.TOOL_DISPATCH,
            call_id,
            tool_name=tool.name,
        )

        start_time = time.time()
        self.event_log.log_event(
            EventType.TOOL_EXECUTION_START,
            call_id,
        )

        try:
            result = tool.handler(**tool_call.arguments)
            elapsed = time.time() - start_time

            self.event_log.log_event(
                EventType.TOOL_EXECUTION_END,
                call_id,
                success=True,
                elapsed_seconds=elapsed,
            )
        except Exception as e:
            elapsed = time.time() - start_time
            self.event_log.log_event(
                EventType.TOOL_EXECUTION_END,
                call_id,
                success=False,
                error=str(e),
                elapsed_seconds=elapsed,
            )

            # Use error envelope
            error_envelope = create_error_envelope(str(e))
            return ToolResult(
                tool_call_id=call_id,
                content=error_envelope.render(),
                success=False,
                error=str(e),
            )

        # Apply truncation
        truncation_type = "shell" if tool.envelope_type == "shell" else "generic"
        truncated_result = self._apply_truncation(result, call_id, truncation_type)

        # Wrap in envelope
        envelope_data = {
            "path": tool_call.arguments.get("path", ""),
            "total_lines": len(result.split("\n")) if result else 0,
            "command": tool_call.arguments.get("command", ""),
            "return_code": 0,
            "exec_dir": tool_call.arguments.get("exec_dir", "/"),
            "shell_id": tool_call.arguments.get("shell_id", "default"),
            "elapsed_seconds": elapsed,
        }
        wrapped_result = self._wrap_envelope(tool, truncated_result, call_id, **envelope_data)

        # Log final result
        self.event_log.log_event(
            EventType.TOOL_RESULT_RETURNED,
            call_id,
            result_length=len(wrapped_result),
        )

        return ToolResult(
            tool_call_id=call_id,
            content=wrapped_result,
            success=True,
        )

    def execute_parallel(self, tool_calls: list[ToolCall]) -> list[ToolResult]:
        """
        Execute multiple tool calls in parallel.

        Per Experiment 7.12, the harness supports true concurrent dispatch.
        This simulates that behavior.
        """
        # In a real implementation, this would use asyncio or threading
        # For now, we execute sequentially but log as parallel
        results = []
        for call in tool_calls:
            result = self.execute(call)
            results.append(result)
        return results

    def get_event_log(self) -> EventLog:
        """Get the event log for inspection."""
        return self.event_log

    def save_event_log(self, path: Path) -> None:
        """Save the event log to a file."""
        self.event_log.save(path)

    def clear_event_log(self) -> None:
        """Clear the event log."""
        self.event_log.clear()


def create_default_simulator() -> HarnessSimulator:
    """
    Create a simulator with default mock tools.

    These tools demonstrate the harness behavior without
    actually performing file/shell operations.
    """
    simulator = HarnessSimulator()

    # Read file tool
    def mock_read_file(file_path: str, offset: int = 0, limit: int = 136) -> str:
        """Mock file read that demonstrates line truncation."""
        # Generate mock content
        lines = [f"Line {i}: This is mock content for {file_path}" for i in range(1, 1001)]

        # Apply line-based truncation
        truncated_lines, was_truncated = truncate_lines(lines[offset:], limit)

        if was_truncated:
            return "\n".join(truncated_lines) + f"\n\n[Showing {limit} of {len(lines)} lines. Use offset/limit for more.]"
        return "\n".join(truncated_lines)

    simulator.register_tool(SimulatedTool(
        name="Read",
        schema=ToolSchema(
            name="Read",
            required_params=["file_path"],
            optional_params=["offset", "limit"],
            param_types={"file_path": "string", "offset": "number", "limit": "number"},
        ),
        handler=mock_read_file,
        envelope_type="file_read",
    ))

    # Bash tool
    def mock_bash(command: str, exec_dir: str = "/", bash_id: str = "default") -> str:
        """Mock bash that demonstrates shell output truncation."""
        # Generate mock output
        return f"Mock output for command: {command}\nExecuted in: {exec_dir}"

    simulator.register_tool(SimulatedTool(
        name="bash",
        schema=ToolSchema(
            name="bash",
            required_params=["command", "exec_dir", "bash_id"],
            optional_params=["timeout"],
            param_types={"command": "string", "exec_dir": "string", "bash_id": "string"},
        ),
        handler=mock_bash,
        envelope_type="shell",
    ))

    # Write tool
    def mock_write(file_path: str, content: str) -> str:
        """Mock file write."""
        return f"Successfully wrote {len(content)} characters to {file_path}"

    simulator.register_tool(SimulatedTool(
        name="Write",
        schema=ToolSchema(
            name="Write",
            required_params=["file_path", "content"],
            optional_params=[],
            param_types={"file_path": "string", "content": "string"},
        ),
        handler=mock_write,
        envelope_type="generic",
    ))

    return simulator
