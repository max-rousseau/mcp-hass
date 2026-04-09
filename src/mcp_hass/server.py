# SPDX-License-Identifier: BSD-3-Clause
"""
Module: server

Purpose:
    Thin orchestrator for MCP-HASS using a modular, dependency-injection architecture.
    Initializes configuration, creates ToolContext, and registers all handlers (tools,
    resources, prompts) with FastMCP.

Architecture:
    This module implements the "thin orchestrator" pattern:
    1. Initializes core dependencies (config, ha_client, FastMCP)
    2. Creates ToolContext with dependencies
    3. Delegates tool registration to modular tool packages
    4. Configures transport (stdio, HTTP, SSE)
    5. Manages server lifecycle

Key Features:
    - Modular tool registration via ToolContext dependency injection
    - Support for multiple transports (stdio, HTTP, SSE)
    - Health check endpoint for HTTP transports
    - Structured logging with file and console output
    - Self-healing Home Assistant client integration

Note:
    This server is a pure MCP tools backend with no authentication.

Classes:
    - MCPHomeAssistantServer: Main server orchestrator

Functions:
    - main: Async entry point for standalone execution

Tool Registration:
    Tools are registered via modular packages in src/mcp_hass/tools/:
    - entity.py: Entity discovery and history
    - service.py: Service operations
    - spatial.py: Area/zone management
    - device.py: Device discovery
    - bulk.py: Bulk operations
    - camera.py: Camera snapshots
    - yaml_config.py: Configuration reload

Usage Example:
    # Standalone execution
    from mcp_hass.server import MCPHomeAssistantServer

    server = MCPHomeAssistantServer()
    server.run(transport="stdio")

    # With HTTP transport
    server.run(transport="http", host="0.0.0.0", port=3000)
"""

import asyncio
import logging
from typing import Optional

from mcp.server.fastmcp import FastMCP

from .config import ConfigurationManager
from .ha_client import HomeAssistantClient
from .http import DebugRequestMiddleware
from .prompts import register_prompts
from .resources import register_resources
from .tools import ToolContext, register_all_tools


def get_logger(name: str) -> logging.Logger:
    """Compatibility shim for fastmcp.utilities.logging.get_logger"""
    return logging.getLogger(name)


