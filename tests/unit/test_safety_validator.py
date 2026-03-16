# Copyright (c) 2026 AIFLOW LABS LIMITED / RobotFlowLabs
# All rights reserved.
# ANIMA ROS2 Bridge — Safety validator tests

"""Tests for anima_bridge.safety.validator module."""

from __future__ import annotations

import pytest

from anima_bridge.config import SafetySettings, WorkspaceLimits
from anima_bridge.safety.validator import SafetyValidator


@pytest.fixture
def validator() -> SafetyValidator:
    settings = SafetySettings(
        max_linear_velocity=1.0,
        max_angular_velocity=1.5,
        workspace_limits=WorkspaceLimits(
            x_min=-2.0,
            x_max=2.0,
            y_min=-2.0,
            y_max=2.0,
            z_min=0.0,
            z_max=2.0,
        ),
        max_gripper_force=40.0,
    )
    return SafetyValidator(settings)


class TestTwistVelocityValidation:
    def test_safe_velocity(self, validator: SafetyValidator) -> None:
        ok, reason = validator.validate(
            "ros2_publish",
            {
                "msg_type": "geometry_msgs/msg/Twist",
                "message": {
                    "linear": {"x": 0.5, "y": 0.0, "z": 0.0},
                    "angular": {"x": 0.0, "y": 0.0, "z": 0.3},
                },
            },
        )
        assert ok is True

    def test_excessive_linear_velocity(self, validator: SafetyValidator) -> None:
        ok, reason = validator.validate(
            "ros2_publish",
            {
                "msg_type": "geometry_msgs/msg/Twist",
                "message": {
                    "linear": {"x": 5.0, "y": 0.0, "z": 0.0},
                    "angular": {"x": 0.0, "y": 0.0, "z": 0.0},
                },
            },
        )
        assert ok is False
        assert "linear" in reason.lower() or "velocity" in reason.lower()

    def test_excessive_angular_velocity(self, validator: SafetyValidator) -> None:
        ok, reason = validator.validate(
            "ros2_publish",
            {
                "msg_type": "geometry_msgs/msg/Twist",
                "message": {
                    "linear": {"x": 0.0, "y": 0.0, "z": 0.0},
                    "angular": {"x": 0.0, "y": 0.0, "z": 10.0},
                },
            },
        )
        assert ok is False

    def test_combined_velocity_magnitude(self, validator: SafetyValidator) -> None:
        # sqrt(0.7^2 + 0.7^2) ≈ 0.99 — should pass
        ok, _ = validator.validate(
            "ros2_publish",
            {
                "msg_type": "geometry_msgs/msg/Twist",
                "message": {
                    "linear": {"x": 0.7, "y": 0.7, "z": 0.0},
                    "angular": {"x": 0.0, "y": 0.0, "z": 0.0},
                },
            },
        )
        assert ok is True

        # sqrt(0.8^2 + 0.8^2) ≈ 1.13 — should fail
        ok, _ = validator.validate(
            "ros2_publish",
            {
                "msg_type": "geometry_msgs/msg/Twist",
                "message": {
                    "linear": {"x": 0.8, "y": 0.8, "z": 0.0},
                    "angular": {"x": 0.0, "y": 0.0, "z": 0.0},
                },
            },
        )
        assert ok is False


class TestWorkspaceValidation:
    def test_pose_within_bounds(self, validator: SafetyValidator) -> None:
        ok, _ = validator.validate(
            "ros2_publish",
            {
                "msg_type": "geometry_msgs/msg/PoseStamped",
                "message": {
                    "pose": {"position": {"x": 1.0, "y": 0.5, "z": 0.3}},
                },
            },
        )
        assert ok is True

    def test_pose_outside_x(self, validator: SafetyValidator) -> None:
        ok, reason = validator.validate(
            "ros2_publish",
            {
                "msg_type": "geometry_msgs/msg/PoseStamped",
                "message": {
                    "pose": {"position": {"x": 5.0, "y": 0.0, "z": 0.0}},
                },
            },
        )
        assert ok is False
        assert "workspace" in reason.lower() or "x" in reason.lower()

    def test_pose_below_z_floor(self, validator: SafetyValidator) -> None:
        ok, _ = validator.validate(
            "ros2_publish",
            {
                "msg_type": "geometry_msgs/msg/PoseStamped",
                "message": {
                    "pose": {"position": {"x": 0.0, "y": 0.0, "z": -0.5}},
                },
            },
        )
        assert ok is False


class TestNonRobotTools:
    def test_introspect_always_passes(self, validator: SafetyValidator) -> None:
        ok, _ = validator.validate("ros2_list_topics", {})
        assert ok is True

    def test_subscribe_always_passes(self, validator: SafetyValidator) -> None:
        ok, _ = validator.validate("ros2_subscribe_once", {"topic": "/odom"})
        assert ok is True

    def test_camera_always_passes(self, validator: SafetyValidator) -> None:
        ok, _ = validator.validate("ros2_camera_snapshot", {})
        assert ok is True
