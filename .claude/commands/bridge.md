# ANIMA ROS2 Bridge — Project Control Skill

Working directory: `/Users/ilessio/Development/AIFLOWLABS/projects/anima-ros2-bridge/`
Session: `33134c3e-82c0-49c6-9eda-8c5cd2d3c47e`

## Rules
1. All code files under 480 lines
2. `ruff check` must pass with zero errors
3. `uv run pytest tests/` must pass with zero failures
4. Copyright: `Copyright (c) 2026 AIFLOW LABS LIMITED / RobotFlowLabs`
5. Python 3.14, StrEnum, modern syntax
6. Docker containers use `anima_` prefix
7. 100% original IP

## Development
```bash
uv run pytest tests/ -v            # Run tests
ruff check anima_bridge/ tests/    # Lint
ruff format anima_bridge/ tests/   # Format
```

## Docker Modes
```bash
# WebSocket mode (universal)
docker compose -f docker/docker-compose.ws.yml up

# Direct DDS mode (fastest)
docker compose -f docker/docker-compose.dds.yml up

# TRON1 biped demo (impressive)
docker compose -f docker/docker-compose.tron1.yml up

# Dev mode (live reload)
docker compose -f docker/docker-compose.ws.yml -f docker/docker-compose.dev.yml up
```

## CLI (all commands)
```bash
anima-bridge serve                 # MCP server for AI agents
anima-bridge serve --mode sse      # MCP via SSE
anima-bridge discover              # Auto-discover + fingerprint robot
anima-bridge discover --manifest   # Output hardware_manifest.yaml
anima-bridge topics                # List ROS2 topics
anima-bridge publish TOPIC TYPE MSG  # Publish to topic
anima-bridge subscribe TOPIC       # Read one message
anima-bridge service SRV           # Call service
anima-bridge camera                # Capture frame
anima-bridge estop                 # Emergency stop
anima-bridge status                # Transport status
```

## Simulator Control (TRON1)
```bash
# Start simulation
docker compose -f docker/docker-compose.tron1.yml up -d

# View in browser
open http://localhost:8080

# Walk forward
anima-bridge --transport rosbridge --url ws://localhost:9090 \
  publish /cmd_vel geometry_msgs/msg/Twist '{"linear":{"x":0.3}}'

# Turn
anima-bridge --transport rosbridge --url ws://localhost:9090 \
  publish /cmd_vel geometry_msgs/msg/Twist '{"angular":{"z":0.5}}'

# Stop
anima-bridge --transport rosbridge --url ws://localhost:9090 estop

# Camera snapshot
anima-bridge --transport rosbridge --url ws://localhost:9090 \
  camera --output frame.jpg

# Record video (Gazebo built-in)
docker exec anima_tron1_sim gz service -s /gui/record_video \
  --reqtype gz.msgs.VideoRecord --reptype gz.msgs.Boolean \
  --req 'start:true, save_filename:"/recordings/demo.mp4"' --timeout 3000

# Stop recording
docker exec anima_tron1_sim gz service -s /gui/record_video \
  --reqtype gz.msgs.VideoRecord --reptype gz.msgs.Boolean \
  --req 'stop:true' --timeout 3000
```

## Video Recording for Marketing
```bash
# Method 1: Mac screen recording (best quality)
# Cmd+Shift+5 → Record Selected Window → select browser at localhost:8080

# Method 2: ffmpeg screen capture
ffmpeg -f avfoundation -framerate 30 -i "1" -t 60 -c:v h264 tron1_demo.mp4

# Method 3: Gazebo internal recording (see above)

# Method 4: ROS2 bag → video
docker exec anima_tron1_sim ros2 bag record /camera/image_raw -o /recordings/bag
```

## Architecture
- `anima_bridge/transport/` — DDS + WebSocket transports
- `anima_bridge/tools/` — 7 ROS2 tools
- `anima_bridge/safety/` — Safety validator (velocity, workspace, joints, force, service denylist)
- `anima_bridge/discovery/` — Smart discovery + fingerprinting
- `anima_bridge/context/` — Robot context → agent prompt
- `anima_bridge/commands/` — E-stop + transport switch
- `anima_bridge/mcp_server.py` — MCP server (9 tools)
- `anima_bridge/openclaw_plugin.py` — OpenClaw compatibility
- `anima_bridge/cli.py` — Full CLI
- `sim/` — TRON1 URDF/MJCF models
- `docker/` — All Docker infrastructure

## Git
```bash
git add -A && git commit -m "feat: description" && git push origin main
```
