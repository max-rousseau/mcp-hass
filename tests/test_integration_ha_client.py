"""
Integration tests for HomeAssistantClient against fake HA server.

These tests validate the full client code including HTTP and WebSocket
communication against a fake Home Assistant server that returns fixture data.
"""

from datetime import datetime, timedelta, timezone

import pytest

from tests.fixtures import FIXTURES


@pytest.mark.asyncio
class TestHomeAssistantClientIntegration:
    """Integration tests for HomeAssistantClient."""

    async def test_get_all_states(self, fake_ha_client):
        """Test fetching all entity states via REST API."""
        client, _ = fake_ha_client
        states = await client.get_all_states()

        assert len(states) == len(FIXTURES["states"])
        entity_ids = [s["entity_id"] for s in states]
        assert "light.living_room" in entity_ids
        assert "sensor.living_room_temperature" in entity_ids

    async def test_call_service(self, fake_ha_client):
        """Test calling a service and verify it was tracked."""
        client, tracker = fake_ha_client

        await client.call_service(
            domain="light",
            service="turn_on",
            service_data={"entity_id": "light.bedroom", "brightness": 128},
        )

        tracker.assert_called(
            "light", "turn_on", entity_id="light.bedroom", brightness=128
        )

    async def test_call_service_multiple(self, fake_ha_client):
        """Test calling multiple services and tracking all calls."""
        client, tracker = fake_ha_client

        await client.call_service(
            "light", "turn_on", {"entity_id": "light.living_room"}
        )
        await client.call_service("light", "turn_off", {"entity_id": "light.bedroom"})
        await client.call_service(
            "climate",
            "set_temperature",
            {"entity_id": "climate.living_room", "temperature": 22},
        )

        assert len(tracker.calls) == 3
        tracker.assert_called("light", "turn_on")
        tracker.assert_called("light", "turn_off")
        tracker.assert_called("climate", "set_temperature", temperature=22)

    async def test_get_services(self, fake_ha_client):
        """Test fetching available services."""
        client, _ = fake_ha_client
        services = await client.get_services()

        assert "light" in services
        assert "turn_on" in services["light"]
        assert "turn_off" in services["light"]

    async def test_get_config(self, fake_ha_client):
        """Test fetching HA configuration."""
        client, _ = fake_ha_client
        config = await client.get_config()

        assert config["location_name"] == "Test Home"
        assert config["version"] == "2024.12.0"
        assert "light" in config["components"]

    async def test_get_history(self, fake_ha_client):
        """Test fetching entity history."""
        client, _ = fake_ha_client
        start_time = datetime.now(timezone.utc) - timedelta(hours=24)
        history = await client.get_history(
            entity_id="light.living_room",
            start_time=start_time,
        )

        # History fixture returns nested list structure
        assert len(history) > 0

    async def test_get_areas_via_websocket(self, fake_ha_client):
        """Test fetching areas via WebSocket API."""
        client, _ = fake_ha_client
        areas = await client.get_areas()

        assert len(areas) == len(FIXTURES["areas"])
        area_ids = [a["area_id"] for a in areas]
        assert "living_room" in area_ids
        assert "bedroom" in area_ids
        assert "kitchen" in area_ids

    async def test_get_devices_via_websocket(self, fake_ha_client):
        """Test fetching devices via WebSocket API."""
        client, _ = fake_ha_client
        devices = await client.get_devices()

        assert len(devices) == len(FIXTURES["devices"])
        device_names = [d["name"] for d in devices]
        assert "Philips Hue Bridge" in device_names

    async def test_get_entity_registry_via_websocket(self, fake_ha_client):
        """Test fetching entity registry via WebSocket API."""
        client, _ = fake_ha_client
        registry = await client.get_entity_registry()

        assert len(registry) == len(FIXTURES["entity_registry"])
        entity_ids = [e["entity_id"] for e in registry]
        assert "light.living_room" in entity_ids


@pytest.mark.asyncio
class TestServiceCallTracking:
    """Test service call tracking for assertions."""

    async def test_tracker_assert_called_success(self, fake_ha_client):
        """Test tracker correctly identifies called services."""
        client, tracker = fake_ha_client

        await client.call_service("switch", "turn_on", {"entity_id": "switch.coffee"})

        # Should not raise
        tracker.assert_called("switch", "turn_on")

    async def test_tracker_assert_called_with_data(self, fake_ha_client):
        """Test tracker can verify specific service call data."""
        client, tracker = fake_ha_client

        await client.call_service(
            "light", "turn_on", {"entity_id": "light.test", "brightness": 200}
        )

        # Should not raise - partial match on data
        tracker.assert_called("light", "turn_on", brightness=200)

    async def test_tracker_assert_called_failure(self, fake_ha_client):
        """Test tracker raises when service not called."""
        client, tracker = fake_ha_client

        await client.call_service("light", "turn_on", {})

        with pytest.raises(AssertionError):
            tracker.assert_called("light", "turn_off")  # Wrong service

    async def test_tracker_assert_not_called(self, fake_ha_client):
        """Test tracker can verify service was not called."""
        client, tracker = fake_ha_client

        await client.call_service("light", "turn_on", {})

        # Should not raise - turn_off was never called
        tracker.assert_not_called("light", "turn_off")

    async def test_tracker_reset(self, fake_ha_client):
        """Test tracker can be reset between test phases."""
        client, tracker = fake_ha_client

        await client.call_service("light", "turn_on", {})
        assert len(tracker.calls) == 1

        tracker.reset()
        assert len(tracker.calls) == 0

        await client.call_service("light", "turn_off", {})
        assert len(tracker.calls) == 1
