# SPDX-License-Identifier: BSD-3-Clause
"""
Custom exceptions for Home Assistant client operations.

These exceptions provide specific error handling for different types of
failures that can occur when communicating with the Home Assistant API.
"""

from typing import Optional


class HomeAssistantError(Exception):
    """Base exception for all Home Assistant related errors."""

    def __init__(self, message: str, status_code: Optional[int] = None) -> None:
        """Initialize the exception with message and optional status code.

        Args:
            message: Human-readable error message
            status_code: HTTP status code if applicable
        """
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class HomeAssistantConnectionError(HomeAssistantError):
    """Raised when connection to Home Assistant fails."""

    def __init__(self, message: str = "Failed to connect to Home Assistant") -> None:
        """Initialize connection error.

        Args:
            message: Error message describing the connection failure
        """
        super().__init__(message)


class HomeAssistantAuthError(HomeAssistantError):
    """Raised when authentication with Home Assistant fails."""

    def __init__(self, message: str = "Authentication failed") -> None:
        """Initialize authentication error.

        Args:
            message: Error message describing the authentication failure
        """
        super().__init__(message, status_code=401)


class HomeAssistantAPIError(HomeAssistantError):
    """Raised when Home Assistant API returns an error response."""

    def __init__(self, message: str, status_code: int) -> None:
        """Initialize API error with status code.

        Args:
            message: Error message from the API
            status_code: HTTP status code from the response
        """
        super().__init__(message, status_code)


class HomeAssistantTimeoutError(HomeAssistantError):
    """Raised when requests to Home Assistant time out."""

    def __init__(self, message: str = "Request to Home Assistant timed out") -> None:
        """Initialize timeout error.

        Args:
            message: Error message describing the timeout
        """
        super().__init__(message)


class HomeAssistantValidationError(HomeAssistantError):
    """Raised when input validation fails."""

    def __init__(self, message: str, field: Optional[str] = None) -> None:
        """Initialize validation error.

        Args:
            message: Error message describing the validation failure
            field: Name of the field that failed validation
        """
        super().__init__(message)
        self.field = field
