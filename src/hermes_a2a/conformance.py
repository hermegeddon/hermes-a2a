"""Local conformance gate helpers."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

_LABEL_RE = re.compile(
    r"a2a-v\d+(?:\.\d+)?(?:-[A-Za-z0-9_.-]+)?|"
    + "a2a" + "-" + "native|"
    + "upstream" + "-" + "compatible"
)


def scan_forbidden_labels(root: Path, *, allowed_prefixes: dict[str, bool] | None = None) -> list[dict[str, Any]]:
    allowed_prefixes = allowed_prefixes or {}
    findings: list[dict[str, Any]] = []
    if not root.exists():
        return findings
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix not in {".py", ".md", ".toml", ".json"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for lineno, line in enumerate(text.splitlines(), start=1):
            for match in _LABEL_RE.finditer(line):
                label = match.group(0)
                if allowed_prefixes.get(label, False):
                    continue
                findings.append({"path": str(path), "line": lineno, "label": label})
    return findings


def validate_matrix_has_zero_untriaged_required(matrix: dict[str, Any]) -> dict[str, Any]:
    rows = matrix.get("rows", [])
    bad = [
        row for row in rows
        if row.get("requiredness", "required") == "required"
        and row.get("status") not in {"passed", "not-applicable", "optional"}
    ]
    return {
        "status": "passed" if not bad else "blocked",
        "required_unimplemented": len(bad),
        "sample_ids": [row.get("id") for row in bad[:10]],
    }
