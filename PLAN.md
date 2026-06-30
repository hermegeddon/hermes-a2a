# hermes-a2a Plan — upstream A2A implementation roadmap

Updated: `2026-06-30T17:13:15Z`
Workspace: `/home/openclaw/workspace/hermes-a2a`
Review baseline: `reviews/20260630T165925Z-plan-a2a-v1-multi-model-review`
Current status baseline: M0–M6 local pilot artifacts are complete, but the implementation is **not yet canonical upstream A2A-compatible**.

## Purpose

`hermes-a2a` is now the implementation workspace for turning the completed local A2A-shaped Hermes pilot into a **full, spec-tracked implementation of the upstream Agent2Agent (A2A) protocol**, while preserving the IAP-lite safety boundaries already proven for the M1–M6 local/fixture surfaces.

The target is:

> Implement the pinned upstream A2A release semantics, expose interoperable A2A client/server bindings, and keep Hermes/IAP policy, redaction, receipt, work/personal, and MCP boundaries as a local safety layer rather than as a forked protocol.

Candidate upstream version at plan time: `v1.0.0`. M7 must verify the exact pinned version and derive all version labels from the pinned source bundle before any M8+ implementation work begins.

This plan supersedes the earlier local-only pilot roadmap as the governing `PLAN.md`. The earlier M0–M6 artifacts remain evidence and regression fixtures; they do **not** constitute upstream A2A wire conformance.

## Multi-model review reconciliation

This plan incorporates accepted findings from the requested four-route review:

| Route | Requested provider/model | Normalized verdict |
| --- | --- | --- |
| Hermes | `openai-codex` / `gpt-5.5` | `pass_with_changes` |
| Hermes | `minimax-oauth` / `MiniMax-M3` | `pass_with_changes` |
| Hermes | `ollama-cloud` / `glm-5.2` | `pass_with_changes` |
| Claude Code | `claude-opus-4-8` | `pass_with_changes` |

Accepted review deltas now embedded in this plan:

- M7 verifies the normative source bundle before proto-first or SDK-first implementation assumptions become binding.
- `latest` and `main` upstream URLs are informational only; implementation authority must come from pinned version/tag/commit artifacts.
- Method names, REST paths, gRPC status, push operations, and SDK/tooling choices are provisional until M7 extracts the pinned operation table.
- M7 gates license compatibility, provenance/signature availability, official SDK versions, implementation language, generated-artifact reproducibility, M0–M6 evidence re-indexing, and conformance-label enforcement.
- Later milestones now require client-side conformance, positive auth/security tests, task state-machine tests, idempotency semantics, policy-store integrity, receipt atomicity, network-bind evidence, binding-equivalence oracle, leak-scanner expansion, and MCP/tool-proxy reachability tests.
- The canonical loopback pilot and optional LAN pilot are split into separate milestones so LAN is never implied by same-machine success.

Raw outputs, normalized JSON, route smokes, and review prompt are preserved in the review baseline directory.

## Canonical upstream sources and source-of-truth policy

M7 must convert the candidate sources below into a pinned source bundle. Until M7 passes, this table is a planning input, not execution authority.

| Candidate source | Role before M7 | M7 required treatment |
| --- | --- | --- |
| `https://a2a-protocol.org/v1.0.0/specification/` | Candidate version-pinned prose specification. | Pin exact URL, retrieval timestamp, content hash where practical, cited sections, and relationship to repo tag/commit. |
| Upstream repository tag/commit containing `spec/a2a.proto` | Candidate normative data model / request-response source if confirmed. | Verify whether the pinned release treats proto as normative, derived, or one of several authoritative artifacts. Record SHA-256, commit/tag, license, and provenance. |
| Upstream JSON schemas / OpenAPI / binding docs, if present | Candidate binding/schema authority. | Identify whether required, optional, generated, or non-normative; include hashes and generation source if used. |
| Official A2A SDKs / examples, if present | Candidate interop and conformance partners. | Pin SDK package names, versions, source commits, supported languages, and compatibility with the pinned spec. |
| `https://a2a-protocol.org/latest/specification/` and `https://github.com/a2aproject/A2A/blob/main/docs/specification.md` | Informational references only. | Do not use mutable `latest` or `main` as implementation authority except to discover the pinned release to fetch. |
| Existing `milestones/m0`–`milestones/m6` | Local safety, projection, approval, receipt, and pilot evidence. | Re-index paths/hashes in M7 and classify each artifact as regression evidence or historical context. |

Protocol rule: generated SDKs, JSON schemas, protobuf artifacts, OpenAPI artifacts, and binding code must be regenerated from the pinned source bundle or official SDK sources. They must not become hand-edited local authorities. If M7 finds that the plan's candidate upstream assumptions are wrong or ambiguous, M7 must stop before implementation and produce a revised plan patch.

