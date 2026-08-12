# SPDX-License-Identifier: BSD-3-Clause
"""
Module: client

Purpose:
    Dual-API Home Assistant client implementation providing access to both
    REST API (for entity states, services, config) and WebSocket API (for registries).
    This unified client abstracts the complexity of Home Assistant's dual-API architecture.

Classes:
    - HomeAssistantClient: Unified REST + WebSocket client

Functions:
    - get_all_states: All entity states via REST API
    - call_service: Service calls via REST API
    - get_areas: Area registry via WebSocket API
    - get_devices: Device registry via WebSocket API
    - get_entity_registry: Entity registry via WebSocket API

Usage Example:
    from mcp_hass.ha_client import HomeAssistantClient

    client = HomeAssistantClient(
        base_url="http://X.X.X.X:8123",
        token="your_token_here"
    )

    await client.connect()

    # REST API calls
    state = await client.get_entity_state("light.bedroom")
    result = await client.call_service("light", "turn_on", {"entity_id": "light.bedroom"})

    # WebSocket API calls (delegated to WebSocketClient)
    areas = await client.get_areas()
    devices = await client.get_devices()

Architecture Decision:
    Home Assistant exposes different data through different APIs:

    REST API (/api/...):
    - Entity states and attributes
    - Service calls
    - Configuration
    - History data

    WebSocket API (ws://host/api/websocket):
    - Area registry (config/area_registry/list)
    - Device registry (config/device_registry/list)
    - Entity registry (config/entity_registry/list)
    - Real-time events and subscriptions

    This client provides a unified interface while using the appropriate
    API for each type of data access.

Happy Path Flow:

```mermaid
sequenceDiagram
    participant MCP as MCP Tool
    participant Client as HomeAssistantClient
    participant REST as REST Session
    participant WS as WebSocketClient
    participant HASS as Home Assistant

    Note over MCP,HASS: Dual-API Access Pattern

    MCP->>Client: get_entity_state("light.bedroom")
    Client->>REST: HTTP GET /api/states/light.bedroom
    REST->>HASS: REST request
    HASS-->>REST: entity state data
    REST-->>Client: parsed response
    Client-->>MCP: entity state

    Note over MCP,HASS: WebSocket API Required for Registries

    MCP->>Client: get_areas()
    Client->>WS: get_areas()
    WS->>HASS: WebSocket: config/area_registry/list
    HASS-->>WS: area registry data
    WS-->>Client: areas list
    Client-->>MCP: areas data
```

Dual Client Architecture:

```mermaid
graph TB
    subgraph "HomeAssistantClient (Unified Interface)"
        RESTMethods[REST API Methods<br/>get_entity_state<br/>call_service<br/>get_config<br/>get_history]
        WSMethods[WebSocket API Methods<br/>get_areas<br/>get_devices<br/>get_entity_registry]
    end

    subgraph "Transport Layer"
        HTTPSession[aiohttp.ClientSession<br/>REST Transport]
        WSClient[HomeAssistantWebSocketClient<br/>WebSocket Transport]
    end

    subgraph "Home Assistant APIs"
        RESTAPI[REST API<br/>/api/states<br/>/api/services<br/>/api/config]
        WSAPI[WebSocket API<br/>config/area_registry<br/>config/device_registry<br/>config/entity_registry]
    end

    RESTMethods --> HTTPSession
    WSMethods --> WSClient
    HTTPSession --> RESTAPI
    WSClient --> WSAPI
```
"""

import aiohttp
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urljoin, urlparse

from .exceptions import (
    HomeAssistantConnectionError,
    HomeAssistantAuthError,
    HomeAssistantAPIError,
    HomeAssistantTimeoutError,
    HomeAssistantValidationError,
)
from .websocket_client import HomeAssistantWebSocketClient


def _to_utc_iso(value: datetime) -> str:
    """Normalize a datetime to a URL-safe UTC ISO 8601 string.

    Converts naive datetimes to UTC (assuming they already represent UTC)
    and aware datetimes to UTC, then renders the offset as the ``Z``
    designator instead of ``+00:00``. HA's ciso8601 parser and DATETIME_RE
    both accept ``Z``, and unlike ``+00:00`` it survives untouched through
    aiohttp/yarl URL encoding in both the path and the query string (a
    literal ``+`` is decoded by the server as a space).

    Args:
        value: Datetime to normalize (naive or timezone-aware)

    Returns:
        UTC ISO 8601 string ending in ``Z``
    """
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


