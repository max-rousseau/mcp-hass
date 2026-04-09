"""
Test suite for service control tools.

Tests the service-related operations: call_service, turn_on_entity,
turn_off_entity, toggle_entity, and get_services. Critical for ensuring
proper device control and service invocation functionality.
"""

import logging

import pytest
import json
from unittest.mock import AsyncMock, Mock

from src.mcp_hass.server import MCPHomeAssistantServer
from src.mcp_hass.ha_client.exceptions import HomeAssistantAPIError
from src.mcp_hass.tools import ToolContext, register_service_tools
from src.mcp_hass.config import ConfigurationManager


@pytest.fixture
def server_with_mocks():
    """Create server with mocked components for service tool testing."""
    server = MCPHomeAssistantServer()

    # Mock HA client
    mock_ha_client = Mock()
    mock_ha_client.session = Mock()  # Connected
    mock_ha_client.call_service = AsyncMock()
    mock_ha_client.get_services = AsyncMock()
    server.ha_client = mock_ha_client

    # Mock config
    mock_config = Mock(spec=ConfigurationManager)
    mock_config.get_tool_token_limit.return_value = None  # No limit by default
    server.config = mock_config

    # Storage for registered tools
    registered_tools = {}

    # Mock decorator that captures functions
    def mock_tool_decorator(*args, **kwargs):
        if args and callable(args[0]):
            # Direct decoration: @mcp.tool
            func = args[0]
            registered_tools[func.__name__] = func
            return func

        # Decorator factory: @mcp.tool(annotations=...)
        def decorator(func):
            registered_tools[func.__name__] = func
            return func

        return decorator

    # Mock FastMCP
    server.mcp = Mock()
    server.mcp.tool = Mock(side_effect=mock_tool_decorator)
    server.mcp._test_tools = registered_tools  # Store for test access

    # Create ToolContext and register service tools
    ctx = ToolContext(
        mcp=server.mcp,
        ha_client=mock_ha_client,
        config=mock_config,
        logger=logging.getLogger(__name__),
    )
    register_service_tools(ctx)

    return server, mock_ha_client


@pytest.fixture
def sample_service_response():
    """Sample service call response."""
    return [
        {
            "entity_id": "light.living_room",
            "state": "on",
            "attributes": {"brightness": 255},
        }
    ]


@pytest.fixture
def sample_services_data():
    """Sample services data from Home Assistant (raw API format)."""
    return [
        {
            "domain": "light",
            "services": {
                "turn_on": {
                    "description": "Turn the light on.",
                    "fields": {
                        "entity_id": {"description": "Name(s) of entities to turn on"},
                        "brightness": {"description": "Number indicating brightness"},
                        "color_temp": {"description": "Color temperature in mireds"},
                    },
                },
                "turn_off": {
                    "description": "Turn the light off.",
                    "fields": {
                        "entity_id": {"description": "Name(s) of entities to turn off"}
                    },
                },
                "toggle": {
                    "description": "Toggle the light.",
                    "fields": {
                        "entity_id": {"description": "Name(s) of entities to toggle"}
                    },
                },
            },
        },
        {
            "domain": "switch",
            "services": {
                "turn_on": {
                    "description": "Turn the switch on.",
                    "fields": {
                        "entity_id": {"description": "Name(s) of entities to turn on"}
                    },
                },
                "turn_off": {
                    "description": "Turn the switch off.",
                    "fields": {
                        "entity_id": {"description": "Name(s) of entities to turn off"}
                    },
                },
            },
        },
    ]


