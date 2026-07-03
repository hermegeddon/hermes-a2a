from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import yaml

from .conftest import RUN_ID, write_roster


def parse_cli(argv):  # type: ignore[no-untyped-def]
    from hermes_a2a_plugin.cli import register_cli

    parser = argparse.ArgumentParser()
    register_cli(parser)
    return parser.parse_args(argv)


def write_receipt(home: Path, *, operation="serve-live", instance="agent:local:hermes-blinky-wsl", expired=False) -> Path:  # type: ignore[no-untyped-def]
    from hermes_a2a_plugin.gates import approvals_dir

    now = datetime.now(timezone.utc)
    data = {
        "kind": "approval",
        "schema_version": 1,
        "id": "22222222-2222-4222-8222-222222222222",
        "operation": operation,
        "instance": instance,
        "issued_at": (now - timedelta(minutes=5)).isoformat().replace("+00:00", "Z"),
        "expires_at": (now + (-timedelta(minutes=1) if expired else timedelta(minutes=5))).isoformat().replace("+00:00", "Z"),
        "approver": "operator",
        "scope": "single-use",
    }
    path = approvals_dir(home) / f"{data['id']}.yaml"
    path.parent.mkdir(parents=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return path


@pytest.fixture(autouse=True)
def no_real_live_effects(monkeypatch):  # type: ignore[no-untyped-def]
    import os
    import socket
    import subprocess

    def blocked(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("real process/network/service effect attempted")

    monkeypatch.setattr(subprocess, "Popen", blocked)
    monkeypatch.setattr(subprocess, "run", blocked)
    monkeypatch.setattr(socket.socket, "bind", blocked)
    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(os, "system", blocked)


def test_invalid_gated_paths_do_not_call_delegate(monkeypatch, tmp_path: Path, hermes_home: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    from hermes_a2a_plugin import cli

    config_path, _ = write_roster(tmp_path)
    calls: list[object] = []
    monkeypatch.setattr(cli, "_serve_delegate", lambda args: calls.append(args) or 0)

    rc = cli.a2a_command(parse_cli(["serve", "agent:local:hermes-blinky-wsl", "--foreground", "--executor", "live", "--config", str(config_path), "--run-id", RUN_ID, "--management-root", str(tmp_path)]))

    assert rc == 2
    assert calls == []
    assert "missing_live_enabled" in capsys.readouterr().err


def test_valid_gated_path_reaches_only_top_level_mock(monkeypatch, tmp_path: Path, hermes_home: Path) -> None:  # type: ignore[no-untyped-def]
    from hermes_a2a_plugin import cli

    config_path, _ = write_roster(tmp_path)
    receipt = write_receipt(hermes_home)
    monkeypatch.setenv("HERMES_A2A_PLUGIN_LIVE", "1")
    calls: list[object] = []
    monkeypatch.setattr(cli, "_serve_delegate", lambda args: calls.append(args) or 0)

    rc = cli.a2a_command(parse_cli(["serve", "agent:local:hermes-blinky-wsl", "--foreground", "--executor", "live", "--live-enabled", "--yes", "--approval-receipt", str(receipt), "--config", str(config_path), "--run-id", RUN_ID, "--management-root", str(tmp_path)]))

    assert rc == 0
    assert len(calls) == 1


def test_valid_service_gate_reaches_only_service_delegate_mock(monkeypatch, tmp_path: Path, hermes_home: Path) -> None:  # type: ignore[no-untyped-def]
    from hermes_a2a_plugin import cli

    receipt = write_receipt(hermes_home, operation="service-install", instance="local-services")
    monkeypatch.setenv("HERMES_A2A_PLUGIN_SERVICE", "1")
    calls: list[object] = []
    monkeypatch.setattr(cli, "_service_delegate", lambda args: calls.append(args) or 0)

    rc = cli.a2a_command(parse_cli(["service", "install", "--instance", "local-services", "--live-enabled", "--yes", "--approval-receipt", str(receipt), "--management-root", str(tmp_path)]))

    assert rc == 0
    assert len(calls) == 1


def test_unsupported_service_instance_refuses_before_delegate(monkeypatch, tmp_path: Path, hermes_home: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    from hermes_a2a_plugin import cli

    receipt = write_receipt(hermes_home, operation="service-install", instance="agent:work:hermes-work")
    monkeypatch.setenv("HERMES_A2A_PLUGIN_SERVICE", "1")
    calls: list[object] = []
    monkeypatch.setattr(cli, "_service_delegate", lambda args: calls.append(args) or 0)

    rc = cli.a2a_command(parse_cli(["service", "install", "--instance", "agent:work:hermes-work", "--live-enabled", "--yes", "--approval-receipt", str(receipt), "--management-root", str(tmp_path)]))

    assert rc == 2
    assert calls == []
    assert "unsupported_service_instance" in capsys.readouterr().err


def test_valid_task_smoke_gate_reaches_only_task_delegate_mock(monkeypatch, tmp_path: Path, hermes_home: Path) -> None:  # type: ignore[no-untyped-def]
    from hermes_a2a_plugin import cli

    config_path, _ = write_roster(tmp_path)
    receipt = write_receipt(hermes_home, operation="task-smoke")
    monkeypatch.setenv("HERMES_A2A_PLUGIN_TASK_SMOKE", "1")
    calls: list[object] = []
    monkeypatch.setattr(cli, "_task_smoke_delegate", lambda args: calls.append(args) or 0)

    rc = cli.a2a_command(parse_cli(["task-smoke", "agent:local:hermes-blinky-wsl", "--live-enabled", "--yes", "--approval-receipt", str(receipt), "--config", str(config_path), "--run-id", RUN_ID, "--management-root", str(tmp_path)]))

    assert rc == 0
    assert len(calls) == 1


def test_unsupported_task_smoke_instance_refuses_before_delegate(monkeypatch, tmp_path: Path, hermes_home: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    from hermes_a2a_plugin import cli

    config_path, _ = write_roster(tmp_path)
    receipt = write_receipt(hermes_home, operation="task-smoke", instance="agent:local:hermes-blinky-windows")
    monkeypatch.setenv("HERMES_A2A_PLUGIN_TASK_SMOKE", "1")
    calls: list[object] = []
    monkeypatch.setattr(cli, "_task_smoke_delegate", lambda args: calls.append(args) or 0)

    rc = cli.a2a_command(parse_cli(["task-smoke", "agent:local:hermes-blinky-windows", "--live-enabled", "--yes", "--approval-receipt", str(receipt), "--config", str(config_path), "--run-id", RUN_ID, "--management-root", str(tmp_path)]))

    assert rc == 2
    assert calls == []
    assert "unsupported_task_smoke_instance" in capsys.readouterr().err


def test_service_unit_selection_excludes_work_labeled_unit() -> None:
    from hermes_a2a_plugin.cli import _service_units_for_instance

    local_units = _service_units_for_instance("local-services")

    assert local_units == (
        "hermes-a2a-local-hermes-blinky-wsl.service",
        "hermes-a2a-local-hermes-blinky-windows.service",
    )
    assert "hermes-a2a-work-hermes-work.service" not in local_units
    assert _service_units_for_instance("agent:work:hermes-work") == ()


def test_task_smoke_delegate_calls_m17c_script_not_dry_run(monkeypatch, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    from hermes_a2a_plugin import cli

    calls: list[tuple[str, list[str]]] = []

    class Module:
        @staticmethod
        def main(argv):  # type: ignore[no-untyped-def]
            calls.append(("run_m17c_live_executor_pilot", list(argv)))
            return 0

    monkeypatch.setattr(cli, "_load_script_module", lambda stem: Module)
    args = parse_cli([
        "task-smoke",
        "agent:local:hermes-blinky-wsl",
        "--live-enabled",
        "--yes",
        "--approval-receipt",
        str(tmp_path / "approval.yaml"),
        "--run-id",
        RUN_ID,
        "--management-root",
        str(tmp_path),
    ])

    rc = cli._task_smoke_delegate(args)

    assert rc == 0
    assert calls == [
        (
            "run_m17c_live_executor_pilot",
            ["--management-root", str(tmp_path), "--approval-receipt", str(tmp_path / "approval.yaml"), "--run-id", RUN_ID, "--profile", "default"],
        )
    ]


def test_service_status_is_ungated_read_only(monkeypatch, capsys) -> None:  # type: ignore[no-untyped-def]
    from hermes_a2a_plugin import cli

    rc = cli.a2a_command(parse_cli(["service", "status"]))

    assert rc == 0
    assert "read_only" in capsys.readouterr().out
