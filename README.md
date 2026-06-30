# hermes-a2a

Local implementation lane for canonical upstream A2A v1.0.0 using the pinned `a2a-sdk==1.0.0` package plus Hermes/IAP safety wrappers.

This workspace is local-only. No public release, LAN exposure, service installation, profile mutation, or IAP repo mutation is authorized by this package.

## Implemented local surfaces

- Agent Card: `GET /.well-known/agent-card.json`
- Extended Agent Card with optional local API-key gate: `GET /extendedAgentCard`
- JSON-RPC over HTTP: `POST /`
- REST/HTTP+JSON SDK routes for messages, tasks, streaming, and push notification configs
- SSE streaming via SDK streaming routes
- gRPC `A2AService` via an ephemeral loopback-only helper
- Hermes safety wrappers: projection scanning, receipt-before-exposure, safe receipt refs, loopback-only push policy, and conformance-label gates

## Validate

```bash
uv run --extra dev python -m pytest tests -q
uv run --extra dev python scripts/validate_local_conformance.py
uv run --extra dev python scripts/run_m17a_pilot.py
```

Expected result at closeout: all tests pass, M16 conformance receipt is `passed`, and M17a loopback pilot receipt is `passed`.

## Documentation

- Operator guide: `docs/operator.md`
- Developer guide: `docs/developer.md`
- Release-readiness checklist: `milestones/m18/RELEASE-READINESS.md`
- IAP porting packet: `milestones/m18/IAP-PORTING-PACKET.md`
- Final conformance matrix: `milestones/m16/CONFORMANCE-MATRIX-FINAL.json`
- M17a pilot synthesis: `milestones/m17a/M17A-SYNTHESIS.md`
