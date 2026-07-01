# hermes-a2a local operator guide

This package exposes a **local-only** A2A v1.0.0 endpoint using the pinned upstream `a2a-sdk==1.0.0` runtime and Hermes safety wrappers.

## Scope and non-authorizations

Allowed by this workspace:

- local package/test execution;
- ephemeral loopback HTTP/gRPC smokes;
- synthetic local-only A2A tasks;
- local receipt/artifact generation under this workspace.

Not authorized by this workspace:

- public PRs, public releases, package publication, deployment, or public Agent Card publication;
- LAN/public/wildcard/tunnel listeners;
- live Hermes profile/plugin/skill/MCP/service mutation;
- IAP repository mutation;
- protected work data, credentials, or work-paid compute.

## Run local tests

```bash
uv run --extra dev python -m pytest tests -q
```

## Run conformance evidence

```bash
uv run --extra dev python scripts/validate_local_conformance.py
```

This writes:

- `milestones/m16/validation-receipt.json`
- `milestones/m16/CONFORMANCE-MATRIX-FINAL.json`
- `milestones/m16/CONFORMANCE-SYNTHESIS.md`

The warning logs for denied external push and missing extended-card auth are expected negative tests.

## Run the same-machine pilot

```bash
uv run --extra dev python scripts/run_m17a_pilot.py
```

This starts an ephemeral `127.0.0.1:0` gRPC server, sends a synthetic A2A task, reads it back, stops the server, and writes:

- `milestones/m17a/validation-receipt.json`
- `milestones/m17a/M17A-SYNTHESIS.md`

## Run the M17b synthetic sidecar triad

```bash
uv run --extra dev python scripts/run_m17b_triad_pilot.py --overwrite-config
```

This is still synthetic-only. It writes or refreshes the management roster at:

```text
/home/openclaw/workspace/hermes-a2a/instances/instances.yaml
```

Then it validates the roster, starts three foreground loopback sidecars with in-memory `test_ephemeral` auth, exercises JSON-RPC, REST, and gRPC, captures `ss -ltnp` bind/teardown evidence, stops every sidecar, and writes per-run evidence under:

```text
/home/openclaw/workspace/hermes-a2a/milestones/m17b/runs/<run_id>/
```

The M17b runner must not be used for live Hermes profile execution, host inventory, service installation/restart, LAN/Tailscale exposure, work data, credentials, or raw MCP/tool proxying. Those remain M17c+ / M17d+ / M17e gated actions.

## A2A surfaces implemented locally

- Agent Card: `GET /.well-known/agent-card.json`
- JSON-RPC: `POST /`
- REST: SDK routes for `message:send`, `message:stream`, `tasks`, push notification config, and extended Agent Card.
- gRPC: SDK `A2AService` served by `LocalGrpcServer` for loopback smokes and by the M17b sidecar runtime on validated per-instance ports.

Every HTTP request to SDK protocol routes must include:

```text
A2A-Version: 1.0
```

## Receipts

Peer-visible executor output is projected and scanned before emission. A private receipt is written before the completion status is enqueued. Peer-visible task metadata exposes only:

- `hermesReceiptRef`
- `hermesPayloadSha256`

Receipt files are local artifacts under the requested receipt directory and are not public protocol payloads.
