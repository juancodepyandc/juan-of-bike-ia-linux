---
description: Probe the 3D pipeline routing via the bridge endpoint (works from UI/extension/external)
argument-hint: <3D prompt>
allowed-tools: Bash
---

POST the prompt to the bridge `/api/3d/route-test` endpoint:

```bash
curl -sS -X POST -H "Content-Type: application/json" \
  -d "{\"prompt\":\"$ARGUMENTS\"}" \
  http://127.0.0.1:3001/api/3d/route-test
```

If the local bridge is offline, swap to the active tunnel:

```bash
curl -sS -X POST -H "Content-Type: application/json" \
  -d "{\"prompt\":\"$ARGUMENTS\"}" \
  https://cooper-inspection-thanks-lives.trycloudflare.com/api/3d/route-test
```

The bridge endpoint wraps `application/scripts/route_test.py`. Use this when you need to probe routing from a context that doesn't have local Python (e.g. mobile, extension, external tool). For pure-local use, `/aurora-route-test` is faster (no HTTP round-trip).

Added in v78l.
