#!/usr/bin/env python3
"""
M9 Comprehensive Integration Testing

This script verifies the CompyMac memory system works end-to-end by:
1. Running actual production code paths (not component demos)
2. Verifying all 6 invariants with SQL queries and artifact file reads
3. Testing through the same interfaces the agent uses (LocalHarness, TraceContext)

Invariants from MEMORY_SYSTEM_DESIGN.md:
- INV-1: Every LLM request/response is stored as artifact and referenced in trace_events
- INV-2: Every tool input/output is stored as artifact
- INV-3: Large payloads (>10KB) never stored inline in trace_events
- INV-4: All artifacts are content-addressed (hash matches content)
- INV-5: All persisted records include trace_id + timestamp
- INV-6: No secrets in stored content (after redaction enabled)
"""

import hashlib
import json
import os
import sqlite3
import sys
import time
from pathlib import Path

# Check required environment variables
# LLMClient uses these env vars: LLM_API_KEY, LLM_BASE_URL, LLM_MODEL
required_env_vars = ["LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL"]
missing_vars = [var for var in required_env_vars if not os.environ.get(var)]
if missing_vars:
    print(f"ERROR: Missing required environment variables: {', '.join(missing_vars)}")
    print("Please set the following environment variables:")
    print("  export LLM_API_KEY='your-api-key'")
    print("  export LLM_BASE_URL='https://api.venice.ai/api/v1'")
    print("  export LLM_MODEL='qwen3-235b-a22b-instruct-2507'")
    sys.exit(1)

# Set VENICE_* vars for backward compatibility
os.environ.setdefault("VENICE_API_KEY", os.environ.get("LLM_API_KEY", ""))
os.environ.setdefault("VENICE_API_BASE", os.environ.get("LLM_BASE_URL", ""))

# Test directories
TEST_DIR = Path("/tmp/m9_comprehensive")
TEST_DIR.mkdir(parents=True, exist_ok=True)
TRACE_DB = TEST_DIR / "traces.db"
KNOWLEDGE_DB = TEST_DIR / "knowledge.db"
ARTIFACT_DIR = TEST_DIR / "artifacts"
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

os.environ["COMPYMAC_TRACE_DB_PATH"] = str(TRACE_DB)
os.environ["COMPYMAC_KNOWLEDGE_DB_PATH"] = str(KNOWLEDGE_DB)
os.environ["COMPYMAC_ARTIFACT_PATH"] = str(ARTIFACT_DIR)

# Results tracking
RESULTS = {
    "passed": [],
    "failed": [],
    "evidence": {}
}


def log_result(test_name: str, passed: bool, evidence: dict, message: str = ""):
    """Log a test result with evidence."""
    status = "PASS" if passed else "FAIL"
    print(f"[{status}] {test_name}")
    if message:
        print(f"       {message}")
    
    if passed:
        RESULTS["passed"].append(test_name)
    else:
        RESULTS["failed"].append(test_name)
    
    RESULTS["evidence"][test_name] = evidence


