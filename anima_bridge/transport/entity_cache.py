"""ROS2 entity caching and message conversion utilities.

Provides thread-safe caches for rclpy publishers, subscribers, and service
clients, plus helpers for dynamic message class loading, dict ↔ rclpy
message conversion, and rclpy-to-asyncio future bridging.

Copyright (c) 2026 AIFLOW LABS LIMITED / RobotFlowLabs. All rights reserved.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from importlib import import_module
from typing import Any

from anima_bridge.transport.types import ACTION_FEEDBACK_SUFFIX

logger = logging.getLogger(__name__)

# Re-export for backward compatibility (direct_dds.py imports this name).
_ACTION_FEEDBACK_SUFFIX = ACTION_FEEDBACK_SUFFIX

# Topics and services that are ROS2 infrastructure -- not user-facing.
_INTERNAL_TOPIC_PREFIXES: tuple[str, ...] = (
    "/rosout",
    "/parameter_events",
    "/anima/internal",
)

_INTERNAL_SERVICE_SUFFIXES: tuple[str, ...] = (
    "/describe_parameters",
    "/get_parameter_types",
    "/get_parameters",
    "/list_parameters",
    "/set_parameters",
    "/set_parameters_atomically",
)


# ---------------------------------------------------------------------------
# Filtering helpers
# ---------------------------------------------------------------------------


def is_internal_topic(name: str) -> bool:
    """Return True if *name* is a ROS2 infrastructure topic."""
    return any(name.startswith(p) for p in _INTERNAL_TOPIC_PREFIXES)


def is_internal_service(name: str) -> bool:
    """Return True if *name* is a ROS2 infrastructure service."""
    if any(name.startswith(p) for p in _INTERNAL_TOPIC_PREFIXES):
        return True
    return any(name.endswith(s) for s in _INTERNAL_SERVICE_SUFFIXES)


# ---------------------------------------------------------------------------
# Message class loading
# ---------------------------------------------------------------------------


def load_msg_class(type_str: str) -> Any:
    """Dynamically load a ROS2 message/service/action class.

    Args:
        type_str: Fully qualified type such as ``"std_msgs/msg/String"``
                  or ``"std_srvs/srv/Trigger"``.

    Returns:
        The Python class for the given type.

    Raises:
        ImportError: If the package or type cannot be found.
    """
    parts = type_str.replace("/", ".").rsplit(".", 1)
    if len(parts) != 2:
        raise ImportError(
            f"Invalid ROS2 type format: {type_str!r}. "
            "Expected 'package/kind/TypeName' (e.g. 'std_msgs/msg/String')."
        )
    module_path, class_name = parts
    mod = import_module(module_path)
    return getattr(mod, class_name)


# ---------------------------------------------------------------------------
# Message ↔ dict conversion
# ---------------------------------------------------------------------------


def msg_to_dict(msg: Any) -> dict[str, Any]:
    """Convert an rclpy message instance to a plain dict.

    Uses ``rosidl_runtime_py.convert.message_to_ordereddict`` if available,
    otherwise falls back to iterating ``get_fields_and_field_types()``.
    """
    try:
        from rosidl_runtime_py.convert import message_to_ordereddict

        return dict(message_to_ordereddict(msg))
    except ImportError:
        pass

    result: dict[str, Any] = {}
    for field_name in msg.get_fields_and_field_types():
        value = getattr(msg, field_name)
        if hasattr(value, "get_fields_and_field_types"):
            result[field_name] = msg_to_dict(value)
        else:
            result[field_name] = value
    return result


def dict_to_msg(msg_class: Any, data: dict[str, Any]) -> Any:
    """Populate an rclpy message instance from a plain dict.

    Uses ``rosidl_runtime_py.set_message.set_message_fields`` if available,
    otherwise sets attributes directly.
    """
    msg = msg_class()
    try:
        from rosidl_runtime_py.set_message import set_message_fields

        set_message_fields(msg, data)
    except ImportError:
        for key, value in data.items():
            setattr(msg, key, value)
    return msg


# ---------------------------------------------------------------------------
# Async bridge
# ---------------------------------------------------------------------------


def bridge_rclpy_future(rclpy_future: Any, loop: asyncio.AbstractEventLoop) -> asyncio.Future[Any]:
    """Bridge an rclpy future to an asyncio future via ``call_soon_threadsafe``.

    The returned asyncio future resolves (or raises) when the rclpy future
    completes on the spin thread.
    """
    asyncio_future: asyncio.Future[Any] = loop.create_future()

    def _on_done(fut: Any) -> None:
        try:
            result = fut.result()
            loop.call_soon_threadsafe(asyncio_future.set_result, result)
        except Exception as exc:
            loop.call_soon_threadsafe(asyncio_future.set_exception, exc)

    rclpy_future.add_done_callback(_on_done)
    return asyncio_future


# ---------------------------------------------------------------------------
# Parameter value helpers
# ---------------------------------------------------------------------------

# rcl_interfaces ParameterValue type constants
_PARAM_BOOL = 1
_PARAM_INTEGER = 2
_PARAM_DOUBLE = 3
_PARAM_STRING = 4


def extract_parameter_value(param_value: Any) -> object:
    """Extract a Python value from an rcl_interfaces ParameterValue."""
    if param_value.type == _PARAM_BOOL:
        return param_value.bool_value
    if param_value.type == _PARAM_INTEGER:
        return param_value.integer_value
    if param_value.type == _PARAM_DOUBLE:
        return param_value.double_value
    if param_value.type == _PARAM_STRING:
        return param_value.string_value
    return None


def build_parameter_msg(name: str, value: object) -> Any:
    """Build an rcl_interfaces Parameter message from a Python name/value pair.

    Raises:
        TypeError: If *value* is not bool, int, float, or str.
    """
    from rcl_interfaces.msg import Parameter, ParameterType, ParameterValue

    param = Parameter()
    param.name = name
    pv = ParameterValue()
    if isinstance(value, bool):
        pv.type = ParameterType.PARAMETER_BOOL
        pv.bool_value = value
    elif isinstance(value, int):
        pv.type = ParameterType.PARAMETER_INTEGER
        pv.integer_value = value
    elif isinstance(value, float):
        pv.type = ParameterType.PARAMETER_DOUBLE
        pv.double_value = value
    elif isinstance(value, str):
        pv.type = ParameterType.PARAMETER_STRING
        pv.string_value = value
    else:
        raise TypeError(f"Unsupported parameter type for {name}: {type(value)}")
    param.value = pv
    return param


# ---------------------------------------------------------------------------
# Entity cache
# ---------------------------------------------------------------------------


class EntityCache:
    """Thread-safe cache for rclpy publishers, subscribers, and service clients.

    All ``get_*`` methods lazily create entities on first access and return
    the cached instance on subsequent calls. The cache is tied to a single
    rclpy node whose lifetime is managed externally.

    Args:
        node: The rclpy node used to create publishers, subscribers, and clients.
    """

    def __init__(self, node: Any) -> None:
        self._node = node
        self._lock = threading.Lock()

        self._publishers: dict[tuple[str, str], Any] = {}
        self._subscribers: dict[str, Any] = {}
        self._service_clients: dict[tuple[str, str], Any] = {}

    # -- Publishers --------------------------------------------------------

    def get_publisher(self, topic: str, msg_type: str) -> Any:
        """Get or create a cached publisher for *topic* with *msg_type*."""
        key = (topic, msg_type)
        with self._lock:
            if key not in self._publishers:
                msg_class = load_msg_class(msg_type)
                self._publishers[key] = self._node.create_publisher(msg_class, topic, 10)
                logger.debug("Created publisher: %s [%s]", topic, msg_type)
            return self._publishers[key]

    # -- Subscribers -------------------------------------------------------

    def track_subscriber(self, sub_id: str, sub: Any) -> None:
        """Register a subscriber for later cleanup."""
        with self._lock:
            self._subscribers[sub_id] = sub

    def remove_subscriber(self, sub_id: str) -> Any | None:
        """Remove and return a tracked subscriber, or None if not found."""
        with self._lock:
            return self._subscribers.pop(sub_id, None)

    # -- Service clients ---------------------------------------------------

    def get_service_client(self, service: str, srv_type: str) -> Any:
        """Get or create a cached service client for *service* with *srv_type*."""
        key = (service, srv_type)
        with self._lock:
            if key not in self._service_clients:
                srv_class = load_msg_class(srv_type)
                self._service_clients[key] = self._node.create_client(srv_class, service)
                logger.debug("Created service client: %s [%s]", service, srv_type)
            return self._service_clients[key]

    # -- Graph resolution --------------------------------------------------

    def resolve_topic_type(self, topic: str) -> str | None:
        """Resolve a topic's type from the ROS2 graph."""
        for name, types in self._node.get_topic_names_and_types():
            if name == topic and types:
                return types[0]
        return None

    def resolve_service_type(self, service: str) -> str | None:
        """Resolve a service's type from the ROS2 graph."""
        for name, types in self._node.get_service_names_and_types():
            if name == service and types:
                return types[0]
        return None

    # -- Cleanup -----------------------------------------------------------

    def destroy_all(self) -> None:
        """Destroy all cached publishers, subscribers, and service clients."""
        with self._lock:
            for pub in self._publishers.values():
                try:
                    self._node.destroy_publisher(pub)
                except Exception:
                    pass
            self._publishers.clear()

            for sub in self._subscribers.values():
                try:
                    self._node.destroy_subscription(sub)
                except Exception:
                    pass
            self._subscribers.clear()

            for client in self._service_clients.values():
                try:
                    self._node.destroy_client(client)
                except Exception:
                    pass
            self._service_clients.clear()

        logger.debug("All cached ROS2 entities destroyed")
