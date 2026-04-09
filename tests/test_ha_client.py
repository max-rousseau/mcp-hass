"""
Test suite for HomeAssistantClient class.

Following TDD principles to define the expected behavior before implementation.
Tests cover connection management, API calls, error handling, and authentication.
"""

import pytest
import aiohttp
from unittest.mock import AsyncMock, Mock, patch
from datetime import datetime

from src.mcp_hass.ha_client.client import HomeAssistantClient
from src.mcp_hass.ha_client.exceptions import (
    HomeAssistantConnectionError,
    HomeAssistantAuthError,
    HomeAssistantAPIError,
    HomeAssistantTimeoutError,
)


@pytest.fixture
def ha_client():
    """Create a HomeAssistantClient instance for testing."""
    return HomeAssistantClient(
        base_url="http://homeassistant.local:8123", token="test_token_123456789"
    )


@pytest.fixture
def mock_response():
    """Create a mock aiohttp response."""
    response = AsyncMock()
    response.status = 200
    response.headers = {"Content-Type": "application/json"}
    return response


@pytest.fixture
def services_data():
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


@pytest.fixture
def mock_aiohttp_session():
    """Create a mock aiohttp.ClientSession for testing without real connections."""
    mock_session = AsyncMock(spec=aiohttp.ClientSession)
    mock_session.closed = False
    mock_session.close = AsyncMock()
    # Mock headers as a dict-like object
    mock_session.headers = {}
    return mock_session


class TestHomeAssistantClientInitialization:
    """Test client initialization and configuration."""

    def test_init_with_valid_parameters(self):
        """Test client initialization with valid parameters."""
        client = HomeAssistantClient(
            base_url="http://homeassistant.local:8123", token="test_token"
        )
        assert client.base_url == "http://homeassistant.local:8123"
        assert client.token == "test_token"
        assert client.session is None
        assert client.timeout is not None

    def test_init_with_trailing_slash_in_url(self):
        """Test that trailing slash is properly handled in base URL."""
        client = HomeAssistantClient(
            base_url="http://homeassistant.local:8123/", token="test_token"
        )
        assert client.base_url == "http://homeassistant.local:8123"

    def test_init_with_custom_timeout(self):
        """Test initialization with custom timeout value."""
        client = HomeAssistantClient(
            base_url="http://homeassistant.local:8123", token="test_token", timeout=30
        )
        assert client.timeout.total == 30

    def test_init_raises_error_with_invalid_url(self):
        """Test that invalid URL raises appropriate error."""
        with pytest.raises(ValueError, match="Invalid base URL"):
            HomeAssistantClient(base_url="invalid_url", token="test_token")

    def test_init_raises_error_with_empty_token(self):
        """Test that empty token raises appropriate error."""
        with pytest.raises(ValueError, match="Token cannot be empty"):
            HomeAssistantClient(base_url="http://homeassistant.local:8123", token="")


class TestHomeAssistantClientConnectionManagement:
    """Test connection lifecycle management."""

    @pytest.mark.asyncio
    async def test_connect_creates_session(self, ha_client, mock_aiohttp_session):
        """Test that connect() creates aiohttp session with proper headers."""
        with patch("aiohttp.ClientSession", return_value=mock_aiohttp_session):
            await ha_client.connect()

            assert ha_client.session is not None
            assert ha_client.session is mock_aiohttp_session

            await ha_client.disconnect()

    @pytest.mark.asyncio
    async def test_connect_idempotent(self, ha_client, mock_aiohttp_session):
        """Test that multiple connect() calls don't create multiple sessions."""
        with patch("aiohttp.ClientSession", return_value=mock_aiohttp_session):
            await ha_client.connect()
            first_session = ha_client.session

            await ha_client.connect()
            second_session = ha_client.session

            assert first_session is second_session
            await ha_client.disconnect()

    @pytest.mark.asyncio
    async def test_disconnect_closes_session(self, ha_client, mock_aiohttp_session):
        """Test that disconnect() properly closes the session."""
        with patch("aiohttp.ClientSession", return_value=mock_aiohttp_session):
            await ha_client.connect()

            await ha_client.disconnect()

            mock_aiohttp_session.close.assert_called_once()
            assert ha_client.session is None

    @pytest.mark.asyncio
    async def test_disconnect_when_not_connected(self, ha_client):
        """Test that disconnect() handles case when not connected."""
        assert ha_client.session is None
        await ha_client.disconnect()  # Should not raise exception

    @pytest.mark.asyncio
    async def test_context_manager_support(self, ha_client, mock_aiohttp_session):
        """Test that client can be used as async context manager."""
        with patch("aiohttp.ClientSession", return_value=mock_aiohttp_session):
            async with ha_client as client:
                assert client.session is not None

            assert ha_client.session is None


