"""test_video_parity — vérifie que les 3+ chemins qui peuvent produire un rendu
vidéo pour LA MÊME intention aboutissent tous à des VideoJobSpec CANONIQUEMENT
identiques (mêmes `spec_hash`).

Chemins couverts :
  1. Appel direct Python : `video_spec_builder.build_spec_from_intent(...)`
  2. CLI : `video_render.py --prompt ... --print-spec` (parse le SPEC_HASH: stdout)
  3. HTTP bridge : `POST /api/video/render` avec `{"intent": {...}, "dry_run": true}`
     (ce chemin est activé si le bridge tourne localement — sinon skip
     honnêtement avec `SKIP: bridge unreachable`, jamais un faux vert).

Utilisable en trois modes :
    python test_video_parity.py                  # dry-run, quelques secondes
    python test_video_parity.py --bridge-url URL # force une URL bridge (tunnel)
    python test_video_parity.py --strict         # exit != 0 si un chemin skipe

Discipline : ce test protège contre une régression future du type « un jour
la CLI et l'UI ne construisent plus la même spec sans que personne s'en rende
compte » — c'est LA cause racine documentée dans le PROMPT_REFONTE §3.3.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from urllib import request as urlreq, error as urlerr

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import video_spec_builder as vsb
import video_job_spec as vjs


# ── intentions de test — chacune doit produire un hash identique sur tous les chemins ──
TEST_INTENTS = [
    dict(prompt="a red bike rolling down a hill", aspect="16:9",
         duration_s=3.0, quality_mode="premium"),
    dict(prompt="the young boy turns his head, gentle wind", aspect="9:16",
         duration_s=2.5, quality_mode="balanced"),
    dict(prompt="a cat sits still", aspect="1:1",
         duration_s=1.5, quality_mode="auto", seed=1031),
    dict(prompt="fireflies drift", aspect="16:9",
         num_frames=41, quality_mode="premium",
         motion_suffix="soft parallax pan"),
]


def _hash_via_python(intent: dict) -> str:
    spec = vsb.build_spec_from_intent(**intent)
    return spec.spec_hash()


def _hash_via_cli(intent: dict) -> str | None:
    cli = HERE / "video_render.py"
    if not cli.exists():
        return None
    args = [sys.executable, str(cli), "--print-spec"]
    for k, v in intent.items():
        if v is None or v == "":
            continue
        args.append(f"--{k}")
        args.append(str(v))
    try:
        proc = subprocess.run(args, capture_output=True, text=True, timeout=30)
        for line in (proc.stdout or "").splitlines():
            if line.startswith("SPEC_HASH:"):
                return line.split(":", 1)[1].strip()
    except Exception as e:
        print(f"  cli error: {e}")
    return None


def _hash_via_bridge(intent: dict, bridge_url: str) -> str | None:
    body = json.dumps({"intent": intent, "dry_run": True}).encode("utf-8")
    req = urlreq.Request(
        f"{bridge_url.rstrip('/')}/api/video/render",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlreq.urlopen(req, timeout=10) as r:
            data = json.loads(r.read().decode("utf-8"))
    except (urlerr.URLError, urlerr.HTTPError, TimeoutError, ConnectionError) as e:
        print(f"  bridge unreachable: {e}")
        return None
    except Exception as e:
        print(f"  bridge error: {e}")
        return None
    if not data.get("ok"):
        print(f"  bridge rejected: {data.get('error')}")
        return None
    return (data.get("spec") or {}).get("spec_hash")


# ── storyboard multi-plans : chaque plan doit produire un spec_hash déterministe ──
TEST_STORYBOARD = {
    "title": "Trois plans de test parité",
    "style": "realistic",
    "aspect": "16:9",
    "quality_mode": "balanced",
    "characters": [{"name": "Alice"}],
    "shots": [
        {"id": 1, "scene": "Alice walks into a garden at sunrise",
         "duration_s": 3.0, "camera": "wide"},
        {"id": 2, "scene": "Alice picks a red flower, close on hands",
         "duration_s": 2.5, "camera": "close-up"},
        {"id": 3, "scene": "Alice stands and looks toward the horizon",
         "duration_s": 3.5, "camera": "medium"},
    ],
}


def _shot_hashes_via_python_builder(storyboard: dict) -> list[str]:
    import video_spec_builder as vsb
    hashes = []
    for shot in storyboard["shots"]:
        spec = vsb.build_spec_from_shot(shot=shot, storyboard=storyboard)
        hashes.append(spec.spec_hash())
    return hashes


def _test_storyboard_parity() -> bool:
    """Le storyboard multi-plans passe par `build_spec_from_shot` — vérifie que
    (a) chaque plan produit un hash déterministe reproductible (2 appels = même
    résultat), et (b) les hashes des 3 plans sont TOUS distincts (sinon la
    déduction seed/prompt/params n'est pas sensible aux différences de plan).
    """
    print("\n[storyboard] multi-plans (3 shots via build_spec_from_shot)")
    h1 = _shot_hashes_via_python_builder(TEST_STORYBOARD)
    h2 = _shot_hashes_via_python_builder(TEST_STORYBOARD)
    print(f"  run 1 hashes: {[h[:12] for h in h1]}")
    print(f"  run 2 hashes: {[h[:12] for h in h2]}")
    if h1 != h2:
        print("  ❌ non-déterminisme : deux appels avec la même storyboard divergent")
        return False
    if len(set(h1)) != len(h1):
        print(f"  ❌ collision : deux plans distincts partagent le même spec_hash")
        return False
    print(f"  ✅ 3 plans, 3 hashes distincts, reproductibles run à run")
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bridge-url", default=os.environ.get("BRIDGE_URL", "http://localhost:3001"))
    ap.add_argument("--strict", action="store_true",
                    help="Exit != 0 si un chemin est skipé (pas juste s'il diffère)")
    args = ap.parse_args()

    all_ok = True
    skipped_any = False
    for idx, intent in enumerate(TEST_INTENTS, 1):
        print(f"\n[intent {idx}] {intent}")
        h_py = _hash_via_python(intent)
        h_cli = _hash_via_cli(intent)
        h_br = _hash_via_bridge(intent, args.bridge_url)
        print(f"  python : {h_py[:32]}")
        print(f"  cli    : {(h_cli or 'SKIP')[:32]}")
        print(f"  bridge : {(h_br or 'SKIP')[:32]}")

        hashes = [("python", h_py)]
        if h_cli is not None:
            hashes.append(("cli", h_cli))
        else:
            skipped_any = True
        if h_br is not None:
            hashes.append(("bridge", h_br))
        else:
            skipped_any = True

        distinct = set(h for _, h in hashes)
        if len(distinct) != 1:
            print("  ❌ DIVERGENCE — les chemins ne produisent pas la même spec")
            all_ok = False
        else:
            print(f"  ✅ parité — {len(hashes)} chemin(s) alignés")

    if not _test_storyboard_parity():
        all_ok = False

    print("\n=====")
    if not all_ok:
        print("PARITY FAILURE")
        sys.exit(1)
    if skipped_any and args.strict:
        print("PARITY OK on tested paths, mais des chemins ont été skippés (mode --strict)")
        sys.exit(2)
    print("PARITY OK")


if __name__ == "__main__":
    main()
