#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""livraison_organisee — range un run 3D en arborescence CLAIRE.

Le probleme constate (run guerrier): TOUT etait melange dans models/ (GLB +
photos + prompt en double), references/ ne contenait que des vues abandonnees,
et la moitie des dossiers n'avait aucune utilite lisible. Regle de Juan: chaque
chose a UN dossier comprehensible, les refus sont supprimes, pas de doublon.

Arborescence livree (noms en francais, stables):
    <run>/
      prompt/       le prompt (un seul exemplaire)
      reference/    UNIQUEMENT les images retenues (face + vues derivees)
      modele/       modele_couleurs.glb + modele_geometrie.glb + GEOMETRIE.png
      mouvement/    mouvement_couleurs.glb + mouvement_geometrie.glb
                    + MOUVEMENT_GEOMETRIE.png (+ composite/ si demande)
      journal/      audit.json, manifeste — ce qui s'est passe, pour relecture
      travail/      TOUS les intermediaires (bruts, essais, caches) — peut se
                    supprimer sans rien perdre de la livraison

La version "geometrie" d'un GLB = le meme maillage (et la meme animation pour
le mouvement) SANS materiaux ni textures: la geometrie pure se juge sans que
les couleurs maquillent les defauts.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path


def _glb_sans_materiaux(src: str | Path, dst: str | Path) -> dict:
    """Copie un GLB en retirant materiaux/textures/images (geometrie pure).

    pygltflib seulement — pas de Blender: on garde sommets, normales et
    ANIMATIONS intacts, on detache juste toute matiere. Les accessors des
    images restent dans le binaire (inoffensif); l'important est qu'aucune
    primitive ne reference plus de materiau.
    """
    try:
        from pygltflib import GLTF2
        g = GLTF2().load(str(src))
        for mesh in g.meshes or []:
            for prim in mesh.primitives or []:
                prim.material = None
        g.materials = []
        g.textures = []
        g.images = []
        g.samplers = []
        g.save(str(dst))
        return {"ok": True, "fichier": str(dst)}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": repr(exc)}


