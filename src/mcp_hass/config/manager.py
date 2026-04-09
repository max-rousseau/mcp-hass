# SPDX-License-Identifier: BSD-3-Clause
"""
Configuration manager for MCP-HASS.

Handles loading and validation of configuration from environment variables
with NO silent fallbacks, following the sacred coding standards.
"""

import os
from typing import Any, Dict, Optional
from pathlib import Path


class ConfigurationError(Exception):
    """Raised when configuration is invalid or missing."""

    def __init__(self, message: str, variable_name: Optional[str] = None) -> None:
        """Initialize configuration error.

        Args:
            message: Error description
            variable_name: Name of the problematic environment variable
        """
        super().__init__(message)
        self.message = message
        self.variable_name = variable_name


class ConfigurationManager:
    """Zero-silent-fallback configuration manager for MCP-HASS server.

    This configuration manager implements the sacred principle of explicit configuration
    with NO silent fallbacks. Every configuration value is either explicitly provided
    or has an explicitly documented default - no hidden assumptions.

    Configuration Categories:
        1. **Required Configuration**: Must be explicitly set or server fails to start
           - HA_BASE_URL: Home Assistant base URL (http:// or https://)
           - HA_TOKEN: Long-lived access token from Home Assistant

        2. **Optional Configuration**: Explicit defaults provided, clearly documented
           - HA_TIMEOUT: Request timeout (default: 10.0 seconds)
           - MCP_SERVER_NAME: Server identification (default: "MCP-HASS")
           - LOG_LEVEL: Logging verbosity (default: "INFO")

        3. **Development Configuration**: Debug and development settings
           - DEBUG_MODE: Enable debug logging and features (default: False)

    Usage Example:
        ```python
        try:
            config = ConfigurationManager()
            ha_url = config.get_ha_base_url()
            ha_token = config.get_ha_token()
        except ConfigurationError as e:
            print(f"Configuration Error: {e}")
            print("Please check .env.example for configuration guidance")
            sys.exit(1)
        ```

    Attributes:
        _config (Dict[str, Any]): Internal configuration storage with validated values

    Raises:
        ConfigurationError: Invalid, missing, or malformed configuration values
    """

    def __init__(self) -> None:
        """Initialize zero-silent-fallback configuration manager."""
        self._config: Dict[str, Any] = {}
        self._load_configuration()

    def _load_configuration(self) -> None:
        """Load and validate all configuration from environment variables.

        ALL variables are REQUIRED. No hidden defaults.
        If any variable is missing, the program fails catastrophically.
        """
        # Load .env file if it exists (for development)
        self._load_env_file()

        # ==========================================================================
        # HOME ASSISTANT CONFIGURATION (Required)
        # ==========================================================================
        self._config["ha_base_url"] = self._get_required_env("HA_BASE_URL")
        self._config["ha_token"] = self._get_required_env("HA_TOKEN")
        self._config["ha_timeout"] = self._get_required_float_env("HA_TIMEOUT")
        self._config["ws_reconnect_attempts"] = self._get_required_int_env(
            "WS_RECONNECT_ATTEMPTS"
        )
        self._config["ha_ssl_verify"] = self._get_required_bool_env("HA_SSL_VERIFY")

        # ==========================================================================
        # SERVER CONFIGURATION (Required)
        # ==========================================================================
        self._config["mcp_server_name"] = self._get_required_env("MCP_SERVER_NAME")
        self._config["log_level"] = self._get_required_env("LOG_LEVEL")
        self._config["debug_mode"] = self._get_required_bool_env("DEBUG_MODE")

        # LOG_FILE_PATH: Optional - enables file logging when set
        if "LOG_FILE_PATH" in os.environ and os.environ["LOG_FILE_PATH"].strip():
            self._config["log_file_path"] = os.environ["LOG_FILE_PATH"].strip()

        # TOOL_TOKEN_LIMIT: Optional - limits response size when set
        if "TOOL_TOKEN_LIMIT" in os.environ and os.environ["TOOL_TOKEN_LIMIT"].strip():
            try:
                self._config["tool_token_limit"] = int(os.environ["TOOL_TOKEN_LIMIT"])
            except ValueError:
                raise ConfigurationError(
                    f"TOOL_TOKEN_LIMIT must be an integer, got: {os.environ['TOOL_TOKEN_LIMIT']}",
                    variable_name="TOOL_TOKEN_LIMIT",
                )

        if (
            "MCP_SERVER_STATELESS" in os.environ
            and os.environ["MCP_SERVER_STATELESS"].strip()
        ):
            self._config["stateless_http"] = os.environ[
                "MCP_SERVER_STATELESS"
            ].strip().lower() in ("true", "1", "yes", "on")
        else:
            self._config["stateless_http"] = False

        # Validate configuration
        self._validate_configuration()

    def _load_env_file(self) -> None:
        """Load config file from standard locations (priority order).

        Checks in order:
        1. ~/.config/mcp-hass/config (primary, XDG standard)
        2. .env (current directory, development override)

        First file found wins. Environment variables always take precedence.
        """
        config_locations = [
            Path.home() / ".config" / "mcp-hass" / "config",  # XDG standard
            Path(".env"),  # Development override
        ]

        for config_file in config_locations:
            if config_file.exists():
                self._parse_config_file(config_file)
                break  # First one wins

    def _parse_config_file(self, config_file: Path) -> None:
        """Parse config file and load into environment variables.

        Args:
            config_file: Path to config file to parse
        """
        with open(config_file, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    if key:
                        # Only set if not already in environment
                        # Empty values are valid (e.g., LOG_FILE_PATH=)
                        if key not in os.environ:
                            os.environ[key] = value

    def _get_required_env(self, var_name: str, allow_empty: bool = False) -> str:
        """Get required environment variable.

        Args:
            var_name: Environment variable name
            allow_empty: If True, empty string is a valid value (for optional behaviors)

        Returns:
            Environment variable value (may be empty string if allow_empty=True)

        Raises:
            ConfigurationError: If variable is not set (or empty when allow_empty=False)
        """
        value = os.environ.get(var_name)

        # Variable not in environment at all
        if value is None:
            config_path = self.get_config_file_path()
            if config_path.exists():
                error_msg = (
                    f"Required variable '{var_name}' not set.\n\n"
                    f"Configuration file found: {config_path}\n\n"
                    f"Edit your configuration file:\n"
                    f"    vi {config_path}\n\n"
                    f"Then test:\n"
                    f"    mcp-hass validate"
                )
            else:
                error_msg = (
                    f"Required variable '{var_name}' not set.\n\n"
                    f"Configuration file not found. Run:\n\n"
                    f"    mcp-hass init"
                )
            raise ConfigurationError(error_msg, variable_name=var_name)

        value = value.strip()

        # Empty string check (only if empty not allowed)
        if not allow_empty and not value:
            raise ConfigurationError(
                f"Required variable '{var_name}' is set but empty.",
                variable_name=var_name,
            )

        return value

    def _get_required_bool_env(self, var_name: str) -> bool:
        """Get REQUIRED boolean environment variable.

        Args:
            var_name: Environment variable name

        Returns:
            Boolean value

        Raises:
            ConfigurationError: If variable is not set
        """
        value = self._get_required_env(var_name)
        return value.lower() in ("true", "1", "yes", "on")

    def _get_required_int_env(self, var_name: str) -> int:
        """Get REQUIRED integer environment variable.

        Args:
            var_name: Environment variable name

        Returns:
            Integer value

        Raises:
            ConfigurationError: If variable is not set or not a valid integer
        """
        value = self._get_required_env(var_name)
        try:
            return int(value)
        except ValueError:
            raise ConfigurationError(
                f"Environment variable '{var_name}' must be an integer, got: {value}",
                variable_name=var_name,
            )

    def _get_required_float_env(self, var_name: str) -> float:
        """Get REQUIRED float environment variable.

        Args:
            var_name: Environment variable name

        Returns:
            Float value

        Raises:
            ConfigurationError: If variable is not set or not a valid float
        """
        value = self._get_required_env(var_name)
        try:
            return float(value)
        except ValueError:
            raise ConfigurationError(
                f"Environment variable '{var_name}' must be a number, got: {value}",
                variable_name=var_name,
            )

    def _validate_configuration(self) -> None:
        """Validate the loaded configuration."""
        # Validate Home Assistant URL
        ha_url = self._config["ha_base_url"]
        if not ha_url.startswith(("http://", "https://")):
            raise ConfigurationError(
                f"HA_BASE_URL must start with http:// or https://, got: {ha_url}",
                variable_name="HA_BASE_URL",
            )

        # Validate token length (Home Assistant tokens are typically long)
        ha_token = self._config["ha_token"]
        if len(ha_token) < 20:
            raise ConfigurationError(
                "HA_TOKEN appears to be too short. Home Assistant tokens are "
                "typically much longer.",
                variable_name="HA_TOKEN",
            )

        # Validate timeout
        timeout = self._config["ha_timeout"]
        if timeout <= 0:
            raise ConfigurationError(
                f"HA_TIMEOUT must be positive, got: {timeout}",
                variable_name="HA_TIMEOUT",
            )

        # Validate log level
        valid_log_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        log_level = self._config["log_level"].upper()
        if log_level not in valid_log_levels:
            raise ConfigurationError(
                f"LOG_LEVEL must be one of {valid_log_levels}, got: {log_level}",
                variable_name="LOG_LEVEL",
            )
        self._config["log_level"] = log_level

        # Validate tool token limit (if set)
        tool_token_limit = self._config.get("tool_token_limit")
        if tool_token_limit is not None and tool_token_limit <= 0:
            raise ConfigurationError(
                f"TOOL_TOKEN_LIMIT must be positive, got: {tool_token_limit}",
                variable_name="TOOL_TOKEN_LIMIT",
            )

    def get_ha_base_url(self) -> str:
        """Get Home Assistant base URL."""
        return self._config["ha_base_url"]

    def get_ha_token(self) -> str:
        """Get Home Assistant access token."""
        return self._config["ha_token"]

    def get_ha_timeout(self) -> float:
        """Get Home Assistant request timeout."""
        return self._config["ha_timeout"]

    def get_ha_ssl_verify(self) -> bool:
        """Get whether TLS certificate verification is enabled."""
        return self._config["ha_ssl_verify"]

    def get_server_name(self) -> str:
        """Get MCP server name."""
        return self._config["mcp_server_name"]

    def get_server_version(self) -> str:
        """Get MCP server version from package metadata.

        The version is read from pyproject.toml via package metadata,
        not from user configuration. This ensures the version always
        matches the installed package.

        Returns:
            Package version string (e.g., "0.3.0")
        """
        from importlib.metadata import version

        return version("mcp-hass")

    def get_log_level(self) -> str:
        """Get logging level."""
        return self._config["log_level"]

    def get_log_file_path(self) -> Optional[str]:
        """Get log file path. None means file logging is disabled."""
        return self._config.get("log_file_path")

    def is_debug_mode(self) -> bool:
        """Check if debug mode is enabled."""
        return self._config["debug_mode"]

    def get_tool_token_limit(self) -> Optional[int]:
        """Get tool response token limit (None if no limit set)."""
        return self._config.get("tool_token_limit")

    def is_stateless_http(self) -> bool:
        """Check if stateless HTTP mode is enabled.

        When enabled, each request creates a fresh transport with no session
        tracking. Useful for clients that don't properly handle session
        expiration (404 responses).

        Returns:
            True if stateless HTTP mode is enabled.
        """
        return self._config["stateless_http"]

    @staticmethod
    def get_config_file_path() -> Path:
        """Get the primary config file path.

        Returns:
            Path to ~/.config/mcp-hass/config
        """
        return Path.home() / ".config" / "mcp-hass" / "config"
