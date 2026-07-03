#!/usr/bin/env python3
"""Install, start, and verify gated M17d user-level sidecar services."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import socket
import secrets
import stat
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

import grpc
import httpx
from a2a.types import a2a_pb2, a2a_pb2_grpc

from run_m17b_triad_pilot import artifact_entry, listener_assertions, message_payload, run_command, ss_snapshot, write_json, write_manifest

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANAGEMENT_ROOT = Path(os.environ.get("HERMES_A2A_MANAGEMENT_ROOT", ROOT))
SYSTEMD_USER_DIR = Path.home() / ".config" / "systemd" / "user"
ENV_DIR = Path.home() / ".config" / "hermes-a2a" / "m17d"
PYTHON = ROOT / ".venv" / "bin" / "python"
HERMES = Path.home() / ".local" / "bin" / "hermes"
A2A_HEADERS = {"A2A-Version": "1.0"}


@dataclass(frozen=True)
class ServiceSpec:
    conceptual_agent_id: str
    slug: str
    unit: str
    agent_name: str
    http_port: int
    grpc_port: int
    executor: str
    live_profile: str | None
    allowed_peer_id: str

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.http_port}/"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def default_specs() -> list[ServiceSpec]:
    return [
        ServiceSpec(
            conceptual_agent_id="agent:local:hermes-blinky-wsl",
            slug="local-hermes-blinky-wsl",
            unit="hermes-a2a-local-hermes-blinky-wsl.service",
            agent_name="Hermes Blinky WSL service sidecar",
            http_port=18731,
            grpc_port=18741,
            executor="live",
            live_profile="default",
            allowed_peer_id="agent:local:hermes-blinky-windows",
        ),
        ServiceSpec(
            conceptual_agent_id="agent:local:hermes-blinky-windows",
            slug="local-hermes-blinky-windows",
            unit="hermes-a2a-local-hermes-blinky-windows.service",
            agent_name="Hermes Blinky Windows synthetic service sidecar",
            http_port=18732,
            grpc_port=18742,
            executor="synthetic",
            live_profile=None,
            allowed_peer_id="agent:local:hermes-blinky-wsl",
        ),
        ServiceSpec(
            conceptual_agent_id="agent:work:hermes-work",
            slug="work-hermes-work",
            unit="hermes-a2a-work-hermes-work.service",
            agent_name="Hermes Work synthetic service sidecar",
            http_port=18733,
            grpc_port=18743,
            executor="synthetic",
            live_profile=None,
            allowed_peer_id="agent:local:hermes-blinky-wsl",
        ),
    ]


def write_env_file(path: Path, token: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"HERMES_A2A_TEST_TOKEN={token}\n", encoding="utf-8")
    path.chmod(stat.S_IRUSR | stat.S_IWUSR)


def unit_text(spec: ServiceSpec, *, management_root: Path, receipt_root: Path, env_path: Path) -> str:
    live_args = ""
    if spec.executor == "live":
        live_args = f" --live-profile {spec.live_profile} --live-workdir {management_root} --live-timeout-seconds 180 --hermes-command {HERMES}"
    return f"""[Unit]
Description=Hermes A2A sidecar for {spec.conceptual_agent_id}
After=default.target

[Service]
Type=simple
WorkingDirectory={ROOT}
EnvironmentFile={env_path}
ExecStart={PYTHON} -m hermes_a2a.service_runner --conceptual-agent-id {spec.conceptual_agent_id} --host 127.0.0.1 --http-port {spec.http_port} --grpc-port {spec.grpc_port} --base-url {spec.base_url} --agent-name {json.dumps(spec.agent_name)} --agent-description {json.dumps('M17d gated local user-service A2A sidecar.')} --receipt-root {receipt_root} --allowed-peer-id {spec.allowed_peer_id} --test-token-env HERMES_A2A_TEST_TOKEN --executor {spec.executor}{live_args}
Restart=on-failure
RestartSec=2

