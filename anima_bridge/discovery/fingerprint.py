"""Robot fingerprinting engine — identifies robot type and capabilities from ROS2 graph.

Copyright (c) 2026 AIFLOW LABS LIMITED / RobotFlowLabs. All rights reserved.

This is the "magic" of ANIMA discovery. Instead of just listing topics,
we UNDERSTAND what the robot is and what it can do by analyzing topic
patterns, message types, and naming conventions.

Example:
    Connect to any ROS2 robot → ANIMA tells you:
    "This is a Unitree Go2 quadruped with a RealSense D455 camera,
     a Livox Mid-360 LiDAR, and an IMU. It supports velocity control,
     Nav2 navigation, and camera streaming. Recommended ANIMA modules:
     AZOTH (detection), CHRONOS (depth), HERMES (navigation)."
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import StrEnum

from anima_bridge.transport.types import ActionInfo, ServiceInfo, TopicInfo

logger = logging.getLogger("anima_bridge.discovery")


class RobotCategory(StrEnum):
    """High-level robot classification."""

    QUADRUPED = "quadruped"
    HUMANOID = "humanoid"
    MOBILE_BASE = "mobile_base"
    ARM = "arm"
    DRONE = "drone"
    MOBILE_MANIPULATOR = "mobile_manipulator"
    UNKNOWN = "unknown"


class SensorType(StrEnum):
    """Detected sensor types."""

    RGB_CAMERA = "rgb_camera"
    DEPTH_CAMERA = "depth_camera"
    STEREO_CAMERA = "stereo_camera"
    LIDAR_2D = "lidar_2d"
    LIDAR_3D = "lidar_3d"
    IMU = "imu"
    FORCE_TORQUE = "force_torque"
    JOINT_STATE = "joint_state"
    ODOMETRY = "odometry"
    GPS = "gps"
    BATTERY = "battery"
    AUDIO = "audio"
    TACTILE = "tactile"
    RADAR = "radar"
    UWB = "uwb"


class ControlType(StrEnum):
    """Detected control interfaces."""

    VELOCITY = "velocity"  # cmd_vel → Twist
    JOINT_POSITION = "joint_position"  # joint commands
    JOINT_TRAJECTORY = "joint_trajectory"  # trajectory controller
    NAV2 = "nav2"  # NavigateToPose action
    MOVEIT = "moveit"  # MoveGroup action
    GRIPPER = "gripper"  # GripperCommand action


@dataclass
class SensorFingerprint:
    """A detected sensor on the robot."""

    sensor_type: SensorType
    topic: str
    msg_type: str
    estimated_hz: float = 0.0


@dataclass
class ControlFingerprint:
    """A detected control interface."""

    control_type: ControlType
    topic_or_action: str
    msg_type: str


@dataclass
class RobotFingerprint:
    """Complete fingerprint of a discovered robot."""

    category: RobotCategory = RobotCategory.UNKNOWN
    vendor_hint: str = ""
    model_hint: str = ""
    sensors: list[SensorFingerprint] = field(default_factory=list)
    controls: list[ControlFingerprint] = field(default_factory=list)
    recommended_modules: list[str] = field(default_factory=list)
    confidence: float = 0.0  # 0.0-1.0


# ── Topic signature patterns ──────────────────────────────────────────────

_SENSOR_PATTERNS: list[tuple[str, str, SensorType]] = [
    # (topic_contains, msg_type_contains, sensor_type)
    ("image_raw", "sensor_msgs/msg/Image", SensorType.RGB_CAMERA),
    ("image_raw/compressed", "sensor_msgs/msg/CompressedImage", SensorType.RGB_CAMERA),
    ("depth", "sensor_msgs/msg/Image", SensorType.DEPTH_CAMERA),
    ("pointcloud", "sensor_msgs/msg/PointCloud2", SensorType.LIDAR_3D),
    ("points", "sensor_msgs/msg/PointCloud2", SensorType.LIDAR_3D),
    ("scan", "sensor_msgs/msg/LaserScan", SensorType.LIDAR_2D),
    ("imu", "sensor_msgs/msg/Imu", SensorType.IMU),
    ("odom", "nav_msgs/msg/Odometry", SensorType.ODOMETRY),
    ("joint_states", "sensor_msgs/msg/JointState", SensorType.JOINT_STATE),
    ("battery", "sensor_msgs/msg/BatteryState", SensorType.BATTERY),
    ("wrench", "geometry_msgs/msg/WrenchStamped", SensorType.FORCE_TORQUE),
    ("gps", "sensor_msgs/msg/NavSatFix", SensorType.GPS),
    ("audio", "audio_msgs", SensorType.AUDIO),
]

_CONTROL_PATTERNS: list[tuple[str, str, ControlType]] = [
    ("cmd_vel", "geometry_msgs/msg/Twist", ControlType.VELOCITY),
    ("joint_commands", "sensor_msgs/msg/JointState", ControlType.JOINT_POSITION),
    ("joint_trajectory", "trajectory_msgs", ControlType.JOINT_TRAJECTORY),
]

_ACTION_CONTROL_PATTERNS: list[tuple[str, str, ControlType]] = [
    ("navigate_to_pose", "nav2_msgs", ControlType.NAV2),
    ("move_group", "moveit_msgs", ControlType.MOVEIT),
    ("gripper_command", "control_msgs", ControlType.GRIPPER),
]

_VENDOR_SIGNATURES: list[tuple[str, str, str]] = [
    # (topic_contains, vendor, model_hint)
    ("go2", "Unitree", "Go2"),
    ("go1", "Unitree", "Go1"),
    ("unitree", "Unitree", ""),
    ("b2", "Unitree", "B2"),
    ("h1", "Unitree", "H1"),
    ("g1", "Unitree", "G1"),
    ("spot", "Boston Dynamics", "Spot"),
    ("turtlebot", "Clearpath", "TurtleBot"),
    ("husky", "Clearpath", "Husky"),
    ("jackal", "Clearpath", "Jackal"),
    ("xarm", "UFactory", "xArm"),
    ("panda", "Franka", "Panda"),
    ("ur5", "Universal Robots", "UR5"),
    ("ur10", "Universal Robots", "UR10"),
    ("kinova", "Kinova", "Gen3"),
    ("stretch", "Hello Robot", "Stretch"),
    ("tron", "LimX Dynamics", "TRON"),
    ("limx", "LimX Dynamics", ""),
]

# Module recommendations based on sensors + controls
_MODULE_RECOMMENDATIONS: dict[SensorType, list[str]] = {
    SensorType.RGB_CAMERA: ["AZOTH (detection)", "MONAD (segmentation)", "LOGOS (VLM tracking)"],
    SensorType.DEPTH_CAMERA: ["CHRONOS (depth)", "ABYSSOS (metric depth)"],
    SensorType.STEREO_CAMERA: ["PRISM (3D SLAM)", "LOCI (place recognition)"],
    SensorType.LIDAR_3D: ["NEXUS (semantic 3D)", "PRISM (SLAM)", "HERMES (navigation)"],
    SensorType.LIDAR_2D: ["HERMES (navigation)"],
    SensorType.IMU: ["GNOMON (odometry fusion)"],
    SensorType.FORCE_TORQUE: ["HAPTOS (tactile)", "DAEDALUS (manipulation)"],
    SensorType.JOINT_STATE: ["DAEDALUS (manipulation)", "PYGMALION (VLA)"],
}


class RobotFingerprinter:
    """Analyzes ROS2 graph to identify robot type, sensors, and capabilities.

    This goes far beyond topic listing — it understands WHAT the robot is.
    """

    def fingerprint(
        self,
        topics: list[TopicInfo],
        services: list[ServiceInfo],
        actions: list[ActionInfo],
    ) -> RobotFingerprint:
        """Analyze discovered ROS2 entities and produce a robot fingerprint."""
        fp = RobotFingerprint()

        # Detect sensors
        for topic in topics:
            for pattern, msg_pattern, sensor_type in _SENSOR_PATTERNS:
                if pattern in topic.name.lower() and msg_pattern in topic.msg_type:
                    fp.sensors.append(
                        SensorFingerprint(
                            sensor_type=sensor_type,
                            topic=topic.name,
                            msg_type=topic.msg_type,
                        )
                    )
                    break

        # Detect control interfaces from topics
        for topic in topics:
            for pattern, msg_pattern, ctrl_type in _CONTROL_PATTERNS:
                if pattern in topic.name.lower() and msg_pattern in topic.msg_type:
                    fp.controls.append(
                        ControlFingerprint(
                            control_type=ctrl_type,
                            topic_or_action=topic.name,
                            msg_type=topic.msg_type,
                        )
                    )
                    break

        # Detect control interfaces from actions
        for action in actions:
            for pattern, msg_pattern, ctrl_type in _ACTION_CONTROL_PATTERNS:
                if pattern in action.name.lower() and msg_pattern in action.action_type:
                    fp.controls.append(
                        ControlFingerprint(
                            control_type=ctrl_type,
                            topic_or_action=action.name,
                            msg_type=action.action_type,
                        )
                    )
                    break

        # Identify vendor/model from topic names
        all_names = [t.name.lower() for t in topics]
        all_names += [s.name.lower() for s in services]
        all_names += [a.name.lower() for a in actions]
        joined = " ".join(all_names)

        for pattern, vendor, model in _VENDOR_SIGNATURES:
            if pattern in joined:
                fp.vendor_hint = vendor
                fp.model_hint = model or fp.model_hint
                break

        # Classify robot category
        fp.category = self._classify_category(fp)

        # Recommend ANIMA modules
        seen_modules: set[str] = set()
        for sensor in fp.sensors:
            for module in _MODULE_RECOMMENDATIONS.get(sensor.sensor_type, []):
                if module not in seen_modules:
                    fp.recommended_modules.append(module)
                    seen_modules.add(module)

        # Confidence based on how much we detected
        total_detections = len(fp.sensors) + len(fp.controls)
        fp.confidence = min(1.0, total_detections / 5.0)

        logger.info(
            "Fingerprint: %s %s %s — %d sensors, %d controls, confidence=%.0f%%",
            fp.vendor_hint or "Unknown",
            fp.model_hint or "",
            fp.category.value,
            len(fp.sensors),
            len(fp.controls),
            fp.confidence * 100,
        )

        return fp

    def _classify_category(self, fp: RobotFingerprint) -> RobotCategory:
        """Classify robot type from detected features."""
        ctrl_types = {c.control_type for c in fp.controls}
        sensor_types = {s.sensor_type for s in fp.sensors}

        has_velocity = ControlType.VELOCITY in ctrl_types
        has_joints = (
            ControlType.JOINT_POSITION in ctrl_types or ControlType.JOINT_TRAJECTORY in ctrl_types
        )
        has_nav2 = ControlType.NAV2 in ctrl_types
        has_moveit = ControlType.MOVEIT in ctrl_types
        has_gripper = ControlType.GRIPPER in ctrl_types

        # Humanoid: many joints + velocity + IMU
        if has_joints and has_velocity and SensorType.IMU in sensor_types:
            joint_count = sum(1 for s in fp.sensors if s.sensor_type == SensorType.JOINT_STATE)
            if joint_count > 0 and fp.vendor_hint in ("Unitree", "LimX Dynamics", ""):
                if fp.model_hint in ("H1", "G1", "TRON", ""):
                    return RobotCategory.HUMANOID

        # Mobile manipulator: velocity + arm joints + gripper
        if has_velocity and (has_moveit or has_gripper):
            return RobotCategory.MOBILE_MANIPULATOR

        # Arm: joints/moveit + gripper, no velocity
        if (has_moveit or has_gripper or has_joints) and not has_velocity:
            return RobotCategory.ARM

        # Quadruped: velocity + IMU + joint states + specific vendor
        if has_velocity and SensorType.IMU in sensor_types:
            if fp.vendor_hint in ("Unitree", "Boston Dynamics", "DEEP Robotics", "ANYbotics"):
                return RobotCategory.QUADRUPED

        # Mobile base: velocity + nav2
        if has_velocity and (has_nav2 or SensorType.LIDAR_2D in sensor_types):
            return RobotCategory.MOBILE_BASE

        # Drone: check for mavros/px4 topics
        if has_velocity and SensorType.GPS in sensor_types:
            return RobotCategory.DRONE

        if has_velocity:
            return RobotCategory.MOBILE_BASE

        return RobotCategory.UNKNOWN

    def format_report(self, fp: RobotFingerprint) -> str:
        """Format fingerprint as a human-readable report."""
        lines: list[str] = []
        lines.append("## ANIMA Robot Discovery Report")
        lines.append("")

        # Identity
        name = f"{fp.vendor_hint} {fp.model_hint}".strip() or "Unknown Robot"
        lines.append(f"**Robot**: {name}")
        lines.append(f"**Category**: {fp.category.value}")
        lines.append(f"**Confidence**: {fp.confidence:.0%}")
        lines.append("")

        # Sensors
        if fp.sensors:
            lines.append("### Detected Sensors")
            for s in fp.sensors:
                lines.append(f"- **{s.sensor_type.value}**: `{s.topic}` ({s.msg_type})")
            lines.append("")

        # Controls
        if fp.controls:
            lines.append("### Control Interfaces")
            for c in fp.controls:
                lines.append(f"- **{c.control_type.value}**: `{c.topic_or_action}` ({c.msg_type})")
            lines.append("")

        # Recommendations
        if fp.recommended_modules:
            lines.append("### Recommended ANIMA Modules")
            for mod in fp.recommended_modules:
                lines.append(f"- {mod}")
            lines.append("")

        return "\n".join(lines)
