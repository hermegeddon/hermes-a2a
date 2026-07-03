"""Operator CLI for the hermes-a2a Hermes plugin wrapper."""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from .gates import GateResult, require_live_gate
from .tools import project_response
from .views import _management_root, status_view, validate_config_view


def _emit(data: dict[str, Any], *, stream=None) -> None:  # type: ignore[no-untyped-def]
    print(json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True), file=stream or sys.stdout)


def _add_config_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--config", dest="config_path", default=None)
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--management-root", default=None, help="management workspace root; default: HERMES_A2A_MANAGEMENT_ROOT or current directory")


def _add_gate_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--live-enabled", action="store_true")
    parser.add_argument("--yes", action="store_true")
    parser.add_argument("--approval-receipt", default=None)


def register_cli(parser: argparse.ArgumentParser) -> None:
    parser.set_defaults(func=a2a_command)
    subs = parser.add_subparsers(dest="a2a_command", required=True)

    status = subs.add_parser("status", help="Read-only plugin/package/config status")
    _add_config_args(status)

    validate = subs.add_parser("validate-config", help="Validate instances.yaml without writing unless requested")
    _add_config_args(validate)
    validate.add_argument("--write-receipt", action="store_true")

    plan = subs.add_parser("plan", help="Print a read-only sidecar rollout plan")
    _add_config_args(plan)

    receipts = subs.add_parser("receipts", help="Read safe receipt metadata")
    receipt_subs = receipts.add_subparsers(dest="receipt_command", required=True)
    receipt_list = receipt_subs.add_parser("list", help="List receipt files")
    receipt_list.add_argument("--receipt-dir", required=True)
    receipt_show = receipt_subs.add_parser("show", help="Show a projection-scanned receipt summary")
    receipt_show.add_argument("ref")
    receipt_show.add_argument("--receipt-dir", required=True)

    card = subs.add_parser("card", help="Show public-safe Agent Card metadata")
    card_subs = card.add_subparsers(dest="card_command", required=True)
    card_show = card_subs.add_parser("show")
    card_show.add_argument("instance", nargs="?")
    _add_config_args(card_show)

    serve = subs.add_parser("serve", help="Run a foreground sidecar through the package entry point")
    serve.add_argument("instance")
    serve.add_argument("--foreground", action="store_true")
    serve.add_argument("--executor", choices=["synthetic", "live"], default="synthetic")
    _add_config_args(serve)
    _add_gate_args(serve)

    service = subs.add_parser("service", help="Inspect or gate service operations")
    service_subs = service.add_subparsers(dest="service_command", required=True)
    service_subs.add_parser("status", help="Read-only service status summary")
    for name in ["install", "restart", "stop"]:
        svc = service_subs.add_parser(name)
        svc.add_argument("--instance", default="local-services")
        svc.add_argument("--management-root", default=None, help="management workspace root; default: HERMES_A2A_MANAGEMENT_ROOT or current directory")
        svc.add_argument("--run-id", default=None)
        _add_gate_args(svc)

    task_smoke = subs.add_parser("task-smoke", help="Gate a live loopback task smoke")
    task_smoke.add_argument("instance")
    _add_config_args(task_smoke)
    _add_gate_args(task_smoke)


def _args_dict(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "config_path": getattr(args, "config_path", None),
        "run_id": getattr(args, "run_id", None),
        "management_root": getattr(args, "management_root", None),
    }


def _load_config_for_cli(args: argparse.Namespace):  # type: ignore[no-untyped-def]
    from hermes_a2a.config import load_instances_config

    return load_instances_config(
        getattr(args, "config_path", None),
        run_id=getattr(args, "run_id"),
        management_root=_management_root(_args_dict(args)),
        require_validation_receipt=False,
    )


def _status(args: argparse.Namespace) -> int:
    _emit(status_view(_args_dict(args)))
    return 0


