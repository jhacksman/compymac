"""
LocalHarness - Real tool execution with measured harness constraints.

This harness executes real file I/O and shell commands while applying
the same truncation, envelope, and validation rules as the Devin harness.
It produces identical event logs for debugging and replay.
"""

import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from compymac.harness import (
    EventLog,
    EventType,
    Harness,
    HarnessConfig,
    ToolSchema,
)
from compymac.harness_spec import (
    create_error_envelope,
    create_file_read_envelope,
    create_shell_output_envelope,
    truncate_lines,
    truncate_output,
)
from compymac.types import ToolCall, ToolResult


@dataclass
class RegisteredTool:
    """A tool registered with the harness."""
    name: str
    schema: ToolSchema
    handler: Callable[..., str]
    envelope_type: str = "generic"


class LocalHarness(Harness):
    """
    Harness that executes real operations with measured constraints.

    This implementation:
    - Executes real file I/O and shell commands
    - Applies truncation rules matching measured limits
    - Wraps results in XML envelopes
    - Logs all events for debugging/replay
    """

    def __init__(
        self,
        config: HarnessConfig | None = None,
        full_output_dir: Path | None = None,
    ):
        self.config = config or HarnessConfig()
        self.full_output_dir = full_output_dir or Path("/tmp/local_harness_outputs")
        self.full_output_dir.mkdir(parents=True, exist_ok=True)

        self._event_log = EventLog()
        self._tools: dict[str, RegisteredTool] = {}
        self._call_counter = 0

        # Register default tools
        self._register_default_tools()

    def _generate_call_id(self) -> str:
        self._call_counter += 1
        return f"local_{self._call_counter}_{int(time.time() * 1000)}"

    def _register_default_tools(self) -> None:
        """Register the standard tool set."""
        # Read file tool
        self.register_tool(
            name="Read",
            schema=ToolSchema(
                name="Read",
                description="Read the contents of a file",
                required_params=["file_path"],
                optional_params=["offset", "limit"],
                param_types={"file_path": "string", "offset": "number", "limit": "number"},
            ),
            handler=self._read_file,
        )

        # Write file tool
        self.register_tool(
            name="Write",
            schema=ToolSchema(
                name="Write",
                description="Write content to a file",
                required_params=["file_path", "content"],
                optional_params=[],
                param_types={"file_path": "string", "content": "string"},
            ),
            handler=self._write_file,
        )

        # Bash tool
        self.register_tool(
            name="bash",
            schema=ToolSchema(
                name="bash",
                description="Execute a shell command",
                required_params=["command", "exec_dir", "bash_id"],
                optional_params=["timeout"],
                param_types={
                    "command": "string",
                    "exec_dir": "string",
                    "bash_id": "string",
                    "timeout": "number",
                },
            ),
            handler=self._run_bash,
        )

    def _read_file(
        self,
        file_path: str,
        offset: int = 0,
        limit: int | None = None,
    ) -> str:
        """Read a file with line-based truncation."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        content = path.read_text()
        lines = content.split("\n")
        total_lines = len(lines)

        # Apply offset
        if offset > 0:
            lines = lines[offset:]

        # Apply limit (default to measured constraint)
        effective_limit = limit or self.config.file_read_default_lines
        truncated_lines, was_truncated = truncate_lines(lines, effective_limit)

        result = "\n".join(truncated_lines)
        if was_truncated:
            result += f"\n\n[Showing {effective_limit} of {total_lines} lines. Use offset/limit for more.]"

        return result

    def _write_file(self, file_path: str, content: str) -> str:
        """Write content to a file."""
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        return f"Successfully wrote {len(content)} characters to {file_path}"

    def _run_bash(
        self,
        command: str,
        exec_dir: str,
        bash_id: str,
        timeout: int | None = None,
    ) -> str:
        """Execute a shell command with output truncation."""
        effective_timeout = timeout or 45  # Default 45 second timeout

        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=exec_dir,
                capture_output=True,
                text=True,
                timeout=effective_timeout,
            )
            output = result.stdout + result.stderr
            return_code = result.returncode
        except subprocess.TimeoutExpired:
            output = f"Command timed out after {effective_timeout} seconds"
            return_code = 124  # Standard timeout exit code
        except Exception as e:
            output = f"Error executing command: {e}"
            return_code = 1

        # Store return code for envelope
        self._last_return_code = return_code
        self._last_exec_dir = exec_dir
        self._last_bash_id = bash_id

        return output

    def register_tool(
        self,
        name: str,
        schema: ToolSchema,
        handler: Callable[..., str],
    ) -> None:
        """Register a tool with the harness."""
        envelope_type = "generic"
        if name == "Read":
            envelope_type = "file_read"
        elif name == "bash":
            envelope_type = "shell"

        self._tools[name] = RegisteredTool(
            name=name,
            schema=schema,
            handler=handler,
            envelope_type=envelope_type,
        )

    def validate_schema(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> tuple[bool, str | None]:
        """Validate arguments against tool schema."""
        tool = self._tools.get(tool_name)
        if tool is None:
            return False, f"Unknown tool: {tool_name}"

        for param in tool.schema.required_params:
            if param not in arguments:
                return False, f"Missing required parameter: {param}"

        return True, None

    def execute(self, tool_call: ToolCall) -> ToolResult:
        """Execute a single tool call."""
        call_id = tool_call.id or self._generate_call_id()

        # Log receipt
        self._event_log.log_event(
            EventType.TOOL_CALL_RECEIVED,
            call_id,
            tool_name=tool_call.name,
            arguments=tool_call.arguments,
        )

        # Check if tool exists
        tool = self._tools.get(tool_call.name)
        if tool is None:
            self._event_log.log_event(
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

        # Schema validation
        is_valid, error = self.validate_schema(tool_call.name, tool_call.arguments)
        self._event_log.log_event(
            EventType.SCHEMA_VALIDATION,
            call_id,
            valid=is_valid,
            error=error,
        )

        if not is_valid:
            return ToolResult(
                tool_call_id=call_id,
                content=f"Error: {error}",
                success=False,
                error=error,
            )

        # Execute
        self._event_log.log_event(EventType.TOOL_DISPATCH, call_id, tool_name=tool.name)
        self._event_log.log_event(EventType.TOOL_EXECUTION_START, call_id)

        start_time = time.time()
        try:
            result = tool.handler(**tool_call.arguments)
            elapsed = time.time() - start_time

            self._event_log.log_event(
                EventType.TOOL_EXECUTION_END,
                call_id,
                success=True,
                elapsed_seconds=elapsed,
            )
        except Exception as e:
            elapsed = time.time() - start_time
            self._event_log.log_event(
                EventType.TOOL_EXECUTION_END,
                call_id,
                success=False,
                error=str(e),
                elapsed_seconds=elapsed,
            )

            error_envelope = create_error_envelope(str(e))
            return ToolResult(
                tool_call_id=call_id,
                content=error_envelope.render(),
                success=False,
                error=str(e),
            )

        # Apply truncation for shell output
        if tool.envelope_type == "shell":
            truncated, chars_removed = truncate_output(
                result,
                self.config.shell_output_display_limit,
            )

            if chars_removed > 0:
                output_file = self.full_output_dir / f"{call_id}.txt"
                output_file.write_text(result)

                self._event_log.log_event(
                    EventType.OUTPUT_TRUNCATION,
                    call_id,
                    original_length=len(result),
                    truncated_length=len(truncated),
                    chars_removed=chars_removed,
                    full_output_path=str(output_file),
                )

                result = truncated + f"\n\n[Output truncated. {chars_removed} characters removed.]"

        # Wrap in envelope
        wrapped = self._wrap_envelope(tool, result, call_id, tool_call.arguments, elapsed)

        self._event_log.log_event(
            EventType.ENVELOPE_WRAP,
            call_id,
            envelope_type=tool.envelope_type,
        )

        self._event_log.log_event(
            EventType.TOOL_RESULT_RETURNED,
            call_id,
            result_length=len(wrapped),
        )

        return ToolResult(
            tool_call_id=call_id,
            content=wrapped,
            success=True,
        )

    def _wrap_envelope(
        self,
        tool: RegisteredTool,
        result: str,
        call_id: str,
        arguments: dict[str, Any],
        elapsed: float,
    ) -> str:
        """Wrap result in appropriate XML envelope."""
        if tool.envelope_type == "file_read":
            path = arguments.get("file_path", "unknown")
            total_lines = len(result.split("\n"))
            envelope = create_file_read_envelope(path, result, total_lines)
            return envelope.render()
        elif tool.envelope_type == "shell":
            envelope = create_shell_output_envelope(
                command=arguments.get("command", ""),
                output=result,
                return_code=getattr(self, "_last_return_code", 0),
                exec_dir=arguments.get("exec_dir", "/"),
                shell_id=arguments.get("bash_id", "default"),
                elapsed_seconds=elapsed,
            )
            return envelope.render()
        else:
            return f"<tool-result name=\"{tool.name}\">\n{result}\n</tool-result>"

    def execute_parallel(self, tool_calls: list[ToolCall]) -> list[ToolResult]:
        """Execute multiple tool calls."""
        # For now, execute sequentially
        # TODO: Add true parallel execution with threading/asyncio
        return [self.execute(call) for call in tool_calls]

    def get_event_log(self) -> EventLog:
        return self._event_log

    def clear_event_log(self) -> None:
        self._event_log.clear()

    def get_tool_schemas(self) -> list[dict[str, Any]]:
        """Get OpenAI-format schemas for all registered tools."""
        schemas = []
        for tool in self._tools.values():
            properties = {}
            for param in tool.schema.required_params + tool.schema.optional_params:
                param_type = tool.schema.param_types.get(param, "string")
                properties[param] = {"type": param_type}

            schemas.append({
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.schema.description,
                    "parameters": {
                        "type": "object",
                        "properties": properties,
                        "required": tool.schema.required_params,
                    },
                },
            })
        return schemas
