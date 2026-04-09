"""
Test suite for camera snapshot tools.

Tests the camera snapshot capture functionality, including service calls,
HTTP retrieval, base64 encoding, and error handling scenarios.
"""

import logging

import json
import pytest
import uuid
import base64
from unittest.mock import AsyncMock, Mock, patch
from aiohttp import ClientSession

from src.mcp_hass.server import MCPHomeAssistantServer
from src.mcp_hass.ha_client.client import HomeAssistantClient
from src.mcp_hass.ha_client.exceptions import HomeAssistantAPIError
from src.mcp_hass.tools import ToolContext, register_camera_tools
from src.mcp_hass.config import ConfigurationManager


@pytest.fixture
def mock_ha_client():
    """Mock HomeAssistantClient for camera snapshot testing."""
    client = Mock(spec=HomeAssistantClient)
    client.validate_entity_id = Mock(return_value=True)
    client.call_service = AsyncMock()
    client.connect = AsyncMock()
    client.session = Mock(spec=ClientSession)
    client.base_url = "http://homeassistant.local:8123"
    return client


@pytest.fixture
def server_with_camera_tools(mock_ha_client):
    """Create server instance with camera tools registered."""
    server = MCPHomeAssistantServer()
    server.ha_client = mock_ha_client
    server.logger = Mock()

    # Mock config
    mock_config = Mock(spec=ConfigurationManager)
    mock_config.get_tool_token_limit.return_value = 100000
    server.config = mock_config

    # Storage for registered tools
    registered_tools = {}

    def mock_tool_decorator(*args, **kwargs):
        if args and callable(args[0]):
            func = args[0]
            registered_tools[func.__name__] = func
            return func

        def decorator(func):
            registered_tools[func.__name__] = func
            return func

        return decorator

    server.mcp = Mock()
    server.mcp.tool = Mock(side_effect=mock_tool_decorator)
    server.mcp._test_tools = registered_tools

    # Create ToolContext and register camera tools
    ctx = ToolContext(
        mcp=server.mcp,
        ha_client=mock_ha_client,
        config=mock_config,
        logger=logging.getLogger(__name__),
    )
    register_camera_tools(ctx)

    return server


