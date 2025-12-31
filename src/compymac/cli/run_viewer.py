"""
RunViewer - CLI tool for viewing agent run timelines and artifacts.

This module implements Gap 2: Run Viewer UI by providing a command-line
interface to view:
- Run timeline (messages, tool calls, results)
- File diffs from edits
- Artifacts produced during the run
- Run metadata and status

Design decision: Use plain CLI output instead of TUI libraries (Textual/Rich)
to avoid adding new dependencies. This is sufficient for the initial implementation.
"""

import json
from datetime import datetime
from pathlib import Path

from compymac.storage.run_store import RunStatus, RunStore
from compymac.types import Role


class RunViewer:
    """
    CLI viewer for agent runs.

    Provides methods to display run information in a human-readable format.
    """

    def __init__(self, storage_dir: str | Path = "~/.compymac/runs"):
        """
        Initialize the run viewer.

        Args:
            storage_dir: Directory where runs are stored
        """
        self.store = RunStore(storage_dir)

    def list_runs(
        self,
        status: RunStatus | None = None,
        limit: int = 20,
        show_details: bool = False,
    ) -> str:
        """
        List all runs with optional filtering.

        Args:
            status: Optional status filter
            limit: Maximum number of runs to show
            show_details: Whether to show detailed information

        Returns:
            Formatted string output
        """
        runs = self.store.list_runs(status=status, limit=limit)

        if not runs:
            return "No runs found."

        lines = [f"Found {len(runs)} run(s):", ""]

        for run in runs:
            status_icon = self._status_icon(run.status)
            age = self._format_age(run.updated_at)

            lines.append(f"{status_icon} {run.run_id[:8]}... | {run.status.value:12} | {age:>10} ago")

            if show_details:
                lines.append(f"   Task: {run.task_description[:60]}...")
                lines.append(f"   Steps: {run.step_count} | Tool calls: {run.tool_calls_count}")
                if run.error_message:
                    lines.append(f"   Error: {run.error_message[:60]}...")
                lines.append("")

        return "\n".join(lines)

    def view_run(self, run_id: str) -> str:
        """
        View detailed information about a specific run.

        Args:
            run_id: The run ID to view

        Returns:
            Formatted string output
        """
        saved_run = self.store.load_run(run_id)
        if not saved_run:
            return f"Run not found: {run_id}"

        lines = [
            "=" * 60,
            f"Run: {saved_run.metadata.run_id}",
            "=" * 60,
            "",
            "Metadata:",
            f"  Status: {saved_run.metadata.status.value}",
            f"  Created: {saved_run.metadata.created_at.isoformat()}",
            f"  Updated: {saved_run.metadata.updated_at.isoformat()}",
            f"  Steps: {saved_run.metadata.step_count}",
            f"  Tool calls: {saved_run.metadata.tool_calls_count}",
            "",
            f"Task: {saved_run.metadata.task_description}",
            "",
        ]

        if saved_run.metadata.error_message:
            lines.extend([
                "Error:",
                f"  {saved_run.metadata.error_message}",
                "",
            ])

        if saved_run.metadata.tags:
            lines.extend([
                f"Tags: {', '.join(saved_run.metadata.tags)}",
                "",
            ])

        return "\n".join(lines)

    def view_timeline(self, run_id: str, limit: int = 50) -> str:
        """
        View the message timeline for a run.

        Args:
            run_id: The run ID to view
            limit: Maximum number of messages to show

        Returns:
            Formatted string output
        """
        saved_run = self.store.load_run(run_id)
        if not saved_run:
            return f"Run not found: {run_id}"

        messages = saved_run.session.messages
        if not messages:
            return "No messages in this run."

        lines = [
            "=" * 60,
            f"Timeline for run: {run_id[:8]}...",
            f"Total messages: {len(messages)}",
            "=" * 60,
            "",
        ]

        # Show last N messages
        display_messages = messages[-limit:] if len(messages) > limit else messages
        if len(messages) > limit:
            lines.append(f"[Showing last {limit} of {len(messages)} messages]")
            lines.append("")

        for i, msg in enumerate(display_messages):
            role_icon = self._role_icon(msg.role)
            content_preview = self._truncate(msg.content, 200)

            lines.append(f"[{i+1}] {role_icon} {msg.role.value.upper()}")
            lines.append(f"    {content_preview}")

            if msg.tool_calls:
                lines.append(f"    Tool calls: {len(msg.tool_calls)}")
                for tc in msg.tool_calls[:3]:  # Show first 3
                    tc_name = tc.get("function", {}).get("name", "unknown")
                    lines.append(f"      - {tc_name}")

            lines.append("")

        return "\n".join(lines)

    def view_tool_calls(self, run_id: str) -> str:
        """
        View all tool calls made during a run.

        Args:
            run_id: The run ID to view

        Returns:
            Formatted string output
        """
        saved_run = self.store.load_run(run_id)
        if not saved_run:
            return f"Run not found: {run_id}"

        lines = [
            "=" * 60,
            f"Tool calls for run: {run_id[:8]}...",
            "=" * 60,
            "",
        ]

        tool_calls = []
        for msg in saved_run.session.messages:
            if msg.tool_calls:
                for tc in msg.tool_calls:
                    tool_calls.append(tc)

        if not tool_calls:
            return "No tool calls in this run."

        lines.append(f"Total tool calls: {len(tool_calls)}")
        lines.append("")

        # Group by tool name
        by_tool: dict[str, int] = {}
        for tc in tool_calls:
            name = tc.get("function", {}).get("name", "unknown")
            by_tool[name] = by_tool.get(name, 0) + 1

        lines.append("Tool usage summary:")
        for name, count in sorted(by_tool.items(), key=lambda x: -x[1]):
            lines.append(f"  {name}: {count}")

        lines.append("")
        lines.append("Recent tool calls:")

        for i, tc in enumerate(tool_calls[-10:]):  # Show last 10
            name = tc.get("function", {}).get("name", "unknown")
            args = tc.get("function", {}).get("arguments", "{}")
            if isinstance(args, str):
                try:
                    args_dict = json.loads(args)
                    args_preview = ", ".join(f"{k}=..." for k in list(args_dict.keys())[:3])
                except json.JSONDecodeError:
                    args_preview = args[:50]
            else:
                args_preview = str(args)[:50]

            lines.append(f"  [{i+1}] {name}({args_preview})")

        return "\n".join(lines)

    def view_diffs(self, run_id: str) -> str:
        """
        View file diffs from edits made during a run.

        Args:
            run_id: The run ID to view

        Returns:
            Formatted string output
        """
        saved_run = self.store.load_run(run_id)
        if not saved_run:
            return f"Run not found: {run_id}"

        lines = [
            "=" * 60,
            f"File edits for run: {run_id[:8]}...",
            "=" * 60,
            "",
        ]

        # Extract file edits from tool calls
        edits = []
        for msg in saved_run.session.messages:
            if msg.tool_calls:
                for tc in msg.tool_calls:
                    name = tc.get("function", {}).get("name", "")
                    if name in ["Edit", "file_edit", "Write", "file_write"]:
                        args = tc.get("function", {}).get("arguments", "{}")
                        if isinstance(args, str):
                            try:
                                args = json.loads(args)
                            except json.JSONDecodeError:
                                args = {}
                        edits.append({
                            "tool": name,
                            "file_path": args.get("file_path", "unknown"),
                            "old_string": args.get("old_string", "")[:100] if args.get("old_string") else None,
                            "new_string": args.get("new_string", "")[:100] if args.get("new_string") else None,
                            "content": args.get("content", "")[:100] if args.get("content") else None,
                        })

        if not edits:
            return "No file edits in this run."

        lines.append(f"Total file edits: {len(edits)}")
        lines.append("")

        for i, edit in enumerate(edits):
            lines.append(f"[{i+1}] {edit['tool']} - {edit['file_path']}")
            if edit.get("old_string"):
                lines.append(f"    - {edit['old_string']}...")
            if edit.get("new_string"):
                lines.append(f"    + {edit['new_string']}...")
            if edit.get("content"):
                lines.append(f"    Content: {edit['content']}...")
            lines.append("")

        return "\n".join(lines)

    def get_resumable(self) -> str:
        """
        List runs that can be resumed.

        Returns:
            Formatted string output
        """
        runs = self.store.get_resumable_runs()

        if not runs:
            return "No resumable runs found."

        lines = [
            "Resumable runs:",
            "",
        ]

        for run in runs:
            status_icon = self._status_icon(run.status)
            age = self._format_age(run.updated_at)

            lines.append(f"{status_icon} {run.run_id}")
            lines.append(f"   Status: {run.status.value} | {age} ago")
            lines.append(f"   Task: {run.task_description[:60]}...")
            lines.append(f"   Steps: {run.step_count}")
            lines.append("")

        return "\n".join(lines)

    def _status_icon(self, status: RunStatus) -> str:
        """Get icon for run status."""
        icons = {
            RunStatus.PENDING: "[.]",
            RunStatus.RUNNING: "[>]",
            RunStatus.PAUSED: "[|]",
            RunStatus.COMPLETED: "[+]",
            RunStatus.FAILED: "[X]",
            RunStatus.INTERRUPTED: "[!]",
        }
        return icons.get(status, "[?]")

    def _role_icon(self, role: Role) -> str:
        """Get icon for message role."""
        icons = {
            Role.SYSTEM: "[S]",
            Role.USER: "[U]",
            Role.ASSISTANT: "[A]",
            Role.TOOL: "[T]",
        }
        return icons.get(role, "[?]")

    def _truncate(self, text: str, max_len: int) -> str:
        """Truncate text to max length."""
        if len(text) <= max_len:
            return text.replace("\n", " ")
        return text[:max_len].replace("\n", " ") + "..."

    def _format_age(self, dt: datetime) -> str:
        """Format datetime as human-readable age."""
        now = datetime.utcnow()
        delta = now - dt

        if delta.days > 0:
            return f"{delta.days}d"
        elif delta.seconds >= 3600:
            return f"{delta.seconds // 3600}h"
        elif delta.seconds >= 60:
            return f"{delta.seconds // 60}m"
        else:
            return f"{delta.seconds}s"


