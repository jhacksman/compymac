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
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
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
from compymac.safety import PolicyEngine
from compymac.tool_menu import MenuManager
from compymac.types import ToolCall, ToolResult
from compymac.verification import (
    VerificationEngine,
    VerificationResult,
)

if TYPE_CHECKING:
    from compymac.trace_store import TraceContext


class ToolCategory(Enum):
    """Categories for organizing tools in the toolshed."""
    CORE = "core"  # Always enabled: Read, Write, Edit, bash, grep, glob, think, message_user, request_tools
    SHELL = "shell"  # bash_output, write_to_shell, kill_shell, wait
    GIT_LOCAL = "git_local"  # git_status, git_diff_*, git_commit, git_add, etc.
    GIT_REMOTE = "git_remote"  # git_view_pr, git_create_pr, git_pr_checks, etc.
    FILESYSTEM = "filesystem"  # fs_read_file, fs_write_file, fs_list_directory, etc.
    BROWSER = "browser"  # browser_navigate, browser_view, browser_click, etc.
    SEARCH = "search"  # web_search, web_get_contents
    LSP = "lsp"  # lsp_tool
    DEPLOY = "deploy"  # deploy
    RECORDING = "recording"  # recording_start, recording_stop
    MCP = "mcp"  # mcp_tool
    AI = "ai"  # ask_smart_friend, visual_checker
    SECRETS = "secrets"  # list_secrets
    TODO = "todo"  # TodoCreate, TodoRead, TodoStart, TodoClaim, TodoVerify


@dataclass
class RegisteredTool:
    """A tool registered with the harness."""
    name: str
    schema: ToolSchema
    handler: Callable[..., str]
    envelope_type: str = "generic"
    category: ToolCategory = ToolCategory.CORE
    is_core: bool = False  # If True, always included in active toolset


