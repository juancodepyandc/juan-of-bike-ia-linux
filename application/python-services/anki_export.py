"""anki_export — build a real .apkg file from a flashcards payload.

The TS front can already export Anki-compatible TSV, but `genanki` produces
the proper SQLite-backed .apkg that any Anki client (desktop / mobile /
AnkiDroid) imports with full notetype fidelity.

Usage (from bridge_server.py via runPythonScript) :
  python anki_export.py --out public/exports/deck.apkg --json <deck_json>

Input JSON shape :
  {
    "deck": { "name": "Maths — Dérivées", "description": "fiche BAC STI2D" },
    "cards": [
      { "front": "...", "back": "...", "tags": ["derivees", "bac"] }
    ]
  }

Output : writes the .apkg to the workspace-relative path, prints JSON on stdout.
"""
import argparse
import json
import os
import random
import sys
from pathlib import Path

WORKSPACE = str(Path(__file__).resolve().parent.parent)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, help="Workspace-relative path of the .apkg to write")
    ap.add_argument("--json", required=True, help="JSON payload as a string")
    args = ap.parse_args()

    try:
        import genanki
    except ImportError:
        print(json.dumps({
            "ok": False,
            "error": "genanki is not installed. Run: pip install genanki",
        }))
        return 2

    try:
        payload = json.loads(args.json)
    except json.JSONDecodeError as e:
        print(json.dumps({"ok": False, "error": f"bad JSON: {e}"}))
        return 3

    deck_meta = payload.get("deck") or {}
    cards = payload.get("cards") or []
    if not cards:
        print(json.dumps({"ok": False, "error": "payload contains no cards"}))
        return 4

    deck_name = (deck_meta.get("name") or "juan of bike IA — Deck").strip()
    deck_desc = deck_meta.get("description") or ""
    # Deterministic deck id from name so re-exporting the same deck updates
    # instead of duplicating on the client side.
    deck_id = abs(hash(deck_name)) % (1 << 30) + 2**30
    model_id = abs(hash("aurora-basic-v1")) % (1 << 30) + 2**30

    # Basic front/back notetype with HTML allowed (matches our TSV path).
    model = genanki.Model(
        model_id,
        "Aurora Basic",
        fields=[
            {"name": "Front"},
            {"name": "Back"},
        ],
        templates=[
            {
                "name": "Card 1",
                "qfmt": "{{Front}}",
                "afmt": '{{FrontSide}}<hr id="answer">{{Back}}',
            },
        ],
        css="""
        .card {
          font-family: 'Inter', -apple-system, system-ui, sans-serif;
          font-size: 18px;
          color: #1a0f05;
          background: #ecdcb0;
          text-align: left;
          padding: 20px 14px;
          line-height: 1.5;
        }
        b { color: #b5241e; }
        i { color: #6b523a; }
        hr#answer { border: 0; border-top: 2px dashed #1a0f05; margin: 14px 0; }
        """,
    )

    deck = genanki.Deck(deck_id, deck_name, description=deck_desc)
    for i, card in enumerate(cards):
        front = str(card.get("front") or "").strip()
        back  = str(card.get("back")  or "").strip()
        tags  = card.get("tags") or []
        if not front:
            continue
        note = genanki.Note(
            model=model,
            fields=[front, back],
            tags=[str(t).replace(" ", "_") for t in tags if t],
            # Deterministic guid per (deck_name, position) so reimport updates
            guid=genanki.guid_for(f"{deck_name}-{i}"),
        )
        deck.add_note(note)

    if not deck.notes:
        print(json.dumps({"ok": False, "error": "after filtering, no valid notes to export"}))
        return 5

    out_abs = os.path.abspath(os.path.join(WORKSPACE, args.out))
    os.makedirs(os.path.dirname(out_abs), exist_ok=True)
    package = genanki.Package(deck)
    try:
        package.write_to_file(out_abs)
    except Exception as e:
        print(json.dumps({"ok": False, "error": f"write failed: {e}"}))
        return 6

    url = "/" + os.path.relpath(out_abs, os.path.join(WORKSPACE, "public")).replace(os.sep, "/") \
        if out_abs.startswith(os.path.join(WORKSPACE, "public") + os.sep) else None
    print(json.dumps({
        "ok": True,
        "path": out_abs,
        "url": url,
        "cards": len(deck.notes),
        "deck_name": deck_name,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    # genanki imports shuffle when building, keep it deterministic per run
    random.seed(1)
    sys.exit(main())
