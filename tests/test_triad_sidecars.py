from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.run_m17b_triad_pilot import run_pilot

RUN_ID = "20260701T000002Z-abcdef"


@pytest.mark.asyncio
async def test_m17b_triad_pilot_writes_manifest_and_synthesis(tmp_path: Path) -> None:
    management_root = tmp_path / "management"
    config_path = management_root / "instances" / "instances.yaml"

    final = await run_pilot(management_root=management_root, config_path=config_path, run_id=RUN_ID, overwrite_config=False)

    assert final["status"] == "passed"
    assert config_path.exists()
    manifest_path = Path(final["manifest"])
    synthesis_path = Path(final["synthesis"])
    receipt_path = Path(final["triad_receipt"])
    assert manifest_path.exists()
    assert synthesis_path.exists()
    assert receipt_path.exists()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert manifest["run_id"] == RUN_ID
    assert manifest["readback"]["bad_count"] == 0
    assert receipt["status"] == "passed"
    assert receipt["assertions"]["listener_during_loopback_only"]
    assert receipt["assertions"]["listener_after_teardown_clean"]
    assert receipt["assertions"]["negative_config_tests_denied"]
    assert "No live Hermes profile execution" in synthesis_path.read_text(encoding="utf-8")
