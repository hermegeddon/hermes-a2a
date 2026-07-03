from __future__ import annotations

from pathlib import Path

from .conftest import RUN_ID, decode_tool_result, tool_handler, tree_snapshot, write_roster


def test_status_unresolved_env_reports_presence_not_value(monkeypatch, hermes_home: Path, registered_context) -> None:  # type: ignore[no-untyped-def]
    sentinel = "/tmp/sentinel-env-value-should-not-leak"
    monkeypatch.setenv("HERMES_A2A_INSTANCES", sentinel)
    before = tree_snapshot(hermes_home)

    result = decode_tool_result(tool_handler(registered_context, "hermes_a2a_status")({}))

    assert result["ok"] is True
    assert result["effect"] == "read_only"
    assert result["env"] == {"name": "HERMES_A2A_INSTANCES", "set": True}
    assert sentinel not in str(result)
    assert result["config"]["status"] in {"needs_run_id", "unresolved"}
    assert tree_snapshot(hermes_home) == before


def test_status_valid_config_summary_has_no_env_or_private_config_reads(monkeypatch, tmp_path: Path, hermes_home: Path, registered_context) -> None:  # type: ignore[no-untyped-def]
    config_path, _ = write_roster(tmp_path)
    core_config = hermes_home / "config.yaml"
    core_config.parent.mkdir(parents=True)
    core_config.write_text("sentinel_core_config: should_not_read\n", encoding="utf-8")
    monkeypatch.setenv("HERMES_A2A_INSTANCES", "SHOULD_NOT_APPEAR")

    result = decode_tool_result(tool_handler(registered_context, "hermes_a2a_status")({"config_path": str(config_path), "run_id": RUN_ID, "management_root": str(tmp_path)}))

    assert result["config"]["status"] == "valid"
    assert result["roster"]["instance_count"] == 3
    assert "SHOULD_NOT_APPEAR" not in str(result)
    assert "should_not_read" not in str(result)
    assert str(core_config) not in str(result)
