"""Loopback-only sidecar runner for validated M17b instance configs."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import socket
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence

from a2a.server.agent_execution import AgentExecutor
import httpx
import uvicorn

from hermes_a2a.app import build_app
from hermes_a2a.config import InstanceConfig, InstancesConfig, default_management_root, load_instances_config
from hermes_a2a.grpc_server import LocalGrpcServer
from hermes_a2a.live_executor import HermesProfileExecutor, LiveExecutorLimits


class SidecarRuntimeError(RuntimeError):
    """Raised when a sidecar cannot bind or shut down safely."""


@dataclass(frozen=True)
class SidecarEndpoint:
    conceptual_agent_id: str
    http_url: str
    grpc_target: str | None
    receipt_root: Path


class SidecarRuntime:
    """Async context manager for one validated loopback sidecar."""

    def __init__(
        self,
        instance: InstanceConfig,
        *,
        test_token: str | None,
        executor_factory: Callable[[Path], AgentExecutor] | None = None,
    ) -> None:
        self.instance = instance
        self.test_token = test_token
        self.executor_factory = executor_factory
        self._uvicorn_server: uvicorn.Server | None = None
        self._uvicorn_task: asyncio.Task[None] | None = None
        self._grpc_server: LocalGrpcServer | None = None

    @property
    def endpoint(self) -> SidecarEndpoint:
        grpc_target = None
        if self.instance.bind.grpc_port is not None:
            grpc_target = f"{self.instance.bind.host}:{self.instance.bind.grpc_port}"
        return SidecarEndpoint(
            conceptual_agent_id=self.instance.conceptual_agent_id,
            http_url=self.instance.agent_card.base_url.rstrip("/"),
            grpc_target=grpc_target,
            receipt_root=self.instance.receipt_root,
        )

    async def __aenter__(self) -> "SidecarRuntime":
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # type: ignore[no-untyped-def]
        await self.stop()

    async def start(self) -> None:
        if self.instance.bind.host != "127.0.0.1":
            raise SidecarRuntimeError("M17b sidecars may bind only 127.0.0.1")
        assert_port_free(self.instance.bind.host, self.instance.bind.http_port)
        if self.instance.bind.grpc_port is not None:
            assert_port_free(self.instance.bind.host, self.instance.bind.grpc_port)
        self.instance.receipt_root.mkdir(parents=True, exist_ok=True)
        app = build_app(
            receipt_dir=self.instance.receipt_root,
            require_auth=self.instance.auth.mode == "test_ephemeral",
            api_key=self.test_token if self.instance.auth.mode == "test_ephemeral" else None,
            agent_name=self.instance.agent_card.name,
            agent_description=f"Synthetic M17b loopback sidecar for {self.instance.conceptual_agent_id}.",
            base_url=self.instance.agent_card.base_url,
            grpc_url=(f"{self.instance.bind.host}:{self.instance.bind.grpc_port}" if self.instance.bind.grpc_port else "127.0.0.1:0"),
            allowed_peer_ids=self.instance.allowed_peer_ids,
            test_token=self.test_token if self.instance.auth.mode == "test_ephemeral" else None,
            agent_executor=self.executor_factory(self.instance.receipt_root) if self.executor_factory else None,
        )
        config = uvicorn.Config(
            app,
            host=self.instance.bind.host,
            port=self.instance.bind.http_port,
            log_level="warning",
            access_log=False,
            lifespan="off",
        )
        server = uvicorn.Server(config)
        self._uvicorn_server = server
        self._uvicorn_task = asyncio.create_task(server.serve())
        await wait_for_tcp(self.instance.bind.host, self.instance.bind.http_port)
        if self.instance.bind.grpc_port is not None:
            self._grpc_server = await LocalGrpcServer(
                receipt_dir=self.instance.receipt_root,
                host=self.instance.bind.host,
                port=self.instance.bind.grpc_port,
                agent_name=self.instance.agent_card.name,
                base_url=self.instance.agent_card.base_url,
                grpc_url=f"{self.instance.bind.host}:{self.instance.bind.grpc_port}",
                agent_executor=self.executor_factory(self.instance.receipt_root) if self.executor_factory else None,
            ).__aenter__()
            await wait_for_tcp(self.instance.bind.host, self.instance.bind.grpc_port)

    async def stop(self) -> None:
        errors: list[str] = []
        if self._grpc_server is not None:
            try:
                await self._grpc_server.__aexit__(None, None, None)
            except Exception as exc:  # pragma: no cover - defensive teardown evidence
                errors.append(f"gRPC stop failed: {exc}")
            self._grpc_server = None
        if self._uvicorn_server is not None:
            self._uvicorn_server.should_exit = True
        if self._uvicorn_task is not None:
            try:
                await asyncio.wait_for(self._uvicorn_task, timeout=5)
            except TimeoutError:
                self._uvicorn_task.cancel()
                errors.append("HTTP server did not stop within 5 seconds")
            self._uvicorn_task = None
        self._uvicorn_server = None
        if errors:
            raise SidecarRuntimeError("; ".join(errors))


class SidecarGroup:
    """Async context manager for all sidecars in one validated config."""

    def __init__(
        self,
        config: InstancesConfig,
        *,
        test_token: str | None,
        executor_factory: Callable[[Path], AgentExecutor] | None = None,
    ) -> None:
        self.config = config
        self.test_token = test_token
        self.executor_factory = executor_factory
        self.runtimes = [
            SidecarRuntime(instance, test_token=test_token, executor_factory=executor_factory) for instance in config.instances
        ]

    async def __aenter__(self) -> "SidecarGroup":
        started: list[SidecarRuntime] = []
        try:
            for runtime in self.runtimes:
                await runtime.start()
                started.append(runtime)
        except BaseException:
            for runtime in reversed(started):
                await runtime.stop()
            raise
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # type: ignore[no-untyped-def]
        errors: list[str] = []
        for runtime in reversed(self.runtimes):
            try:
                await runtime.stop()
            except Exception as stop_exc:  # pragma: no cover - defensive teardown evidence
                errors.append(str(stop_exc))
        if errors:
            raise SidecarRuntimeError("; ".join(errors))

    @property
    def endpoints(self) -> list[SidecarEndpoint]:
        return [runtime.endpoint for runtime in self.runtimes]


async def wait_for_tcp(host: str, port: int, *, timeout: float = 5.0) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    last_error: Exception | None = None
    while asyncio.get_running_loop().time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.2):
                return
        except OSError as exc:
            last_error = exc
            await asyncio.sleep(0.05)
    raise SidecarRuntimeError(f"listener did not become ready on {host}:{port}: {last_error}")


def assert_port_free(host: str, port: int) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, port))
        except OSError as exc:
            raise SidecarRuntimeError(f"port is not free before launch: {host}:{port}") from exc


async def smoke_agent_card(endpoint: SidecarEndpoint) -> dict[str, object]:
    async with httpx.AsyncClient(base_url=endpoint.http_url, timeout=5.0) as client:
        response = await client.get("/.well-known/agent-card.json")
    return {"status_code": response.status_code, "json": response.json() if response.status_code == 200 else None}


async def _serve_until_interrupted(
    config: InstancesConfig,
    *,
    instance_id: str,
    token: str | None,
    executor_factory: Callable[[Path], AgentExecutor] | None = None,
) -> None:
    instance = config.instance(instance_id)
    async with SidecarRuntime(instance, test_token=token, executor_factory=executor_factory):
        print(json.dumps({"status": "running", "instance": instance_id, "http": instance.agent_card.base_url}, indent=2))
        try:
            while True:
                await asyncio.sleep(3600)
        except (KeyboardInterrupt, asyncio.CancelledError):
            return


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run one validated hermes-a2a M17b sidecar")
    parser.add_argument("--config", default=None, help="instances.yaml; default: HERMES_A2A_INSTANCES")
    parser.add_argument("--run-id", required=True, help="M17b run id used in validation receipt")
    parser.add_argument("--instance", required=True, help="conceptual_agent_id to serve")
    parser.add_argument("--management-root", default=None, help="management workspace root; default: HERMES_A2A_MANAGEMENT_ROOT or current directory")
    parser.add_argument(
        "--test-token",
        default=None,
        help="in-memory test_ephemeral token; intended for local harnesses only and must not be persisted",
    )
    parser.add_argument("--test-token-env", default=None, help="read test_ephemeral token from this environment variable")
    parser.add_argument("--executor", choices=["synthetic", "live"], default="synthetic")
    parser.add_argument("--live-profile", default="default", help="Hermes profile for --executor live")
    parser.add_argument("--live-workdir", default=None, help="working directory for --executor live")
    parser.add_argument("--live-timeout-seconds", type=float, default=180.0)
    args = parser.parse_args(argv)
    token = args.test_token
    if args.test_token_env:
        token = os.environ.get(args.test_token_env)
    executor_factory: Callable[[Path], AgentExecutor] | None = None
    if args.executor == "live":
        live_workdir = Path(args.live_workdir) if args.live_workdir else None
        limits = LiveExecutorLimits(timeout_seconds=args.live_timeout_seconds)

        def _factory(receipt_root: Path) -> AgentExecutor:
            return HermesProfileExecutor(receipt_root, profile=args.live_profile, workdir=live_workdir, limits=limits)

        executor_factory = _factory
    config = load_instances_config(
        args.config,
        run_id=args.run_id,
        management_root=Path(args.management_root).expanduser() if args.management_root else default_management_root(),
        require_validation_receipt=True,
    )
    asyncio.run(_serve_until_interrupted(config, instance_id=args.instance, token=token, executor_factory=executor_factory))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
