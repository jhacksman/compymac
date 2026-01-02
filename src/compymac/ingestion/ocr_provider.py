"""
OCR Provider - Vision-based OCR using OpenAI-compatible APIs.

Simple design:
- Read config from env vars (OCR_BASE_URL, OCR_MODEL, OCR_PROMPT, LLM_API_KEY)
- Send image to vision model with OCR prompt
- Return extracted text

Supports any OpenAI-compatible vision API:
- Venice.ai (default, Gemma 3 27B)
- vLLM with olmOCR-2, DeepSeek-OCR, Qwen2.5-VL
- Any other compatible endpoint
"""

import base64
import os
import re
import time
from dataclasses import dataclass
from typing import Any

import httpx


# Default OCR prompt - works well with most vision models
DEFAULT_OCR_PROMPT = """You are an OCR system. Transcribe ALL text visible in this image exactly as it appears.

Rules:
- Extract all text preserving structure (paragraphs, lists, headers)
- For tables, use markdown format
- For equations, use LaTeX notation
- If text is unclear, mark as [unclear]
- If no text exists, respond: [NO TEXT]
- Do NOT describe the image - only transcribe text

Output the text directly:"""


@dataclass
class OCRResult:
    """Result from OCR analysis of a page."""
    page_num: int
    text: str
    confidence: float
    model_used: str
    processing_time_ms: float

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "page_num": self.page_num,
            "text": self.text,
            "confidence": self.confidence,
            "model_used": self.model_used,
            "processing_time_ms": self.processing_time_ms,
        }


def _strip_yaml_frontmatter(text: str) -> str:
    """
    Strip YAML front-matter from olmOCR-style output.
    
    olmOCR-2 returns output like:
    ---
    primary_language: en
    is_rotation_valid: True
    ...
    ---
    Actual text content here
    
    This function strips the YAML header and returns just the text.
    """
    if not text.startswith("---"):
        return text
    
    # Find the closing ---
    match = re.match(r'^---\n.*?\n---\n?', text, re.DOTALL)
    if match:
        return text[match.end():].strip()
    
    return text


class OCRClient:
    """
    OCR client using vision-language models.
    
    Configuration via environment variables:
        OCR_BASE_URL: API base URL (default: uses LLM_BASE_URL or Venice.ai)
        OCR_MODEL: Model to use (default: google-gemma-3-27b-it)
        OCR_PROMPT: Custom OCR prompt (optional, uses default if not set)
        LLM_API_KEY: API key for authentication
    """

    # Defaults for Venice.ai with Gemma 3 27B
    DEFAULT_BASE_URL = "https://api.venice.ai/api/v1"
    DEFAULT_MODEL = "google-gemma-3-27b-it"

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        api_key: str | None = None,
        prompt: str | None = None,
        timeout: float = 120.0,
    ):
        """
        Initialize OCR client.

        Args:
            base_url: API base URL. Reads from OCR_BASE_URL, then LLM_BASE_URL, then Venice default.
            model: Model to use. Reads from OCR_MODEL or uses Gemma 3 default.
            api_key: API key. Reads from LLM_API_KEY env var.
            prompt: OCR prompt. Reads from OCR_PROMPT or uses default.
            timeout: Request timeout in seconds.
        """
        self.base_url = (
            base_url 
            or os.environ.get("OCR_BASE_URL")
            or os.environ.get("LLM_BASE_URL")
            or self.DEFAULT_BASE_URL
        ).rstrip("/")
        
        self.model = (
            model 
            or os.environ.get("OCR_MODEL") 
            or self.DEFAULT_MODEL
        )
        
        self.api_key = (
            api_key 
            or os.environ.get("LLM_API_KEY") 
            or os.environ.get("OPENAI_API_KEY", "")
        )
        
        self.prompt = (
            prompt
            or os.environ.get("OCR_PROMPT")
            or DEFAULT_OCR_PROMPT
        )
        
        self.timeout = timeout
        self._client: httpx.Client | None = None

    @property
    def client(self) -> httpx.Client:
        """Get or create HTTP client."""
        if self._client is None:
            headers = {"Content-Type": "application/json"}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            self._client = httpx.Client(timeout=self.timeout, headers=headers)
        return self._client

    def ocr_page(self, image_bytes: bytes, page_num: int = 1) -> OCRResult:
        """
        Perform OCR on a page image.

        Args:
            image_bytes: PNG/JPEG image bytes.
            page_num: Page number (1-indexed).

        Returns:
            OCRResult with extracted text.
        """
        start_time = time.time()

        # Encode image
        image_b64 = base64.b64encode(image_bytes).decode()
        image_type = "image/jpeg" if image_bytes[:2] == b"\xff\xd8" else "image/png"

        payload = {
            "model": self.model,
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "text", "text": self.prompt},
                    {"type": "image_url", "image_url": {"url": f"data:{image_type};base64,{image_b64}"}},
                ],
            }],
            "max_tokens": 4096,
            "temperature": 0.0,
        }

        try:
            response = self.client.post(f"{self.base_url}/chat/completions", json=payload)
            response.raise_for_status()
            data = response.json()
            
            text = data["choices"][0]["message"]["content"].strip()
            
            # Strip YAML front-matter from olmOCR-style output
            text = _strip_yaml_frontmatter(text)
            
            # Clean up common wrapper patterns
            if text.startswith("```") and text.endswith("```"):
                lines = text.split("\n")
                text = "\n".join(lines[1:-1]) if len(lines) > 2 else text
            
            processing_time = (time.time() - start_time) * 1000
            
            return OCRResult(
                page_num=page_num,
                text=text,
                confidence=0.9 if text and text != "[NO TEXT]" else 0.0,
                model_used=self.model,
                processing_time_ms=processing_time,
            )

        except Exception as e:
            processing_time = (time.time() - start_time) * 1000
            return OCRResult(
                page_num=page_num,
                text=f"[OCR failed: {e}]",
                confidence=0.0,
                model_used=self.model,
                processing_time_ms=processing_time,
            )

    def close(self) -> None:
        """Close HTTP client."""
        if self._client:
            self._client.close()
            self._client = None

    def __enter__(self) -> "OCRClient":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()


# Simple function for one-off OCR
def ocr_image(image_bytes: bytes, page_num: int = 1) -> OCRResult:
    """
    OCR a single image using default configuration.
    
    Args:
        image_bytes: PNG/JPEG image bytes.
        page_num: Page number (1-indexed).
    
    Returns:
        OCRResult with extracted text.
    """
    with OCRClient() as client:
        return client.ocr_page(image_bytes, page_num)
