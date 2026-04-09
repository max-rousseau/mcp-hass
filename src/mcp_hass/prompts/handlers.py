# SPDX-License-Identifier: BSD-3-Clause
"""
FastMCP prompt registration for MCP-HASS.

Provides guided workflows and decision-making assistance for common tasks.
"""

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


def register_prompts(ctx: "ToolContext") -> None:
    """Register FastMCP prompts.

    Args:
        ctx: Tool context with mcp, ha_client, config, logger dependencies
    """

    @ctx.mcp.prompt()
    def discover_area_entities() -> str:
        """Hierarchical discovery workflow for finding entities in a specific area.

        This prompt demonstrates the efficient area → device → entity discovery
        pattern, which is more targeted than using find_entities with broad filters.
        """
        return _load_content("area_discovery.md")

    @ctx.mcp.prompt()
    def tool_selection_guide() -> str:
        """Guide for selecting the most efficient tool for entity discovery tasks."""
        return _load_content("tool_selection.md")
