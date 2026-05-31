"""
Shared test fixtures and configuration for MCP-HASS test suite.

This module centralizes common fixtures to reduce duplication across test files
and ensure consistent test setup.
"""

import json
import pytest
from typing import Any
from unittest.mock import AsyncMock, Mock

from aiohttp import web
from aiohttp.test_utils import TestServer

from mcp_hass.ha_client.client import HomeAssistantClient
from mcp_hass.config.manager import ConfigurationManager
from tests.fixtures import FIXTURES, ServiceCallTracker


@pytest.fixture(autouse=True, scope="function")
def prevent_env_file_loading(monkeypatch):
    """Prevent ConfigurationManager from loading .env files during tests."""
    monkeypatch.setattr(ConfigurationManager, "_load_env_file", lambda self: None)


@pytest.fixture(autouse=True, scope="function")
def stub_tiktoken_encoding(monkeypatch):
    """Stub tiktoken.get_encoding so tests never hit the network.

    Real tiktoken downloads BPE files from openaipublic.blob.core.windows.net
    on first use, which breaks isolation. The stub returns an encoder whose
    encode() yields a token count proportional to input length so existing
    assertions (count > 0; longer text → more tokens) remain meaningful.
    """
    import tiktoken

    class _StubEncoding:
        def encode(self, text: str) -> list[int]:
            return [0] * max(1, len(text) // 4)

    monkeypatch.setattr(tiktoken, "get_encoding", lambda name: _StubEncoding())


# =============================================================================
# Configuration Fixtures
# =============================================================================


@pytest.fixture
def mock_config():
    """Mock ConfigurationManager for testing.

    Provides a fully configured mock with all required getter methods.
    """
    config = Mock(spec=ConfigurationManager)
    config.get_ha_base_url.return_value = "http://homeassistant.local:8123"
    config.get_ha_token.return_value = "test_token_123456789"
    config.get_ha_timeout.return_value = 10.0
    config.get_server_name.return_value = "Test-MCP-HASS"
    config.get_server_version.return_value = "0.1.0"
    config.get_log_level.return_value = "INFO"
    config.is_debug_mode.return_value = False
    config.get_tool_token_limit.return_value = 100000
    config.get_log_file_path.return_value = None
    return config


# =============================================================================
# Home Assistant Client Fixtures
# =============================================================================


@pytest.fixture
def mock_ha_client():
    """Mock HomeAssistantClient for testing.

    Provides a mock client with all API methods mocked as AsyncMock.
    Initially not connected (session=None) to test auto-connect behavior.
    """
    client = Mock(spec=HomeAssistantClient)
    client.base_url = "http://homeassistant.local:8123"
    client.token = "test_token_123456789"
    client.timeout = 10.0
    client.session = None  # Initially not connected
    client.connect = AsyncMock()
    client.disconnect = AsyncMock()
    client.validate_connection = AsyncMock(return_value=True)

    # REST API methods
    client.get_entity_state = AsyncMock()
    client.get_all_states = AsyncMock()
    client.get_history = AsyncMock()
    client.call_service = AsyncMock()
    client.get_services = AsyncMock()
    client.get_config = AsyncMock()

    # WebSocket API methods
    client.get_areas = AsyncMock()
    client.get_devices = AsyncMock()
    client.get_entity_registry = AsyncMock()

    return client


@pytest.fixture
def connected_ha_client(mock_ha_client):
    """Mock HomeAssistantClient that is already connected.

    Useful for tests that don't need to verify auto-connect behavior.
    """
    mock_ha_client.session = Mock()  # Mark as connected
    return mock_ha_client


# =============================================================================
# Mock Response Fixtures
# =============================================================================


@pytest.fixture
def mock_aiohttp_response():
    """Create a mock aiohttp response."""
    response = AsyncMock()
    response.status = 200
    response.headers = {"Content-Type": "application/json"}
    return response


# =============================================================================
# Sample Data Fixtures
# =============================================================================


@pytest.fixture
def sample_entity_state():
    """Sample entity state data from Home Assistant API."""
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
def sample_areas_data():
    """Sample areas data from Home Assistant."""
    return [
        {"area_id": "living_room", "name": "Living Room", "picture": None},
        {"area_id": "kitchen", "name": "Kitchen", "picture": "/local/kitchen.jpg"},
        {"area_id": "bedroom", "name": "Master Bedroom", "picture": None},
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
    ]


@pytest.fixture
def sample_entity_registry():
    """Sample entity registry data mapping entities to devices."""
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
            "entity_id": "light.kitchen_light",
            "device_id": "device3",
            "platform": "lifx",
        },
    ]


@pytest.fixture
def sample_services_data():
    """Sample services data from Home Assistant API."""
    return {
        "light": {
            "turn_on": {
                "description": "Turn on light",
                "fields": {
                    "entity_id": {"description": "Entity ID"},
                    "brightness": {"description": "Brightness value"},
                },
            },
            "turn_off": {
                "description": "Turn off light",
                "fields": {"entity_id": {"description": "Entity ID"}},
            },
        }
    }


# =============================================================================
# Fake Home Assistant Server (Integration Testing)
# =============================================================================


