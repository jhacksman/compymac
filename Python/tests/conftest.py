"""Test fixtures for memory system tests."""

import os
import uuid
import time
import asyncio
import pytest
import pytest_asyncio
from datetime import datetime
from unittest.mock import Mock, AsyncMock, MagicMock

from memory.message_types import MemoryMetadata, MemoryResponse
from memory.venice_client import VeniceClient
from memory.librarian import LibrarianAgent

# Global memory store for tests
_test_memories = []

# Set test environment variables if not already set
if not os.getenv("VENICE_API_KEY"):
    os.environ["VENICE_API_KEY"] = "test-key"
if not os.getenv("VENICE_BASE_URL"):
    os.environ["VENICE_BASE_URL"] = "https://api.venice.ai"
if not os.getenv("VENICE_MODEL"):
    os.environ["VENICE_MODEL"] = "llama-3.3-70b"

# Get environment variables
VENICE_API_KEY = os.getenv("VENICE_API_KEY")
VENICE_BASE_URL = os.getenv("VENICE_BASE_URL")
VENICE_MODEL = os.getenv("VENICE_MODEL")

@pytest_asyncio.fixture(scope="function")
async def venice_client():
    """Create mock Venice client for testing."""
    client = MagicMock(spec=VeniceClient)
    
    async def mock_store_memory(content, metadata=None):
        """Mock store_memory with async behavior."""
        memory_id = str(uuid.uuid4())
        
        # Create default metadata if none provided
        if metadata is None:
            metadata = MemoryMetadata(
                timestamp=datetime.now().timestamp(),
                importance=0.0,
                context_ids=[],
                tags=[],
                source=None,
                task_id=None
            )
            
        # Convert metadata to dict for storage
        if isinstance(metadata, MemoryMetadata):
            metadata_dict = {
                "timestamp": metadata.timestamp,
                "importance": metadata.importance or 0.0,
                "context_ids": metadata.context_ids or [],
                "tags": metadata.tags or [],
                "source": metadata.source,
                "task_id": metadata.task_id
            }
        else:
            metadata_dict = dict(metadata)
            
        # Create memory entry
        memory = {
            "id": memory_id,
            "content": content,
            "metadata": metadata_dict,
            "timestamp": datetime.now().timestamp()
        }
        
        # Store memory
        _test_memories.append(memory)
        
        # Add small delay to simulate network latency
        await asyncio.sleep(0.1)
        
        response = MemoryResponse(
            action="store_memory",
            success=True,
            memory_id=memory_id,
            content=content,
            metadata=metadata_dict
        )
        
        return response
        
    async def mock_retrieve_context(query=None, context_id=None, **kwargs):
        """Mock retrieve_context with async behavior."""
        # Add small delay to simulate network latency
        await asyncio.sleep(0.1)
        
        memories = []
        for memory in _test_memories:
            metadata = memory.get("metadata", {})
            if not isinstance(metadata, dict):
                continue
                
            context_ids = metadata.get("context_ids", [])
            if not context_id or context_id in context_ids:
                # Create a copy to avoid modifying original
                memory_copy = {
                    "id": memory["id"],
                    "content": memory["content"],
                    "metadata": dict(metadata),  # Make a copy of metadata
                    "timestamp": memory.get("timestamp", datetime.now().timestamp())
                }
                memories.append(memory_copy)
                
        return MemoryResponse(
            action="retrieve_context",
            success=True,
            memories=memories
        )
        
    async def mock_update_memory(memory_id, content=None, metadata=None):
        """Mock update_memory with async behavior."""
        # Add small delay to simulate network latency
        await asyncio.sleep(0.1)
        
        for memory in _test_memories:
            if memory["id"] == memory_id:
                if content is not None:
                    memory["content"] = content
                if metadata is not None:
                    memory["metadata"] = metadata
                memory["timestamp"] = datetime.now().timestamp()
                break
                
        return MemoryResponse(
            action="update_memory",
            success=True
        )
        
    async def mock_delete_memory(memory_id):
        """Mock delete_memory with async behavior."""
        # Add small delay to simulate network latency
        await asyncio.sleep(0.1)
        
        # Remove memory if it exists
        for i, memory in enumerate(_test_memories):
            if memory["id"] == memory_id:
                _test_memories.pop(i)
                break
                
        return MemoryResponse(
            action="delete_memory",
            success=True
        )
        
    # Set up async mock methods
    client.store_memory = AsyncMock(side_effect=mock_store_memory)
    client.retrieve_context = AsyncMock(side_effect=mock_retrieve_context)
    client.update_memory = AsyncMock(side_effect=mock_update_memory)
    client.delete_memory = AsyncMock(side_effect=mock_delete_memory)
    
    return client

@pytest_asyncio.fixture(scope="function")
async def librarian(venice_client):
    """Create librarian with Venice client."""
    agent = LibrarianAgent(venice_client)
    
    # Clear memories at start
    _test_memories.clear()
    agent.recent_memories.clear()
    LibrarianAgent._shared_memories.clear()
    
    try:
        yield agent
    finally:
        # Clear any shared memories
        agent.recent_memories.clear()
        LibrarianAgent._shared_memories.clear()
        _test_memories.clear()
