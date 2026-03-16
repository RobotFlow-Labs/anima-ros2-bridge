"""ANIMA ROS2 Bridge — CLI tool commands.

Exposes all bridge tools as CLI commands for direct human/script usage.
Same tools available via MCP server for AI agents.

Copyright (c) 2026 AIFLOW LABS LIMITED / RobotFlowLabs. All rights reserved.

Usage:
    anima-bridge serve                    # Start MCP server for AI agents
    anima-bridge discover                 # Auto-discover robot + fingerprint
    anima-bridge publish /cmd_vel ...     # Publish to topic
    anima-bridge subscribe /odom          # Read one message
    anima-bridge topics                   # List available topics
    anima-bridge camera                   # Capture camera frame
    anima-bridge estop                    # Emergency stop
    anima-bridge status                   # Transport status
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys

from anima_bridge.config import AnimaBridgeConfig

logger = logging.getLogger("anima_bridge.cli")


def _add_transport_args(parser: argparse.ArgumentParser) -> None:
    """Add common transport arguments to a subparser."""
    parser.add_argument(
        "--transport",
        choices=["direct_dds", "rosbridge"],
        default=None,
        help="Transport mode (default: from env or direct_dds)",
    )
    parser.add_argument("--url", default=None, help="Rosbridge URL")
    parser.add_argument("--domain-id", type=int, default=None, help="DDS domain ID")


def build_parser() -> argparse.ArgumentParser:
    """Build the full CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="anima-bridge",
        description="ANIMA ROS2 Bridge — AI-powered robotics bridge",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default=None,
        help="Log level",
    )

    sub = parser.add_subparsers(dest="command", help="Available commands")

    # serve — start MCP server
    p_serve = sub.add_parser("serve", help="Start MCP server for AI agents")
    _add_transport_args(p_serve)
    p_serve.add_argument("--port", type=int, default=8765, help="MCP server SSE port")
    p_serve.add_argument(
        "--mode",
        choices=["stdio", "sse"],
        default="stdio",
        help="MCP transport mode (default: stdio)",
    )

    # discover — auto-discover robot
    p_discover = sub.add_parser("discover", help="Auto-discover robot and fingerprint")
    _add_transport_args(p_discover)
    p_discover.add_argument("--manifest", action="store_true", help="Output as YAML manifest")

    # publish — publish to topic
    p_pub = sub.add_parser("publish", help="Publish message to ROS2 topic")
    _add_transport_args(p_pub)
    p_pub.add_argument("topic", help="Topic name (e.g. /cmd_vel)")
    p_pub.add_argument("msg_type", help="Message type (e.g. geometry_msgs/msg/Twist)")
    p_pub.add_argument("message", help="Message as JSON string")

    # subscribe — read one message
    p_sub = sub.add_parser("subscribe", help="Read one message from topic")
    _add_transport_args(p_sub)
    p_sub.add_argument("topic", help="Topic name")
    p_sub.add_argument("--type", dest="msg_type", default=None, help="Message type")
    p_sub.add_argument("--timeout", type=int, default=5000, help="Timeout in ms")

    # topics — list topics
    p_topics = sub.add_parser("topics", help="List available ROS2 topics")
    _add_transport_args(p_topics)

    # service — call service
    p_srv = sub.add_parser("service", help="Call a ROS2 service")
    _add_transport_args(p_srv)
    p_srv.add_argument("service_name", help="Service name")
    p_srv.add_argument("--type", dest="srv_type", default=None, help="Service type")
    p_srv.add_argument("--args", default="{}", help="Service args as JSON")

    # camera — capture frame
    p_cam = sub.add_parser("camera", help="Capture camera frame")
    _add_transport_args(p_cam)
    p_cam.add_argument("--topic", default="/camera/image_raw/compressed", help="Camera topic")
    p_cam.add_argument("--output", default=None, help="Save to file (otherwise base64 to stdout)")

    # estop — emergency stop
    p_estop = sub.add_parser("estop", help="Emergency stop — zero all velocities")
    _add_transport_args(p_estop)
    p_estop.add_argument("--namespace", default="", help="Robot namespace")

    # status — transport status
    sub.add_parser("status", help="Show transport connection status")

    return parser


