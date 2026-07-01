from __future__ import annotations

import sys
from pathlib import Path

import pytest
from a2a.types import a2a_pb2

from hermes_a2a.live_executor import HermesProfileExecutor, LiveExecutorLimits, LiveInvocationResult, run_hermes_profile


def write_fake_hermes(tmp_path: Path, body: str) -> tuple[str, str]:
    script = tmp_path / "fake_hermes.py"
    script.write_text(body, encoding="utf-8")
    return (sys.executable, str(script))


@pytest.mark.asyncio
async def test_run_hermes_profile_uses_profile_prompt_and_safe_mode(tmp_path: Path) -> None:
    command = write_fake_hermes(
        tmp_path,
        """
from __future__ import annotations
import argparse
parser = argparse.ArgumentParser()
parser.add_argument('-p')
parser.add_argument('-z')
parser.add_argument('--ignore-rules', action='store_true')
parser.add_argument('--safe-mode', action='store_true')
args = parser.parse_args()
assert args.p == 'default'
assert args.ignore_rules
assert args.safe_mode
assert 'Peer task:' in args.z
assert 'hello from peer' in args.z
print('LIVE_OK')
""".strip(),
    )

    result = await run_hermes_profile(
        "hello from peer",
        profile="default",
        command=command,
        workdir=tmp_path,
        limits=LiveExecutorLimits(timeout_seconds=5),
    )

    assert result.ok
    assert result.stdout.strip() == "LIVE_OK"
    assert "hello from peer" not in " ".join(result.command_shape)
    assert "<prompt>" in result.command_shape


@pytest.mark.asyncio
async def test_run_hermes_profile_times_out_without_exposing_stderr(tmp_path: Path) -> None:
    command = write_fake_hermes(
        tmp_path,
        """
from __future__ import annotations
import time
print('before timeout')
time.sleep(5)
""".strip(),
    )

    result = await run_hermes_profile(
        "slow task",
        profile="default",
        command=command,
        limits=LiveExecutorLimits(timeout_seconds=0.1),
    )

    assert result.timed_out
    assert result.exit_code is None
    assert result.stdout_sha256
    assert result.stderr_sha256


def test_live_executor_records_private_invocation_metadata_without_raw_output(tmp_path: Path) -> None:
    executor = HermesProfileExecutor(tmp_path, profile="default")
    result = LiveInvocationResult(
        profile="default",
        command_shape=("hermes", "-p", "default", "-z", "<prompt>", "--safe-mode"),
        cwd=str(tmp_path),
        exit_code=0,
        timed_out=False,
        stdout="private raw output should not be stored in invocation receipt",
        stderr="private raw error should not be stored in invocation receipt",
        prompt_sha256="0" * 64,
        stdout_sha256="1" * 64,
        stderr_sha256="2" * 64,
        stdout_bytes=57,
        stderr_bytes=51,
    )

    ref = executor._write_invocation_receipt(result, correlation_id="unit-task")
    receipt_path = tmp_path / ref.removeprefix("receipts/")
    receipt_text = receipt_path.read_text(encoding="utf-8")

    assert ref.startswith("receipts/live-invocation-unit-task-")
    assert "private raw output" not in receipt_text
    assert "private raw error" not in receipt_text
    assert '"raw_stdout_stderr_omitted": true' in receipt_text


def test_live_executor_peer_text_fails_closed_for_oversized_output(tmp_path: Path) -> None:
    executor = HermesProfileExecutor(
        tmp_path,
        profile="default",
        limits=LiveExecutorLimits(max_peer_visible_text_bytes=8),
    )
    result = LiveInvocationResult(
        profile="default",
        command_shape=("hermes",),
        cwd=None,
        exit_code=0,
        timed_out=False,
        stdout="this is too long",
        stderr="",
        prompt_sha256="0" * 64,
        stdout_sha256="1" * 64,
        stderr_sha256="2" * 64,
        stdout_bytes=16,
        stderr_bytes=0,
    )

    state, text = executor._peer_text_from_result(result)

    assert state == a2a_pb2.TASK_STATE_FAILED
    assert "exceeded" in text
    assert "this is too long" not in text
