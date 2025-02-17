import pytest
import asyncio
import json
from browser_automation_server import BrowserAutomationServer

@pytest.fixture
async def server():
    return BrowserAutomationServer()

@pytest.mark.asyncio
async def test_execute_command_success(server):
    """Test successful command execution with 'whoami'"""
    result = await server.execute_browser_action("runCommand", {"command": "whoami"})
    assert result["action"] == "runCommand"
    assert result["status"] == "success"
    assert result["output"] != ""
    assert result["returnCode"] == 0

@pytest.mark.asyncio
async def test_execute_command_error(server):
    """Test command execution with invalid command"""
    result = await server.execute_browser_action("runCommand", {"command": "invalid_command_123"})
    assert result["action"] == "runCommand"
    assert result["status"] == "error"
    assert result["error"] != ""
    assert result["returnCode"] != 0

@pytest.mark.asyncio
async def test_execute_command_missing_command(server):
    """Test command execution with missing command parameter"""
    result = await server.execute_browser_action("runCommand", {})
    assert result["action"] == "runCommand"
    assert result["status"] == "error"
    assert result["message"] == "Command not specified"

@pytest.mark.asyncio
async def test_execute_command_empty_command(server):
    """Test command execution with empty command"""
    result = await server.execute_browser_action("runCommand", {"command": ""})
    assert result["action"] == "runCommand"
    assert result["status"] == "error"
    assert result["message"] == "Command not specified"
