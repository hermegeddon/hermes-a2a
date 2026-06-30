"""Local policy gates for Hermes A2A."""

from __future__ import annotations

import ipaddress
from urllib.parse import urlparse


def ensure_loopback_push_url(url: str) -> str:
    """Allow push webhook destinations only on loopback by default."""
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("push URL must be an HTTP(S) loopback URL")
    host = parsed.hostname
    if host == "localhost":
        return url
    try:
        ip = ipaddress.ip_address(host)
    except ValueError as exc:
        raise ValueError("push URL host is not loopback") from exc
    if not ip.is_loopback:
        raise ValueError("push URL host is not loopback")
    if str(ip) in {"0.0.0.0", "::"}:
        raise ValueError("wildcard push URL host is forbidden")
    return url


def require_api_key(headers: dict[str, str], expected: str | None) -> None:
    if not expected:
        return
    supplied = headers.get("x-hermes-a2a-key") or headers.get("X-Hermes-A2A-Key")
    if supplied != expected:
        raise PermissionError("A2A extended card authentication required")
