# M18 documentation and release-readiness synthesis

Status: **PASSED for local documentation/release-readiness packet**.

Created/updated:

- `docs/operator.md`
- `docs/developer.md`
- `milestones/m18/RELEASE-READINESS.md`
- `milestones/m18/IAP-PORTING-PACKET.md`

M17b refresh:

- Operator/developer docs now cover the validated `instances.yaml` roster, `hermes_a2a.config`, `hermes_a2a.serve`, and `scripts/run_m17b_triad_pilot.py`.
- Release readiness now records that M17b is synthetic-only, foreground, loopback-only, and not a live/service/LAN/public readiness claim.

The packet documents local operation, development, release/publication blockers, IAP porting recommendations, and preserved non-actions. Public release, PR, package publication, deployment, LAN/public exposure, live Hermes profile execution, service installation/restart, host inventory, and IAP mutation remain separately gated.