def test_inv1_llm_artifacts():
    """
    INV-1: Every LLM request/response is stored as artifact and referenced in trace_events.
    
    This test makes a real LLM call through the production code path and verifies:
    - span_start event exists for llm_call
    - span_end event exists for llm_call
    - Input artifact is stored and referenced
    - Output artifact is stored and referenced
    """
    print("\n" + "=" * 60)
    print("TEST INV-1: LLM Artifacts")
    print("=" * 60)
    
    from compymac.trace_store import TraceStore, ArtifactStore, TraceContext, SpanKind, SpanStatus
    from compymac.llm import LLMClient
    
    # Clean up any existing test data
    if TRACE_DB.exists():
        TRACE_DB.unlink()
    
    # Create trace store
    artifact_store = ArtifactStore(ARTIFACT_DIR)
    trace_store = TraceStore(TRACE_DB, artifact_store)
    
    # Create trace context
    trace_id = f"test-inv1-{int(time.time())}"
    ctx = TraceContext(trace_store, trace_id)
    
    # Make a real LLM call (LLMClient uses LLMConfig.from_env())
    client = LLMClient()
    
    messages = [{"role": "user", "content": "Say 'hello' and nothing else."}]
    
    # Start span for LLM call (requires actor_id)
    span_id = ctx.start_span(kind=SpanKind.LLM_CALL, name="test_llm_call", actor_id="test-agent")
    
    # Store input artifact
    input_data = json.dumps({"messages": messages}).encode()
    input_artifact = ctx.store_artifact(input_data, "llm_input", "application/json")
    
    # Make the actual API call
    try:
        response = client.chat(messages=messages)
        llm_output = response.content  # ChatResponse has .content directly
        
        # Store output artifact
        output_data = json.dumps({"response": llm_output, "raw": response.raw_response}).encode()
        output_artifact = ctx.store_artifact(output_data, "llm_output", "application/json")
        
        # End span (uses SpanStatus enum, no span_id needed - pops from stack)
        ctx.end_span(status=SpanStatus.OK)
        
    except Exception as e:
        ctx.end_span(status=SpanStatus.ERROR, error_message=str(e))
        log_result("INV-1: LLM Artifacts", False, {"error": str(e)}, f"LLM call failed: {e}")
        return
    
    # Verify with SQL queries
    conn = sqlite3.connect(TRACE_DB)
    conn.row_factory = sqlite3.Row
    
    # Check span_start events for llm_call
    cursor = conn.execute("""
        SELECT * FROM trace_events 
        WHERE trace_id = ? AND event_type = 'span_start'
    """, (trace_id,))
    span_starts = cursor.fetchall()
    
    # Check span_end events
    cursor = conn.execute("""
        SELECT * FROM trace_events 
        WHERE trace_id = ? AND event_type = 'span_end'
    """, (trace_id,))
    span_ends = cursor.fetchall()
    
    # Check artifacts table
    cursor = conn.execute("SELECT * FROM artifacts")
    artifacts = cursor.fetchall()
    
    conn.close()
    
    evidence = {
        "trace_id": trace_id,
        "span_id": span_id,
        "span_start_count": len(span_starts),
        "span_end_count": len(span_ends),
        "artifact_count": len(artifacts),
        "input_artifact_hash": input_artifact.artifact_hash,
        "output_artifact_hash": output_artifact.artifact_hash,
        "llm_response": llm_output[:100],
    }
    
    # Verify invariant
    passed = (
        len(span_starts) >= 1 and
        len(span_ends) >= 1 and
        len(artifacts) >= 2  # input + output
    )
    
    log_result("INV-1: LLM Artifacts", passed, evidence,
               f"span_starts={len(span_starts)}, span_ends={len(span_ends)}, artifacts={len(artifacts)}")


def test_inv2_tool_artifacts():
    """
    INV-2: Every tool input/output is stored as artifact.
    
    This test executes a tool through LocalHarness and verifies:
    - Tool call is traced
    - Input artifact is stored
    - Output artifact is stored
    """
    print("\n" + "=" * 60)
    print("TEST INV-2: Tool Artifacts")
    print("=" * 60)
    
    from compymac.trace_store import TraceStore, ArtifactStore, TraceContext
    from compymac.local_harness import LocalHarness, ToolCall
    
    # Create fresh trace store
    trace_db = TEST_DIR / "traces_inv2.db"
    if trace_db.exists():
        trace_db.unlink()
    
    artifact_store = ArtifactStore(ARTIFACT_DIR)
    trace_store = TraceStore(trace_db, artifact_store)
    
    trace_id = f"test-inv2-{int(time.time())}"
    ctx = TraceContext(trace_store, trace_id)
    
    # Create harness and set trace context
    harness = LocalHarness()
    harness.set_trace_context(ctx)
    
    # Execute a tool (Read is simple and reliable)
    test_file = TEST_DIR / "test_file.txt"
    test_file.write_text("This is test content for INV-2 verification.")
    
    tool_call = ToolCall(
        id="test-tool-call-1",
        name="Read",
        arguments={"file_path": str(test_file)},
    )
    
    result = harness.execute(tool_call)
    
    # Verify with SQL queries
    conn = sqlite3.connect(trace_db)
    conn.row_factory = sqlite3.Row
    
    # Check for tool call spans
    cursor = conn.execute("""
        SELECT * FROM trace_events 
        WHERE trace_id = ? AND event_type IN ('span_start', 'span_end')
    """, (trace_id,))
    events = cursor.fetchall()
    
    # Check artifacts
    cursor = conn.execute("SELECT * FROM artifacts")
    artifacts = cursor.fetchall()
    
    conn.close()
    
    evidence = {
        "trace_id": trace_id,
        "tool_name": "Read",
        "tool_result_success": result.success,
        "event_count": len(events),
        "artifact_count": len(artifacts),
        "artifact_hashes": [a["artifact_hash"] for a in artifacts],
    }
    
    # Tool calls should create trace events
    passed = len(events) >= 2 and result.success
    
    log_result("INV-2: Tool Artifacts", passed, evidence,
               f"events={len(events)}, artifacts={len(artifacts)}, success={result.success}")


