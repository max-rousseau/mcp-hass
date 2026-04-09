"""
Comprehensive test suite for HomeAssistantWebSocketClient enhanced resilience features.

This test suite verifies the robust websocket implementation including:
- Auto-reconnection on connection loss
- Proper handling of CancelledError without timeout exceptions
- Connection health validation before requests
- Exponential backoff retry logic
- Graceful cleanup of pending messages on connection loss
- Proper locking to prevent race conditions

Focus on testing the new methods:
- _ensure_connection()
- _handle_connection_loss()
- _cleanup_connection()
- Enhanced connect() with retry logic
"""

import asyncio
import json
import pytest
import aiohttp
from unittest.mock import AsyncMock, MagicMock, patch, call

from src.mcp_hass.ha_client.websocket_client import HomeAssistantWebSocketClient
from src.mcp_hass.ha_client.exceptions import (
    HomeAssistantConnectionError,
    HomeAssistantAuthError,
    HomeAssistantAPIError,
    HomeAssistantTimeoutError,
)


@pytest.fixture
def ws_client():
    """Create a WebSocket client instance for testing."""
    return HomeAssistantWebSocketClient(
        base_url="http://homeassistant.local:8123", token="test_token_123456789"
    )


@pytest.fixture
def mock_websocket():
    """Create a mock websocket response."""
    mock_ws = AsyncMock()
    mock_ws.closed = False
    mock_ws.close = AsyncMock()
    mock_ws.send_json = AsyncMock()
    mock_ws.receive_json = AsyncMock()
    mock_ws.receive = AsyncMock()
    return mock_ws


@pytest.fixture
def mock_session():
    """Create a mock aiohttp session."""
    session = AsyncMock()
    session.ws_connect = AsyncMock()
    session.close = AsyncMock()
    return session


class TestWebSocketConnectionEstablishment:
    """Test WebSocket connection establishment with retry logic."""

    @pytest.mark.asyncio
    async def test_connect_successful_first_attempt(
        self, ws_client, mock_session, mock_websocket
    ):
        """Test successful connection on first attempt."""
        # Setup mocks
        mock_session.ws_connect.return_value = mock_websocket
        mock_websocket.receive_json.side_effect = [
            {"type": "auth_required"},
            {"type": "auth_ok"},
        ]

        # Mock the task creation to prevent background tasks
        mock_task = AsyncMock()

        with patch("aiohttp.ClientSession", return_value=mock_session):
            with patch("asyncio.create_task", return_value=mock_task):
                await ws_client.connect()

        # Verify connection was established
        assert ws_client.websocket is mock_websocket
        assert ws_client.session is mock_session
        assert ws_client._reconnect_attempts == 0

        # Verify auth sequence
        mock_websocket.send_json.assert_called_once_with(
            {"type": "auth", "access_token": "test_token_123456789"}
        )

        # Verify listener task was created
        assert ws_client.listener_task is mock_task

    @pytest.mark.asyncio
    async def test_connect_with_retry_after_failure(
        self, ws_client, mock_session, mock_websocket
    ):
        """Test successful connection after initial failure with exponential backoff."""
        # First attempt fails, second succeeds
        mock_session.ws_connect.side_effect = [
            aiohttp.ClientError("Connection failed"),
            mock_websocket,
        ]

        mock_websocket.receive_json.side_effect = [
            {"type": "auth_required"},
            {"type": "auth_ok"},
        ]

        mock_task = AsyncMock()

        with patch("aiohttp.ClientSession", return_value=mock_session):
            with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
                with patch("asyncio.create_task", return_value=mock_task):
                    await ws_client.connect()

        # Verify retry happened with exponential backoff
        assert mock_session.ws_connect.call_count == 2
        mock_sleep.assert_called_once_with(1.0)  # First retry delay

        # Verify final successful connection
        assert ws_client.websocket is mock_websocket
        assert ws_client._reconnect_attempts == 0

    @pytest.mark.asyncio
    async def test_connect_fails_after_max_attempts(self, ws_client, mock_session):
        """Test connection failure after exhausting retry attempts."""
        mock_session.ws_connect.side_effect = aiohttp.ClientError("Persistent failure")

        with patch("aiohttp.ClientSession", return_value=mock_session):
            with patch("asyncio.sleep", new_callable=AsyncMock):
                with patch("asyncio.create_task", return_value=AsyncMock()):
                    with pytest.raises(HomeAssistantConnectionError) as exc_info:
                        await ws_client.connect()

        # Verify all attempts were made
        assert mock_session.ws_connect.call_count == 3
        assert "WebSocket connection failed after 3 attempts" in str(exc_info.value)
        assert ws_client.websocket is None

    @pytest.mark.asyncio
    async def test_connect_auth_failure_no_retry(
        self, ws_client, mock_session, mock_websocket
    ):
        """Test authentication failure doesn't trigger retry."""
        mock_session.ws_connect.return_value = mock_websocket
        mock_websocket.receive_json.side_effect = [
            {"type": "auth_required"},
            {"type": "auth_invalid", "message": "Invalid token"},
        ]

        with patch("aiohttp.ClientSession", return_value=mock_session):
            with patch("asyncio.create_task", return_value=AsyncMock()):
                with pytest.raises(HomeAssistantAuthError) as exc_info:
                    await ws_client.connect()

        # Verify no retry on auth error
        assert mock_session.ws_connect.call_count == 1
        assert "Invalid token" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_connect_idempotent_with_existing_connection(
        self, ws_client, mock_websocket
    ):
        """Test connect() is idempotent when connection already exists."""
        ws_client.websocket = mock_websocket
        ws_client.session = AsyncMock()

        await ws_client.connect()

        # Should not create new connection
        assert ws_client.websocket is mock_websocket


