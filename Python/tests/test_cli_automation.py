import pytest
import pytest_asyncio
import asyncio
import json
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from ..browser_automation_server import BrowserAutomationServer
from desktop_automation import DesktopAutomation

@pytest_asyncio.fixture(scope="function")
async def automation():
    """Create automation fixture."""
    automation = DesktopAutomation()
    try:
        await automation.start()
        yield automation
    finally:
        try:
            await automation.stop()
        except Exception:
            pass

@pytest.mark.asyncio
async def test_execute_command_success(automation):
    """Test successful command execution with 'whoami'"""
    result = await automation.execute_browser_action("runCommand", {"command": "whoami"})
    assert result["action"] == "runCommand"
    assert result["status"] == "success"
    assert result["output"] != ""
    assert result["returnCode"] == 0

@pytest.mark.asyncio
async def test_execute_command_error(automation):
    """Test command execution with invalid command"""
    result = await automation.execute_browser_action("runCommand", {"command": "invalid_command_123"})
    assert result["action"] == "runCommand"
    assert result["status"] == "error"
    assert result["error"] != ""
    assert result["returnCode"] != 0

@pytest.mark.asyncio
async def test_execute_command_missing_command(automation):
    """Test command execution with missing command parameter"""
    result = await automation.execute_browser_action("runCommand", {})
    assert result["action"] == "runCommand"
    assert result["status"] == "error"
    assert result["message"] == "Command not specified"

@pytest.mark.asyncio
async def test_execute_command_empty_command(automation):
    """Test command execution with empty command"""
    result = await automation.execute_browser_action("runCommand", {"command": ""})
    assert result["action"] == "runCommand"
    assert result["status"] == "error"
    assert result["message"] == "Command not specified"
