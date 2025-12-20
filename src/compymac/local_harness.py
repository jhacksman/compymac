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

        # wait tool - pause execution
        self.register_tool(
            name="wait",
            schema=ToolSchema(
                name="wait",
                description="Wait for a specified number of seconds",
                required_params=["seconds"],
                optional_params=[],
                param_types={"seconds": "number"},
            ),
            handler=self._wait,
        )

        # think tool - reasoning without action
        self.register_tool(
            name="think",
            schema=ToolSchema(
                name="think",
                description="Think about something without taking action. Useful for reasoning.",
                required_params=["thought"],
                optional_params=[],
                param_types={"thought": "string"},
            ),
            handler=self._think,
        )

        # TodoWrite tool - task management
        self.register_tool(
            name="TodoWrite",
            schema=ToolSchema(
                name="TodoWrite",
                description="Create and manage a task list for tracking progress",
                required_params=["todos"],
                optional_params=[],
                param_types={"todos": "array"},
            ),
            handler=self._todo_write,
        )

        # message_user tool - communicate with user
        self.register_tool(
            name="message_user",
            schema=ToolSchema(
                name="message_user",
                description="Send a message to the user",
                required_params=["message"],
                optional_params=["block_on_user", "should_use_concise_message"],
                param_types={
                    "message": "string",
                    "block_on_user": "boolean",
                    "should_use_concise_message": "boolean",
                },
            ),
            handler=self._message_user,
        )

        # web_search tool - search the web
        self.register_tool(
            name="web_search",
            schema=ToolSchema(
                name="web_search",
                description="Search the web using a search query",
                required_params=["query"],
                optional_params=["num_results", "include_domains", "exclude_domains"],
                param_types={
                    "query": "string",
                    "num_results": "number",
                    "include_domains": "array",
                    "exclude_domains": "array",
                },
            ),
            handler=self._web_search,
        )

        # web_get_contents tool - fetch web page contents
        self.register_tool(
            name="web_get_contents",
            schema=ToolSchema(
                name="web_get_contents",
                description="Fetch the contents of one or more web pages",
                required_params=["urls"],
                optional_params=[],
                param_types={"urls": "array"},
            ),
            handler=self._web_get_contents,
        )

        # lsp_tool - Language Server Protocol operations
        self.register_tool(
            name="lsp_tool",
            schema=ToolSchema(
                name="lsp_tool",
                description="Language Server Protocol operations: goto_definition, goto_references, hover_symbol, file_diagnostics",
                required_params=["command", "path"],
                optional_params=["symbol", "line"],
                param_types={
                    "command": "string",
                    "path": "string",
                    "symbol": "string",
                    "line": "number",
                },
            ),
            handler=self._lsp_tool,
        )

        # list_secrets - list available secrets
        self.register_tool(
            name="list_secrets",
            schema=ToolSchema(
                name="list_secrets",
                description="List the names of all secrets available to the agent",
                required_params=[],
                optional_params=[],
                param_types={},
            ),
            handler=self._list_secrets,
        )

        # ask_smart_friend - consult for complex reasoning
        self.register_tool(
            name="ask_smart_friend",
            schema=ToolSchema(
                name="ask_smart_friend",
                description="Ask a smart friend for help with complex reasoning or debugging",
                required_params=["question"],
                optional_params=[],
                param_types={"question": "string"},
            ),
            handler=self._ask_smart_friend,
        )

        # visual_checker - analyze visual content
        self.register_tool(
            name="visual_checker",
            schema=ToolSchema(
                name="visual_checker",
                description="Analyze images, screenshots, or visual content",
                required_params=["question"],
                optional_params=[],
                param_types={"question": "string"},
            ),
            handler=self._visual_checker,
        )

        # Git tools
        self.register_tool(
            name="git_view_pr",
            schema=ToolSchema(
                name="git_view_pr",
                description="View details of a pull request including description, comments, and CI status",
                required_params=["repo", "pull_number"],
                optional_params=[],
                param_types={"repo": "string", "pull_number": "number"},
            ),
            handler=self._git_view_pr,
        )

        self.register_tool(
            name="git_create_pr",
            schema=ToolSchema(
                name="git_create_pr",
                description="Create a new pull request",
                required_params=["repo", "title", "head_branch", "base_branch", "exec_dir"],
                optional_params=["draft"],
                param_types={
                    "repo": "string",
                    "title": "string",
                    "head_branch": "string",
                    "base_branch": "string",
                    "exec_dir": "string",
                    "draft": "boolean",
                },
            ),
            handler=self._git_create_pr,
        )

        self.register_tool(
            name="git_update_pr_description",
            schema=ToolSchema(
                name="git_update_pr_description",
                description="Update the description of an existing pull request",
                required_params=["repo", "pull_number"],
                optional_params=["force"],
                param_types={"repo": "string", "pull_number": "number", "force": "boolean"},
            ),
            handler=self._git_update_pr_description,
        )

        self.register_tool(
            name="git_pr_checks",
            schema=ToolSchema(
                name="git_pr_checks",
                description="Check the CI status of a pull request",
                required_params=["repo", "pull_number"],
                optional_params=["wait_until_complete"],
                param_types={
                    "repo": "string",
                    "pull_number": "number",
                    "wait_until_complete": "boolean",
                },
            ),
            handler=self._git_pr_checks,
        )

        self.register_tool(
            name="git_ci_job_logs",
            schema=ToolSchema(
                name="git_ci_job_logs",
                description="View the logs for a specific CI job",
                required_params=["repo", "job_id"],
                optional_params=[],
                param_types={"repo": "string", "job_id": "number"},
            ),
            handler=self._git_ci_job_logs,
        )

        self.register_tool(
            name="git_comment_on_pr",
            schema=ToolSchema(
                name="git_comment_on_pr",
                description="Post a comment on a pull request",
                required_params=["repo", "pull_number", "body"],
                optional_params=["commit_id", "path", "line", "side", "in_reply_to"],
                param_types={
                    "repo": "string",
                    "pull_number": "number",
                    "body": "string",
                    "commit_id": "string",
                    "path": "string",
                    "line": "number",
                    "side": "string",
                    "in_reply_to": "number",
                },
            ),
            handler=self._git_comment_on_pr,
        )

        self.register_tool(
            name="list_repos",
            schema=ToolSchema(
                name="list_repos",
                description="List all repositories that you have access to",
                required_params=[],
                optional_params=["keyword", "page"],
                param_types={"keyword": "string", "page": "number"},
            ),
            handler=self._list_repos,
        )

        # Deploy tool
        self.register_tool(
            name="deploy",
            schema=ToolSchema(
                name="deploy",
                description="Deploy applications: frontend (static), backend (FastAPI), logs, or expose local port",
                required_params=["command"],
                optional_params=["dir", "port"],
                param_types={"command": "string", "dir": "string", "port": "number"},
            ),
            handler=self._deploy,
        )

        # Recording tools
        self.register_tool(
            name="recording_start",
            schema=ToolSchema(
                name="recording_start",
                description="Start a new screen recording",
                required_params=[],
                optional_params=[],
                param_types={},
            ),
            handler=self._recording_start,
        )

        self.register_tool(
            name="recording_stop",
            schema=ToolSchema(
                name="recording_stop",
                description="Stop the current recording and process it",
                required_params=[],
                optional_params=[],
                param_types={},
            ),
            handler=self._recording_stop,
        )

        # MCP tool
        self.register_tool(
            name="mcp_tool",
            schema=ToolSchema(
                name="mcp_tool",
                description="Interact with MCP servers: list_servers, list_tools, call_tool, read_resource",
                required_params=["command"],
                optional_params=["server", "tool_name", "tool_args", "resource_uri", "shell_id"],
                param_types={
                    "command": "string",
                    "server": "string",
                    "tool_name": "string",
                    "tool_args": "string",
                    "resource_uri": "string",
                    "shell_id": "string",
                },
            ),
            handler=self._mcp_tool,
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

        def browser_press_key(content: str, tab_idx: int | None = None) -> str:
            """Press keyboard keys in the browser."""
            # Stub - would need to add press_key to SyncBrowserService
            return f"Pressed key(s): {content}"

        def browser_move_mouse(
            devinid: str | None = None,
            coordinates: str | None = None,
            tab_idx: int | None = None,
        ) -> str:
            """Move the mouse to an element or coordinates."""
            # Stub - would need to add move_mouse to SyncBrowserService
            if devinid:
                return f"Moved mouse to element {devinid}"
            elif coordinates:
                return f"Moved mouse to coordinates {coordinates}"
            return "No target specified for mouse move"

        def browser_select_option(
            index: str,
            devinid: str | None = None,
            tab_idx: int | None = None,
        ) -> str:
            """Select an option from a dropdown."""
            # Stub - would need to add select_option to SyncBrowserService
            target = f" in element {devinid}" if devinid else ""
            return f"Selected option at index {index}{target}"

        def browser_select_file(content: str, tab_idx: int | None = None) -> str:
            """Select file(s) for upload."""
            # Stub - would need to add select_file to SyncBrowserService
            files = content.strip().split("\n")
            return f"Selected {len(files)} file(s) for upload"

        def browser_set_mobile(enabled: bool, tab_idx: int | None = None) -> str:
            """Toggle mobile mode in the browser."""
            # Stub - would need to add set_mobile to SyncBrowserService
            mode = "enabled" if enabled else "disabled"
            return f"Mobile mode {mode}"

        def browser_restart(url: str, extensions: str | None = None) -> str:
            """Restart the browser with optional extensions."""
            # Stub - would need to add restart to SyncBrowserService
            ext_info = f" with extensions: {extensions}" if extensions else ""
            return f"Browser restarted{ext_info}, navigating to {url}"

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

        self.register_tool(
            name="browser_press_key",
            schema=ToolSchema(
                name="browser_press_key",
                description="Press keyboard keys in the browser",
                required_params=["content"],
                optional_params=["tab_idx"],
                param_types={"content": "string", "tab_idx": "number"},
            ),
            handler=browser_press_key,
        )

        self.register_tool(
            name="browser_move_mouse",
            schema=ToolSchema(
                name="browser_move_mouse",
                description="Move the mouse to an element or coordinates",
                required_params=[],
                optional_params=["devinid", "coordinates", "tab_idx"],
                param_types={"devinid": "string", "coordinates": "string", "tab_idx": "number"},
            ),
            handler=browser_move_mouse,
        )

        self.register_tool(
            name="browser_select_option",
            schema=ToolSchema(
                name="browser_select_option",
                description="Select an option from a dropdown",
                required_params=["index"],
                optional_params=["devinid", "tab_idx"],
                param_types={"index": "string", "devinid": "string", "tab_idx": "number"},
            ),
            handler=browser_select_option,
        )

        self.register_tool(
            name="browser_select_file",
            schema=ToolSchema(
                name="browser_select_file",
                description="Select file(s) for upload in the browser",
                required_params=["content"],
                optional_params=["tab_idx"],
                param_types={"content": "string", "tab_idx": "number"},
            ),
            handler=browser_select_file,
        )

        self.register_tool(
            name="browser_set_mobile",
            schema=ToolSchema(
                name="browser_set_mobile",
                description="Toggle mobile mode in the browser",
                required_params=["enabled"],
                optional_params=["tab_idx"],
                param_types={"enabled": "boolean", "tab_idx": "number"},
            ),
            handler=browser_set_mobile,
        )

        self.register_tool(
            name="browser_restart",
            schema=ToolSchema(
                name="browser_restart",
                description="Restart the browser with optional extensions",
                required_params=["url"],
                optional_params=["extensions"],
                param_types={"url": "string", "extensions": "string"},
            ),
            handler=browser_restart,
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

    def _wait(self, seconds: float) -> str:
        """Wait for a specified number of seconds."""
        if seconds < 0:
            raise ValueError("seconds must be non-negative")
        if seconds > 600:
            raise ValueError("Maximum wait time is 600 seconds")
        time.sleep(seconds)
        return f"Waited {seconds} seconds"

    def _think(self, thought: str) -> str:
        """Record a thought without taking action. Useful for reasoning."""
        # Just log the thought and return it - no side effects
        return f"Thought recorded: {thought}"

    def _todo_write(self, todos: list[dict[str, Any]]) -> str:
        """Update the todo list for task tracking."""
        # Store todos in instance state
        if not hasattr(self, "_todos"):
            self._todos: list[dict[str, Any]] = []
        self._todos = todos

        # Format output
        lines = ["Updated todo list:"]
        for todo in todos:
            status = todo.get("status", "pending")
            content = todo.get("content", "")
            marker = {"pending": "[ ]", "in_progress": "[*]", "completed": "[x]"}.get(
                status, "[ ]"
            )
            lines.append(f"  {marker} {content}")

        return "\n".join(lines)

    def _message_user(
        self,
        message: str,
        block_on_user: bool = False,
        should_use_concise_message: bool = True,
    ) -> str:
        """Send a message to the user."""
        # In local harness, we just print the message
        # In a real deployment, this would send to a UI/API
        print(f"\n[MESSAGE TO USER]\n{message}\n")

        if block_on_user:
            return f"Message sent (blocking): {message[:100]}..."
        return f"Message sent: {message[:100]}..."

    def _web_search(
        self,
        query: str,
        num_results: int = 5,
        include_domains: list[str] | None = None,
        exclude_domains: list[str] | None = None,
        search_type: str = "auto",
        start_published_date: str | None = None,
    ) -> str:
        """Search the web using Exa API.

        Args:
            query: The search query string
            num_results: Number of results to return (default: 5, max: 10)
            include_domains: List of domains to restrict search to
            exclude_domains: List of domains to exclude from search
            search_type: 'auto' (default), 'keyword' for exact matches, 'neural' for semantic
            start_published_date: Only return results published after this date (ISO format)

        Returns:
            Formatted search results with URL, title, and snippet
        """
        import httpx

        # Get API key from environment
        api_key = os.environ.get("EXA_API_KEY")
        if not api_key:
            return "Error: EXA_API_KEY environment variable not set"

        # Build request payload
        payload: dict[str, Any] = {
            "query": query,
            "numResults": min(num_results, 10),
            "text": True,  # Include text snippets
        }

        if search_type != "auto":
            payload["type"] = search_type
        if include_domains:
            payload["includeDomains"] = include_domains
        if exclude_domains:
            payload["excludeDomains"] = exclude_domains
        if start_published_date:
            payload["startPublishedDate"] = start_published_date

        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.post(
                    "https://api.exa.ai/search",
                    headers={
                        "x-api-key": api_key,
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()

            # Format results
            results = data.get("results", [])
            if not results:
                return f"No results found for: {query}"

            output_lines = [f"Search results for: {query}\n"]
            for i, result in enumerate(results, 1):
                title = result.get("title", "No title")
                url = result.get("url", "")
                published = result.get("publishedDate", "")
                text = result.get("text", "")[:300]  # Truncate text

                output_lines.append(f"## Result {i}: {title}")
                output_lines.append(f"URL: {url}")
                if published:
                    output_lines.append(f"Published: {published}")
                if text:
                    output_lines.append(f"\n{text}...")
                output_lines.append("")

            return "\n".join(output_lines)

        except httpx.HTTPStatusError as e:
            return f"Exa API error: {e.response.status_code} - {e.response.text}"
        except httpx.RequestError as e:
            return f"Request error: {e}"
        except Exception as e:
            return f"Error performing web search: {e}"

    def _web_get_contents(self, urls: list[str]) -> str:
        """Fetch the contents of one or more web pages using Exa API.

        Args:
            urls: List of URLs to fetch content from (max 10)

        Returns:
            Formatted page contents with title, URL, and text
        """
        import httpx

        # Get API key from environment
        api_key = os.environ.get("EXA_API_KEY")
        if not api_key:
            return "Error: EXA_API_KEY environment variable not set"

        if len(urls) > 10:
            return "Error: Maximum 10 URLs allowed per request"

        # Build request payload
        payload = {
            "urls": urls,
            "text": True,  # Include full text content
        }

        try:
            with httpx.Client(timeout=60.0) as client:
                response = client.post(
                    "https://api.exa.ai/contents",
                    headers={
                        "x-api-key": api_key,
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()

            # Format results
            results = data.get("results", [])
            if not results:
                return f"No content retrieved for URLs: {urls}"

            output_lines = [f"Content from {len(results)} URL(s):\n"]
            for i, result in enumerate(results, 1):
                title = result.get("title", "No title")
                url = result.get("url", "")
                text = result.get("text", "")

                output_lines.append(f"## Page {i}: {title}")
                output_lines.append(f"URL: {url}")
                output_lines.append(f"\n{text[:5000]}")  # Truncate to 5000 chars
                output_lines.append("\n---\n")

            return "\n".join(output_lines)

        except httpx.HTTPStatusError as e:
            return f"Exa API error: {e.response.status_code} - {e.response.text}"
        except httpx.RequestError as e:
            return f"Request error: {e}"
        except Exception as e:
            return f"Error fetching contents: {e}"

    def _lsp_tool(
        self,
        command: str,
        path: str,
        symbol: str | None = None,
        line: int | None = None,
    ) -> str:
        """Execute LSP operations.

        Note: This is a stub implementation. In production, this would
        integrate with a real LSP server.
        """
        valid_commands = ["goto_definition", "goto_references", "hover_symbol", "file_diagnostics"]
        if command not in valid_commands:
            raise ValueError(f"Invalid LSP command: {command}. Valid: {valid_commands}")

        result = f"LSP {command} on {path}\n"
        if symbol:
            result += f"Symbol: {symbol}\n"
        if line:
            result += f"Line: {line}\n"
        result += "\n[Stub: No actual LSP operation performed. Integrate with LSP server for real results.]"
        return result

    def _list_secrets(self) -> str:
        """List available secrets.

        In local harness, returns environment variables that look like secrets.
        """
        import os

        # Look for common secret patterns in environment
        secret_patterns = ["API_KEY", "SECRET", "TOKEN", "PASSWORD", "CREDENTIAL"]
        found_secrets = []

        for key in os.environ:
            if any(pattern in key.upper() for pattern in secret_patterns):
                found_secrets.append(key)

        if found_secrets:
            return "Available secrets:\n" + "\n".join(f"  - {s}" for s in sorted(found_secrets))
        return "No secrets found in environment."

    def _ask_smart_friend(self, question: str) -> str:
        """Ask a smart friend for help with complex reasoning.

        Note: In production, this would call an LLM for assistance.
        In local harness, returns a placeholder response.
        """
        # In a real implementation, this would call the LLM
        return f"""Smart friend response to: "{question[:100]}..."

[Stub: In production, this would invoke an LLM to help with complex reasoning.
For now, consider:
- Breaking down the problem into smaller parts
- Checking documentation and existing code
- Looking for similar patterns in the codebase]"""

    def _visual_checker(self, question: str) -> str:
        """Analyze visual content.

        Note: In production, this would use a vision model.
        In local harness, returns a placeholder response.
        """
        # In a real implementation, this would call a vision model
        return f"""Visual analysis request: "{question[:100]}..."

[Stub: In production, this would invoke a vision model (e.g., omniparser v2) to analyze images.
For now, ensure:
- The image path is correct and accessible
- The question is specific about what to look for
- Screenshots are taken before analysis]"""

    def _git_view_pr(self, repo: str, pull_number: int) -> str:
        """View details of a pull request using GitHub API.

        Args:
            repo: Repository in owner/repo format
            pull_number: PR number

        Returns:
            PR details including title, description, comments, and CI status
        """
        import httpx

        # Get API token from environment
        token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
        if not token:
            return "Error: GITHUB_TOKEN or GH_TOKEN environment variable not set"

        # Normalize repo format (remove github.com/ prefix if present)
        if repo.startswith("github.com/"):
            repo = repo[11:]

        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

        try:
            with httpx.Client(timeout=30.0) as client:
                # Get PR details
                pr_response = client.get(
                    f"https://api.github.com/repos/{repo}/pulls/{pull_number}",
                    headers=headers,
                )
                pr_response.raise_for_status()
                pr = pr_response.json()

                # Get PR comments
                comments_response = client.get(
                    f"https://api.github.com/repos/{repo}/issues/{pull_number}/comments",
                    headers=headers,
                )
                comments = comments_response.json() if comments_response.status_code == 200 else []

                # Get review comments (inline)
                review_comments_response = client.get(
                    f"https://api.github.com/repos/{repo}/pulls/{pull_number}/comments",
                    headers=headers,
                )
                review_comments = review_comments_response.json() if review_comments_response.status_code == 200 else []

            # Format output
            output_lines = [
                f"# PR #{pull_number}: {pr.get('title', 'No title')}",
                f"URL: {pr.get('html_url', '')}",
                f"State: {pr.get('state', 'unknown')}",
                f"Author: {pr.get('user', {}).get('login', 'unknown')}",
                f"Branch: {pr.get('head', {}).get('ref', '')} -> {pr.get('base', {}).get('ref', '')}",
                f"Mergeable: {pr.get('mergeable', 'unknown')}",
                f"Created: {pr.get('created_at', '')}",
                f"Updated: {pr.get('updated_at', '')}",
                "",
                "## Description",
                pr.get("body", "No description") or "No description",
                "",
            ]

            # Add comments
            if comments:
                output_lines.append(f"## Comments ({len(comments)})")
                for comment in comments[:10]:  # Limit to 10 comments
                    author = comment.get("user", {}).get("login", "unknown")
                    body = comment.get("body", "")[:500]
                    comment_id = comment.get("id", "")
                    output_lines.append(f"\n**{author}** (id: {comment_id}):")
                    output_lines.append(body)
                output_lines.append("")

            # Add review comments
            if review_comments:
                output_lines.append(f"## Review Comments ({len(review_comments)})")
                for comment in review_comments[:10]:
                    author = comment.get("user", {}).get("login", "unknown")
                    path = comment.get("path", "")
                    line = comment.get("line", "")
                    body = comment.get("body", "")[:300]
                    comment_id = comment.get("id", "")
                    output_lines.append(f"\n**{author}** on {path}:{line} (id: {comment_id}):")
                    output_lines.append(body)

            return "\n".join(output_lines)

        except httpx.HTTPStatusError as e:
            return f"GitHub API error: {e.response.status_code} - {e.response.text}"
        except httpx.RequestError as e:
            return f"Request error: {e}"
        except Exception as e:
            return f"Error viewing PR: {e}"

    def _git_create_pr(
        self,
        repo: str,
        title: str,
        head_branch: str,
        base_branch: str,
        exec_dir: str,
        draft: bool = False,
    ) -> str:
        """Create a new pull request using GitHub API.

        Args:
            repo: Repository in owner/repo format
            title: PR title
            head_branch: Branch to merge from
            base_branch: Branch to merge into
            exec_dir: Working directory (for context)
            draft: Whether to create as draft PR

        Returns:
            Created PR details with URL
        """
        import httpx

        # Get API token from environment
        token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
        if not token:
            return "Error: GITHUB_TOKEN or GH_TOKEN environment variable not set"

        # Normalize repo format
        if repo.startswith("github.com/"):
            repo = repo[11:]

        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.post(
                    f"https://api.github.com/repos/{repo}/pulls",
                    headers=headers,
                    json={
                        "title": title,
                        "head": head_branch,
                        "base": base_branch,
                        "draft": draft,
                    },
                )
                response.raise_for_status()
                pr = response.json()

            pr_number = pr.get("number", "")
            pr_url = pr.get("html_url", "")
            draft_str = " (draft)" if draft else ""

            return f"""Created PR{draft_str}: {title}
PR #{pr_number}: {pr_url}
Repository: {repo}
Branch: {head_branch} -> {base_branch}

The user can view it at {pr_url}"""

        except httpx.HTTPStatusError as e:
            error_body = e.response.text
            return f"GitHub API error: {e.response.status_code} - {error_body}"
        except httpx.RequestError as e:
            return f"Request error: {e}"
        except Exception as e:
            return f"Error creating PR: {e}"

    def _git_update_pr_description(
        self,
        repo: str,
        pull_number: int,
        force: bool = False,
    ) -> str:
        """Update the description of an existing pull request.

        Args:
            repo: Repository in owner/repo format
            pull_number: PR number
            force: Force update even if description was modified

        Returns:
            Confirmation of update
        """
        import httpx

        # Get API token from environment
        token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
        if not token:
            return "Error: GITHUB_TOKEN or GH_TOKEN environment variable not set"

        # Normalize repo format
        if repo.startswith("github.com/"):
            repo = repo[11:]

        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

        try:
            with httpx.Client(timeout=30.0) as client:
                # Get current PR to check description
                pr_response = client.get(
                    f"https://api.github.com/repos/{repo}/pulls/{pull_number}",
                    headers=headers,
                )
                pr_response.raise_for_status()
                pr = pr_response.json()

                current_body = pr.get("body", "")
                pr_url = pr.get("html_url", "")

                # Generate new description based on PR diff
                # For now, just append a timestamp to show it was updated
                new_body = current_body or ""
                if not force and "[Auto-updated]" in new_body:
                    return f"PR #{pull_number} description was already auto-updated. Use force=True to update again."

                # In a real implementation, we'd generate a description from the diff
                # For now, we just note that it was updated
                import datetime
                timestamp = datetime.datetime.now(datetime.UTC).isoformat()
                if "[Auto-updated]" not in new_body:
                    new_body += f"\n\n[Auto-updated: {timestamp}]"
                else:
                    # Update existing timestamp
                    import re
                    new_body = re.sub(
                        r"\[Auto-updated: [^\]]+\]",
                        f"[Auto-updated: {timestamp}]",
                        new_body,
                    )

                # Update the PR
                update_response = client.patch(
                    f"https://api.github.com/repos/{repo}/pulls/{pull_number}",
                    headers=headers,
                    json={"body": new_body},
                )
                update_response.raise_for_status()

            return f"""Updated PR #{pull_number} description in {repo}
URL: {pr_url}"""

        except httpx.HTTPStatusError as e:
            return f"GitHub API error: {e.response.status_code} - {e.response.text}"
        except httpx.RequestError as e:
            return f"Request error: {e}"
        except Exception as e:
            return f"Error updating PR description: {e}"

    def _git_pr_checks(
        self,
        repo: str,
        pull_number: int,
        wait_until_complete: bool = True,
    ) -> str:
        """Check the CI status of a pull request.

        Args:
            repo: Repository in owner/repo format
            pull_number: PR number
            wait_until_complete: Whether to wait for all checks to complete

        Returns:
            CI check status for all checks
        """
        import time as time_module

        import httpx

        # Get API token from environment
        token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
        if not token:
            return "Error: GITHUB_TOKEN or GH_TOKEN environment variable not set"

        # Normalize repo format
        if repo.startswith("github.com/"):
            repo = repo[11:]

        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

        max_wait = 600  # 10 minutes max wait
        poll_interval = 10  # Check every 10 seconds
        waited = 0

        try:
            with httpx.Client(timeout=30.0) as client:
                while True:
                    # Get PR to find head SHA
                    pr_response = client.get(
                        f"https://api.github.com/repos/{repo}/pulls/{pull_number}",
                        headers=headers,
                    )
                    pr_response.raise_for_status()
                    pr = pr_response.json()
                    head_sha = pr.get("head", {}).get("sha", "")

                    if not head_sha:
                        return "Error: Could not get PR head SHA"

                    # Get check runs for the commit
                    checks_response = client.get(
                        f"https://api.github.com/repos/{repo}/commits/{head_sha}/check-runs",
                        headers=headers,
                    )
                    checks_response.raise_for_status()
                    checks_data = checks_response.json()
                    check_runs = checks_data.get("check_runs", [])

                    # Count statuses
                    pending = 0
                    success = 0
                    failure = 0
                    skipped = 0
                    cancelled = 0

                    for check in check_runs:
                        status = check.get("status", "")
                        conclusion = check.get("conclusion", "")

                        if status != "completed":
                            pending += 1
                        elif conclusion == "success":
                            success += 1
                        elif conclusion in ("failure", "timed_out"):
                            failure += 1
                        elif conclusion == "skipped":
                            skipped += 1
                        elif conclusion == "cancelled":
                            cancelled += 1

                    all_complete = pending == 0

                    if all_complete or not wait_until_complete or waited >= max_wait:
                        break

                    time_module.sleep(poll_interval)
                    waited += poll_interval

            # Format output
            output_lines = [
                f"CI check results for {head_sha[:8]} (waited {waited}s)",
                "",
                f"{failure} fail",
                f"{pending} pending",
                f"{success} pass",
                f"{skipped} skipping",
                f"{cancelled} cancel",
                "",
            ]

            if failure > 0:
                output_lines.append("Failed checks:")
                for check in check_runs:
                    if check.get("conclusion") in ("failure", "timed_out"):
                        name = check.get("name", "unknown")
                        job_id = check.get("id", "")
                        output_lines.append(f'  - {name} (job_id: {job_id})')
                output_lines.append("")

            if success > 0:
                output_lines.append("Passed checks:")
                for check in check_runs:
                    if check.get("conclusion") == "success":
                        name = check.get("name", "unknown")
                        job_id = check.get("id", "")
                        output_lines.append(f'  - {name} (job_id: {job_id})')

            return "\n".join(output_lines)

        except httpx.HTTPStatusError as e:
            return f"GitHub API error: {e.response.status_code} - {e.response.text}"
        except httpx.RequestError as e:
            return f"Request error: {e}"
        except Exception as e:
            return f"Error checking PR status: {e}"

    def _git_ci_job_logs(self, repo: str, job_id: int) -> str:
        """View the logs for a specific CI job.

        Args:
            repo: Repository in owner/repo format
            job_id: CI job ID

        Returns:
            Full job logs
        """
        import httpx

        # Get API token from environment
        token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
        if not token:
            return "Error: GITHUB_TOKEN or GH_TOKEN environment variable not set"

        # Normalize repo format
        if repo.startswith("github.com/"):
            repo = repo[11:]

        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

        try:
            with httpx.Client(timeout=60.0) as client:
                # Get job details first
                job_response = client.get(
                    f"https://api.github.com/repos/{repo}/actions/jobs/{job_id}",
                    headers=headers,
                )
                job_response.raise_for_status()
                job = job_response.json()

                job_name = job.get("name", "unknown")
                job_status = job.get("status", "unknown")
                job_conclusion = job.get("conclusion", "unknown")

                # Get job logs
                logs_headers = headers.copy()
                logs_headers["Accept"] = "application/vnd.github+json"
                logs_response = client.get(
                    f"https://api.github.com/repos/{repo}/actions/jobs/{job_id}/logs",
                    headers=logs_headers,
                    follow_redirects=True,
                )

                if logs_response.status_code == 200:
                    logs = logs_response.text
                    # Truncate if too long
                    if len(logs) > 50000:
                        logs = logs[:50000] + "\n\n[... truncated ...]"
                else:
                    logs = f"Could not fetch logs: {logs_response.status_code}"

            return f"""Job: {job_name} (ID: {job_id})
Status: {job_status}
Conclusion: {job_conclusion}

--- Logs ---
{logs}"""

        except httpx.HTTPStatusError as e:
            return f"GitHub API error: {e.response.status_code} - {e.response.text}"
        except httpx.RequestError as e:
            return f"Request error: {e}"
        except Exception as e:
            return f"Error fetching job logs: {e}"

    def _git_comment_on_pr(
        self,
        repo: str,
        pull_number: int,
        body: str,
        commit_id: str | None = None,
        path: str | None = None,
        line: int | None = None,
        side: str | None = None,
        in_reply_to: int | None = None,
    ) -> str:
        """Post a comment on a pull request.

        Args:
            repo: Repository in owner/repo format
            pull_number: PR number
            body: Comment body in markdown
            commit_id: Commit SHA for inline comments
            path: File path for inline comments
            line: Line number for inline comments
            side: Side of diff (LEFT or RIGHT)
            in_reply_to: Comment ID to reply to

        Returns:
            Confirmation with comment ID
        """
        import httpx

        # Get API token from environment
        token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
        if not token:
            return "Error: GITHUB_TOKEN or GH_TOKEN environment variable not set"

        # Normalize repo format
        if repo.startswith("github.com/"):
            repo = repo[11:]

        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

        try:
            with httpx.Client(timeout=30.0) as client:
                if in_reply_to:
                    # Reply to existing review comment
                    response = client.post(
                        f"https://api.github.com/repos/{repo}/pulls/{pull_number}/comments/{in_reply_to}/replies",
                        headers=headers,
                        json={"body": body},
                    )
                elif path and line and commit_id:
                    # Create inline review comment
                    payload: dict[str, Any] = {
                        "body": body,
                        "commit_id": commit_id,
                        "path": path,
                        "line": line,
                    }
                    if side:
                        payload["side"] = side

                    response = client.post(
                        f"https://api.github.com/repos/{repo}/pulls/{pull_number}/comments",
                        headers=headers,
                        json=payload,
                    )
                else:
                    # Create general issue comment
                    response = client.post(
                        f"https://api.github.com/repos/{repo}/issues/{pull_number}/comments",
                        headers=headers,
                        json={"body": body},
                    )

                response.raise_for_status()
                comment = response.json()

            comment_id = comment.get("id", "")
            comment_url = comment.get("html_url", "")
            comment_type = "inline" if path and line else "general"
            reply_str = f" (reply to #{in_reply_to})" if in_reply_to else ""

            return f"""Posted {comment_type} comment{reply_str} on PR #{pull_number}
Comment ID: {comment_id}
URL: {comment_url}"""

        except httpx.HTTPStatusError as e:
            return f"GitHub API error: {e.response.status_code} - {e.response.text}"
        except httpx.RequestError as e:
            return f"Request error: {e}"
        except Exception as e:
            return f"Error posting comment: {e}"

    def _list_repos(
        self,
        keyword: str | None = None,
        page: int = 1,
    ) -> str:
        """List all repositories that you have access to.

        Args:
            keyword: Filter repositories by keyword in owner/repo format
            page: Page number for pagination (30 per page)

        Returns:
            List of repositories
        """
        import httpx

        # Get API token from environment
        token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
        if not token:
            return "Error: GITHUB_TOKEN or GH_TOKEN environment variable not set"

        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

        try:
            with httpx.Client(timeout=30.0) as client:
                # Get user's repos
                response = client.get(
                    "https://api.github.com/user/repos",
                    headers=headers,
                    params={
                        "per_page": 30,
                        "page": page,
                        "sort": "updated",
                        "direction": "desc",
                    },
                )
                response.raise_for_status()
                repos = response.json()

            # Filter by keyword if provided
            if keyword:
                keyword_lower = keyword.lower()
                repos = [r for r in repos if keyword_lower in r.get("full_name", "").lower()]

            if not repos:
                filter_str = f" matching '{keyword}'" if keyword else ""
                return f"No repositories found{filter_str} on page {page}"

            # Format output
            output_lines = [f"Repositories (page {page}, {len(repos)} results):"]
            if keyword:
                output_lines[0] += f" matching '{keyword}'"
            output_lines.append("")

            for repo in repos:
                full_name = repo.get("full_name", "")
                description = repo.get("description", "") or "No description"
                private = " (private)" if repo.get("private") else ""
                stars = repo.get("stargazers_count", 0)
                updated = repo.get("updated_at", "")[:10]

                output_lines.append(f"- {full_name}{private}")
                output_lines.append(f"  {description[:80]}")
                output_lines.append(f"  Stars: {stars} | Updated: {updated}")
                output_lines.append("")

            return "\n".join(output_lines)

        except httpx.HTTPStatusError as e:
            return f"GitHub API error: {e.response.status_code} - {e.response.text}"
        except httpx.RequestError as e:
            return f"Request error: {e}"
        except Exception as e:
            return f"Error listing repos: {e}"

    def _deploy(
        self,
        command: str,
        dir: str | None = None,
        port: int | None = None,
    ) -> str:
        """Deploy applications.

        Note: This is a stub. In production, integrate with deployment services.
        """
        valid_commands = ["frontend", "backend", "logs", "expose"]
        if command not in valid_commands:
            raise ValueError(f"Invalid deploy command: {command}. Valid: {valid_commands}")

        if command == "frontend":
            return f"""Deploying frontend from {dir or 'current directory'}

[Stub: In production, this would deploy static files to a CDN and return a public URL.]"""
        elif command == "backend":
            return f"""Deploying backend from {dir or 'current directory'}

[Stub: In production, this would deploy FastAPI to Fly.io and return a public URL.]"""
        elif command == "logs":
            return """Fetching deployment logs

[Stub: In production, this would fetch logs from the deployed application.]"""
        else:  # expose
            return f"""Exposing local port {port or 'unknown'}

[Stub: In production, this would create a tunnel and return a public URL.]"""

    def _recording_start(self) -> str:
        """Start a new screen recording.

        Note: This is a stub. In production, integrate with screen recording service.
        """
        if not hasattr(self, "_recording_active"):
            self._recording_active = False

        if self._recording_active:
            return "Error: Recording already in progress"

        self._recording_active = True
        return "Started screen recording"

    def _recording_stop(self) -> str:
        """Stop the current recording and process it.

        Note: This is a stub. In production, integrate with screen recording service.
        """
        if not hasattr(self, "_recording_active"):
            self._recording_active = False

        if not self._recording_active:
            return "Error: No recording in progress"

        self._recording_active = False
        return """Stopped screen recording

[Stub: In production, this would return the path to the recorded video file.]"""

    def _mcp_tool(
        self,
        command: str,
        server: str | None = None,
        tool_name: str | None = None,
        tool_args: str | None = None,
        resource_uri: str | None = None,
        shell_id: str | None = None,
    ) -> str:
        """Interact with MCP (Model Context Protocol) servers.

        Note: This is a stub. In production, integrate with MCP servers.
        """
        valid_commands = ["list_servers", "list_tools", "call_tool", "read_resource"]
        if command not in valid_commands:
            raise ValueError(f"Invalid MCP command: {command}. Valid: {valid_commands}")

        if command == "list_servers":
            return """Available MCP servers:

[Stub: In production, this would list configured MCP servers like Slack, Linear, etc.]"""
        elif command == "list_tools":
            return f"""Tools available on {server or 'unknown server'}:

[Stub: In production, this would list tools and resources from the MCP server.]"""
        elif command == "call_tool":
            return f"""Called {tool_name} on {server or 'unknown server'}
Args: {tool_args or '{}'}

[Stub: In production, this would execute the tool and return results.]"""
        else:  # read_resource
            return f"""Reading resource {resource_uri} from {server or 'unknown server'}

[Stub: In production, this would read the resource from the MCP server.]"""

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
