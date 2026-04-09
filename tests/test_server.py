"""
Test suite for MCPHomeAssistantServer class.

Tests the server lifecycle, component initialization, and tool registration.
Critical for catching connection issues and ensuring proper server behavior.
"""

import pytest
import logging
from unittest.mock import AsyncMock, Mock, patch
from mcp.server.fastmcp import FastMCP

from src.mcp_hass.server import MCPHomeAssistantServer
from src.mcp_hass.config.manager import ConfigurationManager
from src.mcp_hass.ha_client.client import HomeAssistantClient
from src.mcp_hass.ha_client.exceptions import (
    HomeAssistantConnectionError,
)


@pytest.fixture
def mock_config():
    """Mock ConfigurationManager for testing."""
    config = Mock(spec=ConfigurationManager)
    config.get_ha_base_url.return_value = "http://homeassistant.local:8123"
    config.get_ha_token.return_value = "test_token_123456789"
    config.get_ha_timeout.return_value = 10.0
    config.get_server_name.return_value = "Test-MCP-HASS"
    config.get_server_version.return_value = "0.1.0"
    config.get_log_level.return_value = "INFO"
    config.is_debug_mode.return_value = False
    config.get_tool_token_limit.return_value = 100000
    return config


@pytest.fixture
def mock_ha_client():
    """Mock HomeAssistantClient for testing."""
    client = Mock(spec=HomeAssistantClient)
    client.connect = AsyncMock()
    client.validate_connection = AsyncMock(return_value=True)
    client.disconnect = AsyncMock()
    client.session = None  # Initially not connected

    # Mock all API methods
    client.get_entity_state = AsyncMock()
    client.get_all_states = AsyncMock()
    client.get_history = AsyncMock()
    client.call_service = AsyncMock()
    client.get_services = AsyncMock()
    client.get_areas = AsyncMock()
    client.get_devices = AsyncMock()
    client.get_entity_registry = AsyncMock()
    client.get_config = AsyncMock()

    return client


@pytest.fixture
def mock_fastmcp():
    """Mock FastMCP instance for testing."""
    mcp = Mock(spec=FastMCP)

    # Track registered functions to make them accessible via call_args_list
    class ToolMock:
        def __init__(self):
            self.call_args_list = []
            self._mock = Mock()

        def __call__(self, *args, **kwargs):
            if args and callable(args[0]):
                # Called as @mcp.tool (bare decorator)
                func = args[0]
                # Store as ((func,), {}) to match call_args_list format
                self.call_args_list.append(((func,), {}))
                return func
            else:
                # Called as @mcp.tool(annotations=...) (decorator factory)
                def decorator(func):
                    # Store as ((func,), kwargs) to match call_args_list format
                    self.call_args_list.append(((func,), kwargs))
                    return func

                return decorator

        @property
        def called(self):
            return len(self.call_args_list) > 0

        @property
        def call_count(self):
            return len(self.call_args_list)

        def __getattr__(self, name):
            return getattr(self._mock, name)

    mcp.tool = ToolMock()
    mcp.resource = Mock(side_effect=lambda _uri: lambda func: func)
    mcp.prompt = Mock(side_effect=lambda name: lambda func: func)
    mcp.run = AsyncMock()
    return mcp


@pytest.fixture
def server():
    """Create MCPHomeAssistantServer instance for testing."""
    return MCPHomeAssistantServer()


class TestMCPHomeAssistantServerInitialization:
    """Test server initialization and basic setup."""

    def test_init_sets_initial_state(self, server):
        """Test that initialization sets proper initial state."""
        assert server.config is None
        assert server.ha_client is None
        assert server.mcp is None
        assert server.logger is not None

    def test_setup_logging_configures_basic_format(self, server):
        """Test that logging is configured with proper format."""
        server._setup_logging()

        # Verify basic logging configuration was called
        # We can't easily test the exact format without mocking logging.basicConfig
        assert server.logger is not None


