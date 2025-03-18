"""Test configuration and fixtures."""
import os
import pytest
import pytest_asyncio
from unittest.mock import Mock, AsyncMock
import asyncio
import json

from memory.message_types import MemoryMetadata, MemoryResponse
from memory.venice_client import VeniceClient
from memory.db import MemoryDB
from memory.librarian import LibrarianAgent
from .mock_memory_db import MockMemoryDB

# Mock LLM for testing
class MockLLM:
    """Mock LLM for testing."""
    def __init__(self, response=None):
        self._response = response or {}
        
    async def apredict(self, *args, **kwargs):
        """Mock async prediction."""
        if isinstance(self._response, Exception):
            raise self._response
        return json.dumps(self._response)
        
    def predict(self, *args, **kwargs):
        """Mock sync prediction."""
        if isinstance(self._response, Exception):
            raise self._response
        return json.dumps(self._response)
        
    # Implement Runnable interface
    def invoke(self, *args, **kwargs):
        """Implement Runnable.invoke."""
        return self.predict(*args, **kwargs)
        
    async def ainvoke(self, *args, **kwargs):
        """Implement Runnable.ainvoke."""
        return await self.apredict(*args, **kwargs)
        
    async def astream(self, *args, **kwargs):
        """Implement Runnable.astream."""
        yield await self.apredict(*args, **kwargs)
        
    def stream(self, *args, **kwargs):
        """Implement Runnable.stream."""
        yield self.predict(*args, **kwargs)

@pytest.fixture
def mock_llm():
    """Create mock LLM."""
    return MockLLM()

@pytest_asyncio.fixture
async def mock_memory_db():
    """Create mock memory database."""
    db = MockMemoryDB()
    yield db
    await db.cleanup()

@pytest_asyncio.fixture
async def mock_venice_client():
    """Create mock Venice client."""
    client = Mock(spec=VeniceClient)
    
    async def mock_store(*args, **kwargs):
        return MemoryResponse(
            action="store_memory",
            success=True,
            memory_id="test_id"
        )
    
    async def mock_retrieve(*args, **kwargs):
        return MemoryResponse(
            action="retrieve_context",
            success=True,
            memories=[{
                "id": "test_id",
                "content": "test content",
                "metadata": {
                    "timestamp": 1234567890,
                    "importance": 0.8
                }
            }]
        )
    
    async def mock_embedding(*args, **kwargs):
        return MemoryResponse(
            action="get_embedding",
            success=True,
            embedding=[0.1] * 1536
        )
    
    client.store_memory = AsyncMock(side_effect=mock_store)
    client.retrieve_context = AsyncMock(side_effect=mock_retrieve)
    client.get_embedding = AsyncMock(side_effect=mock_embedding)
    return client

@pytest_asyncio.fixture
async def librarian(mock_venice_client, mock_memory_db):
    """Create librarian agent with mocks."""
    agent = LibrarianAgent(
        venice_client=mock_venice_client,
        importance_threshold=0.5,
        max_context_size=10
    )
    agent._shared_memories = []  # Reset shared memories
    return agent

# Skip desktop automation tests in CI
def pytest_collection_modifyitems(config, items):
    """Skip desktop automation tests in CI."""
    if os.environ.get("CI"):
        skip_desktop = pytest.mark.skip(reason="Desktop automation tests disabled in CI")
        for item in items:
            if "desktop" in item.keywords:
                item.add_marker(skip_desktop)

class MockResponse:
    """Mock HTTP response for testing."""
    def __init__(self, json_data, status_code=200):
        self.json_data = json_data
        self.status_code = status_code
        
    async def json(self):
        """Return mock JSON data."""
        return self.json_data
        
    async def __aenter__(self):
        """Async context manager enter."""
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        pass
