"""
EPUB Chapter Renderer with HTML Sanitization and CSS Scoping.

Phase 1 of Citation Linking: Renders EPUB chapters as sanitized HTML
with scoped CSS for safe embedding in the web UI.

Security features:
- HTML sanitization (remove scripts, event handlers, dangerous elements)
- CSS scoping to container class to prevent style leakage
- Path traversal prevention for EPUB internal resources
- Malformed HTML tolerance via lxml recovery mode
"""

import html
import re
from pathlib import Path
from typing import Any

# Try to import lxml for robust HTML parsing
try:
    from lxml.html import HTMLParser
    from lxml.html import fromstring as lxml_fromstring
    from lxml.html import tostring as lxml_tostring
    LXML_AVAILABLE = True
except ImportError:
    LXML_AVAILABLE = False
    HTMLParser = None  # type: ignore[misc, assignment]

# Try to import BeautifulSoup as fallback
try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False
    BeautifulSoup = None  # type: ignore[misc, assignment]

# Try to import bleach for HTML sanitization
try:
    import bleach
    BLEACH_AVAILABLE = True
except ImportError:
    BLEACH_AVAILABLE = False
    bleach = None  # type: ignore[misc, assignment]

# Try to import EbookLib for EPUB parsing
try:
    import ebooklib
    from ebooklib import epub
    EBOOKLIB_AVAILABLE = True
except ImportError:
    EBOOKLIB_AVAILABLE = False
    epub = None  # type: ignore[misc, assignment]
    ebooklib = None  # type: ignore[misc, assignment]


# Allowed HTML tags for sanitization
ALLOWED_TAGS = [
    'p', 'div', 'span', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'ul', 'ol', 'li', 'a', 'em', 'strong', 'b', 'i', 'u',
    'blockquote', 'pre', 'code', 'br', 'hr', 'img', 'table',
    'thead', 'tbody', 'tr', 'th', 'td', 'figure', 'figcaption',
    'section', 'article', 'aside', 'nav', 'header', 'footer',
    'sup', 'sub', 'small', 'mark', 'del', 'ins', 'abbr',
    'dl', 'dt', 'dd', 'caption', 'colgroup', 'col',
]

# Allowed attributes per tag
ALLOWED_ATTRIBUTES = {
    '*': ['class', 'id'],
    'a': ['href', 'title'],
    'img': ['src', 'alt', 'title', 'width', 'height'],
    'td': ['colspan', 'rowspan'],
    'th': ['colspan', 'rowspan', 'scope'],
    'col': ['span'],
    'colgroup': ['span'],
}

# Dangerous CSS properties to strip
DANGEROUS_CSS_PROPERTIES = [
    r'position\s*:\s*fixed',
    r'position\s*:\s*absolute',
    r'z-index\s*:',
    r'expression\s*\(',
    r'javascript\s*:',
    r'behavior\s*:',
    r'-moz-binding\s*:',
    r'@import',
]


class EpubChapter:
    """Represents a rendered EPUB chapter."""

    def __init__(
        self,
        href: str,
        title: str,
        html_content: str,
        css_content: str,
        chapter_index: int,
        total_chapters: int,
    ):
        self.href = href
        self.title = title
        self.html_content = html_content
        self.css_content = css_content
        self.chapter_index = chapter_index
        self.total_chapters = total_chapters

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "href": self.href,
            "title": self.title,
            "html": self.html_content,
            "css": self.css_content,
            "chapter_index": self.chapter_index,
            "total_chapters": self.total_chapters,
            "has_prev": self.chapter_index > 0,
            "has_next": self.chapter_index < self.total_chapters - 1,
        }