class TestCameraSnapshotTool:
    """Test cases for the get_camera_snapshot tool."""

    @pytest.mark.asyncio
    async def test_get_camera_snapshot_success(self, server_with_camera_tools):
        """Test successful camera snapshot capture and retrieval."""
        # Setup
        entity_id = "camera.front_door"
        mock_image_data = b"fake_jpeg_data_here"
        expected_base64 = base64.b64encode(mock_image_data).decode("utf-8")

        # Mock HTTP response for image retrieval
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.read = AsyncMock(return_value=mock_image_data)

        # Mock session.get context manager
        mock_session_get = AsyncMock()
        mock_session_get.__aenter__ = AsyncMock(return_value=mock_response)
        mock_session_get.__aexit__ = AsyncMock(return_value=None)
        server_with_camera_tools.ha_client.session.get = Mock(
            return_value=mock_session_get
        )

        # Get the registered tool function
        camera_tool_func = server_with_camera_tools.mcp._test_tools[
            "get_camera_snapshot"
        ]

        # Execute the tool
        with patch("asyncio.sleep", return_value=None):  # Mock sleep
            result_json = await camera_tool_func(entity_id)

        # Parse result
        result = json.loads(result_json)

        # Verify the OUTCOME: we got a valid snapshot result
        assert result["success"] is True
        assert result["image_base64"] == expected_base64
        assert result["snapshot_id"]  # Has a snapshot ID
        assert result["error"] == ""
        assert "original_size" in result
        assert "final_size" in result
        assert "downsampled" in result

    @pytest.mark.asyncio
    async def test_get_camera_snapshot_invalid_entity_id(
        self, server_with_camera_tools
    ):
        """Test handling of invalid entity ID format."""
        # Setup invalid entity ID
        invalid_entity_id = "invalid_entity_format"
        server_with_camera_tools.ha_client.validate_entity_id = Mock(return_value=False)

        # Get the registered tool function
        camera_tool_func = server_with_camera_tools.mcp._test_tools[
            "get_camera_snapshot"
        ]

        # Execute the tool
        result_json = await camera_tool_func(invalid_entity_id)
        result = json.loads(result_json)

        # Verify error handling
        assert result["success"] is False
        assert "Invalid entity ID format" in result["error"]
        assert result["image_base64"] == ""
        assert result["snapshot_id"] == ""
        assert "original_size" in result
        assert "final_size" in result
        assert "downsampled" in result

        # Verify no service call was made
        server_with_camera_tools.ha_client.call_service.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_camera_snapshot_service_call_failure(
        self, server_with_camera_tools
    ):
        """Test handling of camera service call failure."""
        # Setup
        entity_id = "camera.front_door"
        server_with_camera_tools.ha_client.call_service.side_effect = (
            HomeAssistantAPIError("Camera not found", 404)
        )

        # Get the registered tool function
        camera_tool_func = server_with_camera_tools.mcp._test_tools[
            "get_camera_snapshot"
        ]

        # Execute the tool
        with patch(
            "uuid.uuid4", return_value=uuid.UUID("12345678-1234-5678-9012-123456789abc")
        ):
            result_json = await camera_tool_func(entity_id)

        result = json.loads(result_json)

        # Verify error handling
        assert result["success"] is False
        assert "Camera snapshot failed" in result["error"]
        assert "Camera not found" in result["error"]
        assert result["image_base64"] == ""
        assert result["snapshot_id"] == ""
        assert "original_size" in result
        assert "final_size" in result
        assert "downsampled" in result

    @pytest.mark.asyncio
    async def test_get_camera_snapshot_http_retrieval_failure(
        self, server_with_camera_tools
    ):
        """Test handling of HTTP image retrieval failure."""
        # Setup
        entity_id = "camera.front_door"

        # Mock HTTP response with 404 error
        mock_response = AsyncMock()
        mock_response.status = 404

        mock_session_get = AsyncMock()
        mock_session_get.__aenter__ = AsyncMock(return_value=mock_response)
        mock_session_get.__aexit__ = AsyncMock(return_value=None)
        server_with_camera_tools.ha_client.session.get = Mock(
            return_value=mock_session_get
        )

        # Get the registered tool function
        camera_tool_func = server_with_camera_tools.mcp._test_tools[
            "get_camera_snapshot"
        ]

        # Execute the tool
        with patch("asyncio.sleep", return_value=None):
            result_json = await camera_tool_func(entity_id)

        result = json.loads(result_json)

        # Verify the OUTCOME: error is properly reported
        assert result["success"] is False
        assert "Failed to retrieve snapshot image: HTTP 404" in result["error"]
        assert result["image_base64"] == ""
        assert result["snapshot_id"]  # Has a snapshot ID even on failure
        assert "original_size" in result
        assert "final_size" in result
        assert "downsampled" in result

    @pytest.mark.asyncio
    async def test_get_camera_snapshot_auto_connect(self, server_with_camera_tools):
        """Test that auto-connect is triggered when session is None."""
        # Setup
        entity_id = "camera.front_door"
        server_with_camera_tools.ha_client.session = None  # No session initially
        mock_image_data = b"fake_jpeg_data"

        # Mock successful reconnection
        mock_session = Mock(spec=ClientSession)
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.read = AsyncMock(return_value=mock_image_data)

        mock_session_get = AsyncMock()
        mock_session_get.__aenter__ = AsyncMock(return_value=mock_response)
        mock_session_get.__aexit__ = AsyncMock(return_value=None)
        mock_session.get = Mock(return_value=mock_session_get)

        # Mock connect to set session
        async def mock_connect():
            server_with_camera_tools.ha_client.session = mock_session

        server_with_camera_tools.ha_client.connect = AsyncMock(side_effect=mock_connect)

        # Get the registered tool function
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

        # Verify the OUTCOME: we got a successful snapshot even without a pre-existing session
        assert result["success"] is True
        assert "original_size" in result
        assert "final_size" in result
        assert "downsampled" in result

    def test_camera_tool_docstring_compliance(self, server_with_camera_tools):
        """Test that camera tool has proper docstring and parameter documentation."""
        # Get the registered tool function
        camera_tool_func = server_with_camera_tools.mcp._test_tools[
            "get_camera_snapshot"
        ]

        # Check docstring exists and contains key information
        docstring = camera_tool_func.__doc__
        assert docstring is not None, "Camera tool missing docstring"
        assert "entity_id" in docstring, "Docstring missing parameter documentation"
        assert "base64" in docstring, "Docstring missing base64 encoding info"
        assert "UUID v4" in docstring, "Docstring missing UUID info"
        assert "camera.snapshot" in docstring, "Docstring missing service call info"
        assert "downsampl" in docstring, "Docstring missing downsampling info"
        assert (
            "original_size" in docstring
        ), "Docstring missing original_size field info"
        assert "final_size" in docstring, "Docstring missing final_size field info"

    @pytest.mark.asyncio
    async def test_uuid_generation_uniqueness(self, server_with_camera_tools):
        """Test that each snapshot gets a unique UUID identifier."""
        entity_id = "camera.test"
        mock_image_data = b"test_data"

        # Mock HTTP response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.read = AsyncMock(return_value=mock_image_data)

        mock_session_get = AsyncMock()
        mock_session_get.__aenter__ = AsyncMock(return_value=mock_response)
        mock_session_get.__aexit__ = AsyncMock(return_value=None)
        server_with_camera_tools.ha_client.session.get = Mock(
            return_value=mock_session_get
        )

        # Get the registered tool function
        camera_tool_func = server_with_camera_tools.mcp._test_tools[
            "get_camera_snapshot"
        ]

        # Execute multiple times and collect snapshot IDs
        snapshot_ids = []
        for _ in range(3):
            with patch("asyncio.sleep", return_value=None):
                result_json = await camera_tool_func(entity_id)
            result = json.loads(result_json)
            snapshot_ids.append(result["snapshot_id"])

        # Verify all IDs are unique and valid UUIDs
        assert len(set(snapshot_ids)) == 3, "Snapshot IDs are not unique"
        for snapshot_id in snapshot_ids:
            # Test UUID format
            uuid.UUID(snapshot_id)  # Will raise ValueError if invalid
