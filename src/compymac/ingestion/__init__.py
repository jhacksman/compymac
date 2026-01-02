"""
Document Ingestion Pipeline for CompyMac memory system.

Provides document parsing, chunking, and ingestion into KnowledgeStore.

Phase 5: Includes librarian tools for agent integration.
"""

from compymac.ingestion.chunker import DocumentChunker
from compymac.ingestion.librarian_tools import (
    create_librarian_tools,
    get_librarian_tool_schemas,
)
from compymac.ingestion.pipeline import IngestionPipeline

__all__ = [
    "DocumentChunker",
    "IngestionPipeline",
    "create_librarian_tools",
    "get_librarian_tool_schemas",
]
