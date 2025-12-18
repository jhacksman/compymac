"""
Conformance tests for the Harness Simulator.

These tests verify that the simulator accurately reflects the
measured constraints from empirical probing of the Devin harness.

Each test corresponds to an experiment documented in harness.md.
"""

import pytest

from compymac.harness_simulator import (
    EventType,
    HarnessSimulator,
    SimulatedTool,
    ToolSchema,
    create_default_simulator,
)
from compymac.harness_spec import HARNESS_CONSTRAINTS, truncate_lines, truncate_output
from compymac.types import ToolCall


class TestTruncationBehavior:
    """Tests for truncation behavior (Experiments 7.1, 8.1, 8.3)."""
    
    def test_shell_output_truncation_at_20k(self):
        """Verify shell output truncates at 20,000 characters."""
        content = "x" * 25_000
        truncated, chars_removed = truncate_output(content)
        
        assert len(truncated) == HARNESS_CONSTRAINTS.shell_output_display_limit
        assert chars_removed == 5_000
    
    def test_shell_output_no_truncation_under_limit(self):
        """Verify no truncation when under limit."""
        content = "x" * 10_000
        truncated, chars_removed = truncate_output(content)
        
        assert truncated == content
        assert chars_removed == 0
    
    def test_file_read_line_truncation(self):
        """Verify file read truncates at ~136 lines."""
        lines = [f"Line {i}" for i in range(200)]
        truncated, was_truncated = truncate_lines(lines)
        
        assert len(truncated) == HARNESS_CONSTRAINTS.file_read_default_lines
        assert was_truncated is True
    
    def test_file_read_no_truncation_under_limit(self):
        """Verify no truncation when under line limit."""
        lines = [f"Line {i}" for i in range(50)]
        truncated, was_truncated = truncate_lines(lines)
        
        assert truncated == lines
        assert was_truncated is False


class TestSchemaValidation:
    """Tests for schema validation (Experiment 7.2)."""
    
    def test_missing_required_param_returns_plain_text_error(self):
        """Verify schema errors are plain text, not XML envelope."""
        simulator = create_default_simulator()
        
        # Call Read without required file_path
        tool_call = ToolCall(
            id="test_1",
            name="Read",
            arguments={},
        )
        
        result = simulator.execute(tool_call)
        
        assert result.success is False
        assert "Missing required parameter" in result.content
        # Should NOT be wrapped in XML
        assert "<" not in result.content or "Error:" in result.content
    
    def test_valid_params_pass_validation(self):
        """Verify valid parameters pass schema validation."""
        simulator = create_default_simulator()
        
        tool_call = ToolCall(
            id="test_2",
            name="Read",
            arguments={"file_path": "/test/file.txt"},
        )
        
        result = simulator.execute(tool_call)
        
        assert result.success is True


class TestToolResultIsolation:
    """Tests for tool result isolation (Experiment 7.3)."""
    
    def test_file_read_wrapped_in_envelope(self):
        """Verify file read results are wrapped in XML envelope."""
        simulator = create_default_simulator()
        
        tool_call = ToolCall(
            id="test_3",
            name="Read",
            arguments={"file_path": "/test/file.txt"},
        )
        
        result = simulator.execute(tool_call)
        
        assert "<full-file-view" in result.content
        assert "</full-file-view>" in result.content
    
    def test_shell_output_wrapped_in_envelope(self):
        """Verify shell output is wrapped in XML envelope."""
        simulator = create_default_simulator()
        
        tool_call = ToolCall(
            id="test_4",
            name="bash",
            arguments={
                "command": "echo hello",
                "exec_dir": "/tmp",
                "bash_id": "default",
            },
        )
        
        result = simulator.execute(tool_call)
        
        assert "<shell-output>" in result.content
        assert "</shell-output>" in result.content


