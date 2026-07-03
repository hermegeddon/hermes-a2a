# Hermes Stuff project/submodule receipt

`hermes-a2a` is classified primarily as a **project** under Hermes Stuff:

- it is an installable Python package/library plus local conformance and pilot scripts;
- it wraps the pinned upstream A2A v1.0.0 SDK with Hermes/IAP-lite safety behavior;
- it now also contains a disabled-by-default Hermes Agent plugin wrapper under `plugin/` and `src/hermes_a2a_plugin/` for operator convenience.

The plugin wrapper does not change the repository classification: implementation work still belongs in this project repo/submodule, while plugin enablement, service mutation, LAN exposure, public release, and package publication remain separately gated.

## Workspace / repository split

The active Hermes Project / management workspace remains:

```text
<management-root>
```

That workspace is for project-level coordination: plans, reviews, Kanban/meta-management artifacts, research/design notes, status refreshes, and cross-repo receipts.

The durable Git-backed implementation artifact lives under Hermes Stuff:

```text
<repo-root>
```

That path is backed by the standalone local repository:

```text
<standalone-repo>
```

## Snapshot source and included scope

The first code artifact snapshot was prepared from the management workspace:

```text
<management-root>
```

Included in the durable code artifact:

- code: `src/`, `tests/`, `scripts/`;
- package metadata: `pyproject.toml`, `uv.lock`;
- code/project docs: `README.md`, `PLAN.md`, `docs/`;
- plugin wrapper shim and metadata: `plugin/`;
- provenance/evidence: `spec/`, `milestones/m7`, `milestones/m16`, `milestones/m17a`, `milestones/m18`, `milestones/final`.

Excluded from the durable code repo:

- local virtual environments and caches;
- prior multi-model review raw outputs;
- old M0–M6 exploratory artifacts and Kanban scratch artifacts;
- special files such as historical FIFO receipts.

Future implementation edits should happen in the Git-backed code repo/submodule, while `<management-root>` remains the Hermes Project management layer.

No public PR, public release, package publication, deployment, LAN exposure, live profile/service/MCP mutation, or IAP repository mutation is implied by this local submodule move or by the disabled plugin wrapper.
