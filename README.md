# ANIMA ROS2 Bridge

> **Direct DDS + WebSocket bridge between AI agents and ROS2 robots.**
> The fastest path from natural language to robot action.

[![Python 3.14](https://img.shields.io/badge/python-3.14-blue.svg)](https://www.python.org/)
[![ROS2 Humble](https://img.shields.io/badge/ROS2-Humble-green.svg)](https://docs.ros.org/en/humble/)
[![Tests](https://img.shields.io/badge/tests-74%20passed-brightgreen.svg)]()
[![License](https://img.shields.io/badge/license-Proprietary-red.svg)](LICENSE)

**Copyright (c) 2026 AIFLOW LABS LIMITED / [RobotFlowLabs](https://robotflowlabs.com)**

---

## Overview

ANIMA ROS2 Bridge connects AI agents to ROS2 robots with two transport modes:

| Mode | Transport | Latency | Use Case |
|------|-----------|---------|----------|
| **Direct DDS** | rclpy → CycloneDDS | **<1ms** | Production, same network |
| **WebSocket** | rosbridge v2 | 5-50ms | Universal, any network |

Switch with one env var. No code changes.

```bash
# Direct DDS — production speed
docker compose -f docker/docker-compose.dds.yml up

# WebSocket — universal compatibility
docker compose -f docker/docker-compose.ws.yml up
```

---

## Architecture

```mermaid
graph TB
    subgraph AGENT["AI Agent (Claude / GPT / Ollama)"]
        A1[Natural Language Intent]
    end

    subgraph BRIDGE["ANIMA ROS2 Bridge"]
        direction TB
        MCP[MCP Server<br/>9 tools exposed]
        CLI[CLI Interface<br/>discover / publish / subscribe]
        SAFETY[Safety Validator<br/>velocity + workspace + joints + force]
        CONTEXT[Robot Context Builder<br/>auto-discovery → prompt injection]

        subgraph TRANSPORT["Transport Layer"]
            DDS[Mode A: Direct DDS<br/>rclpy — less than 1ms]
            WS[Mode B: WebSocket<br/>rosbridge — 5-50ms]
        end
    end

    subgraph ROBOT["ROS2 Robot"]
        TOPICS[Topics / Services / Actions]
    end

    AGENT --> MCP
    AGENT --> CLI
    MCP --> SAFETY
    CLI --> SAFETY
    SAFETY --> TRANSPORT
    CONTEXT -.->|capabilities| MCP
    DDS --> TOPICS
    WS --> TOPICS

    style AGENT fill:#1A1A1A,color:#FF3B00,stroke:#FF3B00
    style BRIDGE fill:#050505,color:#f3f3f3,stroke:#FF3B00
    style ROBOT fill:#1A1A1A,color:#f3f3f3,stroke:#FF3B00
    style SAFETY fill:#FF3B00,color:#050505
```

---

## Smart Discovery Engine

```mermaid
graph LR
    PLUG[Plug in ANY<br/>ROS2 Robot] --> SCAN[Scan Graph<br/>topics / services / actions]
    SCAN --> FINGER[Fingerprint<br/>identify type + vendor]
    FINGER --> DETECT[Detect<br/>sensors + controls]
    DETECT --> RECOMMEND[Recommend<br/>ANIMA modules]
    RECOMMEND --> MANIFEST[Generate<br/>hardware_manifest.yaml]

    style PLUG fill:#f3f3f3,color:#050505,stroke:#050505
    style FINGER fill:#FF3B00,color:#050505
    style RECOMMEND fill:#FF3B00,color:#050505
    style MANIFEST fill:#050505,color:#FF3B00,stroke:#FF3B00
```

Auto-identifies 15+ robot vendors including Unitree, LimX Dynamics, Boston Dynamics, UFactory, Franka, Clearpath, and more. Detects sensors (RGB, depth, LiDAR, IMU, F/T), control interfaces (velocity, joints, Nav2, MoveIt, gripper), and recommends which ANIMA modules to use.

---

## Safety Architecture

```mermaid
graph TD
    TOOL[Tool Call from Agent] --> GATE{Safety Validator}
    GATE -->|PASS| EXEC[Execute on Robot]
    GATE -->|BLOCK| REJECT[Reject + Reason]

    GATE --> V1[Velocity Check<br/>linear + angular magnitude]
    GATE --> V2[Workspace Check<br/>3D bounds x/y/z]
    GATE --> V3[Joint Limits<br/>per-joint velocity]
    GATE --> V4[Gripper Force<br/>max Newton check]
    GATE --> V5[Service Denylist<br/>block shutdown/reboot/etc]
    GATE --> V6[Param Guard<br/>velocity/force params]

    ESTOP[E-STOP] -->|bypass ALL| ZERO[Zero Velocity<br/>+ rclpy fallback]

    style GATE fill:#FF3B00,color:#050505
    style ESTOP fill:#FF0000,color:#fff
    style REJECT fill:#1A1A1A,color:#FF3B00
```

Every tool call passes through the SafetyValidator before reaching ROS2. The emergency stop has a dedicated rclpy fallback path that works even when the main transport is down.

---

## Data Flow

```mermaid
sequenceDiagram
    participant Agent as AI Agent
    participant MCP as MCP Server
    participant Safety as Safety Validator
    participant Transport as Transport Layer
    participant ROS2 as ROS2 Robot

    Agent->>MCP: ros2_publish("/cmd_vel", Twist, {linear: {x: 0.5}})
    MCP->>Safety: validate("ros2_publish", args)
    Safety-->>MCP: (True, "ok")
    MCP->>Transport: publish(options)

    alt Direct DDS (Mode A)
        Transport->>ROS2: rclpy publisher → DDS → robot (less than 1ms)
    else WebSocket (Mode B)
        Transport->>ROS2: websocket → rosbridge → DDS → robot (5-50ms)
    end

    ROS2-->>Transport: ack
    Transport-->>MCP: PublishResult(success=True)
    MCP-->>Agent: {"success": true, "topic": "/cmd_vel"}
```

---

## CLI Reference

```bash
# Start MCP server for AI agents
anima-bridge serve                              # stdio mode (default)
anima-bridge serve --mode sse --port 8765       # SSE mode

# Auto-discover robot
anima-bridge discover                           # Human-readable report
anima-bridge discover --manifest                # YAML hardware manifest

# Publish to topic
anima-bridge publish /cmd_vel geometry_msgs/msg/Twist '{"linear":{"x":0.5}}'

# Read one message
anima-bridge subscribe /odom --timeout 5000

# List topics
anima-bridge topics

# Call service
anima-bridge service /trigger_save --type std_srvs/srv/Trigger

# Capture camera frame
anima-bridge camera --output frame.jpg
anima-bridge camera --topic /camera/depth/image_raw

# Emergency stop
anima-bridge estop
anima-bridge estop --namespace /go2

# Transport status
anima-bridge status

# Transport selection (via args or env)
anima-bridge --transport direct_dds discover
anima-bridge --transport rosbridge --url ws://robot:9090 topics
```

---

## MCP Tools

```mermaid
graph LR
    subgraph READ["Read-Only (always safe)"]
        T1[ros2_list_topics]
        T2[ros2_subscribe_once]
        T3[ros2_camera_snapshot]
        T4[ros2_param_get]
    end

    subgraph VALIDATED["Safety Validated"]
        T5[ros2_publish]
        T6[ros2_service_call]
        T7[ros2_param_set]
    end

    subgraph SUPERVISED["Safety + Workspace Check"]
        T8[ros2_action_goal]
    end

    subgraph EMERGENCY["Bypass Everything"]
        T9[emergency_stop]
    end

    style READ fill:#1A1A1A,color:#f3f3f3,stroke:#666
    style VALIDATED fill:#1A1A1A,color:#FF3B00,stroke:#FF3B00
    style SUPERVISED fill:#FF3B00,color:#050505,stroke:#FF3B00
    style EMERGENCY fill:#FF0000,color:#fff,stroke:#FF0000
```

| Tool | Safety | Description |
|------|--------|-------------|
| `ros2_publish` | Validated | Publish to any ROS2 topic |
| `ros2_subscribe_once` | Read-only | Read one message with timeout |
| `ros2_service_call` | Validated + denylist | Call any ROS2 service |
| `ros2_action_goal` | Validated + workspace | Send action goal with feedback |
| `ros2_param_get` | Read-only | Get node parameter |
| `ros2_param_set` | Validated + param guard | Set node parameter |
| `ros2_camera_snapshot` | Read-only | Capture camera frame (base64) |
| `ros2_list_topics` | Read-only | Discover available topics |
| `emergency_stop` | Bypass all | Zero all velocities immediately |

---

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

---

## Docker

```mermaid
graph LR
    subgraph WS["docker-compose.ws.yml"]
        R1[anima_ros2<br/>ROS2 + rosbridge<br/>port 9090]
        B1[anima_bridge_ws<br/>WebSocket mode]
        R1 <--> B1
    end

    subgraph DDS["docker-compose.dds.yml"]
        B2[anima_bridge_dds<br/>Direct DDS<br/>network: host]
    end

    style WS fill:#1A1A1A,color:#f3f3f3,stroke:#FF3B00
    style DDS fill:#050505,color:#FF3B00,stroke:#FF3B00
```

```bash
# WebSocket mode (includes ROS2 + rosbridge)
docker compose -f docker/docker-compose.ws.yml up

# Direct DDS mode (connects to host ROS2)
docker compose -f docker/docker-compose.dds.yml up

# Development mode (live reload)
docker compose -f docker/docker-compose.ws.yml -f docker/docker-compose.dev.yml up
```

---

## Project Structure

```
anima-ros2-bridge/
├── anima_bridge/                  # Main Python package (6,562 LOC)
│   ├── __main__.py                # Entry point (env + CLI config)
│   ├── cli.py                     # Full CLI (discover/publish/subscribe/...)
│   ├── config.py                  # Pydantic v2 configuration
│   ├── mcp_server.py              # MCP server (9 tools for AI agents)
│   ├── openclaw_plugin.py         # OpenClaw compatibility wrapper
│   ├── transport_manager.py       # Transport singleton + switching
│   ├── discovery/                 # Smart Discovery Engine
│   │   ├── fingerprint.py         # Robot type + vendor identification
│   │   └── scanner.py             # Capability scanner + health monitoring
│   ├── tools/                     # 7 ROS2 tools
│   │   ├── ros2_publish.py
│   │   ├── ros2_subscribe.py
│   │   ├── ros2_service.py
│   │   ├── ros2_action.py
│   │   ├── ros2_param.py
│   │   ├── ros2_introspect.py
│   │   └── ros2_camera.py
│   ├── safety/                    # Safety validator
│   │   └── validator.py           # Velocity + workspace + joints + force + denylist
│   ├── context/                   # Robot context builder
│   │   └── robot_context.py       # Auto-discovery → agent prompt injection
│   ├── commands/                  # Direct commands
│   │   ├── estop.py               # Emergency stop (with rclpy fallback)
│   │   └── transport_cmd.py       # Runtime transport switching
│   └── transport/                 # Transport abstraction
│       ├── types.py               # Shared types
│       ├── base.py                # AnimaTransport ABC
│       ├── entity_cache.py        # Thread-safe entity caching
│       ├── direct_dds.py          # Mode A: rclpy Direct DDS
│       ├── factory.py             # Transport factory
│       └── rosbridge/             # Mode B: WebSocket
│           ├── client.py          # WS client + auto-reconnect
│           └── adapter.py         # RosbridgeTransport
├── anima_msgs/                    # Custom ROS2 messages
│   ├── msg/AnimaCapabilities.msg  # Rich capability manifest
│   └── srv/GetCapabilities.srv    # On-demand capability query
├── anima_discovery/               # ROS2 discovery node
│   └── discovery_node.py          # Periodic capability publisher
├── sim/                           # Simulation models
│   ├── TRON1/                     # LimX TRON1 biped (URDF + MJCF)
│   └── tron1_urdf/                # Multiple variants (PF/WF/SF)
├── docker/                        # Docker infrastructure
│   ├── docker-compose.ws.yml      # WebSocket mode
│   ├── docker-compose.dds.yml     # Direct DDS mode
│   ├── docker-compose.dev.yml     # Dev overrides
│   ├── Dockerfile.ros2            # ROS2 base image
│   └── Dockerfile.bridge          # Bridge image
├── tests/                         # 74 tests, 100% passing
│   └── unit/
│       ├── test_config.py
│       ├── test_transport_types.py
│       ├── test_safety_validator.py
│       └── test_tools.py
└── pyproject.toml                 # Python 3.14, uv, ruff, mypy
```

---

## Testing

```bash
# Unit tests (no ROS2 required)
uv run pytest tests/ -v

# Lint
ruff check anima_bridge/ tests/

# Format
ruff format anima_bridge/ tests/
```

**Current**: 74 tests passing, 0 ruff errors, all files under 480 lines.

---

## OpenClaw Compatibility

The bridge can be loaded as an OpenClaw plugin for multi-channel AI agent deployments:

```python
from anima_bridge.openclaw_plugin import get_plugin

plugin = get_plugin(config)
tools = plugin.get_tool_definitions()      # 9 tools for OpenClaw
context = await plugin.before_agent_start() # Robot capabilities
```

---

## Part of ANIMA

This bridge is a component of **ANIMA** — the Robotics Intelligence Compiler by AIFLOW LABS LIMITED.

**A**utonomous **N**eural **I**ntelligence for **M**achine **A**wareness

> "Compiles intelligence into speed."

Learn more at [robotflowlabs.com](https://robotflowlabs.com)

---

*Built with AI agents. Powered by ROS2. Made for robots.*
*Copyright (c) 2026 AIFLOW LABS LIMITED / RobotFlowLabs. All rights reserved.*
