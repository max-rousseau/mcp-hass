# SPDX-License-Identifier: BSD-3-Clause
"""
MCP-HASS Tool Registration Module.

Purpose:
    Central registry for all MCP-HASS tools using modular, dependency-injection
    architecture. Each tool domain is implemented in a focused module that receives
    dependencies via ToolContext.

Architecture:
    - ToolContext: Dataclass containing all dependencies (mcp, ha_client, config, logger)
    - Modular Registration: Each domain has register_*_tools(ctx) function
    - FastMCP Decorators: Tools registered via @ctx.mcp.tool()
    - Explicit Exports: __all__ defines public API

Tool Modules:
    - entity.py: Entity discovery and history (find_entities, get_entity_history)
    - service.py: Service operations (call_service, get_services, get_service_detail)
    - spatial.py: Area/zone management (list_areas, get_area_devices)
    - device.py: Device discovery (find_devices, get_device_entities)
    - bulk.py: Bulk operations (call_service_bulk)
    - camera.py: Camera snapshots (get_camera_snapshot)
    - yaml_config.py: Configuration reload (reload_yaml_config)

Usage Example:
    from mcp_hass.tools import ToolContext, register_all_tools

    # Create context with dependencies
    ctx = ToolContext(
        mcp=fastmcp_instance,
        ha_client=ha_client_instance,
        config=config_manager,
        logger=logger_instance
    )

    # Register all tools
    register_all_tools(ctx)

Adding New Tools:
    1. Create new module in tools/ (e.g., automation.py)
    2. Define register_automation_tools(ctx: ToolContext) function
    3. Use @ctx.mcp.tool() decorator for tool functions
    4. Import and call in register_all_tools()
    5. Add to __all__ exports
"""

from .bulk import register_bulk_tools
from .camera import register_camera_tools
from .context import ToolContext
from .device import register_device_tools
from .entity import register_entity_tools
from .service import register_service_tools
from .spatial import register_spatial_tools
from .yaml_config import register_yaml_config_tools


def register_all_tools(ctx: ToolContext) -> None:
    """Register all MCP-HASS tools with FastMCP.

    Args:
        ctx: Tool context with required dependencies

    Raises:
        Exception: If any tool registration fails
    """
    ctx.logger.debug("Registering entity tools...")
    register_entity_tools(ctx)

    ctx.logger.debug("Registering service tools...")
    register_service_tools(ctx)

    ctx.logger.debug("Registering spatial tools...")
    register_spatial_tools(ctx)

    ctx.logger.debug("Registering device tools...")
    register_device_tools(ctx)

    ctx.logger.debug("Registering bulk tools...")
    register_bulk_tools(ctx)

    ctx.logger.debug("Registering camera tools...")
    register_camera_tools(ctx)

    ctx.logger.debug("Registering YAML config tools...")
    register_yaml_config_tools(ctx)

    ctx.logger.debug("All tools registered successfully")


__all__ = [
    "ToolContext",
    "register_all_tools",
    "register_entity_tools",
    "register_service_tools",
    "register_spatial_tools",
    "register_device_tools",
    "register_bulk_tools",
    "register_camera_tools",
    "register_yaml_config_tools",
]
