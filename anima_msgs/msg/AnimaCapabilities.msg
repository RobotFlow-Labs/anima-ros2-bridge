# Copyright (c) 2026 AIFLOW LABS LIMITED / RobotFlowLabs
# Robot capability manifest published by the ANIMA discovery node.
#
# This message provides a complete snapshot of what the robot can do,
# including ROS2 graph entities (topics, services, actions) and
# ANIMA-specific telemetry (module health, GPU usage, pipeline FPS).

string robot_name
string robot_namespace
string anima_version

# Topics
string[] topic_names
string[] topic_types
float32[] topic_hz

# Services
string[] service_names
string[] service_types

# Actions
string[] action_names
string[] action_types

# ANIMA-specific (not in ROSClaw)
string[] module_names
string[] module_statuses
float32 pipeline_fps
float32 gpu_vram_used_mb
float32 gpu_vram_total_mb
string pipeline_id
string[] active_safety_violations

builtin_interfaces/Time stamp
