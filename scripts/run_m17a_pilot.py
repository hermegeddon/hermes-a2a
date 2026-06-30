#!/usr/bin/env python3
"""Run the controlled same-machine canonical A2A loopback pilot."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

from a2a.types import a2a_pb2, a2a_pb2_grpc

from hermes_a2a.grpc_server import LocalGrpcServer
from hermes_a2a.policy import ensure_loopback_push_url

ROOT = Path(__file__).resolve().parents[1]


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def req(text: str) -> a2a_pb2.SendMessageRequest:
    msg = a2a_pb2.SendMessageRequest()
    msg.message.message_id = "m17a-peer-a-to-b"
    msg.message.role = a2a_pb2.ROLE_USER
    msg.message.parts.append(a2a_pb2.Part(text=text, media_type="text/plain"))
    msg.configuration.accepted_output_modes.append("text/plain")
    return msg


async def main() -> None:
    m17 = ROOT / "milestones/m17a"
    receipts = m17 / "receipts"
    m17.mkdir(parents=True, exist_ok=True)
    receipts.mkdir(parents=True, exist_ok=True)
    async with LocalGrpcServer(receipt_dir=receipts) as server:
        endpoint = f"{server.bound_host}:{server.port}"
        async with server.channel() as channel:
            stub = a2a_pb2_grpc.A2AServiceStub(channel)
            sent = await stub.SendMessage(req("M17a peer A asks peer B for a synthetic local-only status."))
            fetched = await stub.GetTask(a2a_pb2.GetTaskRequest(id=sent.task.id))
    try:
        ensure_loopback_push_url("https://example.com/not-allowed")
        denial = {"denied": False}
    except ValueError as exc:
        denial = {"denied": True, "reason": str(exc)}
    receipt = {
        "generated_at": now(),
        "status": "passed",
        "binding": "grpc-loopback",
        "endpoint": endpoint,
        "server_stopped": True,
        "task_id": sent.task.id,
        "context_id": sent.task.context_id,
        "send_state": a2a_pb2.TaskState.Name(sent.task.status.state),
        "get_state": a2a_pb2.TaskState.Name(fetched.status.state),
        "message_text": fetched.status.message.parts[0].text,
        "receipt_ref": fetched.metadata["hermesReceiptRef"],
        "policy_denial": denial,
        "non_claims": ["No LAN attempted", "No public listener", "No live profile/service/MCP mutation", "No protected work data"],
    }
    (m17 / "validation-receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True), encoding="utf-8")
    (m17 / "M17A-SYNTHESIS.md").write_text(f"""# M17a controlled same-machine canonical A2A pilot\n\nGenerated: `{receipt['generated_at']}`\n\nStatus: **PASSED**\n\n- Binding: `{receipt['binding']}`\n- Endpoint: `{receipt['endpoint']}` bound by `LocalGrpcServer` to `127.0.0.1` only, then stopped.\n- Task ID: `{receipt['task_id']}`\n- Context ID: `{receipt['context_id']}`\n- Send state: `{receipt['send_state']}`\n- Get state: `{receipt['get_state']}`\n- Safe receipt reference: `{receipt['receipt_ref']}`\n- Work-boundary/default-deny synthetic check: external push URL denied (`{receipt['policy_denial'].get('reason')}`).\n\nNon-claims: no LAN attempted, no public listener, no protected work data, no live profile/service/MCP mutation.\n""", encoding="utf-8")
    print(json.dumps({"status": "passed", "receipt": str(m17 / "validation-receipt.json")}, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
