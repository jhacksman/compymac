import pytest
import pytest_asyncio
import asyncio
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from browser_automation_server import BrowserAutomationServer

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
async def test_open_browser_success(server):
    """Test successful browser page opening"""
    result = await server.execute_browser_action("openBrowser", {
        "url": "https://example.com",
        "mode": "webkit"
    })
    assert result["action"] == "openBrowser"
    assert result["status"] == "success"
    assert result["title"] != ""
    assert result["url"] == "https://example.com"

@pytest.mark.asyncio
async def test_open_browser_missing_url(server):
    """Test browser opening with missing URL"""
    result = await server.execute_browser_action("openBrowser", {})
    assert result["action"] == "openBrowser"
    assert result["status"] == "error"
    assert result["message"] == "URL not specified"

@pytest.mark.asyncio
async def test_click_element(server):
    """Test clicking an element on a page"""
    # First open a page
    await server.execute_browser_action("openBrowser", {
        "url": "https://example.com"
    })
    
    # Then try to click an element
    result = await server.execute_browser_action("clickElement", {
        "selector": "a"  # Click first link
    })
    assert result["action"] == "clickElement"
    assert result["status"] == "success"

@pytest.mark.asyncio
async def test_fill_form(server):
    """Test filling a form on a page"""
    # First open a page
    await server.execute_browser_action("openBrowser", {
        "url": "https://example.com"
    })
    
    # Then try to fill a form
    result = await server.execute_browser_action("fillForm", {
        "fields": {
            "input[type=text]": "test input"
        }
    })
    assert result["action"] == "fillForm"
    assert result["status"] == "success"

@pytest.mark.asyncio
async def test_browser_navigation(server):
    """Test browser navigation (back/forward/refresh)"""
    # First open initial page
    await server.execute_browser_action("openBrowser", {
        "url": "https://example.com"
    })
    
    # Navigate to another page
    await server.execute_browser_action("openBrowser", {
        "url": "https://example.org"
    })
    
    # Test back navigation
    result = await server.execute_browser_action("navigateBack", {})
    assert result["action"] == "navigateBack"
    assert result["status"] == "success"
    assert "example.com" in result["url"]
    
    # Test forward navigation
    result = await server.execute_browser_action("navigateForward", {})
    assert result["action"] == "navigateForward"
    assert result["status"] == "success"
    assert "example.org" in result["url"]
    
    # Test refresh
    result = await server.execute_browser_action("refresh", {})
    assert result["action"] == "refresh"
    assert result["status"] == "success"
