from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import yaml


def write_receipt(home: Path, **overrides) -> Path:  # type: ignore[no-untyped-def]
    from hermes_a2a_plugin.gates import approvals_dir

    now = datetime(2026, 7, 3, 12, 0, tzinfo=timezone.utc)
    data = {
        "kind": "approval",
        "schema_version": 1,
        "id": "11111111-1111-4111-8111-111111111111",
        "operation": "serve-live",
        "instance": "agent:local:hermes-blinky-wsl",
        "issued_at": (now - timedelta(minutes=5)).isoformat().replace("+00:00", "Z"),
        "expires_at": (now + timedelta(minutes=5)).isoformat().replace("+00:00", "Z"),
        "approver": "janusz",
        "scope": "single-use",
        "reason": "unit test",
    }
    data.update(overrides)
    path = approvals_dir(home) / f"{data.get('id', 'receipt')}.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return path


def call_gate(home: Path, receipt: Path | None, **kwargs):  # type: ignore[no-untyped-def]
    from hermes_a2a_plugin.gates import require_live_gate

    now = datetime(2026, 7, 3, 12, 0, tzinfo=timezone.utc)
    return require_live_gate(
        operation=kwargs.pop("operation", "serve-live"),
        instance=kwargs.pop("instance", "agent:local:hermes-blinky-wsl"),
        live_enabled=kwargs.pop("live_enabled", True),
        yes=kwargs.pop("yes", True),
        approval_receipt=receipt,
        env_gate=kwargs.pop("env_gate", None),
        hermes_home=home,
        now=kwargs.pop("now", now),
        consume=kwargs.pop("consume", False),
        extra_args=kwargs.pop("extra_args", None),
    )