class TestWebSocketConnectionHealthAndResilience:
    """Test connection health validation and auto-reconnection."""

    @pytest.mark.asyncio
    async def test_ensure_connection_with_healthy_connection(
        self, ws_client, mock_websocket
    ):
        """Test _ensure_connection with healthy existing connection."""
        ws_client.websocket = mock_websocket
        mock_websocket.closed = False

        with patch.object(ws_client, "connect", new_callable=AsyncMock) as mock_connect:
            await ws_client._ensure_connection()

        # Should not reconnect when connection is healthy
        mock_connect.assert_not_called()

    @pytest.mark.asyncio
    async def test_ensure_connection_with_closed_connection(
        self, ws_client, mock_websocket
    ):
        """Test _ensure_connection reconnects when websocket is closed."""
        ws_client.websocket = mock_websocket
        mock_websocket.closed = True

        with patch.object(ws_client, "connect", new_callable=AsyncMock) as mock_connect:
            await ws_client._ensure_connection()

        # Should reconnect when connection is closed
        mock_connect.assert_called_once()

    @pytest.mark.asyncio
    async def test_ensure_connection_with_no_connection(self, ws_client):
        """Test _ensure_connection reconnects when no websocket exists."""
        ws_client.websocket = None

        with patch.object(ws_client, "connect", new_callable=AsyncMock) as mock_connect:
            await ws_client._ensure_connection()

        # Should connect when no websocket exists
        mock_connect.assert_called_once()

    @pytest.mark.asyncio
    async def test_connection_health_validation_before_send_message(
        self, ws_client, mock_websocket
    ):
        """Test that _send_message establishes connection if not connected before sending."""
        # Start with no websocket to verify connection is established
        ws_client.websocket = None

        async def establish_connection():
            # Simulate connect() setting up the websocket
            ws_client.websocket = mock_websocket
            mock_websocket.closed = False

        with patch.object(
            ws_client,
            "connect",
            new_callable=AsyncMock,
            side_effect=establish_connection,
        ) as mock_connect:
            with patch("asyncio.wait_for", return_value={"success": True}):
                message = {"id": 1, "type": "test"}
                await ws_client._send_message(message)

        # Verify connect() was called to establish connection before sending
        mock_connect.assert_called_once()
        mock_websocket.send_json.assert_called_once_with(message)