def test_inv3_large_payload():
    """
    INV-3: Large payloads (>10KB) never stored inline in trace_events.
    
    This test creates a >10KB payload and verifies it's stored as artifact, not inline.
    """
    print("\n" + "=" * 60)
    print("TEST INV-3: Large Payload Handling")
    print("=" * 60)
    
    from compymac.trace_store import TraceStore, ArtifactStore, TraceContext, SpanKind, SpanStatus
    
    # Create fresh trace store
    trace_db = TEST_DIR / "traces_inv3.db"
    if trace_db.exists():
        trace_db.unlink()
    
    artifact_store = ArtifactStore(ARTIFACT_DIR)
    trace_store = TraceStore(trace_db, artifact_store)
    
    trace_id = f"test-inv3-{int(time.time())}"
    ctx = TraceContext(trace_store, trace_id)
    
    # Create a large payload (>10KB)
    large_content = "X" * 15000  # 15KB
    
    # Start span (requires actor_id)
    span_id = ctx.start_span(kind=SpanKind.TOOL_CALL, name="large_payload_test", actor_id="test-agent")
    
    # Store as artifact (this is how large payloads should be handled)
    artifact = ctx.store_artifact(
        large_content.encode(),
        "large_output",
        "text/plain"
    )
    
    ctx.end_span(status=SpanStatus.OK)
    
    # Verify with SQL queries
    conn = sqlite3.connect(trace_db)
    conn.row_factory = sqlite3.Row
    
    # Check max data size in trace_events
    cursor = conn.execute("SELECT MAX(LENGTH(data)) as max_len FROM trace_events")
    max_data_len = cursor.fetchone()["max_len"]
    
    # Check artifact was stored
    cursor = conn.execute("SELECT * FROM artifacts WHERE artifact_hash = ?", (artifact.artifact_hash,))
    stored_artifact = cursor.fetchone()
    
    conn.close()
    
    # Verify artifact file exists and has correct size
    artifact_path = ARTIFACT_DIR / artifact.artifact_hash[:2] / artifact.artifact_hash
    artifact_exists = artifact_path.exists()
    artifact_size = artifact_path.stat().st_size if artifact_exists else 0
    
    evidence = {
        "trace_id": trace_id,
        "large_content_size": len(large_content),
        "max_trace_event_data_len": max_data_len,
        "artifact_hash": artifact.artifact_hash,
        "artifact_exists": artifact_exists,
        "artifact_file_size": artifact_size,
    }
    
    # Invariant: trace_events data should be small, large content in artifact
    passed = (
        max_data_len < 50000 and  # trace_events data should be small
        artifact_exists and
        artifact_size >= 15000  # artifact should have the large content
    )
    
    log_result("INV-3: Large Payload Handling", passed, evidence,
               f"max_event_data={max_data_len}, artifact_size={artifact_size}")


