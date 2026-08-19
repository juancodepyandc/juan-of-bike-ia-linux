"""video_render — CLI unifiée de rendu vidéo (WS-V-P § parité).

Deux formes équivalentes :

    video_render.py --spec spec.json                     # rendu réel
    video_render.py --prompt "..." [--aspect ...] ...    # rendu réel
    video_render.py --prompt "..." --print-spec          # sort la spec, ne rend pas

En interne : PASSE PAR video_spec_builder pour construire une VideoJobSpec
canonique, imprime son `spec_hash` sur stdout au démarrage (utile pour
`test_video_parity.py` qui compare les hash de trois chemins produisant
« la même » vidéo), puis délègue le rendu au worker `video_generate.py`
via son contrat `--worker-config-json` — même worker, même code, quelle
que soit l'origine (CLI, bridge, tunnel).
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import video_job_spec as vjs
import video_spec_builder as vsb


def parse_args():
    p = argparse.ArgumentParser(
        prog="video_render",
        description="CLI unifiée de rendu vidéo (VideoJobSpec canonique)",
    )
    # Deux chemins mutuellement exclusifs (mais on gère à la main pour messages
    # d'erreur clairs).
    p.add_argument("--spec", type=str, default=None,
                   help="Chemin vers un fichier JSON contenant une VideoJobSpec sérialisée")
    p.add_argument("--prompt", type=str, default=None,
                   help="Texte utilisateur brut (mode intention)")

    # Intent-side (utilisé quand --prompt fourni)
    p.add_argument("--aspect", type=str, default="16:9",
                   choices=["16:9", "9:16", "1:1", "4:3"])
    p.add_argument("--duration_s", type=float, default=None)
    p.add_argument("--num_frames", type=int, default=None)
    p.add_argument("--quality_mode", type=str, default="auto",
                   choices=["auto", "balanced", "premium"])
    p.add_argument("--seed", type=int, default=None,
                   help="Forcé si fourni ; sinon dérivé du prompt de manière déterministe")
    p.add_argument("--image", dest="image_path", type=str, default=None,
                   help="Image d'ancre i2v (chemin absolu)")
    p.add_argument("--motion_suffix", type=str, default="")
    p.add_argument("--cinematography", type=str, default="")
    p.add_argument("--style_suffix", type=str, default="")
    p.add_argument("--reference_contract", type=str, default="")
    p.add_argument("--negative_prompt", type=str, default=None)
    p.add_argument("--force_strategy", type=str, default="auto",
                   choices=["auto", "wan5b", "ltx"])
    p.add_argument("--motion_interp", type=int, default=1, choices=[0, 1, 2])
    p.add_argument("--fps", type=int, default=24)

    # Sortie
    p.add_argument("--output", type=str, default=None,
                   help="Chemin mp4 de sortie (obligatoire hors --print-spec)")
    p.add_argument("--thumbnail", type=str, default=None)

    # Modes non-rendu
    p.add_argument("--print-spec", action="store_true",
                   help="Résout et imprime la spec sur stdout, ne lance PAS le rendu")
    p.add_argument("--dry-run", action="store_true",
                   help="Alias de --print-spec")

    return p.parse_args()


def load_or_build_spec(args) -> vjs.VideoJobSpec:
    if args.spec:
        path = Path(args.spec)
        if not path.exists():
            print(f"FATAL: --spec fichier introuvable: {path}", file=sys.stderr)
            sys.exit(2)
        data = json.loads(path.read_text(encoding="utf-8"))
        return vjs.from_dict(data)

    if not args.prompt:
        print("FATAL: --spec OU --prompt requis", file=sys.stderr)
        sys.exit(2)

    return vsb.build_spec_from_intent(
        prompt=args.prompt,
        aspect=args.aspect,
        duration_s=args.duration_s,
        num_frames=args.num_frames,
        quality_mode=args.quality_mode,
        seed=args.seed,
        image_path=args.image_path,
        motion_suffix=args.motion_suffix,
        cinematography=args.cinematography,
        style_suffix=args.style_suffix,
        reference_contract=args.reference_contract,
        negative_prompt=args.negative_prompt,
        force_strategy=args.force_strategy,
        motion_interp=args.motion_interp,
        fps=args.fps,
    )


def main():
    args = parse_args()
    spec = load_or_build_spec(args)

    # Le hash sort TOUJOURS sur stdout au format machine-parsable — c'est
    # ce que consomme `test_video_parity.py`.
    print(f"SPEC_HASH:{spec.spec_hash()}", flush=True)

    if args.print_spec or args.dry_run:
        print(spec.to_json(indent=2), flush=True)
        return

    if not args.output:
        print("FATAL: --output requis hors --print-spec", file=sys.stderr)
        sys.exit(2)

    # Délègue au worker existant (contrat --worker-config-json).
    output = args.output
    thumbnail = args.thumbnail or os.path.splitext(output)[0] + ".thumb.png"
    strategy = {
        "id": "wan5b-i2v-primary" if spec.image_path else "wan5b-t2v-primary",
        "family": "wan",
        "width": spec.width,
        "height": spec.height,
        "num_frames": spec.num_frames,
        "num_inference_steps": spec.num_inference_steps,
        "fps": spec.fps,
        "offload": "group_block",
        "num_blocks_per_group": 4,
    }
    worker_config = {
        "prompt": spec.prompt_composed,
        "output_path": output,
        "thumbnail_path": thumbnail,
        "image_path": spec.image_path,
        "mode": "i2v" if spec.image_path else "t2v",
        "model_id": spec.model_id,
        "strategy": strategy,
        "negative_prompt": spec.negative_prompt,
        "seed": spec.seed,
        "motion_interp": spec.motion_interp,
        "requested_frames": spec.num_frames,
        "spec_hash": spec.spec_hash(),
    }

    video_generate = HERE / "video_generate.py"
    if not video_generate.exists():
        print(f"FATAL: video_generate.py introuvable: {video_generate}", file=sys.stderr)
        sys.exit(3)

    cmd = [sys.executable, str(video_generate),
           "--worker-config-json", json.dumps(worker_config)]
    # Exécute en streaming (pas .communicate) pour laisser passer les
    # PROGRESS: du worker.
    proc = subprocess.Popen(cmd)
    rc = proc.wait()
    sys.exit(rc)


if __name__ == "__main__":
    main()
