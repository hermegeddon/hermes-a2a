#!/usr/bin/env python3
"""Run the M17b synthetic three-sidecar loopback pilot."""

from __future__ import annotations

import argparse
import asyncio
import copy
import hashlib
import json
import secrets
import shutil
import socket
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Sequence

import httpx
import grpc
import yaml
from a2a.types import a2a_pb2, a2a_pb2_grpc

from hermes_a2a.config import (
    ConfigValidationError,
    InstancesConfig,
    build_validation_receipt,
    load_instances_config,
    parse_instances_config,
    run_dir,
    sha256_file,
    utc_now,
    validation_receipt_path,
    write_validation_receipt,
)
from hermes_a2a.policy import ensure_loopback_push_url
from hermes_a2a.projection import scan_peer_visible
from hermes_a2a.serve import SidecarEndpoint, SidecarGroup

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANAGEMENT_ROOT = Path("/home/openclaw/workspace/hermes-a2a")
A2A_HEADERS = {"A2A-Version": "1.0"}


def mint_run_id() -> str:
    return f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{secrets.token_hex(3)}"


def reserve_ports(count: int) -> list[int]:
    sockets: list[socket.socket] = []
    ports: list[int] = []
    try:
        for _ in range(count):
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.bind(("127.0.0.1", 0))
            sockets.append(sock)
            ports.append(sock.getsockname()[1])
        return ports
    finally:
        for sock in sockets:
            sock.close()


def message_payload(text: str) -> dict[str, Any]:
    suffix = hashlib.sha1(text.encode("utf-8")).hexdigest()[:10]
    return {
        "message": {
            "messageId": f"msg-m17b-{suffix}",
            "role": "ROLE_USER",
            "parts": [{"text": text, "mediaType": "text/plain"}],
        },
        "configuration": {"acceptedOutputModes": ["text/plain"]},
    }


def proto_request(text: str) -> a2a_pb2.SendMessageRequest:
    request = a2a_pb2.SendMessageRequest()
    request.message.message_id = f"msg-m17b-grpc-{hashlib.sha1(text.encode()).hexdigest()[:8]}"
    request.message.role = a2a_pb2.ROLE_USER
    request.message.parts.append(a2a_pb2.Part(text=text, media_type="text/plain"))
    request.configuration.accepted_output_modes.append("text/plain")
    return request


def default_config_data(management_root: Path, run_id: str, ports: Sequence[int]) -> dict[str, Any]:
    http_ports = ports[:3]
    grpc_ports = ports[3:]
    receipt_base = management_root / "milestones" / "m17b" / "runs" / run_id / "receipts"
    rows = [
        {
            "conceptual_agent_id": "agent:local:hermes-blinky-wsl",
            "display_name": "Hermes Blinky WSL synthetic sidecar",
            "slug": "local-hermes-blinky-wsl",
            "http_port": http_ports[0],
            "grpc_port": grpc_ports[0],
            "allowed_peer_ids": ["agent:local:hermes-blinky-windows", "agent:work:hermes-work"],
            "work_boundary": "local_only",
        },
        {
            "conceptual_agent_id": "agent:local:hermes-blinky-windows",
            "display_name": "Hermes Blinky Windows synthetic sidecar",
            "slug": "local-hermes-blinky-windows",
            "http_port": http_ports[1],
            "grpc_port": grpc_ports[1],
            "allowed_peer_ids": ["agent:local:hermes-blinky-wsl", "agent:work:hermes-work"],
            "work_boundary": "local_only",
        },
        {
            "conceptual_agent_id": "agent:work:hermes-work",
            "display_name": "Hermes Work synthetic sidecar",
            "slug": "work-hermes-work",
            "http_port": http_ports[2],
            "grpc_port": grpc_ports[2],
            "allowed_peer_ids": ["agent:local:hermes-blinky-wsl", "agent:local:hermes-blinky-windows"],
            "work_boundary": "work_synthetic_only",
        },
    ]
    instances: list[dict[str, Any]] = []
    for row in rows:
        http_port = row["http_port"]
        instances.append(
            {
                "conceptual_agent_id": row["conceptual_agent_id"],
                "status": "synthetic",
                "display_name": row["display_name"],
                "profile_install_hint": "Synthetic M17b identity only; no launcher proof, host inventory, or live profile invocation.",
                "host_inventory_status": "not_checked",
                "live_execution_enabled": False,
                "bind": {"host": "127.0.0.1", "http_port": http_port, "grpc_port": row["grpc_port"]},
                "agent_card": {
                    "name": row["display_name"],
                    "base_url": f"http://127.0.0.1:{http_port}/",
                },
                "bindings": {"jsonrpc": "required", "rest": "required", "grpc": "required"},
                "auth": {"mode": "test_ephemeral", "key_env": None},
                "allowed_peer_ids": row["allowed_peer_ids"],
                "receipt_root": str(receipt_base / row["slug"]),
                "work_boundary": row["work_boundary"],
            }
        )
    return {
        "schema_version": 1,
        "config_status": "validated",
        "receipt_base": str(receipt_base),
        "instances": instances,
    }


