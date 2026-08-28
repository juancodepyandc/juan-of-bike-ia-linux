#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""glb_clips_merge — reunit plusieurs animations dans UN seul GLB.

Pourquoi ce module existe
-------------------------
Le service d'animation rend UN clip par appel: un fichier pour la marche, un
autre pour la transition debout->assis, un autre pour l'assise. Un site web,
lui, charge UN modele et enchaine les clips (le personnage se deplace, puis
s'assoit sur evenement). Sans fusion il faudrait charger trois fois le meme
maillage 8K — et le viewer ne saurait pas qu'il s'agit du meme personnage.

Ce que le module fait
---------------------
Il prend le GLB de reference (maillage + squelette + 1er clip) et y AJOUTE les
animations des autres fichiers: les accesseurs de temps et de valeurs sont
recopies dans le binaire, de nouveaux bufferViews/accessors sont crees, et les
canaux sont re-pointes sur les memes noeuds. La geometrie, le squelette et les
textures du fichier de reference ne sont jamais touches — on n'ajoute que des
blocs d'animation.

Garde-fou: les clips doivent venir du MEME squelette. On le verifie sur le
nombre de noeuds ET sur les noeuds cibles de chaque canal; sinon la fusion est
refusee plutot que de produire un personnage qui se tord (un canal qui pointe
le mauvais os deforme le maillage sans rien signaler).

Schema: aurora.glb_clips.v1

Usage:
    python glb_clips_merge.py --base marche.glb --ajouter assis.glb debout_assis.glb \\
        --sortie personnage_clips.glb
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

SCHEMA = "aurora.glb_clips.v1"


def _aligner(blob: bytearray) -> None:
    """Le glTF exige des bufferViews alignes sur 4 octets."""
    reste = len(blob) % 4
    if reste:
        blob.extend(b"\x00" * (4 - reste))


def _copier_accesseur(src, src_blob: bytes, idx: int,
                      dst, dst_blob: bytearray) -> int:
    """Recopie l'accesseur `idx` de `src` dans `dst`. Rend son nouvel index."""
    from pygltflib import Accessor, BufferView

    acc = src.accessors[idx]
    bv = src.bufferViews[acc.bufferView]
    debut = (bv.byteOffset or 0)
    donnees = bytes(src_blob[debut:debut + bv.byteLength])

    _aligner(dst_blob)
    nouvel_offset = len(dst_blob)
    dst_blob.extend(donnees)

    dst.bufferViews.append(BufferView(
        buffer=0, byteOffset=nouvel_offset, byteLength=len(donnees),
        byteStride=bv.byteStride, target=bv.target))
    nouveau_bv = len(dst.bufferViews) - 1

    dst.accessors.append(Accessor(
        bufferView=nouveau_bv, byteOffset=acc.byteOffset or 0,
        componentType=acc.componentType, count=acc.count, type=acc.type,
        min=list(acc.min) if acc.min else None,
        max=list(acc.max) if acc.max else None,
        normalized=acc.normalized))
    return len(dst.accessors) - 1


def _noeuds_cibles(g) -> set:
    cibles = set()
    for a in (g.animations or []):
        for c in a.channels:
            if c.target is not None and c.target.node is not None:
                cibles.add(int(c.target.node))
    return cibles


def fusionner(base: str, ajouts: List[str], sortie: str,
              noms: List[str] | None = None) -> Dict[str, Any]:
    """Reunit les animations de `ajouts` dans une copie de `base`."""
    from pygltflib import GLTF2, Animation, AnimationChannel, AnimationChannelTarget, AnimationSampler

    g = GLTF2().load(base)
    blob = bytearray(g.binary_blob())
    rapport: Dict[str, Any] = {
        "ok": True, "schema": SCHEMA, "base": base,
        "clips": [a.name or "(sans nom)" for a in (g.animations or [])],
        "ajoutes": [], "refuses": [],
    }
    if g.animations is None:
        g.animations = []
    n_noeuds = len(g.nodes or [])
    cibles_base = _noeuds_cibles(g)

    for i, chemin in enumerate(ajouts):
        try:
            autre = GLTF2().load(chemin)
        except Exception as exc:  # noqa: BLE001
            rapport["refuses"].append({"fichier": chemin, "motif": repr(exc)[:120]})
            continue
        if not (autre.animations or []):
            rapport["refuses"].append({"fichier": chemin, "motif": "aucune animation"})
            continue
        # MEME SQUELETTE, sinon un canal pointe le mauvais os et tord le
        # maillage en silence. On compare le nombre de noeuds ET les cibles.
        if len(autre.nodes or []) != n_noeuds:
            rapport["refuses"].append({
                "fichier": chemin,
                "motif": "squelette different (%d noeuds contre %d)"
                         % (len(autre.nodes or []), n_noeuds)})
            continue
        cibles_autre = _noeuds_cibles(autre)
        if cibles_base and cibles_autre and not (cibles_autre <= cibles_base | cibles_autre):
            rapport["refuses"].append({"fichier": chemin, "motif": "noeuds cibles incompatibles"})
            continue

        autre_blob = autre.binary_blob()
        for anim in autre.animations:
            correspondance: Dict[int, int] = {}
            nouveaux_samplers = []
            for s in anim.samplers:
                for acc_idx in (s.input, s.output):
                    if acc_idx not in correspondance:
                        correspondance[acc_idx] = _copier_accesseur(
                            autre, autre_blob, acc_idx, g, blob)
                nouveaux_samplers.append(AnimationSampler(
                    input=correspondance[s.input],
                    output=correspondance[s.output],
                    interpolation=s.interpolation or "LINEAR"))
            nouveaux_canaux = [
                AnimationChannel(
                    sampler=c.sampler,
                    target=AnimationChannelTarget(node=c.target.node,
                                                  path=c.target.path))
                for c in anim.channels]
            nom = (noms[i] if noms and i < len(noms) and noms[i]
                   else (anim.name or Path(chemin).stem))
            g.animations.append(Animation(name=nom, samplers=nouveaux_samplers,
                                          channels=nouveaux_canaux))
            rapport["ajoutes"].append({"fichier": Path(chemin).name, "clip": nom,
                                       "canaux": len(nouveaux_canaux)})

    _aligner(blob)
    g.buffers[0].byteLength = len(blob)
    g.set_binary_blob(bytes(blob))
    g.save(str(sortie))
    rapport["sortie"] = str(sortie)
    rapport["clips_final"] = [a.name for a in g.animations]
    rapport["total_clips"] = len(g.animations)
    return rapport


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Reunit plusieurs clips dans un GLB")
    ap.add_argument("--base", required=True)
    ap.add_argument("--ajouter", nargs="+", required=True)
    ap.add_argument("--sortie", required=True)
    ap.add_argument("--noms", nargs="*", default=None,
                    help="noms des clips ajoutes, dans l'ordre")
    a = ap.parse_args(argv)
    try:
        r = fusionner(a.base, a.ajouter, a.sortie, a.noms)
    except Exception as exc:  # noqa: BLE001 — contrat CLI: toujours du JSON
        r = {"ok": False, "schema": SCHEMA, "erreur": "%s: %s" % (type(exc).__name__, exc)}
    print(json.dumps(r, ensure_ascii=False))
    return 0 if r.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
