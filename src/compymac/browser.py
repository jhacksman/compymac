"""
Browser Automation Module - AI-agent-friendly browser control.

This module provides browser automation capabilities for the CompyMac agent,
built on Playwright with patterns inspired by browser-use and Devin.

Key features:
- Headless and headful mode support
- DOM extraction with element ID injection (like Devin's devinid)
- Standard browser actions (navigate, click, type, scroll)
- Screenshot capture for debugging
- Page state tracking
"""

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class BrowserMode(Enum):
    """Browser execution mode."""
    HEADLESS = "headless"
    HEADFUL = "headful"


class BrowserEngine(Enum):
    """Supported browser engines."""
    CHROMIUM = "chromium"
    FIREFOX = "firefox"
    WEBKIT = "webkit"


@dataclass
class ElementInfo:
    """Information about a DOM element."""
    element_id: str  # Our injected ID (like devinid)
    tag: str
    text: str
    attributes: dict[str, str]
    is_interactive: bool
    is_visible: bool
    bounding_box: dict[str, float] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "element_id": self.element_id,
            "tag": self.tag,
            "text": self.text[:100] if self.text else "",  # Truncate for LLM context
            "attributes": self.attributes,
            "is_interactive": self.is_interactive,
            "is_visible": self.is_visible,
            "bounding_box": self.bounding_box,
        }


@dataclass
class PageState:
    """Current state of a browser page."""
    url: str
    title: str
    elements: list[ElementInfo]
    screenshot_path: str | None = None
    html_snippet: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "title": self.title,
            "element_count": len(self.elements),
            "interactive_elements": [
                e.to_dict() for e in self.elements if e.is_interactive
            ][:50],  # Limit for LLM context
            "screenshot_path": self.screenshot_path,
        }

    def get_element_by_id(self, element_id: str) -> ElementInfo | None:
        """Find element by our injected ID."""
        for elem in self.elements:
            if elem.element_id == element_id:
                return elem
        return None


@dataclass
class BrowserConfig:
    """Configuration for browser service."""
    mode: BrowserMode = BrowserMode.HEADLESS
    engine: BrowserEngine = BrowserEngine.CHROMIUM
    viewport_width: int = 1280
    viewport_height: int = 720
    timeout_ms: int = 30000
    user_agent: str | None = None
    # Stealth options
    disable_webdriver_flag: bool = True
    # Screenshot options
    capture_screenshots: bool = False
    screenshot_dir: str = "/tmp/browser_screenshots"


@dataclass
class BrowserAction:
    """Result of a browser action."""
    success: bool
    action_type: str
    details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    page_state: PageState | None = None

    def to_dict(self) -> dict[str, Any]:
        result = {
            "success": self.success,
            "action_type": self.action_type,
            "details": self.details,
        }
        if self.error:
            result["error"] = self.error
        if self.page_state:
            result["page_state"] = self.page_state.to_dict()
        return result


