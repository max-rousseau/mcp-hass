"""
Comprehensive test suite for the enhanced find_entities tool.

This test file focuses on the NEW consolidated find_entities functionality
that replaces the old get_area_entities tool and extends the original
find_entities with powerful filtering capabilities.

NEW FEATURES TESTED:
- Wildcard "*" matching all entities
- Area filtering via area name
- Device class filtering
- Combined filtering with all parameters
- Performance with large entity sets
- Error handling for invalid parameters
"""

import logging

import pytest
import json
from unittest.mock import AsyncMock, Mock

from src.mcp_hass.server import MCPHomeAssistantServer
from src.mcp_hass.ha_client.exceptions import (
    HomeAssistantAPIError,
)
from src.mcp_hass.tools import ToolContext, register_entity_tools
from src.mcp_hass.config import ConfigurationManager


@pytest.fixture
def server_with_enhanced_mocks():
    """Create server with enhanced mocking for comprehensive find_entities testing."""
    server = MCPHomeAssistantServer()

    # Mock config manager
    mock_config = Mock(spec=ConfigurationManager)
    mock_config.get_tool_token_limit.return_value = 100000
    server.config = mock_config

    # Mock HA client with all required methods
    mock_ha_client = Mock()
    mock_ha_client.session = Mock()  # Connected by default
    mock_ha_client.connect = AsyncMock()
    mock_ha_client.get_all_states = AsyncMock()
    mock_ha_client.get_areas = AsyncMock()
    mock_ha_client.get_devices = AsyncMock()
    mock_ha_client.get_entity_registry = AsyncMock()
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
def comprehensive_areas_data():
    """Comprehensive areas data for testing."""
    return [
        {"area_id": "living_room", "name": "Living Room", "picture": None},
        {"area_id": "kitchen", "name": "Kitchen", "picture": None},
        {"area_id": "master_bedroom", "name": "Master Bedroom", "picture": None},
        {"area_id": "office", "name": "Home Office", "picture": None},
        {"area_id": "garage", "name": "Garage", "picture": None},
    ]


@pytest.fixture
def comprehensive_devices_data():
    """Comprehensive devices data for testing."""
    return [
        {"id": "hue_bridge", "area_id": "living_room", "name": "Hue Bridge"},
        {
            "id": "living_sensor",
            "area_id": "living_room",
            "name": "Living Multi-Sensor",
        },
        {"id": "kitchen_hub", "area_id": "kitchen", "name": "Kitchen Smart Hub"},
        {
            "id": "bedroom_climate",
            "area_id": "master_bedroom",
            "name": "Bedroom Climate",
        },
        {"id": "office_pc", "area_id": "office", "name": "Office Computer"},
        {"id": "garage_door", "area_id": "garage", "name": "Garage Door Controller"},
        {"id": "floating_device", "area_id": None, "name": "Unassigned Device"},
    ]


@pytest.fixture
def comprehensive_entity_registry():
    """Comprehensive entity registry mapping entities to devices."""
    return [
        # Living Room entities
        {"entity_id": "light.living_room_main", "device_id": "hue_bridge"},
        {"entity_id": "light.living_room_accent", "device_id": "hue_bridge"},
        {"entity_id": "sensor.living_room_temperature", "device_id": "living_sensor"},
        {"entity_id": "sensor.living_room_humidity", "device_id": "living_sensor"},
        {"entity_id": "binary_sensor.living_room_motion", "device_id": "living_sensor"},
        {"entity_id": "sensor.living_room_illuminance", "device_id": "living_sensor"},
        # Kitchen entities
        {"entity_id": "light.kitchen_main", "device_id": "kitchen_hub"},
        {"entity_id": "light.kitchen_under_cabinet", "device_id": "kitchen_hub"},
        {"entity_id": "sensor.kitchen_temperature", "device_id": "kitchen_hub"},
        {"entity_id": "binary_sensor.kitchen_motion", "device_id": "kitchen_hub"},
        # Bedroom entities
        {"entity_id": "sensor.bedroom_temperature", "device_id": "bedroom_climate"},
        {"entity_id": "sensor.bedroom_humidity", "device_id": "bedroom_climate"},
        {"entity_id": "climate.bedroom_ac", "device_id": "bedroom_climate"},
        # Office entities
        {"entity_id": "switch.office_pc", "device_id": "office_pc"},
        {"entity_id": "sensor.office_cpu_temp", "device_id": "office_pc"},
        # Garage entities
        {"entity_id": "cover.garage_door", "device_id": "garage_door"},
        {"entity_id": "binary_sensor.garage_door", "device_id": "garage_door"},
        # Floating entities (no area)
        {"entity_id": "sensor.floating_temp", "device_id": "floating_device"},
    ]