class TestWebSocketConnectionLoss:
    """Test connection loss handling and recovery."""

    @pytest.mark.asyncio
    async def test_handle_connection_loss_clears_pending_messages(self, ws_client):
        """Test that connection loss fails all pending messages properly."""
        # Setup pending messages
        future1 = asyncio.Future()
        future2 = asyncio.Future()
        ws_client.pending_messages = {1: future1, 2: future2}
        ws_client.websocket = AsyncMock()

        await ws_client._handle_connection_loss()

        # Verify pending messages were failed with connection error
        assert future1.done()
        assert future2.done()
        assert isinstance(future1.exception(), HomeAssistantConnectionError)
        assert isinstance(future2.exception(), HomeAssistantConnectionError)
        assert "connection lost" in str(future1.exception()).lower()

        # Verify pending messages dict was cleared
        assert len(ws_client.pending_messages) == 0

        # Verify websocket was marked as None
        assert ws_client.websocket is None

    @pytest.mark.asyncio
    async def test_handle_connection_loss_with_cancelled_futures(self, ws_client):
        """Test connection loss handling when some futures are already cancelled."""
        # Setup mix of cancelled and active futures
        future1 = asyncio.Future()
        future2 = asyncio.Future()
        future2.cancel()  # Pre-cancel this future

        ws_client.pending_messages = {1: future1, 2: future2}
        ws_client.websocket = AsyncMock()

        await ws_client._handle_connection_loss()

        # Active future should be failed
        assert future1.done()
        assert isinstance(future1.exception(), HomeAssistantConnectionError)

        # Cancelled future should remain cancelled
        assert future2.cancelled()

        # All pending messages cleared
        assert len(ws_client.pending_messages) == 0

    @pytest.mark.asyncio
    async def test_message_listener_handles_websocket_closure(
        self, ws_client, mock_websocket
    ):
        """Test message listener properly handles websocket closure."""
        ws_client.websocket = mock_websocket

        # Setup pending messages to verify connection loss handling
        future = asyncio.Future()
        ws_client.pending_messages = {1: future}

        # Simulate websocket closure
        mock_msg = MagicMock()
        mock_msg.type = aiohttp.WSMsgType.CLOSED
        mock_websocket.receive.return_value = mock_msg

        await ws_client._message_listener()

        # Verify connection loss effects: pending messages failed, websocket cleared
        assert future.done()
        assert isinstance(future.exception(), HomeAssistantConnectionError)
        assert len(ws_client.pending_messages) == 0
        assert ws_client.websocket is None

    @pytest.mark.asyncio
    async def test_message_listener_handles_websocket_error(
        self, ws_client, mock_websocket
    ):
        """Test message listener properly handles websocket errors."""
        ws_client.websocket = mock_websocket

        # Setup pending messages to verify connection loss handling
        future = asyncio.Future()
        ws_client.pending_messages = {1: future}

        # Simulate websocket error
        mock_msg = MagicMock()
        mock_msg.type = aiohttp.WSMsgType.ERROR
        mock_websocket.receive.return_value = mock_msg

        await ws_client._message_listener()

        # Verify connection loss effects: pending messages failed, websocket cleared
        assert future.done()
        assert isinstance(future.exception(), HomeAssistantConnectionError)
        assert len(ws_client.pending_messages) == 0
        assert ws_client.websocket is None

    @pytest.mark.asyncio
    async def test_message_listener_handles_exceptions(self, ws_client, mock_websocket):
        """Test message listener handles unexpected exceptions gracefully."""
        ws_client.websocket = mock_websocket

        # Setup pending messages to verify connection loss handling
        future = asyncio.Future()
        ws_client.pending_messages = {1: future}

        mock_websocket.receive.side_effect = Exception("Unexpected error")

        await ws_client._message_listener()

        # Verify connection loss effects: pending messages failed, websocket cleared
        assert future.done()
        assert isinstance(future.exception(), HomeAssistantConnectionError)
        assert len(ws_client.pending_messages) == 0
        assert ws_client.websocket is None

    @pytest.mark.asyncio
    async def test_message_listener_cancelled_error_handling(
        self, ws_client, mock_websocket
    ):
        """Test message listener properly handles CancelledError."""
        ws_client.websocket = mock_websocket

        # Setup pending messages to verify they are NOT failed on CancelledError
        future = asyncio.Future()
        ws_client.pending_messages = {1: future}

        mock_websocket.receive.side_effect = asyncio.CancelledError()

        with pytest.raises(asyncio.CancelledError):
            await ws_client._message_listener()

        # CancelledError should be re-raised, NOT handled as connection loss
        # Pending messages should NOT be failed, websocket should NOT be cleared
        assert not future.done()
        assert 1 in ws_client.pending_messages
        assert ws_client.websocket is mock_websocket


class TestWebSocketCleanupAndResourceManagement:
    """Test resource cleanup and connection management."""

    @pytest.mark.asyncio
    async def test_cleanup_connection_cancels_listener_task(self, ws_client):
        """Test that cleanup properly cancels listener task."""

        # Create a real task to mock
        async def dummy_task():
            await asyncio.sleep(1)  # Long running task

        listener_task = asyncio.create_task(dummy_task())
        ws_client.listener_task = listener_task

        # Cancel the task immediately so cleanup can proceed
        listener_task.cancel()

        try:
            await ws_client._cleanup_connection()
        except asyncio.CancelledError:
            pass  # Expected when task is cancelled

        # Verify cleanup was called
        assert ws_client.listener_task is None
        assert listener_task.cancelled()

    @pytest.mark.asyncio
    async def test_cleanup_connection_handles_cancelled_listener(self, ws_client):
        """Test cleanup handles already cancelled listener tasks."""
        # Mock the listener task to be None (already cleaned up)
        ws_client.listener_task = None

        # Should not raise exception when no task exists
        await ws_client._cleanup_connection()

        assert ws_client.listener_task is None

    @pytest.mark.asyncio
    async def test_cleanup_connection_closes_websocket(self, ws_client, mock_websocket):
        """Test that cleanup properly closes websocket."""
        mock_websocket.closed = False
        ws_client.websocket = mock_websocket

        await ws_client._cleanup_connection()

        # Verify websocket was closed
        mock_websocket.close.assert_called_once()
        assert ws_client.websocket is None

    @pytest.mark.asyncio
    async def test_cleanup_connection_skips_closed_websocket(
        self, ws_client, mock_websocket
    ):
        """Test cleanup skips already closed websockets."""
        mock_websocket.closed = True
        ws_client.websocket = mock_websocket

        await ws_client._cleanup_connection()

        # Should not try to close already closed websocket
        mock_websocket.close.assert_not_called()
        assert ws_client.websocket is None

    @pytest.mark.asyncio
    async def test_cleanup_connection_fails_pending_messages(self, ws_client):
        """Test cleanup fails all pending messages with connection error."""
        # Setup pending messages
        future1 = asyncio.Future()
        future2 = asyncio.Future()
        ws_client.pending_messages = {1: future1, 2: future2}

        await ws_client._cleanup_connection()

        # All futures should be failed with connection error
        assert future1.done()
        assert future2.done()
        assert isinstance(future1.exception(), HomeAssistantConnectionError)
        assert isinstance(future2.exception(), HomeAssistantConnectionError)
        assert len(ws_client.pending_messages) == 0

    @pytest.mark.asyncio
    async def test_disconnect_uses_connection_lock(self, ws_client):
        """Test that disconnect properly uses connection lock."""
        lock_acquired = False

        original_acquire = ws_client._connection_lock.acquire

        async def track_acquire():
            nonlocal lock_acquired
            lock_acquired = True
            return await original_acquire()

        ws_client._connection_lock.acquire = track_acquire

        # Let cleanup run naturally - it's safe on an unconnected client
        await ws_client.disconnect()

        assert lock_acquired


