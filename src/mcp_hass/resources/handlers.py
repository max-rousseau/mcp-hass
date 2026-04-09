# SPDX-License-Identifier: BSD-3-Clause
"""
FastMCP resource registration for MCP-HASS.

Provides access to Home Assistant configuration and documentation.
"""

import json
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mcp_hass.tools.context import ToolContext


def _load_content(filename: str) -> str:
    """Load static content from content directory.

    Args:
        filename: Name of file in content/ directory

    Returns:
        File contents as string
    """
    content_dir = Path(__file__).parent / "content"
    content_file = content_dir / filename
    return content_file.read_text(encoding="utf-8")


def register_resources(ctx: "ToolContext") -> None:
    """Register FastMCP resources.

    Args:
        ctx: Tool context with mcp, ha_client, config, logger dependencies
    """

    @ctx.mcp.resource("mcp-hass://config")
    async def get_ha_config() -> str:
        """Get Home Assistant configuration."""
        try:
            config = await ctx.ha_client.get_config()
            return json.dumps(config, indent=2, default=str)
        except Exception as e:
            ctx.logger.error("Failed to get HA config", exc_info=True)
            return f"Error getting config: {e}"

    @ctx.mcp.resource("mcp-hass://config-guide")
    async def hass_config_structure_guide() -> str:
        """Home Assistant Configuration Structure Guide."""
        return _load_content("config_guide.md")
