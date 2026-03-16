"""Shared types for the ANIMA transport abstraction layer.

Defines all data structures used across transport backends: connection
state, publish/subscribe options, service call results, action goals,
and introspection descriptors.

Copyright 2026 AIFLOW LABS LIMITED. All rights reserved.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------


class ConnectionStatus(Enum):
    """Transport connection state machine."""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"


MessageHandler = Callable[[dict[str, Any]], None]
"""Callback signature for incoming ROS2 messages (deserialized to dict)."""

ConnectionHandler = Callable[[ConnectionStatus], None]
"""Callback signature for connection status changes."""


# ---------------------------------------------------------------------------
# Introspection descriptors
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class TopicInfo:
    """Descriptor for a discovered ROS2 topic."""

    name: str
    msg_type: str


@dataclass(frozen=True, slots=True)
class ServiceInfo:
    """Descriptor for a discovered ROS2 service."""

    name: str
    srv_type: str


@dataclass(frozen=True, slots=True)
class ActionInfo:
    """Descriptor for a discovered ROS2 action server."""

    name: str
    action_type: str


# ---------------------------------------------------------------------------
# Publish
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class PublishOptions:
    """Arguments for publishing a message to a ROS2 topic."""

    topic: str
    msg_type: str
    msg: dict[str, Any]


@dataclass(frozen=True, slots=True)
class PublishResult:
    """Outcome of a publish operation."""

    success: bool
    error: str | None = None


# ---------------------------------------------------------------------------
# Subscribe
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class SubscribeOptions:
    """Arguments for subscribing to a ROS2 topic."""

    topic: str
    msg_type: str | None = None
    queue_size: int = 10


@dataclass(frozen=True, slots=True)
class SubscribeResult:
    """Outcome of a one-shot subscribe (subscribe_once)."""

    success: bool
    msg: dict[str, Any] | None = None
    error: str | None = None


@dataclass(slots=True)
class Subscription:
    """Handle to an active topic subscription.

    Call ``unsubscribe()`` to stop receiving messages and release resources.
    """

    topic: str
    _unsubscribe_fn: Callable[[], None]

    def unsubscribe(self) -> None:
        """Stop receiving messages and release the subscription."""
        self._unsubscribe_fn()


# ---------------------------------------------------------------------------
# Service call
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class ServiceCallOptions:
    """Arguments for calling a ROS2 service."""

    service: str
    srv_type: str | None = None
    args: dict[str, Any] = field(default_factory=dict)
    timeout_ms: int = 30_000


@dataclass(frozen=True, slots=True)
class ServiceCallResult:
    """Outcome of a ROS2 service call."""

    success: bool
    values: dict[str, Any] | None = None
    error: str | None = None


# ---------------------------------------------------------------------------
# Action
# ---------------------------------------------------------------------------

FeedbackHandler = Callable[[dict[str, Any]], None]
"""Callback signature for action feedback messages."""


@dataclass(slots=True)
class ActionGoalOptions:
    """Arguments for sending a goal to a ROS2 action server."""

    action: str
    action_type: str
    goal: dict[str, Any] = field(default_factory=dict)
    feedback_cb: FeedbackHandler | None = None
    timeout_s: float = 120.0


@dataclass(frozen=True, slots=True)
class ActionResult:
    """Outcome of a ROS2 action goal."""

    success: bool
    values: dict[str, Any] | None = None
    error: str | None = None