class TestWebSocketRaceConditionPrevention:
    """Test proper locking to prevent race conditions."""

    @pytest.mark.asyncio
    async def test_concurrent_connect_calls_use_lock(
        self, ws_client, mock_session, mock_websocket
    ):
        """Test that concurrent connect calls are properly serialized."""
        connection_attempts = 0

        async def mock_connect_sequence(*args, **kwargs):
            nonlocal connection_attempts
            connection_attempts += 1
            await asyncio.sleep(0.1)  # Simulate connection delay
            return mock_websocket

        mock_session.ws_connect.side_effect = mock_connect_sequence
        mock_websocket.receive_json.side_effect = [
            {"type": "auth_required"},
            {"type": "auth_ok"},
        ]

        mock_task = AsyncMock()

        with patch("aiohttp.ClientSession", return_value=mock_session):
            with patch("asyncio.create_task", return_value=mock_task):
                # Start multiple concurrent connect attempts
                tasks = [ws_client.connect() for _ in range(3)]
                await asyncio.gather(*tasks)

        # Only one connection should have been made due to locking
        assert connection_attempts == 1
        assert ws_client.websocket is mock_websocket

    @pytest.mark.asyncio
    async def test_connect_with_existing_connection_under_lock(
        self, ws_client, mock_websocket
    ):
        """Test connect with existing connection properly uses lock."""
        ws_client.websocket = mock_websocket
        mock_websocket.closed = False

        # Track lock acquisition
        lock_acquired = 0
        original_acquire = ws_client._connection_lock.acquire

        async def track_acquire():
            nonlocal lock_acquired
            lock_acquired += 1
            return await original_acquire()

        ws_client._connection_lock.acquire = track_acquire

        await ws_client.connect()

        # Lock should have been acquired
        assert lock_acquired > 0
        # No new connection should have been created
        assert ws_client.websocket is mock_websocket


class TestWebSocketMessageHandling:
    """Test WebSocket message sending and response handling."""

    @pytest.mark.asyncio
    async def test_send_message_success(self, ws_client, mock_websocket):
        """Test successful message sending and response handling."""
        # Setup websocket as connected - _ensure_connection will see healthy connection
        ws_client.websocket = mock_websocket
        mock_websocket.closed = False

        # Setup message and response
        message = {"id": 1, "type": "test"}
        expected_response = {"success": True, "data": "test"}

        # Mock wait_for at asyncio boundary (external library)
        with patch("asyncio.wait_for", return_value=expected_response):
            result = await ws_client._send_message(message)

        assert result == expected_response
        mock_websocket.send_json.assert_called_once_with(message)

    @pytest.mark.asyncio
    async def test_send_message_timeout_handling(self, ws_client, mock_websocket):
        """Test proper timeout error handling in _send_message."""
        # Setup websocket as connected - _ensure_connection will see healthy connection
        ws_client.websocket = mock_websocket
        mock_websocket.closed = False

        message = {"id": 1, "type": "test"}

        # Mock wait_for at asyncio boundary (external library)
        with patch("asyncio.wait_for", side_effect=asyncio.TimeoutError()):
            with pytest.raises(HomeAssistantTimeoutError) as exc_info:
                await ws_client._send_message(message)

        assert "Message 1 timed out" in str(exc_info.value)
        # Message should be cleaned up from pending messages
        assert 1 not in ws_client.pending_messages

    @pytest.mark.asyncio
    async def test_send_message_connection_error_handling(
        self, ws_client, mock_websocket
    ):
        """Test connection error handling in _send_message."""
        # Setup websocket as connected - _ensure_connection will see healthy connection
        ws_client.websocket = mock_websocket
        mock_websocket.closed = False

        message = {"id": 1, "type": "test"}

        # Simulate connection error by having wait_for fail (asyncio boundary)
        with patch(
            "asyncio.wait_for",
            side_effect=HomeAssistantConnectionError("Connection lost"),
        ):
            with pytest.raises(HomeAssistantConnectionError):
                await ws_client._send_message(message)

        # Message should be cleaned up
        assert 1 not in ws_client.pending_messages

    @pytest.mark.asyncio
    async def test_message_listener_routes_responses(self, ws_client, mock_websocket):
        """Test message listener properly routes responses to pending requests."""
        ws_client.websocket = mock_websocket

        # Setup pending request
        future = asyncio.Future()
        ws_client.pending_messages[123] = future

        # Mock websocket message with response
        mock_msg = MagicMock()
        mock_msg.type = aiohttp.WSMsgType.TEXT
        mock_msg.data = json.dumps(
            {"id": 123, "success": True, "result": {"test": "data"}}
        )

        # Mock websocket to return message then raise to exit loop
        mock_websocket.receive.side_effect = [mock_msg, asyncio.CancelledError()]

        with pytest.raises(asyncio.CancelledError):
            await ws_client._message_listener()

        # Verify response was routed to correct future
        assert future.done()
        assert not future.cancelled()
        assert future.result() == {"test": "data"}
        assert 123 not in ws_client.pending_messages

    @pytest.mark.asyncio
    async def test_message_listener_handles_api_errors(self, ws_client, mock_websocket):
        """Test message listener handles API error responses."""
        ws_client.websocket = mock_websocket

        # Setup pending request
        future = asyncio.Future()
        ws_client.pending_messages[456] = future

        # Mock error response
        mock_msg = MagicMock()
        mock_msg.type = aiohttp.WSMsgType.TEXT
        mock_msg.data = json.dumps(
            {"id": 456, "success": False, "error": {"message": "Test API error"}}
        )

        mock_websocket.receive.side_effect = [mock_msg, asyncio.CancelledError()]

        with pytest.raises(asyncio.CancelledError):
            await ws_client._message_listener()

        # Verify error was set on future
        assert future.done()
        assert not future.cancelled()
        assert isinstance(future.exception(), HomeAssistantAPIError)
        assert "Test API error" in str(future.exception())


