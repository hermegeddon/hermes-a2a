"""Fail-closed live-operation gates for the hermes-a2a plugin wrapper."""
from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

CONTROL_ARG_DENYLIST = {
    "execute",
    "live",
    "yes",
    "approval_receipt",
    "approval",
    "force",
    "write_receipt",
    "receipt_path",
}
ALLOWED_KEYS = {
    "kind",
    "schema_version",
    "id",
    "operation",
    "instance",
    "issued_at",
    "expires_at",
    "approver",
    "scope",
    "reason",
}
REQUIRED_KEYS = ALLOWED_KEYS - {"reason"}
SUPPORTED_OPERATIONS = {"serve-live", "service-install", "service-restart", "service-stop", "task-smoke"}


@dataclass(frozen=True)
class GateResult:
    allowed: bool
    rule: str
    message: str
    receipt_id: str | None = None
    consumed_path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "rule": self.rule,
            "message": self.message,
            "receipt_id": self.receipt_id,
            "consumed_path": self.consumed_path,
        }


def _fail(rule: str, message: str) -> GateResult:
    return GateResult(False, rule, message)


def approvals_dir(hermes_home: str | os.PathLike[str] | Path | None = None) -> Path:
    root = Path(hermes_home) if hermes_home is not None else Path(os.environ.get("HERMES_HOME", "~/.hermes")).expanduser()
    return root / "state" / "hermes-a2a-plugin" / "approvals"


def _contained(path: Path, root: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(root.resolve(strict=False))
        return True
    except ValueError:
        return False


def _parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    text = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _truthy_env(name: str | None) -> bool:
    if not name:
        return True
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _verify_receipt(
    *,
    receipt_path: Path,
    operation: str,
    instance: str,
    hermes_home: Path,
    now: datetime,
) -> tuple[GateResult | None, dict[str, Any] | None, Path | None]:
    root = approvals_dir(hermes_home)
    if not _contained(receipt_path, root):
        return _fail("approval_receipt_outside_approvals_dir", "approval receipt must be contained in the approvals directory"), None, None
    if not receipt_path.exists():
        return _fail("approval_receipt_missing", f"approval receipt is missing: {receipt_path}"), None, None
    if not receipt_path.is_file():
        return _fail("approval_receipt_not_regular", "approval receipt is not a regular file"), None, None
    try:
        data = yaml.safe_load(receipt_path.read_text(encoding="utf-8"))
    except yaml.YAMLError:
        return _fail("approval_receipt_yaml", "approval receipt is not valid YAML"), None, None
    except OSError as exc:
        return _fail("approval_receipt_read_failed", str(exc)), None, None
    if not isinstance(data, dict):
        return _fail("approval_receipt_schema", "approval receipt must be a mapping"), None, None
    unknown = set(data) - ALLOWED_KEYS
    if unknown:
        return _fail("approval_receipt_unknown_keys", f"unknown approval keys: {sorted(unknown)}"), None, None
    missing = REQUIRED_KEYS - set(data)
    if missing:
        return _fail("approval_receipt_missing_keys", f"missing approval keys: {sorted(missing)}"), None, None
    if data.get("kind") != "approval":
        return _fail("approval_receipt_kind", "approval receipt kind must be approval"), None, None
    if data.get("schema_version") != 1:
        return _fail("approval_receipt_schema_version", "unsupported approval receipt schema_version"), None, None
    if data.get("operation") not in SUPPORTED_OPERATIONS or data.get("operation") != operation:
        return _fail("approval_receipt_operation", "approval receipt operation does not match requested operation"), None, None
    if data.get("instance") != instance:
        return _fail("approval_receipt_instance", "approval receipt instance does not match requested instance"), None, None
    issued_at = _parse_time(data.get("issued_at"))
    expires_at = _parse_time(data.get("expires_at"))
    if issued_at is None or expires_at is None:
        return _fail("approval_receipt_time", "approval receipt timestamps must be RFC3339"), None, None
    now = now.astimezone(timezone.utc)
    if issued_at > now:
        return _fail("approval_receipt_not_yet_valid", "approval receipt is not yet valid"), None, None
    if now >= expires_at:
        return _fail("approval_receipt_expired", "approval receipt is expired"), None, None
    if (expires_at - issued_at).total_seconds() > 24 * 60 * 60:
        return _fail("approval_receipt_ttl_too_long", "approval receipt TTL exceeds 24 hours"), None, None
    if not str(data.get("approver") or "").strip():
        return _fail("approval_receipt_approver", "approval receipt approver is empty"), None, None
    if data.get("scope") != "single-use":
        return _fail("approval_receipt_scope", "approval receipt scope must be single-use"), None, None
    receipt_id_raw = str(data.get("id") or "")
    try:
        receipt_uuid = uuid.UUID(receipt_id_raw, version=4)
    except (ValueError, AttributeError, TypeError):
        return _fail("approval_receipt_id", "approval receipt id must be a UUID4 string"), None, None
    receipt_id = str(receipt_uuid)
    if receipt_uuid.version != 4 or receipt_id != receipt_id_raw:
        return _fail("approval_receipt_id", "approval receipt id must be a normalized UUID4 string"), None, None
    marker = receipt_path.parent / f"{receipt_id}.consumed"
    if not _contained(marker, root):
        return _fail("approval_receipt_marker_outside_approvals_dir", "approval receipt consumption marker must remain inside approvals directory"), None, None
    if marker.exists():
        return _fail("approval_receipt_consumed", "approval receipt has already been consumed"), None, None
    return None, {**data, "id": receipt_id}, marker


def require_live_gate(
    *,
    operation: str,
    instance: str,
    live_enabled: bool,
    yes: bool,
    approval_receipt: str | os.PathLike[str] | Path | None,
    env_gate: str | None,
    hermes_home: str | os.PathLike[str] | Path | None = None,
    now: datetime | None = None,
    consume: bool = False,
    extra_args: dict[str, Any] | None = None,
) -> GateResult:
    for key in extra_args or {}:
        if key in CONTROL_ARG_DENYLIST:
            return _fail("unexpected_argument", f"unexpected execution-control argument: {key}")
    if not live_enabled:
        return _fail("missing_live_enabled", "missing --live-enabled")
    if not yes:
        return _fail("missing_yes", "missing --yes")
    if approval_receipt is None:
        return _fail("missing_approval_receipt", "missing --approval-receipt")
    if not _truthy_env(env_gate):
        return _fail("missing_env_gate", f"missing environment gate: {env_gate}")
    now = now or datetime.now(timezone.utc)
    home = Path(hermes_home) if hermes_home is not None else Path(os.environ.get("HERMES_HOME", "~/.hermes")).expanduser()
    failure, data, marker = _verify_receipt(
        receipt_path=Path(approval_receipt).expanduser(),
        operation=operation,
        instance=instance,
        hermes_home=home,
        now=now,
    )
    if failure is not None:
        return failure
    assert data is not None and marker is not None
    if consume:
        try:
            fd = os.open(marker, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(f"consumed_at: {datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')}\n")
        except FileExistsError:
            return _fail("approval_receipt_consumed", "approval receipt has already been consumed")
        except OSError as exc:
            return _fail("approval_receipt_consume_failed", str(exc))
    return GateResult(True, "allowed", "all live gates satisfied", receipt_id=str(data.get("id")), consumed_path=str(marker) if consume else None)
