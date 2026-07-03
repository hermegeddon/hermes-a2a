# hermes-a2a plugin wrapper implementation evidence

Governing plan: `/home/openclaw/workspace/hermes-a2a/.hermes/plans/2026-07-03_1218-hermes-a2a-plugin-wrapper-plan.md`

Verified plan SHA-256: `8edd084d6f4fc363f49ab89b99be5ea4541f4fb25c2f26612dc7c06d90af54da`.

Implementation branch: `feat/hermes-plugin-wrapper`.

## Slice 0

- Branch created from clean `main` at `6c58dde`.
- Baseline command: `uv run --extra dev python -m pytest tests -q`
- Baseline result: `38 passed in 3.19s`.
- Slice 0 gate matrix recorded in `docs/plugin.md` and committed as `66c9b10 Record hermes-a2a plugin Slice 0 gates` before plugin implementation code.

## Red state

After creating `tests/plugin/`, the plugin suite failed because implementation files were intentionally absent:

```text
uv run --extra dev python -m pytest tests/plugin -q
34 failed, 9 errors
primary failure class: ModuleNotFoundError: No module named 'hermes_a2a_plugin'
```

This established the plugin-wrapper tests before the implementation package existed.

## Focused safety evidence

All commands ran in `/home/openclaw/dev/hermes-stuff/projects/hermes-a2a`.

| Command | Result |
|---|---|
| `uv run --extra dev python -m pytest tests/plugin/test_register_side_effect_free.py -q -v` | `3 passed in 0.02s` |
| `uv run --extra dev python -m pytest tests/plugin/test_register_api_allowlist.py -q -v` | `1 passed in 0.01s` |
| `uv run --extra dev python -m pytest tests/plugin/test_tool_factory.py -q -v` | `5 passed in 0.02s` |
| `uv run --extra dev python -m pytest tests/plugin/test_gates.py -q -v` | `18 passed in 0.07s` |
| `uv run --extra dev python -m pytest tests/plugin/test_live_delegation_seam.py -q -v` | `9 passed in 0.06s` |
| `uv run --extra dev python -m pytest tests/plugin/test_tool_schemas.py -q -v` | `1 passed in 0.01s` |
| `uv run --extra dev python -m pytest tests/plugin/test_status_tool.py tests/plugin/test_validate_config_tool.py tests/plugin/test_peer_task_dry_run.py -q -v` | `8 passed in 0.06s` |

Coverage highlights:

- `register(ctx)` creates no `$HERMES_HOME` state and registers only tools, one CLI command, and the bundled skill.
- Register degrades when CLI/skill registration methods are absent.
- Register does not import `hermes_a2a`.
- Context spy proves no hook, slash command, `dispatch_tool`, auxiliary task, LLM access, or `override=True` registration.
- Every model tool schema has `additionalProperties: false` and every model tool is factory-wrapped.
- Unknown/denylisted tool args are rejected before `hermes_a2a` import or file open.
- Projection findings redact unsafe fields; scanner failure returns `projection_unavailable` without raw output.
- Approval receipt tests cover missing file, non-regular path, containment, YAML, unknown keys, wrong kind/version/operation/instance, time validity, TTL, canonical lowercase UUID4 id validation, marker escape prevention, approver, single-use consumption, missing flags/env, and execution-control args.
- Valid live/service/task-smoke gate paths reach only top-level mocked delegates under global process/network/exec/systemctl guards.
- Service unit selection excludes `hermes-a2a-work-hermes-work.service`; unsupported work-labeled service instances are refused before gate consumption.
- Task-smoke delegates to the existing `run_m17c_live_executor_pilot` top-level seam rather than a dry-run placeholder.

## Pre-review hardening during final handoff

Before final independent review, the staged diff was reconciled with the safety constraints after local inspection found three issues to harden before commit:

1. Approval receipt ids needed normalized UUID4/path-safe validation before consumption marker construction.
2. Service restart/stop needed to exclude `hermes-a2a-work-hermes-work.service` from the plugin wrapper path.
3. `task-smoke` needed a real top-level delegate seam for the approved local live-smoke instance rather than a dry-run placeholder after gates were consumed.

