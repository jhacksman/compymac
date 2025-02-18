"""Test fixtures for memory system tests."""

import pytest
import pytest_asyncio
import os
from datetime import datetime

from memory.message_types import MemoryMetadata
from memory.venice_client import VeniceClient
from memory.librarian import LibrarianAgent

# Set test environment variables if not already set
if not os.getenv("VENICE_API_KEY"):
    os.environ["VENICE_API_KEY"] = "B9Y68yQgatQw8wmpmnIMYcGip1phCt-43CS0OktZU6"
if not os.getenv("VENICE_BASE_URL"):
    os.environ["VENICE_BASE_URL"] = "https://api.venice.ai"  # Base URL without /api/v1
if not os.getenv("VENICE_MODEL"):
    os.environ["VENICE_MODEL"] = "llama-3.3-70b"  # Using the specified model from docs

# Get environment variables
VENICE_API_KEY = os.getenv("VENICE_API_KEY")
VENICE_BASE_URL = os.getenv("VENICE_BASE_URL")
VENICE_MODEL = os.getenv("VENICE_MODEL")


@pytest_asyncio.fixture(scope="function")
async def venice_client():
    """Create Venice client for memory operations."""
    client = VeniceClient(api_key=VENICE_API_KEY)
    client.base_url = VENICE_BASE_URL
    client.model = VENICE_MODEL
    
    try:
        yield client
    finally:
        # Cleanup any open sessions
        if hasattr(client, '_session'):
            await client._session.close()


@pytest_asyncio.fixture(scope="function")
async def librarian(venice_client):
    """Create librarian with Venice client."""
    agent = LibrarianAgent(venice_client)
    try:
        yield agent
    finally:
        # Clear any shared memories
        agent.recent_memories.clear()
        LibrarianAgent._shared_memories.clear()
        
        
# Remove all mock-related code to use real Venice.ai API