async def _run_command(args: argparse.Namespace) -> None:
    """Execute the parsed CLI command."""
    from anima_bridge.__main__ import config_from_env
    from anima_bridge.transport_manager import connect, disconnect

    # Build config dict from env, then apply CLI overrides before construction
    base_config = config_from_env()
    overrides: dict[str, object] = {}

    if hasattr(args, "transport") and args.transport:
        from anima_bridge.config import TransportMode, TransportSettings

        overrides["transport"] = TransportSettings(mode=TransportMode(args.transport))
    if hasattr(args, "url") and args.url:
        from anima_bridge.config import RosbridgeSettings

        rb = base_config.rosbridge.model_dump()
        rb["url"] = args.url
        overrides["rosbridge"] = RosbridgeSettings(**rb)
    if hasattr(args, "domain_id") and args.domain_id is not None:
        from anima_bridge.config import DirectDdsSettings

        overrides["direct_dds"] = DirectDdsSettings(domain_id=args.domain_id)

    if overrides:
        merged = base_config.model_dump()
        for key, val in overrides.items():
            merged[key] = val.model_dump() if hasattr(val, "model_dump") else val
        config = AnimaBridgeConfig.model_validate(merged)
    else:
        config = base_config

    if args.command == "status":
        from anima_bridge.commands.transport_cmd import get_transport_status

        result = await get_transport_status()
        print(json.dumps(result, indent=2))
        return

    # Commands that need transport connected
    await connect(config)

    try:
        if args.command == "discover":
            await _cmd_discover(args)
        elif args.command == "publish":
            await _cmd_publish(args)
        elif args.command == "subscribe":
            await _cmd_subscribe(args)
        elif args.command == "topics":
            await _cmd_topics()
        elif args.command == "service":
            await _cmd_service(args)
        elif args.command == "camera":
            await _cmd_camera(args)
        elif args.command == "estop":
            await _cmd_estop(args)
        elif args.command == "serve":
            await _cmd_serve(args, config)
    finally:
        await disconnect()


async def _cmd_discover(args: argparse.Namespace) -> None:
    from anima_bridge.discovery.scanner import CapabilityScanner

    scanner = CapabilityScanner()
    result = await scanner.scan(force=True)

    if args.manifest:
        print(scanner.generate_manifest_yaml(result))
    else:
        if result.fingerprint:
            from anima_bridge.discovery.fingerprint import RobotFingerprinter

            printer = RobotFingerprinter()
            print(printer.format_report(result.fingerprint))
        print(f"\nTopics: {len(result.topics)}")
        print(f"Services: {len(result.services)}")
        print(f"Actions: {len(result.actions)}")
        print(f"Scan time: {result.scan_time_ms:.1f}ms")


async def _cmd_publish(args: argparse.Namespace) -> None:
    from anima_bridge.tools.ros2_publish import ros2_publish

    message = json.loads(args.message)
    result = await ros2_publish(args.topic, args.msg_type, message)
    print(json.dumps(result, indent=2))


async def _cmd_subscribe(args: argparse.Namespace) -> None:
    from anima_bridge.tools.ros2_subscribe import ros2_subscribe_once

    result = await ros2_subscribe_once(args.topic, args.msg_type, args.timeout)
    print(json.dumps(result, indent=2))


async def _cmd_topics() -> None:
    from anima_bridge.tools.ros2_introspect import ros2_list_topics

    result = await ros2_list_topics()
    if result.get("success"):
        for t in result.get("topics", []):
            print(f"  {t['name']:40s} {t['type']}")
    else:
        print(f"Error: {result.get('error')}")


async def _cmd_service(args: argparse.Namespace) -> None:
    from anima_bridge.tools.ros2_service import ros2_service_call

    srv_args = json.loads(args.args)
    result = await ros2_service_call(args.service_name, args.srv_type, srv_args)
    print(json.dumps(result, indent=2))


async def _cmd_camera(args: argparse.Namespace) -> None:
    import base64

    from anima_bridge.tools.ros2_camera import ros2_camera_snapshot

    result = await ros2_camera_snapshot(args.topic)
    if result.get("success") and args.output:
        data = base64.b64decode(result["data"])
        with open(args.output, "wb") as f:
            f.write(data)
        print(f"Saved {len(data)} bytes to {args.output}")
    else:
        print(json.dumps(result, indent=2))


async def _cmd_estop(args: argparse.Namespace) -> None:
    from anima_bridge.commands.estop import emergency_stop

    result = await emergency_stop(args.namespace)
    print(json.dumps(result, indent=2))


async def _cmd_serve(args: argparse.Namespace, config: AnimaBridgeConfig) -> None:
    """Start the MCP server."""
    try:
        from anima_bridge.mcp_server import AnimaMcpServer

        server = AnimaMcpServer(config)
        mode = getattr(args, "mode", "stdio")
        if mode == "sse":
            await server.run_sse(port=args.port)
        else:
            await server.run_stdio()
    except ImportError:
        logger.error("MCP server not available. Install mcp package: uv add mcp")
        sys.exit(1)


def cli_main() -> None:
    """CLI entry point."""
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    log_level = args.log_level or "INFO"
    logging.basicConfig(
        level=getattr(logging, log_level),
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    asyncio.run(_run_command(args))
