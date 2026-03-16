"""Tool: call a ROS2 service and return the response.

Copyright (c) 2026 AIFLOW LABS LIMITED / RobotFlowLabs. All rights reserved.
"""

from __future__ import annotations

from typing import Any

from anima_bridge.transport.types import ServiceCallOptions
from anima_bridge.transport_manager import get_transport


async def ros2_service_call(
    service: str,
    srv_type: str | None = None,
    args: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Call a ROS2 service and wait for the response.

    Args:
        service: Service name (e.g. ``"/trigger_save"``).
        srv_type: Fully qualified service type (e.g. ``"std_srvs/srv/Trigger"``).
            If ``None``, the transport will attempt to resolve it.
        args: Request arguments as a plain dict. Defaults to empty.

    Returns:
        Dict with ``success``, ``service``, and ``response`` on success,
        or ``success=False`` and ``error`` on failure.
    """
    try:
        transport = get_transport()
        options = ServiceCallOptions(
            service=service,
            srv_type=srv_type,
            args=args or {},
        )
        result = await transport.call_service(options)
        if result.success:
            return {"success": True, "service": service, "response": result.values}
        return {"success": False, "error": result.error or "Service call failed"}
    except Exception as e:
        return {"success": False, "error": str(e)}
