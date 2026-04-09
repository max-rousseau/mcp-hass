"""
Test suite for bulk operation tools.

Tests the bulk tools: call_service_bulk, get_states_bulk, turn_on_bulk,
turn_off_bulk. Critical for ensuring efficient multi-entity operations
and proper error handling for bulk operations.
"""

import pytest
import json
from unittest.mock import AsyncMock, Mock

import logging

from src.mcp_hass.server import MCPHomeAssistantServer
from src.mcp_hass.ha_client.exceptions import (
    HomeAssistantAPIError,
    HomeAssistantConnectionError,
)
from src.mcp_hass.tools import ToolContext, register_bulk_tools
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


@pytest.fixture
def server_with_mocks():
    """Create server with mocked components for bulk tool testing."""
    server = MCPHomeAssistantServer()

    # Mock HA client - test connection handling
    mock_ha_client = Mock()
    mock_ha_client.session = None  # Initially not connected
    mock_ha_client.connect = AsyncMock()
    mock_ha_client.call_service = AsyncMock()
    mock_ha_client.get_entity_state = AsyncMock()
    server.ha_client = mock_ha_client

    # Mock config
    mock_config = Mock(spec=ConfigurationManager)
    mock_config.get_tool_token_limit.return_value = 100000
    server.config = mock_config

    # Storage for registered tools
    registered_tools = {}

    # Mock decorator that captures functions
    def mock_tool_decorator(*args, **kwargs):
        if args and callable(args[0]):
            func = args[0]
            registered_tools[func.__name__] = func
            return func

        def decorator(func):
            registered_tools[func.__name__] = func
            return func

        return decorator

    # Mock FastMCP
    server.mcp = Mock()
    server.mcp.tool = Mock(side_effect=mock_tool_decorator)
    server.mcp._test_tools = registered_tools

    # Create ToolContext and register bulk tools
    ctx = ToolContext(
        mcp=server.mcp,
        ha_client=mock_ha_client,
        config=mock_config,
        logger=logging.getLogger(__name__),
    )
    register_bulk_tools(ctx)

    return server, mock_ha_client


@pytest.fixture
def sample_entity_states():
    """Sample entity states for bulk operations."""
    return [
        {
            "entity_id": "light.living_room",
            "state": "on",
            "attributes": {"brightness": 255, "friendly_name": "Living Room Light"},
        },
        {
            "entity_id": "light.bedroom",
            "state": "off",
            "attributes": {"brightness": 0, "friendly_name": "Bedroom Light"},
        },
        {
            "entity_id": "switch.kitchen",
            "state": "on",
            "attributes": {"friendly_name": "Kitchen Switch"},
        },
    ]


@pytest.fixture
def sample_service_response():
    """Sample service call response."""
    return [{"entity_id": "light.living_room", "state": "on"}]