def test_valid_gate_can_consume_once(monkeypatch, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    receipt = write_receipt(tmp_path)
    monkeypatch.setenv("HERMES_A2A_PLUGIN_LIVE", "1")

    first = call_gate(tmp_path, receipt, env_gate="HERMES_A2A_PLUGIN_LIVE", consume=True)
    second = call_gate(tmp_path, receipt, env_gate="HERMES_A2A_PLUGIN_LIVE", consume=True)

    assert first.allowed is True
    assert (receipt.parent / "11111111-1111-4111-8111-111111111111.consumed").exists()
    assert second.allowed is False
    assert second.rule == "approval_receipt_consumed"


@pytest.mark.parametrize(
    ("label", "receipt_factory", "expected_rule"),
    [
        ("missing", lambda home: home / "state" / "hermes-a2a-plugin" / "approvals" / "missing.yaml", "approval_receipt_missing"),
        ("directory", lambda home: (home / "state" / "hermes-a2a-plugin" / "approvals"), "approval_receipt_not_regular"),
        ("outside", lambda home: home / "outside.yaml", "approval_receipt_outside_approvals_dir"),
        ("unknown_key", lambda home: write_receipt(home, unexpected="x"), "approval_receipt_unknown_keys"),
        ("wrong_kind", lambda home: write_receipt(home, kind="not-approval"), "approval_receipt_kind"),
        ("bad_version", lambda home: write_receipt(home, schema_version=2), "approval_receipt_schema_version"),
        ("wrong_operation", lambda home: write_receipt(home, operation="service-stop"), "approval_receipt_operation"),
        ("wrong_instance", lambda home: write_receipt(home, instance="agent:local:other"), "approval_receipt_instance"),
        ("expired", lambda home: write_receipt(home, expires_at="2026-07-03T11:59:00Z"), "approval_receipt_expired"),
        ("not_yet_valid", lambda home: write_receipt(home, issued_at="2026-07-03T12:01:00Z"), "approval_receipt_not_yet_valid"),
        ("ttl", lambda home: write_receipt(home, issued_at="2026-07-02T11:59:00Z"), "approval_receipt_ttl_too_long"),
        ("bad_id", lambda home: write_receipt(home, id="not-a-uuid"), "approval_receipt_id"),
        ("uppercase_id", lambda home: write_receipt(home, id="AAAAAAAA-AAAA-4AAA-8AAA-AAAAAAAAAAAA"), "approval_receipt_id"),
        ("empty_approver", lambda home: write_receipt(home, approver=""), "approval_receipt_approver"),
    ],
)
def test_gate_refuses_each_receipt_rule(label, receipt_factory, expected_rule, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    receipt = receipt_factory(tmp_path)
    if label == "directory":
        receipt.mkdir(parents=True, exist_ok=True)

    result = call_gate(tmp_path, receipt)

    assert result.allowed is False
    assert result.rule == expected_rule


def test_gate_refuses_invalid_yaml(tmp_path: Path) -> None:
    from hermes_a2a_plugin.gates import approvals_dir

    path = approvals_dir(tmp_path) / "bad.yaml"
    path.parent.mkdir(parents=True)
    path.write_text("kind: [", encoding="utf-8")

    result = call_gate(tmp_path, path)

    assert result.allowed is False
    assert result.rule == "approval_receipt_yaml"


def test_gate_refuses_path_traversal_receipt_id_without_writing_marker(tmp_path: Path) -> None:
    from hermes_a2a_plugin.gates import approvals_dir

    now = datetime(2026, 7, 3, 12, 0, tzinfo=timezone.utc)
    receipt = approvals_dir(tmp_path) / "malicious.yaml"
    receipt.parent.mkdir(parents=True)
    receipt.write_text(
        yaml.safe_dump(
            {
                "kind": "approval",
                "schema_version": 1,
                "id": "../../escape-marker",
                "operation": "serve-live",
                "instance": "agent:local:hermes-blinky-wsl",
                "issued_at": (now - timedelta(minutes=5)).isoformat().replace("+00:00", "Z"),
                "expires_at": (now + timedelta(minutes=5)).isoformat().replace("+00:00", "Z"),
                "approver": "janusz",
                "scope": "single-use",
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    result = call_gate(tmp_path, receipt, consume=True)

    assert result.allowed is False
    assert result.rule == "approval_receipt_id"
    assert not (tmp_path / "state" / "escape-marker.consumed").exists()
    assert not (tmp_path / "state" / "hermes-a2a-plugin" / "escape-marker.consumed").exists()


def test_gate_requires_canonical_receipt_path_for_single_use_marker(tmp_path: Path) -> None:
    from hermes_a2a_plugin.gates import approvals_dir

    canonical = write_receipt(tmp_path)
    nested = approvals_dir(tmp_path) / "nested" / "copied.yaml"
    nested.parent.mkdir(parents=True)
    nested.write_text(canonical.read_text(encoding="utf-8"), encoding="utf-8")

    result = call_gate(tmp_path, nested, consume=True)

    assert result.allowed is False
    assert result.rule == "approval_receipt_path"
    assert not (nested.parent / "11111111-1111-4111-8111-111111111111.consumed").exists()
    assert not (approvals_dir(tmp_path) / "11111111-1111-4111-8111-111111111111.consumed").exists()


def test_gate_refuses_missing_flags_env_and_execution_args(monkeypatch, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    receipt = write_receipt(tmp_path)
    monkeypatch.delenv("HERMES_A2A_PLUGIN_LIVE", raising=False)

    assert call_gate(tmp_path, receipt, live_enabled=False).rule == "missing_live_enabled"
    assert call_gate(tmp_path, receipt, yes=False).rule == "missing_yes"
    assert call_gate(tmp_path, None).rule == "missing_approval_receipt"
    assert call_gate(tmp_path, receipt, env_gate="HERMES_A2A_PLUGIN_LIVE").rule == "missing_env_gate"
    assert call_gate(tmp_path, receipt, extra_args={"force": True}).rule == "unexpected_argument"
