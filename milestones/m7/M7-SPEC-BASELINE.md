# M7 upstream source pin and conformance baseline

Generated: `2026-06-30T18:30:20Z`

## Pinned upstream

- Repository: `https://github.com/a2aproject/A2A.git`
- Tag: `v1.0.0`
- Commit: `173695755607e884aa9acf8ce4feed90e32727a1`
- Versioned spec: `https://a2a-protocol.org/v1.0.0/specification/`
- License: Apache-2.0 (`spec/upstream/LICENSE`)

## Normative classification

The published v1.0.0 specification Section 1.4 states that `spec/a2a.proto` is the single authoritative normative definition of all protocol data objects and request/response messages. The tagged repo stores this file as `specification/a2a.proto`; it is vendored locally as `spec/upstream/a2a.proto`. The prose spec is normative for binding behavior, security guidance, discovery, error mapping, and lifecycle requirements.

## Implementation decision

- Language: Python.
- Package manager: `uv`.
- Official SDK candidate: `a2a-sdk==1.0.0` from PyPI, Apache-classified, repository `https://github.com/a2aproject/a2a-python`.
- Role: use the pinned SDK for generated proto/types, client transports, Starlette server routes, request handlers, task stores, and gRPC stubs; implement Hermes/IAP safety wrappers locally in `hermes_a2a`.
- Fallback: generate protobuf/gRPC code directly from `spec/upstream/a2a.proto` if the SDK cannot satisfy a conformance row.

## Binding classification

`operation-binding-table.json` classifies 11 required service operations across JSON-RPC, gRPC, and REST. gRPC is present in the v1.0.0 specification and must be implemented for the local "full" claim.

Known note: `SubscribeToTask` has a REST prose/proto inconsistency. The proto HTTP annotation uses `GET /tasks/{id=*}:subscribe`; Section 5.3/11.3 text says `POST /tasks/{id}:subscribe`. The pinned SDK accepts both; local implementation should treat proto/GET as canonical and keep POST as compatibility.

## Generated artifacts

- `spec/upstream/SOURCE.json`
- `spec/upstream/source-bundle-manifest.json`
- `milestones/m7/conformance-matrix.json`
- `milestones/m7/operation-binding-table.json`
- `milestones/m7/gap-ledger.json`
- `milestones/m7/m0-m6-evidence-manifest.json`
- `milestones/m7/LOCAL-SAFETY-SUBSTRATE.md`

## Non-actions

No public PR/release/deploy, LAN/public listener, live profile/plugin/MCP/service mutation, or IAP repo mutation occurred.
