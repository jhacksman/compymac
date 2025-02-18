import pytest
import websockets.sync.client as websockets
import json
from ..browser_automation_server import BrowserAutomationServer

@pytest.fixture
def server():
    """Create WebSocket server for testing."""
    server = BrowserAutomationServer(mock_mode=True)
    server.start()  # Synchronous start
    yield server
    server.stop()  # Synchronous stop

def test_websocket_command_roundtrip(server):
    """Test complete WebSocket message round-trip with command execution"""
    with websockets.connect('ws://localhost:8765') as websocket:
        # Send command request
        command_request = {
            "action": "runCommand",
            "command": "echo 'test message'"
        }
        websocket.send(json.dumps(command_request))
        
        # Receive response
        response = json.loads(websocket.recv())
        
        # Verify response structure
        assert response["action"] == "runCommand"
        assert response["status"] == "success"
        assert "test message" in response["output"]
        assert response["returnCode"] == 0

def test_websocket_error_handling(server):
    """Test WebSocket error handling with invalid command"""
    with websockets.connect('ws://localhost:8765') as websocket:
        # Send invalid command request
        command_request = {
            "action": "runCommand",
            "command": "invalid_command_xyz"
        }
        websocket.send(json.dumps(command_request))
        
        # Receive response
        response = json.loads(websocket.recv())
        
        # Verify error handling
        assert response["action"] == "runCommand"
        assert response["status"] == "error"
        assert response["error"] != ""
        assert response["returnCode"] != 0
