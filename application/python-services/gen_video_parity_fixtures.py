"""Génère un fixture d'intents + spec_hash attendus pour le test de parité
TS↔Python (`src/__tests__/videoSpecParity.test.ts`).

Le fichier écrit est la SEULE source de vérité pour ce test — le TS le charge
et compare ses hashes à ceux consignés ici. À régénérer chaque fois qu'une
règle du builder ou du contrat spec change (le hash change alors partout et
c'est exactement ce qu'on veut détecter).

Usage :
    /home/juan/AuroraIA/application/.venv/bin/python \\
        /home/juan/AuroraIA/application/python-services/gen_video_parity_fixtures.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import video_spec_builder as vsb

OUT = HERE.parent / "src" / "__tests__" / "fixtures" / "video-spec-hashes.json"

INTENTS = [
    # Cas simple 16:9 balanced
    dict(prompt="a red bike rolling down a hill", aspect="16:9",
         duration_s=3.0, quality_mode="balanced"),
    # Portrait premium
    dict(prompt="the young boy turns his head, gentle wind", aspect="9:16",
         duration_s=2.5, quality_mode="premium"),
    # Seed explicite (pas de dérivation)
    dict(prompt="a cat sits still", aspect="1:1",
         duration_s=1.5, quality_mode="auto", seed=1031),
    # num_frames explicite au lieu de duration
    dict(prompt="fireflies drift", aspect="16:9",
         num_frames=41, quality_mode="premium",
         motion_suffix="soft parallax pan"),
    # Avec image_path et negative_prompt
    dict(prompt="a lantern swings in wind", aspect="4:3",
         duration_s=2.0, quality_mode="premium",
         image_path="/tmp/anchor.png",
         negative_prompt="blurry, watermark"),
    # Longueur prompt qui teste FNV-1a sur un texte plus long
    dict(prompt=("a wide cinematic shot of an ancient library at dusk, "
                 "dust motes drifting through shafts of golden light, "
                 "gentle camera glide from left to right, real physics"),
         aspect="16:9", duration_s=4.0, quality_mode="premium",
         cinematography="wide shot", style_suffix="cinematic realism"),
    # motion_suffix change → seed change (même prompt utilisateur)
    dict(prompt="wind in tall grass", aspect="16:9",
         duration_s=3.0, quality_mode="balanced",
         motion_suffix="handheld micro-parallax"),
    dict(prompt="wind in tall grass", aspect="16:9",
         duration_s=3.0, quality_mode="balanced",
         motion_suffix="locked static camera"),
]


def main() -> None:
    entries = []
    for intent in INTENTS:
        spec = vsb.build_spec_from_intent(**intent)
        entries.append({
            "intent": intent,
            "expected_spec_hash": spec.spec_hash(),
            # Sub-set de champs résolus utile pour diagnostic (ne participent
            # pas à la comparaison mais aident à voir pourquoi ça diverge).
            "resolved": {
                "prompt_composed": spec.prompt_composed,
                "width": spec.width,
                "height": spec.height,
                "delivered_width": spec.delivered_width,
                "delivered_height": spec.delivered_height,
                "num_frames": spec.num_frames,
                "fps": spec.fps,
                "num_inference_steps": spec.num_inference_steps,
                "guidance_scale": spec.guidance_scale,
                "seed": spec.seed,
            },
        })

    payload = {
        "spec_version": vsb.vjs.SPEC_VERSION if hasattr(vsb, "vjs") else __import__("video_job_spec").SPEC_VERSION,
        "count": len(entries),
        "entries": entries,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {len(entries)} fixtures → {OUT}")


if __name__ == "__main__":
    main()
