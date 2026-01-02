"""
Document Parsers for extracting text from various file formats.

Supports:
- Plain text files (.txt)
- PDF files (via PyMuPDF, docling, or fallback)
- EPUB files (via docling if available)

Phase 2 additions:
- Document classification (digital vs scanned)
- Table detection with Camelot
- OCR fallback for scanned PDFs
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

# Try to import Camelot for table detection
try:
    import camelot
    CAMELOT_AVAILABLE = True
except ImportError:
    CAMELOT_AVAILABLE = False

# Try to import pytesseract for OCR
try:
    import pytesseract
    from PIL import Image
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False


class PDFClassification:
    """Classification of a PDF document type."""

    DIGITAL = "digital"  # Text-based, extractable text
    SCANNED = "scanned"  # Image-based, needs OCR
    MIXED = "mixed"  # Some pages digital, some scanned

    def __init__(
        self,
        doc_type: str,
        text_pages: list[int],
        scanned_pages: list[int],
        confidence: float,
    ):
        self.doc_type = doc_type
        self.text_pages = text_pages
        self.scanned_pages = scanned_pages
        self.confidence = confidence

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "doc_type": self.doc_type,
            "text_pages": self.text_pages,
            "scanned_pages": self.scanned_pages,
            "confidence": self.confidence,
        }


class TableResult:
    """Result from table extraction."""

    def __init__(
        self,
        page_num: int,
        table_index: int,
        markdown: str,
        accuracy: float,
    ):
        self.page_num = page_num
        self.table_index = table_index
        self.markdown = markdown
        self.accuracy = accuracy

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "page_num": self.page_num,
            "table_index": self.table_index,
            "markdown": self.markdown,
            "accuracy": self.accuracy,
        }


class ParseResult:
    """Result from parsing a document."""

    def __init__(
        self,
        text: str,
        metadata: dict[str, Any],
        format: str,
        classification: PDFClassification | None = None,
        tables: list[TableResult] | None = None,
    ):
        self.text = text
        self.metadata = metadata
        self.format = format
        self.classification = classification
        self.tables = tables or []


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
        """Parse PDF using PyMuPDF (fitz) with classification and OCR fallback."""
        doc = fitz.open(str(file_path))

        # Check for encryption
        if doc.is_encrypted:
            doc.close()
            raise ValueError("PDF is password-protected. Please provide password.")

        page_count = len(doc)

        # Phase 2: Classify document (digital vs scanned)
        classification = self._classify_pdf(doc)

        # Extract text based on classification
        pages_text = []
        for page_num in range(page_count):
            page = doc[page_num]
            text = page.get_text()

            # If page has little/no text and OCR is available, try OCR
            if (
                page_num + 1 in classification.scanned_pages
                and TESSERACT_AVAILABLE
            ):
                ocr_text = self._ocr_page(doc, page_num)
                if ocr_text.strip():
                    text = ocr_text

            if text.strip():
                pages_text.append(f"--- Page {page_num + 1} ---\n{text}")

        # Phase 2: Extract tables if Camelot is available
        tables = []
        if CAMELOT_AVAILABLE:
            tables = self._extract_tables(file_path)

        doc.close()

        full_text = "\n\n".join(pages_text)

        # Append table content to text
        if tables:
            table_text = "\n\n--- Tables ---\n"
            for table in tables:
                table_text += f"\n[Table on Page {table.page_num}]\n{table.markdown}\n"
            full_text += table_text

        return ParseResult(
            text=full_text,
            metadata={
                **metadata,
                "parser": "pymupdf",
                "page_count": page_count,
                "classification": classification.to_dict(),
                "table_count": len(tables),
                "ocr_used": len(classification.scanned_pages) > 0 and TESSERACT_AVAILABLE,
            },
            format="pdf",
            classification=classification,
            tables=tables,
        )

    def _classify_pdf(self, doc: "fitz.Document") -> PDFClassification:
        """
        Classify PDF as digital, scanned, or mixed.

        A page is considered "scanned" if it has very little extractable text
        relative to its image content.
        """
        text_pages = []
        scanned_pages = []
        min_chars_per_page = 50  # Threshold for considering a page as having text

        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text().strip()

            if len(text) >= min_chars_per_page:
                text_pages.append(page_num + 1)
            else:
                # Check if page has images (likely scanned)
                image_list = page.get_images()
                if image_list or len(text) < 10:
                    scanned_pages.append(page_num + 1)
                else:
                    # Very little text but no images - still count as text page
                    text_pages.append(page_num + 1)

        # Determine document type
        total_pages = len(doc)
        if not scanned_pages:
            doc_type = PDFClassification.DIGITAL
            confidence = 1.0
        elif not text_pages:
            doc_type = PDFClassification.SCANNED
            confidence = 1.0
        else:
            doc_type = PDFClassification.MIXED
            # Confidence based on ratio of text pages
            confidence = len(text_pages) / total_pages

        return PDFClassification(
            doc_type=doc_type,
            text_pages=text_pages,
            scanned_pages=scanned_pages,
            confidence=confidence,
        )

    def _ocr_page(self, doc: "fitz.Document", page_num: int) -> str:
        """
        Perform OCR on a PDF page using pytesseract.

        Converts the page to an image and runs OCR.
        """
        if not TESSERACT_AVAILABLE:
            return ""

        try:
            page = doc[page_num]
            # Render page to image at 300 DPI for better OCR
            mat = fitz.Matrix(300 / 72, 300 / 72)
            pix = page.get_pixmap(matrix=mat)

            # Convert to PIL Image
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

            # Run OCR
            text = pytesseract.image_to_string(img)
            return text
        except Exception:
            # OCR failed, return empty string
            return ""

    def _extract_tables(self, file_path: Path) -> list[TableResult]:
        """
        Extract tables from PDF using Camelot.

        Returns list of TableResult objects with markdown representation.
        """
        if not CAMELOT_AVAILABLE:
            return []

        tables = []
        try:
            # Try lattice method first (for bordered tables)
            extracted = camelot.read_pdf(
                str(file_path),
                pages="all",
                flavor="lattice",
            )

            for i, table in enumerate(extracted):
                if table.accuracy > 50:  # Only include reasonably accurate tables
                    # Convert to markdown
                    df = table.df
                    markdown = df.to_markdown(index=False)
                    tables.append(
                        TableResult(
                            page_num=table.page,
                            table_index=i,
                            markdown=markdown,
                            accuracy=table.accuracy,
                        )
                    )

            # If no tables found with lattice, try stream method
            if not tables:
                extracted = camelot.read_pdf(
                    str(file_path),
                    pages="all",
                    flavor="stream",
                )
                for i, table in enumerate(extracted):
                    if table.accuracy > 50:
                        df = table.df
                        markdown = df.to_markdown(index=False)
                        tables.append(
                            TableResult(
                                page_num=table.page,
                                table_index=i,
                                markdown=markdown,
                                accuracy=table.accuracy,
                            )
                        )
        except Exception:
            # Table extraction failed, return empty list
            pass

        return tables

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
