from __future__ import annotations

import argparse
import json
from pathlib import Path

from .conftest import RUN_ID, tree_snapshot, write_roster


def parse_cli(argv):  # type: ignore[no-untyped-def]
    from hermes_a2a_plugin.cli import a2a_command, register_cli

    parser = argparse.ArgumentParser()
    register_cli(parser)
    args = parser.parse_args(argv)
    assert getattr(args, "func", None) is a2a_command
    return args


def test_cli_registers_expected_subcommands() -> None:
    parser = argparse.ArgumentParser()
    from hermes_a2a_plugin.cli import register_cli

    register_cli(parser)
    help_text = parser.format_help()

    for word in ["status", "validate-config", "plan", "receipts", "card", "serve", "service", "task-smoke"]:
        assert word in help_text


def test_cli_serve_passes_test_token_env_to_package_entrypoint(monkeypatch, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    from hermes_a2a_plugin import cli

    calls: list[list[str]] = []
    monkeypatch.setattr("hermes_a2a.serve.main", lambda argv: calls.append(list(argv)) or 0)

    rc = cli.a2a_command(
        parse_cli(
            [
                "serve",
                "agent:local:hermes-blinky-wsl",
                "--executor",
                "synthetic",
                "--test-token-env",
                "HERMES_A2A_LOCAL_TEST_TOKEN",
                "--config",
                str(tmp_path / "instances.yaml"),
                "--run-id",
                RUN_ID,
                "--management-root",
                str(tmp_path),
            ]
        )
    )

    assert rc == 0
    assert len(calls) == 1
    assert calls[0][-2:] == ["--test-token-env", "HERMES_A2A_LOCAL_TEST_TOKEN"]


def test_cli_status_and_plan_are_read_only(tmp_path: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    from hermes_a2a_plugin.cli import a2a_command

    config_path, _ = write_roster(tmp_path)
    before = tree_snapshot(tmp_path)

    assert a2a_command(parse_cli(["status", "--config", str(config_path), "--run-id", RUN_ID, "--management-root", str(tmp_path)])) == 0
    assert a2a_command(parse_cli(["plan", "--config", str(config_path), "--run-id", RUN_ID, "--management-root", str(tmp_path)])) == 0
    out = capsys.readouterr().out

    assert "read_only" in out
    assert tree_snapshot(tmp_path) == before


def test_cli_validate_write_receipt_is_opt_in(tmp_path: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    from hermes_a2a_plugin.cli import a2a_command

    config_path, _ = write_roster(tmp_path)
    before = tree_snapshot(tmp_path)
    assert a2a_command(parse_cli(["validate-config", "--config", str(config_path), "--run-id", RUN_ID, "--management-root", str(tmp_path)])) == 0
    assert tree_snapshot(tmp_path) == before

    assert a2a_command(parse_cli(["validate-config", "--config", str(config_path), "--run-id", RUN_ID, "--management-root", str(tmp_path), "--write-receipt"])) == 0
    receipt_files = list((tmp_path / "milestones" / "m17b" / "runs" / RUN_ID).rglob("validation-receipt.json"))
    assert len(receipt_files) == 1
    assert json.loads(receipt_files[0].read_text())["status"] == "passed"


def test_cli_receipts_show_projection_scans(tmp_path: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    from hermes_a2a_plugin.cli import a2a_command

    receipt_dir = tmp_path / "receipts"
    receipt_dir.mkdir()
    (receipt_dir / "receipt-safe.json").write_text(json.dumps({"schema": "x", "payload_sha256": "0" * 64, "note": "/home/example/.hermes/private"}), encoding="utf-8")

    assert a2a_command(parse_cli(["receipts", "show", "receipt-safe.json", "--receipt-dir", str(receipt_dir)])) == 0
    out = capsys.readouterr().out

    assert "projection_refused" in out
    assert "/home/example" not in out


def test_cli_card_show_uses_roster_without_writes(tmp_path: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    from hermes_a2a_plugin.cli import a2a_command

    config_path, _ = write_roster(tmp_path)
    before = tree_snapshot(tmp_path)

    assert a2a_command(parse_cli(["card", "show", "agent:local:hermes-blinky-wsl", "--config", str(config_path), "--run-id", RUN_ID, "--management-root", str(tmp_path)])) == 0
    out = capsys.readouterr().out

    assert "Hermes Blinky WSL synthetic sidecar" in out
    assert tree_snapshot(tmp_path) == before
