from __future__ import annotations

from pathlib import Path

from .conftest import RUN_ID, decode_tool_result, tool_handler, tree_snapshot, write_roster


def test_validate_config_validates_in_memory_without_receipt_write(tmp_path: Path, registered_context) -> None:  # type: ignore[no-untyped-def]
    config_path, _ = write_roster(tmp_path)
    before = tree_snapshot(tmp_path)

    result = decode_tool_result(tool_handler(registered_context, "hermes_a2a_validate_config")({"config_path": str(config_path), "run_id": RUN_ID, "management_root": str(tmp_path)}))

    assert result["ok"] is True
    assert result["validation"] == "passed"
    assert result["roster"]["instance_count"] == 3
    assert tree_snapshot(tmp_path) == before


def test_validate_config_invalid_config_returns_structured_errors(tmp_path: Path, registered_context) -> None:  # type: ignore[no-untyped-def]
    config_path, _ = write_roster(tmp_path, mutate=lambda data: data.update({"config_status": "draft"}))

    result = decode_tool_result(tool_handler(registered_context, "hermes_a2a_validate_config")({"config_path": str(config_path), "run_id": RUN_ID, "management_root": str(tmp_path)}))

    assert result["ok"] is False
    assert result["validation"] == "failed"
    assert any("validated" in error for error in result["errors"])


def test_validate_config_rejects_path_traversal_without_writes(tmp_path: Path, registered_context) -> None:  # type: ignore[no-untyped-def]
    before = tree_snapshot(tmp_path)

    result = decode_tool_result(tool_handler(registered_context, "hermes_a2a_validate_config")({"config_path": str(tmp_path / "x" / ".." / "instances.yaml"), "run_id": RUN_ID, "management_root": str(tmp_path)}))

    assert result["ok"] is False
    assert result["error"] == "invalid_config_path"
    assert tree_snapshot(tmp_path) == before
