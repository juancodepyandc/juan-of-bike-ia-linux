#!/usr/bin/env python3
"""
v82m1 — Live test for the GET /api/cowork/extraction-stats aggregation route.
Uses Flask test_client so we can run offline (no Ollama, no real bridge).

Coverage :
  1. Empty buffer → totals zero, by_host_top5=[]
  2. 5 entries populated via _record_extraction_stat → total:5, percentiles
     non-zero, under_extraction_rate computed.
  3. by_host_top5 sorted by count desc (linkedin.com > reddit.com > github.com).
  4. ?since=<ts> filters to recent entries only.
  5. Empty extract response : non-card_iteration mode does NOT append to
     the buffer (mode-gate respected).

Run :
    python application/test_bridge_extraction_stats.py

Exits 0 on success, 1 on any assertion failure.
"""
import json
import os
import sys
import time
import unittest.mock as mock

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


def reset_buffer():
    bridge_server._EXTRACTION_STATS.clear()


@case("empty buffer --> total=0, all numeric fields zero, by_host_top5=[]")
def case_empty(client):
    reset_buffer()
    r = client.get("/api/cowork/extraction-stats")
    assert r.status_code == 200, f"status={r.status_code}"
    body = r.get_json()
    assert body["ok"] is True
    assert body["total"] == 0, f"total={body['total']}"
    assert body["under_extraction_rate"] == 0.0
    assert body["avg_yield"] == 0.0
    assert body["p50_yield"] == 0.0
    assert body["p90_yield"] == 0.0
    assert body["by_host_top5"] == [], f"by_host_top5={body['by_host_top5']}"
    # v82m3 — window now also echoes `host` (null when not filtered).
    assert body["window"] == {"since": None, "host": None}, f"window={body['window']!r}"


@case("5 entries (mixed yields) --> total=5, percentiles + by_host_top5 ordered correctly")
def case_five_mocks(client):
    reset_buffer()
    # 7 entries on linkedin (3 under-extracted), 4 on reddit (1 under), 2 on github (0 under)
    # → total 13, by_host top5 = linkedin, reddit, github (count desc)
    fixtures = [
        ("linkedin.com",  10, 8),    # yield 0.80, ok
        ("linkedin.com",  10, 9),    # yield 0.90, ok
        ("linkedin.com",  10, 4),    # yield 0.40, UNDER
        ("linkedin.com",  10, 3),    # yield 0.30, UNDER
        ("linkedin.com",  10, 2),    # yield 0.20, UNDER
        ("linkedin.com",  10, 7),    # yield 0.70, ok
        ("linkedin.com",  10, 8),    # yield 0.80, ok
        ("reddit.com",     5, 4),    # yield 0.80, ok
        ("reddit.com",     5, 2),    # yield 0.40, UNDER
        ("reddit.com",     5, 5),    # yield 1.00, ok
        ("reddit.com",     5, 3),    # yield 0.60, ok
        ("github.com",     8, 8),    # yield 1.00, ok
        ("github.com",     8, 7),    # yield 0.875, ok
    ]
    for host, cp, ic in fixtures:
        bridge_server._record_extraction_stat(host=host, cards_processed=cp, items_count=ic)

    r = client.get("/api/cowork/extraction-stats")
    assert r.status_code == 200
    body = r.get_json()
    assert body["total"] == 13, f"total={body['total']}"
    # under_extraction_rate = 4/13 ≈ 0.3076
    assert abs(body["under_extraction_rate"] - 4 / 13) < 1e-6, (
        f"under_extraction_rate={body['under_extraction_rate']!r}"
    )
    # avg_yield = sum(yields)/13 — non-zero
    assert body["avg_yield"] > 0.0
    assert body["p50_yield"] > 0.0
    assert body["p90_yield"] > 0.0
    # p90 must be >= p50
    assert body["p90_yield"] >= body["p50_yield"], (
        f"p90={body['p90_yield']} < p50={body['p50_yield']}"
    )
    rows = body["by_host_top5"]
    assert len(rows) == 3, f"expected 3 hosts, got {len(rows)}"
    # Ordered : linkedin (7), reddit (4), github (2)
    assert rows[0]["host"] == "linkedin.com" and rows[0]["count"] == 7, f"row0={rows[0]}"
    assert rows[1]["host"] == "reddit.com"   and rows[1]["count"] == 4, f"row1={rows[1]}"
    assert rows[2]["host"] == "github.com"   and rows[2]["count"] == 2, f"row2={rows[2]}"
    # avg_yield per host should reflect the fixture's mean
    assert abs(rows[2]["avg_yield"] - (1.00 + 0.875) / 2) < 1e-6


