"""
Test suite for spatial/area tools.

Tests the spatial tools: list_areas, get_area_devices, and the consolidated find_entities.
CRITICAL: These tests specifically target the "Client not connected" bug
that was discovered in the list_areas tool.

NOTE: get_area_entities has been REMOVED and replaced with enhanced find_entities
that supports area filtering via the 'area' parameter.
"""

import logging

import pytest
import json
from unittest.mock import AsyncMock, Mock

from src.mcp_hass.server import MCPHomeAssistantServer
from src.mcp_hass.ha_client.exceptions import (
    HomeAssistantAPIError,
    HomeAssistantConnectionError,
)
from src.mcp_hass.tools import (
    ToolContext,
    register_spatial_tools,
    register_entity_tools,
)
from src.mcp_hass.config import ConfigurationManager


@pytest.fixture
def server_with_mocks():
    """Create server with mocked components for spatial tool testing."""
    server = MCPHomeAssistantServer()

    # Mock config manager
    mock_config = Mock(spec=ConfigurationManager)
    mock_config.get_tool_token_limit.return_value = 100000
    server.config = mock_config

    # Mock HA client - initially not connected to test the bug
    mock_ha_client = Mock()
    mock_ha_client.session = None  # This is the critical bug condition!
    mock_ha_client.connect = AsyncMock()
    mock_ha_client.get_areas = AsyncMock()
    mock_ha_client.get_devices = AsyncMock()
    mock_ha_client.get_entity_registry = AsyncMock()
    mock_ha_client.get_all_states = AsyncMock()
    server.ha_client = mock_ha_client

    # Mock FastMCP
    server.mcp = Mock()

    # Track registered functions to make them accessible via call_args_list
    class ToolMock:
        def __init__(self):
            self.call_args_list = []
            self._mock = Mock()

        def __call__(self, *args, **kwargs):
            if args and callable(args[0]):
                # Called as @mcp.tool (bare decorator)
                func = args[0]
                # Store as ((func,), {}) to match call_args_list format
                self.call_args_list.append(((func,), {}))
                return func
            else:
                # Called as @mcp.tool(annotations=...) (decorator factory)
                def decorator(func):
                    # Store as ((func,), kwargs) to match call_args_list format
                    self.call_args_list.append(((func,), kwargs))
                    return func

                return decorator

        @property
        def call_count(self):
            return len(self.call_args_list)

        def __getattr__(self, name):
            return getattr(self._mock, name)

    server.mcp.tool = ToolMock()

    # Create ToolContext and register tools
    ctx = ToolContext(
        mcp=server.mcp,
        ha_client=mock_ha_client,
        config=mock_config,
        logger=logging.getLogger(__name__),
    )
    register_spatial_tools(ctx)
    register_entity_tools(ctx)

    return server, mock_ha_client


@pytest.fixture
def sample_areas_data():
    """Sample areas data from Home Assistant."""
    return [
        {
            "area_id": "living_room",
            "name": "Living Room",
            "picture": None,
        },
        {
            "area_id": "kitchen",
            "name": "Kitchen",
            "picture": "/local/kitchen.jpg",
        },
        {
            "area_id": "bedroom",
            "name": "Master Bedroom",
            "picture": None,
        },
    ]


@pytest.fixture
def sample_devices_data():
    """Sample devices data from Home Assistant."""
    return [
        {
            "id": "device1",
            "area_id": "living_room",
            "name": "Living Room Multi-Sensor",
            "model": "Philips Hue Motion Sensor",
            "manufacturer": "Signify",
        },
        {
            "id": "device2",
            "area_id": "living_room",
            "name": "Living Room Switch",
            "model": "Smart Switch",
            "manufacturer": "Generic",
        },
        {
            "id": "device3",
            "area_id": "kitchen",
            "name": "Kitchen Multi-Device",
            "model": "LIFX Strip+",
            "manufacturer": "LIFX",
        },
        {
            "id": "device4",
            "area_id": None,  # Device not assigned to any area
            "name": "Unassigned Device",
            "model": "Generic",
            "manufacturer": "Unknown",
        },
        {
            "id": "device5",
            "area_id": "bedroom",
            "name": "Bedroom Climate Sensor",
            "model": "Mi Temperature Sensor",
            "manufacturer": "Xiaomi",
        },
    ]