class FakeHomeAssistantServer:
    """Fake Home Assistant server for integration testing.

    Provides both REST API and WebSocket API endpoints that return fixture data.
    Tracks service calls for test assertions.
    """

    def __init__(self, fixtures: dict[str, Any] | None = None):
        self.fixtures = fixtures or FIXTURES
        self.service_tracker = ServiceCallTracker()
        self.app = self._create_app()

    def _create_app(self) -> web.Application:
        """Create aiohttp application with HA-like routes."""
        app = web.Application()

        # REST API routes
        app.router.add_get("/api/", self._handle_api_root)
        app.router.add_get("/api/states", self._handle_states)
        app.router.add_get("/api/states/{entity_id}", self._handle_state)
        app.router.add_get("/api/services", self._handle_services)
        app.router.add_post(
            "/api/services/{domain}/{service}", self._handle_service_call
        )
        app.router.add_get("/api/config", self._handle_config)
        app.router.add_get("/api/history/period", self._handle_history)
        app.router.add_get("/api/history/period/{timestamp}", self._handle_history)
        app.router.add_post("/api/config/core/check_config", self._handle_check_config)

        # WebSocket API route
        app.router.add_get("/api/websocket", self._handle_websocket)

        return app

    async def _handle_api_root(self, request: web.Request) -> web.Response:
        """Handle GET /api/ - connection validation."""
        return web.json_response({"message": "API running."})

    async def _handle_states(self, request: web.Request) -> web.Response:
        """Handle GET /api/states - return all entity states."""
        return web.json_response(self.fixtures.get("states", []))

    async def _handle_state(self, request: web.Request) -> web.Response:
        """Handle GET /api/states/{entity_id} - return single entity state."""
        entity_id = request.match_info["entity_id"]
        for state in self.fixtures.get("states", []):
            if state["entity_id"] == entity_id:
                return web.json_response(state)
        return web.json_response(
            {"message": f"Entity not found: {entity_id}"}, status=404
        )

    async def _handle_services(self, request: web.Request) -> web.Response:
        """Handle GET /api/services - return available services."""
        return web.json_response(self.fixtures.get("services", {}))

    async def _handle_service_call(self, request: web.Request) -> web.Response:
        """Handle POST /api/services/{domain}/{service} - execute service."""
        domain = request.match_info["domain"]
        service = request.match_info["service"]

        try:
            data = await request.json()
        except json.JSONDecodeError:
            data = {}

        self.service_tracker.record(domain, service, data)
        return web.json_response([{"result": "ok"}])

    async def _handle_config(self, request: web.Request) -> web.Response:
        """Handle GET /api/config - return HA configuration."""
        return web.json_response(self.fixtures.get("config", {}))

    async def _handle_history(self, request: web.Request) -> web.Response:
        """Handle GET /api/history/period - return entity history."""
        filter_entity = request.query.get("filter_entity_id", "")
        history = self.fixtures.get("history", {})

        if filter_entity and filter_entity in history:
            return web.json_response(history[filter_entity])

        # Return empty history if entity not in fixtures
        return web.json_response([[]])

    async def _handle_check_config(self, request: web.Request) -> web.Response:
        """Handle POST /api/config/core/check_config - validate config."""
        return web.json_response({"result": "valid", "errors": None})

    async def _handle_websocket(self, request: web.Request) -> web.WebSocketResponse:
        """Handle WebSocket connection for registry APIs."""
        ws = web.WebSocketResponse()
        await ws.prepare(request)

        # Send auth_required
        await ws.send_json({"type": "auth_required", "ha_version": "2024.12.0"})

        # Wait for auth message
        msg = await ws.receive_json()
        if msg.get("type") == "auth":
            await ws.send_json({"type": "auth_ok", "ha_version": "2024.12.0"})
        else:
            await ws.send_json({"type": "auth_invalid", "message": "Invalid auth"})
            await ws.close()
            return ws

        # Handle registry requests
        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT:
                try:
                    data = json.loads(msg.data)
                except json.JSONDecodeError:
                    continue

                msg_id = data.get("id")
                msg_type = data.get("type")

                result = self._handle_ws_message(msg_type)
                await ws.send_json(
                    {
                        "id": msg_id,
                        "type": "result",
                        "success": True,
                        "result": result,
                    }
                )
            elif msg.type == web.WSMsgType.CLOSE:
                break

        return ws

    def _handle_ws_message(self, msg_type: str) -> list[dict[str, Any]]:
        """Route WebSocket message to appropriate handler."""
        handlers = {
            "config/area_registry/list": lambda: self.fixtures.get("areas", []),
            "config/device_registry/list": lambda: self.fixtures.get("devices", []),
            "config/entity_registry/list": lambda: self.fixtures.get(
                "entity_registry", []
            ),
        }
        handler = handlers.get(msg_type, lambda: [])
        return handler()


@pytest.fixture
def service_tracker() -> ServiceCallTracker:
    """Standalone service call tracker for test assertions."""
    return ServiceCallTracker()


@pytest.fixture
async def fake_ha_server():
    """Spin up a fake Home Assistant server for integration tests.

    Yields the base URL (e.g., 'http://127.0.0.1:PORT') that can be used
    to configure HomeAssistantClient.

    Example:
        async def test_integration(fake_ha_server):
            url, tracker = fake_ha_server
            client = HomeAssistantClient(url, "fake-token")
            await client.validate_connection()
            # ... test with real client against fake server
    """
    fake_ha = FakeHomeAssistantServer()
    server = TestServer(fake_ha.app)
    await server.start_server()

    base_url = f"http://{server.host}:{server.port}"

    yield base_url, fake_ha.service_tracker

    await server.close()


@pytest.fixture
async def fake_ha_client(fake_ha_server) -> HomeAssistantClient:
    """Create a real HomeAssistantClient connected to fake HA server.

    This tests the full client code against fake HTTP/WebSocket responses.

    Example:
        async def test_client_integration(fake_ha_client):
            client, tracker = fake_ha_client
            states = await client.get_all_states()
            assert len(states) > 0
    """
    url, tracker = fake_ha_server
    client = HomeAssistantClient(
        base_url=url,
        token="fake-test-token",
        timeout=10.0,
    )

    yield client, tracker

    await client.disconnect()
