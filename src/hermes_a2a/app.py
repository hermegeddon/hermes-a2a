"""Starlette application factory for the local Hermes A2A endpoint."""

from __future__ import annotations

from functools import partial
from pathlib import Path

from a2a.server.routes.agent_card_routes import create_agent_card_routes
from a2a.server.routes.jsonrpc_routes import create_jsonrpc_routes
from a2a.server.routes.rest_routes import create_rest_routes
from a2a.server.tasks import InMemoryPushNotificationConfigStore, InMemoryTaskStore
from starlette.applications import Starlette

from hermes_a2a.agent_card import build_agent_card
from hermes_a2a.executor import SafeEchoExecutor
from hermes_a2a.handler import SafeRequestHandler, authenticated_extended_card


def build_handler(*, receipt_dir: Path, require_auth: bool = False, api_key: str | None = None) -> SafeRequestHandler:
    card = build_agent_card(require_auth=require_auth)
    extended_card = build_agent_card(require_auth=require_auth)
    executor = SafeEchoExecutor(Path(receipt_dir))
    return SafeRequestHandler(
        agent_executor=executor,
        task_store=InMemoryTaskStore(),
        agent_card=card,
        push_config_store=InMemoryPushNotificationConfigStore(),
        extended_agent_card=extended_card,
        extended_card_modifier=partial(authenticated_extended_card, api_key=api_key if require_auth else None),
    )


def build_app(*, receipt_dir: Path, require_auth: bool = False, api_key: str | None = None) -> Starlette:
    handler = build_handler(receipt_dir=receipt_dir, require_auth=require_auth, api_key=api_key)
    card = build_agent_card(require_auth=require_auth)
    routes = []
    routes.extend(create_agent_card_routes(card))
    routes.extend(create_jsonrpc_routes(handler, rpc_url="/"))
    routes.extend(create_rest_routes(handler))
    return Starlette(debug=False, routes=routes)
