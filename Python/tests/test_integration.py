import pytest
import pytest_asyncio
import asyncio
import websockets
import json
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

@pytest.mark.asyncio
async def test_websocket_command_roundtrip(server):
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
async def test_websocket_error_handling(server):
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
