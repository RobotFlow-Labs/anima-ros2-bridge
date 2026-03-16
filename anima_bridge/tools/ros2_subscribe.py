"""Tool: read one message from a ROS2 topic with timeout.

Copyright 2026 AIFLOW LABS LIMITED. All rights reserved.
"""

from __future__ import annotations

from anima_bridge.transport_manager import get_transport


async def ros2_subscribe_once(
    topic: str,
    msg_type: str | None = None,
    timeout_ms: int = 5000,
) -> dict:
    """Subscribe to a ROS2 topic and wait for a single message.

    Args:
        topic: Topic name to listen on (e.g. ``"/odom"``).
        msg_type: Message type string. If ``None``, the transport will
            attempt to resolve it from the ROS2 graph.
        timeout_ms: Maximum time to wait for a message in milliseconds.

    Returns:
        Dict with ``success``, ``topic``, and ``message`` on success,
        or ``success=False`` and ``error`` (e.g. ``"timeout"``) on failure.
    """
    try:
        transport = get_transport()
        result = await transport.subscribe_once(
            topic=topic, msg_type=msg_type, timeout_ms=timeout_ms
        )
        if result.success:
            return {"success": True, "topic": topic, "message": result.msg}
        return {"success": False, "error": result.error or "timeout"}
    except Exception as e:
        return {"success": False, "error": str(e)}
