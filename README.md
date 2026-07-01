# hermes-a2a

Local implementation lane for canonical upstream A2A v1.0.0 using the pinned `a2a-sdk==1.0.0` package plus Hermes/IAP safety wrappers.

This repository is the Git-backed implementation artifact for the active Hermes Project workspace at:

```text
/home/openclaw/workspace/hermes-a2a
```

The project workspace remains the meta/management layer for plans, reviews, Kanban receipts, and status documents. This repo/submodule is where implementation code, tests, scripts, package metadata, and code-facing docs should live.

This repository is local-first. Public release, public Agent Card publication, deployment, push/merge, package publication, production access, credential rotation, destructive action, and IAP repository mutation remain separately gated. M17c/M17d/M17e local live-executor, service, and LAN pilots require explicit local approval receipts in the management workspace.

## Implemented local surfaces

- Agent Card: `GET /.well-known/agent-card.json`
- Extended Agent Card with optional local API-key gate: `GET /extendedAgentCard`
- JSON-RPC over HTTP: `POST /`
- REST/HTTP+JSON SDK routes for messages, tasks, streaming, and push notification configs
- SSE streaming via SDK streaming routes
- gRPC `A2AService` via an ephemeral loopback-only helper
- M17b validated three-instance synthetic sidecar roster and loopback sidecar runner
- M17c gated live Hermes profile executor for one approved local profile
- M17d gated user-level loopback sidecar service rollout
- M17e bounded synthetic LAN Agent Card/A2A pilot script; current proof is blocked on negative unlisted-host reachability evidence
- Hermes safety wrappers: projection scanning, receipt-before-exposure, safe receipt refs, loopback-only push policy, and conformance-label gates

## Validate

```bash
uv run --extra dev python -m pytest tests -q
uv run --extra dev python scripts/validate_local_conformance.py
uv run --extra dev python scripts/run_m17a_pilot.py
uv run --extra dev python scripts/run_m17b_triad_pilot.py --overwrite-config
uv run --extra dev python scripts/run_m17c_live_executor_pilot.py --approval-receipt /home/openclaw/workspace/hermes-a2a/milestones/m17c/<approval>.yaml --profile default
uv run --extra dev python scripts/run_m17d_service_rollout.py --approval-receipt /home/openclaw/workspace/hermes-a2a/milestones/m17d/<approval>.yaml
uv run --extra dev python scripts/run_m17e_lan_pilot.py --approval-receipt /home/openclaw/workspace/hermes-a2a/milestones/m17e/<approval>.yaml
```

Expected result at closeout: all tests pass, M16 conformance receipt is `passed`, M17a loopback pilot receipt is `passed`, M17b/M17c/M17d approved pilots write passed per-run manifests under the management workspace, and M17e writes either a passed LAN manifest or a blocked manifest naming the missing negative reachability proof.

## Documentation

- Operator guide: `docs/operator.md`
- Developer guide: `docs/developer.md`
- Release-readiness checklist: `milestones/m18/RELEASE-READINESS.md`
- IAP porting packet: `milestones/m18/IAP-PORTING-PACKET.md`
- Final conformance matrix: `milestones/m16/CONFORMANCE-MATRIX-FINAL.json`
- M17a pilot synthesis: `milestones/m17a/M17A-SYNTHESIS.md`
- M17b triad synthesis: `/home/openclaw/workspace/hermes-a2a/milestones/m17b/M17B-SYNTHETIC-TRIAD-SYNTHESIS.md`
- M17c live-executor synthesis: `/home/openclaw/workspace/hermes-a2a/milestones/m17c/M17C-LIVE-EXECUTOR-SYNTHESIS.md`
- M17d service synthesis: `/home/openclaw/workspace/hermes-a2a/milestones/m17d/M17D-LOCAL-SERVICE-SYNTHESIS.md`
- M17e LAN synthesis: `/home/openclaw/workspace/hermes-a2a/milestones/m17e/M17E-SYNTHESIS.md`
