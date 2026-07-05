#!/usr/bin/env python3
"""
v82m6 — Live test for GET /api/cowork/dual-signal-effective?host=<name>.
Uses Flask test_client so we can run offline (no Ollama, no real bridge).

Coverage :
  1. Empty rings + any host -> effective:true (insufficient data fallback)
  2. Host with 5 emitted, 0 accepted -> effective:false (cool-down)
  3. Host with 3 emitted, 1 accepted -> effective:true (insufficient data)
  4. Host with 5 emitted, 2 accepted -> effective:true (some acceptance)
  5. Unknown host -> effective:true (no events)
  6. Missing host param -> 400
  7. Host normalisation : "www.LinkedIn.com" -> "linkedin.com"

Run :
    python application/test_bridge_dual_signal_effective.py

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


def emit_event(client, kind, host):
    return client.post(
        "/api/cowork/dual-signal-event",
        data=json.dumps({"kind": kind, "host": host}),
        content_type="application/json",
    )


# ---------------------------------------------------------------------------
# Cases
# ---------------------------------------------------------------------------


@case("empty rings + any host -> effective:true (insufficient-data fallback)")
def case_empty(client):
    reset_rings()
    r = client.get("/api/cowork/dual-signal-effective?host=linkedin.com")
    assert r.status_code == 200, f"status={r.status_code}"
    body = r.get_json()
    assert body["ok"] is True
    assert body["host"] == "linkedin.com"
    assert body["emitted"] == 0
    assert body["accepted"] == 0
    assert body["effective"] is True
    assert body["min_emitted"] == 5


@case("agenda fixture : linkedin (5 emitted, 0 accepted) -> effective:false")
def case_ineffective(client):
    reset_rings()
    for _ in range(5):
        emit_event(client, "emitted", "linkedin.com")
    r = client.get("/api/cowork/dual-signal-effective?host=linkedin.com")
    body = r.get_json()
    assert body["ok"] is True
    assert body["emitted"] == 5
    assert body["accepted"] == 0
    assert body["effective"] is False, f"expected effective:false, got {body['effective']!r}"


@case("agenda fixture : reddit (3 emitted, 1 accepted) -> effective:true (insufficient)")
def case_insufficient_data(client):
    reset_rings()
    for _ in range(3):
        emit_event(client, "emitted", "reddit.com")
    emit_event(client, "accepted", "reddit.com")
    r = client.get("/api/cowork/dual-signal-effective?host=reddit.com")
    body = r.get_json()
    assert body["emitted"] == 3
    assert body["accepted"] == 1
    assert body["effective"] is True, "below MIN_EMITTED -> default trust"


@case("host with 5 emitted, 2 accepted -> effective:true (acceptance > 0)")
def case_some_acceptance(client):
    reset_rings()
    for _ in range(5):
        emit_event(client, "emitted", "github.com")
    for _ in range(2):
        emit_event(client, "accepted", "github.com")
    r = client.get("/api/cowork/dual-signal-effective?host=github.com")
    body = r.get_json()
    assert body["emitted"] == 5
    assert body["accepted"] == 2
    assert body["effective"] is True


@case("agenda fixture : unknown.com -> effective:true (no data, default trust)")
def case_unknown_host(client):
    reset_rings()
    r = client.get("/api/cowork/dual-signal-effective?host=unknown.com")
    body = r.get_json()
    assert body["ok"] is True
    assert body["emitted"] == 0
    assert body["accepted"] == 0
    assert body["effective"] is True


@case("missing host param -> 400")
def case_missing_host(client):
    r = client.get("/api/cowork/dual-signal-effective")
    assert r.status_code == 400, f"status={r.status_code}"
    body = r.get_json()
    assert body["ok"] is False


@case("empty host param -> 400")
def case_empty_host(client):
    r = client.get("/api/cowork/dual-signal-effective?host=")
    assert r.status_code == 400, f"status={r.status_code}"


@case("host normalisation : www.LinkedIn.com matches linkedin.com aggregation")
def case_host_normalisation(client):
    reset_rings()
    # Records with "linkedin.com" (already normalised by _record_dual_signal_event).
    for _ in range(5):
        emit_event(client, "emitted", "linkedin.com")
    # Query with mixed-case + www. -> should still find them.
    r = client.get("/api/cowork/dual-signal-effective?host=www.LinkedIn.com")
    body = r.get_json()
    assert body["host"] == "linkedin.com"
    assert body["emitted"] == 5
    assert body["effective"] is False


@case("isolation across hosts : linkedin ineffective doesn't poison reddit")
def case_host_isolation(client):
    reset_rings()
    for _ in range(5):
        emit_event(client, "emitted", "linkedin.com")
    # Reddit has its own data : 5 emitted, 3 accepted -> effective:true
    for _ in range(5):
        emit_event(client, "emitted", "reddit.com")
    for _ in range(3):
        emit_event(client, "accepted", "reddit.com")
    r1 = client.get("/api/cowork/dual-signal-effective?host=linkedin.com")
    r2 = client.get("/api/cowork/dual-signal-effective?host=reddit.com")
    assert r1.get_json()["effective"] is False
    assert r2.get_json()["effective"] is True


@case("ok shape : response carries host, emitted, accepted, effective, min_emitted")
def case_response_shape(client):
    reset_rings()
    r = client.get("/api/cowork/dual-signal-effective?host=example.com")
    body = r.get_json()
    for key in ("ok", "host", "emitted", "accepted", "effective", "min_emitted"):
        assert key in body, f"missing key {key!r}"


def main():
    client = bridge_server.app.test_client()
    print(f"[v82m6] Running {len(CASES)} dual-signal-effective cases via Flask test_client\n")
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
