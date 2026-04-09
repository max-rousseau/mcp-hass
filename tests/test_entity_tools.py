"""
Test suite for entity management tools.

Tests the core entity operations: get_entity_state, get_all_entities,
get_entity_history, and find_entities. Critical for ensuring proper
entity data retrieval and search functionality.
"""

import logging

import pytest
import json
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch

from src.mcp_hass.server import MCPHomeAssistantServer
from src.mcp_hass.ha_client.exceptions import HomeAssistantAPIError
from src.mcp_hass.tools import ToolContext, register_entity_tools
from src.mcp_hass.config import ConfigurationManager


@pytest.fixture
def server_with_mocks():
    """Create server with mocked components for entity tool testing."""
    server = MCPHomeAssistantServer()

    # Mock HA client
    mock_ha_client = Mock()
    mock_ha_client.session = Mock()  # Connected
    mock_ha_client.get_entity_state = AsyncMock()
    mock_ha_client.get_all_states = AsyncMock()
    mock_ha_client.get_history = AsyncMock()
    server.ha_client = mock_ha_client

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

    # Mock FastMCP
    server.mcp = Mock()
    server.mcp.tool = Mock(side_effect=mock_tool_decorator)
    server.mcp._test_tools = registered_tools

    # Create ToolContext and register entity tools
    ctx = ToolContext(
        mcp=server.mcp,
        ha_client=mock_ha_client,
        config=mock_config,
        logger=logging.getLogger(__name__),
    )
    register_entity_tools(ctx)

    return server, mock_ha_client


@pytest.fixture
def sample_entity_state():
    """Sample entity state data."""
    return {
        "entity_id": "light.living_room",
        "state": "on",
        "attributes": {
            "friendly_name": "Living Room Light",
            "brightness": 255,
            "color_temp": 370,
            "supported_features": 47,
        },
        "last_changed": "2025-01-20T10:30:00.000000+00:00",
        "last_updated": "2025-01-20T10:30:00.000000+00:00",
    }


@pytest.fixture
def sample_all_states():
    """Sample all states data."""
    return [
        {
            "entity_id": "light.living_room",
            "state": "on",
            "attributes": {"friendly_name": "Living Room Light", "brightness": 255},
        },
        {
            "entity_id": "light.bedroom",
            "state": "off",
            "attributes": {"friendly_name": "Bedroom Light"},
        },
        {
            "entity_id": "sensor.temperature",
            "state": "22.5",
            "attributes": {
                "friendly_name": "Temperature Sensor",
                "unit_of_measurement": "°C",
            },
        },
        {
            "entity_id": "switch.kitchen",
            "state": "on",
            "attributes": {"friendly_name": "Kitchen Switch"},
        },
    ]


@pytest.fixture
def sample_history_data():
    """Sample history data.

    Note: Home Assistant history API returns data as [[entry1, entry2, ...]]
    (array of arrays where each inner array contains history for one entity).
    """
    return [
        [
            {
                "entity_id": "sensor.temperature",
                "state": "22.5",
                "attributes": {
                    "unit_of_measurement": "°C",
                    "friendly_name": "Temperature Sensor",
                },
                "last_changed": "2025-01-20T10:00:00+00:00",
            },
            {
                "entity_id": "sensor.temperature",
                "state": "23.0",
                "attributes": {
                    "unit_of_measurement": "°C",
                    "friendly_name": "Temperature Sensor",
                },
                "last_changed": "2025-01-20T11:00:00+00:00",
            },
        ]
    ]


