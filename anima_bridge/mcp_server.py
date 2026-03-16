"""MCP (Model Context Protocol) server for the ANIMA ROS2 Bridge.

Copyright (c) 2026 AIFLOW LABS LIMITED / RobotFlowLabs. All rights reserved.

Exposes all ANIMA tools to any MCP-compatible AI agent (Claude, GPT,
or other LLMs that speak MCP). Each tool has a full JSON Schema so
the LLM understands the parameters without additional prompting.

Usage::

    python -m anima_bridge.mcp_server          # stdio transport (default)
    python -m anima_bridge.mcp_server --sse     # SSE transport

The server registers these tools:
    - ros2_publish, ros2_subscribe_once, ros2_service_call
    - ros2_action_goal, ros2_param_get, ros2_param_set
    - ros2_camera_snapshot, ros2_list_topics
    - emergency_stop
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from anima_bridge.commands.estop import emergency_stop
from anima_bridge.config import AnimaBridgeConfig, load_config
from anima_bridge.context.robot_context import RobotContextBuilder
from anima_bridge.safety.validator import SafetyValidator
from anima_bridge.tools.ros2_action import ros2_action_goal
from anima_bridge.tools.ros2_camera import ros2_camera_snapshot
from anima_bridge.tools.ros2_introspect import ros2_list_topics
from anima_bridge.tools.ros2_param import ros2_param_get, ros2_param_set
from anima_bridge.tools.ros2_publish import ros2_publish
from anima_bridge.tools.ros2_service import ros2_service_call
from anima_bridge.tools.ros2_subscribe import ros2_subscribe_once

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────
# Tool metadata
# ──────────────────────────────────────────────────────────────────────

_TOOL_SCHEMAS: list[Tool] = [
    Tool(
        name="ros2_publish",
        description=(
            "Publish a message to a ROS2 topic. "
            "Provide the topic name, fully-qualified message type, and payload."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "Target ROS2 topic."},
                "msg_type": {
                    "type": "string",
                    "description": "Fully qualified message type (e.g. geometry_msgs/msg/Twist).",
                },
                "message": {"type": "object", "description": "Message payload as JSON."},
            },
            "required": ["topic", "msg_type", "message"],
        },
    ),
    Tool(
        name="ros2_subscribe_once",
        description="Read a single message from a ROS2 topic with a timeout.",
        inputSchema={
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "Topic to read from."},
                "msg_type": {"type": "string", "description": "Message type (auto-resolved)."},
                "timeout_ms": {
                    "type": "integer",
                    "description": "Max wait time in ms.",
                    "default": 5000,
                },
            },
            "required": ["topic"],
        },
    ),
    Tool(
        name="ros2_service_call",
        description="Call a ROS2 service and return its response.",
        inputSchema={
            "type": "object",
            "properties": {
                "service": {"type": "string", "description": "Service name."},
                "srv_type": {"type": "string", "description": "Service type (auto-resolved)."},
                "args": {"type": "object", "description": "Request arguments."},
            },
            "required": ["service"],
        },
    ),
    Tool(
        name="ros2_action_goal",
        description="Send a goal to a ROS2 action server and await the result.",
        inputSchema={
            "type": "object",
            "properties": {
                "action": {"type": "string", "description": "Action server name."},
                "action_type": {"type": "string", "description": "Fully qualified action type."},
                "goal": {"type": "object", "description": "Goal payload."},
            },
            "required": ["action", "action_type", "goal"],
        },
    ),
    Tool(
        name="ros2_param_get",
        description="Read a parameter from a ROS2 node.",
        inputSchema={
            "type": "object",
            "properties": {
                "node": {"type": "string", "description": "Fully qualified node name."},
                "parameter": {"type": "string", "description": "Parameter name to read."},
            },
            "required": ["node", "parameter"],
        },
    ),
    Tool(
        name="ros2_param_set",
        description="Set a parameter on a ROS2 node.",
        inputSchema={
            "type": "object",
            "properties": {
                "node": {"type": "string", "description": "Fully qualified node name."},
                "parameter": {"type": "string", "description": "Parameter name to set."},
                "value": {"description": "New parameter value (bool, int, float, or string)."},
            },
            "required": ["node", "parameter", "value"],
        },
    ),
    Tool(
        name="ros2_camera_snapshot",
        description="Capture a single frame from a compressed image topic as base64.",
        inputSchema={
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "description": "Camera topic.",
                    "default": "/camera/image_raw/compressed",
                },
                "timeout_ms": {
                    "type": "integer",
                    "description": "Max wait time in ms.",
                    "default": 5000,
                },
            },
        },
    ),
    Tool(
        name="ros2_list_topics",
        description="List all available ROS2 topics (excluding internal ones).",
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="emergency_stop",
        description=(
            "EMERGENCY STOP. Immediately publishes zero velocity to halt the robot. "
            "Bypasses the agent loop and safety validator."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "namespace": {
                    "type": "string",
                    "description": "ROS2 namespace prefix.",
                    "default": "",
                },
            },
        },
    ),
]

# Map tool names to their async handler functions.
_TOOL_HANDLERS: dict[str, Any] = {
    "ros2_publish": ros2_publish,
    "ros2_subscribe_once": ros2_subscribe_once,
    "ros2_service_call": ros2_service_call,
    "ros2_action_goal": ros2_action_goal,
    "ros2_param_get": ros2_param_get,
    "ros2_param_set": ros2_param_set,
    "ros2_camera_snapshot": ros2_camera_snapshot,
    "ros2_list_topics": ros2_list_topics,
    "emergency_stop": emergency_stop,
}


# ──────────────────────────────────────────────────────────────────────
# Server class
# ──────────────────────────────────────────────────────────────────────


class AnimaMcpServer:
    """MCP server exposing ANIMA ROS2 tools to AI agents.

    This allows Claude, GPT, or any MCP-compatible LLM to control
    ROS2 robots through the ANIMA bridge.
    """

    def __init__(self, config: AnimaBridgeConfig | None = None) -> None:
        self._config = config or AnimaBridgeConfig()
        self._safety = SafetyValidator(self._config.safety)
        self._context_builder = RobotContextBuilder(self._config)
        self._server = Server("anima-ros2-bridge")
        self._register_handlers()

    # ── Handler registration ─────────────────────────────────────────

    def _register_handlers(self) -> None:
        """Wire MCP protocol handlers to the server instance."""

        @self._server.list_tools()
        async def handle_list_tools() -> list[Tool]:
            return list(_TOOL_SCHEMAS)

        @self._server.call_tool()
        async def handle_call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
            return await self._dispatch_tool(name, arguments)

    # ── Tool dispatch ────────────────────────────────────────────────

    async def _dispatch_tool(
        self,
        name: str,
        arguments: dict[str, Any],
    ) -> list[TextContent]:
        """Route a tool call through safety validation then to the handler."""
        handler = _TOOL_HANDLERS.get(name)
        if handler is None:
            return [TextContent(type="text", text=f'{{"error": "Unknown tool: {name}"}}')]

        # Safety gate (skip for emergency_stop -- it IS the safety mechanism)
        if name != "emergency_stop":
            allowed, reason = self._safety.validate(name, arguments)
            if not allowed:
                msg = f'{{"blocked": true, "reason": "{reason}"}}'
                logger.warning("Tool %s blocked by safety: %s", name, reason)
                return [TextContent(type="text", text=msg)]

        try:
            result = await handler(**arguments)
            return [TextContent(type="text", text=json.dumps(result, default=str))]
        except Exception as exc:
            error_payload = json.dumps({"error": str(exc)})
            logger.exception("Tool %s raised an exception", name)
            return [TextContent(type="text", text=error_payload)]

    # ── Context helper ───────────────────────────────────────────────

    async def get_robot_context(self) -> str:
        """Build robot context markdown for system prompt injection."""
        return await self._context_builder.build_context()

    # ── Run ───────────────────────────────────────────────────────────

    async def run_stdio(self) -> None:
        """Run the MCP server over stdio transport."""
        logger.info("Starting ANIMA MCP server (stdio transport)")
        async with stdio_server() as (read_stream, write_stream):
            init_opts = self._server.create_initialization_options()
            await self._server.run(read_stream, write_stream, init_opts)

    async def run_sse(self, host: str = "0.0.0.0", port: int = 8765) -> None:
        """Run the MCP server over SSE transport.

        Args:
            host: Bind address.
            port: Bind port.
        """
        try:
            from mcp.server.sse import SseServerTransport
        except ImportError as exc:
            raise RuntimeError(
                "SSE transport requires the 'mcp[sse]' extra. Install with: pip install 'mcp[sse]'"
            ) from exc

        logger.info("Starting ANIMA MCP server (SSE transport) on %s:%d", host, port)
        sse = SseServerTransport("/messages")

        from starlette.applications import Starlette
        from starlette.routing import Route

        async def handle_sse(request: Any) -> Any:
            async with sse.connect_sse(request.scope, request.receive, request._send) as streams:
                await self._server.run(
                    streams[0],
                    streams[1],
                    self._server.create_initialization_options(),
                )

        app = Starlette(routes=[Route("/sse", endpoint=handle_sse)])

        import uvicorn

        config = uvicorn.Config(app, host=host, port=port, log_level="info")
        server = uvicorn.Server(config)
        await server.serve()


# ──────────────────────────────────────────────────────────────────────
# CLI entry point
# ──────────────────────────────────────────────────────────────────────


def main() -> None:
    """CLI entry point for the ANIMA MCP server."""
    parser = argparse.ArgumentParser(description="ANIMA ROS2 Bridge MCP Server")
    parser.add_argument(
        "--sse",
        action="store_true",
        help="Use SSE transport instead of stdio.",
    )
    parser.add_argument("--host", default="0.0.0.0", help="SSE bind host.")
    parser.add_argument("--port", type=int, default=8765, help="SSE bind port.")
    parser.add_argument("--config", type=str, default=None, help="Path to config JSON file.")
    args = parser.parse_args()

    config: AnimaBridgeConfig | None = None
    if args.config:
        import json
        from pathlib import Path

        raw = json.loads(Path(args.config).read_text())
        config = load_config(raw)

    server = AnimaMcpServer(config=config)

    if args.sse:
        asyncio.run(server.run_sse(host=args.host, port=args.port))
    else:
        asyncio.run(server.run_stdio())


if __name__ == "__main__":
    main()
