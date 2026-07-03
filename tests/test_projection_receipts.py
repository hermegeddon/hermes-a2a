import json
from pathlib import Path

import pytest
from a2a.types import a2a_pb2

from hermes_a2a.projection import ProjectionViolation, assert_safe_peer_visible
from hermes_a2a.receipts import ReceiptStore, emit_peer_visible


def test_projection_rejects_private_paths_mcp_and_secret_shaped_text() -> None:
    msg = a2a_pb2.Message(role=a2a_pb2.ROLE_AGENT)
    msg.parts.append(a2a_pb2.Part(text="internal /home/example/.hermes config uses MCP tool sk-live"))

    with pytest.raises(ProjectionViolation) as exc:
        assert_safe_peer_visible(msg, surface="message")

    assert "private local path" in str(exc.value)
    assert "mcp/tool surface" in str(exc.value)
    assert "secret-shaped token" in str(exc.value)


def test_emit_peer_visible_writes_receipt_before_payload(tmp_path: Path) -> None:
    store = ReceiptStore(tmp_path / "receipts")
    msg = a2a_pb2.Message(role=a2a_pb2.ROLE_AGENT)
    msg.parts.append(a2a_pb2.Part(text="safe hello"))

    emitted = emit_peer_visible(store, msg, surface="message", correlation_id="corr-1")

    assert emitted["payload"]["parts"][0]["text"] == "safe hello"
    receipt_path = Path(emitted["receipt_path"])
    assert receipt_path.exists()
    receipt = json.loads(receipt_path.read_text())
    assert receipt["payload_sha256"] == emitted["payload_sha256"]
    assert receipt["surface"] == "message"
