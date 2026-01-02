"""
Document Ingestion Pipeline for CompyMac memory system.

Provides document parsing, chunking, and ingestion into KnowledgeStore.

Phase 5: Includes librarian tools for agent integration.
Phase 6: Pluggable OCR provider for vision-based text extraction.
"""

from compymac.ingestion.chunker import DocumentChunker
from compymac.ingestion.librarian_tools import (
    create_librarian_tools,
    get_librarian_tool_schemas,
)
from compymac.ingestion.ocr_provider import OCRClient, OCRResult
from compymac.ingestion.pipeline import IngestionPipeline

__all__ = [
    "DocumentChunker",
    "IngestionPipeline",
    "OCRClient",
    "OCRResult",
    "create_librarian_tools",
    "get_librarian_tool_schemas",
]
