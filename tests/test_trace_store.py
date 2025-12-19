"""
Tests for the TraceStore module.

Tests cover:
- Append-only event semantics
- Span lifecycle (start/end)
- Parallelization support (multiple actors, links)
- Artifact storage (content-addressed, deduplication)
- Provenance relations (PROV-style)
- Video metadata handling
- Summary view generation
- TraceContext convenience API
"""

import tempfile
from datetime import UTC, datetime
from pathlib import Path

import pytest

from compymac.trace_store import (
    ArtifactStore,
    ProvenanceRelation,
    SpanKind,
    SpanStatus,
    SummaryEventLog,
    ToolProvenance,
    TraceContext,
    TraceEventType,
    TraceStore,
    VideoMetadata,
    compute_hash,
    create_trace_store,
    generate_span_id,
    generate_trace_id,
)


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def artifact_store(temp_dir):
    """Create an ArtifactStore for tests."""
    return ArtifactStore(temp_dir / "artifacts")


@pytest.fixture
def trace_store(temp_dir, artifact_store):
    """Create a TraceStore for tests."""
    return TraceStore(temp_dir / "traces.db", artifact_store)


class TestIdGeneration:
    """Test ID generation functions."""

    def test_generate_trace_id_format(self):
        trace_id = generate_trace_id()
        assert trace_id.startswith("trace-")
        assert len(trace_id) == 22

    def test_generate_span_id_format(self):
        span_id = generate_span_id()
        assert span_id.startswith("span-")
        assert len(span_id) == 17

    def test_ids_are_unique(self):
        ids = [generate_trace_id() for _ in range(100)]
        assert len(set(ids)) == 100

    def test_compute_hash_deterministic(self):
        data = b"test data"
        hash1 = compute_hash(data)
        hash2 = compute_hash(data)
        assert hash1 == hash2
        assert len(hash1) == 64


class TestArtifactStore:
    """Test content-addressed artifact storage."""

    def test_store_and_retrieve(self, artifact_store):
        data = b"test artifact data"
        artifact = artifact_store.store(data, "test", "text/plain")

        assert artifact.artifact_hash == compute_hash(data)
        assert artifact.byte_len == len(data)
        assert artifact.artifact_type == "test"

        retrieved = artifact_store.retrieve(artifact.artifact_hash)
        assert retrieved == data

    def test_deduplication(self, artifact_store):
        data = b"duplicate data"
        artifact1 = artifact_store.store(data, "test", "text/plain")
        artifact2 = artifact_store.store(data, "test", "text/plain")

        assert artifact1.artifact_hash == artifact2.artifact_hash
        assert artifact1.storage_path == artifact2.storage_path

    def test_sharding(self, artifact_store):
        data = b"sharded data"
        artifact = artifact_store.store(data, "test", "text/plain")

        path = Path(artifact.storage_path)
        assert path.parent.name == artifact.artifact_hash[:2]

    def test_exists(self, artifact_store):
        data = b"existence test"
        artifact = artifact_store.store(data, "test", "text/plain")

        assert artifact_store.exists(artifact.artifact_hash)
        assert not artifact_store.exists("nonexistent")

    def test_store_with_metadata(self, artifact_store):
        data = b"metadata test"
        metadata = {"key": "value", "number": 42}
        artifact = artifact_store.store(data, "test", "text/plain", metadata)

        assert artifact.metadata == metadata


