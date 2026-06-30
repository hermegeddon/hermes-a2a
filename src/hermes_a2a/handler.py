"""Request-handler wrappers that enforce local Hermes policy before SDK dispatch."""

from __future__ import annotations

from a2a.server.context import ServerCallContext
from a2a.server.request_handlers.default_request_handler import LegacyRequestHandler
from a2a.types import a2a_pb2
from a2a.utils.errors import InvalidRequestError

from hermes_a2a.policy import ensure_loopback_push_url, require_api_key


class SafeRequestHandler(LegacyRequestHandler):
    async def on_create_task_push_notification_config(
        self, params: a2a_pb2.TaskPushNotificationConfig, context: ServerCallContext
    ) -> a2a_pb2.TaskPushNotificationConfig:
        try:
            ensure_loopback_push_url(params.url)
        except ValueError as exc:
            raise InvalidRequestError(message=str(exc)) from exc
        return await super().on_create_task_push_notification_config(params, context)


async def authenticated_extended_card(card: a2a_pb2.AgentCard, context: ServerCallContext, *, api_key: str | None) -> a2a_pb2.AgentCard:
    headers = {str(k).lower(): str(v) for k, v in context.state.get("headers", {}).items()}
    try:
        require_api_key(headers, api_key)
    except PermissionError as exc:
        raise InvalidRequestError(message=str(exc)) from exc
    return card
