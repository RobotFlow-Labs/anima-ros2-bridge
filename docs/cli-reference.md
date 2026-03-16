# CLI Reference

> Copyright (c) 2026 AIFLOW LABS LIMITED / RobotFlowLabs. All rights reserved.

## Global Options

All commands accept these transport options:

```bash
--transport {direct_dds,rosbridge}    # Transport mode
--url URL                              # Rosbridge WebSocket URL
--domain-id N                          # ROS2 DDS domain ID
--log-level {DEBUG,INFO,WARNING,ERROR} # Log level
```

## Commands

### `anima-bridge discover`

Auto-discover robot capabilities and generate a fingerprint report.

```bash
# Human-readable report
anima-bridge discover --transport rosbridge --url ws://localhost:9090

# Output:
# ## ANIMA Robot Discovery Report
# **Robot**: Unitree Go2
# **Category**: quadruped
# **Confidence**: 95%
# ### Detected Sensors
# - rgb_camera: /camera/image_raw
# - imu: /imu
# - lidar_3d: /points
# ### Recommended ANIMA Modules
# - AZOTH (detection)
# - CHRONOS (depth)
# - GNOMON (odometry fusion)

# YAML manifest output
anima-bridge discover --manifest --transport rosbridge --url ws://localhost:9090
```

### `anima-bridge topics`

List all available ROS2 topics.

```bash
anima-bridge topics --transport rosbridge --url ws://localhost:9090

# Output:
#   /cmd_vel                   geometry_msgs/msg/Twist
#   /imu                       sensor_msgs/msg/Imu
#   /odom                      nav_msgs/msg/Odometry
```

### `anima-bridge publish`

Publish a message to a ROS2 topic.

```bash
# Drive forward
anima-bridge publish /cmd_vel geometry_msgs/msg/Twist \
  '{"linear":{"x":0.5},"angular":{"z":0.0}}' \
  --transport rosbridge --url ws://localhost:9090

# Stop
anima-bridge publish /cmd_vel geometry_msgs/msg/Twist \
  '{"linear":{"x":0.0},"angular":{"z":0.0}}' \
  --transport rosbridge --url ws://localhost:9090
```

### `anima-bridge subscribe`

Read one message from a topic.

```bash
# Read odometry
anima-bridge subscribe /odom --timeout 5000 \
  --transport rosbridge --url ws://localhost:9090

# Read with specific type
anima-bridge subscribe /imu --type sensor_msgs/msg/Imu --timeout 3000 \
  --transport rosbridge --url ws://localhost:9090
```

### `anima-bridge service`

Call a ROS2 service.

```bash
anima-bridge service /trigger_save \
  --type std_srvs/srv/Trigger \
  --transport rosbridge --url ws://localhost:9090
```

### `anima-bridge camera`

Capture a camera frame.

```bash
# Save to file
anima-bridge camera --output frame.jpg \
  --transport rosbridge --url ws://localhost:9090

# Custom topic
anima-bridge camera --topic /camera/depth/image_raw --output depth.jpg \
  --transport rosbridge --url ws://localhost:9090
```

### `anima-bridge estop`

Emergency stop — immediately zeros all velocities.

```bash
anima-bridge estop --transport rosbridge --url ws://localhost:9090

# With namespace
anima-bridge estop --namespace /go2 \
  --transport rosbridge --url ws://localhost:9090
```

### `anima-bridge status`

Show current transport connection status.

```bash
anima-bridge status
```

### `anima-bridge serve`

Start the MCP server for AI agents.

```bash
# stdio mode (default, for Claude Code / local agents)
anima-bridge serve --transport rosbridge --url ws://localhost:9090

# SSE mode (for web-based agents)
anima-bridge serve --mode sse --port 8765 \
  --transport rosbridge --url ws://localhost:9090
```
