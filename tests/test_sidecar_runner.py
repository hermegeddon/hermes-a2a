from __future__ import annotations

from pathlib import Path

import grpc
import httpx
import pytest
import yaml
from a2a.types import a2a_pb2, a2a_pb2_grpc

from hermes_a2a.config import load_instances_config
from hermes_a2a.serve import SidecarRuntime
from scripts.run_m17b_triad_pilot import default_config_data, message_payload, reserve_ports

RUN_ID = "20260701T000001Z-abcdef"
A2A_HEADERS = {"A2A-Version": "1.0"}


def write_config(tmp_path: Path):  # type: ignore[no-untyped-def]
    data = default_config_data(tmp_path, RUN_ID, reserve_ports(6))
    config_path = tmp_path / "instances" / "instances.yaml"
    config_path.parent.mkdir(parents=True)
    config_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return load_instances_config(config_path, run_id=RUN_ID, management_root=tmp_path)


@pytest.mark.asyncio
async def test_sidecar_runtime_serves_instance_card_auth_and_grpc(tmp_path: Path) -> None:
    config = write_config(tmp_path)
    instance = config.instances[0]
    token = "unit-test-token"
    allowed_headers = {
        **A2A_HEADERS,
        "x-hermes-a2a-test-token": token,
        "x-hermes-a2a-peer-id": instance.allowed_peer_ids[0],
    }
    denied_headers = {
        **A2A_HEADERS,
        "x-hermes-a2a-test-token": token,
        "x-hermes-a2a-peer-id": "agent:test:unauthorized",
    }

    async with SidecarRuntime(instance, test_token=token):
        async with httpx.AsyncClient(base_url=instance.agent_card.base_url.rstrip("/"), timeout=5.0) as client:
            card = await client.get("/.well-known/agent-card.json")
            allowed = await client.post(
                "/",
                json={"jsonrpc": "2.0", "id": "unit-jsonrpc", "method": "SendMessage", "params": message_payload("unit")},
                headers=allowed_headers,
            )
            denied = await client.post(
                "/",
                json={"jsonrpc": "2.0", "id": "unit-denied", "method": "SendMessage", "params": message_payload("denied")},
                headers=denied_headers,
            )
        assert instance.bind.grpc_port is not None
        async with grpc.aio.insecure_channel(f"{instance.bind.host}:{instance.bind.grpc_port}") as channel:
            stub = a2a_pb2_grpc.A2AServiceStub(channel)
            req = a2a_pb2.SendMessageRequest()
            req.message.message_id = "unit-grpc"
            req.message.role = a2a_pb2.ROLE_USER
            req.message.parts.append(a2a_pb2.Part(text="grpc unit", media_type="text/plain"))
            req.configuration.accepted_output_modes.append("text/plain")
            grpc_sent = await stub.SendMessage(req)

    assert card.status_code == 200
    card_body = card.json()
    assert card_body["name"] == instance.agent_card.name
    assert {item["protocolBinding"] for item in card_body["supportedInterfaces"]} == {"GRPC", "HTTP+JSON", "JSONRPC"}
    assert allowed.status_code == 200
    task = allowed.json()["result"]["task"]
    assert task["status"]["state"] == "TASK_STATE_COMPLETED"
    assert task["metadata"]["hermesReceiptRef"].startswith("receipts/")
    assert denied.status_code == 403
    assert grpc_sent.task.status.state == a2a_pb2.TASK_STATE_COMPLETED
    assert list(instance.receipt_root.glob("receipt-*.json"))