class MCPHomeAssistantServer:
    """Self-healing FastMCP server for comprehensive Home Assistant integration.

    This server provides intelligent, efficient access to Home Assistant through
    a self-healing dual-API architecture. Built on the FastMCP framework with
    decorator-based tool registration.

    Tool Categories (12 tools total):
        - Entity Tools (2): Entity discovery and history
        - Service Tools (3): Universal service control and discovery
        - Spatial Tools (2): Area-based queries
        - Device Tools (2): Device discovery and entity mapping
        - Bulk Tools (1): Multi-entity service operations
        - Camera Tools (1): Camera snapshot capture
        - Config Tools (1): Configuration validation

    Attributes:
        config: Configuration manager instance
        ha_client: Self-healing Home Assistant client
        mcp: FastMCP framework instance
        logger: Structured logging instance
    """

    def __init__(self) -> None:
        """Initialize the FastMCP-based MCP-HASS server."""
        self.config: Optional[ConfigurationManager] = None
        self.ha_client: Optional[HomeAssistantClient] = None
        self.mcp: Optional[FastMCP] = None

        self._setup_logging()
        self.logger = get_logger(__name__)

    def _setup_logging(self) -> None:
        """Setup logging configuration."""
        console_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )

        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)
        root_logger.handlers.clear()

        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)

    def _setup_file_logging(self, log_file_path: str) -> None:
        """Setup file logging to the specified path."""
        from pathlib import Path

        log_path = Path(log_file_path).expanduser()
        root_logger = logging.getLogger()

        for handler in root_logger.handlers:
            if isinstance(handler, logging.FileHandler):
                if handler.baseFilename == str(log_path.resolve()):
                    return

        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s"
        )
        file_handler = logging.FileHandler(log_path, mode="a")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)

        self.logger.debug(f"File logging enabled - logging to {log_file_path}")

    def _register_all_handlers(self) -> None:
        """Register all FastMCP tools, resources, and prompts."""
        ctx = ToolContext(
            mcp=self.mcp,
            ha_client=self.ha_client,
            config=self.config,
            logger=self.logger,
        )

        try:
            register_all_tools(ctx)
            register_resources(ctx)
            register_prompts(ctx)
            self.logger.debug("Successfully registered all handlers")
        except Exception as e:
            self.logger.error(f"Failed to register handlers: {e}", exc_info=True)
            raise

    def _register_health_endpoint(self) -> None:
        """Register health check endpoint for HTTP transports."""
        if not self.mcp:
            return

        from starlette.requests import Request
        from starlette.responses import JSONResponse

        @self.mcp.custom_route("/health", methods=["GET"])
        async def health_check(request: Request) -> JSONResponse:
            """Health check endpoint for container orchestration."""
            return JSONResponse(
                {
                    "status": "healthy",
                    "server": (
                        self.config.get_server_name() if self.config else "MCP-HASS"
                    ),
                    "version": (
                        self.config.get_server_version() if self.config else "unknown"
                    ),
                }
            )

        self.logger.debug("Health endpoint registered at /health")

    async def _cleanup_components(self) -> None:
        """Cleanup server components."""
        try:
            if self.ha_client:
                await self.ha_client.disconnect()
                self.logger.info("Disconnected from Home Assistant")
        except Exception as e:
            self.logger.error(f"Cleanup error: {e}")

    def run(
        self, transport: str = "stdio", host: str = "127.0.0.1", port: int = 3000
    ) -> None:
        """Run the FastMCP server with specified transport.

        Args:
            transport: Transport type ("stdio", "http", or "sse")
            host: Host to bind to for HTTP/SSE transport
            port: Port to bind to for HTTP/SSE transport
        """
        if not hasattr(self, "config") or self.config is None:
            self.config = ConfigurationManager()
            self.logger.debug("Configuration loaded successfully")

        root_logger = logging.getLogger()
        log_level = getattr(logging, self.config.get_log_level())
        is_debug = self.config.is_debug_mode() or log_level == logging.DEBUG

        root_logger.setLevel(log_level)
        for handler in root_logger.handlers:
            handler.setLevel(log_level)

        if is_debug:
            debug_loggers = [
                "mcp_hass",
                "fastmcp",
                "aiohttp",
                "websockets",
                "mcp",
                "mcp.server",
            ]
            for logger_name in debug_loggers:
                logging.getLogger(logger_name).setLevel(logging.DEBUG)

            self.logger.debug("=== Debug logging enabled ===")
            self.logger.debug(f"Transport: {transport}, Host: {host}, Port: {port}")

        if log_file_path := self.config.get_log_file_path():
            self._setup_file_logging(log_file_path)

        server_name = self.config.get_server_name()

        log_level_str = (
            "DEBUG" if (self.config and self.config.is_debug_mode()) else "INFO"
        )

        fastmcp_kwargs = {
            "name": server_name,
            "log_level": log_level_str,
            "host": host,
            "port": port,
        }

        if self.config.is_stateless_http():
            fastmcp_kwargs["stateless_http"] = True
            self.logger.info("Stateless HTTP mode enabled (no session tracking)")

        self.mcp = FastMCP(**fastmcp_kwargs)
        self.logger.debug(
            f"FastMCP initialized for server: {server_name} at {host}:{port}"
        )

        ssl_verify = self.config.get_ha_ssl_verify()
        if not ssl_verify:
            self.logger.warning(
                "TLS certificate verification is DISABLED (HA_SSL_VERIFY=false)"
            )

        self.ha_client = HomeAssistantClient(
            base_url=self.config.get_ha_base_url(),
            token=self.config.get_ha_token(),
            timeout=self.config.get_ha_timeout(),
            ssl_verify=ssl_verify,
        )

        self._register_all_handlers()

        if transport in ("http", "sse"):
            self._register_health_endpoint()

        self.logger.debug("FastMCP-based MCP-HASS server starting...")
        server_version = self.config.get_server_version()
        self.logger.debug(f"Server: {server_name} v{server_version}")
        self.logger.debug("Server ready for connections")

        try:
            if transport == "http":
                self.logger.info(f"Streamable HTTP server at: http://{host}:{port}/mcp")

                # Add debug middleware in debug mode
                log_level = getattr(logging, self.config.get_log_level())
                is_debug = self.config.is_debug_mode() or log_level == logging.DEBUG
                if is_debug:
                    import uvicorn

                    starlette_app = self.mcp.streamable_http_app()
                    starlette_app.add_middleware(
                        DebugRequestMiddleware,
                        logger=self.logger,
                    )

                    config = uvicorn.Config(
                        starlette_app,
                        host=self.mcp.settings.host,
                        port=self.mcp.settings.port,
                        log_level=self.mcp.settings.log_level.lower(),
                    )
                    server = uvicorn.Server(config)
                    asyncio.run(server.serve())
                else:
                    self.mcp.run(transport="streamable-http")
            elif transport == "sse":
                self.logger.info(f"SSE server at: http://{host}:{port}/sse")
                self.mcp.run(transport="sse")
            else:
                self.mcp.run(transport="stdio")
        except Exception as e:
            self.logger.error(f"FastMCP server error: {e}")
            raise


async def main() -> None:
    """Main entry point for the FastMCP-based MCP-HASS server."""
    server = MCPHomeAssistantServer()
    try:
        await server.run()
    except KeyboardInterrupt:
        logging.getLogger(__name__).info("Server shutdown requested")
    except Exception as e:
        logging.getLogger(__name__).error(f"Server error: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