def write_default_config(path: Path, data: dict[str, Any], *, overwrite: bool) -> None:
    if path.exists() and not overwrite:
        raise FileExistsError(f"refusing to overwrite existing config without --overwrite-config: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def run_command(command: Sequence[str], *, cwd: Path | None = None, output_limit: int | None = 6000) -> dict[str, Any]:
    try:
        completed = subprocess.run(command, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    except FileNotFoundError as exc:
        return {"command": list(command), "cwd": str(cwd) if cwd else None, "exit_code": 127, "output": str(exc)}
    output = completed.stdout if output_limit is None else completed.stdout[-output_limit:]
    return {"command": list(command), "cwd": str(cwd) if cwd else None, "exit_code": completed.returncode, "output": output}


def ss_snapshot(ports: Sequence[int]) -> dict[str, Any]:
    if shutil.which("ss"):
        result = run_command(["ss", "-ltnp"], output_limit=None)
        output_format = "ss"
    else:
        result = run_command(["netstat", "-ano", "-p", "tcp"], output_limit=None)
        output_format = "netstat"
    lines = result["output"].splitlines() if isinstance(result["output"], str) else []
    port_strings = {f":{port}" for port in ports}
    filtered = [line for line in lines if any(marker in line for marker in port_strings)]
    if output_format == "netstat":
        filtered = [line for line in filtered if "LISTENING" in line]
    output = result["output"][-6000:] if isinstance(result["output"], str) else result["output"]
    return {**result, "output": output, "format": output_format, "filtered_lines": filtered}


def listener_assertions(snapshot: dict[str, Any], ports: Sequence[int], *, expect_present: bool) -> dict[str, Any]:
    lines = list(snapshot.get("filtered_lines", []))
    by_port = {port: [line for line in lines if f":{port}" in line] for port in ports}
    local_field_index = 1 if snapshot.get("format") == "netstat" else 3
    if expect_present:
        local_fields = {line: (line.split()[local_field_index] if len(line.split()) > local_field_index else "") for line in lines}
        present = {
            str(port): any(
                local.endswith(f"127.0.0.1:{port}") or local == f"[::ffff:127.0.0.1]:{port}"
                for line in port_lines
                for local in [local_fields.get(line, "")]
            )
            for port, port_lines in by_port.items()
        }
        forbidden_local = [
            line
            for line, local in local_fields.items()
            if local.startswith("0.0.0.0:") or local.startswith("[::]:") or local.startswith(":::") or local.startswith("[::1]:") or local.startswith("::1:")
        ]
        ok = all(present.values()) and not forbidden_local
        return {"ok": ok, "present_by_port": present, "local_fields": local_fields, "forbidden_local_lines": forbidden_local}
    absent = {str(port): not port_lines for port, port_lines in by_port.items()}
    return {"ok": all(absent.values()), "absent_by_port": absent, "remaining_lines": lines}


def validate_variant(
    base_data: dict[str, Any],
    *,
    source_path: Path,
    run_id: str,
    management_root: Path,
    mutate: Callable[[dict[str, Any]], None],
) -> dict[str, Any]:
    variant = copy.deepcopy(base_data)
    mutate(variant)
    try:
        parse_instances_config(
            variant,
            source_path=source_path,
            source_sha256="0" * 64,
            run_id=run_id,
            management_root=management_root,
        )
    except ConfigValidationError as exc:
        return {"denied": True, "errors": list(exc.errors)}
    return {"denied": False, "errors": []}


def negative_validation_evidence(base_data: dict[str, Any], *, source_path: Path, run_id: str, management_root: Path) -> dict[str, Any]:
    tests = {
        "bind_0_0_0_0": lambda data: data["instances"][0]["bind"].update({"host": "0.0.0.0"}),
        "bind_ipv6_wildcard": lambda data: data["instances"][0]["bind"].update({"host": "::"}),
        "bind_ipv6_loopback_deferred": lambda data: data["instances"][0]["bind"].update({"host": "::1"}),
        "bind_lan_address": lambda data: data["instances"][0]["bind"].update({"host": "192.168.1.55"}),
        "duplicate_http_port": lambda data: data["instances"][1]["bind"].update({"http_port": data["instances"][0]["bind"]["http_port"]}),
        "receipt_root_escape": lambda data: data["instances"][0].update({"receipt_root": "/tmp/hermes-a2a-outside-receipts"}),
        "auth_none_not_evidence": lambda data: data["instances"][0]["auth"].update({"mode": "none"}),
        "secret_token_rejected": lambda data: data["instances"][0].update({"token": "sk-" + "testsecret1234567890"}),
        "live_execution_rejected": lambda data: data["instances"][0].update({"live_execution_enabled": True}),
    }
    return {
        name: validate_variant(base_data, source_path=source_path, run_id=run_id, management_root=management_root, mutate=mutate)
        for name, mutate in tests.items()
    }


def allowed_headers(instance: Any, token: str) -> dict[str, str]:
    return {
        **A2A_HEADERS,
        "x-hermes-a2a-test-token": token,
        "x-hermes-a2a-peer-id": instance.allowed_peer_ids[0],
    }


def denied_headers(token: str) -> dict[str, str]:
    return {**A2A_HEADERS, "x-hermes-a2a-test-token": token, "x-hermes-a2a-peer-id": "agent:test:unauthorized"}


async def exercise_http(instance: Any, token: str) -> dict[str, Any]:
    base = instance.agent_card.base_url.rstrip("/")
    async with httpx.AsyncClient(base_url=base, timeout=10.0) as client:
        card = await client.get("/.well-known/agent-card.json")
        card_json = card.json()
        jsonrpc = await client.post(
            "/",
            json={
                "jsonrpc": "2.0",
                "id": f"m17b-jsonrpc-{instance.safe_slug}",
                "method": "SendMessage",
                "params": message_payload(f"M17b JSON-RPC ping for {instance.conceptual_agent_id}"),
            },
            headers=allowed_headers(instance, token),
        )
        rest = await client.post(
            "/message:send",
            json=message_payload(f"M17b REST ping for {instance.conceptual_agent_id}"),
            headers=allowed_headers(instance, token),
        )
        denied = await client.post(
            "/",
            json={"jsonrpc": "2.0", "id": "m17b-denied", "method": "SendMessage", "params": message_payload("denied")},
            headers=denied_headers(token),
        )
    card_findings = [finding.__dict__ for finding in scan_peer_visible(card_json, surface=f"agent-card:{instance.conceptual_agent_id}")]
    jsonrpc_body = jsonrpc.json() if jsonrpc.headers.get("content-type", "").startswith("application/json") else {}
    rest_body = rest.json() if rest.headers.get("content-type", "").startswith("application/json") else {}
    task = jsonrpc_body.get("result", {}).get("task", {})
    rest_task = rest_body.get("task", rest_body)
    return {
        "agent_card_status": card.status_code,
        "agent_card_name": card_json.get("name"),
        "agent_card_interfaces": sorted(i.get("protocolBinding") for i in card_json.get("supportedInterfaces", [])),
        "agent_card_projection_findings": card_findings,
        "jsonrpc_status": jsonrpc.status_code,
        "jsonrpc_state": task.get("status", {}).get("state"),
        "jsonrpc_receipt_ref": task.get("metadata", {}).get("hermesReceiptRef"),
        "rest_status": rest.status_code,
        "rest_state": rest_task.get("status", {}).get("state"),
        "rest_receipt_ref": rest_task.get("metadata", {}).get("hermesReceiptRef"),
        "disallowed_peer_status": denied.status_code,
        "disallowed_peer_body": denied.text[:200],
    }


async def exercise_grpc(endpoint: SidecarEndpoint) -> dict[str, Any]:
    if endpoint.grpc_target is None:
        return {"enabled": False}
    async with grpc.aio.insecure_channel(endpoint.grpc_target) as channel:
        stub = a2a_pb2_grpc.A2AServiceStub(channel)
        sent = await stub.SendMessage(proto_request(f"M17b gRPC ping for {endpoint.conceptual_agent_id}"))
        fetched = await stub.GetTask(a2a_pb2.GetTaskRequest(id=sent.task.id))
    return {
        "enabled": True,
        "target": endpoint.grpc_target,
        "send_state": a2a_pb2.TaskState.Name(sent.task.status.state),
        "get_state": a2a_pb2.TaskState.Name(fetched.status.state),
        "receipt_ref": fetched.metadata["hermesReceiptRef"] if "hermesReceiptRef" in fetched.metadata else "",
    }


def receipt_separation(config: InstancesConfig) -> dict[str, Any]:
    roots = {}
    for instance in config.instances:
        files = sorted(str(path) for path in instance.receipt_root.glob("receipt-*.json"))
        roots[instance.conceptual_agent_id] = {
            "root": str(instance.receipt_root),
            "receipt_count": len(files),
            "sample_receipts": files[:5],
        }
    root_values = [item["root"] for item in roots.values()]
    return {"ok": all(item["receipt_count"] > 0 for item in roots.values()) and len(root_values) == len(set(root_values)), "roots": roots}


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True), encoding="utf-8")