@dataclass
class ActiveToolset:
    """Tracks which tools are currently enabled for the agent."""
    _enabled_categories: set[ToolCategory] = field(default_factory=lambda: {ToolCategory.CORE})
    _enabled_tools: set[str] = field(default_factory=set)  # Explicitly enabled tool names
    _disabled_tools: set[str] = field(default_factory=set)  # Explicitly disabled tool names

    def enable_category(self, category: ToolCategory) -> None:
        """Enable all tools in a category."""
        self._enabled_categories.add(category)

    def disable_category(self, category: ToolCategory) -> None:
        """Disable a category (except CORE which cannot be disabled)."""
        if category != ToolCategory.CORE:
            self._enabled_categories.discard(category)

    def enable_tool(self, tool_name: str) -> None:
        """Explicitly enable a specific tool."""
        self._enabled_tools.add(tool_name)
        self._disabled_tools.discard(tool_name)

    def disable_tool(self, tool_name: str) -> None:
        """Explicitly disable a specific tool."""
        self._disabled_tools.add(tool_name)
        self._enabled_tools.discard(tool_name)

    def is_enabled(self, tool: "RegisteredTool") -> bool:
        """Check if a tool is currently enabled."""
        # Core tools are always enabled unless explicitly disabled
        if tool.is_core and tool.name not in self._disabled_tools:
            return True
        # Explicitly enabled tools are enabled
        if tool.name in self._enabled_tools:
            return True
        # Explicitly disabled tools are disabled
        if tool.name in self._disabled_tools:
            return False
        # Otherwise, check if the tool's category is enabled
        return tool.category in self._enabled_categories

    def get_enabled_categories(self) -> list[str]:
        """Get list of enabled category names."""
        return [cat.value for cat in self._enabled_categories]

    def reset(self) -> None:
        """Reset to default state (only CORE enabled)."""
        self._enabled_categories = {ToolCategory.CORE}
        self._enabled_tools = set()
        self._disabled_tools = set()


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

        # Active toolset for dynamic tool discovery
        self._active_toolset = ActiveToolset()

        # Verification engine for contract-driven execution
        self._verification_engine = VerificationEngine(enabled=True)

        # Store last verification result for agent consumption
        self._last_verification_result: VerificationResult | None = None

        # Safety policy engine for runtime safety enforcement
        # Respects config setting (disabled by default for backward compatibility)
        self._policy_engine = PolicyEngine(enabled=self.config.enable_safety_policies)

        # Menu manager for hierarchical tool discovery
        self._menu_manager = MenuManager()

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
        # CORE tools - always enabled
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
            category=ToolCategory.CORE,
            is_core=True,
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
            category=ToolCategory.CORE,
            is_core=True,
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
            category=ToolCategory.CORE,
            is_core=True,
        )

        # Bash tool
        self.register_tool(
            name="bash",
            schema=ToolSchema(
                name="bash",
                description="Execute a shell command",
                required_params=["command", "exec_dir", "bash_id"],
                optional_params=["timeout", "description", "run_in_background"],
                param_types={
                    "command": "string",
                    "exec_dir": "string",
                    "bash_id": "string",
                    "timeout": "number",
                    "description": "string",
                    "run_in_background": "boolean",
                },
            ),
            handler=self._run_bash,
            category=ToolCategory.CORE,
            is_core=True,
        )

        # SHELL tools - shell session management
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
            category=ToolCategory.SHELL,
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
            category=ToolCategory.SHELL,
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
            category=ToolCategory.SHELL,
        )

        # CORE tools continued - search tools
        # grep tool - search file contents
        self.register_tool(
            name="grep",
            schema=ToolSchema(
                name="grep",
                description="Search for patterns in files using regex",
                required_params=["pattern", "path"],
                optional_params=["output_mode", "glob", "type", "-i", "-n", "-A", "-B", "-C", "multiline", "head_limit"],
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
                    "multiline": "boolean",
                    "head_limit": "number",
                },
            ),
            handler=self._grep,
            category=ToolCategory.CORE,
            is_core=True,
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
            category=ToolCategory.CORE,
            is_core=True,
        )

        # SHELL tools continued
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
            category=ToolCategory.SHELL,
        )

        # CORE tools continued - reasoning
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
            category=ToolCategory.CORE,
            is_core=True,
        )

        # TODO tools - Guardrailed task management with anti-hallucination patterns
        # See docs/guardrail-architecture.md for design rationale

        # TodoCreate - Create a single todo item with stable ID
        self.register_tool(
            name="TodoCreate",
            schema=ToolSchema(
                name="TodoCreate",
                description=(
                    "Create a single todo item with a stable ID. "
                    "Flow: TodoCreate -> TodoStart -> TodoClaim -> TodoVerify. "
                    "Use acceptance_criteria for machine-verifiable completion: "
                    "[{\"type\": \"command_exit_zero\", \"params\": {\"command\": \"ruff check\"}}, "
                    "{\"type\": \"file_exists\", \"params\": {\"path\": \"/path/to/file\"}}]"
                ),
                required_params=["content"],
                optional_params=["acceptance_criteria"],
                param_types={
                    "content": "string",
                    "acceptance_criteria": "array",  # List of {type, params} objects
                },
            ),
            handler=self._todo_create,
            category=ToolCategory.TODO,
        )

        # TodoRead - List all todos with IDs and status
        self.register_tool(
            name="TodoRead",
            schema=ToolSchema(
                name="TodoRead",
                description="List all todos with their stable IDs, status, and audit history. Status: pending -> in_progress -> claimed -> verified.",
                required_params=[],
                optional_params=[],
                param_types={},
            ),
            handler=self._todo_read,
            category=ToolCategory.TODO,
        )

        # TodoStart - Move todo from pending to in_progress
        self.register_tool(
            name="TodoStart",
            schema=ToolSchema(
                name="TodoStart",
                description="Start working on a todo. Moves status from 'pending' to 'in_progress'. Must provide the todo ID.",
                required_params=["id"],
                optional_params=[],
                param_types={"id": "string"},
            ),
            handler=self._todo_start,
            category=ToolCategory.TODO,
        )

        # TodoClaim - Claim a todo is complete (agent assertion, not verified)
        self.register_tool(
            name="TodoClaim",
            schema=ToolSchema(
                name="TodoClaim",
                description=(
                    "Claim a todo is complete. IMPORTANT: 'claimed' is NOT done - only 'verified' counts as complete. "
                    "Moves status from 'in_progress' to 'claimed'. Provide evidence to support the claim. "
                    "Evidence format: [{\"type\": \"tool_call_id\", \"data\": \"call_xyz\"}, "
                    "{\"type\": \"file_path\", \"data\": \"/path/to/output\"}]. "
                    "Use TodoVerify next to check acceptance criteria."
                ),
                required_params=["id"],
                optional_params=["evidence"],
                param_types={
                    "id": "string",
                    "evidence": "array",  # List of {type, data} objects
                },
            ),
            handler=self._todo_claim,
            category=ToolCategory.TODO,
        )

        # TodoVerify - Verify a claimed todo (harness-level, checks acceptance criteria)
        self.register_tool(
            name="TodoVerify",
            schema=ToolSchema(
                name="TodoVerify",
                description=(
                    "Verify a claimed todo by checking its acceptance criteria. "
                    "Only works on 'claimed' todos. If all criteria pass, moves to 'verified' (the only true completion state). "
                    "If criteria fail, status remains 'claimed' - fix the issue and verify again."
                ),
                required_params=["id"],
                optional_params=[],
                param_types={"id": "string"},
            ),
            handler=self._todo_verify,
            category=ToolCategory.TODO,
        )

        # request_tools - dynamic tool discovery (CORE - always enabled)
        self.register_tool(
            name="request_tools",
            schema=ToolSchema(
                name="request_tools",
                description="Request additional tools to be enabled. Use list_categories=true to see available tool categories, or specify a category or tool_names to enable specific tools.",
                required_params=[],
                optional_params=["category", "tool_names", "list_categories"],
                param_types={
                    "category": "string",
                    "tool_names": "array",
                    "list_categories": "boolean",
                },
            ),
            handler=self._request_tools,
            category=ToolCategory.CORE,
            is_core=True,
        )

        # CORE tools - message_user (always enabled)
        self.register_tool(
            name="message_user",
            schema=ToolSchema(
                name="message_user",
                description="Send a message to the user",
                required_params=["message", "block_on_user", "should_use_concise_message"],
                optional_params=["attachments", "request_auth", "request_deploy"],
                param_types={
                    "message": "string",
                    "block_on_user": "boolean",
                    "should_use_concise_message": "boolean",
                    "attachments": "string",
                    "request_auth": "boolean",
                    "request_deploy": "boolean",
                },
            ),
            handler=self._message_user,
            category=ToolCategory.CORE,
            is_core=True,
        )

        # SEARCH tools - web search
        self.register_tool(
            name="web_search",
            schema=ToolSchema(
                name="web_search",
                description="Search the web using a search query",
                required_params=["query"],
                optional_params=["num_results", "type", "include_domains", "exclude_domains", "start_published_date"],
                param_types={
                    "query": "string",
                    "num_results": "number",
                    "type": "string",
                    "include_domains": "array",
                    "exclude_domains": "array",
                    "start_published_date": "string",
                },
            ),
            handler=self._web_search,
            category=ToolCategory.SEARCH,
        )

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
            category=ToolCategory.SEARCH,
        )

        # LSP tools
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
            category=ToolCategory.LSP,
        )

        # SECRETS tools
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
            category=ToolCategory.SECRETS,
        )

        # AI tools - smart friend and visual checker
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
            category=ToolCategory.AI,
        )

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
            category=ToolCategory.AI,
        )

        # GIT_REMOTE tools - GitHub/GitLab API operations
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
            category=ToolCategory.GIT_REMOTE,
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
            category=ToolCategory.GIT_REMOTE,
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
            category=ToolCategory.GIT_REMOTE,
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
            category=ToolCategory.GIT_REMOTE,
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
            category=ToolCategory.GIT_REMOTE,
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
            category=ToolCategory.GIT_REMOTE,
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
            category=ToolCategory.GIT_REMOTE,
        )

        # DEPLOY tools
        self.register_tool(
            name="deploy",
            schema=ToolSchema(
                name="deploy",
                description="Deploy applications: frontend (static to GitHub Pages), backend (FastAPI to Fly.io), logs (view Fly.io logs), or expose local port",
                required_params=["command"],
                optional_params=["dir", "port", "repo", "app"],
                param_types={"command": "string", "dir": "string", "port": "number", "repo": "string", "app": "string"},
            ),
            handler=self._deploy,
            category=ToolCategory.DEPLOY,
        )

        # RECORDING tools
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
            category=ToolCategory.RECORDING,
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
            category=ToolCategory.RECORDING,
        )

        # MCP tools
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
            category=ToolCategory.MCP,
        )

        # GIT_LOCAL tools (local git operations using GitPython)
        self.register_tool(
            name="git_status",
            schema=ToolSchema(
                name="git_status",
                description="Get the status of a git repository",
                required_params=["repo_path"],
                optional_params=[],
                param_types={"repo_path": "string"},
            ),
            handler=self._git_status,
            category=ToolCategory.GIT_LOCAL,
        )

        self.register_tool(
            name="git_diff_unstaged",
            schema=ToolSchema(
                name="git_diff_unstaged",
                description="Get diff of unstaged changes in a git repository",
                required_params=["repo_path"],
                optional_params=["context_lines"],
                param_types={"repo_path": "string", "context_lines": "number"},
            ),
            handler=self._git_diff_unstaged,
            category=ToolCategory.GIT_LOCAL,
        )

        self.register_tool(
            name="git_diff_staged",
            schema=ToolSchema(
                name="git_diff_staged",
                description="Get diff of staged changes in a git repository",
                required_params=["repo_path"],
                optional_params=["context_lines"],
                param_types={"repo_path": "string", "context_lines": "number"},
            ),
            handler=self._git_diff_staged,
            category=ToolCategory.GIT_LOCAL,
        )

        self.register_tool(
            name="git_diff",
            schema=ToolSchema(
                name="git_diff",
                description="Get diff between current state and a target (branch, commit, tag)",
                required_params=["repo_path", "target"],
                optional_params=["context_lines"],
                param_types={"repo_path": "string", "target": "string", "context_lines": "number"},
            ),
            handler=self._git_diff,
            category=ToolCategory.GIT_LOCAL,
        )

        self.register_tool(
            name="git_commit",
            schema=ToolSchema(
                name="git_commit",
                description="Commit staged changes with a message",
                required_params=["repo_path", "message"],
                optional_params=[],
                param_types={"repo_path": "string", "message": "string"},
            ),
            handler=self._git_commit,
            category=ToolCategory.GIT_LOCAL,
        )

        self.register_tool(
            name="git_add",
            schema=ToolSchema(
                name="git_add",
                description="Stage files for commit",
                required_params=["repo_path", "files"],
                optional_params=[],
                param_types={"repo_path": "string", "files": "array"},
            ),
            handler=self._git_add,
            category=ToolCategory.GIT_LOCAL,
        )

        self.register_tool(
            name="git_reset",
            schema=ToolSchema(
                name="git_reset",
                description="Unstage all staged changes",
                required_params=["repo_path"],
                optional_params=[],
                param_types={"repo_path": "string"},
            ),
            handler=self._git_reset,
            category=ToolCategory.GIT_LOCAL,
        )

        self.register_tool(
            name="git_log",
            schema=ToolSchema(
                name="git_log",
                description="Get commit history",
                required_params=["repo_path"],
                optional_params=["max_count"],
                param_types={"repo_path": "string", "max_count": "number"},
            ),
            handler=self._git_log,
            category=ToolCategory.GIT_LOCAL,
        )

        self.register_tool(
            name="git_create_branch",
            schema=ToolSchema(
                name="git_create_branch",
                description="Create a new branch",
                required_params=["repo_path", "branch_name"],
                optional_params=["base_branch"],
                param_types={"repo_path": "string", "branch_name": "string", "base_branch": "string"},
            ),
            handler=self._git_create_branch,
            category=ToolCategory.GIT_LOCAL,
        )

        self.register_tool(
            name="git_checkout",
            schema=ToolSchema(
                name="git_checkout",
                description="Switch to a branch",
                required_params=["repo_path", "branch_name"],
                optional_params=[],
                param_types={"repo_path": "string", "branch_name": "string"},
            ),
            handler=self._git_checkout,
            category=ToolCategory.GIT_LOCAL,
        )

        self.register_tool(
            name="git_show",
            schema=ToolSchema(
                name="git_show",
                description="Show details of a commit",
                required_params=["repo_path", "revision"],
                optional_params=[],
                param_types={"repo_path": "string", "revision": "string"},
            ),
            handler=self._git_show,
            category=ToolCategory.GIT_LOCAL,
        )

        self.register_tool(
            name="git_branch_list",
            schema=ToolSchema(
                name="git_branch_list",
                description="List branches in a repository",
                required_params=["repo_path"],
                optional_params=["show_remote"],
                param_types={"repo_path": "string", "show_remote": "boolean"},
            ),
            handler=self._git_branch_list,
            category=ToolCategory.GIT_LOCAL,
        )

        # FILESYSTEM tools (local file operations)
        self.register_tool(
            name="fs_read_file",
            schema=ToolSchema(
                name="fs_read_file",
                description="Read contents of a file",
                required_params=["path"],
                optional_params=[],
                param_types={"path": "string"},
            ),
            handler=self._fs_read_file,
            category=ToolCategory.FILESYSTEM,
        )

        self.register_tool(
            name="fs_write_file",
            schema=ToolSchema(
                name="fs_write_file",
                description="Write contents to a file",
                required_params=["path", "content"],
                optional_params=[],
                param_types={"path": "string", "content": "string"},
            ),
            handler=self._fs_write_file,
            category=ToolCategory.FILESYSTEM,
        )

        self.register_tool(
            name="fs_list_directory",
            schema=ToolSchema(
                name="fs_list_directory",
                description="List contents of a directory",
                required_params=["path"],
                optional_params=[],
                param_types={"path": "string"},
            ),
            handler=self._fs_list_directory,
            category=ToolCategory.FILESYSTEM,
        )

        self.register_tool(
            name="fs_create_directory",
            schema=ToolSchema(
                name="fs_create_directory",
                description="Create a directory (and parent directories if needed)",
                required_params=["path"],
                optional_params=[],
                param_types={"path": "string"},
            ),
            handler=self._fs_create_directory,
            category=ToolCategory.FILESYSTEM,
        )

        self.register_tool(
            name="fs_delete",
            schema=ToolSchema(
                name="fs_delete",
                description="Delete a file or empty directory",
                required_params=["path"],
                optional_params=[],
                param_types={"path": "string"},
            ),
            handler=self._fs_delete,
            category=ToolCategory.FILESYSTEM,
        )

        self.register_tool(
            name="fs_move",
            schema=ToolSchema(
                name="fs_move",
                description="Move or rename a file or directory",
                required_params=["source", "destination"],
                optional_params=[],
                param_types={"source": "string", "destination": "string"},
            ),
            handler=self._fs_move,
            category=ToolCategory.FILESYSTEM,
        )

        self.register_tool(
            name="fs_file_info",
            schema=ToolSchema(
                name="fs_file_info",
                description="Get metadata about a file or directory",
                required_params=["path"],
                optional_params=[],
                param_types={"path": "string"},
            ),
            handler=self._fs_file_info,
            category=ToolCategory.FILESYSTEM,
        )

        # AGENT CONTROL tools - for action-gated dialogue protocol
        # complete tool - the ONLY way to finish in action-gated mode
        self.register_tool(
            name="complete",
            schema=ToolSchema(
                name="complete",
                description=(
                    "Signal that you have completed the task. "
                    "This is the ONLY way to finish - you cannot end by just returning text. "
                    "Call this when you have accomplished the goal or determined it cannot be done."
                ),
                required_params=["final_answer"],
                optional_params=["status"],
                param_types={"final_answer": "string", "status": "string"},
            ),
            handler=self._complete,
            category=ToolCategory.CORE,
            is_core=True,
        )

        # MENU NAVIGATION tools - for hierarchical tool discovery
        self.register_tool(
            name="menu_list",
            schema=ToolSchema(
                name="menu_list",
                description=(
                    "List the current menu state and available options. "
                    "Shows current mode (if any) and available modes to enter. "
                    "Use this to see what tools are available in the current context."
                ),
                required_params=[],
                optional_params=[],
                param_types={},
            ),
            handler=self._menu_list,
            category=ToolCategory.CORE,
            is_core=True,
        )

        self.register_tool(
            name="menu_enter",
            schema=ToolSchema(
                name="menu_enter",
                description=(
                    "Enter a specific tool mode to access its tools. "
                    "Available modes: swe (code editing), browser (web automation), "
                    "git (version control), deploy (deployment), search (web search), "
                    "ai (AI assistance), data (filesystem). "
                    "Once in a mode, you can use that mode's tools plus meta-tools."
                ),
                required_params=["mode"],
                optional_params=[],
                param_types={"mode": "string"},
            ),
            handler=self._menu_enter,
            category=ToolCategory.CORE,
            is_core=True,
        )

        self.register_tool(
            name="menu_exit",
            schema=ToolSchema(
                name="menu_exit",
                description=(
                    "Exit the current mode and return to ROOT. "
                    "Use this when you need to switch to a different mode. "
                    "At ROOT, only meta-tools are available."
                ),
                required_params=[],
                optional_params=[],
                param_types={},
            ),
            handler=self._menu_exit,
            category=ToolCategory.CORE,
            is_core=True,
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
                    f"  [{e.element_id}] {e.tag}: {e.text[:50] if e.text else ''}"
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
                    f"  [{e.element_id}] {e.tag}: {e.text[:50] if e.text else ''}"
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
            # "page" means scroll the whole page, not an element
            element_id = None if devinid == "page" else devinid
            result = browser.scroll(direction=direction, element_id=element_id)
            if result.error:
                return f"Error: {result.error}"
            return f"Scrolled {direction}"

        def browser_screenshot(full_page: bool = False, tab_idx: int | None = None) -> str:
            browser = _ensure_browser()
            result = browser.screenshot(full_page=full_page)
            if result.error:
                return f"Error: {result.error}"
            if result.details and result.details.get("path"):
                return f"Screenshot saved to: {result.details['path']}"
            return "Screenshot taken"

        def browser_console(content: str | None = None, tab_idx: int | None = None) -> str:
            browser = _ensure_browser()
            if content:
                result = browser.execute_js(content)
                if result.error:
                    return f"Error: {result.error}"
                js_result = result.details.get("result", "") if result.details else ""
                return f"Executed JS: {js_result}"
            return "No JS to execute"

        def browser_press_key(content: str, tab_idx: int | None = None) -> str:
            """Press keyboard keys in the browser."""
            browser = _ensure_browser()
            result = browser.press_key(content)
            if result.error:
                return f"Error: {result.error}"
            return f"Pressed key(s): {content}"

        def browser_move_mouse(
            devinid: str | None = None,
            coordinates: str | None = None,
            tab_idx: int | None = None,
        ) -> str:
            """Move the mouse to an element or coordinates."""
            browser = _ensure_browser()
            coords_tuple = None
            if coordinates:
                parts = coordinates.split(",")
                if len(parts) == 2:
                    coords_tuple = (float(parts[0].strip()), float(parts[1].strip()))
            result = browser.move_mouse(element_id=devinid, coordinates=coords_tuple)
            if result.error:
                return f"Error: {result.error}"
            if devinid:
                return f"Moved mouse to element {devinid}"
            elif coordinates:
                return f"Moved mouse to coordinates {coordinates}"
            return "Mouse moved"

        def browser_select_option(
            index: str,
            devinid: str | None = None,
            tab_idx: int | None = None,
        ) -> str:
            """Select an option from a dropdown."""
            browser = _ensure_browser()
            result = browser.select_option(index=int(index), element_id=devinid)
            if result.error:
                return f"Error: {result.error}"
            target = f" in element {devinid}" if devinid else ""
            return f"Selected option at index {index}{target}"

        def browser_select_file(
            content: str,
            devinid: str | None = None,
            tab_idx: int | None = None,
        ) -> str:
            """Select file(s) for upload on a file input element."""
            browser = _ensure_browser()
            files = content.strip().split("\n")
            result = browser.select_file(files, element_id=devinid)
            if result.error:
                return f"Error: {result.error}"
            target = f" on element {devinid}" if devinid else ""
            return f"Selected {len(files)} file(s) for upload{target}"

        def browser_set_mobile(enabled: bool, tab_idx: int | None = None) -> str:
            """Toggle mobile mode in the browser."""
            browser = _ensure_browser()
            result = browser.set_mobile(enabled)
            if result.error:
                return f"Error: {result.error}"
            mode = "enabled" if enabled else "disabled"
            return f"Mobile mode {mode}"

        def browser_restart(url: str, extensions: str | None = None) -> str:
            """Restart the browser with optional extensions."""
            browser = _ensure_browser()
            ext_list = extensions.split(",") if extensions else None
            result = browser.restart(url, ext_list)
            if result.error:
                return f"Error: {result.error}"
            ext_info = f" with extensions: {extensions}" if extensions else ""
            return f"Browser restarted{ext_info}, navigating to {url}"

        # Register browser tools (BROWSER category)
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
            category=ToolCategory.BROWSER,
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
            category=ToolCategory.BROWSER,
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
            category=ToolCategory.BROWSER,
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
            category=ToolCategory.BROWSER,
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
            category=ToolCategory.BROWSER,
        )

        self.register_tool(
            name="browser_screenshot",
            schema=ToolSchema(
                name="browser_screenshot",
                description="Take a screenshot of the current page",
                required_params=[],
                optional_params=["tab_idx"],
                param_types={"tab_idx": "number"},
            ),
            handler=browser_screenshot,
            category=ToolCategory.BROWSER,
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
            category=ToolCategory.BROWSER,
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
            category=ToolCategory.BROWSER,
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
            category=ToolCategory.BROWSER,
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
            category=ToolCategory.BROWSER,
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
            category=ToolCategory.BROWSER,
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
            category=ToolCategory.BROWSER,
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
            category=ToolCategory.BROWSER,
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
        description: str | None = None,
        run_in_background: bool = False,
    ) -> str:
        """Execute a shell command with output truncation.

        Args:
            command: The shell command to execute
            exec_dir: Directory to execute the command in
            bash_id: Identifier for the shell session
            timeout: Optional timeout in seconds (default: 45)
            description: Optional human-readable description of what the command does
            run_in_background: Whether to run the command in the background
        """
        effective_timeout = timeout or 45  # Default 45 second timeout

        # Store description for tracing/logging purposes
        if description:
            self._last_command_description = description

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
        multiline: bool = False,
        head_limit: int | None = None,
        **kwargs: Any,
    ) -> str:
        """Search for patterns in files using regex.

        Args:
            pattern: The regex pattern to search for
            path: File or directory to search in
            output_mode: 'files_with_matches', 'content', or 'count'
            glob: Glob pattern to filter files
            type: File type to search (py, js, ts, etc.)
            multiline: Enable multiline mode where . matches newlines
            head_limit: Limit output to first N lines/entries
        """
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
        if multiline:
            flags |= re.MULTILINE | re.DOTALL
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
                file_content = file_path.read_text()
                lines = file_content.split("\n")

                file_matches = []

                if multiline:
                    # Multiline mode: search across the entire file content
                    for match in regex.finditer(file_content):
                        files_with_matches.add(str(file_path))
                        match_counts[str(file_path)] = match_counts.get(str(file_path), 0) + 1

                        if output_mode == "content":
                            line_num = file_content[:match.start()].count("\n") + 1
                            matched_text = match.group()
                            if len(matched_text) > 500:
                                matched_text = matched_text[:500] + "..."
                            prefix = f"{file_path}:{line_num}:" if show_line_numbers else f"{file_path}:"
                            file_matches.append(f"{prefix}{matched_text}")
                else:
                    # Line-by-line mode (original behavior)
                    for i, line in enumerate(lines):
                        if regex.search(line):
                            files_with_matches.add(str(file_path))
                            match_counts[str(file_path)] = match_counts.get(str(file_path), 0) + 1

                            if output_mode == "content":
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
            output_list = sorted(files_with_matches)
            if head_limit:
                output_list = output_list[:head_limit]
            return "\n".join(output_list) if output_list else "No matches found"
        elif output_mode == "count":
            output_list = [f"{f}:{c}" for f, c in sorted(match_counts.items())]
            if head_limit:
                output_list = output_list[:head_limit]
            return "\n".join(output_list)
        else:  # content
            if head_limit:
                results = results[:head_limit]
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

    def _complete(self, final_answer: str, status: str = "success") -> str:
        """Signal task completion. This is the ONLY way to finish in action-gated mode.

        Args:
            final_answer: The final answer or result of the task
            status: Optional status indicator (success/failure/partial)

        Returns:
            Confirmation message with the final answer
        """
        # Store completion state for the agent loop to detect
        self._completion_signaled = True
        self._completion_answer = final_answer
        self._completion_status = status
        return f"Task completed with status '{status}': {final_answer}"

    # =========================================================================
    # Menu Navigation System - Hierarchical tool discovery
    # See tool_menu.py for design rationale
    # =========================================================================

    def _menu_list(self) -> str:
        """List the current menu state and available options."""
        return self._menu_manager.list_menu()

    def _menu_enter(self, mode: str) -> str:
        """Enter a specific tool mode to access its tools."""
        success, message = self._menu_manager.enter_mode(mode)
        return message

    def _menu_exit(self) -> str:
        """Exit the current mode and return to ROOT."""
        success, message = self._menu_manager.exit_mode()
        return message

    def get_menu_tool_schemas(self) -> list[dict[str, Any]]:
        """Get OpenAI-format schemas for only the tools visible in the current menu state.

        This is the key method for hierarchical tool discovery. It returns:
        - At ROOT: only meta-tools (menu_list, menu_enter, menu_exit, complete, think, message_user)
        - In a mode: meta-tools + that mode's tools

        This dramatically reduces context size compared to exposing all 60+ tools.
        """
        visible_tool_names = self._menu_manager.get_visible_tools()
        visible_tools = [
            self._tools[name] for name in visible_tool_names
            if name in self._tools
        ]
        return self._build_schemas(visible_tools)

    def get_menu_manager(self) -> MenuManager:
        """Get the menu manager for external access (e.g., by agent loop)."""
        return self._menu_manager

    def reset_menu(self) -> None:
        """Reset the menu to ROOT state."""
        self._menu_manager.reset()

    # =========================================================================
    # Guardrailed Todo System - Anti-hallucination patterns
    # See docs/guardrail-architecture.md for design rationale
    # =========================================================================

    # Valid status transitions (state machine)
    _TODO_VALID_TRANSITIONS: dict[str, list[str]] = {
        "pending": ["in_progress"],
        "in_progress": ["claimed"],
        "claimed": ["verified"],
        "verified": [],  # Terminal state
    }

    def _init_todo_state(self) -> None:
        """Initialize todo state if not already initialized."""
        if not hasattr(self, "_todos"):
            self._todos: dict[str, dict[str, Any]] = {}  # id -> todo
        if not hasattr(self, "_todo_audit_log"):
            self._todo_audit_log: list[dict[str, Any]] = []  # Immutable audit log

    def _log_todo_event(
        self,
        event_type: str,
        todo_id: str,
        before: dict[str, Any] | None = None,
        after: dict[str, Any] | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        """Log a todo state change to the immutable audit log."""
        self._init_todo_state()
        event = {
            "timestamp": datetime.now(UTC).isoformat(),
            "event_type": event_type,
            "todo_id": todo_id,
            "before": before,
            "after": after,
        }
        if extra:
            event["extra"] = extra
        self._todo_audit_log.append(event)

    def _format_todo_list(self, header: str) -> str:
        """Format the todo list for display."""
        self._init_todo_state()
        if not self._todos:
            return f"{header}\n  (no todos)"

        lines = [header]
        status_markers = {
            "pending": "[ ]",
            "in_progress": "[*]",
            "claimed": "[?]",  # Claimed but not verified
            "verified": "[x]",  # Verified complete
        }
        for todo_id, todo in self._todos.items():
            status = todo.get("status", "pending")
            content = todo.get("content", "")
            marker = status_markers.get(status, "[ ]")
            lines.append(f"  {marker} [{todo_id}] {content}")

            # Show acceptance criteria if present
            criteria = todo.get("acceptance_criteria", [])
            if criteria:
                lines.append(f"      Acceptance criteria: {len(criteria)} defined")

            # Show evidence if claimed
            if status in ("claimed", "verified"):
                evidence = todo.get("evidence", [])
                if evidence:
                    lines.append(f"      Evidence: {len(evidence)} items")

        return "\n".join(lines)

    def _todo_create(
        self,
        content: str,
        acceptance_criteria: list[dict[str, Any]] | None = None,
    ) -> str:
        """Create a single todo item with a stable ID.

        Args:
            content: Description of the task
            acceptance_criteria: Optional list of machine-verifiable criteria
                Each criterion: {"type": "command_exit_zero"|"file_exists"|..., "params": {...}}

        Returns:
            Confirmation with the assigned stable ID
        """
        self._init_todo_state()

        # Generate stable UUID
        todo_id = str(uuid.uuid4())[:8]

        # Create todo item
        todo = {
            "id": todo_id,
            "content": content,
            "status": "pending",
            "created_at": datetime.now(UTC).isoformat(),
            "acceptance_criteria": acceptance_criteria or [],
            "evidence": [],
        }

        # Store todo
        self._todos[todo_id] = todo

        # Log creation event
        self._log_todo_event(
            event_type="TODO_CREATE",
            todo_id=todo_id,
            after=todo.copy(),
        )

        result_lines = [
            f"Created todo [{todo_id}]: {content}",
            "Status: pending",
        ]
        if acceptance_criteria:
            result_lines.append(f"Acceptance criteria: {len(acceptance_criteria)} defined")

        return "\n".join(result_lines)

    def _todo_read(self) -> str:
        """List all todos with their stable IDs, status, and audit history."""
        self._init_todo_state()

        if not self._todos:
            return "No todos. Use TodoCreate to create individual todo items."

        output = self._format_todo_list("Current todo list:")

        # Add summary
        status_counts = {"pending": 0, "in_progress": 0, "claimed": 0, "verified": 0}
        for todo in self._todos.values():
            status = todo.get("status", "pending")
            if status in status_counts:
                status_counts[status] += 1

        output += f"\n\nSummary: {status_counts['pending']} pending, {status_counts['in_progress']} in_progress, {status_counts['claimed']} claimed, {status_counts['verified']} verified"
        output += f"\nAudit log entries: {len(self._todo_audit_log)}"

        return output

    def _todo_start(self, id: str) -> str:
        """Start working on a todo. Moves status from 'pending' to 'in_progress'.

        Args:
            id: The stable ID of the todo to start

        Returns:
            Confirmation of status change
        """
        self._init_todo_state()

        if id not in self._todos:
            raise ValueError(f"Todo '{id}' not found. Use TodoRead to see available todos.")

        todo = self._todos[id]
        current_status = todo.get("status", "pending")

        # Enforce state machine
        if current_status != "pending":
            raise ValueError(
                f"Cannot start todo '{id}': current status is '{current_status}', "
                f"but TodoStart only works on 'pending' todos. "
                f"Valid transitions: {self._TODO_VALID_TRANSITIONS.get(current_status, [])}"
            )

        # Capture before state
        before = todo.copy()

        # Update status
        todo["status"] = "in_progress"
        todo["started_at"] = datetime.now(UTC).isoformat()

        # Log state change
        self._log_todo_event(
            event_type="TODO_START",
            todo_id=id,
            before=before,
            after=todo.copy(),
        )

        return f"Started todo [{id}]: {todo['content']}\nStatus: pending -> in_progress"

    def _todo_claim(
        self,
        id: str,
        evidence: list[dict[str, Any]] | None = None,
    ) -> str:
        """Claim a todo is complete. Moves status from 'in_progress' to 'claimed'.

        This is an agent assertion that the work is done. Actual verification
        happens separately via TodoVerify which checks acceptance criteria.

        Args:
            id: The stable ID of the todo to claim
            evidence: Optional list of evidence supporting the claim
                Each item: {"type": "tool_call_id"|"file_path"|"command_output"|..., "data": ...}

        Returns:
            Confirmation of claim with next steps
        """
        self._init_todo_state()

        if id not in self._todos:
            raise ValueError(f"Todo '{id}' not found. Use TodoRead to see available todos.")

        todo = self._todos[id]
        current_status = todo.get("status", "pending")

        # Enforce state machine
        if current_status != "in_progress":
            raise ValueError(
                f"Cannot claim todo '{id}': current status is '{current_status}', "
                f"but TodoClaim only works on 'in_progress' todos. "
                f"Use TodoStart first to move from 'pending' to 'in_progress'."
            )

        # Capture before state
        before = todo.copy()

        # Update status and add evidence
        todo["status"] = "claimed"
        todo["claimed_at"] = datetime.now(UTC).isoformat()
        if evidence:
            todo["evidence"].extend(evidence)

        # Log state change
        self._log_todo_event(
            event_type="TODO_CLAIM",
            todo_id=id,
            before=before,
            after=todo.copy(),
            extra={"evidence_count": len(evidence) if evidence else 0},
        )

        result_lines = [
            f"Claimed todo [{id}]: {todo['content']}",
            "Status: in_progress -> claimed",
        ]
        if evidence:
            result_lines.append(f"Evidence provided: {len(evidence)} items")

        # Check if acceptance criteria exist
        criteria = todo.get("acceptance_criteria", [])
        if criteria:
            result_lines.append(f"\nThis todo has {len(criteria)} acceptance criteria.")
            result_lines.append("Use TodoVerify to check if criteria are met and move to 'verified' status.")
        else:
            result_lines.append("\nNo acceptance criteria defined - manual verification required.")

        return "\n".join(result_lines)

    def _todo_verify(self, id: str) -> str:
        """Verify a claimed todo by checking its acceptance criteria.

        This is a harness-level operation that checks machine-verifiable criteria.
        Only works on todos with status 'claimed'.

        Args:
            id: The stable ID of the todo to verify

        Returns:
            Verification result with details
        """
        self._init_todo_state()

        if id not in self._todos:
            raise ValueError(f"Todo '{id}' not found. Use TodoRead to see available todos.")

        todo = self._todos[id]
        current_status = todo.get("status", "pending")

        # Enforce state machine
        if current_status != "claimed":
            raise ValueError(
                f"Cannot verify todo '{id}': current status is '{current_status}', "
                f"but TodoVerify only works on 'claimed' todos. "
                f"Use TodoClaim first to move from 'in_progress' to 'claimed'."
            )

        criteria = todo.get("acceptance_criteria", [])

        # If no criteria, require manual verification
        if not criteria:
            return (
                f"Todo [{id}] has no acceptance criteria defined.\n"
                f"Manual verification required - this todo cannot be automatically verified.\n"
                f"Status remains: claimed"
            )

        # Check each criterion
        results: list[dict[str, Any]] = []
        all_passed = True

        for criterion in criteria:
            crit_type = criterion.get("type", "unknown")
            params = criterion.get("params", {})

            result = self._check_acceptance_criterion(crit_type, params)
            results.append({
                "type": crit_type,
                "params": params,
                "passed": result["passed"],
                "message": result["message"],
            })
            if not result["passed"]:
                all_passed = False

        # Capture before state
        before = todo.copy()

        if all_passed:
            # Move to verified
            todo["status"] = "verified"
            todo["verified_at"] = datetime.now(UTC).isoformat()
            todo["verification_results"] = results

            # Log state change
            self._log_todo_event(
                event_type="TODO_VERIFY",
                todo_id=id,
                before=before,
                after=todo.copy(),
                extra={"all_passed": True, "criteria_count": len(criteria)},
            )

            result_lines = [
                f"VERIFIED: Todo [{id}] passed all {len(criteria)} acceptance criteria!",
                "Status: claimed -> verified",
                "",
                "Criteria results:",
            ]
            for r in results:
                result_lines.append(f"  [PASS] {r['type']}: {r['message']}")

            return "\n".join(result_lines)
        else:
            # Log failed verification attempt (status unchanged)
            self._log_todo_event(
                event_type="TODO_VERIFY_FAILED",
                todo_id=id,
                before=before,
                after=todo.copy(),  # Unchanged
                extra={"all_passed": False, "criteria_count": len(criteria)},
            )

            result_lines = [
                f"VERIFICATION FAILED: Todo [{id}] did not pass all acceptance criteria.",
                "Status remains: claimed",
                "",
                "Criteria results:",
            ]
            for r in results:
                status = "[PASS]" if r["passed"] else "[FAIL]"
                result_lines.append(f"  {status} {r['type']}: {r['message']}")

            return "\n".join(result_lines)

    def _check_acceptance_criterion(
        self,
        crit_type: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """Check a single acceptance criterion.

        Supported types:
        - command_exit_zero: Run a command and check exit code is 0
        - file_exists: Check if a file exists
        - file_contains: Check if a file contains a string
        - pr_exists: Check if a PR exists (by number)

        Returns:
            {"passed": bool, "message": str}
        """
        if crit_type == "command_exit_zero":
            command = params.get("command", "")
            if not command:
                return {"passed": False, "message": "No command specified"}
            try:
                result = subprocess.run(
                    command,
                    shell=True,
                    capture_output=True,
                    timeout=30,
                )
                if result.returncode == 0:
                    return {"passed": True, "message": f"Command '{command}' exited with code 0"}
                else:
                    return {
                        "passed": False,
                        "message": f"Command '{command}' exited with code {result.returncode}",
                    }
            except subprocess.TimeoutExpired:
                return {"passed": False, "message": f"Command '{command}' timed out"}
            except Exception as e:
                return {"passed": False, "message": f"Command error: {e}"}

        elif crit_type == "file_exists":
            path = params.get("path", "")
            if not path:
                return {"passed": False, "message": "No path specified"}
            if os.path.exists(path):
                return {"passed": True, "message": f"File exists: {path}"}
            else:
                return {"passed": False, "message": f"File not found: {path}"}

        elif crit_type == "file_contains":
            path = params.get("path", "")
            text = params.get("text", "")
            if not path or not text:
                return {"passed": False, "message": "Missing path or text parameter"}
            try:
                with open(path) as f:
                    content = f.read()
                if text in content:
                    return {"passed": True, "message": "File contains expected text"}
                else:
                    return {"passed": False, "message": "File does not contain expected text"}
            except Exception as e:
                return {"passed": False, "message": f"Error reading file: {e}"}

        elif crit_type == "pr_exists":
            # Check PR existence using GitHub API
            pr_number = params.get("pr_number")
            repo = params.get("repo")
            if not pr_number:
                return {"passed": False, "message": "No pr_number specified"}
            if not repo:
                return {"passed": False, "message": "No repo specified (format: owner/repo)"}

            # Use GitHub API to verify PR exists
            import httpx
            token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
            if not token:
                return {"passed": False, "message": "GITHUB_TOKEN not set - cannot verify PR existence"}

            # Normalize repo format
            if repo.startswith("github.com/"):
                repo = repo[11:]

            try:
                with httpx.Client(timeout=10.0) as client:
                    response = client.get(
                        f"https://api.github.com/repos/{repo}/pulls/{pr_number}",
                        headers={
                            "Authorization": f"Bearer {token}",
                            "Accept": "application/vnd.github+json",
                        },
                    )
                    if response.status_code == 200:
                        pr_data = response.json()
                        state = pr_data.get("state", "unknown")
                        title = pr_data.get("title", "")[:50]
                        return {"passed": True, "message": f"PR #{pr_number} exists ({state}): {title}"}
                    elif response.status_code == 404:
                        return {"passed": False, "message": f"PR #{pr_number} not found in {repo}"}
                    else:
                        return {"passed": False, "message": f"GitHub API error: {response.status_code}"}
            except Exception as e:
                return {"passed": False, "message": f"Error checking PR: {e}"}

        else:
            return {"passed": False, "message": f"Unknown criterion type: {crit_type}"}

    def _request_tools(
        self,
        category: str | None = None,
        tool_names: list[str] | None = None,
        list_categories: bool = False,
    ) -> str:
        """Request additional tools to be enabled.

        Args:
            category: Enable all tools in a category (e.g., "git_local", "browser")
            tool_names: Enable specific tools by name
            list_categories: If True, list all available categories and their tools
        """
        if list_categories:
            categories = self.get_available_categories()
            lines = ["Available tool categories:"]
            for cat_name, tools in sorted(categories.items()):
                enabled = cat_name in [c.value for c in self._active_toolset._enabled_categories]
                status = "[enabled]" if enabled else "[available]"
                lines.append(f"\n{cat_name} {status}:")
                for tool in sorted(tools):
                    lines.append(f"  - {tool}")
            return "\n".join(lines)

        enabled_tools: list[str] = []

        if category:
            enabled_tools.extend(self.enable_category(category))

        if tool_names:
            enabled_tools.extend(self.enable_tools(tool_names))

        if not enabled_tools:
            if category:
                return f"Error: Unknown category '{category}'. Use list_categories=true to see available categories."
            return "Error: No tools specified. Provide 'category' or 'tool_names' parameter."

        # Get descriptions for newly enabled tools
        lines = [f"Enabled {len(enabled_tools)} tools:"]
        for name in enabled_tools:
            tool = self._tools.get(name)
            if tool:
                lines.append(f"  - {name}: {tool.schema.description}")

        return "\n".join(lines)

    def _message_user(
        self,
        message: str,
        block_on_user: bool = False,
        should_use_concise_message: bool = True,
        attachments: str | None = None,
        request_auth: bool = False,
        request_deploy: bool = False,
    ) -> str:
        """Send a message to the user.

        Args:
            message: The message content to send
            block_on_user: Whether to wait for user response before continuing
            should_use_concise_message: Whether to use a concise version of the message
            attachments: Comma-separated list of absolute file paths to attach
            request_auth: Whether to request authentication from the user
            request_deploy: Whether to request deployment approval from the user
        """
        # In local harness, we just print the message
        # In a real deployment, this would send to a UI/API
        output_parts = [f"\n[MESSAGE TO USER]\n{message}"]

        if attachments:
            attachment_list = [a.strip() for a in attachments.split(",")]
            valid_attachments = []
            for att in attachment_list:
                if os.path.exists(att):
                    valid_attachments.append(att)
                else:
                    output_parts.append(f"Warning: Attachment not found: {att}")
            if valid_attachments:
                output_parts.append(f"\nAttachments: {', '.join(valid_attachments)}")

        if request_auth:
            output_parts.append("\n[REQUESTING AUTHENTICATION]")

        if request_deploy:
            output_parts.append("\n[REQUESTING DEPLOYMENT APPROVAL]")

        print("\n".join(output_parts))

        status_parts = []
        if block_on_user:
            status_parts.append("blocking")
        if attachments:
            status_parts.append(f"{len(attachments.split(','))} attachment(s)")
        if request_auth:
            status_parts.append("auth requested")
        if request_deploy:
            status_parts.append("deploy approval requested")

        status = f" ({', '.join(status_parts)})" if status_parts else ""
        return f"Message sent{status}: {message[:100]}..."

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
        """Execute LSP operations using jedi for Python files.

        Args:
            command: LSP command (goto_definition, goto_references, hover_symbol, file_diagnostics)
            path: Absolute path to the file
            symbol: Symbol name to search for (required for most commands)
            line: Line number where the symbol occurs (1-indexed)

        Returns:
            LSP operation results
        """
        valid_commands = ["goto_definition", "goto_references", "hover_symbol", "file_diagnostics"]
        if command not in valid_commands:
            raise ValueError(f"Invalid LSP command: {command}. Valid: {valid_commands}")

        # Check if file exists
        if not os.path.exists(path):
            return f"Error: File not found: {path}"

        # Only support Python files with jedi
        if not path.endswith(".py"):
            return f"LSP {command} on {path}\n\n[Note: Only Python files are supported. For other languages, integrate with appropriate LSP server.]"

        try:
            import jedi
        except ImportError:
            return f"LSP {command} on {path}\n\n[Error: jedi not installed. Run: pip install jedi]"

        try:
            # Read file content
            with open(path, encoding="utf-8") as f:
                source = f.read()

            if command == "file_diagnostics":
                # Get syntax errors and warnings
                script = jedi.Script(source, path=path)
                errors = script.get_syntax_errors()

                if not errors:
                    return f"No diagnostics found in {path}"

                output_lines = [f"Diagnostics for {path}:", ""]
                for error in errors:
                    output_lines.append(f"  Line {error.line}: {error.get_message()}")

                return "\n".join(output_lines)

            # For other commands, we need symbol and line
            if not symbol or not line:
                return f"Error: {command} requires both 'symbol' and 'line' parameters"

            # Find the column position of the symbol on the line
            lines = source.split("\n")
            if line < 1 or line > len(lines):
                return f"Error: Line {line} is out of range (file has {len(lines)} lines)"

            target_line = lines[line - 1]
            col = target_line.find(symbol)
            if col == -1:
                return f"Error: Symbol '{symbol}' not found on line {line}"

            # Create jedi script and get completions at position
            script = jedi.Script(source, path=path)

            if command == "goto_definition":
                definitions = script.goto(line, col)
                if not definitions:
                    return f"No definition found for '{symbol}' at {path}:{line}"

                output_lines = [f"Definition(s) for '{symbol}':", ""]
                for defn in definitions:
                    module_path = defn.module_path or "built-in"
                    defn_line = defn.line or "?"
                    output_lines.append(f"  {module_path}:{defn_line}")
                    if defn.description:
                        output_lines.append(f"    {defn.description}")

                return "\n".join(output_lines)

            elif command == "goto_references":
                references = script.get_references(line, col)
                if not references:
                    return f"No references found for '{symbol}'"

                output_lines = [f"References for '{symbol}':", ""]
                for ref in references[:20]:  # Limit to 20 references
                    module_path = ref.module_path or path
                    ref_line = ref.line or "?"
                    output_lines.append(f"  {module_path}:{ref_line}")

                if len(references) > 20:
                    output_lines.append(f"\n  ... and {len(references) - 20} more references")

                return "\n".join(output_lines)

            elif command == "hover_symbol":
                # Get type info and documentation
                names = script.infer(line, col)
                if not names:
                    return f"No type information found for '{symbol}'"

                output_lines = [f"Type info for '{symbol}':", ""]
                for name in names:
                    output_lines.append(f"  Type: {name.type}")
                    if name.full_name:
                        output_lines.append(f"  Full name: {name.full_name}")
                    if name.description:
                        output_lines.append(f"  Description: {name.description}")
                    docstring = name.docstring()
                    if docstring:
                        # Truncate long docstrings
                        if len(docstring) > 500:
                            docstring = docstring[:500] + "..."
                        output_lines.append(f"\n  Documentation:\n  {docstring}")

                return "\n".join(output_lines)

            return f"Unknown command: {command}"

        except Exception as e:
            return f"LSP error: {e}"

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
        """Ask a smart friend for help with complex reasoning using Venice.ai LLM.

        Args:
            question: The question to ask for help with

        Returns:
            LLM response with reasoning assistance
        """
        import httpx

        # Get API key from environment
        api_key = os.environ.get("LLM_API_KEY") or os.environ.get("VENICE_API_KEY")
        if not api_key:
            return "Error: LLM_API_KEY or VENICE_API_KEY environment variable not set"

        # Use Venice.ai API with qwen3-next-80b model for reasoning
        model = os.environ.get("LLM_MODEL", "qwen3-next-80b")

        system_prompt = """You are a smart friend helping with complex reasoning and debugging.
You have expertise in software engineering, debugging, and problem-solving.
Provide clear, actionable suggestions. Be concise but thorough.
If you're unsure about something, say so and suggest how to find out."""

        try:
            with httpx.Client(timeout=120.0) as client:
                response = client.post(
                    "https://api.venice.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": question},
                        ],
                        "max_tokens": 2000,
                        "temperature": 0.7,
                    },
                )
                response.raise_for_status()
                data = response.json()

            # Extract response
            choices = data.get("choices", [])
            if not choices:
                return "Error: No response from LLM"

            content = choices[0].get("message", {}).get("content", "")
            if not content:
                return "Error: Empty response from LLM"

            return f"Smart friend response:\n\n{content}"

        except httpx.HTTPStatusError as e:
            return f"Venice API error: {e.response.status_code} - {e.response.text}"
        except httpx.RequestError as e:
            return f"Request error: {e}"
        except Exception as e:
            return f"Error asking smart friend: {e}"

    def _visual_checker(self, question: str) -> str:
        """Analyze visual content using a vision model.

        Args:
            question: The question about visual content, may include image paths

        Returns:
            Analysis of the visual content or configuration error

        Note: This tool uses Venice.ai's mistral-31-24b vision model by default.
        You can override with VISION_API_URL and VISION_MODEL environment variables.
        """
        import base64
        from pathlib import Path

        import httpx

        # Check if a custom vision API is configured, otherwise use Venice.ai
        vision_api_url = os.environ.get("VISION_API_URL")
        vision_model = os.environ.get("VISION_MODEL")
        api_key = os.environ.get("VISION_API_KEY")

        # Default to Venice.ai with mistral-31-24b (vision-capable model)
        if not vision_api_url:
            vision_api_url = "https://api.venice.ai/api/v1/chat/completions"
            vision_model = "mistral-31-24b"
            api_key = os.environ.get("LLM_API_KEY")

        if not api_key:
            return "Error: No API key configured. Set LLM_API_KEY for Venice.ai or VISION_API_KEY for custom vision API."

        # Extract image paths from the question (look for file paths)
        import re
        image_paths = re.findall(r'(/[\w/.-]+\.(?:png|jpg|jpeg|gif|webp))', question)

        messages = []
        user_content = []

        # Add text part
        user_content.append({"type": "text", "text": question})

        # Add image parts if paths found
        for img_path in image_paths:
            path = Path(img_path)
            if path.exists():
                with open(path, "rb") as f:
                    img_data = base64.b64encode(f.read()).decode()
                suffix = path.suffix.lower().lstrip(".")
                media_type = f"image/{suffix}" if suffix != "jpg" else "image/jpeg"
                user_content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:{media_type};base64,{img_data}"}
                })

        messages.append({"role": "user", "content": user_content})

        try:
            with httpx.Client(timeout=120.0) as client:
                response = client.post(
                    vision_api_url,
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": vision_model,
                        "messages": messages,
                        "max_tokens": 2000,
                    },
                )
                response.raise_for_status()
                data = response.json()

            choices = data.get("choices", [])
            if not choices:
                return "Error: No response from vision model"

            result = choices[0].get("message", {}).get("content", "")
            if not result:
                return "Error: Empty response from vision model"

            return f"Visual analysis:\n\n{result}"

        except httpx.HTTPStatusError as e:
            return f"Vision API error: {e.response.status_code} - {e.response.text}"
        except httpx.RequestError as e:
            return f"Request error: {e}"
        except Exception as e:
            return f"Error in visual analysis: {e}"

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

        Note: This implementation has limitations compared to Devin's version.
        Devin can automatically generate PR descriptions from diffs.
        This version can only append a timestamp marker to existing descriptions.
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

                new_body = current_body or ""
                if not force and "[Auto-updated]" in new_body:
                    return f"PR #{pull_number} description was already auto-updated. Use force=True to update again."

                # Limitation: We can only append a timestamp, not generate descriptions
                # Devin's version uses an internal service to generate descriptions from diffs
                import datetime
                timestamp = datetime.datetime.now(datetime.UTC).isoformat()
                if "[Auto-updated]" not in new_body:
                    new_body += f"\n\n[Auto-updated: {timestamp}]"
                    new_body += "\n\nNote: CompyMac cannot auto-generate PR descriptions from diffs."
                    new_body += "\nTo generate a description, manually review the diff and update."
                else:
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
URL: {pr_url}

