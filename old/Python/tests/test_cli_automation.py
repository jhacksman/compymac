"""Tests for CLI automation."""
import pytest

pytestmark = [
    pytest.mark.desktop,
    pytest.mark.skip(reason="Desktop automation tests are disabled in CI")
]

def test_browser_automation():
    """Test browser automation."""
    pytest.skip("Desktop automation tests are disabled in CI")
