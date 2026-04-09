#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
"""
Convenience wrapper for launching MCP-HASS from repository root.

For production use, install the package and use the `mcp-hass` command:
    pip install -e .
    mcp-hass serve

This file exists for development convenience only.
"""

import logging
import os
import sys
from pathlib import Path

import click

from mcp_hass.server import MCPHomeAssistantServer

# Configuration file template
CONFIG_TEMPLATE = """# ==============================================================================
# HOME ASSISTANT INTERFACE
# ==============================================================================

HA_BASE_URL=http://homeassistant.local:8123
HA_TOKEN=your_long_lived_access_token
HA_TIMEOUT=10
WS_RECONNECT_ATTEMPTS=5
# Set to false to disable TLS certificate verification (e.g. self-signed certs)
HA_SSL_VERIFY=true

# ==============================================================================
# MCP SERVER
# ==============================================================================

MCP_SERVER_NAME=MCP-HASS
LOG_LEVEL=INFO
DEBUG_MODE=false
#LOG_FILE_PATH=/var/log/mcp-hass/server.log
#TOOL_TOKEN_LIMIT=100000

# Stateless HTTP mode (optional, default: false)
# When true, each request creates a fresh transport with no session tracking.
# Useful for clients that don't properly handle session expiration (404).
#MCP_SERVER_STATELESS=false

"""