## Current state snapshot

Completed local evidence:

- M0 — workspace/decision record: PASS.
- M1 — private model, envelope, safety fixtures: PASS.
- M2 — A2A-shaped local adapter proof: PASS for fixture/private-file-mailbox semantics only.
- M3 — IAP-lite policy and exact-scope approval proof: PASS.
- M4 — local read-only Hermes/MCP-style introspection proof: PASS.
- M5 — expanded safe projection envelope: PASS.
- M6 — same-machine controlled local live pilot: PASS for narrow fixture/private-file-mailbox scope.
- Final closeout: `milestones/final/PLAN-CLOSEOUT.md` records the local plan as complete through M6.

Known gaps versus upstream A2A:

- No pinned upstream source bundle is vendored or verified in this workspace.
- No canonical generated or SDK-derived A2A model layer exists.
- No upstream-conformant `AgentCard`, `Message`, `Part`, `Artifact`, `Task`, or request/response objects are implemented as the primary protocol surface.
- No JSON-RPC A2A server/client binding exists.
- No HTTP+JSON/REST binding exists.
- No gRPC binding exists; M7 must determine whether this is required, optional, or out-of-scope for the pinned spec.
- No SSE streaming, task subscription, or push-notification config implementation exists.
- No upstream SDK/proto/schema conformance suite exists.
- No LAN or public A2A endpoint has been proven or authorized by the existing M6 result.

Conformance label rules:

- Existing local code remains `a2a-shaped` / `a2a-adapter`.
- Do not call anything `a2a-native`, `upstream-compatible`, or `a2a-<version>` until it passes the relevant conformance milestone below.
- Version labels must be generated from the M7 pinned source bundle, not hardcoded. Examples after M7 may look like `a2a-v1-jsonrpc-loopback`, `a2a-v1-rest-loopback`, `a2a-v1-grpc-loopback`, or `a2a-v1-full-local`, but only if M7 confirms those labels match the pinned release.
- M7 must add an enforcement gate: grep/lint documentation and source for forbidden premature labels and cross-check any allowed label against a conformance-matrix row marked `passed`.

## Boundary rule

A2A crosses the peer-agent boundary. MCP normally stays behind the owning Hermes runtime boundary.

Peer agents should request outcomes through canonical A2A tasks and messages. The owning Hermes instance decides which local tools, MCP servers, files, APIs, models, or native runtime surfaces to use. Peers receive A2A-conformant task status, messages, artifacts, and safe metadata, not raw private tool control.

IAP-lite is a policy/safety layer around A2A. It must not silently fork the protocol:

- A2A objects and methods must remain upstream-conformant.
- IAP-lite data belongs only in M7-confirmed extension fields, local policy stores, transport/auth context, or safe metadata fields allowed by the pinned spec.
- Private roster, policy, hidden prompts, memory, raw config, raw tool traces, private MCP details, broad local paths, credentials, and work-protected data must never be exposed through A2A responses.
- M7 must identify the exact extension placement mechanism; M8+ must reject IAP-lite data placed outside that mechanism.

## Non-authorizations preserved by this plan

This plan authorizes planning and future local implementation work only when separately executed through a bounded task/workstream. It does **not** by itself authorize:

- public PRs, public releases, package publication, deployments, public registry publication, or public Agent Card publication;
- wildcard, public, or tunnel listeners;
- LAN exposure before the explicit LAN gate milestone;
- external messages/writes beyond controlled protocol tests explicitly scoped later;
- raw MCP publication, raw all-tools proxying, or arbitrary shell proxying;
- protected work data, work credentials, work-paid compute, Windows ACL mutation, or work-protected artifacts;
- mutation of `/home/openclaw/dev/hermes-agent-interop-profile`, Hermes Stuff submodules, remotes, or unrelated repositories;
- live profile/plugin/skill/MCP enablement, installation, configuration mutation, or restart without a separately approved exact-scope task.

## Implementation architecture

Preferred future implementation layout, unless M7/M8 establish a different package scaffold from the pinned SDK/tooling decision:

