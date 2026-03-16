"""WebSocket client for the rosbridge v2 protocol.

Copyright (c) 2026 AIFLOW LABS LIMITED / RobotFlowLabs. All rights reserved.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Callable
from typing import Any

import websockets
from websockets.asyncio.client import ClientConnection

logger = logging.getLogger(__name__)

_ACTION_FB_PREFIX = "__action_feedback__"


class PendingRequest:
    """In-flight request awaiting a matching response."""

    __slots__ = ("future", "timeout_handle")

    def __init__(
        self,
        future: asyncio.Future[dict[str, Any]],
        timeout_handle: asyncio.TimerHandle,
    ) -> None:
        self.future = future
        self.timeout_handle = timeout_handle


class RosbridgeClient:
    """WebSocket client implementing the rosbridge v2 protocol.

    Handles connection with timeout, auto-reconnect with exponential backoff
    (max attempts, capped at 30s), message routing by op type, and pending
    request tracking with per-request timeouts.
    """

    def __init__(
        self,
        url: str = "ws://localhost:9090",
        *,
        reconnect: bool = True,
        reconnect_interval_ms: int = 3000,
        max_reconnect_attempts: int = 10,
        connect_timeout_s: float = 10.0,
    ) -> None:
        self._url = url
        self._reconnect_enabled = reconnect
        self._reconnect_interval_ms = reconnect_interval_ms
        self._max_reconnect_attempts = max_reconnect_attempts
        self._connect_timeout_s = connect_timeout_s
        self._ws: ClientConnection | None = None
        self._status: str = "disconnected"
        self._intentional_close = False
        self._reconnect_attempts = 0
        self._reconnect_task: asyncio.Task[None] | None = None
        self._receive_task: asyncio.Task[None] | None = None
        self._id_counter = 0
        self._msg_handlers: dict[str, set[Callable[[dict[str, Any]], None]]] = {}
        self._conn_handlers: set[Callable[[str], None]] = set()
        self._pending: dict[str, PendingRequest] = {}

    @property
    def status(self) -> str:
        return self._status

    def next_id(self, prefix: str = "anima") -> str:
        self._id_counter += 1
        return f"{prefix}_{self._id_counter}"

    @property
    def active_topic_keys(self) -> list[str]:
        return [k for k in self._msg_handlers if not k.startswith(_ACTION_FB_PREFIX)]

    async def connect(self) -> None:
        """Open the WebSocket connection to the rosbridge server."""
        if self._status == "connected":
            return
        self._intentional_close = False
        self._set_status("connecting")
        try:
            self._ws = await asyncio.wait_for(
                websockets.connect(self._url), timeout=self._connect_timeout_s
            )
        except Exception as exc:
            self._set_status("disconnected")
            raise RuntimeError(f"Cannot connect to rosbridge at {self._url}: {exc}") from exc
        self._reconnect_attempts = 0
        self._set_status("connected")
        logger.info("Connected to rosbridge at %s", self._url)
        self._receive_task = asyncio.create_task(self._receive_loop(), name="rb_recv")

    async def disconnect(self) -> None:
        """Gracefully close the connection. Safe to call when already disconnected."""
        self._intentional_close = True
        if self._reconnect_task is not None:
            self._reconnect_task.cancel()
            self._reconnect_task = None
        self._reject_all_pending("Client disconnected")
        if self._receive_task is not None:
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass
            self._receive_task = None
        if self._ws is not None:
            try:
                await self._ws.close()
            except Exception:
                pass
            self._ws = None
        self._set_status("disconnected")

    async def send_async(self, message: dict[str, Any]) -> None:
        """Send a JSON rosbridge message asynchronously. Awaits the send."""
        if self._ws is None or self._status != "connected":
            raise RuntimeError("Not connected to rosbridge server")
        await self._ws.send(json.dumps(message))

    def send(self, message: dict[str, Any]) -> None:
        """Send a JSON rosbridge message. Fire-and-forget with error logging.

        Raises RuntimeError if not connected.
        """
        if self._ws is None or self._status != "connected":
            raise RuntimeError("Not connected to rosbridge server")
        task = asyncio.get_running_loop().create_task(self._ws.send(json.dumps(message)))
        task.add_done_callback(self._handle_send_error)

    @staticmethod
    def _handle_send_error(task: asyncio.Task[None]) -> None:
        """Log errors from fire-and-forget send tasks."""
        if task.cancelled():
            return
        exc = task.exception()
        if exc is not None:
            logger.error("WebSocket send failed: %s", exc)

    def on_message(
        self, topic: str, handler: Callable[[dict[str, Any]], None]
    ) -> Callable[[], None]:
        """Register a handler for incoming messages. Returns a removal callable."""
        handlers = self._msg_handlers.setdefault(topic, set())
        handlers.add(handler)

        def _remove() -> None:
            handlers.discard(handler)
            if not handlers:
                self._msg_handlers.pop(topic, None)

        return _remove

    def on_connection(self, handler: Callable[[str], None]) -> Callable[[], None]:
        """Register a connection status change callback."""
        self._conn_handlers.add(handler)
        return lambda: self._conn_handlers.discard(handler)

    def register_pending(
        self, msg_id: str, timeout_ms: int = 30_000
    ) -> asyncio.Future[dict[str, Any]]:
        """Create a future resolved when a response with *msg_id* arrives."""
        loop = asyncio.get_running_loop()
        future: asyncio.Future[dict[str, Any]] = loop.create_future()

        def _expire() -> None:
            p = self._pending.pop(msg_id, None)
            if p and not p.future.done():
                p.future.set_exception(TimeoutError(f"Request {msg_id} timed out ({timeout_ms}ms)"))

        handle = loop.call_later(timeout_ms / 1000.0, _expire)
        self._pending[msg_id] = PendingRequest(future=future, timeout_handle=handle)
        return future

    # -- internal ----------------------------------------------------------

    def _set_status(self, status: str) -> None:
        self._status = status
        for h in list(self._conn_handlers):
            try:
                h(status)
            except Exception:
                logger.exception("Error in connection handler")

    async def _receive_loop(self) -> None:
        assert self._ws is not None
        try:
            async for raw in self._ws:
                self._route(raw if isinstance(raw, str) else raw.decode())
        except asyncio.CancelledError:
            return
        except Exception:
            logger.debug("Receive loop ended", exc_info=True)
        self._ws = None
        self._set_status("disconnected")
        self._reject_all_pending("WebSocket connection lost")
        if not self._intentional_close and self._reconnect_enabled:
            self._schedule_reconnect()

    def _route(self, raw: str) -> None:
        try:
            msg: dict[str, Any] = json.loads(raw)
        except json.JSONDecodeError:
            return
        op = msg.get("op")
        if op == "publish":
            topic = msg.get("topic", "")
            payload = msg.get("msg", {})
            for h in list(self._msg_handlers.get(topic, ())):
                try:
                    h(payload)
                except Exception:
                    logger.exception("Handler error on %s", topic)
        elif op in ("service_response", "action_result"):
            self._resolve_pending(msg.get("id"), msg)
        elif op == "action_feedback":
            fb_id = msg.get("id")
            if fb_id:
                for h in list(self._msg_handlers.get(f"{_ACTION_FB_PREFIX}{fb_id}", ())):
                    try:
                        h(msg)
                    except Exception:
                        logger.exception("Feedback handler error")

    def _resolve_pending(self, mid: str | None, result: dict[str, Any]) -> None:
        if mid is None:
            return
        p = self._pending.pop(mid, None)
        if p and not p.future.done():
            p.timeout_handle.cancel()
            p.future.set_result(result)

    def _reject_all_pending(self, reason: str) -> None:
        for p in self._pending.values():
            p.timeout_handle.cancel()
            if not p.future.done():
                p.future.set_exception(RuntimeError(reason))
        self._pending.clear()

    def _schedule_reconnect(self) -> None:
        if self._reconnect_attempts >= self._max_reconnect_attempts:
            logger.warning("Exhausted %d reconnect attempts", self._max_reconnect_attempts)
            return
        self._reconnect_attempts += 1
        delay = min(
            (self._reconnect_interval_ms / 1000.0) * (2 ** (self._reconnect_attempts - 1)),
            30.0,
        )
        logger.info(
            "Reconnecting in %.1fs (attempt %d/%d)",
            delay,
            self._reconnect_attempts,
            self._max_reconnect_attempts,
        )
        self._reconnect_task = asyncio.get_running_loop().create_task(self._do_reconnect(delay))

    async def _do_reconnect(self, delay: float) -> None:
        await asyncio.sleep(delay)
        if self._intentional_close:
            return
        try:
            await self.connect()
            for topic in self.active_topic_keys:
                self.send({"op": "subscribe", "id": self.next_id("resub"), "topic": topic})
        except Exception:
            logger.debug("Reconnect failed", exc_info=True)
