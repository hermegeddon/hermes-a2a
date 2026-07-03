---
name: operator
description: Safely operate the local-first hermes-a2a Hermes plugin wrapper.
version: 0.1.0
---

# hermes-a2a operator skill

## Purpose & scope

Use this skill when operating the local-first `hermes-a2a` Hermes plugin wrapper. The plugin exposes read-only model tools and an operator CLI around the existing `hermes_a2a` package. It is not a public deployment path, a model provider, a gateway platform adapter, a raw MCP/tool proxy, or an automatic service launcher.

## Model tool index

- `hermes_a2a_status`: returns package/config/roster metadata and env-var presence by name only. It must not return env values, Hermes core/profile config, receipt contents, live service state, or raw private paths.
- `hermes_a2a_validate_config`: validates an instances config in memory. It must not write validation receipts or launch sidecars.
- `hermes_a2a_peer_task_dry_run`: builds a network-free peer-task plan. It must not send a task, open sockets, write receipts, or consume approvals.

## CLI index

Read-only commands: `status`, `validate-config` without `--write-receipt`, `plan`, `receipts list`, `receipts show`, `card show`, and `service status`.

Gated commands: live `serve`, `service install|restart|stop --instance local-services`, and `task-smoke agent:local:hermes-blinky-wsl` require every live gate before any delegate is touched. Plugin service operations are limited to the two local units and exclude `hermes-a2a-work-hermes-work.service`; task-smoke delegates to the existing M17c live loopback pilot for the supported local live instance.

## Gate model

Every gated command requires: `--live-enabled`, `--yes`, `--approval-receipt <path>`, and the operation-specific environment gate (`HERMES_A2A_PLUGIN_LIVE`, `HERMES_A2A_PLUGIN_SERVICE`, or `HERMES_A2A_PLUGIN_TASK_SMOKE`). Missing any one gate is a refusal before delegation.

## Approval receipts

Approval receipts live at `$HERMES_HOME/state/hermes-a2a-plugin/approvals/<id>.yaml`. They use strict schema version 1, a normalized UUID4 `id`, operation and instance binding, `issued_at`/`expires_at` timestamps with TTL at most 24 hours, a non-empty approver, and `scope: single-use`. The receipt path must be the canonical approvals-root `<id>.yaml` path, and the plugin derives the root-level `<id>.consumed` marker from the normalized UUID before writing it immediately before a gated delegate call.

## Receipt/artifact locations

Package execution receipts remain under the configured package receipt roots. Plugin approval receipts and consumption markers live under `$HERMES_HOME/state/hermes-a2a-plugin/approvals/`. Model tools do not read receipt contents and do not write receipts.

## Rollback / uninstall

Before enablement, remove the copied/symlinked plugin shim or uninstall the wheel. Optional cleanup is `$HERMES_HOME/state/hermes-a2a-plugin/` if approvals were created. No systemd units, profiles, Hermes config files, or services are changed by registration.

## Standing non-authorizations

No public release, public PR, push, merge, deployment, package publication, public Agent Card publication, plugin enablement, service install/restart/stop execution, live profile/service/LAN mutation, credential access, work-data access, raw-tool/MCP proxying, public/wildcard/tunnel listener, or `agent:work:hermes-work` live execution is authorized by this wrapper.

## Interpreting refusal messages

- `missing_live_enabled`: explicit live-operation opt-in was absent.
- `missing_yes`: operator confirmation was absent.
- `missing_approval_receipt`: no receipt path was supplied.
- `approval_receipt_*`: the receipt failed the named containment, schema, operation, instance, time, approver, or single-use rule.
- `missing_env_gate`: the operation-specific env gate is absent or false.
- `unexpected_argument`: an execution-control argument was refused before work.
- `projection_refused`: unsafe output was redacted and raw content was not returned.