```text
/home/openclaw/workspace/hermes-a2a/
  PLAN.md
  spec/
    upstream/
      SOURCE.json                    # pinned release/tag/commit/license/provenance
      source-bundle-manifest.json    # hashes of every pinned source artifact
      a2a.proto                      # only if confirmed present/relevant in pinned source
      ... pinned schemas/docs/examples as required by M7 ...
    generated/
      ... generated artifacts only; reproducible from pinned commands ...
  src/hermes_a2a/
    canonical/        # generated or thin typed wrappers around pinned source/SDK model
    agent_card/       # public-safe card generation and discovery helpers
    task_engine/      # durable task store, lifecycle, cancellation, history
    bindings/
      jsonrpc/        # JSON-RPC over HTTP binding, if required by pinned spec
      rest/           # HTTP+JSON/REST binding, if required by pinned spec
      grpc/           # gRPC binding only if M7 classifies it required/optional
      sse/            # streaming/subscription support where required
      push/           # push notification config + webhook delivery harness where required
    hermes_bridge/    # Hermes runtime adapter, execution sandbox, profile/task bridge
    iap_lite/         # policy, roster, exact-scope approval, receipt integration
    projection/       # M5-derived peer-visible projection gates, extended for A2A fields
    receipts/         # private receipt schemas/writers and safe receipt references
  tests/
    conformance/
    integration/
    security/
    fixtures/
  milestones/
    m7/ ...
    m8/ ...
    ...
```

Typing rule: prefer precise typed models and bounded JSON-value metadata wrappers. Avoid loose `dict[str, Any]` / `map[string]any` surfaces except where the upstream protocol explicitly defines extension metadata; even then, wrap and validate extension namespaces and value shapes.

## Local safety substrate reference requirement

Before M10 can claim it preserves M1–M6 safety behavior, M7 or M8 must publish a `milestones/<current>/LOCAL-SAFETY-SUBSTRATE.md` reference that names:

| Safety concept | Historical source | Future structural contract required |
| --- | --- | --- |
| IAP-lite roster/attestation | M1/M3 artifacts | Versioned model/schema and policy evaluation entry point. |
| Exact-scope approval | M3 artifacts | Typed approval object, evaluator function/API, denial/error mapping. |
| Safe projection/leak scanner | M5 artifacts | Single egress projection API, scanner contract, canonical A2A field coverage. |
| Receipt-before-exposure | M2–M6 receipts | Atomic writer/outbox contract and failure-mode semantics. |
| Kill switch / default-deny | M1–M6 tests | Pre-execution policy gate API and negative fixture matrix. |
| MCP/tool non-exposure | M4/M5 artifacts | Reachability scan and allowlist boundaries for all bindings. |

Historical artifacts are not enough. Each future implementation must call the structural contract and verify it with tests.

## Milestone roadmap

### M7 — Upstream source pin and conformance baseline

Goal: establish the pinned A2A release source bundle before writing protocol code.

Work:

- Discover the exact upstream release to target, starting from candidate `v1.0.0`, and record the pinned version in `spec/upstream/SOURCE.json`.
- Fetch or vendor every required source artifact for the pinned release: prose specification, proto if present/relevant, JSON schemas/OpenAPI if present, binding docs, license files, examples, and SDK source/package metadata if used.
- Record source URL, release/tag/commit, retrieval timestamp, SHA-256, license, and provenance/signature/SLSA/cosign status for every pinned artifact.
- If upstream signatures or attestations exist, verify them; if none exist, record that absence as a risk and perform a second-source cross-check such as release archive versus tag checkout.
- Verify the normative role of each source artifact: required, optional, deprecated, extension, generated/non-normative, or informational.
- Decide and record implementation language, official SDK(s) and versions, codegen path, fallback generated-client strategy, and package manager/lockfile approach.
- Verify license compatibility for local vendoring and code generation. If license terms are unclear or restrictive, stop before M8.
- Generate `milestones/m7/conformance-matrix.json` from the pinned source bundle. Required row fields: `id`, `source_artifact`, `source_section`, `requirement_text`, `object_or_operation`, `binding`, `status`, `requiredness`, `owner_milestone`, `evidence_path`, `notes`.
- Generate `milestones/m7/operation-binding-table.json` with exact method names, endpoint paths, request/response types, error shapes, required/optional/deprecated status, and citations.
- Generate `milestones/m7/gap-ledger.json` comparing current M1–M6 behavior to pinned upstream requirements. Required row fields: `id`, `spec_row`, `current_state`, `blocker_milestone`, `status`, `closure_evidence`.
- Re-index M0–M6 artifacts with current paths, hashes, and classification as regression evidence or historical context.
- Add conformance-label lint/grep enforcement and matrix cross-check design.

Acceptance:

- `spec/upstream/SOURCE.json` and `source-bundle-manifest.json` exist and validate.
- The pinned release version is recorded; all future `a2a-<version>` labels derive from that value.
- The source bundle classifies proto/schema/prose/SDK/binding docs by normative role; no later milestone depends on an unclassified artifact.
- License compatibility for vendoring/codegen is explicitly PASS or M7 blocks.
- `conformance-matrix.json`, `operation-binding-table.json`, and `gap-ledger.json` exist and validate against their schemas.
- M7 establishes the implementation language and SDK/codegen strategy or blocks with a concrete decision needed.
- M7 states whether gRPC is required, optional, non-normative extension, or absent for the pinned spec.
- No M8+ protocol code, endpoint, model, or binding work may begin until every required/optional/deprecated/not-applicable row needed for M8 is classified.
- No service/profile/plugin/MCP enablement, listener exposure, public publication, or external mutation occurred.