Note: This tool can only append timestamps to PR descriptions.
Unlike Devin, CompyMac cannot automatically generate descriptions from diffs.
Please manually review and update the description if needed."""

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
        repo: str | None = None,
        app: str | None = None,
    ) -> str:
        """Deploy applications using GitHub Pages, Fly.io, or ngrok.

        Args:
            command: One of 'frontend', 'backend', 'logs', 'expose'
            dir: Directory containing the build files to deploy
            port: Port to expose (for 'expose' command)
            repo: GitHub repo in owner/repo format (for 'frontend' command)
            app: App name for Fly.io (for 'logs' command)

        Returns:
            Deployment result or error message
        """
        import base64
        import hashlib
        import shutil
        import subprocess

        import httpx

        valid_commands = ["frontend", "backend", "logs", "expose"]
        if command not in valid_commands:
            raise ValueError(f"Invalid deploy command: {command}. Valid: {valid_commands}")

        # Check for deployment configuration
        github_token = os.environ.get("GITHUB_TOKEN")
        fly_token = os.environ.get("FLY_API_TOKEN")
        ngrok_token = os.environ.get("NGROK_AUTHTOKEN")

        # Find flyctl binary
        flyctl_path = shutil.which("flyctl") or shutil.which("fly")
        if not flyctl_path:
            # Check common installation paths
            home_fly = os.path.expanduser("~/.fly/bin/flyctl")
            if os.path.exists(home_fly):
                flyctl_path = home_fly

        if command == "frontend":
            if not github_token:
                return """Error: Frontend deployment not configured.

