# Local safety substrate contract for canonical A2A

Generated: `2026-06-30T18:30:20Z`

This contract converts M1-M6 local safety evidence into structural contracts future A2A code must call. Historical artifacts remain regression evidence, not protocol conformance.

| Safety concept | Historical source | Future structural contract | First enforcing milestone |
| --- | --- | --- | --- |
| IAP-lite roster/attestation | `milestones/m1`, `milestones/m3` | Typed requester/peer context plus allow/deny evaluator returning canonical denial reason. | M10 |
| Exact-scope approval | `milestones/m3` | Approval object with scope, requester, action, data class, expiry, and verifier; all mutating or boundary-crossing work must call it before execution. | M10 |
| Safe projection/leak scanner | `milestones/m5` | Single egress API for AgentCard, Message, Task, Artifact, Error, SSE event, push payload; covers bytes, metadata, extensions, file refs, logs, paths, memory, config, MCP/tool traces. | M8-M12 |
| Receipt-before-exposure | `milestones/m2`-`milestones/m6` | Atomic outbox/writer that persists private receipt before peer-visible emission; failure safe-denies. | M10-M13 |
| Kill switch/default-deny | M1-M6 tests | Policy readiness check and per-request deny-first gate; unknown auth/policy/projection/receipt failures do not execute. | M10-M11 |
| MCP/tool non-exposure | `milestones/m4`, `milestones/m5` | No raw MCP/tool/shell route; M16 reachability scan for names, schemas, inputs/outputs, traces. | M16 |

Implementation note: use official `a2a-sdk==1.0.0` for pinned wire/runtime surfaces where possible; wrap all peer-visible egress and execution entrypoints with these local contracts.