class TestTraceStore:
    """Test the main TraceStore functionality."""

    def test_start_span(self, trace_store):
        trace_id = generate_trace_id()
        span_id = trace_store.start_span(
            trace_id=trace_id,
            kind=SpanKind.TOOL_CALL,
            name="test_tool",
            actor_id="executor",
        )

        assert span_id.startswith("span-")

        events = trace_store.get_events(trace_id=trace_id)
        assert len(events) == 1
        assert events[0].event_type == TraceEventType.SPAN_START

    def test_end_span(self, trace_store):
        trace_id = generate_trace_id()
        span_id = trace_store.start_span(
            trace_id=trace_id,
            kind=SpanKind.TOOL_CALL,
            name="test_tool",
            actor_id="executor",
        )

        trace_store.end_span(
            trace_id=trace_id,
            span_id=span_id,
            status=SpanStatus.OK,
        )

        events = trace_store.get_events(trace_id=trace_id)
        assert len(events) == 2
        assert events[0].event_type == TraceEventType.SPAN_START
        assert events[1].event_type == TraceEventType.SPAN_END

    def test_reconstruct_span(self, trace_store):
        trace_id = generate_trace_id()
        span_id = trace_store.start_span(
            trace_id=trace_id,
            kind=SpanKind.LLM_CALL,
            name="chat_completion",
            actor_id="manager",
            attributes={"model": "qwen3-next-80b"},
        )

        trace_store.end_span(
            trace_id=trace_id,
            span_id=span_id,
            status=SpanStatus.OK,
        )

        span = trace_store.reconstruct_span(trace_id, span_id)
        assert span is not None
        assert span.kind == SpanKind.LLM_CALL
        assert span.name == "chat_completion"
        assert span.actor_id == "manager"
        assert span.status == SpanStatus.OK
        assert span.attributes["model"] == "qwen3-next-80b"
        assert span.duration_ms is not None
        assert span.duration_ms >= 0

    def test_parent_child_spans(self, trace_store):
        trace_id = generate_trace_id()

        parent_span_id = trace_store.start_span(
            trace_id=trace_id,
            kind=SpanKind.AGENT_TURN,
            name="turn_1",
            actor_id="manager",
        )

        child_span_id = trace_store.start_span(
            trace_id=trace_id,
            kind=SpanKind.TOOL_CALL,
            name="browser.navigate",
            actor_id="executor",
            parent_span_id=parent_span_id,
        )

        trace_store.end_span(trace_id, child_span_id, SpanStatus.OK)
        trace_store.end_span(trace_id, parent_span_id, SpanStatus.OK)

        child = trace_store.reconstruct_span(trace_id, child_span_id)
        assert child.parent_span_id == parent_span_id

    def test_span_with_error(self, trace_store):
        trace_id = generate_trace_id()
        span_id = trace_store.start_span(
            trace_id=trace_id,
            kind=SpanKind.TOOL_CALL,
            name="failing_tool",
            actor_id="executor",
        )

        trace_store.end_span(
            trace_id=trace_id,
            span_id=span_id,
            status=SpanStatus.ERROR,
            error_class="TimeoutError",
            error_message="Tool execution timed out after 60s",
        )

        span = trace_store.reconstruct_span(trace_id, span_id)
        assert span.status == SpanStatus.ERROR
        assert span.error_class == "TimeoutError"
        assert span.error_message == "Tool execution timed out after 60s"

    def test_tool_provenance(self, trace_store):
        trace_id = generate_trace_id()
        provenance = ToolProvenance(
            tool_name="browser.navigate",
            schema_hash="abc123",
            impl_version="4ed1458",
            external_fingerprint={
                "playwright_version": "1.40.0",
                "browser": "chromium",
            },
        )

        span_id = trace_store.start_span(
            trace_id=trace_id,
            kind=SpanKind.TOOL_CALL,
            name="browser.navigate",
            actor_id="executor",
            tool_provenance=provenance,
        )

        trace_store.end_span(trace_id, span_id, SpanStatus.OK)

        span = trace_store.reconstruct_span(trace_id, span_id)
        assert span.tool_provenance is not None
        assert span.tool_provenance.tool_name == "browser.navigate"
        assert span.tool_provenance.schema_hash == "abc123"
        assert span.tool_provenance.external_fingerprint["playwright_version"] == "1.40.0"


