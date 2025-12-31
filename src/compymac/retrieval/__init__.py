"""
Retrieval module for CompyMac memory system.

Provides embedding generation and hybrid retrieval capabilities.
"""

from compymac.retrieval.embedder import VeniceEmbedder
from compymac.retrieval.hybrid import HybridRetriever

__all__ = [
    "VeniceEmbedder",
    "HybridRetriever",
]
