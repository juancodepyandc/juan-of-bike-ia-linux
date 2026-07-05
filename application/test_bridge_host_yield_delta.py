#!/usr/bin/env python3
"""
v82m2 — Live test for the X-Host-Yield-Delta-Pct response header on
/api/cowork/extract-structured. Uses Flask test_client so we can run offline
(no Ollama, no real bridge process). Mocks Ollama via requests.post so the
route hits the header emission path with controlled items[] payloads.

Coverage :
  1. Empty per-host history --> header OMITTED on first 3 calls (need >= 3
     prior entries to compute a baseline).
  2. After 3 priors with avg_yield=0.8, a 4th call with yield=0.6 produces
     X-Host-Yield-Delta-Pct: -20.0.
  3. After 3 priors with avg_yield=0.5, a 4th call with yield=0.7 produces
     X-Host-Yield-Delta-Pct: +20.0.
  4. Non-card_iteration mode (no cards) --> header OMITTED (mode-gate
     respected).
  5. Unknown host (no url in payload) --> header OMITTED.
  6. cards_processed < 5 --> header OMITTED (statistical floor).
  7. Different hosts maintain independent histories.
  8. Header is exposed via CORS expose_headers (regression check).

Run :
    python application/test_bridge_host_yield_delta.py

Exits 0 on success, 1 on any assertion failure.
"""
import json
import os
import sys
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


def reset_state():
    bridge_server._EXTRACTION_STATS.clear()
    bridge_server._HOST_YIELD_HISTORY.clear()


def fake_ollama_response(items_list):
    resp = mock.MagicMock()
    resp.status_code = 200
    resp.text = ""
    resp.json.return_value = {
        "message": {"content": json.dumps({"items": items_list, "schema": "x", "notes": ""})},
    }
    return resp


def post_extract(client, host_url, cards_count, items_count):
    """POST one card_iteration extract with `cards_count` synthetic cards
    and a mocked Ollama response producing `items_count` items.
    """
    cards = [{"idx": i, "outerHTML": f"<div>card {i}</div>"} for i in range(cards_count)]
    items = [{"a": i} for i in range(items_count)]
    with mock.patch("bridge_server.requests.post", return_value=fake_ollama_response(items)):
        return client.post(
            "/api/cowork/extract-structured",
            data=json.dumps({
                "intent": "extract",
                "html_or_text": "<html>x</html>",
                "mode": "card_iteration",
                "cards": cards,
                "url": host_url,
            }),
            content_type="application/json",
        )


@case("first 3 calls (no prior baseline) --> header OMITTED")
def case_no_prior(client):
    reset_state()
    for i in range(3):
        r = post_extract(client, "https://www.linkedin.com/feed/", cards_count=10, items_count=8)
        assert r.status_code == 200, f"call {i}: status={r.status_code}"
        assert "X-Host-Yield-Delta-Pct" not in r.headers, (
            f"call {i}: expected omitted header, got {r.headers.get('X-Host-Yield-Delta-Pct')!r}"
        )


@case("4th call with yield=0.6 vs prior avg=0.8 --> -20.0 pp")
def case_negative_delta(client):
    reset_state()
    # 3 priors with yield=0.8 (8 items / 10 cards each).
    for _ in range(3):
        post_extract(client, "https://www.linkedin.com/feed/", cards_count=10, items_count=8)
    # 4th call with yield=0.6 (6 items / 10 cards) --> delta = (0.6 - 0.8) * 100 = -20.0
    r = post_extract(client, "https://www.linkedin.com/feed/", cards_count=10, items_count=6)
    assert r.status_code == 200
    val = r.headers.get("X-Host-Yield-Delta-Pct")
    assert val is not None, f"expected header present, got {val!r}"
    assert val == "-20.0", f"expected -20.0, got {val!r}"


@case("4th call with yield=0.7 vs prior avg=0.5 --> +20.0 pp")
def case_positive_delta(client):
    reset_state()
    # 3 priors with yield=0.5 (5 items / 10 cards each).
    for _ in range(3):
        post_extract(client, "https://reddit.com/r/x", cards_count=10, items_count=5)
    r = post_extract(client, "https://reddit.com/r/x", cards_count=10, items_count=7)
    assert r.status_code == 200
    val = r.headers.get("X-Host-Yield-Delta-Pct")
    assert val == "+20.0", f"expected +20.0, got {val!r}"


@case("mode != card_iteration --> header OMITTED (no buffer write either)")
def case_wrong_mode(client):
    reset_state()
    # Build up a baseline first.
    for _ in range(3):
        post_extract(client, "https://www.linkedin.com/feed/", cards_count=10, items_count=8)
    # Now call WITHOUT mode=card_iteration (and without cards).
    with mock.patch("bridge_server.requests.post", return_value=fake_ollama_response([{"a": 1}])):
        r = client.post(
            "/api/cowork/extract-structured",
            data=json.dumps({
                "intent": "extract",
                "html_or_text": "<html>x</html>",
                "url": "https://www.linkedin.com/feed/",
            }),
            content_type="application/json",
        )
    assert r.status_code == 200
    assert "X-Host-Yield-Delta-Pct" not in r.headers, (
        f"non-card_iteration must NOT emit the header"
    )