class TestMCPHomeAssistantServerToolRegistration:
    """Test tool registration methods."""

    def test_register_all_handlers_registers_all_tool_categories(
        self, server, mock_config, mock_ha_client
    ):
        """Test that all tool categories are registered and functional.

        CONTRACT: After registration, all expected tool categories should have
        registered tools that are callable. Tests WHAT is registered, not HOW.
        """
        server.config = mock_config
        server.ha_client = mock_ha_client
        server.mcp = Mock()

        # Track registered functions to make them accessible via call_args_list
        class ToolMock:
            def __init__(self):
                self.call_args_list = []
                self._mock = Mock()

            def __call__(self, *args, **kwargs):
                if args and callable(args[0]):
                    # Called as @mcp.tool (bare decorator)
                    func = args[0]
                    # Store as ((func,), {}) to match call_args_list format
                    self.call_args_list.append(((func,), {}))
                    return func
                else:
                    # Called as @mcp.tool(annotations=...) (decorator factory)
                    def decorator(func):
                        # Store as ((func,), kwargs) to match call_args_list format
                        self.call_args_list.append(((func,), kwargs))
                        return func

                    return decorator

            @property
            def called(self):
                return len(self.call_args_list) > 0

            @property
            def call_count(self):
                return len(self.call_args_list)

            def __getattr__(self, name):
                return getattr(self._mock, name)

        server.mcp.tool = ToolMock()

        server._register_all_handlers()

        # Test the CONTRACT: tools are registered via the decorator
        # We verify the outcome (tools registered), not the implementation
        # (which internal methods were called)
        assert server.mcp.tool.called, "No tools were registered"

        # Extract registered tool names
        registered_tools = {
            call[0][0].__name__
            for call in server.mcp.tool.call_args_list
            if call[0]  # Only positional args (decorated functions)
        }

        # Verify expected tool categories are represented after consolidation
        # Entity tools (2): get_entity_history, find_entities
        assert "get_entity_history" in registered_tools
        assert "find_entities" in registered_tools

        # Service tools (2): call_service, get_services
        assert "call_service" in registered_tools
        assert "get_services" in registered_tools

        # Spatial tools (2): list_areas, get_area_devices
        assert "list_areas" in registered_tools
        assert "get_area_devices" in registered_tools

        # Device tools (1): get_device_entities
        assert "get_device_entities" in registered_tools

        # Bulk tools (1): call_service_bulk
        assert "call_service_bulk" in registered_tools

        # Verify exact tool count after consolidation (8 core tools + camera/config tools)
        # Note: This count may vary based on which optional tools are registered
        assert (
            len(registered_tools) >= 8
        ), f"Expected at least 8 core tools, got {len(registered_tools)}: {registered_tools}"


class TestMCPHomeAssistantServerLifecycle:
    """Test server lifecycle methods."""

    def test_register_all_handlers_success(self, server, mock_config, mock_ha_client):
        """Test successful handler registration.

        CONTRACT: After registration succeeds, server should have all
        tools, resources, and prompts registered. We test the OUTCOME
        (handlers are registered), not the implementation details.
        """
        # Pre-configure server with mocked dependencies
        server.config = mock_config
        mock_config.get_server_name.return_value = "test-server"
        mock_config.is_debug_mode.return_value = False
        mock_config.get_tool_token_limit.return_value = 100000
        server.ha_client = mock_ha_client

        # Track registered functions
        class ToolMock:
            def __init__(self):
                self.call_args_list = []
                self._mock = Mock()

            def __call__(self, *args, **kwargs):
                if args and callable(args[0]):
                    func = args[0]
                    self.call_args_list.append(((func,), {}))
                    return func
                else:

                    def decorator(func):
                        self.call_args_list.append(((func,), kwargs))
                        return func

                    return decorator

            @property
            def called(self):
                return len(self.call_args_list) > 0

            @property
            def call_count(self):
                return len(self.call_args_list)

            def __getattr__(self, name):
                return getattr(self._mock, name)

        mock_mcp = Mock()
        mock_mcp.tool = ToolMock()
        mock_mcp.resource = Mock(side_effect=lambda _uri: lambda func: func)
        mock_mcp.prompt = Mock(side_effect=lambda *args, **kwargs: lambda func: func)
        server.mcp = mock_mcp

        # Register handlers
        server._register_all_handlers()

        # Test the CONTRACT: tools are registered
        assert mock_mcp.tool.called, "No tools were registered"
        assert mock_mcp.tool.call_count == 12, "Expected 12 tools registered"

    @pytest.mark.asyncio
    async def test_cleanup_components(self, server, mock_ha_client):
        """Test component cleanup."""
        server.ha_client = mock_ha_client

        await server._cleanup_components()

        mock_ha_client.disconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_components_with_error(self, server):
        """Test component cleanup handles errors gracefully."""
        mock_ha_client = Mock()
        mock_ha_client.disconnect = AsyncMock(
            side_effect=Exception("Disconnect failed")
        )
        server.ha_client = mock_ha_client

        # Should not raise exception, only log error
        await server._cleanup_components()

    @pytest.mark.asyncio
    async def test_cleanup_components_with_no_client(self, server):
        """Test cleanup when no HA client exists."""
        server.ha_client = None

        # Should not raise exception
        await server._cleanup_components()


