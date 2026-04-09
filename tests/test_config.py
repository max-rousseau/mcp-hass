"""
Test suite for ConfigurationManager.

Tests ensure NO silent fallbacks and proper error handling for configuration.
ALL environment variables are REQUIRED - missing values cause startup failure.
"""

import inspect
import os
import tempfile
from pathlib import Path
from unittest.mock import mock_open, patch

import pytest

from src.mcp_hass.config.manager import ConfigurationError, ConfigurationManager


def get_complete_env_vars() -> dict:
    """Return a complete set of ALL required environment variables.

    This represents a valid, complete configuration. Tests can copy and modify
    this base set as needed.
    """
    return {
        # Home Assistant
        "HA_BASE_URL": "http://localhost:8123",
        "HA_TOKEN": "test_token_that_is_long_enough_for_validation",
        "HA_TIMEOUT": "10",
        "WS_RECONNECT_ATTEMPTS": "5",
        "HA_SSL_VERIFY": "true",
        # Server
        "MCP_SERVER_NAME": "MCP-HASS",
        "LOG_LEVEL": "INFO",
        "DEBUG_MODE": "false",
    }


@pytest.fixture
def complete_env():
    """Provide complete environment variables for tests."""
    return get_complete_env_vars()


@pytest.fixture
def _isolated_config_env():
    """Isolate tests from real config files by using temp directories.

    This mocks filesystem boundaries (Path.home and working directory)
    rather than internal implementation methods.
    """
    with tempfile.TemporaryDirectory() as temp_home:
        with tempfile.TemporaryDirectory() as temp_cwd:
            # Mock Path.home() to return our temp directory (no config file exists)
            with patch.object(Path, "home", return_value=Path(temp_home)):
                # Change to temp working directory (no .env file exists)
                original_cwd = os.getcwd()
                os.chdir(temp_cwd)
                try:
                    yield temp_home, temp_cwd
                finally:
                    os.chdir(original_cwd)


