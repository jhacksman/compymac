"""Tests for deep research session workflows."""

import pytest
import pytest_asyncio
from datetime import datetime, timedelta
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
async def librarian(mock_venice_client):
    """Create librarian fixture."""
    return LibrarianAgent(mock_venice_client)


@pytest.mark.asyncio
async def test_multi_turn_conversation_tracking(librarian, mock_venice_client):
    """Test tracking of multi-turn conversations."""
    # Simulate a conversation about Python programming
    conversation_metadata = MemoryMetadata(
        timestamp=datetime.now().timestamp(),
        tags=["python", "programming"],
        context_ids=["conversation_1"]
    )
    
    # First turn: Question about Python
    await librarian.store_memory(
        "What is Python used for?",
        conversation_metadata
    )
    
    # Mock response about Python's general use
    mock_venice_client.retrieve_context.return_value = MemoryResponse(
        action="retrieve_context",
        success=True,
        memories=[{
            "id": "response_1",
            "content": "Python is a versatile programming language",
            "metadata": {
                "timestamp": datetime.now().timestamp(),
                "importance": 0.8,
                "context_ids": ["conversation_1"]
            }
        }]
    )
    
    # Second turn: Follow-up about web development
    await librarian.store_memory(
        "How is Python used in web development?",
        conversation_metadata
    )
    
    # Verify context preservation
    memories = await librarian.retrieve_memories(
        "Python web development",
        context_id="conversation_1"
    )
    
    assert len(memories) == 1
    assert "Python" in memories[0]["content"]
    assert "conversation_1" in memories[0]["metadata"]["context_ids"]


@pytest.mark.asyncio
async def test_context_preservation_across_sessions(librarian):
    """Test preservation of context across multiple sessions."""
    # Session 1: Initial research
    session_1_metadata = MemoryMetadata(
        timestamp=datetime.now().timestamp(),
        tags=["research", "session_1"],
        context_ids=["project_x"]
    )
    
    await librarian.store_memory(
        "Initial research findings about Project X",
        session_1_metadata
    )
    
    # Simulate time passing between sessions
    session_2_time = datetime.now() + timedelta(hours=2)
    session_2_metadata = MemoryMetadata(
        timestamp=session_2_time.timestamp(),
        tags=["research", "session_2"],
        context_ids=["project_x"]
    )
    
    # Session 2: Follow-up research
    await librarian.store_memory(
        "Follow-up research on Project X",
        session_2_metadata
    )
    
    # Verify context maintained across sessions
    memories = await librarian.retrieve_memories(
        "Project X research",
        context_id="project_x"
    )
    
    assert len(memories) == 2
    assert all("project_x" in m["metadata"]["context_ids"] for m in memories)


@pytest.mark.asyncio
async def test_memory_consolidation_during_session(librarian):
    """Test memory consolidation during long research sessions."""
    session_metadata = MemoryMetadata(
        timestamp=datetime.now().timestamp(),
        tags=["research"],
        context_ids=["long_session"]
    )
    
    # Store multiple related memories
    research_topics = [
        "Introduction to quantum computing",
        "Quantum bits and superposition",
        "Quantum gates and circuits",
        "Quantum algorithms overview"
    ]
    
    for topic in research_topics:
        await librarian.store_memory(
            topic,
            session_metadata
        )
    
    # Verify consolidated retrieval
    memories = await librarian.retrieve_memories(
        "quantum computing research",
        context_id="long_session"
    )
    
    assert len(memories) > 0
    assert all("long_session" in m["metadata"]["context_ids"] for m in memories)


@pytest.mark.asyncio
async def test_importance_based_memory_retention(librarian):
    """Test retention of important memories during long sessions."""
    session_metadata = MemoryMetadata(
        timestamp=datetime.now().timestamp(),
        tags=["research"],
        context_ids=["retention_test"]
    )
    
    # Store important memory
    await librarian.store_memory(
        "Critical breakthrough in research",
        MemoryMetadata(
            timestamp=datetime.now().timestamp(),
            importance=0.9,
            tags=["research"],
            context_ids=["retention_test"]
        )
    )
    
    # Fill context with less important memories
    for i in range(librarian.max_context_tokens // 4):
        await librarian.store_memory(
            f"Regular research note {i}",
            session_metadata
        )
    
    # Verify important memory retained
    memories = await librarian.retrieve_memories(
        "critical research",
        context_id="retention_test",
        min_importance=0.8
    )
    
    assert len(memories) == 1
    assert "Critical breakthrough" in memories[0]["content"]


@pytest.mark.asyncio
async def test_chain_of_thought_preservation(librarian):
    """Test preservation of reasoning chain in research."""
    chain_metadata = MemoryMetadata(
        timestamp=datetime.now().timestamp(),
        tags=["research", "chain_of_thought"],
        context_ids=["reasoning_chain"]
    )
    
    # Store chain of reasoning steps
    reasoning_steps = [
        "Initial hypothesis: AI systems can improve memory management",
        "Evidence: Studies show 30% improvement in recall",
        "Analysis: Improvement correlates with context preservation",
        "Conclusion: AI-enhanced memory systems are effective"
    ]
    
    for step in reasoning_steps:
        await librarian.store_memory(
            step,
            chain_metadata
        )
    
    # Verify complete chain retrieval
    memories = await librarian.retrieve_memories(
        "AI memory management research",
        context_id="reasoning_chain"
    )
    
    assert len(memories) == len(reasoning_steps)
    retrieved_steps = [m["content"] for m in memories]
    assert "Initial hypothesis" in retrieved_steps[0]
    assert "Conclusion" in retrieved_steps[-1]