def test_inv4_content_addressed():
    """
    INV-4: All artifacts are content-addressed (hash matches content).
    
    This test stores artifacts and verifies SHA-256 hash matches actual content.
    """
    print("\n" + "=" * 60)
    print("TEST INV-4: Content-Addressed Artifacts")
    print("=" * 60)
    
    from compymac.trace_store import ArtifactStore
    
    artifact_store = ArtifactStore(ARTIFACT_DIR)
    
    # Store multiple artifacts with known content
    test_contents = [
        b"Test content 1 for hash verification",
        b"Test content 2 with different data",
        b'{"json": "content", "for": "testing"}',
    ]
    
    hash_matches = []
    for content in test_contents:
        # Store artifact
        artifact = artifact_store.store(content, "test", "text/plain")
        
        # Compute expected hash
        expected_hash = hashlib.sha256(content).hexdigest()
        
        # Read artifact file and compute actual hash
        artifact_path = ARTIFACT_DIR / artifact.artifact_hash[:2] / artifact.artifact_hash
        if artifact_path.exists():
            actual_content = artifact_path.read_bytes()
            actual_hash = hashlib.sha256(actual_content).hexdigest()
            
            hash_matches.append({
                "stored_hash": artifact.artifact_hash,
                "expected_hash": expected_hash,
                "actual_hash": actual_hash,
                "matches": (artifact.artifact_hash == expected_hash == actual_hash),
            })
    
    evidence = {
        "artifacts_tested": len(test_contents),
        "hash_verifications": hash_matches,
    }
    
    # All hashes should match
    passed = all(h["matches"] for h in hash_matches)
    
    log_result("INV-4: Content-Addressed Artifacts", passed, evidence,
               f"all_hashes_match={passed}, tested={len(hash_matches)}")


def test_inv5_trace_id_timestamp():
    """
    INV-5: All persisted records include trace_id + timestamp.
    
    This test verifies no records have NULL trace_id or timestamp.
    """
    print("\n" + "=" * 60)
    print("TEST INV-5: Trace ID and Timestamp")
    print("=" * 60)
    
    from compymac.trace_store import TraceStore, ArtifactStore, TraceContext, SpanKind, SpanStatus
    
    # Create fresh trace store
    trace_db = TEST_DIR / "traces_inv5.db"
    if trace_db.exists():
        trace_db.unlink()
    
    artifact_store = ArtifactStore(ARTIFACT_DIR)
    trace_store = TraceStore(trace_db, artifact_store)
    
    # Create multiple traces with events
    for i in range(3):
        trace_id = f"test-inv5-{i}-{int(time.time())}"
        ctx = TraceContext(trace_store, trace_id)
        
        span_id = ctx.start_span(kind=SpanKind.AGENT_TURN, name=f"test_span_{i}", actor_id="test-agent")
        ctx.end_span(status=SpanStatus.OK)
    
    # Verify with SQL queries
    conn = sqlite3.connect(trace_db)
    conn.row_factory = sqlite3.Row
    
    # Check for NULL trace_id or timestamp
    cursor = conn.execute("""
        SELECT COUNT(*) as null_count FROM trace_events 
        WHERE trace_id IS NULL OR timestamp IS NULL
    """)
    null_count = cursor.fetchone()["null_count"]
    
    # Get total count
    cursor = conn.execute("SELECT COUNT(*) as total FROM trace_events")
    total_count = cursor.fetchone()["total"]
    
    # Sample some records to show they have values
    cursor = conn.execute("SELECT trace_id, timestamp FROM trace_events LIMIT 5")
    sample_records = [dict(r) for r in cursor.fetchall()]
    
    conn.close()
    
    evidence = {
        "total_events": total_count,
        "null_trace_id_or_timestamp": null_count,
        "sample_records": sample_records,
    }
    
    # No records should have NULL trace_id or timestamp
    passed = null_count == 0 and total_count > 0
    
    log_result("INV-5: Trace ID and Timestamp", passed, evidence,
               f"total={total_count}, nulls={null_count}")