class TestConfigurationManagerRequired:
    """Test handling of required configuration variables."""

    def test_missing_ha_base_url_raises_error(
        self, _isolated_config_env
    ):  # noqa: ARG002
        """Test that missing HA_BASE_URL raises ConfigurationError."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ConfigurationError) as exc_info:
                ConfigurationManager()

            assert "HA_BASE_URL" in str(exc_info.value)
            assert exc_info.value.variable_name == "HA_BASE_URL"

    def test_missing_ha_token_raises_error(
        self, _isolated_config_env, complete_env
    ):  # noqa: ARG002
        """Test that missing HA_TOKEN raises ConfigurationError."""
        env = complete_env.copy()
        del env["HA_TOKEN"]
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ConfigurationError) as exc_info:
                ConfigurationManager()

            assert "HA_TOKEN" in str(exc_info.value)
            assert exc_info.value.variable_name == "HA_TOKEN"

    def test_empty_ha_base_url_raises_error(
        self, _isolated_config_env, complete_env
    ):  # noqa: ARG002
        """Test that empty HA_BASE_URL raises ConfigurationError."""
        env = complete_env.copy()
        env["HA_BASE_URL"] = ""
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ConfigurationError) as exc_info:
                ConfigurationManager()

            assert "HA_BASE_URL" in str(exc_info.value)

    def test_empty_ha_token_raises_error(
        self, _isolated_config_env, complete_env
    ):  # noqa: ARG002
        """Test that empty HA_TOKEN raises ConfigurationError."""
        env = complete_env.copy()
        env["HA_TOKEN"] = ""
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ConfigurationError) as exc_info:
                ConfigurationManager()

            assert "HA_TOKEN" in str(exc_info.value)

    def test_missing_ha_timeout_raises_error(
        self, _isolated_config_env, complete_env
    ):  # noqa: ARG002
        """Test that missing HA_TIMEOUT raises ConfigurationError."""
        env = complete_env.copy()
        del env["HA_TIMEOUT"]
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ConfigurationError) as exc_info:
                ConfigurationManager()

            assert "HA_TIMEOUT" in str(exc_info.value)

    def test_missing_mcp_server_name_raises_error(
        self, _isolated_config_env, complete_env
    ):  # noqa: ARG002
        """Test that missing MCP_SERVER_NAME raises ConfigurationError."""
        env = complete_env.copy()
        del env["MCP_SERVER_NAME"]
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ConfigurationError) as exc_info:
                ConfigurationManager()

            assert "MCP_SERVER_NAME" in str(exc_info.value)


class TestConfigurationManagerValidation:
    """Test configuration validation."""

    def test_invalid_url_scheme_raises_error(
        self, _isolated_config_env, complete_env
    ):  # noqa: ARG002
        """Test that invalid URL scheme raises ConfigurationError."""
        env = complete_env.copy()
        env["HA_BASE_URL"] = "ftp://localhost:8123"
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ConfigurationError) as exc_info:
                ConfigurationManager()

            assert "http://" in str(exc_info.value) or "https://" in str(exc_info.value)
            assert exc_info.value.variable_name == "HA_BASE_URL"

    def test_short_token_raises_error(
        self, _isolated_config_env, complete_env
    ):  # noqa: ARG002
        """Test that suspiciously short token raises ConfigurationError."""
        env = complete_env.copy()
        env["HA_TOKEN"] = "short"
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ConfigurationError) as exc_info:
                ConfigurationManager()

            assert "too short" in str(exc_info.value)
            assert exc_info.value.variable_name == "HA_TOKEN"

    def test_negative_timeout_raises_error(
        self, _isolated_config_env, complete_env
    ):  # noqa: ARG002
        """Test that negative timeout raises ConfigurationError."""
        env = complete_env.copy()
        env["HA_TIMEOUT"] = "-5"
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ConfigurationError) as exc_info:
                ConfigurationManager()

            assert "positive" in str(exc_info.value)
            assert exc_info.value.variable_name == "HA_TIMEOUT"

    def test_invalid_log_level_raises_error(
        self, _isolated_config_env, complete_env
    ):  # noqa: ARG002
        """Test that invalid log level raises ConfigurationError."""
        env = complete_env.copy()
        env["LOG_LEVEL"] = "INVALID"
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ConfigurationError) as exc_info:
                ConfigurationManager()

            assert "LOG_LEVEL" in str(exc_info.value)
            assert exc_info.value.variable_name == "LOG_LEVEL"


class TestConfigurationManagerValid:
    """Test valid configuration scenarios."""

    def test_minimal_valid_configuration(
        self, _isolated_config_env, complete_env
    ):  # noqa: ARG002
        """Test minimal valid configuration with all required values."""
        with patch.dict(os.environ, complete_env, clear=True):
            config = ConfigurationManager()

            assert config.get_ha_base_url() == "http://localhost:8123"
            assert (
                config.get_ha_token() == "test_token_that_is_long_enough_for_validation"
            )
            assert config.get_ha_timeout() == 10.0
            assert config.get_server_name() == "MCP-HASS"
            assert config.get_log_level() == "INFO"

    def test_full_valid_configuration(
        self, _isolated_config_env, complete_env
    ):  # noqa: ARG002
        """Test full configuration with all values set."""
        env = complete_env.copy()
        env.update(
            {
                "HA_BASE_URL": "https://homeassistant.example.com:8123",
                "HA_TOKEN": "test_token_that_is_long_enough_for_validation_purposes",
                "HA_TIMEOUT": "15.5",
                "MCP_SERVER_NAME": "Custom-MCP-Server",
                "LOG_LEVEL": "DEBUG",
                "LOG_FILE_PATH": "/custom/log/path.log",
                "DEBUG_MODE": "true",
            }
        )

        with patch.dict(os.environ, env, clear=True):
            config = ConfigurationManager()

            assert config.get_ha_base_url() == "https://homeassistant.example.com:8123"
            assert (
                config.get_ha_token()
                == "test_token_that_is_long_enough_for_validation_purposes"
            )
            assert config.get_ha_timeout() == 15.5
            assert config.get_server_name() == "Custom-MCP-Server"
            version = config.get_server_version()
            assert isinstance(version, str)
            assert len(version) > 0
            assert config.get_log_level() == "DEBUG"
            assert config.is_debug_mode() is True
            assert config.get_log_file_path() == "/custom/log/path.log"

    def test_boolean_parsing(self, _isolated_config_env, complete_env):  # noqa: ARG002
        """Test boolean environment variable parsing."""
        true_values = ["true", "1", "yes", "on", "TRUE", "Yes", "ON"]
        false_values = ["false", "0", "no", "off", "FALSE", "No", "OFF"]

        for true_val in true_values:
            env = complete_env.copy()
            env["DEBUG_MODE"] = true_val
            with patch.dict(os.environ, env, clear=True):
                config = ConfigurationManager()
                assert config.is_debug_mode() is True

        for false_val in false_values:
            env = complete_env.copy()
            env["DEBUG_MODE"] = false_val
            with patch.dict(os.environ, env, clear=True):
                config = ConfigurationManager()
                assert config.is_debug_mode() is False

    def test_integer_parsing_errors(
        self, _isolated_config_env, complete_env
    ):  # noqa: ARG002
        """Test integer environment variable parsing errors."""
        env = complete_env.copy()
        env["WS_RECONNECT_ATTEMPTS"] = "not_a_number"
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ConfigurationError) as exc_info:
                ConfigurationManager()

            assert "integer" in str(exc_info.value)
            assert exc_info.value.variable_name == "WS_RECONNECT_ATTEMPTS"

    def test_float_parsing_errors(
        self, _isolated_config_env, complete_env
    ):  # noqa: ARG002
        """Test float environment variable parsing errors."""
        env = complete_env.copy()
        env["HA_TIMEOUT"] = "not_a_number"
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ConfigurationError) as exc_info:
                ConfigurationManager()

            assert "number" in str(exc_info.value)
            assert exc_info.value.variable_name == "HA_TIMEOUT"


class TestConfigurationManagerEnvFile:
    """Test .env file loading functionality."""

    def test_env_file_loading(self, complete_env, _isolated_config_env):  # noqa: ARG002
        """Test that .env file is properly loaded."""
        # Build env file content from complete_env
        # Note: empty values like LOG_FILE_PATH= need explicit handling
        lines = []
        for k, v in complete_env.items():
            if v:
                lines.append(f"{k}={v}")
            else:
                lines.append(f"{k}=")
        env_content = "# Test .env file\n" + "\n".join(lines) + "\n"

        with patch("builtins.open", mock_open(read_data=env_content)):
            # Only mock .env as existing (not XDG config path)
            def mock_exists(path):
                return str(path).endswith(".env")

            with patch.object(Path, "exists", mock_exists):
                with patch.dict(os.environ, {}, clear=True):
                    config = ConfigurationManager()

                    assert config.get_ha_base_url() == "http://localhost:8123"
                    assert (
                        config.get_ha_token()
                        == "test_token_that_is_long_enough_for_validation"
                    )

    def test_env_file_not_exists(self, complete_env):
        """Test behavior when .env file doesn't exist."""
        with patch("pathlib.Path.exists", return_value=False):
            with patch.dict(os.environ, complete_env, clear=True):
                # Should not raise an error
                config = ConfigurationManager()
                assert config.get_ha_base_url() == "http://localhost:8123"


