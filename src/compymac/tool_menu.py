"""
Tool Menu System - Hierarchical tool discovery with mode-based navigation.

This module implements a 2-level hierarchical menu system for tools to reduce
context size and improve tool selection accuracy. Instead of exposing 60+ tools
at once (causing decision fatigue), the agent starts with meta-tools and drills
into specific modes (swe, browser, git, etc.) with 7-15 tools per mode.

Architecture:
- MenuManager tracks current mode (ROOT or a specific mode)
- Navigation tools (menu_list, menu_enter, menu_exit) are always visible
- Mode tools are only visible when that mode is active
- Cross-cutting tools appear in multiple modes where semantically appropriate
  (e.g., web_search in swe AND search, librarian in swe AND library)

Design Principles (based on Manus/Devin research):
1. "Mask, Don't Remove" - tools are always registered, visibility is controlled
2. Cross-cutting tools appear in multiple modes where users expect them
3. Every registered tool must be in at least one mode (validated at startup)
4. Mode ordering matters - most common modes first (swe, library, browser, search)

Usage:
    manager = MenuManager()
    manager.enter_mode("swe")  # Now only SWE tools + meta-tools are visible
    manager.exit_mode()  # Back to ROOT, only meta-tools visible
"""

from dataclasses import dataclass, field
from enum import Enum


class MenuState(Enum):
    """Current state of the menu system."""
    ROOT = "root"  # At root level, only meta-tools visible
    IN_MODE = "in_mode"  # In a specific mode, mode tools + meta-tools visible


@dataclass
class ToolMode:
    """Definition of a tool mode with its associated tools."""
    name: str  # Internal name (e.g., "swe", "browser")
    display_name: str  # Human-readable name (e.g., "SWE Mode", "Browser Mode")
    tool_list: list[str]  # List of tool names in this mode
    description: str  # Brief description of what this mode is for


# Always-visible meta-tools (available in all modes)
# These are the navigation and core communication tools
META_TOOLS = [
    "menu_list",
    "menu_enter",
    "menu_exit",
    "complete",
    "think",
    "message_user",
]


