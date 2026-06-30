import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_m7_source_bundle_and_operation_table_are_pinned() -> None:
    source = json.loads((ROOT / "spec/upstream/SOURCE.json").read_text())
    operation_table = json.loads((ROOT / "milestones/m7/operation-binding-table.json").read_text())
    matrix = json.loads((ROOT / "milestones/m7/conformance-matrix.json").read_text())

    assert source["target_protocol_version"] == "1.0.0"
    assert source["tag"] == "v1.0.0"
    assert source["implementation_decision"]["sdk"]["package"] == "a2a-sdk"
    assert source["implementation_decision"]["sdk"]["version"] == "1.0.0"
    assert "single authoritative normative definition" in source["normative_roles"]["spec/upstream/a2a.proto"]
    assert len(operation_table["operations"]) == 11
    assert any(op["abstract_operation"] == "SendMessage" for op in operation_table["operations"])
    assert any(row["binding"] == "grpc" and row["object_or_operation"] == "SendMessage" for row in matrix["rows"])