### M8 — Canonical data model and serialization layer

Goal: make upstream A2A objects the primary protocol model rather than custom local envelopes.

Work:

- Generate or implement typed canonical models using the M7-approved source/SDK path for all required pinned objects, including Agent Card, Extended Agent Card if present, Message, Part variants, Artifact, Task, task status/state objects, request/response/error objects, metadata/extension maps, and push notification config objects if present.
- Implement JSON/proto/schema round-trip tests only for encodings classified as required or relevant by M7.
- Implement strict validation for `Part` oneof semantics: exactly one content variant per part, with required media/type fields and invalid-combination negatives.
- Implement property-based/fuzz tests seeded from upstream golden fixtures for required fields, enum coverage, oneof constraints, metadata bounds, unknown extensions, and malformed payloads.
- Implement deterministic codegen/regeneration verification: pinned generator versions, exact commands, lockfiles, clean-temp regeneration diff, generated-file manifest, and no hand-edited generated source.
- Implement typed, namespace-scoped Hermes/IAP extension models using the exact placement mechanism selected by M7.
- Extend the M5-derived projection/leak scanner to cover every canonical A2A field that can become peer-visible: part bytes/raw file fields, file references, artifact fields, metadata maps, extension namespaces, error data, stream frames, and push payloads.

Acceptance:

- Canonical objects round-trip through every M7-required encoding according to the pinned source bundle.
- Golden fixtures include text, file reference, raw bytes/file content where allowed, structured data parts, metadata/extension cases, and error objects.
- Invalid objects fail closed with canonical protocol errors and safe local logs.
- IAP-lite extensions are typed, namespace-scoped, and validated; placement outside the M7-approved mechanism is rejected.
- Projection/leak tests include positive leak-injection cases for every new canonical peer-visible field.
- Generated artifacts are reproducible from a clean/temp copy with no unexpected diff.
- M1–M6 local fixtures are either mapped into canonical A2A objects or explicitly kept as legacy regression fixtures.

### M9 — Canonical Agent Card, discovery, and security declaration surface

Goal: expose upstream-conformant Agent Cards without leaking private Hermes/IAP/MCP details.

Work:

- Implement public-safe Agent Card generation from local profile/capability policy according to the M7-pinned schema/model.
- Implement Extended Agent Card handling if required by the pinned spec, with authenticated access and safe denial.
- Declare supported pinned protocol version(s), bindings, capabilities, modalities, skills, extensions, and security requirements from M7 operation/binding tables.
- Implement the A2A security-scheme declaration model required by the pinned spec: API key, HTTP auth, OAuth2, OpenID Connect, or only the subset M7 classifies as applicable.
- Exercise both negative and positive auth tests: missing/invalid credentials deny safely; valid credentials for each declared scheme are accepted.
- Keep private roster/attestation records separate from the public Agent Card.
- Verify exact discovery endpoint/path semantics from the pinned spec before exposing any endpoint.
- Publish the projection scanner surface contract for Agent Cards: versioned deny-list/patterns for private MCP names/URLs, profile paths, hidden prompts, memory, raw config, environment variables, credential-backed account details, broad filesystem roots, and work-protected data.

Acceptance:

- Agent Card fixtures validate against the pinned upstream model.
- Public cards contain no private MCP names/URLs, profile paths, hidden prompts, memory, raw config, environment variables, credential-backed account details, broad filesystem roots, or work-protected data.
- Extended Agent Card access succeeds for authorized callers and denies safely for unauthorized callers without leaking card contents.
- Agent Card security schemes are both declared and functionally exercised.
- Agent Card output has projection hashes and private receipt references where appropriate.

### M10 — Canonical task engine, safety substrate, and Hermes execution boundary

Goal: implement a durable local task engine that can back all A2A bindings.

Work:

- Implement a canonical task store with server-generated task IDs, context IDs, status history, artifacts, messages, cancellation status, timestamps, terminal-state immutability, and durable receipt links.
- Map Hermes execution requests to A2A `Message`/`Task` semantics without exposing Hermes internals.
- Preserve M3 exact-scope approval and kill-switch behavior through the structural safety substrate contracts, not by prose reference alone.
- Define the pinned-spec task state machine, legal transitions, terminal states, input/auth-required states, and canonical errors for illegal transitions.
- Define the idempotency/replay contract: key presence requirements if any, scope, retention window, replay behavior, canonical error or original-response behavior, and relationship to server-generated task IDs.
- Implement receipt-before-exposure atomically, using an outbox/transactional pattern or equivalent proof for status, messages, artifacts, errors, stream events, and push payloads.
- Implement policy-store integrity checks: read-only load/readiness, tamper detection where practical, malformed/stale policy safe-deny, and audited in-process mutation attempts.
- Implement concurrency/durability tests for simultaneous send/get/cancel/subscribe, cancel-vs-complete races, terminal immutability, crash between receipt write and exposure, and restart behavior if durability is claimed.
- Support direct `Message` responses for interactions that do not require task tracking, only if allowed by the pinned spec and local policy.

