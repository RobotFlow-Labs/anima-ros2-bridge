# Quick Start Guide

> Copyright (c) 2026 AIFLOW LABS LIMITED / RobotFlowLabs. All rights reserved.

## Installation

```bash
git clone https://github.com/RobotFlow-Labs/anima-ros2-bridge.git
cd anima-ros2-bridge
uv sync
```

## Option 1: Connect to an Existing ROS2 Robot

### Direct DDS (same network, fastest)

```bash
# Your robot must be running ROS2 on the same network
uv run anima-bridge discover --transport direct_dds
uv run anima-bridge topics --transport direct_dds
```

### WebSocket (any network)

```bash
# Your robot must be running rosbridge_server
uv run anima-bridge discover --transport rosbridge --url ws://ROBOT_IP:9090
uv run anima-bridge topics --transport rosbridge --url ws://ROBOT_IP:9090
```

## Option 2: Run the Simulation

```bash
# Requires Docker + the anima/sim image built from rlf-gazebo
docker compose -p anima_ros2_stack -f docker/docker-compose.sim.yml up -d

# Open the live viewer
open http://localhost:8080

# Use the CLI
uv run anima-bridge discover --transport rosbridge --url ws://localhost:9090
uv run anima-bridge topics --transport rosbridge --url ws://localhost:9090

# Drive the robot
uv run anima-bridge publish /cmd_vel geometry_msgs/msg/Twist \
  '{"linear":{"x":0.5},"angular":{"z":0.2}}' \
  --transport rosbridge --url ws://localhost:9090

# Emergency stop
uv run anima-bridge estop --transport rosbridge --url ws://localhost:9090

# Stop simulation
docker compose -p anima_ros2_stack -f docker/docker-compose.sim.yml down
```

## Option 3: MCP Server for AI Agents

```bash
# Start MCP server (Claude, GPT, or any MCP-compatible agent)
uv run anima-bridge serve --transport rosbridge --url ws://ROBOT_IP:9090

# Or SSE mode for web-based agents
uv run anima-bridge serve --mode sse --port 8765 \
  --transport rosbridge --url ws://ROBOT_IP:9090
```

## Environment Variables

All settings can be configured via environment variables:

```bash
export ANIMA_TRANSPORT_MODE=rosbridge     # or direct_dds
export ANIMA_ROSBRIDGE_URL=ws://localhost:9090
export ANIMA_ROBOT_NAME="My Robot"
export ANIMA_MAX_LINEAR_VELOCITY=1.0
export ANIMA_MAX_ANGULAR_VELOCITY=1.5
export ANIMA_LOG_LEVEL=INFO
```

## Docker Modes

| Command | Mode | Use Case |
|---------|------|----------|
| `docker compose -f docker/docker-compose.ws.yml up` | WebSocket | Connect to remote robot |
| `docker compose -f docker/docker-compose.dds.yml up` | Direct DDS | Same-machine robot |
| `docker compose -f docker/docker-compose.sim.yml up` | Simulation | Demo/testing with Gazebo |

## Next Steps

- [Architecture](architecture.md) — How it works internally
- [CLI Reference](cli-reference.md) — All CLI commands
- [Safety](safety.md) — Safety validator configuration
- [Discovery](discovery.md) — Smart robot discovery engine
- [Simulation](simulation.md) — Gazebo simulation setup