class TestCallService:
    """Test call_service tool."""

    @pytest.mark.asyncio
    async def test_call_service_basic(self, server_with_mocks, sample_service_response):
        """Test basic service call."""
        server, mock_ha_client = server_with_mocks
        mock_ha_client.call_service.return_value = sample_service_response

        # Get the registered tool function
        call_service_func = server.mcp._test_tools["call_service"]

        result = await call_service_func("light", "turn_on")
        # Verify result is valid JSON
        assert result is not None

        # Verify HA client was called correctly
        mock_ha_client.call_service.assert_called_once_with("light", "turn_on", {})

        # Verify result is valid JSON
        parsed_result = json.loads(result)
        assert parsed_result == sample_service_response

    @pytest.mark.asyncio
    async def test_call_service_with_entity_id(
        self, server_with_mocks, sample_service_response
    ):
        """Test service call with entity ID."""
        server, mock_ha_client = server_with_mocks
        mock_ha_client.call_service.return_value = sample_service_response

        call_service_func = server.mcp._test_tools["call_service"]

        result = await call_service_func(
            "light", "turn_on", entity_id="light.living_room"
        )

        # Verify result is valid JSON
        assert result is not None

        expected_data = {"entity_id": "light.living_room"}
        mock_ha_client.call_service.assert_called_once_with(
            "light", "turn_on", expected_data
        )

        parsed_result = json.loads(result)
        assert parsed_result == sample_service_response

    @pytest.mark.asyncio
    async def test_call_service_with_data(
        self, server_with_mocks, sample_service_response
    ):
        """Test service call with additional data."""
        server, mock_ha_client = server_with_mocks
        mock_ha_client.call_service.return_value = sample_service_response

        call_service_func = server.mcp._test_tools["call_service"]

        data = {"brightness": 255, "color_temp": 370}
        result = await call_service_func(
            "light", "turn_on", entity_id="light.living_room", data=data
        )

        # Verify result is valid JSON
        assert result is not None

        expected_data = {
            "entity_id": "light.living_room",
            "brightness": 255,
            "color_temp": 370,
        }
        mock_ha_client.call_service.assert_called_once_with(
            "light", "turn_on", expected_data
        )

        parsed_result = json.loads(result)
        assert parsed_result == sample_service_response

    @pytest.mark.asyncio
    async def test_call_service_data_only(
        self, server_with_mocks, sample_service_response
    ):
        """Test service call with data but no entity ID."""
        server, mock_ha_client = server_with_mocks
        mock_ha_client.call_service.return_value = sample_service_response

        call_service_func = server.mcp._test_tools["call_service"]

        data = {"notification": {"message": "Test message"}}
        result = await call_service_func("notify", "mobile_app", data=data)
        # Verify result is valid JSON
        assert result is not None

        mock_ha_client.call_service.assert_called_once_with(
            "notify", "mobile_app", data
        )

        parsed_result = json.loads(result)
        assert parsed_result == sample_service_response

    @pytest.mark.asyncio
    async def test_call_service_api_error(self, server_with_mocks):
        """Test service call with API error."""
        server, mock_ha_client = server_with_mocks
        mock_ha_client.call_service.side_effect = HomeAssistantAPIError(
            "Service not found", 400
        )

        call_service_func = server.mcp._test_tools["call_service"]

        with pytest.raises(ValueError, match="Failed to call service"):
            await call_service_func("nonexistent", "invalid")


class TestGetServices:
    """Test get_services tool (summary format)."""

    @pytest.mark.asyncio
    async def test_get_services_success(self, server_with_mocks, sample_services_data):
        """Test successful services retrieval returns summary format."""
        server, mock_ha_client = server_with_mocks
        mock_ha_client.get_services.return_value = sample_services_data

        get_services_func = server.mcp._test_tools["get_services"]

        result = await get_services_func()
        assert result is not None

        mock_ha_client.get_services.assert_called_once()

        parsed_result = json.loads(result)
        # Should be summary format: list of {domain, services: [names]}
        assert isinstance(parsed_result, list)
        assert len(parsed_result) == 2

        # Find light domain entry
        light_entry = next(d for d in parsed_result if d["domain"] == "light")
        assert "turn_on" in light_entry["services"]
        assert "turn_off" in light_entry["services"]
        assert "toggle" in light_entry["services"]

        # Find switch domain entry
        switch_entry = next(d for d in parsed_result if d["domain"] == "switch")
        assert "turn_on" in switch_entry["services"]
        assert "turn_off" in switch_entry["services"]

    @pytest.mark.asyncio
    async def test_get_services_empty_response(self, server_with_mocks):
        """Test services retrieval with empty response."""
        server, mock_ha_client = server_with_mocks
        mock_ha_client.get_services.return_value = []

        get_services_func = server.mcp._test_tools["get_services"]

        result = await get_services_func()
        assert result is not None

        parsed_result = json.loads(result)
        assert parsed_result == []

    @pytest.mark.asyncio
    async def test_get_services_api_error(self, server_with_mocks):
        """Test services retrieval with API error."""
        server, mock_ha_client = server_with_mocks
        mock_ha_client.get_services.side_effect = HomeAssistantAPIError(
            "Services unavailable", 503
        )

        get_services_func = server.mcp._test_tools["get_services"]

        with pytest.raises(ValueError, match="Failed to get services"):
            await get_services_func()

    @pytest.mark.asyncio
    async def test_get_services_token_limit_exceeded(self, server_with_mocks):
        """Test services retrieval with token limit exceeded returns error."""
        server, mock_ha_client = server_with_mocks
        # Return some data
        mock_ha_client.get_services.return_value = [
            {"domain": "light", "services": {"turn_on": {}, "turn_off": {}}}
        ]
        # Set a very low token limit to trigger the error
        server.config.get_tool_token_limit.return_value = 1

        get_services_func = server.mcp._test_tools["get_services"]

        result = await get_services_func()
        parsed_result = json.loads(result)

        assert "error" in parsed_result
        assert "token_count" in parsed_result
        assert "token_limit" in parsed_result
        assert parsed_result["token_limit"] == 1


