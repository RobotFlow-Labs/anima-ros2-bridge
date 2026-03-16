# Simulation Setup

> Copyright (c) 2026 AIFLOW LABS LIMITED / RobotFlowLabs. All rights reserved.

## Quick Start

```bash
# Start the full simulation stack
docker compose -p anima_ros2_stack -f docker/docker-compose.sim.yml up -d

# Open the live viewer (3 cameras + all sensors)
open http://localhost:8080

# Connect CLI
anima-bridge topics --transport rosbridge --url ws://localhost:9090

# Drive the robot
anima-bridge publish /cmd_vel geometry_msgs/msg/Twist \
  '{"linear":{"x":0.5},"angular":{"z":0.2}}' \
  --transport rosbridge --url ws://localhost:9090

# Stop
docker compose -p anima_ros2_stack -f docker/docker-compose.sim.yml down
```

## What's Included

The simulation stack runs in a single Docker container:

| Component | Description |
|-----------|-------------|
| Gazebo Harmonic | Physics simulation (headless) |
| Mobile Base Robot | Diff-drive with camera, IMU, LiDAR, depth |
| TRON1 Biped | LimX Dynamics TRON1 (visual model) |
| GZ Bridge | Gazebo → ROS2 topic forwarding |
| Image Compressor | Raw 900KB → JPEG 7KB per frame |
| Rosbridge | WebSocket server on port 9090 |

## Cameras

Three live camera feeds:

| Camera | View | Topic |
|--------|------|-------|
| Robot POV | First-person from robot | `/camera/rgb/image_raw/compressed` |
| Overhead | Bird's eye looking down | `/camera/overhead/image_raw/compressed` |
| Side | Corner view of warehouse | `/camera/side/image_raw/compressed` |

## Sensor Topics

| Topic | Type | Rate | Description |
|-------|------|------|-------------|
| `/camera/rgb/image_raw` | Image | 15 Hz | Robot camera (raw) |
| `/camera/rgb/image_raw/compressed` | CompressedImage | ~5 Hz | Robot camera (JPEG) |
| `/camera/overhead/image_raw/compressed` | CompressedImage | ~3 Hz | Overhead view |
| `/camera/side/image_raw/compressed` | CompressedImage | ~3 Hz | Side view |
| `/imu` | Imu | 100 Hz | IMU (orientation, angular vel, accel) |
| `/odom` | Odometry | 20 Hz | Odometry (position, velocity) |
| `/lidar/scan` | LaserScan | 10 Hz | 2D LiDAR (360 points) |
| `/depth/image` | Image | 10 Hz | Depth camera |
| `/joint_states` | JointState | ~500 Hz | Wheel and camera joints |
| `/cmd_vel` | Twist | subscriber | Drive commands |

## TRON1 Biped Model

The TRON1 biped from LimX Dynamics (Shenzhen) is included as a visual model:

- **Variants**: Point-Foot (PF), Wheel-Foot (WF), Sole-Foot (SF)
- **DOF**: 12 (6 per leg)
- **Files**: `sim/TRON1/TRON1A/PF_TRON1A/urdf/robot.urdf`
- **Meshes**: STL files in `sim/TRON1/TRON1A/PF_TRON1A/meshes/`

## Live Viewer

The web viewer at `http://localhost:8080` shows:

- 3 live camera feeds (Robot POV + Overhead + Side)
- IMU data (orientation, angular velocity, linear acceleration)
- Odometry (position, velocity)
- Joint states with position bars
- LiDAR 360° scan visualization
- Message rate monitor
- Topic discovery with sensor badges
- Bridge connection log

## Docker Group

All containers use the `anima_ros2_stack` project name:

```bash
# Start
docker compose -p anima_ros2_stack -f docker/docker-compose.sim.yml up -d

# Check status
docker compose -p anima_ros2_stack -f docker/docker-compose.sim.yml ps

# Logs
docker compose -p anima_ros2_stack -f docker/docker-compose.sim.yml logs -f

# Stop
docker compose -p anima_ros2_stack -f docker/docker-compose.sim.yml down
```

## Building the Simulation Image

The simulation image extends `rlf-gazebo:latest` with rosbridge + foxglove:

```bash
docker build -t anima/sim:latest -f docker/Dockerfile.sim docker/
```

## Recording Video

```bash
# Mac screen recording
# Cmd+Shift+5 → Record Selected Window → select browser at localhost:8080

# FFmpeg capture
ffmpeg -f avfoundation -framerate 30 -i "1" -t 60 -c:v h264 demo.mp4
```
