"""
Fixture data simulating Home Assistant API responses.

These fixtures provide realistic data for integration testing without
requiring a real Home Assistant instance.
"""

from typing import Any


class ServiceCallTracker:
    """Track service calls made during tests for assertions."""

    def __init__(self):
        self.calls: list[dict[str, Any]] = []

    def record(self, domain: str, service: str, data: dict[str, Any]) -> None:
        self.calls.append({"domain": domain, "service": service, "data": data})

    def reset(self):
        self.calls.clear()

    def assert_called(self, domain: str, service: str, **expected_data) -> None:
        for call in self.calls:
            if call["domain"] == domain and call["service"] == service:
                if not expected_data or all(
                    call["data"].get(k) == v for k, v in expected_data.items()
                ):
                    return
        raise AssertionError(
            f"Expected call to {domain}.{service} with {expected_data}, "
            f"got: {self.calls}"
        )

    def assert_not_called(self, domain: str, service: str) -> None:
        for call in self.calls:
            if call["domain"] == domain and call["service"] == service:
                raise AssertionError(
                    f"Expected no call to {domain}.{service}, but found: {call}"
                )


FIXTURES: dict[str, Any] = {
    # =========================================================================
    # Entity States (REST API: GET /api/states)
    # =========================================================================
    "states": [
        # Lights
        {
            "entity_id": "light.living_room",
            "state": "on",
            "attributes": {
                "friendly_name": "Living Room Light",
                "brightness": 255,
                "color_temp": 370,
                "supported_features": 47,
                "device_class": "light",
            },
            "last_changed": "2025-01-20T10:30:00.000000+00:00",
            "last_updated": "2025-01-20T10:30:00.000000+00:00",
        },
        {
            "entity_id": "light.bedroom",
            "state": "off",
            "attributes": {
                "friendly_name": "Bedroom Light",
                "supported_features": 1,
            },
            "last_changed": "2025-01-20T08:00:00.000000+00:00",
            "last_updated": "2025-01-20T08:00:00.000000+00:00",
        },
        {
            "entity_id": "light.kitchen",
            "state": "on",
            "attributes": {
                "friendly_name": "Kitchen Light",
                "brightness": 180,
                "supported_features": 1,
            },
            "last_changed": "2025-01-20T07:00:00.000000+00:00",
            "last_updated": "2025-01-20T07:00:00.000000+00:00",
        },
        # Sensors
        {
            "entity_id": "sensor.living_room_temperature",
            "state": "22.5",
            "attributes": {
                "friendly_name": "Living Room Temperature",
                "unit_of_measurement": "°C",
                "device_class": "temperature",
                "state_class": "measurement",
            },
            "last_changed": "2025-01-20T10:29:00.000000+00:00",
            "last_updated": "2025-01-20T10:30:00.000000+00:00",
        },
        {
            "entity_id": "sensor.bedroom_humidity",
            "state": "45",
            "attributes": {
                "friendly_name": "Bedroom Humidity",
                "unit_of_measurement": "%",
                "device_class": "humidity",
                "state_class": "measurement",
            },
            "last_changed": "2025-01-20T10:25:00.000000+00:00",
            "last_updated": "2025-01-20T10:30:00.000000+00:00",
        },
        # Switches
        {
            "entity_id": "switch.coffee_maker",
            "state": "off",
            "attributes": {
                "friendly_name": "Coffee Maker",
                "device_class": "outlet",
            },
            "last_changed": "2025-01-20T06:30:00.000000+00:00",
            "last_updated": "2025-01-20T06:30:00.000000+00:00",
        },
        # Binary sensors
        {
            "entity_id": "binary_sensor.front_door",
            "state": "off",
            "attributes": {
                "friendly_name": "Front Door",
                "device_class": "door",
            },
            "last_changed": "2025-01-20T09:00:00.000000+00:00",
            "last_updated": "2025-01-20T09:00:00.000000+00:00",
        },
        {
            "entity_id": "binary_sensor.motion_hallway",
            "state": "on",
            "attributes": {
                "friendly_name": "Hallway Motion",
                "device_class": "motion",
            },
            "last_changed": "2025-01-20T10:28:00.000000+00:00",
            "last_updated": "2025-01-20T10:28:00.000000+00:00",
        },
        # Climate
        {
            "entity_id": "climate.living_room_thermostat",
            "state": "heat",
            "attributes": {
                "friendly_name": "Living Room Thermostat",
                "hvac_modes": ["off", "heat", "cool", "auto"],
                "current_temperature": 21.5,
                "temperature": 22.0,
                "hvac_action": "heating",
            },
            "last_changed": "2025-01-20T10:00:00.000000+00:00",
            "last_updated": "2025-01-20T10:30:00.000000+00:00",
        },
        # Camera
        {
            "entity_id": "camera.front_porch",
            "state": "idle",
            "attributes": {
                "friendly_name": "Front Porch Camera",
                "entity_picture": "/api/camera_proxy/camera.front_porch",
            },
            "last_changed": "2025-01-20T00:00:00.000000+00:00",
            "last_updated": "2025-01-20T10:30:00.000000+00:00",
        },
    ],
    # =========================================================================
    # Areas (WebSocket API: config/area_registry/list)
    # =========================================================================
    "areas": [
        {
            "area_id": "living_room",
            "name": "Living Room",
            "picture": None,
            "aliases": [],
            "floor_id": "main_floor",
        },
        {
            "area_id": "bedroom",
            "name": "Master Bedroom",
            "picture": None,
            "aliases": ["master"],
            "floor_id": "main_floor",
        },
        {
            "area_id": "kitchen",
            "name": "Kitchen",
            "picture": "/local/kitchen.jpg",
            "aliases": [],
            "floor_id": "main_floor",
        },
        {
            "area_id": "garage",
            "name": "Garage",
            "picture": None,
            "aliases": [],
            "floor_id": None,
        },
    ],
    # =========================================================================
    # Devices (WebSocket API: config/device_registry/list)
    # =========================================================================
    "devices": [
        {
            "id": "device_hue_bridge",
            "area_id": "living_room",
            "name": "Philips Hue Bridge",
            "name_by_user": None,
            "model": "BSB002",
            "manufacturer": "Signify",
            "sw_version": "1.56.0",
            "hw_version": "1.0",
            "serial_number": "001788FFFE123456",
            "via_device_id": None,
            "disabled_by": None,
            "configuration_url": "http://X.X.X.X",
        },
        {
            "id": "device_hue_bulb_1",
            "area_id": "living_room",
            "name": "Living Room Bulb",
            "name_by_user": "Main Light",
            "model": "LCT016",
            "manufacturer": "Signify",
            "sw_version": "1.90.1",
            "hw_version": None,
            "serial_number": None,
            "via_device_id": "device_hue_bridge",
            "disabled_by": None,
            "configuration_url": None,
        },
        {
            "id": "device_motion_sensor",
            "area_id": "living_room",
            "name": "Living Room Motion Sensor",
            "name_by_user": None,
            "model": "SML001",
            "manufacturer": "Signify",
            "sw_version": "2.53.6",
            "hw_version": None,
            "serial_number": None,
            "via_device_id": "device_hue_bridge",
            "disabled_by": None,
            "configuration_url": None,
        },
        {
            "id": "device_thermostat",
            "area_id": "living_room",
            "name": "Ecobee Thermostat",
            "name_by_user": None,
            "model": "ecobee4",
            "manufacturer": "ecobee",
            "sw_version": "4.7.340",
            "hw_version": None,
            "serial_number": "123456789",
            "via_device_id": None,
            "disabled_by": None,
            "configuration_url": "https://www.ecobee.com",
        },
        {
            "id": "device_bedroom_light",
            "area_id": "bedroom",
            "name": "Bedroom Light",
            "name_by_user": None,
            "model": "LIFX A19",
            "manufacturer": "LIFX",
            "sw_version": "3.70",
            "hw_version": None,
            "serial_number": None,
            "via_device_id": None,
            "disabled_by": None,
            "configuration_url": None,
        },
    ],
    # =========================================================================
    # Entity Registry (WebSocket API: config/entity_registry/list)
    # =========================================================================
    "entity_registry": [
        {
            "entity_id": "light.living_room",
            "device_id": "device_hue_bulb_1",
            "platform": "hue",
            "area_id": None,  # Inherits from device
            "disabled_by": None,
            "hidden_by": None,
            "name": None,
            "icon": None,
            "unique_id": "00:17:88:01:12:34:56:78-0b",
        },
        {
            "entity_id": "light.bedroom",
            "device_id": "device_bedroom_light",
            "platform": "lifx",
            "area_id": None,
            "disabled_by": None,
            "hidden_by": None,
            "name": None,
            "icon": None,
            "unique_id": "d073d5123456",
        },
        {
            "entity_id": "light.kitchen",
            "device_id": None,  # No device association
            "platform": "demo",
            "area_id": "kitchen",  # Direct area assignment
            "disabled_by": None,
            "hidden_by": None,
            "name": None,
            "icon": None,
            "unique_id": "demo_light_kitchen",
        },
        {
            "entity_id": "sensor.living_room_temperature",
            "device_id": "device_motion_sensor",
            "platform": "hue",
            "area_id": None,
            "disabled_by": None,
            "hidden_by": None,
            "name": None,
            "icon": None,
            "unique_id": "00:17:88:01:12:34:56:78-temp",
        },
        {
            "entity_id": "binary_sensor.motion_hallway",
            "device_id": "device_motion_sensor",
            "platform": "hue",
            "area_id": None,
            "disabled_by": None,
            "hidden_by": None,
            "name": "Hallway Motion",
            "icon": "mdi:motion-sensor",
            "unique_id": "00:17:88:01:12:34:56:78-motion",
        },
        {
            "entity_id": "climate.living_room_thermostat",
            "device_id": "device_thermostat",
            "platform": "ecobee",
            "area_id": None,
            "disabled_by": None,
            "hidden_by": None,
            "name": None,
            "icon": None,
            "unique_id": "123456789",
        },
    ],
    # =========================================================================
    # Services (REST API: GET /api/services)
    # =========================================================================
    "services": {
        "light": {
            "turn_on": {
                "name": "Turn on",
                "description": "Turn on a light.",
                "fields": {
                    "entity_id": {
                        "description": "Entity ID of the light.",
                        "example": "light.living_room",
                    },
                    "brightness": {
                        "description": "Brightness value (0-255).",
                        "example": 255,
                    },
                    "color_temp": {
                        "description": "Color temperature in mireds.",
                        "example": 370,
                    },
                    "rgb_color": {
                        "description": "RGB color as [r, g, b].",
                        "example": [255, 100, 50],
                    },
                    "transition": {
                        "description": "Transition time in seconds.",
                        "example": 2,
                    },
                },
                "target": {"entity": {"domain": "light"}},
            },
            "turn_off": {
                "name": "Turn off",
                "description": "Turn off a light.",
                "fields": {
                    "entity_id": {
                        "description": "Entity ID of the light.",
                        "example": "light.living_room",
                    },
                    "transition": {
                        "description": "Transition time in seconds.",
                        "example": 2,
                    },
                },
                "target": {"entity": {"domain": "light"}},
            },
            "toggle": {
                "name": "Toggle",
                "description": "Toggle a light on/off.",
                "fields": {
                    "entity_id": {
                        "description": "Entity ID of the light.",
                    },
                },
                "target": {"entity": {"domain": "light"}},
            },
        },
        "switch": {
            "turn_on": {
                "name": "Turn on",
                "description": "Turn on a switch.",
                "fields": {},
                "target": {"entity": {"domain": "switch"}},
            },
            "turn_off": {
                "name": "Turn off",
                "description": "Turn off a switch.",
                "fields": {},
                "target": {"entity": {"domain": "switch"}},
            },
        },
        "climate": {
            "set_temperature": {
                "name": "Set temperature",
                "description": "Set target temperature.",
                "fields": {
                    "temperature": {
                        "description": "Target temperature.",
                        "example": 22,
                    },
                    "target_temp_high": {
                        "description": "High target temperature.",
                    },
                    "target_temp_low": {
                        "description": "Low target temperature.",
                    },
                },
                "target": {"entity": {"domain": "climate"}},
            },
            "set_hvac_mode": {
                "name": "Set HVAC mode",
                "description": "Set HVAC operation mode.",
                "fields": {
                    "hvac_mode": {
                        "description": "HVAC mode (off, heat, cool, auto).",
                        "example": "heat",
                    },
                },
                "target": {"entity": {"domain": "climate"}},
            },
        },
        "homeassistant": {
            "reload_all": {
                "name": "Reload all",
                "description": "Reload all YAML configuration.",
                "fields": {},
            },
        },
    },
    # =========================================================================
    # Config (REST API: GET /api/config)
    # =========================================================================
    "config": {
        "location_name": "Test Home",
        "version": "2024.12.0",
        "config_dir": "/config",
        "time_zone": "America/Los_Angeles",
        "latitude": 37.7749,
        "longitude": -122.4194,
        "elevation": 10,
        "unit_system": {
            "length": "mi",
            "mass": "lb",
            "pressure": "psi",
            "temperature": "°F",
            "volume": "gal",
        },
        "components": [
            "light",
            "switch",
            "sensor",
            "binary_sensor",
            "climate",
            "camera",
            "automation",
        ],
        "state": "RUNNING",
        "internal_url": "http://homeassistant.local:8123",
        "external_url": None,
        "currency": "USD",
        "country": "US",
        "language": "en",
    },
    # =========================================================================
    # History (REST API: GET /api/history/period)
    # =========================================================================
    "history": {
        "light.living_room": [
            [
                {
                    "entity_id": "light.living_room",
                    "state": "off",
                    "attributes": {"brightness": 0},
                    "last_changed": "2025-01-20T06:00:00.000000+00:00",
                },
                {
                    "entity_id": "light.living_room",
                    "state": "on",
                    "attributes": {"brightness": 128},
                    "last_changed": "2025-01-20T07:00:00.000000+00:00",
                },
                {
                    "entity_id": "light.living_room",
                    "state": "on",
                    "attributes": {"brightness": 255},
                    "last_changed": "2025-01-20T10:30:00.000000+00:00",
                },
            ]
        ],
        "sensor.living_room_temperature": [
            [
                {
                    "entity_id": "sensor.living_room_temperature",
                    "state": "20.0",
                    "last_changed": "2025-01-20T06:00:00.000000+00:00",
                },
                {
                    "entity_id": "sensor.living_room_temperature",
                    "state": "21.0",
                    "last_changed": "2025-01-20T08:00:00.000000+00:00",
                },
                {
                    "entity_id": "sensor.living_room_temperature",
                    "state": "22.5",
                    "last_changed": "2025-01-20T10:29:00.000000+00:00",
                },
            ]
        ],
    },
}


def get_fixture(key: str, default: Any = None) -> Any:
    """Get fixture data by key with optional default."""
    return FIXTURES.get(key, default)
