# A2A v1.0.0 local implementation closeout

Generated: `2026-06-30T18:46:32.887735Z`

Status: **COMPLETE for the authorized local implementation scope**.

## Implemented

- Pinned upstream A2A v1.0.0 source and `a2a-sdk==1.0.0` runtime.
- Added Python package `hermes_a2a` with SDK-backed Agent Card, JSON-RPC, REST/HTTP+JSON, SSE streaming, push config policy, Extended Agent Card auth, and loopback-only gRPC helper.
- Preserved Hermes/IAP-lite safety as a local wrapper: safe projection scan, receipt-before-exposure, safe receipt refs, default-deny external push URLs, and conformance-label gates.
- Added local tests, conformance scripts, M17a loopback pilot, operator/developer docs, release-readiness checklist, and IAP porting packet.

## Verification

- `uv run --extra dev python -m pytest tests -q` → **19 passed**.
- `uv run --extra dev python scripts/validate_local_conformance.py` → **passed**.
- `uv run --extra dev python scripts/run_m17a_pilot.py` → **passed**.
- Clean-temp copy validation → **passed**.
- Final conformance matrix rows: `{'passed': 102}`.
- Hygiene: trailing whitespace `0`, non-fixture secret-shaped hits `0`, git state `not_a_git_repo`.

## Key hashes

- `PLAN.md`: `5fab0228398a335806c27426172653c374852da145280ef159820fcd863364d1`
- `uv.lock`: `5f8027b4a5121131aaff69c7b4f4f2abb613caedb4af3207c460bf29f67d4aff`
- `milestones/m16/CONFORMANCE-MATRIX-FINAL.json`: `8b15d5f00364cb583c03beca1344abf2b84e3544e0bfa910c0d1c4f5b58c945d`
- `milestones/m16/validation-receipt.json`: `54dc526611ce8c92be6a2f3a9e0c4447faeef50da17480e38f3d55467da68233`
- `milestones/m17a/validation-receipt.json`: `02e395f8d1010e53ee0a009e80d5903182b583ce30664a39f0110e8cf1fbe2aa`
- `milestones/m18/validation-receipt.json`: `10e2cd7353173820886a37fb808cdbe8256c845f2574055e2345c90feea1c2ce`

## Important non-claims / gated next steps

- No public PR, public release, package publication, deployment, or public Agent Card publication was performed.
- No LAN/public/wildcard/tunnel listener was opened. M17b remains separately gated and requires exact named hosts/profiles/ports.
- No live Hermes profile/plugin/skill/MCP/service config or IAP repository was mutated.
- The workspace is not a git repository, so no local commit was possible.

## Artifact manifest

See `milestones/final/artifact-manifest.json`.
