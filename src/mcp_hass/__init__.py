# SPDX-License-Identifier: BSD-3-Clause
"""
MCP-HASS: Model Context Protocol integration for Home Assistant.

This package provides a standardized MCP interface for interacting with
Home Assistant instances through REST and WebSocket APIs.
"""

__version__ = "1.0.0"
__author__ = "Maxime Rousseau"

from .ha_client import HomeAssistantClient

__all__ = ["HomeAssistantClient"]