class HomeAssistantClient:
    """Self-healing Home Assistant API client with dual REST/WebSocket architecture.

    This unified client provides seamless access to both Home Assistant's REST API
    and WebSocket API through an intelligent self-healing connection pattern.
    The client automatically establishes connections when needed, eliminating
    the need for manual connection management.

    Key Features:
        - **Self-Healing Connections**: Auto-connects when needed, never requires manual connect()
        - **Dual-API Architecture**: Unified interface for REST and WebSocket APIs
        - **Connection Persistence**: Maintains connections for optimal performance
        - **Intelligent API Selection**: Automatically routes requests to appropriate API
        - **Comprehensive Error Handling**: Graceful degradation with detailed error messages

    Architecture:
        The client manages two connection types:
        - HTTP Session: For entity states, service calls, configuration (REST API)
        - WebSocket Client: For area/device/entity registries (WebSocket API)

    Connection Management:
        All methods implement self-healing behavior:
        ```python
        async def _make_request(self, method, endpoint, **kwargs):
            # Auto-connect if not connected (self-healing behavior)
            if self.session is None:
                await self.connect()
            # ... rest of implementation
        ```

    API Coverage:
        REST API (via HTTP Session):
        - Entity states (/api/states)
        - Service calls (/api/services)
        - Configuration (/api/config)
        - History data (/api/history)

        WebSocket API (via WebSocketClient):
        - Area registry (config/area_registry/list)
        - Device registry (config/device_registry/list)
        - Entity registry (config/entity_registry/list)

    Example:
        >>> client = HomeAssistantClient("http://homeassistant:8123", "token")
        >>> # No manual connect() needed - client auto-connects
        >>> state = await client.get_entity_state("light.bedroom")
        >>> areas = await client.get_areas()  # Uses WebSocket automatically
        >>> await client.disconnect()  # Optional cleanup

    Self-Healing Flow:
        ```mermaid
        sequenceDiagram
            participant Tool as MCP Tool
            participant Client as HomeAssistantClient
            participant Session as HTTP Session
            participant WS as WebSocket Client
            participant HASS as Home Assistant

            Tool->>Client: get_entity_state("light.bedroom")
            Note over Client: Check if session exists
            alt Session is None
                Client->>Session: create and authenticate
                Session->>HASS: validate connection
            end
            Client->>Session: GET /api/states/light.bedroom
            Session->>HASS: HTTP request
            HASS-->>Session: entity data
            Session-->>Client: parsed response
            Client-->>Tool: entity state

            Tool->>Client: get_areas()
            Client->>WS: get_areas()
            Note over WS: Check WebSocket connection
            alt Not connected
                WS->>HASS: connect and authenticate
            end
            WS->>HASS: {"type": "config/area_registry/list"}
            HASS-->>WS: area data
            WS-->>Client: parsed areas
            Client-->>Tool: areas list
        ```

    Attributes:
        base_url (str): Home Assistant base URL (normalized)
        token (str): Authentication token (validated)
        timeout (ClientTimeout): Request timeout configuration
        session (Optional[ClientSession]): HTTP session for REST API
        ws_client (HomeAssistantWebSocketClient): WebSocket client for registry access

    Raises:
        ValueError: If URL or token validation fails during initialization
        HomeAssistantConnectionError: If connection to Home Assistant fails
        HomeAssistantAuthError: If authentication fails
        HomeAssistantAPIError: If API calls return errors
        HomeAssistantTimeoutError: If requests timeout
        HomeAssistantValidationError: If input validation fails
    """

    def __init__(
        self, base_url: str, token: str, timeout: float = 10.0, ssl_verify: bool = True
    ) -> None:
        """Initialize Home Assistant client with self-healing dual-API architecture.

        Creates a unified client that provides seamless access to both REST and
        WebSocket APIs without requiring manual connection management. The client
        automatically establishes connections when needed and routes requests
        to the appropriate API based on the type of data being accessed.

        Self-Healing Behavior:
            - HTTP sessions created automatically on first REST API call
            - WebSocket connections established automatically on first registry call
            - Connections maintained across multiple requests for performance
            - Failed connections trigger automatic reconnection attempts

        API Routing Strategy:
            - Entity states, service calls → REST API (fast, efficient)
            - Area/device/entity registries → WebSocket API (only available source)
            - Configuration data → REST API
            - History data → REST API

        Args:
            base_url (str): Base URL of Home Assistant instance. Will be normalized
                          to remove trailing slashes and validated for proper scheme.
                          Automatically converted to WebSocket URL for registry access.
            token (str): Long-lived access token for authentication. Used for both
                        REST and WebSocket API authentication. Must be at least 20
                        characters (Home Assistant tokens are typically much longer).
            timeout (float, optional): Request timeout in seconds for both REST and
                                     WebSocket operations. Defaults to 10.0 seconds.

        Raises:
            ValueError: If base_url is invalid (missing scheme/host) or if token
                       is invalid (empty or too short for Home Assistant standards)

        Example:
            >>> client = HomeAssistantClient(
            ...     base_url="http://X.X.X.X:8123",
            ...     token="eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
            ... )
            >>> # No manual connect() needed - auto-connects on first use
            >>> state = await client.get_entity_state("light.bedroom")
            >>> areas = await client.get_areas()  # Uses WebSocket automatically

        Note:
            The client validates URLs and tokens during initialization but does
            not establish connections until the first API call is made. This
            allows for fast initialization and lazy connection establishment.
        """
        self.base_url = self._validate_and_normalize_url(base_url)
        self.token = self._validate_token(token)
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.ssl_verify = ssl_verify
        self.session: Optional[aiohttp.ClientSession] = None

        if not self.ssl_verify:
            import ssl

            self._ssl_context = ssl.create_default_context()
            self._ssl_context.check_hostname = False
            self._ssl_context.verify_mode = ssl.CERT_NONE
        else:
            self._ssl_context = None

        # Initialize WebSocket client for registry access
        self.ws_client = HomeAssistantWebSocketClient(
            base_url=self.base_url,
            token=self.token,
            timeout=timeout,
            ssl_verify=ssl_verify,
        )

    def _validate_and_normalize_url(self, url: str) -> str:
        """
        Validate and normalize the base URL.

        Args:
            url: URL to validate

        Returns:
            Normalized URL without trailing slash

        Raises:
            ValueError: If URL is invalid
        """
        if not url or not isinstance(url, str):
            raise ValueError("Invalid base URL: URL cannot be empty")

        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            raise ValueError("Invalid base URL: Must include scheme and host")

        # Remove trailing slash
        return url.rstrip("/")

    def _validate_token(self, token: str) -> str:
        """
        Validate the authentication token.

        Args:
            token: Token to validate

        Returns:
            Validated token

        Raises:
            ValueError: If token is invalid
        """
        if not token or not isinstance(token, str):
            raise ValueError("Token cannot be empty")

        if len(token.strip()) == 0:
            raise ValueError("Token cannot be empty")

        return token.strip()

    async def connect(self) -> None:
        """
        Establish connection to Home Assistant.

        Creates aiohttp session with proper headers and timeout configuration.
        This method is idempotent - multiple calls won't create multiple sessions.
        """
        if self.session is not None:
            return

        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

        connector = aiohttp.TCPConnector(ssl=self._ssl_context)
        self.session = aiohttp.ClientSession(
            headers=headers, timeout=self.timeout, connector=connector
        )

    async def disconnect(self) -> None:
        """
        Close connection to Home Assistant.

        Properly closes the aiohttp session, WebSocket connection, and cleans up resources.
        Safe to call multiple times.
        """
        # Close WebSocket connection
        if self.ws_client:
            await self.ws_client.disconnect()

        # Close REST session
        if self.session is not None:
            await self.session.close()
            self.session = None

    async def __aenter__(self) -> "HomeAssistantClient":
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, _exc_type, _exc_val, _exc_tb) -> None:
        """Async context manager exit."""
        await self.disconnect()

    async def _make_request(
        self, method: str, endpoint: str, **kwargs
    ) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
        """Make HTTP request to Home Assistant API with self-healing connection management.

        This method implements the core self-healing pattern that eliminates the need
        for manual connection management. It automatically establishes connections
        when needed and maintains them for optimal performance.

        Self-Healing Behavior:
            1. Checks if HTTP session exists
            2. If not connected, automatically calls connect()
            3. Creates authenticated session with proper headers
            4. Maintains session for subsequent requests
            5. Handles connection errors gracefully

        Connection Lifecycle:
            ```python
            # Session management is completely automatic:
            client = HomeAssistantClient(url, token)
            # No manual connect() needed - happens automatically
            data = await client.get_entity_state("light.bedroom")
            # Session is created and maintained internally
            ```

        Error Handling Philosophy:
            - Connection errors trigger automatic retry with fresh session
            - Authentication errors are surfaced immediately (no retry)
            - API errors include contextual information for debugging
            - Timeout errors preserve original timeout context

        Args:
            method (str): HTTP method (GET, POST, PUT, DELETE)
            endpoint (str): API endpoint path relative to base_url
            **kwargs: Additional arguments passed to aiohttp request
                     (json, params, headers, etc.)

        Returns:
            Union[Dict[str, Any], List[Dict[str, Any]]]: Parsed JSON response
            from Home Assistant API. Single objects return Dict,
            array responses return List[Dict].

        Raises:
            HomeAssistantConnectionError: Network connectivity issues, DNS failures,
                                        or Home Assistant service unavailable
            HomeAssistantAuthError: Invalid token or authentication failure (401)
            HomeAssistantAPIError: API-level errors (4xx/5xx status codes) with
                                 detailed error messages from Home Assistant
            HomeAssistantTimeoutError: Request exceeded configured timeout period

        Example:
            >>> # All these calls trigger auto-connect if needed:
            >>> states = await client._make_request("GET", "/api/states")
            >>> result = await client._make_request("POST", "/api/services/light/turn_on",
            ...                                   json={"entity_id": "light.bedroom"})

        Performance Notes:
            - Session creation overhead only on first request or after disconnect
            - Persistent connections maintained for optimal performance
            - Connection pooling handled automatically by aiohttp
        """
        # Auto-connect if not connected (self-healing behavior)
        if self.session is None:
            await self.connect()

        url = urljoin(self.base_url, endpoint)

        try:
            async with self.session.request(method, url, **kwargs) as response:
                await self._handle_response_errors(response)
                return await response.json()

        except aiohttp.ClientConnectorCertificateError as e:
            raise HomeAssistantConnectionError(
                f"TLS certificate verification failed: {e}\n\n"
                "If your Home Assistant uses a self-signed certificate, "
                "set HA_SSL_VERIFY=false in your configuration."
            )
        except aiohttp.ClientConnectorError as e:
            raise HomeAssistantConnectionError(f"Connection failed: {str(e)}")
        except aiohttp.ServerTimeoutError as e:
            raise HomeAssistantTimeoutError(f"Request timed out: {str(e)}")
        except aiohttp.ClientError as e:
            raise HomeAssistantConnectionError(f"Client error: {str(e)}")

    async def _handle_response_errors(self, response: aiohttp.ClientResponse) -> None:
        """
        Handle HTTP response errors.

        Args:
            response: aiohttp response object

        Raises:
            HomeAssistantAuthError: For 401 responses
            HomeAssistantAPIError: For other error responses
        """
        if response.status == 401:
            error_text = await response.text()
            raise HomeAssistantAuthError(f"Authentication failed: {error_text}")

        if response.status >= 400:
            error_text = await response.text()
            raise HomeAssistantAPIError(
                f"API error: {error_text}", status_code=response.status
            )

    async def get_all_states(self) -> List[Dict[str, Any]]:
        """
        Get the current state of all entities.

        Returns:
            List of all entity states
        """
        return await self._make_request("GET", "/api/states")

    async def call_service(
        self, domain: str, service: str, service_data: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Call a Home Assistant service.

        Args:
            domain: Service domain (e.g., 'light', 'switch')
            service: Service name (e.g., 'turn_on', 'turn_off')
            service_data: Optional data for the service call

        Returns:
            List of affected entities with their new states

        Raises:
            HomeAssistantValidationError: If service data is invalid
        """
        if service_data is None:
            service_data = {}

        if not self.validate_service_data(domain, service, service_data):
            raise HomeAssistantValidationError(
                f"Invalid service data for {domain}.{service}", field="service_data"
            )

        endpoint = f"/api/services/{domain}/{service}"
        return await self._make_request("POST", endpoint, json=service_data)

    async def get_config(self) -> Dict[str, Any]:
        """
        Get Home Assistant configuration.

        Returns:
            Configuration data including version, location, timezone, etc.
        """
        return await self._make_request("GET", "/api/config")

    async def get_services(self) -> Dict[str, Any]:
        """
        Get available services and their schemas.

        Returns:
            Dictionary of domains and their available services
        """
        return await self._make_request("GET", "/api/services")

    async def get_history(
        self, entity_id: str, start_time: datetime, end_time: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """
        Get historical data for an entity.

        Args:
            entity_id: Entity to get history for
            start_time: Start time for history query
            end_time: Optional end time (defaults to start_time + 1 day, per HA)

        Returns:
            List of historical state changes
        """
        if not self.validate_entity_id(entity_id):
            raise HomeAssistantValidationError(
                f"Invalid entity ID format: {entity_id}", field="entity_id"
            )

        start_iso = _to_utc_iso(start_time)
        endpoint = f"/api/history/period/{start_iso}?filter_entity_id={entity_id}"

        if end_time is not None:
            end_iso = _to_utc_iso(end_time)
            endpoint += f"&end_time={end_iso}"

        return await self._make_request("GET", endpoint)

    def validate_entity_id(self, entity_id: str) -> bool:
        """
        Validate entity ID format.

        Entity IDs must follow the format: domain.entity_name
        where both parts contain only lowercase letters, numbers, and underscores.

        Args:
            entity_id: Entity ID to validate

        Returns:
            True if valid, False otherwise
        """
        if not entity_id or not isinstance(entity_id, str):
            return False

        # Entity ID pattern: domain.entity_name
        # Both parts: lowercase letters, numbers, underscores only
        pattern = r"^[a-z][a-z0-9_]*\.[a-z0-9_]+$"
        return bool(re.match(pattern, entity_id))

    def validate_service_data(
        self, domain: str, service: str, service_data: Dict[str, Any]
    ) -> bool:
        """
        Validate service call data.

        Performs basic validation of service data structure.
        Full validation would require service schema from HA.

        Args:
            domain: Service domain
            service: Service name
            service_data: Data to validate

        Returns:
            True if valid, False otherwise
        """
        if not isinstance(service_data, dict):
            return False

        # Validate entity_id if present
        if "entity_id" in service_data:
            entity_id = service_data["entity_id"]
            if isinstance(entity_id, str):
                if not self.validate_entity_id(entity_id):
                    return False
            elif isinstance(entity_id, list):
                if not all(self.validate_entity_id(eid) for eid in entity_id):
                    return False
            else:
                return False

        # Basic validation for common parameters
        if "brightness" in service_data:
            brightness = service_data["brightness"]
            if not isinstance(brightness, (int, float)) or not (0 <= brightness <= 255):
                return False

        if "target" in service_data:
            target = service_data["target"]
            if not isinstance(target, dict):
                return False

        return True

    async def get_areas(self) -> List[Dict[str, Any]]:
        """
        Get all areas from Home Assistant via WebSocket.

        Returns:
            List of areas with their metadata

        Raises:
            HomeAssistantAPIError: If API call fails
        """
        # Auto-connect REST session if needed (WebSocket will auto-connect itself)
        if self.session is None:
            await self.connect()
        # Use WebSocket client for area registry
        return await self.ws_client.get_areas()

    async def get_devices(self) -> List[Dict[str, Any]]:
        """
        Get all devices from Home Assistant via WebSocket.

        Returns:
            List of devices with their metadata

        Raises:
            HomeAssistantAPIError: If API call fails
        """
        # Auto-connect REST session if needed (WebSocket will auto-connect itself)
        if self.session is None:
            await self.connect()
        # Use WebSocket client for device registry
        return await self.ws_client.get_devices()

    async def get_entity_registry(self) -> List[Dict[str, Any]]:
        """
        Get entity registry with device and area relationships via WebSocket.

        Returns:
            List of entity registry entries

        Raises:
            HomeAssistantAPIError: If API call fails
        """
        # Auto-connect REST session if needed (WebSocket will auto-connect itself)
        if self.session is None:
            await self.connect()
        # Use WebSocket client for entity registry
        return await self.ws_client.get_entities()
