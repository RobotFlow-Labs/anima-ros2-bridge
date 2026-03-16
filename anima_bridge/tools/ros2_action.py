"""Tool: send a goal to a ROS2 action server and await the result.

Copyright 2026 AIFLOW LABS LIMITED. All rights reserved.
"""

from __future__ import annotations

from anima_bridge.transport.types import ActionGoalOptions
from anima_bridge.transport_manager import get_transport


async def ros2_action_goal(
    action: str,
    action_type: str,
    goal: dict,
) -> dict:
    """Send a goal to a ROS2 action server and wait for the result.

    Args:
        action: Action name (e.g. ``"/navigate_to_pose"``).
        action_type: Fully qualified action type
            (e.g. ``"nav2_msgs/action/NavigateToPose"``).
        goal: Goal payload as a plain dict.

    Returns:
        Dict with ``success``, ``action``, and ``result`` on success,
        or ``success=False`` and ``error`` on failure.
    """
    try:
        transport = get_transport()
        options = ActionGoalOptions(
            action=action,
            action_type=action_type,
            goal=goal,
        )
        result = await transport.send_action_goal(options)
        if result.success:
            return {"success": True, "action": action, "result": result.values}
        return {"success": False, "error": result.error or "Action failed"}
    except Exception as e:
        return {"success": False, "error": str(e)}
