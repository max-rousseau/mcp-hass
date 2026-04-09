"""
Test suite for camera snapshot image downsampling functionality.

Tests the intelligent image processing logic including aspect ratio preservation,
LANCZOS resampling, and conditional downsampling based on image dimensions.
"""

import json
import pytest
import uuid
import base64
import io
from unittest.mock import AsyncMock, Mock, patch
from PIL import Image

from src.mcp_hass.server import MCPHomeAssistantServer
from src.mcp_hass.ha_client.client import HomeAssistantClient
from src.mcp_hass.tools import ToolContext, register_camera_tools
from src.mcp_hass.config import ConfigurationManager


def create_mock_tool_decorator():
    """Create a mock decorator for @mcp.tool that tracks registered functions."""
    registered_tools = {}

    def mock_decorator(*args, **kwargs):
        if args and callable(args[0]):
            func = args[0]
            registered_tools[func.__name__] = func
            return func

        def decorator(func):
            registered_tools[func.__name__] = func
            return func

        return decorator

    return mock_decorator, registered_tools


def create_test_image(width: int, height: int) -> bytes:
    """Create a test JPEG image with specified dimensions."""
    image = Image.new("RGB", (width, height), color="red")
    output_buffer = io.BytesIO()
    image.save(output_buffer, format="JPEG", quality=85)
    return output_buffer.getvalue()


@pytest.fixture
def mock_ha_client():
    """Mock HomeAssistantClient for downsampling testing."""
    client = Mock(spec=HomeAssistantClient)
    client.validate_entity_id = Mock(return_value=True)
    client.call_service = AsyncMock()
    client.connect = AsyncMock()
    client.session = Mock()
    client.base_url = "http://homeassistant.local:8123"
    return client


@pytest.fixture
def server_with_camera_tools(mock_ha_client):
    """Create server instance with camera tools registered."""
    server = MCPHomeAssistantServer()
    server.ha_client = mock_ha_client
    mock_decorator, registered_tools = create_mock_tool_decorator()
    server.mcp = Mock()
    server.mcp.tool = Mock(side_effect=mock_decorator)
    server.mcp._test_tools = registered_tools
    server.logger = Mock()

    # Mock config
    mock_config = Mock(spec=ConfigurationManager)
    mock_config.get_tool_token_limit.return_value = 100000
    server.config = mock_config

    # Create ToolContext with the same mock logger for test assertions
    ctx = ToolContext(
        mcp=server.mcp,
        ha_client=mock_ha_client,
        config=mock_config,
        logger=server.logger,  # Use the mock logger for test assertions
    )
    register_camera_tools(ctx)

    return server