@pytest.fixture
def sample_entity_registry():
    """Sample entity registry data aligned with device and area structure."""
    return [
        {
            "entity_id": "light.living_room_light",
            "device_id": "device1",
            "platform": "hue",
        },
        {
            "entity_id": "sensor.living_room_temperature",
            "device_id": "device1",
            "platform": "hue",
        },
        {
            "entity_id": "binary_sensor.living_room_motion",
            "device_id": "device1",
            "platform": "hue",
        },
        {
            "entity_id": "switch.living_room_switch",
            "device_id": "device2",
            "platform": "generic",
        },
        {
            "entity_id": "light.kitchen_light",
            "device_id": "device3",
            "platform": "lifx",
        },
        {
            "entity_id": "sensor.kitchen_temperature",
            "device_id": "device3",
            "platform": "lifx",
        },
        {
            "entity_id": "sensor.bedroom_humidity",
            "device_id": "device5",  # New device for bedroom
            "platform": "xiaomi",
        },
    ]


@pytest.fixture
def sample_states_data():
    """Sample entity states data with comprehensive test coverage."""
    return [
        {
            "entity_id": "light.living_room_light",
            "state": "on",
            "attributes": {
                "friendly_name": "Living Room Main Light",
                "brightness": 255,
                "device_class": None,
            },
        },
        {
            "entity_id": "light.kitchen_light",
            "state": "off",
            "attributes": {
                "friendly_name": "Kitchen Light",
                "brightness": 0,
                "device_class": None,
            },
        },
        {
            "entity_id": "sensor.living_room_temperature",
            "state": "22.5",
            "attributes": {
                "friendly_name": "Living Room Temperature",
                "unit_of_measurement": "°C",
                "device_class": "temperature",
            },
        },
        {
            "entity_id": "sensor.kitchen_temperature",
            "state": "21.0",
            "attributes": {
                "friendly_name": "Kitchen Temperature",
                "unit_of_measurement": "°C",
                "device_class": "temperature",
            },
        },
        {
            "entity_id": "binary_sensor.living_room_motion",
            "state": "off",
            "attributes": {
                "friendly_name": "Living Room Motion",
                "device_class": "motion",
            },
        },
        {
            "entity_id": "switch.living_room_switch",
            "state": "on",
            "attributes": {"friendly_name": "Living Room Switch", "device_class": None},
        },
        {
            "entity_id": "sensor.bedroom_humidity",
            "state": "45.2",
            "attributes": {
                "friendly_name": "Master Bedroom Humidity",
                "unit_of_measurement": "%",
                "device_class": "humidity",
            },
        },
    ]


class TestListAreas:
    """Test list_areas tool - THE CRITICAL BUG LOCATION."""

    @pytest.mark.asyncio
    async def test_list_areas_auto_connects_when_not_connected(
        self, server_with_mocks, sample_areas_data
    ):
        """Test that list_areas succeeds even when initially disconnected.

        CONTRACT: Operation succeeds and returns areas data regardless of
        initial connection state. Tests WHAT (areas retrieved), not HOW
        (connection established).
        """
        server, mock_ha_client = server_with_mocks
        mock_ha_client.session = None  # Start disconnected
        mock_ha_client.get_areas.return_value = sample_areas_data

        # Get the registered tool function
        tool_calls = server.mcp.tool.call_args_list
        list_areas_func = next(
            call[0][0]
            for call in tool_calls
            if hasattr(call[0][0], "__name__") and call[0][0].__name__ == "list_areas"
        )

        result = await list_areas_func()

        # Test the CONTRACT: operation succeeds with valid area data
        areas = json.loads(result)
        assert len(areas) == 3, f"Expected 3 areas, got {len(areas)}"
        assert areas[0]["area_id"] == "living_room"
        assert areas[0]["name"] == "Living Room"

        # Verify the API call was made (outcome, not connect() call)
        mock_ha_client.get_areas.assert_called_once()

        # Verify result is valid JSON
        parsed_result = json.loads(result)
        assert parsed_result == sample_areas_data

    @pytest.mark.asyncio
    async def test_list_areas_already_connected_skips_connect(
        self, server_with_mocks, sample_areas_data
    ):
        """Test that list_areas doesn't reconnect if already connected."""
        server, mock_ha_client = server_with_mocks
        mock_ha_client.session = Mock()  # Already connected
        mock_ha_client.get_areas.return_value = sample_areas_data

        tool_calls = server.mcp.tool.call_args_list
        list_areas_func = next(
            call[0][0]
            for call in tool_calls
            if hasattr(call[0][0], "__name__") and call[0][0].__name__ == "list_areas"
        )

        result = await list_areas_func()

        # Should NOT call connect since already connected
        mock_ha_client.connect.assert_not_called()

        # Should still make the API call
        mock_ha_client.get_areas.assert_called_once()

        parsed_result = json.loads(result)
        assert parsed_result == sample_areas_data

    @pytest.mark.asyncio
    async def test_list_areas_empty_response(self, server_with_mocks):
        """Test list_areas with empty response."""
        server, mock_ha_client = server_with_mocks
        mock_ha_client.get_areas.return_value = []

        tool_calls = server.mcp.tool.call_args_list
        list_areas_func = next(
            call[0][0]
            for call in tool_calls
            if hasattr(call[0][0], "__name__") and call[0][0].__name__ == "list_areas"
        )

        result = await list_areas_func()

        parsed_result = json.loads(result)
        assert parsed_result == []

    @pytest.mark.asyncio
    async def test_list_areas_connection_error(self, server_with_mocks):
        """Test list_areas handles connection errors gracefully."""
        server, mock_ha_client = server_with_mocks
        mock_ha_client.session = None
        mock_ha_client.connect = AsyncMock()
        mock_ha_client.connect.side_effect = HomeAssistantConnectionError(
            "Cannot connect"
        )

        # Mock auto-connect behavior that fails
        async def auto_connect_get_areas():
            if mock_ha_client.session is None:
                await mock_ha_client.connect()  # This will raise the error
            return []

        mock_ha_client.get_areas.side_effect = auto_connect_get_areas

        tool_calls = server.mcp.tool.call_args_list
        list_areas_func = next(
            call[0][0]
            for call in tool_calls
            if hasattr(call[0][0], "__name__") and call[0][0].__name__ == "list_areas"
        )

        with pytest.raises(ValueError, match="Failed to list areas"):
            await list_areas_func()

    @pytest.mark.asyncio
    async def test_list_areas_api_error(self, server_with_mocks):
        """Test list_areas with API error."""
        server, mock_ha_client = server_with_mocks
        mock_ha_client.session = Mock()  # Connected
        mock_ha_client.get_areas.side_effect = HomeAssistantAPIError(
            "Areas unavailable", 503
        )

        tool_calls = server.mcp.tool.call_args_list
        list_areas_func = next(
            call[0][0]
            for call in tool_calls
            if hasattr(call[0][0], "__name__") and call[0][0].__name__ == "list_areas"
        )

        with pytest.raises(ValueError, match="Failed to list areas"):
            await list_areas_func()


