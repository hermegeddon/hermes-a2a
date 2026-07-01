from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from hermes_a2a.config import ConfigValidationError, load_instances_config, parse_instances_config, resolve_config_path
from scripts.run_m17b_triad_pilot import default_config_data, reserve_ports

RUN_ID = "20260701T000000Z-abcdef"


def write_config(tmp_path: Path) -> tuple[Path, dict]:
    data = default_config_data(tmp_path, RUN_ID, reserve_ports(6))
    config_path = tmp_path / "instances" / "instances.yaml"
    config_path.parent.mkdir(parents=True)
    config_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return config_path, data


def test_valid_m17b_config_loads_as_typed_config(tmp_path: Path) -> None:
    config_path, _ = write_config(tmp_path)

    config = load_instances_config(config_path, run_id=RUN_ID, management_root=tmp_path)

    assert config.schema_version == 1
    assert config.config_status == "validated"
    assert len(config.instances) == 3
    assert {instance.conceptual_agent_id for instance in config.instances} == {
        "agent:local:hermes-blinky-wsl",
        "agent:local:hermes-blinky-windows",
        "agent:work:hermes-work",
    }
    assert all(instance.bind.host == "127.0.0.1" for instance in config.instances)
    assert all(instance.auth.mode == "test_ephemeral" for instance in config.instances)
    assert all(not instance.live_execution_enabled for instance in config.instances)
    assert len(set(config.http_ports + config.grpc_ports)) == 6


def test_config_path_resolution_supports_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    config_path, _ = write_config(tmp_path)
    monkeypatch.setenv("HERMES_A2A_INSTANCES", str(config_path))

    assert resolve_config_path(None) == config_path


def test_config_validation_fails_closed_for_missing_explicit_or_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HERMES_A2A_INSTANCES", raising=False)

    with pytest.raises(ConfigValidationError, match="no config path"):
        resolve_config_path(None)


@pytest.mark.parametrize(
    ("name", "mutate", "expected"),
    [
        ("wildcard", lambda data: data["instances"][0]["bind"].update({"host": "0.0.0.0"}), "127.0.0.1"),
        ("ipv6_loopback", lambda data: data["instances"][0]["bind"].update({"host": "::1"}), "127.0.0.1"),
        (
            "duplicate_port",
            lambda data: data["instances"][1]["bind"].update({"http_port": data["instances"][0]["bind"]["http_port"]}),
            "ports must be distinct",
        ),
        ("receipt_escape", lambda data: data["instances"][0].update({"receipt_root": "/tmp/outside"}), "receipt_root must be under"),
        ("secret", lambda data: data["instances"][0].update({"token": "sk-" + "testsecret123456789"}), "secret scan"),
        ("auth_none", lambda data: data["instances"][0]["auth"].update({"mode": "none"}), "test_ephemeral"),
        ("live_execution", lambda data: data["instances"][0].update({"live_execution_enabled": True}), "must be false"),
    ],
)
def test_config_validation_rejects_forbidden_m17b_shapes(tmp_path: Path, name: str, mutate, expected: str) -> None:  # type: ignore[no-untyped-def]
    config_path, data = write_config(tmp_path)
    mutate(data)

    with pytest.raises(ConfigValidationError) as exc:
        parse_instances_config(data, source_path=config_path, source_sha256="0" * 64, run_id=RUN_ID, management_root=tmp_path)

    assert expected in str(exc.value)