To enable frontend deployment to GitHub Pages, set the GITHUB_TOKEN environment variable.

Steps to configure:
1. Create a GitHub personal access token at https://github.com/settings/tokens
2. Grant 'repo' scope for full repository access
3. Set GITHUB_TOKEN=<your-token> in your environment"""

            if not repo:
                return "Error: 'repo' parameter required for frontend deployment. Specify the target repo in owner/repo format."

            if not dir:
                return "Error: 'dir' parameter required for frontend deployment. Specify the directory containing your build files."

            if not os.path.isdir(dir):
                return f"Error: Directory not found: {dir}"

            # Parse repo
            if "/" not in repo:
                return f"Error: Invalid repo format '{repo}'. Use owner/repo format."
            owner, repo_name = repo.split("/", 1)

            try:
                # Collect all files from the build directory
                files_to_upload = []
                for root, dirs, files in os.walk(dir):
                    # Skip hidden directories
                    dirs[:] = [d for d in dirs if not d.startswith('.')]
                    for file in files:
                        if file.startswith('.'):
                            continue
                        file_path = os.path.join(root, file)
                        rel_path = os.path.relpath(file_path, dir)
                        with open(file_path, 'rb') as f:
                            content = f.read()
                        files_to_upload.append({
                            'path': rel_path,
                            'content': base64.b64encode(content).decode('utf-8'),
                            'sha': hashlib.sha1(f"blob {len(content)}\0".encode() + content).hexdigest(),
                        })

                if not files_to_upload:
                    return f"Error: No files found in directory: {dir}"

                # Create blobs and tree using GitHub API
                headers = {
                    "Authorization": f"token {github_token}",
                    "Accept": "application/vnd.github.v3+json",
                }

                # Get the current gh-pages branch ref (or create it)
                ref_url = f"https://api.github.com/repos/{owner}/{repo_name}/git/ref/heads/gh-pages"
                ref_response = httpx.get(ref_url, headers=headers, timeout=30)

                parent_sha = None
                if ref_response.status_code == 200:
                    parent_sha = ref_response.json()["object"]["sha"]

                # Create blobs for each file
                tree_items = []
                for file_info in files_to_upload:
                    blob_url = f"https://api.github.com/repos/{owner}/{repo_name}/git/blobs"
                    blob_response = httpx.post(
                        blob_url,
                        headers=headers,
                        json={"content": file_info['content'], "encoding": "base64"},
                        timeout=60,
                    )
                    if blob_response.status_code not in (200, 201):
                        return f"Error creating blob for {file_info['path']}: {blob_response.text}"

                    blob_sha = blob_response.json()["sha"]
                    tree_items.append({
                        "path": file_info['path'],
                        "mode": "100644",
                        "type": "blob",
                        "sha": blob_sha,
                    })

                # Create tree
                tree_url = f"https://api.github.com/repos/{owner}/{repo_name}/git/trees"
                tree_response = httpx.post(
                    tree_url,
                    headers=headers,
                    json={"tree": tree_items},
                    timeout=60,
                )
                if tree_response.status_code not in (200, 201):
                    return f"Error creating tree: {tree_response.text}"

                tree_sha = tree_response.json()["sha"]

                # Create commit
                commit_url = f"https://api.github.com/repos/{owner}/{repo_name}/git/commits"
                commit_data = {
                    "message": "Deploy to GitHub Pages via CompyMac",
                    "tree": tree_sha,
                }
                if parent_sha:
                    commit_data["parents"] = [parent_sha]

                commit_response = httpx.post(
                    commit_url,
                    headers=headers,
                    json=commit_data,
                    timeout=60,
                )
                if commit_response.status_code not in (200, 201):
                    return f"Error creating commit: {commit_response.text}"

                commit_sha = commit_response.json()["sha"]

                # Update or create gh-pages branch ref
                if parent_sha:
                    # Update existing ref
                    update_response = httpx.patch(
                        ref_url,
                        headers=headers,
                        json={"sha": commit_sha, "force": True},
                        timeout=30,
                    )
                    if update_response.status_code != 200:
                        return f"Error updating gh-pages ref: {update_response.text}"
                else:
                    # Create new ref
                    create_ref_url = f"https://api.github.com/repos/{owner}/{repo_name}/git/refs"
                    create_response = httpx.post(
                        create_ref_url,
                        headers=headers,
                        json={"ref": "refs/heads/gh-pages", "sha": commit_sha},
                        timeout=30,
                    )
                    if create_response.status_code not in (200, 201):
                        return f"Error creating gh-pages ref: {create_response.text}"

                # Enable GitHub Pages if not already enabled
                pages_url = f"https://api.github.com/repos/{owner}/{repo_name}/pages"
                pages_response = httpx.get(pages_url, headers=headers, timeout=30)

                if pages_response.status_code == 404:
                    # Enable Pages
                    enable_response = httpx.post(
                        pages_url,
                        headers=headers,
                        json={"source": {"branch": "gh-pages", "path": "/"}},
                        timeout=30,
                    )
                    if enable_response.status_code not in (200, 201):
                        return f"Deployed to gh-pages branch but failed to enable Pages: {enable_response.text}\n\nManually enable Pages at https://github.com/{owner}/{repo_name}/settings/pages"

                pages_url_final = f"https://{owner}.github.io/{repo_name}/"
                return f"Deployment successful!\n\nFiles deployed: {len(files_to_upload)}\nCommit: {commit_sha[:7]}\n\nSite URL: {pages_url_final}\n\nNote: It may take a few minutes for changes to appear."

            except httpx.HTTPStatusError as e:
                return f"GitHub API error: {e.response.status_code} - {e.response.text}"
            except httpx.RequestError as e:
                return f"Request error: {e}"
            except Exception as e:
                return f"Error during deployment: {e}"

        elif command == "backend":
            if not fly_token:
                return """Error: Backend deployment not configured.

