"""
Document Parsers for extracting text from various file formats.

Supports:
- Plain text files (.txt)
- PDF files (via PyMuPDF, docling, or fallback)
- EPUB files (via EbookLib or docling)

Phase 2 additions:
- Document classification (digital vs scanned)
- Table detection with Camelot
- OCR fallback for scanned PDFs

Phase 3 additions:
- Venice.ai vision API integration for complex pages
- Image/diagram description extraction

Phase 3.1 additions:
- Pluggable OCR provider abstraction (Venice, vLLM, OpenAI-compatible)
- OCR-first approach using Gemma 3 27B (default) or custom models
- Support for SOTA OCR models via vLLM (olmOCR-2, DeepSeek-OCR, Qwen2.5-VL)

Phase 4 additions (Folder Library):
- PDF bookmark/outline extraction via get_toc()
- EPUB chapter navigation extraction via EbookLib
- Navigation tree structure for document internal navigation
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

# Try to import OCR client for vision-based text extraction
try:
    from compymac.ingestion.ocr_provider import OCRClient, OCRResult
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False
    OCRClient = None  # type: ignore[misc, assignment]
    OCRResult = None  # type: ignore[misc, assignment]

# Try to import EbookLib for EPUB parsing
try:
    import ebooklib
    from ebooklib import epub
    EBOOKLIB_AVAILABLE = True
except ImportError:
    EBOOKLIB_AVAILABLE = False
    epub = None  # type: ignore[misc, assignment]
    ebooklib = None  # type: ignore[misc, assignment]

# Try to import BeautifulSoup for HTML parsing (EPUB content)
try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False
    BeautifulSoup = None  # type: ignore[misc, assignment]


class PDFClassification:
    """Classification of a PDF document type."""

    DIGITAL = "digital"  # Text-based, extractable text
    IMAGE_BASED = "image_based"  # Image-based, needs OCR
    MIXED = "mixed"  # Some pages have extractable text, some need OCR

    def __init__(
        self,
        doc_type: str,
        text_pages: list[int],
        ocr_required_pages: list[int],
        confidence: float,
    ):
        self.doc_type = doc_type
        self.text_pages = text_pages
        self.ocr_required_pages = ocr_required_pages
        self.confidence = confidence

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "doc_type": self.doc_type,
            "text_pages": self.text_pages,
            "ocr_required_pages": self.ocr_required_pages,
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
    Phase 2: Includes classification, table detection, and OCR.
    Phase 3: Includes vision analysis for complex PDF pages.
    """

    def __init__(
        self,
        use_docling: bool = True,
        use_ocr: bool = True,
        ocr_api_key: str | None = None,
    ):
        """
        Initialize document parser.

        Args:
            use_docling: Whether to use docling for PDF/EPUB parsing
            use_ocr: Whether to use vision-based OCR for complex pages
            ocr_api_key: API key for OCR (uses LLM_API_KEY env var if None)
        """
        self.use_docling = use_docling and DOCLING_AVAILABLE
        self.use_ocr = use_ocr and OCR_AVAILABLE
        self._converter = None
        self._ocr_client: OCRClient | None = None

        if self.use_docling:
            self._converter = DocumentConverter()

        if self.use_ocr and OCRClient is not None:
            self._ocr_client = OCRClient(api_key=ocr_api_key)

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
        """Parse PDF using PyMuPDF (fitz) with classification, OCR, and vision fallback."""
        doc = fitz.open(str(file_path))

        # Check for encryption
        if doc.is_encrypted:
            doc.close()
            raise ValueError("PDF is password-protected. Please provide password.")

        page_count = len(doc)
        vision_analyses: list[dict[str, Any]] = []
        ocr_errors: list[dict[str, Any]] = []  # Track OCR failures for debugging

        # Phase 2: Classify document (digital vs scanned)
        classification = self._classify_pdf(doc)

        # Extract text based on classification
        pages_text = []
        for page_num in range(page_count):
            page = doc[page_num]
            text = page.get_text()
            needs_ocr = (page_num + 1) in classification.ocr_required_pages

            # For pages that need OCR, use vision OCR as primary method (not Tesseract)
            # This is more accurate than Tesseract for most documents
            if needs_ocr and self._ocr_client is not None:
                ocr_result = self._ocr_page_with_vision(doc, page_num)
                if ocr_result:
                    if ocr_result.confidence > 0 and ocr_result.text:
                        # Successful OCR - use the extracted text
                        vision_analyses.append(ocr_result.to_dict())
                        pages_text.append(
                            f"--- Page {page_num + 1} ---\n{ocr_result.text}"
                        )
                        continue
                    elif ocr_result.confidence == 0:
                        # OCR failed - track the error for debugging
                        ocr_errors.append({
                            "page_num": page_num + 1,
                            "error": ocr_result.text,
                            "model": ocr_result.model_used,
                        })

            # Fallback: If page needs OCR and Tesseract is available, try it
            if needs_ocr and TESSERACT_AVAILABLE:
                ocr_text = self._ocr_page(doc, page_num)
                if ocr_text.strip():
                    text = ocr_text

            # Use whatever text we have (extracted or OCR'd)
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
                "tesseract_ocr_used": len(classification.ocr_required_pages) > 0 and TESSERACT_AVAILABLE,
                "vision_ocr_results": vision_analyses,
                "vision_ocr_pages": len(vision_analyses),
                "vision_ocr_errors": ocr_errors,
            },
            format="pdf",
            classification=classification,
            tables=tables,
        )

    def _classify_pdf(self, doc: "fitz.Document") -> PDFClassification:
        """
        Classify PDF as digital, image-based, or mixed.

        A page is considered to require OCR if it has very little extractable text
        relative to its image content, or if it has large images covering most
        of the page (common for image-based PDFs with text overlays like stamps).
        """
        text_pages = []
        ocr_required_pages = []

        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text().strip()
            rect = page.rect
            page_area = rect.width * rect.height

            # Calculate text density (chars per 1000 sq points)
            text_density = (len(text) / page_area) * 1000 if page_area > 0 else 0

            # Check for large images that cover significant portion of page
            image_list = page.get_images()
            has_large_images = False
            for img in image_list:
                # img format: (xref, smask, width, height, bpc, colorspace, alt, name, filter, referencer)
                img_width = img[2] if len(img) > 2 else 0
                img_height = img[3] if len(img) > 3 else 0
                img_area = img_width * img_height
                # Consider "large" if image covers >30% of page area (scaled by typical DPI ratio)
                # Images are often stored at higher resolution than page dimensions
                if img_area > 0 and (img_area / 4) > page_area * 0.3:
                    has_large_images = True
                    break

            # Classification logic:
            # - High text density (>5 chars/1000 sq pts) AND no large images = digital
            # - Has large images = likely image-based, needs OCR (even with some text overlay)
            # - Very low text density (<1) = needs OCR
            if has_large_images:
                # Large image covering page = needs OCR, even if there's some text overlay
                ocr_required_pages.append(page_num + 1)
            elif text_density > 5:
                # Good amount of text relative to page size = digital
                text_pages.append(page_num + 1)
            elif text_density < 1:
                # Almost no text = needs OCR
                ocr_required_pages.append(page_num + 1)
            else:
                # Ambiguous - check if text is just headers/footers
                blocks = page.get_text("blocks")
                # Filter to content area (not top/bottom 10%)
                content_blocks = [
                    b for b in blocks
                    if b[1] > rect.height * 0.1 and b[3] < rect.height * 0.9
                ]
                if len(content_blocks) < 2:
                    # Only header/footer text, no real content = needs OCR
                    ocr_required_pages.append(page_num + 1)
                else:
                    text_pages.append(page_num + 1)

        # Determine document type
        total_pages = len(doc)
        if not ocr_required_pages:
            doc_type = PDFClassification.DIGITAL
            confidence = 1.0
        elif not text_pages:
            doc_type = PDFClassification.IMAGE_BASED
            confidence = 1.0
        else:
            doc_type = PDFClassification.MIXED
            # Confidence based on ratio of text pages
            confidence = len(text_pages) / total_pages

        return PDFClassification(
            doc_type=doc_type,
            text_pages=text_pages,
            ocr_required_pages=ocr_required_pages,
            confidence=confidence,
        )

    def _ocr_page_with_vision(
        self,
        doc: "fitz.Document",
        page_idx: int,
    ) -> "OCRResult | None":
        """
        Perform OCR on a PDF page using vision-language model.

        Args:
            doc: Open PyMuPDF document.
            page_idx: Page index (0-based).

        Returns:
            OCRResult or None if OCR fails.
        """
        if self._ocr_client is None:
            return None

        try:
            # Render page to image at 150 DPI (good balance of quality vs size)
            page = doc[page_idx]
            mat = fitz.Matrix(150 / 72, 150 / 72)
            pix = page.get_pixmap(matrix=mat)
            page_image = pix.tobytes("png")

            # Perform OCR
            return self._ocr_client.ocr_page(
                image_bytes=page_image,
                page_num=page_idx + 1,
            )
        except Exception:
            # OCR failed, return None
            return None

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
        """Parse EPUB file using EbookLib (preferred) or docling."""
        # Try EbookLib first (better for navigation extraction)
        if EBOOKLIB_AVAILABLE and BS4_AVAILABLE:
            return self._parse_with_ebooklib(file_path, metadata)

        # Fall back to docling if available
        if self.use_docling and self._converter:
            return self._parse_with_docling(file_path, metadata, "epub")

        raise ValueError(
            "EPUB parsing requires ebooklib+beautifulsoup4 or docling. "
            "Install with: pip install ebooklib beautifulsoup4"
        )

    def _parse_with_ebooklib(
        self, file_path: Path, metadata: dict[str, Any]
    ) -> ParseResult:
        """Parse EPUB using EbookLib with chapter extraction and href tracking.

        Phase 3 Citation Linking: Tracks href and character ranges for each chapter
        to enable mapping chunks back to their source spine items for citation linking.
        """
        if epub is None or ebooklib is None or BeautifulSoup is None:
            raise ValueError("EbookLib or BeautifulSoup not available")

        book = epub.read_epub(str(file_path))

        # Extract text from each spine item (chapter) with href tracking
        chapters_text = []
        chapter_ranges: list[dict[str, Any]] = []
        chapter_count = 0
        current_pos = 0

        for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
            href = item.get_name()
            soup = BeautifulSoup(item.get_content(), "html.parser")
            text = soup.get_text(separator="\n", strip=True)

            if text:
                chapter_count += 1
                chapter_header = f"--- Chapter {chapter_count} ---\n"
                chapter_content = chapter_header + text

                # Track chapter range for citation linking
                chapter_start = current_pos
                chapter_end = current_pos + len(chapter_content)

                # Try to extract chapter title from HTML
                chapter_title = None
                title_tag = soup.find(["h1", "h2", "title"])
                if title_tag:
                    chapter_title = title_tag.get_text(strip=True)

                chapter_ranges.append({
                    "href": href,
                    "chapter_index": chapter_count,
                    "chapter_title": chapter_title,
                    "start_char": chapter_start,
                    "end_char": chapter_end,
                })

                chapters_text.append(chapter_content)
                current_pos = chapter_end + 2  # +2 for "\n\n" separator

        full_text = "\n\n".join(chapters_text)

        # Extract metadata
        title = None
        author = None
        try:
            title_meta = book.get_metadata("DC", "title")
            if title_meta:
                title = title_meta[0][0]
            author_meta = book.get_metadata("DC", "creator")
            if author_meta:
                author = author_meta[0][0]
        except (IndexError, KeyError):
            pass

        return ParseResult(
            text=full_text,
            metadata={
                **metadata,
                "parser": "ebooklib",
                "chapter_count": chapter_count,
                "epub_title": title,
                "epub_author": author,
                "chapter_ranges": chapter_ranges,
            },
            format="epub",
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
        if EBOOKLIB_AVAILABLE or DOCLING_AVAILABLE:
            formats.append(".epub")
        return formats


def extract_pdf_navigation(file_path: Path | str) -> list[dict[str, Any]]:
    """
    Extract PDF bookmarks/outline as navigation entries.

    Uses PyMuPDF's get_toc() to extract the table of contents.

    Args:
        file_path: Path to the PDF file

    Returns:
        List of navigation entries with format:
        [{"id": "nav_0", "title": "Chapter 1", "level": 1, "target": {"type": "pdf_page", "page": 1}}]
    """
    if not PYMUPDF_AVAILABLE:
        return []

    file_path = Path(file_path)
    if not file_path.exists():
        return []

    try:
        doc = fitz.open(str(file_path))
        toc = doc.get_toc()  # Returns [[level, title, page], ...]
        doc.close()

        if not toc:
            return []  # Many PDFs don't have bookmarks

        navigation = []
        for i, entry in enumerate(toc):
            if len(entry) >= 3:
                level, title, page = entry[0], entry[1], entry[2]
                navigation.append({
                    "id": f"nav_{i}",
                    "title": str(title),
                    "level": int(level),
                    "target": {"type": "pdf_page", "page": int(page)},
                })

        return navigation

    except Exception:
        return []


def extract_epub_navigation(file_path: Path | str) -> list[dict[str, Any]]:
    """
    Extract EPUB table of contents as navigation entries.

    Uses EbookLib to parse the EPUB navigation structure.

    Args:
        file_path: Path to the EPUB file

    Returns:
        List of navigation entries with format:
        [{"id": "nav_0", "title": "Chapter 1", "level": 1, "target": {"type": "epub_href", "href": "..."}}]
    """
    if not EBOOKLIB_AVAILABLE or epub is None:
        return []

    file_path = Path(file_path)
    if not file_path.exists():
        return []

    try:
        book = epub.read_epub(str(file_path))
        navigation: list[dict[str, Any]] = []
        nav_counter = [0]  # Use list to allow mutation in nested function

        def process_toc_item(
            item: Any, level: int = 1
        ) -> dict[str, Any] | None:
            """Process a single TOC item recursively."""
            nav_id = f"nav_{nav_counter[0]}"
            nav_counter[0] += 1

            if hasattr(item, "title") and hasattr(item, "href"):
                # It's a Link object
                return {
                    "id": nav_id,
                    "title": str(item.title),
                    "level": level,
                    "target": {"type": "epub_href", "href": str(item.href)},
                }
            elif isinstance(item, tuple) and len(item) >= 2:
                # It's a Section with children: (Section, [children])
                section, children = item[0], item[1]
                title = getattr(section, "title", str(section)) if hasattr(section, "title") else str(section)
                href = getattr(section, "href", "") if hasattr(section, "href") else ""

                entry: dict[str, Any] = {
                    "id": nav_id,
                    "title": str(title),
                    "level": level,
                    "target": {"type": "epub_href", "href": str(href)},
                }

                # Process children
                if children:
                    child_entries = []
                    for child in children:
                        child_entry = process_toc_item(child, level + 1)
                        if child_entry:
                            child_entries.append(child_entry)
                    if child_entries:
                        entry["children"] = child_entries

                return entry

            return None

        for item in book.toc:
            entry = process_toc_item(item)
            if entry:
                navigation.append(entry)

        return navigation

    except Exception:
        return []


def extract_navigation(file_path: Path | str, doc_format: str) -> list[dict[str, Any]]:
    """
    Extract navigation from a document based on its format.

    Args:
        file_path: Path to the document
        doc_format: Document format ("pdf" or "epub")

    Returns:
        List of navigation entries
    """
    if doc_format == "pdf":
        return extract_pdf_navigation(file_path)
    elif doc_format == "epub":
        return extract_epub_navigation(file_path)
    return []
