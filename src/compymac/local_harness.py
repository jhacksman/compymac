"""
LocalHarness - Real tool execution with measured harness constraints.

This harness executes real file I/O and shell commands while applying
the same truncation, envelope, and validation rules as the Devin harness.
It produces identical event logs for debugging and replay.

Supports optional TraceContext for complete execution capture.
"""

import fnmatch
import hashlib
import json
import os
import pty
import re
import select
import subprocess
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

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

if TYPE_CHECKING:
    from compymac.trace_store import TraceContext


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
    - Optionally records complete traces via TraceContext
    """

    def __init__(
        self,
        config: HarnessConfig | None = None,
        full_output_dir: Path | None = None,
        trace_context: "TraceContext | None" = None,
    ):
        self.config = config or HarnessConfig()
        self.full_output_dir = full_output_dir or Path("/tmp/local_harness_outputs")
        self.full_output_dir.mkdir(parents=True, exist_ok=True)

        self._event_log = EventLog()
        self._tools: dict[str, RegisteredTool] = {}
        self._call_counter = 0
        self._trace_context: TraceContext | None = trace_context

        # Thread-local storage for per-thread trace contexts
        # This allows parallel execution with independent trace contexts per thread
        self._thread_local = threading.local()

        # Track files that have been read (for Edit's Read-before-Edit constraint)
        self._files_read: set[str] = set()

        # Shell session state (for persistent bash sessions)
        self._shell_sessions: dict[str, dict[str, Any]] = {}
        self._shell_lock = threading.Lock()

        # Register default tools
        self._register_default_tools()

    def set_trace_context(self, trace_context: "TraceContext | None") -> None:
        """
        Set the trace context for complete execution capture.

        If called from a worker thread (during parallel execution),
        sets the thread-local context. Otherwise sets the default context.
        """
        # Always set thread-local context for the current thread
        self._thread_local.trace_context = trace_context
        # Also update the default context if this is the main setup
        if not hasattr(self._thread_local, '_is_worker'):
            self._trace_context = trace_context

    def get_trace_context(self) -> "TraceContext | None":
        """
        Get the current trace context.

        Returns the thread-local context if set, otherwise the default context.
        """
        # Check for thread-local context first
        thread_ctx = getattr(self._thread_local, 'trace_context', None)
        if thread_ctx is not None:
            return thread_ctx
        return self._trace_context

    def set_thread_local_context(self, trace_context: "TraceContext | None") -> None:
        """
        Set a thread-local trace context for parallel execution.

        This is used by ParallelExecutor to give each worker thread
        its own forked trace context.
        """
        self._thread_local.trace_context = trace_context
        self._thread_local._is_worker = True

    def clear_thread_local_context(self) -> None:
        """Clear the thread-local trace context after parallel execution."""
        if hasattr(self._thread_local, 'trace_context'):
            del self._thread_local.trace_context
        if hasattr(self._thread_local, '_is_worker'):
            del self._thread_local._is_worker

    def _compute_schema_hash(self, tool: RegisteredTool) -> str:
        """Compute a hash of the tool schema for provenance tracking."""
        schema_data = json.dumps({
            "name": tool.schema.name,
            "required_params": tool.schema.required_params,
            "optional_params": tool.schema.optional_params,
            "param_types": tool.schema.param_types,
        }, sort_keys=True)
        return hashlib.sha256(schema_data.encode()).hexdigest()[:16]

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

        # Edit file tool (requires prior Read)
        self.register_tool(
            name="Edit",
            schema=ToolSchema(
                name="Edit",
                description="Edit a file by replacing old_string with new_string. Requires prior Read.",
                required_params=["file_path", "old_string", "new_string"],
                optional_params=["replace_all"],
                param_types={
                    "file_path": "string",
                    "old_string": "string",
                    "new_string": "string",
                    "replace_all": "boolean",
                },
            ),
            handler=self._edit_file,
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
                optional_params=["timeout", "run_in_background"],
                param_types={
                    "command": "string",
                    "exec_dir": "string",
                    "bash_id": "string",
                    "timeout": "number",
                    "run_in_background": "boolean",
                },
            ),
            handler=self._run_bash,
        )

        # bash_output tool - get output from background shell
        self.register_tool(
            name="bash_output",
            schema=ToolSchema(
                name="bash_output",
                description="Get output from a running or completed background shell",
                required_params=["bash_id"],
                optional_params=["filter"],
                param_types={"bash_id": "string", "filter": "string"},
            ),
            handler=self._get_bash_output,
        )

        # write_to_shell tool - send input to shell
        self.register_tool(
            name="write_to_shell",
            schema=ToolSchema(
                name="write_to_shell",
                description="Write input to an active shell process",
                required_params=["shell_id"],
                optional_params=["content", "press_enter"],
                param_types={
                    "shell_id": "string",
                    "content": "string",
                    "press_enter": "boolean",
                },
            ),
            handler=self._write_to_shell,
        )

        # kill_shell tool - terminate a shell
        self.register_tool(
            name="kill_shell",
            schema=ToolSchema(
                name="kill_shell",
                description="Kill a running background shell",
                required_params=["shell_id"],
                optional_params=[],
                param_types={"shell_id": "string"},
            ),
            handler=self._kill_shell,
        )

        # grep tool - search file contents
        self.register_tool(
            name="grep",
            schema=ToolSchema(
                name="grep",
                description="Search for patterns in files using regex",
                required_params=["pattern", "path"],
                optional_params=["output_mode", "glob", "type", "-i", "-n", "-A", "-B", "-C"],
                param_types={
                    "pattern": "string",
                    "path": "string",
                    "output_mode": "string",
                    "glob": "string",
                    "type": "string",
                    "-i": "boolean",
                    "-n": "boolean",
                    "-A": "number",
                    "-B": "number",
                    "-C": "number",
                },
            ),
            handler=self._grep,
        )

        # glob tool - find files by pattern
        self.register_tool(
            name="glob",
            schema=ToolSchema(
                name="glob",
                description="Find files matching a glob pattern",
                required_params=["pattern", "path"],
                optional_params=[],
                param_types={"pattern": "string", "path": "string"},
            ),
            handler=self._glob,
        )

    def register_browser_tools(self) -> None:
        """Register browser automation tools using SyncBrowserService."""
        from compymac.browser import SyncBrowserService

        # Lazy initialization of browser service
        if not hasattr(self, "_browser_service"):
            self._browser_service: SyncBrowserService | None = None

        def _ensure_browser() -> SyncBrowserService:
            if self._browser_service is None:
                self._browser_service = SyncBrowserService()
                self._browser_service.initialize()
            return self._browser_service

        def browser_navigate(url: str, tab_idx: int | None = None) -> str:
            browser = _ensure_browser()
            result = browser.navigate(url)
            if result.error:
                return f"Error: {result.error}"
            page_state = result.page_state
            if page_state:
                elements_info = "\n".join(
                    f"  [{e.element_id}] {e.tag_name}: {e.text[:50] if e.text else ''}"
                    for e in page_state.elements[:20]
                )
                return f"Navigated to {url}\n\nPage title: {page_state.title}\nURL: {page_state.url}\n\nInteractive elements:\n{elements_info}"
            return f"Navigated to {url}"

        def browser_view(tab_idx: int | None = None, reload_window: bool = False) -> str:
            browser = _ensure_browser()
            result = browser.get_page_content()
            if result.error:
                return f"Error: {result.error}"
            page_state = result.page_state
            if page_state:
                elements_info = "\n".join(
                    f"  [{e.element_id}] {e.tag_name}: {e.text[:50] if e.text else ''}"
                    for e in page_state.elements[:20]
                )
                return f"Page title: {page_state.title}\nURL: {page_state.url}\n\nInteractive elements:\n{elements_info}"
            return "No page content available"

        def browser_click(
            devinid: str | None = None,
            coordinates: str | None = None,
            tab_idx: int | None = None,
        ) -> str:
            browser = _ensure_browser()
            coords = None
            if coordinates:
                parts = coordinates.split(",")
                if len(parts) == 2:
                    coords = (float(parts[0]), float(parts[1]))
            result = browser.click(element_id=devinid, coordinates=coords)
            if result.error:
                return f"Error: {result.error}"
            return f"Clicked element {devinid or coordinates}"

        def browser_type(
            content: str,
            devinid: str | None = None,
            coordinates: str | None = None,
            press_enter: bool = False,
            tab_idx: int | None = None,
        ) -> str:
            browser = _ensure_browser()
            result = browser.type_text(
                text=content,
                element_id=devinid,
                press_enter=press_enter,
            )
            if result.error:
                return f"Error: {result.error}"
            return f"Typed '{content[:50]}...' into element"

        def browser_scroll(
            direction: str = "down",
            devinid: str | None = None,
            tab_idx: int | None = None,
        ) -> str:
            browser = _ensure_browser()
            result = browser.scroll(direction=direction, element_id=devinid)
            if result.error:
                return f"Error: {result.error}"
            return f"Scrolled {direction}"

        def browser_screenshot(full_page: bool = False, tab_idx: int | None = None) -> str:
            browser = _ensure_browser()
            result = browser.screenshot(full_page=full_page)
            if result.error:
                return f"Error: {result.error}"
            if result.screenshot_path:
                return f"Screenshot saved to: {result.screenshot_path}"
            return "Screenshot taken"

        def browser_console(content: str | None = None, tab_idx: int | None = None) -> str:
            browser = _ensure_browser()
            if content:
                result = browser.execute_js(content)
                if result.error:
                    return f"Error: {result.error}"
                return f"Executed JS: {result.data}"
            return "No JS to execute"

        # Register browser tools
        self.register_tool(
            name="browser_navigate",
            schema=ToolSchema(
                name="browser_navigate",
                description="Navigate to a URL in the browser",
                required_params=["url"],
                optional_params=["tab_idx"],
                param_types={"url": "string", "tab_idx": "number"},
            ),
            handler=browser_navigate,
        )

        self.register_tool(
            name="browser_view",
            schema=ToolSchema(
                name="browser_view",
                description="View the current browser page state",
                required_params=[],
                optional_params=["tab_idx", "reload_window"],
                param_types={"tab_idx": "number", "reload_window": "boolean"},
            ),
            handler=browser_view,
        )

        self.register_tool(
            name="browser_click",
            schema=ToolSchema(
                name="browser_click",
                description="Click an element in the browser",
                required_params=[],
                optional_params=["devinid", "coordinates", "tab_idx"],
                param_types={"devinid": "string", "coordinates": "string", "tab_idx": "number"},
            ),
            handler=browser_click,
        )

        self.register_tool(
            name="browser_type",
            schema=ToolSchema(
                name="browser_type",
                description="Type text into an element in the browser",
                required_params=["content"],
                optional_params=["devinid", "coordinates", "press_enter", "tab_idx"],
                param_types={
                    "content": "string",
                    "devinid": "string",
                    "coordinates": "string",
                    "press_enter": "boolean",
                    "tab_idx": "number",
                },
            ),
            handler=browser_type,
        )

        self.register_tool(
            name="browser_scroll",
            schema=ToolSchema(
                name="browser_scroll",
                description="Scroll the browser page",
                required_params=["direction", "devinid"],
                optional_params=["tab_idx"],
                param_types={"direction": "string", "devinid": "string", "tab_idx": "number"},
            ),
            handler=browser_scroll,
        )

        self.register_tool(
            name="browser_screenshot",
            schema=ToolSchema(
                name="browser_screenshot",
                description="Take a screenshot of the current page",
                required_params=[],
                optional_params=["full_page", "tab_idx"],
                param_types={"full_page": "boolean", "tab_idx": "number"},
            ),
            handler=browser_screenshot,
        )

        self.register_tool(
            name="browser_console",
            schema=ToolSchema(
                name="browser_console",
                description="Execute JavaScript in the browser console",
                required_params=[],
                optional_params=["content", "tab_idx"],
                param_types={"content": "string", "tab_idx": "number"},
            ),
            handler=browser_console,
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

        # Track that this file has been read (for Edit's Read-before-Edit constraint)
        self._files_read.add(str(path.resolve()))

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
        run_in_background: bool = False,
    ) -> str:
        """Execute a shell command with output truncation."""
        effective_timeout = timeout or 45  # Default 45 second timeout

        if run_in_background:
            return self._run_bash_background(command, exec_dir, bash_id)

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

    def _run_bash_background(
        self,
        command: str,
        exec_dir: str,
        bash_id: str,
    ) -> str:
        """Run a shell command in the background."""
        with self._shell_lock:
            # Create a new PTY for this shell session
            master_fd, slave_fd = pty.openpty()

            process = subprocess.Popen(
                command,
                shell=True,
                cwd=exec_dir,
                stdin=slave_fd,
                stdout=slave_fd,
                stderr=slave_fd,
                preexec_fn=os.setsid,
            )

            self._shell_sessions[bash_id] = {
                "process": process,
                "master_fd": master_fd,
                "slave_fd": slave_fd,
                "output_buffer": "",
                "exec_dir": exec_dir,
                "command": command,
            }

        # Store for envelope
        self._last_return_code = 0
        self._last_exec_dir = exec_dir
        self._last_bash_id = bash_id

        return f"Started background process with bash_id={bash_id}"

    def _get_bash_output(
        self,
        bash_id: str,
        filter: str | None = None,
    ) -> str:
        """Get output from a background shell session."""
        with self._shell_lock:
            if bash_id not in self._shell_sessions:
                return f"Error: No shell session with id '{bash_id}'"

            session = self._shell_sessions[bash_id]
            master_fd = session["master_fd"]
            process = session["process"]

            # Read any available output
            new_output = ""
            try:
                while True:
                    ready, _, _ = select.select([master_fd], [], [], 0.1)
                    if not ready:
                        break
                    data = os.read(master_fd, 4096)
                    if not data:
                        break
                    new_output += data.decode("utf-8", errors="replace")
            except OSError:
                pass

            session["output_buffer"] += new_output

            # Check if process is still running
            poll_result = process.poll()
            status = "running" if poll_result is None else f"finished (exit code {poll_result})"

            output = session["output_buffer"]

            # Apply filter if provided
            if filter:
                try:
                    pattern = re.compile(filter)
                    output = "\n".join(
                        line for line in output.split("\n") if pattern.search(line)
                    )
                except re.error as e:
                    return f"Error: Invalid regex filter: {e}"

            return f"Shell {bash_id} status: {status}\n\nOutput:\n{output}"

    def _write_to_shell(
        self,
        shell_id: str,
        content: str | None = None,
        press_enter: bool = False,
    ) -> str:
        """Write input to an active shell session."""
        with self._shell_lock:
            if shell_id not in self._shell_sessions:
                return f"Error: No shell session with id '{shell_id}'"

            session = self._shell_sessions[shell_id]
            master_fd = session["master_fd"]

            try:
                if content:
                    os.write(master_fd, content.encode("utf-8"))
                if press_enter:
                    os.write(master_fd, b"\n")
                return f"Wrote to shell {shell_id}"
            except OSError as e:
                return f"Error writing to shell: {e}"

    def _kill_shell(self, shell_id: str) -> str:
        """Kill a background shell session."""
        with self._shell_lock:
            if shell_id not in self._shell_sessions:
                return f"Error: No shell session with id '{shell_id}'"

            session = self._shell_sessions[shell_id]
            process = session["process"]

            try:
                process.terminate()
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()

            # Clean up file descriptors
            try:
                os.close(session["master_fd"])
            except OSError:
                pass
            try:
                os.close(session["slave_fd"])
            except OSError:
                pass

            del self._shell_sessions[shell_id]
            return f"Killed shell {shell_id}"

    def _edit_file(
        self,
        file_path: str,
        old_string: str,
        new_string: str,
        replace_all: bool = False,
    ) -> str:
        """Edit a file by replacing old_string with new_string."""
        path = Path(file_path)
        resolved_path = str(path.resolve())

        # Check Read-before-Edit constraint
        if resolved_path not in self._files_read:
            raise ValueError(
                f"Edit requires prior Read. You must Read '{file_path}' before editing it."
            )

        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        content = path.read_text()

        # Check uniqueness constraint
        count = content.count(old_string)
        if count == 0:
            raise ValueError(f"old_string not found in file: {old_string[:100]}...")
        if count > 1 and not replace_all:
            raise ValueError(
                f"old_string appears {count} times. Use replace_all=true to replace all, "
                "or provide more context to make it unique."
            )

        # Perform replacement
        if replace_all:
            new_content = content.replace(old_string, new_string)
            replacements = count
        else:
            new_content = content.replace(old_string, new_string, 1)
            replacements = 1

        path.write_text(new_content)
        return f"Successfully edited {file_path}: {replacements} replacement(s) made"

    def _grep(
        self,
        pattern: str,
        path: str,
        output_mode: str = "files_with_matches",
        glob: str | None = None,
        type: str | None = None,
        **kwargs: Any,
    ) -> str:
        """Search for patterns in files using regex."""
        search_path = Path(path)
        if not search_path.exists():
            raise FileNotFoundError(f"Path not found: {path}")

        # Build ripgrep-like flags
        case_insensitive = kwargs.get("-i", False)
        show_line_numbers = kwargs.get("-n", False)
        context_after = kwargs.get("-A", 0)
        context_before = kwargs.get("-B", 0)
        context_both = kwargs.get("-C", 0)

        if context_both:
            context_after = context_both
            context_before = context_both

        # Compile regex
        flags = re.IGNORECASE if case_insensitive else 0
        try:
            regex = re.compile(pattern, flags)
        except re.error as e:
            raise ValueError(f"Invalid regex pattern: {e}") from e

        results: list[str] = []
        files_with_matches: set[str] = set()
        match_counts: dict[str, int] = {}

        # Determine file type filter
        type_extensions: dict[str, list[str]] = {
            "py": [".py"],
            "js": [".js", ".jsx"],
            "ts": [".ts", ".tsx"],
            "rust": [".rs"],
            "go": [".go"],
            "java": [".java"],
            "c": [".c", ".h"],
            "cpp": [".cpp", ".hpp", ".cc", ".hh"],
        }

        def should_include_file(file_path: Path) -> bool:
            if glob:
                # Support multiple patterns separated by semicolon
                patterns = glob.split(";")
                return any(fnmatch.fnmatch(file_path.name, p.strip()) for p in patterns)
            if type and type in type_extensions:
                return file_path.suffix in type_extensions[type]
            return True

        # Walk directory or search single file
        if search_path.is_file():
            files_to_search = [search_path]
        else:
            files_to_search = [
                f for f in search_path.rglob("*")
                if f.is_file() and should_include_file(f)
            ]

        for file_path in files_to_search:
            try:
                content = file_path.read_text()
                lines = content.split("\n")

                file_matches = []
                for i, line in enumerate(lines):
                    if regex.search(line):
                        files_with_matches.add(str(file_path))
                        match_counts[str(file_path)] = match_counts.get(str(file_path), 0) + 1

                        if output_mode == "content":
                            # Add context lines
                            start = max(0, i - context_before)
                            end = min(len(lines), i + context_after + 1)

                            for j in range(start, end):
                                prefix = f"{file_path}:{j + 1}:" if show_line_numbers else f"{file_path}:"
                                file_matches.append(f"{prefix}{lines[j]}")

                if file_matches:
                    results.extend(file_matches)

            except (UnicodeDecodeError, PermissionError):
                continue

        # Format output based on mode
        if output_mode == "files_with_matches":
            return "\n".join(sorted(files_with_matches)) if files_with_matches else "No matches found"
        elif output_mode == "count":
            return "\n".join(f"{f}:{c}" for f, c in sorted(match_counts.items()))
        else:  # content
            return "\n".join(results) if results else "No matches found"

    def _glob(self, pattern: str, path: str) -> str:
        """Find files matching a glob pattern."""
        search_path = Path(path)
        if not search_path.exists():
            raise FileNotFoundError(f"Path not found: {path}")

        # Support multiple patterns separated by semicolon
        patterns = pattern.split(";")
        matches: set[str] = set()

        for p in patterns:
            p = p.strip()
            # If pattern doesn't contain **, add it to match anywhere
            if "**" not in p:
                p = f"**/{p}"

            for match in search_path.glob(p):
                if match.is_file():
                    matches.add(str(match))

        return "\n".join(sorted(matches)) if matches else "No matches found"

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
        """Execute a single tool call with optional trace capture."""
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

        # Start trace span if tracing is enabled
        span_id: str | None = None
        input_artifact_hash: str | None = None
        trace_ctx = self.get_trace_context()
        if trace_ctx:
            from compymac.trace_store import SpanKind, ToolProvenance

            # Store input as artifact
            input_data = json.dumps(tool_call.arguments, sort_keys=True).encode()
            input_artifact = trace_ctx.store_artifact(
                data=input_data,
                artifact_type="tool_input",
                content_type="application/json",
                metadata={"tool_name": tool_call.name, "call_id": call_id},
            )
            input_artifact_hash = input_artifact.artifact_hash

            # Create tool provenance
            tool_provenance = ToolProvenance(
                tool_name=tool.name,
                schema_hash=self._compute_schema_hash(tool),
                impl_version="1.0.0",
                external_fingerprint={},
            )

            # Start span
            span_id = trace_ctx.start_span(
                kind=SpanKind.TOOL_CALL,
                name=f"tool:{tool.name}",
                actor_id="harness",
                attributes={
                    "tool_name": tool.name,
                    "call_id": call_id,
                    "envelope_type": tool.envelope_type,
                },
                tool_provenance=tool_provenance,
                input_artifact_hash=input_artifact_hash,
            )

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

            # End trace span with error if tracing
            if trace_ctx and span_id:
                from compymac.trace_store import SpanStatus
                trace_ctx.end_span(
                    status=SpanStatus.ERROR,
                    error_class=type(e).__name__,
                    error_message=str(e),
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

        # End trace span with success if tracing
        output_artifact_hash: str | None = None
        if trace_ctx and span_id:
            from compymac.trace_store import SpanStatus

            # Store output as artifact
            output_artifact = trace_ctx.store_artifact(
                data=wrapped.encode(),
                artifact_type="tool_output",
                content_type="text/xml",
                metadata={"tool_name": tool.name, "call_id": call_id},
            )
            output_artifact_hash = output_artifact.artifact_hash

            trace_ctx.end_span(
                status=SpanStatus.OK,
                output_artifact_hash=output_artifact_hash,
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
