"""
Storage backends for CompyMac memory system.

This module provides pluggable storage backends for TraceStore and KnowledgeStore.
Supports SQLite (local development) and PostgreSQL (production with pgvector).
"""

from compymac.storage.backend import StorageBackend
from compymac.storage.sqlite_backend import SQLiteBackend

# PostgresBackend is optional - requires psycopg2
try:
    from compymac.storage.postgres_backend import PostgresBackend
    __all__ = [
        "StorageBackend",
        "SQLiteBackend",
        "PostgresBackend",
    ]
except ImportError:
    __all__ = [
        "StorageBackend",
        "SQLiteBackend",
    ]
