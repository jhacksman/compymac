"""Test fixtures for memory system tests."""

import os
import uuid
import time
import asyncio
import json
import pytest
import pytest_asyncio
from datetime import datetime
from unittest.mock import Mock, AsyncMock, MagicMock
from langchain.llms.base import BaseLLM
from langchain_core.outputs import LLMResult, Generation
from langchain_core.runnables import Runnable, RunnableConfig
from typing import Any, List, Optional, Iterator, AsyncIterator

from memory.message_types import MemoryMetadata, MemoryResponse
from memory.venice_client import VeniceClient
from memory.librarian import LibrarianAgent
from .mock_memory_db import MockMemoryDB
from .mock_websocket_server import MockWebSocketServer

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
            
        # Mock embedding and summary generation
        embedding = [0.1] * 1536
        summary = "Mock summary"
        
        # Create memory entry with embedding and summary
        memory = {
            "id": memory_id,
            "content": content,
            "metadata": metadata_dict,
            "embedding": embedding,
            "summary": summary,
            "timestamp": datetime.now().timestamp()
        }
        
        # Store memory
        _test_memories.append(memory)
        
        # Add small delay to simulate network latency
        await asyncio.sleep(0.1)
        
        return MemoryResponse(
            action="store_memory",
            success=True,
            memory_id=memory_id,
            embedding=embedding,
            summary=summary
        )
        
    async def mock_retrieve_context(query=None, context_id=None, **kwargs):
        """Mock retrieve_context with async behavior."""
        # Add small delay to simulate network latency
        await asyncio.sleep(0.1)
        
        # Return all test memories for simplicity in tests
        return MemoryResponse(
            action="retrieve_context",
            success=True,
            memories=_test_memories
        )
        
    async def mock_update_memory(memory_id, content=None, metadata=None):
        """Mock update_memory with async behavior."""
        # Add small delay to simulate network latency
        await asyncio.sleep(0.1)
        
        # Validate memory_id
        if not memory_id:
            raise Exception("Memory ID is required")
            
        found = False
        for memory in _test_memories:
            if memory["id"] == memory_id:
                found = True
                if content is not None:
                    memory["content"] = content
                if metadata is not None:
                    memory["metadata"] = metadata
                memory["timestamp"] = datetime.now().timestamp()
                memory["embedding"] = [0.1] * 1536  # Update embedding
                memory["summary"] = "Mock summary"  # Update summary
                return MemoryResponse(
                    action="update_memory",
                    success=True,
                    memory_id=memory_id,
                    embedding=[0.1] * 1536,
                    summary="Mock summary"
                )
                
        if not found:
            raise Exception(f"Memory {memory_id} not found")
        
    async def mock_delete_memory(memory_id):
        """Mock delete_memory with async behavior."""
        # Add small delay to simulate network latency
        await asyncio.sleep(0.1)
        
        found = False
        for i, memory in enumerate(_test_memories):
            if memory["id"] == memory_id:
                found = True
                _test_memories.pop(i)
                return MemoryResponse(
                    action="delete_memory",
                    success=True,
                    memory_id=memory_id
                )
                
        if not found:
            raise Exception(f"Memory {memory_id} not found")
        
    # Set up async mock methods
    client.store_memory = AsyncMock(side_effect=mock_store_memory)
    client.retrieve_context = AsyncMock(side_effect=mock_retrieve_context)
    client.update_memory = AsyncMock(side_effect=mock_update_memory)
    client.delete_memory = AsyncMock(side_effect=mock_delete_memory)
    
    return client