class EpubRenderer:
    """
    Renders EPUB chapters as sanitized HTML with scoped CSS.

    Features:
    - Extracts chapter HTML from EPUB files
    - Sanitizes HTML to remove dangerous elements
    - Scopes CSS to container class to prevent style leakage
    - Handles malformed HTML with lxml recovery mode
    """

    def __init__(self, container_class: str = "epub-content"):
        """
        Initialize the renderer.

        Args:
            container_class: CSS class to scope styles to
        """
        self.container_class = container_class
        self._epub_cache: dict[str, Any] = {}  # Cache opened EPUBs

    def get_chapter(
        self,
        epub_path: Path | str,
        href: str | None = None,
        chapter_index: int | None = None,
    ) -> EpubChapter | None:
        """
        Get a chapter from an EPUB file.

        Args:
            epub_path: Path to the EPUB file
            href: Chapter href (e.g., "chapter1.xhtml")
            chapter_index: Chapter index (0-based), used if href is None

        Returns:
            EpubChapter with sanitized HTML and scoped CSS, or None if not found
        """
        if not EBOOKLIB_AVAILABLE or epub is None:
            return None

        epub_path = Path(epub_path)
        if not epub_path.exists():
            return None

        try:
            book = epub.read_epub(str(epub_path))

            # Get spine items (ordered chapters)
            spine_items = list(book.get_items_of_type(ebooklib.ITEM_DOCUMENT))
            if not spine_items:
                return None

            total_chapters = len(spine_items)

            # Find the requested chapter
            target_item = None
            target_index = 0

            if href is not None:
                # Find by href
                for i, item in enumerate(spine_items):
                    item_href = item.get_name()
                    # Handle both exact match and fragment match
                    if item_href == href or item_href == href.split('#')[0]:
                        target_item = item
                        target_index = i
                        break
            elif chapter_index is not None:
                # Find by index
                if 0 <= chapter_index < total_chapters:
                    target_item = spine_items[chapter_index]
                    target_index = chapter_index
            else:
                # Default to first chapter
                target_item = spine_items[0]
                target_index = 0

            if target_item is None:
                return None

            # Extract and sanitize content
            raw_html = target_item.get_content()
            sanitized_html, extracted_css = self._process_chapter_html(
                raw_html, epub_path, target_item.get_name()
            )

            # Scope CSS
            scoped_css = self._scope_css(extracted_css)

            # Get chapter title
            title = self._extract_title(raw_html) or f"Chapter {target_index + 1}"

            return EpubChapter(
                href=target_item.get_name(),
                title=title,
                html_content=sanitized_html,
                css_content=scoped_css,
                chapter_index=target_index,
                total_chapters=total_chapters,
            )

        except Exception as e:
            # Log error but don't crash
            print(f"Error reading EPUB chapter: {e}")
            return None

    def get_chapter_list(self, epub_path: Path | str) -> list[dict[str, Any]]:
        """
        Get list of chapters in an EPUB.

        Args:
            epub_path: Path to the EPUB file

        Returns:
            List of chapter info dicts with href, title, and index
        """
        if not EBOOKLIB_AVAILABLE or epub is None:
            return []

        epub_path = Path(epub_path)
        if not epub_path.exists():
            return []

        try:
            book = epub.read_epub(str(epub_path))
            spine_items = list(book.get_items_of_type(ebooklib.ITEM_DOCUMENT))

            chapters = []
            for i, item in enumerate(spine_items):
                raw_html = item.get_content()
                title = self._extract_title(raw_html) or f"Chapter {i + 1}"
                chapters.append({
                    "index": i,
                    "href": item.get_name(),
                    "title": title,
                })

            return chapters

        except Exception:
            return []

    def _process_chapter_html(
        self,
        raw_html: bytes,
        epub_path: Path,
        chapter_href: str,
    ) -> tuple[str, str]:
        """
        Process chapter HTML: parse, extract CSS, sanitize.

        Args:
            raw_html: Raw HTML bytes from EPUB
            epub_path: Path to EPUB for resource resolution
            chapter_href: Chapter href for relative path resolution

        Returns:
            Tuple of (sanitized_html, extracted_css)
        """
        # Parse HTML with tolerance for malformed content
        html_str = self._parse_with_recovery(raw_html)

        # Extract inline and embedded CSS
        extracted_css = self._extract_css(html_str)

        # Remove style tags from HTML (we'll inject scoped CSS separately)
        html_str = re.sub(r'<style[^>]*>.*?</style>', '', html_str, flags=re.DOTALL | re.IGNORECASE)

        # Sanitize HTML
        sanitized = self._sanitize_html(html_str, epub_path, chapter_href)

        return sanitized, extracted_css

    def _parse_with_recovery(self, raw_html: bytes) -> str:
        """
        Parse HTML with tolerance for malformed content.

        Uses lxml recovery mode, falls back to BeautifulSoup, then plain text.
        """
        # Decode bytes
        try:
            html_str = raw_html.decode('utf-8')
        except UnicodeDecodeError:
            try:
                html_str = raw_html.decode('latin-1')
            except Exception:
                html_str = raw_html.decode('utf-8', errors='replace')

        # Try lxml with recovery mode
        if LXML_AVAILABLE and HTMLParser is not None:
            try:
                parser = HTMLParser(
                    recover=True,
                    remove_comments=True,
                    remove_pis=True,
                )
                doc = lxml_fromstring(html_str, parser=parser)

                # Extract body content if present
                body = doc.find('.//body')
                if body is not None:
                    return lxml_tostring(body, encoding='unicode', method='html')
                return lxml_tostring(doc, encoding='unicode', method='html')
            except Exception:
                pass

        # Fall back to BeautifulSoup
        if BS4_AVAILABLE and BeautifulSoup is not None:
            try:
                soup = BeautifulSoup(html_str, 'lxml')
                body = soup.find('body')
                if body:
                    return str(body)
                return str(soup)
            except Exception:
                try:
                    soup = BeautifulSoup(html_str, 'html.parser')
                    body = soup.find('body')
                    if body:
                        return str(body)
                    return str(soup)
                except Exception:
                    pass

        # Last resort: escape and wrap
        return f"<div>{html.escape(html_str)}</div>"

    def _extract_css(self, html_str: str) -> str:
        """Extract CSS from style tags and inline styles."""
        css_parts = []

        # Extract from <style> tags
        style_pattern = re.compile(r'<style[^>]*>(.*?)</style>', re.DOTALL | re.IGNORECASE)
        for match in style_pattern.finditer(html_str):
            css_parts.append(match.group(1))

        return '\n'.join(css_parts)

    def _extract_title(self, raw_html: bytes) -> str | None:
        """Extract title from chapter HTML."""
        try:
            html_str = raw_html.decode('utf-8', errors='replace')

            # Try <title> tag
            title_match = re.search(r'<title[^>]*>(.*?)</title>', html_str, re.IGNORECASE | re.DOTALL)
            if title_match:
                title = title_match.group(1).strip()
                # Remove HTML tags from title
                title = re.sub(r'<[^>]+>', '', title)
                if title:
                    return title

            # Try first <h1>
            h1_match = re.search(r'<h1[^>]*>(.*?)</h1>', html_str, re.IGNORECASE | re.DOTALL)
            if h1_match:
                title = h1_match.group(1).strip()
                title = re.sub(r'<[^>]+>', '', title)
                if title:
                    return title[:100]  # Limit length

            return None
        except Exception:
            return None

    def _sanitize_html(
        self,
        html_str: str,
        epub_path: Path,
        chapter_href: str,
    ) -> str:
        """
        Sanitize HTML for safe rendering.

        Removes dangerous elements, rewrites resource URLs.
        """
        if BLEACH_AVAILABLE and bleach is not None:
            # Use bleach for sanitization
            clean = bleach.clean(
                html_str,
                tags=ALLOWED_TAGS,
                attributes=ALLOWED_ATTRIBUTES,
                strip=True,
            )
        else:
            # Basic sanitization without bleach
            clean = html_str
            # Remove script tags
            clean = re.sub(r'<script[^>]*>.*?</script>', '', clean, flags=re.DOTALL | re.IGNORECASE)
            # Remove on* event handlers
            clean = re.sub(r'\s+on\w+\s*=\s*["\'][^"\']*["\']', '', clean, flags=re.IGNORECASE)
            # Remove javascript: URLs
            clean = re.sub(r'href\s*=\s*["\']javascript:[^"\']*["\']', 'href="#"', clean, flags=re.IGNORECASE)

        # Rewrite image URLs to safe endpoint
        # For now, we'll use data URIs or strip images
        # TODO: Add image proxy endpoint
        clean = re.sub(
            r'src\s*=\s*["\']([^"\']+)["\']',
            lambda m: self._rewrite_image_src(m.group(1), epub_path, chapter_href),
            clean,
            flags=re.IGNORECASE,
        )

        return clean

    def _rewrite_image_src(
        self,
        src: str,
        epub_path: Path,
        chapter_href: str,
    ) -> str:
        """
        Rewrite image src to safe format.

        For now, strips external images and keeps data URIs.
        TODO: Add image proxy endpoint for EPUB internal images.
        """
        # Keep data URIs
        if src.startswith('data:'):
            return f'src="{src}"'

        # Strip external URLs
        if src.startswith(('http://', 'https://', '//')):
            return 'src=""'

        # For internal images, we'd need an image proxy endpoint
        # For now, strip them (will be added in later phase)
        return 'src=""'

    def _scope_css(self, css_content: str) -> str:
        """
        Scope CSS to container class to prevent style leakage.

        Example:
            Input:  "p { margin: 1em; }"
            Output: ".epub-content p { margin: 1em; }"
        """
        if not css_content.strip():
            return ""

        # First, sanitize CSS
        sanitized = self._sanitize_css(css_content)

        # Parse and scope each rule
        scoped_rules = []

        # Simple regex-based CSS parsing
        # Matches: selector { properties }
        rule_pattern = re.compile(r'([^{}]+)\{([^{}]+)\}', re.DOTALL)

        for match in rule_pattern.finditer(sanitized):
            selector = match.group(1).strip()
            properties = match.group(2).strip()

            # Skip @rules (media queries, font-face, etc.)
            if selector.startswith('@'):
                continue

            # Skip empty rules
            if not properties:
                continue

            # Handle multiple selectors (comma-separated)
            selectors = [s.strip() for s in selector.split(',')]
            scoped_selectors = []

            for sel in selectors:
                if sel:
                    # Scope to container
                    scoped_selectors.append(f".{self.container_class} {sel}")

            if scoped_selectors:
                scoped_rules.append(f"{', '.join(scoped_selectors)} {{ {properties} }}")

        return '\n'.join(scoped_rules)

    def _sanitize_css(self, css_content: str) -> str:
        """Remove dangerous CSS properties."""
        sanitized = css_content

        for pattern in DANGEROUS_CSS_PROPERTIES:
            sanitized = re.sub(pattern + r'[^;]*;?', '', sanitized, flags=re.IGNORECASE)

        return sanitized


# Module-level renderer instance
_renderer: EpubRenderer | None = None


def get_epub_renderer() -> EpubRenderer:
    """Get or create the module-level EPUB renderer."""
    global _renderer
    if _renderer is None:
        _renderer = EpubRenderer()
    return _renderer


def render_epub_chapter(
    epub_path: Path | str,
    href: str | None = None,
    chapter_index: int | None = None,
) -> dict[str, Any] | None:
    """
    Convenience function to render an EPUB chapter.

    Args:
        epub_path: Path to the EPUB file
        href: Chapter href (e.g., "chapter1.xhtml")
        chapter_index: Chapter index (0-based), used if href is None

    Returns:
        Dict with chapter data, or None if not found
    """
    renderer = get_epub_renderer()
    chapter = renderer.get_chapter(epub_path, href, chapter_index)
    if chapter:
        return chapter.to_dict()
    return None