class TestConsolidatedFindEntities:
    """Test the consolidated find_entities tool with spatial/area filtering.

    This replaces the old get_area_entities functionality with a more powerful
    and unified find_entities tool that supports area filtering.
    """

    @pytest.mark.asyncio
    async def test_find_entities_wildcard_all_entities(
        self, server_with_mocks, sample_states_data
    ):
        """Test find_entities with wildcard '*' returns all entities."""
        server, mock_ha_client = server_with_mocks
        mock_ha_client.session = Mock()
        mock_ha_client.get_all_states.return_value = sample_states_data

        tool_calls = server.mcp.tool.call_args_list
        find_entities_func = next(
            call[0][0]
            for call in tool_calls
            if hasattr(call[0][0], "__name__")
            and call[0][0].__name__ == "find_entities"
        )

        result = await find_entities_func("*")

        mock_ha_client.get_all_states.assert_called_once()
        parsed_result = json.loads(result)
        assert len(parsed_result) == 7  # All entities in sample data
        entity_ids = {entity["entity_id"] for entity in parsed_result}
        assert "light.living_room_light" in entity_ids
        assert "sensor.living_room_temperature" in entity_ids
        assert "sensor.bedroom_humidity" in entity_ids

    @pytest.mark.asyncio
    async def test_find_entities_area_filter_living_room(
        self,
        server_with_mocks,
        sample_areas_data,
        sample_devices_data,
        sample_entity_registry,
        sample_states_data,
    ):
        """Test find_entities with area filter for living room."""
        server, mock_ha_client = server_with_mocks
        mock_ha_client.session = Mock()
        mock_ha_client.get_all_states.return_value = sample_states_data
        mock_ha_client.get_areas.return_value = sample_areas_data
        mock_ha_client.get_devices.return_value = sample_devices_data
        mock_ha_client.get_entity_registry.return_value = sample_entity_registry

        tool_calls = server.mcp.tool.call_args_list
        find_entities_func = next(
            call[0][0]
            for call in tool_calls
            if hasattr(call[0][0], "__name__")
            and call[0][0].__name__ == "find_entities"
        )

        result = await find_entities_func("*", area="Living Room")

        # Verify all required API calls were made
        mock_ha_client.get_all_states.assert_called_once()
        mock_ha_client.get_areas.assert_called_once()
        mock_ha_client.get_devices.assert_called_once()
        mock_ha_client.get_entity_registry.assert_called_once()

        parsed_result = json.loads(result)
        # Should find all living room entities (light, temp sensor, motion sensor, switch)
        assert len(parsed_result) == 4
        entity_ids = {entity["entity_id"] for entity in parsed_result}
        assert "light.living_room_light" in entity_ids
        assert "sensor.living_room_temperature" in entity_ids
        assert "binary_sensor.living_room_motion" in entity_ids
        assert "switch.living_room_switch" in entity_ids

    @pytest.mark.asyncio
    async def test_find_entities_area_and_domain_filter(
        self,
        server_with_mocks,
        sample_areas_data,
        sample_devices_data,
        sample_entity_registry,
        sample_states_data,
    ):
        """Test find_entities with both area and domain filters."""
        server, mock_ha_client = server_with_mocks
        mock_ha_client.session = Mock()
        mock_ha_client.get_all_states.return_value = sample_states_data
        mock_ha_client.get_areas.return_value = sample_areas_data
        mock_ha_client.get_devices.return_value = sample_devices_data
        mock_ha_client.get_entity_registry.return_value = sample_entity_registry

        tool_calls = server.mcp.tool.call_args_list
        find_entities_func = next(
            call[0][0]
            for call in tool_calls
            if hasattr(call[0][0], "__name__")
            and call[0][0].__name__ == "find_entities"
        )

        result = await find_entities_func("*", area="Living Room", domain="sensor")

        parsed_result = json.loads(result)
        # Should find only living room sensors (sensor domain entities)
        # Note: binary_sensor is a different domain than sensor
        assert len(parsed_result) == 1
        entity_ids = {entity["entity_id"] for entity in parsed_result}
        assert "sensor.living_room_temperature" in entity_ids
        # binary_sensor is not in "sensor" domain, so it shouldn't match

    @pytest.mark.asyncio
    async def test_find_entities_all_filters_combined(
        self,
        server_with_mocks,
        sample_areas_data,
        sample_devices_data,
        sample_entity_registry,
        sample_states_data,
    ):
        """Test find_entities with all filters: area, domain, device_class, and name.

        Note: find_entities returns minimal fields by default.
        To verify device_class we use expand=["attributes"] to get full attributes.
        """
        server, mock_ha_client = server_with_mocks
        mock_ha_client.session = Mock()
        mock_ha_client.get_all_states.return_value = sample_states_data
        mock_ha_client.get_areas.return_value = sample_areas_data
        mock_ha_client.get_devices.return_value = sample_devices_data
        mock_ha_client.get_entity_registry.return_value = sample_entity_registry

        tool_calls = server.mcp.tool.call_args_list
        find_entities_func = next(
            call[0][0]
            for call in tool_calls
            if hasattr(call[0][0], "__name__")
            and call[0][0].__name__ == "find_entities"
        )

        result = await find_entities_func(
            "temperature",
            area="Kitchen",
            domain="sensor",
            device_class="temperature",
            expand=["attributes"],
        )

        parsed_result = json.loads(result)
        # Should find only the kitchen temperature sensor
        assert len(parsed_result) == 1
        assert parsed_result[0]["entity_id"] == "sensor.kitchen_temperature"
        assert parsed_result[0]["attributes"]["device_class"] == "temperature"

    @pytest.mark.asyncio
    async def test_find_entities_device_class_filter_only(
        self, server_with_mocks, sample_states_data
    ):
        """Test find_entities with device_class filter only."""
        server, mock_ha_client = server_with_mocks
        mock_ha_client.session = Mock()
        mock_ha_client.get_all_states.return_value = sample_states_data

        tool_calls = server.mcp.tool.call_args_list
        find_entities_func = next(
            call[0][0]
            for call in tool_calls
            if hasattr(call[0][0], "__name__")
            and call[0][0].__name__ == "find_entities"
        )

        result = await find_entities_func("*", device_class="temperature")

        parsed_result = json.loads(result)
        # Should find all temperature sensors
        assert len(parsed_result) == 2
        entity_ids = {entity["entity_id"] for entity in parsed_result}
        assert "sensor.living_room_temperature" in entity_ids
        assert "sensor.kitchen_temperature" in entity_ids

    @pytest.mark.asyncio
    async def test_find_entities_name_filter_with_friendly_name(
        self, server_with_mocks, sample_states_data
    ):
        """Test find_entities name filter matches friendly names."""
        server, mock_ha_client = server_with_mocks
        mock_ha_client.session = Mock()
        mock_ha_client.get_all_states.return_value = sample_states_data

        tool_calls = server.mcp.tool.call_args_list
        find_entities_func = next(
            call[0][0]
            for call in tool_calls
            if hasattr(call[0][0], "__name__")
            and call[0][0].__name__ == "find_entities"
        )

        result = await find_entities_func("Main Light")

        parsed_result = json.loads(result)
        # Should find the living room light by friendly name
        assert len(parsed_result) == 1
        assert parsed_result[0]["entity_id"] == "light.living_room_light"
        assert "Main Light" in parsed_result[0]["attributes"]["friendly_name"]

    @pytest.mark.asyncio
    async def test_find_entities_case_insensitive_area_name(
        self,
        server_with_mocks,
        sample_areas_data,
        sample_devices_data,
        sample_entity_registry,
        sample_states_data,
    ):
        """Test that area name matching is case insensitive."""
        server, mock_ha_client = server_with_mocks
        mock_ha_client.session = Mock()
        mock_ha_client.get_all_states.return_value = sample_states_data
        mock_ha_client.get_areas.return_value = sample_areas_data
        mock_ha_client.get_devices.return_value = sample_devices_data
        mock_ha_client.get_entity_registry.return_value = sample_entity_registry

        tool_calls = server.mcp.tool.call_args_list
        find_entities_func = next(
            call[0][0]
            for call in tool_calls
            if hasattr(call[0][0], "__name__")
            and call[0][0].__name__ == "find_entities"
        )

        # Use lowercase "living room" to match "Living Room"
        result = await find_entities_func("*", area="living room")

        parsed_result = json.loads(result)
        # Should find all living room entities despite case difference
        assert len(parsed_result) == 4

    @pytest.mark.asyncio
    async def test_find_entities_area_matches_area_id_slug(
        self,
        server_with_mocks,
        sample_areas_data,
        sample_devices_data,
        sample_entity_registry,
        sample_states_data,
    ):
        """area parameter should resolve when passed an area_id slug, not just display name."""
        server, mock_ha_client = server_with_mocks
        mock_ha_client.session = Mock()
        mock_ha_client.get_all_states.return_value = sample_states_data
        mock_ha_client.get_areas.return_value = sample_areas_data
        mock_ha_client.get_devices.return_value = sample_devices_data
        mock_ha_client.get_entity_registry.return_value = sample_entity_registry

        tool_calls = server.mcp.tool.call_args_list
        find_entities_func = next(
            call[0][0]
            for call in tool_calls
            if hasattr(call[0][0], "__name__")
            and call[0][0].__name__ == "find_entities"
        )

        result = await find_entities_func("*", area="living_room")

        parsed_result = json.loads(result)
        assert len(parsed_result) == 4

    @pytest.mark.asyncio
    async def test_find_entities_area_not_found(
        self, server_with_mocks, sample_areas_data, sample_states_data
    ):
        """Test find_entities with non-existent area."""
        server, mock_ha_client = server_with_mocks
        mock_ha_client.session = Mock()
        mock_ha_client.get_all_states.return_value = sample_states_data
        mock_ha_client.get_areas.return_value = sample_areas_data

        tool_calls = server.mcp.tool.call_args_list
        find_entities_func = next(
            call[0][0]
            for call in tool_calls
            if hasattr(call[0][0], "__name__")
            and call[0][0].__name__ == "find_entities"
        )

        with pytest.raises(ValueError, match="Area 'Nonexistent' not found"):
            await find_entities_func("*", area="Nonexistent")

    @pytest.mark.asyncio
    async def test_find_entities_auto_connects_when_not_connected(
        self,
        server_with_mocks,
        sample_areas_data,
        sample_devices_data,
        sample_entity_registry,
        sample_states_data,
    ):
        """Test that find_entities succeeds when initially disconnected.

        CONTRACT: Operation succeeds and returns filtered entities regardless
        of initial connection state. Tests WHAT (entities found), not HOW
        (connection established).
        """
        server, mock_ha_client = server_with_mocks
        mock_ha_client.session = None  # Start disconnected

        # Set up simple return values (no auto-connect simulation needed)
        mock_ha_client.get_all_states.return_value = sample_states_data
        mock_ha_client.get_areas.return_value = sample_areas_data
        mock_ha_client.get_devices.return_value = sample_devices_data
        mock_ha_client.get_entity_registry.return_value = sample_entity_registry

        tool_calls = server.mcp.tool.call_args_list
        find_entities_func = next(
            call[0][0]
            for call in tool_calls
            if hasattr(call[0][0], "__name__")
            and call[0][0].__name__ == "find_entities"
        )

        result = await find_entities_func("*", area="Kitchen")

        # Test the CONTRACT: operation succeeds with valid filtered entities
        entities = json.loads(result)
        assert isinstance(entities, list), "Result should be a list"
        # Verify entities from Kitchen area are returned
        kitchen_entities = [e for e in entities if e.get("entity_id")]
        assert len(kitchen_entities) > 0, "Should find entities in Kitchen"

    @pytest.mark.asyncio
    async def test_find_entities_no_entities_in_area(
        self, server_with_mocks, sample_areas_data, sample_states_data
    ):
        """Test find_entities for area with no entities."""
        server, mock_ha_client = server_with_mocks
        mock_ha_client.session = Mock()
        mock_ha_client.get_all_states.return_value = sample_states_data
        mock_ha_client.get_areas.return_value = sample_areas_data
        mock_ha_client.get_devices.return_value = []  # No devices in the area
        mock_ha_client.get_entity_registry.return_value = []

        tool_calls = server.mcp.tool.call_args_list
        find_entities_func = next(
            call[0][0]
            for call in tool_calls
            if hasattr(call[0][0], "__name__")
            and call[0][0].__name__ == "find_entities"
        )

        result = await find_entities_func("*", area="Kitchen")

        parsed_result = json.loads(result)
        assert len(parsed_result) == 0


