"""Safety validator for ANIMA Bridge tool calls.

Inspects tool arguments BEFORE execution and blocks commands that would
violate configured safety limits (velocity, workspace bounds, joint limits,
gripper force).

Copyright 2026 AIFLOW LABS LIMITED. All rights reserved.
"""

from __future__ import annotations

import math
from typing import Any

from anima_bridge.config import SafetySettings


class SafetyValidator:
    """Pre-execution safety gate for ROS2 tool calls.

    Instantiate once with a ``SafetySettings`` config and call ``validate()``
    before every tool invocation. Returns ``(True, "ok")`` if the call is
    safe, or ``(False, "reason")`` if it must be blocked.
    """

    def __init__(self, config: SafetySettings) -> None:
        self._config = config

    def validate(self, tool_name: str, args: dict[str, Any]) -> tuple[bool, str]:
        """Validate a tool call against safety limits.

        Args:
            tool_name: Name of the tool being called (e.g. ``"ros2_publish"``).
            args: The arguments dict that will be passed to the tool.

        Returns:
            A tuple of ``(allowed, reason)``. If ``allowed`` is ``False``,
            ``reason`` explains why the call was blocked.
        """
        if tool_name == "ros2_publish":
            return self._check_publish(args)
        return (True, "ok")

    # ------------------------------------------------------------------
    # Publish message checks
    # ------------------------------------------------------------------

    def _check_publish(self, args: dict[str, Any]) -> tuple[bool, str]:
        """Run all relevant checks on a publish call."""
        message = args.get("message", {})
        if not isinstance(message, dict):
            return (True, "ok")

        # Twist velocity checks
        if "linear" in message or "angular" in message:
            result = self._check_twist(message)
            if not result[0]:
                return result

        # Pose / position workspace checks (handle both flat and nested PoseStamped)
        msg_type = args.get("msg_type", "")
        pose_data = message
        if "pose" in message and isinstance(message["pose"], dict):
            pose_data = message["pose"]
        if "position" in pose_data or "Pose" in msg_type:
            result = self._check_pose(pose_data)
            if not result[0]:
                return result

        # JointState velocity checks
        if "velocity" in message and "name" in message:
            result = self._check_joint_state(message)
            if not result[0]:
                return result

        # Gripper force checks
        if "force" in message:
            result = self._check_gripper_force(message)
            if not result[0]:
                return result

        return (True, "ok")

    def _check_twist(self, message: dict[str, Any]) -> tuple[bool, str]:
        """Validate linear and angular velocity in Twist messages."""
        linear = message.get("linear", {})
        if isinstance(linear, dict):
            lx = float(linear.get("x", 0.0))
            ly = float(linear.get("y", 0.0))
            lz = float(linear.get("z", 0.0))
            speed = math.sqrt(lx**2 + ly**2 + lz**2)
            limit = self._config.max_linear_velocity
            if speed > limit:
                return (
                    False,
                    f"Linear velocity {speed:.2f} m/s exceeds limit of {limit} m/s",
                )

        angular = message.get("angular", {})
        if isinstance(angular, dict):
            ax = float(angular.get("x", 0.0))
            ay = float(angular.get("y", 0.0))
            az = float(angular.get("z", 0.0))
            rate = math.sqrt(ax**2 + ay**2 + az**2)
            limit = self._config.max_angular_velocity
            if rate > limit:
                return (
                    False,
                    f"Angular velocity {rate:.2f} rad/s exceeds limit of {limit} rad/s",
                )

        return (True, "ok")

    def _check_pose(self, message: dict[str, Any]) -> tuple[bool, str]:
        """Validate position within workspace bounds."""
        position = message.get("position", {})
        if not isinstance(position, dict):
            return (True, "ok")

        ws = self._config.workspace_limits
        x = float(position.get("x", 0.0))
        y = float(position.get("y", 0.0))
        z = float(position.get("z", 0.0))

        if not (ws.x_min <= x <= ws.x_max):
            return (False, f"X position {x:.2f} outside workspace [{ws.x_min}, {ws.x_max}]")
        if not (ws.y_min <= y <= ws.y_max):
            return (False, f"Y position {y:.2f} outside workspace [{ws.y_min}, {ws.y_max}]")
        if not (ws.z_min <= z <= ws.z_max):
            return (False, f"Z position {z:.2f} outside workspace [{ws.z_min}, {ws.z_max}]")

        return (True, "ok")

    def _check_joint_state(self, message: dict[str, Any]) -> tuple[bool, str]:
        """Validate per-joint velocities against configured limits."""
        limits = self._config.joint_velocity_limits
        if not limits:
            return (True, "ok")

        names: list[str] = message.get("name", [])
        velocities: list[float] = message.get("velocity", [])

        for name, vel in zip(names, velocities):
            vel = float(vel)
            if name in limits and abs(vel) > limits[name]:
                return (
                    False,
                    f"Joint '{name}' velocity {abs(vel):.2f} rad/s exceeds "
                    f"limit of {limits[name]} rad/s",
                )

        return (True, "ok")

    def _check_gripper_force(self, message: dict[str, Any]) -> tuple[bool, str]:
        """Validate gripper force against the configured maximum."""
        force = float(message.get("force", 0.0))
        limit = self._config.max_gripper_force
        if abs(force) > limit:
            return (False, f"Gripper force {abs(force):.1f} N exceeds limit of {limit} N")
        return (True, "ok")