@case("by_host_top5 caps at 5 even with 6+ distinct hosts")
def case_top5_cap(client):
    reset_buffer()
    for i in range(7):
        bridge_server._record_extraction_stat(host=f"host{i}.com", cards_processed=10, items_count=5)
    r = client.get("/api/cowork/extraction-stats")
    body = r.get_json()
    assert body["total"] == 7
    assert len(body["by_host_top5"]) == 5, f"by_host_top5 len={len(body['by_host_top5'])}"


@case("?since=<ts> filters to recent entries only")
def case_since_filter(client):
    reset_buffer()
    now = time.time()
    # First 3 entries with old ts (1 hour ago).
    for i in range(3):
        bridge_server._EXTRACTION_STATS.append({
            "ts": now - 3600,
            "host": "old.com",
            "cards_processed": 10,
            "items_count": 5,
            "under_extraction": False,
            "yield_pct": 0.5,
        })
    # 2 entries with recent ts (within last 60s).
    for i in range(2):
        bridge_server._record_extraction_stat(host="recent.com", cards_processed=10, items_count=8)
    # Without filter → 5
    r = client.get("/api/cowork/extraction-stats")
    body = r.get_json()
    assert body["total"] == 5, f"unfiltered total={body['total']}"
    # With since=now-30 → only the 2 recent ones survive
    r2 = client.get(f"/api/cowork/extraction-stats?since={now - 30}")
    body2 = r2.get_json()
    assert body2["total"] == 2, f"filtered total={body2['total']}"
    assert body2["window"]["since"] is not None
    assert body2["by_host_top5"][0]["host"] == "recent.com"


@case("?since=<invalid> ignored gracefully (no filter)")
def case_since_invalid(client):
    reset_buffer()
    bridge_server._record_extraction_stat(host="x.com", cards_processed=4, items_count=2)
    bridge_server._record_extraction_stat(host="x.com", cards_processed=4, items_count=4)
    # Malformed since → no filter applied, total=2.
    r = client.get("/api/cowork/extraction-stats?since=notanumber")
    body = r.get_json()
    assert body["total"] == 2, f"total with invalid since={body['total']}"
    assert body["window"]["since"] is None


@case("buffer auto-evicts at maxlen=50 (deque cap respected)")
def case_evict(client):
    reset_buffer()
    # Append 60 → only last 50 remain.
    for i in range(60):
        bridge_server._record_extraction_stat(host="bulk.com", cards_processed=10, items_count=8)
    r = client.get("/api/cowork/extraction-stats")
    body = r.get_json()
    assert body["total"] == 50, f"deque-capped total={body['total']}"


@case("under_extraction flag follows items < cards*0.5 rule")
def case_under_extraction_flag(client):
    reset_buffer()
    # 4 items / 10 cards = 0.4 < 0.5 → under = true
    bridge_server._record_extraction_stat(host="u1.com", cards_processed=10, items_count=4)
    # 5 items / 10 cards = 0.5 → under = false (strict <, not <=)
    bridge_server._record_extraction_stat(host="u2.com", cards_processed=10, items_count=5)
    # 0 items / 10 cards → under = true
    bridge_server._record_extraction_stat(host="u3.com", cards_processed=10, items_count=0)
    r = client.get("/api/cowork/extraction-stats")
    body = r.get_json()
    # 2 of 3 under_extraction
    assert abs(body["under_extraction_rate"] - 2 / 3) < 1e-6, (
        f"under_extraction_rate={body['under_extraction_rate']}"
    )


@case("extract_structured(card_iteration) with cards != [] APPENDS to buffer")
def case_extract_appends(client):
    """End-to-end : the route must call _record_extraction_stat after a
    successful card_iteration response. Mocks Ollama, posts to extract,
    then probes /extraction-stats and asserts +1."""
    reset_buffer()
    fake = mock.MagicMock()
    fake.status_code = 200
    fake.text = ""
    fake.json.return_value = {
        "message": {"content": json.dumps({"items": [{"a": 1}, {"a": 2}], "schema": "x", "notes": ""})},
    }
    with mock.patch("bridge_server.requests.post", return_value=fake):
        r = client.post(
            "/api/cowork/extract-structured",
            data=json.dumps({
                "intent": "extract",
                "html_or_text": "<html>x</html>",
                "mode": "card_iteration",
                "cards": [{"idx": i, "outerHTML": f"<div>{i}</div>"} for i in range(5)],
                "url": "https://www.linkedin.com/feed/",
            }),
            content_type="application/json",
        )
    assert r.status_code == 200, f"extract status={r.status_code}"
    # Now check the stats reflect the append.
    s = client.get("/api/cowork/extraction-stats")
    body = s.get_json()
    assert body["total"] == 1, f"total after one extract={body['total']}"
    row = body["by_host_top5"][0]
    assert row["host"] == "linkedin.com", f"host={row['host']!r}"
    assert row["count"] == 1