class TestHomeAssistantClientAPIRequests:
    """Test API request methods."""

    @pytest.mark.asyncio
    async def test_call_service_success(self, ha_client):
        """Test successful service call."""
        service_data = {"entity_id": "light.living_room", "brightness": 255}
        expected_response = [{"entity_id": "light.living_room", "state": "on"}]

        with patch.object(
            ha_client, "_make_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = expected_response

            result = await ha_client.call_service("light", "turn_on", service_data)

            mock_request.assert_called_once_with(
                "POST", "/api/services/light/turn_on", json=service_data
            )
            assert result == expected_response

    @pytest.mark.asyncio
    async def test_get_all_states(self, ha_client):
        """Test retrieval of all entity states."""
        states_data = [
            {"entity_id": "light.living_room", "state": "on"},
            {"entity_id": "switch.kitchen", "state": "off"},
        ]

        with patch.object(
            ha_client, "_make_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = states_data

            result = await ha_client.get_all_states()

            mock_request.assert_called_once_with("GET", "/api/states")
            assert result == states_data

    @pytest.mark.asyncio
    async def test_get_config(self, ha_client):
        """Test Home Assistant configuration retrieval."""
        config_data = {
            "version": "2025.1.0",
            "location_name": "Home",
            "time_zone": "America/New_York",
        }

        with patch.object(
            ha_client, "_make_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = config_data

            result = await ha_client.get_config()

            mock_request.assert_called_once_with("GET", "/api/config")
            assert result == config_data

    @pytest.mark.asyncio
    async def test_get_services(self, ha_client, services_data):
        """Test services retrieval."""
        with patch.object(
            ha_client, "_make_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = services_data

            result = await ha_client.get_services()

            mock_request.assert_called_once_with("GET", "/api/services")
            assert result == services_data

    @pytest.mark.asyncio
    async def test_get_history(self, ha_client):
        """Test history data retrieval."""
        start_time = datetime(2025, 1, 20, 10, 0, 0)
        entity_id = "sensor.temperature"
        history_data = [
            {
                "entity_id": entity_id,
                "state": "22.5",
                "last_changed": "2025-01-20T10:00:00",
            }
        ]

        with patch.object(
            ha_client, "_make_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = history_data

            result = await ha_client.get_history(entity_id, start_time)

            expected_url = (
                f"/api/history/period/2025-01-20T10:00:00?filter_entity_id={entity_id}"
            )
            mock_request.assert_called_once_with("GET", expected_url)
            assert result == history_data


class TestHomeAssistantClientErrorHandling:
    """Test error handling and exception scenarios."""

    @pytest.mark.asyncio
    async def test_connection_error_handling(self, ha_client):
        """Test handling of connection errors."""
        with patch.object(
            ha_client, "_make_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.side_effect = HomeAssistantConnectionError("Connection failed")

            with pytest.raises(HomeAssistantConnectionError):
                await ha_client.get_all_states()

    @pytest.mark.asyncio
    async def test_timeout_error_handling(self, ha_client):
        """Test handling of timeout errors."""
        with patch.object(
            ha_client, "_make_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.side_effect = HomeAssistantTimeoutError("Request timed out")

            with pytest.raises(HomeAssistantTimeoutError):
                await ha_client.get_all_states()

    @pytest.mark.asyncio
    async def test_authentication_error_handling(self, ha_client):
        """Test handling of authentication errors (401)."""
        with patch.object(
            ha_client, "_make_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.side_effect = HomeAssistantAuthError("Invalid token")

            with pytest.raises(HomeAssistantAuthError):
                await ha_client.get_all_states()

    @pytest.mark.asyncio
    async def test_api_error_with_status_codes(self, ha_client):
        """Test API errors with different HTTP status codes."""
        test_cases = [
            (400, "Bad Request"),
            (404, "Not Found"),
            (500, "Internal Server Error"),
        ]

        for status_code, message in test_cases:
            with patch.object(
                ha_client, "_make_request", new_callable=AsyncMock
            ) as mock_request:
                mock_request.side_effect = HomeAssistantAPIError(message, status_code)

                with pytest.raises(HomeAssistantAPIError) as exc_info:
                    await ha_client.get_all_states()

                assert exc_info.value.status_code == status_code


class TestHomeAssistantClientValidation:
    """Test input validation."""

    def test_validate_entity_id_format(self, ha_client):
        """Test entity ID format validation."""
        valid_ids = [
            "light.living_room",
            "sensor.temperature_1",
            "switch.kitchen_outlet",
            "binary_sensor.door_sensor",
        ]

        invalid_ids = [
            "invalid",
            "light.",
            ".living_room",
            "light..living_room",
            "",
            "light.living room",  # space not allowed
        ]

        for entity_id in valid_ids:
            assert ha_client.validate_entity_id(entity_id) is True

        for entity_id in invalid_ids:
            assert ha_client.validate_entity_id(entity_id) is False

    def test_validate_service_call_data(self, ha_client):
        """Test service call data validation."""
        valid_data = [
            {"entity_id": "light.living_room"},
            {"entity_id": "light.living_room", "brightness": 255},
            {"target": {"entity_id": "light.living_room"}},
            {},  # Empty data is valid
        ]

        invalid_data = [
            {"entity_id": "invalid_entity"},
            {"brightness": "not_a_number"},
        ]

        for data in valid_data:
            assert ha_client.validate_service_data("light", "turn_on", data) is True

        for data in invalid_data:
            assert ha_client.validate_service_data("light", "turn_on", data) is False


class TestHomeAssistantClientAutoConnect:
    """Test auto-connect behavior through public APIs.

    CONTRACT: All public API methods should auto-connect when session is None.
    Tests verify WHAT happens (operations succeed regardless of connection state),
    not HOW it happens (internal _make_request or connect() calls).
    """

    @pytest.mark.asyncio
    async def test_auto_connect_behavior_in_api_methods(self, ha_client):
        """Test that all API methods auto-connect when needed."""
        # Ensure session is None initially
        assert ha_client.session is None

        test_cases = [
            ("get_all_states", (), [{"entity_id": "light.test", "state": "on"}]),
            ("get_config", (), {"version": "2025.1.0"}),
            ("get_services", (), {"light": {"turn_on": {}}}),
        ]

        for method_name, args, mock_return in test_cases:
            # Reset session to None for each test
            if ha_client.session:
                await ha_client.disconnect()
            assert ha_client.session is None

            with patch.object(
                ha_client, "connect", new_callable=AsyncMock
            ) as mock_connect:
                # Create mock session that gets set by connect
                mock_session = AsyncMock()
                mock_response = AsyncMock()
                mock_response.status = 200
                mock_response.json = AsyncMock(return_value=mock_return)

                # Configure the request method to return an async context manager
                class MockAsyncContextManager:
                    async def __aenter__(self):
                        return mock_response

                    async def __aexit__(self, *args):
                        return None

                mock_session.request = Mock(return_value=MockAsyncContextManager())

                async def set_session():
                    ha_client.session = mock_session

                mock_connect.side_effect = set_session

                # Call the API method
                method = getattr(ha_client, method_name)
                await method(*args)

                # Verify connect was called for auto-connection
                mock_connect.assert_called_once()

    @pytest.mark.asyncio
    async def test_websocket_methods_auto_connect_rest_session(self, ha_client):
        """Test that WebSocket API methods auto-connect REST session when needed."""
        # Ensure session is None initially
        assert ha_client.session is None

        # These methods use the websocket client internally
        websocket_methods = [
            ("get_areas", [], [{"area_id": "test", "name": "Test Area"}]),
            ("get_devices", [], [{"id": "test_device", "name": "Test Device"}]),
            (
                "get_entity_registry",
                [],
                [{"entity_id": "light.test", "device_id": "test_device"}],
            ),
        ]

        for method_name, args, mock_return in websocket_methods:
            # Reset session to None for each test
            if ha_client.session:
                await ha_client.disconnect()
            assert ha_client.session is None

            with patch.object(
                ha_client, "connect", new_callable=AsyncMock
            ) as mock_connect:
                # Patch the actual websocket method
                ws_method_name = (
                    "get_entities"
                    if method_name == "get_entity_registry"
                    else method_name
                )
                with patch.object(
                    ha_client.ws_client,
                    ws_method_name,
                    new_callable=AsyncMock,
                ) as mock_ws_method:
                    mock_ws_method.return_value = mock_return

                    async def set_session():
                        ha_client.session = AsyncMock()  # Mock session

                    mock_connect.side_effect = set_session

                    # Call the WebSocket API method
                    method = getattr(ha_client, method_name)
                    result = await method(*args)

                    # Verify connect was called for REST session auto-connection
                    mock_connect.assert_called_once()

                    # Verify the WebSocket method was called
                    mock_ws_method.assert_called_once()

                    # Verify result
                    assert result == mock_return


class TestHomeAssistantClientAutoConnectErrorHandling:
    """Test auto-connect behavior with various error scenarios."""

    @pytest.mark.asyncio
    async def test_auto_connect_failure_propagates_error(self, ha_client):
        """Test that auto-connect failures propagate the connection error.

        CONTRACT: When auto-connect fails, the error should propagate to the caller.
        Tests WHAT happens (operation fails with connection error), not HOW
        (internal _make_request behavior).
        """
        # Ensure session is None initially
        assert ha_client.session is None

        with patch.object(ha_client, "connect", new_callable=AsyncMock) as mock_connect:
            mock_connect.side_effect = HomeAssistantConnectionError("Connection failed")

            # Attempt a public API call which should auto-connect and fail
            with pytest.raises(HomeAssistantConnectionError, match="Connection failed"):
                await ha_client.get_all_states()

            # Verify connect was called and failed
            mock_connect.assert_called_once()

            # Verify session is still None after failed connection
            assert ha_client.session is None

    @pytest.mark.asyncio
    async def test_auto_connect_with_auth_error(self, ha_client):
        """Test auto-connect behavior when authentication fails."""
        # Ensure session is None initially
        assert ha_client.session is None

        with patch.object(ha_client, "connect", new_callable=AsyncMock) as mock_connect:
            mock_connect.side_effect = HomeAssistantAuthError("Invalid token")

            # Attempt to get states which should auto-connect and fail
            with pytest.raises(HomeAssistantAuthError, match="Invalid token"):
                await ha_client.get_all_states()

            # Verify connect was attempted
            mock_connect.assert_called_once()

    @pytest.mark.asyncio
    async def test_self_healing_connection_after_disconnect(
        self, ha_client, mock_aiohttp_session
    ):
        """Test that the client can self-heal after being disconnected."""
        with patch("aiohttp.ClientSession", return_value=mock_aiohttp_session):
            # First, establish a connection
            await ha_client.connect()
            assert ha_client.session is not None

            # Simulate disconnect (e.g., network issue)
            await ha_client.disconnect()
            assert ha_client.session is None

            # Now make a request which should auto-reconnect
            with patch.object(
                ha_client, "_make_request", new_callable=AsyncMock
            ) as mock_request:
                mock_request.return_value = [{"entity_id": "light.test", "state": "on"}]

                # This should work because _make_request will auto-connect
                result = await ha_client.get_all_states()

                # Verify the request was made
                mock_request.assert_called_once_with("GET", "/api/states")
                assert result == [{"entity_id": "light.test", "state": "on"}]

    @pytest.mark.asyncio
    async def test_concurrent_auto_connect_requests(self, ha_client):
        """Test that concurrent requests handle auto-connect properly."""
        import asyncio

        # Ensure session is None initially
        assert ha_client.session is None

        connect_call_count = 0
        original_connect = ha_client.connect

        async def counting_connect():
            nonlocal connect_call_count
            connect_call_count += 1
            await original_connect()

        # Mock the session.request to return a response-like object
        mock_response = Mock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"success": True})

        class MockAsyncContextManager:
            async def __aenter__(self):
                return mock_response

            async def __aexit__(self, *args):
                return None

        with patch.object(ha_client, "connect", side_effect=counting_connect):
            # Patch the session after connect is called
            with patch("aiohttp.ClientSession") as mock_session_class:
                mock_session = Mock()
                mock_session.request = Mock(return_value=MockAsyncContextManager())
                mock_session_class.return_value = mock_session

                # Make multiple concurrent requests
                tasks = [
                    ha_client.get_all_states(),
                    ha_client.get_config(),
                    ha_client.get_services(),
                    ha_client.get_all_states(),
                ]

                results = await asyncio.gather(*tasks)

                # All requests should succeed
                assert len(results) == 4
                assert all(result == {"success": True} for result in results)

                # Connect should be called at least once (auto-connect behavior)
                # Due to concurrent requests, it might be called multiple times before
                # the first one completes and sets the session
                assert connect_call_count >= 1


@pytest.mark.asyncio
async def test_client_full_lifecycle(mock_aiohttp_session):
    """Integration test of full client lifecycle."""
    client = HomeAssistantClient(
        base_url="http://homeassistant.local:8123", token="test_token"
    )

    with patch("aiohttp.ClientSession", return_value=mock_aiohttp_session):
        # Test connection
        await client.connect()
        assert client.session is not None

        # Mock a successful API call
        with patch.object(
            client, "_make_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = {"version": "2025.1.0"}

            result = await client.get_config()
            assert result["version"] == "2025.1.0"

        # Test disconnection
        await client.disconnect()
        assert client.session is None


@pytest.mark.asyncio
async def test_concurrent_requests(ha_client, mock_aiohttp_session):
    """Test that client can handle concurrent requests properly."""
    import asyncio

    with patch("aiohttp.ClientSession", return_value=mock_aiohttp_session):
        with patch.object(
            ha_client, "_make_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = {"result": "success"}

            await ha_client.connect()

            # Make multiple concurrent requests
            tasks = [ha_client.get_all_states() for _ in range(5)]

            results = await asyncio.gather(*tasks)

            assert len(results) == 5
            assert all(result["result"] == "success" for result in results)
            assert mock_request.call_count == 5

            await ha_client.disconnect()


class TestHomeAssistantClientValidationEdgeCases:
    """Test validation edge cases and error paths."""

    def test_validate_url_empty_string(self):
        """Test URL validation with empty string."""
        with pytest.raises(ValueError, match="Invalid base URL"):
            HomeAssistantClient(base_url="", token="test_token")

    def test_validate_url_none(self):
        """Test URL validation with None."""
        with pytest.raises(ValueError, match="Invalid base URL"):
            HomeAssistantClient(base_url=None, token="test_token")

    def test_validate_url_missing_scheme(self):
        """Test URL validation with missing scheme."""
        with pytest.raises(ValueError, match="Must include scheme and host"):
            HomeAssistantClient(base_url="localhost:8123", token="test_token")

    def test_validate_url_missing_host(self):
        """Test URL validation with missing host."""
        with pytest.raises(ValueError, match="Must include scheme and host"):
            HomeAssistantClient(base_url="http://", token="test_token")

    def test_validate_token_empty_string(self):
        """Test token validation with empty string."""
        with pytest.raises(ValueError, match="Token cannot be empty"):
            HomeAssistantClient(base_url="http://localhost:8123", token="")

    def test_validate_token_whitespace_only(self):
        """Test token validation with whitespace-only string."""
        with pytest.raises(ValueError, match="Token cannot be empty"):
            HomeAssistantClient(base_url="http://localhost:8123", token="   ")

    def test_validate_token_none(self):
        """Test token validation with None."""
        with pytest.raises(ValueError, match="Token cannot be empty"):
            HomeAssistantClient(base_url="http://localhost:8123", token=None)


class TestHomeAssistantClientContextManager:
    """Test context manager functionality."""

    @pytest.mark.asyncio
    async def test_context_manager_connects_and_disconnects(self, mock_aiohttp_session):
        """Test that context manager properly connects and disconnects."""
        client = HomeAssistantClient(
            base_url="http://localhost:8123", token="test_token"
        )

        assert client.session is None

        with patch("aiohttp.ClientSession", return_value=mock_aiohttp_session):
            async with client:
                # Should be connected
                assert client.session is not None

            # Should be disconnected
            assert client.session is None

    @pytest.mark.asyncio
    async def test_context_manager_disconnect_on_error(self, mock_aiohttp_session):
        """Test that context manager disconnects even on error."""
        client = HomeAssistantClient(
            base_url="http://localhost:8123", token="test_token"
        )

        with patch("aiohttp.ClientSession", return_value=mock_aiohttp_session):
            try:
                async with client:
                    assert client.session is not None
                    raise ValueError("Test error")
            except ValueError:
                pass

            # Should be disconnected even after error
            assert client.session is None


class TestHomeAssistantClientServiceValidation:
    """Test service data validation functionality."""

    def test_validate_service_data_with_none(self, ha_client):
        """Test service data validation when data is None."""
        # None is not valid as service_data (must be dict)
        assert ha_client.validate_service_data("light", "turn_on", None) is False

    @pytest.mark.asyncio
    async def test_call_service_with_none_data(self, ha_client, mock_aiohttp_session):
        """Test calling service with None service_data."""
        with patch("aiohttp.ClientSession", return_value=mock_aiohttp_session):
            await ha_client.connect()

            mock_response = {"success": True}

            with patch.object(
                ha_client, "_make_request", new_callable=AsyncMock
            ) as mock_request:
                mock_request.return_value = mock_response

                # Should convert None to {}
                result = await ha_client.call_service("light", "turn_on", None)

                mock_request.assert_called_once_with(
                    "POST", "/api/services/light/turn_on", json={}
                )
                assert result == mock_response

            await ha_client.disconnect()

    @pytest.mark.asyncio
    async def test_call_service_invalid_data_raises_error(
        self, ha_client, mock_aiohttp_session
    ):
        """Test calling service with invalid data raises validation error."""
        with patch("aiohttp.ClientSession", return_value=mock_aiohttp_session):
            await ha_client.connect()

            invalid_data = {"invalid_key": "value"}

            with patch.object(ha_client, "validate_service_data", return_value=False):
                with pytest.raises(Exception, match="Invalid service data"):
                    await ha_client.call_service("light", "turn_on", invalid_data)

            await ha_client.disconnect()

    def test_validate_service_data_with_entity_id_string(self, ha_client):
        """Test service data validation with entity_id as string."""
        data = {"entity_id": "light.living_room"}
        assert ha_client.validate_service_data("light", "turn_on", data) is True

    def test_validate_service_data_with_invalid_entity_id_string(self, ha_client):
        """Test service data validation with invalid entity_id string."""
        data = {"entity_id": "invalid"}
        assert ha_client.validate_service_data("light", "turn_on", data) is False

    def test_validate_service_data_with_entity_id_list(self, ha_client):
        """Test service data validation with entity_id as list."""
        data = {"entity_id": ["light.living_room", "light.bedroom"]}
        assert ha_client.validate_service_data("light", "turn_on", data) is True

    def test_validate_service_data_with_invalid_entity_id_list(self, ha_client):
        """Test service data validation with invalid entity_id in list."""
        data = {"entity_id": ["light.living_room", "invalid"]}
        assert ha_client.validate_service_data("light", "turn_on", data) is False

    def test_validate_service_data_with_entity_id_wrong_type(self, ha_client):
        """Test service data validation with entity_id as wrong type."""
        data = {"entity_id": 123}
        assert ha_client.validate_service_data("light", "turn_on", data) is False

    def test_validate_service_data_with_brightness(self, ha_client):
        """Test service data validation with brightness parameter."""
        data = {"entity_id": "light.test", "brightness": 128}
        assert ha_client.validate_service_data("light", "turn_on", data) is True

    def test_validate_service_data_with_invalid_brightness_range(self, ha_client):
        """Test service data validation with brightness out of range."""
        data_too_high = {"entity_id": "light.test", "brightness": 300}
        assert (
            ha_client.validate_service_data("light", "turn_on", data_too_high) is False
        )

        data_negative = {"entity_id": "light.test", "brightness": -10}
        assert (
            ha_client.validate_service_data("light", "turn_on", data_negative) is False
        )

    def test_validate_service_data_with_target_dict(self, ha_client):
        """Test service data validation with target as dict."""
        data = {"target": {"entity_id": "light.test"}}
        assert ha_client.validate_service_data("light", "turn_on", data) is True

    def test_validate_service_data_with_target_wrong_type(self, ha_client):
        """Test service data validation with target as wrong type."""
        data = {"target": "not_a_dict"}
        assert ha_client.validate_service_data("light", "turn_on", data) is False


class TestHomeAssistantClientHistoryWithEndTime:
    """Test history retrieval with end_time parameter."""

    @pytest.mark.asyncio
    async def test_get_history_with_end_time(self, ha_client, mock_aiohttp_session):
        """Test getting history with both start and end time."""
        with patch("aiohttp.ClientSession", return_value=mock_aiohttp_session):
            await ha_client.connect()

            start_time = datetime(2025, 1, 1, 0, 0, 0)
            end_time = datetime(2025, 1, 2, 0, 0, 0)

            mock_history = [
                {
                    "entity_id": "light.test",
                    "state": "on",
                    "last_changed": "2025-01-01T12:00:00",
                }
            ]

            with patch.object(
                ha_client, "_make_request", new_callable=AsyncMock
            ) as mock_request:
                mock_request.return_value = mock_history

                result = await ha_client.get_history("light.test", start_time, end_time)

                # Verify the request includes end_time parameter
                call_args = mock_request.call_args
                endpoint = call_args[0][1]
                assert "end_time=" in endpoint
                assert result == mock_history

            await ha_client.disconnect()

    @pytest.mark.asyncio
    async def test_get_history_invalid_entity_id(self, ha_client, mock_aiohttp_session):
        """Test getting history with invalid entity_id."""
        with patch("aiohttp.ClientSession", return_value=mock_aiohttp_session):
            await ha_client.connect()

            start_time = datetime(2025, 1, 1, 0, 0, 0)

            with pytest.raises(Exception, match="Invalid entity ID"):
                await ha_client.get_history("invalid", start_time)

            await ha_client.disconnect()


class TestHomeAssistantClientWebSocketDisconnect:
    """Test WebSocket client cleanup during disconnect."""

    @pytest.mark.asyncio
    async def test_disconnect_closes_websocket(self, ha_client, mock_aiohttp_session):
        """Test that disconnect properly closes WebSocket connection."""
        # Create a mock WebSocket client
        mock_ws_client = AsyncMock()
        mock_ws_client.disconnect = AsyncMock()

        ha_client.ws_client = mock_ws_client

        with patch("aiohttp.ClientSession", return_value=mock_aiohttp_session):
            await ha_client.connect()

            await ha_client.disconnect()

            # Verify WebSocket was disconnected
            mock_ws_client.disconnect.assert_called_once()
            assert ha_client.session is None
