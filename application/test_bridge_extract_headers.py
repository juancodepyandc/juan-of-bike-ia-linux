#!/usr/bin/env python3
"""
v82m0 — Live test for the X-Cards-Processed and X-Items-Extracted response
headers on /api/cowork/extract-structured. Uses Flask test_client so we can
run offline (no Ollama, no real bridge process). We mock the Ollama HTTP
call via requests-mock OR by stubbing requests.post directly so the route
hits the response header emission path with a controlled items[] payload.

Run :
    python application/test_bridge_extract_headers.py

Exits 0 on success, 1 on any assertion failure. Prints a summary table.
"""
import json
import sys
import os
import unittest.mock as mock

# Ensure we import the bridge_server from this directory.
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import bridge_server  # noqa: E402

CASES = []


def case(name):
    """Decorator that registers a callable as a numbered case."""
    def deco(fn):
        CASES.append((name, fn))
        return fn
    return deco


def fake_ollama_response(items_list):
    """Build a Mock response shaped like requests.post(...)."""
    resp = mock.MagicMock()
    resp.status_code = 200
    resp.text = ""
    resp.json.return_value = {
        "message": {"content": json.dumps({"items": items_list, "schema": "auteur,contenu", "notes": ""})},
    }
    return resp


def post(client, payload):
    return client.post(
        "/api/cowork/extract-structured",
        data=json.dumps(payload),
        content_type="application/json",
    )


@case("card_iteration with cards=[3 entries] + items=[2] --> both headers, X-Items-Extracted=2")
def case_two_extracted(client):
    cards = [
        {"idx": i, "outerHTML": f"<div>card {i}</div>"} for i in range(3)
    ]
    with mock.patch("bridge_server.requests.post", return_value=fake_ollama_response([{"a": 1}, {"a": 2}])):
        r = post(client, {
            "intent": "extract recent posts",
            "html_or_text": "<html>fallback</html>",
            "mode": "card_iteration",
            "cards": cards,
        })
    assert r.status_code == 200, f"unexpected status {r.status_code} body={r.data[:200]!r}"
    assert r.headers.get("X-Cards-Processed") == "3", f"X-Cards-Processed={r.headers.get('X-Cards-Processed')!r}"
    assert r.headers.get("X-Items-Extracted") == "2", f"X-Items-Extracted={r.headers.get('X-Items-Extracted')!r}"
    body = r.get_json()
    assert body["ok"] is True
    assert body["cards_processed"] == 3, f"body cards_processed={body.get('cards_processed')}"


@case("card_iteration with cards=[5] + items=[] --> headers present, X-Items-Extracted=0")
def case_zero_extracted(client):
    cards = [
        {"idx": i, "outerHTML": f"<div>{i}</div>"} for i in range(5)
    ]
    with mock.patch("bridge_server.requests.post", return_value=fake_ollama_response([])):
        r = post(client, {
            "intent": "extract feed",
            "html_or_text": "fallback",
            "mode": "card_iteration",
            "cards": cards,
        })
    assert r.status_code == 200, f"status={r.status_code}"
    assert r.headers.get("X-Cards-Processed") == "5"
    assert r.headers.get("X-Items-Extracted") == "0", "empty items must emit X-Items-Extracted: 0"


@case("mode missing --> headers OMITTED (legacy shape preserved)")
def case_no_mode(client):
    with mock.patch("bridge_server.requests.post", return_value=fake_ollama_response([{"x": 1}])):
        r = post(client, {
            "intent": "free extraction",
            "html_or_text": "<html><p>hello</p></html>",
        })
    assert r.status_code == 200
    assert "X-Cards-Processed" not in r.headers, "X-Cards-Processed must be omitted when mode missing"
    assert "X-Items-Extracted" not in r.headers, "X-Items-Extracted must be omitted when mode missing"


@case("mode != card_iteration --> headers OMITTED")
def case_wrong_mode(client):
    cards = [{"idx": 0, "outerHTML": "<div>x</div>"}]
    with mock.patch("bridge_server.requests.post", return_value=fake_ollama_response([{"a": 1}])):
        r = post(client, {
            "intent": "free",
            "html_or_text": "fallback",
            "mode": "list_items",  # not card_iteration
            "cards": cards,
        })
    assert r.status_code == 200
    assert "X-Cards-Processed" not in r.headers
    assert "X-Items-Extracted" not in r.headers


@case("card_iteration with mode set but cards=[] --> headers OMITTED (no per-card stream)")
def case_no_cards(client):
    with mock.patch("bridge_server.requests.post", return_value=fake_ollama_response([{"a": 1}])):
        r = post(client, {
            "intent": "extract feed",
            "html_or_text": "fallback content",
            "mode": "card_iteration",
            "cards": [],  # empty array --> bridge has nothing to count
        })
    # The bridge already gates `cards_processed` on `cards != []` ; mirror.
    assert r.status_code == 200
    assert "X-Cards-Processed" not in r.headers, "without cards stream, no per-card telemetry to surface"


@case("CORS expose_headers contains X-Cards-Processed and X-Items-Extracted")
def case_cors_exposed(client):
    # We can't probe CORS from inside the same origin via test_client easily,
    # but we CAN verify the Flask-CORS extension was configured to expose
    # both headers (avoids regression on the expose_headers list).
    cors = bridge_server.CORS  # the imported decorator class — used only for source identity
    assert cors is not None
    # The actual config is on the Flask app — flask-cors stores it in
    # `_cors_options` when `CORS(app, ...)` was called. Easiest assert : do a
    # CORS preflight OPTIONS and inspect Access-Control-Expose-Headers.
    r = client.options(
        "/api/cowork/extract-structured",
        headers={
            "Origin": "https://chrome-extension-id",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    expose = r.headers.get("Access-Control-Expose-Headers", "")
    # Note : `Expose-Headers` is sometimes only emitted on actual responses
    # (not preflight). Flask-CORS does emit it on preflight when expose_headers
    # is set. If absent, fall through to a real POST and inspect.
    if not expose:
        with mock.patch("bridge_server.requests.post", return_value=fake_ollama_response([{"a": 1}])):
            r2 = post(client, {
                "intent": "test",
                "html_or_text": "x",
                "mode": "card_iteration",
                "cards": [{"idx": 0, "outerHTML": "<div>1</div>"}],
            })
        expose = r2.headers.get("Access-Control-Expose-Headers", "")
    assert "X-Cards-Processed" in expose, f"expose_headers missing X-Cards-Processed : {expose!r}"
    assert "X-Items-Extracted" in expose, f"expose_headers missing X-Items-Extracted : {expose!r}"


def main():
    client = bridge_server.app.test_client()
    print(f"[v82m0] Running {len(CASES)} extract-structured header cases via Flask test_client\n")
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