class TestCallServiceBulk:
    """Test call_service_bulk tool."""

    @pytest.mark.asyncio
    async def test_call_service_bulk_auto_connects(
        self, server_with_mocks, sample_service_response
    ):
        """Test that call_service_bulk succeeds when initially disconnected.

        CONTRACT: Operation succeeds and calls services for all entities
        regardless of initial connection state. Tests WHAT (bulk services called),
        not HOW (connection established).
        """
        server, mock_ha_client = server_with_mocks
        mock_ha_client.session = None  # Start disconnected
        mock_ha_client.call_service.return_value = sample_service_response

        # Get the registered tool function
        call_service_bulk_func = server.mcp._test_tools["call_service_bulk"]

        entity_ids = ["light.living_room", "light.bedroom"]
        result = await call_service_bulk_func("light", "turn_on", entity_ids)

        # Test the CONTRACT: operation succeeds with all services called
        parsed_result = json.loads(result)
        assert parsed_result["total"] == 2
        assert parsed_result["succeeded"] == 2
        assert parsed_result["failed"] == 0

        # Verify service calls were made for each entity (outcome)
        assert mock_ha_client.call_service.call_count == 2

        # Verify result structure
        parsed_result = json.loads(result)
        assert parsed_result["total"] == 2
        assert parsed_result["succeeded"] == 2
        assert parsed_result["failed"] == 0
        assert len(parsed_result["results"]) == 2

    @pytest.mark.asyncio
    async def test_call_service_bulk_already_connected(
        self, server_with_mocks, sample_service_response
    ):
        """Test call_service_bulk when already connected."""
        server, mock_ha_client = server_with_mocks
        mock_ha_client.session = Mock()  # Already connected
        mock_ha_client.call_service.return_value = sample_service_response

        call_service_bulk_func = server.mcp._test_tools["call_service_bulk"]

        entity_ids = ["light.living_room", "light.bedroom", "switch.kitchen"]
        result = await call_service_bulk_func("homeassistant", "turn_on", entity_ids)

        # Should NOT call connect since already connected
        mock_ha_client.connect.assert_not_called()

        # Verify service calls were made for each entity
        assert mock_ha_client.call_service.call_count == 3

        # Verify each call had the correct entity_id
        call_args_list = mock_ha_client.call_service.call_args_list
        expected_entity_ids = ["light.living_room", "light.bedroom", "switch.kitchen"]

        for i, call_args in enumerate(call_args_list):
            args, kwargs = call_args
            assert args[0] == "homeassistant"  # domain
            assert args[1] == "turn_on"  # service
            assert args[2]["entity_id"] == expected_entity_ids[i]  # service data

        parsed_result = json.loads(result)
        assert parsed_result["total"] == 3
        assert parsed_result["succeeded"] == 3
        assert parsed_result["failed"] == 0

    @pytest.mark.asyncio
    async def test_call_service_bulk_with_data(
        self, server_with_mocks, sample_service_response
    ):
        """Test call_service_bulk with additional service data."""
        server, mock_ha_client = server_with_mocks
        mock_ha_client.session = Mock()
        mock_ha_client.call_service.return_value = sample_service_response

        call_service_bulk_func = server.mcp._test_tools["call_service_bulk"]

        entity_ids = ["light.living_room", "light.bedroom"]
        data = {"brightness": 128, "color_temp": 300}
        result = await call_service_bulk_func("light", "turn_on", entity_ids, data=data)

        # Verify service calls include the data
        call_args_list = mock_ha_client.call_service.call_args_list
        for i, call_args in enumerate(call_args_list):
            args, kwargs = call_args
            service_data = args[2]
            assert service_data["entity_id"] == entity_ids[i]
            assert service_data["brightness"] == 128
            assert service_data["color_temp"] == 300

        parsed_result = json.loads(result)
        assert parsed_result["succeeded"] == 2

    @pytest.mark.asyncio
    async def test_call_service_bulk_partial_failure(
        self, server_with_mocks, sample_service_response
    ):
        """Test call_service_bulk with some entities failing."""
        server, mock_ha_client = server_with_mocks
        mock_ha_client.session = Mock()

        # First entity succeeds, second fails, third succeeds
        def mock_call_service(domain, service, data):
            if data["entity_id"] == "light.bedroom":
                raise HomeAssistantAPIError("Entity not found", 404)
            return sample_service_response

        mock_ha_client.call_service.side_effect = mock_call_service

        call_service_bulk_func = server.mcp._test_tools["call_service_bulk"]

        entity_ids = ["light.living_room", "light.bedroom", "switch.kitchen"]
        result = await call_service_bulk_func("homeassistant", "turn_on", entity_ids)

        parsed_result = json.loads(result)
        assert parsed_result["total"] == 3
        assert parsed_result["succeeded"] == 2
        assert parsed_result["failed"] == 1

        # Verify results structure
        results = parsed_result["results"]
        assert len(results) == 3

        # Check successful results
        success_results = [r for r in results if r["success"]]
        assert len(success_results) == 2
        assert success_results[0]["entity_id"] == "light.living_room"
        assert success_results[1]["entity_id"] == "switch.kitchen"

        # Check failed result
        failed_results = [r for r in results if not r["success"]]
        assert len(failed_results) == 1
        assert failed_results[0]["entity_id"] == "light.bedroom"
        assert "Entity not found" in failed_results[0]["error"]

    @pytest.mark.asyncio
    async def test_call_service_bulk_empty_entity_list(self, server_with_mocks):
        """Test call_service_bulk with empty entity list."""
        server, mock_ha_client = server_with_mocks
        mock_ha_client.session = Mock()

        call_service_bulk_func = server.mcp._test_tools["call_service_bulk"]

        result = await call_service_bulk_func("light", "turn_on", [])

        # Should not make any service calls
        mock_ha_client.call_service.assert_not_called()

        parsed_result = json.loads(result)
        assert parsed_result["total"] == 0
        assert parsed_result["succeeded"] == 0
        assert parsed_result["failed"] == 0
        assert len(parsed_result["results"]) == 0


