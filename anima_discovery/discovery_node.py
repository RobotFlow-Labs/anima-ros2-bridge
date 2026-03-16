# Copyright (c) 2026 AIFLOW LABS LIMITED / RobotFlowLabs
"""ANIMA Discovery Node — publishes robot capabilities to the ROS2 graph.

Periodically introspects the live ROS2 graph and publishes an
``AnimaCapabilities`` message describing all topics, services, actions,
ANIMA module health, GPU telemetry, and pipeline status.

Published topic:
    /anima/capabilities  (anima_msgs/msg/AnimaCapabilities)

Service:
    /anima/get_capabilities  (anima_msgs/srv/GetCapabilities)

Parameters:
    robot_name        — Human-readable robot name (default: "Robot")
    robot_namespace   — Namespace filter; empty = discover all (default: "")
    publish_interval  — Seconds between publications (default: 5.0)
    anima_version     — ANIMA suite version string (default: "0.1.0")
"""

from __future__ import annotations

import time
from collections import defaultdict

import rclpy
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile

from anima_msgs.msg import AnimaCapabilities
from anima_msgs.srv import GetCapabilities

# ROS2 internal topics that should never appear in the manifest.
_INTERNAL_PREFIXES = (
    "/rosout",
    "/parameter_events",
    "/anima/internal",
    "/anima/capabilities",
    "/anima/get_capabilities",
)

# Maximum number of Hz samples to keep per topic for rate estimation.
_HZ_WINDOW = 20


