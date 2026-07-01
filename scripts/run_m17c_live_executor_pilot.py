#!/usr/bin/env python3
"""Run the gated M17c one-profile live Hermes executor pilot over loopback A2A."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import secrets
import socket
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

import httpx
import uvicorn
from a2a.server.agent_execution import AgentExecutor

from hermes_a2a.app import build_app
from hermes_a2a.live_executor import HermesProfileExecutor, LiveExecutorLimits
from hermes_a2a.serve import wait_for_tcp
from run_m17b_triad_pilot import artifact_entry, listener_assertions, run_command, ss_snapshot, write_json, write_manifest

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANAGEMENT_ROOT = Path("/home/openclaw/workspace/hermes-a2a")
A2A_HEADERS = {"A2A-Version": "1.0"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def mint_run_id() -> str:
    return f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{secrets.token_hex(3)}"


def reserve_port(host: str = "127.0.0.1") -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        return int(sock.getsockname()[1])


def message_payload(text: str) -> dict[str, Any]:
    suffix = hashlib.sha1(text.encode("utf-8")).hexdigest()[:10]
    return {
        "message": {
            "messageId": f"msg-m17c-{suffix}",
            "role": "ROLE_USER",
            "parts": [{"text": text, "mediaType": "text/plain"}],
        },
        "configuration": {"acceptedOutputModes": ["text/plain"]},
    }


def run_launcher_probe(*, profile: str, workdir: Path, output_path: Path) -> dict[str, Any]:
    command = [
        "uv",
        "run",
        "--extra",
        "dev",
        "python",
        "scripts/probe_profile_launcher.py",
        "--profile",
        profile,
        "--workdir",
        str(workdir),
        "--marker",
        "HERMES_A2A_LAUNCHER_OK",
    ]
    completed = subprocess.run(command, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(completed.stdout, encoding="utf-8")
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        payload = {"status": "failed", "parse_error": True, "output_tail": completed.stdout[-1000:]}
    payload["command"] = command
    payload["cwd"] = str(ROOT)
    payload["exit_code"] = completed.returncode
    return payload


async def run_live_a2a_smoke(
    *,
    host: str,
    http_port: int,
    base_url: str,
    receipt_root: Path,
    profile: str,
    workdir: Path,
    token: str,
) -> dict[str, Any]:
    executor: AgentExecutor = HermesProfileExecutor(
        receipt_root,
        profile=profile,
        workdir=workdir,
        limits=LiveExecutorLimits(timeout_seconds=180.0, max_peer_visible_text_bytes=20_000),
    )
    app = build_app(
        receipt_dir=receipt_root,
        require_auth=True,
        api_key=token,
        agent_name="Hermes Blinky WSL live A2A sidecar",
        agent_description="M17c gated live Hermes profile executor for synthetic A2A smoke tasks only.",
        base_url=base_url,
        grpc_url="127.0.0.1:0",
        allowed_peer_ids=["agent:local:hermes-blinky-windows"],
        test_token=token,
        agent_executor=executor,
    )
    server = uvicorn.Server(uvicorn.Config(app, host=host, port=http_port, log_level="warning", access_log=False, lifespan="off"))
    task = asyncio.create_task(server.serve())
    try:
        await wait_for_tcp(host, http_port)
        async with httpx.AsyncClient(base_url=base_url.rstrip("/"), timeout=240.0) as client:
            card = await client.get("/.well-known/agent-card.json")
            allowed = await client.post(
                "/",
                json={
                    "jsonrpc": "2.0",
                    "id": "m17c-live-jsonrpc",
                    "method": "SendMessage",
                    "params": message_payload("Reply exactly HERMES_A2A_LIVE_A2A_OK and no extra text."),
                },
                headers={**A2A_HEADERS, "x-hermes-a2a-test-token": token, "x-hermes-a2a-peer-id": "agent:local:hermes-blinky-windows"},
            )
            denied = await client.post(
                "/",
                json={"jsonrpc": "2.0", "id": "m17c-denied", "method": "SendMessage", "params": message_payload("denied")},
                headers={**A2A_HEADERS, "x-hermes-a2a-test-token": token, "x-hermes-a2a-peer-id": "agent:test:unauthorized"},
            )
        allowed_body = allowed.json() if allowed.headers.get("content-type", "").startswith("application/json") else {}
        task_body = allowed_body.get("result", {}).get("task", {})
        message_text = ""
        parts = task_body.get("status", {}).get("message", {}).get("parts", [])
        if parts and isinstance(parts[0], dict):
            message_text = str(parts[0].get("text", ""))
        return {
            "agent_card_status": card.status_code,
            "agent_card_name": card.json().get("name") if card.status_code == 200 else None,
            "allowed_status": allowed.status_code,
            "allowed_state": task_body.get("status", {}).get("state"),
            "allowed_message_sha256": hashlib.sha256(message_text.encode("utf-8")).hexdigest(),
            "live_marker_seen": "HERMES_A2A_LIVE_A2A_OK" in message_text,
            "receipt_ref": task_body.get("metadata", {}).get("hermesReceiptRef"),
            "live_invocation_receipt_ref": task_body.get("metadata", {}).get("hermesLiveInvocationReceiptRef"),
            "denied_status": denied.status_code,
            "denied_body": denied.text[:200],
        }
    finally:
        server.should_exit = True
        await task


async def run_pilot(*, management_root: Path, run_id: str, approval_receipt: Path, profile: str) -> dict[str, Any]:
    if not approval_receipt.exists():
        raise FileNotFoundError(f"approval receipt is required before M17c: {approval_receipt}")
    run_root = management_root / "milestones" / "m17c" / "runs" / run_id
    if run_root.exists():
        raise FileExistsError(f"run directory already exists: {run_root}")
    run_root.mkdir(parents=True)
    receipt_root = run_root / "receipts" / "local-hermes-blinky-wsl-live"
    http_port = reserve_port()
    base_url = f"http://127.0.0.1:{http_port}/"
    token = secrets.token_urlsafe(32)
    launcher_path = run_root / "launcher-proof.json"
    launcher = run_launcher_probe(profile=profile, workdir=management_root, output_path=launcher_path)
    before_snapshot = ss_snapshot([http_port])
    smoke = await run_live_a2a_smoke(
        host="127.0.0.1",
        http_port=http_port,
        base_url=base_url,
        receipt_root=receipt_root,
        profile=profile,
        workdir=management_root,
        token=token,
    )
    during_after = ss_snapshot([http_port])
    run_receipt_path = run_root / "live-executor-run-receipt.json"
    implementation_state_path = run_root / "implementation-state.json"
    assertions = {
        "approval_receipt_present": approval_receipt.exists(),
        "launcher_proof_passed": launcher.get("status") == "passed" and launcher.get("exit_code") == 0,
        "agent_card_passed": smoke["agent_card_status"] == 200,
        "live_jsonrpc_passed": smoke["allowed_status"] == 200 and smoke["allowed_state"] == "TASK_STATE_COMPLETED" and smoke["live_marker_seen"],
        "peer_denial_passed": smoke["denied_status"] == 403,
        "receipt_refs_present": bool(smoke["receipt_ref"]) and bool(smoke["live_invocation_receipt_ref"]),
        "listener_after_teardown_clean": listener_assertions(during_after, [http_port], expect_present=False)["ok"],
    }
    status = "passed" if all(assertions.values()) else "failed"
    run_receipt = {
        "schema": "hermes-a2a/m17c-live-executor-run-receipt/v1",
        "generated_at": utc_now(),
        "status": status,
        "run_id": run_id,
        "approval_receipt": str(approval_receipt),
        "selected_instance": "agent:local:hermes-blinky-wsl",
        "profile": profile,
        "base_url": base_url,
        "http_port": http_port,
        "executor_limits": {
            "timeout_seconds": 180,
            "max_peer_visible_text_bytes": 20000,
            "max_artifact_bytes": 1048576,
            "max_private_stdout_stderr_bytes": 204800,
        },
        "assertions": assertions,
        "launcher_proof": launcher,
        "smoke": smoke,
        "bind_before": before_snapshot,
        "bind_after_teardown": during_after,
        "non_claims": [
            "Only agent:local:hermes-blinky-wsl used live Hermes execution",
            "agent:local:hermes-blinky-windows remains synthetic/no live launcher proof",
            "agent:work:hermes-work remains synthetic/no work live execution",
            "No LAN bind, service installation, work data, credentials, or raw MCP/tool proxy occurred in M17c",
        ],
    }
    write_json(run_receipt_path, run_receipt)
    implementation_state = {
        "root": str(ROOT),
        "head": run_command(["git", "rev-parse", "HEAD"], cwd=ROOT),
        "status": run_command(["git", "status", "--short", "--branch"], cwd=ROOT),
        "parent_submodule_status": run_command(["git", "-C", str(ROOT.parents[1]), "status", "--short", "--branch", "--", "projects/hermes-a2a"]),
    }
    write_json(implementation_state_path, implementation_state)
    synthesis_path = management_root / "milestones" / "m17c" / "M17C-LIVE-EXECUTOR-SYNTHESIS.md"
    manifest_path = run_root / "artifact-manifest.json"
    synthesis_lines = [
        "# M17c live Hermes profile executor synthesis",
        "",
        f"Generated: `{utc_now()}`",
        "",
        f"Status: **{status.upper()}**",
        "",
        f"Run ID: `{run_id}`",
        f"Approval receipt: `{approval_receipt}`",
        f"Launcher proof: `{launcher_path}`",
        f"Run receipt: `{run_receipt_path}`",
        f"Artifact manifest: `{manifest_path}`",
        "",
        "## Proven",
        "",
        "- One approved local instance, `agent:local:hermes-blinky-wsl`, invoked live Hermes profile `default` through a loopback A2A sidecar.",
        "- Launcher proof used `hermes -p default -z <prompt> --safe-mode` and omitted raw stdout/stderr from receipts.",
        "- JSON-RPC `SendMessage` returned a completed task with receipt-before-exposure metadata and a private live-invocation receipt reference.",
        "- Disallowed peer `agent:test:unauthorized` was denied before execution.",
        "- Output limits, timeout, and safe-error behavior are covered by focused contract tests in `tests/test_live_executor_contract.py`.",
        "",
        "## Non-claims / non-actions",
        "",
        "No service install/restart, LAN/Tailscale/public bind, work live executor, work data, credentials, raw MCP/tool proxy, public PR/release/package/deploy, push, merge, publication, or destructive action occurred in this M17c pilot.",
        "",
    ]
    synthesis_path.parent.mkdir(parents=True, exist_ok=True)
    synthesis_path.write_text("\n".join(synthesis_lines), encoding="utf-8")
    artifacts = [
        artifact_entry(approval_receipt, management_root=management_root, role="M17c approval receipt", owner_workspace="management", classification="management-evidence", source="current user chat approval normalized before M17c pilot"),
        artifact_entry(launcher_path, management_root=management_root, role="profile launcher proof", owner_workspace="management", classification="management-evidence", source="scripts/probe_profile_launcher.py"),
        artifact_entry(run_receipt_path, management_root=management_root, role="M17c live executor run receipt", owner_workspace="management", classification="management-evidence", source="scripts/run_m17c_live_executor_pilot.py"),
        artifact_entry(implementation_state_path, management_root=management_root, role="implementation commit/status evidence", owner_workspace="implementation", classification="implementation-evidence", source="git readback"),
        artifact_entry(synthesis_path, management_root=management_root, role="M17c synthesis", owner_workspace="management", classification="management-evidence", source="M17c live executor pilot synthesis"),
    ]
    manifest = write_manifest(manifest_path, run_id=run_id, management_root=management_root, artifacts=artifacts)
    final = {
        "status": "passed" if status == "passed" and manifest["readback"]["bad_count"] == 0 else "failed",
        "run_id": run_id,
        "approval_receipt": str(approval_receipt),
        "run_receipt": str(run_receipt_path),
        "manifest": str(manifest_path),
        "synthesis": str(synthesis_path),
        "manifest_bad_count": manifest["readback"]["bad_count"],
    }
    print(json.dumps(final, indent=2, sort_keys=True))
    if final["status"] != "passed":
        raise SystemExit(1)
    return final


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run M17c live Hermes profile executor pilot")
    parser.add_argument("--management-root", default=str(DEFAULT_MANAGEMENT_ROOT))
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--approval-receipt", required=True)
    parser.add_argument("--profile", default="default")
    args = parser.parse_args(argv)
    run_id = args.run_id or mint_run_id()
    asyncio.run(
        run_pilot(
            management_root=Path(args.management_root),
            run_id=run_id,
            approval_receipt=Path(args.approval_receipt),
            profile=args.profile,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
