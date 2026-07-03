"""Read-only views for hermes-a2a plugin tools and CLI."""
from __future__ import annotations

import importlib.metadata
import os
from pathlib import Path
from typing import Any


def _management_root(args: dict[str, Any]) -> Path:
    text = args.get("management_root") or "/home/openclaw/workspace/hermes-a2a"
    return Path(str(text)).expanduser()


def _path_from_args(args: dict[str, Any]) -> tuple[Path | None, dict[str, Any]]:
    env_set = "HERMES_A2A_INSTANCES" in os.environ
    explicit = args.get("config_path")
    if explicit:
        path = Path(str(explicit)).expanduser()
        source = "explicit"
    elif env_set:
        path = Path(os.environ["HERMES_A2A_INSTANCES"]).expanduser()
        source = "env"
    else:
        path = None
        source = "unresolved"
    return path, {"source": source, "env": {"name": "HERMES_A2A_INSTANCES", "set": env_set}}


def _reject_lexical_traversal(path: Path | None) -> dict[str, Any] | None:
    if path is not None and ".." in path.parts:
        return {"ok": False, "error": "invalid_config_path", "reason": "path_traversal"}
    return None


def _load_config(args: dict[str, Any]):  # type: ignore[no-untyped-def]
    from hermes_a2a.config import ConfigValidationError, load_instances_config

    run_id = str(args.get("run_id") or "")
    if not run_id:
        return None, {"ok": False, "error": "missing_run_id"}
    path, _ = _path_from_args(args)
    path_error = _reject_lexical_traversal(path)
    if path_error is not None:
        return None, path_error
    try:
        config = load_instances_config(
            str(path) if path is not None else None,
            run_id=run_id,
            management_root=_management_root(args),
            require_validation_receipt=False,
        )
    except ConfigValidationError as exc:
        return None, {"ok": False, "validation": "failed", "errors": list(exc.errors)}
    return config, None


def _version() -> str:
    try:
        return importlib.metadata.version("hermes-a2a")
    except Exception:
        return "0.1.0"


def roster_summary(config) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    return {
        "schema_version": config.schema_version,
        "config_status": config.config_status,
        "instance_count": len(config.instances),
        "instances": [
            {
                "conceptual_agent_id": item.conceptual_agent_id,
                "display_name": item.display_name,
                "status": item.status,
                "live_execution_enabled": item.live_execution_enabled,
                "bind": {
                    "host": item.bind.host,
                    "http_port": item.bind.http_port,
                    "grpc_port": item.bind.grpc_port,
                },
                "auth_mode": item.auth.mode,
                "work_boundary": item.work_boundary,
            }
            for item in config.instances
        ],
    }


def status_view(args: dict[str, Any]) -> dict[str, Any]:
    path, resolution = _path_from_args(args)
    payload: dict[str, Any] = {
        "ok": True,
        "effect": "read_only",
        "package": {"installed": True, "version": _version()},
        "env": resolution["env"],
        "config": {
            "status": "unresolved" if path is None else ("needs_run_id" if not args.get("run_id") else "checking"),
            "source": resolution["source"],
            "exists": bool(path.exists()) if path is not None else False,
        },
    }
    if path is None or not args.get("run_id"):
        return payload
    config, error = _load_config(args)
    if error is not None:
        payload["config"] = {**payload["config"], **error}
        return payload
    payload["config"]["status"] = "valid"
    payload["roster"] = roster_summary(config)
    return payload


def validate_config_view(args: dict[str, Any]) -> dict[str, Any]:
    path, _ = _path_from_args(args)
    path_error = _reject_lexical_traversal(path)
    if path_error is not None:
        return path_error
    config, error = _load_config(args)
    if error is not None:
        return error
    return {"ok": True, "effect": "read_only", "validation": "passed", "roster": roster_summary(config)}


def peer_task_dry_run_view(args: dict[str, Any]) -> dict[str, Any]:
    config, error = _load_config(args)
    if error is not None:
        return error
    instance_id = str(args.get("instance") or "")
    try:
        instance = config.instance(instance_id)
    except KeyError:
        return {"ok": False, "error": "unknown_instance", "instance": instance_id}
    task_text = str(args.get("task_text") or "")
    return {
        "ok": True,
        "effect": "read_only",
        "plan": {
            "instance": instance.conceptual_agent_id,
            "target_url": instance.agent_card.base_url.rstrip("/"),
            "method": "POST",
            "network": "not_performed",
            "receipt_write": "not_performed",
            "payload": {
                "message": {
                    "role": "ROLE_USER",
                    "parts": [{"text": task_text, "mediaType": "text/plain"}],
                },
                "configuration": {"acceptedOutputModes": ["text/plain"]},
            },
        },
    }
