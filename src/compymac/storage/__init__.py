"""
Storage backends for CompyMac memory system.

This module provides pluggable storage backends for TraceStore and KnowledgeStore.
Supports SQLite (local development) and PostgreSQL (production with pgvector).

Gap 1: Also provides RunStore for session persistence and resume.
"""

from compymac.storage.backend import StorageBackend
from compymac.storage.sqlite_backend import SQLiteBackend
from compymac.storage.run_store import RunStore, RunStatus, RunMetadata, SavedRun

# PostgresBackend is optional - requires psycopg2
try:
    from compymac.storage.postgres_backend import PostgresBackend
    __all__ = [
        "StorageBackend",
        "SQLiteBackend",
        "PostgresBackend",
        "RunStore",
        "RunStatus",
        "RunMetadata",
        "SavedRun",
    ]
except ImportError:
    __all__ = [
        "StorageBackend",
        "SQLiteBackend",
        "RunStore",
        "RunStatus",
        "RunMetadata",
        "SavedRun",
    ]
