from __future__ import annotations

from pathlib import Path

from .conftest import RUN_ID, decode_tool_result, tool_handler, tree_snapshot, write_roster


def test_peer_task_dry_run_is_network_free_and_writes_nothing(monkeypatch, tmp_path: Path, registered_context) -> None:  # type: ignore[no-untyped-def]
    config_path, _ = write_roster(tmp_path)
    before = tree_snapshot(tmp_path)

    result = decode_tool_result(tool_handler(registered_context, "hermes_a2a_peer_task_dry_run")({"config_path": str(config_path), "run_id": RUN_ID, "management_root": str(tmp_path), "instance": "agent:local:hermes-blinky-wsl", "task_text": "ping"}))

    assert result["ok"] is True
    assert result["effect"] == "read_only"
    assert result["plan"]["method"] == "POST"
    assert result["plan"]["network"] == "not_performed"
    assert tree_snapshot(tmp_path) == before


def test_peer_task_dry_run_unknown_instance_is_structured_error(tmp_path: Path, registered_context) -> None:  # type: ignore[no-untyped-def]
    config_path, _ = write_roster(tmp_path)

    result = decode_tool_result(tool_handler(registered_context, "hermes_a2a_peer_task_dry_run")({"config_path": str(config_path), "run_id": RUN_ID, "management_root": str(tmp_path), "instance": "agent:test:nope", "task_text": "ping"}))

    assert result["ok"] is False
    assert result["error"] == "unknown_instance"


def test_peer_task_dry_run_rejects_execution_keys_before_work(registered_context) -> None:  # type: ignore[no-untyped-def]
    result = decode_tool_result(tool_handler(registered_context, "hermes_a2a_peer_task_dry_run")({"execute": True, "task_text": "ping"}))

    assert result == {"ok": False, "error": "unexpected_argument", "key": "execute"}
