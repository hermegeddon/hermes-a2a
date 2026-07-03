from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from scripts.run_m17b_triad_pilot import default_config_data

RUN_ID = "20260703T000000Z-abcdef"
PORTS = [18101, 18102, 18103, 18111, 18112, 18113]


def decode_tool_result(value: Any) -> dict[str, Any]:
    if isinstance(value, str):
        return json.loads(value)
    assert isinstance(value, dict)
    return value


def write_roster(tmp_path: Path, *, run_id: str = RUN_ID, mutate=None) -> tuple[Path, dict[str, Any]]:
    data = default_config_data(tmp_path, run_id, PORTS)
    if mutate is not None:
        mutate(data)
    path = tmp_path / "instances" / "instances.yaml"
    path.parent.mkdir(parents=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return path, data


def tree_snapshot(root: Path) -> set[str]:
    if not root.exists():
        return set()
    return {str(path.relative_to(root)) for path in root.rglob("*")}


class SpyPluginContext:
    def __init__(self, *, cli: bool = True, skill: bool = True) -> None:
        object.__setattr__(self, "cli", cli)
        object.__setattr__(self, "skill", skill)
        object.__setattr__(self, "calls", [])
        object.__setattr__(self, "tools", [])
        object.__setattr__(self, "cli_commands", [])
        object.__setattr__(self, "skills", [])
        object.__setattr__(self, "accesses", [])

    def __getattribute__(self, name: str):  # type: ignore[no-untyped-def]
        if name not in {"accesses", "calls", "tools", "cli_commands", "skills", "cli", "skill", "__dict__", "__class__", "__setattr__", "__getattribute__"}:
            object.__getattribute__(self, "accesses").append(name)
        if name == "register_cli_command" and not object.__getattribute__(self, "cli"):
            raise AttributeError(name)
        if name == "register_skill" and not object.__getattribute__(self, "skill"):
            raise AttributeError(name)
        return object.__getattribute__(self, name)

    def register_tool(self, **kwargs):  # type: ignore[no-untyped-def]
        self.calls.append(("register_tool", kwargs))
        self.tools.append(kwargs)

    def register_cli_command(self, **kwargs):  # type: ignore[no-untyped-def]
        self.calls.append(("register_cli_command", kwargs))
        self.cli_commands.append(kwargs)

    def register_skill(self, **kwargs):  # type: ignore[no-untyped-def]
        self.calls.append(("register_skill", kwargs))
        self.skills.append(kwargs)


@pytest.fixture
def hermes_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "hermes-home"
    monkeypatch.setenv("HERMES_HOME", str(home))
    return home


@pytest.fixture
def registered_context(monkeypatch: pytest.MonkeyPatch, hermes_home: Path) -> SpyPluginContext:
    import hermes_a2a_plugin

    ctx = SpyPluginContext()
    hermes_a2a_plugin.register(ctx)
    return ctx


def tool_handler(ctx: SpyPluginContext, name: str):  # type: ignore[no-untyped-def]
    for item in ctx.tools:
        if item["name"] == name:
            return item["handler"]
    raise AssertionError(f"missing tool {name}")
