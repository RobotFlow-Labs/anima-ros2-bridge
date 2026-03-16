"""Unit tests for all ANIMA Bridge tool functions.

Copyright (c) 2026 AIFLOW LABS LIMITED / RobotFlowLabs. All rights reserved.

Every tool is tested with a mocked transport so that no real ROS2
installation is required. Tests verify:
    - Correct dict format on success.
    - Error handling when transport is not connected.
    - Safety validator integration via the OpenClaw plugin hooks.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from anima_bridge.config import SafetySettings
from anima_bridge.safety.validator import SafetyValidator
from anima_bridge.transport.types import (
    ActionResult,
    PublishResult,
    ServiceCallResult,
    SubscribeResult,
    TopicInfo,
)


@pytest.fixture()
def mock_transport() -> MagicMock:
    """Create a mock transport with all methods pre-configured."""
    transport = MagicMock()
    transport.is_connected.return_value = True
    transport.publish = AsyncMock(return_value=PublishResult(success=True))
    transport.subscribe_once = AsyncMock(
        return_value=SubscribeResult(success=True, msg={"data": "hello"})
    )
    transport.call_service = AsyncMock(
        return_value=ServiceCallResult(success=True, values={"result": 42})
    )
    transport.send_action_goal = AsyncMock(
        return_value=ActionResult(success=True, values={"status": "done"})
    )
    transport.list_topics = AsyncMock(
        return_value=[
            TopicInfo(name="/cmd_vel", msg_type="geometry_msgs/msg/Twist"),
            TopicInfo(name="/odom", msg_type="nav_msgs/msg/Odometry"),
        ]
    )
    transport.get_parameters = AsyncMock(return_value={"max_speed": 1.0})
    transport.set_parameters = AsyncMock(return_value=True)
    return transport


@pytest.fixture()
def safety_validator() -> SafetyValidator:
    """Create a safety validator with default limits."""
    return SafetyValidator(SafetySettings())


class TestRos2Publish:
    """Tests for the ros2_publish tool."""

    @pytest.mark.asyncio()
    async def test_successful_publish(self, mock_transport: MagicMock) -> None:
        with patch("anima_bridge.tools.ros2_publish.get_transport", return_value=mock_transport):
            from anima_bridge.tools.ros2_publish import ros2_publish

            result = await ros2_publish(
                topic="/cmd_vel",
                msg_type="geometry_msgs/msg/Twist",
                message={"linear": {"x": 0.5}},
            )
        assert result["success"] is True
        assert result["topic"] == "/cmd_vel"
        assert result["msg_type"] == "geometry_msgs/msg/Twist"

    @pytest.mark.asyncio()
    async def test_publish_failure(self, mock_transport: MagicMock) -> None:
        mock_transport.publish = AsyncMock(
            return_value=PublishResult(success=False, error="topic not found")
        )
        with patch("anima_bridge.tools.ros2_publish.get_transport", return_value=mock_transport):
            from anima_bridge.tools.ros2_publish import ros2_publish

            result = await ros2_publish(
                topic="/nonexistent",
                msg_type="std_msgs/msg/String",
                message={"data": "test"},
            )
        assert result["success"] is False
        assert "topic not found" in result["error"]

    @pytest.mark.asyncio()
    async def test_publish_no_transport(self) -> None:
        with patch(
            "anima_bridge.tools.ros2_publish.get_transport",
            side_effect=RuntimeError("No transport"),
        ):
            from anima_bridge.tools.ros2_publish import ros2_publish

            result = await ros2_publish("/cmd_vel", "geometry_msgs/msg/Twist", {})
        assert result["success"] is False
        assert "No transport" in result["error"]


class TestRos2SubscribeOnce:
    """Tests for the ros2_subscribe_once tool."""

    @pytest.mark.asyncio()
    async def test_successful_subscribe(self, mock_transport: MagicMock) -> None:
        with patch(
            "anima_bridge.tools.ros2_subscribe.get_transport",
            return_value=mock_transport,
        ):
            from anima_bridge.tools.ros2_subscribe import ros2_subscribe_once

            result = await ros2_subscribe_once(topic="/odom")
        assert result["success"] is True
        assert result["topic"] == "/odom"
        assert result["message"] == {"data": "hello"}

    @pytest.mark.asyncio()
    async def test_subscribe_timeout(self, mock_transport: MagicMock) -> None:
        mock_transport.subscribe_once = AsyncMock(
            return_value=SubscribeResult(success=False, error="timeout")
        )
        with patch(
            "anima_bridge.tools.ros2_subscribe.get_transport",
            return_value=mock_transport,
        ):
            from anima_bridge.tools.ros2_subscribe import ros2_subscribe_once

            result = await ros2_subscribe_once(topic="/odom", timeout_ms=100)
        assert result["success"] is False
        assert "timeout" in result["error"]

    @pytest.mark.asyncio()
    async def test_subscribe_no_transport(self) -> None:
        with patch(
            "anima_bridge.tools.ros2_subscribe.get_transport",
            side_effect=RuntimeError("No transport"),
        ):
            from anima_bridge.tools.ros2_subscribe import ros2_subscribe_once

            result = await ros2_subscribe_once("/odom")
        assert result["success"] is False
        assert "No transport" in result["error"]


class TestRos2ServiceCall:
    """Tests for the ros2_service_call tool."""

    @pytest.mark.asyncio()
    async def test_successful_call(self, mock_transport: MagicMock) -> None:
        with patch(
            "anima_bridge.tools.ros2_service.get_transport",
            return_value=mock_transport,
        ):
            from anima_bridge.tools.ros2_service import ros2_service_call

            result = await ros2_service_call(service="/trigger")
        assert result["success"] is True
        assert result["service"] == "/trigger"
        assert result["response"] == {"result": 42}

    @pytest.mark.asyncio()
    async def test_service_failure(self, mock_transport: MagicMock) -> None:
        mock_transport.call_service = AsyncMock(
            return_value=ServiceCallResult(success=False, error="service unavailable")
        )
        with patch(
            "anima_bridge.tools.ros2_service.get_transport",
            return_value=mock_transport,
        ):
            from anima_bridge.tools.ros2_service import ros2_service_call

            result = await ros2_service_call(service="/trigger")
        assert result["success"] is False
        assert "service unavailable" in result["error"]

    @pytest.mark.asyncio()
    async def test_service_no_transport(self) -> None:
        with patch(
            "anima_bridge.tools.ros2_service.get_transport",
            side_effect=RuntimeError("No transport"),
        ):
            from anima_bridge.tools.ros2_service import ros2_service_call

            result = await ros2_service_call("/trigger")
        assert result["success"] is False


class TestRos2ActionGoal:
    """Tests for the ros2_action_goal tool."""

    @pytest.mark.asyncio()
    async def test_successful_goal(self, mock_transport: MagicMock) -> None:
        with patch(
            "anima_bridge.tools.ros2_action.get_transport",
            return_value=mock_transport,
        ):
            from anima_bridge.tools.ros2_action import ros2_action_goal

            result = await ros2_action_goal(
                action="/navigate",
                action_type="nav2_msgs/action/NavigateToPose",
                goal={"pose": {"position": {"x": 1.0}}},
            )
        assert result["success"] is True
        assert result["action"] == "/navigate"
        assert result["result"] == {"status": "done"}

    @pytest.mark.asyncio()
    async def test_action_failure(self, mock_transport: MagicMock) -> None:
        mock_transport.send_action_goal = AsyncMock(
            return_value=ActionResult(success=False, error="goal rejected")
        )
        with patch(
            "anima_bridge.tools.ros2_action.get_transport",
            return_value=mock_transport,
        ):
            from anima_bridge.tools.ros2_action import ros2_action_goal

            result = await ros2_action_goal("/navigate", "nav2_msgs/action/Nav", {})
        assert result["success"] is False
        assert "goal rejected" in result["error"]

    @pytest.mark.asyncio()
    async def test_action_no_transport(self) -> None:
        with patch(
            "anima_bridge.tools.ros2_action.get_transport",
            side_effect=RuntimeError("No transport"),
        ):
            from anima_bridge.tools.ros2_action import ros2_action_goal

            result = await ros2_action_goal("/navigate", "nav2_msgs/action/Nav", {})
        assert result["success"] is False


class TestRos2Params:
    """Tests for ros2_param_get and ros2_param_set tools."""

    @pytest.mark.asyncio()
    async def test_param_get(self, mock_transport: MagicMock) -> None:
        with patch(
            "anima_bridge.tools.ros2_param.get_transport",
            return_value=mock_transport,
        ):
            from anima_bridge.tools.ros2_param import ros2_param_get

            result = await ros2_param_get(node="/controller", parameter="max_speed")
        assert result["success"] is True
        assert result["value"] == 1.0

    @pytest.mark.asyncio()
    async def test_param_set(self, mock_transport: MagicMock) -> None:
        with patch(
            "anima_bridge.tools.ros2_param.get_transport",
            return_value=mock_transport,
        ):
            from anima_bridge.tools.ros2_param import ros2_param_set

            result = await ros2_param_set(node="/controller", parameter="max_speed", value=2.0)
        assert result["success"] is True
        assert result["value"] == 2.0

    @pytest.mark.asyncio()
    async def test_param_get_no_transport(self) -> None:
        with patch(
            "anima_bridge.tools.ros2_param.get_transport",
            side_effect=RuntimeError("No transport"),
        ):
            from anima_bridge.tools.ros2_param import ros2_param_get

            result = await ros2_param_get("/controller", "max_speed")
        assert result["success"] is False

    @pytest.mark.asyncio()
    async def test_param_set_failure(self, mock_transport: MagicMock) -> None:
        mock_transport.set_parameters = AsyncMock(return_value=False)
        with patch(
            "anima_bridge.tools.ros2_param.get_transport",
            return_value=mock_transport,
        ):
            from anima_bridge.tools.ros2_param import ros2_param_set

            result = await ros2_param_set("/controller", "max_speed", 99.0)
        assert result["success"] is False


class TestRos2CameraSnapshot:
    """Tests for the ros2_camera_snapshot tool."""

    @pytest.mark.asyncio()
    async def test_successful_snapshot(self, mock_transport: MagicMock) -> None:
        mock_transport.subscribe_once = AsyncMock(
            return_value=SubscribeResult(
                success=True,
                msg={"format": "jpeg", "data": b"\xff\xd8\xff\xe0"},
            )
        )
        with patch(
            "anima_bridge.tools.ros2_camera.get_transport",
            return_value=mock_transport,
        ):
            from anima_bridge.tools.ros2_camera import ros2_camera_snapshot

            result = await ros2_camera_snapshot()
        assert result["success"] is True
        assert result["format"] == "jpeg"
        assert isinstance(result["data"], str)  # base64

    @pytest.mark.asyncio()
    async def test_snapshot_timeout(self, mock_transport: MagicMock) -> None:
        mock_transport.subscribe_once = AsyncMock(
            return_value=SubscribeResult(success=False, error="timeout")
        )
        with patch(
            "anima_bridge.tools.ros2_camera.get_transport",
            return_value=mock_transport,
        ):
            from anima_bridge.tools.ros2_camera import ros2_camera_snapshot

            result = await ros2_camera_snapshot(timeout_ms=100)
        assert result["success"] is False


class TestRos2ListTopics:
    """Tests for the ros2_list_topics tool."""

    @pytest.mark.asyncio()
    async def test_list_topics(self, mock_transport: MagicMock) -> None:
        with patch(
            "anima_bridge.tools.ros2_introspect.get_transport",
            return_value=mock_transport,
        ):
            from anima_bridge.tools.ros2_introspect import ros2_list_topics

            result = await ros2_list_topics()
        assert result["success"] is True
        assert len(result["topics"]) == 2
        assert result["topics"][0]["name"] == "/cmd_vel"

    @pytest.mark.asyncio()
    async def test_list_topics_no_transport(self) -> None:
        with patch(
            "anima_bridge.tools.ros2_introspect.get_transport",
            side_effect=RuntimeError("No transport"),
        ):
            from anima_bridge.tools.ros2_introspect import ros2_list_topics

            result = await ros2_list_topics()
        assert result["success"] is False


class TestSafetyValidatorIntegration:
    """Test that the safety validator correctly blocks dangerous commands."""

    def test_safe_velocity_allowed(self, safety_validator: SafetyValidator) -> None:
        allowed, reason = safety_validator.validate(
            "ros2_publish",
            {
                "topic": "/cmd_vel",
                "msg_type": "geometry_msgs/msg/Twist",
                "message": {"linear": {"x": 0.5, "y": 0.0, "z": 0.0}},
            },
        )
        assert allowed is True

    def test_excessive_velocity_blocked(self, safety_validator: SafetyValidator) -> None:
        allowed, reason = safety_validator.validate(
            "ros2_publish",
            {
                "topic": "/cmd_vel",
                "msg_type": "geometry_msgs/msg/Twist",
                "message": {"linear": {"x": 10.0, "y": 0.0, "z": 0.0}},
            },
        )
        assert allowed is False
        assert "exceeds limit" in reason.lower()

    def test_excessive_angular_blocked(self, safety_validator: SafetyValidator) -> None:
        allowed, reason = safety_validator.validate(
            "ros2_publish",
            {
                "topic": "/cmd_vel",
                "msg_type": "geometry_msgs/msg/Twist",
                "message": {"angular": {"x": 0.0, "y": 0.0, "z": 5.0}},
            },
        )
        assert allowed is False
        assert "angular" in reason.lower()

    def test_non_publish_always_allowed(self, safety_validator: SafetyValidator) -> None:
        allowed, _ = safety_validator.validate("ros2_list_topics", {})
        assert allowed is True

    def test_workspace_bounds_blocked(self, safety_validator: SafetyValidator) -> None:
        allowed, reason = safety_validator.validate(
            "ros2_publish",
            {
                "topic": "/target_pose",
                "msg_type": "geometry_msgs/msg/Pose",
                "message": {"position": {"x": 100.0, "y": 0.0, "z": 0.0}},
            },
        )
        assert allowed is False
        assert "workspace" in reason.lower()

    def test_gripper_force_blocked(self, safety_validator: SafetyValidator) -> None:
        allowed, reason = safety_validator.validate(
            "ros2_publish",
            {
                "topic": "/gripper_cmd",
                "msg_type": "custom_msgs/msg/Gripper",
                "message": {"force": 100.0},
            },
        )
        assert allowed is False
        assert "gripper" in reason.lower()

    def test_openclaw_plugin_hooks(self) -> None:
        """Test that the OpenClaw plugin wires up safety correctly."""
        from anima_bridge.openclaw_plugin import AnimaOpenClawPlugin

        plugin = AnimaOpenClawPlugin()
        plugin.initialize()

        # Safe call should pass
        allowed, reason = plugin.before_tool_call(
            "ros2_publish",
            {
                "topic": "/cmd_vel",
                "msg_type": "geometry_msgs/msg/Twist",
                "message": {"linear": {"x": 0.3}},
            },
        )
        assert allowed is True

        # Dangerous call should be blocked
        allowed, reason = plugin.before_tool_call(
            "ros2_publish",
            {
                "topic": "/cmd_vel",
                "msg_type": "geometry_msgs/msg/Twist",
                "message": {"linear": {"x": 50.0}},
            },
        )
        assert allowed is False
