"""Direct DDS transport — rclpy-based AnimaTransport implementation.

Creates an ``anima_bridge`` ROS2 node, spins it in a daemon thread, and
bridges rclpy futures to asyncio via ``call_soon_threadsafe``.

Copyright (c) 2026 AIFLOW LABS LIMITED / RobotFlowLabs. All rights reserved.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from collections.abc import Callable
from typing import Any

from anima_bridge.transport.base import AnimaTransport
from anima_bridge.transport.entity_cache import (
    _ACTION_FEEDBACK_SUFFIX,
    EntityCache,
    bridge_rclpy_future,
    build_parameter_msg,
    dict_to_msg,
    extract_parameter_value,
    is_internal_service,
    is_internal_topic,
    load_msg_class,
    msg_to_dict,
)
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


class DirectDdsTransport(AnimaTransport):
    """Transport backend using rclpy for direct DDS communication.

    This transport creates a ROS2 node named ``anima_bridge`` and spins it
    in a background thread. All async methods bridge back to the caller's
    event loop via ``call_soon_threadsafe``.
    """

    def __init__(self, domain_id: int = 0) -> None:
        self._domain_id = domain_id
        self._status = ConnectionStatus.DISCONNECTED
        self._connection_handlers: set[ConnectionHandler] = set()

        # rclpy state (populated on connect)
        self._node: Any | None = None
        self._cache: EntityCache | None = None
        self._spin_thread: threading.Thread | None = None
        self._spin_stop = threading.Event()

        # Active action goals: keyed by action name
        self._active_goals: dict[str, Any] = {}

    # -- Connection lifecycle ----------------------------------------------

    async def connect(self) -> None:
        """Create the ROS2 node and start the spin thread."""
        if self._status == ConnectionStatus.CONNECTED:
            return

        self._set_status(ConnectionStatus.CONNECTING)

        try:
            import rclpy
            from rclpy.executors import SingleThreadedExecutor

            if not rclpy.ok():
                rclpy.init(domain_id=self._domain_id)
                logger.info("rclpy initialized (domain_id=%d)", self._domain_id)
            else:
                logger.info("rclpy already initialized, reusing context")

            self._node = rclpy.create_node("anima_bridge")
            self._cache = EntityCache(self._node)
            logger.info("Created ROS2 node: anima_bridge")

            self._spin_stop.clear()
            executor = SingleThreadedExecutor()
            executor.add_node(self._node)

            def _spin_worker() -> None:
                while not self._spin_stop.is_set():
                    executor.spin_once(timeout_sec=0.05)
                executor.shutdown()

            self._spin_thread = threading.Thread(
                target=_spin_worker,
                name="anima_bridge_spin",
                daemon=True,
            )
            self._spin_thread.start()

            self._set_status(ConnectionStatus.CONNECTED)

        except Exception:
            self._set_status(ConnectionStatus.DISCONNECTED)
            raise

    async def disconnect(self) -> None:
        """Stop spinning, destroy all entities, and shut down the node."""
        if self._status == ConnectionStatus.DISCONNECTED:
            return

        for action_name in list(self._active_goals):
            try:
                await self.cancel_action(action_name)
            except Exception:
                pass
        self._active_goals.clear()

        if self._spin_thread is not None:
            self._spin_stop.set()
            self._spin_thread.join(timeout=5.0)
            self._spin_thread = None

        if self._cache is not None:
            self._cache.destroy_all()
            self._cache = None

        if self._node is not None:
            self._node.destroy_node()
            self._node = None
            logger.info("ROS2 node destroyed")

        self._set_status(ConnectionStatus.DISCONNECTED)

    def is_connected(self) -> bool:
        """Return True if the transport is connected."""
        return self._status == ConnectionStatus.CONNECTED

    def get_status(self) -> ConnectionStatus:
        """Return the current connection status."""
        return self._status

    def on_connection(self, handler: ConnectionHandler) -> Callable[[], None]:
        """Register a connection status change handler."""
        self._connection_handlers.add(handler)

        def _remove() -> None:
            self._connection_handlers.discard(handler)

        return _remove

    # -- Publish / Subscribe ------------------------------------------------

    async def publish(self, options: PublishOptions) -> PublishResult:
        """Publish a message to a ROS2 topic."""
        self._ensure_connected()
        try:
            pub = self._cache.get_publisher(options.topic, options.msg_type)
            msg_class = load_msg_class(options.msg_type)
            ros_msg = dict_to_msg(msg_class, options.msg)
            pub.publish(ros_msg)
            return PublishResult(success=True)
        except Exception as exc:
            return PublishResult(success=False, error=str(exc))

    async def subscribe_once(
        self,
        topic: str,
        msg_type: str | None = None,
        timeout_ms: int = 5000,
    ) -> SubscribeResult:
        """Wait for a single message on a topic, then unsubscribe."""
        self._ensure_connected()

        resolved_type = msg_type or self._cache.resolve_topic_type(topic)
        if resolved_type is None:
            return SubscribeResult(
                success=False,
                error=f"Cannot resolve type for topic {topic}. Provide msg_type explicitly.",
            )

        loop = asyncio.get_running_loop()
        future: asyncio.Future[dict[str, Any]] = loop.create_future()
        msg_class = load_msg_class(resolved_type)

        sub: Any = None

        def _on_message(ros_msg: Any) -> None:
            if not future.done():
                data = msg_to_dict(ros_msg)
                loop.call_soon_threadsafe(future.set_result, data)

        sub = self._node.create_subscription(msg_class, topic, _on_message, 1)

        try:
            result_msg = await asyncio.wait_for(future, timeout=timeout_ms / 1000.0)
            return SubscribeResult(success=True, msg=result_msg)
        except TimeoutError:
            return SubscribeResult(
                success=False,
                error=f"Timed out waiting for message on {topic} ({timeout_ms}ms).",
            )
        finally:
            if sub is not None:
                self._node.destroy_subscription(sub)

    def subscribe(
        self,
        topic: str,
        msg_type: str | None,
        callback: MessageHandler,
    ) -> Subscription:
        """Subscribe to a ROS2 topic with a persistent callback."""
        self._ensure_connected()

        resolved_type = msg_type or self._cache.resolve_topic_type(topic)
        if resolved_type is None:
            raise ValueError(f"Cannot resolve type for topic {topic}. Provide msg_type explicitly.")

        msg_class = load_msg_class(resolved_type)

        def _on_message(ros_msg: Any) -> None:
            try:
                data = msg_to_dict(ros_msg)
                callback(data)
            except Exception:
                logger.exception("Error in subscriber callback for %s", topic)

        sub = self._node.create_subscription(msg_class, topic, _on_message, 10)

        sub_id = f"{topic}:{id(sub)}"
        self._cache.track_subscriber(sub_id, sub)

        def _unsubscribe() -> None:
            removed = self._cache.remove_subscriber(sub_id)
            if removed is not None and self._node is not None:
                self._node.destroy_subscription(removed)

        return Subscription(topic=topic, _unsubscribe_fn=_unsubscribe)

    # -- Services -----------------------------------------------------------

    async def call_service(self, options: ServiceCallOptions) -> ServiceCallResult:
        """Call a ROS2 service and wait for the response."""
        self._ensure_connected()

        resolved_type = options.srv_type or self._cache.resolve_service_type(options.service)
        if resolved_type is None:
            return ServiceCallResult(
                success=False,
                error=f"Cannot resolve type for service {options.service}.",
            )

        try:
            client = self._cache.get_service_client(options.service, resolved_type)

            loop = asyncio.get_running_loop()
            ready = await loop.run_in_executor(
                None, lambda: client.wait_for_service(timeout_sec=5.0)
            )
            if not ready:
                return ServiceCallResult(
                    success=False,
                    error=f"Service {options.service} not available after 5 seconds.",
                )

            srv_class = load_msg_class(resolved_type)
            request = dict_to_msg(srv_class.Request, options.args)

            rclpy_future = client.call_async(request)

            response = await asyncio.wait_for(
                bridge_rclpy_future(rclpy_future, loop),
                timeout=options.timeout_ms / 1000.0,
            )
            return ServiceCallResult(success=True, values=msg_to_dict(response))

        except TimeoutError:
            return ServiceCallResult(
                success=False,
                error=f"Service call to {options.service} timed out ({options.timeout_ms}ms).",
            )
        except Exception as exc:
            return ServiceCallResult(success=False, error=str(exc))

    # -- Actions ------------------------------------------------------------

    async def send_action_goal(self, options: ActionGoalOptions) -> ActionResult:
        """Send a goal to a ROS2 action server and wait for the result."""
        self._ensure_connected()

        try:
            from rclpy.action import ActionClient as RclpyActionClient

            action_class = load_msg_class(options.action_type)
            action_client = RclpyActionClient(self._node, action_class, options.action)

            loop = asyncio.get_running_loop()
            server_ready = await loop.run_in_executor(
                None, lambda: action_client.wait_for_server(timeout_sec=5.0)
            )
            if not server_ready:
                action_client.destroy()
                return ActionResult(
                    success=False,
                    error=f"Action server {options.action} not available after 5 seconds.",
                )

            goal_msg = dict_to_msg(action_class.Goal, options.goal)

            send_goal_future = action_client.send_goal_async(
                goal_msg,
                feedback_callback=(
                    (lambda fb: options.feedback_cb(msg_to_dict(fb.feedback)))
                    if options.feedback_cb
                    else None
                ),
            )

            goal_handle = await asyncio.wait_for(
                bridge_rclpy_future(send_goal_future, loop), timeout=10.0
            )

            if not goal_handle.accepted:
                action_client.destroy()
                return ActionResult(success=False, error="Goal was rejected by action server.")

            self._active_goals[options.action] = goal_handle

            get_result_future = goal_handle.get_result_async()
            result_response = await asyncio.wait_for(
                bridge_rclpy_future(get_result_future, loop), timeout=options.timeout_s
            )

            self._active_goals.pop(options.action, None)
            action_client.destroy()

            return ActionResult(
                success=True,
                values=msg_to_dict(result_response.result),
            )

        except TimeoutError:
            self._active_goals.pop(options.action, None)
            return ActionResult(
                success=False,
                error=f"Action {options.action} timed out after {options.timeout_s}s.",
            )
        except Exception as exc:
            self._active_goals.pop(options.action, None)
            return ActionResult(success=False, error=str(exc))

    async def cancel_action(self, action: str) -> None:
        """Cancel an in-progress action goal."""
        goal_handle = self._active_goals.pop(action, None)
        if goal_handle is not None:
            try:
                goal_handle.cancel_goal_async()
            except Exception:
                logger.warning("Failed to cancel action goal: %s", action)

    # -- Introspection ------------------------------------------------------

    async def list_topics(self) -> list[TopicInfo]:
        """List all non-internal ROS2 topics."""
        self._ensure_connected()
        names_and_types = self._node.get_topic_names_and_types()
        return [
            TopicInfo(name=name, msg_type=types[0] if types else "")
            for name, types in names_and_types
            if not is_internal_topic(name)
        ]

    async def list_services(self) -> list[ServiceInfo]:
        """List all non-internal ROS2 services."""
        self._ensure_connected()
        names_and_types = self._node.get_service_names_and_types()
        return [
            ServiceInfo(name=name, srv_type=types[0] if types else "")
            for name, types in names_and_types
            if not is_internal_service(name)
        ]

    async def list_actions(self) -> list[ActionInfo]:
        """Discover action servers via the ``_action/feedback`` topic heuristic."""
        topics = await self.list_topics()
        actions: list[ActionInfo] = []
        for topic in topics:
            if topic.name.endswith(_ACTION_FEEDBACK_SUFFIX):
                action_name = topic.name[: -len(_ACTION_FEEDBACK_SUFFIX)]
                action_type = topic.msg_type
                if action_type.endswith("_FeedbackMessage"):
                    action_type = action_type[: -len("_FeedbackMessage")]
                actions.append(ActionInfo(name=action_name, action_type=action_type))
        return actions

    # -- Parameters ---------------------------------------------------------

    async def get_parameters(self, node: str, names: list[str]) -> dict[str, object]:
        """Read parameters from a remote ROS2 node via the get_parameters service."""
        self._ensure_connected()

        from rcl_interfaces.srv import GetParameters

        service_name = f"{node}/get_parameters"
        client = self._node.create_client(GetParameters, service_name)

        try:
            loop = asyncio.get_running_loop()
            ready = await loop.run_in_executor(
                None, lambda: client.wait_for_service(timeout_sec=5.0)
            )
            if not ready:
                raise RuntimeError(f"Parameter service {service_name} not available.")

            request = GetParameters.Request()
            request.names = names
            rclpy_future = client.call_async(request)
            response = await asyncio.wait_for(bridge_rclpy_future(rclpy_future, loop), timeout=10.0)

            return {
                name: extract_parameter_value(value) for name, value in zip(names, response.values)
            }
        finally:
            self._node.destroy_client(client)

    async def set_parameters(self, node: str, params: dict[str, object]) -> bool:
        """Set parameters on a remote ROS2 node via the set_parameters service."""
        self._ensure_connected()

        from rcl_interfaces.srv import SetParameters

        service_name = f"{node}/set_parameters"
        client = self._node.create_client(SetParameters, service_name)

        try:
            loop = asyncio.get_running_loop()
            ready = await loop.run_in_executor(
                None, lambda: client.wait_for_service(timeout_sec=5.0)
            )
            if not ready:
                raise RuntimeError(f"Parameter service {service_name} not available.")

            request = SetParameters.Request()
            for name, value in params.items():
                request.parameters.append(build_parameter_msg(name, value))
            rclpy_future = client.call_async(request)
            response = await asyncio.wait_for(bridge_rclpy_future(rclpy_future, loop), timeout=10.0)
            return all(r.successful for r in response.results)
        finally:
            self._node.destroy_client(client)

    # -- Private helpers ----------------------------------------------------

    def _set_status(self, status: ConnectionStatus) -> None:
        """Update connection status and notify all handlers."""
        self._status = status
        for handler in self._connection_handlers:
            try:
                handler(status)
            except Exception:
                logger.exception("Error in connection handler")

    def _ensure_connected(self) -> None:
        """Raise if the transport is not connected."""
        if self._status != ConnectionStatus.CONNECTED or self._node is None:
            raise RuntimeError("DirectDdsTransport is not connected. Call connect() first.")