class TestParallelization:
    """Test parallelization support."""

    def test_multiple_actors(self, trace_store):
        trace_id = generate_trace_id()

        span1 = trace_store.start_span(
            trace_id=trace_id,
            kind=SpanKind.TOOL_CALL,
            name="task_1",
            actor_id="executor-1",
        )

        span2 = trace_store.start_span(
            trace_id=trace_id,
            kind=SpanKind.TOOL_CALL,
            name="task_2",
            actor_id="executor-2",
        )

        trace_store.end_span(trace_id, span1, SpanStatus.OK)
        trace_store.end_span(trace_id, span2, SpanStatus.OK)

        spans = trace_store.get_trace_spans(trace_id)
        assert len(spans) == 2

        actors = {s.actor_id for s in spans}
        assert actors == {"executor-1", "executor-2"}

    def test_actor_sequence_numbers(self, trace_store):
        trace_id = generate_trace_id()

        for i in range(3):
            span_id = trace_store.start_span(
                trace_id=trace_id,
                kind=SpanKind.TOOL_CALL,
                name=f"task_{i}",
                actor_id="executor",
            )
            trace_store.end_span(trace_id, span_id, SpanStatus.OK)

        spans = trace_store.get_trace_spans(trace_id)
        seqs = [s.seq for s in spans]
        assert seqs == [0, 1, 2]

    def test_span_links_for_fan_in(self, trace_store):
        trace_id = generate_trace_id()

        span1 = trace_store.start_span(
            trace_id=trace_id,
            kind=SpanKind.TOOL_CALL,
            name="parallel_1",
            actor_id="executor-1",
        )
        trace_store.end_span(trace_id, span1, SpanStatus.OK)

        span2 = trace_store.start_span(
            trace_id=trace_id,
            kind=SpanKind.TOOL_CALL,
            name="parallel_2",
            actor_id="executor-2",
        )
        trace_store.end_span(trace_id, span2, SpanStatus.OK)

        aggregator_span = trace_store.start_span(
            trace_id=trace_id,
            kind=SpanKind.REASONING,
            name="aggregate_results",
            actor_id="manager",
        )

        trace_store.add_span_link(trace_id, aggregator_span, span1)
        trace_store.add_span_link(trace_id, aggregator_span, span2)

        trace_store.end_span(trace_id, aggregator_span, SpanStatus.OK)

        span = trace_store.reconstruct_span(trace_id, aggregator_span)
        assert len(span.links) == 2
        assert span1 in span.links
        assert span2 in span.links


class TestProvenance:
    """Test PROV-style provenance relations."""

    def test_used_relation(self, trace_store):
        trace_id = generate_trace_id()

        artifact = trace_store.store_artifact(
            data=b"memory content",
            artifact_type="memory",
            content_type="text/plain",
        )

        span_id = trace_store.start_span(
            trace_id=trace_id,
            kind=SpanKind.CONTEXT_ASSEMBLY,
            name="build_prompt",
            actor_id="manager",
        )

        trace_store.add_provenance(
            trace_id=trace_id,
            relation=ProvenanceRelation.USED,
            subject_span_id=span_id,
            object_artifact_hash=artifact.artifact_hash,
        )

        trace_store.end_span(trace_id, span_id, SpanStatus.OK)

    def test_was_generated_by_relation(self, trace_store):
        trace_id = generate_trace_id()

        span_id = trace_store.start_span(
            trace_id=trace_id,
            kind=SpanKind.LLM_CALL,
            name="chat_completion",
            actor_id="manager",
        )

        artifact = trace_store.store_artifact(
            data=b"LLM response content",
            artifact_type="llm_response",
            content_type="text/plain",
        )

        trace_store.add_provenance(
            trace_id=trace_id,
            relation=ProvenanceRelation.WAS_GENERATED_BY,
            subject_span_id=span_id,
            object_artifact_hash=artifact.artifact_hash,
        )

        trace_store.end_span(
            trace_id, span_id, SpanStatus.OK, output_artifact_hash=artifact.artifact_hash
        )

    def test_was_informed_by_relation(self, trace_store):
        trace_id = generate_trace_id()

        planning_span = trace_store.start_span(
            trace_id=trace_id,
            kind=SpanKind.REASONING,
            name="planning",
            actor_id="planner",
        )
        trace_store.end_span(trace_id, planning_span, SpanStatus.OK)

        execution_span = trace_store.start_span(
            trace_id=trace_id,
            kind=SpanKind.TOOL_CALL,
            name="execute_plan",
            actor_id="executor",
        )

        trace_store.add_provenance(
            trace_id=trace_id,
            relation=ProvenanceRelation.WAS_INFORMED_BY,
            subject_span_id=execution_span,
            object_span_id=planning_span,
        )

        trace_store.end_span(trace_id, execution_span, SpanStatus.OK)