@case("v82m3 — ?host=<known> filters buffer to that host only")
def case_host_filter_known(client):
    reset_buffer()
    # Mixed buffer : 4 linkedin + 3 reddit + 2 github = 9 total.
    for _ in range(4):
        bridge_server._record_extraction_stat(host="linkedin.com", cards_processed=10, items_count=8)
    for _ in range(3):
        bridge_server._record_extraction_stat(host="reddit.com", cards_processed=10, items_count=4)
    for _ in range(2):
        bridge_server._record_extraction_stat(host="github.com", cards_processed=10, items_count=9)
    # Probe linkedin only.
    r = client.get("/api/cowork/extraction-stats?host=linkedin.com")
    body = r.get_json()
    assert body["total"] == 4, f"linkedin total={body['total']}"
    assert body["window"]["host"] == "linkedin.com"
    assert body["window"]["since"] is None
    # Top5 will only contain linkedin since the snapshot was filtered.
    assert len(body["by_host_top5"]) == 1
    assert body["by_host_top5"][0]["host"] == "linkedin.com"
    assert body["by_host_top5"][0]["count"] == 4
    # avg_yield = 0.8 (8/10 each)
    assert abs(body["avg_yield"] - 0.8) < 1e-6


@case("v82m3 — ?host=<unknown> --> total:0, window.host echoed")
def case_host_filter_unknown(client):
    reset_buffer()
    bridge_server._record_extraction_stat(host="linkedin.com", cards_processed=10, items_count=8)
    r = client.get("/api/cowork/extraction-stats?host=neverseen.example")
    body = r.get_json()
    assert body["total"] == 0, f"unknown host total={body['total']}"
    assert body["under_extraction_rate"] == 0.0
    assert body["by_host_top5"] == []
    assert body["window"]["host"] == "neverseen.example", (
        f"window.host echo expected, got {body['window']!r}"
    )


@case("v82m3 — ?host=&since= AND-compose (both filters applied)")
def case_host_and_since(client):
    reset_buffer()
    now = time.time()
    # Old linkedin entries (1h ago) — should be filtered out by since.
    for _ in range(3):
        bridge_server._EXTRACTION_STATS.append({
            "ts": now - 3600,
            "host": "linkedin.com",
            "cards_processed": 10,
            "items_count": 5,
            "under_extraction": False,
            "yield_pct": 0.5,
        })
    # Recent linkedin entries — pass both filters.
    for _ in range(2):
        bridge_server._record_extraction_stat(host="linkedin.com", cards_processed=10, items_count=8)
    # Recent reddit entry — passes since but not host.
    bridge_server._record_extraction_stat(host="reddit.com", cards_processed=10, items_count=8)
    # AND-compose : host=linkedin.com & since=now-30 → only the 2 recent linkedin.
    r = client.get(f"/api/cowork/extraction-stats?host=linkedin.com&since={now - 30}")
    body = r.get_json()
    assert body["total"] == 2, f"AND-filter total={body['total']}"
    assert body["window"]["host"] == "linkedin.com"
    assert body["window"]["since"] is not None
    assert body["by_host_top5"][0]["host"] == "linkedin.com"
    assert body["by_host_top5"][0]["count"] == 2


@case("v82m3 — empty host param ignored gracefully (no filter)")
def case_host_empty(client):
    reset_buffer()
    bridge_server._record_extraction_stat(host="linkedin.com", cards_processed=10, items_count=8)
    bridge_server._record_extraction_stat(host="reddit.com", cards_processed=10, items_count=8)
    # Empty host → no filter applied.
    r = client.get("/api/cowork/extraction-stats?host=")
    body = r.get_json()
    assert body["total"] == 2, f"empty host should not filter, got total={body['total']}"
    # window.host should be null (empty stripped).
    assert body["window"]["host"] is None


@case("v82m3 — host filter with no since echoes since:null")
def case_host_only_no_since(client):
    reset_buffer()
    bridge_server._record_extraction_stat(host="linkedin.com", cards_processed=10, items_count=8)
    r = client.get("/api/cowork/extraction-stats?host=linkedin.com")
    body = r.get_json()
    assert body["window"]["since"] is None
    assert body["window"]["host"] == "linkedin.com"


