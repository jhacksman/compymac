"""
Tool Menu System - Hierarchical tool discovery with mode-based navigation.

This module implements a 2-level hierarchical menu system for tools to reduce
context size and improve tool selection accuracy. Instead of exposing 60+ tools
at once (causing decision fatigue), the agent starts with meta-tools and drills
into specific modes (swe, browser, git, etc.) with 7-12 tools per mode.

Architecture:
- MenuManager tracks current mode (ROOT or a specific mode)
- Navigation tools (menu_list, menu_enter, menu_exit) are always visible
- Mode tools are only visible when that mode is active
- Cross-mode tools (e.g., browser_navigate in search mode) are supported

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
META_TOOLS = [
    "menu_list",
    "menu_enter",
    "menu_exit",
    "complete",
    "think",
    "message_user",
]


# Mode definitions based on user requirements
TOOL_MODES: dict[str, ToolMode] = {
    "swe": ToolMode(
        name="swe",
        display_name="SWE Mode",
        tool_list=[
            "Read", "Edit", "Write", "bash", "grep", "glob",
            "lsp_tool", "git_status", "git_diff_unstaged", "git_diff_staged",
            "git_commit", "git_add",
            "web_search", "web_get_contents",  # Research capabilities
        ],
        description="Software engineering: read, edit, search code, run commands, git operations, web research",
    ),
    "browser": ToolMode(
        name="browser",
        display_name="Browser Mode",
        tool_list=[
            "browser_navigate", "browser_view", "browser_click",
            "browser_type", "browser_scroll", "browser_screenshot",
            "browser_console", "browser_press_key", "browser_select_option",
        ],
        description="Browser automation: navigate, interact with web pages, take screenshots",
    ),
    "git": ToolMode(
        name="git",
        display_name="Git Mode",
        tool_list=[
            # GIT_LOCAL tools
            "git_status", "git_diff_unstaged", "git_diff_staged", "git_diff",
            "git_commit", "git_add", "git_reset", "git_log",
            "git_create_branch", "git_checkout", "git_show",
            # GIT_REMOTE tools
            "git_view_pr", "git_create_pr", "git_update_pr_description",
            "git_pr_checks", "git_ci_job_logs", "git_comment_on_pr", "list_repos",
        ],
        description="Git operations: local and remote repository management, PRs, CI",
    ),
    "deploy": ToolMode(
        name="deploy",
        display_name="Deploy Mode",
        tool_list=[
            "deploy", "git_ci_job_logs", "git_pr_checks",
        ],
        description="Deployment: deploy apps, check CI status, view logs",
    ),
    "search": ToolMode(
        name="search",
        display_name="Search Mode",
        tool_list=[
            "web_search", "web_get_contents", "browser_navigate", "browser_view",
        ],
        description="Web search: search the web, fetch page contents",
    ),
    "ai": ToolMode(
        name="ai",
        display_name="AI Mode",
        tool_list=[
            "ask_smart_friend", "visual_checker", "TodoCreate", "TodoRead",
        ],
        description="AI assistance: smart friend, visual analysis, task management",
    ),
    "data": ToolMode(
        name="data",
        display_name="Data Mode",
        tool_list=[
            # FILESYSTEM tools
            "fs_read_file", "fs_write_file", "fs_list_directory",
            "fs_create_directory", "fs_delete", "fs_move", "fs_copy",
        ],
        description="Data/filesystem: file operations, directory management",
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
