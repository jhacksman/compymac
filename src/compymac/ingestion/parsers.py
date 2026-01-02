"""
Document Parsers for extracting text from various file formats.

Supports:
- Plain text files (.txt)
- PDF files (via PyMuPDF, docling, or fallback)
- EPUB files (via docling if available)
"""

from pathlib import Path
from typing import Any

# Try to import PyMuPDF for PDF parsing
try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False

# Try to import docling for advanced parsing
try:
    from docling.document_converter import DocumentConverter
    DOCLING_AVAILABLE = True
except ImportError:
    DOCLING_AVAILABLE = False


class ParseResult:
    """Result from parsing a document."""

    def __init__(
        self,
        text: str,
        metadata: dict[str, Any],
        format: str,
    ):
        self.text = text
        self.metadata = metadata
        self.format = format


class DocumentParser:
    """
    Parses documents into plain text.

    Supports multiple formats with graceful fallbacks.
    """

    def __init__(self, use_docling: bool = True):
        """
        Initialize document parser.

        Args:
            use_docling: Whether to use docling for PDF/EPUB parsing
        """
        self.use_docling = use_docling and DOCLING_AVAILABLE
        self._converter = None

        if self.use_docling:
            self._converter = DocumentConverter()

    def parse(self, file_path: Path | str) -> ParseResult:
        """
        Parse a document file.

        Args:
            file_path: Path to the document

        Returns:
            ParseResult with extracted text and metadata

        Raises:
            ValueError: If file format is not supported
            FileNotFoundError: If file does not exist
        """
        file_path = Path(file_path)

        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        suffix = file_path.suffix.lower()
        metadata = {
            "filename": file_path.name,
            "filepath": str(file_path.absolute()),
            "format": suffix,
            "size_bytes": file_path.stat().st_size,
        }

        if suffix == ".txt":
            return self._parse_text(file_path, metadata)
        elif suffix == ".pdf":
            return self._parse_pdf(file_path, metadata)
        elif suffix == ".epub":
            return self._parse_epub(file_path, metadata)
        elif suffix in (".md", ".markdown"):
            return self._parse_text(file_path, metadata)
        else:
            raise ValueError(f"Unsupported file format: {suffix}")

    def _parse_text(self, file_path: Path, metadata: dict[str, Any]) -> ParseResult:
        """Parse plain text file."""
        text = file_path.read_text(encoding="utf-8")
        return ParseResult(
            text=text,
            metadata=metadata,
            format="text",
        )

    def _parse_pdf(self, file_path: Path, metadata: dict[str, Any]) -> ParseResult:
        """Parse PDF file using PyMuPDF (preferred) or docling."""
        # Try PyMuPDF first (fast and reliable)
        if PYMUPDF_AVAILABLE:
            return self._parse_with_pymupdf(file_path, metadata)

        # Fall back to docling if available
        if self.use_docling and self._converter:
            return self._parse_with_docling(file_path, metadata, "pdf")

        raise ValueError(
            "PDF parsing requires PyMuPDF or docling. "
            "Install with: pip install pymupdf"
        )

    def _parse_with_pymupdf(
        self, file_path: Path, metadata: dict[str, Any]
    ) -> ParseResult:
        """Parse PDF using PyMuPDF (fitz)."""
        doc = fitz.open(str(file_path))

        # Check for encryption
        if doc.is_encrypted:
            doc.close()
            raise ValueError("PDF is password-protected. Please provide password.")

        pages_text = []
        page_count = len(doc)

        for page_num in range(page_count):
            page = doc[page_num]
            text = page.get_text()
            if text.strip():
                pages_text.append(f"--- Page {page_num + 1} ---\n{text}")

        doc.close()

        full_text = "\n\n".join(pages_text)

        return ParseResult(
            text=full_text,
            metadata={
                **metadata,
                "parser": "pymupdf",
                "page_count": page_count,
            },
            format="pdf",
        )

    def _parse_epub(self, file_path: Path, metadata: dict[str, Any]) -> ParseResult:
        """Parse EPUB file."""
        if self.use_docling and self._converter:
            return self._parse_with_docling(file_path, metadata, "epub")

        raise ValueError(
            "EPUB parsing requires docling. Install with: pip install docling"
        )

    def _parse_with_docling(
        self,
        file_path: Path,
        metadata: dict[str, Any],
        format: str,
    ) -> ParseResult:
        """Parse document using docling."""
        if not self._converter:
            raise ValueError("Docling converter not initialized")

        result = self._converter.convert(str(file_path))
        text = result.document.export_to_markdown()

        return ParseResult(
            text=text,
            metadata={**metadata, "parser": "docling"},
            format=format,
        )

    @staticmethod
    def supported_formats() -> list[str]:
        """Get list of supported file formats."""
        formats = [".txt", ".md", ".markdown"]
        if PYMUPDF_AVAILABLE or DOCLING_AVAILABLE:
            formats.append(".pdf")
        if DOCLING_AVAILABLE:
            formats.append(".epub")
        return formats
