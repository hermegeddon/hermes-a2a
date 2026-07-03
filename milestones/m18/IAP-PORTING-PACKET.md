# IAP porting packet — canonical A2A local implementation

This packet summarizes local decisions that may later be proposed to the IAP repository. It is **not** an IAP repo mutation.

## Recommended IAP concepts to port

1. **A2A safety wrapper pattern**
   - Keep upstream A2A proto/spec/SDK semantics canonical.
   - Put IAP-lite policy in local policy stores, transport/auth context, or M7-approved extension/metadata fields.

2. **Receipt-before-exposure contract**
   - Require private receipt persistence before A2A status/message/artifact/error/stream/push emission.
   - Expose only safe receipt references/hashes to peers.

3. **Projection scanner coverage**
   - Cover Agent Cards, Message, Part text/raw/url/data, Artifact, metadata, extensions, error data, SSE frames, and push payloads.

4. **Default-deny push URL policy**
   - Loopback-only by default.
   - External/public webhook destinations require exact-scope approval and SSRF controls.

5. **Protocol-label discipline**
   - Labels like `a2a-<version>-full-local` must derive from pinned source and matrix evidence, not prose claims.

6. **Synthetic sidecar rollout discipline**
   - Treat per-instance A2A sidecars as separately configured identities with distinct loopback ports, Agent Cards, receipt roots, and allowed peers.
   - Require a validation receipt that binds the exact roster SHA-256 and per-run receipt base before any sidecar binds.
   - Keep live profile execution, serviceization, LAN/Tailscale exposure, and work-labeled execution behind separate approval receipts.

7. **Gated live-executor and service rollout discipline**
   - Require a profile-launcher proof before any live Hermes executor handles an A2A task.
   - Persist raw launcher stdout/stderr and invocation diagnostics only in private receipts; peer-visible output must remain bounded, projected, and receipt-backed.
   - User-level sidecar services should use finite unit names, explicit bind ports, absolute launcher paths, env/file token inputs, service/PID/bind/readiness/log receipts, and rollback commands.

8. **LAN-readiness proof discipline**
   - A named-address LAN pilot is not enough for LAN readiness.
   - Require positive reachability from approved hosts plus negative reachability from an unlisted host, or an equivalent firewall/Tailscale ACL deny receipt, before claiming exposure is limited to named hosts.

## Evidence paths

- `milestones/m7/M7-SPEC-BASELINE.md`
- `milestones/m16/CONFORMANCE-SYNTHESIS.md`
- `milestones/m17a/M17A-SYNTHESIS.md`
- `<management-root>/milestones/m17b/M17B-SYNTHETIC-TRIAD-SYNTHESIS.md`
- `<management-root>/milestones/m17c/M17C-LIVE-EXECUTOR-SYNTHESIS.md`
- `<management-root>/milestones/m17d/M17D-LOCAL-SERVICE-SYNTHESIS.md`
- `<management-root>/milestones/m17e/M17E-SYNTHESIS.md`
- `docs/operator.md`
- `docs/developer.md`

## Non-action

No files under `<local-iap-workspace>` were modified.