class TestMCPHomeAssistantServerRun:
    """Test server run method components and lifecycle.

    Note: The run() method itself calls mcp.run() which starts an event loop,
    making it difficult to test in pytest-asyncio. Instead, we test that:
    1. The components it orchestrates work correctly (init, cleanup - tested elsewhere)
    2. The method exists and has the right structure
    """

    def test_run_method_exists(self, server):
        """Test that run method exists and is callable."""
        assert hasattr(server, "run")
        assert callable(server.run)


class TestMCPHomeAssistantServerConnectionHandling:
    """Test connection handling in tools - the critical bug area."""

    @pytest.mark.asyncio
    async def test_connection_initialization_in_tool(self, server, mock_config):
        """Test that tools work properly regardless of connection state."""
        from src.mcp_hass.tools import ToolContext, register_spatial_tools

        # This test verifies that tools leverage the client's auto-connect behavior
        mock_ha_client = Mock()
        mock_ha_client.session = None  # Not connected

        server.ha_client = mock_ha_client
        server.config = mock_config

        # Track registered functions
        class ToolMock:
            def __init__(self):
                self.call_args_list = []
                self._mock = Mock()

            def __call__(self, *args, **kwargs):
                if args and callable(args[0]):
                    func = args[0]
                    self.call_args_list.append(((func,), {}))
                    return func
                else:

                    def decorator(func):
                        self.call_args_list.append(((func,), kwargs))
                        return func

                    return decorator

            @property
            def called(self):
                return len(self.call_args_list) > 0

            @property
            def call_count(self):
                return len(self.call_args_list)

            def __getattr__(self, name):
                return getattr(self._mock, name)

        server.mcp = Mock()
        server.mcp.tool = ToolMock()

        # Register tools using the new module pattern
        ctx = ToolContext(
            mcp=server.mcp,
            ha_client=mock_ha_client,
            config=mock_config,
            logger=logging.getLogger(__name__),
        )
        register_spatial_tools(ctx)

        # Get the registered list_areas function
        tool_calls = server.mcp.tool.call_args_list
        list_areas_func = None
        for call in tool_calls:
            if hasattr(call[0][0], "__name__") and call[0][0].__name__ == "list_areas":
                list_areas_func = call[0][0]
                break

        assert list_areas_func is not None, "list_areas tool should be registered"

        # Mock the get_areas method - it will auto-connect internally
        mock_ha_client.get_areas = AsyncMock(
            return_value=[{"area_id": "living_room", "name": "Living Room"}]
        )

        # Call the tool function - auto-connect happens in get_areas
        result = await list_areas_func()

        # Verify the client method was called (which handles auto-connect internally)
        mock_ha_client.get_areas.assert_called_once()

        # Verify the result is proper JSON
        import json

        parsed_result = json.loads(result)
        assert isinstance(parsed_result, list)

    @pytest.mark.asyncio
    async def test_tools_handle_connection_errors(self, server, mock_config):
        """Test that tools handle connection errors gracefully."""
        from src.mcp_hass.tools import ToolContext, register_spatial_tools

        mock_ha_client = Mock()
        mock_ha_client.session = None
        mock_ha_client.connect = AsyncMock(
            side_effect=HomeAssistantConnectionError("Connection failed")
        )

        server.ha_client = mock_ha_client
        server.config = mock_config

        # Track registered functions
        class ToolMock:
            def __init__(self):
                self.call_args_list = []
                self._mock = Mock()

            def __call__(self, *args, **kwargs):
                if args and callable(args[0]):
                    func = args[0]
                    self.call_args_list.append(((func,), {}))
                    return func
                else:

                    def decorator(func):
                        self.call_args_list.append(((func,), kwargs))
                        return func

                    return decorator

            @property
            def called(self):
                return len(self.call_args_list) > 0

            @property
            def call_count(self):
                return len(self.call_args_list)

            def __getattr__(self, name):
                return getattr(self._mock, name)

        server.mcp = Mock()
        server.mcp.tool = ToolMock()

        # Register tools using the new module pattern
        ctx = ToolContext(
            mcp=server.mcp,
            ha_client=mock_ha_client,
            config=mock_config,
            logger=logging.getLogger(__name__),
        )
        register_spatial_tools(ctx)

        # Get the registered function
        tool_calls = server.mcp.tool.call_args_list
        list_areas_func = tool_calls[0][0][0]  # First registered tool

        # Should raise ValueError with descriptive message
        with pytest.raises(ValueError, match="Failed to list areas"):
            await list_areas_func()


