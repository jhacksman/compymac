"""
Document Ingestion Pipeline for CompyMac memory system.

Provides document parsing, chunking, and ingestion into KnowledgeStore.
"""

from compymac.ingestion.chunker import DocumentChunker
from compymac.ingestion.pipeline import IngestionPipeline

__all__ = [
    "DocumentChunker",
    "IngestionPipeline",
]
