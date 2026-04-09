# SPDX-License-Identifier: BSD-3-Clause
"""
HTTP middleware for MCP-HASS debugging.

Provides:
- DebugRequestMiddleware: Full request/response logging for debugging
"""

import logging
from typing import Any


class DebugRequestMiddleware:
    """Middleware to log full request/response details for debugging.

    When debug mode is enabled, logs:
    - Full request headers
    - Request body (JSON-RPC payloads)
    - Response status and headers
    - Response body (truncated for large responses)
    """

    MAX_BODY_LOG_SIZE = 4096

    def __init__(self, app: Any, logger: logging.Logger) -> None:
        """Initialize middleware.

        Args:
            app: ASGI application to wrap
            logger: Logger instance for debug output
        """
        self.app = app
        self.logger = logger

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        """ASGI interface."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "?")
        path = scope.get("path", "?")
        query_string = scope.get("query_string", b"").decode()

        raw_headers = scope.get("headers", [])
        decoded_headers = {
            (k.decode() if isinstance(k, bytes) else k): (
                v.decode() if isinstance(v, bytes) else v
            )
            for k, v in raw_headers
        }

        self.logger.debug(f"{'=' * 60}")
        self.logger.debug(f">>> REQUEST: {method} {path}")
        if query_string:
            self.logger.debug(f">>> Query: {query_string}")
        self.logger.debug(">>> Headers:")
        for k, v in decoded_headers.items():
            if k.lower() == "authorization":
                v = "[REDACTED]"
            self.logger.debug(f">>>   {k}: {v}")

        request_body = b""

        async def receive_wrapper() -> dict:
            nonlocal request_body
            message = await receive()
            if message["type"] == "http.request":
                body_chunk = message.get("body", b"")
                request_body += body_chunk
            return message

        response_status = None
        response_headers: list = []
        response_body = b""

        async def send_wrapper(message: dict) -> None:
            nonlocal response_status, response_headers, response_body

            if message["type"] == "http.response.start":
                response_status = message.get("status")
                response_headers = [
                    (
                        k.decode() if isinstance(k, bytes) else k,
                        v.decode() if isinstance(v, bytes) else v,
                    )
                    for k, v in message.get("headers", [])
                ]

            elif message["type"] == "http.response.body":
                body_chunk = message.get("body", b"")
                if len(response_body) < self.MAX_BODY_LOG_SIZE:
                    response_body += body_chunk[
                        : self.MAX_BODY_LOG_SIZE - len(response_body)
                    ]

            await send(message)

        await self.app(scope, receive_wrapper, send_wrapper)

        # SECURITY: logs MCP tool arguments (entity IDs, service data) in plaintext.
        # Accepted risk — this only runs when DEBUG_MODE=true (default false).
        if request_body:
            try:
                body_str = request_body.decode("utf-8")
                if len(body_str) > self.MAX_BODY_LOG_SIZE:
                    body_str = body_str[: self.MAX_BODY_LOG_SIZE] + "...[truncated]"
                self.logger.debug(f">>> Body: {body_str}")
            except UnicodeDecodeError:
                self.logger.debug(f">>> Body: <binary {len(request_body)} bytes>")

        self.logger.debug(f"<<< RESPONSE: {response_status}")
        self.logger.debug("<<< Headers:")
        for k, v in response_headers:
            self.logger.debug(f"<<<   {k}: {v}")

        if response_body:
            try:
                body_str = response_body.decode("utf-8")
                if len(body_str) > self.MAX_BODY_LOG_SIZE:
                    body_str = body_str[: self.MAX_BODY_LOG_SIZE] + "...[truncated]"
                self.logger.debug(f"<<< Body: {body_str}")
            except UnicodeDecodeError:
                self.logger.debug(f"<<< Body: <binary {len(response_body)} bytes>")

        self.logger.debug(f"{'=' * 60}")