@case("unknown host (no url) --> header OMITTED even with priors")
def case_no_url(client):
    reset_state()
    # 3 priors WITH url so the per-host history has an entry under "" host.
    # Then a 4th call without url --> empty host string, gate fails.
    # Per-host entries are keyed by normalised host, "" is empty so the
    # _compute_host_yield_delta_pct gate trips on `not host`.
    for _ in range(3):
        post_extract(client, "https://example.com/feed", cards_count=10, items_count=8)
    # Same 4th call WITHOUT url field in the payload.
    cards = [{"idx": i, "outerHTML": f"<div>{i}</div>"} for i in range(10)]
    with mock.patch("bridge_server.requests.post", return_value=fake_ollama_response([{"a": 1}, {"a": 2}])):
        r = client.post(
            "/api/cowork/extract-structured",
            data=json.dumps({
                "intent": "extract",
                "html_or_text": "<html>x</html>",
                "mode": "card_iteration",
                "cards": cards,
                # url intentionally absent
            }),
            content_type="application/json",
        )
    assert r.status_code == 200
    assert "X-Host-Yield-Delta-Pct" not in r.headers


@case("cards_processed < 5 --> header OMITTED (statistical floor)")
def case_too_few_cards(client):
    reset_state()
    # Build baseline with 10-card extracts.
    for _ in range(3):
        post_extract(client, "https://github.com/orgs/x/discussions", cards_count=10, items_count=8)
    # Now extract with only 4 cards --> below the 5-card floor.
    r = post_extract(client, "https://github.com/orgs/x/discussions", cards_count=4, items_count=2)
    assert r.status_code == 200
    assert "X-Host-Yield-Delta-Pct" not in r.headers, (
        f"<5 cards must NOT emit the header, got {r.headers.get('X-Host-Yield-Delta-Pct')!r}"
    )


@case("different hosts maintain independent histories")
def case_independent_histories(client):
    reset_state()
    # 3 priors for linkedin (avg 0.8), 3 priors for reddit (avg 0.4).
    for _ in range(3):
        post_extract(client, "https://www.linkedin.com/feed/", cards_count=10, items_count=8)
    for _ in range(3):
        post_extract(client, "https://reddit.com/r/x", cards_count=10, items_count=4)
    # 4th call on linkedin with 0.7 --> delta = (0.7 - 0.8) * 100 = -10.0
    r1 = post_extract(client, "https://www.linkedin.com/feed/", cards_count=10, items_count=7)
    assert r1.headers.get("X-Host-Yield-Delta-Pct") == "-10.0", (
        f"linkedin delta={r1.headers.get('X-Host-Yield-Delta-Pct')!r}"
    )
    # 4th call on reddit with 0.6 --> delta = (0.6 - 0.4) * 100 = +20.0
    r2 = post_extract(client, "https://reddit.com/r/x", cards_count=10, items_count=6)
    assert r2.headers.get("X-Host-Yield-Delta-Pct") == "+20.0", (
        f"reddit delta={r2.headers.get('X-Host-Yield-Delta-Pct')!r}"
    )


@case("www. prefix normalised --> same host bucket as bare domain")
def case_www_prefix(client):
    reset_state()
    # 3 priors on www.linkedin.com (yield 0.8).
    for _ in range(3):
        post_extract(client, "https://www.linkedin.com/feed/", cards_count=10, items_count=8)
    # 4th call on linkedin.com (no www) --> should hit the same bucket.
    r = post_extract(client, "https://linkedin.com/feed/", cards_count=10, items_count=4)
    assert r.headers.get("X-Host-Yield-Delta-Pct") == "-40.0", (
        f"www-normalised delta={r.headers.get('X-Host-Yield-Delta-Pct')!r}"
    )


@case("CORS expose_headers includes X-Host-Yield-Delta-Pct")
def case_cors_exposed(client):
    """Regression check : without expose_headers, browsers hide custom
    response headers from JS through CORS. Ensure the header is in the
    list so the extension can read it."""
    # The CORS init wires expose_headers as a list ; we can introspect the
    # Flask app's after_request by performing an OPTIONS preflight is ugly.
    # Instead, check the module-level CORS init by inspecting the kwargs
    # cached on the extension. Defensive : we just import the constant.
    # Look at the Flask app's CORS extension config.
    seen = False
    # flask-cors stores its config via app.extensions or similar.
    # Best : trigger a request and inspect the Access-Control-Expose-Headers
    # response header on a real request.
    reset_state()
    cards = [{"idx": i, "outerHTML": f"<div>{i}</div>"} for i in range(5)]
    with mock.patch("bridge_server.requests.post", return_value=fake_ollama_response([])):
        r = client.post(
            "/api/cowork/extract-structured",
            data=json.dumps({
                "intent": "x",
                "html_or_text": "x",
                "mode": "card_iteration",
                "cards": cards,
                "url": "https://example.com/",
            }),
            content_type="application/json",
            headers={"Origin": "http://localhost:5173"},
        )
    expose = r.headers.get("Access-Control-Expose-Headers", "")
    assert "X-Host-Yield-Delta-Pct" in expose, (
        f"X-Host-Yield-Delta-Pct missing from expose-headers: {expose!r}"
    )
    seen = True
    assert seen


def main():
    client = bridge_server.app.test_client()
    print(f"[v82m2] Running {len(CASES)} X-Host-Yield-Delta-Pct cases via Flask test_client\n")
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