Acceptance:

- Task IDs are server-generated for new tasks unless the pinned spec explicitly permits another flow.
- Requester-provided idempotency/correlation metadata is validated as metadata/policy input, not confused with canonical server-generated task IDs.
- A state-machine conformance test verifies every legal pinned transition and rejects illegal transitions with canonical errors.
- M2/M3 cancellation fixtures are preserved as regression tests against the canonical task engine.
- Receipt atomicity tests prove no peer-visible output can be emitted when receipt writing or projection fails mid-flight.
- Policy-store tamper/unreadiness tests safe-deny before execution or exposure.
- No raw Hermes tool/MCP/shell control is exposed to peers.

### M11 — JSON-RPC over HTTP binding: core non-streaming operations and client

Goal: implement the primary interoperable A2A JSON-RPC binding first, locally and loopback-only, if M7 classifies JSON-RPC as required for the pinned spec.

Work:

- Implement A2A server endpoint(s) for the exact pinned JSON-RPC method identifiers and request/response envelopes from M7's operation-binding table.
- Implement an A2A JSON-RPC client that can discover/parse remote Agent Cards, validate remote security declarations, send requests, process remote errors, and retrieve remote task state.
- Support all M7-required non-streaming core operations. Examples may include message send, task get, task cancel, Agent Card/Extended Agent Card retrieval, or task listing only if the pinned spec includes them.
- Implement canonical JSON-RPC error handling and safe local error projection.
- Add request size, content-type, method, version, auth/security, idempotency, and policy checks.
- Keep the first binding loopback-only or Unix-socket-only until later gates pass.
- Add transport-bind proof covering IPv4 loopback, IPv6 loopback, no `0.0.0.0`, no `::`, no LAN interface, no public tunnel, and Unix-socket permission checks if applicable.
- Add a binding-equivalence oracle stub before REST/gRPC work: canonical task state transition, canonical object identity, canonical error category, receipt/projection result, and allowed binding-specific encoding differences.

Acceptance:

- M7-pinned official SDK/example clients, or generated clients from the pinned source bundle, can call the local JSON-RPC endpoint for required core operations.
- The local JSON-RPC client can call a pinned official/example server if available; otherwise the absence is recorded with a generated-server fallback.
- Negative tests cover unknown method, malformed JSON-RPC, wrong content type, missing/invalid auth, invalid Agent Card, invalid message parts, unknown task, non-local transport, replay/idempotency misuse, policy denial, projection failure, receipt-write failure, and version mismatch.
- Positive auth tests prove each declared security scheme accepts valid credentials.
- No wildcard/LAN/public listener is used in M11.
- `milestones/m11/JSONRPC-CONFORMANCE.md` records command output, network-bind evidence, and interop results.

### M12 — Streaming, task subscription, and SSE semantics

Goal: implement upstream streaming behavior without weakening projection/receipt gates.

Work:

- Implement the pinned streaming operation(s), such as streaming message send or task subscription, only as classified by M7.
- Implement SSE framing requirements separately from payload validation: content type, event/id/retry fields if required, reconnection tokens/cursors if required, terminal-state closure, and client disconnect behavior.
- Ensure each stream event is canonical, safe-projected, receipt-backed, ordered, and emitted through one projection egress point.
- Add tests proving the projection/leak scanner is invoked exactly once per peer-visible stream event: no skip, no double-application, no bypass.
- Define reconnection behavior, terminal state detection, stream closure, and cancellation interaction according to the pinned spec.
- Add backpressure, timeout, client disconnect, concurrent subscriber, and partial-artifact tests.

Acceptance:

- Streamed task status, message, and artifact update events validate against upstream models and SSE framing rules.
- Terminal states close streams according to pinned spec semantics.
- Disconnected clients can resubscribe where supported.
- Projection failure or receipt-write failure terminates safely without leaking private details.
- The extended M8 projection scanner covers every event payload before exposure.

### M13 — Push notification config operations and webhook harness

Goal: implement asynchronous task update configuration safely, if required or supported by the pinned spec.

Work:

- Implement push notification config operations required by M7's operation table, such as create/set, get, list, and delete.
- Build a local webhook harness for synthetic/loopback push delivery tests.
- Validate destination URL policy at runtime, not only at config time: loopback/private allowlist by default; external/public destinations denied unless separately approved by exact-scope gate.
- Validate auth tokens, replay protection, delivery receipts, retry/backoff, idempotency, cancellation behavior, and canonical error mapping.
- Deny public/external webhook destinations unless separately approved by an exact-scope gate.

Acceptance:

- Loopback push notification configs work with synthetic receivers.
- Public/external webhook URLs are denied by default with canonical errors and safe projected reasons.
- Delivery attempts have private receipts and safe peer-visible delivery status.
- Push payloads validate against canonical upstream objects and M8 projection gates.

### M14 — HTTP+JSON/REST binding

Goal: implement the REST binding after JSON-RPC semantics are stable, if M7 classifies REST as required or supported.

Work:

- Implement REST endpoints exactly as enumerated in M7's operation-binding table. Do not hardcode placeholder endpoint paths from pre-M7 assumptions.
- Implement REST client behavior for discovering remote Agent Cards, validating security declarations, sending requests, polling/subscribing where supported, handling errors, and processing artifacts.
- Share the same canonical model, task engine, policy gate, projection gate, receipt writer, and binding-equivalence oracle as JSON-RPC.
- Add REST-specific status code, header, content negotiation, auth, version, and error-shape tests.

Acceptance:

- REST requests/responses validate against the pinned A2A model and operation semantics.
- REST and JSON-RPC bindings produce equivalent canonical task state transitions for equivalent requests under the M11/M16 equivalence oracle.
- REST streaming and push behavior match the pinned spec where applicable.
- Loopback-only transport remains enforced until LAN gate approval.

### M15 — gRPC binding, if required or intentionally optional

Goal: implement the gRPC binding only if M7 classifies it as required or valuable optional interop for the pinned spec.

Work:

- If gRPC is required by the pinned spec, generate gRPC server/client stubs from the M7-approved source bundle and implement the required service methods.
- If gRPC is optional or non-normative, reclassify this milestone as an optional local extension outside the required conformance path; it must not block `a2a-<pinned-version>-full-local` unless M7 says it is required.
- Support streaming RPCs and push/config operations where the pinned source defines them.
- Add gRPC metadata/auth policy, deadlines, cancellation, status/error mapping, and interop tests.

Acceptance:

- If required, generated gRPC clients can call the local gRPC server over loopback.
- If optional/non-normative, the milestone states that clearly and cannot be used as evidence for required upstream conformance.
- gRPC, REST, and JSON-RPC bindings share canonical behavior and conformance fixtures where implemented.
- gRPC cancellation maps correctly into the canonical task engine and private receipt model.
- No hand-edited generated gRPC artifacts are treated as source of truth.

### M16 — Full conformance, interoperability, and enforcement suite

Goal: prove implementation status against upstream A2A, not only against local expectations.

Work:

- Build a machine-readable conformance suite that maps each pinned normative object, field, state, method, error, binding requirement, security requirement, and optional/deprecated item to tests/evidence.
- Add golden upstream fixtures and local Hermes/IAP extension fixtures.
- Add official SDK/example interop tests with exact pinned versions, or generated-client fallback tests when official SDKs are absent.
- Add cross-binding equivalence tests using the M11 oracle: canonical task transition, canonical object, canonical error category, receipt/projection result, and allowed binding-specific encodings.
- Add security/projection/leak tests for every peer-visible surface.
- Add protocol-version negotiation tests: unsupported newer/older versions produce canonical errors; supported versions are declared correctly.
- Add conformance-label enforcement: forbidden labels fail lint unless corresponding matrix rows are `passed`.
- Add MCP/tool-proxy reachability scans across all peer-visible A2A surfaces: no MCP server names, tool names, tool schemas, tool inputs, tool outputs, raw tool traces, shell proxies, or private MCP connection details.
- Add receipt-leakage self-scans before receipts are written or referenced externally.
- Add fuzz/property tests for malformed parts, invalid metadata, unknown extensions, content-type mismatches, and policy-denied requests.

Acceptance:

- `milestones/m16/CONFORMANCE-MATRIX-FINAL.json` has zero untriaged required rows.
- Every non-passing optional/not-applicable row has a written justification tied to pinned spec language.
- All required local tests pass from a clean/temp copy.
- Official SDK/example interop results are recorded with exact commands and versions, or absence/fallback is documented from M7.
- Security/projection scan finds no secrets, private memory, hidden prompts, broad paths, private MCP details, raw config, environment variables, credentials, raw tool traces, or work-protected data in peer-visible outputs.
- The implementation may be labeled `a2a-<pinned-version>-full-local` only if all mandatory rows pass or are explicitly documented as optional/not-applicable under the pinned spec.