class AnimaDiscoveryNode(Node):
    """Periodically discovers ROS2 capabilities and publishes a manifest.

    Enhancements over the ROSClaw discovery node:
        - Measures per-topic publication rate (Hz).
        - Reports ANIMA module names and statuses.
        - Includes GPU VRAM telemetry and pipeline FPS.
        - Reports active safety violations.
        - Supports runtime namespace override via the service request.
    """

    def __init__(self) -> None:
        super().__init__("anima_discovery")

        # ── Parameters ───────────────────────────────────────────────
        self.declare_parameter("robot_name", "Robot")
        self.declare_parameter("robot_namespace", "")
        self.declare_parameter("publish_interval", 5.0)
        self.declare_parameter("anima_version", "0.1.0")

        self._robot_name: str = self.get_parameter("robot_name").value  # type: ignore[assignment]
        self._robot_namespace: str = self.get_parameter("robot_namespace").value  # type: ignore[assignment]
        self._publish_interval: float = self.get_parameter("publish_interval").value  # type: ignore[assignment]
        self._anima_version: str = self.get_parameter("anima_version").value  # type: ignore[assignment]

        # ── Hz tracking state ────────────────────────────────────────
        self._topic_timestamps: dict[str, list[float]] = defaultdict(list)

        # ── ANIMA telemetry (populated externally or via sub-topics) ─
        self._module_names: list[str] = []
        self._module_statuses: list[str] = []
        self._pipeline_fps: float = 0.0
        self._gpu_vram_used_mb: float = 0.0
        self._gpu_vram_total_mb: float = 0.0
        self._pipeline_id: str = ""
        self._active_safety_violations: list[str] = []

        # ── Publisher — TRANSIENT_LOCAL so late subscribers get last ──
        qos = QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL)
        self._capabilities_pub = self.create_publisher(
            AnimaCapabilities, "/anima/capabilities", qos
        )

        # ── Service — on-demand query ────────────────────────────────
        self._get_caps_srv = self.create_service(
            GetCapabilities,
            "/anima/get_capabilities",
            self._handle_get_capabilities,
        )

        # ── Timer — periodic discovery ───────────────────────────────
        self._timer = self.create_timer(self._publish_interval, self._on_timer)

        self.get_logger().info(
            "ANIMA Discovery started: robot=%s namespace='%s' interval=%.1fs",
            self._robot_name,
            self._robot_namespace,
            self._publish_interval,
        )

    # ──────────────────────────────────────────────────────────────────
    # Timer callback
    # ──────────────────────────────────────────────────────────────────

    def _on_timer(self) -> None:
        """Discover capabilities and publish the manifest."""
        msg = self._build_capabilities(self._robot_namespace)
        self._capabilities_pub.publish(msg)
        self.get_logger().debug(
            "Published: %d topics, %d services, %d actions",
            len(msg.topic_names),
            len(msg.service_names),
            len(msg.action_names),
        )

    # ──────────────────────────────────────────────────────────────────
    # Service handler
    # ──────────────────────────────────────────────────────────────────

    def _handle_get_capabilities(
        self,
        request: GetCapabilities.Request,
        response: GetCapabilities.Response,
    ) -> GetCapabilities.Response:
        """Handle an on-demand capability query."""
        namespace = request.robot_namespace or self._robot_namespace
        try:
            response.capabilities = self._build_capabilities(namespace)
            response.success = True
            response.error_message = ""
        except Exception as exc:  # noqa: BLE001
            self.get_logger().error("get_capabilities failed: %s", exc)
            response.success = False
            response.error_message = str(exc)
        return response

    # ──────────────────────────────────────────────────────────────────
    # Manifest builder
    # ──────────────────────────────────────────────────────────────────

    def _build_capabilities(self, namespace: str) -> AnimaCapabilities:
        """Query the ROS2 graph and assemble an AnimaCapabilities message."""
        msg = AnimaCapabilities()
        msg.robot_name = self._robot_name
        msg.robot_namespace = namespace
        msg.anima_version = self._anima_version
        msg.stamp = self.get_clock().now().to_msg()

        ns_prefix = namespace if namespace else ""

        # ── Topics ───────────────────────────────────────────────────
        for name, types in self.get_topic_names_and_types():
            if not self._should_include(name, ns_prefix):
                continue
            msg.topic_names.append(name)
            msg.topic_types.append(types[0] if types else "")
            msg.topic_hz.append(self._estimate_hz(name))

        # ── Services ─────────────────────────────────────────────────
        for name, types in self.get_service_names_and_types():
            if not self._should_include(name, ns_prefix):
                continue
            msg.service_names.append(name)
            msg.service_types.append(types[0] if types else "")

        # ── Actions — heuristic via _action/feedback topics ──────────
        feedback_suffix = "/_action/feedback"
        for name, types in self.get_topic_names_and_types():
            if not name.endswith(feedback_suffix):
                continue
            action_name = name[: -len(feedback_suffix)]
            if not self._should_include(action_name, ns_prefix):
                continue
            action_type = types[0] if types else ""
            if action_type.endswith("_FeedbackMessage"):
                action_type = action_type[: -len("_FeedbackMessage")]
            msg.action_names.append(action_name)
            msg.action_types.append(action_type)

        # ── ANIMA telemetry ──────────────────────────────────────────
        msg.module_names = list(self._module_names)
        msg.module_statuses = list(self._module_statuses)
        msg.pipeline_fps = self._pipeline_fps
        msg.gpu_vram_used_mb = self._gpu_vram_used_mb
        msg.gpu_vram_total_mb = self._gpu_vram_total_mb
        msg.pipeline_id = self._pipeline_id
        msg.active_safety_violations = list(self._active_safety_violations)

        return msg

    # ──────────────────────────────────────────────────────────────────
    # Hz estimation
    # ──────────────────────────────────────────────────────────────────

    def record_topic_timestamp(self, topic_name: str) -> None:
        """Record a reception timestamp for Hz estimation.

        Called externally (e.g. by a generic subscriber) to feed the
        rate estimator.
        """
        stamps = self._topic_timestamps[topic_name]
        stamps.append(time.monotonic())
        if len(stamps) > _HZ_WINDOW:
            del stamps[: len(stamps) - _HZ_WINDOW]

    def _estimate_hz(self, topic_name: str) -> float:
        """Estimate the publication rate of a topic from recorded timestamps."""
        stamps = self._topic_timestamps.get(topic_name)
        if not stamps or len(stamps) < 2:
            return 0.0
        elapsed = stamps[-1] - stamps[0]
        if elapsed <= 0.0:
            return 0.0
        return (len(stamps) - 1) / elapsed

    # ──────────────────────────────────────────────────────────────────
    # ANIMA telemetry setters (called by external pipeline monitor)
    # ──────────────────────────────────────────────────────────────────

    def update_module_status(
        self,
        module_names: list[str],
        module_statuses: list[str],
    ) -> None:
        """Update the reported ANIMA module names and statuses."""
        self._module_names = list(module_names)
        self._module_statuses = list(module_statuses)

    def update_pipeline_telemetry(
        self,
        *,
        pipeline_fps: float = 0.0,
        gpu_vram_used_mb: float = 0.0,
        gpu_vram_total_mb: float = 0.0,
        pipeline_id: str = "",
    ) -> None:
        """Update GPU and pipeline telemetry reported in the manifest."""
        self._pipeline_fps = pipeline_fps
        self._gpu_vram_used_mb = gpu_vram_used_mb
        self._gpu_vram_total_mb = gpu_vram_total_mb
        self._pipeline_id = pipeline_id

    def update_safety_violations(self, violations: list[str]) -> None:
        """Update the list of active safety violations."""
        self._active_safety_violations = list(violations)

    # ──────────────────────────────────────────────────────────────────
    # Filtering
    # ──────────────────────────────────────────────────────────────────

    @staticmethod
    def _should_include(name: str, ns_prefix: str) -> bool:
        """Return True if a topic/service/action should appear in the manifest."""
        for prefix in _INTERNAL_PREFIXES:
            if name.startswith(prefix):
                return False
        if ns_prefix and not name.startswith(ns_prefix):
            return False
        return True


# ──────────────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────────────


def main() -> None:
    """Entry point for the ANIMA discovery node."""
    rclpy.init()
    node = AnimaDiscoveryNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