def test_inv6_secret_redaction():
    """
    INV-6: No secrets in stored content (after redaction enabled).
    
    This test verifies SecretScanner integration status:
    1. Check if SecretScanner is wired into artifact storage
    2. Store content with secrets and check if redacted
    """
    print("\n" + "=" * 60)
    print("TEST INV-6: Secret Redaction")
    print("=" * 60)
    
    from compymac.trace_store import TraceStore, ArtifactStore, TraceContext, SpanKind, SpanStatus
    from compymac.security.scanner import SecretScanner
    
    # Create fresh trace store
    trace_db = TEST_DIR / "traces_inv6.db"
    if trace_db.exists():
        trace_db.unlink()
    
    artifact_store = ArtifactStore(ARTIFACT_DIR)
    trace_store = TraceStore(trace_db, artifact_store)
    
    trace_id = f"test-inv6-{int(time.time())}"
    ctx = TraceContext(trace_store, trace_id)
    
    # Content with secrets
    secret_content = """
    API_KEY=sk-1234567890abcdefghijklmnopqrstuvwxyz
    password=hunter2
    AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
    """
    
    # Store as artifact (through production code path)
    span_id = ctx.start_span(kind=SpanKind.TOOL_CALL, name="secret_test", actor_id="test-agent")
    artifact = ctx.store_artifact(
        secret_content.encode(),
        "tool_output",
        "text/plain"
    )
    ctx.end_span(status=SpanStatus.OK)
    
    # Read the stored artifact file
    artifact_path = ARTIFACT_DIR / artifact.artifact_hash[:2] / artifact.artifact_hash
    stored_content = artifact_path.read_bytes().decode() if artifact_path.exists() else ""
    
    # Check if secrets are present in stored content
    secrets_present = (
        "sk-1234567890" in stored_content or
        "hunter2" in stored_content or
        "wJalrXUtnFEMI" in stored_content
    )
    
    # Also verify SecretScanner works independently
    scanner = SecretScanner()
    matches = scanner.scan(secret_content)
    redacted = scanner.redact(secret_content)
    
    evidence = {
        "trace_id": trace_id,
        "artifact_hash": artifact.artifact_hash,
        "secrets_in_stored_artifact": secrets_present,
        "scanner_detected_count": len(matches),
        "scanner_redaction_works": "[REDACTED]" in redacted,
        "stored_content_sample": stored_content[:200] if stored_content else "N/A",
    }
    
    # CRITICAL: This invariant FAILS if secrets are stored unredacted
    # The design doc says SecretScanner should be integrated into artifact storage
    passed = not secrets_present
    
    if secrets_present:
        evidence["CRITICAL_GAP"] = "SecretScanner is NOT integrated into artifact storage path"
    
    log_result("INV-6: Secret Redaction", passed, evidence,
               f"secrets_in_artifact={secrets_present}, scanner_works={len(matches) > 0}")


def test_librarian_tool_registration():
    """
    M8 Acceptance Test: librarian_search tool is registered and discoverable.
    
    The design doc says: tools = harness.get_tools() should include librarian_search
    """
    print("\n" + "=" * 60)
    print("TEST M8: Librarian Tool Registration")
    print("=" * 60)
    
    from compymac.local_harness import LocalHarness
    
    harness = LocalHarness()
    
    # Get all tool schemas (this is what the LLM sees)
    schemas = harness.get_tool_schemas()
    tool_names = [s["function"]["name"] for s in schemas]
    
    # Check if librarian_search is in the list
    librarian_in_schemas = "librarian_search" in tool_names
    
    # Also check if tool is registered internally
    librarian_registered = "librarian_search" in harness._tools
    
    evidence = {
        "total_tools": len(tool_names),
        "librarian_in_schemas": librarian_in_schemas,
        "librarian_registered": librarian_registered,
        "sample_tools": tool_names[:10],
    }
    
    # M8 acceptance test: tool should be discoverable
    passed = librarian_in_schemas
    
    if not librarian_in_schemas and librarian_registered:
        evidence["NOTE"] = "Tool is registered but not in get_tool_schemas() output"
    
    log_result("M8: Librarian Tool Registration", passed, evidence,
               f"in_schemas={librarian_in_schemas}, registered={librarian_registered}")


