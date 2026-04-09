"""
Test suite for find_devices tool.

Tests the device discovery tool with comprehensive filtering scenarios
including manufacturer, model, area, name matching, and field selection.
"""

import logging

import pytest
import json
from unittest.mock import Mock

from src.mcp_hass.server import MCPHomeAssistantServer
from src.mcp_hass.tools import ToolContext, register_device_tools


@pytest.fixture
def server_with_mocks(mock_config, mock_ha_client):
    """Create server with mocked components for find_devices testing."""
    server = MCPHomeAssistantServer()
    server.config = mock_config
    server.ha_client = mock_ha_client

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

    # Create ToolContext and register device tools
    ctx = ToolContext(
        mcp=server.mcp,
        ha_client=mock_ha_client,
        config=mock_config,
        logger=logging.getLogger(__name__),
    )
    register_device_tools(ctx)

    return server


@pytest.fixture
def sample_devices():
    """Sample device data from Home Assistant."""
    return [
        {
            "id": "device1",
            "name": "Living Room Hue Bridge",
            "name_by_user": None,
            "area_id": "living_room",
            "manufacturer": "Signify Netherlands B.V.",
            "model": "Philips Hue Bridge 2.1",
            "model_id": "BSB002",
            "sw_version": "1.50.1950310030",
            "hw_version": "2.1",
            "identifiers": [["hue", "001788010203"]],
            "connections": [["mac", "00:17:88:01:02:03"]],
        },
        {
            "id": "device2",
            "name": "Kitchen Smart Plug",
            "name_by_user": "Coffee Maker Plug",
            "area_id": "kitchen",
            "manufacturer": "TP-Link",
            "model": "HS110",
            "model_id": "HS110(US)",
            "sw_version": "1.2.6",
            "hw_version": "2.0",
            "identifiers": [["tplink", "plug_001"]],
            "connections": [["wifi", "aa:bb:cc:dd:ee:ff"]],
        },
        {
            "id": "device3",
            "name": "Bedroom Ecobee Thermostat",
            "name_by_user": None,
            "area_id": "bedroom",
            "manufacturer": "Ecobee",
            "model": "ecobee3 Lite",
            "model_id": "EB-STATE3LT-02",
            "sw_version": "4.5.81",
            "hw_version": "1.0",
            "identifiers": [["ecobee", "123456789"]],
            "connections": [["wifi", "11:22:33:44:55:66"]],
        },
        {
            "id": "device4",
            "name": "Office Light",
            "name_by_user": None,
            "area_id": "office",
            "manufacturer": "Signify Netherlands B.V.",
            "model": "Hue White Ambiance",
            "model_id": "LWA001",
            "sw_version": None,
            "hw_version": None,
            "identifiers": [["hue", "light_office_001"]],
            "connections": [],
        },
        {
            "id": "device5",
            "name": "Unassigned Sensor",
            "name_by_user": None,
            "area_id": None,
            "manufacturer": "Generic",
            "model": "Temperature Sensor",
            "model_id": "TEMP-01",
            "sw_version": None,
            "hw_version": None,
            "identifiers": [["generic", "temp_001"]],
            "connections": [],
        },
    ]


@pytest.fixture
def sample_entity_registry():
    """Sample entity registry for device-entity mapping."""
    return [
        {"entity_id": "light.living_room_1", "device_id": "device1"},
        {"entity_id": "light.living_room_2", "device_id": "device1"},
        {"entity_id": "switch.coffee_maker", "device_id": "device2"},
        {"entity_id": "sensor.coffee_maker_power", "device_id": "device2"},
        {"entity_id": "climate.bedroom", "device_id": "device3"},
        {"entity_id": "sensor.bedroom_temperature", "device_id": "device3"},
        {"entity_id": "light.office_desk", "device_id": "device4"},
        {"entity_id": "sensor.unassigned_temp", "device_id": "device5"},
    ]


@pytest.fixture
def sample_states():
    """Sample entity states for full entity expansion."""
    return [
        {
            "entity_id": "light.living_room_1",
            "state": "on",
            "attributes": {"friendly_name": "Living Room Light 1", "brightness": 255},
        },
        {
            "entity_id": "light.living_room_2",
            "state": "off",
            "attributes": {"friendly_name": "Living Room Light 2"},
        },
        {
            "entity_id": "switch.coffee_maker",
            "state": "on",
            "attributes": {"friendly_name": "Coffee Maker"},
        },
        {
            "entity_id": "sensor.coffee_maker_power",
            "state": "150",
            "attributes": {
                "friendly_name": "Coffee Maker Power",
                "unit_of_measurement": "W",
            },
        },
        {
            "entity_id": "climate.bedroom",
            "state": "heat",
            "attributes": {"friendly_name": "Bedroom Thermostat", "temperature": 72},
        },
        {
            "entity_id": "sensor.bedroom_temperature",
            "state": "72.5",
            "attributes": {
                "friendly_name": "Bedroom Temperature",
                "unit_of_measurement": "°F",
            },
        },
        {
            "entity_id": "light.office_desk",
            "state": "on",
            "attributes": {"friendly_name": "Office Desk Light"},
        },
        {
            "entity_id": "sensor.unassigned_temp",
            "state": "68",
            "attributes": {
                "friendly_name": "Unassigned Temperature",
                "unit_of_measurement": "°F",
            },
        },
    ]