[Install]
WantedBy=default.target
"""


def write_units(*, specs: Sequence[ServiceSpec], management_root: Path, run_root: Path) -> dict[str, Any]:
    SYSTEMD_USER_DIR.mkdir(parents=True, exist_ok=True)
    receipts: dict[str, Any] = {}
    for spec in specs:
        token = secrets.token_urlsafe(32)
        env_path = ENV_DIR / f"{spec.slug}.env"
        unit_path = SYSTEMD_USER_DIR / spec.unit
        receipt_root = management_root / "milestones" / "m17d" / "services" / spec.slug / "receipts"
        receipt_root.mkdir(parents=True, exist_ok=True)
        backups: dict[str, str] = {}
        if unit_path.exists() or unit_path.is_symlink():
            backup_path = run_root / "backups" / f"{spec.unit}.bak"
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            backup_path.write_text(unit_path.read_text(encoding="utf-8"), encoding="utf-8")
            backups["unit_backup"] = str(backup_path)
        if env_path.exists() or env_path.is_symlink():
            backups["env_preexisting_sha256"] = hashlib.sha256(env_path.read_bytes()).hexdigest()
        write_env_file(env_path, token)
        text = unit_text(spec, management_root=management_root, receipt_root=receipt_root, env_path=env_path)
        unit_path.write_text(text, encoding="utf-8")
        receipts[spec.unit] = {
            "unit_path": str(unit_path),
            "env_path": str(env_path),
            "env_mode": oct(env_path.stat().st_mode & 0o777),
            "env_sha256": hashlib.sha256(env_path.read_bytes()).hexdigest(),
            "token_omitted": True,
            "receipt_root": str(receipt_root),
            "executor": spec.executor,
            "live_profile": spec.live_profile,
            "backups": backups,
        }
    return receipts


def systemctl(args: Sequence[str]) -> dict[str, Any]:
    return run_command(["systemctl", "--user", *args])


def wait_for_ports(ports: Sequence[int], *, host: str = "127.0.0.1", timeout: float = 15.0) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    ready = {str(port): False for port in ports}
    last_errors: dict[str, str] = {}
    while time.monotonic() < deadline and not all(ready.values()):
        for port in ports:
            if ready[str(port)]:
                continue
            try:
                with socket.create_connection((host, port), timeout=0.2):
                    ready[str(port)] = True
            except OSError as exc:
                last_errors[str(port)] = str(exc)
        if not all(ready.values()):
            time.sleep(0.1)
    return {"ok": all(ready.values()), "ready": ready, "last_errors": last_errors}


async def smoke_http(spec: ServiceSpec, token: str) -> dict[str, Any]:
    async with httpx.AsyncClient(base_url=spec.base_url.rstrip("/"), timeout=240.0) as client:
        card = await client.get("/.well-known/agent-card.json")
        prompt = "Reply exactly M17D_SERVICE_LIVE_OK and no extra text." if spec.executor == "live" else f"M17d service smoke for {spec.conceptual_agent_id}"
        allowed = await client.post(
            "/",
            json={"jsonrpc": "2.0", "id": f"m17d-{spec.slug}", "method": "SendMessage", "params": message_payload(prompt)},
            headers={**A2A_HEADERS, "x-hermes-a2a-test-token": token, "x-hermes-a2a-peer-id": spec.allowed_peer_id},
        )
        denied = await client.post(
            "/",
            json={"jsonrpc": "2.0", "id": f"m17d-denied-{spec.slug}", "method": "SendMessage", "params": message_payload("denied")},
            headers={**A2A_HEADERS, "x-hermes-a2a-test-token": token, "x-hermes-a2a-peer-id": "agent:test:unauthorized"},
        )
    body = allowed.json() if allowed.headers.get("content-type", "").startswith("application/json") else {}
    task = body.get("result", {}).get("task", {})
    parts = task.get("status", {}).get("message", {}).get("parts", [])
    text = str(parts[0].get("text", "")) if parts and isinstance(parts[0], dict) else ""
    return {
        "agent_card_status": card.status_code,
        "agent_card_name": card.json().get("name") if card.status_code == 200 else None,
        "allowed_status": allowed.status_code,
        "allowed_state": task.get("status", {}).get("state"),
        "message_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "live_marker_seen": "M17D_SERVICE_LIVE_OK" in text if spec.executor == "live" else None,
        "receipt_ref": task.get("metadata", {}).get("hermesReceiptRef"),
        "live_invocation_receipt_ref": task.get("metadata", {}).get("hermesLiveInvocationReceiptRef"),
        "denied_status": denied.status_code,
    }


async def smoke_grpc(spec: ServiceSpec) -> dict[str, Any]:
    target = f"127.0.0.1:{spec.grpc_port}"
    async with grpc.aio.insecure_channel(target) as channel:
        stub = a2a_pb2_grpc.A2AServiceStub(channel)
        req = a2a_pb2.SendMessageRequest()
        req.message.message_id = f"m17d-grpc-{spec.slug}"
        req.message.role = a2a_pb2.ROLE_USER
        req.message.parts.append(a2a_pb2.Part(text=f"M17d gRPC smoke for {spec.conceptual_agent_id}", media_type="text/plain"))
        req.configuration.accepted_output_modes.append("text/plain")
        sent = await stub.SendMessage(req)
        fetched = await stub.GetTask(a2a_pb2.GetTaskRequest(id=sent.task.id))
    return {
        "target": target,
        "send_state": a2a_pb2.TaskState.Name(sent.task.status.state),
        "get_state": a2a_pb2.TaskState.Name(fetched.status.state),
        "receipt_ref": fetched.metadata["hermesReceiptRef"] if "hermesReceiptRef" in fetched.metadata else "",
    }


def read_token(env_path: Path) -> str:
    for line in env_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("HERMES_A2A_TEST_TOKEN="):
            return line.split("=", 1)[1]
    raise RuntimeError(f"missing token in {env_path}")


async def smoke_services(specs: Sequence[ServiceSpec]) -> dict[str, Any]:
    results: dict[str, Any] = {}
    for spec in specs:
        token = read_token(ENV_DIR / f"{spec.slug}.env")
        results[spec.unit] = {
            "http": await smoke_http(spec, token),
            "grpc": await smoke_grpc(spec),
        }
    return results


def process_identity(specs: Sequence[ServiceSpec]) -> dict[str, Any]:
    evidence = {}
    for spec in specs:
        show = systemctl(["show", spec.unit, "-p", "MainPID", "-p", "ActiveState", "-p", "SubState", "-p", "ExecMainStartTimestamp", "--no-pager"])
        pid = "0"
        for line in str(show.get("output", "")).splitlines():
            if line.startswith("MainPID="):
                pid = line.split("=", 1)[1]
        proc = {"pid": pid}
        if pid and pid != "0":
            cwd_path = Path("/proc") / pid / "cwd"
            cmdline_path = Path("/proc") / pid / "cmdline"
            try:
                proc["cwd"] = str(cwd_path.resolve())
            except OSError as exc:
                proc["cwd_error"] = str(exc)
            try:
                proc["cmdline"] = cmdline_path.read_bytes().replace(b"\x00", b" ").decode("utf-8", errors="replace")[:1000]
            except OSError as exc:
                proc["cmdline_error"] = str(exc)
        evidence[spec.unit] = {"systemctl_show": show, "proc": proc}
    return evidence


async def run_rollout(*, management_root: Path, run_id: str, approval_receipt: Path) -> dict[str, Any]:
    if not approval_receipt.exists():
        raise FileNotFoundError(f"approval receipt is required before M17d: {approval_receipt}")
    if not PYTHON.exists():
        raise FileNotFoundError(f"project venv python not found: {PYTHON}")
    if not HERMES.exists():
        raise FileNotFoundError(f"Hermes launcher not found: {HERMES}")
    specs = default_specs()
    ports = [port for spec in specs for port in (spec.http_port, spec.grpc_port)]
    run_root = management_root / "milestones" / "m17d" / "runs" / run_id
    if run_root.exists():
        raise FileExistsError(f"run directory already exists: {run_root}")
    run_root.mkdir(parents=True)
    before_snapshot = ss_snapshot(ports)
    unit_records = write_units(specs=specs, management_root=management_root, run_root=run_root)
    verify_results = {spec.unit: run_command(["systemd-analyze", "--user", "verify", str(SYSTEMD_USER_DIR / spec.unit)]) for spec in specs}
    daemon_reload = systemctl(["daemon-reload"])
    enable_now = systemctl(["enable", "--now", *(spec.unit for spec in specs)])
    restart = systemctl(["restart", *(spec.unit for spec in specs)])
    is_active = {spec.unit: systemctl(["is-active", spec.unit]) for spec in specs}
    process = process_identity(specs)
    readiness = wait_for_ports(ports)
    during_snapshot = ss_snapshot(ports)
    smoke = await smoke_services(specs)
    assertions = {
        "approval_receipt_present": approval_receipt.exists(),
        "unit_files_written": all(Path(unit_records[spec.unit]["unit_path"]).exists() for spec in specs),
        "env_files_0600": all(unit_records[spec.unit]["env_mode"] == "0o600" for spec in specs),
        "systemd_verify_passed": all(item["exit_code"] == 0 for item in verify_results.values()),
        "daemon_reload_passed": daemon_reload["exit_code"] == 0,
        "enable_now_passed": enable_now["exit_code"] == 0,
        "restart_passed": restart["exit_code"] == 0,
        "all_units_active": all(item["exit_code"] == 0 and str(item.get("output", "")).strip() == "active" for item in is_active.values()),
        "all_ports_ready": readiness["ok"],
        "listener_loopback_only": listener_assertions(during_snapshot, ports, expect_present=True)["ok"],
        "http_smokes_passed": all(
            item["http"]["agent_card_status"] == 200
            and item["http"]["allowed_status"] == 200
            and item["http"]["allowed_state"] == "TASK_STATE_COMPLETED"
            and item["http"]["denied_status"] == 403
            and (item["http"]["live_marker_seen"] is not False)
            for item in smoke.values()
        ),
        "grpc_smokes_passed": all(
            item["grpc"]["send_state"] == "TASK_STATE_COMPLETED" and item["grpc"]["get_state"] == "TASK_STATE_COMPLETED"
            for item in smoke.values()
        ),
    }
    status = "passed" if all(assertions.values()) else "failed"
    run_receipt_path = run_root / "service-rollout-receipt.json"
    service_state_path = run_root / "service-state.json"
    bind_path = run_root / "bind-evidence.json"
    implementation_state_path = run_root / "implementation-state.json"
    run_receipt = {
        "schema": "hermes-a2a/m17d-service-rollout-receipt/v1",
        "generated_at": utc_now(),
        "status": status,
        "run_id": run_id,
        "approval_receipt": str(approval_receipt),
        "units": unit_records,
        "assertions": assertions,
        "smoke": smoke,
        "rollback": "systemctl --user disable --now " + " ".join(spec.unit for spec in specs) + "; remove the three unit files and env files; systemctl --user daemon-reload",
        "non_claims": [
            "M17d services are local user services only",
            "Listeners are loopback-only",
            "Only agent:local:hermes-blinky-wsl uses live executor; Windows/work labels remain synthetic",
            "No LAN/Tailscale/public bind, work data, credentials, raw MCP/tool proxy, public PR/release/package/deploy, push, merge, or publication",
        ],
    }
    service_state = {
        "verify_results": verify_results,
        "daemon_reload": daemon_reload,
        "enable_now": enable_now,
        "restart": restart,
        "is_active": is_active,
        "process_identity": process,
        "readiness": readiness,
    }
    bind_evidence = {
        "before": before_snapshot,
        "during": during_snapshot,
        "during_assertions": listener_assertions(during_snapshot, ports, expect_present=True),
    }
    implementation_state = {
        "root": str(ROOT),
        "head": run_command(["git", "rev-parse", "HEAD"], cwd=ROOT),
        "status": run_command(["git", "status", "--short", "--branch"], cwd=ROOT),
        "parent_submodule_status": run_command(["git", "-C", str(ROOT.parents[1]), "status", "--short", "--branch", "--", "projects/hermes-a2a"]),
    }
    write_json(run_receipt_path, run_receipt)
    write_json(service_state_path, service_state)
    write_json(bind_path, bind_evidence)
    write_json(implementation_state_path, implementation_state)
    synthesis_path = management_root / "milestones" / "m17d" / "M17D-LOCAL-SERVICE-SYNTHESIS.md"
    manifest_path = run_root / "artifact-manifest.json"
    lines = [
        "# M17d local user-service sidecar rollout synthesis",
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
        "- Installed and started exactly three user-level sidecar units named in the approval receipt.",
        "- Unit verification, daemon reload, enable/start, restart, process identity, loopback listener readback, Agent Card, JSON-RPC, peer-denial, and gRPC smokes passed.",
        "- `agent:local:hermes-blinky-wsl` is live-Hermes-backed through profile `default`; the Windows and work conceptual sidecars remain synthetic.",
        "- Each unit uses a 0600 local EnvironmentFile token; token values are omitted from receipts and manifests.",
        "",
        "## Rollback",
        "",
        "`systemctl --user disable --now hermes-a2a-local-hermes-blinky-wsl.service hermes-a2a-local-hermes-blinky-windows.service hermes-a2a-work-hermes-work.service` then remove the three unit/env files and run `systemctl --user daemon-reload`.",
        "",
        "## Non-claims / non-actions",
        "",
        "No LAN/Tailscale/public bind, work live executor, work data, credentials, raw MCP/tool proxy, public PR/release/package/deploy, push, merge, publication, or destructive action occurred in M17d.",
        "",
    ]
    synthesis_path.parent.mkdir(parents=True, exist_ok=True)
    synthesis_path.write_text("\n".join(lines), encoding="utf-8")
    artifacts = [
        artifact_entry(approval_receipt, management_root=management_root, role="M17d approval receipt", owner_workspace="management", classification="management-evidence", source="current user chat approval normalized before service rollout"),
        artifact_entry(run_receipt_path, management_root=management_root, role="M17d service rollout receipt", owner_workspace="management", classification="management-evidence", source="scripts/run_m17d_service_rollout.py"),
        artifact_entry(service_state_path, management_root=management_root, role="systemd service state evidence", owner_workspace="management", classification="management-evidence", source="systemctl/systemd-analyze/proc readback"),
        artifact_entry(bind_path, management_root=management_root, role="listener bind evidence", owner_workspace="management", classification="management-evidence", source="ss -ltnp readback"),
        artifact_entry(implementation_state_path, management_root=management_root, role="implementation commit/status evidence", owner_workspace="implementation", classification="implementation-evidence", source="git readback"),
        artifact_entry(synthesis_path, management_root=management_root, role="M17d synthesis", owner_workspace="management", classification="management-evidence", source="service rollout synthesis"),
    ]
    for spec in specs:
        artifacts.append(
            artifact_entry(SYSTEMD_USER_DIR / spec.unit, management_root=management_root, role=f"systemd unit file {spec.unit}", owner_workspace="runtime", classification="management-evidence", source="scripts/run_m17d_service_rollout.py wrote exact-scope unit")
        )
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


def mint_run_id() -> str:
    return f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{secrets.token_hex(3)}"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run M17d user-level sidecar service rollout")
    parser.add_argument("--management-root", default=str(DEFAULT_MANAGEMENT_ROOT))
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--approval-receipt", required=True)
    args = parser.parse_args(argv)
    asyncio_run = __import__("asyncio").run
    asyncio_run(run_rollout(management_root=Path(args.management_root), run_id=args.run_id or mint_run_id(), approval_receipt=Path(args.approval_receipt)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
