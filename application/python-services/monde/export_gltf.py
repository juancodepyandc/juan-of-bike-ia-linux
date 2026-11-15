"""Export d'une `monde.ir.Scene` en GLB (glTF 2.0) : hiérarchie de nœuds, matériaux PBR, UV mis à l'échelle.

- Chaque `Noeud` devient un nœud glTF ; sa géométrie fixe (coordonnées monde) est regroupée par matériau.
- Sans `fusion`, chaque `Instance` devient un nœud nommé portant sa pose (rotation + translation) et ses
  parties en enfants : la scène reste éditable et animable objet par objet (une porte, une chaise).
- Avec `fusion`, instances et géométrie fixe sont fusionnées par matériau (villes, forêts : peu de nœuds).
- Les UV, en mètres, sont divisées par `taille_m` du matériau ; un même matériau est un seul matériau glTF.
- Les `extras` de la scène et des nœuds sont écrits dans les extras glTF (programme, rapports).
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np
import trimesh
from trimesh.visual import TextureVisuals

from monde import materiaux, vocabulaire
from monde.geometrie import fusionner, transformer
from monde.ir import Instance, Noeud, Partie, Scene


def _nom_sur(nom: str) -> str:
    return re.sub(r"[^0-9A-Za-z_\-]+", "_", nom).strip("_") or "noeud"


class _Noms:
    def __init__(self) -> None:
        self.vus: dict[str, int] = defaultdict(int)

    def __call__(self, nom: str) -> str:
        base = _nom_sur(nom)
        self.vus[base] += 1
        return base if self.vus[base] == 1 else f"{base}_{self.vus[base]}"


def _preparer(maillage: trimesh.Trimesh, cle: str, resolution: int) -> trimesh.Trimesh:
    spec = vocabulaire.materiau(cle)
    m = trimesh.Trimesh(vertices=maillage.vertices, faces=maillage.faces,
                        vertex_normals=np.asarray(maillage.vertex_normals), process=False)
    uv = getattr(maillage.visual, "uv", None)
    uv = np.zeros((len(m.vertices), 2)) if uv is None else np.asarray(uv, dtype=np.float64) / spec["taille_m"]
    m.visual = TextureVisuals(uv=uv, material=materiaux.materiau_trimesh(cle, resolution))
    return m


def _par_materiau(parties: list[Partie]) -> dict[str, trimesh.Trimesh]:
    groupes: dict[str, list[trimesh.Trimesh]] = defaultdict(list)
    for p in parties:
        if p.maillage is not None and len(p.maillage.faces):
            groupes[p.materiau].append(p.maillage)
    return {cle: fusionner(liste) for cle, liste in groupes.items()}


# Clés d'extras qu'un visualiseur INTERPRÈTE : three.js r183 reconstruit un pivot depuis `userData.pivot`
# (convention de son GLTFExporter, un tableau) ; notre « charniere » y devenait une position NaN et faisait
# disparaître chaque porte de la scène (maison du 15/11/2026). Elles sont écrites sous un nom à nous.
CLES_RESERVEES = {"pivot": "aurora_pivot"}


def _extras_surs(extras: dict) -> dict:
    return {CLES_RESERVEES.get(k, k): v for k, v in extras.items()}


def _matrices_en_trs(arbre: dict, extras_par_nom: dict[str, dict] | None = None) -> None:
    """glTF n'anime que les nœuds en translation/rotation/échelle (jamais un nœud à `matrix`) : chaque
    matrice est décomposée, pour que la scène reste animable objet par objet. Les extras des nœuds
    (catégorie, pivot et angle d'ouverture d'une porte…) sont écrits ici : trimesh ne les exporte pas
    (0 nœud sur 223 les portait, maison du 15/11/2026) ; three.js les lit dans `userData`."""
    for noeud in arbre.get("nodes", []):
        extras = (extras_par_nom or {}).get(noeud.get("name", ""))
        if extras:
            noeud["extras"] = json.loads(json.dumps(_extras_surs(extras), ensure_ascii=False, default=str))
        matrice = noeud.pop("matrix", None)
        if matrice is None:
            continue
        m = np.asarray(matrice, dtype=np.float64).reshape(4, 4).T          # glTF : colonne par colonne
        t = m[:3, 3]
        echelle = np.linalg.norm(m[:3, :3], axis=0)
        echelle[echelle < 1e-12] = 1.0
        r = m[:3, :3] / echelle
        if np.linalg.det(r) < 0:                                            # réflexion : portée par l'échelle
            echelle[0] = -echelle[0]
            r[:, 0] = -r[:, 0]
        q = trimesh.transformations.quaternion_from_matrix(np.vstack([np.column_stack([r, [0, 0, 0]]), [0, 0, 0, 1]]))
        if not np.allclose(t, 0.0):
            noeud["translation"] = [float(v) for v in t]
        if not np.allclose(q, [1.0, 0.0, 0.0, 0.0]) and not np.allclose(q, [-1.0, 0.0, 0.0, 0.0]):
            noeud["rotation"] = [float(q[1]), float(q[2]), float(q[3]), float(q[0])]   # glTF : x, y, z, w
        if not np.allclose(echelle, 1.0):
            noeud["scale"] = [float(v) for v in echelle]


def _parties_monde(instance: Instance) -> list[Partie]:
    matrice = instance.pose.matrice()
    return [Partie(transformer(p.maillage, matrice), p.materiau, p.nom) for p in instance.objet.parties]


def exporter(scene: Scene, chemin: str | Path, *, resolution: int = 512) -> dict[str, Any]:
    """Écrit le GLB et rend un rapport (nœuds, maillages, triangles, matériaux, taille)."""
    chemin = Path(chemin)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    ts = trimesh.Scene()
    noms = _Noms()
    stats = {"noeuds": 0, "maillages": 0, "triangles": 0, "materiaux": set(), "objets": 0}
    extras_par_nom: dict[str, dict] = {}

    def ajouter_maillage(m: trimesh.Trimesh, cle: str, nom: str, parent: str, matrice: np.ndarray | None = None):
        if m is None or not len(m.faces):
            return
        nom_g = noms(nom)
        ts.add_geometry(_preparer(m, cle, resolution), node_name=nom_g, geom_name=nom_g, parent_node_name=parent,
                        transform=np.eye(4) if matrice is None else matrice)
        stats["maillages"] += 1
        stats["triangles"] += int(len(m.faces))
        stats["materiaux"].add(cle)

    def ajouter_vide(nom: str, parent: str, matrice: np.ndarray | None = None, extras: dict | None = None) -> str:
        nom_n = noms(nom)
        ts.graph.update(frame_to=nom_n, frame_from=parent, matrix=np.eye(4) if matrice is None else matrice)
        if extras:
            extras_par_nom[nom_n] = extras
        stats["noeuds"] += 1
        return nom_n

    def visiter(noeud: Noeud, parent: str) -> None:
        nom_n = ajouter_vide(noeud.nom, parent, extras=noeud.extras or None)
        if noeud.fusion:
            parties = list(noeud.parties)
            for inst in noeud.instances:
                parties.extend(_parties_monde(inst))
                stats["objets"] += 1
            for cle, m in _par_materiau(parties).items():
                ajouter_maillage(m, cle, f"{noeud.nom}_{cle}", nom_n)
        else:
            for cle, m in _par_materiau(noeud.parties).items():
                ajouter_maillage(m, cle, f"{noeud.nom}_{cle}", nom_n)
            for inst in noeud.instances:
                stats["objets"] += 1
                nom_i = ajouter_vide(inst.nom or inst.objet.nom or inst.objet.categorie, nom_n, inst.pose.matrice(),
                                     extras={"categorie": inst.objet.categorie, **(inst.meta or {})})
                for cle, m in _par_materiau(inst.objet.parties).items():
                    ajouter_maillage(m, cle, f"{inst.nom or inst.objet.categorie}_{cle}", nom_i)
        for enfant in noeud.enfants:
            visiter(enfant, nom_n)

    visiter(scene.racine, ts.graph.base_frame)
    if scene.extras:
        ts.metadata["extras"] = json.loads(json.dumps(scene.extras, ensure_ascii=False, default=str))
    donnees = ts.export(file_type="glb", include_normals=True,
                        tree_postprocessor=lambda arbre: _matrices_en_trs(arbre, extras_par_nom))
    chemin.write_bytes(donnees)
    stats["materiaux"] = sorted(stats["materiaux"])
    stats["octets"] = len(donnees)
    stats["chemin"] = str(chemin)
    return stats
