# Architecture

> Copyright (c) 2026 AIFLOW LABS LIMITED / RobotFlowLabs. All rights reserved.

## Overview

ANIMA ROS2 Bridge is a two-transport bridge between AI agents and ROS2 robots.

```mermaid
graph TB
    subgraph AGENT["AI Agent"]
        MCP[MCP Server]
        CLI[CLI Interface]
    end

    subgraph BRIDGE["ANIMA ROS2 Bridge"]
        SAFETY[Safety Validator]
        CONTEXT[Robot Context Builder]
        DISCOVERY[Smart Discovery Engine]
        subgraph TRANSPORT["Transport Layer"]
            DDS[Direct DDS — rclpy<br/>less than 1ms]
            WS[WebSocket — rosbridge<br/>5-50ms]
        end
    end

    subgraph ROBOT["ROS2 Robot"]
        TOPICS[Topics / Services / Actions]
    end

    AGENT --> SAFETY --> TRANSPORT --> ROBOT
    CONTEXT -.-> AGENT
    DISCOVERY -.-> CONTEXT
```

## Transport Modes

### Mode A: Direct DDS (Default)

Uses `rclpy` to connect directly to the ROS2 DDS network. Sub-millisecond latency. Requires the bridge to be on the same network as the robot.

```
Agent → AnimaTransport.publish() → rclpy Publisher → CycloneDDS → Robot
```

### Mode B: WebSocket (Rosbridge)

Uses the rosbridge v2 WebSocket protocol. Works over any network. 5-50ms latency depending on payload size.

```
Agent → AnimaTransport.publish() → WebSocket → rosbridge_server → DDS → Robot
```

## Component Diagram

```mermaid
graph LR
    subgraph anima_bridge
        CONFIG[config.py<br/>Pydantic v2]
        MANAGER[transport_manager.py<br/>Singleton + switching]

        subgraph tools
            PUB[ros2_publish]
            SUB[ros2_subscribe]
            SRV[ros2_service]
            ACT[ros2_action]
            PAR[ros2_param]
            CAM[ros2_camera]
            INT[ros2_introspect]
        end

        subgraph safety
            VAL[validator.py<br/>velocity + workspace<br/>+ joints + force<br/>+ service denylist]
        end

        subgraph discovery
            SCAN[scanner.py<br/>capability scan + health]
            FINGER[fingerprint.py<br/>robot identification]
        end

        subgraph transport
            BASE[base.py — ABC]
            DDS_T[direct_dds.py<br/>rclpy native]
            WS_T[rosbridge/<br/>WebSocket client]
            CACHE[entity_cache.py<br/>thread-safe]
        end
    end
```

## Data Flow

### Tool Call (e.g., publish velocity)

```mermaid
sequenceDiagram
    participant Agent
    participant MCP as MCP Server
    participant Safety as Safety Validator
    participant Manager as Transport Manager
    participant Transport as DDS/WebSocket
    participant ROS2 as Robot

    Agent->>MCP: ros2_publish("/cmd_vel", Twist, {x: 0.5})
    MCP->>Safety: validate("ros2_publish", args)
    Safety-->>MCP: (True, "ok") or (False, "blocked")
    MCP->>Manager: get_transport()
    Manager-->>MCP: DirectDdsTransport
    MCP->>Transport: publish(options)
    Transport->>ROS2: DDS message
    ROS2-->>Transport: ack
    Transport-->>MCP: PublishResult(success=True)
    MCP-->>Agent: {"success": true}
```

### Discovery Flow

```mermaid
sequenceDiagram
    participant CLI as anima-bridge discover
    participant Scanner as CapabilityScanner
    participant Transport as Transport
    participant Fingerprint as RobotFingerprinter
    participant ROS2 as ROS2 Graph

    CLI->>Scanner: scan(force=True)
    Scanner->>Transport: list_topics() + list_services() + list_actions()
    Transport->>ROS2: graph introspection
    ROS2-->>Transport: topics, services, actions
    Transport-->>Scanner: lists
    Scanner->>Fingerprint: fingerprint(topics, services, actions)
    Fingerprint-->>Scanner: RobotFingerprint(category, vendor, sensors, controls)
    Scanner-->>CLI: ScanResult + fingerprint + health + manifest
```

## Thread Safety

The Direct DDS transport uses two threads:

1. **asyncio event loop** — handles all async calls from tools/CLI
2. **rclpy spin thread** — runs the ROS2 executor in background

Communication between threads uses `asyncio.get_running_loop().call_soon_threadsafe()` for callbacks and `loop.run_in_executor()` for blocking rclpy calls.

All entity caches (publishers, subscribers, service clients) are protected by `threading.Lock`.

## Safety Architecture

Every tool call passes through the `SafetyValidator` before reaching ROS2:

| Check | Tools Affected | What's Validated |
|-------|---------------|------------------|
| Velocity magnitude | `ros2_publish` (Twist) | linear + angular speed vs limits |
| 3D workspace bounds | `ros2_publish` (Pose), `ros2_action_goal` | x/y/z position vs bounds |
| Joint velocity | `ros2_publish` (JointState) | per-joint speed vs limits |
| Gripper force | `ros2_publish` | force vs max_gripper_force |
| Parameter guard | `ros2_param_set` | velocity/force param names |
| Service denylist | `ros2_service_call` | blocked: shutdown, reboot, etc. |
| E-stop | `emergency_stop` | bypasses ALL checks, zeros velocity |

The e-stop has a dedicated rclpy fallback path that works even when the main transport is down.
