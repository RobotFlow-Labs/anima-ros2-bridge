"""Emergency stop command — bypasses the agent entirely.

Publishes zero-velocity messages directly to the transport layer without
passing through the AI agent or safety validator. This is the last line
of defence and must work even if the agent is unresponsive.

Copyright 2026 AIFLOW LABS LIMITED. All rights reserved.
"""

from __future__ import annotations

import logging

from anima_bridge.transport.types import PublishOptions

logger = logging.getLogger(__name__)

_ZERO_TWIST: dict[str, object] = {
    "linear": {"x": 0.0, "y": 0.0, "z": 0.0},
    "angular": {"x": 0.0, "y": 0.0, "z": 0.0},
}


async def emergency_stop(namespace: str = "") -> dict[str, object]:
    """Emergency stop -- immediately publishes zero velocity.

    This BYPASSES the agent and safety validator. It publishes a zero
    ``geometry_msgs/msg/Twist`` to ``{namespace}/cmd_vel`` and attempts
    to zero any detected arm joint-command topics.

    Args:
        namespace: ROS2 namespace prefix (e.g. ``"/go2"``).

    Returns:
        A dict with ``success`` (bool) and ``stopped_topics`` (list).
    """
    try:
        from anima_bridge.transport_manager import get_transport

        transport = get_transport()

        cmd_vel = f"{namespace}/cmd_vel" if namespace else "/cmd_vel"
        stopped: list[str] = []

        # 1. Zero the velocity topic
        result = await transport.publish(
            PublishOptions(
                topic=cmd_vel,
                msg_type="geometry_msgs/msg/Twist",
                msg=_ZERO_TWIST,
            )
        )
        if result.success:
            stopped.append(cmd_vel)

        # 2. Discover and zero arm joint-command topics
        try:
            topics = await transport.list_topics()
            arm_keywords = ("joint_command", "arm_cmd", "joint_group_cmd")
            for t in topics:
                if any(kw in t.name for kw in arm_keywords):
                    await transport.publish(
                        PublishOptions(
                            topic=t.name,
                            msg_type=t.msg_type,
                            msg={},  # empty msg = zero values
                        )
                    )
                    stopped.append(t.name)
        except Exception:
            # Arm discovery is best-effort; velocity stop already sent
            pass

        logger.warning("ESTOP: zero velocity sent to %s", stopped)
        return {"success": True, "stopped_topics": stopped}

    except Exception as exc:
        logger.error("ESTOP FAILED: %s", exc)
        return {"success": False, "error": str(exc)}
