# SPDX-License-Identifier: BSD-3-Clause
"""
Tool registration context providing dependencies to tool modules.

Purpose:
    Defines ToolContext dataclass for dependency injection across all tool modules.
    Provides a consistent interface for accessing shared resources (FastMCP instance,
    Home Assistant client, configuration, logging) without global state.

Pattern:
    This implements the "context object" pattern for dependency injection:
    - Single source of truth for all tool dependencies
    - Type-safe access to resources
    - Testable (easy to mock context in tests)
    - No global state or singletons

Usage Example:
    def register_my_tools(ctx: ToolContext) -> None:
        @ctx.mcp.tool()
        async def my_tool(param: str) -> str:
            # Access Home Assistant API
            states = await ctx.ha_client.get_all_states()

            # Use structured logging
            ctx.logger.debug(f"Processing {len(states)} states")

            # Check token limits
            result = json.dumps(states)
            if token_limit := ctx.get_token_limit():
                token_count = ctx.count_tokens(result)
                if token_count > token_limit:
                    return json.dumps({"error": f"Exceeds {token_limit} tokens"})

            return result
"""

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

    from mcp_hass.config import ConfigurationManager
    from mcp_hass.ha_client import HomeAssistantClient


@dataclass
class ToolContext:
    """Dependencies required for MCP tool registration.

    Passed to tool registration functions to provide access to:
    - FastMCP instance for decorator-based registration
    - Home Assistant client for API calls
    - Configuration for settings like token limits
    - Logger for structured logging

    This follows the existing dependency injection pattern used throughout
    the codebase (e.g., HomeAssistantClient accepts base_url, token, timeout).

    Attributes:
        mcp: FastMCP framework instance with decorator registration
        ha_client: Self-healing Home Assistant client with dual-API support
        config: Configuration manager with zero-silent-fallback settings
        logger: Structured logging instance
    """

    mcp: "FastMCP"
    ha_client: "HomeAssistantClient"
    config: "ConfigurationManager"
    logger: logging.Logger

    def count_tokens(self, text: str) -> int:
        """Count tokens in text using tiktoken (Claude-compatible encoding).

        Centralized token counting to avoid duplication across tools.
        Uses cl100k_base encoding (GPT-4/Claude compatible approximation).

        Args:
            text: Text to count tokens for

        Returns:
            Number of tokens in text
        """
        import tiktoken

        encoding = tiktoken.get_encoding("cl100k_base")
        return len(encoding.encode(text))

    def get_token_limit(self) -> int | None:
        """Get configured token limit or None if not set.

        Returns:
            Token limit from configuration, or None if unlimited
        """
        return self.config.get_tool_token_limit()
