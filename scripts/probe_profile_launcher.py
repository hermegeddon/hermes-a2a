#!/usr/bin/env python3
"""M17c-gated launcher proof for one live Hermes profile."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
from typing import Sequence

from hermes_a2a.live_executor import LiveExecutorLimits, run_hermes_profile


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Probe one approved Hermes profile launcher shape")
    parser.add_argument("--profile", default="default")
    parser.add_argument("--workdir", default=os.environ.get("HERMES_A2A_MANAGEMENT_ROOT", "."))
    parser.add_argument("--marker", default="HERMES_A2A_LAUNCHER_OK")
    parser.add_argument("--timeout-seconds", type=float, default=120.0)
    return parser


async def probe(args: argparse.Namespace) -> dict[str, object]:
    prompt = f"M17c launcher proof: reply with exactly {args.marker} and no extra text."
    result = await run_hermes_profile(
        prompt,
        profile=args.profile,
        workdir=Path(args.workdir),
        limits=LiveExecutorLimits(timeout_seconds=args.timeout_seconds, max_peer_visible_text_bytes=2000),
    )
    visible_text = result.stdout.strip() or result.stderr.strip()
    return {
        "schema": "hermes-a2a/m17c-launcher-proof/v1",
        "status": "passed" if result.ok and args.marker in visible_text else "failed",
        "profile": args.profile,
        "workdir": args.workdir,
        "command_shape": list(result.command_shape),
        "exit_code": result.exit_code,
        "timed_out": result.timed_out,
        "stdout_sha256": result.stdout_sha256,
        "stderr_sha256": result.stderr_sha256,
        "stdout_bytes": result.stdout_bytes,
        "stderr_bytes": result.stderr_bytes,
        "marker_seen": args.marker in visible_text,
        "raw_stdout_stderr_omitted": True,
    }


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    payload = asyncio.run(probe(args))
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
