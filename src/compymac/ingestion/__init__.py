"""
Document Ingestion Pipeline for CompyMac memory system.

Provides document parsing, chunking, and ingestion into KnowledgeStore.

Phase 5: Librarian sub-agent for document library interaction (see librarian_agent.py).
Phase 6: Pluggable OCR provider for vision-based text extraction.
"""

from compymac.ingestion.chunker import DocumentChunker
from compymac.ingestion.librarian_agent import LibrarianAgent, create_librarian_tool_handler
from compymac.ingestion.ocr_provider import OCRClient, OCRResult
from compymac.ingestion.pipeline import IngestionPipeline

__all__ = [
    "DocumentChunker",
    "IngestionPipeline",
    "LibrarianAgent",
    "OCRClient",
    "OCRResult",
    "create_librarian_tool_handler",
]