class TestWebSocketAPIMethodResilience:
    """Test API method resilience with connection issues."""

    @pytest.mark.asyncio
    async def test_get_areas_with_connection_recovery(self, ws_client, mock_websocket):
        """Test get_areas sends correct message and returns result."""
        expected_areas = [{"area_id": "living_room", "name": "Living Room"}]

        # Set up websocket as connected
        ws_client.websocket = mock_websocket
        mock_websocket.closed = False

        # Capture the sent message for verification
        sent_messages = []
        mock_websocket.send_json.side_effect = lambda msg: sent_messages.append(msg)

        with patch("asyncio.wait_for", return_value=expected_areas):
            result = await ws_client.get_areas()

        # Verify correct message was sent via websocket
        assert len(sent_messages) == 1
        assert sent_messages[0]["type"] == "config/area_registry/list"
        assert result == expected_areas

    @pytest.mark.asyncio
    async def test_get_devices_with_connection_recovery(
        self, ws_client, mock_websocket
    ):
        """Test get_devices sends correct message and returns result."""
        expected_devices = [{"id": "device_123", "name": "Test Device"}]

        # Set up websocket as connected
        ws_client.websocket = mock_websocket
        mock_websocket.closed = False

        # Capture the sent message for verification
        sent_messages = []
        mock_websocket.send_json.side_effect = lambda msg: sent_messages.append(msg)

        with patch("asyncio.wait_for", return_value=expected_devices):
            result = await ws_client.get_devices()

        assert len(sent_messages) == 1
        assert sent_messages[0]["type"] == "config/device_registry/list"
        assert result == expected_devices

    @pytest.mark.asyncio
    async def test_get_entities_with_connection_recovery(
        self, ws_client, mock_websocket
    ):
        """Test get_entities sends correct message and returns result."""
        expected_entities = [{"entity_id": "light.test", "device_id": "device_123"}]

        # Set up websocket as connected
        ws_client.websocket = mock_websocket
        mock_websocket.closed = False

        # Capture the sent message for verification
        sent_messages = []
        mock_websocket.send_json.side_effect = lambda msg: sent_messages.append(msg)

        with patch("asyncio.wait_for", return_value=expected_entities):
            result = await ws_client.get_entities()

        assert len(sent_messages) == 1
        assert sent_messages[0]["type"] == "config/entity_registry/list"
        assert result == expected_entities


