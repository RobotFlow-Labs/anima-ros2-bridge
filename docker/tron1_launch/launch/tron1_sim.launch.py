"""TRON1 Biped Simulation Launch — ANIMA ROS2 Bridge Demo.

Copyright (c) 2026 AIFLOW LABS LIMITED / RobotFlowLabs. All rights reserved.

Launches:
1. Gazebo Harmonic with empty world
2. TRON1 biped robot (point-foot variant)
3. Robot state publisher (joint states → tf)
4. Rosbridge server (for WebSocket bridge mode)
5. ANIMA discovery node
"""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    ExecuteProcess,
    IncludeLaunchDescription,
    TimerAction,
)
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    # Robot model path
    robot_type = os.environ.get("ROBOT_TYPE", "PF_TRON1A")
    urdf_path = f"/anima_ws/src/tron1_description/tron1/TRON1A/{robot_type}/urdf/robot.urdf"

    # Fallback to tron1_urdf if TRON1A path doesn't exist
    if not os.path.exists(urdf_path):
        urdf_path = f"/anima_ws/src/tron1_description/urdf/PF_P441C/urdf/robot.urdf"

    with open(urdf_path, "r") as f:
        robot_description = f.read()

    return LaunchDescription([
        # Gazebo Harmonic
        ExecuteProcess(
            cmd=["gz", "sim", "-r", "empty.sdf", "--headless-rendering"],
            output="screen",
        ),

        # Spawn robot in Gazebo
        TimerAction(
            period=3.0,
            actions=[
                ExecuteProcess(
                    cmd=[
                        "ros2", "run", "ros_gz_sim", "create",
                        "-topic", "robot_description",
                        "-name", "tron1",
                        "-z", "0.5",
                    ],
                    output="screen",
                ),
            ],
        ),

        # Robot state publisher
        Node(
            package="robot_state_publisher",
            executable="robot_state_publisher",
            parameters=[{"robot_description": robot_description}],
            output="screen",
        ),

        # Joint state publisher (GUI if display available)
        Node(
            package="joint_state_publisher",
            executable="joint_state_publisher",
            output="screen",
        ),

        # Rosbridge server (for WebSocket bridge mode)
        Node(
            package="rosbridge_server",
            executable="rosbridge_websocket",
            parameters=[{"port": 9090}],
            output="screen",
        ),

        # Gazebo → ROS2 bridge (clock, joint states)
        Node(
            package="ros_gz_bridge",
            executable="parameter_bridge",
            arguments=[
                "/clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock",
                "/joint_states@sensor_msgs/msg/JointState[gz.msgs.Model",
            ],
            output="screen",
        ),
    ])
