"""
Hybrid Retriever combining sparse and dense retrieval.

Implements:
- Sparse retrieval (keyword/BM25-like)
- Dense retrieval (vector similarity)
- Reciprocal Rank Fusion (RRF) for merging results
- Optional cross-encoder reranking
"""

from dataclasses import dataclass
from typing import Any

from compymac.knowledge_store import KnowledgeStore, MemoryUnit, RetrievalResult


@dataclass
class HybridResult:
    """Result from hybrid retrieval with scores from each method."""

    memory_unit: MemoryUnit
    sparse_score: float
    dense_score: float
    rrf_score: float
    final_score: float


class HybridRetriever:
    """
    Hybrid retriever combining sparse and dense retrieval.

    Uses Reciprocal Rank Fusion (RRF) to merge results from both methods.
    """

    def __init__(
        self,
        store: KnowledgeStore,
        embedder: Any | None = None,
        rrf_k: int = 60,
        sparse_weight: float = 0.5,
        dense_weight: float = 0.5,
    ):
        """
        Initialize hybrid retriever.

        Args:
            store: KnowledgeStore to retrieve from
            embedder: Optional embedder for dense retrieval (VeniceEmbedder)
            rrf_k: RRF constant (default 60)
            sparse_weight: Weight for sparse retrieval in final score
            dense_weight: Weight for dense retrieval in final score
        """
        self.store = store
        self.embedder = embedder
        self.rrf_k = rrf_k
        self.sparse_weight = sparse_weight
        self.dense_weight = dense_weight

    def retrieve(
        self,
        query: str,
        limit: int = 10,
        source_type: str | None = None,
        source_id: str | None = None,
        use_dense: bool = True,
    ) -> list[RetrievalResult]:
        """
        Retrieve memory units using hybrid search.

        Args:
            query: Search query
            limit: Maximum results to return
            source_type: Optional filter by source type
            source_id: Optional filter by source ID
            use_dense: Whether to use dense retrieval (requires embedder)

        Returns:
            List of RetrievalResults ordered by relevance
        """
        # Get sparse results (keyword search)
        sparse_results = self._sparse_retrieve(
            query, limit * 2, source_type, source_id
        )

        # Get dense results if embedder available and requested
        dense_results: list[RetrievalResult] = []
        if use_dense and self.embedder is not None:
            dense_results = self._dense_retrieve(
                query, limit * 2, source_type, source_id
            )

        # If no dense results, just return sparse
        if not dense_results:
            return sparse_results[:limit]

        # Merge using RRF
        merged = self._rrf_merge(sparse_results, dense_results)

        # Return top results
        return merged[:limit]

    def _sparse_retrieve(
        self,
        query: str,
        limit: int,
        source_type: str | None = None,
        source_id: str | None = None,
    ) -> list[RetrievalResult]:
        """Perform sparse (keyword) retrieval."""
        return self.store.retrieve(
            query=query,
            limit=limit,
            source_type=source_type,
            source_id=source_id,
        )

    def _dense_retrieve(
        self,
        query: str,
        limit: int,
        source_type: str | None = None,
        source_id: str | None = None,
    ) -> list[RetrievalResult]:
        """
        Perform dense (vector) retrieval.

        Note: This is a simplified implementation that works with SQLite.
        For production, use PostgreSQL with pgvector for efficient similarity search.
        """
        if self.embedder is None:
            return []

        # Get query embedding
        query_embedding = self.embedder.embed(query)

        # Get all memory units (inefficient for large datasets - use pgvector in production)
        # Build WHERE clause for filters
        where_parts = []
        params: list[Any] = []

        if source_type:
            where_parts.append("source_type = ?")
            params.append(source_type)

        if source_id:
            where_parts.append("source_id = ?")
            params.append(source_id)

        where_clause = " AND ".join(where_parts) if where_parts else "1=1"

        sql = f"""
            SELECT * FROM memory_units
            WHERE {where_clause} AND embedding IS NOT NULL
            LIMIT 1000
        """

        rows = self.store.backend.fetch_all(sql, tuple(params))

        # Calculate cosine similarity for each
        results = []
        for row in rows:
            unit = MemoryUnit.from_dict(row)
            if unit.embedding is None:
                continue

            similarity = self._cosine_similarity(query_embedding, unit.embedding)
            results.append(RetrievalResult(
                memory_unit=unit,
                score=similarity,
                match_type="vector",
            ))

        # Sort by similarity descending
        results.sort(key=lambda r: r.score, reverse=True)
        return results[:limit]

    def _cosine_similarity(self, a: list[float], b: list[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        if len(a) != len(b):
            return 0.0

        dot_product = sum(x * y for x, y in zip(a, b, strict=True))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return dot_product / (norm_a * norm_b)

    def _rrf_merge(
        self,
        sparse_results: list[RetrievalResult],
        dense_results: list[RetrievalResult],
    ) -> list[RetrievalResult]:
        """
        Merge results using Reciprocal Rank Fusion.

        RRF score = sum(1 / (k + rank)) for each result list
        """
        # Build ID -> rank mapping for each result list
        sparse_ranks: dict[str, int] = {}
        for i, result in enumerate(sparse_results):
            sparse_ranks[result.memory_unit.id] = i + 1

        dense_ranks: dict[str, int] = {}
        for i, result in enumerate(dense_results):
            dense_ranks[result.memory_unit.id] = i + 1

        # Collect all unique memory units
        all_units: dict[str, MemoryUnit] = {}
        for result in sparse_results:
            all_units[result.memory_unit.id] = result.memory_unit
        for result in dense_results:
            all_units[result.memory_unit.id] = result.memory_unit

        # Calculate RRF scores
        merged_results = []
        for unit_id, unit in all_units.items():
            sparse_rank = sparse_ranks.get(unit_id, len(sparse_results) + 1)
            dense_rank = dense_ranks.get(unit_id, len(dense_results) + 1)

            sparse_rrf = 1.0 / (self.rrf_k + sparse_rank)
            dense_rrf = 1.0 / (self.rrf_k + dense_rank)

            # Weighted combination
            rrf_score = (
                self.sparse_weight * sparse_rrf +
                self.dense_weight * dense_rrf
            )

            merged_results.append(RetrievalResult(
                memory_unit=unit,
                score=rrf_score,
                match_type="hybrid",
            ))

        # Sort by RRF score descending
        merged_results.sort(key=lambda r: r.score, reverse=True)
        return merged_results