class BrowserService:
    """
    Browser automation service using Playwright.

    Provides AI-agent-friendly browser control with:
    - Element ID injection for reliable targeting
    - DOM extraction for LLM context
    - Both headless and headful modes
    """

    def __init__(self, config: BrowserConfig | None = None):
        self.config = config or BrowserConfig()
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None
        self._element_id_counter = 0
        self._is_initialized = False

    async def initialize(self) -> None:
        """Initialize the browser."""
        if self._is_initialized:
            return

        try:
            from playwright.async_api import async_playwright
        except ImportError as e:
            raise ImportError(
                "Playwright is required for browser automation. "
                "Install it with: pip install playwright && playwright install"
            ) from e

        self._playwright = await async_playwright().start()

        # Select browser engine
        if self.config.engine == BrowserEngine.CHROMIUM:
            browser_type = self._playwright.chromium
        elif self.config.engine == BrowserEngine.FIREFOX:
            browser_type = self._playwright.firefox
        else:
            browser_type = self._playwright.webkit

        # Launch browser
        launch_options: dict[str, Any] = {
            "headless": self.config.mode == BrowserMode.HEADLESS,
        }

        self._browser = await browser_type.launch(**launch_options)

        # Create context with viewport
        context_options: dict[str, Any] = {
            "viewport": {
                "width": self.config.viewport_width,
                "height": self.config.viewport_height,
            },
        }
        if self.config.user_agent:
            context_options["user_agent"] = self.config.user_agent

        self._context = await self._browser.new_context(**context_options)
        self._page = await self._context.new_page()

        # Set default timeout
        self._page.set_default_timeout(self.config.timeout_ms)

        self._is_initialized = True
        logger.info(
            f"Browser initialized: {self.config.engine.value}, "
            f"mode={self.config.mode.value}"
        )

    async def close(self) -> None:
        """Close the browser and cleanup resources."""
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

        self._page = None
        self._context = None
        self._browser = None
        self._playwright = None
        self._is_initialized = False
        logger.info("Browser closed")

    async def _ensure_initialized(self) -> None:
        """Ensure browser is initialized before operations."""
        if not self._is_initialized:
            await self.initialize()

    async def _inject_element_ids(self) -> None:
        """Inject unique IDs into interactive elements (like Devin's devinid)."""
        if not self._page:
            return

        # JavaScript to inject element IDs
        inject_script = """
        () => {
            const interactiveSelectors = [
                'a', 'button', 'input', 'select', 'textarea',
                '[role="button"]', '[role="link"]', '[role="checkbox"]',
                '[role="radio"]', '[role="textbox"]', '[role="combobox"]',
                '[onclick]', '[tabindex]'
            ];

            let counter = 0;
            const selector = interactiveSelectors.join(', ');
            document.querySelectorAll(selector).forEach(el => {
                if (!el.getAttribute('data-compyid')) {
                    el.setAttribute('data-compyid', 'cid-' + counter++);
                }
            });
            return counter;
        }
        """
        count = await self._page.evaluate(inject_script)
        logger.debug(f"Injected IDs into {count} elements")

    async def _extract_elements(self) -> list[ElementInfo]:
        """Extract interactive elements from the page."""
        if not self._page:
            return []

        # First inject IDs
        await self._inject_element_ids()

        # JavaScript to extract element info
        extract_script = """
        () => {
            const elements = [];
            document.querySelectorAll('[data-compyid]').forEach(el => {
                const rect = el.getBoundingClientRect();
                const style = window.getComputedStyle(el);
                const isVisible = style.display !== 'none' &&
                                  style.visibility !== 'hidden' &&
                                  rect.width > 0 && rect.height > 0;

                const attrs = {};
                for (const attr of el.attributes) {
                    if (['id', 'class', 'name', 'type', 'href', 'placeholder',
                         'aria-label', 'title', 'value', 'data-compyid'].includes(attr.name)) {
                        attrs[attr.name] = attr.value;
                    }
                }

                elements.push({
                    element_id: el.getAttribute('data-compyid'),
                    tag: el.tagName.toLowerCase(),
                    text: (el.innerText || el.value || '').substring(0, 200),
                    attributes: attrs,
                    is_visible: isVisible,
                    bounding_box: isVisible ? {
                        x: rect.x,
                        y: rect.y,
                        width: rect.width,
                        height: rect.height
                    } : null
                });
            });
            return elements;
        }
        """
        raw_elements = await self._page.evaluate(extract_script)

        elements = []
        for raw in raw_elements:
            elements.append(ElementInfo(
                element_id=raw["element_id"],
                tag=raw["tag"],
                text=raw["text"],
                attributes=raw["attributes"],
                is_interactive=True,  # All extracted elements are interactive
                is_visible=raw["is_visible"],
                bounding_box=raw["bounding_box"],
            ))

        return elements

    async def _get_page_state(self, capture_screenshot: bool = False) -> PageState:
        """Get current page state."""
        if not self._page:
            return PageState(url="", title="", elements=[])

        url = self._page.url
        title = await self._page.title()
        elements = await self._extract_elements()

        screenshot_path = None
        if capture_screenshot or self.config.capture_screenshots:
            import os
            os.makedirs(self.config.screenshot_dir, exist_ok=True)
            screenshot_path = f"{self.config.screenshot_dir}/{uuid.uuid4().hex[:8]}.png"
            await self._page.screenshot(path=screenshot_path)

        return PageState(
            url=url,
            title=title,
            elements=elements,
            screenshot_path=screenshot_path,
        )

    async def navigate(self, url: str, wait_until: str = "load") -> BrowserAction:
        """Navigate to a URL."""
        await self._ensure_initialized()

        try:
            if not self._page:
                raise RuntimeError("Page not initialized")

            response = await self._page.goto(url, wait_until=wait_until)
            status = response.status if response else None

            page_state = await self._get_page_state()

            return BrowserAction(
                success=True,
                action_type="navigate",
                details={"url": url, "status": status},
                page_state=page_state,
            )
        except Exception as e:
            logger.error(f"Navigation failed: {e}")
            return BrowserAction(
                success=False,
                action_type="navigate",
                details={"url": url},
                error=str(e),
            )

    async def click(
        self,
        element_id: str | None = None,
        selector: str | None = None,
        coordinates: tuple[float, float] | None = None,
    ) -> BrowserAction:
        """Click an element by ID, selector, or coordinates."""
        await self._ensure_initialized()

        try:
            if not self._page:
                raise RuntimeError("Page not initialized")

            target_desc = ""
            if element_id:
                selector = f'[data-compyid="{element_id}"]'
                target_desc = f"element_id={element_id}"
            elif selector:
                target_desc = f"selector={selector}"
            elif coordinates:
                await self._page.mouse.click(coordinates[0], coordinates[1])
                target_desc = f"coordinates={coordinates}"
                page_state = await self._get_page_state()
                return BrowserAction(
                    success=True,
                    action_type="click",
                    details={"target": target_desc},
                    page_state=page_state,
                )
            else:
                raise ValueError("Must provide element_id, selector, or coordinates")

            await self._page.click(selector)
            page_state = await self._get_page_state()

            return BrowserAction(
                success=True,
                action_type="click",
                details={"target": target_desc},
                page_state=page_state,
            )
        except Exception as e:
            logger.error(f"Click failed: {e}")
            return BrowserAction(
                success=False,
                action_type="click",
                details={"element_id": element_id, "selector": selector},
                error=str(e),
            )

    async def type_text(
        self,
        text: str,
        element_id: str | None = None,
        selector: str | None = None,
        clear_first: bool = False,
        press_enter: bool = False,
    ) -> BrowserAction:
        """Type text into an element."""
        await self._ensure_initialized()

        try:
            if not self._page:
                raise RuntimeError("Page not initialized")

            if element_id:
                selector = f'[data-compyid="{element_id}"]'
            elif not selector:
                raise ValueError("Must provide element_id or selector")

            if clear_first:
                await self._page.fill(selector, "")

            await self._page.type(selector, text)

            if press_enter:
                await self._page.press(selector, "Enter")

            page_state = await self._get_page_state()

            return BrowserAction(
                success=True,
                action_type="type",
                details={
                    "text_length": len(text),
                    "element_id": element_id,
                    "press_enter": press_enter,
                },
                page_state=page_state,
            )
        except Exception as e:
            logger.error(f"Type failed: {e}")
            return BrowserAction(
                success=False,
                action_type="type",
                details={"element_id": element_id, "selector": selector},
                error=str(e),
            )

    async def scroll(
        self,
        direction: str = "down",
        amount: int = 500,
        element_id: str | None = None,
    ) -> BrowserAction:
        """Scroll the page or an element."""
        await self._ensure_initialized()

        try:
            if not self._page:
                raise RuntimeError("Page not initialized")

            delta_y = amount if direction == "down" else -amount

            if element_id:
                selector = f'[data-compyid="{element_id}"]'
                await self._page.evaluate(
                    f'document.querySelector("{selector}").scrollBy(0, {delta_y})'
                )
            else:
                await self._page.evaluate(f"window.scrollBy(0, {delta_y})")

            # Wait for any lazy-loaded content
            await self._page.wait_for_timeout(500)

            page_state = await self._get_page_state()

            return BrowserAction(
                success=True,
                action_type="scroll",
                details={"direction": direction, "amount": amount},
                page_state=page_state,
            )
        except Exception as e:
            logger.error(f"Scroll failed: {e}")
            return BrowserAction(
                success=False,
                action_type="scroll",
                error=str(e),
            )

    async def get_page_content(self) -> BrowserAction:
        """Get the current page state without performing an action."""
        await self._ensure_initialized()

        try:
            page_state = await self._get_page_state()
            return BrowserAction(
                success=True,
                action_type="get_content",
                page_state=page_state,
            )
        except Exception as e:
            logger.error(f"Get content failed: {e}")
            return BrowserAction(
                success=False,
                action_type="get_content",
                error=str(e),
            )

    async def screenshot(self, full_page: bool = False) -> BrowserAction:
        """Take a screenshot of the current page."""
        await self._ensure_initialized()

        try:
            if not self._page:
                raise RuntimeError("Page not initialized")

            import os
            os.makedirs(self.config.screenshot_dir, exist_ok=True)
            path = f"{self.config.screenshot_dir}/{uuid.uuid4().hex[:8]}.png"

            await self._page.screenshot(path=path, full_page=full_page)

            return BrowserAction(
                success=True,
                action_type="screenshot",
                details={"path": path, "full_page": full_page},
            )
        except Exception as e:
            logger.error(f"Screenshot failed: {e}")
            return BrowserAction(
                success=False,
                action_type="screenshot",
                error=str(e),
            )

    async def execute_js(self, script: str) -> BrowserAction:
        """Execute JavaScript on the page."""
        await self._ensure_initialized()

        try:
            if not self._page:
                raise RuntimeError("Page not initialized")

            result = await self._page.evaluate(script)

            return BrowserAction(
                success=True,
                action_type="execute_js",
                details={"result": str(result)[:1000]},  # Truncate result
            )
        except Exception as e:
            logger.error(f"JS execution failed: {e}")
            return BrowserAction(
                success=False,
                action_type="execute_js",
                error=str(e),
            )

    async def wait_for_selector(
        self,
        selector: str,
        timeout_ms: int | None = None,
    ) -> BrowserAction:
        """Wait for an element to appear."""
        await self._ensure_initialized()

        try:
            if not self._page:
                raise RuntimeError("Page not initialized")

            timeout = timeout_ms or self.config.timeout_ms
            await self._page.wait_for_selector(selector, timeout=timeout)

            page_state = await self._get_page_state()

            return BrowserAction(
                success=True,
                action_type="wait_for_selector",
                details={"selector": selector},
                page_state=page_state,
            )
        except Exception as e:
            logger.error(f"Wait for selector failed: {e}")
            return BrowserAction(
                success=False,
                action_type="wait_for_selector",
                details={"selector": selector},
                error=str(e),
            )


