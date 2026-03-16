# TRON1 Demo — Simulator Control & Video Recording

Control the LimX TRON1 biped robot in Gazebo and record marketing videos.

## Quick Start

```bash
# 1. Launch TRON1 simulation
docker compose -f docker/docker-compose.tron1.yml up -d

# 2. View in browser (Gazebo web)
open http://localhost:8080

# 3. Check ROS2 topics
docker exec anima_tron1_sim ros2 topic list

# 4. Connect ANIMA bridge
anima-bridge --transport rosbridge --url ws://localhost:9090 discover
```

## Control Commands

### Move the robot
```bash
# Walk forward (Twist velocity)
anima-bridge publish /cmd_vel geometry_msgs/msg/Twist '{"linear":{"x":0.3},"angular":{"z":0.0}}'

# Turn left
anima-bridge publish /cmd_vel geometry_msgs/msg/Twist '{"linear":{"x":0.1},"angular":{"z":0.5}}'

# Stop
anima-bridge publish /cmd_vel geometry_msgs/msg/Twist '{"linear":{"x":0.0},"angular":{"z":0.0}}'

# Emergency stop
anima-bridge estop
```

### Read sensor data
```bash
# Joint states
anima-bridge subscribe /joint_states --timeout 3000

# IMU
anima-bridge subscribe /imu/data --timeout 3000

# Camera
anima-bridge camera --topic /camera/image_raw/compressed --output tron1_frame.jpg

# All topics
anima-bridge topics
```

### Auto-discover
```bash
# Full fingerprint report
anima-bridge discover

# Expected output:
# Robot: LimX Dynamics TRON1
# Category: humanoid
# Sensors: joint_state, imu, rgb_camera
# Controls: velocity, joint_position
# Recommended: AZOTH, CHRONOS, GNOMON, DAEDALUS

# Generate hardware manifest
anima-bridge discover --manifest > hardware_manifest.yaml
```

## Video Recording

### Method 1: Gazebo built-in recording
```bash
# Start recording
docker exec anima_tron1_sim gz service \
  -s /gui/record_video \
  --reqtype gz.msgs.VideoRecord \
  --reptype gz.msgs.Boolean \
  --req 'start:true, save_filename:"/recordings/tron1_demo.mp4"' \
  --timeout 3000

# ... do robot actions ...

# Stop recording
docker exec anima_tron1_sim gz service \
  -s /gui/record_video \
  --reqtype gz.msgs.VideoRecord \
  --reptype gz.msgs.Boolean \
  --req 'stop:true' \
  --timeout 3000

# File saved in docker/recordings/tron1_demo.mp4
```

### Method 2: Screen recording on Mac (best quality)
```bash
# Record the browser window showing Gazebo web viewer
# Use macOS built-in: Cmd+Shift+5 → Record Selected Window → select browser

# Or use ffmpeg to record the screen
ffmpeg -f avfoundation -framerate 30 -i "1" -t 60 tron1_demo.mp4
```

### Method 3: ROS2 image topic recording
```bash
# Record camera feed from robot
docker exec anima_tron1_sim ros2 bag record /camera/image_raw -o /recordings/camera_bag

# Convert to video later
# ros2 bag → images → ffmpeg → mp4
```

## Demo Script for Marketing Video

### Scene 1: Auto-Discovery (10 seconds)
```bash
# Terminal shows:
anima-bridge discover
# Output appears with robot fingerprint:
# "LimX Dynamics TRON1 humanoid — 12 DOF, IMU, RGBD camera"
# "Recommended ANIMA modules: AZOTH, CHRONOS, GNOMON"
```

### Scene 2: Walk Command (15 seconds)
```bash
# Human types natural language (or voice with STT later):
anima-bridge publish /cmd_vel geometry_msgs/msg/Twist '{"linear":{"x":0.3}}'
# TRON1 walks forward in simulator
# Safety validator passes: "Linear velocity 0.30 m/s within limit of 1.0 m/s"
```

### Scene 3: Safety Block (10 seconds)
```bash
# Try to go too fast:
anima-bridge publish /cmd_vel geometry_msgs/msg/Twist '{"linear":{"x":5.0}}'
# BLOCKED: "Linear velocity 5.00 m/s exceeds limit of 1.0 m/s"
# Robot doesn't move. Safety works.
```

### Scene 4: Camera Snapshot (10 seconds)
```bash
anima-bridge camera --output tron1_view.jpg
# Shows: captured frame from robot's perspective
```

### Scene 5: Emergency Stop (5 seconds)
```bash
anima-bridge estop
# All velocities zeroed. Robot stops immediately.
```

### Scene 6: Transport Switch (10 seconds)
```bash
# Show switching between modes:
anima-bridge status
# → mode: rosbridge, connected
# Switch to DDS (if available):
# → mode: direct_dds, latency: <1ms
```

## Viewing Options

### Browser (easiest — no X11 needed)
- Gazebo ships with gzweb: http://localhost:8080
- Works on Mac without X11 forwarding
- Best for recording with screen capture

### X11 Forwarding (if you want native Gazebo GUI)
```bash
# Mac: install XQuartz first
brew install --cask xquartz
# Restart, then:
xhost +localhost
export DISPLAY=host.docker.internal:0
docker compose -f docker/docker-compose.tron1.yml up
```

### RViz2 (robot visualization only)
```bash
docker exec -it anima_tron1_sim rviz2
# Load the TRON1 URDF model
# Shows joint states, tf frames, sensor data
```

## File Locations
- Recordings: `docker/recordings/`
- TRON1 URDF: `sim/TRON1/TRON1A/PF_TRON1A/urdf/robot.urdf`
- TRON1 MJCF: `sim/TRON1/TRON1A/PF_TRON1A/xml/robot.xml`
- Launch file: `docker/tron1_launch/launch/tron1_sim.launch.py`
