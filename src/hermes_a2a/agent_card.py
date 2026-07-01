"""Agent Card construction for local Hermes A2A sidecars."""

from __future__ import annotations

from a2a.types import a2a_pb2


def _normalized_http_base(base_url: str) -> str:
    return base_url.rstrip("/")


def build_agent_card(
    *,
    base_url: str = "http://127.0.0.1",
    grpc_url: str = "127.0.0.1:0",
    name: str = "Hermes A2A Local",
    description: str = "Local-only canonical A2A v1.0.0 endpoint backed by Hermes safety gates.",
    require_auth: bool = False,
) -> a2a_pb2.AgentCard:
    http_base = _normalized_http_base(base_url)
    card = a2a_pb2.AgentCard(
        name=name,
        description=description,
        version="0.1.0-local",
        provider=a2a_pb2.AgentProvider(organization="Hermes local", url="http://127.0.0.1"),
        capabilities=a2a_pb2.AgentCapabilities(streaming=True, push_notifications=True, extended_agent_card=True),
        default_input_modes=["text/plain"],
        default_output_modes=["text/plain", "application/json"],
        supported_interfaces=[
            a2a_pb2.AgentInterface(url=f"{http_base}/", protocol_binding="JSONRPC", protocol_version="1.0"),
            a2a_pb2.AgentInterface(url=http_base, protocol_binding="HTTP+JSON", protocol_version="1.0"),
            a2a_pb2.AgentInterface(url=grpc_url, protocol_binding="GRPC", protocol_version="1.0"),
        ],
        skills=[
            a2a_pb2.AgentSkill(
                id="local-echo",
                name="Local safe echo",
                description="Synthetic local-only task execution used for canonical A2A conformance and safety-gate validation.",
                tags=["local", "synthetic", "safe"],
                examples=["ping"],
                input_modes=["text/plain"],
                output_modes=["text/plain"],
            )
        ],
    )
    if require_auth:
        card.security_schemes["HermesApiKey"].api_key_security_scheme.CopyFrom(
            a2a_pb2.APIKeySecurityScheme(
                description="Local test API key for authenticated extended Agent Card access.",
                location="header",
                name="x-hermes-a2a-key",
            )
        )
        req = card.security_requirements.add()
        req.schemes["HermesApiKey"].list.append("extended-agent-card")
    return card
