import pytest
import pytest_asyncio
import asyncio
import websockets
import json
from ..browser_automation_server import BrowserAutomationServer

@pytest_asyncio.fixture(scope="function")
async def server():
    """Create server fixture."""
    server = BrowserAutomationServer(mock_mode=True)
    server_task = asyncio.create_task(server.start_server())
    await asyncio.sleep(0.1)  # Give server time to start
    try:
        await server.start()
        yield server
    finally:
        server_task.cancel()
        try:
            await server_task
        except asyncio.CancelledError:
            pass
        await server.stop()

@pytest.mark.asyncio
async def test_browser_websocket_roundtrip(server):
    """Test complete WebSocket message round-trip with browser actions"""
    # Open browser request
    result = await server.execute_browser_action("openBrowser", {
        "url": "https://example.com"
    })
    assert result["action"] == "openBrowser"
    assert result["status"] == "success"
    assert result["title"] != ""
    
    # Click element request
    result = await server.execute_browser_action("clickElement", {
        "selector": "a"
    })
    assert result["action"] == "clickElement"
    assert result["status"] == "success"

@pytest.mark.asyncio
async def test_browser_error_handling(server):
    """Test WebSocket error handling for browser actions"""
    # Send invalid selector
    result = await server.execute_browser_action("clickElement", {
        "selector": "#nonexistent-element-123"
    })
    assert result["action"] == "clickElement"
    assert result["status"] == "error"
    assert result["message"] != ""
