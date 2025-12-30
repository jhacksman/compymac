"""
KnowledgeStore - Persistent storage for factual and working memory.

Provides storage and retrieval of memory units with support for:
- Keyword search (SQLite LIKE, PostgreSQL tsvector)
- Vector similarity search (PostgreSQL pgvector)
- Hybrid retrieval combining both approaches
"""

import json
from dataclasses import dataclass
from typing import Any

from compymac.storage.sqlite_backend import SQLiteBackend


@dataclass
class MemoryUnit:
    """A unit of knowledge stored in the KnowledgeStore."""

    id: str
    content: str
    embedding: list[float] | None
    source_type: str
    source_id: str
    metadata: dict[str, Any]
    created_at: float

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "id": self.id,
            "content": self.content,
            "embedding": json.dumps(self.embedding) if self.embedding else None,
            "source_type": self.source_type,
            "source_id": self.source_id,
            "metadata": json.dumps(self.metadata),
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MemoryUnit":
        """Create from dictionary."""
        embedding = data.get("embedding")
        if embedding and isinstance(embedding, str):
            embedding = json.loads(embedding)

        metadata = data.get("metadata", "{}")
        if isinstance(metadata, str):
            metadata = json.loads(metadata)

        return cls(
            id=data["id"],
            content=data["content"],
            embedding=embedding,
            source_type=data["source_type"],
            source_id=data["source_id"],
            metadata=metadata,
            created_at=data["created_at"],
        )


@dataclass
class RetrievalResult:
    """Result from a retrieval query."""

    memory_unit: MemoryUnit
    score: float
    match_type: str  # 'keyword', 'vector', 'hybrid'


class KnowledgeStore:
    """
    Storage and retrieval for memory units.

    Supports both SQLite (keyword search only) and PostgreSQL (hybrid search).
    """

    def __init__(self, backend: SQLiteBackend | Any):
        """
        Initialize KnowledgeStore with a storage backend.

        Args:
            backend: Storage backend (SQLiteBackend or PostgresBackend)
        """
        self.backend = backend
        self._init_schema()

    def _init_schema(self) -> None:
        """Create tables if they don't exist."""
        # Main memory_units table
        self.backend.execute("""
            CREATE TABLE IF NOT EXISTS memory_units (
                id TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                embedding TEXT,
                source_type TEXT NOT NULL,
                source_id TEXT NOT NULL,
                metadata TEXT DEFAULT '{}',
                created_at REAL NOT NULL
            )
        """)

        # Create index for keyword search
        self.backend.execute("""
            CREATE INDEX IF NOT EXISTS idx_memory_units_content
            ON memory_units(content)
        """)

        # Create index for source lookup
        self.backend.execute("""
            CREATE INDEX IF NOT EXISTS idx_memory_units_source
            ON memory_units(source_type, source_id)
        """)

    def store(self, unit: MemoryUnit) -> None:
        """
        Store a memory unit.

        Args:
            unit: MemoryUnit to store
        """
        data = unit.to_dict()
        self.backend.execute("""
            INSERT OR REPLACE INTO memory_units
            (id, content, embedding, source_type, source_id, metadata, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            data["id"],
            data["content"],
            data["embedding"],
            data["source_type"],
            data["source_id"],
            data["metadata"],
            data["created_at"],
        ))

    def store_batch(self, units: list[MemoryUnit]) -> None:
        """
        Store multiple memory units.

        Args:
            units: List of MemoryUnits to store
        """
        params_list = []
        for unit in units:
            data = unit.to_dict()
            params_list.append((
                data["id"],
                data["content"],
                data["embedding"],
                data["source_type"],
                data["source_id"],
                data["metadata"],
                data["created_at"],
            ))

        self.backend.execute_many("""
            INSERT OR REPLACE INTO memory_units
            (id, content, embedding, source_type, source_id, metadata, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, params_list)

    def get(self, unit_id: str) -> MemoryUnit | None:
        """
        Get a memory unit by ID.

        Args:
            unit_id: ID of the memory unit

        Returns:
            MemoryUnit if found, None otherwise
        """
        result = self.backend.fetch_one(
            "SELECT * FROM memory_units WHERE id = ?",
            (unit_id,)
        )
        if result is None:
            return None
        return MemoryUnit.from_dict(result)

    def delete(self, unit_id: str) -> bool:
        """
        Delete a memory unit by ID.

        Args:
            unit_id: ID of the memory unit

        Returns:
            True if deleted, False if not found
        """
        # Check if exists first
        existing = self.get(unit_id)
        if existing is None:
            return False

        self.backend.execute(
            "DELETE FROM memory_units WHERE id = ?",
            (unit_id,)
        )
        return True

    def retrieve(
        self,
        query: str,
        limit: int = 10,
        source_type: str | None = None,
        source_id: str | None = None,
    ) -> list[RetrievalResult]:
        """
        Retrieve memory units matching a query.

        Uses keyword search for SQLite, hybrid search for PostgreSQL.

        Args:
            query: Search query
            limit: Maximum results to return
            source_type: Optional filter by source type
            source_id: Optional filter by source ID

        Returns:
            List of RetrievalResults ordered by relevance
        """
        # Build WHERE clause for filters
        where_parts = []
        params: list[Any] = []

        if source_type:
            where_parts.append("source_type = ?")
            params.append(source_type)

        if source_id:
            where_parts.append("source_id = ?")
            params.append(source_id)

        # Keyword search using LIKE
        # Split query into words and search for each
        words = query.lower().split()
        if words:
            word_conditions = []
            for word in words:
                word_conditions.append("LOWER(content) LIKE ?")
                params.append(f"%{word}%")
            where_parts.append(f"({' OR '.join(word_conditions)})")

        where_clause = " AND ".join(where_parts) if where_parts else "1=1"

        sql = f"""
            SELECT * FROM memory_units
            WHERE {where_clause}
            ORDER BY created_at DESC
            LIMIT ?
        """
        params.append(limit)

        rows = self.backend.fetch_all(sql, tuple(params))

        results = []
        for row in rows:
            unit = MemoryUnit.from_dict(row)
            # Simple scoring based on word matches
            content_lower = unit.content.lower()
            matches = sum(1 for word in words if word in content_lower)
            score = matches / len(words) if words else 0.0

            results.append(RetrievalResult(
                memory_unit=unit,
                score=score,
                match_type="keyword",
            ))

        # Sort by score descending
        results.sort(key=lambda r: r.score, reverse=True)
        return results

    def retrieve_by_source(
        self,
        source_type: str,
        source_id: str,
        limit: int = 100,
    ) -> list[MemoryUnit]:
        """
        Retrieve all memory units from a specific source.

        Args:
            source_type: Source type to filter by
            source_id: Source ID to filter by
            limit: Maximum results

        Returns:
            List of MemoryUnits
        """
        rows = self.backend.fetch_all("""
            SELECT * FROM memory_units
            WHERE source_type = ? AND source_id = ?
            ORDER BY created_at DESC
            LIMIT ?
        """, (source_type, source_id, limit))

        return [MemoryUnit.from_dict(row) for row in rows]

    def count(self) -> int:
        """Get total count of memory units."""
        result = self.backend.fetch_one("SELECT COUNT(*) as count FROM memory_units")
        return result["count"] if result else 0

    def clear(self) -> None:
        """Delete all memory units."""
        self.backend.execute("DELETE FROM memory_units")