@pytest.fixture
def mock_llm():
    """Provide mock LLM."""
    class MockLLM(BaseLLM):
        """Mock LLM for testing."""
        from pydantic import Field, BaseModel, PrivateAttr
        
        class Config:
            arbitrary_types_allowed = True
            extra = "allow"
            underscore_attrs_are_private = True
            validate_assignment = True
            allow_inf_nan = True
        
        mock_response: Any = None
        
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self._lc_kwargs = kwargs
            self.mock_response = {
                "execution_plan": [{
                    "step": "Test step",
                    "verification": "Step complete"
                }],
                "success_criteria": {
                    "step_criteria": ["complete"],
                    "overall_criteria": "success"
                }
            }
            
        def _call(self, prompt: str, stop=None, run_manager=None, **kwargs) -> str:
            """Call the LLM."""
            if isinstance(self._response, Exception):
                raise self._response
            if isinstance(self._response, str):
                return self._response
            return json.dumps(self._response)
            
        async def _acall(self, prompt: str, stop=None, run_manager=None, **kwargs) -> str:
            """Call the LLM asynchronously."""
            if isinstance(self._response, Exception):
                raise self._response
            if isinstance(self._response, str):
                return self._response
            return json.dumps(self._response)
            
        def _format_response(self, response: Any) -> str:
            """Format response consistently."""
            if isinstance(response, Exception):
                raise response
            if isinstance(response, str):
                return response
            return json.dumps(response)
            
        def predict(self, **kwargs) -> str:
            """Sync predict method."""
            return self._call("", **kwargs)
            
        async def apredict(self, **kwargs) -> str:
            """Async predict method."""
            return await self._acall("", **kwargs)
            
        def run(self, **kwargs) -> str:
            """Sync run method."""
            return self._call("", **kwargs)
            
        async def arun(self, **kwargs) -> str:
            """Async run method."""
            return await self._acall("", **kwargs)
            
        def __getattr__(self, name):
            """Handle dynamic attribute access."""
            if name in ['predict', 'apredict', 'run', 'arun']:
                return getattr(self, name)
            if name == '_response':  # For backward compatibility
                return self.mock_response
            return super().__getattr__(name)
            
        def _generate(self, prompts: List[str], stop=None, run_manager=None, **kwargs) -> LLMResult:
            """Generate completions."""
            if isinstance(self._response, Exception):
                raise self._response
            response = self._response if isinstance(self._response, str) else json.dumps(self._response)
            return LLMResult(generations=[[Generation(text=response)]])
            
        async def _agenerate(self, prompts: List[str], stop=None, run_manager=None, **kwargs) -> LLMResult:
            """Generate completions asynchronously."""
            if isinstance(self._response, Exception):
                raise self._response
            response = self._response if isinstance(self._response, str) else json.dumps(self._response)
            return LLMResult(generations=[[Generation(text=response)]])
            
        def invoke(self, input: Any, config: Optional[RunnableConfig] = None) -> Any:
            """Invoke the LLM."""
            return self._call(input)
            
        async def ainvoke(self, input: Any, config: Optional[RunnableConfig] = None) -> Any:
            """Invoke the LLM asynchronously."""
            return await self._acall(input)
            
        def stream(self, input: Any, config: Optional[RunnableConfig] = None) -> Iterator[Any]:
            """Stream output."""
            yield self._call(input)
            
        async def astream(self, input: Any, config: Optional[RunnableConfig] = None) -> AsyncIterator[Any]:
            """Stream output asynchronously."""
            yield await self._acall(input)
            
        def transform(self, input: Any) -> Any:
            """Transform input."""
            return self._call(input)
            
        async def atransform(self, input: Any) -> Any:
            """Transform input asynchronously."""
            return await self._acall(input)
            
        def batch(self, inputs: List[Any], config: Optional[RunnableConfig] = None) -> List[Any]:
            """Process a batch of inputs."""
            return [self._call(input) for input in inputs]
            
        async def abatch(self, inputs: List[Any], config: Optional[RunnableConfig] = None) -> List[Any]:
            """Process a batch of inputs asynchronously."""
            return [await self._acall(input) for input in inputs]
            
        @property
        def _llm_type(self) -> str:
            """Get LLM type."""
            return "mock"
    
    return MockLLM()

@pytest.fixture
def mock_memory_db():
    """Provide mock memory database."""
    return MockMemoryDB()

@pytest.fixture
def mock_websocket_server():
    """Provide mock WebSocket server."""
    return MockWebSocketServer()

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