To enable backend deployment to Fly.io, set the FLY_API_TOKEN environment variable.

Steps to configure:
1. Install flyctl: curl -L https://fly.io/install.sh | sh
2. Login: flyctl auth login
3. Get token: flyctl auth token
4. Set FLY_API_TOKEN=<your-token> in your environment

Alternative: You can manually deploy by running:
  flyctl launch && flyctl deploy"""

            if not flyctl_path:
                return """Error: flyctl not found.

Install flyctl to enable Fly.io deployment:
  curl -L https://fly.io/install.sh | sh

Then add to PATH:
  export PATH="$HOME/.fly/bin:$PATH"
"""

            if not dir:
                return "Error: 'dir' parameter required for backend deployment. Specify the directory containing your FastAPI app."

            if not os.path.isdir(dir):
                return f"Error: Directory not found: {dir}"

            # Check for fly.toml or create one
            fly_toml = os.path.join(dir, "fly.toml")
            has_fly_toml = os.path.exists(fly_toml)

            env = os.environ.copy()
            env["FLY_API_TOKEN"] = fly_token

            try:
                if not has_fly_toml:
                    # Launch new app (creates fly.toml)
                    app_name = f"compymac-{int(time.time())}"
                    launch_cmd = [
                        flyctl_path, "launch",
                        "--name", app_name,
                        "--no-deploy",
                        "--yes",
                        "--region", "iad",
                    ]
                    result = subprocess.run(
                        launch_cmd,
                        cwd=dir,
                        env=env,
                        capture_output=True,
                        text=True,
                        timeout=120,
                    )
                    if result.returncode != 0:
                        return f"Error launching app: {result.stderr or result.stdout}"

                # Deploy the app
                deploy_cmd = [flyctl_path, "deploy", "--yes"]
                result = subprocess.run(
                    deploy_cmd,
                    cwd=dir,
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=600,  # 10 minute timeout for deploy
                )

                if result.returncode != 0:
                    return f"Deployment failed: {result.stderr or result.stdout}"

                # Get the app URL
                status_cmd = [flyctl_path, "status", "--json"]
                status_result = subprocess.run(
                    status_cmd,
                    cwd=dir,
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )

                app_url = None
                if status_result.returncode == 0:
                    try:
                        import json
                        status_data = json.loads(status_result.stdout)
                        app_name = status_data.get("Name", "")
                        if app_name:
                            app_url = f"https://{app_name}.fly.dev"
                    except (json.JSONDecodeError, KeyError):
                        pass

                output = f"Deployment successful!\n\n{result.stdout}"
                if app_url:
                    output += f"\n\nApp URL: {app_url}"
                return output

            except subprocess.TimeoutExpired:
                return "Error: Deployment timed out after 10 minutes"
            except Exception as e:
                return f"Error during deployment: {e}"

        elif command == "logs":
            if not fly_token:
                return """Error: Cannot fetch logs - deployment not configured.

