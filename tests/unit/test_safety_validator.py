"""Tests for anima_bridge.safety.validator module.

Copyright (c) 2026 AIFLOW LABS LIMITED / RobotFlowLabs. All rights reserved.
"""

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


class TestActionGoalValidation:
    def test_action_goal_safe_position(self, validator: SafetyValidator) -> None:
        ok, _ = validator.validate(
            "ros2_action_goal",
            {
                "action": "/navigate_to_pose",
                "action_type": "nav2_msgs/action/NavigateToPose",
                "goal": {
                    "pose": {"pose": {"position": {"x": 1.0, "y": 0.5, "z": 0.3}}},
                },
            },
        )
        assert ok is True

    def test_action_goal_outside_workspace(self, validator: SafetyValidator) -> None:
        ok, reason = validator.validate(
            "ros2_action_goal",
            {
                "action": "/navigate_to_pose",
                "action_type": "nav2_msgs/action/NavigateToPose",
                "goal": {
                    "pose": {"pose": {"position": {"x": 50.0, "y": 0.0, "z": 0.0}}},
                },
            },
        )
        assert ok is False
        assert "workspace" in reason.lower() or "x" in reason.lower()

    def test_action_goal_flat_position(self, validator: SafetyValidator) -> None:
        ok, reason = validator.validate(
            "ros2_action_goal",
            {
                "action": "/move_arm",
                "action_type": "arm_msgs/action/MoveArm",
                "goal": {"position": {"x": 100.0, "y": 0.0, "z": 0.0}},
            },
        )
        assert ok is False

    def test_action_goal_no_position(self, validator: SafetyValidator) -> None:
        ok, _ = validator.validate(
            "ros2_action_goal",
            {
                "action": "/spin",
                "action_type": "nav2_msgs/action/Spin",
                "goal": {"target_yaw": 3.14},
            },
        )
        assert ok is True


class TestParamSetValidation:
    def test_safe_param(self, validator: SafetyValidator) -> None:
        ok, _ = validator.validate(
            "ros2_param_set",
            {"node": "/controller", "parameter": "use_sim_time", "value": True},
        )
        assert ok is True

    def test_velocity_param_exceeds_limit(self, validator: SafetyValidator) -> None:
        ok, reason = validator.validate(
            "ros2_param_set",
            {"node": "/controller", "parameter": "max_velocity", "value": 50.0},
        )
        assert ok is False
        assert "velocity" in reason.lower() or "limit" in reason.lower()

    def test_speed_param_within_limit(self, validator: SafetyValidator) -> None:
        ok, _ = validator.validate(
            "ros2_param_set",
            {"node": "/controller", "parameter": "max_speed", "value": 0.5},
        )
        assert ok is True

    def test_force_param_exceeds_limit(self, validator: SafetyValidator) -> None:
        ok, reason = validator.validate(
            "ros2_param_set",
            {"node": "/gripper", "parameter": "max_force", "value": 100.0},
        )
        assert ok is False
        assert "force" in reason.lower()


class TestServiceCallValidation:
    def test_safe_service(self, validator: SafetyValidator) -> None:
        ok, _ = validator.validate(
            "ros2_service_call",
            {"service": "/trigger_save"},
        )
        assert ok is True

    def test_dangerous_shutdown_blocked(self, validator: SafetyValidator) -> None:
        ok, reason = validator.validate(
            "ros2_service_call",
            {"service": "/robot/shutdown"},
        )
        assert ok is False
        assert "dangerous" in reason.lower() or "blocked" in reason.lower()

    def test_dangerous_reboot_blocked(self, validator: SafetyValidator) -> None:
        ok, _ = validator.validate(
            "ros2_service_call",
            {"service": "/system/reboot"},
        )
        assert ok is False

    def test_firmware_update_blocked(self, validator: SafetyValidator) -> None:
        ok, _ = validator.validate(
            "ros2_service_call",
            {"service": "/firmware_update"},
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
