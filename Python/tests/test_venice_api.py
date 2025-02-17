"""Tests for Venice.ai API client."""

import pytest
import pytest_asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime, timezone
from typing import Any, Dict

from ..memory.venice_api import VeniceAPI
from ..memory.exceptions import VeniceAPIError

@pytest.fixture
def api_key():
    return "test_api_key"

@pytest.fixture
def venice_api(api_key):
    return VeniceAPI(api_key)

@pytest_asyncio.fixture
async def mock_session():
    mock_session = AsyncMock()
    mock_session.__aenter__.return_value = mock_session
    mock_session.__aexit__.return_value = None
    mock_session.post = AsyncMock()
    mock_session.get = AsyncMock()
    mock_session.patch = AsyncMock()
    mock_session.delete = AsyncMock()
    
    with patch("aiohttp.ClientSession", return_value=mock_session):
        yield mock_session

@pytest.mark.asyncio
async def test_store_memory_success(venice_api, mock_session):
    """Test successful memory storage."""
    mock_response = AsyncMock()
    mock_response.status = 201
    mock_response.json.return_value = {
        "id": "test_id",
        "content": "test memory",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    
    mock_session.post.return_value = mock_response
    
    result = await venice_api.store_memory(
        "test memory",
        {"importance": "high"}
    )
    
    assert result["id"] == "test_id"
    assert result["content"] == "test memory"

@pytest.mark.asyncio
async def test_store_memory_error(venice_api, mock_session):
    """Test memory storage error handling."""
    mock_response = AsyncMock()
    mock_response.status = 400
    mock_response.text = AsyncMock()
    mock_response.text.return_value = "Invalid request"
    mock_response.json = AsyncMock()
    mock_response.json.side_effect = Exception("Should not be called")
    
    mock_session.post.return_value = mock_response
    
    with pytest.raises(VeniceAPIError):
        await venice_api.store_memory(
            "test memory",
            {"importance": "high"}
        )

@pytest.mark.asyncio
async def test_retrieve_context_success(venice_api, mock_session):
    """Test successful context retrieval."""
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json.return_value = [{
        "id": "test_id",
        "content": "test memory",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }]
    
    mock_session.get.return_value = mock_response
    
    result = await venice_api.retrieve_context(
        "test query",
        {"time_range": "1d"}
    )
    
    assert len(result) == 1
    assert result[0]["id"] == "test_id"

@pytest.mark.asyncio
async def test_retrieve_context_error(venice_api, mock_session):
    """Test context retrieval error handling."""
    mock_response = AsyncMock()
    mock_response.status = 500
    mock_response.text = AsyncMock()
    mock_response.text.return_value = "Server error"
    mock_response.json = AsyncMock()
    mock_response.json.side_effect = Exception("Should not be called")
    
    mock_session.get.return_value = mock_response
    
    with pytest.raises(VeniceAPIError):
        await venice_api.retrieve_context("test query")

@pytest.mark.asyncio
async def test_update_memory_success(venice_api, mock_session):
    """Test successful memory update."""
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json.return_value = {
        "id": "test_id",
        "content": "updated memory",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    
    mock_session.patch = AsyncMock(return_value=mock_response)
    
    result = await venice_api.update_memory(
        "test_id",
        {"content": "updated memory"}
    )
    
    assert result["content"] == "updated memory"

@pytest.mark.asyncio
async def test_delete_memory_success(venice_api, mock_session):
    """Test successful memory deletion."""
    mock_response = AsyncMock()
    mock_response.status = 204
    
    mock_session.delete = AsyncMock(return_value=mock_response)
    
    await venice_api.delete_memory("test_id")  # Should not raise
