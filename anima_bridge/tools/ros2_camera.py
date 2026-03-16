"""Tool: capture a single frame from a ROS2 camera topic.

Copyright 2026 AIFLOW LABS LIMITED. All rights reserved.
"""

from __future__ import annotations

import base64

from anima_bridge.transport_manager import get_transport


async def ros2_camera_snapshot(
    topic: str = "/camera/image_raw/compressed",
    timeout_ms: int = 5000,
) -> dict:
    """Capture one frame from a compressed image topic.

    Subscribes to a ``sensor_msgs/msg/CompressedImage`` topic, waits for
    a single message, and returns the image data as base64.

    Args:
        topic: Camera topic publishing ``CompressedImage`` messages.
        timeout_ms: Maximum time to wait for a frame in milliseconds.

    Returns:
        Dict with ``success``, ``topic``, ``format``, and ``data``
        (base64-encoded image bytes) on success, or ``success=False``
        and ``error`` on failure.
    """
    try:
        transport = get_transport()
        result = await transport.subscribe_once(
            topic=topic,
            msg_type="sensor_msgs/msg/CompressedImage",
            timeout_ms=timeout_ms,
        )
        if not result.success:
            return {"success": False, "error": result.error or "timeout"}

        msg = result.msg or {}
        image_format = msg.get("format", "jpeg")
        raw_data = msg.get("data", b"")

        if isinstance(raw_data, (bytes, bytearray)):
            encoded = base64.b64encode(raw_data).decode("ascii")
        else:
            encoded = base64.b64encode(bytes(raw_data)).decode("ascii")

        return {
            "success": True,
            "topic": topic,
            "format": image_format,
            "data": encoded,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
