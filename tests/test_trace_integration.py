"""
Integration tests for TraceStore with AgentLoop and LocalHarness.

These tests verify that complete execution traces are captured when
TraceContext is wired into the agent loop and harness.
"""

import json
import tempfile
from pathlib import Path

import pytest

from compymac.agent_loop import AgentConfig, AgentLoop, ScriptedPolicy
from compymac.local_harness import LocalHarness
from compymac.trace_store import (
    ArtifactStore,
    SpanKind,
    SpanStatus,
    TraceContext,
    TraceStore,
    create_trace_store,
)
from compymac.types import ToolCall


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test artifacts."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def trace_store(temp_dir: Path) -> TraceStore:
    """Create a TraceStore for testing."""
    artifact_store = ArtifactStore(temp_dir / "artifacts")
    return TraceStore(temp_dir / "traces.db", artifact_store)


@pytest.fixture
def trace_context(trace_store: TraceStore) -> TraceContext:
    """Create a TraceContext for testing."""
    return TraceContext(trace_store)


@pytest.fixture
def local_harness(temp_dir: Path, trace_context: TraceContext) -> LocalHarness:
    """Create a LocalHarness with trace context."""
    harness = LocalHarness(full_output_dir=temp_dir / "outputs")
    harness.set_trace_context(trace_context)
    return harness


class TestLocalHarnessTracing:
    """Tests for TraceStore integration with LocalHarness."""

    def test_tool_call_creates_span(
        self, local_harness: LocalHarness, trace_context: TraceContext
    ):
        """Verify that executing a tool call creates a span in the trace."""
        # Execute a simple tool call
        tool_call = ToolCall(
            id="test_call_1",
            name="Read",
            arguments={"file_path": "/etc/hostname"},
        )
        result = local_harness.execute(tool_call)

        # Verify the result
        assert result.success

        # Verify a span was created
        spans = trace_context.trace_store.get_trace_spans(trace_context.trace_id)
        assert len(spans) >= 1

        # Find the tool call span
        tool_spans = [s for s in spans if s.kind == SpanKind.TOOL_CALL]
        assert len(tool_spans) == 1

        tool_span = tool_spans[0]
        assert tool_span.name == "tool:Read"
        assert tool_span.status == SpanStatus.OK
        assert tool_span.actor_id == "harness"
        assert tool_span.input_artifact_hash is not None
        assert tool_span.output_artifact_hash is not None

    def test_tool_call_error_creates_error_span(
        self, local_harness: LocalHarness, trace_context: TraceContext
    ):
        """Verify that a failed tool call creates an error span."""
        # Execute a tool call that will fail
        tool_call = ToolCall(
            id="test_call_2",
            name="Read",
            arguments={"file_path": "/nonexistent/file/path"},
        )
        result = local_harness.execute(tool_call)

        # Verify the result failed
        assert not result.success

        # Verify an error span was created
        spans = trace_context.trace_store.get_trace_spans(trace_context.trace_id)
        tool_spans = [s for s in spans if s.kind == SpanKind.TOOL_CALL]
        assert len(tool_spans) == 1

        tool_span = tool_spans[0]
        assert tool_span.status == SpanStatus.ERROR
        assert tool_span.error_class is not None
        assert tool_span.error_message is not None

    def test_multiple_tool_calls_create_multiple_spans(
        self, local_harness: LocalHarness, trace_context: TraceContext, temp_dir: Path
    ):
        """Verify that multiple tool calls create multiple spans."""
        # Create a test file
        test_file = temp_dir / "test.txt"
        test_file.write_text("Hello, World!")

        # Execute multiple tool calls
        tool_calls = [
            ToolCall(id="call_1", name="Read", arguments={"file_path": str(test_file)}),
            ToolCall(
                id="call_2",
                name="Write",
                arguments={"file_path": str(temp_dir / "output.txt"), "content": "Test"},
            ),
            ToolCall(
                id="call_3", name="Read", arguments={"file_path": str(temp_dir / "output.txt")}
            ),
        ]

        for tool_call in tool_calls:
            local_harness.execute(tool_call)

        # Verify spans were created
        spans = trace_context.trace_store.get_trace_spans(trace_context.trace_id)
        tool_spans = [s for s in spans if s.kind == SpanKind.TOOL_CALL]
        assert len(tool_spans) == 3

        # Verify each span has unique ID
        span_ids = [s.span_id for s in tool_spans]
        assert len(set(span_ids)) == 3

    def test_tool_provenance_captured(
        self, local_harness: LocalHarness, trace_context: TraceContext
    ):
        """Verify that tool provenance is captured in spans."""
        tool_call = ToolCall(
            id="test_call_prov",
            name="Read",
            arguments={"file_path": "/etc/hostname"},
        )
        local_harness.execute(tool_call)

        spans = trace_context.trace_store.get_trace_spans(trace_context.trace_id)
        tool_spans = [s for s in spans if s.kind == SpanKind.TOOL_CALL]
        assert len(tool_spans) == 1

        tool_span = tool_spans[0]
        assert tool_span.tool_provenance is not None
        assert tool_span.tool_provenance.tool_name == "Read"
        assert tool_span.tool_provenance.schema_hash is not None
        assert len(tool_span.tool_provenance.schema_hash) == 16

    def test_artifacts_stored_and_retrievable(
        self, local_harness: LocalHarness, trace_context: TraceContext, temp_dir: Path
    ):
        """Verify that input/output artifacts are stored and retrievable."""
        test_file = temp_dir / "artifact_test.txt"
        test_file.write_text("Artifact test content")

        tool_call = ToolCall(
            id="test_artifact",
            name="Read",
            arguments={"file_path": str(test_file)},
        )
        local_harness.execute(tool_call)

        spans = trace_context.trace_store.get_trace_spans(trace_context.trace_id)
        tool_spans = [s for s in spans if s.kind == SpanKind.TOOL_CALL]
        assert len(tool_spans) == 1

        tool_span = tool_spans[0]

        # Verify input artifact
        assert tool_span.input_artifact_hash is not None
        input_data = trace_context.trace_store.get_artifact_data(tool_span.input_artifact_hash)
        assert input_data is not None
        input_json = json.loads(input_data.decode())
        assert input_json["file_path"] == str(test_file)

        # Verify output artifact
        assert tool_span.output_artifact_hash is not None
        output_data = trace_context.trace_store.get_artifact_data(tool_span.output_artifact_hash)
        assert output_data is not None
        assert b"Artifact test content" in output_data