class TestNoSilentFallbacks:
    """Test that NO silent fallbacks exist in the configuration manager."""

    def test_no_silent_fallback_patterns(self):
        """Test that the source code contains no silent fallback patterns."""
        # Get the source code of the ConfigurationManager class
        source = inspect.getsource(ConfigurationManager)

        # All os.environ.get calls should be in helper methods only
        # Check that we don't have any direct os.environ.get with default values
        # that aren't properly documented
        lines = source.split("\n")

        # Look for direct os.environ.get calls outside of helper methods
        in_helper_method = False
        in_docstring = False
        problematic_lines = []

        for line in lines:
            stripped = line.strip()

            # Track docstring boundaries
            if '"""' in stripped:
                # Toggle docstring state (simple heuristic)
                if stripped.count('"""') == 1:
                    in_docstring = not in_docstring
                # If line has 2 or more, it's a single-line docstring, stay same state

            if stripped.startswith("def _get_"):
                in_helper_method = True
            elif stripped.startswith("def ") and not stripped.startswith("def _get_"):
                in_helper_method = False

            # Skip if in helper method, docstring, or comment
            if in_helper_method or in_docstring:
                continue
            if stripped.startswith("#"):
                continue

            # Look for os.environ.get with a default value (second argument)
            if "os.environ.get(" in stripped and ", " in stripped:
                # Check if it's a legitimate use (just getting the value)
                if "os.environ.get(var_name)" not in stripped:
                    problematic_lines.append(stripped)

        assert (
            len(problematic_lines) == 0
        ), f"Found potentially unsafe os.environ.get usage: {problematic_lines}"

    def test_all_variables_are_required(
        self, _isolated_config_env, complete_env
    ):  # noqa: ARG002
        """Test that all variables are required (no hidden defaults)."""
        # Test each variable by removing it and checking for error
        required_vars = [
            "HA_BASE_URL",
            "HA_TOKEN",
            "HA_TIMEOUT",
            "WS_RECONNECT_ATTEMPTS",
            "HA_SSL_VERIFY",
            "MCP_SERVER_NAME",
            "LOG_LEVEL",
            "DEBUG_MODE",
        ]

        for var in required_vars:
            env = complete_env.copy()
            del env[var]
            with patch.dict(os.environ, env, clear=True):
                with pytest.raises(ConfigurationError) as exc_info:
                    ConfigurationManager()
                assert var in str(exc_info.value), f"{var} should be required"


