# SPDX-License-Identifier: BSD-3-Clause
"""
MCP-HASS Prompt Registration Module.

Provides guided workflows and decision-making assistance for common tasks.
"""

from .handlers import register_prompts

__all__ = [
    "register_prompts",
]
