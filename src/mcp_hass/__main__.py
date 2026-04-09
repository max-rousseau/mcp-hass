# SPDX-License-Identifier: BSD-3-Clause
"""
Entry point for MCP-HASS server.

Allows running the server using: python -m mcp_hass
"""

import asyncio
from .server import main

if __name__ == "__main__":
    asyncio.run(main())