class TestErrorHandling:
    """Tests for error handling (Experiment 7.7)."""
    
    def test_unknown_tool_returns_error(self):
        """Verify unknown tool returns error without crashing."""
        simulator = create_default_simulator()
        
        tool_call = ToolCall(
            id="test_5",
            name="nonexistent_tool",
            arguments={},
        )
        
        result = simulator.execute(tool_call)
        
        assert result.success is False
        assert "Unknown tool" in result.content


class TestEventLogging:
    """Tests for event logging functionality."""
    
    def test_events_logged_for_tool_call(self):
        """Verify events are logged for each tool call."""
        simulator = create_default_simulator()
        
        tool_call = ToolCall(
            id="test_6",
            name="Read",
            arguments={"file_path": "/test/file.txt"},
        )
        
        simulator.execute(tool_call)
        
        events = simulator.get_event_log().events
        event_types = [e.event_type for e in events]
        
        assert EventType.TOOL_CALL_RECEIVED in event_types
        assert EventType.SCHEMA_VALIDATION in event_types
        assert EventType.TOOL_DISPATCH in event_types
        assert EventType.TOOL_EXECUTION_START in event_types
        assert EventType.TOOL_EXECUTION_END in event_types
        assert EventType.TOOL_RESULT_RETURNED in event_types
    
    def test_event_log_can_be_cleared(self):
        """Verify event log can be cleared."""
        simulator = create_default_simulator()
        
        tool_call = ToolCall(
            id="test_7",
            name="Read",
            arguments={"file_path": "/test/file.txt"},
        )
        
        simulator.execute(tool_call)
        assert len(simulator.get_event_log().events) > 0
        
        simulator.clear_event_log()
        assert len(simulator.get_event_log().events) == 0
    
    def test_events_for_specific_call_can_be_retrieved(self):
        """Verify events for a specific call can be filtered."""
        simulator = create_default_simulator()
        
        # Execute two different calls
        call_1 = ToolCall(id="call_1", name="Read", arguments={"file_path": "/a.txt"})
        call_2 = ToolCall(id="call_2", name="Read", arguments={"file_path": "/b.txt"})
        
        simulator.execute(call_1)
        simulator.execute(call_2)
        
        events_1 = simulator.get_event_log().get_events_for_call("call_1")
        events_2 = simulator.get_event_log().get_events_for_call("call_2")
        
        assert all(e.tool_call_id == "call_1" for e in events_1)
        assert all(e.tool_call_id == "call_2" for e in events_2)


class TestHarnessConstraints:
    """Tests for harness constraint values."""
    
    def test_shell_output_limit_is_20k(self):
        """Verify shell output limit matches measured value."""
        assert HARNESS_CONSTRAINTS.shell_output_display_limit == 20_000
    
    def test_file_read_default_lines_is_136(self):
        """Verify file read line limit matches measured value."""
        assert HARNESS_CONSTRAINTS.file_read_default_lines == 136
    
    def test_no_auto_retry(self):
        """Verify no auto-retry is configured."""
        assert HARNESS_CONSTRAINTS.auto_retry_on_failure is False
    
    def test_parallel_dispatch_enabled(self):
        """Verify parallel dispatch is enabled."""
        assert HARNESS_CONSTRAINTS.parallel_dispatch is True
    
    def test_min_parallel_calls_is_10(self):
        """Verify minimum parallel calls matches measured value."""
        assert HARNESS_CONSTRAINTS.min_parallel_calls == 10


class TestParallelExecution:
    """Tests for parallel execution (Experiment 7.12)."""
    
    def test_multiple_calls_can_execute(self):
        """Verify multiple tool calls can be executed."""
        simulator = create_default_simulator()
        
        calls = [
            ToolCall(id=f"parallel_{i}", name="Read", arguments={"file_path": f"/file_{i}.txt"})
            for i in range(5)
        ]
        
        results = simulator.execute_parallel(calls)
        
        assert len(results) == 5
        assert all(r.success for r in results)
