"""Abstract base class for ANIMA transport backends.

Every transport backend (direct DDS, rosbridge, Zenoh) implements this
interface so that higher-level code (tools, commands, safety layer) works
identically regardless of the underlying communication mechanism.

Copyright 2026 AIFLOW LABS LIMITED. All rights reserved.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable

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


class AnimaTransport(ABC):
    """Unified async interface for ROS2 communication.

    Subclasses must implement every abstract method. The bridge guarantees
    that ``connect()`` is called before any publish/subscribe/service/action
    methods, and ``disconnect()`` is called during shutdown.
    """

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    @abstractmethod
    async def connect(self) -> None:
        """Establish the transport connection.

        Raises:
            RuntimeError: If the connection cannot be established.
        """

    @abstractmethod
    async def disconnect(self) -> None:
        """Gracefully tear down the transport connection.

        Must be safe to call even if already disconnected.
        """

    @abstractmethod
    def is_connected(self) -> bool:
        """Return ``True`` if the transport is currently connected."""

    @abstractmethod
    def get_status(self) -> ConnectionStatus:
        """Return the current connection status."""

    @abstractmethod
    def on_connection(self, handler: ConnectionHandler) -> Callable[[], None]:
        """Register a callback for connection status changes.

        Args:
            handler: Called with the new ``ConnectionStatus`` on every transition.

        Returns:
            A zero-argument callable that removes the handler when called.
        """

    # ------------------------------------------------------------------
    # Publish / Subscribe
    # ------------------------------------------------------------------

    @abstractmethod
    async def publish(self, options: PublishOptions) -> PublishResult:
        """Publish a message to a ROS2 topic.

        Args:
            options: Topic name, message type, and payload.

        Returns:
            A ``PublishResult`` indicating success or failure.
        """

    @abstractmethod
    async def subscribe_once(
        self,
        topic: str,
        msg_type: str | None = None,
        timeout_ms: int = 5000,
    ) -> SubscribeResult:
        """Wait for a single message on a topic, then unsubscribe.

        Args:
            topic: The ROS2 topic to listen on.
            msg_type: Message type string (e.g. ``"std_msgs/msg/String"``).
                      If ``None``, the transport should attempt to resolve it.
            timeout_ms: Maximum time to wait for a message.

        Returns:
            A ``SubscribeResult`` with the received message or an error.
        """

    @abstractmethod
    def subscribe(
        self,
        topic: str,
        msg_type: str | None,
        callback: MessageHandler,
    ) -> Subscription:
        """Subscribe to a ROS2 topic and deliver messages via *callback*.

        Args:
            topic: The ROS2 topic to subscribe to.
            msg_type: Message type string. If ``None``, the transport should
                      attempt to resolve it from the ROS graph.
            callback: Invoked with each incoming message (as a dict).

        Returns:
            A ``Subscription`` handle. Call ``unsubscribe()`` to stop.
        """

    # ------------------------------------------------------------------
    # Services
    # ------------------------------------------------------------------

    @abstractmethod
    async def call_service(self, options: ServiceCallOptions) -> ServiceCallResult:
        """Call a ROS2 service and wait for the response.

        Args:
            options: Service name, type, arguments, and timeout.

        Returns:
            A ``ServiceCallResult`` with the response values.
        """

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    @abstractmethod
    async def send_action_goal(self, options: ActionGoalOptions) -> ActionResult:
        """Send a goal to a ROS2 action server and wait for the result.

        Args:
            options: Action name, type, goal dict, feedback callback, timeout.

        Returns:
            An ``ActionResult`` with the final result values.
        """

    @abstractmethod
    async def cancel_action(self, action: str) -> None:
        """Cancel an in-progress action goal.

        Args:
            action: The action name whose goal should be cancelled.
        """

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    @abstractmethod
    async def list_topics(self) -> list[TopicInfo]:
        """List all discovered ROS2 topics (filtering internal ones)."""

    @abstractmethod
    async def list_services(self) -> list[ServiceInfo]:
        """List all discovered ROS2 services (filtering internal ones)."""

    @abstractmethod
    async def list_actions(self) -> list[ActionInfo]:
        """List all discovered ROS2 action servers."""

    # ------------------------------------------------------------------
    # Parameters
    # ------------------------------------------------------------------

    @abstractmethod
    async def get_parameters(self, node: str, names: list[str]) -> dict[str, object]:
        """Read parameters from a remote ROS2 node.

        Args:
            node: Fully-qualified node name (e.g. ``"/my_robot/controller"``).
            names: List of parameter names to read.

        Returns:
            A dict mapping parameter name to its value.
        """

    @abstractmethod
    async def set_parameters(self, node: str, params: dict[str, object]) -> bool:
        """Set parameters on a remote ROS2 node.

        Args:
            node: Fully-qualified node name.
            params: Dict mapping parameter name to desired value.

        Returns:
            ``True`` if all parameters were set successfully.
        """
