"""Integration tests for memory system."""
import pytest
import asyncio
import websockets
import json
from datetime import datetime

from memory.message_types import MemoryMetadata
from .mock_websocket_server import MockWebSocketServer

@pytest.fixture(scope="function")
async def server():
    """Create and start WebSocket server."""
    server = MockWebSocketServer()
    await server.start()
    yield server
    await server.stop()

@pytest.mark.asyncio
async def test_websocket_command_roundtrip(server):
    """Test complete WebSocket message round-trip with command execution"""
    async with websockets.connect(f'ws://localhost:{server.actual_port}') as websocket:
        request = {
            "action": "store_memory",
            "content": "Test memory content",
            "metadata": {
                "timestamp": datetime.now().timestamp(),
                "importance": 0.8,
                "tags": ["test"]
            }
        }
        
        await websocket.send(json.dumps(request))
        response = json.loads(await websocket.recv())
        
        assert response["status"] == "success"
        assert "memory_id" in response

@pytest.mark.asyncio
async def test_websocket_error_handling(server):
    """Test WebSocket error handling with invalid command"""
    async with websockets.connect(f'ws://localhost:{server.actual_port}') as websocket:
        request = {
            "action": "invalid_action",
            "data": "test"
        }
        
        await websocket.send(json.dumps(request))
        response = json.loads(await websocket.recv())
        
        assert response["status"] == "error"
        assert "message" in response