# Mode definitions with narrative priming and behavioral guidance
# Based on research: arxiv:2505.03961 (narrative priming), arxiv:2505.11584 (nudge sensitivity)
# Ordered by frequency: most common modes first to leverage hypersensitivity to ordering
#
# IMPORTANT: Every registered tool must appear in at least one mode.
# Cross-cutting tools (web_search, ask_smart_friend, librarian, etc.) appear in multiple modes.
TOOL_MODES: dict[str, ToolMode] = {
    # =========================================================================
    # PRIMARY MODES - Most frequently used, ordered by frequency
    # =========================================================================
    "swe": ToolMode(
        name="swe",
        display_name="Software Engineering",
        tool_list=[
            # CORE file operations
            "Read", "Edit", "Write", "bash", "grep", "glob",
            # LSP for code intelligence
            "lsp_tool",
            # Git subset for quick commits (full git ops in 'git' mode)
            "git_status", "git_diff_unstaged", "git_diff_staged", "git_commit", "git_add",
            # Shell session management (for background processes, interactive shells)
            "bash_output", "write_to_shell", "kill_shell", "wait",
            # Cross-cutting: research capabilities
            "web_search", "web_get_contents",
            # Cross-cutting: browser subset for quick web verification (full browser in 'browser' mode)
            "browser_navigate", "browser_view",
            # Cross-cutting: AI assistance for debugging
            "ask_smart_friend",
            # Cross-cutting: document library for code docs
            "librarian", "librarian_search",
            # Cross-cutting: task management
            "TodoCreate", "TodoRead", "TodoStart", "TodoClaim", "TodoVerify",
            # SWE-bench phase tools (for structured workflows)
            "advance_phase", "return_to_fix_phase", "analyze_test_failure", "get_phase_status",
        ],
        description="You are working as a skilled software engineer in a codebase. Your goal is to understand existing code, make targeted improvements, verify changes with tests, and commit your work. This mode provides tools to read source code files, search for implementations, edit code precisely, run tests and builds, manage git commits, research documentation, and consult the document library for code docs. Use this when you need to fix bugs, implement features, refactor code, or investigate how existing code works. Remember: Read files before editing them, verify changes with tests, and commit with clear messages. For quick web verification, browser_navigate and browser_view are available; for full browser automation, enter 'browser' mode.",
    ),
    "library": ToolMode(
        name="library",
        display_name="Document Library",
        tool_list=[
            # LIBRARY tools - canonical home for document operations
            "librarian", "librarian_search",
            # Cross-cutting: web search for online docs
            "web_search", "web_get_contents",
        ],
        description="You are searching and retrieving information from the document library (uploaded PDFs, EPUBs, and other documents). Your goal is to find relevant content, extract information, and provide citations. This mode provides the librarian tool for searching, listing, and reading documents. Use this when you need to find information in uploaded documents, cite sources, or answer questions based on library content. Remember: Use librarian with action='search' to find content, action='list' to see available documents, and action='answer' to get synthesized answers with citations.",
    ),
    "browser": ToolMode(
        name="browser",
        display_name="Browser Automation",
        tool_list=[
            # All BROWSER tools
            "browser_navigate", "browser_view", "browser_click",
            "browser_type", "browser_scroll", "browser_screenshot",
            "browser_console", "browser_press_key", "browser_move_mouse",
            "browser_select_option", "browser_select_file",
            "browser_set_mobile", "browser_restart",
            # RECORDING tools - for UI testing
            "recording_start", "recording_stop",
            # Cross-cutting: visual verification
            "visual_checker",
            # Cross-cutting: task management (agents often want to plan before browsing)
            "TodoCreate", "TodoRead",
        ],
        description="You are interacting with a live web application in a real browser to test, verify, or automate user interactions. Your goal is to navigate pages, interact with UI elements, and verify that the application behaves correctly from a user's perspective. This mode provides tools to navigate to URLs, view page content with screenshots, click elements, type text, scroll pages, execute JavaScript, and record screen for UI testing. Use this when you need to test a web UI, verify visual appearance, automate form submissions, or investigate how a web application behaves. Remember: Use browser_view after navigation to see what's on the page, prefer clicking elements by devinid over coordinates, and use recording_start/stop for UI testing evidence.",
    ),
    "search": ToolMode(
        name="search",
        display_name="Web Research",
        tool_list=[
            # SEARCH tools
            "web_search", "web_get_contents",
            # Browser subset for complex pages
            "browser_navigate", "browser_view",
            # Cross-cutting: document library for local docs
            "librarian", "librarian_search",
            # Cross-cutting: AI for research questions
            "ask_smart_friend",
            # Cross-cutting: task management (research tasks often benefit from planning)
            "TodoCreate", "TodoRead",
        ],
        description="You are researching information on the web or in the document library to find documentation, answers, or current information. Your goal is to find relevant, accurate information efficiently and extract what's needed for the task. This mode provides tools to search the web, fetch webpage content, navigate to documentation sites, and search the document library. Use this when you need to find error message solutions, read API documentation, research library usage, or search uploaded documents. Remember: Start with web_search for online content or librarian for uploaded documents, then use web_get_contents for simple pages or browser_navigate for complex sites.",
    ),
    # =========================================================================
    # SECONDARY MODES - Less frequent but important
    # =========================================================================
    "git": ToolMode(
        name="git",
        display_name="Version Control",
        tool_list=[
            # All GIT_LOCAL tools
            "git_status", "git_diff_unstaged", "git_diff_staged", "git_diff",
            "git_commit", "git_add", "git_reset", "git_log",
            "git_create_branch", "git_checkout", "git_show", "git_branch_list",
            # All GIT_REMOTE tools
            "git_view_pr", "git_create_pr", "git_update_pr_description",
            "git_pr_checks", "git_ci_job_logs", "git_comment_on_pr", "list_repos",
        ],
        description="You are managing code changes and pull requests in a git repository. Your goal is to create well-structured commits, manage branches effectively, and collaborate through pull requests with clear communication. This mode provides tools for local git operations (status, diff, commit, branch management) and remote operations (creating/viewing PRs, checking CI status, commenting). Use this when you need to create pull requests, review changes across branches, manage complex git workflows, or debug CI failures. Remember: Check git_status before committing, write clear commit messages explaining what changed and why, and review diffs before pushing.",
    ),
    "data": ToolMode(
        name="data",
        display_name="File Management",
        tool_list=[
            # All FILESYSTEM tools
            "fs_read_file", "fs_write_file", "fs_list_directory",
            "fs_create_directory", "fs_delete", "fs_move", "fs_file_info",
            # Cross-cutting: search within files
            "grep", "glob",
            # Cross-cutting: bash for file operations
            "bash",
        ],
        description="You are managing files and directories in the filesystem for organization, backup, or data processing. Your goal is to organize files, manage directory structures, and handle non-code files efficiently. This mode provides tools to read/write files, list directories, create/delete/move files and folders, and search within files. Use this when you need to organize configuration files, manage data files (.json, .yaml, .csv), handle logs, or perform bulk file operations. This is for NON-CODE files - use 'swe' mode for reading/editing source code. Remember: Check if directories exist before creating them, and be cautious with delete operations.",
    ),
    "deploy": ToolMode(
        name="deploy",
        display_name="Deployment",
        tool_list=[
            # DEPLOY tools
            "deploy",
            # Git subset for CI/CD
            "git_ci_job_logs", "git_pr_checks",
            # Cross-cutting: bash for deploy commands
            "bash", "bash_output",
        ],
        description="You are deploying and monitoring applications in production or staging environments. Your goal is to deploy applications safely, verify deployment health, and debug deployment failures. This mode provides tools to deploy frontend/backend applications, check CI/CD status, and view deployment logs. Use this when you need to deploy new versions, verify deployment succeeded, or investigate why a deployment failed. Remember: Check git_pr_checks to verify CI passed before deploying, and review git_ci_job_logs if deployment fails to identify the root cause.",
    ),
    # =========================================================================
    # UTILITY MODES - Specialized tools
    # =========================================================================
    "ai": ToolMode(
        name="ai",
        display_name="AI Assistance & Tasks",
        tool_list=[
            # AI tools
            "ask_smart_friend", "visual_checker",
            # All TODO tools
            "TodoCreate", "TodoRead", "TodoStart", "TodoClaim", "TodoVerify",
            # Cross-cutting: web search for research
            "web_search", "web_get_contents",
        ],
        description="You are using advanced AI capabilities for complex analysis, visual verification, or task management. Your goal is to leverage specialized AI for tasks that benefit from additional intelligence or structured task tracking. This mode provides tools to consult specialized AI for complex questions, verify visual/UI elements, and manage tasks with the todo system. Use this when you need expert-level analysis beyond your capabilities, visual verification of screenshots, or structured task management. Remember: Use ask_smart_friend for truly complex questions where you need another perspective, not for simple lookups.",
    ),
    "integrations": ToolMode(
        name="integrations",
        display_name="External Integrations",
        tool_list=[
            # MCP tools
            "mcp_tool",
            # SECRETS tools
            "list_secrets",
            # Dynamic tool discovery
            "request_tools",
        ],
        description="You are working with external integrations, MCP servers, secrets, and dynamic tool discovery. Your goal is to connect to external services, manage credentials safely, and discover additional tools. This mode provides tools to interact with MCP servers (list_servers, list_tools, call_tool), list available secrets, and request additional tools. Use this when you need to connect to external APIs via MCP, check what secrets are available, or enable additional tool categories. Remember: Use mcp_tool with command='list_servers' first to see available integrations.",
    ),
}


