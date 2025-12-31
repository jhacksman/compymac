"""
Document Ingestion Pipeline for CompyMac memory system.

Orchestrates: parse → chunk → embed → store
"""

import hashlib
import time
import uuid
from pathlib import Path
from typing import Any

from compymac.ingestion.chunker import DocumentChunker
from compymac.ingestion.parsers import DocumentParser
from compymac.knowledge_store import KnowledgeStore, MemoryUnit


class IngestionPipeline:
    """
    Pipeline for ingesting documents into KnowledgeStore.

    Orchestrates the full flow:
    1. Parse document to extract text
    2. Chunk text into manageable pieces
    3. Optionally embed chunks
    4. Store chunks as memory units
    """

    def __init__(
        self,
        store: KnowledgeStore,
        embedder: Any | None = None,
        chunker: DocumentChunker | None = None,
        parser: DocumentParser | None = None,
    ):
        """
        Initialize ingestion pipeline.

        Args:
            store: KnowledgeStore to store chunks in
            embedder: Optional embedder for generating embeddings
            chunker: Optional custom chunker (default: DocumentChunker)
            parser: Optional custom parser (default: DocumentParser)
        """
        self.store = store
        self.embedder = embedder
        self.chunker = chunker or DocumentChunker()
        self.parser = parser or DocumentParser()

    def ingest(
        self,
        file_path: Path | str,
        source_type: str = "document",
        metadata: dict[str, Any] | None = None,
        generate_embeddings: bool = True,
    ) -> str:
        """
        Ingest a document into the KnowledgeStore.

        Args:
            file_path: Path to the document
            source_type: Type of source (e.g., 'document', 'book', 'article')
            metadata: Optional additional metadata
            generate_embeddings: Whether to generate embeddings for chunks

        Returns:
            Document ID

        Raises:
            FileNotFoundError: If file does not exist
            ValueError: If file format is not supported
        """
        file_path = Path(file_path)
        metadata = metadata or {}

        # Generate document ID from file content hash
        doc_id = self._generate_doc_id(file_path)

        # Parse document
        parse_result = self.parser.parse(file_path)

        # Chunk text
        chunks = self.chunker.chunk(
            text=parse_result.text,
            doc_id=doc_id,
            metadata={
                **parse_result.metadata,
                **metadata,
            },
        )

        # Generate embeddings if requested and embedder available
        embeddings: list[list[float] | None] = [None] * len(chunks)
        if generate_embeddings and self.embedder is not None:
            texts = [chunk.content for chunk in chunks]
            embeddings = self.embedder.embed_batch(texts)

        # Store chunks as memory units
        memory_units = []
        for i, chunk in enumerate(chunks):
            unit = MemoryUnit(
                id=chunk.id,
                content=chunk.content,
                embedding=embeddings[i] if i < len(embeddings) else None,
                source_type=source_type,
                source_id=doc_id,
                metadata={
                    **chunk.metadata,
                    "start_char": chunk.start_char,
                    "end_char": chunk.end_char,
                },
                created_at=time.time(),
            )
            memory_units.append(unit)

        # Batch store
        self.store.store_batch(memory_units)

        return doc_id

    def ingest_text(
        self,
        text: str,
        source_id: str | None = None,
        source_type: str = "text",
        metadata: dict[str, Any] | None = None,
        generate_embeddings: bool = True,
    ) -> str:
        """
        Ingest raw text into the KnowledgeStore.

        Args:
            text: Text to ingest
            source_id: Optional source ID (generated if not provided)
            source_type: Type of source
            metadata: Optional additional metadata
            generate_embeddings: Whether to generate embeddings

        Returns:
            Source ID
        """
        metadata = metadata or {}
        source_id = source_id or str(uuid.uuid4())

        # Chunk text
        chunks = self.chunker.chunk(
            text=text,
            doc_id=source_id,
            metadata=metadata,
        )

        # Generate embeddings if requested and embedder available
        embeddings: list[list[float] | None] = [None] * len(chunks)
        if generate_embeddings and self.embedder is not None:
            texts = [chunk.content for chunk in chunks]
            embeddings = self.embedder.embed_batch(texts)

        # Store chunks as memory units
        memory_units = []
        for i, chunk in enumerate(chunks):
            unit = MemoryUnit(
                id=chunk.id,
                content=chunk.content,
                embedding=embeddings[i] if i < len(embeddings) else None,
                source_type=source_type,
                source_id=source_id,
                metadata={
                    **chunk.metadata,
                    "start_char": chunk.start_char,
                    "end_char": chunk.end_char,
                },
                created_at=time.time(),
            )
            memory_units.append(unit)

        # Batch store
        self.store.store_batch(memory_units)

        return source_id

    def _generate_doc_id(self, file_path: Path) -> str:
        """Generate document ID from file content hash."""
        content = file_path.read_bytes()
        hash_hex = hashlib.sha256(content).hexdigest()[:16]
        return f"doc-{hash_hex}"

    def delete_document(self, doc_id: str) -> int:
        """
        Delete all chunks from a document.

        Args:
            doc_id: Document ID to delete

        Returns:
            Number of chunks deleted
        """
        # Get all chunks for this document
        units = self.store.retrieve_by_source(
            source_type="document",
            source_id=doc_id,
            limit=10000,
        )

        # Delete each chunk
        deleted = 0
        for unit in units:
            if self.store.delete(unit.id):
                deleted += 1

        return deleted
