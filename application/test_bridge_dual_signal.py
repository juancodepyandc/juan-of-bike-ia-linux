#!/usr/bin/env python3
"""
v82m5 — Live test for the GET /api/cowork/dual-signal-stats and
POST /api/cowork/dual-signal-event endpoints.
Uses Flask test_client so we can run offline (no Ollama, no real bridge).

Coverage :
  1. Empty buffers -> totals zero, acceptance_rate=0.0, by_host_top5=[]
  2. POST emitted×3 + accepted×2 -> acceptance_rate=2/3=0.667
  3. POST malformed kind -> 400
  4. by_host_top5 aggregates emitted/accepted per host correctly
  5. Module-level rings cap at 100 (deque maxlen)

Run :
    python application/test_bridge_dual_signal.py

Exits 0 on success, 1 on any assertion failure.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import bridge_server  # noqa: E402

CASES = []


def case(name):
    def deco(fn):
        CASES.append((name, fn))
        return fn
    return deco


def reset_rings():
    bridge_server._DUAL_SIGNAL_EMITTED.clear()
    bridge_server._DUAL_SIGNAL_ACCEPTED.clear()


@case("empty rings -> totals zero, acceptance_rate=0.0, by_host_top5=[]")
def case_empty(client):
    reset_rings()
    r = client.get("/api/cowork/dual-signal-stats")
    assert r.status_code == 200, f"status={r.status_code}"
    body = r.get_json()
    assert body["ok"] is True
    assert body["total_dual_signal_emitted"] == 0
    assert body["total_dual_signal_accepted"] == 0
    assert body["acceptance_rate"] == 0.0
    assert body["by_host_top5"] == []


@case("agenda fixture : emitted×3 + accepted×2 -> acceptance_rate=2/3")
def case_emitted_accepted(client):
    reset_rings()
    # 3 emitted (linkedin), 2 accepted (linkedin).
    for _ in range(3):
        client.post(
            "/api/cowork/dual-signal-event",
            data=json.dumps({"kind": "emitted", "host": "linkedin.com"}),
            content_type="application/json",
        )
    for _ in range(2):
        client.post(
            "/api/cowork/dual-signal-event",
            data=json.dumps({"kind": "accepted", "host": "linkedin.com"}),
            content_type="application/json",
        )
    r = client.get("/api/cowork/dual-signal-stats")
    body = r.get_json()
    assert body["total_dual_signal_emitted"] == 3, f"emitted={body['total_dual_signal_emitted']}"
    assert body["total_dual_signal_accepted"] == 2, f"accepted={body['total_dual_signal_accepted']}"
    # 2/3 = 0.6666...
    assert abs(body["acceptance_rate"] - (2.0 / 3.0)) < 1e-6, (
        f"acceptance_rate={body['acceptance_rate']!r}"
    )
    # Per-host : linkedin only.
    rows = body["by_host_top5"]
    assert len(rows) == 1, f"expected 1 host, got {len(rows)}"
    assert rows[0]["host"] == "linkedin.com"
    assert rows[0]["emitted"] == 3
    assert rows[0]["accepted"] == 2
    assert abs(rows[0]["rate"] - (2.0 / 3.0)) < 1e-6


@case("zero events -> totals=0, rate=0.0 (stable shape)")
def case_zero_events(client):
    reset_rings()
    r = client.get("/api/cowork/dual-signal-stats")
    body = r.get_json()
    assert body["total_dual_signal_emitted"] == 0
    assert body["total_dual_signal_accepted"] == 0
    assert body["acceptance_rate"] == 0.0
    assert body["by_host_top5"] == []


@case("by_host_top5 — multi-host aggregation, sorted emitted desc")
def case_multi_host(client):
    reset_rings()
    # linkedin : 5 emitted, 4 accepted (rate=0.8)
    for _ in range(5):
        client.post("/api/cowork/dual-signal-event",
                    data=json.dumps({"kind": "emitted", "host": "linkedin.com"}),
                    content_type="application/json")
    for _ in range(4):
        client.post("/api/cowork/dual-signal-event",
                    data=json.dumps({"kind": "accepted", "host": "linkedin.com"}),
                    content_type="application/json")
    # reddit : 3 emitted, 1 accepted (rate=0.333)
    for _ in range(3):
        client.post("/api/cowork/dual-signal-event",
                    data=json.dumps({"kind": "emitted", "host": "reddit.com"}),
                    content_type="application/json")
    client.post("/api/cowork/dual-signal-event",
                data=json.dumps({"kind": "accepted", "host": "reddit.com"}),
                content_type="application/json")
    # github : 1 emitted, 1 accepted (rate=1.0)
    client.post("/api/cowork/dual-signal-event",
                data=json.dumps({"kind": "emitted", "host": "github.com"}),
                content_type="application/json")
    client.post("/api/cowork/dual-signal-event",
                data=json.dumps({"kind": "accepted", "host": "github.com"}),
                content_type="application/json")
    r = client.get("/api/cowork/dual-signal-stats")
    body = r.get_json()
    assert body["total_dual_signal_emitted"] == 9
    assert body["total_dual_signal_accepted"] == 6
    rows = body["by_host_top5"]
    # Sorted by emitted desc -> linkedin (5), reddit (3), github (1).
    assert rows[0]["host"] == "linkedin.com"
    assert rows[0]["emitted"] == 5
    assert rows[0]["accepted"] == 4
    assert abs(rows[0]["rate"] - 0.8) < 1e-6
    assert rows[1]["host"] == "reddit.com"
    assert rows[1]["emitted"] == 3
    assert abs(rows[1]["rate"] - (1.0 / 3.0)) < 1e-6
    assert rows[2]["host"] == "github.com"
    assert rows[2]["emitted"] == 1


@case("POST malformed kind -> 400")
def case_post_malformed(client):
    reset_rings()
    r = client.post(
        "/api/cowork/dual-signal-event",
        data=json.dumps({"kind": "garbage"}),
        content_type="application/json",
    )
    assert r.status_code == 400, f"status={r.status_code}"
    body = r.get_json()
    assert body["ok"] is False
    # Buffers untouched.
    s = client.get("/api/cowork/dual-signal-stats")
    sbody = s.get_json()
    assert sbody["total_dual_signal_emitted"] == 0
    assert sbody["total_dual_signal_accepted"] == 0


@case("POST without host -> recorded with empty host")
def case_post_no_host(client):
    reset_rings()
    r = client.post(
        "/api/cowork/dual-signal-event",
        data=json.dumps({"kind": "emitted"}),
        content_type="application/json",
    )
    assert r.status_code == 200
    s = client.get("/api/cowork/dual-signal-stats")
    body = s.get_json()
    assert body["total_dual_signal_emitted"] == 1
    rows = body["by_host_top5"]
    assert rows[0]["host"] == ""


@case("ring cap=100 — buffer evicts oldest")
def case_ring_cap(client):
    reset_rings()
    # Append 110 emitted events ; ring should keep only last 100.
    for i in range(110):
        client.post(
            "/api/cowork/dual-signal-event",
            data=json.dumps({"kind": "emitted", "host": f"host{i % 3}.com"}),
            content_type="application/json",
        )
    s = client.get("/api/cowork/dual-signal-stats")
    body = s.get_json()
    assert body["total_dual_signal_emitted"] == 100, f"capped emitted={body['total_dual_signal_emitted']}"


@case("host normalisation — strips www. and lowercases")
def case_host_normalisation(client):
    reset_rings()
    client.post("/api/cowork/dual-signal-event",
                data=json.dumps({"kind": "emitted", "host": "www.LinkedIn.com"}),
                content_type="application/json")
    s = client.get("/api/cowork/dual-signal-stats")
    body = s.get_json()
    rows = body["by_host_top5"]
    assert rows[0]["host"] == "linkedin.com", f"got host={rows[0]['host']!r}"


def main():
    client = bridge_server.app.test_client()
    print(f"[v82m5] Running {len(CASES)} dual-signal-stats cases via Flask test_client\n")
    failures = []
    for i, (name, fn) in enumerate(CASES, 1):
        try:
            fn(client)
            print(f"  [{i}/{len(CASES)}] PASS  {name}")
        except AssertionError as e:
            failures.append((name, str(e)))
            print(f"  [{i}/{len(CASES)}] FAIL  {name}\n           --> {e}")
        except Exception as e:  # noqa: BLE001
            failures.append((name, f"{type(e).__name__}: {e}"))
            print(f"  [{i}/{len(CASES)}] ERR   {name}\n           --> {type(e).__name__}: {e}")
    print()
    if failures:
        print(f"{len(failures)} / {len(CASES)} failed.")
        return 1
    print(f"All {len(CASES)} passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
