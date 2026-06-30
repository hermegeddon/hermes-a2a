# Hermes Stuff submodule receipt

`hermes-a2a` is classified as a **project**, not a Hermes plugin:

- it has no `plugin.yaml`;
- it has no dashboard plugin manifest or Hermes plugin registration surface;
- it is an installable Python package/library plus local conformance/pilot scripts;
- it wraps the pinned upstream A2A v1.0.0 SDK with Hermes/IAP-lite safety behavior.

## Workspace / repository split

The active Hermes Project / management workspace remains:

```text
/home/openclaw/workspace/hermes-a2a
```

That workspace is for project-level coordination: plans, reviews, Kanban/meta-management artifacts, research/design notes, status refreshes, and cross-repo receipts.

The durable Git-backed implementation artifact lives under Hermes Stuff:

```text
/home/openclaw/dev/hermes-stuff/projects/hermes-a2a
```

That path is a local-path git submodule pointing at the standalone local repository:

```text
/home/openclaw/dev/hermes-a2a
```

## Snapshot source and included scope

The first code artifact snapshot was prepared from the management workspace:

```text
/home/openclaw/workspace/hermes-a2a
```

Included in the durable code artifact:

- code: `src/`, `tests/`, `scripts/`;
- package metadata: `pyproject.toml`, `uv.lock`;
- code/project docs: `README.md`, `PLAN.md`, `docs/`;
- provenance/evidence: `spec/`, `milestones/m7`, `milestones/m16`, `milestones/m17a`, `milestones/m18`, `milestones/final`.

Excluded from the durable code repo:

- local virtual environments and caches;
- prior multi-model review raw outputs;
- old M0–M6 exploratory artifacts and Kanban scratch artifacts;
- special files such as historical FIFO receipts.

Historical implementation files may still exist in the management workspace. Treat those as project history unless deliberately refreshed from this repo. Future implementation edits should happen in the Git-backed code repo/submodule, while `/home/openclaw/workspace/hermes-a2a` remains the Hermes Project management layer.

No public PR, public release, remote push, package publication, deployment, LAN exposure, live profile/service/MCP mutation, or IAP repository mutation is implied by this local submodule move.
