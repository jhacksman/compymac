"""Tests for browser automation module."""

from unittest.mock import AsyncMock, patch

import pytest

from compymac.browser import (
    BrowserAction,
    BrowserConfig,
    BrowserEngine,
    BrowserMode,
    BrowserService,
    ElementInfo,
    PageState,
    SyncBrowserService,
    create_browser_tools,
)


class TestBrowserConfig:
    """Tests for BrowserConfig."""

    def test_default_config(self):
        config = BrowserConfig()
        assert config.mode == BrowserMode.HEADLESS
        assert config.engine == BrowserEngine.CHROMIUM
        assert config.viewport_width == 1280
        assert config.viewport_height == 720
        assert config.timeout_ms == 30000

    def test_custom_config(self):
        config = BrowserConfig(
            mode=BrowserMode.HEADFUL,
            engine=BrowserEngine.FIREFOX,
            viewport_width=1920,
            viewport_height=1080,
        )
        assert config.mode == BrowserMode.HEADFUL
        assert config.engine == BrowserEngine.FIREFOX
        assert config.viewport_width == 1920


class TestElementInfo:
    """Tests for ElementInfo."""

    def test_to_dict(self):
        elem = ElementInfo(
            element_id="cid-0",
            tag="button",
            text="Click me",
            attributes={"class": "btn", "data-compyid": "cid-0"},
            is_interactive=True,
            is_visible=True,
            bounding_box={"x": 10, "y": 20, "width": 100, "height": 50},
        )
        d = elem.to_dict()
        assert d["element_id"] == "cid-0"
        assert d["tag"] == "button"
        assert d["text"] == "Click me"
        assert d["is_interactive"] is True
        assert d["is_visible"] is True

    def test_text_truncation(self):
        long_text = "x" * 200
        elem = ElementInfo(
            element_id="cid-1",
            tag="p",
            text=long_text,
            attributes={},
            is_interactive=False,
            is_visible=True,
        )
        d = elem.to_dict()
        assert len(d["text"]) == 100  # Truncated to 100 chars


class TestPageState:
    """Tests for PageState."""

    def test_to_dict(self):
        elements = [
            ElementInfo(
                element_id="cid-0",
                tag="button",
                text="Submit",
                attributes={},
                is_interactive=True,
                is_visible=True,
            ),
            ElementInfo(
                element_id="cid-1",
                tag="input",
                text="",
                attributes={"type": "text"},
                is_interactive=True,
                is_visible=True,
            ),
        ]
        state = PageState(
            url="https://example.com",
            title="Example",
            elements=elements,
        )
        d = state.to_dict()
        assert d["url"] == "https://example.com"
        assert d["title"] == "Example"
        assert d["element_count"] == 2
        assert len(d["interactive_elements"]) == 2

    def test_get_element_by_id(self):
        elements = [
            ElementInfo(
                element_id="cid-0",
                tag="button",
                text="Submit",
                attributes={},
                is_interactive=True,
                is_visible=True,
            ),
        ]
        state = PageState(url="", title="", elements=elements)

        found = state.get_element_by_id("cid-0")
        assert found is not None
        assert found.tag == "button"

        not_found = state.get_element_by_id("cid-999")
        assert not_found is None


class TestBrowserAction:
    """Tests for BrowserAction."""

    def test_success_action(self):
        action = BrowserAction(
            success=True,
            action_type="navigate",
            details={"url": "https://example.com"},
        )
        d = action.to_dict()
        assert d["success"] is True
        assert d["action_type"] == "navigate"
        assert "error" not in d

    def test_failed_action(self):
        action = BrowserAction(
            success=False,
            action_type="click",
            error="Element not found",
        )
        d = action.to_dict()
        assert d["success"] is False
        assert d["error"] == "Element not found"


class TestBrowserService:
    """Tests for BrowserService."""

    def test_init_default_config(self):
        service = BrowserService()
        assert service.config.mode == BrowserMode.HEADLESS
        assert service._is_initialized is False

    def test_init_custom_config(self):
        config = BrowserConfig(mode=BrowserMode.HEADFUL)
        service = BrowserService(config)
        assert service.config.mode == BrowserMode.HEADFUL

    @pytest.mark.asyncio
    async def test_ensure_initialized_calls_initialize(self):
        service = BrowserService()

        # Mock the initialize method
        service.initialize = AsyncMock()
        service._is_initialized = False

        await service._ensure_initialized()
        service.initialize.assert_called_once()

    @pytest.mark.asyncio
    async def test_ensure_initialized_skips_if_already_initialized(self):
        service = BrowserService()
        service.initialize = AsyncMock()
        service._is_initialized = True

        await service._ensure_initialized()
        service.initialize.assert_not_called()


class TestCreateBrowserTools:
    """Tests for create_browser_tools function."""

    def test_returns_tool_definitions(self):
        service = BrowserService()
        tools = create_browser_tools(service)

        assert len(tools) == 6

        tool_names = [t["name"] for t in tools]
        assert "browser_navigate" in tool_names
        assert "browser_click" in tool_names
        assert "browser_type" in tool_names
        assert "browser_scroll" in tool_names
        assert "browser_get_content" in tool_names
        assert "browser_screenshot" in tool_names

    def test_tool_schema_format(self):
        service = BrowserService()
        tools = create_browser_tools(service)

        navigate_tool = next(t for t in tools if t["name"] == "browser_navigate")
        assert "description" in navigate_tool
        assert "parameters" in navigate_tool
        assert navigate_tool["parameters"]["type"] == "object"
        assert "url" in navigate_tool["parameters"]["properties"]
        assert "url" in navigate_tool["parameters"]["required"]


class TestSyncBrowserService:
    """Tests for SyncBrowserService."""

    def test_init(self):
        service = SyncBrowserService()
        assert service._async_service is not None
        assert service._loop is None

    def test_context_manager(self):
        with patch.object(SyncBrowserService, 'initialize') as mock_init:
            with patch.object(SyncBrowserService, 'close') as mock_close:
                with SyncBrowserService() as _:
                    mock_init.assert_called_once()
                mock_close.assert_called_once()


class TestBrowserModes:
    """Tests for browser mode enums."""

    def test_browser_mode_values(self):
        assert BrowserMode.HEADLESS.value == "headless"
        assert BrowserMode.HEADFUL.value == "headful"

    def test_browser_engine_values(self):
        assert BrowserEngine.CHROMIUM.value == "chromium"
        assert BrowserEngine.FIREFOX.value == "firefox"
        assert BrowserEngine.WEBKIT.value == "webkit"
