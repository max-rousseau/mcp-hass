# SPDX-License-Identifier: BSD-3-Clause
"""
Camera snapshot tools for MCP-HASS.

Provides camera operations:
- get_camera_snapshot: Capture and return snapshot with intelligent downsampling
"""

import asyncio
import base64
import io
import json
import uuid
from typing import TYPE_CHECKING

from PIL import Image

if TYPE_CHECKING:
    from .context import ToolContext


def register_camera_tools(ctx: "ToolContext") -> None:
    """Register camera snapshot tools with FastMCP.

    Args:
        ctx: Tool context with mcp, ha_client, config, logger dependencies
    """

    @ctx.mcp.tool()
    async def get_camera_snapshot(entity_id: str) -> str:
        """Capture and return a snapshot from any Home Assistant camera entity.

        This tool captures a snapshot from a Home Assistant camera entity using
        the camera.snapshot service, then retrieves and intelligently downsamples
        the image for LLM optimization before returning it as base64-encoded data.

        Args:
            entity_id: Camera entity ID (e.g., "camera.g4p_patio_high")

        Returns:
            JSON string containing:
            - success: bool - Whether the operation succeeded
            - image_base64: str - Base64-encoded image data (only on success)
            - snapshot_id: str - UUID v4 identifier for this snapshot (only on success)
            - original_size: str - Original image dimensions (e.g., "3840x2160")
            - final_size: str - Final image dimensions after processing (e.g., "1024x576")
            - downsampled: bool - Whether image was downsampled for optimization
            - error: str - Error message (only on failure)

        Implementation Details:
            1. Generates UUID v4 as snapshot identifier
            2. Calls camera.snapshot service to save image to /config/www/snaps/{uuid}.jpg
            3. Waits 500ms for file write completion
            4. Fetches image via HTTP GET from {hass_url}/local/snaps/{uuid}.jpg
            5. Intelligently downsamples images >1024px using high-quality LANCZOS resampling
            6. Converts processed image data to base64 for MCP transport

        Security:
            - Uses secure temporary file approach with UUID naming
            - Files saved to Home Assistant's www directory for secure HTTP access
            - Automatic cleanup handled by Home Assistant's www directory management

        Example:
            get_camera_snapshot("camera.front_door")
            # Returns: {
            #   "success": true,
            #   "image_base64": "/9j/4AAQ...",
            #   "snapshot_id": "abc123...",
            #   "original_size": "3840x2160",
            #   "final_size": "1024x576",
            #   "downsampled": true
            # }
        """
        try:
            if not ctx.ha_client.validate_entity_id(entity_id):
                return json.dumps(
                    {
                        "success": False,
                        "error": f"Invalid entity ID format: {entity_id}",
                        "image_base64": "",
                        "snapshot_id": "",
                        "original_size": "unknown",
                        "final_size": "unknown",
                        "downsampled": False,
                    },
                    indent=2,
                )

            # WORKAROUND: Take two snapshots to avoid stale cached images
            stale_id = str(uuid.uuid4())
            stale_filename = f"{stale_id}.jpg"
            stale_path = f"/config/www/snaps/{stale_filename}"

            ctx.logger.debug(
                f"Taking initial snapshot to clear cache for {entity_id} (ID: {stale_id})"
            )

            stale_service_data = {"entity_id": entity_id, "filename": stale_path}
            await ctx.ha_client.call_service("camera", "snapshot", stale_service_data)

            await asyncio.sleep(1.0)

            snapshot_id = str(uuid.uuid4())
            filename = f"{snapshot_id}.jpg"
            file_path = f"/config/www/snaps/{filename}"

            ctx.logger.debug(
                f"Taking fresh snapshot for {entity_id} with ID {snapshot_id}"
            )

            service_data = {"entity_id": entity_id, "filename": file_path}
            await ctx.ha_client.call_service("camera", "snapshot", service_data)

            await asyncio.sleep(0.5)

            local_url = f"/local/snaps/{filename}"
            full_url = f"{ctx.ha_client.base_url}{local_url}"

            ctx.logger.debug(f"Fetching snapshot from: {full_url}")

            if ctx.ha_client.session is None:
                await ctx.ha_client.connect()

            async with ctx.ha_client.session.get(full_url) as response:
                if response.status == 200:
                    image_data = await response.read()

                    original_size = None
                    final_size = None
                    downsampled = False

                    try:
                        image = Image.open(io.BytesIO(image_data))
                        original_size = image.size
                        max_dimension = 1024

                        if image.width > max_dimension or image.height > max_dimension:
                            aspect_ratio = image.width / image.height
                            if image.width > image.height:
                                new_width = max_dimension
                                new_height = int(max_dimension / aspect_ratio)
                            else:
                                new_height = max_dimension
                                new_width = int(max_dimension * aspect_ratio)

                            image = image.resize(
                                (new_width, new_height), Image.Resampling.LANCZOS
                            )

                            output_buffer = io.BytesIO()
                            image.save(
                                output_buffer,
                                format="JPEG",
                                quality=85,
                                optimize=True,
                            )
                            image_data = output_buffer.getvalue()

                            final_size = image.size
                            downsampled = True

                            ctx.logger.debug(
                                f"Downsampled image from {original_size} to {final_size} "
                                f"for entity {entity_id}"
                            )
                        else:
                            final_size = original_size
                            downsampled = False

                    except Exception as img_error:
                        ctx.logger.warning(
                            f"Failed to process image for downsampling: {img_error}. "
                            f"Using original image data."
                        )

                    image_base64 = base64.b64encode(image_data).decode("utf-8")

                    ctx.logger.info(
                        f"Successfully captured snapshot for {entity_id} (ID: {snapshot_id})"
                    )

                    result = json.dumps(
                        {
                            "success": True,
                            "image_base64": image_base64,
                            "snapshot_id": snapshot_id,
                            "original_size": (
                                f"{original_size[0]}x{original_size[1]}"
                                if original_size
                                else "unknown"
                            ),
                            "final_size": (
                                f"{final_size[0]}x{final_size[1]}"
                                if final_size
                                else "unknown"
                            ),
                            "downsampled": downsampled,
                            "error": "",
                        },
                        indent=2,
                    )

                    token_limit = ctx.get_token_limit()
                    if token_limit is not None:
                        token_count = ctx.count_tokens(result)
                        if token_count > token_limit:
                            return json.dumps(
                                {
                                    "success": False,
                                    "error": (
                                        f"Camera snapshot response is "
                                        f"{token_count:,} tokens, exceeds limit of "
                                        f"{token_limit:,}. The image is too large "
                                        f"even after downsampling."
                                    ),
                                    "image_base64": "",
                                    "snapshot_id": snapshot_id,
                                    "original_size": (
                                        f"{original_size[0]}x{original_size[1]}"
                                        if original_size
                                        else "unknown"
                                    ),
                                    "final_size": (
                                        f"{final_size[0]}x{final_size[1]}"
                                        if final_size
                                        else "unknown"
                                    ),
                                    "downsampled": downsampled,
                                    "token_count": token_count,
                                    "token_limit": token_limit,
                                },
                                indent=2,
                            )

                    return result
                else:
                    error_msg = (
                        f"Failed to retrieve snapshot image: HTTP {response.status}"
                    )
                    ctx.logger.error(error_msg)
                    return json.dumps(
                        {
                            "success": False,
                            "error": error_msg,
                            "image_base64": "",
                            "snapshot_id": snapshot_id,
                            "original_size": "unknown",
                            "final_size": "unknown",
                            "downsampled": False,
                        },
                        indent=2,
                    )

        except Exception as e:
            ctx.logger.error(f"Camera snapshot failed for {entity_id}: {e}")
            return json.dumps(
                {
                    "success": False,
                    "error": f"Camera snapshot failed: {str(e)}",
                    "image_base64": "",
                    "snapshot_id": "",
                    "original_size": "unknown",
                    "final_size": "unknown",
                    "downsampled": False,
                },
                indent=2,
            )
