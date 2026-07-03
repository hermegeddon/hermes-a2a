from __future__ import annotations

import tomllib
from pathlib import Path


def test_operator_skill_has_required_sections() -> None:
    text = Path("src/hermes_a2a_plugin/skills/operator/SKILL.md").read_text(encoding="utf-8")
    for heading in [
        "Purpose & scope",
        "Model tool index",
        "CLI index",
        "Gate model",
        "Approval receipts",
        "Receipt/artifact locations",
        "Rollback / uninstall",
        "Standing non-authorizations",
        "Interpreting refusal messages",
    ]:
        assert heading in text


def test_pyproject_includes_plugin_package_and_entry_point() -> None:
    data = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    wheel_config = data["tool"]["hatch"]["build"]["targets"]["wheel"]
    assert "src/hermes_a2a_plugin" in wheel_config["packages"]
    assert (
        wheel_config["force-include"]["src/hermes_a2a_plugin/skills/operator/SKILL.md"]
        == "hermes_a2a_plugin/skills/operator/SKILL.md"
    )
    assert data["project"]["entry-points"]["hermes_agent.plugins"]["hermes-a2a"] == "hermes_a2a_plugin"
