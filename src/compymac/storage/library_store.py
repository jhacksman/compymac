"""
Library Store for managing user document collections.

Provides in-memory storage for Phase 1, with hooks for persistent storage later.

Phase 4 additions:
- Vector embeddings for semantic search
- Hybrid search (keyword + vector)
"""

import math
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

# Try to import Venice embedder for vector search
try:
    from compymac.retrieval.embedder import VeniceEmbedder
    EMBEDDER_AVAILABLE = True
except ImportError:
    EMBEDDER_AVAILABLE = False
    VeniceEmbedder = None  # type: ignore[misc, assignment]


class DocumentStatus(str, Enum):
    """Status of a document in the library."""
    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


@dataclass
class LibraryDocument:
    """A document in the user's library."""
    id: str
    user_id: str
    filename: str
    title: str
    page_count: int
    status: DocumentStatus
    created_at: float
    updated_at: float
    file_path: str | None = None
    file_size_bytes: int = 0
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    chunks: list[dict[str, Any]] = field(default_factory=list)
    # Folder structure support
    library_path: str = ""  # e.g., "Humble Bundle 2025/Programming/Clean Code.pdf"
    doc_format: str = "pdf"  # "pdf" | "epub"
    # Document navigation (TOC/bookmarks)
    navigation: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "filename": self.filename,
            "title": self.title,
            "page_count": self.page_count,
            "status": self.status.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "file_size_bytes": self.file_size_bytes,
            "error": self.error,
            "chunk_count": len(self.chunks),
            "library_path": self.library_path,
            "doc_format": self.doc_format,
            "navigation": self.navigation,
        }


