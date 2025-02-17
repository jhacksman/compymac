import pytest
import asyncio
import websockets
import json
import pytest_asyncio
from browser_automation_server import BrowserAutomationServer

@pytest_asyncio.fixture
async def server():
    server = BrowserAutomationServer()
    await server.start_server()
    yield server
    await server._cleanup_browser()

@pytest.mark.asyncio
async def test_websocket_command_roundtrip():
    """Test complete WebSocket message round-trip with command execution"""
    async with websockets.connect('ws://localhost:8765') as websocket:
        # Send command request
        command_request = {
            "action": "runCommand",
            "command": "echo 'test message'"
        }
        await websocket.send(json.dumps(command_request))
        
        # Receive response
        response = json.loads(await websocket.recv())
        
        # Verify response structure
        assert response["action"] == "runCommand"
        assert response["status"] == "success"
        assert "test message" in response["output"]
        assert response["returnCode"] == 0

@pytest.mark.asyncio
async def test_websocket_error_handling():
    """Test WebSocket error handling with invalid command"""
    async with websockets.connect('ws://localhost:8765') as websocket:
        # Send invalid command request
        command_request = {
            "action": "runCommand",
            "command": "invalid_command_xyz"
        }
        await websocket.send(json.dumps(command_request))
        
        # Receive response
        response = json.loads(await websocket.recv())
        
        # Verify error handling
        assert response["action"] == "runCommand"
        assert response["status"] == "error"
        assert response["error"] != ""
        assert response["returnCode"] != 0