Fixes applied before final review/commit:

- `src/hermes_a2a_plugin/gates.py` now requires normalized UUID4 ids and rechecks the consumption marker path remains inside approvals.
- `src/hermes_a2a_plugin/cli.py` now binds service operations to `local-services` / explicit local instances and excludes the work-labeled unit.
- `task-smoke` now supports only `agent:local:hermes-blinky-wsl` and delegates to `run_m17c_live_executor_pilot` after gates.
- Tests were expanded to cover malicious receipt ids, marker escape prevention, unsupported service/task-smoke instance refusals, work-unit exclusion, and task-smoke top-level delegation.

Final independent review via `profile_delegate` run `pd_20260703_141210_27u37o` returned `status: ok` with no remaining blockers. It verified the staged diff artifact SHA `f69c257418426382ed7bbdf47dcb577346954fc07bc78b3d232fc16aa5d20abf`, the canonical lowercase UUID4 refusal probe, traversal-id refusal/no marker escape, local service-unit allowlist excluding work, task-smoke delegation to `run_m17c_live_executor_pilot`, docs non-authorizations, staged secret-pattern scan, `git diff --staged --check`, and focused/full test results.

## Full-suite evidence

| Command | Result |
|---|---|
| `uv run --extra dev python -m pytest tests/plugin -q` | `52 passed in 0.21s` |
| `uv run --extra dev python -m pytest tests -q` | `90 passed in 3.06s` |
| `uv run --extra dev python scripts/validate_local_conformance.py` | exit `0`, status `passed`; expected negative logs for non-loopback push URL and missing extended-card auth appeared. |

`validate_local_conformance.py` regenerated tracked M16 timestamp/ephemeral-port receipts; those generated diffs were inspected and reverted because they were outside this plugin-wrapper scope. The command output above is retained as evidence.

## Packaging evidence

Command:

```bash
rm -rf dist build /tmp/a2a-wheel-check && \
uv run --with build python -m build && \
python -m pip install --force-reinstall dist/*.whl -t /tmp/a2a-wheel-check && \
PYTHONPATH=/tmp/a2a-wheel-check python - <<'PY'
import importlib.metadata as md
import hermes_a2a_plugin
print({'module': hermes_a2a_plugin.__name__, 'entry_points': [(ep.name, ep.value) for ep in md.entry_points().select(group='hermes_agent.plugins') if ep.name == 'hermes-a2a']})
PY
```

Result:

```text
Successfully built hermes_a2a-0.1.0.tar.gz and hermes_a2a-0.1.0-py3-none-any.whl
Successfully installed ... hermes-a2a-0.1.0
{'module': 'hermes_a2a_plugin', 'entry_points': [('hermes-a2a', 'hermes_a2a_plugin')]}
```

Ignored `dist/` output was removed after the smoke so it is not part of the repository handoff.

## Isolated disabled-plugin smoke

A temporary `HERMES_HOME` was created, `plugin/` was copied to `$TMP/hermes-home/plugins/hermes-a2a`, then this read-only command was run:

```bash
HERMES_HOME=$TMP/hermes-home hermes plugins list --json
```

Result excerpt:

```json
{
  "name": "hermes-a2a",
  "status": "not enabled",
  "version": "0.1.0",
  "description": "Local-first A2A v1.0.0 plugin wrapper with Hermes safety gates and no default live exposure.",
  "source": "user"
}
```

The first smoke incorrectly asserted an `enabled: false` JSON field and exited `1`; the actual Hermes CLI shape is `status: "not enabled"`. The corrected smoke exited `0` and verified `listed_disabled: true`.

The listing command created normal Hermes scaffolding only inside the temporary home (`SOUL.md`, logs/cache/session/skills directories). The live default Hermes profile was not touched.

## Non-actions

No push, public PR, merge, release, package publication, plugin enablement, service install/restart/stop execution, live profile execution, LAN/public listener exposure, credential access, work-data access, raw MCP/tool proxying, or real `~/.hermes/plugins` symlink smoke occurred.
