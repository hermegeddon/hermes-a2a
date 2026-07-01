from __future__ import annotations

from scripts.run_m17e_lan_pilot import parse_remote_probe_output


def test_parse_remote_probe_output_ignores_ssh_noise() -> None:
    output = "Warning: Permanently added host\n{\"reachable\": false, \"error_type\": \"TimeoutError\"}\n"

    parsed = parse_remote_probe_output(output)

    assert parsed == {"reachable": False, "error_type": "TimeoutError"}


def test_parse_remote_probe_output_uses_last_reachability_json() -> None:
    output = "{\"reachable\": false}\nlog line\n{\"reachable\": true, \"http_prefix\": \"HTTP/1.1 200 OK\"}\n"

    parsed = parse_remote_probe_output(output)

    assert parsed == {"reachable": True, "http_prefix": "HTTP/1.1 200 OK"}


def test_parse_remote_probe_output_returns_none_without_reachability_json() -> None:
    assert parse_remote_probe_output("plain ssh failure") is None