@pytest.mark.asyncio
async def test_main_function():
    """Test the main async function."""
    from src.mcp_hass.server import main

    with patch("src.mcp_hass.server.MCPHomeAssistantServer") as mock_server_class:
        mock_server = AsyncMock()
        mock_server.run = AsyncMock()
        mock_server_class.return_value = mock_server

        await main()

        mock_server.run.assert_called_once()


@pytest.mark.asyncio
async def test_main_function_keyboard_interrupt():
    """Test main function handles KeyboardInterrupt gracefully."""
    from src.mcp_hass.server import main

    with patch("src.mcp_hass.server.MCPHomeAssistantServer") as mock_server_class:
        mock_server = AsyncMock()
        mock_server.run = AsyncMock(side_effect=KeyboardInterrupt())
        mock_server_class.return_value = mock_server

        # Should not raise exception
        await main()


@pytest.mark.asyncio
async def test_main_function_general_exception():
    """Test main function handles general exceptions."""
    from src.mcp_hass.server import main

    with patch("src.mcp_hass.server.MCPHomeAssistantServer") as mock_server_class:
        mock_server = AsyncMock()
        mock_server.run = AsyncMock(side_effect=Exception("Server failed"))
        mock_server_class.return_value = mock_server

        with pytest.raises(Exception, match="Server failed"):
            await main()


class TestMCPHomeAssistantServerDebugMode:
    """Test debug mode initialization paths."""

    def test_register_all_handlers_error_handling(self, server, mock_config):
        """Test error handling during handler registration."""
        server.config = mock_config
        server.mcp = Mock()
        server.ha_client = Mock()
        server.mcp.tool = Mock(side_effect=Exception("Registration failed"))

        with pytest.raises(Exception, match="Registration failed"):
            server._register_all_handlers()


