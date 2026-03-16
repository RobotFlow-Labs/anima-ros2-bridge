"""Tests for anima_bridge.transport.types module.

Copyright (c) 2026 AIFLOW LABS LIMITED / RobotFlowLabs. All rights reserved.
"""

from __future__ import annotations

from anima_bridge.transport.types import (
    ActionGoalOptions,
    ActionInfo,
    ActionResult,
    ConnectionStatus,
    PublishOptions,
    PublishResult,
    ServiceCallResult,
    ServiceInfo,
    SubscribeResult,
    Subscription,
    TopicInfo,
)


class TestConnectionStatus:
    def test_states(self) -> None:
        assert ConnectionStatus.DISCONNECTED.value == "disconnected"
        assert ConnectionStatus.CONNECTING.value == "connecting"
        assert ConnectionStatus.CONNECTED.value == "connected"


class TestTopicInfo:
    def test_creation(self) -> None:
        info = TopicInfo(name="/cmd_vel", msg_type="geometry_msgs/msg/Twist")
        assert info.name == "/cmd_vel"
        assert info.msg_type == "geometry_msgs/msg/Twist"

    def test_frozen(self) -> None:
        info = TopicInfo(name="/odom", msg_type="nav_msgs/msg/Odometry")
        assert info.name == "/odom"


class TestServiceInfo:
    def test_creation(self) -> None:
        info = ServiceInfo(name="/get_state", srv_type="std_srvs/srv/Trigger")
        assert info.name == "/get_state"
        assert info.srv_type == "std_srvs/srv/Trigger"


class TestActionInfo:
    def test_creation(self) -> None:
        info = ActionInfo(
            name="/navigate_to_pose",
            action_type="nav2_msgs/action/NavigateToPose",
        )
        assert info.name == "/navigate_to_pose"


class TestPublishOptions:
    def test_creation(self) -> None:
        opts = PublishOptions(
            topic="/cmd_vel",
            msg_type="geometry_msgs/msg/Twist",
            msg={"linear": {"x": 0.5}, "angular": {"z": 0.1}},
        )
        assert opts.topic == "/cmd_vel"
        assert opts.msg["linear"]["x"] == 0.5


class TestPublishResult:
    def test_success(self) -> None:
        result = PublishResult(success=True)
        assert result.success is True
        assert result.error is None

    def test_failure(self) -> None:
        result = PublishResult(success=False, error="not connected")
        assert result.success is False
        assert result.error == "not connected"


class TestSubscribeResult:
    def test_success(self) -> None:
        result = SubscribeResult(success=True, msg={"data": 42})
        assert result.success is True
        assert result.msg is not None

    def test_timeout(self) -> None:
        result = SubscribeResult(success=False, error="timeout")
        assert result.success is False
        assert result.msg is None


class TestSubscription:
    def test_unsubscribe(self) -> None:
        called = False

        def unsub() -> None:
            nonlocal called
            called = True

        sub = Subscription(topic="/odom", _unsubscribe_fn=unsub)
        assert sub.topic == "/odom"
        sub.unsubscribe()
        assert called is True


class TestServiceCallResult:
    def test_success(self) -> None:
        result = ServiceCallResult(
            success=True,
            values={"state": "active"},
        )
        assert result.success is True
        assert result.values is not None
        assert result.values["state"] == "active"

    def test_failure(self) -> None:
        result = ServiceCallResult(success=False, error="service unavailable")
        assert result.success is False


class TestActionGoalOptions:
    def test_creation(self) -> None:
        opts = ActionGoalOptions(
            action="/navigate_to_pose",
            action_type="nav2_msgs/action/NavigateToPose",
            goal={"pose": {"position": {"x": 1.0}}},
        )
        assert opts.action == "/navigate_to_pose"
        assert opts.timeout_s == 120.0


class TestActionResult:
    def test_success(self) -> None:
        result = ActionResult(
            success=True,
            values={"reached": True},
        )
        assert result.success is True
        assert result.values is not None

    def test_failure(self) -> None:
        result = ActionResult(success=False, error="goal rejected")
        assert result.success is False
