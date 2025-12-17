import pytest
import json
from ..desktop.browser_automation_server import BrowserAutomationServer

@pytest.fixture(scope="function")
def server(monkeypatch):
    """Create server fixture."""
    monkeypatch.setenv('DATABASE_URL', 'postgresql://postgres:postgres@localhost:5432/test_db')
    monkeypatch.setenv('TESTING', 'true')
    server = BrowserAutomationServer(mock_mode=True)
    server.start()  # Synchronous start
    try:
        yield server
    finally:
        server.stop()  # Synchronous stop

def test_browser_websocket_roundtrip(server):
    """Test complete WebSocket message round-trip with browser actions"""
    # Open browser request
    result = server.execute_browser_action("openBrowser", {
        "url": "https://example.com"
    })
    assert result["action"] == "openBrowser"
    assert result["status"] == "success"
    assert result["title"] != ""
    
    # Click element request
    result = server.execute_browser_action("clickElement", {
        "selector": "a"
    })
    assert result["action"] == "clickElement"
    assert result["status"] == "success"

def test_browser_error_handling(server):
    """Test WebSocket error handling for browser actions"""
    # Send invalid selector
    result = server.execute_browser_action("clickElement", {
        "selector": "#nonexistent-element-123"
    })
    assert result["action"] == "clickElement"
    assert result["status"] == "error"
    assert result["message"] != ""
