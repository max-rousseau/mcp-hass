"""
Test suite for YAML configuration management tools.

Tests the reload_yaml_config tool which validates and reloads
Home Assistant YAML configuration.
"""

import logging

import aiohttp
import pytest
from unittest.mock import AsyncMock, Mock

# Import from mcp_hass instead of src.mcp_hass to match yaml_config.py imports
from mcp_hass.ha_client.exceptions import (
    HomeAssistantConnectionError,
    HomeAssistantAuthError,
    HomeAssistantAPIError,
    HomeAssistantTimeoutError,
)
from mcp_hass.server import MCPHomeAssistantServer
from mcp_hass.tools import ToolContext, register_yaml_config_tools


@pytest.fixture
def mock_config():
    """Mock ConfigurationManager for testing."""
    config = Mock()
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
    client = Mock()
    client.base_url = "http://homeassistant.local:8123"
    client.token = "test_token_123456789"
    client.timeout = 10.0
    client.connect = AsyncMock()
    client.session = Mock()
    client.call_service = AsyncMock(return_value=[])
    return client


@pytest.fixture
def server_with_mocks(mock_config, mock_ha_client):
    """Create server instance with mocked dependencies."""
    server = MCPHomeAssistantServer()
    server.config = mock_config
    server.ha_client = mock_ha_client

    # Storage for registered tools
    registered_tools = {}

    def mock_tool_decorator(*args, **kwargs):
        if args and callable(args[0]):
            func = args[0]
            registered_tools[func.__name__] = func
            return func

        def decorator(func):
            registered_tools[func.__name__] = func
            return func

        return decorator

    server.mcp = Mock()
    server.mcp.tool = Mock(side_effect=mock_tool_decorator)
    server.mcp._test_tools = registered_tools

    # Create ToolContext for tool registration
    server._tool_ctx = ToolContext(
        mcp=server.mcp,
        ha_client=mock_ha_client,
        config=mock_config,
        logger=logging.getLogger(__name__),
    )

    return server


class TestReloadYamlConfig:
    """Test reload_yaml_config tool functionality."""

    @pytest.mark.asyncio
    async def test_reload_yaml_config_success(self, server_with_mocks):
        """Test successful validation and reload."""
        import json

        server = server_with_mocks

        # Mock successful validation response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"result": "valid"})
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        server.ha_client.session.post = Mock(return_value=mock_response)

        # Register tools using ToolContext
        register_yaml_config_tools(server._tool_ctx)

        # Get the registered tool function
        reload_func = server.mcp._test_tools["reload_yaml_config"]

        # Execute the tool
        result = await reload_func()

        # Parse JSON response
        response_data = json.loads(result)

        # Verify structured JSON response
        assert response_data["status"] == "success"
        assert response_data["validation"]["result"] == "valid"
        assert "validation passed" in response_data["validation"]["message"].lower()
        assert response_data["reload"]["service_called"] == "homeassistant.reload_all"
        assert response_data["reload"]["entities_affected"] == 0
        assert "reloaded successfully" in response_data["reload"]["message"].lower()
        assert "summary" in response_data

        server.ha_client.call_service.assert_called_once_with(
            "homeassistant", "reload_all"
        )

    @pytest.mark.asyncio
    async def test_reload_yaml_config_validation_fails(self, server_with_mocks):
        """Test that reload is NOT performed when validation fails."""
        server = server_with_mocks

        # Mock failed validation response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={
                "result": "invalid",
                "errors": [
                    "Invalid config for [automation]: required key not provided @ data['action']",
                    "Invalid config for [light]: expected a dictionary",
                ],
            }
        )
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        server.ha_client.session.post = Mock(return_value=mock_response)

        # Register tools using ToolContext
        register_yaml_config_tools(server._tool_ctx)

        # Get the registered tool function
        reload_func = server.mcp._test_tools["reload_yaml_config"]

        # Execute and expect ValueError
        with pytest.raises(ValueError) as exc_info:
            await reload_func()

        # Verify error message contains validation failure info
        assert "YAML validation failed" in str(exc_info.value)
        assert "required key not provided" in str(exc_info.value)

        # Verify reload was NOT called
        server.ha_client.call_service.assert_not_called()

    @pytest.mark.asyncio
    async def test_reload_yaml_config_api_unavailable(self, server_with_mocks):
        """Test handling of unavailable validation API."""
        server = server_with_mocks

        # Mock HTTP error response
        mock_response = AsyncMock()
        mock_response.status = 404
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        server.ha_client.session.post = Mock(return_value=mock_response)

        # Register tools using ToolContext
        register_yaml_config_tools(server._tool_ctx)

        # Get the registered tool function
        reload_func = server.mcp._test_tools["reload_yaml_config"]

        # Execute and expect ValueError
        with pytest.raises(ValueError) as exc_info:
            await reload_func()

        assert "validation API unavailable" in str(exc_info.value)
        assert "HTTP 404" in str(exc_info.value)

        # Verify reload was NOT called
        server.ha_client.call_service.assert_not_called()

    @pytest.mark.asyncio
    async def test_reload_yaml_config_connects_if_no_session(self, server_with_mocks):
        """Test that client connects if session doesn't exist."""
        import json

        server = server_with_mocks
        server.ha_client.session = None  # No existing session

        # Mock successful validation response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"result": "valid"})
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        # After connect, session should be available
        def set_session():
            server.ha_client.session = Mock()
            server.ha_client.session.post = Mock(return_value=mock_response)

        server.ha_client.connect = AsyncMock(side_effect=set_session)

        # Register tools using ToolContext
        register_yaml_config_tools(server._tool_ctx)

        # Get the registered tool function
        reload_func = server.mcp._test_tools["reload_yaml_config"]

        # Execute the tool
        result = await reload_func()

        # Verify connect was called
        server.ha_client.connect.assert_called_once()

        # Verify structured JSON response
        response_data = json.loads(result)
        assert response_data["status"] == "success"


