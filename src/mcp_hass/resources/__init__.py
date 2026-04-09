# SPDX-License-Identifier: BSD-3-Clause
"""
MCP-HASS Resource Registration Module.

Provides access to Home Assistant configuration and documentation resources.
"""

from .handlers import register_resources

__all__ = [
    "register_resources",
]
