# hermes-a2a Hermes plugin wrapper

This document is the operator-facing guide and implementation evidence ledger for the reviewed rev-2 Hermes plugin wrapper plan.

Governing plan: `/home/openclaw/workspace/hermes-a2a/.hermes/plans/2026-07-03_1218-hermes-a2a-plugin-wrapper-plan.md`

Plan SHA-256 verified before implementation: `8edd084d6f4fc363f49ab89b99be5ea4541f4fb25c2f26612dc7c06d90af54da`.

## Slice 0 gate matrix findings

Recorded on branch `feat/hermes-plugin-wrapper` before plugin implementation code.

| Gate | Finding | Branch chosen |
|---|---|---|
| G0.1 Hermes version/API | `hermes --version` reports Hermes Agent v0.18.0 (2026.7.1), upstream `f8a76bd5`. `hermes_cli/plugins.py` defines `PluginContext`, directory plugin manifests, tool/CLI/skill registration, and opt-in plugin loading. | Support Hermes v0.18.x plugin API; document the plan as validated against v0.18.0. |
| G0.2 `plugin.yaml` schema and loader behavior | Directory plugins require `plugin.yaml` plus `__init__.py`. `PluginManager._parse_manifest()` reads YAML metadata only; `_load_plugin()` imports and calls `register(ctx)` only for enabled standalone plugins. | Keep a directory shim at `plugin/` with manifest and side-effect-free import/registration. |
| G0.3 Directory shim disabled-by-default | User/project/entry-point standalone plugins are skipped unless present in `plugins.enabled`; disabled entries are listed with `enabled=false` and an explanatory error. | Keep `plugin/` shim; prove with isolated `HERMES_HOME` smoke in Slice 9. |
| G0.4 Pip entry-point group | `ENTRY_POINTS_GROUP = "hermes_agent.plugins"`; `_scan_entry_points()` records entry-point plugins under that group. | Add a `hermes_agent.plugins` entry point in packaging. |
| G0.5 `register_tool` signature | `register_tool(name, toolset, schema, handler, check_fn=None, requires_env=None, is_async=False, description="", emoji="", override=False)` is present; `override=True` is separately gated and must not be used. | Wire tools through `ctx.register_tool(..., override=False)` and enforce factory/schema tests. |
| G0.6 `register_cli_command` signature | `register_cli_command(name, help, setup_fn, handler_fn=None, description="")` is present. | Register one CLI noun, guarded with `hasattr(ctx, "register_cli_command")`. |
| G0.7 `register_skill` path semantics | `register_skill(name, path, description="")` validates an existing path and stores that path in the plugin skill registry; it does not copy into `$HERMES_HOME/skills`. | Register bundled absolute skill path when `register_skill` exists; no profile skill mutation is required. |
| G0.8 In-memory/no-receipt validation API | `hermes_a2a.config.load_instances_config(..., require_validation_receipt=False)` parses and validates the config without writing the validation receipt. Receipt writing is isolated in `write_validation_receipt()` / CLI validate path. | Slice 4a is not needed; model validation tool can use the existing in-memory path directly. |
| G0.9 CLI noun collision | `hermes a2a --help` and `hermes hermes-a2a --help` both currently fail as invalid core commands; no built-in noun collision was found. | Use `hermes a2a ...` as the CLI noun. |

No Slice 0 stop branch was hit. Proceed in-repo per the plan default; relocation remains mechanical if requested later.

## Install and enablement model

The plugin is shipped with this package in two forms:

1. A directory-plugin shim under `plugin/` for copy/symlink installation into a Hermes plugin directory.
2. An importable package `hermes_a2a_plugin` with a `hermes_agent.plugins` entry point for future pip-style discovery.

Enablement is deliberately not performed by this implementation. Operators may enable the plugin later using normal Hermes plugin controls after review. Installing the wheel or copying the shim must not start services, bind ports, mutate profiles, or enable the plugin.

## Model tools

All model-callable tools are read-only and constructed via the internal safe model-tool factory. They can report metadata and safe projections only.

| Tool | Returns | Never returns or does |
|---|---|---|
| `hermes_a2a_status` | Package/plugin availability, config resolution status, env var presence by name, safe roster summary when a config validates, and path-existence metadata. | Env values, Hermes core/profile config, receipt contents, live service state, `systemctl` output, raw private paths without projection scanning, network/process/service actions. |
| `hermes_a2a_validate_config` | In-memory pass/fail validation for an explicit or env-resolved config path, plus structured errors and safe summary metadata. | Validation receipts, writes, sidecar launch, system/service calls, env values, raw credentials. |
| `hermes_a2a_peer_task_dry_run` | A no-network task plan for a roster instance: target URL/method and projected payload metadata. | Live task submission, network I/O, receipt writes, live execution, approval-consuming behavior. |