class TestConfigurationManagerToolTokenLimit:
    """Test TOOL_TOKEN_LIMIT configuration parsing."""

    def test_tool_token_limit_valid_integer(
        self, _isolated_config_env, complete_env
    ):  # noqa: ARG002
        """Test parsing valid TOOL_TOKEN_LIMIT."""
        env = complete_env.copy()
        env["TOOL_TOKEN_LIMIT"] = "50000"
        with patch.dict(os.environ, env, clear=True):
            config = ConfigurationManager()
            assert config.get_tool_token_limit() == 50000

    def test_tool_token_limit_empty_returns_none(
        self, _isolated_config_env, complete_env
    ):  # noqa: ARG002
        """Test that empty TOOL_TOKEN_LIMIT returns None (no limit)."""
        env = complete_env.copy()
        env["TOOL_TOKEN_LIMIT"] = ""
        with patch.dict(os.environ, env, clear=True):
            config = ConfigurationManager()
            assert config.get_tool_token_limit() is None

    def test_tool_token_limit_invalid_raises_error(
        self, _isolated_config_env, complete_env
    ):  # noqa: ARG002
        """Test that invalid TOOL_TOKEN_LIMIT raises ConfigurationError."""
        env = complete_env.copy()
        env["TOOL_TOKEN_LIMIT"] = "not_a_number"
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ConfigurationError) as exc_info:
                ConfigurationManager()

            assert "TOOL_TOKEN_LIMIT must be an integer" in str(exc_info.value)
            assert exc_info.value.variable_name == "TOOL_TOKEN_LIMIT"

    def test_tool_token_limit_with_whitespace(
        self, _isolated_config_env, complete_env
    ):  # noqa: ARG002
        """Test that TOOL_TOKEN_LIMIT handles whitespace correctly."""
        env = complete_env.copy()
        env["TOOL_TOKEN_LIMIT"] = "  75000  "
        with patch.dict(os.environ, env, clear=True):
            config = ConfigurationManager()
            assert config.get_tool_token_limit() == 75000


class TestConfigurationManagerLogFilePath:
    """Test LOG_FILE_PATH configuration parsing."""

    def test_log_file_path_empty_returns_none(
        self, _isolated_config_env, complete_env
    ):  # noqa: ARG002
        """Test that empty LOG_FILE_PATH returns None (no file logging)."""
        env = complete_env.copy()
        env["LOG_FILE_PATH"] = ""
        with patch.dict(os.environ, env, clear=True):
            config = ConfigurationManager()
            assert config.get_log_file_path() is None

    def test_log_file_path_set_returns_path(
        self, _isolated_config_env, complete_env
    ):  # noqa: ARG002
        """Test that LOG_FILE_PATH returns the configured path."""
        env = complete_env.copy()
        env["LOG_FILE_PATH"] = "/var/log/mcp-hass/server.log"
        with patch.dict(os.environ, env, clear=True):
            config = ConfigurationManager()
            assert config.get_log_file_path() == "/var/log/mcp-hass/server.log"

    def test_log_file_path_with_whitespace(
        self, _isolated_config_env, complete_env
    ):  # noqa: ARG002
        """Test that LOG_FILE_PATH handles whitespace correctly."""
        env = complete_env.copy()
        env["LOG_FILE_PATH"] = "  /var/log/mcp-hass/test.log  "
        with patch.dict(os.environ, env, clear=True):
            config = ConfigurationManager()
            assert config.get_log_file_path() == "/var/log/mcp-hass/test.log"
