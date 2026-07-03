"""Model-callable tool schemas and safety wrapper for hermes-a2a."""
from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from functools import wraps
from typing import Any

EXECUTION_CONTROL_DENYLIST = {
    "execute",
    "live",
    "yes",
    "approval_receipt",
    "approval",
    "force",
    "write_receipt",
    "receipt_path",
}

JsonHandler = Callable[[dict[str, Any]], dict[str, Any]]


def _json(value: Mapping[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _incoming(args: dict[str, Any] | None, kwargs: dict[str, Any]) -> dict[str, Any]:
    data: dict[str, Any] = {}
    if args:
        if not isinstance(args, dict):
            return {"__invalid_args__": type(args).__name__}
        data.update(args)
    data.update(kwargs)
    return data


def _schema_params(schema: Mapping[str, Any]) -> Mapping[str, Any]:
    params = schema.get("parameters")
    if not isinstance(params, Mapping):
        raise ValueError("tool schema must contain parameters object")
    return params


def safe_model_tool(name: str, schema: dict[str, Any], allowed_args: set[str], handler: JsonHandler):
    """Wrap a model handler with schema, argument, and projection safety gates."""

    params = _schema_params(schema)
    if params.get("additionalProperties") is not False:
        raise ValueError("tool schema parameters.additionalProperties must be false")
    properties = params.get("properties", {})
    if not isinstance(properties, Mapping):
        raise ValueError("tool schema parameters.properties must be an object")
    denied = EXECUTION_CONTROL_DENYLIST.intersection(properties)
    if denied:
        raise ValueError(f"tool schema uses denylisted execution-control properties: {sorted(denied)}")
    if not set(properties).issubset(allowed_args):
        extra = sorted(set(properties) - allowed_args)
        raise ValueError(f"tool schema properties not in handler allowlist: {extra}")

    @wraps(handler)
    def wrapped(args: dict[str, Any] | None = None, **kwargs: Any) -> str:
        data = _incoming(args, kwargs)
        for key in data:
            if key in EXECUTION_CONTROL_DENYLIST or key not in allowed_args:
                return _json({"ok": False, "error": "unexpected_argument", "key": key})
        try:
            result = handler(data)
        except Exception as exc:  # defensive model boundary: structured error, no traceback
            return _json({"ok": False, "error": "handler_failed", "detail": str(exc)})
        projected = project_response(result, surface=name)
        return _json(projected)

    setattr(wrapped, "__hermes_a2a_safe_model_tool__", True)
    return wrapped


def project_response(value: Any, *, surface: str) -> dict[str, Any]:
    """Projection-scan every string; redact unsafe leaves, fail closed on scanner errors."""
    try:
        from hermes_a2a.projection import scan_peer_visible
    except Exception:
        return {"ok": False, "error": "projection_unavailable"}

    try:
        def visit(item: Any, path: str) -> Any:
            if isinstance(item, str):
                findings = scan_peer_visible(item, surface=path)
                if findings:
                    return {
                        "error": "projection_refused",
                        "field": path,
                        "kinds": sorted({finding.kind for finding in findings}),
                    }
                return item
            if isinstance(item, dict):
                return {str(key): visit(child, f"{path}.{key}") for key, child in item.items()}
            if isinstance(item, (list, tuple)):
                return [visit(child, f"{path}[{index}]") for index, child in enumerate(item)]
            return item

        projected = visit(value, "$")
    except Exception:
        return {"ok": False, "error": "projection_unavailable"}
    if not isinstance(projected, dict):
        return {"ok": True, "value": projected}
    return projected


def _schema(name: str, description: str, properties: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
    params: dict[str, Any] = {
        "type": "object",
        "additionalProperties": False,
        "properties": properties,
    }
    if required:
        params["required"] = required
    return {"name": name, "description": description, "parameters": params}


COMMON_CONFIG_PROPERTIES = {
    "config_path": {"type": "string", "description": "Explicit instances.yaml path; default resolves from HERMES_A2A_INSTANCES by presence only."},
    "run_id": {"type": "string", "pattern": r"^\d{8}T\d{6}Z-[0-9a-f]{6}$"},
    "management_root": {"type": "string", "description": "Optional management root for tests/operator fixtures."},
}


def tool_registrations() -> list[dict[str, Any]]:
    from . import views

    status_schema = _schema(
        "hermes_a2a_status",
        "Return read-only hermes-a2a plugin/package/config status metadata without creating state.",
        dict(COMMON_CONFIG_PROPERTIES),
    )
    validate_schema = _schema(
        "hermes_a2a_validate_config",
        "Validate an instances.yaml roster in memory without writing validation receipts.",
        dict(COMMON_CONFIG_PROPERTIES),
    )
    dry_run_schema = _schema(
        "hermes_a2a_peer_task_dry_run",
        "Build a network-free A2A peer-task plan for a named roster instance.",
        {
            **COMMON_CONFIG_PROPERTIES,
            "instance": {"type": "string"},
            "task_text": {"type": "string", "maxLength": 20000},
        },
        required=["instance", "task_text"],
    )
    return [
        {
            "name": "hermes_a2a_status",
            "toolset": "hermes_a2a",
            "schema": status_schema,
            "handler": safe_model_tool(
                "hermes_a2a_status",
                status_schema,
                {"config_path", "run_id", "management_root"},
                views.status_view,
            ),
            "description": status_schema["description"],
        },
        {
            "name": "hermes_a2a_validate_config",
            "toolset": "hermes_a2a",
            "schema": validate_schema,
            "handler": safe_model_tool(
                "hermes_a2a_validate_config",
                validate_schema,
                {"config_path", "run_id", "management_root"},
                views.validate_config_view,
            ),
            "description": validate_schema["description"],
        },
        {
            "name": "hermes_a2a_peer_task_dry_run",
            "toolset": "hermes_a2a",
            "schema": dry_run_schema,
            "handler": safe_model_tool(
                "hermes_a2a_peer_task_dry_run",
                dry_run_schema,
                {"config_path", "run_id", "management_root", "instance", "task_text"},
                views.peer_task_dry_run_view,
            ),
            "description": dry_run_schema["description"],
        },
    ]
