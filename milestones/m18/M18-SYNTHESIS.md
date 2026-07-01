# M18 documentation and release-readiness synthesis

Status: **PASSED for local documentation/release-readiness packet**.

Created/updated:

- `docs/operator.md`
- `docs/developer.md`
- `milestones/m18/RELEASE-READINESS.md`
- `milestones/m18/IAP-PORTING-PACKET.md`

M17b–M17e refresh:

- Operator/developer docs now cover the validated `instances.yaml` roster, `hermes_a2a.config`, `hermes_a2a.serve`, and `scripts/run_m17b_triad_pilot.py`.
- Operator/developer docs now cover gated `HermesProfileExecutor`, user-level sidecar service rollout, and the bounded synthetic LAN pilot script.
- Release readiness now records that M17b is synthetic-only/foreground/loopback-only, M17c passed for one approved local live profile, M17d passed for approved loopback user services, and M17e remains blocked on negative unlisted-host reachability proof before any LAN-readiness claim.

The packet documents local operation, development, release/publication blockers, IAP porting recommendations, and preserved non-actions. Public release, PR, package publication, deployment, public Agent Card publication, production access, credential rotation, destructive action, work-labeled live execution, and IAP mutation remain separately gated.
