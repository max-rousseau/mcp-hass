# SPDX-License-Identifier: BSD-3-Clause
"""
YAML configuration management tools for MCP-HASS.

Provides configuration validation and reload functionality with structured JSON responses:
- reload_yaml_config: Validate and reload Home Assistant YAML configuration

The reload_yaml_config tool returns structured JSON responses with status, validation
details, and troubleshooting guidance for both success and failure scenarios.
"""

import json
from typing import TYPE_CHECKING

import aiohttp

from mcp_hass.ha_client.exceptions import (
    HomeAssistantConnectionError,
    HomeAssistantAuthError,
    HomeAssistantAPIError,
    HomeAssistantTimeoutError,
)

if TYPE_CHECKING:
    from .context import ToolContext


def register_yaml_config_tools(ctx: "ToolContext") -> None:
    """Register YAML configuration management tools with FastMCP.

    Args:
        ctx: Tool context with mcp, ha_client, config, logger dependencies
    """

    @ctx.mcp.tool()
    async def reload_yaml_config() -> str:
        """Reload all Home Assistant YAML configuration.

        Reloads all YAML-based configuration without requiring a full
        Home Assistant restart. The operation proceeds in two phases:
        1. Validation: Checks YAML configuration for errors
        2. Reload: Calls homeassistant.reload_all service if validation passes

        Returns:
            JSON-formatted string containing structured response data.

            Success response structure:
            {
                "status": "success",
                "validation": {
                    "result": "valid",
                    "message": "YAML configuration validation passed"
                },
                "reload": {
                    "service_called": "homeassistant.reload_all",
                    "entities_affected": <int>,
                    "message": "Configuration reloaded successfully"
                },
                "summary": "Home Assistant YAML configuration validated and reloaded successfully"
            }

            Error response structure:
            {
                "status": "error",
                "error_type": "connection" | "timeout" | "authentication" | "api_error",
                "message": "<detailed error message>",
                "status_code": <int> | null,  # Only for api_error type
                "troubleshooting": [
                    "<actionable troubleshooting step>",
                    ...
                ]
            }

        Raises:
            ValueError: If YAML validation fails (invalid configuration detected)
                       or if Home Assistant validation API is unavailable

        Examples:
            Success case:
            >>> result = await reload_yaml_config()
            >>> data = json.loads(result)
            >>> data["status"]
            'success'
            >>> data["reload"]["entities_affected"]
            42

            Failure case (connection error):
            >>> result = await reload_yaml_config()
            >>> data = json.loads(result)
            >>> data["status"]
            'error'
            >>> data["error_type"]
            'connection'
            >>> data["troubleshooting"]
            ['Verify Home Assistant is running and accessible', ...]

            Validation failure (raises ValueError):
            >>> await reload_yaml_config()
            ValueError: Failed to reload config - YAML validation failed.
            Errors:
            Invalid config for [automation]: ...
        """
        if ctx.ha_client.session is None:
            await ctx.ha_client.connect()

        # Validation phase with connection error handling
        try:
            async with ctx.ha_client.session.post(
                f"{ctx.ha_client.base_url}/api/config/core/check_config",
                headers={"Authorization": f"Bearer {ctx.ha_client.token}"},
                timeout=ctx.ha_client.timeout,
            ) as response:
                if response.status != 200:
                    raise ValueError(
                        f"Home Assistant validation API unavailable (HTTP {response.status}). "
                        f"This may indicate an older HA version or API access issues."
                    )
                validation_result = await response.json()
                if validation_result.get("result") != "valid":
                    errors = validation_result.get("errors", [])
                    raise ValueError(
                        "Failed to reload config - YAML validation failed.\n"
                        "Errors:\n" + "\n".join(errors)
                    )

        except aiohttp.ServerTimeoutError as e:
            error_response = {
                "status": "error",
                "error_type": "timeout",
                "message": f"Configuration validation timed out: {str(e)}",
                "troubleshooting": [
                    "Increase timeout configuration in client settings",
                    "Check if Home Assistant is responding slowly",
                    "Verify network connectivity to Home Assistant",
                ],
            }
            ctx.logger.error(f"Timeout during YAML validation: {e}", exc_info=True)
            return json.dumps(error_response, indent=2)

        except (aiohttp.ClientConnectorError, aiohttp.ClientError) as e:
            # Handle potential string representation errors in aiohttp exceptions
            try:
                error_msg = str(e)
            except (AttributeError, Exception):
                error_msg = f"{type(e).__name__}: Connection failed"

            error_response = {
                "status": "error",
                "error_type": "connection",
                "message": f"Failed to connect to Home Assistant: {error_msg}",
                "troubleshooting": [
                    "Verify Home Assistant is running and accessible",
                    "Check network connectivity",
                    f"Verify base URL is correct: {ctx.ha_client.base_url}",
                ],
            }
            ctx.logger.error(
                f"Connection error during YAML validation: {error_msg}",
                exc_info=True,
            )
            return json.dumps(error_response, indent=2)

        # Reload phase with service call error handling
        try:
            reload_result = await ctx.ha_client.call_service(
                "homeassistant", "reload_all"
            )

        except HomeAssistantConnectionError as e:
            error_response = {
                "status": "error",
                "error_type": "connection",
                "message": f"Connection lost during reload: {str(e)}",
                "troubleshooting": [
                    "Check if Home Assistant is still running",
                    "Verify network connectivity",
                    "Check Home Assistant logs for service errors",
                ],
            }
            ctx.logger.error(
                f"Connection error during service call: {e}", exc_info=True
            )
            return json.dumps(error_response, indent=2)

        except HomeAssistantAuthError as e:
            error_response = {
                "status": "error",
                "error_type": "authentication",
                "message": f"Authentication failed: {str(e)}",
                "troubleshooting": [
                    "Verify your Home Assistant token is valid",
                    "Check if token has expired or been revoked",
                    "Generate a new long-lived access token from Home Assistant",
                ],
            }
            ctx.logger.error(
                f"Authentication error during service call: {e}", exc_info=True
            )
            return json.dumps(error_response, indent=2)

        except HomeAssistantTimeoutError as e:
            error_response = {
                "status": "error",
                "error_type": "timeout",
                "message": f"Reload operation timed out: {str(e)}",
                "troubleshooting": [
                    "Large configurations may take longer to reload",
                    "Increase timeout configuration if needed",
                    "Check Home Assistant logs for reload progress",
                ],
            }
            ctx.logger.error(f"Timeout during service call: {e}", exc_info=True)
            return json.dumps(error_response, indent=2)

        except HomeAssistantAPIError as e:
            error_response = {
                "status": "error",
                "error_type": "api_error",
                "message": f"Home Assistant API error: {str(e)}",
                "status_code": e.status_code if hasattr(e, "status_code") else None,
                "troubleshooting": [
                    "Check Home Assistant logs for detailed error information",
                    "Verify the reload_all service is available",
                    "Ensure your token has sufficient permissions",
                ],
            }
            ctx.logger.error(f"API error during service call: {e}", exc_info=True)
            return json.dumps(error_response, indent=2)

        # Success response
        response_data = {
            "status": "success",
            "validation": {
                "result": validation_result.get("result"),
                "message": "YAML configuration validation passed",
            },
            "reload": {
                "service_called": "homeassistant.reload_all",
                "entities_affected": len(reload_result) if reload_result else 0,
                "message": "Configuration reloaded successfully",
            },
            "summary": "Home Assistant YAML configuration validated and reloaded successfully",
        }

        return json.dumps(response_data, indent=2)
