"""
TraceStore - Foundational observability module for complete agent execution capture.

This module implements a three-layer observability architecture:
1. EventLog (summary) - Derived view for quick overview
2. TraceStore (source of truth) - OTel-style spans + PROV lineage
3. ArtifactStore (blobs) - Content-addressed storage for large payloads

Design principles:
- APPEND-ONLY: All events are immutable, spans use START/END events
- PARALLELIZATION: trace_id/span_id/parent_span_id/links support concurrency
- TOOL PROVENANCE: schema_hash, impl_version, external_fingerprint for drift detection
- 100% CAPTURE: Every tool call, response, LLM request, and main loop iteration

Based on:
- PROV-AGENT (Oak Ridge National Lab) - W3C PROV standard for agent workflows
- AgentSight (UC Santa Cruz) - Boundary tracing for semantic gap bridging
- OpenTelemetry - Distributed tracing semantics
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any


def generate_id() -> str:
    """Generate a unique ID using UUID4."""
    return str(uuid.uuid4())


def generate_trace_id() -> str:
    """Generate a trace ID (groups all events in one run)."""
    return f"trace-{uuid.uuid4().hex[:16]}"


def generate_span_id() -> str:
    """Generate a span ID (single unit of work)."""
    return f"span-{uuid.uuid4().hex[:12]}"


def compute_hash(data: bytes) -> str:
    """Compute SHA-256 hash of data."""
    return hashlib.sha256(data).hexdigest()


class SpanKind(str, Enum):
    """Types of spans in the trace."""
    AGENT_TURN = "agent_turn"
    LLM_CALL = "llm_call"
    TOOL_CALL = "tool_call"
    REASONING = "reasoning"
    STATE_CHANGE = "state_change"
    ARTIFACT_CAPTURE = "artifact"
    BROWSER_SESSION = "browser_session"
    MEMORY_OPERATION = "memory_operation"
    CONTEXT_ASSEMBLY = "context_assembly"


class SpanStatus(str, Enum):
    """Status of a span."""
    STARTED = "started"
    OK = "ok"
    ERROR = "error"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


class TraceEventType(str, Enum):
    """Types of trace events (append-only)."""
    SPAN_START = "span_start"
    SPAN_END = "span_end"
    SPAN_ATTRIBUTE = "span_attribute"
    SPAN_LINK = "span_link"
    ARTIFACT_CREATED = "artifact_created"
    PROVENANCE_RELATION = "provenance_relation"


class ProvenanceRelation(str, Enum):
    """W3C PROV-style relations for lineage tracking."""
    USED = "used"
    WAS_GENERATED_BY = "wasGeneratedBy"
    WAS_DERIVED_FROM = "wasDerivedFrom"
    WAS_ATTRIBUTED_TO = "wasAttributedTo"
    WAS_INFORMED_BY = "wasInformedBy"


class CheckpointStatus(str, Enum):
    """Status of a checkpoint."""
    ACTIVE = "active"
    RESUMED = "resumed"
    FORKED = "forked"
    ARCHIVED = "archived"


@dataclass
class CognitiveEvent:
    """Represents a metacognitive event in agent execution (V5).

    Cognitive events capture the agent's reasoning, temptation awareness,
    and decision points. These are distinct from tool calls - they represent
    the agent's internal cognitive processes.

    Event types:
    - "think": Private reasoning via <think> tool
    - "temptation_awareness": Agent recognized a cognitive shortcut temptation
    - "decision_point": Agent made a deliberate choice between alternatives
    - "reflection": Agent reflected on past actions or outcomes
    """

    event_type: str  # "think", "temptation_awareness", "decision_point", "reflection"
    timestamp: float
    phase: str | None  # SWEPhase value or None if not in SWE mode
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "event_type": self.event_type,
            "timestamp": self.timestamp,
            "phase": self.phase,
            "content": self.content,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CognitiveEvent":
        """Create from dictionary."""
        return cls(
            event_type=data["event_type"],
            timestamp=data["timestamp"],
            phase=data.get("phase"),
            content=data["content"],
            metadata=data.get("metadata", {}),
        )


@dataclass
class ToolProvenance:
    """Provenance information for tool invocations."""
    tool_name: str
    schema_hash: str
    impl_version: str
    external_fingerprint: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "schema_hash": self.schema_hash,
            "impl_version": self.impl_version,
            "external_fingerprint": self.external_fingerprint,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ToolProvenance:
        return cls(
            tool_name=data["tool_name"],
            schema_hash=data["schema_hash"],
            impl_version=data["impl_version"],
            external_fingerprint=data.get("external_fingerprint", {}),
        )


@dataclass
class VideoMetadata:
    """Sidecar metadata for video artifacts."""
    codec: str
    container: str
    duration_ms: int
    resolution: tuple[int, int]
    fps: float
    timebase_offset: datetime
    span_id: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "codec": self.codec,
            "container": self.container,
            "duration_ms": self.duration_ms,
            "resolution": list(self.resolution),
            "fps": self.fps,
            "timebase_offset": self.timebase_offset.isoformat(),
            "span_id": self.span_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> VideoMetadata:
        return cls(
            codec=data["codec"],
            container=data["container"],
            duration_ms=data["duration_ms"],
            resolution=tuple(data["resolution"]),
            fps=data["fps"],
            timebase_offset=datetime.fromisoformat(data["timebase_offset"]),
            span_id=data["span_id"],
        )


@dataclass
class TraceEvent:
    """
    A single immutable event in the trace store.

    Events are append-only - spans are represented as START/END event pairs
    rather than mutable rows. This preserves auditability.
    """
    event_id: str
    timestamp: datetime
    event_type: TraceEventType
    trace_id: str
    span_id: str
    data: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp.isoformat(),
            "event_type": self.event_type.value,
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "data": self.data,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TraceEvent:
        return cls(
            event_id=data["event_id"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            event_type=TraceEventType(data["event_type"]),
            trace_id=data["trace_id"],
            span_id=data["span_id"],
            data=data["data"],
        )


@dataclass
class Span:
    """
    Reconstructed span from START/END events.

    This is a convenience view - the source of truth is the events.
    """
    span_id: str
    trace_id: str
    parent_span_id: str | None
    kind: SpanKind
    name: str
    actor_id: str
    seq: int
    start_ts: datetime
    end_ts: datetime | None
    status: SpanStatus
    attributes: dict[str, Any]
    links: list[str]
    tool_provenance: ToolProvenance | None
    input_artifact_hash: str | None
    output_artifact_hash: str | None
    error_class: str | None
    error_message: str | None

    @property
    def duration_ms(self) -> int | None:
        if self.end_ts is None:
            return None
        delta = self.end_ts - self.start_ts
        return int(delta.total_seconds() * 1000)

    def to_dict(self) -> dict[str, Any]:
        return {
            "span_id": self.span_id,
            "trace_id": self.trace_id,
            "parent_span_id": self.parent_span_id,
            "kind": self.kind.value,
            "name": self.name,
            "actor_id": self.actor_id,
            "seq": self.seq,
            "start_ts": self.start_ts.isoformat(),
            "end_ts": self.end_ts.isoformat() if self.end_ts else None,
            "duration_ms": self.duration_ms,
            "status": self.status.value,
            "attributes": self.attributes,
            "links": self.links,
            "tool_provenance": self.tool_provenance.to_dict() if self.tool_provenance else None,
            "input_artifact_hash": self.input_artifact_hash,
            "output_artifact_hash": self.output_artifact_hash,
            "error_class": self.error_class,
            "error_message": self.error_message,
        }


@dataclass
class Checkpoint:
    """
    A checkpoint captures the complete agent state at a point in time.

    Checkpoints enable:
    - Pause/resume: Stop execution and continue later
    - Time-travel: Navigate backward and forward through execution
    - Forking: Create alternative execution branches from any point
    """
    checkpoint_id: str
    trace_id: str
    created_ts: datetime
    status: CheckpointStatus
    step_number: int
    description: str
    state_artifact_hash: str  # Points to serialized agent state
    parent_checkpoint_id: str | None = None  # For forked checkpoints
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "checkpoint_id": self.checkpoint_id,
            "trace_id": self.trace_id,
            "created_ts": self.created_ts.isoformat(),
            "status": self.status.value,
            "step_number": self.step_number,
            "description": self.description,
            "state_artifact_hash": self.state_artifact_hash,
            "parent_checkpoint_id": self.parent_checkpoint_id,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Checkpoint:
        return cls(
            checkpoint_id=data["checkpoint_id"],
            trace_id=data["trace_id"],
            created_ts=datetime.fromisoformat(data["created_ts"]),
            status=CheckpointStatus(data["status"]),
            step_number=data["step_number"],
            description=data["description"],
            state_artifact_hash=data["state_artifact_hash"],
            parent_checkpoint_id=data.get("parent_checkpoint_id"),
            metadata=data.get("metadata", {}),
        )


@dataclass
class SessionOverview:
    """
    High-level summary of a session for quick overview.

    This is the "overview" view that can be expanded into full detail.
    """
    trace_id: str
    start_ts: datetime
    end_ts: datetime | None
    status: str
    total_steps: int
    total_llm_calls: int
    total_tool_calls: int
    total_tokens: int
    checkpoints_available: int
    current_step: str
    key_milestones: list[dict[str, Any]]
    errors: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "start_ts": self.start_ts.isoformat(),
            "end_ts": self.end_ts.isoformat() if self.end_ts else None,
            "status": self.status,
            "total_steps": self.total_steps,
            "total_llm_calls": self.total_llm_calls,
            "total_tool_calls": self.total_tool_calls,
            "total_tokens": self.total_tokens,
            "checkpoints_available": self.checkpoints_available,
            "current_step": self.current_step,
            "key_milestones": self.key_milestones,
            "errors": self.errors,
        }


@dataclass
class Artifact:
    """
    Content-addressed artifact in the artifact store.
    """
    artifact_hash: str
    artifact_type: str
    content_type: str
    byte_len: int
    storage_path: str
    created_ts: datetime
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_hash": self.artifact_hash,
            "artifact_type": self.artifact_type,
            "content_type": self.content_type,
            "byte_len": self.byte_len,
            "storage_path": self.storage_path,
            "created_ts": self.created_ts.isoformat(),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Artifact:
        return cls(
            artifact_hash=data["artifact_hash"],
            artifact_type=data["artifact_type"],
            content_type=data["content_type"],
            byte_len=data["byte_len"],
            storage_path=data["storage_path"],
            created_ts=datetime.fromisoformat(data["created_ts"]),
            metadata=data.get("metadata", {}),
        )


class ArtifactStore:
    """
    Content-addressed storage for large payloads.

    Artifacts are stored by SHA-256 hash, enabling deduplication across runs.
    """

    def __init__(self, base_path: Path):
        self.base_path = base_path
        self.base_path.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def _get_artifact_path(self, artifact_hash: str) -> Path:
        """Get the storage path for an artifact (sharded by first 2 chars)."""
        shard = artifact_hash[:2]
        shard_dir = self.base_path / shard
        shard_dir.mkdir(exist_ok=True)
        return shard_dir / artifact_hash

    def store(
        self,
        data: bytes,
        artifact_type: str,
        content_type: str,
        metadata: dict[str, Any] | None = None,
    ) -> Artifact:
        """Store data and return artifact metadata."""
        artifact_hash = compute_hash(data)

        with self._lock:
            path = self._get_artifact_path(artifact_hash)

            if not path.exists():
                path.write_bytes(data)

            artifact = Artifact(
                artifact_hash=artifact_hash,
                artifact_type=artifact_type,
                content_type=content_type,
                byte_len=len(data),
                storage_path=str(path),
                created_ts=datetime.now(UTC),
                metadata=metadata or {},
            )

        return artifact

    def store_file(
        self,
        file_path: Path,
        artifact_type: str,
        content_type: str,
        metadata: dict[str, Any] | None = None,
    ) -> Artifact:
        """Store a file and return artifact metadata."""
        data = file_path.read_bytes()
        return self.store(data, artifact_type, content_type, metadata)

    def retrieve(self, artifact_hash: str) -> bytes | None:
        """Retrieve artifact data by hash."""
        path = self._get_artifact_path(artifact_hash)
        if path.exists():
            return path.read_bytes()
        return None

    def exists(self, artifact_hash: str) -> bool:
        """Check if artifact exists."""
        return self._get_artifact_path(artifact_hash).exists()


class TraceStore:
    """
    Source of truth for agent execution traces.

    Uses SQLite for structured data with append-only semantics.
    Spans are represented as START/END event pairs for auditability.
    """

    def __init__(self, db_path: Path, artifact_store: ArtifactStore):
        self.db_path = db_path
        self.artifact_store = artifact_store
        self._lock = threading.Lock()
        self._actor_seq: dict[str, int] = {}
        self._init_db()

    def _init_db(self) -> None:
        """Initialize the database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS trace_events (
                    event_id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    trace_id TEXT NOT NULL,
                    span_id TEXT NOT NULL,
                    data TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_trace_events_trace_id
                    ON trace_events(trace_id);
                CREATE INDEX IF NOT EXISTS idx_trace_events_span_id
                    ON trace_events(span_id);
                CREATE INDEX IF NOT EXISTS idx_trace_events_timestamp
                    ON trace_events(timestamp);
                CREATE INDEX IF NOT EXISTS idx_trace_events_type
                    ON trace_events(event_type);

                CREATE TABLE IF NOT EXISTS artifacts (
                    artifact_hash TEXT PRIMARY KEY,
                    artifact_type TEXT NOT NULL,
                    content_type TEXT NOT NULL,
                    byte_len INTEGER NOT NULL,
                    storage_path TEXT NOT NULL,
                    created_ts TEXT NOT NULL,
                    metadata TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS provenance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trace_id TEXT NOT NULL,
                    relation TEXT NOT NULL,
                    subject_span_id TEXT NOT NULL,
                    object_span_id TEXT,
                    object_artifact_hash TEXT,
                    timestamp TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_provenance_trace_id
                    ON provenance(trace_id);
                CREATE INDEX IF NOT EXISTS idx_provenance_subject
                    ON provenance(subject_span_id);

                -- Checkpoints table for pause/resume/time-travel
                CREATE TABLE IF NOT EXISTS checkpoints (
                    checkpoint_id TEXT PRIMARY KEY,
                    trace_id TEXT NOT NULL,
                    created_ts TEXT NOT NULL,
                    status TEXT NOT NULL,
                    step_number INTEGER NOT NULL,
                    description TEXT NOT NULL,
                    state_artifact_hash TEXT NOT NULL,
                    parent_checkpoint_id TEXT,
                    metadata TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_checkpoints_trace_id
                    ON checkpoints(trace_id);
                CREATE INDEX IF NOT EXISTS idx_checkpoints_status
                    ON checkpoints(status);
                CREATE INDEX IF NOT EXISTS idx_checkpoints_step
                    ON checkpoints(step_number);

                -- V5: Cognitive events table for metacognitive tracking
                CREATE TABLE IF NOT EXISTS cognitive_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trace_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    phase TEXT,
                    content TEXT NOT NULL,
                    metadata TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_cognitive_events_trace_id
                    ON cognitive_events(trace_id);
                CREATE INDEX IF NOT EXISTS idx_cognitive_events_type
                    ON cognitive_events(event_type);
                CREATE INDEX IF NOT EXISTS idx_cognitive_events_timestamp
                    ON cognitive_events(timestamp);
            """)

    def _next_seq(self, actor_id: str) -> int:
        """Get next sequence number for an actor."""
        with self._lock:
            seq = self._actor_seq.get(actor_id, 0)
            self._actor_seq[actor_id] = seq + 1
            return seq

    def _append_event(self, event: TraceEvent) -> None:
        """Append an event to the trace store."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO trace_events (event_id, timestamp, event_type, trace_id, span_id, data)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    event.event_id,
                    event.timestamp.isoformat(),
                    event.event_type.value,
                    event.trace_id,
                    event.span_id,
                    json.dumps(event.data),
                ),
            )

    def start_span(
        self,
        trace_id: str,
        kind: SpanKind,
        name: str,
        actor_id: str,
        parent_span_id: str | None = None,
        attributes: dict[str, Any] | None = None,
        tool_provenance: ToolProvenance | None = None,
        input_artifact_hash: str | None = None,
    ) -> str:
        """
        Start a new span and return its ID.

        This appends a SPAN_START event to the trace.
        """
        span_id = generate_span_id()
        seq = self._next_seq(actor_id)

        event = TraceEvent(
            event_id=generate_id(),
            timestamp=datetime.now(UTC),
            event_type=TraceEventType.SPAN_START,
            trace_id=trace_id,
            span_id=span_id,
            data={
                "kind": kind.value,
                "name": name,
                "actor_id": actor_id,
                "seq": seq,
                "parent_span_id": parent_span_id,
                "attributes": attributes or {},
                "tool_provenance": tool_provenance.to_dict() if tool_provenance else None,
                "input_artifact_hash": input_artifact_hash,
                "links": [],
            },
        )

        self._append_event(event)
        return span_id

    def end_span(
        self,
        trace_id: str,
        span_id: str,
        status: SpanStatus,
        output_artifact_hash: str | None = None,
        error_class: str | None = None,
        error_message: str | None = None,
        additional_attributes: dict[str, Any] | None = None,
    ) -> None:
        """
        End a span.

        This appends a SPAN_END event to the trace.
        """
        event = TraceEvent(
            event_id=generate_id(),
            timestamp=datetime.now(UTC),
            event_type=TraceEventType.SPAN_END,
            trace_id=trace_id,
            span_id=span_id,
            data={
                "status": status.value,
                "output_artifact_hash": output_artifact_hash,
                "error_class": error_class,
                "error_message": error_message,
                "additional_attributes": additional_attributes or {},
            },
        )

        self._append_event(event)

    def add_span_link(
        self,
        trace_id: str,
        span_id: str,
        linked_span_id: str,
    ) -> None:
        """
        Add a link from one span to another (for fan-in scenarios).
        """
        event = TraceEvent(
            event_id=generate_id(),
            timestamp=datetime.now(UTC),
            event_type=TraceEventType.SPAN_LINK,
            trace_id=trace_id,
            span_id=span_id,
            data={"linked_span_id": linked_span_id},
        )

        self._append_event(event)

    def add_provenance(
        self,
        trace_id: str,
        relation: ProvenanceRelation,
        subject_span_id: str,
        object_span_id: str | None = None,
        object_artifact_hash: str | None = None,
    ) -> None:
        """
        Add a PROV-style provenance relation.

        Examples:
        - span USED artifact (retrieved memory)
        - artifact WAS_GENERATED_BY span (LLM output)
        - span WAS_INFORMED_BY span (dependency)
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO provenance (trace_id, relation, subject_span_id, object_span_id, object_artifact_hash, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    trace_id,
                    relation.value,
                    subject_span_id,
                    object_span_id,
                    object_artifact_hash,
                    datetime.now(UTC).isoformat(),
                ),
            )

    def store_artifact(
        self,
        data: bytes,
        artifact_type: str,
        content_type: str,
        metadata: dict[str, Any] | None = None,
    ) -> Artifact:
        """Store an artifact and record it in the database."""
        artifact = self.artifact_store.store(data, artifact_type, content_type, metadata)

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO artifacts (artifact_hash, artifact_type, content_type, byte_len, storage_path, created_ts, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    artifact.artifact_hash,
                    artifact.artifact_type,
                    artifact.content_type,
                    artifact.byte_len,
                    artifact.storage_path,
                    artifact.created_ts.isoformat(),
                    json.dumps(artifact.metadata),
                ),
            )

        return artifact

    def store_video(
        self,
        video_path: Path,
        video_metadata: VideoMetadata,
    ) -> Artifact:
        """Store a video artifact with sidecar metadata."""
        data = video_path.read_bytes()
        artifact = self.store_artifact(
            data=data,
            artifact_type="video",
            content_type=f"video/{video_metadata.container}",
            metadata=video_metadata.to_dict(),
        )
        return artifact

    def store_playwright_trace(
        self,
        trace_path: Path,
        span_id: str,
    ) -> Artifact:
        """Store a Playwright trace.zip as-is."""
        data = trace_path.read_bytes()
        artifact = self.store_artifact(
            data=data,
            artifact_type="playwright_trace",
            content_type="application/zip",
            metadata={"span_id": span_id},
        )
        return artifact

    def get_events(
        self,
        trace_id: str | None = None,
        span_id: str | None = None,
        event_type: TraceEventType | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int | None = None,
    ) -> list[TraceEvent]:
        """Query events with optional filters."""
        query = "SELECT event_id, timestamp, event_type, trace_id, span_id, data FROM trace_events WHERE 1=1"
        params: list[Any] = []

        if trace_id:
            query += " AND trace_id = ?"
            params.append(trace_id)
        if span_id:
            query += " AND span_id = ?"
            params.append(span_id)
        if event_type:
            query += " AND event_type = ?"
            params.append(event_type.value)
        if since:
            query += " AND timestamp >= ?"
            params.append(since.isoformat())
        if until:
            query += " AND timestamp <= ?"
            params.append(until.isoformat())

        query += " ORDER BY timestamp ASC"

        if limit:
            query += " LIMIT ?"
            params.append(limit)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()

        return [
            TraceEvent(
                event_id=row[0],
                timestamp=datetime.fromisoformat(row[1]),
                event_type=TraceEventType(row[2]),
                trace_id=row[3],
                span_id=row[4],
                data=json.loads(row[5]),
            )
            for row in rows
        ]

    def reconstruct_span(self, trace_id: str, span_id: str) -> Span | None:
        """Reconstruct a span from its START/END events."""
        events = self.get_events(trace_id=trace_id, span_id=span_id)

        start_event = None
        end_event = None
        links: list[str] = []
        additional_attrs: dict[str, Any] = {}

        for event in events:
            if event.event_type == TraceEventType.SPAN_START:
                start_event = event
            elif event.event_type == TraceEventType.SPAN_END:
                end_event = event
            elif event.event_type == TraceEventType.SPAN_LINK:
                links.append(event.data["linked_span_id"])
            elif event.event_type == TraceEventType.SPAN_ATTRIBUTE:
                additional_attrs.update(event.data.get("attributes", {}))

        if start_event is None:
            return None

        start_data = start_event.data
        tool_prov = None
        if start_data.get("tool_provenance"):
            tool_prov = ToolProvenance.from_dict(start_data["tool_provenance"])

        attributes = start_data.get("attributes", {})
        attributes.update(additional_attrs)

        return Span(
            span_id=span_id,
            trace_id=trace_id,
            parent_span_id=start_data.get("parent_span_id"),
            kind=SpanKind(start_data["kind"]),
            name=start_data["name"],
            actor_id=start_data["actor_id"],
            seq=start_data["seq"],
            start_ts=start_event.timestamp,
            end_ts=end_event.timestamp if end_event else None,
            status=SpanStatus(end_event.data["status"]) if end_event else SpanStatus.STARTED,
            attributes=attributes,
            links=links + start_data.get("links", []),
            tool_provenance=tool_prov,
            input_artifact_hash=start_data.get("input_artifact_hash"),
            output_artifact_hash=end_event.data.get("output_artifact_hash") if end_event else None,
            error_class=end_event.data.get("error_class") if end_event else None,
            error_message=end_event.data.get("error_message") if end_event else None,
        )

    def get_trace_spans(self, trace_id: str) -> list[Span]:
        """Get all spans for a trace."""
        events = self.get_events(trace_id=trace_id, event_type=TraceEventType.SPAN_START)
        span_ids = [e.span_id for e in events]

        spans = []
        for span_id in span_ids:
            span = self.reconstruct_span(trace_id, span_id)
            if span:
                spans.append(span)

        return sorted(spans, key=lambda s: s.start_ts)

    def get_artifact(self, artifact_hash: str) -> Artifact | None:
        """Get artifact metadata by hash."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                SELECT artifact_hash, artifact_type, content_type, byte_len, storage_path, created_ts, metadata
                FROM artifacts WHERE artifact_hash = ?
                """,
                (artifact_hash,),
            )
            row = cursor.fetchone()

        if row is None:
            return None

        return Artifact(
            artifact_hash=row[0],
            artifact_type=row[1],
            content_type=row[2],
            byte_len=row[3],
            storage_path=row[4],
            created_ts=datetime.fromisoformat(row[5]),
            metadata=json.loads(row[6]),
        )

    def get_artifact_data(self, artifact_hash: str) -> bytes | None:
        """Get artifact data by hash."""
        return self.artifact_store.retrieve(artifact_hash)

    # =========================================================================
    # Checkpoint Operations - Phase 1: Total Execution Capture
    # =========================================================================

    def create_checkpoint(
        self,
        trace_id: str,
        step_number: int,
        description: str,
        state_data: bytes,
        parent_checkpoint_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Checkpoint:
        """
        Create a checkpoint capturing the complete agent state.

        Args:
            trace_id: The trace this checkpoint belongs to
            step_number: Current step number in the execution
            description: Human-readable description of this checkpoint
            state_data: Serialized agent state (messages, tool state, etc.)
            parent_checkpoint_id: If forking, the parent checkpoint
            metadata: Additional metadata

        Returns:
            The created Checkpoint
        """
        # Store state as artifact
        state_artifact = self.store_artifact(
            data=state_data,
            artifact_type="checkpoint_state",
            content_type="application/json",
            metadata={"step_number": step_number, "description": description},
        )

        checkpoint_id = f"cp-{uuid.uuid4().hex[:16]}"
        checkpoint = Checkpoint(
            checkpoint_id=checkpoint_id,
            trace_id=trace_id,
            created_ts=datetime.now(UTC),
            status=CheckpointStatus.ACTIVE,
            step_number=step_number,
            description=description,
            state_artifact_hash=state_artifact.artifact_hash,
            parent_checkpoint_id=parent_checkpoint_id,
            metadata=metadata or {},
        )

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO checkpoints
                (checkpoint_id, trace_id, created_ts, status, step_number,
                 description, state_artifact_hash, parent_checkpoint_id, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    checkpoint.checkpoint_id,
                    checkpoint.trace_id,
                    checkpoint.created_ts.isoformat(),
                    checkpoint.status.value,
                    checkpoint.step_number,
                    checkpoint.description,
                    checkpoint.state_artifact_hash,
                    checkpoint.parent_checkpoint_id,
                    json.dumps(checkpoint.metadata),
                ),
            )

        return checkpoint

    def list_checkpoints(
        self,
        trace_id: str,
        status: CheckpointStatus | None = None,
    ) -> list[Checkpoint]:
        """
        List all checkpoints for a trace.

        Args:
            trace_id: The trace to list checkpoints for
            status: Optional filter by status

        Returns:
            List of checkpoints ordered by step number
        """
        query = """
            SELECT checkpoint_id, trace_id, created_ts, status, step_number,
                   description, state_artifact_hash, parent_checkpoint_id, metadata
            FROM checkpoints WHERE trace_id = ?
        """
        params: list[Any] = [trace_id]

        if status:
            query += " AND status = ?"
            params.append(status.value)

        query += " ORDER BY step_number ASC"

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()

        return [
            Checkpoint(
                checkpoint_id=row[0],
                trace_id=row[1],
                created_ts=datetime.fromisoformat(row[2]),
                status=CheckpointStatus(row[3]),
                step_number=row[4],
                description=row[5],
                state_artifact_hash=row[6],
                parent_checkpoint_id=row[7],
                metadata=json.loads(row[8]),
            )
            for row in rows
        ]

    def get_checkpoint(self, checkpoint_id: str) -> Checkpoint | None:
        """
        Get a checkpoint by ID.

        Args:
            checkpoint_id: The checkpoint ID

        Returns:
            The checkpoint or None if not found
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                SELECT checkpoint_id, trace_id, created_ts, status, step_number,
                       description, state_artifact_hash, parent_checkpoint_id, metadata
                FROM checkpoints WHERE checkpoint_id = ?
                """,
                (checkpoint_id,),
            )
            row = cursor.fetchone()

        if row is None:
            return None

        return Checkpoint(
            checkpoint_id=row[0],
            trace_id=row[1],
            created_ts=datetime.fromisoformat(row[2]),
            status=CheckpointStatus(row[3]),
            step_number=row[4],
            description=row[5],
            state_artifact_hash=row[6],
            parent_checkpoint_id=row[7],
            metadata=json.loads(row[8]),
        )

    def get_checkpoint_state(self, checkpoint_id: str) -> bytes | None:
        """
        Get the serialized state data for a checkpoint.

        Args:
            checkpoint_id: The checkpoint ID

        Returns:
            The serialized state data or None if not found
        """
        checkpoint = self.get_checkpoint(checkpoint_id)
        if checkpoint is None:
            return None
        return self.get_artifact_data(checkpoint.state_artifact_hash)

    def update_checkpoint_status(
        self,
        checkpoint_id: str,
        status: CheckpointStatus,
    ) -> None:
        """
        Update the status of a checkpoint.

        Args:
            checkpoint_id: The checkpoint ID
            status: The new status
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE checkpoints SET status = ? WHERE checkpoint_id = ?",
                (status.value, checkpoint_id),
            )

    def fork_from_checkpoint(
        self,
        checkpoint_id: str,
        new_trace_id: str | None = None,
    ) -> tuple[str, Checkpoint]:
        """
        Fork execution from a checkpoint, creating a new trace.

        This marks the original checkpoint as FORKED and creates a new
        checkpoint in the forked trace that references the parent.

        Args:
            checkpoint_id: The checkpoint to fork from
            new_trace_id: Optional new trace ID (generated if not provided)

        Returns:
            Tuple of (new_trace_id, new_checkpoint)
        """
        parent_checkpoint = self.get_checkpoint(checkpoint_id)
        if parent_checkpoint is None:
            raise ValueError(f"Checkpoint not found: {checkpoint_id}")

        # Mark parent as forked
        self.update_checkpoint_status(checkpoint_id, CheckpointStatus.FORKED)

        # Create new trace
        new_trace_id = new_trace_id or generate_trace_id()

        # Get parent state
        state_data = self.get_checkpoint_state(checkpoint_id)
        if state_data is None:
            raise ValueError(f"Checkpoint state not found: {checkpoint_id}")

        # Create new checkpoint in forked trace
        new_checkpoint = self.create_checkpoint(
            trace_id=new_trace_id,
            step_number=parent_checkpoint.step_number,
            description=f"Forked from {checkpoint_id}",
            state_data=state_data,
            parent_checkpoint_id=checkpoint_id,
            metadata={
                "forked_from_trace": parent_checkpoint.trace_id,
                "forked_from_checkpoint": checkpoint_id,
            },
        )

        return new_trace_id, new_checkpoint

    # =========================================================================
    # Session Overview - Phase 1: Overview + Detail Drill-down
    # =========================================================================

    def get_session_overview(self, trace_id: str) -> SessionOverview:
        """
        Generate a high-level overview of a session.

        This is the "overview" view that can be expanded into full detail.

        Args:
            trace_id: The trace to generate overview for

        Returns:
            SessionOverview with summary statistics
        """
        spans = self.get_trace_spans(trace_id)
        checkpoints = self.list_checkpoints(trace_id)

        # Calculate statistics
        llm_calls = [s for s in spans if s.kind == SpanKind.LLM_CALL]
        tool_calls = [s for s in spans if s.kind == SpanKind.TOOL_CALL]
        agent_turns = [s for s in spans if s.kind == SpanKind.AGENT_TURN]
        errors = [s for s in spans if s.status == SpanStatus.ERROR]

        # Calculate total tokens from LLM output artifacts
        total_tokens = 0
        for span in llm_calls:
            if span.output_artifact_hash:
                artifact_data = self.get_artifact_data(span.output_artifact_hash)
                if artifact_data:
                    try:
                        output = json.loads(artifact_data.decode())
                        usage = output.get("usage", {})
                        total_tokens += usage.get("total_tokens", 0)
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        pass

        # Determine session status
        if not spans:
            status = "empty"
        elif any(s.end_ts is None for s in spans):
            status = "in_progress"
        elif errors:
            status = "completed_with_errors"
        else:
            status = "completed"

        # Get timestamps
        start_ts = spans[0].start_ts if spans else datetime.now(UTC)
        end_ts = None
        for span in reversed(spans):
            if span.end_ts:
                end_ts = span.end_ts
                break

        # Current step
        current_step = "idle"
        for span in reversed(spans):
            if span.end_ts is None:
                current_step = f"{span.kind.value}: {span.name}"
                break
            else:
                current_step = f"completed: {span.name}"
                break

        # Key milestones (PR created, tests run, etc.)
        milestones = []
        for span in spans:
            if span.kind == SpanKind.TOOL_CALL and span.tool_provenance:
                tool_name = span.tool_provenance.tool_name
                if tool_name in ["git_create_pr", "git_pr_checks", "bash"]:
                    milestones.append({
                        "timestamp": span.start_ts.isoformat(),
                        "tool": tool_name,
                        "status": span.status.value,
                        "span_id": span.span_id,
                    })

        # Error details
        error_details = [
            {
                "timestamp": s.start_ts.isoformat(),
                "name": s.name,
                "error_class": s.error_class,
                "error_message": s.error_message,
                "span_id": s.span_id,
            }
            for s in errors
        ]

        return SessionOverview(
            trace_id=trace_id,
            start_ts=start_ts,
            end_ts=end_ts,
            status=status,
            total_steps=len(agent_turns),
            total_llm_calls=len(llm_calls),
            total_tool_calls=len(tool_calls),
            total_tokens=total_tokens,
            checkpoints_available=len(checkpoints),
            current_step=current_step,
            key_milestones=milestones,
            errors=error_details,
        )

    def get_session_timeline(
        self,
        trace_id: str,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """
        Get a timeline of all events in a session.

        This is the "full detail" view that shows every event.

        Args:
            trace_id: The trace to get timeline for
            since: Optional start time filter
            until: Optional end time filter

        Returns:
            List of events in chronological order
        """
        events = self.get_events(trace_id=trace_id, since=since, until=until)
        return [e.to_dict() for e in events]

    def store_cognitive_event(self, trace_id: str, event: CognitiveEvent) -> None:
        """Store a cognitive event (V5 metacognitive tracking).

        Cognitive events capture the agent's reasoning, temptation awareness,
        and decision points. These are stored separately from spans to enable
        metacognitive compliance analysis.

        Args:
            trace_id: The trace this event belongs to
            event: The cognitive event to store
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO cognitive_events (trace_id, event_type, timestamp, phase, content, metadata)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    trace_id,
                    event.event_type,
                    event.timestamp,
                    event.phase,
                    event.content,
                    json.dumps(event.metadata),
                ),
            )

    def get_cognitive_events(self, trace_id: str) -> list[CognitiveEvent]:
        """Retrieve all cognitive events for a trace (V5 metacognitive tracking).

        Args:
            trace_id: The trace to get cognitive events for

        Returns:
            List of CognitiveEvent objects in chronological order
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                SELECT event_type, timestamp, phase, content, metadata
                FROM cognitive_events
                WHERE trace_id = ?
                ORDER BY timestamp
                """,
                (trace_id,),
            )
            events = []
            for row in cursor.fetchall():
                events.append(
                    CognitiveEvent(
                        event_type=row[0],
                        timestamp=row[1],
                        phase=row[2],
                        content=row[3],
                        metadata=json.loads(row[4]),
                    )
                )
            return events


class SummaryEventLog:
    """
    Derived summary view of the TraceStore.

    This provides a quick overview of what happened in a run,
    always referencing the canonical trace_id/span_id.
    """

    def __init__(self, trace_store: TraceStore):
        self.trace_store = trace_store

    def get_summary(self, trace_id: str) -> list[dict[str, Any]]:
        """Get a summary of events for a trace."""
        spans = self.trace_store.get_trace_spans(trace_id)

        summary = []
        for span in spans:
            entry = {
                "timestamp": span.start_ts.isoformat(),
                "kind": span.kind.value,
                "name": span.name,
                "actor_id": span.actor_id,
                "status": span.status.value,
                "duration_ms": span.duration_ms,
                "trace_ref": {
                    "trace_id": span.trace_id,
                    "span_id": span.span_id,
                },
            }

            if span.error_message:
                entry["error"] = span.error_message

            if span.tool_provenance:
                entry["tool"] = span.tool_provenance.tool_name

            summary.append(entry)

        return summary

    def get_tool_calls(self, trace_id: str) -> list[dict[str, Any]]:
        """Get just the tool calls for a trace."""
        spans = self.trace_store.get_trace_spans(trace_id)
        return [
            {
                "timestamp": s.start_ts.isoformat(),
                "tool": s.tool_provenance.tool_name if s.tool_provenance else s.name,
                "status": s.status.value,
                "duration_ms": s.duration_ms,
                "trace_ref": {"trace_id": s.trace_id, "span_id": s.span_id},
            }
            for s in spans
            if s.kind == SpanKind.TOOL_CALL
        ]

    def get_errors(self, trace_id: str) -> list[dict[str, Any]]:
        """Get just the errors for a trace."""
        spans = self.trace_store.get_trace_spans(trace_id)
        return [
            {
                "timestamp": s.start_ts.isoformat(),
                "name": s.name,
                "error_class": s.error_class,
                "error_message": s.error_message,
                "trace_ref": {"trace_id": s.trace_id, "span_id": s.span_id},
            }
            for s in spans
            if s.status == SpanStatus.ERROR
        ]


class TraceContext:
    """
    Context manager for tracing a complete agent run.

    Provides convenient methods for recording spans during execution.
    """

    def __init__(self, trace_store: TraceStore, trace_id: str | None = None):
        self.trace_store = trace_store
        self.trace_id = trace_id or generate_trace_id()
        self._span_stack: list[str] = []

    @property
    def current_span_id(self) -> str | None:
        """Get the current span ID (top of stack)."""
        return self._span_stack[-1] if self._span_stack else None

    def start_span(
        self,
        kind: SpanKind,
        name: str,
        actor_id: str,
        attributes: dict[str, Any] | None = None,
        tool_provenance: ToolProvenance | None = None,
        input_artifact_hash: str | None = None,
    ) -> str:
        """Start a span with automatic parent linking."""
        span_id = self.trace_store.start_span(
            trace_id=self.trace_id,
            kind=kind,
            name=name,
            actor_id=actor_id,
            parent_span_id=self.current_span_id,
            attributes=attributes,
            tool_provenance=tool_provenance,
            input_artifact_hash=input_artifact_hash,
        )
        self._span_stack.append(span_id)
        return span_id

    def end_span(
        self,
        status: SpanStatus,
        output_artifact_hash: str | None = None,
        error_class: str | None = None,
        error_message: str | None = None,
    ) -> None:
        """End the current span."""
        if not self._span_stack:
            return

        span_id = self._span_stack.pop()
        self.trace_store.end_span(
            trace_id=self.trace_id,
            span_id=span_id,
            status=status,
            output_artifact_hash=output_artifact_hash,
            error_class=error_class,
            error_message=error_message,
        )

    def store_artifact(
        self,
        data: bytes,
        artifact_type: str,
        content_type: str,
        metadata: dict[str, Any] | None = None,
    ) -> Artifact:
        """Store an artifact."""
        return self.trace_store.store_artifact(data, artifact_type, content_type, metadata)

    def add_provenance(
        self,
        relation: ProvenanceRelation,
        object_span_id: str | None = None,
        object_artifact_hash: str | None = None,
    ) -> None:
        """Add provenance from current span."""
        if not self.current_span_id:
            return

        self.trace_store.add_provenance(
            trace_id=self.trace_id,
            relation=relation,
            subject_span_id=self.current_span_id,
            object_span_id=object_span_id,
            object_artifact_hash=object_artifact_hash,
        )

    def add_cognitive_event(self, event: CognitiveEvent) -> None:
        """Record a cognitive event (V5 metacognitive tracking).

        Cognitive events capture the agent's reasoning, temptation awareness,
        and decision points. This method stores the event in the trace store
        for later analysis.

        Args:
            event: The cognitive event to record
        """
        self.trace_store.store_cognitive_event(self.trace_id, event)


def create_trace_store(base_path: Path) -> tuple[TraceStore, ArtifactStore]:
    """
    Create a TraceStore with its ArtifactStore.

    Args:
        base_path: Base directory for all trace data

    Returns:
        Tuple of (TraceStore, ArtifactStore)
    """
    base_path.mkdir(parents=True, exist_ok=True)
    artifact_store = ArtifactStore(base_path / "artifacts")
    trace_store = TraceStore(base_path / "traces.db", artifact_store)
    return trace_store, artifact_store