Set FLY_API_TOKEN to enable log fetching from Fly.io deployments."""

            if not flyctl_path:
                return """Error: flyctl not found.

Install flyctl to fetch logs:
  curl -L https://fly.io/install.sh | sh"""

            env = os.environ.copy()
            env["FLY_API_TOKEN"] = fly_token

            try:
                # If dir is provided, use it as working directory (to find fly.toml)
                cwd = dir if dir and os.path.isdir(dir) else None

                # Build logs command with optional app name
                logs_cmd = [flyctl_path, "logs", "--no-tail"]
                if app:
                    logs_cmd.extend(["-a", app])

                result = subprocess.run(
                    logs_cmd,
                    cwd=cwd,
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=60,  # 60 second timeout for logs
                )

                if result.returncode != 0:
                    # Try to list apps if no fly.toml found
                    if "Could not find" in result.stderr or "no app" in result.stderr.lower() or "missing an app" in result.stderr.lower():
                        list_cmd = [flyctl_path, "apps", "list"]
                        list_result = subprocess.run(
                            list_cmd,
                            env=env,
                            capture_output=True,
                            text=True,
                            timeout=30,
                        )
                        return f"No app specified. Available apps:\n{list_result.stdout}\n\nUse 'app' parameter to specify app name, or 'dir' to specify app directory with fly.toml"

                    return f"Error fetching logs: {result.stderr or result.stdout}"

                app_name = app or "current app"
                return f"Recent logs for {app_name}:\n\n{result.stdout}"

            except subprocess.TimeoutExpired:
                return "Error: Log fetch timed out"
            except Exception as e:
                return f"Error fetching logs: {e}"

        else:  # expose
            if not ngrok_token:
                return f"""Error: Port exposure not configured.

To expose local port {port or 'unknown'} to the internet, set NGROK_AUTHTOKEN.

Steps to configure:
1. Create an ngrok account at https://ngrok.com
2. Get your authtoken from https://dashboard.ngrok.com/get-started/your-authtoken
3. Set NGROK_AUTHTOKEN=<your-token> in your environment

Alternative: You can manually expose by running:
  ngrok http {port or 3000}"""
            # ngrok integration requires the pyngrok library
            try:
                from pyngrok import ngrok as pyngrok_client

                # Start tunnel
                tunnel = pyngrok_client.connect(port, "http")
                public_url = tunnel.public_url

                return f"""Port {port} exposed to the internet.

Public URL: {public_url}

This tunnel will remain active until you kill the process or call recording_stop.
Share this URL with users to let them access your local server."""
            except ImportError:
                return """Error: pyngrok library not installed.

To enable port exposure, install pyngrok:
  pip install pyngrok

Then set NGROK_AUTHTOKEN and try again."""
            except Exception as e:
                return f"Error creating ngrok tunnel: {e}"

    def _recording_start(self) -> str:
        """Start a new screen recording using ffmpeg.

        Records the screen to a temporary video file. Only one recording
        can be active at a time.

        Returns:
            Confirmation message or error
        """
        import shutil
        import subprocess
        import tempfile

        if not hasattr(self, "_recording_active"):
            self._recording_active = False
            self._recording_process = None
            self._recording_path = None

        if self._recording_active:
            return "Error: Recording already in progress"

        # Check if ffmpeg is available
        if not shutil.which("ffmpeg"):
            return "Error: ffmpeg not found. Install ffmpeg to enable screen recording."

        # Create temporary file for recording
        temp_dir = tempfile.gettempdir()
        timestamp = int(time.time())
        self._recording_path = os.path.join(temp_dir, f"recording_{timestamp}.mp4")

        # Determine the display to record
        display = os.environ.get("DISPLAY", ":0")

        try:
            # Start ffmpeg recording in background
            # Using x11grab for Linux, would need different input for macOS/Windows
            cmd = [
                "ffmpeg",
                "-y",  # Overwrite output file
                "-f", "x11grab",
                "-framerate", "10",  # Lower framerate for smaller files
                "-i", display,
                "-c:v", "libx264",
                "-preset", "ultrafast",
                "-crf", "28",  # Lower quality for smaller files
                self._recording_path,
            ]

            self._recording_process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.PIPE,
            )

            self._recording_active = True
            return f"Started screen recording to {self._recording_path}"

        except Exception as e:
            self._recording_active = False
            self._recording_process = None
            self._recording_path = None
            return f"Error starting recording: {e}"

    def _recording_stop(self) -> str:
        """Stop the current recording and return the video path.

        Returns:
            Path to the recorded video file or error message
        """
        if not hasattr(self, "_recording_active"):
            self._recording_active = False
            self._recording_process = None
            self._recording_path = None

        if not self._recording_active:
            return "Error: No recording in progress"

        if self._recording_process is None:
            self._recording_active = False
            return "Error: Recording process not found"

        try:
            # Send 'q' to ffmpeg to stop recording gracefully
            self._recording_process.stdin.write(b"q")
            self._recording_process.stdin.flush()

            # Wait for process to finish (with timeout)
            try:
                self._recording_process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self._recording_process.kill()
                self._recording_process.wait()

            video_path = self._recording_path

            # Reset state
            self._recording_active = False
            self._recording_process = None
            self._recording_path = None

            # Check if file was created
            if video_path and os.path.exists(video_path):
                file_size = os.path.getsize(video_path)
                return f"Stopped screen recording\nVideo saved to: {video_path}\nFile size: {file_size} bytes"
            else:
                return f"Recording stopped but video file not found at {video_path}"

        except Exception as e:
            self._recording_active = False
            self._recording_process = None
            self._recording_path = None
            return f"Error stopping recording: {e}"

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

        Uses the official MCP Python SDK to connect to configured servers.
        Servers are spawned on-demand and cached for the session.
        """
        import asyncio

        valid_commands = ["list_servers", "list_tools", "call_tool", "read_resource"]
        if command not in valid_commands:
            raise ValueError(f"Invalid MCP command: {command}. Valid: {valid_commands}")

        # Load MCP configuration
        config = self._load_mcp_config()
        if config is None:
            return """Error: MCP (Model Context Protocol) not configured.

