import pytest
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

def test_open_browser_success(server):
    """Test successful browser page opening"""
    result = server.execute_browser_action("openBrowser", {
        "url": "https://example.com",
        "mode": "webkit"
    })
    assert result["action"] == "openBrowser"
    assert result["status"] == "success"
    assert result["title"] != ""
    assert result["url"] == "https://example.com"

def test_open_browser_missing_url(server):
    """Test browser opening with missing URL"""
    result = server.execute_browser_action("openBrowser", {})
    assert result["action"] == "openBrowser"
    assert result["status"] == "error"
    assert result["message"] == "URL not specified"

def test_click_element(server):
    """Test clicking an element on a page"""
    # First open a page
    server.execute_browser_action("openBrowser", {
        "url": "https://example.com"
    })
    
    # Then try to click an element
    result = server.execute_browser_action("clickElement", {
        "selector": "a"  # Click first link
    })
    assert result["action"] == "clickElement"
    assert result["status"] == "success"

def test_fill_form(server):
    """Test filling a form on a page"""
    # First open a page
    server.execute_browser_action("openBrowser", {
        "url": "https://example.com"
    })
    
    # Then try to fill a form
    result = server.execute_browser_action("fillForm", {
        "fields": {
            "input[type=text]": "test input"
        }
    })
    assert result["action"] == "fillForm"
    assert result["status"] == "success"

def test_browser_navigation(server):
    """Test browser navigation (back/forward/refresh)"""
    # First open initial page
    server.execute_browser_action("openBrowser", {
        "url": "https://example.com"
    })
    
    # Navigate to another page
    server.execute_browser_action("openBrowser", {
        "url": "https://example.org"
    })
    
    # Test back navigation
    result = server.execute_browser_action("navigateBack", {})
    assert result["action"] == "navigateBack"
    assert result["status"] == "success"
    assert "example.com" in result["url"]
    
    # Test forward navigation
    result = server.execute_browser_action("navigateForward", {})
    assert result["action"] == "navigateForward"
    assert result["status"] == "success"
    assert "example.org" in result["url"]
    
    # Test refresh
    result = server.execute_browser_action("refresh", {})
    assert result["action"] == "refresh"
    assert result["status"] == "success"
