"""Peer-visible projection and leak checks for local Hermes A2A surfaces."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from google.protobuf import json_format
from google.protobuf.message import Message as ProtoMessage

_SECRET_RE = re.compile(r"\b(?:sk|xox[baprs]|gh[pousr]|pat|api[_-]?key|token)[-_A-Za-z0-9]{4,}", re.IGNORECASE)
_PRIVATE_PATH_RE = re.compile(r"(?:/home/openclaw|/mnt/[a-z]/Users|\.hermes|/\.ssh|/\.config)", re.IGNORECASE)
_MCP_RE = re.compile(r"\b(?:mcp|tool schema|tool call|raw tool|shell proxy)\b", re.IGNORECASE)
_ENV_RE = re.compile(r"\b[A-Z][A-Z0-9_]{5,}\s*=", re.IGNORECASE)


class ProjectionViolation(ValueError):
    """Raised when a peer-visible payload contains private/local material."""


@dataclass(frozen=True)
class ProjectionFinding:
    kind: str
    path: str
    excerpt: str


def _to_jsonable(value: Any) -> Any:
    if isinstance(value, ProtoMessage):
        return json_format.MessageToDict(value, preserving_proto_field_name=False)
    if isinstance(value, dict):
        return {str(k): _to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_jsonable(v) for v in value]
    return value


def _walk_strings(value: Any, path: str = "$"):
    if isinstance(value, str):
        yield path, value
    elif isinstance(value, dict):
        for k, v in value.items():
            yield from _walk_strings(v, f"{path}.{k}")
    elif isinstance(value, list):
        for i, v in enumerate(value):
            yield from _walk_strings(v, f"{path}[{i}]")


def scan_peer_visible(value: Any, *, surface: str) -> list[ProjectionFinding]:
    """Return leak findings for a would-be peer-visible payload."""
    payload = _to_jsonable(value)
    findings: list[ProjectionFinding] = []
    for path, text in _walk_strings(payload):
        checks = [
            ("private local path", _PRIVATE_PATH_RE),
            ("mcp/tool surface", _MCP_RE),
            ("secret-shaped token", _SECRET_RE),
            ("environment assignment", _ENV_RE),
        ]
        for kind, regex in checks:
            if regex.search(text):
                excerpt = text[:160].replace("\n", " ")
                findings.append(ProjectionFinding(kind=kind, path=f"{surface}:{path}", excerpt=excerpt))
    return findings


def assert_safe_peer_visible(value: Any, *, surface: str) -> Any:
    """Fail closed if a payload should not leave the owning Hermes boundary."""
    findings = scan_peer_visible(value, surface=surface)
    if findings:
        kinds = ", ".join(sorted({f.kind for f in findings}))
        details = "; ".join(f"{f.kind} at {f.path}" for f in findings[:5])
        raise ProjectionViolation(f"unsafe peer-visible {surface}: {kinds}; {details}")
    return value


def to_peer_dict(value: Any) -> dict[str, Any]:
    payload = _to_jsonable(value)
    if not isinstance(payload, dict):
        raise TypeError("peer-visible protobuf payload did not serialize to an object")
    return payload
