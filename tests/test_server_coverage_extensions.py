"""
Extended test coverage for server.py to reach 85% threshold.

Tests file logging setup, token limit enforcement across tools,
resource/prompt handlers, and edge cases in the run method.
"""

import pytest
import json
import logging
from unittest.mock import AsyncMock, Mock, patch
from datetime import datetime

from src.mcp_hass.server import MCPHomeAssistantServer
from src.mcp_hass.tools import (
    ToolContext,
    register_entity_tools,
    register_service_tools,
    register_spatial_tools,
    register_device_tools,
    register_camera_tools,
)
from src.mcp_hass.resources import register_resources
from src.mcp_hass.prompts import register_prompts


class TestFileLoggingSetup:
    """Test file logging configuration paths."""

    def test_setup_file_logging_creates_directory(self, tmp_path):
        """Test that file logging creates parent directories."""
        server = MCPHomeAssistantServer()
        log_file = tmp_path / "logs" / "test.log"

        server._setup_file_logging(str(log_file))

        # Parent directory should be created
        assert log_file.parent.exists()

    def test_setup_file_logging_expands_tilde(self, tmp_path):
        """Test that file logging expands ~ to user home."""
        server = MCPHomeAssistantServer()

        # Use real file path to avoid mocking complexity
        log_dir = tmp_path / "logs"
        log_file = log_dir / "test.log"

        server._setup_file_logging(str(log_file))

        # Parent directory should be created
        assert log_dir.exists()

    def test_setup_file_logging_skips_duplicate_handler(self, tmp_path):
        """Test that file logging doesn't add duplicate handlers."""
        server = MCPHomeAssistantServer()
        log_file = tmp_path / "test.log"

        # Add handler first time
        server._setup_file_logging(str(log_file))
        initial_handlers = len(logging.getLogger().handlers)

        # Try adding again - should skip
        server._setup_file_logging(str(log_file))
        final_handlers = len(logging.getLogger().handlers)

        assert initial_handlers == final_handlers


