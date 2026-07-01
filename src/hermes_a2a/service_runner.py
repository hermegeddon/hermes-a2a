"""Direct sidecar service runner for gated M17d/M17e local service pilots."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import socket
from pathlib import Path
from typing import Sequence

import uvicorn

from a2a.server.agent_execution import AgentExecutor

from hermes_a2a.app import build_app
from hermes_a2a.grpc_server import LocalGrpcServer
from hermes_a2a.live_executor import HermesProfileExecutor, LiveExecutorLimits
from hermes_a2a.serve import SidecarRuntimeError, wait_for_tcp


def _port_free(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, port))
        except OSError:
            return False
    return True


def build_executor(
    executor: str,
    *,
    receipt_root: Path,
    live_profile: str,
    live_workdir: Path | None,
    live_timeout_seconds: float,
    hermes_command: str,
) -> AgentExecutor | None:
    if executor == "synthetic":
        return None
    return HermesProfileExecutor(
        receipt_root,
        profile=live_profile,
        command=(hermes_command,),
        workdir=live_workdir,
        limits=LiveExecutorLimits(timeout_seconds=live_timeout_seconds),
    )


async def run_service(args: argparse.Namespace) -> None:
    if args.host != "127.0.0.1" and not args.allow_non_loopback:
        raise SidecarRuntimeError("non-loopback bind requires --allow-non-loopback")
    if args.grpc_port and args.host != "127.0.0.1":
        raise SidecarRuntimeError("gRPC service runner remains loopback-only; omit --grpc-port for LAN HTTP pilots")
    if not _port_free(args.host, args.http_port):
        raise SidecarRuntimeError(f"HTTP port is not free before launch: {args.host}:{args.http_port}")
    if args.grpc_port and not _port_free(args.host, args.grpc_port):
        raise SidecarRuntimeError(f"gRPC port is not free before launch: {args.host}:{args.grpc_port}")

    receipt_root = Path(args.receipt_root)
    receipt_root.mkdir(parents=True, exist_ok=True)
    token = os.environ.get(args.test_token_env) if args.test_token_env else args.test_token
    agent_executor = build_executor(
        args.executor,
        receipt_root=receipt_root,
        live_profile=args.live_profile,
        live_workdir=Path(args.live_workdir) if args.live_workdir else None,
        live_timeout_seconds=args.live_timeout_seconds,
        hermes_command=args.hermes_command,
    )
    grpc_url = f"{args.host}:{args.grpc_port}" if args.grpc_port else "127.0.0.1:0"
    app = build_app(
        receipt_dir=receipt_root,
        require_auth=bool(token),
        api_key=token,
        agent_name=args.agent_name,
        agent_description=args.agent_description,
        base_url=args.base_url,
        grpc_url=grpc_url,
        allowed_peer_ids=args.allowed_peer_id,
        test_token=token,
        agent_executor=agent_executor,
    )
    config = uvicorn.Config(app, host=args.host, port=args.http_port, log_level=args.log_level, access_log=False, lifespan="off")
    http_server = uvicorn.Server(config)
    http_task = asyncio.create_task(http_server.serve())
    grpc_server: LocalGrpcServer | None = None
    try:
        await wait_for_tcp(args.host, args.http_port)
        if args.grpc_port:
            grpc_server = await LocalGrpcServer(
                receipt_dir=receipt_root,
                host=args.host,
                port=args.grpc_port,
                agent_name=args.agent_name,
                base_url=args.base_url,
                grpc_url=grpc_url,
                agent_executor=agent_executor,
            ).__aenter__()
            await wait_for_tcp(args.host, args.grpc_port)
        print(
            json.dumps(
                {
                    "status": "running",
                    "conceptual_agent_id": args.conceptual_agent_id,
                    "executor": args.executor,
                    "http": args.base_url,
                    "grpc": grpc_url if args.grpc_port else None,
                    "receipt_root": str(receipt_root),
                },
                indent=2,
                sort_keys=True,
            ),
            flush=True,
        )
        while True:
            await asyncio.sleep(3600)
    finally:
        if grpc_server is not None:
            await grpc_server.__aexit__(None, None, None)
        http_server.should_exit = True
        await http_task


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run one gated hermes-a2a sidecar from explicit service args")
    parser.add_argument("--conceptual-agent-id", required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--http-port", type=int, required=True)
    parser.add_argument("--grpc-port", type=int, default=None)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--agent-name", required=True)
    parser.add_argument("--agent-description", default="Local gated Hermes A2A sidecar.")
    parser.add_argument("--receipt-root", required=True)
    parser.add_argument("--allowed-peer-id", action="append", default=[])
    parser.add_argument("--test-token", default=None, help="local harness token; avoid for persistent services")
    parser.add_argument("--test-token-env", default=None, help="read local sidecar token from this environment variable")
    parser.add_argument("--executor", choices=["synthetic", "live"], default="synthetic")
    parser.add_argument("--live-profile", default="default")
    parser.add_argument("--live-workdir", default=None)
    parser.add_argument("--live-timeout-seconds", type=float, default=180.0)
    parser.add_argument("--hermes-command", default=str(Path.home() / ".local" / "bin" / "hermes"))
    parser.add_argument("--allow-non-loopback", action="store_true")
    parser.add_argument("--log-level", default="warning")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    asyncio.run(run_service(args))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
