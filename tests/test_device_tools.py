"""
Test suite for device management tools.

Tests the device-related operations: get_devices and get_device_entities.
Ensures proper device information retrieval and device-entity relationships.
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
from src.mcp_hass.tools import ToolContext, register_device_tools
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
    """Create server with mocked components for device tool testing."""
    server = MCPHomeAssistantServer()

    # Mock HA client - test connection handling
    mock_ha_client = Mock()
    mock_ha_client.session = None  # Initially not connected
    mock_ha_client.connect = AsyncMock()
    mock_ha_client.get_devices = AsyncMock()
    mock_ha_client.get_entity_registry = AsyncMock()
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

    # Create ToolContext and register device tools
    ctx = ToolContext(
        mcp=server.mcp,
        ha_client=mock_ha_client,
        config=mock_config,
        logger=logging.getLogger(__name__),
    )
    register_device_tools(ctx)

    return server, mock_ha_client


@pytest.fixture
def sample_devices_data():
    """Sample devices data from Home Assistant."""
    return [
        {
            "id": "device1_hue_bridge",
            "area_id": "living_room",
            "name": "Philips Hue Bridge",
            "model": "Hue Bridge 2.1",
            "manufacturer": "Signify Netherlands B.V.",
            "sw_version": "1.50.1950310030",
            "hw_version": "BSB002",
            "configuration_url": "http://X.X.X.X",
            "connections": [["mac", "00:17:88:01:02:03"]],
            "identifiers": [["hue", "001788010203"]],
            "entry_type": "service",
            "disabled_by": None,
        },
        {
            "id": "device2_smart_switch",
            "area_id": "kitchen",
            "name": "Kitchen Smart Switch",
            "model": "HS200",
            "manufacturer": "TP-Link",
            "sw_version": "1.0.6",
            "hw_version": "2.0",
            "configuration_url": None,
            "connections": [["wifi", "aa:bb:cc:dd:ee:ff"]],
            "identifiers": [["tplink", "smart_switch_001"]],
            "entry_type": "device",
            "disabled_by": None,
        },
        {
            "id": "device3_temperature_sensor",
            "area_id": "bedroom",
            "name": "Bedroom Temperature Sensor",
            "model": "SNZB-02",
            "manufacturer": "SONOFF",
            "sw_version": "2.0.0",
            "hw_version": "1.0",
            "configuration_url": None,
            "connections": [["zigbee", "0x00124b0024c34567"]],
            "identifiers": [["sonoff", "temp_sensor_bedroom"]],
            "entry_type": "device",
            "disabled_by": None,
        },
        {
            "id": "device4_disabled_device",
            "area_id": "garage",
            "name": "Old Garage Door Sensor",
            "model": "Legacy Model",
            "manufacturer": "Generic",
            "sw_version": None,
            "hw_version": None,
            "configuration_url": None,
            "connections": [],
            "identifiers": [["generic", "garage_sensor_old"]],
            "entry_type": "device",
            "disabled_by": "user",  # This device is disabled
        },
        {
            "id": "device5_no_area",
            "area_id": None,  # Device not assigned to any area
            "name": "Unassigned Smart Plug",
            "model": "HS100",
            "manufacturer": "TP-Link",
            "sw_version": "1.2.5",
            "hw_version": "1.0",
            "configuration_url": None,
            "connections": [["wifi", "11:22:33:44:55:66"]],
            "identifiers": [["tplink", "smart_plug_unassigned"]],
            "entry_type": "device",
            "disabled_by": None,
        },
    ]


@pytest.fixture
def sample_entity_registry():
    """Sample entity registry data showing device-entity relationships."""
    return [
        {
            "entity_id": "light.hue_color_lamp_1",
            "device_id": "device1_hue_bridge",
            "platform": "hue",
            "unique_id": "00:17:88:01:02:03:04:05-01",
            "area_id": "living_room",
            "config_entry_id": "config_entry_hue",
            "entity_category": None,
            "disabled_by": None,
        },
        {
            "entity_id": "light.hue_color_lamp_2",
            "device_id": "device1_hue_bridge",
            "platform": "hue",
            "unique_id": "00:17:88:01:02:03:04:05-02",
            "area_id": "living_room",
            "config_entry_id": "config_entry_hue",
            "entity_category": None,
            "disabled_by": None,
        },
        {
            "entity_id": "switch.kitchen_smart_switch",
            "device_id": "device2_smart_switch",
            "platform": "tplink",
            "unique_id": "smart_switch_001_switch",
            "area_id": "kitchen",
            "config_entry_id": "config_entry_tplink",
            "entity_category": None,
            "disabled_by": None,
        },
        {
            "entity_id": "sensor.kitchen_switch_power",
            "device_id": "device2_smart_switch",
            "platform": "tplink",
            "unique_id": "smart_switch_001_power",
            "area_id": "kitchen",
            "config_entry_id": "config_entry_tplink",
            "entity_category": "diagnostic",
            "disabled_by": None,
        },
        {
            "entity_id": "sensor.bedroom_temperature",
            "device_id": "device3_temperature_sensor",
            "platform": "sonoff",
            "unique_id": "temp_sensor_bedroom_temperature",
            "area_id": "bedroom",
            "config_entry_id": "config_entry_sonoff",
            "entity_category": None,
            "disabled_by": None,
        },
        {
            "entity_id": "sensor.bedroom_humidity",
            "device_id": "device3_temperature_sensor",
            "platform": "sonoff",
            "unique_id": "temp_sensor_bedroom_humidity",
            "area_id": "bedroom",
            "config_entry_id": "config_entry_sonoff",
            "entity_category": None,
            "disabled_by": None,
        },
        {
            "entity_id": "binary_sensor.garage_door_old",
            "device_id": "device4_disabled_device",
            "platform": "generic",
            "unique_id": "garage_sensor_old_binary",
            "area_id": "garage",
            "config_entry_id": "config_entry_generic",
            "entity_category": None,
            "disabled_by": "user",  # This entity is also disabled
        },
        {
            "entity_id": "switch.unassigned_smart_plug",
            "device_id": "device5_no_area",
            "platform": "tplink",
            "unique_id": "smart_plug_unassigned_switch",
            "area_id": None,
            "config_entry_id": "config_entry_tplink_2",
            "entity_category": None,
            "disabled_by": None,
        },
    ]


class TestGetDeviceEntities:
    """Test get_device_entities tool."""

    @pytest.mark.asyncio
    async def test_get_device_entities_auto_connects(
        self, server_with_mocks, sample_entity_registry
    ):
        """Test that get_device_entities succeeds when initially disconnected.

        CONTRACT: Operation succeeds and returns device entities regardless of
        initial connection state. Tests WHAT (entities retrieved), not HOW
        (connection established).
        """
        server, mock_ha_client = server_with_mocks
        mock_ha_client.session = None  # Start disconnected
        mock_ha_client.get_entity_registry.return_value = sample_entity_registry

        get_device_entities_func = server.mcp._test_tools["get_device_entities"]

        result = await get_device_entities_func("device1_hue_bridge")

        # Test the CONTRACT: operation succeeds with valid entity data
        entities = json.loads(result)
        assert len(entities) == 2, f"Expected 2 entities, got {len(entities)}"
        assert entities[0]["entity_id"] == "light.hue_color_lamp_1"
        assert entities[1]["entity_id"] == "light.hue_color_lamp_2"

        # Verify API call was made
        mock_ha_client.get_entity_registry.assert_called_once()

        # Verify result contains entities for the Hue Bridge
        parsed_result = json.loads(result)
        assert len(parsed_result) == 2  # Two Hue lights
        entity_ids = [entity["entity_id"] for entity in parsed_result]
        assert "light.hue_color_lamp_1" in entity_ids
        assert "light.hue_color_lamp_2" in entity_ids

    @pytest.mark.asyncio
    async def test_get_device_entities_already_connected(
        self, server_with_mocks, sample_entity_registry
    ):
        """Test get_device_entities when already connected."""
        server, mock_ha_client = server_with_mocks
        mock_ha_client.session = Mock()  # Already connected
        mock_ha_client.get_entity_registry.return_value = sample_entity_registry

        get_device_entities_func = server.mcp._test_tools["get_device_entities"]

        result = await get_device_entities_func("device2_smart_switch")

        # Should NOT call connect since already connected
        mock_ha_client.connect.assert_not_called()

        # Verify result contains entities for the smart switch
        parsed_result = json.loads(result)
        assert len(parsed_result) == 2  # Switch and power sensor
        entity_ids = [entity["entity_id"] for entity in parsed_result]
        assert "switch.kitchen_smart_switch" in entity_ids
        assert "sensor.kitchen_switch_power" in entity_ids

    @pytest.mark.asyncio
    async def test_get_device_entities_single_entity_device(
        self, server_with_mocks, sample_entity_registry
    ):
        """Test get_device_entities for device with single entity."""
        server, mock_ha_client = server_with_mocks
        mock_ha_client.session = Mock()
        mock_ha_client.get_entity_registry.return_value = sample_entity_registry

        get_device_entities_func = server.mcp._test_tools["get_device_entities"]

        result = await get_device_entities_func("device5_no_area")

        parsed_result = json.loads(result)
        assert len(parsed_result) == 1
        assert parsed_result[0]["entity_id"] == "switch.unassigned_smart_plug"
        assert parsed_result[0]["area_id"] is None  # No area assigned

    @pytest.mark.asyncio
    async def test_get_device_entities_multi_sensor_device(
        self, server_with_mocks, sample_entity_registry
    ):
        """Test get_device_entities for device with multiple sensor entities."""
        server, mock_ha_client = server_with_mocks
        mock_ha_client.session = Mock()
        mock_ha_client.get_entity_registry.return_value = sample_entity_registry

        get_device_entities_func = server.mcp._test_tools["get_device_entities"]

        result = await get_device_entities_func("device3_temperature_sensor")

        parsed_result = json.loads(result)
        assert len(parsed_result) == 2  # Temperature and humidity sensors
        entity_ids = [entity["entity_id"] for entity in parsed_result]
        assert "sensor.bedroom_temperature" in entity_ids
        assert "sensor.bedroom_humidity" in entity_ids

        # Verify entity details are preserved
        temp_entity = next(
            e for e in parsed_result if e["entity_id"] == "sensor.bedroom_temperature"
        )
        assert temp_entity["platform"] == "sonoff"
        assert temp_entity["area_id"] == "bedroom"
        assert temp_entity["disabled_by"] is None

    @pytest.mark.asyncio
    async def test_get_device_entities_includes_disabled_entities(
        self, server_with_mocks, sample_entity_registry
    ):
        """Test that get_device_entities includes disabled entities."""
        server, mock_ha_client = server_with_mocks
        mock_ha_client.session = Mock()
        mock_ha_client.get_entity_registry.return_value = sample_entity_registry

        get_device_entities_func = server.mcp._test_tools["get_device_entities"]

        result = await get_device_entities_func("device4_disabled_device")

        parsed_result = json.loads(result)
        assert len(parsed_result) == 1
        assert parsed_result[0]["entity_id"] == "binary_sensor.garage_door_old"
        assert (
            parsed_result[0]["disabled_by"] == "user"
        )  # Should include disabled status

    @pytest.mark.asyncio
    async def test_get_device_entities_nonexistent_device(
        self, server_with_mocks, sample_entity_registry
    ):
        """Test get_device_entities for non-existent device."""
        server, mock_ha_client = server_with_mocks
        mock_ha_client.session = Mock()
        mock_ha_client.get_entity_registry.return_value = sample_entity_registry

        get_device_entities_func = server.mcp._test_tools["get_device_entities"]

        result = await get_device_entities_func("nonexistent_device_id")

        parsed_result = json.loads(result)
        assert parsed_result == []  # No entities for non-existent device

    @pytest.mark.asyncio
    async def test_get_device_entities_empty_device_id(
        self, server_with_mocks, sample_entity_registry
    ):
        """Test get_device_entities with empty device ID."""
        server, mock_ha_client = server_with_mocks
        mock_ha_client.session = Mock()
        mock_ha_client.get_entity_registry.return_value = sample_entity_registry

        get_device_entities_func = server.mcp._test_tools["get_device_entities"]

        result = await get_device_entities_func("")

        parsed_result = json.loads(result)
        assert parsed_result == []  # No entities for empty device ID

    @pytest.mark.asyncio
    async def test_get_device_entities_preserves_entity_metadata(
        self, server_with_mocks, sample_entity_registry
    ):
        """Test that get_device_entities preserves all entity metadata."""
        server, mock_ha_client = server_with_mocks
        mock_ha_client.session = Mock()
        mock_ha_client.get_entity_registry.return_value = sample_entity_registry

        get_device_entities_func = server.mcp._test_tools["get_device_entities"]

        result = await get_device_entities_func("device2_smart_switch")

        parsed_result = json.loads(result)

        # Find the diagnostic entity (power sensor)
        power_entity = next(
            e for e in parsed_result if e.get("entity_category") == "diagnostic"
        )
        assert power_entity["entity_id"] == "sensor.kitchen_switch_power"
        assert power_entity["platform"] == "tplink"
        assert power_entity["unique_id"] == "smart_switch_001_power"
        assert power_entity["config_entry_id"] == "config_entry_tplink"

        # Find the main switch entity
        switch_entity = next(
            e for e in parsed_result if e.get("entity_category") is None
        )
        assert switch_entity["entity_id"] == "switch.kitchen_smart_switch"
        assert switch_entity["entity_category"] is None

    @pytest.mark.asyncio
    async def test_get_device_entities_connection_error(self, server_with_mocks):
        """Test get_device_entities handles connection errors."""
        server, mock_ha_client = server_with_mocks
        mock_ha_client.session = None
        mock_ha_client.connect.side_effect = HomeAssistantConnectionError(
            "Connection failed"
        )

        get_device_entities_func = server.mcp._test_tools["get_device_entities"]

        with pytest.raises(ValueError, match="Failed to get device entities"):
            await get_device_entities_func("device1")

    @pytest.mark.asyncio
    async def test_get_device_entities_api_error(self, server_with_mocks):
        """Test get_device_entities with API error."""
        server, mock_ha_client = server_with_mocks
        mock_ha_client.session = Mock()  # Connected
        mock_ha_client.get_entity_registry.side_effect = HomeAssistantAPIError(
            "Registry unavailable", 503
        )

        get_device_entities_func = server.mcp._test_tools["get_device_entities"]

        with pytest.raises(ValueError, match="Failed to get device entities"):
            await get_device_entities_func("device1")


class TestDeviceToolsRegistration:
    """Test that device tools are properly registered."""

    def test_all_device_tools_registered(self):
        """Test that all expected device tools are registered."""
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
        register_device_tools(ctx)

        expected_functions = ["find_devices", "get_device_entities"]
        assert set(registered_tools.keys()) == set(expected_functions)


class TestDeviceToolsConnectionHandling:
    """Test connection handling in device tools."""

    @pytest.mark.asyncio
    async def test_device_tools_handle_connection_consistently(self):
        """Test that device tool handles connection properly."""
        mock_ha_client = Mock()
        mock_ha_client.session = None
        mock_ha_client.connect = AsyncMock()
        mock_ha_client.get_entity_registry = AsyncMock(return_value=[])

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
        register_device_tools(ctx)

        await registered_tools["get_device_entities"]("test_device")
        assert mock_ha_client.connect.call_count == 1

    @pytest.mark.asyncio
    async def test_device_tools_respect_existing_connection(self):
        """Test that device tool doesn't reconnect when already connected."""
        mock_ha_client = Mock()
        mock_ha_client.session = Mock()
        mock_ha_client.connect = AsyncMock()
        mock_ha_client.get_entity_registry = AsyncMock(return_value=[])

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
        register_device_tools(ctx)

        await registered_tools["get_device_entities"]("test_device")

        mock_ha_client.connect.assert_not_called()
