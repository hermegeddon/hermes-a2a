"""A minimal local Hermes-backed A2A executor with receipt/projection gates."""

from __future__ import annotations

from pathlib import Path

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import a2a_pb2

from hermes_a2a.receipts import ReceiptStore, emit_peer_visible


class SafeEchoExecutor(AgentExecutor):
    """Synthetic local executor used to prove canonical A2A transport/safety plumbing."""

    def __init__(self, receipt_dir: Path):
        self.receipts = ReceiptStore(Path(receipt_dir))

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        text = context.get_user_input().strip() or "(empty)"
        updater = TaskUpdater(event_queue, context.task_id or "", context.context_id or "")
        response = updater.new_agent_message(
            [a2a_pb2.Part(text=f"Hermes A2A local echo: {text}", media_type="text/plain")]
        )
        emitted = emit_peer_visible(
            self.receipts,
            response,
            surface="message",
            correlation_id=context.task_id or "no-task-id",
        )
        metadata = {
            "hermesReceiptRef": emitted["receipt_ref"],
            "hermesPayloadSha256": emitted["payload_sha256"],
        }
        response.metadata.update(metadata)
        await updater.update_status(
            a2a_pb2.TaskState.TASK_STATE_COMPLETED,
            message=response,
            metadata=metadata,
        )

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        updater = TaskUpdater(event_queue, context.task_id or "", context.context_id or "")
        message = updater.new_agent_message([a2a_pb2.Part(text="Canceled", media_type="text/plain")])
        await updater.cancel(message=message)
