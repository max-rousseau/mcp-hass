# SPDX-License-Identifier: BSD-3-Clause
"""
Spatial/location-based tools for MCP-HASS.

Provides area and zone management:
- list_areas: Get all areas/zones defined in Home Assistant
- get_area_devices: Get all devices in a specific area/zone
"""

import json
from typing import TYPE_CHECKING

from mcp.types import ToolAnnotations

if TYPE_CHECKING:
    from .context import ToolContext


def register_spatial_tools(ctx: "ToolContext") -> None:
    """Register spatial/location-based tools with FastMCP.

    Args:
        ctx: Tool context with mcp, ha_client, config, logger dependencies
    """

    @ctx.mcp.tool(
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            openWorldHint=True,
        )
    )
    async def list_areas() -> str:
        """Get all areas/zones defined in Home Assistant."""
        try:
            areas = await ctx.ha_client.get_areas()
            result = json.dumps(areas, indent=2, default=str)

            token_limit = ctx.get_token_limit()
            if token_limit is not None:
                token_count = ctx.count_tokens(result)
                if token_count > token_limit:
                    return json.dumps(
                        {
                            "error": (
                                f"Areas response is "
                                f"{token_count:,} tokens, exceeds limit of {token_limit:,}."
                            ),
                            "areas_count": len(areas),
                            "token_count": token_count,
                            "token_limit": token_limit,
                        },
                        indent=2,
                    )

            return result
        except Exception as e:
            raise ValueError(f"Failed to list areas: {e}")

    @ctx.mcp.tool(
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            openWorldHint=True,
        )
    )
    async def get_area_devices(area_name: str) -> str:
        """Get all devices in a specific area/zone.

        Args:
            area_name: Display name or area_id slug of the area to get devices for
        """
        try:
            areas = await ctx.ha_client.get_areas()
            area_id = next(
                (
                    a.get("area_id")
                    for a in areas
                    if a.get("name", "").lower() == area_name.lower()
                    or a.get("area_id", "").lower() == area_name.lower()
                ),
                None,
            )

            if not area_id:
                raise ValueError(f"Area '{area_name}' not found")

            devices = await ctx.ha_client.get_devices()
            area_devices = [
                device for device in devices if device.get("area_id") == area_id
            ]

            result = json.dumps(area_devices, indent=2, default=str)

            token_limit = ctx.get_token_limit()
            if token_limit is not None:
                token_count = ctx.count_tokens(result)
                if token_count > token_limit:
                    return json.dumps(
                        {
                            "error": (
                                f"Area devices response is "
                                f"{token_count:,} tokens, exceeds limit of {token_limit:,}."
                            ),
                            "area_name": area_name,
                            "devices_count": len(area_devices),
                            "token_count": token_count,
                            "token_limit": token_limit,
                        },
                        indent=2,
                    )

            return result
        except Exception as e:
            raise ValueError(f"Failed to get area devices: {e}")