@pytest.fixture
def sample_areas():
    """Sample areas data."""
    return [
        {"area_id": "living_room", "name": "Living Room"},
        {"area_id": "kitchen", "name": "Kitchen"},
        {"area_id": "bedroom", "name": "Bedroom"},
        {"area_id": "office", "name": "Office"},
    ]


class TestFindDevicesBasicFiltering:
    """Test basic filtering capabilities of find_devices."""

    @pytest.mark.asyncio
    async def test_find_all_devices_wildcard(
        self, server_with_mocks, sample_devices, sample_entity_registry, sample_states
    ):
        """Test find_devices with wildcard returns all devices with minimal entities."""
        server = server_with_mocks
        server.ha_client.get_devices.return_value = sample_devices
        server.ha_client.get_entity_registry.return_value = sample_entity_registry
        server.ha_client.get_all_states.return_value = sample_states

        # Get find_devices function
        find_devices_func = server.mcp._test_tools["find_devices"]

        result = await find_devices_func(name="*")

        devices = json.loads(result)
        assert len(devices) == 5

        # Verify minimal entity structure
        for device in devices:
            assert "id" in device
            assert "name" in device
            assert "area_id" in device
            assert "entities" in device

            # Entities should be minimal (entity_id + friendly_name only)
            for entity in device["entities"]:
                assert "entity_id" in entity
                assert "attributes" in entity
                assert "friendly_name" in entity["attributes"]
                assert len(entity["attributes"]) == 1  # Only friendly_name

    @pytest.mark.asyncio
    async def test_find_devices_by_manufacturer(
        self, server_with_mocks, sample_devices, sample_entity_registry, sample_states
    ):
        """Test filtering devices by manufacturer."""
        server = server_with_mocks
        server.ha_client.get_devices.return_value = sample_devices
        server.ha_client.get_entity_registry.return_value = sample_entity_registry
        server.ha_client.get_all_states.return_value = sample_states

        find_devices_func = server.mcp._test_tools["find_devices"]

        result = await find_devices_func(manufacturer="Signify")

        devices = json.loads(result)
        assert len(devices) == 2  # Hue Bridge and Hue light
        assert all(
            "Signify" in d["name"] or d["id"] in ["device1", "device4"] for d in devices
        )

    @pytest.mark.asyncio
    async def test_find_devices_by_model(
        self, server_with_mocks, sample_devices, sample_entity_registry, sample_states
    ):
        """Test filtering devices by model."""
        server = server_with_mocks
        server.ha_client.get_devices.return_value = sample_devices
        server.ha_client.get_entity_registry.return_value = sample_entity_registry
        server.ha_client.get_all_states.return_value = sample_states

        find_devices_func = server.mcp._test_tools["find_devices"]

        result = await find_devices_func(model="ecobee")

        devices = json.loads(result)
        assert len(devices) == 1
        assert devices[0]["id"] == "device3"

    @pytest.mark.asyncio
    async def test_find_devices_by_area(
        self,
        server_with_mocks,
        sample_devices,
        sample_entity_registry,
        sample_states,
        sample_areas,
    ):
        """Test filtering devices by area."""
        server = server_with_mocks
        server.ha_client.get_devices.return_value = sample_devices
        server.ha_client.get_entity_registry.return_value = sample_entity_registry
        server.ha_client.get_all_states.return_value = sample_states
        server.ha_client.get_areas.return_value = sample_areas

        find_devices_func = server.mcp._test_tools["find_devices"]

        result = await find_devices_func(area="Kitchen")

        devices = json.loads(result)
        assert len(devices) == 1
        assert devices[0]["id"] == "device2"
        assert devices[0]["area_id"] == "kitchen"

    @pytest.mark.asyncio
    async def test_find_devices_by_name_substring(
        self, server_with_mocks, sample_devices, sample_entity_registry, sample_states
    ):
        """Test filtering devices by name substring."""
        server = server_with_mocks
        server.ha_client.get_devices.return_value = sample_devices
        server.ha_client.get_entity_registry.return_value = sample_entity_registry
        server.ha_client.get_all_states.return_value = sample_states

        find_devices_func = server.mcp._test_tools["find_devices"]

        result = await find_devices_func(name="Bedroom")

        devices = json.loads(result)
        assert len(devices) == 1
        assert devices[0]["id"] == "device3"

    @pytest.mark.asyncio
    async def test_find_devices_by_user_name(
        self, server_with_mocks, sample_devices, sample_entity_registry, sample_states
    ):
        """Test filtering devices by user-assigned name."""
        server = server_with_mocks
        server.ha_client.get_devices.return_value = sample_devices
        server.ha_client.get_entity_registry.return_value = sample_entity_registry
        server.ha_client.get_all_states.return_value = sample_states

        find_devices_func = server.mcp._test_tools["find_devices"]

        result = await find_devices_func(name="Coffee")

        devices = json.loads(result)
        assert len(devices) == 1
        assert devices[0]["id"] == "device2"
        assert devices[0]["name"] == "Coffee Maker Plug"


