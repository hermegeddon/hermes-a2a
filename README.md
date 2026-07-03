# hermes-a2a

Local implementation lane for canonical upstream A2A v1.0.0 using the pinned `a2a-sdk==1.0.0` package plus Hermes/IAP safety wrappers.

This repository is the Git-backed implementation artifact for the active Hermes Project workspace at:

```text
<management-root>
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
- M17e bounded synthetic LAN Agent Card/A2A pilot with remote unlisted-host negative reachability evidence
- Hermes safety wrappers: projection scanning, receipt-before-exposure, safe receipt refs, loopback-only push policy, and conformance-label gates
- Hermes Agent plugin wrapper: read-only model tools, `hermes a2a` operator CLI, approval-gated live/service seams, and bundled operator skill; see `docs/plugin.md`

## Install in Hermes

The Hermes wrapper has two pieces:

1. the Python package, installed into the same Python environment that runs `hermes`;
2. the directory-plugin shim under `plugin/`, installed into the Hermes plugin directory and explicitly enabled.

For a local editable checkout on POSIX/WSL:

```bash
cd <repo>
HERMES_PY="$(dirname "$(dirname "$(realpath "$(command -v hermes)")")")/bin/python"
"$HERMES_PY" -m pip install -e .
hermes plugins install "file://$(pwd)#plugin" --no-enable
hermes plugins enable hermes-a2a --no-allow-tool-override
hermes gateway restart
hermes a2a status
```

For a public Git install, including Windows/PowerShell, use the Python interpreter from the Hermes install/venv as `<hermes-python>`:

```powershell
<hermes-python> -m pip install git+https://github.com/hermegeddon/hermes-a2a.git
hermes plugins install "https://github.com/hermegeddon/hermes-a2a.git#plugin" --no-enable
hermes plugins enable hermes-a2a --no-allow-tool-override
hermes gateway restart
hermes a2a status
```

Do not grant tool override permission; the plugin registers only additive read-only tools and a guarded operator CLI.

To run a local synthetic sidecar, provide an ephemeral test token via environment variable. The public Agent Card remains unauthenticated; protocol routes require both the token and an allowed peer id.

```bash
export HERMES_A2A_LOCAL_TEST_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
hermes a2a serve agent:local:hermes-blinky-wsl \
  --foreground \
  --executor synthetic \
  --test-token-env HERMES_A2A_LOCAL_TEST_TOKEN \
  --management-root <management-root> \
  --config <management-root>/instances/instances.yaml \
  --run-id <validated-run-id>
```

Live executor, service install/restart/stop, task-smoke, LAN exposure, public Agent Card publication, package publication, push/merge, and deployment remain separately gated.

## Validate

Commands that write run artifacts use the management root from `--management-root`, then `HERMES_A2A_MANAGEMENT_ROOT`, then the current directory/repository root depending on the entry point. Examples below use `<management-root>` for explicit approval/receipt paths.

```bash
uv run --extra dev python -m pytest tests -q
uv run --extra dev python scripts/validate_local_conformance.py
uv run --extra dev python scripts/run_m17a_pilot.py
uv run --extra dev python scripts/run_m17b_triad_pilot.py --overwrite-config
uv run --extra dev python scripts/run_m17c_live_executor_pilot.py --approval-receipt <management-root>/milestones/m17c/<approval>.yaml --profile default
uv run --extra dev python scripts/run_m17d_service_rollout.py --approval-receipt <management-root>/milestones/m17d/<approval>.yaml
uv run --extra dev python scripts/run_m17e_lan_pilot.py --approval-receipt <management-root>/milestones/m17e/<approval>.yaml --host <approved-lan-ip> --negative-ssh-host <user@unlisted-lan-host>
```

Expected result at closeout: all tests pass, M16 conformance receipt is `passed`, M17a loopback pilot receipt is `passed`, and M17b/M17c/M17d/M17e approved pilots write passed per-run manifests under the management workspace. If the M17e negative probe is omitted or inconclusive, M17e writes a blocked manifest naming the missing negative reachability proof.

## Documentation

- Operator guide: `docs/operator.md`
- Developer guide: `docs/developer.md`
- Release-readiness checklist: `milestones/m18/RELEASE-READINESS.md`
- IAP porting packet: `milestones/m18/IAP-PORTING-PACKET.md`
- Final conformance matrix: `milestones/m16/CONFORMANCE-MATRIX-FINAL.json`
- M17a pilot synthesis: `milestones/m17a/M17A-SYNTHESIS.md`
- M17b triad synthesis: `<management-root>/milestones/m17b/M17B-SYNTHETIC-TRIAD-SYNTHESIS.md`
- M17c live-executor synthesis: `<management-root>/milestones/m17c/M17C-LIVE-EXECUTOR-SYNTHESIS.md`
- M17d service synthesis: `<management-root>/milestones/m17d/M17D-LOCAL-SERVICE-SYNTHESIS.md`
- M17e LAN synthesis: `<management-root>/milestones/m17e/M17E-SYNTHESIS.md`

## License

Apache-2.0. The pinned upstream A2A v1.0.0 reference artifacts under `spec/upstream/` retain their upstream license and provenance metadata.
