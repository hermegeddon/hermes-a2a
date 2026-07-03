import pytest
import httpx

from hermes_a2a.app import build_app

A2A_HEADERS = {"A2A-Version": "1.0"}


def _message_payload(text: str = "hello") -> dict:
    return {
        "message": {
            "messageId": "msg-test-1",
            "role": "ROLE_USER",
            "parts": [{"text": text, "mediaType": "text/plain"}],
        },
        "configuration": {"acceptedOutputModes": ["text/plain"]},
    }


@pytest.mark.asyncio
async def test_agent_card_is_public_safe_and_declares_bindings(tmp_path):
    app = build_app(receipt_dir=tmp_path / "receipts", require_auth=False)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1") as client:
        response = await client.get("/.well-known/agent-card.json")

    assert response.status_code == 200
    card = response.json()
    assert card["name"] == "Hermes A2A Local"
    assert {i["protocolBinding"] for i in card["supportedInterfaces"]} >= {"JSONRPC", "HTTP+JSON", "GRPC"}
    rendered = response.text
    assert "/home/example" not in rendered
    assert ".hermes" not in rendered
    assert "mcp" not in rendered.lower()
    assert "sk-" not in rendered


@pytest.mark.asyncio
async def test_jsonrpc_send_message_creates_completed_receipted_task(tmp_path):
    app = build_app(receipt_dir=tmp_path / "receipts", require_auth=False)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1") as client:
        response = await client.post(
            "/",
            json={"jsonrpc": "2.0", "id": "1", "method": "SendMessage", "params": _message_payload("ping")},
            headers=A2A_HEADERS,
        )

    assert response.status_code == 200
    body = response.json()
    assert "error" not in body
    task = body["result"]["task"]
    assert task["status"]["state"] == "TASK_STATE_COMPLETED"
    assert task["status"]["message"]["parts"][0]["text"] == "Hermes A2A local echo: ping"
    assert task["metadata"]["hermesReceiptRef"].startswith("receipts/")


@pytest.mark.asyncio
async def test_rest_send_and_get_task_are_equivalent_to_jsonrpc(tmp_path):
    app = build_app(receipt_dir=tmp_path / "receipts", require_auth=False)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1") as client:
        send = await client.post("/message:send", json=_message_payload("rest ping"), headers=A2A_HEADERS)
        task_id = send.json()["task"]["id"]
        fetched = await client.get(f"/tasks/{task_id}", headers=A2A_HEADERS)

    assert send.status_code == 200
    assert fetched.status_code == 200
    assert fetched.json()["id"] == task_id
    assert fetched.json()["status"]["state"] == "TASK_STATE_COMPLETED"
    assert fetched.json()["status"]["message"]["parts"][0]["text"] == "Hermes A2A local echo: rest ping"


@pytest.mark.asyncio
async def test_extended_agent_card_requires_auth_when_enabled(tmp_path):
    app = build_app(receipt_dir=tmp_path / "receipts", require_auth=True, api_key="test-key")
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1") as client:
        denied = await client.get("/extendedAgentCard", headers=A2A_HEADERS)
        allowed = await client.get("/extendedAgentCard", headers={**A2A_HEADERS, "x-hermes-a2a-key": "test-key"})

    assert denied.status_code in {400, 401, 403}
    assert "secret" not in denied.text.lower()
    assert allowed.status_code == 200
    assert allowed.json()["name"] == "Hermes A2A Local"


@pytest.mark.asyncio
async def test_test_ephemeral_auth_fails_closed_without_token(tmp_path):
    app = build_app(
        receipt_dir=tmp_path / "receipts",
        require_auth=True,
        test_token=None,
        allowed_peer_ids=["agent:local:peer"],
    )
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1") as client:
        card = await client.get("/.well-known/agent-card.json")
        denied = await client.post(
            "/",
            json={"jsonrpc": "2.0", "id": "1", "method": "SendMessage", "params": _message_payload("ping")},
            headers={**A2A_HEADERS, "x-hermes-a2a-peer-id": "agent:local:peer"},
        )

    assert card.status_code == 200
    assert denied.status_code == 403
    assert "token unavailable" in denied.text


@pytest.mark.asyncio
async def test_test_ephemeral_auth_allows_only_matching_token_and_peer(tmp_path):
    app = build_app(
        receipt_dir=tmp_path / "receipts",
        require_auth=True,
        test_token="unit-token",
        allowed_peer_ids=["agent:local:peer"],
    )
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1") as client:
        denied = await client.post(
            "/",
            json={"jsonrpc": "2.0", "id": "bad", "method": "SendMessage", "params": _message_payload("bad")},
            headers={**A2A_HEADERS, "x-hermes-a2a-test-token": "wrong", "x-hermes-a2a-peer-id": "agent:local:peer"},
        )
        allowed = await client.post(
            "/",
            json={"jsonrpc": "2.0", "id": "good", "method": "SendMessage", "params": _message_payload("good")},
            headers={**A2A_HEADERS, "x-hermes-a2a-test-token": "unit-token", "x-hermes-a2a-peer-id": "agent:local:peer"},
        )

    assert denied.status_code == 403
    assert allowed.status_code == 200
    assert allowed.json()["result"]["task"]["status"]["state"] == "TASK_STATE_COMPLETED"