class TestGetServiceDetail:
    """Test get_service_detail tool."""

    @pytest.mark.asyncio
    async def test_get_service_detail_success(
        self, server_with_mocks, sample_services_data
    ):
        """Test successful service detail retrieval."""
        server, mock_ha_client = server_with_mocks
        mock_ha_client.get_services.return_value = sample_services_data

        get_service_detail_func = server.mcp._test_tools["get_service_detail"]

        result = await get_service_detail_func("light", "turn_on")
        assert result is not None

        parsed_result = json.loads(result)
        assert parsed_result["domain"] == "light"
        assert parsed_result["service"] == "turn_on"
        assert "fields" in parsed_result
        assert "description" in parsed_result["fields"]

    @pytest.mark.asyncio
    async def test_get_service_detail_domain_not_found(
        self, server_with_mocks, sample_services_data
    ):
        """Test service detail retrieval with invalid domain."""
        server, mock_ha_client = server_with_mocks
        mock_ha_client.get_services.return_value = sample_services_data

        get_service_detail_func = server.mcp._test_tools["get_service_detail"]

        with pytest.raises(ValueError, match="Domain 'nonexistent' not found"):
            await get_service_detail_func("nonexistent", "turn_on")

    @pytest.mark.asyncio
    async def test_get_service_detail_service_not_found(
        self, server_with_mocks, sample_services_data
    ):
        """Test service detail retrieval with invalid service."""
        server, mock_ha_client = server_with_mocks
        mock_ha_client.get_services.return_value = sample_services_data

        get_service_detail_func = server.mcp._test_tools["get_service_detail"]

        with pytest.raises(ValueError, match="Service 'nonexistent' not found"):
            await get_service_detail_func("light", "nonexistent")

    @pytest.mark.asyncio
    async def test_get_service_detail_api_error(self, server_with_mocks):
        """Test service detail retrieval with API error."""
        server, mock_ha_client = server_with_mocks
        mock_ha_client.get_services.side_effect = HomeAssistantAPIError(
            "Services unavailable", 503
        )

        get_service_detail_func = server.mcp._test_tools["get_service_detail"]

        with pytest.raises(ValueError, match="Failed to get service detail"):
            await get_service_detail_func("light", "turn_on")


class TestServiceToolsRegistration:
    """Test that service tools are properly registered."""

    def test_all_service_tools_registered(self):
        """Test that all expected service tools are registered."""
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

        mock_mcp = Mock()
        mock_mcp.tool = Mock(side_effect=mock_tool_decorator)
        mock_ha_client = Mock()
        mock_ha_client.session = Mock()
        mock_config = Mock(spec=ConfigurationManager)
        mock_config.get_tool_token_limit.return_value = None

        ctx = ToolContext(
            mcp=mock_mcp,
            ha_client=mock_ha_client,
            config=mock_config,
            logger=logging.getLogger(__name__),
        )
        register_service_tools(ctx)

        # Verify 3 tools were registered
        assert len(registered_tools) == 3

        expected_functions = [
            "call_service",
            "get_services",
            "get_service_detail",
        ]

        assert set(registered_tools.keys()) == set(expected_functions)
