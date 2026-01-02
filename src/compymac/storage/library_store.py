"""
Library Store for managing user document collections.

Provides in-memory storage for Phase 1, with hooks for persistent storage later.
"""

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


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
        }


class LibraryStore:
    """
    In-memory storage for user document libraries.

    Phase 1: In-memory only
    Phase 4: Will add persistent storage backend
    """

    def __init__(self) -> None:
        self._documents: dict[str, LibraryDocument] = {}
        self._user_documents: dict[str, list[str]] = {}  # user_id -> [doc_ids]
        self._active_sources: dict[str, list[str]] = {}  # session_id -> [doc_ids]

    def create_document(
        self,
        user_id: str,
        filename: str,
        title: str | None = None,
        file_path: str | None = None,
        file_size_bytes: int = 0,
    ) -> LibraryDocument:
        """Create a new document entry in the library."""
        doc_id = str(uuid.uuid4())
        now = time.time()

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
    ) -> LibraryDocument | None:
        """Update a document's properties."""
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
        if metadata is not None:
            doc.metadata.update(metadata)

        doc.updated_at = time.time()
        return doc

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

    # Search within documents (Phase 4: will use vector search)

    def search_chunks(
        self,
        query: str,
        doc_ids: list[str] | None = None,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        """
        Search for relevant chunks in documents.

        Phase 1: Simple keyword matching
        Phase 4: Vector similarity search
        """
        results = []

        # Get documents to search
        if doc_ids:
            docs = [self._documents[d] for d in doc_ids if d in self._documents]
        else:
            docs = list(self._documents.values())

        # Simple keyword search (Phase 1)
        query_lower = query.lower()
        for doc in docs:
            for chunk in doc.chunks:
                content = chunk.get("content", "").lower()
                if query_lower in content:
                    results.append({
                        "document_id": doc.id,
                        "document_title": doc.title,
                        "chunk_id": chunk.get("id", ""),
                        "content": chunk.get("content", ""),
                        "page": chunk.get("metadata", {}).get("page", 0),
                        "score": content.count(query_lower),  # Simple relevance
                    })

        # Sort by score and return top_k
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]
