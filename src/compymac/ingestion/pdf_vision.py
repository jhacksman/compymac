"""
PDF Vision Integration - Venice.ai Vision API for Complex PDF Pages.

Phase 3 of PDF ingestion: Uses Venice.ai vision-capable models to analyze
complex PDF pages containing diagrams, charts, images, and other visual content
that cannot be extracted via text extraction alone.

Key features:
- Page-to-image conversion for vision analysis
- Diagram and chart description extraction
- Image content summarization
- Fallback for pages where OCR fails
"""

import base64
import os
from dataclasses import dataclass
from typing import Any

import httpx

# Try to import PyMuPDF for page rendering
try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False

# PIL is available if PyMuPDF is available (used for image handling)
PIL_AVAILABLE = PYMUPDF_AVAILABLE


@dataclass
class VisionAnalysisResult:
    """Result from vision analysis of a PDF page."""

    page_num: int
    description: str
    detected_elements: list[str]
    confidence: float
    model_used: str
    analysis_time_ms: float

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "page_num": self.page_num,
            "description": self.description,
            "detected_elements": self.detected_elements,
            "confidence": self.confidence,
            "model_used": self.model_used,
            "analysis_time_ms": self.analysis_time_ms,
        }


class PDFVisionClient:
    """
    Client for analyzing PDF pages using Venice.ai vision API.

    Uses vision-capable LLM models to describe complex visual content
    in PDF pages that cannot be extracted via text extraction.
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = "https://api.venice.ai/api/v1",
        model: str = "qwen/qwen2.5-vl-72b-instruct",
        timeout: float = 60.0,
        max_retries: int = 3,
    ):
        """
        Initialize PDF vision client.

        Args:
            api_key: Venice.ai API key. If None, reads from LLM_API_KEY env var.
            base_url: Base URL for Venice.ai API.
            model: Vision-capable model to use.
            timeout: Request timeout in seconds.
            max_retries: Maximum retries for failed requests.
        """
        self.api_key = api_key or os.environ.get("LLM_API_KEY", "")
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries
        self._client: httpx.Client | None = None

    @property
    def client(self) -> httpx.Client:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.Client(
                timeout=self.timeout,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
            )
        return self._client

    def analyze_page(
        self,
        page_image: bytes,
        page_num: int,
        context: str = "",
    ) -> VisionAnalysisResult:
        """
        Analyze a PDF page image using vision model.

        Args:
            page_image: PNG/JPEG image bytes of the page.
            page_num: Page number (1-indexed).
            context: Optional context about the document.

        Returns:
            VisionAnalysisResult with description and detected elements.
        """
        import time

        start_time = time.time()

        # Encode image as base64
        image_b64 = base64.b64encode(page_image).decode()

        # Determine image type
        image_type = "image/png"
        if page_image[:2] == b"\xff\xd8":
            image_type = "image/jpeg"

        # Build prompt for page analysis
        prompt = self._build_analysis_prompt(context)

        # Build request payload using OpenAI vision format
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt,
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{image_type};base64,{image_b64}",
                            },
                        },
                    ],
                }
            ],
            "max_tokens": 1000,
            "temperature": 0.1,
        }

        # Make API request with retries
        last_error: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                response = self.client.post(
                    f"{self.base_url}/chat/completions",
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()

                # Parse response
                content = data["choices"][0]["message"]["content"]
                description, elements = self._parse_analysis_response(content)

                analysis_time = (time.time() - start_time) * 1000

                return VisionAnalysisResult(
                    page_num=page_num,
                    description=description,
                    detected_elements=elements,
                    confidence=0.8,  # Default confidence for vision analysis
                    model_used=self.model,
                    analysis_time_ms=analysis_time,
                )

            except httpx.HTTPStatusError as e:
                last_error = e
                if e.response.status_code == 429:
                    # Rate limited, wait and retry
                    time.sleep(2 ** attempt)
                    continue
                # Other HTTP errors, don't retry
                break
            except Exception as e:
                last_error = e
                time.sleep(1)
                continue

        # All retries failed, return empty result
        analysis_time = (time.time() - start_time) * 1000
        return VisionAnalysisResult(
            page_num=page_num,
            description=f"Vision analysis failed: {last_error}",
            detected_elements=[],
            confidence=0.0,
            model_used=self.model,
            analysis_time_ms=analysis_time,
        )

    def analyze_pdf_pages(
        self,
        pdf_path: str,
        pages: list[int] | None = None,
        dpi: int = 150,
    ) -> list[VisionAnalysisResult]:
        """
        Analyze multiple pages from a PDF file.

        Args:
            pdf_path: Path to PDF file.
            pages: List of page numbers to analyze (1-indexed). None = all pages.
            dpi: Resolution for page rendering.

        Returns:
            List of VisionAnalysisResult for each analyzed page.
        """
        if not PYMUPDF_AVAILABLE:
            return []

        results = []
        doc = fitz.open(pdf_path)

        try:
            page_nums = pages or list(range(1, len(doc) + 1))

            for page_num in page_nums:
                if page_num < 1 or page_num > len(doc):
                    continue

                # Render page to image
                page_image = self._render_page(doc, page_num - 1, dpi)
                if not page_image:
                    continue

                # Analyze page
                result = self.analyze_page(page_image, page_num)
                results.append(result)

        finally:
            doc.close()

        return results

    def _render_page(
        self,
        doc: "fitz.Document",
        page_idx: int,
        dpi: int = 150,
    ) -> bytes | None:
        """Render a PDF page to PNG image bytes."""
        if not PYMUPDF_AVAILABLE:
            return None

        try:
            page = doc[page_idx]
            mat = fitz.Matrix(dpi / 72, dpi / 72)
            pix = page.get_pixmap(matrix=mat)

            # Convert to PNG bytes
            return pix.tobytes("png")
        except Exception:
            return None

    def _build_analysis_prompt(self, context: str = "") -> str:
        """Build the prompt for page analysis."""
        base_prompt = """Analyze this PDF page image and provide:

1. A detailed description of the visual content (text, diagrams, charts, images, tables)
2. A list of key elements detected (e.g., "bar chart", "flowchart", "photograph", "table", "equation")

Format your response as:
DESCRIPTION:
[Your detailed description here]

ELEMENTS:
- [element 1]
- [element 2]
- [etc.]

Focus on:
- Any diagrams, flowcharts, or visual representations
- Charts and graphs (describe what they show)
- Images and photographs (describe content)
- Tables (describe structure and content)
- Mathematical equations or formulas
- Any text that appears in images or diagrams"""

        if context:
            base_prompt = f"Document context: {context}\n\n{base_prompt}"

        return base_prompt

    def _parse_analysis_response(
        self,
        content: str,
    ) -> tuple[str, list[str]]:
        """Parse the vision model's response into description and elements."""
        description = ""
        elements: list[str] = []

        # Split by DESCRIPTION: and ELEMENTS:
        parts = content.split("ELEMENTS:")
        if len(parts) >= 2:
            desc_part = parts[0]
            elem_part = parts[1]

            # Extract description
            if "DESCRIPTION:" in desc_part:
                description = desc_part.split("DESCRIPTION:")[1].strip()
            else:
                description = desc_part.strip()

            # Extract elements
            for line in elem_part.strip().split("\n"):
                line = line.strip()
                if line.startswith("-"):
                    elements.append(line[1:].strip())
                elif line:
                    elements.append(line)
        else:
            # Fallback: use entire content as description
            description = content.strip()

        return description, elements

    def close(self) -> None:
        """Close HTTP client."""
        if self._client:
            self._client.close()
            self._client = None

    def __enter__(self) -> "PDFVisionClient":
        """Context manager entry."""
        return self

    def __exit__(self, *args: Any) -> None:
        """Context manager exit."""
        self.close()


def analyze_complex_page(
    page_image: bytes,
    page_num: int,
    api_key: str | None = None,
) -> VisionAnalysisResult:
    """
    Convenience function to analyze a single page image.

    Args:
        page_image: PNG/JPEG image bytes.
        page_num: Page number (1-indexed).
        api_key: Optional API key (uses env var if not provided).

    Returns:
        VisionAnalysisResult with analysis.
    """
    with PDFVisionClient(api_key=api_key) as client:
        return client.analyze_page(page_image, page_num)