### M17a — Controlled same-machine canonical A2A multi-Hermes pilot

Goal: replace the M6 private-file-mailbox pilot with a canonical A2A loopback pilot.

Entry criteria:

- M7–M16 required gates pass for the binding used.
- Local-only binding verified.
- Projection and receipt gates pass for every binding surface used.
- No protected work data, credentials, work-paid compute, public ingress, or raw MCP/tool/shell proxy is reachable.

Work:

- Run a same-machine Hermes A → Hermes B task using canonical A2A objects and one approved loopback binding.
- Run a synthetic/policy-only Hermes A → Hermes C work-boundary denial test.
- Preserve private receipts and safe projected peer-visible outputs.

Acceptance:

- The same task can be inspected as canonical A2A `Task`, `Message`, `Part`, and `Artifact` objects.
- Local policy gates deny non-authorized work/personal boundary requests before execution.
- A separate `M17A-SYNTHESIS.md` states exactly what was proven and explicitly states that LAN was not attempted unless M17b later passes.

### M17b — Optional tightly scoped LAN pilot

Goal: run a read-only LAN/local-network status/capability pilot only after a separate exact-scope human gate.

Entry criteria:

- M17a passes.
- Janusz approves exact named hosts/profiles, ports, bindings, credentials posture, task classes, data classes, and allowed duration.
- Public tunnel, wildcard listener, public Agent Card publication, work data, credentials, and raw tool/MCP proxy remain out of scope unless separately approved.

Work:

- Run a read-only LAN status/capability pilot between named hosts/profiles with synthetic data only.
- Record bind addresses, firewall/subnet assumptions, auth evidence, receipt/projection evidence, and denial tests for non-allowed hosts.

Acceptance:

- LAN, if approved, uses exact named hosts, explicit auth, no public tunnel, no wildcard listener, no work data, no credentials, and no raw tool/MCP proxy.
- `M17B-SYNTHESIS.md` states exact scope and non-claims.

### M18 — Documentation, IAP porting packet, and release-readiness gate

Goal: prepare durable docs and a review packet without public release by default.

Work:

- Write operator docs for local loopback A2A setup, Agent Card generation, safe bindings, and troubleshooting.
- Write developer docs for generated/source-bundle workflow and conformance testing.
- Update the local IAP porting proposal with canonical A2A decisions and extension schemas.
- Create a release-readiness checklist covering licensing, secrets, generated artifacts, SDK/source provenance, packaging, and public-surface risks.
- If publication is desired later, create a separate approval gate for PR/release/public Agent Card publication.

Acceptance:

- Docs are source-backed and match the tested implementation.
- IAP porting packet is local/non-mutating unless a separate exact-scope IAP worktree task is approved.
- No public PR/release/package/deploy/public Agent Card publication occurs from this plan alone.

## Cross-cutting protocol requirements

Every implementation milestone must preserve these requirements:

1. **Pinned-source first:** M7's pinned source bundle defines protocol semantics; local fixtures must adapt to the pinned source, not redefine it.
2. **No implementation before classification:** no M8+ protocol code, endpoint, model, or binding work may begin until M7 classifies the relevant source rows as required, optional, deprecated, extension, generated/non-normative, or not-applicable.
3. **Opaque execution:** peers never receive internal Hermes reasoning, hidden prompts, private memory, raw tool traces, raw MCP details, or broad local filesystem details.
4. **Receipt-before-exposure:** every peer-visible status, message, artifact, error, denial, stream event, push payload, and metadata surface requires a private receipt or explicit no-receipt-safe reason before exposure.
5. **Receipt atomicity:** tests must prove projection and receipt persistence cannot be bypassed by crashes, races, stream/push paths, or error paths.
6. **Safe projection:** the M8-extended projection checks run on every peer-visible output, including errors, stack traces, logs, receipt references, Agent Cards, stream events, push payloads, and all canonical A2A metadata/extension fields.
7. **Default-deny:** unknown requester, failed auth/attestation, stale timestamp where relevant, replayed nonce/idempotency key, missing classification, disabled kill switch, policy-store/readiness failure, receipt-write failure, projection failure, and non-local transport deny before execution or exposure.
8. **Canonical IDs:** server-generated A2A task/context identifiers must not be confused with local idempotency/correlation IDs.
9. **Task lifecycle integrity:** cancellation, terminal states, input/auth-required states, streaming closure, resubscription, and push delivery must match the pinned spec and preserve private audit state.
10. **No raw MCP/tool proxy:** MCP may support local owner-side introspection/management only through typed allowlisted surfaces, never as an inter-agent all-tools bridge; M16 must scan for reachability leaks.
11. **Typed extensions:** Hermes/IAP extensions must be versioned, namespace-scoped, and validated according to the M7-approved extension placement.
12. **Binding equivalence:** JSON-RPC, REST, and gRPC where implemented must share one canonical task engine and model layer; equivalence is judged by the M11/M16 oracle, not by prose assertion.
13. **Transport containment:** loopback/Unix-socket phases require bind-address evidence for IPv4, IPv6, wildcard negatives, tunnel absence, and socket permissions where applicable.
14. **Version-label enforcement:** labels such as `a2a-<pinned-version>-*` are generated from M7 and linted against conformance-matrix status.

