"""Singleton transport manager for the ANIMA bridge.

Provides a single point of access to the active ``AnimaTransport`` instance.
All tools, commands, and the safety layer use ``get_transport()`` to obtain
the current transport without caring about which backend is active.

Supports runtime transport switching (e.g. switching from rosbridge to
direct DDS) with an asyncio lock to prevent concurrent switch operations.

Copyright 2026 AIFLOW LABS LIMITED. All rights reserved.
"""

from __future__ import annotations

import asyncio
import logging

from anima_bridge.config import AnimaBridgeConfig, TransportMode
from anima_bridge.transport.base import AnimaTransport
from anima_bridge.transport.factory import create_transport

logger = logging.getLogger(__name__)

# Module-level singleton state
_transport: AnimaTransport | None = None
_current_mode: TransportMode | None = None
_switch_lock: asyncio.Lock | None = None


def _get_lock() -> asyncio.Lock:
    """Lazily create the asyncio lock (must be created inside an event loop)."""
    global _switch_lock
    if _switch_lock is None:
        _switch_lock = asyncio.Lock()
    return _switch_lock


def get_transport() -> AnimaTransport:
    """Return the active transport instance.

    Raises:
        RuntimeError: If no transport is connected. Call ``connect()`` first.
    """
    if _transport is None:
        raise RuntimeError("No transport is active. Call TransportManager.connect() first.")
    return _transport


def get_transport_mode() -> str | None:
    """Return the current transport mode name, or ``None`` if not connected."""
    return _current_mode.value if _current_mode is not None else None


async def connect(config: AnimaBridgeConfig | None = None) -> AnimaTransport:
    """Create, connect, and store the transport specified by *config*.

    If a transport is already connected, this is a no-op and returns the
    existing instance. Use ``switch_transport()`` to change backends.

    Args:
        config: Bridge configuration. Defaults to ``AnimaBridgeConfig()``
                (local DDS, domain 0).

    Returns:
        The connected ``AnimaTransport`` instance.
    """
    global _transport, _current_mode

    if _transport is not None and _transport.is_connected():
        logger.info("Transport already connected (%s), reusing", _current_mode)
        return _transport

    if config is None:
        config = AnimaBridgeConfig()

    transport = await create_transport(config)

    transport.on_connection(lambda status: logger.info("Transport status: %s", status.value))

    await transport.connect()

    _transport = transport
    _current_mode = config.transport.mode
    logger.info("Transport connected: %s", _current_mode.value)

    return _transport


async def disconnect() -> None:
    """Disconnect and release the current transport."""
    global _transport, _current_mode

    if _transport is not None:
        await _transport.disconnect()
        logger.info("Transport disconnected: %s", _current_mode)
        _transport = None
        _current_mode = None


async def switch_transport(config: AnimaBridgeConfig) -> AnimaTransport:
    """Switch to a different transport backend at runtime.

    Acquires an async lock so that only one switch can happen at a time.
    The old transport is disconnected before the new one is created. On
    failure the bridge is left with no active transport (the caller
    should retry).

    Args:
        config: New bridge configuration with the desired transport mode.

    Returns:
        The newly connected ``AnimaTransport`` instance.

    Raises:
        RuntimeError: If another switch is already in progress.
    """
    global _transport, _current_mode

    lock = _get_lock()

    if lock.locked():
        raise RuntimeError("A transport switch is already in progress. Please wait.")

    async with lock:
        old_mode = _current_mode

        # Disconnect existing transport
        if _transport is not None:
            await _transport.disconnect()
            _transport = None
            _current_mode = None
            logger.info("Disconnected old transport: %s", old_mode)

        # Create and connect the new transport
        transport = await create_transport(config)

        transport.on_connection(lambda status: logger.info("Transport status: %s", status.value))

        await transport.connect()

        _transport = transport
        _current_mode = config.transport.mode
        logger.info(
            "Transport switched: %s -> %s",
            old_mode.value if old_mode else "none",
            _current_mode.value,
        )

        return _transport
