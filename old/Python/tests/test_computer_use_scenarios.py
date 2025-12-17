"""Tests for computer use scenario memory integration."""

import pytest
from datetime import datetime
from unittest.mock import Mock

from memory.message_types import MemoryMetadata, MemoryResponse
from memory.venice_client import VeniceClient
from memory.librarian import LibrarianAgent
from memory.exceptions import MemoryError


@pytest.fixture(scope="function")
def mock_venice_client():
    """Create mock Venice client."""
    client = Mock(spec=VeniceClient)
    
    stored_memories = []

    async def mock_store_memory(*args, **kwargs):
        memory_id = f"test_id_{len(stored_memories)}"
        memory = {
            "id": memory_id,
            "content": args[0],
            "metadata": args[1].__dict__ if hasattr(args[1], '__dict__') else args[1]
        }
        stored_memories.append(memory)
        return MemoryResponse(
            action="store_memory",
            success=True,
            memory_id=memory_id
        )

    async def mock_retrieve_context(*args, **kwargs):
        context_id = kwargs.get("context_id")
        memories = [m for m in stored_memories if context_id in m["metadata"]["context_ids"]]
        return MemoryResponse(
            action="retrieve_context",
            success=True,
            memories=memories
        )
    
    client.store_memory = mock_store_memory
    client.retrieve_context = mock_retrieve_context
    return client


@pytest.fixture(scope="function")
def librarian(mock_venice_client):
    """Create librarian fixture."""
    return LibrarianAgent(mock_venice_client)


@pytest.mark.asyncio
async def test_browser_automation_memory_integration(librarian):
    """Test browser automation memory integration."""
    # Simulate browser navigation sequence
    browser_metadata = MemoryMetadata(
        timestamp=datetime.now().timestamp(),
        tags=["browser", "navigation"],
        context_ids=["browser_session"]
    )
    
    browser_actions = [
        "Opened browser to research.page",
        "Clicked search button",
        "Entered query 'memory systems'",
        "Navigated to results page"
    ]
    
    # Store browser actions
    for action in browser_actions:
        await librarian.store_memory(
            action,
            browser_metadata
        )
    
    # Verify browser session retrieval
    memories = await librarian.retrieve_memories(
        "browser navigation",
        context_id="browser_session"
    )
    
    assert len(memories) == len(browser_actions)
    assert all("browser" in m["metadata"].tags for m in memories)


@pytest.mark.asyncio
async def test_finder_operation_memory_tracking(librarian):
    """Test Finder operation memory tracking."""
    # Simulate Finder operations
    finder_metadata = MemoryMetadata(
        timestamp=datetime.now().timestamp(),
        tags=["finder", "file_operations"],
        context_ids=["finder_session"]
    )
    
    finder_operations = [
        "Created new folder 'Project Documents'",
        "Moved files to Project Documents",
        "Renamed file 'report.txt' to 'final_report.txt'",
        "Deleted temporary files"
    ]
    
    # Store Finder operations
    for operation in finder_operations:
        await librarian.store_memory(
            operation,
            finder_metadata
        )
    
    # Verify Finder operation retrieval
    memories = await librarian.retrieve_memories(
        "file operations",
        context_id="finder_session"
    )
    
    assert len(memories) == len(finder_operations)
    assert all("finder" in m["metadata"].tags for m in memories)


@pytest.mark.asyncio
async def test_terminal_command_memory_logging(librarian):
    """Test terminal command memory logging."""
    # Simulate terminal command sequence
    terminal_metadata = MemoryMetadata(
        timestamp=datetime.now().timestamp(),
        tags=["terminal", "commands"],
        context_ids=["terminal_session"]
    )
    
    terminal_commands = [
        "git clone repository",
        "cd project_directory",
        "npm install dependencies",
        "npm run build"
    ]
    
    # Store terminal commands
    for command in terminal_commands:
        await librarian.store_memory(
            command,
            terminal_metadata
        )
    
    # Verify terminal command retrieval
    memories = await librarian.retrieve_memories(
        "terminal commands",
        context_id="terminal_session"
    )
    
    assert len(memories) == len(terminal_commands)
    assert all("terminal" in m["metadata"].tags for m in memories)


@pytest.mark.asyncio
async def test_cross_application_context(librarian):
    """Test context preservation across different applications."""
    project_id = "project_xyz"
    
    # Simulate multi-application workflow
    actions = [
        ("browser", "Researched project requirements"),
        ("finder", "Created project directory"),
        ("terminal", "Initialized git repository"),
        ("browser", "Downloaded dependencies"),
        ("finder", "Organized project files"),
        ("terminal", "Installed dependencies")
    ]
    
    # Store cross-application actions
    for app_type, action in actions:
        await librarian.store_memory(
            action,
            MemoryMetadata(
                timestamp=datetime.now().timestamp(),
                tags=[app_type],
                context_ids=[project_id]
            )
        )
    
    # Verify cross-application context
    memories = await librarian.retrieve_memories(
        "project setup",
        context_id=project_id
    )
    
    assert len(memories) == len(actions)
    unique_apps = {m["metadata"].tags[0] for m in memories}
    assert len(unique_apps) == 3  # browser, finder, terminal


@pytest.mark.asyncio
async def test_application_state_tracking(librarian):
    """Test application state memory tracking."""
    # Simulate application state changes
    state_metadata = MemoryMetadata(
        timestamp=datetime.now().timestamp(),
        tags=["state_change"],
        context_ids=["app_state"]
    )
    
    state_changes = [
        "Browser window maximized",
        "Finder sidebar collapsed",
        "Terminal font size increased",
        "Browser dark mode enabled"
    ]
    
    # Store state changes
    for change in state_changes:
        await librarian.store_memory(
            change,
            state_metadata
        )
    
    # Verify state tracking
    memories = await librarian.retrieve_memories(
        "application states",
        context_id="app_state"
    )
    
    assert len(memories) == len(state_changes)
    assert all("state_change" in m["metadata"].tags for m in memories)
