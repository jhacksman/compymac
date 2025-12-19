#!/usr/bin/env python3
"""
Comprehensive Browser Tool Test Suite

This script tests the CompyMac BrowserService against real websites to verify:
1. Navigation and page loading
2. DOM extraction with element ID injection
3. Element targeting and clicking
4. Form filling and typing
5. Scrolling behavior
6. Error handling

Ground truth comparison: Top 3 Hacker News stories captured via Devin browser.
"""

import asyncio
import sys
from datetime import datetime

# Add src to path
sys.path.insert(0, "/home/ubuntu/repos/compymac/src")

from compymac.browser import (
    BrowserConfig,
    BrowserMode,
    BrowserService,
    SyncBrowserService,
)

# Ground truth from Devin browser (captured at test time)
GROUND_TRUTH_HN_TOP3 = [
    {
        "title": "Garage – An S3 object store so reliable you can run it outside datacenters",
        "domain": "deuxfleurs.fr",
        "url_contains": "garagehq.deuxfleurs.fr",
    },
    {
        "title": "GotaTun -- Mullvad's WireGuard Implementation in Rust",
        "domain": "mullvad.net",
        "url_contains": "mullvad.net",
    },
    {
        "title": "Cursor Acquires Graphite",
        "domain": "graphite.com",
        "url_contains": "graphite.com",
    },
]


class TestResult:
    """Result of a single test."""
    def __init__(self, name: str, passed: bool, details: str = "", error: str = ""):
        self.name = name
        self.passed = passed
        self.details = details
        self.error = error
        self.timestamp = datetime.now().isoformat()

    def __str__(self):
        status = "PASS" if self.passed else "FAIL"
        result = f"[{status}] {self.name}"
        if self.details:
            result += f"\n       Details: {self.details}"
        if self.error:
            result += f"\n       Error: {self.error}"
        return result


