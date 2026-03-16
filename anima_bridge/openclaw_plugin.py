# Copyright (c) 2026 AIFLOW LABS LIMITED / RobotFlowLabs
"""OpenClaw compatibility layer for the ANIMA ROS2 Bridge.

Wraps every ANIMA tool, hook, and command as an OpenClaw-compatible
extension so the bridge can be loaded by any OpenClaw-based agent runtime.

Usage in ``openclaw.plugin.json``::

    {
        "id": "anima-ros2-bridge",
        "name": "ANIMA ROS2 Bridge",
        "extensions": ["./anima_bridge/openclaw_plugin.py"]
    }

The plugin exposes:
    - 9 tool definitions in the ``AnyAgentTool`` schema format.
    - ``before_agent_start`` hook  -- injects robot context into the prompt.
    - ``before_tool_call``  hook  -- validates calls via SafetyValidator.
    - ``/estop``  command  -- emergency stop.
    - ``/transport`` command  -- query or switch transport at runtime.
    - Config schema export for ``openclaw.plugin.json`` validation.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from anima_bridge.config import AnimaBridgeConfig, load_config
from anima_bridge.context.robot_context import RobotContextBuilder
from anima_bridge.safety.validator import SafetyValidator

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ToolDefinition:
    """Minimal tool definition compatible with the OpenClaw AnyAgentTool schema."""

    name: str
    description: str
    parameters: dict[str, Any]
    callable_name: str


def _build_tool_definitions() -> list[ToolDefinition]:
    """Return the full list of ANIMA tool definitions."""
    return [
        ToolDefinition(
            name="ros2_publish",
            description=(
                "Publish a message to a ROS2 topic. "
                "Requires topic name, message type, and message payload."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "topic": {"type": "string", "description": "Target ROS2 topic name."},
                    "msg_type": {
                        "type": "string",
                        "description": "Fully qualified message type.",
                    },
                    "message": {
                        "type": "object",
                        "description": "Message payload as a JSON object.",
                    },
                },
                "required": ["topic", "msg_type", "message"],
            },
            callable_name="anima_bridge.tools.ros2_publish.ros2_publish",
        ),
        ToolDefinition(
            name="ros2_subscribe_once",
            description="Read a single message from a ROS2 topic with a timeout.",
            parameters={
                "type": "object",
                "properties": {
                    "topic": {"type": "string", "description": "Topic to subscribe to."},
                    "msg_type": {
                        "type": "string",
                        "description": "Message type (optional, auto-resolved).",
                    },
                    "timeout_ms": {
                        "type": "integer",
                        "description": "Max wait in ms (default 5000).",
                        "default": 5000,
                    },
                },
                "required": ["topic"],
            },
            callable_name="anima_bridge.tools.ros2_subscribe.ros2_subscribe_once",
        ),
        ToolDefinition(
            name="ros2_service_call",
            description="Call a ROS2 service and return the response.",
            parameters={
                "type": "object",
                "properties": {
                    "service": {"type": "string", "description": "Service name."},
                    "srv_type": {
                        "type": "string",
                        "description": "Service type (optional, auto-resolved).",
                    },
                    "args": {
                        "type": "object",
                        "description": "Service request arguments.",
                    },
                },
                "required": ["service"],
            },
            callable_name="anima_bridge.tools.ros2_service.ros2_service_call",
        ),
        ToolDefinition(
            name="ros2_action_goal",
            description="Send a goal to a ROS2 action server and wait for the result.",
            parameters={
                "type": "object",
                "properties": {
                    "action": {"type": "string", "description": "Action server name."},
                    "action_type": {
                        "type": "string",
                        "description": "Fully qualified action type.",
                    },
                    "goal": {"type": "object", "description": "Goal payload."},
                },
                "required": ["action", "action_type", "goal"],
            },
            callable_name="anima_bridge.tools.ros2_action.ros2_action_goal",
        ),
        ToolDefinition(
            name="ros2_param_get",
            description="Read a parameter from a ROS2 node.",
            parameters={
                "type": "object",
                "properties": {
                    "node": {"type": "string", "description": "Fully qualified node name."},
                    "parameter": {"type": "string", "description": "Parameter name."},
                },
                "required": ["node", "parameter"],
            },
            callable_name="anima_bridge.tools.ros2_param.ros2_param_get",
        ),
        ToolDefinition(
            name="ros2_param_set",
            description="Set a parameter on a ROS2 node.",
            parameters={
                "type": "object",
                "properties": {
                    "node": {"type": "string", "description": "Fully qualified node name."},
                    "parameter": {"type": "string", "description": "Parameter name."},
                    "value": {"description": "New parameter value."},
                },
                "required": ["node", "parameter", "value"],
            },
            callable_name="anima_bridge.tools.ros2_param.ros2_param_set",
        ),
        ToolDefinition(
            name="ros2_camera_snapshot",
            description="Capture a single frame from a compressed image topic.",
            parameters={
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": "Camera topic (default /camera/image_raw/compressed).",
                        "default": "/camera/image_raw/compressed",
                    },
                    "timeout_ms": {
                        "type": "integer",
                        "description": "Max wait in ms.",
                        "default": 5000,
                    },
                },
            },
            callable_name="anima_bridge.tools.ros2_camera.ros2_camera_snapshot",
        ),
        ToolDefinition(
            name="ros2_list_topics",
            description="List all available ROS2 topics (excluding internal ones).",
            parameters={"type": "object", "properties": {}},
            callable_name="anima_bridge.tools.ros2_introspect.ros2_list_topics",
        ),
        ToolDefinition(
            name="emergency_stop",
            description=(
                "EMERGENCY STOP. Immediately publishes zero velocity to stop the robot. "
                "Bypasses the agent and safety validator."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "namespace": {
                        "type": "string",
                        "description": "ROS2 namespace prefix.",
                        "default": "",
                    },
                },
            },
            callable_name="anima_bridge.commands.estop.emergency_stop",
        ),
    ]


async def _before_agent_start_hook(
    context_builder: RobotContextBuilder,
) -> str:
    """Generate robot context markdown for system prompt injection."""
    return await context_builder.build_context()


def _before_tool_call_hook(
    validator: SafetyValidator,
    tool_name: str,
    args: dict[str, Any],
) -> tuple[bool, str]:
    """Validate a tool call against safety limits before execution."""
    return validator.validate(tool_name, args)


@dataclass(slots=True)
class CommandDefinition:
    """Describes a slash-command exposed to the agent runtime."""

    name: str
    description: str
    handler_name: str


def _build_command_definitions() -> list[CommandDefinition]:
    """Return the list of commands this plugin registers."""
    return [
        CommandDefinition(
            name="/estop",
            description="Emergency stop -- immediately zeroes all velocity commands.",
            handler_name="anima_bridge.commands.estop.emergency_stop",
        ),
        CommandDefinition(
            name="/transport",
            description=(
                "Query or switch the active transport backend. "
                "Usage: /transport [status | switch <mode>]"
            ),
            handler_name="anima_bridge.commands.transport_cmd.get_transport_status",
        ),
    ]


@dataclass
class AnimaOpenClawPlugin:
    """OpenClaw compatibility wrapper for the ANIMA ROS2 Bridge.

    Allows the ANIMA bridge to be loaded as an OpenClaw extension plugin,
    registering all tools, hooks, and commands with the OpenClaw runtime.
    """

    config: AnimaBridgeConfig = field(default_factory=AnimaBridgeConfig)
    _context_builder: RobotContextBuilder | None = field(default=None, init=False, repr=False)
    _safety_validator: SafetyValidator | None = field(default=None, init=False, repr=False)

    # ── Lifecycle ────────────────────────────────────────────────────

    def initialize(self, raw_config: dict[str, Any] | None = None) -> None:
        """Initialize the plugin with optional config overrides.

        Args:
            raw_config: Raw configuration dict. Falls back to defaults.
        """
        if raw_config is not None:
            self.config = load_config(raw_config)
        self._context_builder = RobotContextBuilder(self.config)
        self._safety_validator = SafetyValidator(self.config.safety)
        logger.info("AnimaOpenClawPlugin initialized (transport=%s)", self.config.transport.mode)

    # ── Tool registration ────────────────────────────────────────────

    def get_tool_definitions(self) -> list[dict[str, Any]]:
        """Return all tool definitions as dicts for OpenClaw registration.

        Each dict has keys: ``name``, ``description``, ``parameters``,
        ``callable_name``.
        """
        tools = _build_tool_definitions()
        return [
            {
                "name": t.name,
                "description": t.description,
                "parameters": t.parameters,
                "callable_name": t.callable_name,
            }
            for t in tools
        ]

    # ── Hook registration ────────────────────────────────────────────

    async def before_agent_start(self) -> str:
        """Hook: called before the agent loop starts.

        Returns:
            Markdown context string for system prompt injection.
        """
        if self._context_builder is None:
            self.initialize()
        assert self._context_builder is not None
        return await _before_agent_start_hook(self._context_builder)

    def before_tool_call(self, tool_name: str, args: dict[str, Any]) -> tuple[bool, str]:
        """Hook: called before each tool invocation.

        Returns:
            Tuple of (allowed, reason). If ``allowed`` is False the call
            is blocked with the given reason.
        """
        if self._safety_validator is None:
            self.initialize()
        assert self._safety_validator is not None
        return _before_tool_call_hook(self._safety_validator, tool_name, args)

    # ── Command registration ─────────────────────────────────────────

    def get_command_definitions(self) -> list[dict[str, str]]:
        """Return all slash-command definitions for OpenClaw registration."""
        cmds = _build_command_definitions()
        return [
            {
                "name": c.name,
                "description": c.description,
                "handler_name": c.handler_name,
            }
            for c in cmds
        ]

    # ── Config schema export ─────────────────────────────────────────

    @staticmethod
    def get_config_schema() -> dict[str, Any]:
        """Return the JSON Schema for this plugin's configuration.

        Used by OpenClaw's ``openclaw.plugin.json`` validation system.
        """
        return AnimaBridgeConfig.model_json_schema()


_plugin_instance: AnimaOpenClawPlugin | None = None


def get_plugin(raw_config: dict[str, Any] | None = None) -> AnimaOpenClawPlugin:
    """Return the singleton plugin instance, initializing on first call.

    This is the entry point called by OpenClaw's ``jiti`` dynamic import
    system when loading the extension.
    """
    global _plugin_instance
    if _plugin_instance is None:
        _plugin_instance = AnimaOpenClawPlugin()
        _plugin_instance.initialize(raw_config)
    return _plugin_instance


def register_tools() -> list[dict[str, Any]]:
    """Convenience function: return all tool definitions.

    Called directly by OpenClaw when scanning extensions for tools.
    """
    return get_plugin().get_tool_definitions()


def register_commands() -> list[dict[str, str]]:
    """Convenience function: return all command definitions."""
    return get_plugin().get_command_definitions()


async def on_before_agent_start() -> str:
    """Convenience function: before-agent-start hook entry point."""
    return await get_plugin().before_agent_start()


def on_before_tool_call(tool_name: str, args: dict[str, Any]) -> tuple[bool, str]:
    """Convenience function: before-tool-call hook entry point."""
    return get_plugin().before_tool_call(tool_name, args)