@dataclass
class MenuManager:
    """
    Manages the hierarchical tool menu system.

    Tracks current mode and provides methods for mode navigation.
    The agent loop uses this to determine which tool schemas to expose.
    """
    _current_mode: str | None = None
    _state: MenuState = field(default=MenuState.ROOT)

    @property
    def current_mode(self) -> str | None:
        """Get the current mode name, or None if at ROOT."""
        return self._current_mode

    @property
    def state(self) -> MenuState:
        """Get the current menu state."""
        return self._state

    def is_at_root(self) -> bool:
        """Check if currently at ROOT level."""
        return self._state == MenuState.ROOT

    def get_current_mode(self) -> ToolMode | None:
        """Get the current ToolMode object, or None if at ROOT."""
        if self._current_mode is None:
            return None
        return TOOL_MODES.get(self._current_mode)

    def enter_mode(self, mode_name: str) -> tuple[bool, str]:
        """
        Enter a specific mode.

        Returns (success, message) tuple.
        """
        if mode_name not in TOOL_MODES:
            available = ", ".join(TOOL_MODES.keys())
            return False, f"Unknown mode '{mode_name}'. Available modes: {available}"

        self._current_mode = mode_name
        self._state = MenuState.IN_MODE

        mode = TOOL_MODES[mode_name]
        tool_count = len(mode.tool_list)
        return True, f"Entered {mode.display_name}. {tool_count} tools now available: {', '.join(mode.tool_list)}"

    def exit_mode(self) -> tuple[bool, str]:
        """
        Exit current mode and return to ROOT.

        Returns (success, message) tuple.
        """
        if self._state == MenuState.ROOT:
            return False, "Already at ROOT level. Use menu_enter to enter a mode."

        old_mode = self._current_mode
        self._current_mode = None
        self._state = MenuState.ROOT

        return True, f"Exited {old_mode} mode. Now at ROOT. Use menu_list to see available modes."

    def list_menu(self) -> str:
        """
        List current menu state and available options.

        Returns a formatted string showing current mode and available actions.
        """
        lines = []

        if self._state == MenuState.ROOT:
            lines.append("Current: ROOT (no mode selected)")
            lines.append("")
            lines.append("Available modes:")
            for name, mode in TOOL_MODES.items():
                lines.append(f"  - {name}: {mode.description}")
            lines.append("")
            lines.append("Use menu_enter(mode='<mode_name>') to enter a mode.")
        else:
            mode = TOOL_MODES[self._current_mode]
            lines.append(f"Current: {mode.display_name}")
            lines.append(f"Description: {mode.description}")
            lines.append("")
            lines.append(f"Available tools ({len(mode.tool_list)}):")
            for tool in mode.tool_list:
                lines.append(f"  - {tool}")
            lines.append("")
            lines.append("Meta-tools (always available):")
            for tool in META_TOOLS:
                lines.append(f"  - {tool}")
            lines.append("")
            lines.append("Use menu_exit() to return to ROOT.")

        return "\n".join(lines)

    def get_visible_tools(self) -> list[str]:
        """
        Get list of tool names that should be visible in current state.

        Returns meta-tools + current mode tools (if in a mode).
        """
        visible = list(META_TOOLS)

        if self._state == MenuState.IN_MODE and self._current_mode:
            mode = TOOL_MODES.get(self._current_mode)
            if mode:
                visible.extend(mode.tool_list)

        return visible

    def get_available_modes(self) -> list[str]:
        """Get list of available mode names."""
        return list(TOOL_MODES.keys())

    def reset(self) -> None:
        """Reset to ROOT state."""
        self._current_mode = None
        self._state = MenuState.ROOT


