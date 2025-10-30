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
from langchain_core.runnables import Runnable
from typing import Any, List
from langchain_core.outputs import LLMResult, Generation

try:
    from langchain.chains import LLMChain
    from langchain_core.runnables import RunnableSequence
    
    if not hasattr(LLMChain, "predict"):
        def _llmchain_predict(self, **kwargs):
            return self.invoke(kwargs)
        async def _llmchain_apredict(self, **kwargs):
            return await self.ainvoke(kwargs)
        LLMChain.predict = _llmchain_predict
        LLMChain.apredict = _llmchain_apredict
    
    if not hasattr(RunnableSequence, "predict"):
        def _rs_predict(self, **kwargs):
            return self.invoke(kwargs)
        async def _rs_apredict(self, **kwargs):
            return await self.ainvoke(kwargs)
        RunnableSequence.predict = _rs_predict
        RunnableSequence.apredict = _rs_apredict
except ImportError:
    pass

class MockResponse:
    """Mock HTTP response for testing."""
    def __init__(self, status_code=200, json_data=None, text="", content=b""):
        self.status_code = status_code
        self._json = json_data or {}
        self.text = text
        self.content = content
    
    @property
    def ok(self):
        return 200 <= self.status_code < 300
    
    def json(self):
        return self._json
    
    def raise_for_status(self):
        if not self.ok:
            raise Exception(f"HTTP {self.status_code}")

class MockLLM(Runnable):
    """Mock LLM for testing that implements Runnable interface with extra fields allowed."""
    
    class Config:
        extra = "allow"
        arbitrary_types_allowed = True
    
    def __init__(self, response=None):
        super().__init__()
        self._response = response if response is not None else ""
        self._generate = None
    
    def __setattr__(self, name, value):
        """Allow setting _generate for test monkeypatching."""
        if name == "_generate":
            object.__setattr__(self, name, value)
            return
        super().__setattr__(name, value)
    
    def _render(self, input_):
        """Render response based on input."""
        if isinstance(self._response, Exception):
            raise self._response
        if callable(self._response):
            return self._response(input_)
        if isinstance(self._response, (dict, list)):
            return json.dumps(self._response)
        return str(self._response)
    
    def generate(self, prompts: List[str], **kwargs) -> LLMResult:
        """Generate method for BaseLanguageModel compatibility."""
        if callable(self._generate):
            return self._generate(prompts, **kwargs)
        texts = [self._render(prompts[0] if prompts else "")]
        return LLMResult(generations=[[Generation(text=t) for t in texts]])
    
    async def agenerate(self, prompts: List[str], **kwargs) -> LLMResult:
        """Async generate method for BaseLanguageModel compatibility."""
        return self.generate(prompts, **kwargs)
    
    def invoke(self, input, config=None, **kwargs):
        """Runnable protocol: invoke."""
        return self._render(input)
    
    async def ainvoke(self, input, config=None, **kwargs):
        """Runnable protocol: async invoke."""
        return self._render(input)
    
    def batch(self, inputs, config=None, **kwargs):
        """Runnable protocol: batch."""
        return [self._render(x) for x in inputs]
    
    async def abatch(self, inputs, config=None, **kwargs):
        """Runnable protocol: async batch."""
        return [self._render(x) for x in inputs]
    
    def __call__(self, input, **kwargs):
        """Make callable for prompt | llm usage."""
        return self._render(input)
    
    def predict(self, *args, **kwargs):
        """Backward-compat: sync prediction."""
        input_ = args[0] if args else kwargs.get("input", "")
        return self._render(input_)
    
    async def apredict(self, *args, **kwargs):
        """Backward-compat: async prediction."""
        input_ = args[0] if args else kwargs.get("input", "")
        return self._render(input_)

@pytest.fixture
def mock_llm_memory():
    """Create mock LLM for memory tests."""
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