class TestAgentLoopTracing:
    """Tests for TraceStore integration with AgentLoop."""

    def test_agent_loop_with_trace_context(
        self, local_harness: LocalHarness, trace_context: TraceContext, temp_dir: Path
    ):
        """Verify that AgentLoop creates spans when trace context is provided."""
        # Create agent loop with trace context
        config = AgentConfig(max_steps=5)
        loop = AgentLoop(
            harness=local_harness,
            llm_client=None,  # We'll use a policy instead
            config=config,
            trace_context=trace_context,
        )

        # Create a test file
        test_file = temp_dir / "agent_test.txt"
        test_file.write_text("Agent test content")

        # Use a scripted policy to execute tool calls
        policy = ScriptedPolicy(
            tool_calls=[
                ToolCall(id="agent_call_1", name="Read", arguments={"file_path": str(test_file)}),
            ],
            final_response="Done reading file",
        )

        # Run with policy
        loop.run_with_policy(policy, "Read the test file")

        # Verify spans were created
        spans = trace_context.trace_store.get_trace_spans(trace_context.trace_id)
        assert len(spans) >= 1

        # Should have tool call span from harness
        tool_spans = [s for s in spans if s.kind == SpanKind.TOOL_CALL]
        assert len(tool_spans) == 1

    def test_agent_loop_with_trace_base_path(self, temp_dir: Path):
        """Verify that AgentLoop creates TraceStore when trace_base_path is provided."""
        harness = LocalHarness(full_output_dir=temp_dir / "outputs")

        config = AgentConfig(
            max_steps=5,
            trace_base_path=temp_dir / "traces",
        )
        loop = AgentLoop(
            harness=harness,
            llm_client=None,
            config=config,
        )

        # Verify trace context was created
        assert loop._trace_context is not None
        assert loop._trace_store is not None

        # Verify harness has trace context
        assert harness.get_trace_context() is not None


class TestCreateTraceStore:
    """Tests for the create_trace_store factory function."""

    def test_create_trace_store_creates_directory(self, temp_dir: Path):
        """Verify that create_trace_store creates the base directory."""
        base_path = temp_dir / "new_traces"
        assert not base_path.exists()

        trace_store, artifact_store = create_trace_store(base_path)

        assert base_path.exists()
        assert (base_path / "traces.db").exists()
        assert (base_path / "artifacts").exists()

    def test_create_trace_store_returns_working_stores(self, temp_dir: Path):
        """Verify that created stores are functional."""
        trace_store, artifact_store = create_trace_store(temp_dir / "functional_test")

        # Test artifact store
        artifact = artifact_store.store(
            data=b"test data",
            artifact_type="test",
            content_type="text/plain",
        )
        assert artifact.artifact_hash is not None
        assert artifact_store.exists(artifact.artifact_hash)

        # Test trace store
        span_id = trace_store.start_span(
            trace_id="test-trace",
            kind=SpanKind.TOOL_CALL,
            name="test_span",
            actor_id="test",
        )
        assert span_id is not None
        assert span_id.startswith("span-")