class TestGetEntityHistory:
    """Test get_entity_history tool."""

    @pytest.mark.asyncio
    async def test_get_entity_history_default_hours(
        self, server_with_mocks, sample_history_data
    ):
        """Test entity history retrieval with default hours.

        Note: get_entity_history returns an optimized format with header metadata
        and compact history entries, not the raw Home Assistant API response.
        """
        server, mock_ha_client = server_with_mocks
        mock_ha_client.get_history.return_value = sample_history_data

        get_entity_history_func = server.mcp._test_tools["get_entity_history"]

        # Mock datetime.now to ensure consistent testing
        with patch("src.mcp_hass.tools.entity.datetime") as mock_datetime:
            now = datetime(2025, 1, 20, 12, 0, 0)
            mock_datetime.now.return_value = now
            mock_datetime.side_effect = lambda *args, **kwargs: datetime(
                *args, **kwargs
            )

            result = await get_entity_history_func("sensor.temperature")

            # Verify the start_time was calculated correctly (24 hours ago)
            expected_start_time = now - timedelta(hours=24.0)
            mock_ha_client.get_history.assert_called_once_with(
                "sensor.temperature", expected_start_time
            )

            # Verify optimized response format
            parsed_result = json.loads(result)
            assert parsed_result["entity_id"] == "sensor.temperature"
            assert "history" in parsed_result
            assert len(parsed_result["history"]) == 2
            assert parsed_result["history"][0]["state"] == "22.5"
            assert parsed_result["history"][1]["state"] == "23.0"

    @pytest.mark.asyncio
    async def test_get_entity_history_custom_hours(
        self, server_with_mocks, sample_history_data
    ):
        """Test entity history retrieval with custom hours.

        Note: get_entity_history returns an optimized format with header metadata
        and compact history entries, not the raw Home Assistant API response.
        """
        server, mock_ha_client = server_with_mocks
        mock_ha_client.get_history.return_value = sample_history_data

        get_entity_history_func = server.mcp._test_tools["get_entity_history"]

        with patch("src.mcp_hass.tools.entity.datetime") as mock_datetime:
            now = datetime(2025, 1, 20, 12, 0, 0)
            mock_datetime.now.return_value = now
            mock_datetime.side_effect = lambda *args, **kwargs: datetime(
                *args, **kwargs
            )

            result = await get_entity_history_func("sensor.temperature", hours=12.0)

            expected_start_time = now - timedelta(hours=12.0)
            mock_ha_client.get_history.assert_called_once_with(
                "sensor.temperature", expected_start_time
            )

            # Verify optimized response format
            parsed_result = json.loads(result)
            assert parsed_result["entity_id"] == "sensor.temperature"
            assert "history" in parsed_result
            assert len(parsed_result["history"]) == 2

    @pytest.mark.asyncio
    async def test_get_entity_history_fractional_hours(self, server_with_mocks):
        """Test entity history with fractional hours."""
        server, mock_ha_client = server_with_mocks
        mock_ha_client.get_history.return_value = []

        get_entity_history_func = server.mcp._test_tools["get_entity_history"]

        with patch("src.mcp_hass.tools.entity.datetime") as mock_datetime:
            now = datetime(2025, 1, 20, 12, 0, 0)
            mock_datetime.now.return_value = now
            mock_datetime.side_effect = lambda *args, **kwargs: datetime(
                *args, **kwargs
            )

            result = await get_entity_history_func("sensor.temperature", hours=1.5)

            # Verify result is valid JSON
            assert result is not None

            expected_start_time = now - timedelta(hours=1.5)
            mock_ha_client.get_history.assert_called_once_with(
                "sensor.temperature", expected_start_time
            )

    @pytest.mark.asyncio
    async def test_get_entity_history_api_error(self, server_with_mocks):
        """Test entity history with API error."""
        server, mock_ha_client = server_with_mocks
        mock_ha_client.get_history.side_effect = HomeAssistantAPIError(
            "History not available", 404
        )

        get_entity_history_func = server.mcp._test_tools["get_entity_history"]

        with pytest.raises(ValueError, match="Failed to get entity history"):
            await get_entity_history_func("sensor.temperature")


class TestEntityToolsRegistration:
    """Test that entity tools are properly registered."""

    def test_all_entity_tools_registered(self):
        """Test that all expected entity tools are registered."""
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
        mock_config.get_tool_token_limit.return_value = 100000

        ctx = ToolContext(
            mcp=mock_mcp,
            ha_client=mock_ha_client,
            config=mock_config,
            logger=logging.getLogger(__name__),
        )
        register_entity_tools(ctx)

        # Verify 2 tools were registered
        assert len(registered_tools) == 2

        expected_functions = [
            "get_entity_history",
            "find_entities",
        ]

        assert set(registered_tools.keys()) == set(expected_functions)
