"""
Vision Model Integration - OmniParser V2 via Venice.ai

This module provides vision-based UI element detection for browser automation,
enabling interaction with elements that can't be accessed via DOM parsing
(Canvas, Shadow DOM, dynamic SPAs).

Gap 5 from docs/real-gaps-implementation-plans.md

The project uses Venice.ai API for vision model hosting. OmniParser V2 is
accessed as an external service rather than running locally.
"""

from __future__ import annotations

import base64
import io
import os
from dataclasses import dataclass, field
from typing import Any

import httpx


@dataclass
class BoundingBox:
    """Bounding box coordinates for a detected element."""

    x: int  # Top-left X
    y: int  # Top-left Y
    width: int
    height: int

    @property
    def center(self) -> tuple[int, int]:
        """Get center coordinates for clicking."""
        return (self.x + self.width // 2, self.y + self.height // 2)

    @property
    def area(self) -> int:
        """Get area of bounding box."""
        return self.width * self.height

    def contains_point(self, x: int, y: int) -> bool:
        """Check if point is within bounding box."""
        return self.x <= x <= self.x + self.width and self.y <= y <= self.y + self.height

    def overlaps(self, other: BoundingBox) -> bool:
        """Check if this bounding box overlaps with another."""
        return not (
            self.x + self.width < other.x
            or other.x + other.width < self.x
            or self.y + self.height < other.y
            or other.y + other.height < self.y
        )

    def to_dict(self) -> dict[str, int]:
        """Convert to dictionary."""
        return {"x": self.x, "y": self.y, "width": self.width, "height": self.height}

    @classmethod
    def from_dict(cls, data: dict[str, int]) -> BoundingBox:
        """Create from dictionary."""
        return cls(x=data["x"], y=data["y"], width=data["width"], height=data["height"])


@dataclass
class VisualElement:
    """A UI element detected by vision model."""

    element_id: str  # Generated ID (e.g., "visual-0")
    element_type: str  # "button", "input", "link", "text", "icon", etc.
    description: str  # Natural language description from Florence-2
    bounding_box: BoundingBox  # Location on screen
    confidence: float  # Detection confidence (0-1)
    screenshot_region: bytes = field(default=b"", repr=False)  # Cropped image

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "element_id": self.element_id,
            "element_type": self.element_type,
            "description": self.description,
            "bounding_box": self.bounding_box.to_dict(),
            "confidence": self.confidence,
            "screenshot_region_base64": base64.b64encode(self.screenshot_region).decode()
            if self.screenshot_region
            else "",
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> VisualElement:
        """Create from dictionary."""
        screenshot_region = b""
        if data.get("screenshot_region_base64"):
            screenshot_region = base64.b64decode(data["screenshot_region_base64"])
        return cls(
            element_id=data["element_id"],
            element_type=data["element_type"],
            description=data["description"],
            bounding_box=BoundingBox.from_dict(data["bounding_box"]),
            confidence=data["confidence"],
            screenshot_region=screenshot_region,
        )


@dataclass
class VisionParseResult:
    """Result of parsing a screenshot with vision model."""

    elements: list[VisualElement]
    screenshot_width: int
    screenshot_height: int
    parse_time_ms: float
    model_used: str = "omniparser-v2"

    def get_element_by_id(self, element_id: str) -> VisualElement | None:
        """Get element by ID."""
        for elem in self.elements:
            if elem.element_id == element_id:
                return elem
        return None

    def get_elements_by_type(self, element_type: str) -> list[VisualElement]:
        """Get all elements of a specific type."""
        return [e for e in self.elements if e.element_type == element_type]

    def get_element_at_point(self, x: int, y: int) -> VisualElement | None:
        """Get element at specific coordinates."""
        for elem in self.elements:
            if elem.bounding_box.contains_point(x, y):
                return elem
        return None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "elements": [e.to_dict() for e in self.elements],
            "screenshot_width": self.screenshot_width,
            "screenshot_height": self.screenshot_height,
            "parse_time_ms": self.parse_time_ms,
            "model_used": self.model_used,
        }