def _validate(args: argparse.Namespace) -> int:
    if not args.write_receipt:
        result = validate_config_view(_args_dict(args))
        _emit(result, stream=sys.stderr if not result.get("ok") else sys.stdout)
        return 0 if result.get("ok") else 2
    from hermes_a2a.config import ConfigValidationError, validation_receipt_path, write_validation_receipt

    try:
        config = _load_config_for_cli(args)
        receipt = write_validation_receipt(
            config,
            validation_receipt_path(_management_root(_args_dict(args)), args.run_id),
            command="hermes a2a validate-config --write-receipt",
        )
    except ConfigValidationError as exc:
        _emit({"ok": False, "validation": "failed", "errors": list(exc.errors)}, stream=sys.stderr)
        return 2
    _emit({"ok": True, "validation": "passed", "receipt": str(receipt.path)})
    return 0


def _plan(args: argparse.Namespace) -> int:
    config = _load_config_for_cli(args)
    _emit(
        {
            "ok": True,
            "effect": "read_only",
            "plan": [
                {
                    "instance": item.conceptual_agent_id,
                    "executor": "synthetic" if not item.live_execution_enabled else "live-gated",
                    "http": item.agent_card.base_url,
                    "grpc_port": item.bind.grpc_port,
                    "network": "not_performed",
                    "service_mutation": "not_performed",
                }
                for item in config.instances
            ],
        }
    )
    return 0


def _receipt_path(receipt_dir: Path, ref: str) -> Path:
    candidate = receipt_dir / ref
    resolved = candidate.resolve(strict=False)
    root = receipt_dir.resolve(strict=False)
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError("receipt ref escapes receipt directory") from exc
    return candidate


def _receipts(args: argparse.Namespace) -> int:
    receipt_dir = Path(args.receipt_dir)
    if args.receipt_command == "list":
        files = sorted(path.name for path in receipt_dir.glob("*.json")) if receipt_dir.exists() else []
        _emit({"ok": True, "effect": "read_only", "receipts": files})
        return 0
    try:
        path = _receipt_path(receipt_dir, args.ref)
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        _emit({"ok": False, "error": "receipt_read_failed", "detail": str(exc)}, stream=sys.stderr)
        return 2
    _emit(project_response({"ok": True, "effect": "read_only", "receipt": data}, surface="receipt"))
    return 0


def _card(args: argparse.Namespace) -> int:
    config = _load_config_for_cli(args)
    instance = config.instance(args.instance) if args.instance else config.instances[0]
    _emit(
        {
            "ok": True,
            "effect": "read_only",
            "card": {
                "name": instance.agent_card.name,
                "base_url": instance.agent_card.base_url,
                "bindings": {
                    "jsonrpc": instance.bindings.jsonrpc,
                    "rest": instance.bindings.rest,
                    "grpc": instance.bindings.grpc,
                },
            },
        }
    )
    return 0


def _gate_or_emit(args: argparse.Namespace, *, operation: str, instance: str, env_gate: str) -> GateResult:
    result = require_live_gate(
        operation=operation,
        instance=instance,
        live_enabled=bool(getattr(args, "live_enabled", False)),
        yes=bool(getattr(args, "yes", False)),
        approval_receipt=getattr(args, "approval_receipt", None),
        env_gate=env_gate,
        consume=True,
    )
    if not result.allowed:
        _emit({"ok": False, "refusal": result.to_dict()}, stream=sys.stderr)
    return result


def _serve(args: argparse.Namespace) -> int:
    if args.executor == "live":
        gate = _gate_or_emit(args, operation="serve-live", instance=args.instance, env_gate="HERMES_A2A_PLUGIN_LIVE")
        if not gate.allowed:
            return 2
    return _serve_delegate(args)


