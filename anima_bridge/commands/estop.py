"""Emergency stop command -- bypasses the agent entirely.

Copyright (c) 2026 AIFLOW LABS LIMITED / RobotFlowLabs. All rights reserved.

Publishes zero-velocity messages directly to the transport layer without
passing through the AI agent or safety validator. This is the last line
of defence and must work even if the agent is unresponsive.

WARNING: This command depends on the transport layer being available.
If the transport is completely down, a fallback using a raw rclpy publisher
is attempted. If rclpy is also unavailable, the e-stop will fail and log
at CRITICAL level. In that scenario the only recourse is a hardware e-stop.
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

    If the normal transport is unavailable, a fallback is attempted by
    creating a minimal rclpy publisher directly. If that also fails, the
    failure is logged at CRITICAL level and the caller receives
    ``success=False``.

    Args:
        namespace: ROS2 namespace prefix (e.g. ``"/go2"``).

    Returns:
        A dict with ``success`` (bool) and ``stopped_topics`` (list).
    """
    cmd_vel = f"{namespace}/cmd_vel" if namespace else "/cmd_vel"
    stopped: list[str] = []

    transport_exc: Exception | None = None

    # --- Primary path: use the active transport ---
    try:
        from anima_bridge.transport_manager import get_transport

        transport = get_transport()

        result = await transport.publish(
            PublishOptions(
                topic=cmd_vel,
                msg_type="geometry_msgs/msg/Twist",
                msg=_ZERO_TWIST,
            )
        )
        if result.success:
            stopped.append(cmd_vel)

        # Discover and zero arm joint-command topics (best-effort)
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

    except Exception as transport_exc:
        logger.error("ESTOP: transport unavailable (%s), attempting rclpy fallback", transport_exc)

    # --- Fallback path: raw rclpy publisher ---
    try:
        import rclpy
        from rclpy.node import Node

        if not rclpy.ok():
            rclpy.init()

        node = Node("anima_estop_fallback")
        try:
            from anima_bridge.transport.entity_cache import dict_to_msg, load_msg_class

            twist_cls = load_msg_class("geometry_msgs/msg/Twist")
            pub = node.create_publisher(twist_cls, cmd_vel, 10)
            ros_msg = dict_to_msg(twist_cls, _ZERO_TWIST)
            pub.publish(ros_msg)
            stopped.append(cmd_vel)
            logger.warning("ESTOP FALLBACK: zero velocity sent to %s via raw rclpy", cmd_vel)
            return {"success": True, "stopped_topics": stopped, "fallback": True}
        finally:
            node.destroy_node()

    except Exception as fallback_exc:
        logger.critical(
            "ESTOP TOTAL FAILURE: neither transport nor rclpy fallback available. "
            "Transport error: %s | Fallback error: %s. "
            "USE HARDWARE E-STOP IMMEDIATELY.",
            transport_exc,
            fallback_exc,
        )
        return {
            "success": False,
            "error": (
                f"E-stop failed: transport ({transport_exc}), "
                f"rclpy fallback ({fallback_exc}). Use hardware e-stop."
            ),
        }
