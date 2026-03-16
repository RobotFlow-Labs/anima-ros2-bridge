"""Tool: list available ROS2 topics.

Copyright 2026 AIFLOW LABS LIMITED. All rights reserved.
"""

from __future__ import annotations

from anima_bridge.transport_manager import get_transport


async def ros2_list_topics() -> dict:
    """List all discovered ROS2 topics (excluding internal ones).

    Returns:
        Dict with ``success`` and ``topics`` (list of name/type dicts)
        on success, or ``success=False`` and ``error`` on failure.
    """
    try:
        transport = get_transport()
        topics = await transport.list_topics()
        return {
            "success": True,
            "topics": [{"name": t.name, "type": t.msg_type} for t in topics],
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