class TestVideoMetadata:
    """Test video artifact handling."""

    def test_video_metadata_serialization(self):
        metadata = VideoMetadata(
            codec="h264",
            container="mp4",
            duration_ms=5000,
            resolution=(1920, 1080),
            fps=30.0,
            timebase_offset=datetime.now(UTC),
            span_id="span-abc123",
        )

        data = metadata.to_dict()
        restored = VideoMetadata.from_dict(data)

        assert restored.codec == metadata.codec
        assert restored.container == metadata.container
        assert restored.duration_ms == metadata.duration_ms
        assert restored.resolution == metadata.resolution
        assert restored.fps == metadata.fps
        assert restored.span_id == metadata.span_id

    def test_store_video(self, trace_store, temp_dir):
        video_path = temp_dir / "test.mp4"
        video_path.write_bytes(b"fake video data")

        metadata = VideoMetadata(
            codec="h264",
            container="mp4",
            duration_ms=5000,
            resolution=(1920, 1080),
            fps=30.0,
            timebase_offset=datetime.now(UTC),
            span_id="span-abc123",
        )

        artifact = trace_store.store_video(video_path, metadata)

        assert artifact.artifact_type == "video"
        assert artifact.content_type == "video/mp4"
        assert artifact.metadata["codec"] == "h264"
        assert artifact.metadata["duration_ms"] == 5000


class TestSummaryEventLog:
    """Test the derived summary view."""

    def test_get_summary(self, trace_store):
        trace_id = generate_trace_id()

        span1 = trace_store.start_span(
            trace_id=trace_id,
            kind=SpanKind.AGENT_TURN,
            name="turn_1",
            actor_id="manager",
        )
        trace_store.end_span(trace_id, span1, SpanStatus.OK)

        provenance = ToolProvenance(
            tool_name="browser.navigate",
            schema_hash="abc",
            impl_version="123",
        )
        span2 = trace_store.start_span(
            trace_id=trace_id,
            kind=SpanKind.TOOL_CALL,
            name="browser.navigate",
            actor_id="executor",
            tool_provenance=provenance,
        )
        trace_store.end_span(trace_id, span2, SpanStatus.OK)

        summary_log = SummaryEventLog(trace_store)
        summary = summary_log.get_summary(trace_id)

        assert len(summary) == 2
        assert summary[0]["kind"] == "agent_turn"
        assert summary[1]["kind"] == "tool_call"
        assert summary[1]["tool"] == "browser.navigate"
        assert "trace_ref" in summary[0]

    def test_get_tool_calls(self, trace_store):
        trace_id = generate_trace_id()

        span1 = trace_store.start_span(
            trace_id=trace_id,
            kind=SpanKind.REASONING,
            name="thinking",
            actor_id="manager",
        )
        trace_store.end_span(trace_id, span1, SpanStatus.OK)

        provenance = ToolProvenance(
            tool_name="shell.execute",
            schema_hash="def",
            impl_version="456",
        )
        span2 = trace_store.start_span(
            trace_id=trace_id,
            kind=SpanKind.TOOL_CALL,
            name="shell.execute",
            actor_id="executor",
            tool_provenance=provenance,
        )
        trace_store.end_span(trace_id, span2, SpanStatus.OK)

        summary_log = SummaryEventLog(trace_store)
        tool_calls = summary_log.get_tool_calls(trace_id)

        assert len(tool_calls) == 1
        assert tool_calls[0]["tool"] == "shell.execute"

    def test_get_errors(self, trace_store):
        trace_id = generate_trace_id()

        span1 = trace_store.start_span(
            trace_id=trace_id,
            kind=SpanKind.TOOL_CALL,
            name="success_tool",
            actor_id="executor",
        )
        trace_store.end_span(trace_id, span1, SpanStatus.OK)

        span2 = trace_store.start_span(
            trace_id=trace_id,
            kind=SpanKind.TOOL_CALL,
            name="failing_tool",
            actor_id="executor",
        )
        trace_store.end_span(
            trace_id,
            span2,
            SpanStatus.ERROR,
            error_class="ValueError",
            error_message="Invalid input",
        )

        summary_log = SummaryEventLog(trace_store)
        errors = summary_log.get_errors(trace_id)

        assert len(errors) == 1
        assert errors[0]["name"] == "failing_tool"
        assert errors[0]["error_class"] == "ValueError"


