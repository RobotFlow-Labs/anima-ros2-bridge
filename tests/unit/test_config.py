# Copyright (c) 2026 AIFLOW LABS LIMITED / RobotFlowLabs
# All rights reserved.
# ANIMA ROS2 Bridge — Configuration tests

"""Tests for anima_bridge.config module."""

from __future__ import annotations

from anima_bridge.config import (
    AnimaBridgeConfig,
    RobotSettings,
    SafetySettings,
    TransportMode,
    TransportSettings,
)


class TestTransportMode:
    def test_default_mode_is_direct_dds(self) -> None:
        config = AnimaBridgeConfig()
        assert config.transport.mode == TransportMode.DIRECT_DDS

    def test_rosbridge_mode(self) -> None:
        config = AnimaBridgeConfig(transport=TransportSettings(mode=TransportMode.ROSBRIDGE))
        assert config.transport.mode == TransportMode.ROSBRIDGE


class TestSafetySettings:
    def test_default_velocity_limits(self) -> None:
        safety = SafetySettings()
        assert safety.max_linear_velocity > 0
        assert safety.max_angular_velocity > 0

    def test_default_workspace_limits(self) -> None:
        safety = SafetySettings()
        assert safety.workspace_limits.x_min < safety.workspace_limits.x_max
        assert safety.workspace_limits.y_min < safety.workspace_limits.y_max
        assert safety.workspace_limits.z_min < safety.workspace_limits.z_max

    def test_custom_velocity(self) -> None:
        safety = SafetySettings(max_linear_velocity=2.0, max_angular_velocity=3.0)
        assert safety.max_linear_velocity == 2.0
        assert safety.max_angular_velocity == 3.0


class TestRobotSettings:
    def test_default_name(self) -> None:
        robot = RobotSettings()
        assert robot.name == "Robot"

    def test_custom_name(self) -> None:
        robot = RobotSettings(name="ANIMA-Go2", namespace="/go2")
        assert robot.name == "ANIMA-Go2"
        assert robot.namespace == "/go2"


class TestFullConfig:
    def test_default_config_valid(self) -> None:
        config = AnimaBridgeConfig()
        assert config.transport.mode == TransportMode.DIRECT_DDS
        assert config.robot.name == "Robot"
        assert config.safety.max_linear_velocity > 0

    def test_config_serialization(self) -> None:
        config = AnimaBridgeConfig()
        data = config.model_dump()
        assert "transport" in data
        assert "robot" in data
        assert "safety" in data
        # Round-trip
        config2 = AnimaBridgeConfig(**data)
        assert config2.transport.mode == config.transport.mode
