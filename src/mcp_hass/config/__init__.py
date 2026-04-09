# SPDX-License-Identifier: BSD-3-Clause
"""Configuration management module for MCP-HASS."""

from .manager import ConfigurationManager, ConfigurationError

__all__ = ["ConfigurationManager", "ConfigurationError"]
