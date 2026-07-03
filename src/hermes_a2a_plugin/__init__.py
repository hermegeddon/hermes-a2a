"""Hermes plugin wrapper for the local hermes-a2a package."""
from __future__ import annotations

from pathlib import Path
from typing import Any


def register(ctx: Any) -> None:
    """Register read-only tools, the operator CLI, and the bundled skill.

    This function is intentionally side-effect-free: it performs no filesystem
    writes, config reads, subprocess calls, socket operations, or runtime A2A
    imports. Runtime package imports are lazy inside handlers only.
    """

    from .tools import tool_registrations

    for registration in tool_registrations():
        ctx.register_tool(**registration)

    if hasattr(ctx, "register_cli_command"):
        from .cli import a2a_command, register_cli

        ctx.register_cli_command(
            name="a2a",
            help="Inspect and operate the local hermes-a2a plugin wrapper",
            setup_fn=register_cli,
            handler_fn=a2a_command,
            description=(
                "Local-first hermes-a2a operator CLI. Read-only commands are "
                "safe by default; live/service actions require explicit gates."
            ),
        )

    if hasattr(ctx, "register_skill"):
        skill_path = Path(__file__).resolve().parent / "skills" / "operator" / "SKILL.md"
        ctx.register_skill(
            name="operator",
            path=skill_path,
            description="Safe operator workflow for the local hermes-a2a plugin wrapper.",
        )


__all__ = ["register"]
