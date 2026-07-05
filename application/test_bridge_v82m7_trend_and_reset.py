#!/usr/bin/env python3
"""
v82m7 — Live tests for the new bridge endpoints :
  - POST /api/cowork/dual-signal-reset?host=<name>
  - POST /api/cowork/trend-signal-event
  - GET  /api/cowork/trend-signal-stats

Uses Flask test_client so we can run offline (no Ollama, no real bridge).

Run :
    python application/test_bridge_v82m7_trend_and_reset.py

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


def reset_dual_rings():
    bridge_server._DUAL_SIGNAL_EMITTED.clear()
    bridge_server._DUAL_SIGNAL_ACCEPTED.clear()


def reset_trend_rings():
    bridge_server._TREND_SIGNAL_EMITTED.clear()
    bridge_server._TREND_SIGNAL_ACCEPTED.clear()


def emit_dual(client, kind, host):
    return client.post(
        "/api/cowork/dual-signal-event",
        data=json.dumps({"kind": kind, "host": host}),
        content_type="application/json",
    )


def emit_trend(client, kind, host):
    return client.post(
        "/api/cowork/trend-signal-event",
        data=json.dumps({"kind": kind, "host": host}),
        content_type="application/json",
    )


# ---------------------------------------------------------------------------
# dual-signal-reset cases
# ---------------------------------------------------------------------------

@case("dual-signal-reset : clears per-host slice + returns counts")
def case_reset_clears(client):
    reset_dual_rings()
    for _ in range(5):
        emit_dual(client, "emitted", "linkedin.com")
    emit_dual(client, "emitted", "reddit.com")
    r = client.post("/api/cowork/dual-signal-reset?host=linkedin.com")
    assert r.status_code == 200, f"status={r.status_code}"
    body = r.get_json()
    assert body["ok"] is True
    assert body["host"] == "linkedin.com"
    assert body["cleared_emitted"] == 5
    assert body["cleared_accepted"] == 0
    # reddit untouched
    r2 = client.get("/api/cowork/dual-signal-effective?host=reddit.com")
    assert r2.get_json()["emitted"] == 1
    # linkedin verified empty
    r3 = client.get("/api/cowork/dual-signal-effective?host=linkedin.com")
    assert r3.get_json()["emitted"] == 0
    assert r3.get_json()["effective"] is True


@case("dual-signal-reset : also clears accepted slice")
def case_reset_accepted(client):
    reset_dual_rings()
    for _ in range(5):
        emit_dual(client, "emitted", "github.com")
    for _ in range(2):
        emit_dual(client, "accepted", "github.com")
    r = client.post("/api/cowork/dual-signal-reset?host=github.com")
    body = r.get_json()
    assert body["cleared_emitted"] == 5
    assert body["cleared_accepted"] == 2


@case("dual-signal-reset : missing host param -> 400")
def case_reset_missing_host(client):
    r = client.post("/api/cowork/dual-signal-reset")
    assert r.status_code == 400


@case("dual-signal-reset : empty host param -> 400")
def case_reset_empty_host(client):
    r = client.post("/api/cowork/dual-signal-reset?host=")
    assert r.status_code == 400


@case("dual-signal-reset : host normalisation (www.LinkedIn.com -> linkedin.com)")
def case_reset_norm(client):
    reset_dual_rings()
    for _ in range(3):
        emit_dual(client, "emitted", "linkedin.com")
    r = client.post("/api/cowork/dual-signal-reset?host=www.LinkedIn.com")
    body = r.get_json()
    assert body["host"] == "linkedin.com"
    assert body["cleared_emitted"] == 3


@case("dual-signal-reset : unknown host -> ok with zero counts")
def case_reset_unknown(client):
    reset_dual_rings()
    r = client.post("/api/cowork/dual-signal-reset?host=nowhere.example")
    body = r.get_json()
    assert body["ok"] is True
    assert body["cleared_emitted"] == 0
    assert body["cleared_accepted"] == 0


# ---------------------------------------------------------------------------
# trend-signal-event + trend-signal-stats cases
# ---------------------------------------------------------------------------

@case("trend-signal-event : emitted recorded into trend ring")
def case_trend_emit(client):
    reset_trend_rings()
    r = emit_trend(client, "emitted", "linkedin.com")
    assert r.status_code == 200
    body = r.get_json()
    assert body["ok"] is True
    assert body["kind"] == "emitted"
    # Verify recorded
    r2 = client.get("/api/cowork/trend-signal-stats")
    stats = r2.get_json()
    assert stats["total_emitted"] == 1
    assert stats["total_accepted"] == 0


@case("trend-signal-event : accepted increments accepted")
def case_trend_accept(client):
    reset_trend_rings()
    emit_trend(client, "emitted", "linkedin.com")
    emit_trend(client, "accepted", "linkedin.com")
    stats = client.get("/api/cowork/trend-signal-stats").get_json()
    assert stats["total_emitted"] == 1
    assert stats["total_accepted"] == 1
    assert stats["acceptance_rate"] == 1.0


@case("trend-signal-event : malformed kind -> 400")
def case_trend_bad_kind(client):
    r = client.post(
        "/api/cowork/trend-signal-event",
        data=json.dumps({"kind": "bogus", "host": "x"}),
        content_type="application/json",
    )
    assert r.status_code == 400


@case("trend-signal-stats : empty -> totals zero, by_host_top5 []")
def case_trend_stats_empty(client):
    reset_trend_rings()
    r = client.get("/api/cowork/trend-signal-stats")
    stats = r.get_json()
    assert stats["ok"] is True
    assert stats["total_emitted"] == 0
    assert stats["total_accepted"] == 0
    assert stats["acceptance_rate"] == 0.0
    assert stats["by_host_top5"] == []


@case("trend-signal-stats : per-host aggregation + top-5 ordering")
def case_trend_stats_per_host(client):
    reset_trend_rings()
    # linkedin : 3 emitted, 1 accepted (rate 0.33)
    for _ in range(3):
        emit_trend(client, "emitted", "linkedin.com")
    emit_trend(client, "accepted", "linkedin.com")
    # reddit : 1 emitted, 1 accepted (rate 1.0)
    emit_trend(client, "emitted", "reddit.com")
    emit_trend(client, "accepted", "reddit.com")
    stats = client.get("/api/cowork/trend-signal-stats").get_json()
    assert stats["total_emitted"] == 4
    assert stats["total_accepted"] == 2
    # linkedin first (3 emitted > 1 emitted)
    assert stats["by_host_top5"][0]["host"] == "linkedin.com"
    assert stats["by_host_top5"][0]["emitted"] == 3
    assert stats["by_host_top5"][0]["accepted"] == 1


@case("trend-signal isolation : tier-1 dual-signal NOT polluted by tier-2 events")
def case_trend_isolation(client):
    reset_dual_rings()
    reset_trend_rings()
    emit_trend(client, "emitted", "linkedin.com")
    emit_trend(client, "accepted", "linkedin.com")
    # dual-signal stats should still be empty
    dual_stats = client.get("/api/cowork/dual-signal-stats").get_json()
    assert dual_stats["total_dual_signal_emitted"] == 0
    assert dual_stats["total_dual_signal_accepted"] == 0
    # trend stats should reflect the events
    trend_stats = client.get("/api/cowork/trend-signal-stats").get_json()
    assert trend_stats["total_emitted"] == 1
    assert trend_stats["total_accepted"] == 1


@case("trend-signal-event : host normalisation (www.X.com -> x.com)")
def case_trend_host_norm(client):
    reset_trend_rings()
    emit_trend(client, "emitted", "www.LinkedIn.com")
    emit_trend(client, "emitted", "linkedin.com")
    stats = client.get("/api/cowork/trend-signal-stats").get_json()
    # Both events normalised to linkedin.com → single host row, count=2
    assert stats["total_emitted"] == 2
    assert len(stats["by_host_top5"]) == 1
    assert stats["by_host_top5"][0]["host"] == "linkedin.com"
    assert stats["by_host_top5"][0]["emitted"] == 2


def main():
    client = bridge_server.app.test_client()
    print(f"[v82m7] Running {len(CASES)} trend + reset cases via Flask test_client\n")
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