def create_browser_tools(browser_service: BrowserService) -> list[dict[str, Any]]:
    """
    Create tool definitions for browser actions.

    Returns a list of tool schemas that can be registered with the ToolRegistry.
    """
    return [
        {
            "name": "browser_navigate",
            "description": "Navigate to a URL in the browser",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The URL to navigate to",
                    },
                },
                "required": ["url"],
            },
        },
        {
            "name": "browser_click",
            "description": "Click an element in the browser by its element_id (from page state)",
            "parameters": {
                "type": "object",
                "properties": {
                    "element_id": {
                        "type": "string",
                        "description": "The element ID (data-compyid) to click",
                    },
                    "selector": {
                        "type": "string",
                        "description": "CSS selector (fallback if element_id not provided)",
                    },
                },
            },
        },
        {
            "name": "browser_type",
            "description": "Type text into an input element",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "The text to type",
                    },
                    "element_id": {
                        "type": "string",
                        "description": "The element ID to type into",
                    },
                    "clear_first": {
                        "type": "boolean",
                        "description": "Clear the field before typing",
                        "default": False,
                    },
                    "press_enter": {
                        "type": "boolean",
                        "description": "Press Enter after typing",
                        "default": False,
                    },
                },
                "required": ["text"],
            },
        },
        {
            "name": "browser_scroll",
            "description": "Scroll the page up or down",
            "parameters": {
                "type": "object",
                "properties": {
                    "direction": {
                        "type": "string",
                        "enum": ["up", "down"],
                        "description": "Scroll direction",
                        "default": "down",
                    },
                    "amount": {
                        "type": "integer",
                        "description": "Pixels to scroll",
                        "default": 500,
                    },
                },
            },
        },
        {
            "name": "browser_get_content",
            "description": "Get the current page state including interactive elements",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
        {
            "name": "browser_screenshot",
            "description": "Take a screenshot of the current page",
            "parameters": {
                "type": "object",
                "properties": {
                    "full_page": {
                        "type": "boolean",
                        "description": "Capture the full scrollable page",
                        "default": False,
                    },
                },
            },
        },
    ]


