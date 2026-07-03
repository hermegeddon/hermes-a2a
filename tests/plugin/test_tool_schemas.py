from __future__ import annotations

DENYLIST = {"execute", "live", "yes", "approval_receipt", "approval", "force", "write_receipt", "receipt_path"}


def test_all_model_tool_schemas_are_strict_and_factory_wrapped(registered_context) -> None:  # type: ignore[no-untyped-def]
    assert registered_context.tools
    for tool in registered_context.tools:
        params = tool["schema"]["parameters"]
        assert params["type"] == "object"
        assert params["additionalProperties"] is False
        assert DENYLIST.isdisjoint(params.get("properties", {}))
        assert getattr(tool["handler"], "__hermes_a2a_safe_model_tool__", False) is True
