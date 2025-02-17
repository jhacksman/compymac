import pytest
import asyncio
import websockets
import json
import os
from browser_automation_server import BrowserAutomationServer

import pytest_asyncio

@pytest_asyncio.fixture
async def server():
    server = BrowserAutomationServer()
    await server.start_server()
    yield server
    await server._cleanup_browser()

@pytest.fixture
def test_dir(tmp_path):
    """Create a temporary directory for testing."""
    return str(tmp_path)

@pytest.mark.asyncio
async def test_finder_websocket_roundtrip(server, test_dir):
    """Test complete WebSocket message round-trip with Finder actions."""
    async with websockets.connect('ws://localhost:8765', open_timeout=10) as websocket:
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
async def test_finder_error_handling():
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
