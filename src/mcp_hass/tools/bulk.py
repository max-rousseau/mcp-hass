# SPDX-License-Identifier: BSD-3-Clause
"""
Bulk operation tools for MCP-HASS.

Provides multi-entity service operations:
- call_service_bulk: Execute service on multiple entities with result tracking
"""

import json
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .context import ToolContext


def register_bulk_tools(ctx: "ToolContext") -> None:
    """Register bulk operation tools with FastMCP.

    Args:
        ctx: Tool context with mcp, ha_client, config, logger dependencies
    """

    @ctx.mcp.tool()
    async def call_service_bulk(
        domain: str,
        service: str,
        entity_ids: List[str],
        data: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Call a service on multiple entities at once.

        Args:
            domain: Service domain (e.g., 'light', 'switch')
            service: Service name (e.g., 'turn_on', 'turn_off')
            entity_ids: List of entity IDs to apply service to
            data: Optional service data
        """
        try:
            if ctx.ha_client.session is None:
                await ctx.ha_client.connect()

            results = []

            for entity_id in entity_ids:
                try:
                    service_data = (data or {}).copy()
                    service_data["entity_id"] = entity_id
                    result = await ctx.ha_client.call_service(
                        domain, service, service_data
                    )
                    results.append(
                        {"entity_id": entity_id, "success": True, "result": result}
                    )
                except Exception as e:
                    ctx.logger.error(
                        "Bulk service call failed for %s", entity_id, exc_info=True
                    )
                    results.append(
                        {
                            "entity_id": entity_id,
                            "success": False,
                            "error": str(e),
                        }
                    )

            return json.dumps(
                {
                    "total": len(entity_ids),
                    "succeeded": sum(1 for r in results if r["success"]),
                    "failed": sum(1 for r in results if not r["success"]),
                    "results": results,
                },
                indent=2,
                default=str,
            )
        except Exception as e:
            raise ValueError(f"Failed to perform bulk service call: {e}")
