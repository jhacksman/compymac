"""Tests for memory integration."""
import pytest
import json
from datetime import datetime
from memory.message_types import MemoryMetadata
from .mock_websocket_server import MockWebSocketServer

@pytest.fixture
async def websocket_server():
    """Create and start mock WebSocket server."""
    server = MockWebSocketServer()
    await server.start()
    yield server
    await server.stop()

@pytest.mark.asyncio
async def test_store_memory(websocket_server):
    """Test storing memory via WebSocket."""
    store_request = {
        "content": "test memory",
        "metadata": MemoryMetadata(
            timestamp=datetime.now().timestamp(),
            agent_id="test_agent",
            importance="high"
        ).to_dict(),
        "action": "store_memory"
    }
    
    async with websocket_server as ws:
        await ws.send(json.dumps(store_request))
        response = json.loads(await ws.recv())
        
        assert response["status"] == "success"
        assert "memory_id" in response

@pytest.mark.asyncio
async def test_error_handling(websocket_server):
    """Test error handling in WebSocket communication."""
    update_request = {
        "action": "update_memory",
        "memory_id": "nonexistent_id",
        "updates": {"content": "test"}
    }
    
    async with websocket_server as ws:
        await ws.send(json.dumps(update_request))
        response = json.loads(await ws.recv())
        
        assert response["status"] == "error"
        assert "message" in response