class LibraryStore:
    """
    In-memory storage for user document libraries.

    Phase 1: In-memory only
    Phase 4: Vector embeddings for semantic search
    """

    def __init__(
        self,
        use_embeddings: bool = True,
        embedder_api_key: str | None = None,
    ) -> None:
        """
        Initialize library store.

        Args:
            use_embeddings: Whether to use vector embeddings for search
            embedder_api_key: API key for embedder (uses env var if None)
        """
        self._documents: dict[str, LibraryDocument] = {}
        self._user_documents: dict[str, list[str]] = {}  # user_id -> [doc_ids]
        self._active_sources: dict[str, list[str]] = {}  # session_id -> [doc_ids]

        # Phase 4: Vector embeddings storage
        self._chunk_embeddings: dict[str, list[float]] = {}  # chunk_id -> embedding
        self._embedder: VeniceEmbedder | None = None
        self.use_embeddings = use_embeddings and EMBEDDER_AVAILABLE

        if self.use_embeddings and VeniceEmbedder is not None:
            try:
                self._embedder = VeniceEmbedder(api_key=embedder_api_key)
            except (ValueError, Exception):
                # Embedder initialization failed (e.g., no API key)
                self.use_embeddings = False
                self._embedder = None

    def create_document(
        self,
        user_id: str,
        filename: str,
        title: str | None = None,
        file_path: str | None = None,
        file_size_bytes: int = 0,
        library_path: str = "",
        doc_format: str = "pdf",
    ) -> LibraryDocument:
        """Create a new document entry in the library."""
        doc_id = str(uuid.uuid4())
        now = time.time()

        # Default library_path to filename if not provided
        if not library_path:
            library_path = filename

        doc = LibraryDocument(
            id=doc_id,
            user_id=user_id,
            filename=filename,
            title=title or filename,
            page_count=0,
            status=DocumentStatus.PENDING,
            created_at=now,
            updated_at=now,
            file_path=file_path,
            file_size_bytes=file_size_bytes,
            library_path=library_path,
            doc_format=doc_format,
        )

        self._documents[doc_id] = doc

        if user_id not in self._user_documents:
            self._user_documents[user_id] = []
        self._user_documents[user_id].append(doc_id)

        return doc

    def get_document(self, doc_id: str) -> LibraryDocument | None:
        """Get a document by ID."""
        return self._documents.get(doc_id)

    def get_user_documents(self, user_id: str) -> list[LibraryDocument]:
        """Get all documents for a user."""
        doc_ids = self._user_documents.get(user_id, [])
        return [self._documents[doc_id] for doc_id in doc_ids if doc_id in self._documents]

    def update_document(
        self,
        doc_id: str,
        status: DocumentStatus | None = None,
        page_count: int | None = None,
        error: str | None = None,
        chunks: list[dict[str, Any]] | None = None,
        metadata: dict[str, Any] | None = None,
        navigation: list[dict[str, Any]] | None = None,
        generate_embeddings: bool = True,
    ) -> LibraryDocument | None:
        """
        Update a document's properties.

        Args:
            doc_id: Document ID
            status: New status
            page_count: New page count
            error: Error message
            chunks: New chunks (will generate embeddings if enabled)
            metadata: Additional metadata
            navigation: Document navigation (TOC/bookmarks)
            generate_embeddings: Whether to generate embeddings for new chunks
        """
        doc = self._documents.get(doc_id)
        if not doc:
            return None

        if status is not None:
            doc.status = status
        if page_count is not None:
            doc.page_count = page_count
        if error is not None:
            doc.error = error
        if chunks is not None:
            doc.chunks = chunks
            # Phase 4: Generate embeddings for chunks
            if generate_embeddings and self.use_embeddings:
                self._generate_chunk_embeddings(doc_id, chunks)
        if metadata is not None:
            doc.metadata.update(metadata)
        if navigation is not None:
            doc.navigation = navigation

        doc.updated_at = time.time()
        return doc

    def _generate_chunk_embeddings(
        self,
        doc_id: str,
        chunks: list[dict[str, Any]],
    ) -> None:
        """
        Generate embeddings for document chunks.

        Args:
            doc_id: Document ID
            chunks: List of chunks to embed
        """
        if not self._embedder or not chunks:
            return

        try:
            # Extract chunk contents
            chunk_texts = [chunk.get("content", "") for chunk in chunks]
            chunk_ids = [chunk.get("id", f"{doc_id}_{i}") for i, chunk in enumerate(chunks)]

            # Generate embeddings in batch
            embeddings = self._embedder.embed_batch(chunk_texts)

            # Store embeddings
            for chunk_id, embedding in zip(chunk_ids, embeddings, strict=True):
                self._chunk_embeddings[chunk_id] = embedding

        except Exception:
            # Embedding generation failed, continue without embeddings
            pass

    def delete_document(self, doc_id: str) -> bool:
        """Delete a document from the library."""
        doc = self._documents.get(doc_id)
        if not doc:
            return False

        del self._documents[doc_id]

        if doc.user_id in self._user_documents:
            self._user_documents[doc.user_id] = [
                d for d in self._user_documents[doc.user_id] if d != doc_id
            ]

        # Remove from active sources
        for session_id in self._active_sources:
            self._active_sources[session_id] = [
                d for d in self._active_sources[session_id] if d != doc_id
            ]

        return True

    # Active sources management (for retrieval scoping)

    def add_active_source(self, session_id: str, doc_id: str) -> bool:
        """Add a document to the active sources for a session."""
        if doc_id not in self._documents:
            return False

        if session_id not in self._active_sources:
            self._active_sources[session_id] = []

        if doc_id not in self._active_sources[session_id]:
            self._active_sources[session_id].append(doc_id)

        return True

    def remove_active_source(self, session_id: str, doc_id: str) -> bool:
        """Remove a document from the active sources for a session."""
        if session_id not in self._active_sources:
            return False

        if doc_id in self._active_sources[session_id]:
            self._active_sources[session_id].remove(doc_id)
            return True

        return False

    def get_active_sources(self, session_id: str) -> list[LibraryDocument]:
        """Get all active source documents for a session."""
        doc_ids = self._active_sources.get(session_id, [])
        return [self._documents[doc_id] for doc_id in doc_ids if doc_id in self._documents]

    def clear_active_sources(self, session_id: str) -> None:
        """Clear all active sources for a session."""
        if session_id in self._active_sources:
            del self._active_sources[session_id]

    # Search within documents (Phase 4: hybrid vector + keyword search)

    def search_chunks(
        self,
        query: str,
        doc_ids: list[str] | None = None,
        top_k: int = 5,
        use_vector_search: bool = True,
    ) -> list[dict[str, Any]]:
        """
        Search for relevant chunks in documents using hybrid search.

        Phase 4: Combines vector similarity with keyword matching.
        Falls back to keyword-only if embeddings unavailable.

        Args:
            query: Search query
            doc_ids: Optional list of document IDs to search within
            top_k: Number of results to return
            use_vector_search: Whether to use vector search (if available)

        Returns:
            List of matching chunks with scores
        """
        # Get documents to search
        if doc_ids:
            docs = [self._documents[d] for d in doc_ids if d in self._documents]
        else:
            docs = list(self._documents.values())

        # Collect all chunks from target documents
        all_chunks: list[tuple[LibraryDocument, dict[str, Any]]] = []
        for doc in docs:
            for chunk in doc.chunks:
                all_chunks.append((doc, chunk))

        if not all_chunks:
            return []

        # Phase 4: Try vector search if available
        vector_scores: dict[str, float] = {}
        if use_vector_search and self.use_embeddings and self._embedder:
            vector_scores = self._vector_search(query, all_chunks)

        # Keyword search (always performed for hybrid scoring)
        keyword_scores = self._keyword_search(query, all_chunks)

        # Combine scores (hybrid search)
        results = []
        for doc, chunk in all_chunks:
            chunk_id = chunk.get("id", "")
            vector_score = vector_scores.get(chunk_id, 0.0)
            keyword_score = keyword_scores.get(chunk_id, 0.0)

            # Skip chunks with no relevance
            if vector_score == 0.0 and keyword_score == 0.0:
                continue

            # Hybrid score: weighted combination
            # Vector similarity is more important when available
            if vector_score > 0:
                combined_score = 0.7 * vector_score + 0.3 * keyword_score
            else:
                combined_score = keyword_score

            results.append({
                "document_id": doc.id,
                "document_title": doc.title,
                "chunk_id": chunk_id,
                "content": chunk.get("content", ""),
                "page": chunk.get("metadata", {}).get("page", 0),
                "score": combined_score,
                "vector_score": vector_score,
                "keyword_score": keyword_score,
            })

        # Sort by combined score and return top_k
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    def _vector_search(
        self,
        query: str,
        chunks: list[tuple["LibraryDocument", dict[str, Any]]],
    ) -> dict[str, float]:
        """
        Perform vector similarity search.

        Args:
            query: Search query
            chunks: List of (document, chunk) tuples

        Returns:
            Dict mapping chunk_id to similarity score (0-1)
        """
        if not self._embedder:
            return {}

        try:
            # Get query embedding
            query_embedding = self._embedder.embed(query)

            # Calculate cosine similarity for each chunk
            scores: dict[str, float] = {}
            for _doc, chunk in chunks:
                chunk_id = chunk.get("id", "")
                if chunk_id in self._chunk_embeddings:
                    chunk_embedding = self._chunk_embeddings[chunk_id]
                    similarity = self._cosine_similarity(query_embedding, chunk_embedding)
                    # Normalize to 0-1 range (cosine similarity is -1 to 1)
                    scores[chunk_id] = (similarity + 1) / 2

            return scores

        except Exception:
            return {}

    def _keyword_search(
        self,
        query: str,
        chunks: list[tuple["LibraryDocument", dict[str, Any]]],
    ) -> dict[str, float]:
        """
        Perform keyword-based search.

        Args:
            query: Search query
            chunks: List of (document, chunk) tuples

        Returns:
            Dict mapping chunk_id to relevance score (0-1)
        """
        query_lower = query.lower()
        query_terms = query_lower.split()
        scores: dict[str, float] = {}

        for _doc, chunk in chunks:
            chunk_id = chunk.get("id", "")
            content = chunk.get("content", "").lower()

            # Count term matches
            term_matches = sum(1 for term in query_terms if term in content)
            if term_matches > 0:
                # Normalize by number of query terms
                scores[chunk_id] = term_matches / len(query_terms)

        return scores

    @staticmethod
    def _cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        if len(vec1) != len(vec2):
            return 0.0

        dot_product = sum(a * b for a, b in zip(vec1, vec2, strict=True))
        norm1 = math.sqrt(sum(a * a for a in vec1))
        norm2 = math.sqrt(sum(b * b for b in vec2))

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return dot_product / (norm1 * norm2)