## CLI index

Read-only commands:

| Command | Purpose | Side effects |
|---|---|---|
| `hermes a2a status` | Operator status view; may include read-only user-service status probes. | No writes. |
| `hermes a2a validate-config [--config PATH] [--write-receipt]` | Validate roster config. | No writes unless `--write-receipt` is explicitly set; then writes exactly the package validation receipt. |
| `hermes a2a plan` | Print the rollout/serve plan for the roster. | No writes. |
| `hermes a2a receipts list|show <ref>` | Show safe receipt metadata/summaries. | No writes. |
| `hermes a2a card show [instance]` | Show public-safe Agent Card metadata. | No writes. |

Gated commands:

| Command | Gate requirement |
|---|---|
| `hermes a2a serve <instance> --foreground` with live executor | Full gate set. Synthetic foreground serving remains aligned with the existing package behavior. |
| `hermes a2a service install|restart|stop` | Full gate set plus service-operation env gate. |
| `hermes a2a task-smoke <instance>` | Full gate set plus task-smoke env gate. |

Service status is read-only and ungated.

## Gate model

All gated operations must pass every gate before any delegate is touched:

1. `--live-enabled`
2. `--yes`
3. `--approval-receipt <path>` valid under the approval receipt contract below
4. Operation-specific environment gate, reported by name only

Any missing or invalid gate produces a structured refusal naming the failed rule. Invalid paths must not invoke top-level delegates.

## Approval receipts

Approval receipts are operator-issued inputs, separate from package execution receipts.

Location:

```text
$HERMES_HOME/state/hermes-a2a-plugin/approvals/<id>.yaml
```

Strict schema:

```yaml
kind: approval
schema_version: 1
id: <uuid4>
operation: <serve-live|service-install|service-restart|service-stop|task-smoke>
instance: <roster instance name>
issued_at: <RFC3339 UTC>
expires_at: <RFC3339 UTC>
approver: <identity string>
scope: single-use
reason: <optional free text>
```

Verification rules:

- The path must be supplied explicitly, resolve to a regular file, and remain contained in the approvals directory after symlink resolution.
- YAML must parse and match the strict schema; unknown keys are refused.
- `kind`, `schema_version`, `operation`, and `instance` must match the requested operation.
- `issued_at <= now < expires_at`; TTL must be at most 24 hours.
- `approver` must be non-empty.
- `scope` must be `single-use`.
- A consumption marker `<id>.consumed` beside the receipt makes a receipt non-reusable.

## Receipt and artifact locations

- Package validation receipts remain owned by `hermes_a2a.config` and are written only by explicit CLI receipt-writing paths.
- Plugin approval receipts live under `$HERMES_HOME/state/hermes-a2a-plugin/approvals/`.
- Approval consumption markers are written only after every gate validates and immediately before a gated delegate call.
- Model tools do not read receipt contents and do not write receipts.

## Rollback and uninstall

Before enablement or merge, rollback is deleting the feature branch. After merge, rollback is reverting the additive plugin wrapper changes.

If an operator later installs the directory shim, uninstall by removing the copied/symlinked `hermes-a2a` plugin directory from the Hermes plugin directory. If approval receipts were created, the optional cleanup surface is `$HERMES_HOME/state/hermes-a2a-plugin/`. No systemd units, Hermes profiles, core config files, or services are changed by plugin registration.

## Standing non-authorizations

This plugin-wrapper work does not authorize public release, public PR, push, merge, deployment, package publication, public Agent Card publication, plugin enablement, service install/restart/stop execution, live profile/service/LAN mutation, credential access, work-data access, raw-tool/MCP proxying, public/wildcard/tunnel listeners, or `agent:work:hermes-work` live execution.

## Interpreting refusal messages

- `missing_live_enabled`: rerun only if the operation is intentionally live and authorized.
- `missing_yes`: explicit operator confirmation was absent.
- `missing_approval_receipt`: no approval receipt path was supplied.
- `approval_receipt_*`: the supplied receipt failed the named schema, containment, time, operation, instance, approver, or single-use rule.
- `missing_env_gate`: the operation-specific environment gate is not set.
- `unexpected_argument`: a model tool received an unrecognized or execution-control argument and did no further work.
- `projection_refused`: output contained material that must not be peer/model visible; raw content was not returned.

## Verification status

Slice 0 is complete. Later slices must attach command receipts proving registration safety, tool factory safety, gate refusals, read-only behavior, packaging, and isolated disabled-plugin discovery.