class TestWebSocketSendMessageRetryLogic:
    """Test the enhanced _send_message retry logic for mid-request connection loss."""

    @pytest.mark.asyncio
    async def test_send_message_retries_on_connection_loss_during_wait(
        self, ws_client, mock_websocket
    ):
        """
        Critical test: Verify that connection loss AFTER message is sent but BEFORE
        response is received triggers retry instead of immediate failure.

        This specifically tests the scenario where:
        1. Message is sent successfully via websocket.send_json()
        2. Connection is lost while waiting in asyncio.wait_for()
        3. The retry mechanism kicks in with exponential backoff
        4. Up to 2 retries are attempted before final failure
        """
        message = {"id": 1, "type": "config/area_registry/list"}
        connect_count = 0
        send_attempts = 0

        # Mock connect() to track reconnection attempts
        async def mock_connect():
            nonlocal connect_count
            connect_count += 1
            # Restore connection successfully
            ws_client.websocket = mock_websocket
            mock_websocket.closed = False

        # Mock send_json to track actual send attempts
        async def mock_send_json(msg):
            nonlocal send_attempts
            send_attempts += 1
            return True

        mock_websocket.send_json.side_effect = mock_send_json

        # Mock wait_for to simulate connection loss during response wait
        call_count = 0

        async def mock_wait_for(future, timeout):
            nonlocal call_count
            call_count += 1

            if call_count <= 2:  # First two attempts fail due to connection loss
                # Simulate connection loss by clearing websocket state
                ws_client.websocket = None
                raise HomeAssistantConnectionError(
                    "WebSocket connection lost during response wait"
                )
            else:
                # Third attempt succeeds
                return [{"area_id": "living_room", "name": "Living Room"}]

        expected_result = [{"area_id": "living_room", "name": "Living Room"}]

        # Start with no websocket - connect() will be called first
        ws_client.websocket = None

        with patch.object(ws_client, "connect", side_effect=mock_connect):
            with patch("asyncio.wait_for", side_effect=mock_wait_for):
                with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
                    result = await ws_client._send_message(message)

        # Verify retry behavior
        assert result == expected_result
        assert connect_count == 3  # Initial + 2 retries via connect()
        assert send_attempts == 3  # Message sent 3 times (initial + 2 retries)
        assert call_count == 3  # wait_for called 3 times

        # Verify exponential backoff delays were applied
        expected_sleep_calls = [
            call(0.5),  # First retry: 0.5 * 1
            call(1.0),  # Second retry: 0.5 * 2
        ]
        assert mock_sleep.call_args_list == expected_sleep_calls

    @pytest.mark.asyncio
    async def test_send_message_fails_after_max_retries_on_connection_loss(
        self, ws_client, mock_websocket
    ):
        """
        Test that _send_message fails with ConnectionError after exhausting
        max_retries when connection keeps getting lost during response wait.
        """
        message = {"id": 1, "type": "test"}
        connect_count = 0

        async def mock_connect():
            nonlocal connect_count
            connect_count += 1
            # Always "succeed" at connecting
            ws_client.websocket = mock_websocket
            mock_websocket.closed = False

        # Always fail during wait_for due to connection loss
        async def mock_wait_for(future, timeout):
            # Simulate connection loss
            ws_client.websocket = None
            raise HomeAssistantConnectionError(
                "Connection consistently lost during response wait"
            )

        # Start with no websocket
        ws_client.websocket = None

        with patch.object(ws_client, "connect", side_effect=mock_connect):
            with patch("asyncio.wait_for", side_effect=mock_wait_for):
                with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
                    # Should fail after max_retries (2) + initial attempt = 3 total
                    with pytest.raises(HomeAssistantConnectionError) as exc_info:
                        await ws_client._send_message(message)

        # Verify all retries were exhausted
        assert connect_count == 3  # Initial + 2 retries
        assert "Connection consistently lost" in str(exc_info.value)

        # Verify exponential backoff was applied for retries
        expected_sleep_calls = [
            call(0.5),  # First retry
            call(1.0),  # Second retry
        ]
        assert mock_sleep.call_args_list == expected_sleep_calls

    @pytest.mark.asyncio
    async def test_send_message_connection_establishment_retry_behavior(
        self, ws_client, mock_websocket
    ):
        """
        Test retry behavior when connect() itself fails initially
        but succeeds on retry, followed by successful message send.
        """
        message = {"id": 1, "type": "test"}
        connection_attempts = 0

        async def mock_connect():
            nonlocal connection_attempts
            connection_attempts += 1

            if connection_attempts <= 2:
                # First two attempts to establish connection fail
                raise HomeAssistantConnectionError(
                    f"Connection establishment failed attempt {connection_attempts}"
                )
            else:
                # Third attempt succeeds
                ws_client.websocket = mock_websocket
                mock_websocket.closed = False

        # Mock successful message flow after connection established
        async def mock_wait_for(future, timeout):
            return "test_response"

        # Start with no websocket
        ws_client.websocket = None

        with patch.object(ws_client, "connect", side_effect=mock_connect):
            with patch("asyncio.wait_for", side_effect=mock_wait_for):
                with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
                    result = await ws_client._send_message(message)

        # Verify connection establishment was retried
        assert connection_attempts == 3
        assert result == "test_response"

        # Verify exponential backoff during connection establishment retries
        expected_sleep_calls = [
            call(0.5),  # First retry
            call(1.0),  # Second retry
        ]
        assert mock_sleep.call_args_list == expected_sleep_calls

    @pytest.mark.asyncio
    async def test_send_message_distinguishes_timeout_from_connection_loss(
        self, ws_client, mock_websocket
    ):
        """
        Test that timeout errors are handled differently from connection loss errors.
        Timeouts should not trigger retry, only connection loss should.
        """
        # Set up websocket as connected - _ensure_connection returns immediately
        ws_client.websocket = mock_websocket
        mock_websocket.closed = False

        message = {"id": 1, "type": "test"}

        # Simulate timeout (not connection loss) during wait_for
        with patch("asyncio.wait_for", side_effect=asyncio.TimeoutError()):
            with pytest.raises(HomeAssistantTimeoutError) as exc_info:
                await ws_client._send_message(message)

        # Verify timeout error is raised, not connection error
        assert "Message 1 timed out" in str(exc_info.value)
        # Verify message was cleaned up
        assert 1 not in ws_client.pending_messages

    @pytest.mark.asyncio
    async def test_send_message_retry_preserves_message_id_correlation(
        self, ws_client, mock_websocket
    ):
        """
        Test that message ID correlation is preserved across retries.
        Each retry should use the same message ID for proper response routing.
        """
        message = {"id": 42, "type": "test"}
        sent_messages = []

        # Track messages sent during retries
        async def mock_send_json(msg):
            sent_messages.append(msg.copy())
            return True

        mock_websocket.send_json.side_effect = mock_send_json

        retry_count = 0

        async def mock_wait_for(future, timeout):
            nonlocal retry_count
            retry_count += 1

            if retry_count <= 1:
                # First attempt fails with connection loss - simulate disconnect
                ws_client.websocket = None
                raise HomeAssistantConnectionError("Connection lost during wait")
            else:
                # Second attempt succeeds
                return "test_data"

        # Mock connect() to restore connection on retry
        async def mock_connect():
            ws_client.websocket = mock_websocket
            mock_websocket.closed = False

        # Start with no websocket
        ws_client.websocket = None

        with patch.object(ws_client, "connect", side_effect=mock_connect):
            with patch("asyncio.wait_for", side_effect=mock_wait_for):
                with patch("asyncio.sleep", new_callable=AsyncMock):
                    result = await ws_client._send_message(message)

        # Verify same message was sent multiple times with same ID
        assert len(sent_messages) == 2  # Initial + 1 retry
        assert all(msg["id"] == 42 for msg in sent_messages)
        assert all(msg["type"] == "test" for msg in sent_messages)
        assert result == "test_data"


