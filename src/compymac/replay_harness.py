"""
ReplayHarness - Deterministic replay from event logs.

This harness replays tool results from a previously recorded event log,
enabling deterministic reproduction of agent runs for debugging and testing.
"""

from collections.abc import Callable
from pathlib import Path
from typing import Any

from compymac.harness import (
    EventLog,
    EventType,
    Harness,
    ToolSchema,
)
from compymac.types import ToolCall, ToolResult


class ReplayHarness(Harness):
    """
    Harness that replays results from a recorded event log.

    This enables:
    - Deterministic reproduction of runs
    - Debugging without re-executing tools
    - Testing agent behavior with known tool outputs
    """

    def __init__(self, event_log: EventLog | None = None, log_path: Path | None = None):
        if event_log is not None:
            self._source_log = event_log
        elif log_path is not None:
            self._source_log = EventLog.load(log_path)
        else:
            self._source_log = EventLog()

        self._replay_log = EventLog()
        self._tools: dict[str, ToolSchema] = {}
        self._result_index = 0
        self._recorded_results = self._extract_results()

    def _extract_results(self) -> list[tuple[str, str, bool]]:
        """Extract (tool_call_id, content, success) from recorded events."""
        results = []
        current_call_id = None

        for event in self._source_log.events:
            if event.event_type == EventType.TOOL_CALL_RECEIVED:
                current_call_id = event.tool_call_id
            elif event.event_type == EventType.TOOL_RESULT_RETURNED:
                if current_call_id:
                    # Find the actual result content from execution end
                    for e in self._source_log.events:
                        if (e.tool_call_id == current_call_id and
                            e.event_type == EventType.TOOL_EXECUTION_END):
                            success = e.data.get("success", True)
                            break
                    else:
                        success = True

                    # We need to reconstruct the content - for now use placeholder
                    results.append((current_call_id, f"[Replayed result for {current_call_id}]", success))
                    current_call_id = None

        return results

    def register_tool(
        self,
        name: str,
        schema: ToolSchema,
        handler: Callable[..., str],
    ) -> None:
        """Register a tool schema (handler is ignored in replay mode)."""
        self._tools[name] = schema

    def validate_schema(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> tuple[bool, str | None]:
        """Validate arguments against tool schema."""
        schema = self._tools.get(tool_name)
        if schema is None:
            return True, None  # Allow unknown tools in replay

        for param in schema.required_params:
            if param not in arguments:
                return False, f"Missing required parameter: {param}"

        return True, None

    def execute(self, tool_call: ToolCall) -> ToolResult:
        """Return the next recorded result."""
        call_id = tool_call.id or f"replay_{self._result_index}"

        self._replay_log.log_event(
            EventType.TOOL_CALL_RECEIVED,
            call_id,
            tool_name=tool_call.name,
            arguments=tool_call.arguments,
            replay_mode=True,
        )

        if self._result_index < len(self._recorded_results):
            recorded_id, content, success = self._recorded_results[self._result_index]
            self._result_index += 1

            self._replay_log.log_event(
                EventType.TOOL_RESULT_RETURNED,
                call_id,
                replayed_from=recorded_id,
            )

            return ToolResult(
                tool_call_id=call_id,
                content=content,
                success=success,
            )
        else:
            # No more recorded results
            self._replay_log.log_event(
                EventType.ERROR,
                call_id,
                error="No more recorded results to replay",
            )

            return ToolResult(
                tool_call_id=call_id,
                content="Error: No more recorded results to replay",
                success=False,
                error="Replay exhausted",
            )

    def execute_parallel(self, tool_calls: list[ToolCall]) -> list[ToolResult]:
        """Replay results for multiple tool calls."""
        return [self.execute(call) for call in tool_calls]

    def get_event_log(self) -> EventLog:
        """Get the replay event log."""
        return self._replay_log

    def clear_event_log(self) -> None:
        """Clear the replay event log."""
        self._replay_log.clear()

    def get_tool_schemas(self) -> list[dict[str, Any]]:
        """Get OpenAI-format schemas for registered tools."""
        schemas = []
        for name, schema in self._tools.items():
            properties = {}
            for param in schema.required_params + schema.optional_params:
                param_type = schema.param_types.get(param, "string")
                properties[param] = {"type": param_type}

            schemas.append({
                "type": "function",
                "function": {
                    "name": name,
                    "description": schema.description,
                    "parameters": {
                        "type": "object",
                        "properties": properties,
                        "required": schema.required_params,
                    },
                },
            })
        return schemas

    def reset(self) -> None:
        """Reset replay to beginning."""
        self._result_index = 0
        self._replay_log.clear()

    def get_source_log(self) -> EventLog:
        """Get the source event log being replayed."""
        return self._source_log
