"""ANIMA Bridge tool functions for ROS2 interaction.

Each tool is an async function that returns a dict with a ``success`` bool.
All tools obtain the transport via ``get_transport()`` and catch exceptions
internally, returning ``{"success": False, "error": ...}`` on failure.

Copyright 2026 AIFLOW LABS LIMITED. All rights reserved.
"""

from anima_bridge.tools.ros2_action import ros2_action_goal
from anima_bridge.tools.ros2_camera import ros2_camera_snapshot
from anima_bridge.tools.ros2_introspect import ros2_list_topics
from anima_bridge.tools.ros2_param import ros2_param_get, ros2_param_set
from anima_bridge.tools.ros2_publish import ros2_publish
from anima_bridge.tools.ros2_service import ros2_service_call
from anima_bridge.tools.ros2_subscribe import ros2_subscribe_once

__all__ = [
    "ros2_action_goal",
    "ros2_camera_snapshot",
    "ros2_list_topics",
    "ros2_param_get",
    "ros2_param_set",
    "ros2_publish",
    "ros2_service_call",
    "ros2_subscribe_once",
]
