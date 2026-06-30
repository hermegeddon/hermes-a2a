# M16 conformance synthesis

Generated: `2026-06-30T19:29:24.220755Z`

Status: **PASSED**

Evidence:

- Pinned SDK/runtime: `a2a-sdk==1.0.0` from `uv.lock` (`5f8027b4a5121131aaff69c7b4f4f2abb613caedb4af3207c460bf29f67d4aff`)
- Operations: 11 methods, descriptor/table match: `True`
- HTTP surfaces: Agent Card, JSON-RPC, REST, SSE, push config, extended Agent Card auth
- gRPC: loopback `127.0.0.1:44909` then stopped by context manager
- Projection: safe pass and unsafe block verified
- Tests: `uv run --extra dev python -m pytest tests -q` exit `0`

No public/LAN/service/profile/IAP mutation occurred.
