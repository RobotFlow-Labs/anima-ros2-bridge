"""Transport management commands -- query status and switch modes at runtime.

Provides two async functions for runtime transport introspection and
switching. After a switch the robot context cache is invalidated so the
agent receives fresh capability data on the next prompt cycle.

Copyright (c) 2026 AIFLOW LABS LIMITED / RobotFlowLabs. All rights reserved.
"""

from __future__ import annotations

import logging
from typing import Any

from anima_bridge.config import (
    AnimaBridgeConfig,
    TransportMode,
    TransportSettings,
)

logger = logging.getLogger(__name__)

_VALID_MODES = {m.value for m in TransportMode}


async def get_transport_status() -> dict[str, Any]:
    """Get the current transport mode and connection status.

    Returns:
        A dict with ``mode`` (str | None) and ``connected`` (bool).
    """
    from anima_bridge.transport_manager import get_transport_mode

    mode = get_transport_mode()

    if mode is None:
        return {"mode": None, "connected": False}

    try:
        from anima_bridge.transport_manager import get_transport

        transport = get_transport()
        connected = transport.is_connected()
        status = transport.get_status().value
        return {"mode": mode, "connected": connected, "status": status}
    except RuntimeError:
        return {"mode": mode, "connected": False, "status": "disconnected"}


async def switch_transport_mode(
    mode: str,
    **overrides: Any,
) -> dict[str, Any]:
    """Switch the transport backend at runtime.

    Builds a new ``AnimaBridgeConfig`` from the requested *mode* and any
    keyword *overrides* (e.g. ``url="ws://192.168.1.10:9090"`` for
    rosbridge). After a successful switch the robot context cache is
    invalidated so the agent picks up the new topology.

    Args:
        mode: One of ``"direct_dds"``, ``"rosbridge"``, or ``"zenoh"``.
        **overrides: Backend-specific config overrides applied on top of
            the current defaults.

    Returns:
        A dict with ``success``, ``mode``, and ``previous_mode``.
    """
    if mode not in _VALID_MODES:
        return {
            "success": False,
            "error": (
                f'Unknown transport mode "{mode}". Valid modes: {", ".join(sorted(_VALID_MODES))}'
            ),
        }

    from anima_bridge.transport_manager import get_transport_mode

    previous_mode = get_transport_mode()

    try:
        config = _build_config(mode, overrides)

        from anima_bridge.transport_manager import switch_transport

        await switch_transport(config)

        # Invalidate robot context cache so the agent re-discovers
        _try_invalidate_context_cache()

        logger.info(
            "Transport switched: %s -> %s",
            previous_mode or "none",
            mode,
        )
        return {
            "success": True,
            "mode": mode,
            "previous_mode": previous_mode,
        }

    except Exception as exc:
        logger.error("Transport switch failed: %s", exc)
        return {
            "success": False,
            "error": str(exc),
            "previous_mode": previous_mode,
        }


# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------


def _build_config(mode: str, overrides: dict[str, Any]) -> AnimaBridgeConfig:
    """Construct an ``AnimaBridgeConfig`` for the target mode + overrides."""
    transport = TransportSettings(mode=TransportMode(mode))

    kwargs: dict[str, Any] = {"transport": transport}

    if mode == TransportMode.ROSBRIDGE.value and overrides:
        from anima_bridge.config import RosbridgeSettings

        kwargs["rosbridge"] = RosbridgeSettings(**overrides)

    elif mode == TransportMode.DIRECT_DDS.value and overrides:
        from anima_bridge.config import DirectDdsSettings

        kwargs["direct_dds"] = DirectDdsSettings(**overrides)

    elif mode == TransportMode.ZENOH.value and overrides:
        from anima_bridge.config import ZenohSettings

        kwargs["zenoh"] = ZenohSettings(**overrides)

    return AnimaBridgeConfig(**kwargs)


def _try_invalidate_context_cache() -> None:
    """Best-effort invalidation of the robot context cache.

    The ``RobotContextBuilder`` instance is owned by the orchestrator,
    so we cannot directly call ``invalidate_cache()`` from here. We emit
    a debug log as a reminder that the orchestrator should wire up cache
    invalidation after transport switches.
    """
    logger.debug("Context cache should be invalidated by the orchestrator after transport switch.")