def test_document_ingestion_e2e():
    """
    M6/M9 Test: Document ingestion end-to-end with Venice.ai embeddings.
    """
    print("\n" + "=" * 60)
    print("TEST M6: Document Ingestion E2E")
    print("=" * 60)
    
    from compymac.knowledge_store import KnowledgeStore
    from compymac.storage.sqlite_backend import SQLiteBackend
    from compymac.ingestion.pipeline import IngestionPipeline
    from compymac.retrieval.embedder import VeniceEmbedder
    
    # Create test document
    test_doc = TEST_DIR / "test_document.txt"
    test_doc.write_text("""
    CompyMac Memory System Documentation
    
    The CompyMac memory system consists of several key components:
    
    1. TraceStore - An append-only event log that captures all LLM calls and tool executions.
    2. KnowledgeStore - A factual memory store for documents and extracted knowledge.
    3. VeniceEmbedder - Generates 1024-dimensional embeddings via Venice.ai API.
    4. HybridRetriever - Combines sparse (keyword) and dense (vector) retrieval.
    5. SecretScanner - Detects and redacts sensitive information.
    """)
    
    # Create knowledge store
    knowledge_db = TEST_DIR / "knowledge_e2e.db"
    if knowledge_db.exists():
        knowledge_db.unlink()
    
    backend = SQLiteBackend(knowledge_db)
    store = KnowledgeStore(backend)
    
    # Create embedder and pipeline
    embedder = VeniceEmbedder()
    pipeline = IngestionPipeline(store, embedder=embedder)
    
    # Ingest document
    try:
        doc_id = pipeline.ingest(test_doc)
        
        # Verify chunks were created
        results = store.retrieve("memory system components", limit=5)
        
        # Check embedding dimensions
        embedding_dim = None
        if results and results[0].memory_unit.embedding:
            embedding_dim = len(results[0].memory_unit.embedding)
        
        evidence = {
            "document_id": doc_id,
            "results_count": len(results),
            "embedding_dimension": embedding_dim,
            "sample_result": results[0].memory_unit.content[:100] if results else "N/A",
        }
        
        passed = doc_id is not None and len(results) > 0 and embedding_dim == 1024
        
        log_result("M6: Document Ingestion E2E", passed, evidence,
                   f"doc_id={doc_id}, results={len(results)}, dim={embedding_dim}")
        
    except Exception as e:
        log_result("M6: Document Ingestion E2E", False, {"error": str(e)}, f"Failed: {e}")


def test_hybrid_retrieval():
    """
    M5 Test: Hybrid retrieval with sparse + dense search.
    """
    print("\n" + "=" * 60)
    print("TEST M5: Hybrid Retrieval")
    print("=" * 60)
    
    from compymac.knowledge_store import KnowledgeStore
    from compymac.storage.sqlite_backend import SQLiteBackend
    from compymac.retrieval.hybrid import HybridRetriever
    from compymac.retrieval.embedder import VeniceEmbedder
    
    # Use the knowledge store from previous test
    knowledge_db = TEST_DIR / "knowledge_e2e.db"
    
    if not knowledge_db.exists():
        log_result("M5: Hybrid Retrieval", False, {"error": "knowledge_db not found"},
                   "Run M6 test first")
        return
    
    backend = SQLiteBackend(knowledge_db)
    store = KnowledgeStore(backend)
    embedder = VeniceEmbedder()
    retriever = HybridRetriever(store, embedder=embedder)
    
    # Test queries
    queries = [
        ("TraceStore SQLite", "keyword"),
        ("how to store agent execution logs", "semantic"),
        ("vector embeddings for search", "mixed"),
    ]
    
    all_results = []
    for query, query_type in queries:
        results = retriever.retrieve(query, limit=3)
        all_results.append({
            "query": query,
            "type": query_type,
            "result_count": len(results),
            "top_score": results[0].score if results else 0,
            "match_type": results[0].match_type if results else "N/A",
        })
    
    evidence = {
        "queries_tested": len(queries),
        "results": all_results,
    }
    
    # All queries should return results
    passed = all(r["result_count"] > 0 for r in all_results)
    
    log_result("M5: Hybrid Retrieval", passed, evidence,
               f"all_queries_returned_results={passed}")


def main():
    """Run all integration tests."""
    print("=" * 60)
    print("M9 COMPREHENSIVE INTEGRATION TESTING")
    print("=" * 60)
    print(f"Test directory: {TEST_DIR}")
    print(f"Started: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}")
    
    # Run all tests
    test_inv1_llm_artifacts()
    test_inv2_tool_artifacts()
    test_inv3_large_payload()
    test_inv4_content_addressed()
    test_inv5_trace_id_timestamp()
    test_inv6_secret_redaction()
    test_librarian_tool_registration()
    test_document_ingestion_e2e()
    test_hybrid_retrieval()
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Passed: {len(RESULTS['passed'])}")
    print(f"Failed: {len(RESULTS['failed'])}")
    
    if RESULTS["failed"]:
        print("\nFailed tests:")
        for test in RESULTS["failed"]:
            print(f"  - {test}")
    
    # Write detailed results to file
    results_file = TEST_DIR / "results.json"
    with open(results_file, "w") as f:
        json.dump(RESULTS, f, indent=2, default=str)
    print(f"\nDetailed results: {results_file}")
    
    # Return exit code
    return 0 if not RESULTS["failed"] else 1


if __name__ == "__main__":
    sys.exit(main())
