"""Mock Venice API client for testing."""

from typing import Dict, Any, List, Optional
from unittest.mock import AsyncMock, MagicMock

from memory.exceptions import VeniceAPIError
from memory.message_types import MemoryResponse, MemoryMetadata

class MockVeniceAPI:
    """Mock Venice API client for testing."""

    def __init__(self, *args, **kwargs):
        """Initialize mock client."""
        self.store_memory = AsyncMock(return_value=MemoryResponse(
            action="store_memory",
            success=True,
            memory_id="test_id"
        ))
        self.retrieve_context = AsyncMock(return_value=MemoryResponse(
            action="retrieve_context",
            success=True,
            memories=[{
                "id": "test_id",
                "content": "test content",
                "metadata": MemoryMetadata(
                    timestamp=1708300208,
                    importance=0.8,
                    tags=["test"]
                ).asdict()
            }]
        ))
        self.update_memory = AsyncMock(return_value=MemoryResponse(
            action="update_memory",
            success=True,
            memory_id="test_id"
        ))
        self.delete_memory = AsyncMock(return_value=MemoryResponse(
            action="delete_memory",
            success=True,
            memory_id="test_id"
        ))
        self.prune_memories = AsyncMock(return_value=MemoryResponse(
            action="prune_memories",
            success=True,
            memory_id="test_id"
        ))
        self.search_memories = AsyncMock(return_value=MemoryResponse(
            action="search_memories",
            success=True,
            memories=[{
                "id": "test_id",
                "content": "test content",
                "metadata": MemoryMetadata(
                    timestamp=1708300208,
                    importance=0.8,
                    tags=["test"]
                ).asdict()
            }]
        ))