No MCP servers are configured. To enable MCP integrations:

Option 1: Set MCP_CONFIG_PATH to a JSON config file:
  {
    "servers": {
      "slack": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-slack"],
        "env": {"SLACK_BOT_TOKEN": "xoxb-..."}
      },
      "github": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-github"],
        "env": {"GITHUB_PERSONAL_ACCESS_TOKEN": "ghp_..."}
      }
    }
  }

Option 2: Set MCP_SERVERS as a JSON string with the same format.

For more information on MCP:
- Specification: https://modelcontextprotocol.io
- Server examples: https://github.com/modelcontextprotocol/servers

Once configured, you can:
- list_servers: See available MCP servers
- list_tools: See tools/resources on a server
- call_tool: Execute a tool on a server
- read_resource: Read a resource from a server"""

        servers = config.get("servers", {})
        if not servers:
            return "Error: MCP configuration found but no servers defined."

        # Handle list_servers command
        if command == "list_servers":
            server_list = []
            for name, cfg in servers.items():
                cmd = cfg.get("command", "unknown")
                args = cfg.get("args", [])
                server_list.append(f"- {name}: {cmd} {' '.join(args)}")
            return "Available MCP servers:\n" + "\n".join(server_list)

        # All other commands require a server name
        if not server:
            return f"Error: 'server' parameter required for '{command}' command."

        if server not in servers:
            available = ", ".join(servers.keys())
            return f"Error: Unknown server '{server}'. Available: {available}"

        server_config = servers[server]

        # Run the async MCP operation
        try:
            result = asyncio.run(
                self._mcp_async_operation(command, server, server_config, tool_name, tool_args, resource_uri)
            )
            return result
        except Exception as e:
            return f"Error executing MCP {command}: {e}"

    def _load_mcp_config(self) -> dict[str, Any] | None:
        """Load MCP configuration from environment."""
        mcp_config_path = os.environ.get("MCP_CONFIG_PATH")
        mcp_servers_json = os.environ.get("MCP_SERVERS")

        if mcp_config_path:
            try:
                with open(mcp_config_path) as f:
                    return json.load(f)
            except Exception as e:
                return {"error": f"Failed to load MCP config from {mcp_config_path}: {e}"}

        if mcp_servers_json:
            try:
                return json.loads(mcp_servers_json)
            except json.JSONDecodeError as e:
                return {"error": f"Failed to parse MCP_SERVERS JSON: {e}"}

        return None

    async def _mcp_async_operation(
        self,
        command: str,
        server_name: str,
        server_config: dict[str, Any],
        tool_name: str | None,
        tool_args: str | None,
        resource_uri: str | None,
    ) -> str:
        """Execute an async MCP operation."""
        from contextlib import AsyncExitStack

        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        # Build server parameters
        cmd = server_config.get("command", "npx")
        args = server_config.get("args", [])
        env = server_config.get("env", {})

        # Merge with current environment
        full_env = {**os.environ, **env}

        server_params = StdioServerParameters(
            command=cmd,
            args=args,
            env=full_env,
        )

        async with AsyncExitStack() as stack:
            # Connect to the server
            try:
                stdio_transport = await stack.enter_async_context(stdio_client(server_params))
                stdio, write = stdio_transport
                session = await stack.enter_async_context(ClientSession(stdio, write))
                await session.initialize()
            except Exception as e:
                return f"Error connecting to MCP server '{server_name}': {e}"

            # Execute the requested command
            if command == "list_tools":
                try:
                    response = await session.list_tools()
                    tools = response.tools
                    if not tools:
                        return f"No tools available on server '{server_name}'."

                    tool_list = []
                    for tool in tools:
                        desc = tool.description or "No description"
                        # Truncate long descriptions
                        if len(desc) > 100:
                            desc = desc[:97] + "..."
                        tool_list.append(f"- {tool.name}: {desc}")

                    return f"Tools on '{server_name}':\n" + "\n".join(tool_list)
                except Exception as e:
                    return f"Error listing tools on '{server_name}': {e}"

            elif command == "call_tool":
                if not tool_name:
                    return "Error: 'tool_name' parameter required for 'call_tool' command."

                # Parse tool_args from JSON string
                parsed_args: dict[str, Any] = {}
                if tool_args:
                    try:
                        parsed_args = json.loads(tool_args)
                        if not isinstance(parsed_args, dict):
                            return f"Error: tool_args must be a JSON object, got {type(parsed_args).__name__}"
                    except json.JSONDecodeError as e:
                        return f"Error parsing tool_args JSON: {e}"

                try:
                    result = await session.call_tool(tool_name, parsed_args)
                    # Format the result content
                    content_parts = []
                    for content in result.content:
                        if hasattr(content, "text"):
                            content_parts.append(content.text)
                        elif hasattr(content, "data"):
                            content_parts.append(f"[Binary data: {len(content.data)} bytes]")
                        else:
                            content_parts.append(str(content))

                    return "\n".join(content_parts) if content_parts else "Tool executed successfully (no output)"
                except Exception as e:
                    return f"Error calling tool '{tool_name}' on '{server_name}': {e}"

            elif command == "read_resource":
                if not resource_uri:
                    return "Error: 'resource_uri' parameter required for 'read_resource' command."

                try:
                    result = await session.read_resource(resource_uri)
                    # Format the resource content
                    content_parts = []
                    for content in result.contents:
                        if hasattr(content, "text"):
                            content_parts.append(content.text)
                        elif hasattr(content, "blob"):
                            content_parts.append(f"[Binary blob: {len(content.blob)} bytes]")
                        else:
                            content_parts.append(str(content))

                    return "\n".join(content_parts) if content_parts else "Resource read successfully (empty)"
                except Exception as e:
                    return f"Error reading resource '{resource_uri}' from '{server_name}': {e}"

            else:
                return f"Unknown command: {command}"

    def _git_status(self, repo_path: str) -> str:
        """Get the status of a git repository."""
        import git

        try:
            repo = git.Repo(repo_path)
            return repo.git.status()
        except git.InvalidGitRepositoryError:
            return f"Error: '{repo_path}' is not a valid git repository"
        except git.NoSuchPathError:
            return f"Error: Path '{repo_path}' does not exist"
        except Exception as e:
            return f"Error getting git status: {e}"

    def _git_diff_unstaged(self, repo_path: str, context_lines: int = 3) -> str:
        """Get diff of unstaged changes."""
        import git

        try:
            repo = git.Repo(repo_path)
            diff = repo.git.diff(f"--unified={context_lines}")
            return diff if diff else "No unstaged changes"
        except git.InvalidGitRepositoryError:
            return f"Error: '{repo_path}' is not a valid git repository"
        except Exception as e:
            return f"Error getting unstaged diff: {e}"

    def _git_diff_staged(self, repo_path: str, context_lines: int = 3) -> str:
        """Get diff of staged changes."""
        import git

        try:
            repo = git.Repo(repo_path)
            diff = repo.git.diff(f"--unified={context_lines}", "--cached")
            return diff if diff else "No staged changes"
        except git.InvalidGitRepositoryError:
            return f"Error: '{repo_path}' is not a valid git repository"
        except Exception as e:
            return f"Error getting staged diff: {e}"

    def _git_diff(self, repo_path: str, target: str, context_lines: int = 3) -> str:
        """Get diff between current state and a target."""
        import git
        from git.exc import BadName

        try:
            if target.startswith("-"):
                return f"Error: Invalid target '{target}' - cannot start with '-'"
            repo = git.Repo(repo_path)
            repo.rev_parse(target)
            diff = repo.git.diff(f"--unified={context_lines}", target)
            return diff if diff else f"No differences from {target}"
        except git.InvalidGitRepositoryError:
            return f"Error: '{repo_path}' is not a valid git repository"
        except BadName:
            return f"Error: Invalid git reference '{target}'"
        except Exception as e:
            return f"Error getting diff: {e}"

    def _git_commit(self, repo_path: str, message: str) -> str:
        """Commit staged changes."""
        import git

        try:
            repo = git.Repo(repo_path)
            if not repo.index.diff("HEAD") and not repo.untracked_files:
                staged = list(repo.index.diff("HEAD", staged=True))
                if not staged:
                    return "Error: No changes staged for commit"
            commit = repo.index.commit(message)
            return f"Committed: {commit.hexsha[:8]} - {message}"
        except git.InvalidGitRepositoryError:
            return f"Error: '{repo_path}' is not a valid git repository"
        except Exception as e:
            return f"Error committing: {e}"

    def _git_add(self, repo_path: str, files: list[str]) -> str:
        """Stage files for commit."""
        import git

        try:
            repo = git.Repo(repo_path)
            repo.index.add(files)
            return f"Staged {len(files)} file(s): {', '.join(files)}"
        except git.InvalidGitRepositoryError:
            return f"Error: '{repo_path}' is not a valid git repository"
        except Exception as e:
            return f"Error staging files: {e}"

    def _git_reset(self, repo_path: str) -> str:
        """Unstage all staged changes."""
        import git

        try:
            repo = git.Repo(repo_path)
            repo.index.reset()
            return "Unstaged all changes"
        except git.InvalidGitRepositoryError:
            return f"Error: '{repo_path}' is not a valid git repository"
        except Exception as e:
            return f"Error resetting: {e}"

    def _git_log(self, repo_path: str, max_count: int = 10) -> str:
        """Get commit history."""
        import git

        try:
            repo = git.Repo(repo_path)
            commits = list(repo.iter_commits(max_count=max_count))
            if not commits:
                return "No commits found"
            log_lines = []
            for c in commits:
                date = c.committed_datetime.strftime("%Y-%m-%d %H:%M")
                msg = c.message.split("\n")[0][:60]
                log_lines.append(f"{c.hexsha[:8]} {date} {msg}")
            return "\n".join(log_lines)
        except git.InvalidGitRepositoryError:
            return f"Error: '{repo_path}' is not a valid git repository"
        except Exception as e:
            return f"Error getting log: {e}"

    def _git_create_branch(
        self, repo_path: str, branch_name: str, base_branch: str | None = None
    ) -> str:
        """Create a new branch."""
        import git

        try:
            if branch_name.startswith("-"):
                return f"Error: Invalid branch name '{branch_name}' - cannot start with '-'"
            repo = git.Repo(repo_path)
            if base_branch:
                if base_branch.startswith("-"):
                    return f"Error: Invalid base branch '{base_branch}' - cannot start with '-'"
                base = repo.refs[base_branch]
                new_branch = repo.create_head(branch_name, base)
            else:
                new_branch = repo.create_head(branch_name)
            return f"Created branch '{new_branch.name}'"
        except git.InvalidGitRepositoryError:
            return f"Error: '{repo_path}' is not a valid git repository"
        except Exception as e:
            return f"Error creating branch: {e}"

    def _git_checkout(self, repo_path: str, branch_name: str) -> str:
        """Switch to a branch."""
        import git

        try:
            if branch_name.startswith("-"):
                return f"Error: Invalid branch name '{branch_name}' - cannot start with '-'"
            repo = git.Repo(repo_path)
            repo.git.checkout(branch_name)
            return f"Switched to branch '{branch_name}'"
        except git.InvalidGitRepositoryError:
            return f"Error: '{repo_path}' is not a valid git repository"
        except Exception as e:
            return f"Error checking out branch: {e}"

    def _git_show(self, repo_path: str, revision: str) -> str:
        """Show details of a commit."""
        import git

        try:
            if revision.startswith("-"):
                return f"Error: Invalid revision '{revision}' - cannot start with '-'"
            repo = git.Repo(repo_path)
            return repo.git.show(revision)
        except git.InvalidGitRepositoryError:
            return f"Error: '{repo_path}' is not a valid git repository"
        except Exception as e:
            return f"Error showing revision: {e}"

    def _git_branch_list(self, repo_path: str, show_remote: bool = False) -> str:
        """List branches in a repository."""
        import git

        try:
            repo = git.Repo(repo_path)
            branches = []
            for branch in repo.heads:
                prefix = "* " if branch == repo.active_branch else "  "
                branches.append(f"{prefix}{branch.name}")
            if show_remote:
                for ref in repo.remotes.origin.refs:
                    branches.append(f"  remotes/{ref.name}")
            return "\n".join(branches) if branches else "No branches found"
        except git.InvalidGitRepositoryError:
            return f"Error: '{repo_path}' is not a valid git repository"
        except Exception as e:
            return f"Error listing branches: {e}"

    def _fs_read_file(self, path: str) -> str:
        """Read contents of a file."""
        from pathlib import Path

        try:
            p = Path(path)
            if not p.exists():
                return f"Error: File '{path}' does not exist"
            if not p.is_file():
                return f"Error: '{path}' is not a file"
            content = p.read_text(encoding="utf-8")
            return content
        except PermissionError:
            return f"Error: Permission denied reading '{path}'"
        except UnicodeDecodeError:
            return f"Error: File '{path}' is not a valid UTF-8 text file"
        except Exception as e:
            return f"Error reading file: {e}"

    def _fs_write_file(self, path: str, content: str) -> str:
        """Write contents to a file."""
        from pathlib import Path

        try:
            p = Path(path)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
            return f"Wrote {len(content)} bytes to '{path}'"
        except PermissionError:
            return f"Error: Permission denied writing to '{path}'"
        except Exception as e:
            return f"Error writing file: {e}"

    def _fs_list_directory(self, path: str) -> str:
        """List contents of a directory."""
        from pathlib import Path

        try:
            p = Path(path)
            if not p.exists():
                return f"Error: Directory '{path}' does not exist"
            if not p.is_dir():
                return f"Error: '{path}' is not a directory"
            entries = []
            for entry in sorted(p.iterdir()):
                entry_type = "d" if entry.is_dir() else "f"
                entries.append(f"[{entry_type}] {entry.name}")
            return "\n".join(entries) if entries else "Directory is empty"
        except PermissionError:
            return f"Error: Permission denied accessing '{path}'"
        except Exception as e:
            return f"Error listing directory: {e}"

    def _fs_create_directory(self, path: str) -> str:
        """Create a directory."""
        from pathlib import Path

        try:
            p = Path(path)
            p.mkdir(parents=True, exist_ok=True)
            return f"Created directory '{path}'"
        except PermissionError:
            return f"Error: Permission denied creating '{path}'"
        except Exception as e:
            return f"Error creating directory: {e}"

    def _fs_delete(self, path: str) -> str:
        """Delete a file or empty directory."""
        from pathlib import Path

        try:
            p = Path(path)
            if not p.exists():
                return f"Error: '{path}' does not exist"
            if p.is_file():
                p.unlink()
                return f"Deleted file '{path}'"
            elif p.is_dir():
                p.rmdir()
                return f"Deleted directory '{path}'"
            else:
                return f"Error: '{path}' is not a file or directory"
        except PermissionError:
            return f"Error: Permission denied deleting '{path}'"
        except OSError as e:
            if "not empty" in str(e).lower() or "directory not empty" in str(e).lower():
                return f"Error: Directory '{path}' is not empty"
            return f"Error deleting: {e}"
        except Exception as e:
            return f"Error deleting: {e}"

    def _fs_move(self, source: str, destination: str) -> str:
        """Move or rename a file or directory."""
        import shutil
        from pathlib import Path

        try:
            src = Path(source)
            dst = Path(destination)
            if not src.exists():
                return f"Error: Source '{source}' does not exist"
            shutil.move(str(src), str(dst))
            return f"Moved '{source}' to '{destination}'"
        except PermissionError:
            return "Error: Permission denied"
        except Exception as e:
            return f"Error moving: {e}"

    def _fs_file_info(self, path: str) -> str:
        """Get metadata about a file or directory."""
        import stat
        from datetime import datetime
        from pathlib import Path

        try:
            p = Path(path)
            if not p.exists():
                return f"Error: '{path}' does not exist"
            st = p.stat()
            file_type = "directory" if p.is_dir() else "file"
            size = st.st_size
            modified = datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            created = datetime.fromtimestamp(st.st_ctime).strftime("%Y-%m-%d %H:%M:%S")
            mode = stat.filemode(st.st_mode)
            return f"""Path: {path}