@click.group()
@click.version_option(package_name="mcp-hass", prog_name="mcp-hass")
@click.option(
    "--log-level",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]),
    default="INFO",
    help="Set logging level",
)
@click.pass_context
def cli(ctx, log_level):
    """MCP-HASS: Model Context Protocol server for Home Assistant.

    Built on the official MCP Python SDK for modern, decorator-based MCP server development.
    Provides AI agents with efficient access to Home Assistant automation systems through
    both STDIO and HTTP transports.

    FEATURES:
    • Entity management (get states, find entities, history)
    • Service calls (turn on/off devices, set parameters)
    • Spatial queries (area-based entity discovery)
    • Device control (bulk operations, filtering)
    • Resources (config, states) and prompts (HA summary)

    USAGE:
    Use 'mcp-hass serve --help' for detailed server options including transport configuration.
    """
    ctx.ensure_object(dict)
    ctx.obj["log_level"] = log_level

    # Setup logging
    logging.basicConfig(
        level=getattr(logging, log_level),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


@cli.command()
@click.option(
    "--env-file",
    type=click.Path(exists=True, path_type=Path),
    help="Path to custom .env file. If not specified, looks for .env in current directory. Contains HA_BASE_URL, HA_TOKEN, etc.",
)
@click.option(
    "--ha-url",
    help="Home Assistant base URL (e.g., http://homeassistant.local:8123). Overrides HA_BASE_URL from .env file.",
)
@click.option(
    "--ha-token",
    help="Home Assistant long-lived access token. Overrides HA_TOKEN from .env file. Generate in HA Profile settings.",
)
@click.option(
    "--timeout",
    type=float,
    help="HTTP request timeout in seconds for Home Assistant API calls (default: 30). Overrides HA_TIMEOUT from .env.",
)
@click.option(
    "--validate/--no-validate",
    default=True,
    help="Validate Home Assistant connection during startup. Use --no-validate to skip connection test.",
)
@click.option(
    "--transport",
    type=click.Choice(["stdio", "http", "sse"]),
    default="stdio",
    help="MCP transport type. STDIO: command-line/local tools. HTTP: streamable HTTP for web. SSE: Server-Sent Events for mcp-proxy compatibility.",
)
@click.option(
    "--host",
    default="127.0.0.1",
    help="Host/IP address to bind server to. Use 0.0.0.0 for all interfaces. Only used with --transport http or --transport sse.",
)
@click.option(
    "--port",
    type=int,
    default=3000,
    help="TCP port for server. HTTP: http://HOST:PORT/mcp, SSE: http://HOST:PORT/sse. Only used with --transport http or --transport sse.",
)
@click.option(
    "--debug",
    is_flag=True,
    help="Enable debug mode with verbose logging and API call tracing. Sets log level to DEBUG.",
)
@click.pass_context
def serve(
    ctx,
    env_file,
    ha_url,
    ha_token,
    timeout,
    validate,
    transport,
    host,
    port,
    debug,
):
    """Start the MCP-HASS server.

    Connects to Home Assistant and exposes all capabilities via Model Context Protocol.
    Provides tools for entity management, service calls, spatial queries, device control,
    and bulk operations. Also includes resources (config, states) and prompts.

    TRANSPORT OPTIONS:
    - STDIO (default): For command-line integrations, Claude Desktop, etc.
    - HTTP: For web deployments, remote access, and multi-client scenarios

    EXAMPLES:
    \b
    # Start with STDIO transport (default)
    mcp-hass serve

    # Start with HTTP transport on port 8080
    mcp-hass serve --transport http --port 8080 --host 0.0.0.0

    # Override Home Assistant settings
    mcp-hass serve --ha-url http://X.X.X.X:8123 --ha-token your_token_here
    """
    # Only show initialization messages for HTTP/SSE transports
    # STDIO mode must remain silent to avoid polluting the protocol stream
    show_output = transport in ["http", "sse"]

    if show_output:
        transport_desc = f"{transport.upper()}" + (
            f" on {host}:{port}" if transport in ["http", "sse"] else ""
        )
        click.echo(f"🔧 Initializing MCP-HASS server ({transport_desc})...")

    # Set environment overrides if provided
    if env_file:
        if show_output:
            click.echo(f"📄 Loading environment from: {env_file}")
        os.environ["MHASS_ENV_FILE"] = str(env_file)

    if ha_url:
        if show_output:
            click.echo(f"🏠 Using Home Assistant URL: {ha_url}")
        os.environ["HA_BASE_URL"] = ha_url

    if ha_token:
        if show_output:
            click.echo("🔑 Using provided access token")
        os.environ["HA_TOKEN"] = ha_token

    if timeout:
        if show_output:
            click.echo(f"⏱️  Setting timeout: {timeout}s")
        os.environ["HA_TIMEOUT"] = str(timeout)

    if not validate:
        if show_output:
            click.echo("⚠️  Skipping connection validation")
        os.environ["HA_VALIDATE_CONNECTION"] = "false"

    if debug:
        if show_output:
            click.echo("🐛 Debug mode enabled")
        os.environ["DEBUG_MODE"] = "true"
        os.environ["LOG_LEVEL"] = "DEBUG"

    # Store transport options for server
    os.environ["FASTMCP_TRANSPORT"] = transport
    if transport in ["http", "sse"]:
        os.environ["FASTMCP_HOST"] = host
        os.environ["FASTMCP_PORT"] = str(port)

    try:
        # Let MCP SDK handle its own asyncio event loop management
        _run_server_sync(transport, host, port)
    except KeyboardInterrupt:
        if show_output:
            click.echo("\n🛑 Server shutdown requested")
        sys.exit(0)
    except Exception as e:
        # Errors always go to stderr regardless of transport
        click.echo(f"❌ Server error: {e}", err=True)
        sys.exit(1)


@cli.command()
def init():
    """Initialize MCP-HASS configuration file.

    Creates ~/.config/mcp-hass/config with default settings and secure permissions (600).
    If config already exists, displays current settings and validates connection.
    """
    from mcp_hass.config import ConfigurationManager

    config_path = ConfigurationManager.get_config_file_path()

    # Check if config already exists
    if config_path.exists():
        click.echo(f"Configuration file already exists: {config_path}")
        click.echo(f"To edit: vi {config_path}")

    else:
        # Create new config file
        try:
            # Create directory if needed
            config_path.parent.mkdir(parents=True, exist_ok=True)
            click.echo(f"Creating configuration directory: {config_path.parent}")

            # Write config file
            config_path.write_text(CONFIG_TEMPLATE)
            click.echo(f"Creating config file: {config_path}")

            # Set secure permissions (user read/write only)
            config_path.chmod(0o600)
            click.echo("Setting permissions: 600 (user read/write only)\n")

            click.echo("✅ Configuration file created!\n")
            click.echo("Next steps:")
            click.echo("  1. Edit the configuration file with your HA details:")
            click.echo(f"     vi {config_path}")
            click.echo("  2. Start the server:")
            click.echo("     mcp-hass serve")

        except Exception as e:
            click.echo(f"❌ Failed to create configuration: {e}", err=True)
            sys.exit(1)


@cli.command()
@click.option(
    "--output",
    type=click.Choice(["table", "json", "yaml"]),
    default="table",
    help="Output format",
)
def tools(_output):
    """List all available MCP tools and their capabilities.

    Shows comprehensive overview of MCP tools including entity management,
    service calls, spatial queries, device control, and bulk operations.
    Tools are automatically registered with the MCP server at startup.
    """
    click.echo("🛠️  Available MCP Tools:")

    try:
        click.echo(
            "MCP tools are integrated into the server. Use the server directly for tool information."
        )

    except Exception as e:
        click.echo(f"❌ Error listing tools: {e}", err=True)
        sys.exit(1)


@cli.command()
def config():
    """Show current configuration and environment settings.

    Displays all configuration values including Home Assistant connection
    details, server settings, and environment variable sources. Useful
    for debugging configuration issues.
    """
    click.echo("📋 MCP-HASS Configuration:")

    try:
        from mcp_hass.config import ConfigurationManager

        config_manager = ConfigurationManager()

        click.echo(f"  🏠 Home Assistant URL: {config_manager.get_ha_base_url()}")
        click.echo(
            f"  🔑 Token configured: {'Yes' if config_manager.get_ha_token() else 'No'}"
        )
        click.echo(f"  ⏱️  Timeout: {config_manager.get_ha_timeout()}s")
        click.echo(f"  📊 Log Level: {config_manager.get_log_level()}")
        click.echo(f"  🖥️  Server Name: {config_manager.get_server_name()}")
        click.echo(f"  📦 Server Version: {config_manager.get_server_version()}")
        click.echo(
            f"  ✅ Validate Connection: {config_manager.get_ha_validate_connection()}"
        )

    except Exception as e:
        click.echo(f"❌ Error reading configuration: {e}", err=True)
        sys.exit(1)


def _run_server_sync(transport="stdio", host="127.0.0.1", port=3000):
    """Run the MCP server with specified transport."""
    # MCP SDK manages its own event loop, so we call run() synchronously
    server = MCPHomeAssistantServer()
    server.run(transport=transport, host=host, port=port)


if __name__ == "__main__":
    cli()
