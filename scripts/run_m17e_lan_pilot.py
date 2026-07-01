#!/usr/bin/env python3
"""Run a bounded M17e local-network Agent Card/A2A pilot and record any remaining reachability blocker."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import secrets
import socket
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

import httpx
import uvicorn

from hermes_a2a.app import build_app
from hermes_a2a.executor import SafeEchoExecutor
from hermes_a2a.serve import wait_for_tcp
from run_m17b_triad_pilot import artifact_entry, listener_assertions, message_payload, run_command, ss_snapshot, write_json, write_manifest

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANAGEMENT_ROOT = Path("/home/openclaw/workspace/hermes-a2a")
DEFAULT_LAN_HOST = "192.168.1.3"
DEFAULT_HTTP_PORT = 18751
A2A_HEADERS = {"A2A-Version": "1.0"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def mint_run_id() -> str:
    return f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{secrets.token_hex(3)}"


def local_ipv4_addresses() -> list[str]:
    result = run_command(["ip", "-4", "-brief", "addr", "show", "scope", "global"])
    addresses: list[str] = []
    for line in str(result.get("output", "")).splitlines():
        parts = line.split()
        for part in parts[2:]:
            if "/" in part:
                addresses.append(part.split("/", 1)[0])
    return addresses


def assert_port_free(host: str, port: int) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((host, port))


async def run_lan_smoke(*, host: str, port: int, base_url: str, receipt_root: Path, token: str) -> dict[str, Any]:
    app = build_app(
        receipt_dir=receipt_root,
        require_auth=True,
        api_key=token,
        agent_name="Hermes Blinky WSL LAN synthetic sidecar",
        agent_description="M17e bounded local-network synthetic A2A pilot; no live/work data.",
        base_url=base_url,
        grpc_url="127.0.0.1:0",
        allowed_peer_ids=["agent:local:hermes-blinky-windows"],
        test_token=token,
        agent_executor=SafeEchoExecutor(receipt_root),
    )
    server = uvicorn.Server(uvicorn.Config(app, host=host, port=port, log_level="warning", access_log=False, lifespan="off"))
    task = asyncio.create_task(server.serve())
    try:
        await wait_for_tcp(host, port)
        async with httpx.AsyncClient(base_url=base_url.rstrip("/"), timeout=10.0, trust_env=False) as client:
            card = await client.get("/.well-known/agent-card.json")
            allowed = await client.post(
                "/",
                json={"jsonrpc": "2.0", "id": "m17e-lan-jsonrpc", "method": "SendMessage", "params": message_payload("M17e LAN synthetic smoke")},
                headers={**A2A_HEADERS, "x-hermes-a2a-test-token": token, "x-hermes-a2a-peer-id": "agent:local:hermes-blinky-windows"},
            )
            denied = await client.post(
                "/",
                json={"jsonrpc": "2.0", "id": "m17e-denied", "method": "SendMessage", "params": message_payload("denied")},
                headers={**A2A_HEADERS, "x-hermes-a2a-test-token": token, "x-hermes-a2a-peer-id": "agent:test:unauthorized"},
            )
        body = allowed.json() if allowed.headers.get("content-type", "").startswith("application/json") else {}
        task_body = body.get("result", {}).get("task", {})
        return {
            "agent_card_status": card.status_code,
            "agent_card_name": card.json().get("name") if card.status_code == 200 else None,
            "agent_card_url": f"{base_url.rstrip('/')}/.well-known/agent-card.json",
            "allowed_status": allowed.status_code,
            "allowed_state": task_body.get("status", {}).get("state"),
            "receipt_ref": task_body.get("metadata", {}).get("hermesReceiptRef"),
            "denied_status": denied.status_code,
        }
    finally:
        server.should_exit = True
        await task


async def run_pilot(
    *,
    management_root: Path,
    run_id: str,
    approval_receipt: Path,
    host: str,
    port: int,
    negative_reachability_receipt: Path | None,
) -> dict[str, Any]:
    if not approval_receipt.exists():
        raise FileNotFoundError(f"approval receipt is required before M17e: {approval_receipt}")
    addresses = local_ipv4_addresses()
    if host not in addresses:
        raise RuntimeError(f"requested LAN host {host} is not one of observed IPv4 addresses: {addresses}")
    run_root = management_root / "milestones" / "m17e" / "runs" / run_id
    if run_root.exists():
        raise FileExistsError(f"run directory already exists: {run_root}")
    run_root.mkdir(parents=True)
    receipt_root = run_root / "receipts" / "local-hermes-blinky-wsl-lan-synthetic"
    receipt_root.mkdir(parents=True, exist_ok=True)
    assert_port_free(host, port)
    base_url = f"http://{host}:{port}/"
    token = secrets.token_urlsafe(32)
    before_snapshot = ss_snapshot([port])
    during_snapshot: dict[str, Any] = {}
    smoke: dict[str, Any] = {}
    app_task = asyncio.create_task(run_lan_smoke(host=host, port=port, base_url=base_url, receipt_root=receipt_root, token=token))
    try:
        await wait_for_tcp(host, port)
        during_snapshot = ss_snapshot([port])
        smoke = await app_task
    finally:
        if not app_task.done():
            app_task.cancel()
            try:
                await app_task
            except asyncio.CancelledError:
                pass
    after_snapshot = ss_snapshot([port])
    local_field_values = list(listener_assertions(during_snapshot, [port], expect_present=True).get("local_fields", {}).values())
    negative_proof_present = negative_reachability_receipt is not None and negative_reachability_receipt.exists()
    assertions = {
        "approval_receipt_present": approval_receipt.exists(),
        "lan_host_observed": host in addresses,
        "agent_card_passed": smoke.get("agent_card_status") == 200,
        "jsonrpc_passed": smoke.get("allowed_status") == 200 and smoke.get("allowed_state") == "TASK_STATE_COMPLETED",
        "peer_denial_passed": smoke.get("denied_status") == 403,
        "no_wildcard_listener": all(not value.startswith("0.0.0.0:") and not value.startswith("[::]:") for value in local_field_values),
        "bound_expected_lan_host": any(value.endswith(f"{host}:{port}") for value in local_field_values),
        "teardown_clean": listener_assertions(after_snapshot, [port], expect_present=False)["ok"],
        "negative_unlisted_host_proof_present": negative_proof_present,
    }
    status = "passed" if all(assertions.values()) else "blocked"
    run_receipt_path = run_root / "lan-pilot-receipt.json"
    bind_path = run_root / "bind-evidence.json"
    implementation_state_path = run_root / "implementation-state.json"
    run_receipt = {
        "schema": "hermes-a2a/m17e-lan-pilot-receipt/v1",
        "generated_at": utc_now(),
        "status": status,
        "run_id": run_id,
        "approval_receipt": str(approval_receipt),
        "negative_reachability_receipt": str(negative_reachability_receipt) if negative_reachability_receipt else None,
        "selected_instance": "agent:local:hermes-blinky-wsl",
        "host": host,
        "http_port": port,
        "base_url": base_url,
        "observed_ipv4_addresses": addresses,
        "assertions": assertions,
        "smoke": smoke,
        "blocker": None if status == "passed" else "M17e acceptance still needs negative reachability proof from an unlisted host or a documented equivalent network ACL/firewall deny receipt.",
        "non_claims": [
            "Synthetic HTTP/JSON-RPC LAN pilot only",
            "No live-over-LAN executor",
            "No gRPC LAN listener",
            "No wildcard/public/tunnel listener",
            "No work data, credentials, raw MCP/tool proxy, public PR/release/package/deploy, push, merge, or publication",
        ],
    }
    bind_evidence = {
        "before": before_snapshot,
        "during": during_snapshot,
        "after": after_snapshot,
        "during_assertions": listener_assertions(during_snapshot, [port], expect_present=True),
        "after_assertions": listener_assertions(after_snapshot, [port], expect_present=False),
    }
    implementation_state = {
        "root": str(ROOT),
        "head": run_command(["git", "rev-parse", "HEAD"], cwd=ROOT),
        "status": run_command(["git", "status", "--short", "--branch"], cwd=ROOT),
        "parent_submodule_status": run_command(["git", "-C", str(ROOT.parents[1]), "status", "--short", "--branch", "--", "projects/hermes-a2a"]),
    }
    write_json(run_receipt_path, run_receipt)
    write_json(bind_path, bind_evidence)
    write_json(implementation_state_path, implementation_state)
    synthesis_path = management_root / "milestones" / "m17e" / "M17E-SYNTHESIS.md"
    manifest_path = run_root / "artifact-manifest.json"
    lines = [
        "# M17e local-network pilot synthesis",
        "",
        f"Generated: `{utc_now()}`",
        "",
        f"Status: **{status.upper()}**",
        "",
        f"Run ID: `{run_id}`",
        f"Approval receipt: `{approval_receipt}`",
        f"Run receipt: `{run_receipt_path}`",
        f"Artifact manifest: `{manifest_path}`",
        "",
        "## Proven",
        "",
        f"- Bound one foreground synthetic HTTP sidecar to the named local-network address `{host}:{port}` (not wildcard).",
        "- Fetched the Agent Card and completed a synthetic JSON-RPC A2A task through the LAN address from the local host.",
        "- Disallowed peer `agent:test:unauthorized` was denied before execution.",
        "- Teardown readback found no selected-port listener after the pilot stopped.",
        "",
        "## Blocker" if status != "passed" else "## Remaining evidence",
        "",
        "M17e is not marked passed because no negative reachability proof from an unlisted host, or documented equivalent network ACL/firewall deny receipt, was available in this single-host session." if status != "passed" else "Negative reachability proof was supplied.",
        "",
        "## Non-claims / non-actions",
        "",
        "No live-over-LAN executor, gRPC LAN listener, wildcard/public/tunnel listener, work data, credentials, raw MCP/tool proxy, public PR/release/package/deploy, push, merge, publication, or destructive action occurred in M17e.",
        "",
    ]
    synthesis_path.parent.mkdir(parents=True, exist_ok=True)
    synthesis_path.write_text("\n".join(lines), encoding="utf-8")
    artifacts = [
        artifact_entry(approval_receipt, management_root=management_root, role="M17e approval receipt", owner_workspace="management", classification="management-evidence", source="current user chat approval normalized before LAN pilot"),
        artifact_entry(run_receipt_path, management_root=management_root, role="M17e LAN pilot receipt", owner_workspace="management", classification="management-evidence", source="scripts/run_m17e_lan_pilot.py"),
        artifact_entry(bind_path, management_root=management_root, role="LAN bind and teardown evidence", owner_workspace="management", classification="management-evidence", source="ss -ltnp readback"),
        artifact_entry(implementation_state_path, management_root=management_root, role="implementation commit/status evidence", owner_workspace="implementation", classification="implementation-evidence", source="git readback"),
        artifact_entry(synthesis_path, management_root=management_root, role="M17e synthesis", owner_workspace="management", classification="management-evidence", source="LAN pilot synthesis"),
    ]
    manifest = write_manifest(manifest_path, run_id=run_id, management_root=management_root, artifacts=artifacts)
    final = {
        "status": status if manifest["readback"]["bad_count"] == 0 else "failed",
        "run_id": run_id,
        "approval_receipt": str(approval_receipt),
        "run_receipt": str(run_receipt_path),
        "manifest": str(manifest_path),
        "synthesis": str(synthesis_path),
        "manifest_bad_count": manifest["readback"]["bad_count"],
        "blocker": run_receipt["blocker"],
    }
    print(json.dumps(final, indent=2, sort_keys=True))
    return final


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run bounded M17e LAN pilot")
    parser.add_argument("--management-root", default=str(DEFAULT_MANAGEMENT_ROOT))
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--approval-receipt", required=True)
    parser.add_argument("--host", default=DEFAULT_LAN_HOST)
    parser.add_argument("--http-port", type=int, default=DEFAULT_HTTP_PORT)
    parser.add_argument("--negative-reachability-receipt", default=None)
    args = parser.parse_args(argv)
    final = asyncio.run(
        run_pilot(
            management_root=Path(args.management_root),
            run_id=args.run_id or mint_run_id(),
            approval_receipt=Path(args.approval_receipt),
            host=args.host,
            port=args.http_port,
            negative_reachability_receipt=Path(args.negative_reachability_receipt) if args.negative_reachability_receipt else None,
        )
    )
    return 0 if final["status"] in {"passed", "blocked"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
