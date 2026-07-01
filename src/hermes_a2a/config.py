"""Typed M17b instance roster configuration loading and validation."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, Mapping, Sequence

import yaml

MANAGEMENT_ROOT = Path("/home/openclaw/workspace/hermes-a2a")
SCHEMA_VERSION = 1
RUN_ID_RE = re.compile(r"^\d{8}T\d{6}Z-[0-9a-f]{6}$")
AGENT_ID_RE = re.compile(r"^agent:(local|work|test):[a-z0-9][a-z0-9-]*$")
ENV_NAME_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")

ConfigStatus = Literal["draft", "validated"]
InstanceStatus = Literal["synthetic", "verified_pending", "verified"]
HostInventoryStatus = Literal["not_checked", "checked_read_only", "verified"]
BindingState = Literal["required", "enabled", "disabled"]
AuthMode = Literal["none", "test_ephemeral", "api_key_env"]
WorkBoundary = Literal["local_only", "work_synthetic_only"]

_CONFIG_STATUSES = {"draft", "validated"}
_INSTANCE_STATUSES = {"synthetic", "verified_pending", "verified"}
_HOST_STATUSES = {"not_checked", "checked_read_only", "verified"}
_BINDING_STATES = {"required", "enabled", "disabled"}
_AUTH_MODES = {"none", "test_ephemeral", "api_key_env"}
_WORK_BOUNDARIES = {"local_only", "work_synthetic_only"}
_SECRET_TOKEN_RE = re.compile(r"\b(?:sk|gh[pousr]|xox[baprs]|pat)-[A-Za-z0-9_-]{8,}\b", re.IGNORECASE)
_SECRET_ASSIGNMENT_RE = re.compile(
    r"\b(?:api[_-]?key|token|password|secret)\s*[:=]\s*[\"']?[A-Za-z0-9_./+=:-]{8,}",
    re.IGNORECASE,
)
_PRIVATE_KEY_RE = re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----")
_ENV_DUMP_RE = re.compile(r"\b[A-Z][A-Z0-9_]{5,}\s=")


class ConfigValidationError(ValueError):
    """Raised when an M17b roster fails closed before any bind occurs."""

    def __init__(self, errors: Sequence[str]):
        self.errors = tuple(errors)
        super().__init__("; ".join(self.errors))


@dataclass(frozen=True)
class BindConfig:
    host: str
    http_port: int
    grpc_port: int | None


@dataclass(frozen=True)
class AgentCardConfig:
    name: str
    base_url: str


@dataclass(frozen=True)
class BindingMatrix:
    jsonrpc: BindingState
    rest: BindingState
    grpc: BindingState


@dataclass(frozen=True)
class AuthConfig:
    mode: AuthMode
    key_env: str | None


@dataclass(frozen=True)
class InstanceConfig:
    conceptual_agent_id: str
    status: InstanceStatus
    display_name: str
    profile_install_hint: str | None
    host_inventory_status: HostInventoryStatus
    live_execution_enabled: bool
    bind: BindConfig
    agent_card: AgentCardConfig
    bindings: BindingMatrix
    auth: AuthConfig
    allowed_peer_ids: tuple[str, ...]
    receipt_root: Path
    work_boundary: WorkBoundary

    @property
    def safe_slug(self) -> str:
        return safe_slug_for_agent_id(self.conceptual_agent_id)


@dataclass(frozen=True)
class InstancesConfig:
    schema_version: int
    config_status: ConfigStatus
    receipt_base: Path
    instances: tuple[InstanceConfig, ...]
    source_path: Path
    source_sha256: str
    run_id: str
    management_root: Path

    def instance(self, conceptual_agent_id: str) -> InstanceConfig:
        for item in self.instances:
            if item.conceptual_agent_id == conceptual_agent_id:
                return item
        raise KeyError(conceptual_agent_id)

    @property
    def http_ports(self) -> tuple[int, ...]:
        return tuple(item.bind.http_port for item in self.instances)

    @property
    def grpc_ports(self) -> tuple[int, ...]:
        return tuple(item.bind.grpc_port for item in self.instances if item.bind.grpc_port is not None)


@dataclass(frozen=True)
class ValidationReceipt:
    path: Path
    data: Mapping[str, Any]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_slug_for_agent_id(agent_id: str) -> str:
    if not AGENT_ID_RE.match(agent_id):
        raise ConfigValidationError([f"invalid conceptual_agent_id: {agent_id!r}"])
    return agent_id.removeprefix("agent:").replace(":", "-")


def run_dir(management_root: Path, run_id: str) -> Path:
    return Path(management_root) / "milestones" / "m17b" / "runs" / run_id


def expected_receipt_base(management_root: Path, run_id: str) -> Path:
    return run_dir(management_root, run_id) / "receipts"


def validation_receipt_path(management_root: Path, run_id: str) -> Path:
    return run_dir(management_root, run_id) / "validation-receipt.json"


def resolve_config_path(explicit: str | os.PathLike[str] | None) -> Path:
    if explicit:
        return Path(explicit).expanduser()
    env_path = os.environ.get("HERMES_A2A_INSTANCES")
    if env_path:
        return Path(env_path).expanduser()
    raise ConfigValidationError(["no config path provided; pass --config or set HERMES_A2A_INSTANCES"])


def _is_mapping(value: Any) -> bool:
    return isinstance(value, Mapping)


def _mapping(value: Any, path: str, errors: list[str]) -> Mapping[str, Any]:
    if not _is_mapping(value):
        errors.append(f"{path} must be an object")
        return {}
    return value


def _string(value: Any, path: str, errors: list[str], *, allow_null: bool = False) -> str | None:
    if value is None and allow_null:
        return None
    if not isinstance(value, str):
        errors.append(f"{path} must be a string")
        return ""
    return value


def _bool(value: Any, path: str, errors: list[str]) -> bool:
    if not isinstance(value, bool):
        errors.append(f"{path} must be a boolean")
        return False
    return value


def _port(value: Any, path: str, errors: list[str], *, allow_null: bool = False) -> int | None:
    if value is None and allow_null:
        return None
    if not isinstance(value, int) or isinstance(value, bool) or value < 1 or value > 65535:
        errors.append(f"{path} must be an integer TCP port in 1..65535")
        return 0
    return value


def _enum(value: Any, path: str, allowed: set[str], errors: list[str]) -> str:
    if not isinstance(value, str) or value not in allowed:
        errors.append(f"{path} must be one of {sorted(allowed)}")
        return ""
    return value


def _path(value: Any, path: str, errors: list[str]) -> Path:
    text = _string(value, path, errors) or ""
    if not text.startswith("/"):
        errors.append(f"{path} must be an absolute path")
    if ".." in Path(text).parts:
        errors.append(f"{path} must not contain path traversal")
    return Path(text)


def _same_resolved(left: Path, right: Path) -> bool:
    return left.expanduser().resolve(strict=False) == right.expanduser().resolve(strict=False)


def _is_relative_to(child: Path, parent: Path) -> bool:
    child_resolved = child.expanduser().resolve(strict=False)
    parent_resolved = parent.expanduser().resolve(strict=False)
    try:
        common = os.path.commonpath([str(child_resolved), str(parent_resolved)])
    except ValueError:
        return False
    return common == str(parent_resolved)


def _has_existing_symlink(path: Path) -> bool:
    current = path.expanduser()
    candidates = [current, *current.parents]
    for candidate in candidates:
        if candidate.exists() and candidate.is_symlink():
            return True
    return False


def _find_secret_like(value: Any, *, path: str = "$", key_name: str | None = None) -> list[str]:
    findings: list[str] = []
    if isinstance(value, Mapping):
        for key, item in value.items():
            findings.extend(_find_secret_like(item, path=f"{path}.{key}", key_name=str(key)))
        return findings
    if isinstance(value, list):
        for index, item in enumerate(value):
            findings.extend(_find_secret_like(item, path=f"{path}[{index}]", key_name=key_name))
        return findings
    if value is None:
        return findings
    text = str(value)
    lowered_key = (key_name or "").lower().replace("-", "_")
    if lowered_key == "key_env":
        if text and not ENV_NAME_RE.match(text):
            findings.append(f"{path} key_env is not a safe environment variable name")
        return findings
    if lowered_key in {"token", "password", "secret", "api_key", "private_key"} and text:
        findings.append(f"{path} uses a secret-bearing field name")
    if _SECRET_TOKEN_RE.search(text):
        findings.append(f"{path} contains a token-shaped value")
    if _SECRET_ASSIGNMENT_RE.search(text):
        findings.append(f"{path} contains a credential assignment")
    if _PRIVATE_KEY_RE.search(text):
        findings.append(f"{path} contains private-key material")
    if _ENV_DUMP_RE.search(text):
        findings.append(f"{path} contains raw environment-assignment text")
    return findings


def _load_yaml(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def parse_instances_config(
    raw: Any,
    *,
    source_path: Path,
    source_sha256: str,
    run_id: str,
    management_root: Path = MANAGEMENT_ROOT,
    require_peer_auth: bool = True,
) -> InstancesConfig:
    """Parse and validate an M17b roster as typed config.

    Validation is intentionally M17b-strict: loopback-only, synthetic-only,
    validated status, per-run receipt containment, and authenticated peer tests.
    """

    errors: list[str] = []
    if not RUN_ID_RE.match(run_id):
        errors.append("run_id must match YYYYMMDDTHHMMSSZ-<6 lowercase hex>")
    root = Path(management_root).expanduser()
    expected_base = expected_receipt_base(root, run_id)

    data = _mapping(raw, "$", errors)
    if _find_secret_like(data):
        errors.extend(f"secret scan: {finding}" for finding in _find_secret_like(data))

    schema_version = data.get("schema_version")
    if schema_version != SCHEMA_VERSION:
        errors.append(f"$.schema_version must be {SCHEMA_VERSION}")
    config_status = _enum(data.get("config_status"), "$.config_status", _CONFIG_STATUSES, errors)
    if config_status != "validated":
        errors.append("$.config_status must be validated before any sidecar bind")
    receipt_base = _path(data.get("receipt_base"), "$.receipt_base", errors)
    if not _same_resolved(receipt_base, expected_base):
        errors.append(f"$.receipt_base must equal {expected_base}")
    if _has_existing_symlink(receipt_base):
        errors.append("$.receipt_base or an existing ancestor is symlinked")

    instance_values = data.get("instances")
    if not isinstance(instance_values, list):
        errors.append("$.instances must be a list")
        instance_values = []
    if len(instance_values) != 3:
        errors.append("$.instances must contain exactly three M17b rows")

    instances: list[InstanceConfig] = []
    conceptual_ids: set[str] = set()
    receipt_roots: set[str] = set()
    ports: list[int] = []

    for index, raw_instance in enumerate(instance_values):
        item_path = f"$.instances[{index}]"
        item = _mapping(raw_instance, item_path, errors)
        conceptual_agent_id = _string(item.get("conceptual_agent_id"), f"{item_path}.conceptual_agent_id", errors) or ""
        if not AGENT_ID_RE.match(conceptual_agent_id):
            errors.append(f"{item_path}.conceptual_agent_id must match agent:<local|work|test>:<name>")
        if conceptual_agent_id in conceptual_ids:
            errors.append(f"{item_path}.conceptual_agent_id duplicates {conceptual_agent_id}")
        conceptual_ids.add(conceptual_agent_id)

        status = _enum(item.get("status"), f"{item_path}.status", _INSTANCE_STATUSES, errors)
        if status not in {"synthetic", "verified_pending"}:
            errors.append(f"{item_path}.status must remain synthetic or verified_pending in M17b")
        display_name = _string(item.get("display_name"), f"{item_path}.display_name", errors) or ""
        profile_install_hint = _string(item.get("profile_install_hint"), f"{item_path}.profile_install_hint", errors, allow_null=True)
        host_inventory_status = _enum(item.get("host_inventory_status"), f"{item_path}.host_inventory_status", _HOST_STATUSES, errors)
        if host_inventory_status != "not_checked":
            errors.append(f"{item_path}.host_inventory_status must remain not_checked in M17b absent a gate receipt")
        live_execution_enabled = _bool(item.get("live_execution_enabled"), f"{item_path}.live_execution_enabled", errors)
        if live_execution_enabled:
            errors.append(f"{item_path}.live_execution_enabled must be false in M17b")

        bind_data = _mapping(item.get("bind"), f"{item_path}.bind", errors)
        host = _string(bind_data.get("host"), f"{item_path}.bind.host", errors) or ""
        if host != "127.0.0.1":
            errors.append(f"{item_path}.bind.host must be 127.0.0.1 for M17b")
        http_port = _port(bind_data.get("http_port"), f"{item_path}.bind.http_port", errors) or 0
        grpc_port = _port(bind_data.get("grpc_port"), f"{item_path}.bind.grpc_port", errors, allow_null=True)
        ports.append(http_port)
        if grpc_port is not None:
            ports.append(grpc_port)

        card_data = _mapping(item.get("agent_card"), f"{item_path}.agent_card", errors)
        card_name = _string(card_data.get("name"), f"{item_path}.agent_card.name", errors) or ""
        base_url = _string(card_data.get("base_url"), f"{item_path}.agent_card.base_url", errors) or ""
        expected_base_url = f"http://127.0.0.1:{http_port}/"
        if base_url != expected_base_url:
            errors.append(f"{item_path}.agent_card.base_url must equal {expected_base_url}")

        bindings_data = _mapping(item.get("bindings"), f"{item_path}.bindings", errors)
        jsonrpc = _enum(bindings_data.get("jsonrpc"), f"{item_path}.bindings.jsonrpc", _BINDING_STATES, errors)
        rest = _enum(bindings_data.get("rest"), f"{item_path}.bindings.rest", _BINDING_STATES, errors)
        grpc_binding = _enum(bindings_data.get("grpc"), f"{item_path}.bindings.grpc", _BINDING_STATES, errors)
        if {jsonrpc, rest, grpc_binding} - {"required", "enabled"}:
            errors.append(f"{item_path}.bindings must keep JSON-RPC, REST, and gRPC required/enabled for M17b")
        if grpc_binding in {"required", "enabled"} and grpc_port is None:
            errors.append(f"{item_path}.bind.grpc_port is required when gRPC binding is enabled")

        auth_data = _mapping(item.get("auth"), f"{item_path}.auth", errors)
        auth_mode = _enum(auth_data.get("mode"), f"{item_path}.auth.mode", _AUTH_MODES, errors)
        key_env = _string(auth_data.get("key_env"), f"{item_path}.auth.key_env", errors, allow_null=True)
        if require_peer_auth and auth_mode != "test_ephemeral":
            errors.append(f"{item_path}.auth.mode must be test_ephemeral for M17b peer-authorization evidence")
        if auth_mode == "api_key_env" and not key_env:
            errors.append(f"{item_path}.auth.key_env is required when auth.mode is api_key_env")
        if auth_mode != "api_key_env" and key_env is not None:
            errors.append(f"{item_path}.auth.key_env must be null unless auth.mode is api_key_env")

        allowed_values = item.get("allowed_peer_ids")
        if not isinstance(allowed_values, list) or not allowed_values:
            errors.append(f"{item_path}.allowed_peer_ids must be a non-empty list")
            allowed_values = []
        allowed_peer_ids: list[str] = []
        for peer_index, peer in enumerate(allowed_values):
            peer_id = _string(peer, f"{item_path}.allowed_peer_ids[{peer_index}]", errors) or ""
            if not AGENT_ID_RE.match(peer_id):
                errors.append(f"{item_path}.allowed_peer_ids[{peer_index}] is not a valid agent id")
            allowed_peer_ids.append(peer_id)

        receipt_root = _path(item.get("receipt_root"), f"{item_path}.receipt_root", errors)
        if _same_resolved(receipt_root, receipt_base):
            errors.append(f"{item_path}.receipt_root must be a per-instance child, not receipt_base itself")
        if not _is_relative_to(receipt_root, receipt_base):
            errors.append(f"{item_path}.receipt_root must be under receipt_base")
        if _has_existing_symlink(receipt_root):
            errors.append(f"{item_path}.receipt_root or an existing ancestor is symlinked")
        root_key = str(receipt_root.expanduser().resolve(strict=False))
        if root_key in receipt_roots:
            errors.append(f"{item_path}.receipt_root duplicates another instance root")
        receipt_roots.add(root_key)

        work_boundary = _enum(item.get("work_boundary"), f"{item_path}.work_boundary", _WORK_BOUNDARIES, errors)
        if conceptual_agent_id.startswith("agent:work:") and work_boundary != "work_synthetic_only":
            errors.append(f"{item_path}.work_boundary must be work_synthetic_only for work-labeled M17b rows")
        if conceptual_agent_id.startswith("agent:local:") and work_boundary != "local_only":
            errors.append(f"{item_path}.work_boundary must be local_only for local M17b rows")

        instances.append(
            InstanceConfig(
                conceptual_agent_id=conceptual_agent_id,
                status=status,  # type: ignore[arg-type]
                display_name=display_name,
                profile_install_hint=profile_install_hint,
                host_inventory_status=host_inventory_status,  # type: ignore[arg-type]
                live_execution_enabled=live_execution_enabled,
                bind=BindConfig(host=host, http_port=http_port, grpc_port=grpc_port),
                agent_card=AgentCardConfig(name=card_name, base_url=base_url),
                bindings=BindingMatrix(jsonrpc=jsonrpc, rest=rest, grpc=grpc_binding),  # type: ignore[arg-type]
                auth=AuthConfig(mode=auth_mode, key_env=key_env),  # type: ignore[arg-type]
                allowed_peer_ids=tuple(allowed_peer_ids),
                receipt_root=receipt_root,
                work_boundary=work_boundary,  # type: ignore[arg-type]
            )
        )

    nonzero_ports = [port for port in ports if port]
    if len(nonzero_ports) != len(set(nonzero_ports)):
        errors.append("HTTP and gRPC ports must be distinct across all M17b sidecars")

    expected_ids = {
        "agent:local:hermes-blinky-wsl",
        "agent:local:hermes-blinky-windows",
        "agent:work:hermes-work",
    }
    if conceptual_ids and conceptual_ids != expected_ids:
        errors.append(f"M17b conceptual ids must be exactly {sorted(expected_ids)}")

    if errors:
        raise ConfigValidationError(errors)

    return InstancesConfig(
        schema_version=SCHEMA_VERSION,
        config_status=config_status,  # type: ignore[arg-type]
        receipt_base=receipt_base,
        instances=tuple(instances),
        source_path=source_path,
        source_sha256=source_sha256,
        run_id=run_id,
        management_root=root,
    )


def load_instances_config(
    config_path: str | os.PathLike[str] | None,
    *,
    run_id: str,
    management_root: Path = MANAGEMENT_ROOT,
    require_validation_receipt: bool = False,
) -> InstancesConfig:
    path = resolve_config_path(config_path)
    if not path.exists():
        raise ConfigValidationError([f"config path does not exist: {path}"])
    source_sha = sha256_file(path)
    config = parse_instances_config(
        _load_yaml(path),
        source_path=path,
        source_sha256=source_sha,
        run_id=run_id,
        management_root=management_root,
    )
    if require_validation_receipt:
        _validate_existing_receipt(config)
    return config


def _validate_existing_receipt(config: InstancesConfig) -> None:
    path = validation_receipt_path(config.management_root, config.run_id)
    if not path.exists():
        raise ConfigValidationError([f"validation receipt is required before binding: {path}"])
    try:
        receipt = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ConfigValidationError([f"validation receipt is not JSON: {path}"]) from exc
    errors = []
    if receipt.get("status") != "passed":
        errors.append("validation receipt status must be passed")
    if receipt.get("run_id") != config.run_id:
        errors.append("validation receipt run_id mismatch")
    if receipt.get("config_sha256") != config.source_sha256:
        errors.append("validation receipt config_sha256 mismatch")
    if receipt.get("config_path") != str(config.source_path):
        errors.append("validation receipt config_path mismatch")
    if errors:
        raise ConfigValidationError(errors)


def build_validation_receipt(config: InstancesConfig, *, command: str | None = None) -> dict[str, Any]:
    return {
        "schema": "hermes-a2a/m17b-validation-receipt/v1",
        "generated_at": utc_now(),
        "status": "passed",
        "run_id": config.run_id,
        "config_path": str(config.source_path),
        "config_sha256": config.source_sha256,
        "receipt_base": str(config.receipt_base),
        "management_root": str(config.management_root),
        "command": command,
        "checks": {
            "schema_version": config.schema_version,
            "config_status": config.config_status,
            "instance_count": len(config.instances),
            "conceptual_agent_ids": [item.conceptual_agent_id for item in config.instances],
            "http_ports": list(config.http_ports),
            "grpc_ports": list(config.grpc_ports),
            "all_bind_hosts": sorted({item.bind.host for item in config.instances}),
            "all_live_execution_disabled": all(not item.live_execution_enabled for item in config.instances),
            "all_host_inventory_not_checked": all(item.host_inventory_status == "not_checked" for item in config.instances),
            "all_auth_test_ephemeral": all(item.auth.mode == "test_ephemeral" for item in config.instances),
            "all_receipt_roots_under_base": all(_is_relative_to(item.receipt_root, config.receipt_base) for item in config.instances),
            "secret_scan_findings": [],
        },
        "instances": [
            {
                "conceptual_agent_id": item.conceptual_agent_id,
                "status": item.status,
                "host_inventory_status": item.host_inventory_status,
                "live_execution_enabled": item.live_execution_enabled,
                "bind": {"host": item.bind.host, "http_port": item.bind.http_port, "grpc_port": item.bind.grpc_port},
                "agent_card_base_url": item.agent_card.base_url,
                "bindings": {"jsonrpc": item.bindings.jsonrpc, "rest": item.bindings.rest, "grpc": item.bindings.grpc},
                "auth_mode": item.auth.mode,
                "allowed_peer_ids": list(item.allowed_peer_ids),
                "receipt_root": str(item.receipt_root),
                "work_boundary": item.work_boundary,
            }
            for item in config.instances
        ],
        "non_actions": [
            "No live Hermes profile execution",
            "No probe_profile_launcher.py execution",
            "No service installation or restart",
            "No LAN/Tailscale/public bind",
            "No host inventory",
            "No work data, credentials, or raw MCP/tool proxy",
        ],
    }


def write_validation_receipt(config: InstancesConfig, output_path: Path, *, command: str | None = None) -> ValidationReceipt:
    receipt = build_validation_receipt(config, command=command)
    output_path.parent.mkdir(parents=True, exist_ok=False)
    output_path.write_text(json.dumps(receipt, indent=2, sort_keys=True), encoding="utf-8")
    return ValidationReceipt(path=output_path, data=receipt)


def _write_failure_receipt(output_path: Path, *, run_id: str, config_path: Path, errors: Sequence[str]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": "hermes-a2a/m17b-validation-receipt/v1",
        "generated_at": utc_now(),
        "status": "failed",
        "run_id": run_id,
        "config_path": str(config_path),
        "errors": list(errors),
    }
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _validate_cli(args: argparse.Namespace) -> int:
    output = Path(args.output) if args.output else validation_receipt_path(Path(args.management_root), args.run_id)
    try:
        config = load_instances_config(
            args.config,
            run_id=args.run_id,
            management_root=Path(args.management_root),
            require_validation_receipt=False,
        )
        receipt = write_validation_receipt(config, output, command=" ".join(sys.argv))
    except ConfigValidationError as exc:
        config_path = resolve_config_path(args.config) if args.config or os.environ.get("HERMES_A2A_INSTANCES") else Path("<missing>")
        _write_failure_receipt(output, run_id=args.run_id, config_path=config_path, errors=exc.errors)
        for error in exc.errors:
            print(error, file=sys.stderr)
        return 2
    print(json.dumps({"status": "passed", "receipt": str(receipt.path), "config_sha256": config.source_sha256}, indent=2))
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate hermes-a2a M17b instance roster config")
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate = subparsers.add_parser("validate", help="validate instances.yaml and write validation receipt")
    validate.add_argument("--config", default=None, help="path to instances.yaml; default: HERMES_A2A_INSTANCES")
    validate.add_argument("--run-id", required=True, help="M17b run id YYYYMMDDTHHMMSSZ-<6 hex>")
    validate.add_argument("--management-root", default=str(MANAGEMENT_ROOT), help="management workspace root")
    validate.add_argument("--output", default=None, help="validation receipt path")
    validate.set_defaults(func=_validate_cli)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
