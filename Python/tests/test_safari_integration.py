import pytest
import asyncio
import websockets
import json
from browser_automation_server import BrowserAutomationServer

import pytest_asyncio

@pytest_asyncio.fixture
async def server():
    server = BrowserAutomationServer()
    await server.start_server()
    yield server
    await server._cleanup_browser()

@pytest.mark.asyncio
async def test_browser_websocket_roundtrip(server):
    """Test complete WebSocket message round-trip with browser actions"""
    async with websockets.connect('ws://localhost:8765', open_timeout=10) as websocket:
        # Open browser request
        open_request = {
            "action": "openBrowser",
            "url": "https://example.com"
        }
        await websocket.send(json.dumps(open_request))
        
        # Verify open response
        response = json.loads(await websocket.recv())
        assert response["action"] == "openBrowser"
        assert response["status"] == "success"
        assert response["title"] != ""
        
        # Click element request
        click_request = {
            "action": "clickElement",
            "selector": "a"
        }
        await websocket.send(json.dumps(click_request))
        
        # Verify click response
        response = json.loads(await websocket.recv())
        assert response["action"] == "clickElement"
        assert response["status"] == "success"

@pytest.mark.asyncio
async def test_browser_error_handling():
    """Test WebSocket error handling for browser actions"""
    async with websockets.connect('ws://localhost:8765') as websocket:
        # Send invalid selector
        click_request = {
            "action": "clickElement",
            "selector": "#nonexistent-element-123"
        }
        await websocket.send(json.dumps(click_request))
        
        # Verify error response
        response = json.loads(await websocket.recv())
        assert response["action"] == "clickElement"
        assert response["status"] == "error"
        assert response["message"] != ""
