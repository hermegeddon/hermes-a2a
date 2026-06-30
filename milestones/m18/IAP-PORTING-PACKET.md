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

## Evidence paths

- `milestones/m7/M7-SPEC-BASELINE.md`
- `milestones/m16/CONFORMANCE-SYNTHESIS.md`
- `milestones/m17a/M17A-SYNTHESIS.md`
- `docs/operator.md`
- `docs/developer.md`

## Non-action

No files under `/home/openclaw/dev/hermes-agent-interop-profile` were modified.
