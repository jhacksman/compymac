"""
Tests for ToolRegistry - the only way to affect the world.

These tests verify the core constraint: tools are the only
mechanism for side effects.
"""


from compymac.tools import Tool, ToolRegistry, create_mock_tools
from compymac.types import ToolCall


class TestToolDefinition:
    """Test tool definition and schema generation."""

    def test_tool_to_openai_schema(self) -> None:
        """Tool should generate valid OpenAI schema."""
        tool = Tool(
            name="test_tool",
            description="A test tool",
            parameters={
                "type": "object",
                "properties": {
                    "arg1": {"type": "string"},
                },
                "required": ["arg1"],
            },
            handler=lambda arg1: f"Got: {arg1}",
        )

        schema = tool.to_openai_schema()

        assert schema["type"] == "function"
        assert schema["function"]["name"] == "test_tool"
        assert schema["function"]["description"] == "A test tool"
        assert "properties" in schema["function"]["parameters"]

    def test_tool_execution_success(self) -> None:
        """Tool execution should return success result."""
        tool = Tool(
            name="echo",
            description="Echo input",
            parameters={"type": "object", "properties": {}},
            handler=lambda **kwargs: "echoed",
        )

        result = tool.execute({})

        assert result.success
        assert result.content == "echoed"

    def test_tool_execution_failure(self) -> None:
        """Tool execution failure should be captured."""
        def failing_handler(**kwargs: object) -> str:
            raise ValueError("Something went wrong")

        tool = Tool(
            name="failing",
            description="Always fails",
            parameters={"type": "object", "properties": {}},
            handler=failing_handler,
        )

        result = tool.execute({})

        assert not result.success
        assert "Something went wrong" in result.content
        assert result.error is not None


class TestToolRegistry:
    """Test the tool registry."""

    def test_register_and_get_tool(self) -> None:
        """Should be able to register and retrieve tools."""
        registry = ToolRegistry()
        tool = Tool(
            name="my_tool",
            description="My tool",
            parameters={"type": "object", "properties": {}},
            handler=lambda: "result",
        )

        registry.register(tool)

        assert "my_tool" in registry
        assert registry.get("my_tool") is tool

    def test_register_function_convenience(self) -> None:
        """register_function should create and register a tool."""
        registry = ToolRegistry()

        tool = registry.register_function(
            name="func_tool",
            description="Function tool",
            parameters={"type": "object", "properties": {}},
            handler=lambda: "done",
        )

        assert "func_tool" in registry
        assert registry.get("func_tool") is tool

    def test_execute_tool_call(self) -> None:
        """Registry should execute tool calls."""
        registry = ToolRegistry()
        registry.register_function(
            name="greet",
            description="Greet someone",
            parameters={
                "type": "object",
                "properties": {"name": {"type": "string"}},
            },
            handler=lambda name: f"Hello, {name}!",
        )

        tool_call = ToolCall(
            id="call_123",
            name="greet",
            arguments={"name": "World"},
        )

        result = registry.execute(tool_call)

        assert result.success
        assert result.tool_call_id == "call_123"
        assert "Hello, World!" in result.content

    def test_execute_unknown_tool(self) -> None:
        """Executing unknown tool should return error."""
        registry = ToolRegistry()

        tool_call = ToolCall(
            id="call_456",
            name="nonexistent",
            arguments={},
        )

        result = registry.execute(tool_call)

        assert not result.success
        assert "Unknown tool" in result.content

    def test_get_schemas(self) -> None:
        """Should return schemas for all registered tools."""
        registry = ToolRegistry()
        registry.register_function(
            name="tool1",
            description="Tool 1",
            parameters={"type": "object", "properties": {}},
            handler=lambda: "1",
        )
        registry.register_function(
            name="tool2",
            description="Tool 2",
            parameters={"type": "object", "properties": {}},
            handler=lambda: "2",
        )

        schemas = registry.get_schemas()

        assert len(schemas) == 2
        names = [s["function"]["name"] for s in schemas]
        assert "tool1" in names
        assert "tool2" in names


class TestMockTools:
    """Test the mock tools for demonstration."""

    def test_create_mock_tools(self) -> None:
        """create_mock_tools should return a populated registry."""
        registry = create_mock_tools()

        assert len(registry) > 0
        assert "read_file" in registry
        assert "write_file" in registry
        assert "run_command" in registry
        assert "search_web" in registry

    def test_mock_tools_return_mock_results(self) -> None:
        """Mock tools should return mock results, not real actions."""
        registry = create_mock_tools()

        tool_call = ToolCall(
            id="test",
            name="read_file",
            arguments={"path": "/etc/passwd"},
        )

        result = registry.execute(tool_call)

        assert result.success
        assert "[MOCK]" in result.content
        assert "/etc/passwd" in result.content
