# M16 conformance synthesis

Generated: `2026-07-01T03:43:48.736732Z`

Status: **PASSED**

Evidence:

- Pinned SDK/runtime: `a2a-sdk==1.0.0` from `uv.lock` (`2f5f7edd4b060b5d32f85a1540097630f946d221a1149f87527ca871420a3cb7`)
- Operations: 11 methods, descriptor/table match: `True`
- HTTP surfaces: Agent Card, JSON-RPC, REST, SSE, push config, extended Agent Card auth
- gRPC: loopback `127.0.0.1:45727` then stopped by context manager
- Projection: safe pass and unsafe block verified
- Tests: `uv run --extra dev python -m pytest tests -q` exit `0`

No public/LAN/service/profile/IAP mutation occurred.
