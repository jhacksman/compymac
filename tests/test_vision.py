"""
Tests for Vision Model Integration (Gap 5).

Tests cover:
- BoundingBox dataclass and methods
- VisualElement dataclass and serialization
- VisionParseResult and element lookup
- VisionClient with mocked API responses
- VisionBrowserTools for harness integration
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from compymac.vision import (
    BoundingBox,
    VisionBrowserTools,
    VisionClient,
    VisionParseResult,
    VisualElement,
)


class TestBoundingBox:
    """Tests for BoundingBox dataclass."""

    def test_center_calculation(self) -> None:
        """Test center point calculation."""
        bbox = BoundingBox(x=100, y=200, width=50, height=30)
        assert bbox.center == (125, 215)

    def test_area_calculation(self) -> None:
        """Test area calculation."""
        bbox = BoundingBox(x=0, y=0, width=100, height=50)
        assert bbox.area == 5000

    def test_contains_point_inside(self) -> None:
        """Test point containment - inside."""
        bbox = BoundingBox(x=10, y=10, width=100, height=100)
        assert bbox.contains_point(50, 50) is True
        assert bbox.contains_point(10, 10) is True  # Edge
        assert bbox.contains_point(110, 110) is True  # Edge

    def test_contains_point_outside(self) -> None:
        """Test point containment - outside."""
        bbox = BoundingBox(x=10, y=10, width=100, height=100)
        assert bbox.contains_point(5, 50) is False
        assert bbox.contains_point(50, 5) is False
        assert bbox.contains_point(200, 200) is False

    def test_overlaps_true(self) -> None:
        """Test overlapping bounding boxes."""
        bbox1 = BoundingBox(x=0, y=0, width=100, height=100)
        bbox2 = BoundingBox(x=50, y=50, width=100, height=100)
        assert bbox1.overlaps(bbox2) is True
        assert bbox2.overlaps(bbox1) is True

    def test_overlaps_false(self) -> None:
        """Test non-overlapping bounding boxes."""
        bbox1 = BoundingBox(x=0, y=0, width=50, height=50)
        bbox2 = BoundingBox(x=100, y=100, width=50, height=50)
        assert bbox1.overlaps(bbox2) is False
        assert bbox2.overlaps(bbox1) is False

    def test_to_dict(self) -> None:
        """Test dictionary conversion."""
        bbox = BoundingBox(x=10, y=20, width=30, height=40)
        assert bbox.to_dict() == {"x": 10, "y": 20, "width": 30, "height": 40}

    def test_from_dict(self) -> None:
        """Test creation from dictionary."""
        data = {"x": 10, "y": 20, "width": 30, "height": 40}
        bbox = BoundingBox.from_dict(data)
        assert bbox.x == 10
        assert bbox.y == 20
        assert bbox.width == 30
        assert bbox.height == 40


class TestVisualElement:
    """Tests for VisualElement dataclass."""

    def test_creation(self) -> None:
        """Test element creation."""
        bbox = BoundingBox(x=100, y=200, width=50, height=30)
        elem = VisualElement(
            element_id="visual-0",
            element_type="button",
            description="Submit button",
            bounding_box=bbox,
            confidence=0.95,
        )
        assert elem.element_id == "visual-0"
        assert elem.element_type == "button"
        assert elem.description == "Submit button"
        assert elem.confidence == 0.95

    def test_to_dict(self) -> None:
        """Test dictionary conversion."""
        bbox = BoundingBox(x=100, y=200, width=50, height=30)
        elem = VisualElement(
            element_id="visual-0",
            element_type="button",
            description="Submit button",
            bounding_box=bbox,
            confidence=0.95,
            screenshot_region=b"test",
        )
        data = elem.to_dict()
        assert data["element_id"] == "visual-0"
        assert data["element_type"] == "button"
        assert data["description"] == "Submit button"
        assert data["confidence"] == 0.95
        assert data["bounding_box"] == {"x": 100, "y": 200, "width": 50, "height": 30}

    def test_from_dict(self) -> None:
        """Test creation from dictionary."""
        data = {
            "element_id": "visual-1",
            "element_type": "input",
            "description": "Email input field",
            "bounding_box": {"x": 50, "y": 100, "width": 200, "height": 40},
            "confidence": 0.88,
            "screenshot_region_base64": "",
        }
        elem = VisualElement.from_dict(data)
        assert elem.element_id == "visual-1"
        assert elem.element_type == "input"
        assert elem.description == "Email input field"
        assert elem.confidence == 0.88
        assert elem.bounding_box.x == 50

    def test_serialization_roundtrip(self) -> None:
        """Test serialization roundtrip."""
        bbox = BoundingBox(x=100, y=200, width=50, height=30)
        original = VisualElement(
            element_id="visual-0",
            element_type="button",
            description="Submit button",
            bounding_box=bbox,
            confidence=0.95,
            screenshot_region=b"test_image_data",
        )
        data = original.to_dict()
        restored = VisualElement.from_dict(data)
        assert restored.element_id == original.element_id
        assert restored.element_type == original.element_type
        assert restored.description == original.description
        assert restored.confidence == original.confidence
        assert restored.screenshot_region == original.screenshot_region


class TestVisionParseResult:
    """Tests for VisionParseResult dataclass."""

    def test_get_element_by_id(self) -> None:
        """Test element lookup by ID."""
        elements = [
            VisualElement(
                element_id="visual-0",
                element_type="button",
                description="Submit",
                bounding_box=BoundingBox(x=0, y=0, width=100, height=50),
                confidence=0.9,
            ),
            VisualElement(
                element_id="visual-1",
                element_type="input",
                description="Email",
                bounding_box=BoundingBox(x=0, y=60, width=200, height=40),
                confidence=0.85,
            ),
        ]
        result = VisionParseResult(
            elements=elements,
            screenshot_width=1920,
            screenshot_height=1080,
            parse_time_ms=150.0,
        )

        elem = result.get_element_by_id("visual-1")
        assert elem is not None
        assert elem.element_type == "input"

        assert result.get_element_by_id("visual-99") is None

    def test_get_elements_by_type(self) -> None:
        """Test element lookup by type."""
        elements = [
            VisualElement(
                element_id="visual-0",
                element_type="button",
                description="Submit",
                bounding_box=BoundingBox(x=0, y=0, width=100, height=50),
                confidence=0.9,
            ),
            VisualElement(
                element_id="visual-1",
                element_type="button",
                description="Cancel",
                bounding_box=BoundingBox(x=110, y=0, width=100, height=50),
                confidence=0.88,
            ),
            VisualElement(
                element_id="visual-2",
                element_type="input",
                description="Email",
                bounding_box=BoundingBox(x=0, y=60, width=200, height=40),
                confidence=0.85,
            ),
        ]
        result = VisionParseResult(
            elements=elements,
            screenshot_width=1920,
            screenshot_height=1080,
            parse_time_ms=150.0,
        )

        buttons = result.get_elements_by_type("button")
        assert len(buttons) == 2

        inputs = result.get_elements_by_type("input")
        assert len(inputs) == 1

        links = result.get_elements_by_type("link")
        assert len(links) == 0

    def test_get_element_at_point(self) -> None:
        """Test element lookup by coordinates."""
        elements = [
            VisualElement(
                element_id="visual-0",
                element_type="button",
                description="Submit",
                bounding_box=BoundingBox(x=100, y=100, width=100, height=50),
                confidence=0.9,
            ),
        ]
        result = VisionParseResult(
            elements=elements,
            screenshot_width=1920,
            screenshot_height=1080,
            parse_time_ms=150.0,
        )

        elem = result.get_element_at_point(150, 125)
        assert elem is not None
        assert elem.element_id == "visual-0"

        assert result.get_element_at_point(50, 50) is None

    def test_to_dict(self) -> None:
        """Test dictionary conversion."""
        elements = [
            VisualElement(
                element_id="visual-0",
                element_type="button",
                description="Submit",
                bounding_box=BoundingBox(x=0, y=0, width=100, height=50),
                confidence=0.9,
            ),
        ]
        result = VisionParseResult(
            elements=elements,
            screenshot_width=1920,
            screenshot_height=1080,
            parse_time_ms=150.0,
        )
        data = result.to_dict()
        assert data["screenshot_width"] == 1920
        assert data["screenshot_height"] == 1080
        assert data["parse_time_ms"] == 150.0
        assert len(data["elements"]) == 1


class TestVisionClient:
    """Tests for VisionClient."""

    def test_initialization_with_env_var(self) -> None:
        """Test client initialization with environment variable."""
        with patch.dict("os.environ", {"VENICE_API_KEY": "test-key"}):
            client = VisionClient()
            assert client.api_key == "test-key"
            assert client.model == "omniparser-v2"

    def test_initialization_with_explicit_key(self) -> None:
        """Test client initialization with explicit API key."""
        client = VisionClient(api_key="explicit-key")
        assert client.api_key == "explicit-key"

    def test_parse_screenshot_api_error(self) -> None:
        """Test parse_screenshot handles API errors gracefully."""
        client = VisionClient(api_key="test-key")

        # Mock the HTTP client to raise an error
        mock_http_client = MagicMock()
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = Exception("API Error")
        mock_http_client.post.return_value = mock_response

        # Set the internal _client directly
        client._client = mock_http_client

        # Create a minimal PNG image
        png_bytes = self._create_minimal_png()
        result = client.parse_screenshot(png_bytes)

        # Should return empty result on error
        assert len(result.elements) == 0
        assert result.parse_time_ms > 0

    def test_parse_screenshot_success(self) -> None:
        """Test successful screenshot parsing."""
        client = VisionClient(api_key="test-key")

        # Mock successful API response
        mock_http_client = MagicMock()
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "detections": [
                {
                    "type": "button",
                    "description": "Submit button",
                    "bbox": {"x": 100, "y": 200, "width": 80, "height": 30},
                    "confidence": 0.95,
                },
                {
                    "type": "input",
                    "description": "Email input field",
                    "bbox": {"x": 100, "y": 100, "width": 200, "height": 40},
                    "confidence": 0.88,
                },
            ]
        }
        mock_http_client.post.return_value = mock_response

        # Set the internal _client directly
        client._client = mock_http_client

        png_bytes = self._create_minimal_png()
        result = client.parse_screenshot(png_bytes)

        assert len(result.elements) == 2
        assert result.elements[0].element_type == "button"
        assert result.elements[0].description == "Submit button"
        assert result.elements[1].element_type == "input"

    def test_find_element_by_description(self) -> None:
        """Test finding element by description."""
        client = VisionClient(api_key="test-key")

        # Mock API response
        mock_http_client = MagicMock()
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "detections": [
                {
                    "type": "button",
                    "description": "Submit form button",
                    "bbox": {"x": 100, "y": 200, "width": 80, "height": 30},
                    "confidence": 0.95,
                },
                {
                    "type": "button",
                    "description": "Cancel button",
                    "bbox": {"x": 200, "y": 200, "width": 80, "height": 30},
                    "confidence": 0.90,
                },
            ]
        }
        mock_http_client.post.return_value = mock_response

        # Set the internal _client directly
        client._client = mock_http_client

        png_bytes = self._create_minimal_png()
        elem = client.find_element_by_description(png_bytes, "submit")

        assert elem is not None
        assert "Submit" in elem.description

    def test_context_manager(self) -> None:
        """Test context manager usage."""
        with VisionClient(api_key="test-key") as client:
            assert client.api_key == "test-key"
        # Client should be closed after context

    def _create_minimal_png(self) -> bytes:
        """Create a minimal valid PNG image."""
        try:
            import io

            from PIL import Image

            img = Image.new("RGB", (100, 100), color="white")
            buffer = io.BytesIO()
            img.save(buffer, format="PNG")
            return buffer.getvalue()
        except ImportError:
            # Return minimal PNG header if PIL not available
            return (
                b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
                b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde"
            )


class TestVisionBrowserTools:
    """Tests for VisionBrowserTools."""

    def test_browser_visual_search_file_not_found(self) -> None:
        """Test visual search with missing file."""
        tools = VisionBrowserTools()
        result = tools.browser_visual_search("/nonexistent/path.png", "button")
        data = json.loads(result)
        assert "error" in data
        assert "Failed to read screenshot" in data["error"]

    def test_browser_visual_parse_file_not_found(self) -> None:
        """Test visual parse with missing file."""
        tools = VisionBrowserTools()
        result = tools.browser_visual_parse("/nonexistent/path.png")
        data = json.loads(result)
        assert "error" in data
        assert "Failed to read screenshot" in data["error"]

    def test_browser_visual_search_success(self, tmp_path) -> None:
        """Test successful visual search."""
        # Create a test image
        try:
            from PIL import Image

            img = Image.new("RGB", (100, 100), color="white")
            img_path = tmp_path / "test.png"
            img.save(img_path, format="PNG")
        except ImportError:
            pytest.skip("PIL not available")

        # Mock the vision client
        mock_client = MagicMock()
        mock_element = VisualElement(
            element_id="visual-0",
            element_type="button",
            description="Submit button",
            bounding_box=BoundingBox(x=10, y=20, width=80, height=30),
            confidence=0.95,
        )
        mock_client.find_element_by_description.return_value = mock_element

        tools = VisionBrowserTools(vision_client=mock_client)
        result = tools.browser_visual_search(str(img_path), "submit")
        data = json.loads(result)

        assert data["element_id"] == "visual-0"
        assert data["element_type"] == "button"
        assert data["click_coordinates"] == [50, 35]

    def test_browser_visual_parse_success(self, tmp_path) -> None:
        """Test successful visual parse."""
        # Create a test image
        try:
            from PIL import Image

            img = Image.new("RGB", (200, 200), color="white")
            img_path = tmp_path / "test.png"
            img.save(img_path, format="PNG")
        except ImportError:
            pytest.skip("PIL not available")

        # Mock the vision client
        mock_client = MagicMock()
        mock_result = VisionParseResult(
            elements=[
                VisualElement(
                    element_id="visual-0",
                    element_type="button",
                    description="Submit",
                    bounding_box=BoundingBox(x=10, y=20, width=80, height=30),
                    confidence=0.95,
                ),
                VisualElement(
                    element_id="visual-1",
                    element_type="input",
                    description="Email",
                    bounding_box=BoundingBox(x=10, y=60, width=180, height=40),
                    confidence=0.88,
                ),
            ],
            screenshot_width=200,
            screenshot_height=200,
            parse_time_ms=100.0,
        )
        mock_client.parse_screenshot.return_value = mock_result

        tools = VisionBrowserTools(vision_client=mock_client)
        result = tools.browser_visual_parse(str(img_path))
        data = json.loads(result)

        assert data["element_count"] == 2
        assert data["screenshot_size"]["width"] == 200
        assert len(data["elements"]) == 2

    def test_get_click_coordinates(self, tmp_path) -> None:
        """Test getting click coordinates for element."""
        # Create a test image
        try:
            from PIL import Image

            img = Image.new("RGB", (100, 100), color="white")
            img_path = tmp_path / "test.png"
            img.save(img_path, format="PNG")
        except ImportError:
            pytest.skip("PIL not available")

        # Mock the vision client
        mock_client = MagicMock()
        mock_result = VisionParseResult(
            elements=[
                VisualElement(
                    element_id="visual-0",
                    element_type="button",
                    description="Submit",
                    bounding_box=BoundingBox(x=10, y=20, width=80, height=30),
                    confidence=0.95,
                ),
            ],
            screenshot_width=100,
            screenshot_height=100,
            parse_time_ms=50.0,
        )
        mock_result.get_element_by_id = lambda eid: (
            mock_result.elements[0] if eid == "visual-0" else None
        )
        mock_client.parse_screenshot.return_value = mock_result

        tools = VisionBrowserTools(vision_client=mock_client)
        coords = tools.get_click_coordinates(str(img_path), "visual-0")

        assert coords == (50, 35)

    def test_get_click_coordinates_not_found(self, tmp_path) -> None:
        """Test getting click coordinates for missing element."""
        # Create a test image
        try:
            from PIL import Image

            img = Image.new("RGB", (100, 100), color="white")
            img_path = tmp_path / "test.png"
            img.save(img_path, format="PNG")
        except ImportError:
            pytest.skip("PIL not available")

        # Mock the vision client
        mock_client = MagicMock()
        mock_result = VisionParseResult(
            elements=[],
            screenshot_width=100,
            screenshot_height=100,
            parse_time_ms=50.0,
        )
        mock_client.parse_screenshot.return_value = mock_result

        tools = VisionBrowserTools(vision_client=mock_client)
        coords = tools.get_click_coordinates(str(img_path), "visual-99")

        assert coords is None
