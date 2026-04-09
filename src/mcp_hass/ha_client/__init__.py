# SPDX-License-Identifier: BSD-3-Clause
"""
Home Assistant client module for MCP-HASS integration.

This module provides async HTTP and WebSocket client functionality for
communicating with Home Assistant's REST and WebSocket API endpoints.
"""

from .client import HomeAssistantClient
from .websocket_client import HomeAssistantWebSocketClient
from .exceptions import (
    HomeAssistantError,
    HomeAssistantConnectionError,
    HomeAssistantAuthError,
    HomeAssistantAPIError,
    HomeAssistantTimeoutError,
    HomeAssistantValidationError,
)

__all__ = [
    "HomeAssistantClient",
    "HomeAssistantWebSocketClient",
    "HomeAssistantError",
    "HomeAssistantConnectionError",
    "HomeAssistantAuthError",
    "HomeAssistantAPIError",
    "HomeAssistantTimeoutError",
    "HomeAssistantValidationError",
]
