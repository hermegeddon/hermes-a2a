"""In-process loopback gRPC server for local A2A conformance smokes."""

from __future__ import annotations

from pathlib import Path
from types import TracebackType
from typing import Self

import grpc

from a2a.server.agent_execution import AgentExecutor
from a2a.server.request_handlers import GrpcHandler
from a2a.types import a2a_pb2_grpc

from hermes_a2a.app import build_handler


class LocalGrpcServer:
    """Async context manager that serves A2A gRPC on loopback only."""

    def __init__(
        self,
        *,
        receipt_dir: Path,
        host: str = "127.0.0.1",
        port: int = 0,
        agent_name: str = "Hermes A2A Local",
        base_url: str = "http://127.0.0.1",
        grpc_url: str = "127.0.0.1:0",
        agent_executor: AgentExecutor | None = None,
    ) -> None:
        if host != "127.0.0.1":
            raise ValueError("LocalGrpcServer is intentionally loopback-only")
        self.receipt_dir = Path(receipt_dir)
        self.bound_host = host
        self.requested_port = port
        self.port = 0
        self.agent_name = agent_name
        self.base_url = base_url
        self.grpc_url = grpc_url
        self.agent_executor = agent_executor
        self._server: grpc.aio.Server | None = None

    async def __aenter__(self) -> Self:
        handler = build_handler(
            receipt_dir=self.receipt_dir,
            agent_name=self.agent_name,
            base_url=self.base_url,
            grpc_url=self.grpc_url,
            agent_executor=self.agent_executor,
        )
        servicer = GrpcHandler(handler)
        server = grpc.aio.server()
        a2a_pb2_grpc.add_A2AServiceServicer_to_server(servicer, server)
        self.port = server.add_insecure_port(f"{self.bound_host}:{self.requested_port}")
        if self.port <= 0:
            raise RuntimeError("failed to bind local gRPC server")
        await server.start()
        self._server = server
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if self._server is not None:
            await self._server.stop(grace=0)
            self._server = None

    def channel(self) -> grpc.aio.Channel:
        if self.port <= 0:
            raise RuntimeError("server is not running")
        return grpc.aio.insecure_channel(f"{self.bound_host}:{self.port}")