class TestTraceContextIntegration:
    """Tests for TraceContext convenience API integration."""

    def test_trace_context_span_stack(self, trace_store: TraceStore):
        """Verify that TraceContext maintains proper span stack."""
        ctx = TraceContext(trace_store)

        # Start nested spans
        span1 = ctx.start_span(SpanKind.AGENT_TURN, "turn1", "agent")
        span2 = ctx.start_span(SpanKind.LLM_CALL, "llm1", "llm")
        span3 = ctx.start_span(SpanKind.TOOL_CALL, "tool1", "harness")

        # Verify stack
        assert ctx.current_span_id == span3

        # End spans in order
        ctx.end_span(SpanStatus.OK)
        assert ctx.current_span_id == span2

        ctx.end_span(SpanStatus.OK)
        assert ctx.current_span_id == span1

        ctx.end_span(SpanStatus.OK)
        assert ctx.current_span_id is None

        # Verify all spans were recorded
        spans = trace_store.get_trace_spans(ctx.trace_id)
        assert len(spans) == 3

    def test_trace_context_parent_linking(self, trace_store: TraceStore):
        """Verify that TraceContext automatically links parent spans."""
        ctx = TraceContext(trace_store)

        # Start nested spans
        parent_span = ctx.start_span(SpanKind.AGENT_TURN, "parent", "agent")
        child_span = ctx.start_span(SpanKind.TOOL_CALL, "child", "harness")

        # End spans
        ctx.end_span(SpanStatus.OK)
        ctx.end_span(SpanStatus.OK)

        # Verify parent linking
        spans = trace_store.get_trace_spans(ctx.trace_id)
        child = next(s for s in spans if s.span_id == child_span)
        assert child.parent_span_id == parent_span


class TestEndToEndTracing:
    """End-to-end tests for complete execution tracing."""

    def test_complete_execution_trace(self, temp_dir: Path):
        """Verify complete execution trace from agent loop through harness."""
        # Set up tracing
        trace_store, artifact_store = create_trace_store(temp_dir / "e2e_traces")
        trace_context = TraceContext(trace_store)

        # Set up harness with tracing
        harness = LocalHarness(full_output_dir=temp_dir / "outputs")
        harness.set_trace_context(trace_context)

        # Create test file
        test_file = temp_dir / "e2e_test.txt"
        test_file.write_text("End-to-end test content")

        # Set up agent loop with tracing
        config = AgentConfig(max_steps=5)
        loop = AgentLoop(
            harness=harness,
            llm_client=None,
            config=config,
            trace_context=trace_context,
        )

        # Execute with policy
        policy = ScriptedPolicy(
            tool_calls=[
                ToolCall(id="e2e_1", name="Read", arguments={"file_path": str(test_file)}),
                ToolCall(
                    id="e2e_2",
                    name="Write",
                    arguments={"file_path": str(temp_dir / "e2e_output.txt"), "content": "Output"},
                ),
            ],
            final_response="Completed end-to-end test",
        )

        loop.run_with_policy(policy, "Run end-to-end test")

        # Verify complete trace
        spans = trace_store.get_trace_spans(trace_context.trace_id)

        # Should have tool call spans
        tool_spans = [s for s in spans if s.kind == SpanKind.TOOL_CALL]
        assert len(tool_spans) == 2

        # Verify all spans have required fields
        for span in spans:
            assert span.span_id is not None
            assert span.trace_id == trace_context.trace_id
            assert span.start_ts is not None
            assert span.end_ts is not None
            assert span.status in (SpanStatus.OK, SpanStatus.ERROR)
            assert span.actor_id is not None

        # Verify artifacts were stored
        for tool_span in tool_spans:
            assert tool_span.input_artifact_hash is not None
            assert tool_span.output_artifact_hash is not None

            # Verify artifacts are retrievable
            input_data = trace_store.get_artifact_data(tool_span.input_artifact_hash)
            output_data = trace_store.get_artifact_data(tool_span.output_artifact_hash)
            assert input_data is not None
            assert output_data is not None
