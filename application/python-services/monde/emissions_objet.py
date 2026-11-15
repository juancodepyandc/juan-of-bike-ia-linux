"""Émissions posées sur un objet livré : le flacon vaporise, la tasse fume, la bougie brûle, la fontaine jaillit.

Le contrat de demande dit, par sujet, la matière émise (`emission.type`) et d'où elle part (`emission.point` :
haut, avant, bas). L'émetteur est placé sur la boîte englobante du modèle, mis à l'ÉCHELLE DE SA SOURCE (la
portée d'un vaporisateur vaut ~3 fois sa hauteur, quelle que soit l'unité du modèle reconstruit), puis le
modèle et ses particules animées sont réécrits ensemble (`emission_couleurs.glb`, à côté du modèle).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import trimesh

from monde import animation_gltf, emetteurs, export_gltf

# Taille réelle typique de la source de chaque émission (m) : l'émission suit la taille du modèle livré.
TAILLE_SOURCE = {"brume": 0.15, "vapeur": 0.10, "flamme": 0.25, "fumee": 1.0, "jet_liquide": 0.8, "gouttes": 0.3}
DIRECTIONS = {"haut": (0.0, 1.0, 0.12), "avant": (0.0, 0.2, 1.0), "bas": (0.0, -1.0, 0.0)}
POINT_PAR_DEFAUT = {"brume": "avant", "gouttes": "bas"}


def emissions_du_contrat(contrat: dict | None) -> list[dict[str, Any]]:
    if not isinstance(contrat, dict) or contrat.get("source") != "llm":
        return []
    return [dict(s["emission"]) for s in contrat.get("sujets") or []
            if isinstance(s.get("emission"), dict) and s["emission"].get("type") in emetteurs.LOIS]


def ajouter(glb_entree: str | Path, glb_sortie: str | Path, emissions: list[dict[str, Any]]) -> dict[str, Any]:
    """Réécrit le modèle avec ses émissions animées ; rend le rapport (origines, échelles, mesures)."""
    scene = trimesh.load(str(glb_entree), force="scene")
    (x0, y0, z0), (x1, y1, z1) = scene.bounds
    hauteur = max(1e-6, y1 - y0)
    cx, cz = (x0 + x1) / 2.0, (z0 + z1) / 2.0
    pistes_toutes: dict[str, dict] = {}
    rapport = []
    for k, emission in enumerate(emissions):
        type_ = emission["type"]
        point = emission.get("point") or POINT_PAR_DEFAUT.get(type_, "haut")
        origine = {"haut": (cx, y1 + 0.01 * hauteur, cz), "avant": (cx, y0 + 0.88 * hauteur, z1 + 0.01 * hauteur),
                   "bas": (cx, y0, cz)}[point]
        echelle = hauteur / TAILLE_SOURCE[type_]
        noeud, pistes, mesures = emetteurs.construire(emetteurs.Emission(
            type_, origine=origine, direction=DIRECTIONS[point], echelle=echelle, nom=f"emission_{k}_{type_}",
            graine=k + 1))
        for inst in noeud.instances:
            for partie in inst.objet.parties:
                maillage = export_gltf._preparer(partie.maillage, partie.materiau, 256)
                scene.add_geometry(maillage, node_name=inst.nom, geom_name=inst.nom, transform=inst.pose.matrice())
        pistes_toutes.update(pistes)
        rapport.append({"type": type_, "point": point, "origine": [round(float(v), 4) for v in origine],
                        "echelle": round(float(echelle), 4), **mesures})
    glb_sortie = Path(glb_sortie)
    glb_sortie.parent.mkdir(parents=True, exist_ok=True)
    glb_sortie.write_bytes(scene.export(file_type="glb", include_normals=True,
                                        tree_postprocessor=lambda arbre: export_gltf._matrices_en_trs(arbre, {})))
    injection = animation_gltf.injecter(glb_sortie, pistes_toutes, nom="emission")
    return {"ok": bool(injection["ok"]), "glb": str(glb_sortie), "emissions": rapport,
            "canaux": injection["canaux"], "absents": injection["absents"]}
