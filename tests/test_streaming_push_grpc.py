import pytest
import httpx

from a2a.types import a2a_pb2, a2a_pb2_grpc
from hermes_a2a.app import build_app
from hermes_a2a.grpc_server import LocalGrpcServer

A2A_HEADERS = {"A2A-Version": "1.0"}


def message_request(text: str = "hello") -> dict:
    return {
        "message": {
            "messageId": "msg-stream-1",
            "role": "ROLE_USER",
            "parts": [{"text": text, "mediaType": "text/plain"}],
        },
        "configuration": {"acceptedOutputModes": ["text/plain"]},
    }


def proto_request(text: str = "hello") -> a2a_pb2.SendMessageRequest:
    req = a2a_pb2.SendMessageRequest()
    req.message.message_id = "msg-grpc-1"
    req.message.role = a2a_pb2.ROLE_USER
    req.message.parts.append(a2a_pb2.Part(text=text, media_type="text/plain"))
    req.configuration.accepted_output_modes.append("text/plain")
    return req


@pytest.mark.asyncio
async def test_jsonrpc_streaming_uses_sse_and_receipted_completion(tmp_path):
    app = build_app(receipt_dir=tmp_path / "receipts", require_auth=False)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1") as client:
        response = await client.post(
            "/",
            json={"jsonrpc": "2.0", "id": "s1", "method": "SendStreamingMessage", "params": message_request("stream ping")},
            headers=A2A_HEADERS,
        )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "TASK_STATE_COMPLETED" in response.text
    assert "hermesReceiptRef" in response.text


@pytest.mark.asyncio
async def test_push_config_route_denies_external_and_accepts_loopback(tmp_path):
    app = build_app(receipt_dir=tmp_path / "receipts", require_auth=False)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1") as client:
        send = await client.post("/message:send", json=message_request("push seed"), headers=A2A_HEADERS)
        task_id = send.json()["task"]["id"]
        denied = await client.post(
            f"/tasks/{task_id}/pushNotificationConfigs",
            json={"id": "cfg-ext", "taskId": task_id, "url": "https://example.com/hook"},
            headers=A2A_HEADERS,
        )
        allowed = await client.post(
            f"/tasks/{task_id}/pushNotificationConfigs",
            json={"id": "cfg-loop", "taskId": task_id, "url": "http://127.0.0.1:9999/hook"},
            headers=A2A_HEADERS,
        )

    assert denied.status_code == 400
    assert "loopback" in denied.text
    assert "example.com" not in denied.text
    assert allowed.status_code == 200
    assert allowed.json()["url"] == "http://127.0.0.1:9999/hook"


@pytest.mark.asyncio
async def test_grpc_send_and_get_task_over_loopback(tmp_path):
    async with LocalGrpcServer(receipt_dir=tmp_path / "receipts") as server:
        assert server.bound_host == "127.0.0.1"
        assert server.port > 0
        async with server.channel() as channel:
            stub = a2a_pb2_grpc.A2AServiceStub(channel)
            sent = await stub.SendMessage(proto_request("grpc ping"))
            assert sent.task.status.state == a2a_pb2.TASK_STATE_COMPLETED
            fetched = await stub.GetTask(a2a_pb2.GetTaskRequest(id=sent.task.id))

    assert fetched.status.state == a2a_pb2.TASK_STATE_COMPLETED
    assert fetched.status.message.parts[0].text == "Hermes A2A local echo: grpc ping"
    assert fetched.metadata["hermesReceiptRef"]
