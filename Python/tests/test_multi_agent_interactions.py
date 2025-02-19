"""Tests for multi-agent interactions."""
import pytest
from datetime import datetime
from memory.message_types import MemoryMetadata
from memory.librarian import LibrarianAgent
from memory.venice_client import VeniceClient
from unittest.mock import Mock, AsyncMock

@pytest.fixture
def mock_venice_client():
    """Create mock Venice client."""
    client = Mock(spec=VeniceClient)
    
    async def mock_store(*args, **kwargs):
        return {"success": True, "memory_id": "test_id"}
    
    async def mock_retrieve(*args, **kwargs):
        return {
            "success": True,
            "memories": [{
                "id": "test_id",
                "content": "test content",
                "metadata": {
                    "timestamp": datetime.now().timestamp(),
                    "importance": 0.8
                }
            }]
        }
    
    client.store_memory = AsyncMock(side_effect=mock_store)
    client.retrieve_context = AsyncMock(side_effect=mock_retrieve)
    return client

@pytest.fixture
def executive_agent(mock_venice_client):
    """Create executive agent with mock client."""
    return LibrarianAgent(mock_venice_client)

@pytest.fixture
def worker_agent(mock_venice_client):
    """Create worker agent with mock client."""
    return LibrarianAgent(mock_venice_client)

@pytest.mark.asyncio
async def test_memory_sharing_between_agents(executive_agent, worker_agent):
    """Test memory sharing between agents."""
    # Executive stores task information
    task_metadata = MemoryMetadata(
        timestamp=datetime.now().timestamp(),
        tags=["task"],
        context_ids=["shared_task_1"]
    )
    
    await executive_agent.store_memory(
        "Complete research on memory systems",
        task_metadata
    )
    
    # Worker accesses shared task
    worker_memories = await worker_agent.retrieve_memories(
        "research task",
        context_id="shared_task_1"
    )
    
    assert len(worker_memories) == 1
    assert "research" in worker_memories[0]["content"].lower()

@pytest.mark.asyncio
async def test_hierarchical_memory_access(executive_agent, worker_agent):
    """Test hierarchical memory access patterns."""
    # Worker stores progress information
    progress_metadata = MemoryMetadata(
        timestamp=datetime.now().timestamp(),
        tags=["progress"],
        context_ids=["task_progress"]
    )
    
    await worker_agent.store_memory(
        "Research progress: 50% complete",
        progress_metadata
    )
    
    # Executive retrieves progress updates
    executive_view = await executive_agent.retrieve_memories(
        "progress updates",
        context_id="task_progress"
    )
    
    assert len(executive_view) == 1
    assert "50% complete" in executive_view[0]["content"]