def main():
    """CLI entry point for run viewer."""
    import argparse

    parser = argparse.ArgumentParser(description="CompyMac Run Viewer")
    parser.add_argument("--storage-dir", default="~/.compymac/runs",
                        help="Directory where runs are stored")

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # list command
    list_parser = subparsers.add_parser("list", help="List all runs")
    list_parser.add_argument("--status", choices=["pending", "running", "paused",
                                                   "completed", "failed", "interrupted"],
                             help="Filter by status")
    list_parser.add_argument("--limit", type=int, default=20, help="Max runs to show")
    list_parser.add_argument("--details", action="store_true", help="Show details")

    # view command
    view_parser = subparsers.add_parser("view", help="View a specific run")
    view_parser.add_argument("run_id", help="Run ID to view")

    # timeline command
    timeline_parser = subparsers.add_parser("timeline", help="View run timeline")
    timeline_parser.add_argument("run_id", help="Run ID to view")
    timeline_parser.add_argument("--limit", type=int, default=50, help="Max messages")

    # tools command
    tools_parser = subparsers.add_parser("tools", help="View tool calls")
    tools_parser.add_argument("run_id", help="Run ID to view")

    # diffs command
    diffs_parser = subparsers.add_parser("diffs", help="View file diffs")
    diffs_parser.add_argument("run_id", help="Run ID to view")

    # resumable command
    subparsers.add_parser("resumable", help="List resumable runs")

    args = parser.parse_args()

    viewer = RunViewer(args.storage_dir)

    if args.command == "list":
        status = RunStatus(args.status) if args.status else None
        print(viewer.list_runs(status=status, limit=args.limit, show_details=args.details))
    elif args.command == "view":
        print(viewer.view_run(args.run_id))
    elif args.command == "timeline":
        print(viewer.view_timeline(args.run_id, limit=args.limit))
    elif args.command == "tools":
        print(viewer.view_tool_calls(args.run_id))
    elif args.command == "diffs":
        print(viewer.view_diffs(args.run_id))
    elif args.command == "resumable":
        print(viewer.get_resumable())
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
