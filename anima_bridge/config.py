"""ANIMA Bridge configuration schema.

Defines the complete configuration model for the ANIMA ROS2 Bridge using
Pydantic v2. All settings have sensible defaults so the bridge can start
with zero configuration for common local-DDS setups.

Copyright 2026 AIFLOW LABS LIMITED. All rights reserved.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class TransportMode(StrEnum):
    """Supported transport backends for ROS2 communication."""

    DIRECT_DDS = "direct_dds"
    ROSBRIDGE = "rosbridge"
    ZENOH = "zenoh"


class TransportSettings(BaseModel):
    """Top-level transport selector."""

    mode: TransportMode = Field(
        default=TransportMode.DIRECT_DDS,
        description="Which transport backend to use for ROS2 communication.",
    )


class RosbridgeSettings(BaseModel):
    """Configuration for the rosbridge WebSocket transport."""

    url: str = Field(
        default="ws://localhost:9090",
        description="WebSocket URL of the rosbridge server.",
    )
    reconnect: bool = Field(
        default=True,
        description="Whether to automatically reconnect on connection loss.",
    )
    reconnect_interval_ms: int = Field(
        default=3000,
        ge=100,
        description="Milliseconds between reconnection attempts.",
    )
    max_reconnect_attempts: int = Field(
        default=10,
        ge=0,
        description="Maximum number of reconnection attempts. 0 means unlimited.",
    )


class DirectDdsSettings(BaseModel):
    """Configuration for the direct DDS (rclpy) transport."""

    domain_id: int = Field(
        default=0,
        ge=0,
        le=232,
        description="ROS2 DDS domain ID.",
    )


class ZenohSettings(BaseModel):
    """Configuration for the Zenoh transport (future)."""

    router_url: str = Field(
        default="tcp/localhost:7447",
        description="Zenoh router endpoint.",
    )


class WorkspaceLimits(BaseModel):
    """3D workspace boundary for safety enforcement."""

    x_min: float = Field(default=-10.0, description="Minimum X coordinate (meters).")
    x_max: float = Field(default=10.0, description="Maximum X coordinate (meters).")
    y_min: float = Field(default=-10.0, description="Minimum Y coordinate (meters).")
    y_max: float = Field(default=10.0, description="Maximum Y coordinate (meters).")
    z_min: float = Field(default=0.0, description="Minimum Z coordinate (meters).")
    z_max: float = Field(default=3.0, description="Maximum Z coordinate (meters).")


class SafetySettings(BaseModel):
    """Safety limits enforced by the bridge before commands reach the robot."""

    max_linear_velocity: float = Field(
        default=1.0,
        gt=0.0,
        description="Maximum linear velocity (m/s).",
    )
    max_angular_velocity: float = Field(
        default=1.5,
        gt=0.0,
        description="Maximum angular velocity (rad/s).",
    )
    workspace_limits: WorkspaceLimits = Field(
        default_factory=WorkspaceLimits,
        description="3D workspace bounding box.",
    )
    joint_velocity_limits: dict[str, float] = Field(
        default_factory=dict,
        description="Per-joint velocity limits (rad/s). Key = joint name.",
    )
    max_gripper_force: float = Field(
        default=40.0,
        gt=0.0,
        description="Maximum gripper force (N).",
    )
    watchdog_timeout_ms: int = Field(
        default=500,
        ge=50,
        description="Watchdog timeout: stop the robot if no command received within this window.",
    )


class RobotSettings(BaseModel):
    """Identity and namespace of the target robot."""

    name: str = Field(
        default="Robot",
        description="Human-readable robot name (for logging and UI).",
    )
    namespace: str = Field(
        default="",
        description="ROS2 namespace prefix for all topics/services.",
    )


class LoggingSettings(BaseModel):
    """Logging and recording configuration."""

    mcap_enabled: bool = Field(
        default=False,
        description="Whether to record messages to MCAP files.",
    )
    mcap_dir: str = Field(
        default="./recordings",
        description="Directory for MCAP recording files.",
    )


class AnimaBridgeConfig(BaseModel):
    """Root configuration for the ANIMA ROS2 Bridge.

    All sections are optional with sensible defaults, so a bare
    ``AnimaBridgeConfig()`` gives you a working local-DDS setup.
    """

    transport: TransportSettings = Field(default_factory=TransportSettings)
    rosbridge: RosbridgeSettings = Field(default_factory=RosbridgeSettings)
    direct_dds: DirectDdsSettings = Field(default_factory=DirectDdsSettings)
    zenoh: ZenohSettings = Field(default_factory=ZenohSettings)
    robot: RobotSettings = Field(default_factory=RobotSettings)
    safety: SafetySettings = Field(default_factory=SafetySettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)

    model_config = {"extra": "forbid"}


def load_config(raw: dict[str, object] | None = None) -> AnimaBridgeConfig:
    """Parse and validate a raw config dict into a fully-defaulted config.

    Args:
        raw: Optional dictionary of config overrides. If ``None``, returns
             a config with all defaults applied.

    Returns:
        A validated ``AnimaBridgeConfig`` instance.
    """
    if raw is None:
        return AnimaBridgeConfig()
    return AnimaBridgeConfig.model_validate(raw)
