"""Rosbridge WebSocket transport adapter (Mode B) for AnimaTransport.

Latency: 5-50ms per operation (WebSocket + JSON overhead).
Compatible with any ROS2 setup running rosbridge_suite.

Copyright (c) 2026 AIFLOW LABS LIMITED / RobotFlowLabs. All rights reserved.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from typing import Any

from anima_bridge.transport.base import AnimaTransport
from anima_bridge.transport.rosbridge.client import _ACTION_FB_PREFIX, RosbridgeClient
from anima_bridge.transport.types import (
    ActionGoalOptions,
    ActionInfo,
    ActionResult,
    ConnectionHandler,
    ConnectionStatus,
    MessageHandler,
    PublishOptions,
    PublishResult,
    ServiceCallOptions,
    ServiceCallResult,
    ServiceInfo,
    SubscribeResult,
    Subscription,
    TopicInfo,
)

logger = logging.getLogger(__name__)

_INTERNAL_TOPIC_PREFIXES = ("/rosout", "/parameter_events", "/rosbridge", "/client_count")
_INTERNAL_SVC_SUFFIXES = (
    "/describe_parameters",
    "/get_parameter_types",
    "/get_parameters",
    "/list_parameters",
    "/set_parameters",
    "/set_parameters_atomically",
)
_ACTION_FB_SUFFIX = "/_action/feedback"
_STATUS_MAP: dict[str, ConnectionStatus] = {
    "disconnected": ConnectionStatus.DISCONNECTED,
    "connecting": ConnectionStatus.CONNECTING,
    "connected": ConnectionStatus.CONNECTED,
}

# rcl_interfaces ParameterType constants
_PT_BOOL, _PT_INT, _PT_DOUBLE, _PT_STRING = 1, 2, 3, 4


def _is_internal_topic(name: str) -> bool:
    return any(name.startswith(p) for p in _INTERNAL_TOPIC_PREFIXES)


def _is_internal_service(name: str) -> bool:
    return any(name.startswith(p) for p in _INTERNAL_TOPIC_PREFIXES) or any(
        name.endswith(s) for s in _INTERNAL_SVC_SUFFIXES
    )


class RosbridgeTransport(AnimaTransport):
    """Rosbridge WebSocket transport (Mode B).

    Connects to a rosbridge_server via WebSocket and translates
    AnimaTransport calls into rosbridge v2 protocol JSON messages.
    """

    def __init__(
        self,
        url: str = "ws://localhost:9090",
        *,
        reconnect: bool = True,
        reconnect_interval_ms: int = 3000,
        max_reconnect_attempts: int = 10,
    ) -> None:
        self._client = RosbridgeClient(
            url=url,
            reconnect=reconnect,
            reconnect_interval_ms=reconnect_interval_ms,
            max_reconnect_attempts=max_reconnect_attempts,
        )
        self._advertised: set[str] = set()
        self._active_action_ids: dict[str, str] = {}

    # -- connection --------------------------------------------------------

    async def connect(self) -> None:
        await self._client.connect()

    async def disconnect(self) -> None:
        self._advertised.clear()
        self._active_action_ids.clear()
        await self._client.disconnect()

    def is_connected(self) -> bool:
        return self._client.status == "connected"

    def get_status(self) -> ConnectionStatus:
        return _STATUS_MAP.get(self._client.status, ConnectionStatus.DISCONNECTED)

    def on_connection(self, handler: ConnectionHandler) -> Callable[[], None]:
        def _bridge(s: str) -> None:
            handler(_STATUS_MAP.get(s, ConnectionStatus.DISCONNECTED))

        return self._client.on_connection(_bridge)

    # -- publish / subscribe -----------------------------------------------

    async def publish(self, options: PublishOptions) -> PublishResult:
        self._ensure_connected()
        try:
            if options.topic not in self._advertised:
                self._client.send(
                    {"op": "advertise", "topic": options.topic, "type": options.msg_type}
                )
                self._advertised.add(options.topic)
            self._client.send({"op": "publish", "topic": options.topic, "msg": options.msg})
            return PublishResult(success=True)
        except Exception as exc:
            return PublishResult(success=False, error=str(exc))

    async def subscribe_once(
        self,
        topic: str,
        msg_type: str | None = None,
        timeout_ms: int = 5000,
    ) -> SubscribeResult:
        self._ensure_connected()
        loop = asyncio.get_running_loop()
        future: asyncio.Future[dict[str, Any]] = loop.create_future()

        def _cb(data: dict[str, Any]) -> None:
            if not future.done():
                future.set_result(data)

        remove = self._client.on_message(topic, _cb)
        sub_id = self._client.next_id("sub")
        sub_msg: dict[str, Any] = {"op": "subscribe", "id": sub_id, "topic": topic}
        if msg_type:
            sub_msg["type"] = msg_type
        self._client.send(sub_msg)
        try:
            result = await asyncio.wait_for(future, timeout=timeout_ms / 1000.0)
            return SubscribeResult(success=True, msg=result)
        except TimeoutError:
            return SubscribeResult(success=False, error=f"Timeout on {topic} ({timeout_ms}ms)")
        finally:
            remove()
            try:
                self._client.send({"op": "unsubscribe", "id": sub_id, "topic": topic})
            except Exception:
                pass

    def subscribe(self, topic: str, msg_type: str | None, callback: MessageHandler) -> Subscription:
        self._ensure_connected()
        remove = self._client.on_message(topic, callback)
        sub_id = self._client.next_id("sub")
        sub_msg: dict[str, Any] = {"op": "subscribe", "id": sub_id, "topic": topic}
        if msg_type:
            sub_msg["type"] = msg_type
        self._client.send(sub_msg)

        def _unsub() -> None:
            remove()
            try:
                self._client.send({"op": "unsubscribe", "id": sub_id, "topic": topic})
            except Exception:
                pass

        return Subscription(topic=topic, _unsubscribe_fn=_unsub)

    # -- services ----------------------------------------------------------

    async def call_service(self, options: ServiceCallOptions) -> ServiceCallResult:
        self._ensure_connected()
        cid = self._client.next_id("srv")
        future = self._client.register_pending(cid, timeout_ms=options.timeout_ms)
        msg: dict[str, Any] = {
            "op": "call_service",
            "id": cid,
            "service": options.service,
            "args": options.args,
        }
        if options.srv_type:
            msg["type"] = options.srv_type
        try:
            self._client.send(msg)
            resp = await future
            ok = resp.get("result", False)
            vals = resp.get("values")
            if isinstance(vals, dict):
                return ServiceCallResult(success=bool(ok), values=vals)
            return ServiceCallResult(
                success=bool(ok), values={"result": vals} if vals is not None else None
            )
        except TimeoutError:
            return ServiceCallResult(
                success=False, error=f"Service {options.service} timed out ({options.timeout_ms}ms)"
            )
        except Exception as exc:
            return ServiceCallResult(success=False, error=str(exc))

    # -- actions -----------------------------------------------------------

    async def send_action_goal(self, options: ActionGoalOptions) -> ActionResult:
        self._ensure_connected()
        gid = self._client.next_id("goal")
        tms = int(options.timeout_s * 1000)
        fut = self._client.register_pending(gid, timeout_ms=tms)
        remove_fb: Callable[[], None] | None = None
        if options.feedback_cb:
            fb_cb = options.feedback_cb

            def _on_fb(m: dict[str, Any]) -> None:
                fb_cb(m.get("values", m.get("feedback", {})))

            remove_fb = self._client.on_message(f"{_ACTION_FB_PREFIX}{gid}", _on_fb)
        self._active_action_ids[options.action] = gid
        self._client.send(
            {
                "op": "send_action_goal",
                "id": gid,
                "action": options.action,
                "action_type": options.action_type,
                "args": options.goal,
            }
        )
        try:
            resp = await fut
            return ActionResult(
                success=bool(resp.get("result", False)),
                values=resp.get("values") if isinstance(resp.get("values"), dict) else None,
            )
        except TimeoutError:
            return ActionResult(
                success=False, error=f"Action {options.action} timed out ({options.timeout_s}s)"
            )
        except Exception as exc:
            return ActionResult(success=False, error=str(exc))
        finally:
            self._active_action_ids.pop(options.action, None)
            if remove_fb:
                remove_fb()

    async def cancel_action(self, action: str) -> None:
        gid = self._active_action_ids.pop(action, None)
        if gid is None:
            return
        try:
            self._client.send({"op": "cancel_action_goal", "id": gid, "action": action})
        except Exception:
            logger.warning("Failed to cancel action %s", action)

    # -- introspection -----------------------------------------------------

    async def list_topics(self) -> list[TopicInfo]:
        r = await self.call_service(
            ServiceCallOptions(
                service="/rosapi/topics",
                srv_type="rosapi/srv/Topics",
                timeout_ms=10_000,
            )
        )
        if not r.success or r.values is None:
            return []
        names: list[str] = r.values.get("topics", [])  # type: ignore[assignment]
        types: list[str] = r.values.get("types", [])  # type: ignore[assignment]
        return [
            TopicInfo(name=n, msg_type=types[i] if i < len(types) else "")
            for i, n in enumerate(names)
            if not _is_internal_topic(n)
        ]

    async def list_services(self) -> list[ServiceInfo]:
        r = await self.call_service(
            ServiceCallOptions(
                service="/rosapi/services",
                srv_type="rosapi/srv/Services",
                timeout_ms=10_000,
            )
        )
        if not r.success or r.values is None:
            return []
        names: list[str] = r.values.get("services", [])  # type: ignore[assignment]
        types: list[str] = r.values.get("types", [])  # type: ignore[assignment]
        return [
            ServiceInfo(name=n, srv_type=types[i] if i < len(types) else "")
            for i, n in enumerate(names)
            if not _is_internal_service(n)
        ]

    async def list_actions(self) -> list[ActionInfo]:
        topics = await self.list_topics()
        actions: list[ActionInfo] = []
        for t in topics:
            if t.name.endswith(_ACTION_FB_SUFFIX):
                atype = t.msg_type
                if atype.endswith("_FeedbackMessage"):
                    atype = atype[: -len("_FeedbackMessage")]
                actions.append(
                    ActionInfo(name=t.name[: -len(_ACTION_FB_SUFFIX)], action_type=atype)
                )
        return actions

    # -- parameters --------------------------------------------------------

    async def get_parameters(self, node: str, names: list[str]) -> dict[str, object]:
        r = await self.call_service(
            ServiceCallOptions(
                service=f"{node}/get_parameters",
                srv_type="rcl_interfaces/srv/GetParameters",
                args={"names": names},
                timeout_ms=10_000,
            )
        )
        if not r.success or r.values is None:
            raise RuntimeError(f"Failed to get parameters from {node}: {r.error}")
        raw: list[dict[str, Any]] = r.values.get("values", [])  # type: ignore[assignment]
        return {n: _extract_param(v) for n, v in zip(names, raw)}

    async def set_parameters(self, node: str, params: dict[str, object]) -> bool:
        plist = [_build_param(n, v) for n, v in params.items()]
        r = await self.call_service(
            ServiceCallOptions(
                service=f"{node}/set_parameters",
                srv_type="rcl_interfaces/srv/SetParameters",
                args={"parameters": plist},
                timeout_ms=10_000,
            )
        )
        if not r.success or r.values is None:
            return False
        results: list[dict[str, Any]] = r.values.get("results", [])  # type: ignore[assignment]
        return all(x.get("successful", False) for x in results)

    # -- helpers -----------------------------------------------------------

    def _ensure_connected(self) -> None:
        if not self.is_connected():
            raise RuntimeError("RosbridgeTransport is not connected. Call connect() first.")


def _extract_param(val: dict[str, Any] | Any) -> object:
    if not isinstance(val, dict):
        return val
    t = val.get("type", 0)
    if t == _PT_BOOL:
        return val.get("bool_value", False)
    if t == _PT_INT:
        return val.get("integer_value", 0)
    if t == _PT_DOUBLE:
        return val.get("double_value", 0.0)
    if t == _PT_STRING:
        return val.get("string_value", "")
    return None


def _build_param(name: str, value: object) -> dict[str, Any]:
    v: dict[str, Any]
    if isinstance(value, bool):
        v = {"type": _PT_BOOL, "bool_value": value}
    elif isinstance(value, int):
        v = {"type": _PT_INT, "integer_value": value}
    elif isinstance(value, float):
        v = {"type": _PT_DOUBLE, "double_value": value}
    elif isinstance(value, str):
        v = {"type": _PT_STRING, "string_value": value}
    else:
        raise TypeError(f"Unsupported parameter type for {name}: {type(value)}")
    return {"name": name, "value": v}
