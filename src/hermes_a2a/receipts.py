"""Private receipt writing before peer-visible A2A exposure."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from hermes_a2a.projection import assert_safe_peer_visible, to_peer_dict


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


@dataclass
class ReceiptStore:
    root: Path

    def __post_init__(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)

    def write_receipt(self, *, surface: str, payload: dict[str, Any], correlation_id: str) -> dict[str, Any]:
        body = _stable_json(payload).encode("utf-8")
        payload_sha = hashlib.sha256(body).hexdigest()
        receipt = {
            "schema": "hermes-a2a/private-receipt/v1",
            "created_at": _utc_now(),
            "surface": surface,
            "correlation_id": correlation_id,
            "payload_sha256": payload_sha,
            "payload_bytes": len(body),
            "projection": "passed-before-exposure",
        }
        name = f"receipt-{correlation_id}-{uuid4().hex}.json"
        tmp = self.root / f".{name}.tmp"
        final = self.root / name
        tmp.write_text(json.dumps(receipt, indent=2, sort_keys=True), encoding="utf-8")
        os.replace(tmp, final)
        receipt["path"] = str(final)
        receipt["relative_ref"] = f"receipts/{name}"
        return receipt


def emit_peer_visible(store: ReceiptStore, payload: Any, *, surface: str, correlation_id: str) -> dict[str, Any]:
    """Project, scan, persist private receipt, then return safe payload metadata."""
    assert_safe_peer_visible(payload, surface=surface)
    peer_dict = to_peer_dict(payload)
    receipt = store.write_receipt(surface=surface, payload=peer_dict, correlation_id=correlation_id)
    return {
        "payload": peer_dict,
        "payload_sha256": receipt["payload_sha256"],
        "receipt_path": receipt["path"],
        "receipt_ref": receipt["relative_ref"],
    }