# Synchronous wrapper for non-async contexts
class SyncBrowserService:
    """Synchronous wrapper around BrowserService for non-async code."""

    def __init__(self, config: BrowserConfig | None = None):
        self._async_service = BrowserService(config)
        self._loop: asyncio.AbstractEventLoop | None = None

    def _get_loop(self) -> asyncio.AbstractEventLoop:
        if self._loop is None or self._loop.is_closed():
            try:
                self._loop = asyncio.get_event_loop()
            except RuntimeError:
                self._loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self._loop)
        return self._loop

    def _run(self, coro: Any) -> Any:
        return self._get_loop().run_until_complete(coro)

    def initialize(self) -> None:
        self._run(self._async_service.initialize())

    def close(self) -> None:
        self._run(self._async_service.close())

    def navigate(self, url: str) -> BrowserAction:
        return self._run(self._async_service.navigate(url))

    def click(
        self,
        element_id: str | None = None,
        selector: str | None = None,
        coordinates: tuple[float, float] | None = None,
    ) -> BrowserAction:
        return self._run(self._async_service.click(element_id, selector, coordinates))

    def type_text(
        self,
        text: str,
        element_id: str | None = None,
        selector: str | None = None,
        clear_first: bool = False,
        press_enter: bool = False,
    ) -> BrowserAction:
        return self._run(
            self._async_service.type_text(text, element_id, selector, clear_first, press_enter)
        )

    def scroll(
        self,
        direction: str = "down",
        amount: int = 500,
        element_id: str | None = None,
    ) -> BrowserAction:
        return self._run(self._async_service.scroll(direction, amount, element_id))

    def get_page_content(self) -> BrowserAction:
        return self._run(self._async_service.get_page_content())

    def screenshot(self, full_page: bool = False) -> BrowserAction:
        return self._run(self._async_service.screenshot(full_page))

    def execute_js(self, script: str) -> BrowserAction:
        return self._run(self._async_service.execute_js(script))

    def wait_for_selector(self, selector: str, timeout_ms: int | None = None) -> BrowserAction:
        return self._run(self._async_service.wait_for_selector(selector, timeout_ms))

    def __enter__(self) -> "SyncBrowserService":
        self.initialize()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()