## Verification expectations

Before treating any new milestone as complete:

- run focused tests for changed code/fixtures;
- run relevant source-bundle/codegen/SDK verification;
- run conformance matrix checks for the milestone's covered rows;
- run temp-copy validation for artifacts and manifests;
- run peer-visible leak scans over all produced A2A outputs;
- run network-bind checks for any server/listener;
- inspect generated private receipts and safe projections;
- verify no unapproved service/profile/plugin/skill/MCP enablement, restart, public listener, LAN/public exposure, IAP repo mutation, remote write, external message, or work-data/work-credential/work-compute access occurred;
- preserve exact commands, exits, hashes, versions, costs where relevant, and artifact paths in the milestone handoff.

## Human gates

Separate human approval is required before any of these actions:

- changing scope from loopback/same-machine to LAN;
- exposing any listener beyond loopback;
- publishing a public Agent Card;
- sending push notifications to non-loopback/external webhooks;
- using real work data, credentials, work-paid compute, or work-protected artifacts;
- enabling, disabling, installing, configuring, or restarting live Hermes services/profiles/plugins/skills/MCP servers;
- mutating the IAP repository or Hermes Stuff submodule;
- opening PRs, pushing branches, publishing packages, making releases, deploying, or changing public surfaces.

## Definition of done for “fully implemented A2A locally”

`hermes-a2a` may claim “fully implemented A2A locally” only when:

1. The pinned upstream source bundle, version, checksums, licenses, provenance, and generated artifacts are recorded.
2. Canonical data model objects round-trip and validate against the pinned source bundle.
3. Agent Card and Extended Agent Card behavior is canonical, safe-projected, and security-scheme tested.
4. Core task/message/artifact lifecycle uses canonical A2A objects as the primary protocol surface.
5. JSON-RPC over HTTP binding passes required conformance and pinned SDK/example interop tests if JSON-RPC is required by the pinned spec.
6. Streaming/subscription behavior passes required payload and transport-framing conformance tests where required by the pinned spec.
7. Push notification config operations pass required local/loopback tests and deny external destinations by default where required or supported by the pinned spec.
8. HTTP+JSON/REST binding passes required conformance tests if required or supported by the pinned spec.
9. gRPC binding passes required conformance tests only if M7 classifies gRPC as required; otherwise it is optional extension evidence, not required DoD.
10. Cross-binding equivalence tests pass for every implemented binding using the M11/M16 oracle.
11. Security, policy, projection, receipt, MCP/tool non-exposure, network-bind, and label-enforcement gates pass for every peer-visible output surface.
12. A clean/temp-copy validation can reproduce tests, manifests, generated artifacts, and conformance receipts.
13. Residual optional/not-applicable rows are explicitly justified against the pinned source bundle rather than silently skipped.
14. A final synthesis packet states exact supported version, bindings, capabilities, non-claims, and remaining gates.

This definition of done does **not** imply production readiness, public release readiness, LAN readiness, or authorization for public/LAN exposure. Those remain separate gates.

## Relationship to existing IAP work

Use the existing IAP repository as the policy/spec source of gravity for Janusz-specific safety/profile policy:

```text
/home/openclaw/dev/hermes-agent-interop-profile
```

This workspace remains the practical implementation/proof lane. If durable A2A/IAP extension patterns emerge, produce local porting proposals/receipts for IAP review. Do not mutate the IAP repo, Hermes Stuff submodule, remote/public surfaces, or live Hermes profile/service state from this workspace unless Janusz separately approves that exact action.

## Immediate next action

Start M7 as a bounded local workstream:

1. Pin the upstream A2A release source bundle with version, URL, tag/commit, license, retrieval time, SHA-256, and provenance/signature status.
2. Verify whether the candidate `v1.0.0` and `spec/a2a.proto` assumptions are correct; if not, patch this plan before code implementation.
3. Generate `milestones/m7/conformance-matrix.json`, `operation-binding-table.json`, `gap-ledger.json`, and M0–M6 evidence manifest from the pinned bundle.
4. Decide implementation language, SDK/codegen path, license compatibility, gRPC requiredness, exact operation names/paths, security schemes, and extension placement.
5. Stop before code implementation if the pinned upstream spec/SDK state is ambiguous or materially conflicts with this plan.
