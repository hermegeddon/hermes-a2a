from __future__ import annotations

import builtins

import pytest

from .conftest import decode_tool_result


def strict_schema() -> dict:
    return {
        "name": "unit_tool",
        "description": "unit",
        "parameters": {"type": "object", "additionalProperties": False, "properties": {"name": {"type": "string"}}},
    }


def test_safe_model_tool_rejects_non_strict_schema() -> None:
    from hermes_a2a_plugin.tools import safe_model_tool

    schema = strict_schema()
    schema["parameters"]["additionalProperties"] = True
    with pytest.raises(ValueError, match="additionalProperties"):
        safe_model_tool("bad", schema, {"name"}, lambda data: {"ok": True})


def test_safe_model_tool_rejects_execution_control_property() -> None:
    from hermes_a2a_plugin.tools import safe_model_tool

    schema = strict_schema()
    schema["parameters"]["properties"]["live"] = {"type": "boolean"}
    with pytest.raises(ValueError, match="denylisted"):
        safe_model_tool("bad", schema, {"name"}, lambda data: {"ok": True})


def test_unknown_argument_is_rejected_before_import_or_open(monkeypatch: pytest.MonkeyPatch) -> None:
    from hermes_a2a_plugin.tools import safe_model_tool

    called: list[str] = []
    original_import = builtins.__import__

    def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):  # type: ignore[no-untyped-def]
        if name == "hermes_a2a" or name.startswith("hermes_a2a."):
            called.append(f"import:{name}")
            raise AssertionError("hermes_a2a imported before arg validation")
        return original_import(name, globals, locals, fromlist, level)

    def guarded_open(*args, **kwargs):  # type: ignore[no-untyped-def]
        called.append("open")
        raise AssertionError("open called before arg validation")

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    monkeypatch.setattr(builtins, "open", guarded_open)
    handler = safe_model_tool("unit", strict_schema(), {"name"}, lambda data: {"ok": True})

    result = decode_tool_result(handler({"execute": True}))

    assert result == {"ok": False, "error": "unexpected_argument", "key": "execute"}
    assert called == []


def test_projection_violation_redacts_instead_of_returning_raw() -> None:
    from hermes_a2a_plugin.tools import safe_model_tool

    handler = safe_model_tool(
        "unit",
        strict_schema(),
        {"name"},
        lambda data: {"ok": True, "leak": "/home/openclaw/.hermes/token", "safe": "hello"},
    )

    raw = handler({"name": "x"})
    result = decode_tool_result(raw)

    assert "projection_refused" in raw
    assert "/home/openclaw" not in raw
    assert result["leak"]["error"] == "projection_refused"
    assert result["safe"] == "hello"


def test_broken_projection_scanner_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    import hermes_a2a.projection as projection
    from hermes_a2a_plugin.tools import safe_model_tool

    monkeypatch.setattr(projection, "scan_peer_visible", lambda value, surface: (_ for _ in ()).throw(RuntimeError("broken scanner")))
    handler = safe_model_tool("unit", strict_schema(), {"name"}, lambda data: {"ok": True, "raw": "safe-looking"})

    raw = handler({"name": "x"})
    result = decode_tool_result(raw)

    assert result["ok"] is False
    assert result["error"] == "projection_unavailable"
    assert "safe-looking" not in raw