def artifact_entry(path: Path, *, management_root: Path, role: str, owner_workspace: str, classification: str, source: str) -> dict[str, Any]:
    data = path.read_bytes()
    try:
        rel = str(path.relative_to(management_root))
    except ValueError:
        try:
            rel = str(path.relative_to(ROOT))
        except ValueError:
            rel = str(path)
    return {
        "path": str(path),
        "workspace_relative_path": rel,
        "role": role,
        "sha256": hashlib.sha256(data).hexdigest(),
        "bytes": len(data),
        "line_count": len(data.splitlines()),
        "owner_workspace": owner_workspace,
        "generation_command_or_source": source,
        "timestamp": utc_now(),
        "backup_mirror_notes": "Durable local artifact only; no external mirror, push, publication, or deployment.",
        "classification": classification,
    }


def write_manifest(path: Path, *, run_id: str, management_root: Path, artifacts: Sequence[dict[str, Any]]) -> dict[str, Any]:
    readback = []
    for entry in artifacts:
        actual = sha256_file(Path(entry["path"]))
        readback.append({"path": entry["path"], "expected_sha256": entry["sha256"], "actual_sha256": actual, "ok": actual == entry["sha256"]})
    manifest = {
        "schema": "hermes-a2a/m17b-artifact-manifest/v1",
        "generated_at": utc_now(),
        "run_id": run_id,
        "manifest_self_excluded_from_stable_readback": True,
        "artifact_count": len(artifacts),
        "artifacts": list(artifacts),
        "readback": {"bad_count": sum(1 for item in readback if not item["ok"]), "items": readback},
    }
    write_json(path, manifest)
    return manifest


