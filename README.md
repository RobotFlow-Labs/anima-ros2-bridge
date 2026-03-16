# ANIMA ROS2 Bridge

> **Direct DDS + WebSocket bridge between AI agents and ROS2 robots.**
> The fastest path from natural language to robot action.

[![Python 3.14](https://img.shields.io/badge/python-3.14-blue.svg)](https://www.python.org/)
[![ROS2 Humble](https://img.shields.io/badge/ROS2-Humble-green.svg)](https://docs.ros.org/en/humble/)
[![License](https://img.shields.io/badge/license-Proprietary-red.svg)](LICENSE)

**Copyright (c) 2026 AIFLOW LABS LIMITED / [RobotFlowLabs](https://robotflowlabs.com)**

---

## What Is This?

ANIMA ROS2 Bridge connects AI agents (LLMs like Claude, GPT, Ollama) to ROS2 robots with two transport modes:

| Mode | Transport | Latency | Use Case |
|------|-----------|---------|----------|
| **Direct DDS** | rclpy → CycloneDDS | **<1ms** | Production, same network |
| **WebSocket** | rosbridge protocol v2 | 5-50ms | Universal, any network |

Switch between them with a single env var. No code changes.

```bash
# Direct DDS — fastest, production-grade
docker compose -f docker/docker-compose.dds.yml up

# WebSocket — universal compatibility
docker compose -f docker/docker-compose.ws.yml up
```

## Features

- **Two transports, one interface** — Direct DDS for speed, WebSocket for compatibility
- **7 ROS2 tools** — publish, subscribe, service call, action goal, parameters, camera snapshot, topic discovery
- **Safety validator** — 3D workspace bounds, velocity limits, joint limits, gripper force checks
- **Robot context injection** — auto-discovers capabilities, injects into AI agent prompt
- **Emergency stop** — bypasses AI, immediately zeroes all velocity commands
- **MCAP logging** — auto-record sessions for training data flywheel
- **Docker-first** — two compose files, zero configuration
- **Python 3.14** — free-threading for maximum concurrency

## Architecture

```
AI Agent (Claude / GPT / Ollama)
       │
       │  MCP tools / function calls
       │
┌──────┴──────────────────────────────────────┐
│           ANIMA ROS2 Bridge                  │
│                                              │
│  ┌─────────────┐  ┌──────────────────────┐  │
│  │ Safety      │  │ Robot Context        │  │
│  │ Validator   │  │ Builder              │  │
│  │ (pre-exec)  │  │ (capability → prompt)│  │
│  └──────┬──────┘  └──────────────────────┘  │
│         │                                    │
│  ┌──────┴──────────────────────────────┐    │
│  │        Transport Abstraction        │    │
│  │                                     │    │
│  │   Mode A          Mode B           │    │
│  │   Direct DDS      WebSocket        │    │
│  │   (rclpy)         (rosbridge)      │    │
│  │   <1ms            5-50ms           │    │
│  └─────────────────────────────────────┘    │
│                                              │
└──────────────────────────────────────────────┘
       │
       │  ROS2 DDS / WebSocket
       │
┌──────┴──────┐
│  ROS2 Robot  │
│  Topics      │
│  Services    │
│  Actions     │
└─────────────┘
```

## Quick Start

### Local Development (no Docker)

```bash
# Install
uv sync

# Run with Direct DDS (requires ROS2 on the machine)
uv run python -m anima_bridge --transport direct_dds

# Run with WebSocket (requires rosbridge_server running)
uv run python -m anima_bridge --transport rosbridge --url ws://localhost:9090
```

### Docker (recommended)

```bash
# WebSocket mode — includes ROS2 + rosbridge + bridge
docker compose -f docker/docker-compose.ws.yml up

# Direct DDS mode — bridge connects to host ROS2 network
docker compose -f docker/docker-compose.dds.yml up

# Development mode — with live reload
docker compose -f docker/docker-compose.ws.yml -f docker/docker-compose.dev.yml up
```

## ROS2 Tools

| Tool | Description | Safety Level |
|------|-------------|-------------|
| `ros2_publish` | Publish to any ROS2 topic | Validated (safety checks) |
| `ros2_subscribe_once` | Read one message with timeout | Read-only |
| `ros2_service_call` | Call any ROS2 service | Validated |
| `ros2_action_goal` | Send action goal with feedback | Validated |
| `ros2_param_get` | Get node parameter | Read-only |
| `ros2_param_set` | Set node parameter | Validated |
| `ros2_camera_snapshot` | Capture camera frame (base64) | Read-only |
| `ros2_list_topics` | Discover available topics | Read-only |

## Safety

Every command passes through the **SafetyValidator** before reaching ROS2:

- **Velocity limits** — linear and angular speed magnitude checked
- **3D workspace bounds** — x/y/z position checked against configured limits
- **Joint velocity limits** — per-joint speed checked (configurable per robot)
- **Gripper force limits** — maximum force checked
- **Emergency stop** — `/estop` command bypasses AI, zeroes all velocities immediately

```python
from anima_bridge.safety.validator import SafetyValidator
from anima_bridge.config import SafetySettings

validator = SafetyValidator(SafetySettings(
    max_linear_velocity=1.0,      # m/s
    max_angular_velocity=1.5,     # rad/s
    max_gripper_force=40.0,       # N
))

ok, reason = validator.validate("ros2_publish", {
    "msg_type": "geometry_msgs/msg/Twist",
    "message": {"linear": {"x": 5.0}},  # Too fast!
})
# ok=False, reason="Linear velocity 5.00 m/s exceeds limit of 1.0 m/s"
```

## Configuration

All settings via environment variables (Docker-friendly):

| Variable | Default | Description |
|----------|---------|-------------|
| `ANIMA_TRANSPORT_MODE` | `direct_dds` | `direct_dds` or `rosbridge` |
| `ANIMA_ROSBRIDGE_URL` | `ws://localhost:9090` | WebSocket URL |
| `ANIMA_DDS_DOMAIN_ID` | `0` | ROS2 DDS domain |
| `ANIMA_ROBOT_NAME` | `Robot` | Robot name for context |
| `ANIMA_ROBOT_NAMESPACE` | `` | ROS2 namespace prefix |
| `ANIMA_MAX_LINEAR_VELOCITY` | `1.0` | Max linear speed (m/s) |
| `ANIMA_MAX_ANGULAR_VELOCITY` | `1.5` | Max angular speed (rad/s) |
| `ANIMA_LOG_LEVEL` | `INFO` | Logging level |
| `ANIMA_MCAP_ENABLED` | `false` | Enable MCAP recording |

## Project Structure

```
anima-ros2-bridge/
├── anima_bridge/              # Main Python package
│   ├── config.py              # Pydantic v2 configuration
│   ├── transport_manager.py   # Transport singleton + mode switching
│   ├── tools/                 # 7 ROS2 tools
│   ├── safety/                # Safety validator
│   ├── context/               # Robot context builder
│   ├── commands/              # E-stop + transport switch
│   └── transport/             # Transport abstraction
│       ├── base.py            # AnimaTransport ABC
│       ├── direct_dds.py      # Mode A: rclpy Direct DDS
│       ├── entity_cache.py    # Thread-safe entity caching
│       ├── factory.py         # Transport factory
│       └── rosbridge/         # Mode B: WebSocket rosbridge
│           ├── client.py      # WebSocket client + reconnect
│           └── adapter.py     # RosbridgeTransport
├── docker/                    # Docker infrastructure
│   ├── docker-compose.ws.yml  # WebSocket mode
│   ├── docker-compose.dds.yml # Direct DDS mode
│   ├── Dockerfile.ros2        # ROS2 base image
│   └── Dockerfile.bridge      # Bridge image
├── tests/                     # Test suite
├── pyproject.toml             # Python 3.14, uv
└── README.md
```

## Testing

```bash
# Unit tests (no ROS2 required)
uv run pytest tests/ -v

# Lint
ruff check anima_bridge/ tests/

# Type check
mypy anima_bridge/
```

## Part of ANIMA

This bridge is a component of **ANIMA** (Autonomous Neural Intelligence for Machine Awareness) — the Robotics Intelligence Compiler by AIFLOW LABS LIMITED. ANIMA compiles AI agent intent into deterministic, real-time robot pipelines.

Learn more at [robotflowlabs.com](https://robotflowlabs.com)

---

*Built with AI agents. Powered by ROS2. Made for robots.*