class TestGetAreaDevices:
    """Test get_area_devices tool."""

    @pytest.mark.asyncio
    async def test_get_area_devices_auto_connects(
        self, server_with_mocks, sample_areas_data, sample_devices_data
    ):
        """Test that get_area_devices succeeds when initially disconnected.

        CONTRACT: Operation succeeds and returns area devices regardless of
        initial connection state. Tests WHAT (area devices retrieved), not HOW
        (connection established).
        """
        server, mock_ha_client = server_with_mocks
        mock_ha_client.session = None  # Start disconnected

        mock_ha_client.get_areas.return_value = sample_areas_data
        mock_ha_client.get_devices.return_value = sample_devices_data

        tool_calls = server.mcp.tool.call_args_list
        get_area_devices_func = next(
            call[0][0]
            for call in tool_calls
            if hasattr(call[0][0], "__name__")
            and call[0][0].__name__ == "get_area_devices"
        )

        result = await get_area_devices_func("Living Room")

        # Test the CONTRACT: operation succeeds with filtered devices
        parsed_result = json.loads(result)
        assert len(parsed_result) == 2, f"Expected 2 devices, got {len(parsed_result)}"
        device_ids = [device["id"] for device in parsed_result]
        assert "device1" in device_ids
        assert "device2" in device_ids

        # Verify API calls were made (outcomes, not connect() call)
        mock_ha_client.get_areas.assert_called_once()
        mock_ha_client.get_devices.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_area_devices_filters_correctly(
        self, server_with_mocks, sample_areas_data, sample_devices_data
    ):
        """Test that get_area_devices filters devices by area correctly."""
        server, mock_ha_client = server_with_mocks
        mock_ha_client.session = Mock()  # Already connected
        mock_ha_client.get_areas.return_value = sample_areas_data
        mock_ha_client.get_devices.return_value = sample_devices_data

        tool_calls = server.mcp.tool.call_args_list
        get_area_devices_func = next(
            call[0][0]
            for call in tool_calls
            if hasattr(call[0][0], "__name__")
            and call[0][0].__name__ == "get_area_devices"
        )

        # Test Kitchen area (should have only device3)
        result = await get_area_devices_func("Kitchen")

        parsed_result = json.loads(result)
        assert len(parsed_result) == 1
        assert parsed_result[0]["id"] == "device3"
        assert parsed_result[0]["name"] == "Kitchen Multi-Device"

    @pytest.mark.asyncio
    async def test_get_area_devices_case_insensitive(
        self, server_with_mocks, sample_areas_data, sample_devices_data
    ):
        """Test that area name matching is case insensitive."""
        server, mock_ha_client = server_with_mocks
        mock_ha_client.session = Mock()
        mock_ha_client.get_areas.return_value = sample_areas_data
        mock_ha_client.get_devices.return_value = sample_devices_data

        tool_calls = server.mcp.tool.call_args_list
        get_area_devices_func = next(
            call[0][0]
            for call in tool_calls
            if hasattr(call[0][0], "__name__")
            and call[0][0].__name__ == "get_area_devices"
        )

        # Use uppercase "KITCHEN" to match "Kitchen"
        result = await get_area_devices_func("KITCHEN")

        parsed_result = json.loads(result)
        assert len(parsed_result) == 1
        assert parsed_result[0]["id"] == "device3"

    @pytest.mark.asyncio
    async def test_get_area_devices_matches_area_id_slug(
        self, server_with_mocks, sample_areas_data, sample_devices_data
    ):
        """area_name parameter should resolve when passed an area_id slug."""
        server, mock_ha_client = server_with_mocks
        mock_ha_client.session = Mock()
        mock_ha_client.get_areas.return_value = sample_areas_data
        mock_ha_client.get_devices.return_value = sample_devices_data

        tool_calls = server.mcp.tool.call_args_list
        get_area_devices_func = next(
            call[0][0]
            for call in tool_calls
            if hasattr(call[0][0], "__name__")
            and call[0][0].__name__ == "get_area_devices"
        )

        result = await get_area_devices_func("kitchen")

        parsed_result = json.loads(result)
        assert len(parsed_result) == 1
        assert parsed_result[0]["id"] == "device3"

    @pytest.mark.asyncio
    async def test_get_area_devices_area_not_found(
        self, server_with_mocks, sample_areas_data
    ):
        """Test get_area_devices with non-existent area."""
        server, mock_ha_client = server_with_mocks
        mock_ha_client.session = Mock()
        mock_ha_client.get_areas.return_value = sample_areas_data

        tool_calls = server.mcp.tool.call_args_list
        get_area_devices_func = next(
            call[0][0]
            for call in tool_calls
            if hasattr(call[0][0], "__name__")
            and call[0][0].__name__ == "get_area_devices"
        )

        with pytest.raises(ValueError, match="Area 'Bathroom' not found"):
            await get_area_devices_func("Bathroom")

    @pytest.mark.asyncio
    async def test_get_area_devices_no_devices(
        self, server_with_mocks, sample_areas_data
    ):
        """Test get_area_devices for area with no devices."""
        server, mock_ha_client = server_with_mocks
        mock_ha_client.session = Mock()
        mock_ha_client.get_areas.return_value = sample_areas_data
        # Only devices without the requested area_id
        devices_without_bedroom = [
            d
            for d in [
                {
                    "id": "device1",
                    "area_id": "living_room",
                    "name": "Living Room Light",
                },
                {"id": "device3", "area_id": "kitchen", "name": "Kitchen Light"},
            ]
        ]
        mock_ha_client.get_devices.return_value = devices_without_bedroom

        tool_calls = server.mcp.tool.call_args_list
        get_area_devices_func = next(
            call[0][0]
            for call in tool_calls
            if hasattr(call[0][0], "__name__")
            and call[0][0].__name__ == "get_area_devices"
        )

        result = await get_area_devices_func("Master Bedroom")

        parsed_result = json.loads(result)
        assert len(parsed_result) == 0

    @pytest.mark.asyncio
    async def test_get_area_devices_connection_error(self, server_with_mocks):
        """Test get_area_devices handles connection errors."""
        server, mock_ha_client = server_with_mocks
        mock_ha_client.session = None
        mock_ha_client.connect.side_effect = HomeAssistantConnectionError(
            "Connection failed"
        )

        tool_calls = server.mcp.tool.call_args_list
        get_area_devices_func = next(
            call[0][0]
            for call in tool_calls
            if hasattr(call[0][0], "__name__")
            and call[0][0].__name__ == "get_area_devices"
        )

        with pytest.raises(ValueError, match="Failed to get area devices"):
            await get_area_devices_func("Living Room")


