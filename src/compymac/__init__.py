"""
CompyMac - A baseline proof-of-concept for an LLM-based agent.

This implementation honestly represents the fundamental constraints of how
LLM-based agents actually work:

1. Session-bounded state: All state is discarded when a session ends
2. Fixed context window: Limited token budget with naive truncation
3. Tool-mediated actions: The only way to affect the world is through tools
4. Turn-based processing: Process one turn, respond, wait for next input
5. No learning: No weight updates from interactions

This is not an idealized system - it's a faithful representation of the
constraints that must be understood before they can be improved.
"""

__version__ = "0.1.0"

from compymac.browser import (
    BrowserAction,
    BrowserConfig,
    BrowserEngine,
    BrowserMode,
    BrowserService,
    SyncBrowserService,
    create_browser_tools,
)
from compymac.context import ContextManager
from compymac.llm import LLMClient
from compymac.loop import AgentLoop
from compymac.session import Session
from compymac.tools import Tool, ToolRegistry, create_mock_tools

__all__ = [
    "Session",
    "ContextManager",
    "LLMClient",
    "ToolRegistry",
    "Tool",
    "AgentLoop",
    "create_mock_tools",
    "BrowserService",
    "SyncBrowserService",
    "BrowserConfig",
    "BrowserMode",
    "BrowserEngine",
    "BrowserAction",
    "create_browser_tools",
]
