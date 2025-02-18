import pytest
import pytest_asyncio
import asyncio
import websockets
import json
import os
from .mock_websocket_server import MockWebSocketServer
from ..browser_automation_server import BrowserAutomationServer

@pytest_asyncio.fixture
async def server():
    """Create WebSocket server for testing."""
    server = BrowserAutomationServer(mock_mode=True)
    server_task = asyncio.create_task(server.start_server())
    await asyncio.sleep(0.1)  # Give server time to start
    await server.start()
    yield server
    server_task.cancel()
    try:
        await server_task
    except asyncio.CancelledError:
        pass
    await server.stop()

@pytest.fixture
def test_dir(tmp_path):
    """Create a temporary directory for testing."""
    return str(tmp_path)

@pytest.mark.asyncio
async def test_finder_websocket_roundtrip(test_dir, server):
    """Test complete WebSocket message round-trip with Finder actions."""
    async with websockets.connect('ws://localhost:8765') as websocket:
        # Create folder request
        folder_path = os.path.join(test_dir, "websocket_test")
        create_request = {
            "action": "desktop_create_folder",
            "path": folder_path
        }
        await websocket.send(json.dumps(create_request))
        
        # Verify create response
        response = json.loads(await websocket.recv())
        assert response["action"] == "desktop_create_folder"
        assert response["status"] == "success"
        assert os.path.exists(folder_path)

@pytest.mark.asyncio
async def test_finder_error_handling(server):
    """Test WebSocket error handling for Finder actions."""
    async with websockets.connect('ws://localhost:8765') as websocket:
        # Try to create folder in invalid location
        create_request = {
            "action": "desktop_create_folder",
            "path": "/invalid/path/that/doesnt/exist"
        }
        await websocket.send(json.dumps(create_request))
        
        # Verify error response
        response = json.loads(await websocket.recv())
        assert response["action"] == "desktop_create_folder"
        assert response["status"] == "error"
        assert response["message"] != ""
