#!/usr/bin/env python3
"""
v82m9 — Live tests via Flask test_client (offline) for :
  - POST /api/cowork/trend-signal-reset?host=<name>          (new in v82m9)
  - TTL eviction on stale hosts inside `_record_trend_signal_event`

Run :
    python application/test_bridge_v82m9_trend_reset_and_ttl.py

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


def reset_trend_state():
    bridge_server._TREND_SIGNAL_EMITTED.clear()
    bridge_server._TREND_SIGNAL_ACCEPTED.clear()
    bridge_server._TREND_SIGNAL_LAST_TS_PER_HOST.clear()


def emit_trend(client, kind, host):
    return client.post(
        "/api/cowork/trend-signal-event",
        data=json.dumps({"kind": kind, "host": host}),
        content_type="application/json",
    )


# ---------------------------------------------------------------------------
# trend-signal-reset cases
# ---------------------------------------------------------------------------

@case("trend-signal-reset : clears per-host slice + returns counts")
def case_trend_reset_clears(client):
    reset_trend_state()
    for _ in range(5):
        emit_trend(client, "emitted", "linkedin.com")
    emit_trend(client, "emitted", "reddit.com")
    r = client.post("/api/cowork/trend-signal-reset?host=linkedin.com")
    assert r.status_code == 200, f"status={r.status_code}"
    body = r.get_json()
    assert body["ok"] is True
    assert body["host"] == "linkedin.com"
    assert body["cleared_emitted"] == 5
    assert body["cleared_accepted"] == 0
    # reddit untouched
    stats = client.get("/api/cowork/trend-signal-stats").get_json()
    assert stats["total_emitted"] == 1
    assert stats["by_host_top5"][0]["host"] == "reddit.com"


@case("trend-signal-reset : also clears accepted slice")
def case_trend_reset_accepted(client):
    reset_trend_state()
    for _ in range(5):
        emit_trend(client, "emitted", "github.com")
    for _ in range(2):
        emit_trend(client, "accepted", "github.com")
    r = client.post("/api/cowork/trend-signal-reset?host=github.com")
    body = r.get_json()
    assert body["cleared_emitted"] == 5
    assert body["cleared_accepted"] == 2
    # last-ts slot also evicted
    assert "github.com" not in bridge_server._TREND_SIGNAL_LAST_TS_PER_HOST


@case("trend-signal-reset : missing host param -> 400")
def case_trend_reset_missing_host(client):
    r = client.post("/api/cowork/trend-signal-reset")
    assert r.status_code == 400


@case("trend-signal-reset : empty host param -> 400")
def case_trend_reset_empty_host(client):
    r = client.post("/api/cowork/trend-signal-reset?host=")
    assert r.status_code == 400


@case("trend-signal-reset : host normalisation (www.LinkedIn.com -> linkedin.com)")
def case_trend_reset_norm(client):
    reset_trend_state()
    for _ in range(3):
        emit_trend(client, "emitted", "linkedin.com")
    r = client.post("/api/cowork/trend-signal-reset?host=www.LinkedIn.com")
    body = r.get_json()
    assert body["host"] == "linkedin.com"
    assert body["cleared_emitted"] == 3


@case("trend-signal-reset : unknown host -> ok with zero counts")
def case_trend_reset_unknown(client):
    reset_trend_state()
    r = client.post("/api/cowork/trend-signal-reset?host=nowhere.example")
    body = r.get_json()
    assert body["ok"] is True
    assert body["cleared_emitted"] == 0
    assert body["cleared_accepted"] == 0


# ---------------------------------------------------------------------------
# TTL eviction cases
# ---------------------------------------------------------------------------

@case("TTL eviction : stale host (>600s) cleared on next emit")
def case_ttl_evicts_stale(client):
    reset_trend_state()
    # Seed linkedin entries with a deliberately old timestamp.
    # We bypass the normal record path so we can manipulate ts directly.
    bridge_server._TREND_SIGNAL_EMITTED.append({"ts": 1.0, "host": "linkedin.com"})
    bridge_server._TREND_SIGNAL_EMITTED.append({"ts": 1.0, "host": "linkedin.com"})
    bridge_server._TREND_SIGNAL_LAST_TS_PER_HOST["linkedin.com"] = 1.0
    # Force a TTL window > 600s by emitting a fresh event for a different
    # host — the eviction step runs before the append.
    emit_trend(client, "emitted", "reddit.com")
    # linkedin should be fully evicted ; only reddit remains.
    stats = client.get("/api/cowork/trend-signal-stats").get_json()
    by_host = {row["host"]: row for row in stats["by_host_top5"]}
    assert "linkedin.com" not in by_host, f"linkedin should be evicted ; got {by_host}"
    assert by_host["reddit.com"]["emitted"] == 1
    assert "linkedin.com" not in bridge_server._TREND_SIGNAL_LAST_TS_PER_HOST


@case("TTL eviction : fresh host (<600s) preserved")
def case_ttl_preserves_fresh(client):
    reset_trend_state()
    import time as _time
    now = _time.time()
    # Both linkedin and reddit are recent (<60s old).
    bridge_server._TREND_SIGNAL_EMITTED.append({"ts": now - 30, "host": "linkedin.com"})
    bridge_server._TREND_SIGNAL_LAST_TS_PER_HOST["linkedin.com"] = now - 30
    emit_trend(client, "emitted", "reddit.com")
    stats = client.get("/api/cowork/trend-signal-stats").get_json()
    by_host = {row["host"]: row for row in stats["by_host_top5"]}
    assert "linkedin.com" in by_host, "fresh linkedin should NOT be evicted"
    assert "reddit.com" in by_host


@case("TTL eviction : configurable via _TREND_SIGNAL_TTL_SECONDS")
def case_ttl_configurable(client):
    reset_trend_state()
    saved_ttl = bridge_server._TREND_SIGNAL_TTL_SECONDS
    try:
        # Drop TTL to 1 second so even recent entries become stale.
        bridge_server._TREND_SIGNAL_TTL_SECONDS = 1.0
        import time as _time
        now = _time.time()
        bridge_server._TREND_SIGNAL_EMITTED.append({"ts": now - 5, "host": "old.com"})
        bridge_server._TREND_SIGNAL_LAST_TS_PER_HOST["old.com"] = now - 5
        emit_trend(client, "emitted", "fresh.com")
        stats = client.get("/api/cowork/trend-signal-stats").get_json()
        by_host = {row["host"]: row for row in stats["by_host_top5"]}
        assert "old.com" not in by_host, "ttl=1s should evict 5s-old entry"
        assert "fresh.com" in by_host
    finally:
        bridge_server._TREND_SIGNAL_TTL_SECONDS = saved_ttl


@case("TTL eviction : zero/negative TTL is a no-op (disabled)")
def case_ttl_disabled(client):
    reset_trend_state()
    saved_ttl = bridge_server._TREND_SIGNAL_TTL_SECONDS
    try:
        bridge_server._TREND_SIGNAL_TTL_SECONDS = 0
        bridge_server._TREND_SIGNAL_EMITTED.append({"ts": 1.0, "host": "ancient.com"})
        bridge_server._TREND_SIGNAL_LAST_TS_PER_HOST["ancient.com"] = 1.0
        emit_trend(client, "emitted", "fresh.com")
        stats = client.get("/api/cowork/trend-signal-stats").get_json()
        by_host = {row["host"]: row for row in stats["by_host_top5"]}
        assert "ancient.com" in by_host, "ttl=0 should NOT evict"
        assert "fresh.com" in by_host
    finally:
        bridge_server._TREND_SIGNAL_TTL_SECONDS = saved_ttl


@case("TTL eviction : only trend rings affected, dual untouched")
def case_ttl_isolation(client):
    reset_trend_state()
    bridge_server._DUAL_SIGNAL_EMITTED.clear()
    # Seed a stale dual entry.
    bridge_server._DUAL_SIGNAL_EMITTED.append({"ts": 1.0, "host": "stale.com"})
    bridge_server._TREND_SIGNAL_EMITTED.append({"ts": 1.0, "host": "stale.com"})
    bridge_server._TREND_SIGNAL_LAST_TS_PER_HOST["stale.com"] = 1.0
    emit_trend(client, "emitted", "fresh.com")
    # Trend ring : stale evicted.
    trend_stats = client.get("/api/cowork/trend-signal-stats").get_json()
    assert all(row["host"] != "stale.com" for row in trend_stats["by_host_top5"])
    # Dual ring : stale STILL there (TTL is trend-only).
    dual_effective = client.get("/api/cowork/dual-signal-effective?host=stale.com").get_json()
    assert dual_effective["emitted"] == 1, "dual ring untouched by trend TTL"


@case("TTL eviction + reset : reset clears last-ts so retry restarts fresh")
def case_ttl_reset_clears_lastts(client):
    reset_trend_state()
    for _ in range(3):
        emit_trend(client, "emitted", "linkedin.com")
    assert "linkedin.com" in bridge_server._TREND_SIGNAL_LAST_TS_PER_HOST
    client.post("/api/cowork/trend-signal-reset?host=linkedin.com")
    assert "linkedin.com" not in bridge_server._TREND_SIGNAL_LAST_TS_PER_HOST


def main():
    client = bridge_server.app.test_client()
    print(f"[v82m9] Running {len(CASES)} trend-reset + TTL cases via Flask test_client\n")
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
