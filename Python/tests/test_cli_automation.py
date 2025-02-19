"""Tests for CLI automation."""
import pytest
from unittest.mock import Mock
from ..browser_automation_server import BrowserAutomationServer

pytestmark = pytest.mark.desktop

def test_browser_automation():
    """Test browser automation."""
    # Skip test in CI
    pytest.skip("Desktop automation tests are disabled in CI")
