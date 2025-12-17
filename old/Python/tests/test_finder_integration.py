import pytest
import websockets.sync.client as websockets
import json
import os
from .mock_websocket_server import MockWebSocketServer
from ..desktop.browser_automation_server import BrowserAutomationServer

@pytest.fixture
def server(monkeypatch):
    """Create WebSocket server for testing."""
    monkeypatch.setenv('DATABASE_URL', 'postgresql://postgres:postgres@localhost:5432/test_db')
    monkeypatch.setenv('TESTING', 'true')
    server = BrowserAutomationServer(mock_mode=True)
    server.start()  # Synchronous start
    yield server
    server.stop()  # Synchronous stop

@pytest.fixture
def test_dir(tmp_path):
    """Create a temporary directory for testing."""
    return str(tmp_path)

def test_finder_websocket_roundtrip(test_dir, server):
    """Test complete WebSocket message round-trip with Finder actions."""
    if server.mock_mode:
        pytest.skip("Skipping WebSocket test in mock mode")
    with websockets.connect('ws://localhost:8765') as websocket:
        # Create folder request
        folder_path = os.path.join(test_dir, "websocket_test")
        create_request = {
            "action": "desktop_create_folder",
            "path": folder_path
        }
        websocket.send(json.dumps(create_request))
        
        # Verify create response
        response = json.loads(websocket.recv())
        assert response["action"] == "desktop_create_folder"
        assert response["status"] == "success"
        assert os.path.exists(folder_path)

def test_finder_error_handling(server):
    """Test WebSocket error handling for Finder actions."""
    if server.mock_mode:
        pytest.skip("Skipping WebSocket test in mock mode")
    with websockets.connect('ws://localhost:8765') as websocket:
        # Try to create folder in invalid location
        create_request = {
            "action": "desktop_create_folder",
            "path": "/invalid/path/that/doesnt/exist"
        }
        websocket.send(json.dumps(create_request))
        
        # Verify error response
        response = json.loads(websocket.recv())
        assert response["action"] == "desktop_create_folder"
        assert response["status"] == "error"
        assert response["message"] != ""
