"""
CompyMac Types Module.

Contains type definitions for various features.
"""

from compymac.types.citation import (
    Citation,
    CitationLocator,
    EpubCitationLocator,
    PdfCitationLocator,
    TextQuoteSelector,
    is_epub_locator,
    is_pdf_locator,
    parse_citation_locator,
)

__all__ = [
    "Citation",
    "CitationLocator",
    "EpubCitationLocator",
    "PdfCitationLocator",
    "TextQuoteSelector",
    "is_epub_locator",
    "is_pdf_locator",
    "parse_citation_locator",
]