Type: {file_type}
Size: {size} bytes
Modified: {modified}
Created: {created}
Permissions: {mode}"""
        except PermissionError:
            return f"Error: Permission denied accessing '{path}'"
        except Exception as e:
            return f"Error getting file info: {e}"

    def register_tool(
        self,
        name: str,
        schema: ToolSchema,
        handler: Callable[..., str],
        category: ToolCategory = ToolCategory.CORE,
        is_core: bool = False,
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
            category=category,
            is_core=is_core,
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

        # Safety policy enforcement
        if self._policy_engine.enabled:
            policy_results = self._policy_engine.evaluate(tool_call)

            # Check for blocking violations
            if self._policy_engine.should_block(policy_results):
                blocking = self._policy_engine.get_blocking_violations(policy_results)
                violation_msg = "; ".join(v.violation_message for v in blocking)

                self._event_log.log_event(
                    EventType.ERROR,
                    call_id,
                    error=f"Policy violation: {violation_msg}",
                    policy_blocked=True,
                )

                return ToolResult(
                    tool_call_id=call_id,
                    content=f"[POLICY BLOCKED] {violation_msg}",
                    success=False,
                    error=f"Safety policy violation: {violation_msg}",
                )

            # Log warnings but allow execution
            warnings = self._policy_engine.get_warnings(policy_results)
            if warnings:
                warning_msg = "; ".join(w.violation_message for w in warnings)
                self._event_log.log_event(
                    EventType.TOOL_CALL_RECEIVED,
                    call_id,
                    policy_warnings=warning_msg,
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

        # Verify tool execution using contract-driven verification
        verification_result: VerificationResult | None = None
        verification_info = ""
        if self._verification_engine.enabled:
            tool_result_for_verification = ToolResult(
                tool_call_id=call_id,
                content=result,
                success=True,
            )
            verification_result = self._verification_engine.verify(
                tool_call, tool_result_for_verification
            )
            self._last_verification_result = verification_result

            if verification_result:
                self._event_log.log_event(
                    EventType.TOOL_RESULT_RETURNED,
                    call_id,
                    verification_passed=verification_result.all_checks_passed,
                    verification_confidence=verification_result.confidence_score,
                )

                if not verification_result.all_checks_passed:
                    verification_info = f"\n\n[VERIFICATION WARNING]\n{verification_result.format_for_agent()}"

        # End trace span with success if tracing
        output_artifact_hash: str | None = None
        if trace_ctx and span_id:
            from compymac.trace_store import SpanStatus

            # Store output as artifact (include verification info if present)
            output_content = wrapped + verification_info
            output_artifact = trace_ctx.store_artifact(
                data=output_content.encode(),
                artifact_type="tool_output",
                content_type="text/xml",
                metadata={
                    "tool_name": tool.name,
                    "call_id": call_id,
                    "verification_passed": verification_result.all_checks_passed if verification_result else None,
                    "verification_confidence": verification_result.confidence_score if verification_result else None,
                },
            )
            output_artifact_hash = output_artifact.artifact_hash

            # Set span status based on verification result
            if verification_result and not verification_result.all_checks_passed:
                trace_ctx.end_span(
                    status=SpanStatus.OK,
                    output_artifact_hash=output_artifact_hash,
                )
            else:
                trace_ctx.end_span(
                    status=SpanStatus.OK,
                    output_artifact_hash=output_artifact_hash,
                )

        return ToolResult(
            tool_call_id=call_id,
            content=wrapped + verification_info,
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
        """Get OpenAI-format schemas for all registered tools (ignores active toolset)."""
        return self._build_schemas(self._tools.values())

    def get_active_tool_schemas(self) -> list[dict[str, Any]]:
        """Get OpenAI-format schemas for only the currently active tools."""
        active_tools = [
            tool for tool in self._tools.values()
            if self._active_toolset.is_enabled(tool)
        ]
        return self._build_schemas(active_tools)

    def _build_schemas(self, tools: list[RegisteredTool] | Any) -> list[dict[str, Any]]:
        """Build OpenAI-format schemas from a list of tools."""
        schemas = []
        for tool in tools:
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

    def get_available_categories(self) -> dict[str, list[str]]:
        """Get all available tool categories and their tools."""
        categories: dict[str, list[str]] = {}
        for tool in self._tools.values():
            cat_name = tool.category.value
            if cat_name not in categories:
                categories[cat_name] = []
            categories[cat_name].append(tool.name)
        return categories

    def enable_category(self, category_name: str) -> list[str]:
        """Enable a tool category and return the list of newly enabled tools."""
        try:
            category = ToolCategory(category_name)
        except ValueError:
            return []

        self._active_toolset.enable_category(category)

        # Return list of tools in this category
        return [
            tool.name for tool in self._tools.values()
            if tool.category == category
        ]

    def enable_tools(self, tool_names: list[str]) -> list[str]:
        """Enable specific tools by name and return the list of successfully enabled tools."""
        enabled = []
        for name in tool_names:
            if name in self._tools:
                self._active_toolset.enable_tool(name)
                enabled.append(name)
        return enabled

    def reset_active_toolset(self) -> None:
        """Reset the active toolset to default (only CORE tools)."""
        self._active_toolset.reset()

    def set_swe_bench_toolset(self) -> list[str]:
        """
        Configure toolset for SWE-bench tasks (ACI-style minimal verb set).

        Based on SWE-agent research (NeurIPS 2024), successful agents use a small,
        closed action space with simple, composable verbs. This method:
        1. Disables ALL tools first (including core tools)
        2. Enables only the tools needed for code fixing: Read, Edit, bash, grep, glob, complete

        Returns list of enabled tool names.
        """
        # Reset to clean state
        self._active_toolset.reset()

        # Disable ALL registered tools first (allow-list approach)
        # This ensures only explicitly enabled tools are available
        for tool_name in self._tools:
            self._active_toolset.disable_tool(tool_name)

        # Explicitly enable only SWE-bench tools
        swe_bench_tools = ["Read", "Edit", "bash", "grep", "glob", "complete"]
        enabled = []
        for tool_name in swe_bench_tools:
            if tool_name in self._tools:
                self._active_toolset.enable_tool(tool_name)
                enabled.append(tool_name)

        return enabled

    def get_swe_bench_tool_schemas(self) -> list[dict[str, Any]]:
        """
        Get OpenAI-format schemas for SWE-bench tools only.

        This is the ACI (Agent-Computer Interface) for SWE-bench tasks.
        Returns a minimal, closed action space.
        """
        swe_bench_tools = ["Read", "Edit", "bash", "grep", "glob", "complete"]
        tools = [
            self._tools[name] for name in swe_bench_tools
            if name in self._tools
        ]
        return self._build_schemas(tools)