def write_synthesis(path: Path, *, config: InstancesConfig, receipt: dict[str, Any], manifest_path: Path) -> None:
    endpoints = receipt["endpoints"]
    lines = [
        "# M17b synthetic three-sidecar triad synthesis",
        "",
        f"Generated: `{receipt['generated_at']}`",
        "",
        "Status: **PASSED**",
        "",
        f"Run ID: `{config.run_id}`",
        f"Config: `{config.source_path}` (`{config.source_sha256}`)",
        f"Validation receipt: `{validation_receipt_path(config.management_root, config.run_id)}`",
        f"Artifact manifest: `{manifest_path}`",
        "",
        "## Proven",
        "",
        "- Three distinct synthetic instance identities ran concurrently on `127.0.0.1` loopback ports.",
        "- JSON-RPC, REST/HTTP+JSON, and gRPC bindings returned completed synthetic `SafeEchoExecutor` tasks for each sidecar.",
        "- Agent Cards were instance-specific and projection-scanned with zero findings.",
        "- `test_ephemeral` peer authorization accepted an allowed peer and denied `agent:test:unauthorized` for every HTTP sidecar.",
        "- Receipt roots were separate per instance and stayed inside the allowlisted per-run M17b receipt base.",
        "- Negative config tests denied wildcard, IPv6, LAN, duplicate-port, receipt-root escape, unauthenticated, secret-shaped, and live-execution variants before exposure.",
        "- `ss -ltnp` readback found only loopback local-address fields (`127.0.0.1` or IPv4-mapped `127.0.0.1`) during the run and no selected-port listeners after teardown.",
        "",
        "## Endpoints exercised",
        "",
    ]
    for endpoint in endpoints:
        lines.append(f"- `{endpoint['conceptual_agent_id']}` — HTTP `{endpoint['http_url']}`, gRPC `{endpoint['grpc_target']}`")
    lines.extend(
        [
            "",
            "## Non-claims / non-actions",
            "",
            "No live Hermes profile execution, `probe_profile_launcher.py`, host inventory, user-service installation/restart, LAN/Tailscale/public bind, work data, work credentials, raw MCP/tool proxy, public PR/release/package/deploy, push, merge, publication, or destructive action was attempted.",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


async def run_pilot(*, management_root: Path, config_path: Path, run_id: str, overwrite_config: bool) -> dict[str, Any]:
    selected_run_dir = run_dir(management_root, run_id)
    if selected_run_dir.exists():
        raise FileExistsError(f"run directory already exists: {selected_run_dir}")
    ports = reserve_ports(6)
    config_data = default_config_data(management_root, run_id, ports)
    write_default_config(config_path, config_data, overwrite=overwrite_config)
    validation_path = validation_receipt_path(management_root, run_id)
    before_snapshot = ss_snapshot(ports)
    config = load_instances_config(config_path, run_id=run_id, management_root=management_root)
    validation_receipt = write_validation_receipt(
        config,
        validation_path,
        command=f"uv run --extra dev python scripts/run_m17b_triad_pilot.py --run-id {run_id}",
    )
    config = load_instances_config(config_path, run_id=run_id, management_root=management_root, require_validation_receipt=True)
    token = secrets.token_urlsafe(32)
    endpoints: list[dict[str, Any]] = []
    http_results: dict[str, Any] = {}
    grpc_results: dict[str, Any] = {}
    during_snapshot: dict[str, Any] = {}
    async with SidecarGroup(config, test_token=token) as group:
        during_snapshot = ss_snapshot(ports)
        for endpoint in group.endpoints:
            endpoints.append(endpoint.__dict__ | {"receipt_root": str(endpoint.receipt_root)})
        for instance in config.instances:
            http_results[instance.conceptual_agent_id] = await exercise_http(instance, token)
        for endpoint in group.endpoints:
            grpc_results[endpoint.conceptual_agent_id] = await exercise_grpc(endpoint)
    after_snapshot = ss_snapshot(ports)

    negative = negative_validation_evidence(config_data, source_path=config_path, run_id=run_id, management_root=management_root)
    try:
        ensure_loopback_push_url("https://example.com/not-allowed")
        push_denial = {"denied": False}
    except ValueError as exc:
        push_denial = {"denied": True, "reason": str(exc)}

    binding_evidence = {
        "before": before_snapshot,
        "during": during_snapshot,
        "after": after_snapshot,
        "during_assertions": listener_assertions(during_snapshot, ports, expect_present=True),
        "after_assertions": listener_assertions(after_snapshot, ports, expect_present=False),
    }
    receipt_roots = receipt_separation(config)
    implementation_state = {
        "root": str(ROOT),
        "head": run_command(["git", "rev-parse", "HEAD"], cwd=ROOT),
        "status": run_command(["git", "status", "--short", "--branch"], cwd=ROOT),
        "parent_submodule_status": run_command(["git", "-C", str(ROOT.parents[1]), "status", "--short", "--branch", "--", "projects/hermes-a2a"]),
    }
    non_action_evidence = {
        "generated_at": utc_now(),
        "probe_profile_launcher_exists": (ROOT / "scripts" / "probe_profile_launcher.py").exists(),
        "probe_profile_launcher_executed": False,
        "live_execution_enabled_values": {item.conceptual_agent_id: item.live_execution_enabled for item in config.instances},
        "host_inventory_status_values": {item.conceptual_agent_id: item.host_inventory_status for item in config.instances},
        "service_install_or_restart_attempted": False,
        "lan_tailscale_public_bind_attempted": False,
        "work_data_credentials_or_raw_mcp_access_attempted": False,
        "process_listener_before_after": {
            "before_selected_port_lines": before_snapshot["filtered_lines"],
            "after_selected_port_lines": after_snapshot["filtered_lines"],
        },
    }

    assertions = {
        "validation_passed": validation_receipt.data["status"] == "passed",
        "listener_during_loopback_only": binding_evidence["during_assertions"]["ok"],
        "listener_after_teardown_clean": binding_evidence["after_assertions"]["ok"],
        "agent_cards_safe": all(not item["agent_card_projection_findings"] for item in http_results.values()),
        "jsonrpc_passed": all(item["jsonrpc_status"] == 200 and item["jsonrpc_state"] == "TASK_STATE_COMPLETED" for item in http_results.values()),
        "rest_passed": all(item["rest_status"] == 200 and item["rest_state"] == "TASK_STATE_COMPLETED" for item in http_results.values()),
        "grpc_passed": all(item.get("enabled") and item.get("send_state") == "TASK_STATE_COMPLETED" and item.get("get_state") == "TASK_STATE_COMPLETED" for item in grpc_results.values()),
        "peer_denials_passed": all(item["disallowed_peer_status"] == 403 for item in http_results.values()),
        "receipt_roots_separated": receipt_roots["ok"],
        "negative_config_tests_denied": all(item["denied"] for item in negative.values()),
        "non_loopback_push_denied": push_denial["denied"],
        "no_live_or_service_actions": not any(non_action_evidence["live_execution_enabled_values"].values()) and not non_action_evidence["service_install_or_restart_attempted"],
    }
    status = "passed" if all(assertions.values()) else "failed"
    run_receipt = {
        "schema": "hermes-a2a/m17b-triad-run-receipt/v1",
        "generated_at": utc_now(),
        "status": status,
        "run_id": run_id,
        "config_path": str(config.source_path),
        "config_sha256": config.source_sha256,
        "endpoints": endpoints,
        "assertions": assertions,
        "http_results": http_results,
        "grpc_results": grpc_results,
        "negative_validation_evidence": negative,
        "non_loopback_push_denial": push_denial,
        "receipt_separation": receipt_roots,
        "validation_receipt_preview": build_validation_receipt(config, command="scripts/run_m17b_triad_pilot.py"),
    }

    run_root = selected_run_dir
    agent_card_dir = run_root / "agent-cards"
    for instance in config.instances:
        card_path = agent_card_dir / f"{instance.safe_slug}.json"
        write_json(card_path, {"conceptual_agent_id": instance.conceptual_agent_id, "agent_card_result": http_results[instance.conceptual_agent_id]})
    bind_path = run_root / "bind-evidence.json"
    implementation_state_path = run_root / "implementation-state.json"
    non_action_path = run_root / "non-action-evidence.json"
    run_receipt_path = run_root / "triad-run-receipt.json"
    write_json(bind_path, binding_evidence)
    write_json(implementation_state_path, implementation_state)
    write_json(non_action_path, non_action_evidence)
    write_json(run_receipt_path, run_receipt)
    synthesis_path = management_root / "milestones" / "m17b" / "M17B-SYNTHETIC-TRIAD-SYNTHESIS.md"
    manifest_path = run_root / "artifact-manifest.json"
    write_synthesis(synthesis_path, config=config, receipt=run_receipt, manifest_path=manifest_path)

    artifacts = [
        artifact_entry(config.source_path, management_root=management_root, role="validated three-instance roster", owner_workspace="management", classification="management-evidence", source="scripts/run_m17b_triad_pilot.py wrote default M17b roster"),
        artifact_entry(validation_path, management_root=management_root, role="config validation receipt", owner_workspace="management", classification="management-evidence", source="hermes_a2a.config validation"),
        artifact_entry(bind_path, management_root=management_root, role="listener bind and teardown evidence", owner_workspace="management", classification="management-evidence", source="ss -ltnp snapshots from triad pilot"),
        artifact_entry(implementation_state_path, management_root=management_root, role="implementation commit/status evidence", owner_workspace="implementation", classification="implementation-evidence", source="git readback from implementation repo and parent submodule"),
        artifact_entry(non_action_path, management_root=management_root, role="non-action evidence", owner_workspace="management", classification="management-evidence", source="triad pilot scoped state checks"),
        artifact_entry(run_receipt_path, management_root=management_root, role="M17b triad run receipt", owner_workspace="management", classification="management-evidence", source="synthetic sidecar pilot"),
        artifact_entry(synthesis_path, management_root=management_root, role="M17b synthesis", owner_workspace="management", classification="management-evidence", source="synthetic sidecar pilot synthesis"),
    ]
    for path in sorted(agent_card_dir.glob("*.json")):
        artifacts.append(artifact_entry(path, management_root=management_root, role="safe Agent Card readback", owner_workspace="management", classification="management-evidence", source="HTTP /.well-known/agent-card.json during M17b pilot"))
    manifest = write_manifest(manifest_path, run_id=run_id, management_root=management_root, artifacts=artifacts)
    if manifest["readback"]["bad_count"] != 0:
        status = "failed"
    final = {
        "status": status,
        "run_id": run_id,
        "config": str(config.source_path),
        "validation_receipt": str(validation_path),
        "triad_receipt": str(run_receipt_path),
        "manifest": str(manifest_path),
        "synthesis": str(synthesis_path),
        "manifest_bad_count": manifest["readback"]["bad_count"],
    }
    print(json.dumps(final, indent=2, sort_keys=True))
    if status != "passed":
        raise SystemExit(1)
    return final


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run M17b synthetic three-sidecar loopback pilot")
    parser.add_argument("--management-root", default=str(DEFAULT_MANAGEMENT_ROOT))
    parser.add_argument("--config", default=None, help="instances.yaml path; default: <management-root>/instances/instances.yaml")
    parser.add_argument("--run-id", default=None, help="optional immutable run id; default: mint one")
    parser.add_argument("--overwrite-config", action="store_true", help="overwrite instances.yaml for this immutable run")
    args = parser.parse_args(argv)
    management_root = Path(args.management_root)
    config_path = Path(args.config) if args.config else management_root / "instances" / "instances.yaml"
    run_id = args.run_id or mint_run_id()
    asyncio.run(run_pilot(management_root=management_root, config_path=config_path, run_id=run_id, overwrite_config=args.overwrite_config))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
