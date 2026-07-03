from __future__ import annotations

import builtins
from pathlib import Path

import pytest

from .conftest import SpyPluginContext, tree_snapshot


def test_register_wires_tools_cli_and_skill_without_home_state(hermes_home: Path) -> None:
    import hermes_a2a_plugin

    before = tree_snapshot(hermes_home)
    ctx = SpyPluginContext()
    hermes_a2a_plugin.register(ctx)
    after = tree_snapshot(hermes_home)

    assert before == after == set()
    assert {tool["name"] for tool in ctx.tools} == {
        "hermes_a2a_status",
        "hermes_a2a_validate_config",
        "hermes_a2a_peer_task_dry_run",
    }
    assert [cmd["name"] for cmd in ctx.cli_commands] == ["a2a"]
    assert [skill["name"] for skill in ctx.skills] == ["operator"]
    assert ctx.skills[0]["path"].name == "SKILL.md"
    assert ctx.skills[0]["path"].exists()


def test_register_degrades_when_cli_or_skill_registration_absent(hermes_home: Path) -> None:
    import hermes_a2a_plugin

    ctx = SpyPluginContext(cli=False, skill=False)
    hermes_a2a_plugin.register(ctx)

    assert len(ctx.tools) == 3
    assert ctx.cli_commands == []
    assert ctx.skills == []


def test_register_does_not_import_hermes_a2a(monkeypatch: pytest.MonkeyPatch, hermes_home: Path) -> None:
    import hermes_a2a_plugin

    original_import = builtins.__import__
    imported: list[str] = []

    def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):  # type: ignore[no-untyped-def]
        if name == "hermes_a2a" or name.startswith("hermes_a2a."):
            imported.append(name)
            raise AssertionError(f"register imported {name}")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    ctx = SpyPluginContext()
    hermes_a2a_plugin.register(ctx)

    assert imported == []
    assert len(ctx.tools) == 3