class TestSpatialToolsRegistration:
    """Test that spatial tools are properly registered."""

    def test_all_spatial_tools_registered(self):
        """Test that all expected spatial tools are registered."""

        # Track registered functions to make them accessible via call_args_list
        class ToolMock:
            def __init__(self):
                self.call_args_list = []
                self._mock = Mock()

            def __call__(self, *args, **kwargs):
                if args and callable(args[0]):
                    func = args[0]
                    self.call_args_list.append(((func,), {}))
                    return func
                else:

                    def decorator(func):
                        self.call_args_list.append(((func,), kwargs))
                        return func

                    return decorator

            @property
            def call_count(self):
                return len(self.call_args_list)

            def __getattr__(self, name):
                return getattr(self._mock, name)

        mock_mcp = Mock()
        mock_mcp.tool = ToolMock()
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
        register_spatial_tools(ctx)

        # Verify 2 spatial tools were registered (get_area_entities was removed)
        assert mock_mcp.tool.call_count == 2

        # Get the function names
        registered_functions = [
            call[0][0].__name__ for call in mock_mcp.tool.call_args_list
        ]

        expected_functions = ["list_areas", "get_area_devices"]

        assert set(registered_functions) == set(expected_functions)


class TestSpatialToolsConnectionHandling:
    """Critical tests for connection handling - the bug source."""

    @pytest.mark.asyncio
    async def test_all_spatial_tools_handle_no_session(self):
        """CRITICAL: Test that ALL spatial tools handle session=None correctly."""
        mock_ha_client = Mock()
        mock_ha_client.session = None  # The bug condition
        mock_ha_client.connect = AsyncMock()

        # Mock auto-connect behavior for all methods
        async def auto_connect_get_areas():
            if mock_ha_client.session is None:
                await mock_ha_client.connect()
                mock_ha_client.session = Mock()
            return []

        async def auto_connect_get_devices():
            if mock_ha_client.session is None:
                await mock_ha_client.connect()
                mock_ha_client.session = Mock()
            return []

        async def auto_connect_get_entity_registry():
            if mock_ha_client.session is None:
                await mock_ha_client.connect()
                mock_ha_client.session = Mock()
            return []

        async def auto_connect_get_all_states():
            if mock_ha_client.session is None:
                await mock_ha_client.connect()
                mock_ha_client.session = Mock()
            return []

        mock_ha_client.get_areas.side_effect = auto_connect_get_areas
        mock_ha_client.get_devices.side_effect = auto_connect_get_devices
        mock_ha_client.get_entity_registry.side_effect = (
            auto_connect_get_entity_registry
        )
        mock_ha_client.get_all_states.side_effect = auto_connect_get_all_states

        # Mock config for find_entities token limit
        mock_config = Mock(spec=ConfigurationManager)
        mock_config.get_tool_token_limit.return_value = None

        # Track registered functions to make them accessible via call_args_list
        class ToolMock:
            def __init__(self):
                self.call_args_list = []
                self._mock = Mock()

            def __call__(self, *args, **kwargs):
                if args and callable(args[0]):
                    func = args[0]
                    self.call_args_list.append(((func,), {}))
                    return func
                else:

                    def decorator(func):
                        self.call_args_list.append(((func,), kwargs))
                        return func

                    return decorator

            @property
            def call_count(self):
                return len(self.call_args_list)

            def __getattr__(self, name):
                return getattr(self._mock, name)

        mock_mcp = Mock()
        mock_mcp.tool = ToolMock()

        ctx = ToolContext(
            mcp=mock_mcp,
            ha_client=mock_ha_client,
            config=mock_config,
            logger=logging.getLogger(__name__),
        )
        register_spatial_tools(ctx)
        register_entity_tools(ctx)

        # Get all registered functions
        tool_calls = mock_mcp.tool.call_args_list
        tools = {call[0][0].__name__: call[0][0] for call in tool_calls}

        # Test list_areas
        await tools["list_areas"]()
        assert mock_ha_client.connect.call_count == 1

        # Reset for next test
        mock_ha_client.connect.reset_mock()
        mock_ha_client.session = None  # Reset session state

        # Test get_area_devices
        with pytest.raises(
            ValueError
        ):  # Will fail on area lookup, but should connect first
            await tools["get_area_devices"]("Test Area")
        assert mock_ha_client.connect.call_count == 1

        # Reset for next test
        mock_ha_client.connect.reset_mock()
        mock_ha_client.session = None  # Reset session state

        # Test find_entities (replaces get_area_entities)
        with pytest.raises(
            ValueError
        ):  # Will fail on area lookup, but should connect first
            await tools["find_entities"]("*", area="Test Area")
        assert mock_ha_client.connect.call_count == 1

    @pytest.mark.asyncio
    async def test_spatial_tools_preserve_existing_connection(self):
        """Test that spatial tools don't unnecessarily reconnect."""
        mock_ha_client = Mock()
        mock_ha_client.session = Mock()  # Already connected
        mock_ha_client.connect = AsyncMock()
        mock_ha_client.get_areas = AsyncMock(
            return_value=[{"area_id": "test", "name": "Test"}]
        )
        mock_ha_client.get_devices = AsyncMock(return_value=[])
        mock_ha_client.get_entity_registry = AsyncMock(return_value=[])
        mock_ha_client.get_all_states = AsyncMock(return_value=[])

        # Mock config for find_entities token limit
        mock_config = Mock(spec=ConfigurationManager)
        mock_config.get_tool_token_limit.return_value = None

        # Track registered functions to make them accessible via call_args_list
        class ToolMock:
            def __init__(self):
                self.call_args_list = []
                self._mock = Mock()

            def __call__(self, *args, **kwargs):
                if args and callable(args[0]):
                    func = args[0]
                    self.call_args_list.append(((func,), {}))
                    return func
                else:

                    def decorator(func):
                        self.call_args_list.append(((func,), kwargs))
                        return func

                    return decorator

            @property
            def call_count(self):
                return len(self.call_args_list)

            def __getattr__(self, name):
                return getattr(self._mock, name)

        mock_mcp = Mock()
        mock_mcp.tool = ToolMock()

        ctx = ToolContext(
            mcp=mock_mcp,
            ha_client=mock_ha_client,
            config=mock_config,
            logger=logging.getLogger(__name__),
        )
        register_spatial_tools(ctx)
        register_entity_tools(ctx)

        # Get all registered functions
        tool_calls = mock_mcp.tool.call_args_list
        tools = {call[0][0].__name__: call[0][0] for call in tool_calls}

        # Test list_areas
        await tools["list_areas"]()

        # Test get_area_devices
        await tools["get_area_devices"]("Test")

        # Test find_entities (replaces get_area_entities)
        await tools["find_entities"]("*", area="Test")

        # Should never have called connect since session exists
        mock_ha_client.connect.assert_not_called()