@pytest.fixture
def comprehensive_states_data():
    """Comprehensive entity states data with various device classes."""
    return [
        # Living Room
        {
            "entity_id": "light.living_room_main",
            "state": "on",
            "attributes": {
                "friendly_name": "Living Room Main Light",
                "brightness": 255,
                "device_class": None,
            },
        },
        {
            "entity_id": "light.living_room_accent",
            "state": "off",
            "attributes": {
                "friendly_name": "Living Room Accent Light",
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
            "entity_id": "sensor.living_room_humidity",
            "state": "45.2",
            "attributes": {
                "friendly_name": "Living Room Humidity",
                "unit_of_measurement": "%",
                "device_class": "humidity",
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
            "entity_id": "sensor.living_room_illuminance",
            "state": "150",
            "attributes": {
                "friendly_name": "Living Room Light Sensor",
                "unit_of_measurement": "lx",
                "device_class": "illuminance",
            },
        },
        # Kitchen
        {
            "entity_id": "light.kitchen_main",
            "state": "on",
            "attributes": {
                "friendly_name": "Kitchen Main Light",
                "brightness": 200,
                "device_class": None,
            },
        },
        {
            "entity_id": "light.kitchen_under_cabinet",
            "state": "on",
            "attributes": {
                "friendly_name": "Kitchen Under Cabinet Lights",
                "brightness": 100,
                "device_class": None,
            },
        },
        {
            "entity_id": "sensor.kitchen_temperature",
            "state": "24.1",
            "attributes": {
                "friendly_name": "Kitchen Temperature",
                "unit_of_measurement": "°C",
                "device_class": "temperature",
            },
        },
        {
            "entity_id": "binary_sensor.kitchen_motion",
            "state": "on",
            "attributes": {"friendly_name": "Kitchen Motion", "device_class": "motion"},
        },
        # Bedroom
        {
            "entity_id": "sensor.bedroom_temperature",
            "state": "21.0",
            "attributes": {
                "friendly_name": "Bedroom Temperature",
                "unit_of_measurement": "°C",
                "device_class": "temperature",
            },
        },
        {
            "entity_id": "sensor.bedroom_humidity",
            "state": "50.8",
            "attributes": {
                "friendly_name": "Bedroom Humidity",
                "unit_of_measurement": "%",
                "device_class": "humidity",
            },
        },
        {
            "entity_id": "climate.bedroom_ac",
            "state": "cool",
            "attributes": {
                "friendly_name": "Bedroom Air Conditioner",
                "temperature": 21,
                "device_class": None,
            },
        },
        # Office
        {
            "entity_id": "switch.office_pc",
            "state": "on",
            "attributes": {"friendly_name": "Office PC", "device_class": None},
        },
        {
            "entity_id": "sensor.office_cpu_temp",
            "state": "65.4",
            "attributes": {
                "friendly_name": "Office PC CPU Temperature",
                "unit_of_measurement": "°C",
                "device_class": "temperature",
            },
        },
        # Garage
        {
            "entity_id": "cover.garage_door",
            "state": "closed",
            "attributes": {"friendly_name": "Garage Door", "device_class": "garage"},
        },
        {
            "entity_id": "binary_sensor.garage_door",
            "state": "off",
            "attributes": {
                "friendly_name": "Garage Door Sensor",
                "device_class": "door",
            },
        },
        # Floating
        {
            "entity_id": "sensor.floating_temp",
            "state": "18.5",
            "attributes": {
                "friendly_name": "Floating Temperature Sensor",
                "unit_of_measurement": "°C",
                "device_class": "temperature",
            },
        },
    ]


class TestEnhancedFindEntitiesBasicFunctionality:
    """Test basic enhanced functionality of find_entities."""

    @pytest.mark.asyncio
    async def test_wildcard_returns_all_entities(
        self, server_with_enhanced_mocks, comprehensive_states_data
    ):
        """Test that wildcard '*' returns all entities."""
        server, mock_ha_client = server_with_enhanced_mocks
        mock_ha_client.get_all_states.return_value = comprehensive_states_data

        find_entities_func = server.mcp._test_tools["find_entities"]

        result = await find_entities_func("*")

        mock_ha_client.get_all_states.assert_called_once()
        parsed_result = json.loads(result)

        # Should return all 18 entities
        assert len(parsed_result) == 18

        # Verify we got entities from all areas
        entity_ids = {entity["entity_id"] for entity in parsed_result}
        assert "light.living_room_main" in entity_ids
        assert "sensor.kitchen_temperature" in entity_ids
        assert "climate.bedroom_ac" in entity_ids
        assert "cover.garage_door" in entity_ids
        assert "sensor.floating_temp" in entity_ids

    @pytest.mark.asyncio
    async def test_domain_filter_only(
        self, server_with_enhanced_mocks, comprehensive_states_data
    ):
        """Test filtering by domain only."""
        server, mock_ha_client = server_with_enhanced_mocks
        mock_ha_client.get_all_states.return_value = comprehensive_states_data

        find_entities_func = server.mcp._test_tools["find_entities"]

        result = await find_entities_func("*", domain="light")

        parsed_result = json.loads(result)

        # Should return only light entities
        assert len(parsed_result) == 4
        for entity in parsed_result:
            assert entity["entity_id"].startswith("light.")

    @pytest.mark.asyncio
    async def test_device_class_filter_only(
        self, server_with_enhanced_mocks, comprehensive_states_data
    ):
        """Test filtering by device_class only.

        Note: find_entities returns minimal fields by default (entity_id + friendly_name).
        To verify device_class we use expand=["attributes"] to get full attributes.
        """
        server, mock_ha_client = server_with_enhanced_mocks
        mock_ha_client.get_all_states.return_value = comprehensive_states_data

        find_entities_func = server.mcp._test_tools["find_entities"]

        result = await find_entities_func(
            "*", device_class="temperature", expand=["attributes"]
        )

        parsed_result = json.loads(result)

        # Should return all temperature sensors (5 total)
        assert len(parsed_result) == 5
        for entity in parsed_result:
            assert entity["attributes"]["device_class"] == "temperature"

    @pytest.mark.asyncio
    async def test_name_filter_with_entity_id_match(
        self, server_with_enhanced_mocks, comprehensive_states_data
    ):
        """Test name filter matching entity IDs."""
        server, mock_ha_client = server_with_enhanced_mocks
        mock_ha_client.get_all_states.return_value = comprehensive_states_data

        find_entities_func = server.mcp._test_tools["find_entities"]

        result = await find_entities_func("kitchen")

        parsed_result = json.loads(result)

        # Should match all entities with "kitchen" in entity_id
        assert len(parsed_result) == 4
        for entity in parsed_result:
            assert "kitchen" in entity["entity_id"].lower()

    @pytest.mark.asyncio
    async def test_name_filter_with_friendly_name_match(
        self, server_with_enhanced_mocks, comprehensive_states_data
    ):
        """Test name filter matching friendly names."""
        server, mock_ha_client = server_with_enhanced_mocks
        mock_ha_client.get_all_states.return_value = comprehensive_states_data

        find_entities_func = server.mcp._test_tools["find_entities"]

        result = await find_entities_func("Main Light")

        parsed_result = json.loads(result)

        # Should match entities with "Main Light" in friendly name
        assert len(parsed_result) == 2  # Living room and kitchen main lights
        for entity in parsed_result:
            assert "Main Light" in entity["attributes"]["friendly_name"]


class TestEnhancedFindEntitiesAreaFiltering:
    """Test area filtering functionality of enhanced find_entities."""

    @pytest.mark.asyncio
    async def test_area_filter_living_room(
        self,
        server_with_enhanced_mocks,
        comprehensive_areas_data,
        comprehensive_devices_data,
        comprehensive_entity_registry,
        comprehensive_states_data,
    ):
        """Test area filtering for living room."""
        server, mock_ha_client = server_with_enhanced_mocks
        mock_ha_client.get_all_states.return_value = comprehensive_states_data
        mock_ha_client.get_areas.return_value = comprehensive_areas_data
        mock_ha_client.get_devices.return_value = comprehensive_devices_data
        mock_ha_client.get_entity_registry.return_value = comprehensive_entity_registry

        find_entities_func = server.mcp._test_tools["find_entities"]

        result = await find_entities_func("*", area="Living Room")

        # Verify all required API calls were made
        mock_ha_client.get_all_states.assert_called_once()
        mock_ha_client.get_areas.assert_called_once()
        mock_ha_client.get_devices.assert_called_once()
        mock_ha_client.get_entity_registry.assert_called_once()

        parsed_result = json.loads(result)

        # Should return all living room entities (6 total)
        assert len(parsed_result) == 6

        expected_entities = {
            "light.living_room_main",
            "light.living_room_accent",
            "sensor.living_room_temperature",
            "sensor.living_room_humidity",
            "binary_sensor.living_room_motion",
            "sensor.living_room_illuminance",
        }

        actual_entities = {entity["entity_id"] for entity in parsed_result}
        assert actual_entities == expected_entities

    @pytest.mark.asyncio
    async def test_area_filter_case_insensitive(
        self,
        server_with_enhanced_mocks,
        comprehensive_areas_data,
        comprehensive_devices_data,
        comprehensive_entity_registry,
        comprehensive_states_data,
    ):
        """Test that area filtering is case insensitive."""
        server, mock_ha_client = server_with_enhanced_mocks
        mock_ha_client.get_all_states.return_value = comprehensive_states_data
        mock_ha_client.get_areas.return_value = comprehensive_areas_data
        mock_ha_client.get_devices.return_value = comprehensive_devices_data
        mock_ha_client.get_entity_registry.return_value = comprehensive_entity_registry

        find_entities_func = server.mcp._test_tools["find_entities"]

        result = await find_entities_func("*", area="HOME OFFICE")

        parsed_result = json.loads(result)

        # Should find office entities despite case difference
        assert len(parsed_result) == 2
        entity_ids = {entity["entity_id"] for entity in parsed_result}
        assert "switch.office_pc" in entity_ids
        assert "sensor.office_cpu_temp" in entity_ids

    @pytest.mark.asyncio
    async def test_area_filter_nonexistent_area(
        self,
        server_with_enhanced_mocks,
        comprehensive_areas_data,
        comprehensive_states_data,
    ):
        """Test error handling for nonexistent area."""
        server, mock_ha_client = server_with_enhanced_mocks
        mock_ha_client.get_all_states.return_value = comprehensive_states_data
        mock_ha_client.get_areas.return_value = comprehensive_areas_data

        find_entities_func = server.mcp._test_tools["find_entities"]

        with pytest.raises(ValueError, match="Area 'Basement' not found"):
            await find_entities_func("*", area="Basement")


class TestEnhancedFindEntitiesCombinedFiltering:
    """Test combined filtering functionality."""

    @pytest.mark.asyncio
    async def test_area_and_domain_combination(
        self,
        server_with_enhanced_mocks,
        comprehensive_areas_data,
        comprehensive_devices_data,
        comprehensive_entity_registry,
        comprehensive_states_data,
    ):
        """Test combining area and domain filters."""
        server, mock_ha_client = server_with_enhanced_mocks
        mock_ha_client.get_all_states.return_value = comprehensive_states_data
        mock_ha_client.get_areas.return_value = comprehensive_areas_data
        mock_ha_client.get_devices.return_value = comprehensive_devices_data
        mock_ha_client.get_entity_registry.return_value = comprehensive_entity_registry

        find_entities_func = server.mcp._test_tools["find_entities"]

        result = await find_entities_func("*", area="Kitchen", domain="light")

        parsed_result = json.loads(result)

        # Should find only kitchen lights
        assert len(parsed_result) == 2
        entity_ids = {entity["entity_id"] for entity in parsed_result}
        assert "light.kitchen_main" in entity_ids
        assert "light.kitchen_under_cabinet" in entity_ids

    @pytest.mark.asyncio
    async def test_area_and_device_class_combination(
        self,
        server_with_enhanced_mocks,
        comprehensive_areas_data,
        comprehensive_devices_data,
        comprehensive_entity_registry,
        comprehensive_states_data,
    ):
        """Test combining area and device_class filters."""
        server, mock_ha_client = server_with_enhanced_mocks
        mock_ha_client.get_all_states.return_value = comprehensive_states_data
        mock_ha_client.get_areas.return_value = comprehensive_areas_data
        mock_ha_client.get_devices.return_value = comprehensive_devices_data
        mock_ha_client.get_entity_registry.return_value = comprehensive_entity_registry

        find_entities_func = server.mcp._test_tools["find_entities"]

        result = await find_entities_func(
            "*", area="Living Room", device_class="motion"
        )

        parsed_result = json.loads(result)

        # Should find only living room motion sensors
        assert len(parsed_result) == 1
        assert parsed_result[0]["entity_id"] == "binary_sensor.living_room_motion"

    @pytest.mark.asyncio
    async def test_all_filters_combined(
        self,
        server_with_enhanced_mocks,
        comprehensive_areas_data,
        comprehensive_devices_data,
        comprehensive_entity_registry,
        comprehensive_states_data,
    ):
        """Test using all filters together.

        Note: find_entities returns minimal fields by default.
        To verify device_class we use expand=["attributes"] to get full attributes.
        """
        server, mock_ha_client = server_with_enhanced_mocks
        mock_ha_client.get_all_states.return_value = comprehensive_states_data
        mock_ha_client.get_areas.return_value = comprehensive_areas_data
        mock_ha_client.get_devices.return_value = comprehensive_devices_data
        mock_ha_client.get_entity_registry.return_value = comprehensive_entity_registry

        find_entities_func = server.mcp._test_tools["find_entities"]

        result = await find_entities_func(
            "temperature",
            area="Master Bedroom",
            domain="sensor",
            device_class="temperature",
            expand=["attributes"],
        )

        parsed_result = json.loads(result)

        # Should find only bedroom temperature sensor
        assert len(parsed_result) == 1
        assert parsed_result[0]["entity_id"] == "sensor.bedroom_temperature"
        assert "temperature" in parsed_result[0]["entity_id"].lower()
        assert parsed_result[0]["attributes"]["device_class"] == "temperature"

    @pytest.mark.asyncio
    async def test_filters_with_no_matches(
        self,
        server_with_enhanced_mocks,
        comprehensive_areas_data,
        comprehensive_devices_data,
        comprehensive_entity_registry,
        comprehensive_states_data,
    ):
        """Test filter combination that yields no results."""
        server, mock_ha_client = server_with_enhanced_mocks
        mock_ha_client.get_all_states.return_value = comprehensive_states_data
        mock_ha_client.get_areas.return_value = comprehensive_areas_data
        mock_ha_client.get_devices.return_value = comprehensive_devices_data
        mock_ha_client.get_entity_registry.return_value = comprehensive_entity_registry

        find_entities_func = server.mcp._test_tools["find_entities"]

        result = await find_entities_func(
            "*", area="Kitchen", domain="climate"  # No climate entities in kitchen
        )

        parsed_result = json.loads(result)
        assert len(parsed_result) == 0


class TestEnhancedFindEntitiesPerformanceAndEdgeCases:
    """Test performance and edge cases."""

    @pytest.mark.asyncio
    async def test_large_entity_set_performance(self, server_with_enhanced_mocks):
        """Test performance with large entity sets."""
        # Create a large dataset (1000 entities)
        large_states_data = []
        for i in range(1000):
            large_states_data.append(
                {
                    "entity_id": f"sensor.test_{i}",
                    "state": "active",
                    "attributes": {
                        "friendly_name": f"Test Sensor {i}",
                        "device_class": "temperature" if i % 3 == 0 else "motion",
                    },
                }
            )

        server, mock_ha_client = server_with_enhanced_mocks
        mock_ha_client.get_all_states.return_value = large_states_data

        find_entities_func = server.mcp._test_tools["find_entities"]

        # Test wildcard query (should be fast)
        result = await find_entities_func("*")
        parsed_result = json.loads(result)
        assert len(parsed_result) == 1000

        # Test device_class filter (should also be efficient)
        result = await find_entities_func("*", device_class="temperature")
        parsed_result = json.loads(result)
        # Every 3rd entity has temperature device_class
        assert len(parsed_result) == 334  # 1000 / 3 rounded up

    @pytest.mark.asyncio
    async def test_empty_states_response(self, server_with_enhanced_mocks):
        """Test handling empty states response."""
        server, mock_ha_client = server_with_enhanced_mocks
        mock_ha_client.get_all_states.return_value = []

        find_entities_func = server.mcp._test_tools["find_entities"]

        result = await find_entities_func("*")
        parsed_result = json.loads(result)
        assert len(parsed_result) == 0

    @pytest.mark.asyncio
    async def test_missing_device_class_attribute(self, server_with_enhanced_mocks):
        """Test handling entities without device_class attribute."""
        states_without_device_class = [
            {
                "entity_id": "sensor.no_device_class",
                "state": "42",
                "attributes": {
                    "friendly_name": "Sensor Without Device Class"
                    # No device_class attribute
                },
            }
        ]

        server, mock_ha_client = server_with_enhanced_mocks
        mock_ha_client.get_all_states.return_value = states_without_device_class

        find_entities_func = server.mcp._test_tools["find_entities"]

        # Should not match when filtering by device_class
        result = await find_entities_func("*", device_class="temperature")
        parsed_result = json.loads(result)
        assert len(parsed_result) == 0

        # Should match with wildcard
        result = await find_entities_func("*")
        parsed_result = json.loads(result)
        assert len(parsed_result) == 1

    @pytest.mark.asyncio
    async def test_connection_error_handling(self, server_with_enhanced_mocks):
        """Test error handling for connection issues."""
        server, mock_ha_client = server_with_enhanced_mocks
        mock_ha_client.get_all_states.side_effect = HomeAssistantAPIError(
            "Connection failed", 503
        )

        find_entities_func = server.mcp._test_tools["find_entities"]

        with pytest.raises(HomeAssistantAPIError, match="Connection failed"):
            await find_entities_func("*")


class TestEnhancedFindEntitiesBackwardCompatibility:
    """Test backward compatibility with old find_entities behavior."""

    @pytest.mark.asyncio
    async def test_old_search_term_behavior_still_works(
        self, server_with_enhanced_mocks, comprehensive_states_data
    ):
        """Test that old search term behavior still works with entity_name_filter."""
        server, mock_ha_client = server_with_enhanced_mocks
        mock_ha_client.get_all_states.return_value = comprehensive_states_data

        find_entities_func = server.mcp._test_tools["find_entities"]

        # Old style: search by entity name/friendly name
        result = await find_entities_func("living")

        parsed_result = json.loads(result)

        # Should find entities with "living" in entity_id or friendly_name
        assert len(parsed_result) > 0
        for entity in parsed_result:
            entity_id_match = "living" in entity["entity_id"].lower()
            friendly_name_match = (
                "living" in entity["attributes"].get("friendly_name", "").lower()
            )
            assert entity_id_match or friendly_name_match

    @pytest.mark.asyncio
    async def test_domain_filter_backward_compatibility(
        self, server_with_enhanced_mocks, comprehensive_states_data
    ):
        """Test that domain filtering works the same as before."""
        server, mock_ha_client = server_with_enhanced_mocks
        mock_ha_client.get_all_states.return_value = comprehensive_states_data

        find_entities_func = server.mcp._test_tools["find_entities"]

        # Old style: search with domain filter
        result = await find_entities_func("sensor", domain="sensor")

        parsed_result = json.loads(result)

        # Should find sensor entities with "sensor" in the name
        assert len(parsed_result) > 0
        for entity in parsed_result:
            assert entity["entity_id"].startswith("sensor.")
            # Should also match the search term
            entity_id_match = "sensor" in entity["entity_id"].lower()
            friendly_name_match = (
                "sensor" in entity["attributes"].get("friendly_name", "").lower()
            )
            assert entity_id_match or friendly_name_match


class TestFindEntitiesAttributeFiltering:
    """Test find_entities with attribute filtering."""

    @pytest.mark.asyncio
    async def test_find_entities_with_attribute_filter(
        self, server_with_enhanced_mocks, comprehensive_states_data
    ):
        """Test filtering entities by specific attribute values.

        Note: find_entities returns minimal fields by default (entity_id + friendly_name).
        To verify brightness we use expand=["attributes"] to get full attributes.
        """
        server, mock_ha_client = server_with_enhanced_mocks

        # Mock get_all_states to return test data
        mock_ha_client.get_all_states = AsyncMock(
            return_value=comprehensive_states_data
        )
        mock_ha_client.get_areas = AsyncMock(return_value=[])
        mock_ha_client.get_devices = AsyncMock(return_value=[])
        mock_ha_client.get_entity_registry = AsyncMock(return_value=[])

        # Get the registered find_entities function
        find_entities_func = server.mcp._test_tools["find_entities"]

        # Test attribute filtering - include expand to get full attributes in response
        result = await find_entities_func(
            "*", domain="light", attributes={"brightness": 255}, expand=["attributes"]
        )

        parsed_result = json.loads(result)

        # Should only find lights with brightness 255
        assert len(parsed_result) > 0
        for entity in parsed_result:
            assert entity["attributes"].get("brightness") == 255

    @pytest.mark.asyncio
    async def test_find_entities_with_state_filter(
        self, server_with_enhanced_mocks, comprehensive_states_data
    ):
        """Test filtering entities by state value.

        Note: find_entities returns minimal fields by default.
        To verify state we use select=["state"] to include it in response.
        """
        server, mock_ha_client = server_with_enhanced_mocks

        # Mock get_all_states to return test data
        mock_ha_client.get_all_states = AsyncMock(
            return_value=comprehensive_states_data
        )
        mock_ha_client.get_areas = AsyncMock(return_value=[])
        mock_ha_client.get_devices = AsyncMock(return_value=[])
        mock_ha_client.get_entity_registry = AsyncMock(return_value=[])

        # Get the registered find_entities function
        find_entities_func = server.mcp._test_tools["find_entities"]

        # Test state filtering - find only "on" lights, include state in response
        result = await find_entities_func(
            "*", domain="light", state="on", select=["state"]
        )

        parsed_result = json.loads(result)

        # Should only find lights that are "on"
        assert len(parsed_result) > 0
        for entity in parsed_result:
            assert entity["state"] == "on"


class TestFindEntitiesTokenLimit:
    """Test find_entities with token limit enforcement."""

    @pytest.mark.asyncio
    async def test_find_entities_with_token_limit_exceeded(
        self, server_with_enhanced_mocks
    ):
        """Test that token limit is enforced and returns error."""
        server, mock_ha_client = server_with_enhanced_mocks

        # Set a very low token limit to trigger the error
        server.config.get_tool_token_limit.return_value = 10

        # Create a large set of entities
        large_states = [
            {
                "entity_id": f"light.test_{i}",
                "state": "on",
                "attributes": {
                    "friendly_name": f"Test Light {i}",
                    "brightness": 255,
                },
            }
            for i in range(100)
        ]

        # Mock get_all_states to return large test data
        mock_ha_client.get_all_states = AsyncMock(return_value=large_states)
        mock_ha_client.get_areas = AsyncMock(return_value=[])
        mock_ha_client.get_devices = AsyncMock(return_value=[])
        mock_ha_client.get_entity_registry = AsyncMock(return_value=[])

        # Get the registered find_entities function
        find_entities_func = server.mcp._test_tools["find_entities"]

        # Execute query that will exceed token limit
        result = await find_entities_func("*")

        parsed_result = json.loads(result)

        # Should return error message instead of data
        assert "error" in parsed_result
        assert "token" in parsed_result["error"].lower()
        assert "token_count" in parsed_result
        assert "token_limit" in parsed_result
        assert parsed_result["token_limit"] == 10

    @pytest.mark.asyncio
    async def test_find_entities_with_token_limit_not_exceeded(
        self, server_with_enhanced_mocks, comprehensive_states_data
    ):
        """Test that reasonable queries work with token limit set."""
        server, mock_ha_client = server_with_enhanced_mocks

        # Set a high token limit
        server.config.get_tool_token_limit.return_value = 100000

        # Mock get_all_states to return test data
        mock_ha_client.get_all_states = AsyncMock(
            return_value=comprehensive_states_data
        )
        mock_ha_client.get_areas = AsyncMock(return_value=[])
        mock_ha_client.get_devices = AsyncMock(return_value=[])
        mock_ha_client.get_entity_registry = AsyncMock(return_value=[])

        # Get the registered find_entities function
        find_entities_func = server.mcp._test_tools["find_entities"]

        # Execute query that won't exceed token limit
        result = await find_entities_func("*", domain="light")

        parsed_result = json.loads(result)

        # Should return normal results, not error
        assert "error" not in parsed_result
        assert isinstance(parsed_result, list)