class VisionClient:
    """
    Client for vision-based UI element detection via Venice.ai.

    Uses OmniParser V2 (YOLOv8 + Florence-2) for detecting and describing
    interactable UI elements in screenshots.
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = "https://api.venice.ai/api/v1",
        model: str = "omniparser-v2",
        timeout: float = 30.0,
    ):
        """
        Initialize vision client.

        Args:
            api_key: Venice.ai API key. If None, reads from VENICE_API_KEY env var.
            base_url: Base URL for Venice.ai API.
            model: Vision model to use (default: omniparser-v2).
            timeout: Request timeout in seconds.
        """
        self.api_key = api_key or os.environ.get("VENICE_API_KEY", "")
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
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

    def parse_screenshot(
        self,
        screenshot: bytes,
        detect_types: list[str] | None = None,
        min_confidence: float = 0.5,
    ) -> VisionParseResult:
        """
        Parse screenshot to detect UI elements.

        Args:
            screenshot: PNG/JPEG screenshot bytes.
            detect_types: Element types to detect. None = all types.
            min_confidence: Minimum confidence threshold (0-1).

        Returns:
            VisionParseResult with detected elements.
        """
        import time

        start_time = time.time()

        # Get image dimensions
        width, height = self._get_image_dimensions(screenshot)

        # Encode screenshot as base64
        screenshot_b64 = base64.b64encode(screenshot).decode()

        # Build request payload
        payload = {
            "model": self.model,
            "image": screenshot_b64,
            "options": {
                "min_confidence": min_confidence,
            },
        }
        if detect_types:
            payload["options"]["detect_types"] = detect_types

        # Make API request
        try:
            response = self.client.post(
                f"{self.base_url}/vision/parse",
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPStatusError:
            # Return empty result on API error
            return VisionParseResult(
                elements=[],
                screenshot_width=width,
                screenshot_height=height,
                parse_time_ms=(time.time() - start_time) * 1000,
                model_used=self.model,
            )
        except Exception:
            # Return empty result on any error
            return VisionParseResult(
                elements=[],
                screenshot_width=width,
                screenshot_height=height,
                parse_time_ms=(time.time() - start_time) * 1000,
                model_used=self.model,
            )

        # Parse detections
        elements = []
        detections = data.get("detections", [])
        for idx, detection in enumerate(detections):
            bbox_data = detection.get("bbox", {})
            bbox = BoundingBox(
                x=bbox_data.get("x", 0),
                y=bbox_data.get("y", 0),
                width=bbox_data.get("width", 0),
                height=bbox_data.get("height", 0),
            )

            # Crop screenshot region
            region = self._crop_image(screenshot, bbox)

            elements.append(
                VisualElement(
                    element_id=f"visual-{idx}",
                    element_type=detection.get("type", "unknown"),
                    description=detection.get("description", ""),
                    bounding_box=bbox,
                    confidence=detection.get("confidence", 0.0),
                    screenshot_region=region,
                )
            )

        parse_time = (time.time() - start_time) * 1000

        return VisionParseResult(
            elements=elements,
            screenshot_width=width,
            screenshot_height=height,
            parse_time_ms=parse_time,
            model_used=self.model,
        )

    def find_element_by_description(
        self,
        screenshot: bytes,
        description: str,
        element_type: str | None = None,
    ) -> VisualElement | None:
        """
        Find element matching a natural language description.

        Args:
            screenshot: Screenshot bytes.
            description: Natural language description to match.
            element_type: Optional element type filter.

        Returns:
            Best matching element or None.
        """
        result = self.parse_screenshot(screenshot)

        # Filter by type if specified
        candidates = result.elements
        if element_type:
            candidates = [e for e in candidates if e.element_type == element_type]

        if not candidates:
            return None

        # Simple matching: find element with description containing query
        description_lower = description.lower()
        for elem in candidates:
            if description_lower in elem.description.lower():
                return elem

        # If no exact match, return highest confidence element
        return max(candidates, key=lambda e: e.confidence)

    def _get_image_dimensions(self, image_bytes: bytes) -> tuple[int, int]:
        """Get image width and height."""
        try:
            from PIL import Image

            img = Image.open(io.BytesIO(image_bytes))
            return img.size
        except Exception:
            return (0, 0)

    def _crop_image(self, image_bytes: bytes, bbox: BoundingBox) -> bytes:
        """Crop image to bounding box."""
        try:
            from PIL import Image

            img = Image.open(io.BytesIO(image_bytes))
            cropped = img.crop(
                (bbox.x, bbox.y, bbox.x + bbox.width, bbox.y + bbox.height)
            )
            output = io.BytesIO()
            cropped.save(output, format="PNG")
            return output.getvalue()
        except Exception:
            return b""

    def close(self) -> None:
        """Close HTTP client."""
        if self._client:
            self._client.close()
            self._client = None

    def __enter__(self) -> VisionClient:
        """Context manager entry."""
        return self

    def __exit__(self, *args: Any) -> None:
        """Context manager exit."""
        self.close()


class VisionBrowserTools:
    """
    Vision-enhanced browser tools for LocalHarness.

    Provides tools that use vision model for element detection,
    enabling interaction with elements not accessible via DOM.
    """

    def __init__(self, vision_client: VisionClient | None = None):
        """
        Initialize vision browser tools.

        Args:
            vision_client: VisionClient instance. If None, creates default.
        """
        self.vision_client = vision_client or VisionClient()

    def browser_visual_search(
        self,
        screenshot_path: str,
        query: str,
        element_type: str | None = None,
    ) -> str:
        """
        Search for UI element by visual description.

        Args:
            screenshot_path: Path to screenshot file.
            query: Natural language description of element to find.
            element_type: Optional element type filter.

        Returns:
            JSON string with found element or error message.
        """
        import json
        from pathlib import Path

        try:
            screenshot = Path(screenshot_path).read_bytes()
        except Exception as e:
            return json.dumps({"error": f"Failed to read screenshot: {e}"})

        element = self.vision_client.find_element_by_description(
            screenshot, query, element_type
        )

        if element is None:
            return json.dumps({"error": f"No element found matching: {query}"})

        return json.dumps(
            {
                "element_id": element.element_id,
                "element_type": element.element_type,
                "description": element.description,
                "bounding_box": element.bounding_box.to_dict(),
                "confidence": element.confidence,
                "click_coordinates": element.bounding_box.center,
            }
        )

    def browser_visual_parse(
        self,
        screenshot_path: str,
        min_confidence: float = 0.5,
    ) -> str:
        """
        Parse screenshot to detect all UI elements.

        Args:
            screenshot_path: Path to screenshot file.
            min_confidence: Minimum confidence threshold.

        Returns:
            JSON string with all detected elements.
        """
        import json
        from pathlib import Path

        try:
            screenshot = Path(screenshot_path).read_bytes()
        except Exception as e:
            return json.dumps({"error": f"Failed to read screenshot: {e}"})

        result = self.vision_client.parse_screenshot(
            screenshot, min_confidence=min_confidence
        )

        return json.dumps(
            {
                "element_count": len(result.elements),
                "screenshot_size": {
                    "width": result.screenshot_width,
                    "height": result.screenshot_height,
                },
                "parse_time_ms": result.parse_time_ms,
                "elements": [
                    {
                        "element_id": e.element_id,
                        "element_type": e.element_type,
                        "description": e.description,
                        "bounding_box": e.bounding_box.to_dict(),
                        "confidence": e.confidence,
                        "click_coordinates": e.bounding_box.center,
                    }
                    for e in result.elements
                ],
            }
        )

    def get_click_coordinates(
        self,
        screenshot_path: str,
        element_id: str,
    ) -> tuple[int, int] | None:
        """
        Get click coordinates for a visual element.

        Args:
            screenshot_path: Path to screenshot file.
            element_id: Visual element ID (e.g., "visual-0").

        Returns:
            (x, y) coordinates or None if not found.
        """
        from pathlib import Path

        try:
            screenshot = Path(screenshot_path).read_bytes()
        except Exception:
            return None

        result = self.vision_client.parse_screenshot(screenshot)
        element = result.get_element_by_id(element_id)

        if element is None:
            return None

        return element.bounding_box.center