class TestBulkToolsErrorHandling:
    """Test error handling in bulk tools."""

    @pytest.mark.asyncio
    async def test_bulk_tools_connection_error(self, server_with_mocks):
        """Test that bulk tools handle connection errors gracefully."""
        server, mock_ha_client = server_with_mocks
        mock_ha_client.session = None
        mock_ha_client.connect.side_effect = HomeAssistantConnectionError(
            "Connection failed"
        )

        # Test call_service_bulk
        call_service_bulk_func = server.mcp._test_tools["call_service_bulk"]

        with pytest.raises(ValueError, match="Failed to perform bulk service call"):
            await call_service_bulk_func("light", "turn_on", ["light.test"])


class TestBulkToolsRegistration:
    """Test that bulk tools are properly registered."""

    def test_all_bulk_tools_registered(self):
        """Test that all expected bulk tools are registered."""
        mock_decorator, registered_tools = create_mock_tool_decorator()
        mock_mcp = Mock()
        mock_mcp.tool = Mock(side_effect=mock_decorator)
        mock_ha_client = Mock()
        mock_ha_client.session = Mock()
        mock_config = Mock(spec=ConfigurationManager)
        mock_config.get_tool_token_limit.return_value = 100000

        ctx = ToolContext(
            mcp=mock_mcp,
            ha_client=mock_ha_client,
            config=mock_config,
            logger=logging.getLogger(__name__),
        )
        register_bulk_tools(ctx)

        expected_functions = ["call_service_bulk"]
        assert set(registered_tools.keys()) == set(expected_functions)


class TestBulkToolsConnectionHandling:
    """Test connection handling consistency across bulk tools."""

    @pytest.mark.asyncio
    async def test_all_bulk_tools_handle_connection_consistently(self):
        """Test that all bulk tools handle connection the same way."""
        mock_ha_client = Mock()
        mock_ha_client.session = None
        mock_ha_client.connect = AsyncMock()
        mock_ha_client.call_service.return_value = []

        mock_decorator, registered_tools = create_mock_tool_decorator()
        mock_mcp = Mock()
        mock_mcp.tool = Mock(side_effect=mock_decorator)
        mock_config = Mock(spec=ConfigurationManager)
        mock_config.get_tool_token_limit.return_value = 100000

        ctx = ToolContext(
            mcp=mock_mcp,
            ha_client=mock_ha_client,
            config=mock_config,
            logger=logging.getLogger(__name__),
        )
        register_bulk_tools(ctx)

        test_cases = [
            ("call_service_bulk", ("light", "turn_on", ["light.test"])),
        ]

        for tool_name, args in test_cases:
            mock_ha_client.session = None
            mock_ha_client.connect.reset_mock()

            await registered_tools[tool_name](*args)

            mock_ha_client.connect.assert_called_once()

    @pytest.mark.asyncio
    async def test_bulk_tools_respect_existing_connection(self):
        """Test that bulk tools don't reconnect when already connected."""
        mock_ha_client = Mock()
        mock_ha_client.session = Mock()
        mock_ha_client.connect = AsyncMock()
        mock_ha_client.call_service.return_value = []

        mock_decorator, registered_tools = create_mock_tool_decorator()
        mock_mcp = Mock()
        mock_mcp.tool = Mock(side_effect=mock_decorator)
        mock_config = Mock(spec=ConfigurationManager)
        mock_config.get_tool_token_limit.return_value = 100000

        ctx = ToolContext(
            mcp=mock_mcp,
            ha_client=mock_ha_client,
            config=mock_config,
            logger=logging.getLogger(__name__),
        )
        register_bulk_tools(ctx)

        await registered_tools["call_service_bulk"]("light", "turn_on", ["light.test"])

        mock_ha_client.connect.assert_not_called()