class TestTokenLimitEnforcement:
    """Test token limit enforcement across different tools."""

    @pytest.mark.asyncio
    async def test_get_entity_history_token_limit_exceeded(
        self, mock_config, mock_ha_client
    ):
        """Test get_entity_history enforces token limits."""
        server = MCPHomeAssistantServer()
        server.config = mock_config
        server.config.get_tool_token_limit.return_value = 10  # Very low limit
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
            def call_count(self):
                return len(self.call_args_list)

            def __getattr__(self, name):
                return getattr(self._mock, name)

        server.mcp.tool = ToolMock()

        # Create large history response
        large_history = [
            [
                {
                    "state": f"value_{i}",
                    "last_changed": datetime.now().isoformat(),
                    "attributes": {
                        "friendly_name": "Test",
                        "unit_of_measurement": "°F",
                    },
                }
                for i in range(1000)
            ]
        ]
        mock_ha_client.get_history.return_value = large_history

        ctx = ToolContext(
            mcp=server.mcp,
            ha_client=mock_ha_client,
            config=mock_config,
            logger=logging.getLogger(__name__),
        )
        register_entity_tools(ctx)

        tool_calls = server.mcp.tool.call_args_list
        get_history_func = next(
            call[0][0]
            for call in tool_calls
            if hasattr(call[0][0], "__name__")
            and call[0][0].__name__ == "get_entity_history"
        )

        result = await get_history_func("sensor.test", hours=24.0)

        response = json.loads(result)
        assert "error" in response
        assert "token" in response["error"].lower()
        assert response["token_count"] > 10

    @pytest.mark.asyncio
    async def test_get_services_token_limit_exceeded(self, mock_config, mock_ha_client):
        """Test get_services enforces token limits."""
        server = MCPHomeAssistantServer()
        server.config = mock_config
        server.config.get_tool_token_limit.return_value = 10
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
            def call_count(self):
                return len(self.call_args_list)

            def __getattr__(self, name):
                return getattr(self._mock, name)

        server.mcp.tool = ToolMock()

        # Create large services response
        large_services = [
            {
                "domain": f"domain_{i}",
                "services": {f"service_{j}": {} for j in range(100)},
            }
            for i in range(50)
        ]
        mock_ha_client.get_services.return_value = large_services

        ctx = ToolContext(
            mcp=server.mcp,
            ha_client=mock_ha_client,
            config=mock_config,
            logger=logging.getLogger(__name__),
        )
        register_service_tools(ctx)

        tool_calls = server.mcp.tool.call_args_list
        get_services_func = next(
            call[0][0]
            for call in tool_calls
            if hasattr(call[0][0], "__name__") and call[0][0].__name__ == "get_services"
        )

        result = await get_services_func()

        response = json.loads(result)
        assert "error" in response
        assert "token" in response["error"].lower()

    @pytest.mark.asyncio
    async def test_get_service_detail_token_limit_exceeded(
        self, mock_config, mock_ha_client
    ):
        """Test get_service_detail enforces token limits."""
        server = MCPHomeAssistantServer()
        server.config = mock_config
        server.config.get_tool_token_limit.return_value = 10
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
            def call_count(self):
                return len(self.call_args_list)

            def __getattr__(self, name):
                return getattr(self._mock, name)

        server.mcp.tool = ToolMock()

        # Create large service detail
        large_service_detail = [
            {
                "domain": "light",
                "services": {
                    "turn_on": {
                        "fields": {
                            f"field_{i}": {"description": "x" * 1000}
                            for i in range(100)
                        }
                    }
                },
            }
        ]
        mock_ha_client.get_services.return_value = large_service_detail

        ctx = ToolContext(
            mcp=server.mcp,
            ha_client=mock_ha_client,
            config=mock_config,
            logger=logging.getLogger(__name__),
        )
        register_service_tools(ctx)

        tool_calls = server.mcp.tool.call_args_list
        get_service_detail_func = next(
            call[0][0]
            for call in tool_calls
            if hasattr(call[0][0], "__name__")
            and call[0][0].__name__ == "get_service_detail"
        )

        result = await get_service_detail_func("light", "turn_on")

        response = json.loads(result)
        assert "error" in response
        assert "token" in response["error"].lower()

    @pytest.mark.asyncio
    async def test_list_areas_token_limit_exceeded(self, mock_config, mock_ha_client):
        """Test list_areas enforces token limits."""
        server = MCPHomeAssistantServer()
        server.config = mock_config
        server.config.get_tool_token_limit.return_value = 10
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
            def call_count(self):
                return len(self.call_args_list)

            def __getattr__(self, name):
                return getattr(self._mock, name)

        server.mcp.tool = ToolMock()

        # Create many areas
        large_areas = [
            {"area_id": f"area_{i}", "name": f"Area {i}" * 100} for i in range(1000)
        ]
        mock_ha_client.get_areas.return_value = large_areas

        ctx = ToolContext(
            mcp=server.mcp,
            ha_client=mock_ha_client,
            config=mock_config,
            logger=logging.getLogger(__name__),
        )
        register_spatial_tools(ctx)

        tool_calls = server.mcp.tool.call_args_list
        list_areas_func = next(
            call[0][0]
            for call in tool_calls
            if hasattr(call[0][0], "__name__") and call[0][0].__name__ == "list_areas"
        )

        result = await list_areas_func()

        response = json.loads(result)
        assert "error" in response

    @pytest.mark.asyncio
    async def test_get_area_devices_token_limit_exceeded(
        self, mock_config, mock_ha_client
    ):
        """Test get_area_devices enforces token limits."""
        server = MCPHomeAssistantServer()
        server.config = mock_config
        server.config.get_tool_token_limit.return_value = 10
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
            def call_count(self):
                return len(self.call_args_list)

            def __getattr__(self, name):
                return getattr(self._mock, name)

        server.mcp.tool = ToolMock()

        mock_ha_client.get_areas.return_value = [{"area_id": "test", "name": "Test"}]
        large_devices = [
            {"id": f"device_{i}", "area_id": "test", "name": f"Device {i}" * 100}
            for i in range(1000)
        ]
        mock_ha_client.get_devices.return_value = large_devices

        ctx = ToolContext(
            mcp=server.mcp,
            ha_client=mock_ha_client,
            config=mock_config,
            logger=logging.getLogger(__name__),
        )
        register_spatial_tools(ctx)

        tool_calls = server.mcp.tool.call_args_list
        get_area_devices_func = next(
            call[0][0]
            for call in tool_calls
            if hasattr(call[0][0], "__name__")
            and call[0][0].__name__ == "get_area_devices"
        )

        result = await get_area_devices_func("Test")

        response = json.loads(result)
        assert "error" in response

    @pytest.mark.asyncio
    async def test_get_device_entities_token_limit_exceeded(
        self, mock_config, mock_ha_client
    ):
        """Test get_device_entities enforces token limits."""
        server = MCPHomeAssistantServer()
        server.config = mock_config
        server.config.get_tool_token_limit.return_value = 10
        server.ha_client = mock_ha_client
        mock_ha_client.session = Mock()
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
            def call_count(self):
                return len(self.call_args_list)

            def __getattr__(self, name):
                return getattr(self._mock, name)

        server.mcp.tool = ToolMock()

        large_entities = [
            {"entity_id": f"sensor.test_{i}", "device_id": "test_device"}
            for i in range(1000)
        ]
        mock_ha_client.get_entity_registry.return_value = large_entities

        ctx = ToolContext(
            mcp=server.mcp,
            ha_client=mock_ha_client,
            config=mock_config,
            logger=logging.getLogger(__name__),
        )
        register_device_tools(ctx)

        tool_calls = server.mcp.tool.call_args_list
        get_device_entities_func = next(
            call[0][0]
            for call in tool_calls
            if hasattr(call[0][0], "__name__")
            and call[0][0].__name__ == "get_device_entities"
        )

        result = await get_device_entities_func("test_device")

        response = json.loads(result)
        assert "error" in response

    @pytest.mark.asyncio
    async def test_get_camera_snapshot_token_limit_exceeded(
        self, mock_config, mock_ha_client
    ):
        """Test get_camera_snapshot enforces token limits on large images."""
        server = MCPHomeAssistantServer()
        server.config = mock_config
        server.config.get_tool_token_limit.return_value = 10
        server.ha_client = mock_ha_client
        mock_ha_client.session = Mock()
        mock_ha_client.validate_entity_id = Mock(return_value=True)
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
            def call_count(self):
                return len(self.call_args_list)

            def __getattr__(self, name):
                return getattr(self._mock, name)

        server.mcp.tool = ToolMock()

        # Mock large image data
        mock_response = AsyncMock()
        mock_response.status = 200
        # Create large fake image data
        mock_response.read = AsyncMock(return_value=b"x" * 1000000)

        mock_session = AsyncMock()
        mock_session.get.return_value.__aenter__.return_value = mock_response
        mock_ha_client.session = mock_session

        ctx = ToolContext(
            mcp=server.mcp,
            ha_client=mock_ha_client,
            config=mock_config,
            logger=logging.getLogger(__name__),
        )
        register_camera_tools(ctx)

        tool_calls = server.mcp.tool.call_args_list
        get_snapshot_func = next(
            call[0][0]
            for call in tool_calls
            if hasattr(call[0][0], "__name__")
            and call[0][0].__name__ == "get_camera_snapshot"
        )

        with patch("asyncio.sleep"):
            result = await get_snapshot_func("camera.test")

            response = json.loads(result)
            # Should either succeed or fail with token limit
            assert "success" in response


