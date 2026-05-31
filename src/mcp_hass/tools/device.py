# SPDX-License-Identifier: BSD-3-Clause
"""
Device management tools for MCP-HASS.

Provides device discovery and device-entity relationship mapping:
- find_devices: Primary device discovery with filtering and OData-like field selection
- get_device_entities: Get all entities for a specific device
"""

import json
from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .context import ToolContext


def register_device_tools(ctx: "ToolContext") -> None:
    """Register device management tools with FastMCP.

    Args:
        ctx: Tool context with mcp, ha_client, config, logger dependencies
    """

    @ctx.mcp.tool()
    async def find_devices(
        name: str = "*",
        manufacturer: Optional[str] = None,
        model: Optional[str] = None,
        area: Optional[str] = None,
        select: Optional[List[str]] = None,
        expand: Optional[List[str]] = None,
    ) -> str:
        """Find Home Assistant devices with filtering and OData-like field selection.

        Primary device discovery tool. Devices represent physical hardware (e.g.,
        a Hue bulb, thermostat, or smart plug) and have a 1:N relationship with
        entities. Uses OData-like `select` and `expand` parameters to control
        response size for token efficiency.

        IMPORTANT: Only include parameters you need. Omit unused parameters entirely
        rather than setting them to null.

        Default Response Fields:
            - id: Device identifier
            - name: Device name
            - area_id: Assigned area
            - entities: Minimal entity list (entity_id + friendly_name)

        Args:
            name: Substring to match device name (use "*" for all)
            manufacturer: Manufacturer filter (e.g., "Philips", "Ecobee")
            model: Model filter (e.g., "Hue White Ambiance")
            area: Area display name or area_id slug filter (e.g., "bedroom", "living_room")
            select: Additional scalar fields. Valid: "manufacturer", "model", "model_id",
                "sw_version", "hw_version", "serial_number", "via_device_id".
            expand: Nested objects to fully include. Valid: "entities" (full entity data),
                "identifiers", "connections".

        Returns:
            JSON array of matching devices with selected fields.

        Examples:
            # Find all devices (minimal response with entities)
            find_devices()

            # Find devices by manufacturer
            find_devices(manufacturer="Philips")

            # Find devices in an area with model info
            find_devices(area="bedroom", select=["manufacturer", "model"])

            # Find devices with full entity data
            find_devices(manufacturer="Ecobee", expand=["entities"])
        """
        devices = await ctx.ha_client.get_devices()

        entity_registry = await ctx.ha_client.get_entity_registry()
        entities_by_device: dict = {}
        for entity in entity_registry:
            device_id = entity.get("device_id")
            if device_id:
                if device_id not in entities_by_device:
                    entities_by_device[device_id] = []
                entities_by_device[device_id].append(entity)

        all_states = await ctx.ha_client.get_all_states()
        states_dict = {s["entity_id"]: s for s in all_states}

        target_area_id = None
        if area:
            areas = await ctx.ha_client.get_areas()
            target_area_id = next(
                (
                    a["area_id"]
                    for a in areas
                    if a["name"].lower() == area.lower()
                    or a["area_id"].lower() == area.lower()
                ),
                None,
            )
            if not target_area_id:
                areas_json = json.dumps(areas, indent=2, default=str)
                raise ValueError(f"Area '{area}' not found. Valid areas:\n{areas_json}")

        matching_devices = []

        for device in devices:
            if target_area_id and device.get("area_id") != target_area_id:
                continue

            if manufacturer:
                device_manufacturer = device.get("manufacturer", "")
                if manufacturer.lower() not in device_manufacturer.lower():
                    continue

            if model:
                device_model = device.get("model", "")
                if model.lower() not in device_model.lower():
                    continue

            if name != "*":
                device_name = device.get("name", "") or ""
                name_by_user = device.get("name_by_user", "") or ""
                if not (
                    name.lower() in device_name.lower()
                    or name.lower() in name_by_user.lower()
                ):
                    continue

            device_id = device.get("id")
            result = {
                "id": device_id,
                "name": device.get("name_by_user") or device.get("name"),
                "area_id": device.get("area_id"),
            }

            if select:
                valid_select = {
                    "manufacturer",
                    "model",
                    "model_id",
                    "sw_version",
                    "hw_version",
                    "serial_number",
                    "via_device_id",
                }
                for field in select:
                    if field in valid_select and field in device:
                        result[field] = device[field]

            device_entity_list = entities_by_device.get(device_id, [])
            expand_entities = expand and "entities" in expand

            if expand_entities:
                result["entities"] = []
                for entity_reg in device_entity_list:
                    entity_id = entity_reg.get("entity_id")
                    if entity_id and entity_id in states_dict:
                        result["entities"].append(states_dict[entity_id])
            else:
                result["entities"] = []
                for entity_reg in device_entity_list:
                    entity_id = entity_reg.get("entity_id")
                    if entity_id and entity_id in states_dict:
                        entity_state = states_dict[entity_id]
                        result["entities"].append(
                            {
                                "entity_id": entity_id,
                                "attributes": {
                                    "friendly_name": entity_state["attributes"].get(
                                        "friendly_name", entity_id
                                    )
                                },
                            }
                        )

            if expand:
                if "identifiers" in expand:
                    result["identifiers"] = device.get("identifiers", [])
                if "connections" in expand:
                    result["connections"] = device.get("connections", [])

            matching_devices.append(result)

        json_response = json.dumps(matching_devices, indent=2, default=str)

        token_limit = ctx.get_token_limit()
        if token_limit is not None:
            token_count = ctx.count_tokens(json_response)
            if token_count > token_limit:
                error_message = (
                    f"Your request is too broad and has resulted in a response of "
                    f"{token_count:,} tokens, this exceeds my token limit of {token_limit:,}. "
                    f"Please make a more focused request using filters like manufacturer, "
                    f"model, or area."
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

    @ctx.mcp.tool()
    async def get_device_entities(device_id: str) -> str:
        """Get all entities associated with a specific device.

        Args:
            device_id: The device ID to get entities for
        """
        try:
            if ctx.ha_client.session is None:
                await ctx.ha_client.connect()

            entity_registry = await ctx.ha_client.get_entity_registry()
            device_entities = [
                entity
                for entity in entity_registry
                if entity.get("device_id") == device_id
            ]

            result = json.dumps(device_entities, indent=2, default=str)

            token_limit = ctx.get_token_limit()
            if token_limit is not None:
                token_count = ctx.count_tokens(result)
                if token_count > token_limit:
                    return json.dumps(
                        {
                            "error": (
                                f"Device entities response is "
                                f"{token_count:,} tokens, exceeds limit of {token_limit:,}."
                            ),
                            "device_id": device_id,
                            "entities_count": len(device_entities),
                            "token_count": token_count,
                            "token_limit": token_limit,
                        },
                        indent=2,
                    )

            return result
        except Exception as e:
            raise ValueError(f"Failed to get device entities: {e}")