def _service(args: argparse.Namespace) -> int:
    if args.service_command == "status":
        _emit({"ok": True, "effect": "read_only", "services": [], "systemctl": "not_called"})
        return 0
    units = _service_units_for_instance(args.instance)
    if not units:
        _emit({"ok": False, "error": "unsupported_service_instance", "instance": args.instance}, stream=sys.stderr)
        return 2
    op = f"service-{args.service_command}"
    gate = _gate_or_emit(args, operation=op, instance=args.instance, env_gate="HERMES_A2A_PLUGIN_SERVICE")
    if not gate.allowed:
        return 2
    return _service_delegate(args)


def _task_smoke(args: argparse.Namespace) -> int:
    if args.instance not in SUPPORTED_TASK_SMOKE_INSTANCES:
        _emit({"ok": False, "error": "unsupported_task_smoke_instance", "instance": args.instance}, stream=sys.stderr)
        return 2
    gate = _gate_or_emit(args, operation="task-smoke", instance=args.instance, env_gate="HERMES_A2A_PLUGIN_TASK_SMOKE")
    if not gate.allowed:
        return 2
    return _task_smoke_delegate(args)


def a2a_command(args: argparse.Namespace) -> int:
    command = getattr(args, "a2a_command", None)
    if command == "status":
        return _status(args)
    if command == "validate-config":
        return _validate(args)
    if command == "plan":
        return _plan(args)
    if command == "receipts":
        return _receipts(args)
    if command == "card":
        return _card(args)
    if command == "serve":
        return _serve(args)
    if command == "service":
        return _service(args)
    if command == "task-smoke":
        return _task_smoke(args)
    _emit({"ok": False, "error": "unknown_command", "command": command}, stream=sys.stderr)
    return 2


def _serve_delegate(args: argparse.Namespace) -> int:
    from hermes_a2a.serve import main

    argv = [
        "--config",
        str(args.config_path),
        "--run-id",
        str(args.run_id),
        "--management-root",
        str(args.management_root),
        "--instance",
        str(args.instance),
        "--executor",
        str(args.executor),
    ]
    return main(argv)


LOCAL_SERVICE_INSTANCE_UNITS = {
    "agent:local:hermes-blinky-wsl": ("hermes-a2a-local-hermes-blinky-wsl.service",),
    "agent:local:hermes-blinky-windows": ("hermes-a2a-local-hermes-blinky-windows.service",),
    "local-services": (
        "hermes-a2a-local-hermes-blinky-wsl.service",
        "hermes-a2a-local-hermes-blinky-windows.service",
    ),
}
SUPPORTED_TASK_SMOKE_INSTANCES = {"agent:local:hermes-blinky-wsl"}


