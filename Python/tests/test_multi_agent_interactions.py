"""Tests for multi-agent memory interactions."""

import pytest
import pytest_asyncio
from datetime import datetime
from unittest.mock import Mock, AsyncMock

from memory.message_types import MemoryMetadata, MemoryResponse
from memory.venice_client import VeniceClient
from memory.librarian import LibrarianAgent
from memory.exceptions import MemoryError


@pytest_asyncio.fixture(scope="function")
async def mock_venice_client():
    """Create mock Venice client."""
    client = Mock(spec=VeniceClient)
    client.store_memory = AsyncMock(return_value=MemoryResponse(
        action="store_memory",
        success=True,
        memory_id="test_id"
    ))
    client.retrieve_context = AsyncMock(return_value=MemoryResponse(
        action="retrieve_context",
        success=True,
        memories=[]
    ))
    return client


@pytest_asyncio.fixture(scope="function")
async def executive_agent(mock_venice_client):
    """Create executive agent fixture."""
    agent = LibrarianAgent(mock_venice_client)
    agent.agent_id = "executive"
    return agent


@pytest_asyncio.fixture(scope="function")
async def worker_agent(mock_venice_client):
    """Create worker agent fixture."""
    agent = LibrarianAgent(mock_venice_client)
    agent.agent_id = "worker"
    return agent


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
    assert "research on memory systems" in worker_memories[0]["content"]


@pytest.mark.asyncio
async def test_hierarchical_memory_access(executive_agent, worker_agent, mock_venice_client):
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
    mock_venice_client.retrieve_context.return_value = MemoryResponse(
        action="retrieve_context",
        success=True,
        memories=[{
            "id": "progress_1",
            "content": "Research progress: 50% complete",
            "metadata": {
                "timestamp": datetime.now().timestamp(),
                "importance": 0.7,
                "context_ids": ["task_progress"]
            }
        }]
    )
    
    executive_view = await executive_agent.retrieve_memories(
        "progress updates",
        context_id="task_progress"
    )
    
    assert len(executive_view) == 1
    assert "50% complete" in executive_view[0]["content"]


@pytest.mark.asyncio
async def test_context_synchronization(executive_agent, worker_agent):
    """Test context synchronization between agents."""
    shared_context = "project_alpha"
    
    # Executive sets project context
    exec_metadata = MemoryMetadata(
        timestamp=datetime.now().timestamp(),
        tags=["project"],
        context_ids=[shared_context]
    )
    
    await executive_agent.store_memory(
        "Project Alpha objectives defined",
        exec_metadata
    )
    
    # Worker adds to same context
    worker_metadata = MemoryMetadata(
        timestamp=datetime.now().timestamp(),
        tags=["project"],
        context_ids=[shared_context]
    )
    
    await worker_agent.store_memory(
        "Project Alpha implementation started",
        worker_metadata
    )
    
    # Both agents should see synchronized context
    exec_view = await executive_agent.retrieve_memories(
        "Project Alpha",
        context_id=shared_context
    )
    worker_view = await worker_agent.retrieve_memories(
        "Project Alpha",
        context_id=shared_context
    )
    
    assert len(exec_view) == len(worker_view)


@pytest.mark.asyncio
async def test_memory_access_control(executive_agent, worker_agent, mock_venice_client):
    """Test memory access control between agents."""
    # Executive stores private memory
    private_metadata = MemoryMetadata(
        timestamp=datetime.now().timestamp(),
        tags=["private"],
        context_ids=["executive_only"]
    )
    
    await executive_agent.store_memory(
        "Confidential executive decision",
        private_metadata
    )
    
    # Worker should not see private executive memories
    mock_venice_client.retrieve_context.return_value = MemoryResponse(
        action="retrieve_context",
        success=True,
        memories=[]  # Empty for worker
    )
    
    worker_view = await worker_agent.retrieve_memories(
        "executive decisions",
        context_id="executive_only"
    )
    
    assert len(worker_view) == 0


@pytest.mark.asyncio
async def test_collaborative_memory_building(executive_agent, worker_agent):
    """Test collaborative building of shared memory."""
    project_id = "collaborative_project"
    
    # Multiple agents contribute to shared context
    contributions = [
        (executive_agent, "Project kickoff meeting completed"),
        (worker_agent, "Initial research completed"),
        (executive_agent, "Milestone 1 approved"),
        (worker_agent, "Implementation phase started")
    ]
    
    for agent, content in contributions:
        await agent.store_memory(
            content,
            MemoryMetadata(
                timestamp=datetime.now().timestamp(),
                tags=["project"],
                context_ids=[project_id]
            )
        )
    
    # Both agents should see complete timeline
    exec_view = await executive_agent.retrieve_memories(
        "project timeline",
        context_id=project_id
    )
    
    assert len(exec_view) == len(contributions)
    assert all(
        any(contrib[1] in mem["content"] for mem in exec_view)
        for contrib in contributions
    )
