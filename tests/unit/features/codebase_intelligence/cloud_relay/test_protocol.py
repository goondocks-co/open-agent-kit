"""Tests for cloud relay wire protocol models."""

import json

from open_agent_kit.features.codebase_intelligence.cloud_relay.protocol import (
    HeartbeatPing,
    HeartbeatPong,
    RegisteredMessage,
    RegisterMessage,
    RelayError,
    RelayMessageType,
    ToolCallRequest,
    ToolCallResponse,
)
from open_agent_kit.features.codebase_intelligence.constants import (
    CLOUD_RELAY_DEFAULT_TOOL_TIMEOUT_SECONDS,
    CLOUD_RELAY_WS_TYPE_ERROR,
    CLOUD_RELAY_WS_TYPE_HEARTBEAT,
    CLOUD_RELAY_WS_TYPE_HEARTBEAT_ACK,
    CLOUD_RELAY_WS_TYPE_REGISTER,
    CLOUD_RELAY_WS_TYPE_REGISTERED,
    CLOUD_RELAY_WS_TYPE_TOOL_CALL,
    CLOUD_RELAY_WS_TYPE_TOOL_RESULT,
)

from .fixtures import (
    TEST_CALL_ID,
    TEST_RELAY_TOKEN,
    TEST_TIMESTAMP,
    TEST_TOOL_ARGUMENTS,
    TEST_TOOL_ERROR,
    TEST_TOOL_NAME,
    TEST_TOOL_RESULT,
)


class TestRelayMessageType:
    """Tests for RelayMessageType enum values match constants."""

    def test_register_value(self) -> None:
        assert RelayMessageType.REGISTER.value == CLOUD_RELAY_WS_TYPE_REGISTER

    def test_registered_value(self) -> None:
        assert RelayMessageType.REGISTERED.value == CLOUD_RELAY_WS_TYPE_REGISTERED

    def test_tool_call_value(self) -> None:
        assert RelayMessageType.TOOL_CALL.value == CLOUD_RELAY_WS_TYPE_TOOL_CALL

    def test_tool_result_value(self) -> None:
        assert RelayMessageType.TOOL_RESULT.value == CLOUD_RELAY_WS_TYPE_TOOL_RESULT

    def test_heartbeat_value(self) -> None:
        assert RelayMessageType.HEARTBEAT.value == CLOUD_RELAY_WS_TYPE_HEARTBEAT

    def test_heartbeat_ack_value(self) -> None:
        assert RelayMessageType.HEARTBEAT_ACK.value == CLOUD_RELAY_WS_TYPE_HEARTBEAT_ACK

    def test_error_value(self) -> None:
        assert RelayMessageType.ERROR.value == CLOUD_RELAY_WS_TYPE_ERROR


class TestRegisterMessage:
    """Tests for RegisterMessage (daemon -> worker)."""

    def test_default_type(self) -> None:
        msg = RegisterMessage(token=TEST_RELAY_TOKEN)
        assert msg.type == CLOUD_RELAY_WS_TYPE_REGISTER

    def test_serialization(self) -> None:
        tools = [{"name": TEST_TOOL_NAME, "description": "Search code"}]
        msg = RegisterMessage(token=TEST_RELAY_TOKEN, tools=tools)
        data = json.loads(msg.model_dump_json())
        assert data["type"] == CLOUD_RELAY_WS_TYPE_REGISTER
        assert data["token"] == TEST_RELAY_TOKEN
        assert len(data["tools"]) == 1
        assert data["tools"][0]["name"] == TEST_TOOL_NAME

    def test_empty_tools_default(self) -> None:
        msg = RegisterMessage(token=TEST_RELAY_TOKEN)
        assert msg.tools == []


class TestRegisteredMessage:
    """Tests for RegisteredMessage (worker -> daemon)."""

    def test_default_type(self) -> None:
        msg = RegisteredMessage()
        assert msg.type == CLOUD_RELAY_WS_TYPE_REGISTERED

    def test_serialization(self) -> None:
        data = json.loads(RegisteredMessage().model_dump_json())
        assert data["type"] == CLOUD_RELAY_WS_TYPE_REGISTERED