class TestFindDevicesFieldSelection:
    """Test select and expand parameters for field selection."""

    @pytest.mark.asyncio
    async def test_find_devices_with_select_fields(
        self, server_with_mocks, sample_devices, sample_entity_registry, sample_states
    ):
        """Test selecting additional scalar fields."""
        server = server_with_mocks
        server.ha_client.get_devices.return_value = sample_devices
        server.ha_client.get_entity_registry.return_value = sample_entity_registry
        server.ha_client.get_all_states.return_value = sample_states

        find_devices_func = server.mcp._test_tools["find_devices"]

        result = await find_devices_func(
            manufacturer="Ecobee", select=["manufacturer", "model", "sw_version"]
        )

        devices = json.loads(result)
        assert len(devices) == 1
        device = devices[0]

        assert device["manufacturer"] == "Ecobee"
        assert device["model"] == "ecobee3 Lite"
        assert device["sw_version"] == "4.5.81"

    @pytest.mark.asyncio
    async def test_find_devices_with_expand_entities(
        self, server_with_mocks, sample_devices, sample_entity_registry, sample_states
    ):
        """Test expanding entities to full state data."""
        server = server_with_mocks
        server.ha_client.get_devices.return_value = sample_devices
        server.ha_client.get_entity_registry.return_value = sample_entity_registry
        server.ha_client.get_all_states.return_value = sample_states

        find_devices_func = server.mcp._test_tools["find_devices"]

        result = await find_devices_func(model="HS110", expand=["entities"])

        devices = json.loads(result)
        assert len(devices) == 1
        device = devices[0]

        # Entities should be full state objects
        assert len(device["entities"]) == 2
        for entity in device["entities"]:
            assert "state" in entity
            assert "attributes" in entity
            # At minimum should have state field (full expansion)
            # Some entities may only have friendly_name in attributes
        # Verify at least one has multiple attributes (the power sensor)
        power_entity = next(
            e for e in device["entities"] if "power" in e.get("entity_id", "")
        )
        assert len(power_entity["attributes"]) > 1

    @pytest.mark.asyncio
    async def test_find_devices_with_expand_identifiers(
        self, server_with_mocks, sample_devices, sample_entity_registry, sample_states
    ):
        """Test expanding identifiers."""
        server = server_with_mocks
        server.ha_client.get_devices.return_value = sample_devices
        server.ha_client.get_entity_registry.return_value = sample_entity_registry
        server.ha_client.get_all_states.return_value = sample_states

        find_devices_func = server.mcp._test_tools["find_devices"]

        result = await find_devices_func(manufacturer="TP-Link", expand=["identifiers"])

        devices = json.loads(result)
        assert len(devices) == 1
        device = devices[0]

        assert "identifiers" in device
        assert device["identifiers"] == [["tplink", "plug_001"]]

    @pytest.mark.asyncio
    async def test_find_devices_with_expand_connections(
        self, server_with_mocks, sample_devices, sample_entity_registry, sample_states
    ):
        """Test expanding connections."""
        server = server_with_mocks
        server.ha_client.get_devices.return_value = sample_devices
        server.ha_client.get_entity_registry.return_value = sample_entity_registry
        server.ha_client.get_all_states.return_value = sample_states

        find_devices_func = server.mcp._test_tools["find_devices"]

        result = await find_devices_func(name="Hue Bridge", expand=["connections"])

        devices = json.loads(result)
        assert len(devices) == 1
        device = devices[0]

        assert "connections" in device
        assert device["connections"] == [["mac", "00:17:88:01:02:03"]]