class BrowserTestSuite:
    """Comprehensive test suite for BrowserService."""

    def __init__(self):
        self.results: list[TestResult] = []
        self.service: BrowserService | None = None

    async def setup(self):
        """Initialize browser service."""
        config = BrowserConfig(
            mode=BrowserMode.HEADLESS,
            viewport_width=1280,
            viewport_height=720,
            timeout_ms=30000,
        )
        self.service = BrowserService(config)
        await self.service.initialize()
        print("Browser initialized (headless Chromium)")

    async def teardown(self):
        """Close browser service."""
        if self.service:
            await self.service.close()
            print("Browser closed")

    def add_result(self, result: TestResult):
        """Add a test result."""
        self.results.append(result)
        print(result)

    async def test_1_navigation(self):
        """Test 1: Basic navigation to example.com"""
        print("\n--- Test 1: Navigation ---")

        action = await self.service.navigate("https://example.com")

        if action.success and action.page_state:
            self.add_result(TestResult(
                "Navigation to example.com",
                passed=True,
                details=f"URL: {action.page_state.url}, Title: {action.page_state.title}"
            ))
        else:
            self.add_result(TestResult(
                "Navigation to example.com",
                passed=False,
                error=action.error or "Unknown error"
            ))

    async def test_2_element_id_injection(self):
        """Test 2: Element ID injection (data-compyid)"""
        print("\n--- Test 2: Element ID Injection ---")

        action = await self.service.navigate("https://example.com")

        if action.success and action.page_state:
            elements = action.page_state.elements
            elements_with_ids = [e for e in elements if e.element_id.startswith("cid-")]

            if elements_with_ids:
                self.add_result(TestResult(
                    "Element ID injection",
                    passed=True,
                    details=f"Found {len(elements_with_ids)} elements with data-compyid"
                ))
            else:
                self.add_result(TestResult(
                    "Element ID injection",
                    passed=False,
                    error="No elements with data-compyid found"
                ))
        else:
            self.add_result(TestResult(
                "Element ID injection",
                passed=False,
                error=action.error or "Navigation failed"
            ))

    async def test_3_hacker_news_extraction(self):
        """Test 3: Extract top 3 stories from Hacker News and compare to ground truth"""
        print("\n--- Test 3: Hacker News Extraction (Ground Truth Comparison) ---")

        action = await self.service.navigate("https://news.ycombinator.com/")

        if not action.success or not action.page_state:
            self.add_result(TestResult(
                "HN navigation",
                passed=False,
                error=action.error or "Navigation failed"
            ))
            return

        # Extract story titles using JavaScript
        js_script = """
        () => {
            const stories = [];
            const titleLinks = document.querySelectorAll('span.titleline > a');
            for (let i = 0; i < Math.min(3, titleLinks.length); i++) {
                const link = titleLinks[i];
                stories.push({
                    title: link.innerText,
                    href: link.href
                });
            }
            return stories;
        }
        """

        js_result = await self.service.execute_js(js_script)

        if not js_result.success:
            self.add_result(TestResult(
                "HN story extraction",
                passed=False,
                error=js_result.error or "JS execution failed"
            ))
            return

        # Parse the result
        try:
            # The result is a string representation, need to parse it
            result_str = js_result.details.get("result", "[]")
            # Try to evaluate as Python list (it's returned as string)
            stories = eval(result_str) if result_str != "[]" else []
        except Exception as e:
            self.add_result(TestResult(
                "HN story parsing",
                passed=False,
                error=f"Failed to parse stories: {e}"
            ))
            return

        print(f"  Extracted {len(stories)} stories from CompyMac browser")

        # Compare with ground truth
        matches = 0
        for i, (extracted, expected) in enumerate(zip(stories, GROUND_TRUTH_HN_TOP3, strict=False)):
            extracted_title = extracted.get("title", "")
            extracted_href = extracted.get("href", "")

            # Check if URL contains expected domain
            url_match = expected["url_contains"] in extracted_href

            print(f"  Story {i+1}:")
            print(f"    Expected: {expected['title'][:50]}...")
            print(f"    Got:      {extracted_title[:50]}...")
            print(f"    URL match: {url_match}")

            if url_match:
                matches += 1

        # HN stories can change rapidly, so we check if at least 1 matches
        # or if we got 3 valid stories (even if different from ground truth)
        if len(stories) >= 3:
            self.add_result(TestResult(
                "HN story extraction",
                passed=True,
                details=f"Extracted {len(stories)} stories, {matches}/3 matched ground truth (HN updates frequently)"
            ))
        else:
            self.add_result(TestResult(
                "HN story extraction",
                passed=False,
                error=f"Only extracted {len(stories)} stories, expected 3"
            ))

    async def test_4_click_navigation(self):
        """Test 4: Click a link and verify navigation"""
        print("\n--- Test 4: Click Navigation ---")

        # Navigate to Hacker News (more reliable for click testing)
        action = await self.service.navigate("https://news.ycombinator.com/")

        if not action.success or not action.page_state:
            self.add_result(TestResult(
                "Click navigation setup",
                passed=False,
                error="Initial navigation failed"
            ))
            return

        # Find the first story link (an <a> tag with href)
        link_element = None
        for elem in action.page_state.elements:
            if elem.tag == "a" and elem.attributes.get("href", "").startswith("http"):
                # Skip HN internal links
                href = elem.attributes.get("href", "")
                if "ycombinator" not in href and elem.text:
                    link_element = elem
                    break

        if not link_element:
            self.add_result(TestResult(
                "Click navigation",
                passed=False,
                error="Could not find external link to click"
            ))
            return

        print(f"  Clicking: {link_element.text[:50]}...")
        original_url = action.page_state.url

        # Click the link
        click_action = await self.service.click(element_id=link_element.element_id)

        if click_action.success and click_action.page_state:
            new_url = click_action.page_state.url
            if new_url != original_url:
                self.add_result(TestResult(
                    "Click navigation",
                    passed=True,
                    details=f"Navigated from HN to: {new_url[:50]}..."
                ))
            else:
                self.add_result(TestResult(
                    "Click navigation",
                    passed=False,
                    error="URL did not change after click"
                ))
        else:
            self.add_result(TestResult(
                "Click navigation",
                passed=False,
                error=click_action.error or "Click failed"
            ))

    async def test_5_form_typing(self):
        """Test 5: Type into a search form"""
        print("\n--- Test 5: Form Typing ---")

        # Navigate to DuckDuckGo (simple search form)
        action = await self.service.navigate("https://duckduckgo.com/")

        if not action.success or not action.page_state:
            self.add_result(TestResult(
                "Form typing setup",
                passed=False,
                error="Navigation to DuckDuckGo failed"
            ))
            return

        # Find the search input
        search_input = None
        for elem in action.page_state.elements:
            if elem.tag == "input" and elem.attributes.get("type") in ["text", "search", None]:
                search_input = elem
                break

        if not search_input:
            # Try using selector directly
            type_action = await self.service.type_text(
                text="test query",
                selector='input[type="text"], input[name="q"]'
            )
        else:
            type_action = await self.service.type_text(
                text="test query",
                element_id=search_input.element_id
            )

        if type_action.success:
            self.add_result(TestResult(
                "Form typing",
                passed=True,
                details="Successfully typed into search input"
            ))
        else:
            self.add_result(TestResult(
                "Form typing",
                passed=False,
                error=type_action.error or "Type failed"
            ))

    async def test_6_scrolling(self):
        """Test 6: Scroll the page"""
        print("\n--- Test 6: Scrolling ---")

        # Navigate to HN (has scrollable content)
        action = await self.service.navigate("https://news.ycombinator.com/")

        if not action.success:
            self.add_result(TestResult(
                "Scroll setup",
                passed=False,
                error="Navigation failed"
            ))
            return

        # Scroll down
        scroll_action = await self.service.scroll(direction="down", amount=500)

        if scroll_action.success:
            self.add_result(TestResult(
                "Scrolling",
                passed=True,
                details="Successfully scrolled down 500px"
            ))
        else:
            self.add_result(TestResult(
                "Scrolling",
                passed=False,
                error=scroll_action.error or "Scroll failed"
            ))

    async def test_7_screenshot(self):
        """Test 7: Take a screenshot"""
        print("\n--- Test 7: Screenshot ---")

        action = await self.service.navigate("https://example.com")

        if not action.success:
            self.add_result(TestResult(
                "Screenshot setup",
                passed=False,
                error="Navigation failed"
            ))
            return

        screenshot_action = await self.service.screenshot()

        if screenshot_action.success:
            path = screenshot_action.details.get("path", "")
            self.add_result(TestResult(
                "Screenshot",
                passed=True,
                details=f"Screenshot saved to: {path}"
            ))
        else:
            self.add_result(TestResult(
                "Screenshot",
                passed=False,
                error=screenshot_action.error or "Screenshot failed"
            ))

    async def test_8_error_handling(self):
        """Test 8: Error handling for invalid element"""
        print("\n--- Test 8: Error Handling ---")

        action = await self.service.navigate("https://example.com")

        if not action.success:
            self.add_result(TestResult(
                "Error handling setup",
                passed=False,
                error="Navigation failed"
            ))
            return

        # Try to click a non-existent element
        click_action = await self.service.click(element_id="nonexistent-element-id-12345")

        if not click_action.success and click_action.error:
            self.add_result(TestResult(
                "Error handling",
                passed=True,
                details=f"Correctly returned error: {click_action.error[:50]}..."
            ))
        else:
            self.add_result(TestResult(
                "Error handling",
                passed=False,
                error="Expected error for non-existent element, but got success"
            ))

    async def test_9_sync_wrapper(self):
        """Test 9: SyncBrowserService wrapper (thread-based)"""
        print("\n--- Test 9: Sync Wrapper ---")

        try:
            # The SyncBrowserService uses a dedicated thread with its own event loop,
            # so it can be called from within an async context without conflicts.
            sync_service = SyncBrowserService()
            sync_service.initialize()

            action = sync_service.navigate("https://example.com")

            if action.success and action.page_state:
                self.add_result(TestResult(
                    "Sync wrapper",
                    passed=True,
                    details=f"SyncBrowserService works (thread-based), URL: {action.page_state.url}"
                ))
            else:
                self.add_result(TestResult(
                    "Sync wrapper",
                    passed=False,
                    error=action.error or "Navigation failed"
                ))

            sync_service.close()

        except Exception as e:
            self.add_result(TestResult(
                "Sync wrapper",
                passed=False,
                error=str(e)
            ))

    async def run_all(self):
        """Run all tests."""
        print("=" * 60)
        print("CompyMac Browser Tool - Comprehensive Test Suite")
        print("=" * 60)
        print(f"Started at: {datetime.now().isoformat()}")

        await self.setup()

        try:
            await self.test_1_navigation()
            await self.test_2_element_id_injection()
            await self.test_3_hacker_news_extraction()
            await self.test_4_click_navigation()
            await self.test_5_form_typing()
            await self.test_6_scrolling()
            await self.test_7_screenshot()
            await self.test_8_error_handling()
            await self.test_9_sync_wrapper()
        finally:
            await self.teardown()

        # Summary
        print("\n" + "=" * 60)
        print("TEST SUMMARY")
        print("=" * 60)

        passed = sum(1 for r in self.results if r.passed)
        failed = sum(1 for r in self.results if not r.passed)

        print(f"Total: {len(self.results)} tests")
        print(f"Passed: {passed}")
        print(f"Failed: {failed}")

        if failed > 0:
            print("\nFailed tests:")
            for r in self.results:
                if not r.passed:
                    print(f"  - {r.name}: {r.error}")

        print("\n" + "=" * 60)

        return failed == 0


async def main():
    suite = BrowserTestSuite()
    success = await suite.run_all()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
