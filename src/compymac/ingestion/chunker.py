"""
Document Chunker for splitting documents into memory units.

Provides configurable chunking with overlap for context preservation.
"""

import re
import uuid
from dataclasses import dataclass
from typing import Any


@dataclass
class Chunk:
    """A chunk of text from a document."""

    id: str
    content: str
    start_char: int
    end_char: int
    metadata: dict[str, Any]


class DocumentChunker:
    """
    Splits documents into chunks for storage in KnowledgeStore.

    Features:
    - Configurable chunk size and overlap
    - Sentence-aware splitting (tries to break at sentence boundaries)
    - Preserves metadata and position information
    """

    def __init__(
        self,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
        min_chunk_size: int = 100,
    ):
        """
        Initialize document chunker.

        Args:
            chunk_size: Target size of each chunk in characters
            chunk_overlap: Number of characters to overlap between chunks
            min_chunk_size: Minimum chunk size (smaller chunks are merged)
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_size = min_chunk_size

        # Sentence boundary pattern
        self._sentence_pattern = re.compile(r'(?<=[.!?])\s+')

    def chunk(
        self,
        text: str,
        doc_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> list[Chunk]:
        """
        Split text into chunks.

        Args:
            text: Text to chunk
            doc_id: Optional document ID for chunk IDs
            metadata: Optional metadata to include in each chunk

        Returns:
            List of Chunk objects
        """
        if not text or not text.strip():
            return []

        doc_id = doc_id or str(uuid.uuid4())
        metadata = metadata or {}

        # Split into sentences first
        sentences = self._split_sentences(text)

        # Build chunks from sentences
        chunks = []
        current_chunk = ""
        current_start = 0
        char_pos = 0

        for sentence in sentences:
            sentence_len = len(sentence)

            # If adding this sentence would exceed chunk size
            if len(current_chunk) + sentence_len > self.chunk_size and current_chunk:
                # Save current chunk
                chunks.append(Chunk(
                    id=f"{doc_id}-{len(chunks)}",
                    content=current_chunk.strip(),
                    start_char=current_start,
                    end_char=char_pos,
                    metadata={
                        **metadata,
                        "chunk_index": len(chunks),
                        "doc_id": doc_id,
                    },
                ))

                # Start new chunk with overlap
                overlap_text = self._get_overlap(current_chunk)
                current_chunk = overlap_text + sentence
                current_start = char_pos - len(overlap_text)
            else:
                current_chunk += sentence

            char_pos += sentence_len

        # Add final chunk if it meets minimum size
        if current_chunk.strip():
            if len(current_chunk.strip()) >= self.min_chunk_size or not chunks:
                chunks.append(Chunk(
                    id=f"{doc_id}-{len(chunks)}",
                    content=current_chunk.strip(),
                    start_char=current_start,
                    end_char=char_pos,
                    metadata={
                        **metadata,
                        "chunk_index": len(chunks),
                        "doc_id": doc_id,
                    },
                ))
            elif chunks:
                # Merge with previous chunk if too small
                prev_chunk = chunks[-1]
                chunks[-1] = Chunk(
                    id=prev_chunk.id,
                    content=prev_chunk.content + " " + current_chunk.strip(),
                    start_char=prev_chunk.start_char,
                    end_char=char_pos,
                    metadata=prev_chunk.metadata,
                )

        return chunks

    def _split_sentences(self, text: str) -> list[str]:
        """Split text into sentences."""
        # Split on sentence boundaries but keep the delimiter
        parts = self._sentence_pattern.split(text)

        # Reconstruct sentences with their trailing space
        sentences = []
        for i, part in enumerate(parts):
            if part:
                # Add space back if not the last part
                if i < len(parts) - 1:
                    sentences.append(part + " ")
                else:
                    sentences.append(part)

        return sentences if sentences else [text]

    def _get_overlap(self, text: str) -> str:
        """Get overlap text from end of chunk."""
        if len(text) <= self.chunk_overlap:
            return text

        # Try to break at word boundary
        overlap_text = text[-self.chunk_overlap:]
        space_idx = overlap_text.find(' ')
        if space_idx > 0:
            overlap_text = overlap_text[space_idx + 1:]

        return overlap_text