class TestToolCallRequest:
    """Tests for ToolCallRequest (worker -> daemon)."""

    def test_creation(self) -> None:
        req = ToolCallRequest(
            call_id=TEST_CALL_ID,
            tool_name=TEST_TOOL_NAME,
            arguments=TEST_TOOL_ARGUMENTS,
        )
        assert req.type == CLOUD_RELAY_WS_TYPE_TOOL_CALL
        assert req.call_id == TEST_CALL_ID
        assert req.tool_name == TEST_TOOL_NAME
        assert req.arguments == TEST_TOOL_ARGUMENTS

    def test_default_timeout(self) -> None:
        req = ToolCallRequest(call_id=TEST_CALL_ID, tool_name=TEST_TOOL_NAME)
        expected_ms = CLOUD_RELAY_DEFAULT_TOOL_TIMEOUT_SECONDS * 1000
        assert req.timeout_ms == expected_ms

    def test_custom_timeout(self) -> None:
        req = ToolCallRequest(
            call_id=TEST_CALL_ID,
            tool_name=TEST_TOOL_NAME,
            timeout_ms=60_000,
        )
        assert req.timeout_ms == 60_000

    def test_serialization_roundtrip(self) -> None:
        req = ToolCallRequest(
            call_id=TEST_CALL_ID,
            tool_name=TEST_TOOL_NAME,
            arguments=TEST_TOOL_ARGUMENTS,
        )
        data = json.loads(req.model_dump_json())
        restored = ToolCallRequest(**data)
        assert restored.call_id == req.call_id
        assert restored.tool_name == req.tool_name
        assert restored.arguments == req.arguments

    def test_empty_arguments_default(self) -> None:
        req = ToolCallRequest(call_id=TEST_CALL_ID, tool_name=TEST_TOOL_NAME)
        assert req.arguments == {}


class TestToolCallResponse:
    """Tests for ToolCallResponse (daemon -> worker)."""

    def test_success_response(self) -> None:
        resp = ToolCallResponse(
            call_id=TEST_CALL_ID,
            result=TEST_TOOL_RESULT,
        )
        assert resp.type == CLOUD_RELAY_WS_TYPE_TOOL_RESULT
        assert resp.call_id == TEST_CALL_ID
        assert resp.result == TEST_TOOL_RESULT
        assert resp.error is None

    def test_error_response(self) -> None:
        resp = ToolCallResponse(
            call_id=TEST_CALL_ID,
            error=TEST_TOOL_ERROR,
        )
        assert resp.result is None
        assert resp.error == TEST_TOOL_ERROR

    def test_serialization(self) -> None:
        resp = ToolCallResponse(call_id=TEST_CALL_ID, result=TEST_TOOL_RESULT)
        data = json.loads(resp.model_dump_json())
        assert data["type"] == CLOUD_RELAY_WS_TYPE_TOOL_RESULT
        assert data["call_id"] == TEST_CALL_ID
        assert data["result"] == TEST_TOOL_RESULT
        assert data["error"] is None


class TestHeartbeatPing:
    """Tests for HeartbeatPing (worker -> daemon)."""

    def test_creation(self) -> None:
        ping = HeartbeatPing(timestamp=TEST_TIMESTAMP)
        assert ping.type == CLOUD_RELAY_WS_TYPE_HEARTBEAT
        assert ping.timestamp == TEST_TIMESTAMP

    def test_serialization(self) -> None:
        data = json.loads(HeartbeatPing(timestamp=TEST_TIMESTAMP).model_dump_json())
        assert data["type"] == CLOUD_RELAY_WS_TYPE_HEARTBEAT
        assert data["timestamp"] == TEST_TIMESTAMP


class TestHeartbeatPong:
    """Tests for HeartbeatPong (daemon -> worker)."""

    def test_creation(self) -> None:
        pong = HeartbeatPong(timestamp=TEST_TIMESTAMP)
        assert pong.type == CLOUD_RELAY_WS_TYPE_HEARTBEAT_ACK
        assert pong.timestamp == TEST_TIMESTAMP

    def test_serialization(self) -> None:
        data = json.loads(HeartbeatPong(timestamp=TEST_TIMESTAMP).model_dump_json())
        assert data["type"] == CLOUD_RELAY_WS_TYPE_HEARTBEAT_ACK
        assert data["timestamp"] == TEST_TIMESTAMP


class TestRelayError:
    """Tests for RelayError (worker -> daemon)."""

    def test_creation(self) -> None:
        err = RelayError(message=TEST_TOOL_ERROR)
        assert err.type == CLOUD_RELAY_WS_TYPE_ERROR
        assert err.message == TEST_TOOL_ERROR
        assert err.code is None

    def test_with_code(self) -> None:
        err = RelayError(message=TEST_TOOL_ERROR, code="auth_failed")
        assert err.code == "auth_failed"

    def test_serialization(self) -> None:
        err = RelayError(message=TEST_TOOL_ERROR, code="timeout")
        data = json.loads(err.model_dump_json())
        assert data["type"] == CLOUD_RELAY_WS_TYPE_ERROR
        assert data["message"] == TEST_TOOL_ERROR
        assert data["code"] == "timeout"