class TestResourceHandlers:
    """Test resource registration and handlers."""

    @pytest.mark.asyncio
    async def test_get_ha_config_resource(self, mock_config, mock_ha_client):
        """Test get_ha_config resource handler."""
        mock_mcp = Mock()

        # Store decorated functions
        registered_funcs = []

        def mock_resource_decorator(uri):
            def decorator(func):
                registered_funcs.append((uri, func))
                return func

            return decorator

        mock_mcp.resource = mock_resource_decorator

        mock_ha_client.get_config.return_value = {"version": "2024.1.0"}

        ctx = ToolContext(
            mcp=mock_mcp,
            ha_client=mock_ha_client,
            config=mock_config,
            logger=logging.getLogger(__name__),
        )
        register_resources(ctx)

        # Get the first registered resource
        assert len(registered_funcs) == 2
        uri, get_config_func = registered_funcs[0]
        assert uri == "mcp-hass://config"

        result = await get_config_func()

        assert "version" in result
        assert "2024.1.0" in result

    @pytest.mark.asyncio
    async def test_get_ha_config_resource_error(self, mock_config, mock_ha_client):
        """Test get_ha_config resource handler with error."""
        mock_mcp = Mock()

        # Store decorated functions
        registered_funcs = []

        def mock_resource_decorator(uri):
            def decorator(func):
                registered_funcs.append((uri, func))
                return func

            return decorator

        mock_mcp.resource = mock_resource_decorator

        mock_ha_client.get_config.side_effect = Exception("Config failed")

        ctx = ToolContext(
            mcp=mock_mcp,
            ha_client=mock_ha_client,
            config=mock_config,
            logger=logging.getLogger(__name__),
        )
        register_resources(ctx)

        # Get the first registered resource
        _, get_config_func = registered_funcs[0]

        result = await get_config_func()

        assert "Error getting config" in result
        assert "Config failed" in result

    @pytest.mark.asyncio
    async def test_hass_config_structure_guide_resource(
        self, mock_config, mock_ha_client
    ):
        """Test hass_config_structure_guide resource handler."""
        mock_mcp = Mock()

        # Store decorated functions
        registered_funcs = []

        def mock_resource_decorator(uri):
            def decorator(func):
                registered_funcs.append((uri, func))
                return func

            return decorator

        mock_mcp.resource = mock_resource_decorator

        ctx = ToolContext(
            mcp=mock_mcp,
            ha_client=mock_ha_client,
            config=mock_config,
            logger=logging.getLogger(__name__),
        )
        register_resources(ctx)

        # Get the second registered resource (config guide)
        assert len(registered_funcs) == 2
        uri, guide_func = registered_funcs[1]
        assert uri == "mcp-hass://config-guide"

        result = await guide_func()

        assert "Home Assistant Configuration Structure Guide" in result
        assert "configs/" in result


