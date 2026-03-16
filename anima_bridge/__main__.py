"""ANIMA ROS2 Bridge — Entry point.

Configurable via CLI args, environment variables, or both.
Env vars take precedence for Docker deployment, CLI args override for dev.

Usage:
    python -m anima_bridge
    python -m anima_bridge --transport direct_dds
    python -m anima_bridge --transport rosbridge --url ws://localhost:9090

Docker:
    docker compose -f docker/docker-compose.ws.yml up   # WebSocket mode
    docker compose -f docker/docker-compose.dds.yml up   # Direct DDS mode

Copyright (c) 2026 AIFLOW LABS LIMITED / RobotFlowLabs. All rights reserved.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import signal

from anima_bridge.config import (
    AnimaBridgeConfig,
    DirectDdsSettings,
    LoggingSettings,
    RobotSettings,
    RosbridgeSettings,
    SafetySettings,
    TransportMode,
    TransportSettings,
)
from anima_bridge.transport_manager import connect, disconnect

logger = logging.getLogger("anima_bridge")


def _env(key: str, default: str | None = None) -> str | None:
    """Read env var with ANIMA_ prefix."""
    return os.environ.get(f"ANIMA_{key}", default)


def config_from_env() -> AnimaBridgeConfig:
    """Build config from environment variables.

    Every setting can be controlled via ANIMA_* env vars.
    This is the primary config path for Docker deployments.
    """
    mode_str = _env("TRANSPORT_MODE", "direct_dds")
    mode = TransportMode(mode_str) if mode_str else TransportMode.DIRECT_DDS

    return AnimaBridgeConfig(
        transport=TransportSettings(mode=mode),
        rosbridge=RosbridgeSettings(
            url=_env("ROSBRIDGE_URL", "ws://localhost:9090") or "ws://localhost:9090",
            reconnect=_env("ROSBRIDGE_RECONNECT", "true") == "true",
            max_reconnect_attempts=int(_env("ROSBRIDGE_MAX_RECONNECT_ATTEMPTS", "10") or "10"),
        ),
        direct_dds=DirectDdsSettings(
            domain_id=int(_env("DDS_DOMAIN_ID", "0") or "0"),
        ),
        robot=RobotSettings(
            name=_env("ROBOT_NAME", "Robot") or "Robot",
            namespace=_env("ROBOT_NAMESPACE", "") or "",
        ),
        safety=SafetySettings(
            max_linear_velocity=float(_env("MAX_LINEAR_VELOCITY", "1.0") or "1.0"),
            max_angular_velocity=float(_env("MAX_ANGULAR_VELOCITY", "1.5") or "1.5"),
        ),
        logging=LoggingSettings(
            mcap_enabled=_env("MCAP_ENABLED", "false") == "true",
        ),
    )


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        prog="anima-bridge",
        description="ANIMA ROS2 Bridge — Direct DDS bridge for AI-powered robotics",
    )
    parser.add_argument(
        "--transport",
        type=str,
        choices=["direct_dds", "rosbridge", "zenoh"],
        default=None,
        help="Transport mode (overrides ANIMA_TRANSPORT_MODE env var)",
    )
    parser.add_argument(
        "--url",
        type=str,
        default=None,
        help="Rosbridge WebSocket URL (overrides ANIMA_ROSBRIDGE_URL)",
    )
    parser.add_argument(
        "--domain-id",
        type=int,
        default=None,
        help="ROS2 DDS domain ID (overrides ANIMA_DDS_DOMAIN_ID)",
    )
    parser.add_argument(
        "--robot-name",
        type=str,
        default=None,
        help="Robot name (overrides ANIMA_ROBOT_NAME)",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default=None,
        help="Log level (overrides ANIMA_LOG_LEVEL)",
    )
    return parser.parse_args()


async def run(config: AnimaBridgeConfig) -> None:
    """Main bridge run loop."""
    logger.info(
        "ANIMA ROS2 Bridge v0.1.0 starting — transport=%s, robot=%s",
        config.transport.mode.value,
        config.robot.name,
    )

    await connect(config)
    logger.info("Transport connected — mode=%s", config.transport.mode.value)

    # Keep running until interrupted
    stop_event = asyncio.Event()

    def _signal_handler() -> None:
        logger.info("Shutdown signal received")
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _signal_handler)

    logger.info("ANIMA ROS2 Bridge running. Press Ctrl+C to stop.")
    await stop_event.wait()

    await disconnect()
    logger.info("ANIMA ROS2 Bridge stopped.")


def main() -> None:
    """Entry point: env vars → config, CLI args override."""
    args = parse_args()

    # Logging (CLI > env > default)
    log_level = args.log_level or _env("LOG_LEVEL", "INFO") or "INFO"
    logging.basicConfig(
        level=getattr(logging, log_level),
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    # Config from env vars (Docker-friendly)
    config = config_from_env()

    # CLI args override env vars
    if args.transport:
        config.transport.mode = TransportMode(args.transport)
    if args.url:
        config.rosbridge.url = args.url
    if args.domain_id is not None:
        config.direct_dds.domain_id = args.domain_id
    if args.robot_name:
        config.robot.name = args.robot_name

    logger.debug("Config: %s", config.model_dump_json(indent=2))

    try:
        asyncio.run(run(config))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
