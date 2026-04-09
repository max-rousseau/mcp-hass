# SPDX-License-Identifier: BSD-3-Clause
"""
Home Assistant service tools for MCP-HASS.

Provides service operations:
- call_service: Universal service caller for all Home Assistant services
- get_services: Service discovery (summary format)
- get_service_detail: Detailed schema for a specific service
"""

import json
from typing import Any, Dict, Optional, TYPE_CHECKING

from mcp.types import ToolAnnotations

if TYPE_CHECKING:
    from .context import ToolContext


def register_service_tools(ctx: "ToolContext") -> None:
    """Register Home Assistant service tools with FastMCP.

    Args:
        ctx: Tool context with mcp, ha_client, config, logger dependencies
    """

    @ctx.mcp.tool(
        annotations=ToolAnnotations(
            readOnlyHint=False,
            destructiveHint=True,
            openWorldHint=True,
        )
    )
    async def call_service(
        domain: str,
        service: str,
        entity_id: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Call a Home Assistant service to control devices or trigger actions.

        Args:
            domain: Service domain (e.g., light, switch, climate)
            service: Service name (e.g., turn_on, turn_off, set_temperature)
            entity_id: Target entity ID (optional)
            data: Additional service data (e.g., brightness, temperature)
        """
        try:
            service_data = data or {}
            if entity_id:
                service_data["entity_id"] = entity_id

            result = await ctx.ha_client.call_service(domain, service, service_data)
            return json.dumps(result, indent=2, default=str)
        except Exception as e:
            raise ValueError(f"Failed to call service: {e}")

    @ctx.mcp.tool(
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            openWorldHint=True,
        )
    )
    async def get_services() -> str:
        """Get summary of all available Home Assistant services.

        Returns a compact summary listing all domains and their available service
        names. This is optimized for token efficiency - use get_service_detail()
        to get full schema information for a specific service.

        Returns:
            JSON array of domain summaries, each containing:
            - domain: Service domain name (e.g., "light", "switch")
            - services: List of available service names for that domain

        Example response:
            [
                {"domain": "light", "services": ["turn_on", "turn_off", "toggle"]},
                {"domain": "switch", "services": ["turn_on", "turn_off", "toggle"]}
            ]
        """
        try:
            raw_services = await ctx.ha_client.get_services()

            summary = []
            for item in raw_services:
                domain = item["domain"]
                service_names = list(item["services"].keys())
                summary.append({"domain": domain, "services": service_names})

            json_response = json.dumps(summary, indent=2, default=str)

            token_limit = ctx.get_token_limit()
            if token_limit is not None:
                token_count = ctx.count_tokens(json_response)
                if token_count > token_limit:
                    error_message = (
                        f"Services summary response of {token_count:,} tokens "
                        f"exceeds limit of {token_limit:,}. This is unexpected "
                        f"for a summary response - please report this issue."
                    )
                    return json.dumps(
                        {
                            "error": error_message,
                            "token_count": token_count,
                            "token_limit": token_limit,
                        },
                        indent=2,
                    )

            return json_response
        except Exception as e:
            raise ValueError(f"Failed to get services: {e}")

    @ctx.mcp.tool(
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            openWorldHint=True,
        )
    )
    async def get_service_detail(domain: str, service: str) -> str:
        """Get detailed schema information for a specific Home Assistant service.

        Returns the full service definition including all fields, their types,
        requirements, examples, and selectors. Use this after get_services()
        to get details for a specific service you want to call.

        Args:
            domain: Service domain (e.g., "light", "switch", "climate")
            service: Service name (e.g., "turn_on", "turn_off", "set_temperature")

        Returns:
            JSON object containing:
            - domain: The service domain
            - service: The service name
            - fields: Detailed field definitions with types, requirements, examples

        Raises:
            ValueError: If domain or service not found

        Example:
            get_service_detail("light", "turn_on")
            # Returns full schema for light.turn_on including brightness, color, etc.
        """
        try:
            raw_services = await ctx.ha_client.get_services()

            domain_data = next(
                (item for item in raw_services if item["domain"] == domain),
                None,
            )

            if domain_data is None:
                available_domains = [item["domain"] for item in raw_services]
                raise ValueError(
                    f"Domain '{domain}' not found. "
                    f"Available domains: {', '.join(sorted(available_domains)[:20])}"
                    f"{'...' if len(available_domains) > 20 else ''}"
                )

            services = domain_data["services"]
            if service not in services:
                available_services = list(services.keys())
                raise ValueError(
                    f"Service '{service}' not found in domain '{domain}'. "
                    f"Available services: {', '.join(sorted(available_services))}"
                )

            service_detail = {
                "domain": domain,
                "service": service,
                "fields": services[service],
            }

            result = json.dumps(service_detail, indent=2, default=str)

            token_limit = ctx.get_token_limit()
            if token_limit is not None:
                token_count = ctx.count_tokens(result)
                if token_count > token_limit:
                    return json.dumps(
                        {
                            "error": (
                                f"Service detail response is "
                                f"{token_count:,} tokens, exceeds limit of {token_limit:,}."
                            ),
                            "domain": domain,
                            "service": service,
                            "token_count": token_count,
                            "token_limit": token_limit,
                        },
                        indent=2,
                    )

            return result
        except ValueError:
            raise
        except Exception as e:
            raise ValueError(f"Failed to get service detail: {e}")
