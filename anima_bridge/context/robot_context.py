"""Robot context builder for AI agent system prompt injection.

Discovers live robot capabilities (topics, services, actions) from the
active transport and formats them as a markdown block suitable for
prepending to an LLM system prompt. Results are cached with a
configurable TTL and automatically invalidated on transport reconnect.

Copyright 2026 AIFLOW LABS LIMITED. All rights reserved.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

from anima_bridge.config import AnimaBridgeConfig
from anima_bridge.transport.types import ActionInfo, ServiceInfo, TopicInfo

logger = logging.getLogger(__name__)

# Topics that should never appear in agent context (ROS2 internals).
_INTERNAL_PREFIXES = (
    "/rosout",
    "/parameter_events",
    "/anima/internal",
)


@dataclass
class _CapabilityCache:
    """Timestamped snapshot of discovered capabilities."""

    topics: list[TopicInfo] = field(default_factory=list)
    services: list[ServiceInfo] = field(default_factory=list)
    actions: list[ActionInfo] = field(default_factory=list)
    timestamp: float = 0.0


class RobotContextBuilder:
    """Discovers robot capabilities and builds context for the AI agent.

    Features:
        - Queries the active transport for topics, services, and actions.
        - Caches results with a configurable TTL (default 60 s).
        - Formats capabilities as markdown for injection into the agent
          system prompt.
        - Falls back to sensible defaults when discovery fails.
        - Cache is invalidated on transport reconnect.
    """

    def __init__(
        self,
        config: AnimaBridgeConfig,
        cache_ttl_seconds: float = 60.0,
    ) -> None:
        self._config = config
        self._cache_ttl = cache_ttl_seconds
        self._cache: _CapabilityCache | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def build_context(self) -> str:
        """Build the full markdown context string for the agent.

        Returns:
            A markdown-formatted string describing the robot and its
            capabilities, ready for system-prompt injection.
        """
        capabilities = await self.discover_capabilities()
        topics = capabilities["topics"]
        services = capabilities["services"]
        actions = capabilities["actions"]

        if topics or services or actions:
            return self._format_capabilities(topics, services, actions)

        return self._build_fallback_context()

    async def discover_capabilities(self) -> dict[str, Any]:
        """Discover topics, services, and actions from the transport.

        Results are cached for ``cache_ttl_seconds``. If discovery fails
        the method returns empty lists rather than raising.

        Returns:
            A dict with keys ``topics``, ``services``, ``actions``.
        """
        if self._cache is not None:
            age = time.monotonic() - self._cache.timestamp
            if age < self._cache_ttl:
                return self._cache_as_dict()

        try:
            from anima_bridge.transport_manager import get_transport

            transport = get_transport()

            topics, services, actions = await _gather(
                transport.list_topics(),
                transport.list_services(),
                transport.list_actions(),
            )

            namespace = self._config.robot.namespace
            topics = self._filter_topics(topics, namespace)
            services = self._filter_by_namespace(services, namespace)
            actions = self._filter_by_namespace(actions, namespace)

            self._cache = _CapabilityCache(
                topics=topics,
                services=services,
                actions=actions,
                timestamp=time.monotonic(),
            )

            logger.info(
                "Discovered %d topics, %d services, %d actions",
                len(topics),
                len(services),
                len(actions),
            )
        except Exception as exc:
            logger.warning("Capability discovery failed, using defaults: %s", exc)
            self._cache = _CapabilityCache(timestamp=0.0)

        return self._cache_as_dict()

    def invalidate_cache(self) -> None:
        """Clear cached capabilities (call on transport reconnect)."""
        self._cache = None
        logger.info("Robot context cache invalidated")

    # ------------------------------------------------------------------
    # Formatting
    # ------------------------------------------------------------------

    def _format_capabilities(
        self,
        topics: list[TopicInfo],
        services: list[ServiceInfo],
        actions: list[ActionInfo],
    ) -> str:
        """Format discovered capabilities as a markdown block."""
        name = self._config.robot.name
        safety = self._config.safety
        ws = safety.workspace_limits

        lines: list[str] = [
            f"## Robot: {name}",
            "",
            (
                f'You are connected to a ROS2 robot named "{name}". '
                "You can control it using the ros2_* tools."
            ),
            "",
        ]

        if topics:
            lines.append("### Available Topics")
            for t in topics:
                lines.append(f"- `{t.name}` ({t.msg_type})")
            lines.append("")

        if services:
            lines.append("### Available Services")
            for s in services:
                lines.append(f"- `{s.name}` ({s.srv_type})")
            lines.append("")

        if actions:
            lines.append("### Available Actions")
            for a in actions:
                lines.append(f"- `{a.name}` ({a.action_type})")
            lines.append("")

        lines.extend(
            [
                "### Safety Limits",
                f"- Maximum linear velocity: {safety.max_linear_velocity} m/s",
                f"- Maximum angular velocity: {safety.max_angular_velocity} rad/s",
                (
                    f"- Workspace bounds: "
                    f"x[{ws.x_min}, {ws.x_max}], "
                    f"y[{ws.y_min}, {ws.y_max}], "
                    f"z[{ws.z_min}, {ws.z_max}]"
                ),
                "- All velocity commands are validated before execution",
                "",
                "### Tips",
                "- Use `ros2_list_topics` to discover all available topics",
                "- Use `ros2_subscribe_once` to read the current value of any topic",
                "- Use `ros2_camera_snapshot` to see what the robot sees",
                "- The user can say /estop at any time to immediately stop the robot",
            ]
        )

        return "\n".join(lines)

    def _build_fallback_context(self) -> str:
        """Fallback context when discovery fails or returns nothing."""
        name = self._config.robot.name
        ns = self._config.robot.namespace
        safety = self._config.safety
        ws = safety.workspace_limits
        prefix = f"{ns}/" if ns else "/"

        return "\n".join(
            [
                f"## Robot: {name}",
                "",
                (
                    f'You are connected to a ROS2 robot named "{name}". '
                    "You can control it using the ros2_* tools."
                ),
                "",
                "### Available Topics",
                f"- `{prefix}cmd_vel` (geometry_msgs/msg/Twist) — Velocity commands",
                f"- `{prefix}odom` (nav_msgs/msg/Odometry) — Odometry data",
                f"- `{prefix}scan` (sensor_msgs/msg/LaserScan) — LIDAR scan",
                (
                    f"- `{prefix}camera/image_raw/compressed` "
                    "(sensor_msgs/msg/CompressedImage) — Camera feed"
                ),
                f"- `{prefix}battery_state` (sensor_msgs/msg/BatteryState) — Battery",
                "",
                "### Safety Limits",
                f"- Maximum linear velocity: {safety.max_linear_velocity} m/s",
                f"- Maximum angular velocity: {safety.max_angular_velocity} rad/s",
                (
                    f"- Workspace bounds: "
                    f"x[{ws.x_min}, {ws.x_max}], "
                    f"y[{ws.y_min}, {ws.y_max}], "
                    f"z[{ws.z_min}, {ws.z_max}]"
                ),
                "- All velocity commands are validated before execution",
                "",
                "### Tips",
                "- Use `ros2_list_topics` to discover all available topics",
                "- Use `ros2_subscribe_once` to read the current value of any topic",
                "- Use `ros2_camera_snapshot` to see what the robot sees",
                "- The user can say /estop at any time to immediately stop the robot",
            ]
        )

    # ------------------------------------------------------------------
    # Filtering helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _filter_topics(
        topics: list[TopicInfo],
        namespace: str,
    ) -> list[TopicInfo]:
        """Remove internal topics and apply namespace filter."""
        filtered: list[TopicInfo] = []
        for t in topics:
            if any(t.name.startswith(p) for p in _INTERNAL_PREFIXES):
                continue
            if namespace and not t.name.startswith(namespace):
                continue
            filtered.append(t)
        return filtered

    @staticmethod
    def _filter_by_namespace(
        items: list[ServiceInfo] | list[ActionInfo],
        namespace: str,
    ) -> list[Any]:
        """Apply namespace filter to services or actions."""
        if not namespace:
            return list(items)
        return [item for item in items if item.name.startswith(namespace)]

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _cache_as_dict(self) -> dict[str, Any]:
        """Return the current cache contents as a plain dict."""
        if self._cache is None:
            return {"topics": [], "services": [], "actions": []}
        return {
            "topics": self._cache.topics,
            "services": self._cache.services,
            "actions": self._cache.actions,
        }


async def _gather(*coros: Any) -> tuple[Any, ...]:
    """Gather coroutines concurrently, equivalent to asyncio.gather."""
    import asyncio

    return tuple(await asyncio.gather(*coros))
