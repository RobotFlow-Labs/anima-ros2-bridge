# ANIMA ROS2 Bridge

## Overview
Direct DDS bridge between the ANIMA Intelligence Compiler agent and ROS2 robots. Python 3.12+, rclpy-native, zero middleware. Replaces rosbridge WebSocket overhead with direct DDS communication for <1ms latency.

## Project Structure

```
anima-ros2-bridge/
├── anima_bridge/              # Main Python package
│   ├── config.py              # Pydantic v2 configuration
│   ├── transport_manager.py   # Transport singleton + mode switching
│   ├── tools/                 # MCP/Agent tools (7 tools)
│   │   ├── ros2_publish.py
│   │   ├── ros2_subscribe.py
│   │   ├── ros2_service.py
│   │   ├── ros2_action.py
│   │   ├── ros2_param.py
│   │   ├── ros2_introspect.py
│   │   └── ros2_camera.py
│   ├── safety/                # Safety validation
│   │   └── validator.py       # 3D workspace + velocity + joint limits
│   ├── context/               # Agent context injection
│   │   └── robot_context.py   # Capability discovery → agent prompt
│   ├── commands/              # Direct commands (bypass agent)
│   │   ├── estop.py
│   │   └── transport_cmd.py
│   └── transport/             # Transport abstraction
│       ├── types.py           # Shared types
│       ├── base.py            # Abstract transport interface
│       ├── factory.py         # Transport factory
│       ├── direct_dds.py      # Mode A: rclpy Direct DDS (DEFAULT)
│       └── rosbridge/         # Mode B: WebSocket rosbridge
│           ├── client.py
│           ├── topics.py
│           ├── services.py
│           ├── actions.py
│           └── adapter.py
├── anima_msgs/                # Custom ROS2 messages
│   ├── msg/
│   ├── srv/
│   ├── CMakeLists.txt
│   └── package.xml
├── anima_discovery/           # ROS2 capability discovery node
│   └── discovery_node.py
├── docker/                    # Docker infrastructure
├── tests/                     # Test suite
├── repositories/              # Reference repos (study only, not deployed)
│   ├── rosclaw/               # ROSClaw (MIT, reference patterns)
│   ├── openclaw/              # OpenClaw (MIT, agent patterns)
│   ├── OpenClaw-RL/           # RL framework (MIT, marketing)
│   └── dimos/                 # DimOS (reference architecture)
└── pyproject.toml
```

## Dev Commands

```bash
# Install
uv sync

# Run bridge (Direct DDS mode)
python -m anima_bridge --transport direct_dds

# Run bridge (Rosbridge mode, for dev/testing)
python -m anima_bridge --transport rosbridge --url ws://localhost:9090

# Test
pytest tests/

# Lint
ruff check anima_bridge/
ruff format anima_bridge/

# Type check
mypy anima_bridge/

# Docker
docker compose -f docker/docker-compose.yml up
```

## Conventions
- Python 3.12+, targeting 3.14 (free-threading)
- Package manager: `uv`
- Validation: `pydantic` v2
- Linting: `ruff` (line-length=100)
- Type checking: `mypy` (strict)
- Testing: `pytest` + `pytest-asyncio`
- Use `rg` (ripgrep) instead of `grep`
- All code is original IP — inspired by ROSClaw patterns but rewritten from scratch
- Transport default: Direct DDS (Mode A), rosbridge available as Mode B

## Key Dependencies
- `rclpy` — ROS2 Python client (from apt, not pip)
- `pydantic>=2.0` — config validation
- `websockets>=12.0` — rosbridge client (Mode B)
- `mcap>=1.0` — data logging format

## Architecture
- **Mode A (Direct DDS)**: rclpy → CycloneDDS → robot. Default. <1ms latency.
- **Mode B (Rosbridge)**: WebSocket → rosbridge_server → DDS. For remote dev. 5-50ms.
- **Safety Validator**: Pre-execution checks on ALL tool calls (velocity, workspace, joints, force)
- **Context Injection**: Auto-discovers robot capabilities, injects into agent system prompt

## IP Notes
- All code in anima_bridge/ is original, written by AIFLOW LABS LIMITED
- Inspired by ROSClaw (MIT) patterns — studied, not copied
- repositories/ folder contains reference code for study only
- Custom ROS2 messages (anima_msgs) are our own definitions

# currentDate
Today's date is 2026-03-16.