def _service_units_for_instance(instance: str) -> tuple[str, ...]:
    return LOCAL_SERVICE_INSTANCE_UNITS.get(instance, ())


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_script_module(stem: str):  # type: ignore[no-untyped-def]
    scripts_dir = _repo_root() / "scripts"
    module_path = scripts_dir / f"{stem}.py"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    spec = importlib.util.spec_from_file_location(f"hermes_a2a_plugin_{stem}", module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault(f"hermes_a2a_plugin_{stem}", module)
    spec.loader.exec_module(module)
    return module


def _service_delegate(args: argparse.Namespace) -> int:
    units = _service_units_for_instance(args.instance)
    if not units:
        _emit({"ok": False, "error": "unsupported_service_instance", "instance": args.instance}, stream=sys.stderr)
        return 2
    if args.service_command == "install":
        module = _load_script_module("run_m17d_service_rollout")
        specs = [spec for spec in module.default_specs() if spec.unit in units]
        if not specs:
            _emit({"ok": False, "error": "no_service_specs", "instance": args.instance}, stream=sys.stderr)
            return 2
        run_id = args.run_id or module.mint_run_id()
        management_root = Path(args.management_root)
        run_root = management_root / "milestones" / "plugin-service" / "runs" / run_id
        if run_root.exists():
            _emit({"ok": False, "error": "run_directory_exists", "run_root": str(run_root)}, stream=sys.stderr)
            return 2
        run_root.mkdir(parents=True)
        ports = [port for spec in specs for port in (spec.http_port, spec.grpc_port)]
        unit_records = module.write_units(specs=specs, management_root=management_root, run_root=run_root)
        verify_results = {spec.unit: module.run_command(["systemd-analyze", "--user", "verify", str(module.SYSTEMD_USER_DIR / spec.unit)]) for spec in specs}
        daemon_reload = module.systemctl(["daemon-reload"])
        enable_now = module.systemctl(["enable", "--now", *units])
        restart = module.systemctl(["restart", *units])
        is_active = {spec.unit: module.systemctl(["is-active", spec.unit]) for spec in specs}
        readiness = module.wait_for_ports(ports)
        smoke = __import__("asyncio").run(module.smoke_services(specs))
        assertions = {
            "approval_receipt_present": Path(args.approval_receipt).exists(),
            "work_labeled_unit_excluded": "hermes-a2a-work-hermes-work.service" not in units,
            "unit_files_written": all(Path(unit_records[spec.unit]["unit_path"]).exists() for spec in specs),
            "systemd_verify_passed": all(item["exit_code"] == 0 for item in verify_results.values()),
            "daemon_reload_passed": daemon_reload["exit_code"] == 0,
            "enable_now_passed": enable_now["exit_code"] == 0,
            "restart_passed": restart["exit_code"] == 0,
            "all_units_active": all(item["exit_code"] == 0 and str(item.get("output", "")).strip() == "active" for item in is_active.values()),
            "all_ports_ready": readiness["ok"],
            "http_smokes_passed": all(item["http"]["agent_card_status"] == 200 and item["http"]["allowed_status"] == 200 for item in smoke.values()),
            "grpc_smokes_passed": all(item["grpc"]["send_state"] == "TASK_STATE_COMPLETED" and item["grpc"]["get_state"] == "TASK_STATE_COMPLETED" for item in smoke.values()),
        }
        status = "passed" if all(assertions.values()) else "failed"
        receipt_path = run_root / "plugin-service-install-receipt.json"
        module.write_json(
            receipt_path,
            {
                "schema": "hermes-a2a/plugin-service-install-receipt/v1",
                "status": status,
                "run_id": run_id,
                "instance": args.instance,
                "units": list(units),
                "assertions": assertions,
                "unit_records": unit_records,
                "verify_results": verify_results,
                "daemon_reload": daemon_reload,
                "enable_now": enable_now,
                "restart": restart,
                "is_active": is_active,
                "readiness": readiness,
                "smoke": smoke,
                "non_claims": [
                    "work-labeled service unit excluded",
                    "no LAN/Tailscale/public bind",
                    "no package publication or plugin enablement",
                ],
            },
        )
        _emit({"ok": status == "passed", "operation": "service-install", "receipt": str(receipt_path), "units": list(units)})
        return 0 if status == "passed" else 1
    action = {"restart": "restart", "stop": "stop"}[args.service_command]
    completed = subprocess.run(["systemctl", "--user", action, *units], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    _emit(
        {
            "ok": completed.returncode == 0,
            "operation": f"service-{args.service_command}",
            "effect": "executed",
            "units": list(units),
            "exit_code": completed.returncode,
            "output_tail": completed.stdout[-4000:],
        },
        stream=sys.stdout if completed.returncode == 0 else sys.stderr,
    )
    return completed.returncode


def _task_smoke_delegate(args: argparse.Namespace) -> int:
    module = _load_script_module("run_m17c_live_executor_pilot")
    argv = ["--management-root", str(args.management_root), "--approval-receipt", str(args.approval_receipt)]
    if args.run_id:
        argv.extend(["--run-id", str(args.run_id)])
    profile = os.environ.get("HERMES_A2A_PLUGIN_TASK_SMOKE_PROFILE", "default")
    argv.extend(["--profile", profile])
    return int(module.main(argv))
