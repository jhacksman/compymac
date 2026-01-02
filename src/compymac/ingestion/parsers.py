"""
Document Parsers for extracting text from various file formats.

Supports:
- Plain text files (.txt)
- PDF files (via PyMuPDF, docling, or fallback)
- EPUB files (via docling if available)

Phase 3 additions:
- Venice.ai vision API integration for complex pages
- Image/diagram description extraction
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

# Try to import PDF vision client for complex page analysis
try:
    from compymac.ingestion.pdf_vision import PDFVisionClient, VisionAnalysisResult
    VISION_AVAILABLE = True
except ImportError:
    VISION_AVAILABLE = False
    PDFVisionClient = None  # type: ignore[misc, assignment]
    VisionAnalysisResult = None  # type: ignore[misc, assignment]


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
    Phase 3: Includes vision analysis for complex PDF pages.
    """

    def __init__(
        self,
        use_docling: bool = True,
        use_vision: bool = True,
        vision_api_key: str | None = None,
    ):
        """
        Initialize document parser.

        Args:
            use_docling: Whether to use docling for PDF/EPUB parsing
            use_vision: Whether to use Venice.ai vision for complex pages
            vision_api_key: API key for vision analysis (uses env var if None)
        """
        self.use_docling = use_docling and DOCLING_AVAILABLE
        self.use_vision = use_vision and VISION_AVAILABLE
        self.vision_api_key = vision_api_key
        self._converter = None
        self._vision_client: PDFVisionClient | None = None

        if self.use_docling:
            self._converter = DocumentConverter()

        if self.use_vision and PDFVisionClient is not None:
            self._vision_client = PDFVisionClient(api_key=vision_api_key)

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
        """Parse PDF using PyMuPDF (fitz) with vision fallback for complex pages."""
        doc = fitz.open(str(file_path))

        # Check for encryption
        if doc.is_encrypted:
            doc.close()
            raise ValueError("PDF is password-protected. Please provide password.")

        pages_text = []
        page_count = len(doc)
        vision_analyses: list[dict[str, Any]] = []
        min_chars_threshold = 50  # Pages with less text may need vision analysis

        for page_num in range(page_count):
            page = doc[page_num]
            text = page.get_text()

            # Check if page has sufficient text
            if text.strip() and len(text.strip()) >= min_chars_threshold:
                pages_text.append(f"--- Page {page_num + 1} ---\n{text}")
            else:
                # Page has little/no text - try vision analysis if available
                vision_text = ""
                if self._vision_client is not None:
                    vision_result = self._analyze_page_with_vision(
                        doc, page_num, file_path.name
                    )
                    if vision_result:
                        vision_analyses.append(vision_result.to_dict())
                        vision_text = (
                            f"\n[Vision Analysis]\n{vision_result.description}"
                        )
                        if vision_result.detected_elements:
                            vision_text += (
                                f"\n[Detected Elements: "
                                f"{', '.join(vision_result.detected_elements)}]"
                            )

                # Include whatever text we have plus vision analysis
                page_content = f"--- Page {page_num + 1} ---\n"
                if text.strip():
                    page_content += text
                if vision_text:
                    page_content += vision_text
                if page_content.strip() != f"--- Page {page_num + 1} ---":
                    pages_text.append(page_content)

        doc.close()

        full_text = "\n\n".join(pages_text)

        return ParseResult(
            text=full_text,
            metadata={
                **metadata,
                "parser": "pymupdf",
                "page_count": page_count,
                "vision_analyses": vision_analyses,
                "vision_pages_analyzed": len(vision_analyses),
            },
            format="pdf",
        )

    def _analyze_page_with_vision(
        self,
        doc: "fitz.Document",
        page_idx: int,
        doc_name: str,
    ) -> "VisionAnalysisResult | None":
        """
        Analyze a PDF page using Venice.ai vision API.

        Args:
            doc: Open PyMuPDF document.
            page_idx: Page index (0-based).
            doc_name: Document name for context.

        Returns:
            VisionAnalysisResult or None if analysis fails.
        """
        if self._vision_client is None:
            return None

        try:
            # Render page to image at 150 DPI
            page = doc[page_idx]
            mat = fitz.Matrix(150 / 72, 150 / 72)
            pix = page.get_pixmap(matrix=mat)
            page_image = pix.tobytes("png")

            # Analyze with vision client
            return self._vision_client.analyze_page(
                page_image=page_image,
                page_num=page_idx + 1,
                context=f"Document: {doc_name}",
            )
        except Exception:
            # Vision analysis failed, return None
            return None

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
