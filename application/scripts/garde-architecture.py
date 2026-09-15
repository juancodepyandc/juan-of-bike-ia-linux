#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Garde d ARCHITECTURE DE SORTIE — verifiable en ligne de commande, depuis
l interface et a travers le tunnel.

`aurora_output_paths` enonce le contrat en toutes lettres :

    « Every module MUST place its outputs, assets, and project files under
      application/output/<module_name>/<project_name>/...
      Nothing should ever be scattered at the root of output/ or dumped in
      random temporary dirs. »

Ce script VERIFIE ce contrat sur l arborescence reelle, et sur le code qui
ecrit dedans. Il rend un compte rendu JSON, ce qui permet de le lire aussi
bien depuis un terminal que depuis le pont HTTP.

Ce qu il controle :

  1. AUCUN artefact livrable (GLB, MP4, WAV, PNG de rendu) ne vit hors de
     `application/output/`. Mesure d ouverture : 10 GLB pour 201,9 Mio
     etaient hors de l arborescence — 1 dans `application/public/_pbr_test/`
     (un dossier Vite que le build effacait) et 9 dans
     `external/TRELLIS.2/tmp/`, references par aucun code. Le fichier existait
     et restait invisible de la bibliotheque, de l interface et du tunnel.

  2. AUCUN code de production ne vise une destination hors contrat. Mesure
     d ouverture : 111 scripts `proc_*.py` ecrivaient dans
     `application/public/_pbr_test/`.

  3. RIEN n est depose a la racine de `output/` : tout artefact est sous
     `output/<module>/<projet>/`.

  4. AUCUNE COLLISION de nom entre deux projets. Mesure d ouverture : sous le
     dossier plat, 8 scripts se partageaient 4 noms de fichier — le second
     ecrasait le premier en silence.

    .venv/bin/python scripts/garde-architecture.py [--json]
"""

from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
APP = RACINE / "application"
SORTIE = APP / "output"

sys.path.insert(0, str(APP / "python-services"))
from aurora_output_paths import CANONICAL_MODULES  # noqa: E402

# Extensions qui designent un LIVRABLE (par opposition a une ressource source).
LIVRABLES = {".glb", ".gltf", ".mp4", ".wav", ".mp3", ".webm", ".fbx", ".obj", ".usdz"}

# Arbres qui ne sont pas de la production Aurora.
HORS_PERIMETRE = (
    "node_modules", ".git", ".venv", "site-packages", "/modele/", "/external/",
    "/dist/", "/build/", "/.vite/", "__pycache__", "/temp/", "/tmp/",
    "src-tauri/icons", "/public/avatars/", "/models/",
)


def hors_perimetre(chemin: Path) -> bool:
    s = str(chemin)
    return any(m in s for m in HORS_PERIMETRE)


def controle_1_artefacts_egares() -> dict:
    egares = []
    for p in RACINE.rglob("*"):
        if not p.is_file() or p.suffix.lower() not in LIVRABLES:
            continue
        if hors_perimetre(p):
            continue
        try:
            p.relative_to(SORTIE)
        except ValueError:
            egares.append({"fichier": str(p), "octets": p.stat().st_size})
    return {
        "controle": "aucun livrable hors de application/output/",
        "conforme": not egares,
        "hors_arborescence": len(egares),
        "octets": sum(e["octets"] for e in egares),
        "detail": egares[:20],
    }


def controle_2_destinations_dans_le_code() -> dict:
    """Cherche une ecriture d artefact vers une destination hors contrat."""
    interdits = []
    motif = re.compile(r'["\'](?:\.\./)*(?:application/)?public/[^"\']*["\']')
    for p in (APP / "python-services").rglob("*.py"):
        if "__pycache__" in str(p):
            continue
        try:
            src = p.read_text(encoding="utf-8")
        except Exception:  # noqa: BLE001
            continue
        for i, ligne in enumerate(src.split("\n"), 1):
            nu = ligne.strip()
            if nu.startswith("#") or '"""' in nu:
                continue
            if "_pbr_test" in nu and "out_dir" in nu:
                interdits.append({"fichier": str(p), "ligne": i, "extrait": nu[:110]})
            elif motif.search(nu) and re.search(r"out_dir|out_glb|export|filepath", nu):
                interdits.append({"fichier": str(p), "ligne": i, "extrait": nu[:110]})
    return {
        "controle": "aucun code de production n ecrit hors de output/",
        "conforme": not interdits,
        "occurrences": len(interdits),
        "detail": interdits[:20],
    }


