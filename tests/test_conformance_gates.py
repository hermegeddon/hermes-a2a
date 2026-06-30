import json
from pathlib import Path

from hermes_a2a.conformance import scan_forbidden_labels, validate_matrix_has_zero_untriaged_required

ROOT = Path(__file__).resolve().parents[1]


def test_no_premature_conformance_labels_in_source_tree() -> None:
    findings = scan_forbidden_labels(ROOT / "src", allowed_prefixes={"a2a-v1-full-local": False})
    assert findings == []


def test_matrix_gate_reports_required_unimplemented_rows() -> None:
    matrix = json.loads((ROOT / "milestones/m7/conformance-matrix.json").read_text())
    result = validate_matrix_has_zero_untriaged_required(matrix)
    assert result["required_unimplemented"] > 0
    assert result["status"] == "blocked"