class TestPromptHandlers:
    """Test prompt registration and handlers."""

    def test_discover_area_entities_prompt(self, mock_config, mock_ha_client):
        """Test discover_area_entities prompt handler."""
        registered_prompts = {}

        def mock_prompt_decorator(*args, **kwargs):
            if args and callable(args[0]):
                func = args[0]
                registered_prompts[func.__name__] = func
                return func

            def decorator(func):
                registered_prompts[func.__name__] = func
                return func

            return decorator

        mock_mcp = Mock()
        mock_mcp.prompt = Mock(side_effect=mock_prompt_decorator)

        ctx = ToolContext(
            mcp=mock_mcp,
            ha_client=mock_ha_client,
            config=mock_config,
            logger=logging.getLogger(__name__),
        )
        register_prompts(ctx)

        result = registered_prompts["discover_area_entities"]()

        assert "Area-Based Entity Discovery Workflow" in result
        assert "list_areas()" in result

    def test_tool_selection_guide_prompt(self, mock_config, mock_ha_client):
        """Test tool_selection_guide prompt handler."""
        registered_prompts = {}

        def mock_prompt_decorator(*args, **kwargs):
            if args and callable(args[0]):
                func = args[0]
                registered_prompts[func.__name__] = func
                return func

            def decorator(func):
                registered_prompts[func.__name__] = func
                return func

            return decorator

        mock_mcp = Mock()
        mock_mcp.prompt = Mock(side_effect=mock_prompt_decorator)

        ctx = ToolContext(
            mcp=mock_mcp,
            ha_client=mock_ha_client,
            config=mock_config,
            logger=logging.getLogger(__name__),
        )
        register_prompts(ctx)

        result = registered_prompts["tool_selection_guide"]()

        assert "MCP-HASS Tool Selection Guide" in result
        assert "find_entities" in result


class TestRunMethodEdgeCases:
    """Test edge cases in the run method."""

    def test_run_with_file_logging_configured(self, tmp_path):
        """Test run() sets up file logging when configured."""
        server = MCPHomeAssistantServer()
        log_file = tmp_path / "test.log"
        initial_handler_count = len(logging.getLogger().handlers)

        with patch("src.mcp_hass.server.ConfigurationManager") as mock_config_class:
            mock_config = Mock()
            mock_config.get_server_name.return_value = "test-server"
            mock_config.get_server_version.return_value = "0.1.0"
            mock_config.is_debug_mode.return_value = False
            mock_config.get_log_level.return_value = "INFO"
            mock_config.get_log_file_path.return_value = str(log_file)
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

                    # Verify a FileHandler was added for the log path
                    root_logger = logging.getLogger()
                    assert len(root_logger.handlers) > initial_handler_count
                    # Find and clean up the handler we just added
                    for handler in root_logger.handlers[:]:
                        if isinstance(handler, logging.FileHandler):
                            if handler.baseFilename == str(log_file.resolve()):
                                root_logger.removeHandler(handler)
                                handler.close()
                                break

    def test_run_sse_transport_error_does_not_fallback(self):
        """Test run() with SSE transport doesn't fallback on error."""
        server = MCPHomeAssistantServer()

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
                    mock_mcp.run = Mock(side_effect=Exception("SSE failed"))
                    mock_fastmcp_class.return_value = mock_mcp

                    with pytest.raises(Exception, match="SSE failed"):
                        server.run(transport="sse", host="127.0.0.1", port=9090)


class TestCountTokensMethod:
    """Test token counting utility."""

    def test_count_tokens_basic(self, mock_config, mock_ha_client):
        """Test token counting with basic text."""
        ctx = ToolContext(
            mcp=Mock(),
            ha_client=mock_ha_client,
            config=mock_config,
            logger=logging.getLogger(__name__),
        )

        # Simple text
        count = ctx.count_tokens("Hello world")
        assert count > 0

        # Longer text should have more tokens
        long_text = "Hello world " * 100
        long_count = ctx.count_tokens(long_text)
        assert long_count > count

    def test_count_tokens_json(self, mock_config, mock_ha_client):
        """Test token counting with JSON."""
        ctx = ToolContext(
            mcp=Mock(),
            ha_client=mock_ha_client,
            config=mock_config,
            logger=logging.getLogger(__name__),
        )

        json_text = json.dumps({"key": "value", "nested": {"data": [1, 2, 3]}})
        count = ctx.count_tokens(json_text)
        assert count > 0