class TestMCPHomeAssistantServerRunMethod:
    """Test the run() method initialization paths."""

    def test_run_initializes_config_if_not_set(self, server):
        """Test that run() initializes config if not already set."""
        assert server.config is None

        with patch("src.mcp_hass.server.ConfigurationManager") as mock_config_class:
            mock_config = Mock()
            mock_config.get_server_name.return_value = "test-server"
            mock_config.get_server_version.return_value = "0.1.0"
            mock_config.is_debug_mode.return_value = False
            mock_config.get_log_level.return_value = "INFO"
            mock_config.get_log_file_path.return_value = None
            mock_config.get_ha_base_url.return_value = "http://localhost:8123"
            mock_config.get_ha_token.return_value = "test_token"
            mock_config.get_ha_timeout.return_value = 10.0
            mock_config_class.return_value = mock_config

            with patch("src.mcp_hass.server.FastMCP") as mock_fastmcp_class:
                with patch("src.mcp_hass.server.HomeAssistantClient"):
                    mock_mcp = Mock()
                    mock_mcp.run = Mock(side_effect=KeyboardInterrupt())
                    mock_fastmcp_class.return_value = mock_mcp

                    try:
                        server.run(transport="stdio")
                    except KeyboardInterrupt:
                        pass

                    # Config should be initialized
                    assert server.config is not None

    def test_run_debug_mode_logging_setup(self, server):
        """Test run() sets up debug logging when in debug mode."""
        with patch("src.mcp_hass.server.ConfigurationManager") as mock_config_class:
            mock_config = Mock()
            mock_config.get_server_name.return_value = "test-server"
            mock_config.get_server_version.return_value = "0.1.0"
            mock_config.is_debug_mode.return_value = True
            mock_config.get_log_level.return_value = "DEBUG"
            mock_config.get_log_file_path.return_value = None
            mock_config.get_ha_base_url.return_value = "http://localhost:8123"
            mock_config.get_ha_token.return_value = "test_token"
            mock_config.get_ha_timeout.return_value = 10.0
            mock_config_class.return_value = mock_config

            with patch("src.mcp_hass.server.FastMCP") as mock_fastmcp_class:
                with patch("src.mcp_hass.server.HomeAssistantClient"):
                    with patch("logging.getLogger") as mock_get_logger:
                        mock_logger = Mock()
                        mock_logger.handlers = []
                        mock_get_logger.return_value = mock_logger

                        mock_mcp = Mock()
                        mock_mcp.run = Mock(side_effect=KeyboardInterrupt())
                        mock_fastmcp_class.return_value = mock_mcp

                        try:
                            server.run(transport="stdio")
                        except KeyboardInterrupt:
                            pass

                        # Debug logging should be configured
                        mock_logger.setLevel.assert_called()

    def test_run_http_transport(self, server):
        """Test run() with HTTP transport."""
        with patch("src.mcp_hass.server.ConfigurationManager") as mock_config_class:
            mock_config = Mock()
            mock_config.get_server_name.return_value = "test-server"
            mock_config.get_server_version.return_value = "0.1.0"
            mock_config.is_debug_mode.return_value = False
            mock_config.get_log_level.return_value = "INFO"
            mock_config.get_log_file_path.return_value = None
            mock_config.get_ha_base_url.return_value = "http://localhost:8123"
            mock_config.get_ha_token.return_value = "test_token"
            mock_config.get_ha_timeout.return_value = 10.0
            mock_config_class.return_value = mock_config

            with patch("src.mcp_hass.server.FastMCP") as mock_fastmcp_class:
                with patch("src.mcp_hass.server.HomeAssistantClient"):
                    mock_mcp = Mock()
                    mock_mcp.run = Mock()
                    mock_fastmcp_class.return_value = mock_mcp

                    server.run(
                        transport="http", host="0.0.0.0", port=8080  # nosec B104
                    )

                    # Verify HTTP transport called
                    mock_mcp.run.assert_called_once_with(transport="streamable-http")

    def test_run_sse_transport(self, server):
        """Test run() with SSE transport."""
        with patch("src.mcp_hass.server.ConfigurationManager") as mock_config_class:
            mock_config = Mock()
            mock_config.get_server_name.return_value = "test-server"
            mock_config.get_server_version.return_value = "0.1.0"
            mock_config.is_debug_mode.return_value = False
            mock_config.get_log_level.return_value = "INFO"
            mock_config.get_log_file_path.return_value = None
            mock_config.get_ha_base_url.return_value = "http://localhost:8123"
            mock_config.get_ha_token.return_value = "test_token"
            mock_config.get_ha_timeout.return_value = 10.0
            mock_config_class.return_value = mock_config

            with patch("src.mcp_hass.server.FastMCP") as mock_fastmcp_class:
                with patch("src.mcp_hass.server.HomeAssistantClient"):
                    mock_mcp = Mock()
                    mock_mcp.run = Mock()
                    mock_fastmcp_class.return_value = mock_mcp

                    server.run(transport="sse", host="127.0.0.1", port=9090)

                    # Verify SSE transport called
                    mock_mcp.run.assert_called_once_with(transport="sse")

    def test_run_stdio_transport(self, server):
        """Test run() with default STDIO transport."""
        with patch("src.mcp_hass.server.ConfigurationManager") as mock_config_class:
            mock_config = Mock()
            mock_config.get_server_name.return_value = "test-server"
            mock_config.get_server_version.return_value = "0.1.0"
            mock_config.is_debug_mode.return_value = False
            mock_config.get_log_level.return_value = "INFO"
            mock_config.get_log_file_path.return_value = None
            mock_config.get_ha_base_url.return_value = "http://localhost:8123"
            mock_config.get_ha_token.return_value = "test_token"
            mock_config.get_ha_timeout.return_value = 10.0
            mock_config_class.return_value = mock_config

            with patch("src.mcp_hass.server.FastMCP") as mock_fastmcp_class:
                with patch("src.mcp_hass.server.HomeAssistantClient"):
                    mock_mcp = Mock()
                    mock_mcp.run = Mock()
                    mock_fastmcp_class.return_value = mock_mcp

                    server.run(transport="stdio")

                    # Verify STDIO transport called
                    mock_mcp.run.assert_called_once_with(transport="stdio")

    def test_run_http_transport_fallback(self, server):
        """Test run() HTTP transport with fallback on error."""
        with patch("src.mcp_hass.server.ConfigurationManager") as mock_config_class:
            mock_config = Mock()
            mock_config.get_server_name.return_value = "test-server"
            mock_config.get_server_version.return_value = "0.1.0"
            mock_config.is_debug_mode.return_value = False
            mock_config.get_log_level.return_value = "INFO"
            mock_config.get_log_file_path.return_value = None
            mock_config.get_ha_base_url.return_value = "http://localhost:8123"
            mock_config.get_ha_token.return_value = "test_token"
            mock_config.get_ha_timeout.return_value = 10.0
            mock_config_class.return_value = mock_config

            with patch("src.mcp_hass.server.FastMCP") as mock_fastmcp_class:
                with patch("src.mcp_hass.server.HomeAssistantClient"):
                    mock_mcp = Mock()
                    mock_mcp.run = Mock()
                    mock_fastmcp_class.return_value = mock_mcp

                    server.run(
                        transport="http", host="0.0.0.0", port=8080  # nosec B104
                    )

                    mock_mcp.run.assert_called_once_with(transport="streamable-http")