@case("v82m4 — last_delta_pct surfaces per host on by_host_top5 rows")
def case_last_delta_pct_field(client):
    reset_buffer()
    # Reset per-host yield history so the test is hermetic.
    bridge_server._HOST_YIELD_HISTORY.clear()
    # 4 entries on linkedin (build a baseline + degraded last entry).
    # First 3 entries → yield 0.80 each (baseline mean = 0.80).
    # 4th entry → yield 0.40 (degraded). last_delta = (0.40 - 0.80) * 100 = -40.0pp.
    for _ in range(3):
        bridge_server._record_extraction_stat("linkedin.com", 10, 8)
        bridge_server._record_host_yield("linkedin.com", 0.80)
    bridge_server._record_extraction_stat("linkedin.com", 10, 4)
    bridge_server._record_host_yield("linkedin.com", 0.40)
    # 1 entry on github (only 1 entry → no prior baseline → null delta).
    bridge_server._record_extraction_stat("github.com", 10, 8)
    bridge_server._record_host_yield("github.com", 0.80)
    r = client.get("/api/cowork/extraction-stats")
    body = r.get_json()
    rows = body["by_host_top5"]
    by_host = {row["host"]: row for row in rows}
    assert "linkedin.com" in by_host, f"rows={rows}"
    assert "github.com" in by_host, f"rows={rows}"
    # linkedin : 4 entries, last - mean(prior3) = 0.40 - 0.80 = -0.40 → -40.0pp.
    ldelta = by_host["linkedin.com"]["last_delta_pct"]
    assert ldelta is not None, "linkedin should have a delta (4 entries)"
    assert abs(ldelta - (-40.0)) < 1e-6, f"linkedin last_delta_pct={ldelta!r} expected ~-40.0"
    # github : only 1 entry → delta is null (no prior baseline).
    gdelta = by_host["github.com"]["last_delta_pct"]
    assert gdelta is None, f"github single entry should produce null delta, got {gdelta!r}"


@case("v82m5 — delta_history array surfaces per host (sparkline data)")
def case_delta_history_field(client):
    reset_buffer()
    bridge_server._HOST_YIELD_HISTORY.clear()
    # 6 entries on linkedin → expect 5 deltas (cap) chronological asc.
    yields = [0.80, 0.70, 0.60, 0.50, 0.40, 0.30]
    for y in yields:
        items_count = int(y * 10)
        bridge_server._record_extraction_stat("linkedin.com", 10, items_count)
        bridge_server._record_host_yield("linkedin.com", y)
    r = client.get("/api/cowork/extraction-stats")
    body = r.get_json()
    rows = body["by_host_top5"]
    by_host = {row["host"]: row for row in rows}
    li = by_host["linkedin.com"]
    assert "delta_history" in li, f"missing delta_history on row : {li!r}"
    arr = li["delta_history"]
    assert isinstance(arr, list), f"delta_history not list : {type(arr).__name__}"
    # Cap at 5 ; 6 yields → 5 deltas (i=1..5).
    assert len(arr) == 5, f"expected 5 deltas, got {len(arr)}: {arr!r}"
    # First entry is index 1 : 0.70 - 0.80 = -10.0pp (chronological asc).
    assert abs(arr[0] - (-10.0)) < 1e-6, f"arr[0]={arr[0]!r} expected -10.0"
    # Last entry is index 5 : 0.30 - mean([0.80,0.70,0.60,0.50,0.40]) = 0.30 - 0.60 = -30.0pp.
    assert abs(arr[-1] - (-30.0)) < 1e-6, f"arr[-1]={arr[-1]!r} expected -30.0"


@case("v82m5 — delta_history empty when host has < 2 entries")
def case_delta_history_empty(client):
    reset_buffer()
    bridge_server._HOST_YIELD_HISTORY.clear()
    bridge_server._record_extraction_stat("solo.com", 10, 8)
    bridge_server._record_host_yield("solo.com", 0.80)
    r = client.get("/api/cowork/extraction-stats")
    body = r.get_json()
    rows = body["by_host_top5"]
    by_host = {row["host"]: row for row in rows}
    solo = by_host["solo.com"]
    # last_delta_pct null AND delta_history empty list (stable shape).
    assert solo["last_delta_pct"] is None
    assert solo["delta_history"] == [], f"delta_history={solo['delta_history']!r}"


@case("extract_structured WITHOUT cards (legacy mode) does NOT append")
def case_extract_no_cards_no_append(client):
    """Mode-gate respected : non-card_iteration calls don't pollute the
    buffer — those sites would skew per-host yield computations."""
    reset_buffer()
    fake = mock.MagicMock()
    fake.status_code = 200
    fake.text = ""
    fake.json.return_value = {
        "message": {"content": json.dumps({"items": [{"a": 1}], "schema": "x", "notes": ""})},
    }
    with mock.patch("bridge_server.requests.post", return_value=fake):
        client.post(
            "/api/cowork/extract-structured",
            data=json.dumps({
                "intent": "extract",
                "html_or_text": "<html>x</html>",
                # no mode, no cards
            }),
            content_type="application/json",
        )
    s = client.get("/api/cowork/extraction-stats")
    body = s.get_json()
    assert body["total"] == 0, f"buffer should stay empty, got total={body['total']}"


def main():
    client = bridge_server.app.test_client()
    print(f"[v82m1] Running {len(CASES)} extraction-stats cases via Flask test_client\n")
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