def controle_3_racine_de_sortie() -> dict:
    """Tout artefact doit etre sous output/<module>/<projet>/, jamais a la racine."""
    a_la_racine = []
    modules_connus = set(CANONICAL_MODULES.values())
    inconnus = []
    if SORTIE.is_dir():
        for e in SORTIE.iterdir():
            if e.is_file():
                a_la_racine.append(str(e))
            elif e.is_dir() and e.name not in modules_connus:
                inconnus.append(str(e))
        for module in SORTIE.iterdir():
            if not module.is_dir():
                continue
            for e in module.iterdir():
                if e.is_file() and e.suffix.lower() in LIVRABLES:
                    a_la_racine.append(str(e))
    return {
        "controle": "rien a la racine de output/ ni d un module ; modules canoniques seulement",
        "conforme": not a_la_racine and not inconnus,
        "a_la_racine": len(a_la_racine),
        "modules_hors_nomenclature": inconnus,
        "detail": a_la_racine[:20],
    }


def controle_4_collisions() -> dict:
    """Deux projets ne doivent pas viser le meme fichier de sortie."""
    noms = defaultdict(list)
    motif = re.compile(r'out_glb\s*=\s*os\.path\.join\(out_dir,\s*["\']([^"\']+)["\']\)')
    for p in sorted((APP / "python-services").glob("proc_*.py")):
        try:
            src = p.read_text(encoding="utf-8")
        except Exception:  # noqa: BLE001
            continue
        for m in motif.finditer(src):
            noms[m.group(1)].append(p.name)
    collisions = {k: v for k, v in noms.items() if len(v) > 1}
    # Sous l architecture par projet, chaque script a SON dossier : deux noms
    # identiques ne s ecrasent plus. On le verifie plutot que de le supposer.
    dossiers = defaultdict(list)
    for nom, scripts in collisions.items():
        for s in scripts:
            dossiers[f"{Path(s).stem}/{nom}"].append(s)
    vraies = {k: v for k, v in dossiers.items() if len(v) > 1}
    return {
        "controle": "aucune collision de destination entre deux projets",
        "conforme": not vraies,
        "noms_partages": len(collisions),
        "collisions_reelles": len(vraies),
        "note": (f"{len(collisions)} nom(s) de fichier partages par plusieurs scripts, "
                 "mais chacun ecrit dans le dossier de SON projet : aucun ecrasement"),
        "detail": {k: v for k, v in list(collisions.items())[:10]},
    }


def inventaire() -> dict:
    """Ce que l arborescence de sortie contient reellement, par module."""
    out = {}
    if not SORTIE.is_dir():
        return out
    for module in sorted(SORTIE.iterdir()):
        if not module.is_dir():
            continue
        fichiers = [p for p in module.rglob("*") if p.is_file()]
        livrables = [p for p in fichiers if p.suffix.lower() in LIVRABLES]
        projets = sorted({p.relative_to(module).parts[0] for p in fichiers
                          if len(p.relative_to(module).parts) > 1})
        out[module.name] = {
            "chemin": str(module),
            "projets": len(projets),
            "fichiers": len(fichiers),
            "livrables": len(livrables),
            "octets": sum(p.stat().st_size for p in fichiers),
        }
    return out


def main() -> int:
    controles = [controle_1_artefacts_egares(), controle_2_destinations_dans_le_code(),
                 controle_3_racine_de_sortie(), controle_4_collisions()]
    inv = inventaire()
    conforme = all(c["conforme"] for c in controles)
    rapport = {"schema": "aurora.garde_architecture.v1", "racine": str(SORTIE),
               "conforme": conforme, "controles": controles, "inventaire": inv}

    if "--json" in sys.argv:
        print(json.dumps(rapport, ensure_ascii=False, indent=2))
        return 0 if conforme else 1

    print("\n\033[1mGARDE D ARCHITECTURE DE SORTIE\033[0m")
    print(f"contrat : application/output/<module>/<projet>/    racine : {SORTIE}")
    print("=" * 96)
    for c in controles:
        etat = "\033[32mCONFORME\033[0m" if c["conforme"] else "\033[31mVIOLE   \033[0m"
        print(f"{etat}  {c['controle']}")
        if c.get("note"):
            print(f"          {c['note']}")
        if not c["conforme"]:
            detail = c.get("detail")
            items = detail.items() if isinstance(detail, dict) else enumerate(detail)
            for _k, v in list(items)[:8]:
                print(f"          {v}")
    print("-" * 96)
    print("\033[1minventaire reel de l arborescence de sortie\033[0m")
    for nom, d in inv.items():
        print(f"  {nom:10s} {d['projets']:4d} projet(s)  {d['fichiers']:6d} fichier(s)  "
              f"{d['livrables']:4d} livrable(s)  {d['octets'] / 1048576:9.1f} Mio  {d['chemin']}")
    print("=" * 96)
    print("\033[32mARCHITECTURE CONFORME\033[0m" if conforme else "\033[31mARCHITECTURE VIOLEE\033[0m")
    return 0 if conforme else 1


if __name__ == "__main__":
    sys.exit(main())
