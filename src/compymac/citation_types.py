"""
Citation Locator Types for CompyMac.

Phase 2 of Citation Linking: Defines the data structures for locating
and highlighting text in documents when citations are clicked.

Based on W3C Web Annotation TextQuoteSelector for resilient text anchoring.
"""

from dataclasses import dataclass, field
from typing import Literal


@dataclass
class TextQuoteSelector:
    """
    W3C Web Annotation inspired locator format.

    Uses exact text with optional prefix/suffix for disambiguation.
    Resilient to minor formatting changes (whitespace, punctuation).
    """

    type: Literal["TextQuoteSelector"] = "TextQuoteSelector"
    exact: str = ""
    prefix: str | None = None
    suffix: str | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        result: dict = {"type": self.type, "exact": self.exact}
        if self.prefix:
            result["prefix"] = self.prefix
        if self.suffix:
            result["suffix"] = self.suffix
        return result

    @classmethod
    def from_dict(cls, data: dict) -> "TextQuoteSelector":
        """Create from dictionary."""
        return cls(
            type=data.get("type", "TextQuoteSelector"),
            exact=data.get("exact", ""),
            prefix=data.get("prefix"),
            suffix=data.get("suffix"),
        )


@dataclass
class EpubCitationLocator:
    """
    EPUB Citation Locator - for navigating to text in EPUB documents.
    """

    type: Literal["epub_text"] = "epub_text"
    href: str = ""
    selector: TextQuoteSelector = field(default_factory=TextQuoteSelector)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "type": self.type,
            "href": self.href,
            "selector": self.selector.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "EpubCitationLocator":
        """Create from dictionary."""
        selector_data = data.get("selector", {})
        return cls(
            type=data.get("type", "epub_text"),
            href=data.get("href", ""),
            selector=TextQuoteSelector.from_dict(selector_data),
        )


@dataclass
class PdfCitationLocator:
    """
    PDF Citation Locator - for navigating to text in PDF documents.

    Includes both page number (for fallback navigation) and text selector
    (for highlighting when text layer is available).
    """

    type: Literal["pdf_text"] = "pdf_text"
    page: int = 1
    selector: TextQuoteSelector = field(default_factory=TextQuoteSelector)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "type": self.type,
            "page": self.page,
            "selector": self.selector.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PdfCitationLocator":
        """Create from dictionary."""
        selector_data = data.get("selector", {})
        return cls(
            type=data.get("type", "pdf_text"),
            page=data.get("page", 1),
            selector=TextQuoteSelector.from_dict(selector_data),
        )


@dataclass
class WebCitationLocator:
    """
    Web Citation Locator - for opening external URLs in a new browser tab.

    Used when the agent browses web pages and wants to cite them.
    """

    type: Literal["web_url"] = "web_url"
    url: str = ""
    title: str = ""
    retrieved_at: str = ""  # ISO timestamp

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "type": self.type,
            "url": self.url,
            "title": self.title,
            "retrieved_at": self.retrieved_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "WebCitationLocator":
        """Create from dictionary."""
        return cls(
            type=data.get("type", "web_url"),
            url=data.get("url", ""),
            title=data.get("title", ""),
            retrieved_at=data.get("retrieved_at", ""),
        )


CitationLocator = EpubCitationLocator | PdfCitationLocator | WebCitationLocator


def parse_citation_locator(data: dict) -> CitationLocator | None:
    """Parse a citation locator from a dictionary."""
    locator_type = data.get("type")
    if locator_type == "epub_text":
        return EpubCitationLocator.from_dict(data)
    elif locator_type == "pdf_text":
        return PdfCitationLocator.from_dict(data)
    elif locator_type == "web_url":
        return WebCitationLocator.from_dict(data)
    return None


@dataclass
class Citation:
    """
    Full citation with document reference and locator.

    Returned by the librarian agent when citing sources.
    """

    doc_id: str
    doc_title: str
    chunk_id: str
    score: float
    excerpt: str
    locator: CitationLocator | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        result: dict = {
            "doc_id": self.doc_id,
            "doc_title": self.doc_title,
            "chunk_id": self.chunk_id,
            "score": self.score,
            "excerpt": self.excerpt,
        }
        if self.locator:
            result["locator"] = self.locator.to_dict()
        return result

    @classmethod
    def from_dict(cls, data: dict) -> "Citation":
        """Create from dictionary."""
        locator_data = data.get("locator")
        locator = parse_citation_locator(locator_data) if locator_data else None
        return cls(
            doc_id=data.get("doc_id", ""),
            doc_title=data.get("doc_title", ""),
            chunk_id=data.get("chunk_id", ""),
            score=data.get("score", 0.0),
            excerpt=data.get("excerpt", ""),
            locator=locator,
        )


def is_epub_locator(locator: CitationLocator) -> bool:
    """Type guard for EPUB locator."""
    return isinstance(locator, EpubCitationLocator)


def is_pdf_locator(locator: CitationLocator) -> bool:
    """Type guard for PDF locator."""
    return isinstance(locator, PdfCitationLocator)


def is_web_locator(locator: CitationLocator) -> bool:
    """Type guard for Web URL locator."""
    return isinstance(locator, WebCitationLocator)
