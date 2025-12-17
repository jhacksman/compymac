"""
Tool System - The only way to affect the world.

Tools are the ONLY mechanism by which the agent can have side effects.
The agent cannot directly modify files, make HTTP requests, or perform
any action except by emitting a tool call that the runtime executes.

This is a fundamental constraint: the agent is isolated from the world
except through this controlled interface.
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Protocol

from compymac.types import ToolCall, ToolResult

logger = logging.getLogger(__name__)


class ToolHandler(Protocol):
    """Protocol for tool handler functions."""
    def __call__(self, **kwargs: Any) -> str: ...


@dataclass
class Tool:
    """
    Definition of a tool that the agent can use.

    A tool has:
    - name: Unique identifier
    - description: What the tool does (shown to the LLM)
    - parameters: JSON Schema for the tool's parameters
    - handler: Function that executes the tool

    The handler is the ONLY code that can have side effects.
    """
    name: str
    description: str
    parameters: dict[str, Any]
    handler: ToolHandler

    def to_openai_schema(self) -> dict[str, Any]:
        """Convert to OpenAI tool format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    def execute(self, arguments: dict[str, Any]) -> ToolResult:
        """
        Execute the tool with the given arguments.

        This is where side effects happen. The result is returned
        as a ToolResult that will be added to the conversation.
        """
        try:
            result = self.handler(**arguments)
            return ToolResult(
                tool_call_id="",
                content=str(result),
                success=True,
            )
        except Exception as e:
            logger.error(f"Tool {self.name} failed: {e}")
            return ToolResult(
                tool_call_id="",
                content=f"Error: {e}",
                success=False,
                error=str(e),
            )


@dataclass
class ToolRegistry:
    """
    Registry of available tools.

    The registry is the controlled interface through which the agent
    can affect the world. Only tools registered here can be called.
    """

    _tools: dict[str, Tool] = field(default_factory=dict)

    def register(self, tool: Tool) -> None:
        """Register a tool."""
        if tool.name in self._tools:
            logger.warning(f"Overwriting existing tool: {tool.name}")
        self._tools[tool.name] = tool
        logger.debug(f"Registered tool: {tool.name}")

    def register_function(
        self,
        name: str,
        description: str,
        parameters: dict[str, Any],
        handler: ToolHandler,
    ) -> Tool:
        """Convenience method to register a function as a tool."""
        tool = Tool(
            name=name,
            description=description,
            parameters=parameters,
            handler=handler,
        )
        self.register(tool)
        return tool

    def get(self, name: str) -> Tool | None:
        """Get a tool by name."""
        return self._tools.get(name)

    def execute(self, tool_call: ToolCall) -> ToolResult:
        """
        Execute a tool call.

        This is the controlled entry point for all side effects.
        """
        tool = self._tools.get(tool_call.name)
        if tool is None:
            return ToolResult(
                tool_call_id=tool_call.id,
                content=f"Error: Unknown tool '{tool_call.name}'",
                success=False,
                error=f"Unknown tool: {tool_call.name}",
            )

        logger.info(f"Executing tool: {tool_call.name}")
        result = tool.execute(tool_call.arguments)
        result.tool_call_id = tool_call.id
        return result

    def get_schemas(self) -> list[dict[str, Any]]:
        """Get OpenAI-format schemas for all registered tools."""
        return [tool.to_openai_schema() for tool in self._tools.values()]

    @property
    def tool_names(self) -> list[str]:
        """List of registered tool names."""
        return list(self._tools.keys())

    def __len__(self) -> int:
        return len(self._tools)

    def __contains__(self, name: str) -> bool:
        return name in self._tools


def create_mock_tools() -> ToolRegistry:
    """
    Create a registry with mock tools for demonstration.

    These tools don't actually do anything - they just demonstrate
    the interface. In a real system, these would have real handlers.
    """
    registry = ToolRegistry()

    registry.register_function(
        name="read_file",
        description="Read the contents of a file",
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "The path to the file to read",
                },
            },
            "required": ["path"],
        },
        handler=lambda path: f"[MOCK] Would read file: {path}",
    )

    registry.register_function(
        name="write_file",
        description="Write content to a file",
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "The path to the file to write",
                },
                "content": {
                    "type": "string",
                    "description": "The content to write to the file",
                },
            },
            "required": ["path", "content"],
        },
        handler=lambda path, content: f"[MOCK] Would write to {path}: {len(content)} chars",
    )

    registry.register_function(
        name="run_command",
        description="Run a shell command",
        parameters={
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The command to run",
                },
            },
            "required": ["command"],
        },
        handler=lambda command: f"[MOCK] Would run: {command}",
    )

    registry.register_function(
        name="search_web",
        description="Search the web for information",
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query",
                },
            },
            "required": ["query"],
        },
        handler=lambda query: f"[MOCK] Would search for: {query}",
    )

    return registry