def organiser(run_dir: str | Path, run_id: str, *,
              final_mesh: str | None = None,
              rigged_mesh: str | None = None,
              front_reference: str | None = None) -> dict:
    """Range le run. Idempotent, best-effort: ne casse jamais la livraison.

    Tout fichier du niveau racine / models/ qui n'est pas un livrable part
    dans travail/. Les livrables sont DEPLACES (pas copies: zero doublon).
    """
    run_dir = Path(run_dir)
    if not run_dir.is_dir():
        return {"ok": False, "error": "run_dir absent: %s" % run_dir}
    d_prompt = run_dir / "prompt"
    d_ref = run_dir / "reference"
    d_modele = run_dir / "modele"
    d_mouv = run_dir / "mouvement"
    d_journal = run_dir / "journal"
    d_travail = run_dir / "travail"
    # mouvement/ n'existe QUE si une animation a ete produite (option cochee):
    # un dossier vide pour un modele statique est du bruit.
    avec_mouvement = bool(rigged_mesh and Path(rigged_mesh).is_file())
    dossiers = [d_prompt, d_ref, d_modele, d_journal, d_travail]
    if avec_mouvement:
        dossiers.append(d_mouv)
    for d in dossiers:
        d.mkdir(parents=True, exist_ok=True)

    deplaces: list[str] = []

    def _mv(src: Path, dst: Path) -> Path | None:
        try:
            if src.is_file() and src.resolve() != dst.resolve():
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(src), str(dst))
                deplaces.append("%s -> %s" % (src.name, dst.relative_to(run_dir)))
                return dst
        except Exception:  # noqa: BLE001
            pass
        return dst if dst.is_file() else None

    # 1) LIVRABLES nommes clairement
    livraison: dict = {}
    if final_mesh and Path(final_mesh).is_file():
        p = _mv(Path(final_mesh), d_modele / "modele_couleurs.glb")
        if p:
            livraison["modele_couleurs"] = str(p)
            geo = _glb_sans_materiaux(p, d_modele / "modele_geometrie.glb")
            if geo.get("ok"):
                livraison["modele_geometrie"] = geo["fichier"]
    if rigged_mesh and Path(rigged_mesh).is_file():
        p = _mv(Path(rigged_mesh), d_mouv / "mouvement_couleurs.glb")
        if p:
            livraison["mouvement_couleurs"] = str(p)
            geo = _glb_sans_materiaux(p, d_mouv / "mouvement_geometrie.glb")
            if geo.get("ok"):
                livraison["mouvement_geometrie"] = geo["fichier"]

    # 2) REFERENCE retenue (face + vues derivees RETENUES seulement)
    if front_reference and Path(front_reference).is_file():
        p = _mv(Path(front_reference), d_ref / "face.png")
        if p:
            livraison["reference_face"] = str(p)
    for suffixe, nom in (("_reference_v2.png", "cote.png"),
                         ("_reference_v3.png", "dos.png")):
        for base in (run_dir, run_dir / "models"):
            src = base / (run_id + suffixe)
            if src.is_file():
                _mv(src, d_ref / nom)

    # 3) Planches argile / geometrie a cote de leur GLB
    cibles_planches = [(run_id + "_GEOMETRIE.png", d_modele / "GEOMETRIE.png")]
    if avec_mouvement:
        cibles_planches.append((run_id + "_MOUVEMENT_GEOMETRIE.png",
                                d_mouv / "MOUVEMENT_GEOMETRIE.png"))
    for motif, dst in cibles_planches:
        for base in (run_dir, run_dir / "models"):
            src = base / motif
            if src.is_file():
                _mv(src, dst)
    src_frames = run_dir / (run_id + "_MOUVEMENT_GEOMETRIE_frames")
    if src_frames.is_dir() and avec_mouvement:
        try:
            shutil.move(str(src_frames), str(d_mouv / "instants_argile"))
        except Exception:  # noqa: BLE001
            pass
    src_comp = run_dir / (run_id + "_COMPOSITE")
    if src_comp.is_dir() and avec_mouvement:
        try:
            shutil.move(str(src_comp), str(d_mouv / "composite"))
        except Exception:  # noqa: BLE001
            pass

    # 4) PROMPT: un seul exemplaire
    vus_prompt = False
    for base in (run_dir / "prompts", run_dir / "models", run_dir):
        src = base / (run_id + "_prompt.txt")
        if src.is_file():
            if not vus_prompt:
                _mv(src, d_prompt / "prompt.txt")
                vus_prompt = True
            else:
                src.unlink(missing_ok=True)   # doublon: supprime

    # 5) JOURNAL: manifeste + audits existants
    for src in list((run_dir / "audits").glob("*")) if (run_dir / "audits").is_dir() else []:
        _mv(src, d_journal / src.name)

    # 6) ANCIENS dossiers UI (references/ = 4 vues pre-generees ABANDONNEES:
    #    elles n'ont pas ete retenues -> supprimees, comme demande)
    old_refs = run_dir / "references"
    if old_refs.is_dir():
        try:
            # 30/07 (audit): on supprimait references/ EN BLOC — y compris la
            # PHOTO fournie par l'utilisateur sur un run UI. Sa photo est le
            # contexte de la conversation: elle part dans reference/, seules
            # les vues abandonnees disparaissent.
            for _f in old_refs.iterdir():
                if _f.is_file() and _f.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp", ".avif"):
                    if "synthetic" in _f.name or "_seed" in _f.name:
                        continue
                    shutil.copyfile(_f, d_ref / _f.name)
            shutil.rmtree(old_refs)
            deplaces.append("references/ -> photos gardees dans reference/, vues abandonnees supprimees")
        except Exception:  # noqa: BLE001
            pass

    # 7) TOUT LE RESTE (racine + models/ + work/ + rescue/ + motion/) -> travail/
    for base in (run_dir, run_dir / "models", run_dir / "work",
                 run_dir / "rescue", run_dir / "motion", run_dir / "prompts",
                 run_dir / "audits"):
        if not base.is_dir():
            continue
        for src in list(base.iterdir()):
            if src.is_dir():
                # les SOUS-DOSSIERS d'intermediaires (mia_work/, matvision/,
                # masques/, ...) restaient sur place: le run paraissait range
                # mais models/ gardait des Go de travail. Racine: on ne touche
                # jamais aux 6 dossiers de livraison.
                if base == run_dir and src.name in (
                        "prompt", "reference", "modele", "mouvement",
                        "journal", "travail", "models", "work", "rescue",
                        "motion", "prompts", "audits"):
                    continue
                try:
                    dst = d_travail / src.name
                    if not dst.exists():
                        shutil.move(str(src), str(dst))
                        deplaces.append("%s/ -> travail/" % src.name)
                except Exception:  # noqa: BLE001
                    pass
                continue
            if base == run_dir and src.parent == run_dir and src.name in (
                    "prompt", "reference", "modele", "mouvement",
                    "journal", "travail"):
                continue
            _mv(src, d_travail / src.name)
    # dossiers desormais vides -> retires
    for base in ("models", "work", "rescue", "motion", "prompts", "audits",
                 "mouvement" if not avec_mouvement else "models"):
        d = run_dir / base
        try:
            if d.is_dir() and not any(d.iterdir()):
                d.rmdir()
        except Exception:  # noqa: BLE001
            pass

    # 8) LISEZMOI: chaque dossier explique en une ligne
    try:
        _lignes = [
            "prompt/     votre demande",
            "reference/  les images RETENUES (face, cote, dos)",
            "modele/     modele_couleurs.glb + modele_geometrie.glb (sans couleurs) + planche GEOMETRIE.png",
        ]
        if avec_mouvement:
            _lignes.append("mouvement/  pareil, avec l'animation "
                           "(+ instants argile, + composite si demande)")
        _lignes += [
            "journal/    ce qui s'est passe (audit)",
            "travail/    intermediaires — supprimable sans perdre la livraison",
        ]
        (run_dir / "LISEZMOI.txt").write_text("\n".join(_lignes) + "\n",
                                              encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass

    return {"ok": True, "livraison": livraison, "deplaces": len(deplaces),
            "arborescence": ["prompt/", "reference/", "modele/", "mouvement/",
                             "journal/", "travail/"]}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--final-mesh", default=None)
    ap.add_argument("--rigged-mesh", default=None)
    ap.add_argument("--front-reference", default=None)
    a = ap.parse_args()
    print(json.dumps(organiser(a.run_dir, a.run_id, final_mesh=a.final_mesh,
                               rigged_mesh=a.rigged_mesh,
                               front_reference=a.front_reference),
                     ensure_ascii=False))
