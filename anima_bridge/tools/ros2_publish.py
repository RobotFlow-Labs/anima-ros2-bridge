"""Tool: publish a message to any ROS2 topic.

Copyright (c) 2026 AIFLOW LABS LIMITED / RobotFlowLabs. All rights reserved.
"""

from __future__ import annotations

from typing import Any

from anima_bridge.transport.types import PublishOptions
from anima_bridge.transport_manager import get_transport


async def ros2_publish(topic: str, msg_type: str, message: dict[str, Any]) -> dict[str, Any]:
    """Publish a single message to a ROS2 topic.

    Args:
        topic: Target topic name (e.g. ``"/cmd_vel"``).
        msg_type: Fully qualified message type (e.g. ``"geometry_msgs/msg/Twist"``).
        message: Message payload as a plain dict.

    Returns:
        Dict with ``success``, ``topic``, and ``msg_type`` on success,
        or ``success=False`` and ``error`` on failure.
    """
    try:
        transport = get_transport()
        options = PublishOptions(topic=topic, msg_type=msg_type, msg=message)
        result = await transport.publish(options)
        if result.success:
            return {"success": True, "topic": topic, "msg_type": msg_type}
        return {"success": False, "error": result.error or "Publish failed"}
    except Exception as e:
        return {"success": False, "error": str(e)}
