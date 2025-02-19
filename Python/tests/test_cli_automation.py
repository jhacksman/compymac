"""Tests for CLI automation."""
import pytest

# Skip all tests in this module if desktop_automation is not available
pytest.importorskip("desktop_automation")

from ..browser_automation_server import BrowserAutomationServer

pytestmark = pytest.mark.desktop

def test_browser_automation():
    """Test browser automation."""
    server = BrowserAutomationServer()
    assert server is not None