def get_all_mode_tools() -> set[str]:
    """Get the union of all tools across all modes (excluding META_TOOLS).

    This is useful for validation to ensure all registered tools are covered.
    """
    all_tools: set[str] = set()
    for mode in TOOL_MODES.values():
        all_tools.update(mode.tool_list)
    return all_tools


def validate_tool_coverage(registered_tools: set[str]) -> tuple[bool, list[str]]:
    """Validate that all registered tools are in at least one mode.

    Args:
        registered_tools: Set of all registered tool names from the harness

    Returns:
        Tuple of (is_valid, list_of_unmapped_tools)

    This implements the "everything accounted for" principle - every registered
    tool must be reachable through the menu system.
    """
    # Tools that are always visible (META_TOOLS) don't need to be in modes
    meta_tools_set = set(META_TOOLS)

    # Get all tools covered by modes
    mode_tools = get_all_mode_tools()

    # Tools that are covered = META_TOOLS + all mode tools
    covered_tools = meta_tools_set | mode_tools

    # Find unmapped tools (registered but not in any mode or META_TOOLS)
    unmapped = registered_tools - covered_tools

    # Filter out tools that are intentionally not in menus:
    # - These are internal/system tools that shouldn't be user-facing
    internal_tools = {
        # None currently - all tools should be accessible
    }
    unmapped = unmapped - internal_tools

    return len(unmapped) == 0, sorted(unmapped)