class TestFindDevicesEdgeCases:
    """Test edge cases and error conditions."""

    @pytest.mark.asyncio
    async def test_find_devices_no_matches(
        self, server_with_mocks, sample_devices, sample_entity_registry, sample_states
    ):
        """Test find_devices with no matching devices."""
        server = server_with_mocks
        server.ha_client.get_devices.return_value = sample_devices
        server.ha_client.get_entity_registry.return_value = sample_entity_registry
        server.ha_client.get_all_states.return_value = sample_states

        find_devices_func = server.mcp._test_tools["find_devices"]

        result = await find_devices_func(manufacturer="NonExistent")

        devices = json.loads(result)
        assert devices == []

    @pytest.mark.asyncio
    async def test_find_devices_invalid_area(
        self,
        server_with_mocks,
        sample_devices,
        sample_entity_registry,
        sample_states,
        sample_areas,
    ):
        """Test find_devices with invalid area name."""
        server = server_with_mocks
        server.ha_client.get_devices.return_value = sample_devices
        server.ha_client.get_entity_registry.return_value = sample_entity_registry
        server.ha_client.get_all_states.return_value = sample_states
        server.ha_client.get_areas.return_value = sample_areas

        find_devices_func = server.mcp._test_tools["find_devices"]

        with pytest.raises(ValueError, match="Area 'InvalidArea' not found"):
            await find_devices_func(area="InvalidArea")

    @pytest.mark.asyncio
    async def test_find_devices_device_without_entities(
        self, server_with_mocks, sample_devices, sample_states
    ):
        """Test device that has no entities."""
        server = server_with_mocks
        server.ha_client.get_devices.return_value = sample_devices
        server.ha_client.get_entity_registry.return_value = []  # No entities
        server.ha_client.get_all_states.return_value = sample_states

        find_devices_func = server.mcp._test_tools["find_devices"]

        result = await find_devices_func(name="*")

        devices = json.loads(result)
        assert len(devices) == 5
        # All devices should have empty entities list
        for device in devices:
            assert device["entities"] == []

    @pytest.mark.asyncio
    async def test_find_devices_combined_filters(
        self,
        server_with_mocks,
        sample_devices,
        sample_entity_registry,
        sample_states,
        sample_areas,
    ):
        """Test combining multiple filters."""
        server = server_with_mocks
        server.ha_client.get_devices.return_value = sample_devices
        server.ha_client.get_entity_registry.return_value = sample_entity_registry
        server.ha_client.get_all_states.return_value = sample_states
        server.ha_client.get_areas.return_value = sample_areas

        find_devices_func = server.mcp._test_tools["find_devices"]

        result = await find_devices_func(manufacturer="Signify", area="Office")

        devices = json.loads(result)
        assert len(devices) == 1
        assert devices[0]["id"] == "device4"

    @pytest.mark.asyncio
    async def test_find_devices_unassigned_area(
        self, server_with_mocks, sample_devices, sample_entity_registry, sample_states
    ):
        """Test finding devices not assigned to any area."""
        server = server_with_mocks
        server.ha_client.get_devices.return_value = sample_devices
        server.ha_client.get_entity_registry.return_value = sample_entity_registry
        server.ha_client.get_all_states.return_value = sample_states

        find_devices_func = server.mcp._test_tools["find_devices"]

        result = await find_devices_func(name="Unassigned")

        devices = json.loads(result)
        assert len(devices) == 1
        assert devices[0]["id"] == "device5"
        assert devices[0]["area_id"] is None


class TestFindDevicesTokenLimits:
    """Test token limit enforcement."""

    @pytest.mark.asyncio
    async def test_find_devices_exceeds_token_limit(
        self, server_with_mocks, sample_devices, sample_entity_registry, sample_states
    ):
        """Test that find_devices enforces token limits."""
        server = server_with_mocks
        server.config.get_tool_token_limit.return_value = 10  # Very low limit
        server.ha_client.get_devices.return_value = sample_devices
        server.ha_client.get_entity_registry.return_value = sample_entity_registry
        server.ha_client.get_all_states.return_value = sample_states

        find_devices_func = server.mcp._test_tools["find_devices"]

        result = await find_devices_func(name="*")

        response = json.loads(result)
        assert "error" in response
        assert "token limit" in response["error"].lower()
        assert response["token_count"] > 10

    @pytest.mark.asyncio
    async def test_find_devices_within_token_limit(
        self, server_with_mocks, sample_devices, sample_entity_registry, sample_states
    ):
        """Test that find_devices succeeds within token limits."""
        server = server_with_mocks
        server.config.get_tool_token_limit.return_value = 100000  # High limit
        server.ha_client.get_devices.return_value = sample_devices
        server.ha_client.get_entity_registry.return_value = sample_entity_registry
        server.ha_client.get_all_states.return_value = sample_states

        find_devices_func = server.mcp._test_tools["find_devices"]

        result = await find_devices_func(name="*")

        devices = json.loads(result)
        assert isinstance(devices, list)
        assert len(devices) == 5
