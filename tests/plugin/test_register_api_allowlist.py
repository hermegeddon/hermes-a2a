from __future__ import annotations

from .conftest import SpyPluginContext


def test_register_uses_only_allowed_context_methods(hermes_home) -> None:  # type: ignore[no-untyped-def]
    import hermes_a2a_plugin

    ctx = SpyPluginContext()
    hermes_a2a_plugin.register(ctx)

    assert {name for name, _ in ctx.calls} <= {"register_tool", "register_cli_command", "register_skill"}
    forbidden = {"register_hook", "dispatch_tool", "register_auxiliary_task", "llm", "register_command"}
    assert not (set(ctx.accesses) & forbidden)
    assert all(not tool.get("override", False) for tool in ctx.tools)