class TestCameraDownsampling:
    """Test cases for image downsampling functionality."""

    @pytest.mark.asyncio
    async def test_4k_image_downsampled_correctly(self, server_with_camera_tools):
        """Test that 4K images are properly downsampled while preserving aspect ratio."""
        entity_id = "camera.4k_camera"

        # Create a 4K image (3840x2160)
        original_image_data = create_test_image(3840, 2160)

        # Mock HTTP response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.read = AsyncMock(return_value=original_image_data)

        mock_session_get = AsyncMock()
        mock_session_get.__aenter__ = AsyncMock(return_value=mock_response)
        mock_session_get.__aexit__ = AsyncMock(return_value=None)
        server_with_camera_tools.ha_client.session.get = Mock(
            return_value=mock_session_get
        )

        camera_tool_func = server_with_camera_tools.mcp._test_tools[
            "get_camera_snapshot"
        ]

        # Execute the tool
        with patch(
            "uuid.uuid4", return_value=uuid.UUID("12345678-1234-5678-9012-123456789abc")
        ):
            with patch("asyncio.sleep", return_value=None):
                result_json = await camera_tool_func(entity_id)

        result = json.loads(result_json)

        # Verify downsampling occurred
        assert result["success"] is True
        assert result["original_size"] == "3840x2160"
        assert result["final_size"] == "1024x576"  # Aspect ratio preserved (16:9)
        assert result["downsampled"] is True

        # Verify the image data is different (downsampled)
        downsampled_data = base64.b64decode(result["image_base64"])
        assert len(downsampled_data) < len(original_image_data)

    @pytest.mark.asyncio
    async def test_small_image_not_downsampled(self, server_with_camera_tools):
        """Test that images smaller than 1024px are not downsampled."""
        entity_id = "camera.small_camera"

        # Create a small image (800x600)
        original_image_data = create_test_image(800, 600)

        # Mock HTTP response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.read = AsyncMock(return_value=original_image_data)

        mock_session_get = AsyncMock()
        mock_session_get.__aenter__ = AsyncMock(return_value=mock_response)
        mock_session_get.__aexit__ = AsyncMock(return_value=None)
        server_with_camera_tools.ha_client.session.get = Mock(
            return_value=mock_session_get
        )

        camera_tool_func = server_with_camera_tools.mcp._test_tools[
            "get_camera_snapshot"
        ]

        # Execute the tool
        with patch(
            "uuid.uuid4", return_value=uuid.UUID("12345678-1234-5678-9012-123456789abc")
        ):
            with patch("asyncio.sleep", return_value=None):
                result_json = await camera_tool_func(entity_id)

        result = json.loads(result_json)

        # Verify no downsampling occurred
        assert result["success"] is True
        assert result["original_size"] == "800x600"
        assert result["final_size"] == "800x600"
        assert result["downsampled"] is False

        # Verify the image data is identical
        returned_data = base64.b64decode(result["image_base64"])
        assert len(returned_data) == len(original_image_data)

    @pytest.mark.asyncio
    async def test_portrait_image_aspect_preservation(self, server_with_camera_tools):
        """Test aspect ratio preservation for portrait orientation images."""
        entity_id = "camera.portrait_camera"

        # Create a portrait image (1200x1600)
        original_image_data = create_test_image(1200, 1600)

        # Mock HTTP response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.read = AsyncMock(return_value=original_image_data)

        mock_session_get = AsyncMock()
        mock_session_get.__aenter__ = AsyncMock(return_value=mock_response)
        mock_session_get.__aexit__ = AsyncMock(return_value=None)
        server_with_camera_tools.ha_client.session.get = Mock(
            return_value=mock_session_get
        )

        camera_tool_func = server_with_camera_tools.mcp._test_tools[
            "get_camera_snapshot"
        ]

        # Execute the tool
        with patch(
            "uuid.uuid4", return_value=uuid.UUID("12345678-1234-5678-9012-123456789abc")
        ):
            with patch("asyncio.sleep", return_value=None):
                result_json = await camera_tool_func(entity_id)

        result = json.loads(result_json)

        # Verify downsampling occurred with correct aspect ratio
        assert result["success"] is True
        assert result["original_size"] == "1200x1600"
        assert result["final_size"] == "768x1024"  # Aspect ratio preserved (3:4)
        assert result["downsampled"] is True

    @pytest.mark.asyncio
    async def test_square_image_downsampling(self, server_with_camera_tools):
        """Test downsampling of square images."""
        entity_id = "camera.square_camera"

        # Create a square image (2000x2000)
        original_image_data = create_test_image(2000, 2000)

        # Mock HTTP response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.read = AsyncMock(return_value=original_image_data)

        mock_session_get = AsyncMock()
        mock_session_get.__aenter__ = AsyncMock(return_value=mock_response)
        mock_session_get.__aexit__ = AsyncMock(return_value=None)
        server_with_camera_tools.ha_client.session.get = Mock(
            return_value=mock_session_get
        )

        camera_tool_func = server_with_camera_tools.mcp._test_tools[
            "get_camera_snapshot"
        ]

        # Execute the tool
        with patch(
            "uuid.uuid4", return_value=uuid.UUID("12345678-1234-5678-9012-123456789abc")
        ):
            with patch("asyncio.sleep", return_value=None):
                result_json = await camera_tool_func(entity_id)

        result = json.loads(result_json)

        # Verify downsampling to perfect square
        assert result["success"] is True
        assert result["original_size"] == "2000x2000"
        assert result["final_size"] == "1024x1024"
        assert result["downsampled"] is True

    @pytest.mark.asyncio
    async def test_image_processing_failure_fallback(self, server_with_camera_tools):
        """Test graceful fallback when image processing fails."""
        entity_id = "camera.test_camera"

        # Create corrupted image data
        corrupted_image_data = b"not_a_valid_jpeg_image"

        # Mock HTTP response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.read = AsyncMock(return_value=corrupted_image_data)

        mock_session_get = AsyncMock()
        mock_session_get.__aenter__ = AsyncMock(return_value=mock_response)
        mock_session_get.__aexit__ = AsyncMock(return_value=None)
        server_with_camera_tools.ha_client.session.get = Mock(
            return_value=mock_session_get
        )

        camera_tool_func = server_with_camera_tools.mcp._test_tools[
            "get_camera_snapshot"
        ]

        # Execute the tool
        with patch(
            "uuid.uuid4", return_value=uuid.UUID("12345678-1234-5678-9012-123456789abc")
        ):
            with patch("asyncio.sleep", return_value=None):
                result_json = await camera_tool_func(entity_id)

        result = json.loads(result_json)

        # Verify fallback to original data
        assert result["success"] is True
        assert result["original_size"] == "unknown"
        assert result["final_size"] == "unknown"
        assert result["downsampled"] is False

        # Verify original corrupted data is returned
        returned_data = base64.b64decode(result["image_base64"])
        assert returned_data == corrupted_image_data

        # Verify warning was logged
        server_with_camera_tools.logger.warning.assert_called()
        warning_call = server_with_camera_tools.logger.warning.call_args[0][0]
        assert "Failed to process image for downsampling" in warning_call

    @pytest.mark.asyncio
    async def test_exactly_1024px_boundary_conditions(self, server_with_camera_tools):
        """Test boundary condition where image is exactly 1024px in one dimension."""
        entity_id = "camera.boundary_camera"

        # Create image exactly at threshold (1024x768)
        original_image_data = create_test_image(1024, 768)

        # Mock HTTP response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.read = AsyncMock(return_value=original_image_data)

        mock_session_get = AsyncMock()
        mock_session_get.__aenter__ = AsyncMock(return_value=mock_response)
        mock_session_get.__aexit__ = AsyncMock(return_value=None)
        server_with_camera_tools.ha_client.session.get = Mock(
            return_value=mock_session_get
        )

        camera_tool_func = server_with_camera_tools.mcp._test_tools[
            "get_camera_snapshot"
        ]

        # Execute the tool
        with patch(
            "uuid.uuid4", return_value=uuid.UUID("12345678-1234-5678-9012-123456789abc")
        ):
            with patch("asyncio.sleep", return_value=None):
                result_json = await camera_tool_func(entity_id)

        result = json.loads(result_json)

        # Image should NOT be downsampled since neither dimension exceeds 1024
        assert result["success"] is True
        assert result["original_size"] == "1024x768"
        assert result["final_size"] == "1024x768"
        assert result["downsampled"] is False
