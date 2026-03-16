"""Transport factory for the ANIMA bridge.

Creates the correct ``AnimaTransport`` implementation based on the
configured transport mode. Uses lazy imports so that unused backends
(and their heavy dependencies like rclpy) are never loaded.

Copyright (c) 2026 AIFLOW LABS LIMITED / RobotFlowLabs. All rights reserved.
"""

from __future__ import annotations

from anima_bridge.config import AnimaBridgeConfig, TransportMode
from anima_bridge.transport.base import AnimaTransport


async def create_transport(config: AnimaBridgeConfig) -> AnimaTransport:
    """Instantiate the transport backend specified by *config*.

    Args:
        config: A validated ``AnimaBridgeConfig`` instance.

    Returns:
        An ``AnimaTransport`` ready to ``connect()``.

    Raises:
        ImportError: If the required backend dependency is not installed.
        ValueError: If the transport mode is unknown.
    """
    mode = config.transport.mode

    if mode == TransportMode.DIRECT_DDS:
        try:
            from anima_bridge.transport.direct_dds import DirectDdsTransport
        except ImportError as exc:
            raise ImportError(
                "Direct DDS transport requires 'rclpy'. "
                "Install it with: pip install rclpy (with ROS2 workspace sourced)."
            ) from exc
        return DirectDdsTransport(domain_id=config.direct_dds.domain_id)

    if mode == TransportMode.ROSBRIDGE:
        try:
            from anima_bridge.transport.rosbridge import RosbridgeTransport
        except ImportError as exc:
            raise ImportError(
                "Rosbridge transport requires 'websockets'. Install it with: uv add websockets"
            ) from exc
        return RosbridgeTransport(
            url=config.rosbridge.url,
            reconnect=config.rosbridge.reconnect,
            reconnect_interval_ms=config.rosbridge.reconnect_interval_ms,
            max_reconnect_attempts=config.rosbridge.max_reconnect_attempts,
        )

    if mode == TransportMode.ZENOH:
        try:
            from anima_bridge.transport.zenoh import ZenohTransport  # type: ignore[attr-defined]
        except ImportError as exc:
            raise ImportError(
                "Zenoh transport requires 'zenoh'. Install it with: pip install eclipse-zenoh."
            ) from exc
        return ZenohTransport(router_url=config.zenoh.router_url)  # type: ignore[no-any-return]

    raise ValueError(f"Unknown transport mode: {mode!r}")
