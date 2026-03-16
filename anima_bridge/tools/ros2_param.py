"""Tool: get and set ROS2 node parameters.

Copyright 2026 AIFLOW LABS LIMITED. All rights reserved.
"""

from __future__ import annotations

from typing import Any

from anima_bridge.transport_manager import get_transport


async def ros2_param_get(node: str, parameter: str) -> dict:
    """Read a single parameter from a ROS2 node.

    Args:
        node: Fully qualified node name (e.g. ``"/my_robot/controller"``).
        parameter: Parameter name to read.

    Returns:
        Dict with ``success``, ``node``, ``parameter``, and ``value``
        on success, or ``success=False`` and ``error`` on failure.
    """
    try:
        transport = get_transport()
        values = await transport.get_parameters(node, [parameter])
        value = values.get(parameter)
        return {
            "success": True,
            "node": node,
            "parameter": parameter,
            "value": value,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


async def ros2_param_set(node: str, parameter: str, value: Any) -> dict:
    """Set a single parameter on a ROS2 node.

    Args:
        node: Fully qualified node name (e.g. ``"/my_robot/controller"``).
        parameter: Parameter name to set.
        value: New value (bool, int, float, or str).

    Returns:
        Dict with ``success``, ``node``, ``parameter``, and ``value``
        on success, or ``success=False`` and ``error`` on failure.
    """
    try:
        transport = get_transport()
        ok = await transport.set_parameters(node, {parameter: value})
        if ok:
            return {
                "success": True,
                "node": node,
                "parameter": parameter,
                "value": value,
            }
        return {"success": False, "error": "Parameter set was not successful"}
    except Exception as e:
        return {"success": False, "error": str(e)}
