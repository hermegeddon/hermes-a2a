# M18 release-readiness checklist

Status: **local implementation complete; public release not authorized**.

## Passed local gates

- M7 source pin complete.
- M8 canonical model path uses pinned `a2a-sdk==1.0.0` generated proto/types.
- M9 Agent Card and Extended Agent Card auth exercised.
- M10 task engine path uses SDK task store/handler plus local receipt/projection wrappers.
- M11 JSON-RPC route exercised.
- M12 SSE streaming route exercised.
- M13 push config default-deny exercised.
- M14 REST route exercised.
- M15 gRPC loopback route exercised.
- M16 final conformance matrix generated with local receipt evidence.
- M17a same-machine canonical A2A pilot passed.
- M17b synthetic three-sidecar loopback triad passed when `scripts/run_m17b_triad_pilot.py --overwrite-config` writes a per-run management manifest and synthesis.
- M17c one-profile live Hermes executor loopback pilot passed with an approval receipt, launcher proof, bounded output/private invocation receipts, and safe projection.
- M17d user-level loopback sidecar service rollout passed for the finite `hermes-a2a-*` unit set, with service/PID/bind/readiness/log/smoke evidence and rollback commands.
- M17e bounded synthetic LAN Agent Card/A2A pilot produced a management receipt but is **blocked** on negative unlisted-host reachability proof or equivalent firewall/ACL deny evidence; it is not a LAN-readiness claim.

## Public release blockers / separate gates

A public release, PR, package publish, deployment, public Agent Card, public listener, or LAN-readiness claim still requires a fresh explicit gate. Before that gate:

- Re-run source provenance checks, including tag/source archive cross-check and any available signature/attestation verification.
- Perform a full secret scan of source, tests, docs, receipts, and review artifacts.
- Decide public package name/versioning and disclosure posture.
- Review Apache-2.0 obligations and generated-artifact notices.
- Decide whether local Hermes/IAP extensions should be public API, private metadata, or omitted.
- Run external SDK/client interoperability against real official examples if publishing interoperability claims.
- Re-review M17b–M17e management artifacts before publication because they intentionally contain Janusz-local conceptual instance labels, local-network addresses, unit names, profile names, and absolute local receipt paths.

## Non-actions preserved

- No public PR/release/package/deploy was performed.
- No public/wildcard/tunnel listener was opened; M17e opened only a foreground synthetic named-LAN-address pilot and tore it down.
- No live Hermes profile/plugin/skill/MCP/service config outside the approved M17c/M17d sidecar scope was mutated; M17d intentionally installed/restarted only the approved user-level `hermes-a2a-*` sidecar units.
- No IAP repo mutation was performed.
- No protected work data or credentials were used.
- Work-labeled live execution remains disabled; `agent:work:hermes-work` is serviceized as synthetic-only.
