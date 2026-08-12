# SPDX-License-Identifier: BSD-3-Clause
"""
Entity management tools for MCP-HASS.

Provides entity discovery and history retrieval:
- find_entities: Primary entity discovery with multi-criteria filtering
- get_entity_history: Historical state data retrieval
"""

import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from mcp.types import ToolAnnotations

if TYPE_CHECKING:
    from .context import ToolContext


def register_entity_tools(ctx: "ToolContext") -> None:
    """Register entity management tools with FastMCP.

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
    async def get_entity_history(entity_id: str, hours: float = 24.0) -> str:
        """Get historical state data for an entity.

        Returns a token-efficient format with entity metadata in the header
        and a compact array of state changes.

        Args:
            entity_id: Entity ID to get history for
            hours: Number of hours of history to retrieve (default: 24)

        Returns:
            JSON object with entity_id, attributes (friendly_name, unit_of_measurement,
            device_class), and history array of {state, last_changed} entries.

        Example response:
            {
                "entity_id": "sensor.temperature",
                "attributes": {
                    "friendly_name": "Temperature",
                    "unit_of_measurement": "°F",
                    "device_class": "temperature"
                },
                "history": [
                    {"state": "72.5", "last_changed": "2025-12-11T01:15:49+00:00"},
                    {"state": "73.0", "last_changed": "2025-12-11T01:30:00+00:00"}
                ]
            }
        """
        try:
            now = datetime.now(timezone.utc)
            start_time = now - timedelta(hours=hours)
            raw_history = await ctx.ha_client.get_history(
                entity_id, start_time, end_time=now
            )

            if not raw_history or not raw_history[0]:
                return json.dumps(
                    {"entity_id": entity_id, "attributes": {}, "history": []},
                    indent=2,
                    default=str,
                )

            history_entries = raw_history[0]
            first_entry = history_entries[0] if history_entries else {}
            raw_attrs = first_entry.get("attributes", {})

            optimized = {
                "entity_id": entity_id,
                "attributes": {
                    "friendly_name": raw_attrs.get("friendly_name", entity_id),
                    "unit_of_measurement": raw_attrs.get("unit_of_measurement"),
                    "device_class": raw_attrs.get("device_class"),
                },
                "history": [
                    {
                        "state": entry.get("state"),
                        "last_changed": entry.get("last_changed"),
                    }
                    for entry in history_entries
                ],
            }

            optimized["attributes"] = {
                k: v for k, v in optimized["attributes"].items() if v is not None
            }

            result = json.dumps(optimized, indent=2, default=str)

            token_limit = ctx.get_token_limit()
            if token_limit is not None:
                token_count = ctx.count_tokens(result)
                if token_count > token_limit:
                    return json.dumps(
                        {
                            "error": (
                                f"History response is "
                                f"{token_count:,} tokens, exceeds limit of {token_limit:,}. "
                                f"Reduce the 'hours' parameter to retrieve less history."
                            ),
                            "entity_id": entity_id,
                            "hours_requested": hours,
                            "history_entries": len(history_entries),
                            "token_count": token_count,
                            "token_limit": token_limit,
                        },
                        indent=2,
                    )

            return result
        except Exception as e:
            raise ValueError(f"Failed to get entity history: {e}")

    @ctx.mcp.tool(
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            openWorldHint=True,
        )
    )
    async def find_entities(
        name: str = "*",
        domain: Optional[str] = None,
        area: Optional[str] = None,
        device_class: Optional[str] = None,
        state: Optional[str] = None,
        attributes: Optional[Dict[str, Any]] = None,
        select: Optional[List[str]] = None,
        expand: Optional[List[str]] = None,
    ) -> str:
        """Find Home Assistant entities with flexible filtering and OData-like field selection.

        Primary entity discovery tool. Filters by name, domain, area, device class,
        state value, and arbitrary attributes. Uses OData-like `select` and `expand`
        parameters to control response size for token efficiency.

        IMPORTANT: Only include parameters you need. Omit unused parameters entirely
        rather than setting them to null.

        Default Response Fields:
            - entity_id: Always included
            - attributes.friendly_name: Always included (minimal attributes object)

        Args:
            name: Substring to match entity_id or friendly_name (use "*" for all)
            domain: Domain filter (e.g., "light", "sensor", "switch"). Omit if not filtering by domain.
            area: Area display name or area_id slug filter (e.g., "bedroom", "living_room"). Omit if not filtering by area.
            device_class: Device class filter (e.g., "temperature", "motion"). Omit if not filtering by device class.
            state: State value filter (e.g., "on", "off", "unavailable"). Omit if not filtering by state.
            attributes: Attribute filters as dict. Omit if not filtering by attributes.
            select: Additional scalar fields to include. Valid values: "state", "last_changed", "last_updated".
            expand: Nested objects to fully include. Valid values: "attributes" (full), "context".

        Returns:
            JSON array of matching entities with selected fields.

        Examples:
            # Minimal discovery (entity_id + friendly_name only)
            find_entities(domain="light")

            # Include current state
            find_entities(domain="light", select=["state"])

            # Include state and timestamps
            find_entities(domain="sensor", select=["state", "last_changed"])

            # Full attributes expansion
            find_entities(domain="light", area="bedroom", expand=["attributes"])

            # Combined: state + full attributes
            find_entities(domain="sensor", device_class="temperature", select=["state"], expand=["attributes"])
        """
        all_states = await ctx.ha_client.get_all_states()
        states_dict = {s["entity_id"]: s for s in all_states}

        candidate_entity_ids = set(states_dict.keys())

        if area:
            areas = await ctx.ha_client.get_areas()
            area_id = next(
                (
                    a["area_id"]
                    for a in areas
                    if a["name"].lower() == area.lower()
                    or a["area_id"].lower() == area.lower()
                ),
                None,
            )

            if not area_id:
                areas_json = json.dumps(areas, indent=2, default=str)
                raise ValueError(f"Area '{area}' not found. Valid areas:\n{areas_json}")

            devices = await ctx.ha_client.get_devices()
            area_device_ids = {d["id"] for d in devices if d["area_id"] == area_id}

            entity_registry = await ctx.ha_client.get_entity_registry()
            area_entity_ids = {
                e["entity_id"]
                for e in entity_registry
                if e["device_id"] in area_device_ids
            }

            candidate_entity_ids &= area_entity_ids

        matching_entities = []

        for entity_id in candidate_entity_ids:
            entity_state = states_dict[entity_id]

            if domain and not entity_id.startswith(f"{domain}."):
                continue

            if device_class:
                if entity_state["attributes"].get("device_class") != device_class:
                    continue

            if state and entity_state["state"] != state:
                continue

            if attributes:
                entity_attrs = entity_state["attributes"]
                if not all(entity_attrs.get(k) == v for k, v in attributes.items()):
                    continue

            if name != "*":
                name_lower = name.lower()
                entity_id_lower = entity_id.lower()
                friendly_name_lower = (
                    entity_state["attributes"].get("friendly_name", "").lower()
                )

                if not (
                    name_lower in entity_id_lower or name_lower in friendly_name_lower
                ):
                    continue

            result = {
                "entity_id": entity_state["entity_id"],
                "attributes": {
                    "friendly_name": entity_state["attributes"].get(
                        "friendly_name", entity_state["entity_id"]
                    )
                },
            }

            if select:
                valid_select = {"state", "last_changed", "last_updated"}
                for field in select:
                    if field in valid_select and field in entity_state:
                        result[field] = entity_state[field]

            if expand:
                if "attributes" in expand:
                    result["attributes"] = entity_state["attributes"]
                if "context" in expand:
                    result["context"] = entity_state["context"]

            matching_entities.append(result)

        json_response = json.dumps(matching_entities, indent=2, default=str)

        token_limit = ctx.get_token_limit()
        if token_limit is not None:
            token_count = ctx.count_tokens(json_response)
            if token_count > token_limit:
                error_message = (
                    f"Your request is too broad and has resulted in a response of "
                    f"{token_count:,} tokens, this exceeds my token limit of {token_limit:,}. "
                    f"Please make a more focused request, using the various filtering capabilities."
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