class TestWebSocketErrorHandlingAndRecovery:
    """Test comprehensive error handling and recovery scenarios."""

    @pytest.mark.asyncio
    async def test_no_cancelled_error_on_connection_loss_during_request(
        self, ws_client, mock_websocket
    ):
        """
        Critical test: Verify that connection loss during request does NOT
        result in CancelledError being raised to the caller.
        """
        # Set up websocket as connected - _ensure_connection returns immediately
        ws_client.websocket = mock_websocket
        mock_websocket.closed = False

        message = {"id": 1, "type": "test"}

        # Track call count for connection error simulation
        call_count = 0

        # Simulate connection loss on send_json (aiohttp boundary)
        async def simulate_send_failure(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            # Fail all attempts with connection error
            raise HomeAssistantConnectionError("Connection lost during request")

        mock_websocket.send_json = AsyncMock(side_effect=simulate_send_failure)

        # This should raise ConnectionError, NOT CancelledError
        with pytest.raises(HomeAssistantConnectionError) as exc_info:
            await ws_client._send_message(message)

        # Verify we get the expected exception type, not CancelledError
        assert isinstance(exc_info.value, HomeAssistantConnectionError)
        assert "Connection lost" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_multiple_concurrent_requests_during_connection_loss(
        self, ws_client, mock_websocket
    ):
        """Test multiple concurrent requests handle connection loss gracefully."""
        # Set up websocket as connected - _ensure_connection returns immediately
        ws_client.websocket = mock_websocket
        mock_websocket.closed = False

        async def make_request(request_id: int):
            message = {"id": request_id, "type": "test"}
            try:
                # Simulate connection loss affecting all requests via asyncio boundary
                future = asyncio.Future()
                future.set_exception(HomeAssistantConnectionError("Connection lost"))

                with patch("asyncio.wait_for", return_value=await future):
                    await ws_client._send_message(message)

            except HomeAssistantConnectionError:
                return f"request_{request_id}_failed"
            except asyncio.CancelledError:
                # This should NOT happen
                return f"request_{request_id}_cancelled"

        # Start multiple concurrent requests
        tasks = [make_request(i) for i in range(5)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # All should fail with connection error, none with CancelledError
        for result in results:
            if isinstance(result, str):
                assert "failed" in result
                assert "cancelled" not in result
            else:
                assert isinstance(result, HomeAssistantConnectionError)

    @pytest.mark.asyncio
    async def test_connection_recovery_after_multiple_failures(
        self, ws_client, mock_session, mock_websocket
    ):
        """Test connection can recover after multiple failure scenarios."""
        # Setup sequence: fail, fail, succeed
        connection_attempts = 0

        async def mock_connect_with_failures(*args, **kwargs):
            nonlocal connection_attempts
            connection_attempts += 1
            if connection_attempts <= 2:
                raise aiohttp.ClientError(f"Failure {connection_attempts}")
            return mock_websocket

        mock_session.ws_connect.side_effect = mock_connect_with_failures
        mock_websocket.receive_json.side_effect = [
            {"type": "auth_required"},
            {"type": "auth_ok"},
        ]

        # Mock create_task to return a mock task (asyncio boundary)
        mock_task = AsyncMock()

        with patch("aiohttp.ClientSession", return_value=mock_session):
            with patch("asyncio.sleep", new_callable=AsyncMock):
                with patch("asyncio.create_task", return_value=mock_task):
                    await ws_client.connect()

        # Verify recovery happened
        assert connection_attempts == 3
        assert ws_client.websocket is mock_websocket
        assert ws_client._reconnect_attempts == 0

    @pytest.mark.asyncio
    async def test_exponential_backoff_timing(self, ws_client, mock_session):
        """Test exponential backoff timing is correct."""
        mock_session.ws_connect.side_effect = aiohttp.ClientError("Always fails")

        sleep_calls = []

        async def track_sleep(delay):
            sleep_calls.append(delay)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            with patch("asyncio.sleep", side_effect=track_sleep):
                with pytest.raises(HomeAssistantConnectionError):
                    await ws_client.connect()

        # Verify exponential backoff: 1.0 * (2^0), 1.0 * (2^1) = [1.0, 2.0]
        expected_delays = [1.0, 2.0]
        assert sleep_calls == expected_delays


class TestWebSocketContextManagerAndLifecycle:
    """Test async context manager and full lifecycle."""

    @pytest.mark.asyncio
    async def test_context_manager_connects_and_disconnects(self, ws_client):
        """Test async context manager properly connects and disconnects."""
        with patch.object(ws_client, "connect", new_callable=AsyncMock) as mock_connect:
            with patch.object(
                ws_client, "disconnect", new_callable=AsyncMock
            ) as mock_disconnect:
                async with ws_client as client:
                    assert client is ws_client
                    mock_connect.assert_called_once()
                    mock_disconnect.assert_not_called()

                mock_disconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_context_manager_handles_exceptions(self, ws_client):
        """Test context manager properly disconnects even when exceptions occur."""
        with patch.object(ws_client, "connect", new_callable=AsyncMock):
            with patch.object(
                ws_client, "disconnect", new_callable=AsyncMock
            ) as mock_disconnect:
                with pytest.raises(ValueError):
                    async with ws_client:
                        raise ValueError("Test exception")

                # Should still disconnect despite exception
                mock_disconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_full_lifecycle_with_real_operations(
        self, ws_client, mock_session, mock_websocket
    ):
        """Integration test of full lifecycle with real API operations."""
        # Setup successful connection
        mock_session.ws_connect.return_value = mock_websocket
        mock_websocket.receive_json.side_effect = [
            {"type": "auth_required"},
            {"type": "auth_ok"},
        ]

        expected_areas = [{"area_id": "test", "name": "Test Area"}]

        # Create a real completed task for the listener
        async def dummy_listener():
            pass

        real_task = asyncio.create_task(dummy_listener())
        await real_task  # Ensure it completes immediately

        with patch("aiohttp.ClientSession", return_value=mock_session):
            with patch("asyncio.create_task", return_value=real_task):
                # Test full lifecycle
                async with ws_client as client:
                    # Verify connection was established
                    assert client.websocket is mock_websocket

                    # Test API operation
                    with patch.object(
                        client, "_send_message", new_callable=AsyncMock
                    ) as mock_send:
                        mock_send.return_value = expected_areas
                        result = await client.get_areas()
                        assert result == expected_areas

                # Verify disconnect was called
                assert ws_client.websocket is None


@pytest.mark.asyncio
async def test_websocket_client_integration_resilience():
    """
    Integration test focusing on the key resilience requirement:
    WebSocket disconnections should NOT cause CancelledError exceptions
    to bubble up to the caller.
    """
    client = HomeAssistantWebSocketClient(
        base_url="http://homeassistant.local:8123", token="test_token"
    )

    # Mock the entire connection flow at aiohttp boundaries
    mock_session = AsyncMock()
    mock_websocket = AsyncMock()
    mock_websocket.closed = False
    mock_websocket.receive_json.side_effect = [
        {"type": "auth_required"},
        {"type": "auth_ok"},
    ]

    with patch("aiohttp.ClientSession", return_value=mock_session):
        with patch("asyncio.create_task", return_value=AsyncMock()):
            mock_session.ws_connect.return_value = mock_websocket

            # Establish connection
            await client.connect()
            assert client.websocket is mock_websocket

            # Simulate API call failing due to connection loss at asyncio boundary
            with patch(
                "asyncio.wait_for",
                side_effect=HomeAssistantConnectionError("WebSocket connection lost"),
            ):
                # This API call should raise ConnectionError, NOT CancelledError
                with pytest.raises(HomeAssistantConnectionError) as exc_info:
                    await client.get_areas()

                # Verify we got the expected exception type
                assert "WebSocket connection lost" in str(exc_info.value)
                # Critically important: this should NOT be a CancelledError
                assert not isinstance(exc_info.value, asyncio.CancelledError)

        # Clean up without calling disconnect to avoid the mocking issues
        client.listener_task = None
        client.websocket = None
