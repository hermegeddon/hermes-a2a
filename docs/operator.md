# hermes-a2a local operator guide

This package exposes a local A2A v1.0.0 endpoint using the pinned upstream `a2a-sdk==1.0.0` runtime and Hermes safety wrappers.

## Scope and non-authorizations

Allowed by this workspace:

- local package/test execution;
- ephemeral loopback HTTP/gRPC smokes;
- synthetic local-only A2A tasks;
- local receipt/artifact generation under this workspace;
- explicitly approved M17c/M17d/M17e local live-executor, sidecar-service, and LAN pilots when the matching approval receipt exists.

Not authorized by this workspace:

- public PRs, public releases, package publication, deployment, or public Agent Card publication;
- public/wildcard/tunnel listeners;
- LAN listeners without an exact-scope approval receipt and rollback;
- live Hermes profile/plugin/skill/MCP/service mutation outside the approved M17c/M17d sidecar scope;
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

## Run the M17c live-executor loopback pilot

```bash
uv run --extra dev python scripts/run_m17c_live_executor_pilot.py \
  --approval-receipt /home/openclaw/workspace/hermes-a2a/milestones/m17c/<approval>.yaml \
  --profile default
```

The pilot first proves the exact noninteractive Hermes launcher for the approved profile, then runs one loopback sidecar with `HermesProfileExecutor`. Raw stdout/stderr, profile paths, hidden prompts, and stack traces are private receipt data only; peer-visible A2A output is bounded and projected. It writes per-run evidence under:

```text
/home/openclaw/workspace/hermes-a2a/milestones/m17c/runs/<run_id>/
```

## Run the M17d user-service rollout

```bash
uv run --extra dev python scripts/run_m17d_service_rollout.py \
  --approval-receipt /home/openclaw/workspace/hermes-a2a/milestones/m17d/<approval>.yaml
```

The rollout installs/reloads only the finite `hermes-a2a-*` user units named in the script, uses environment files under `~/.config/hermes-a2a/m17d/`, binds loopback-only ports `18731`–`18733` and `18741`–`18743`, captures `systemctl --user` state, PID/command lines, focused logs, and `ss -ltnp` evidence, and smokes Agent Card, JSON-RPC, REST, and gRPC. Rollback:

```bash
systemctl --user disable --now hermes-a2a-local-hermes-blinky-wsl.service hermes-a2a-local-hermes-blinky-windows.service hermes-a2a-work-hermes-work.service
rm -f ~/.config/systemd/user/hermes-a2a-local-hermes-blinky-wsl.service \
      ~/.config/systemd/user/hermes-a2a-local-hermes-blinky-windows.service \
      ~/.config/systemd/user/hermes-a2a-work-hermes-work.service
systemctl --user daemon-reload
```

## Run the M17e bounded LAN pilot

```bash
uv run --extra dev python scripts/run_m17e_lan_pilot.py \
  --approval-receipt /home/openclaw/workspace/hermes-a2a/milestones/m17e/<approval>.yaml \
  --host 192.168.1.3 --http-port 18751
```

The LAN pilot is synthetic-only by default and starts a foreground HTTP sidecar on the exact named local-network address, never wildcard. It fetches the Agent Card and completes a synthetic JSON-RPC task through that address, denies a non-allowed peer, captures bind/teardown evidence, and stops the listener. If no negative reachability proof from an unlisted host (or equivalent firewall/ACL deny receipt) is provided, the script writes a `blocked` M17e receipt rather than claiming LAN readiness.

## A2A surfaces implemented locally

- Agent Card: `GET /.well-known/agent-card.json`
- JSON-RPC: `POST /`
- REST: SDK routes for `message:send`, `message:stream`, `tasks`, push notification config, and extended Agent Card.
- gRPC: SDK `A2AService` served by `LocalGrpcServer` for loopback smokes, by the M17b foreground sidecar runtime, and by the M17d loopback user services on validated per-instance ports.

Every HTTP request to SDK protocol routes must include:

```text
A2A-Version: 1.0
```

## Receipts

Peer-visible executor output is projected and scanned before emission. A private receipt is written before the completion status is enqueued. Peer-visible task metadata exposes only:

- `hermesReceiptRef`
- `hermesPayloadSha256`

Receipt files are local artifacts under the requested receipt directory and are not public protocol payloads.