class TestTraceContext:
    """Test the TraceContext convenience API."""

    def test_automatic_parent_linking(self, trace_store):
        ctx = TraceContext(trace_store)

        ctx.start_span(SpanKind.AGENT_TURN, "turn_1", "manager")
        ctx.start_span(SpanKind.TOOL_CALL, "tool_1", "executor")
        ctx.end_span(SpanStatus.OK)
        ctx.end_span(SpanStatus.OK)

        spans = trace_store.get_trace_spans(ctx.trace_id)
        assert len(spans) == 2

        tool_span = next(s for s in spans if s.kind == SpanKind.TOOL_CALL)
        turn_span = next(s for s in spans if s.kind == SpanKind.AGENT_TURN)

        assert tool_span.parent_span_id == turn_span.span_id

    def test_store_artifact_via_context(self, trace_store):
        ctx = TraceContext(trace_store)

        artifact = ctx.store_artifact(
            data=b"test data",
            artifact_type="test",
            content_type="text/plain",
        )

        assert artifact.artifact_hash is not None
        assert trace_store.get_artifact(artifact.artifact_hash) is not None

    def test_add_provenance_via_context(self, trace_store):
        ctx = TraceContext(trace_store)

        artifact = ctx.store_artifact(b"memory", "memory", "text/plain")

        ctx.start_span(SpanKind.CONTEXT_ASSEMBLY, "build_prompt", "manager")
        ctx.add_provenance(
            ProvenanceRelation.USED,
            object_artifact_hash=artifact.artifact_hash,
        )
        ctx.end_span(SpanStatus.OK)


class TestCreateTraceStore:
    """Test the factory function."""

    def test_create_trace_store(self, temp_dir):
        trace_store, artifact_store = create_trace_store(temp_dir / "traces")

        assert (temp_dir / "traces" / "traces.db").exists()
        assert (temp_dir / "traces" / "artifacts").is_dir()

        trace_id = generate_trace_id()
        span_id = trace_store.start_span(
            trace_id=trace_id,
            kind=SpanKind.AGENT_TURN,
            name="test",
            actor_id="test",
        )
        trace_store.end_span(trace_id, span_id, SpanStatus.OK)

        spans = trace_store.get_trace_spans(trace_id)
        assert len(spans) == 1


class TestAppendOnlySemantics:
    """Test that the store maintains append-only semantics."""

    def test_events_are_immutable(self, trace_store):
        trace_id = generate_trace_id()
        span_id = trace_store.start_span(
            trace_id=trace_id,
            kind=SpanKind.TOOL_CALL,
            name="test",
            actor_id="test",
        )

        events_before = trace_store.get_events(trace_id=trace_id)
        assert len(events_before) == 1

        trace_store.end_span(trace_id, span_id, SpanStatus.OK)

        events_after = trace_store.get_events(trace_id=trace_id)
        assert len(events_after) == 2

        assert events_after[0].event_id == events_before[0].event_id
        assert events_after[0].timestamp == events_before[0].timestamp

    def test_span_reconstruction_from_events(self, trace_store):
        trace_id = generate_trace_id()
        span_id = trace_store.start_span(
            trace_id=trace_id,
            kind=SpanKind.TOOL_CALL,
            name="test",
            actor_id="test",
        )

        span_before_end = trace_store.reconstruct_span(trace_id, span_id)
        assert span_before_end.status == SpanStatus.STARTED
        assert span_before_end.end_ts is None

        trace_store.end_span(trace_id, span_id, SpanStatus.OK)

        span_after_end = trace_store.reconstruct_span(trace_id, span_id)
        assert span_after_end.status == SpanStatus.OK
        assert span_after_end.end_ts is not None