class TestYamlConfigToolRegistration:
    """Test YAML config tool registration."""

    def test_reload_yaml_config_is_registered(self, server_with_mocks):
        """Test that reload_yaml_config tool is properly registered."""
        server = server_with_mocks

        register_yaml_config_tools(server._tool_ctx)

        # Check registered tool names via _test_tools
        assert "reload_yaml_config" in server.mcp._test_tools


class TestReloadYamlConfigErrorHandling:
    """Test error handling scenarios for reload_yaml_config."""

    @pytest.mark.asyncio
    async def test_connection_failure_during_validation(self, server_with_mocks):
        """Test connection failure during validation API call."""
        import json

        server = server_with_mocks

        # Mock connection error during validation
        mock_response = AsyncMock()
        mock_response.__aenter__ = AsyncMock(
            side_effect=aiohttp.ClientConnectorError(
                connection_key=None, os_error=OSError("Connection refused")
            )
        )
        mock_response.__aexit__ = AsyncMock(return_value=None)

        server.ha_client.session.post = Mock(return_value=mock_response)

        # Register tools
        register_yaml_config_tools(server._tool_ctx)
        reload_func = server.mcp._test_tools["reload_yaml_config"]

        # Execute and expect structured error response
        result = await reload_func()
        response_data = json.loads(result)

        assert response_data["status"] == "error"
        assert response_data["error_type"] == "connection"
        assert "Failed to connect" in response_data["message"]
        assert "troubleshooting" in response_data
        assert len(response_data["troubleshooting"]) > 0

        # Verify reload was NOT called
        server.ha_client.call_service.assert_not_called()

    @pytest.mark.asyncio
    async def test_authentication_failure_during_reload(self, server_with_mocks):
        """Test authentication failure during reload service call."""
        import json

        server = server_with_mocks

        # Mock successful validation
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"result": "valid"})
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        server.ha_client.session.post = Mock(return_value=mock_response)

        # Mock auth failure during service call
        server.ha_client.call_service = AsyncMock(
            side_effect=HomeAssistantAuthError("Invalid token")
        )

        # Register tools
        register_yaml_config_tools(server._tool_ctx)
        reload_func = server.mcp._test_tools["reload_yaml_config"]

        # Execute and expect structured error response
        result = await reload_func()
        response_data = json.loads(result)

        assert response_data["status"] == "error"
        assert response_data["error_type"] == "authentication"
        assert "Authentication failed" in response_data["message"]
        assert "troubleshooting" in response_data
        assert any("token" in hint.lower() for hint in response_data["troubleshooting"])

    @pytest.mark.asyncio
    async def test_timeout_during_validation(self, server_with_mocks):
        """Test timeout during validation API call."""
        import json

        server = server_with_mocks

        # Mock timeout during validation
        mock_response = AsyncMock()
        mock_response.__aenter__ = AsyncMock(
            side_effect=aiohttp.ServerTimeoutError("Request timeout")
        )
        mock_response.__aexit__ = AsyncMock(return_value=None)

        server.ha_client.session.post = Mock(return_value=mock_response)

        # Register tools
        register_yaml_config_tools(server._tool_ctx)
        reload_func = server.mcp._test_tools["reload_yaml_config"]

        # Execute and expect structured error response
        result = await reload_func()
        response_data = json.loads(result)

        assert response_data["status"] == "error"
        assert response_data["error_type"] == "timeout"
        assert "timed out" in response_data["message"].lower()
        assert "troubleshooting" in response_data

        # Verify reload was NOT called
        server.ha_client.call_service.assert_not_called()

    @pytest.mark.asyncio
    async def test_timeout_during_reload_operation(self, server_with_mocks):
        """Test timeout during reload service call."""
        import json

        server = server_with_mocks

        # Mock successful validation
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"result": "valid"})
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        server.ha_client.session.post = Mock(return_value=mock_response)

        # Mock timeout during service call
        server.ha_client.call_service = AsyncMock(
            side_effect=HomeAssistantTimeoutError("Reload timed out")
        )

        # Register tools
        register_yaml_config_tools(server._tool_ctx)
        reload_func = server.mcp._test_tools["reload_yaml_config"]

        # Execute and expect structured error response
        result = await reload_func()
        response_data = json.loads(result)

        assert response_data["status"] == "error"
        assert response_data["error_type"] == "timeout"
        assert "timed out" in response_data["message"].lower()
        assert "troubleshooting" in response_data

    @pytest.mark.asyncio
    async def test_api_error_during_reload(self, server_with_mocks):
        """Test unexpected API error during reload."""
        import json

        server = server_with_mocks

        # Mock successful validation
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"result": "valid"})
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        server.ha_client.session.post = Mock(return_value=mock_response)

        # Mock API error during service call
        server.ha_client.call_service = AsyncMock(
            side_effect=HomeAssistantAPIError("Service unavailable", status_code=503)
        )

        # Register tools
        register_yaml_config_tools(server._tool_ctx)
        reload_func = server.mcp._test_tools["reload_yaml_config"]

        # Execute and expect structured error response
        result = await reload_func()
        response_data = json.loads(result)

        assert response_data["status"] == "error"
        assert response_data["error_type"] == "api_error"
        assert "API error" in response_data["message"]
        assert response_data["status_code"] == 503
        assert "troubleshooting" in response_data

    @pytest.mark.asyncio
    async def test_connection_lost_during_reload(self, server_with_mocks):
        """Test connection lost during reload operation."""
        import json

        server = server_with_mocks

        # Mock successful validation
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"result": "valid"})
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        server.ha_client.session.post = Mock(return_value=mock_response)

        # Mock connection lost during service call
        server.ha_client.call_service = AsyncMock(
            side_effect=HomeAssistantConnectionError("Connection lost")
        )

        # Register tools
        register_yaml_config_tools(server._tool_ctx)
        reload_func = server.mcp._test_tools["reload_yaml_config"]

        # Execute and expect structured error response
        result = await reload_func()
        response_data = json.loads(result)

        assert response_data["status"] == "error"
        assert response_data["error_type"] == "connection"
        assert "Connection lost" in response_data["message"]
        assert "troubleshooting" in response_data
