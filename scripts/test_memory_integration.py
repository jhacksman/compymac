#!/usr/bin/env python3
"""
Integration tests for CompyMac Memory System.

Tests the complete flow:
1. Document ingestion
2. Hybrid retrieval
3. Trace capture
4. Secret redaction

Run with: python scripts/test_memory_integration.py
"""

import sys
import tempfile
import time
from pathlib import Path


def test_document_ingestion() -> bool:
    """Test: ingest document -> retrieve -> verify citations."""
    try:
        from compymac.ingestion.pipeline import IngestionPipeline
        from compymac.knowledge_store import KnowledgeStore
        from compymac.storage.sqlite_backend import SQLiteBackend

        # Create temp database
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            backend = SQLiteBackend(db_path)
            store = KnowledgeStore(backend)
            pipeline = IngestionPipeline(store)

            # Create test document
            doc_path = Path(tmpdir) / "test_doc.txt"
            doc_path.write_text(
                "Python is a programming language. "
                "It is widely used for web development, data science, and automation. "
                "Python has a simple syntax that makes it easy to learn. " * 10
            )

            # Ingest
            doc_id = pipeline.ingest(doc_path)
            assert doc_id is not None, "Document ID should not be None"

            # Retrieve
            results = store.retrieve("programming language", limit=5)
            assert len(results) >= 1, "Should find at least one result"

            # Verify citation metadata
            first_result = results[0]
            assert first_result.memory_unit.source_id == doc_id
            assert "chunk_index" in first_result.memory_unit.metadata

            return True

    except Exception as e:
        print(f"  Error: {e}")
        return False


def test_hybrid_retrieval() -> bool:
    """Test: hybrid retrieval with sparse + dense."""
    try:
        from compymac.knowledge_store import KnowledgeStore, MemoryUnit
        from compymac.retrieval.hybrid import HybridRetriever
        from compymac.storage.sqlite_backend import SQLiteBackend

        # Create temp database
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            backend = SQLiteBackend(db_path)
            store = KnowledgeStore(backend)
            retriever = HybridRetriever(store)

            # Add test data
            test_docs = [
                "Machine learning is a subset of artificial intelligence.",
                "Deep learning uses neural networks with many layers.",
                "Natural language processing helps computers understand text.",
                "Computer vision enables machines to interpret images.",
                "Reinforcement learning trains agents through rewards.",
            ]

            for i, content in enumerate(test_docs):
                store.store(MemoryUnit(
                    id=f"test-{i}",
                    content=content,
                    embedding=None,
                    source_type="test",
                    source_id="test-suite",
                    metadata={"index": i},
                    created_at=time.time(),
                ))

            # Test sparse retrieval
            results = retriever.retrieve("neural networks", limit=3)
            assert len(results) >= 1, "Should find at least one result"

            # Verify relevance
            found_neural = any(
                "neural" in r.memory_unit.content.lower()
                for r in results
            )
            assert found_neural, "Should find document about neural networks"

            return True

    except Exception as e:
        print(f"  Error: {e}")
        return False


def test_trace_capture() -> bool:
    """Test: trace store captures events correctly."""
    try:
        from compymac.trace_store import (
            SpanKind,
            SpanStatus,
            create_trace_store,
            generate_trace_id,
        )

        # Create temp trace store
        with tempfile.TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir)
            # create_trace_store returns (TraceStore, ArtifactStore) tuple
            trace_store, artifact_store = create_trace_store(base_path)

            # Generate a trace ID
            trace_id = generate_trace_id()

            # Start a span directly on TraceStore
            span_id = trace_store.start_span(
                trace_id=trace_id,
                kind=SpanKind.MEMORY_OPERATION,
                name="test_operation",
                actor_id="test_actor",
                attributes={"input": "test"},
            )
            assert span_id is not None, "Span ID should not be None"

            # End the span
            trace_store.end_span(
                trace_id=trace_id,
                span_id=span_id,
                status=SpanStatus.OK,
            )

            # Verify events were captured
            events = trace_store.get_events(trace_id=trace_id, limit=10)
            assert len(events) >= 2, "Should have at least start and end events"

            return True

    except Exception as e:
        print(f"  Error: {e}")
        return False


def test_secret_redaction() -> bool:
    """Test: secrets are properly detected and redacted."""
    try:
        from compymac.security.scanner import SecretScanner

        scanner = SecretScanner()

        # Test various secret patterns
        test_cases = [
            ("API_KEY=sk-1234567890abcdef", "sk-1234567890"),
            ("password=hunter2", "hunter2"),
            ("Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"),
            ("AKIA1234567890ABCDEF", "AKIA1234567890ABCDEF"),
        ]

        for text, secret_part in test_cases:
            # Test detection
            matches = scanner.scan(text)
            assert len(matches) >= 1, f"Should detect secret in: {text}"

            # Test redaction
            redacted = scanner.redact(text)
            assert secret_part not in redacted, f"Secret should be redacted: {secret_part}"
            assert "[REDACTED]" in redacted, "Should contain redaction placeholder"

        return True

    except Exception as e:
        print(f"  Error: {e}")
        return False


def main() -> int:
    """Run all integration tests."""
    print("CompyMac Memory System Integration Tests")
    print("=" * 50)
    print()

    tests = [
        ("Document ingestion", test_document_ingestion),
        ("Hybrid retrieval", test_hybrid_retrieval),
        ("Trace capture", test_trace_capture),
        ("Secret redaction", test_secret_redaction),
    ]

    results = []
    for name, test_func in tests:
        print(f"Testing: {name}...", end=" ")
        try:
            passed = test_func()
            results.append((name, passed))
            if passed:
                print("[PASS]")
            else:
                print("[FAIL]")
        except Exception as e:
            results.append((name, False))
            print(f"[FAIL] {e}")

    print()
    print("=" * 50)

    # Summary
    passed = sum(1 for _, p in results if p)
    total = len(results)

    if passed == total:
        print(f"All tests passed! ({passed}/{total})")
        return 0
    else:
        print(f"Some tests failed: {passed}/{total} passed")
        for name, p in results:
            status = "[PASS]" if p else "[FAIL]"
            print(f"  {status} {name}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
