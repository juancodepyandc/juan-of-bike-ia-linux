#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Où sont les sommets d'un GLB à l'instant t de son animation : lecture glTF 2.0 pure, sans moteur.

15/11/2026 — Pour poser un milieu autour d'un corps qui bouge, il faut le volume que ce corps
balaie RÉELLEMENT sur le clip, mesuré sur le fichier livré. `animation_multi_sujets.boite_repos`
ne lit que la pose de liaison : sur l'essai « Zig la hyène qui court et Sharko le requin qui
nage », les deux personnages animés (424 270 et 314 181 sommets, 52 os, 156 pistes LINEAR et STEP
sur 4 s, 121 clés) bougent hors de cette boîte. Ici, comme un lecteur glTF :

- les canaux d'animation (translation, rotation, échelle, poids de morphing) en LINEAR (slerp
  par le plus court chemin pour les rotations), STEP, et CUBICSPLINE : spline d'Hermite exacte
  de l'annexe C de la spécification (tangentes multipliées par l'intervalle), rotation
  renormalisée ; ce n'est PAS une approximation par les seules valeurs ;
- avant la première clé la première valeur, après la dernière la dernière ;
- la hiérarchie des nœuds (une matrice fixe est lue telle quelle) ;
- les cibles de morphing (POSITION) pondérées par les poids animés, sinon ceux du nœud, sinon
  ceux du maillage — avant la peau, comme le veut la spécification ;
- la peau (tous les jeux JOINTS_n / WEIGHTS_n, inverseBindMatrices) : un maillage avec peau est
  placé par ses os seuls, la transformation de son propre nœud est ignorée (spécification) ;
- les accesseurs normalisés (poids en octets), clairsemés (sparse) et sans bufferView.

Seule l'animation d'indice 0 est jouée : c'est celle que lisent f3d (`--animation-index` 0 par
défaut) et `animation_multi_sujets.composer` (première animation de chaque fichier). Les canaux
KHR_animation_pointer ne sont pas lus. La peau est calculée par blocs de sommets pour borner la
mémoire sur les maillages de plusieurs centaines de milliers de sommets.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import Any, Iterable, Sequence

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import glb_io  # noqa: E402
from animation_multi_sujets import _matrice  # noqa: E402

_COMPOSANTES = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}
_ENTIERS_NORMALISES = {5120: 127.0, 5121: 255.0, 5122: 32767.0, 5123: 65535.0}
_ENTIERS_SIGNES = {5120, 5122}
_CHEMINS = ("translation", "rotation", "scale", "weights")
# Peau par blocs : 131 072 sommets × 12 flottants × 8 octets ≈ 12,6 Mo par matrice mélangée.
_BLOC_SOMMETS = 1 << 17


# ── Accesseurs ──────────────────────────────────────────────────────────────────────────────────
def _normaliser(valeurs: np.ndarray, type_composante: int) -> np.ndarray:
    valeurs = valeurs / _ENTIERS_NORMALISES[type_composante]
    return np.maximum(valeurs, -1.0) if type_composante in _ENTIERS_SIGNES else valeurs


def _lire_vue(doc: dict, blob: bytes, vue: int, decalage: int, type_composante: int, compte: int,
              composantes: int) -> np.ndarray:
    """Données serrées d'une vue (les parties clairsemées n'ont jamais de byteStride)."""
    bv = doc["bufferViews"][vue]
    depart = int(bv.get("byteOffset", 0)) + int(decalage)
    dtype = glb_io.CT[int(type_composante)]
    return np.frombuffer(blob, dtype=dtype, count=compte * composantes, offset=depart).reshape(compte, composantes)


def lire_accesseur(doc: dict, blob: bytes, indice: int) -> np.ndarray:
    """Valeurs d'un accesseur en float64 (count, composantes) : normalisé, clairsemé ou sans vue."""
    acc = doc["accessors"][indice]
    composantes = _COMPOSANTES.get(acc.get("type", ""))
    if composantes is None:
        raise ValueError(f"accesseur {indice} : type {acc.get('type')!r} non lu")
    compte = int(acc["count"])
    type_composante = int(acc["componentType"])
    normalise = bool(acc.get("normalized")) and type_composante in _ENTIERS_NORMALISES
    if acc.get("bufferView") is not None:
        valeurs = np.array(glb_io.accessor(doc, blob, indice), dtype=np.float64)
        if normalise:
            valeurs = _normaliser(valeurs, type_composante)
    else:
        valeurs = np.zeros((compte, composantes), dtype=np.float64)
    clair = acc.get("sparse")
    if clair and int(clair.get("count", 0)) > 0:
        k = int(clair["count"])
        ind, val = clair["indices"], clair["values"]
        positions = _lire_vue(doc, blob, ind["bufferView"], ind.get("byteOffset", 0), ind["componentType"], k, 1)
        nouvelles = _lire_vue(doc, blob, val["bufferView"], val.get("byteOffset", 0), type_composante, k,
                              composantes).astype(np.float64)
        if normalise:
            nouvelles = _normaliser(nouvelles, type_composante)
        valeurs[positions[:, 0].astype(np.int64)] = nouvelles
    return valeurs


def _indices_echantillon(compte: int, echantillon: int | None) -> np.ndarray | None:
    """Sous-échantillon régulier d'environ `echantillon` sommets ; None = tous.

    Le même pas sert aux positions (`points_animes`) et aux aires (`aires_sommets`) : leurs
    tableaux restent alignés sommet à sommet.
    """
    if echantillon is None or echantillon <= 0 or compte <= echantillon:
        return None
    return np.arange(0, compte, int(math.ceil(compte / float(echantillon))), dtype=np.int64)


# ── Pistes d'animation ──────────────────────────────────────────────────────────────────────────
class _Piste:
    __slots__ = ("chemin", "mode", "temps", "valeurs")

    def __init__(self, chemin: str, mode: str, temps: np.ndarray, valeurs: np.ndarray):
        self.chemin, self.mode, self.temps, self.valeurs = chemin, mode, temps, valeurs

    def valeur(self, t: float) -> np.ndarray:
        temps, cubique = self.temps, self.mode == "CUBICSPLINE"
        sommets = self.valeurs[:, 1, :] if cubique else self.valeurs
        if len(temps) == 1 or t <= temps[0]:
            return sommets[0].copy()
        if t >= temps[-1]:
            return sommets[-1].copy()
        j = int(np.clip(np.searchsorted(temps, t, side="right") - 1, 0, len(temps) - 2))
        t0, t1 = float(temps[j]), float(temps[j + 1])
        intervalle = t1 - t0
        u = (t - t0) / intervalle if intervalle > 0 else 0.0
        if self.mode == "STEP":
            return sommets[j].copy()
        if cubique:
            # Annexe C : p(u) = h00·v_j + h10·Δt·b_j + h01·v_{j+1} + h11·Δt·a_{j+1}
            # (a = tangente entrante, b = tangente sortante, stockées autour de chaque valeur).
            u2, u3 = u * u, u * u * u
            v = ((2 * u3 - 3 * u2 + 1) * self.valeurs[j, 1] + (u3 - 2 * u2 + u) * intervalle * self.valeurs[j, 2]
                 + (-2 * u3 + 3 * u2) * self.valeurs[j + 1, 1] + (u3 - u2) * intervalle * self.valeurs[j + 1, 0])
            if self.chemin == "rotation":
                norme = float(np.linalg.norm(v))
                v = v / norme if norme > 0 else np.array([0.0, 0.0, 0.0, 1.0])
            return v
        if self.chemin == "rotation":
            return _slerp(sommets[j], sommets[j + 1], u)
        return (1.0 - u) * sommets[j] + u * sommets[j + 1]


def _slerp(q0: np.ndarray, q1: np.ndarray, u: float) -> np.ndarray:
    """Interpolation sphérique par le plus court chemin (q et −q sont la même rotation)."""
    q0 = q0 / max(float(np.linalg.norm(q0)), 1e-12)
    q1 = q1 / max(float(np.linalg.norm(q1)), 1e-12)
    cosinus = float(np.dot(q0, q1))
    if cosinus < 0.0:
        q1, cosinus = -q1, -cosinus
    if cosinus > 0.9995:                       # quasi alignés : la corde est la géodésique
        q = q0 + u * (q1 - q0)
        return q / np.linalg.norm(q)
    angle = math.acos(min(cosinus, 1.0))
    sinus = math.sin(angle)
    return (math.sin((1.0 - u) * angle) / sinus) * q0 + (math.sin(u * angle) / sinus) * q1


def _lire_pistes(doc: dict, blob: bytes, animation: int | None) -> dict[tuple[int, str], _Piste]:
    animations = doc.get("animations") or []
    if animation is None or not 0 <= int(animation) < len(animations):
        return {}
    anim = animations[int(animation)]
    pistes: dict[tuple[int, str], _Piste] = {}
    for canal in anim.get("channels", []):
        cible = canal.get("target") or {}
        chemin = cible.get("path")
        if "node" not in cible or chemin not in _CHEMINS:   # KHR_animation_pointer : non lu
            continue
        echantillonneur = anim["samplers"][canal["sampler"]]
        mode = echantillonneur.get("interpolation", "LINEAR")
        temps = lire_accesseur(doc, blob, echantillonneur["input"])[:, 0]
        sortie = lire_accesseur(doc, blob, echantillonneur["output"])
        cles = len(temps)
        if cles == 0:
            continue
        par_cle = 3 if mode == "CUBICSPLINE" else 1
        largeur = sortie.size // (cles * par_cle)
        if largeur == 0:
            continue
        valeurs = sortie.reshape(cles, 3, largeur) if par_cle == 3 else sortie.reshape(cles, largeur)
        pistes[(int(cible["node"]), chemin)] = _Piste(chemin, mode, temps, valeurs)
    return pistes


def duree(doc: dict, *, animation: int = 0, blob: bytes | None = None) -> float:
    """Durée de l'animation `animation` (0 : celle que jouent f3d et le compositeur) ; 0 sans animation.

    Les accesseurs d'entrée portent obligatoirement leur `max` (spécification) ; sans lui, les
    temps sont lus si le binaire est fourni.
    """
    animations = doc.get("animations") or []
    if not 0 <= animation < len(animations):
        return 0.0
    fin = 0.0
    for echantillonneur in animations[animation].get("samplers", []):
        acc = doc["accessors"][echantillonneur["input"]]
        if acc.get("max"):
            fin = max(fin, float(acc["max"][0]))
        elif blob is not None:
            temps = lire_accesseur(doc, blob, echantillonneur["input"])
            if temps.size:
                fin = max(fin, float(temps.max()))
    return fin


def instants_reguliers(duree_s: float, *, minimum: int = 24, frequence_hz: float = 12.0) -> np.ndarray:
    """Instants réguliers de 0 à la durée incluse : au moins `minimum`, au moins `frequence_hz` par seconde."""
    compte = max(int(minimum), int(math.ceil(max(float(duree_s), 0.0) * frequence_hz)) + 1)
    return np.linspace(0.0, max(float(duree_s), 0.0), compte)


# ── Triangles et aires ──────────────────────────────────────────────────────────────────────────
def triangles(doc: dict, blob: bytes, primitive: dict) -> np.ndarray:
    """Triangles (F, 3) d'une primitive : TRIANGLES, TRIANGLE_STRIP ou TRIANGLE_FAN ; vide sinon."""
    compte = int(doc["accessors"][primitive["attributes"]["POSITION"]]["count"])
    if "indices" in primitive:
        ordre = lire_accesseur(doc, blob, primitive["indices"])[:, 0].astype(np.int64)
    else:
        ordre = np.arange(compte, dtype=np.int64)
    mode = int(primitive.get("mode", 4))
    if mode == 4:
        n = len(ordre) - len(ordre) % 3
        return ordre[:n].reshape(-1, 3)
    if mode == 5 and len(ordre) >= 3:
        k = np.arange(len(ordre) - 2)
        tri = np.stack([ordre[k], ordre[k + 1], ordre[k + 2]], axis=1)
        impairs = k % 2 == 1                     # un sur deux est retourné pour garder le sens
        tri[impairs] = tri[impairs][:, [1, 0, 2]]
        return tri
    if mode == 6 and len(ordre) >= 3:
        k = np.arange(1, len(ordre) - 1)
        return np.stack([np.full_like(k, ordre[0]), ordre[k], ordre[k + 1]], axis=1)
    return np.zeros((0, 3), dtype=np.int64)


def aires_sommets(doc: dict, blob: bytes, mesh_index: int, *, echantillon: int | None = None) -> np.ndarray:
    """Poids d'aire de chaque sommet : somme des aires des triangles adjacents / 3, au repos.

    Alignés sur les points que `points_animes` rend pour un nœud de ce maillage (mêmes primitives
    dans le même ordre, même sous-échantillon). La densité d'un maillage biaise une part de
    sommets ; pondérée par l'aire, la part mesure une part de SURFACE. Un maillage sans triangle
    (points, lignes) reçoit des poids uniformes.
    """
    morceaux = []
    for prim in doc["meshes"][mesh_index].get("primitives", []):
        pos = lire_accesseur(doc, blob, prim["attributes"]["POSITION"])
        aires = np.zeros(len(pos))
        tri = triangles(doc, blob, prim)
        if len(tri):
            a, b, c = pos[tri[:, 0]], pos[tri[:, 1]], pos[tri[:, 2]]
            surface = 0.5 * np.linalg.norm(np.cross(b - a, c - a), axis=1)
            for k in range(3):
                np.add.at(aires, tri[:, k], surface / 3.0)
        if not aires.any():
            aires[:] = 1.0
        choix = _indices_echantillon(len(pos), echantillon)
        morceaux.append(aires if choix is None else aires[choix])
    return np.concatenate(morceaux) if morceaux else np.zeros(0)


# ── Échantillonneur ─────────────────────────────────────────────────────────────────────────────
class Echantillonneur:
    """Positions monde des sommets d'un document glTF à tout instant, données statiques en cache.

    `t=None` : pose de repos, sans animation (les poids de morphing par défaut s'appliquent) ; c'est
    la boîte que mesure `animation_multi_sujets.boite_repos`.
    """

    def __init__(self, doc: dict, blob: bytes, *, echantillon: int | None = None, animation: int = 0):
        self.doc, self.blob, self.echantillon = doc, blob, echantillon
        self.noeuds = doc.get("nodes") or []
        self.pistes = _lire_pistes(doc, blob, animation)
        enfants = {i: list(n.get("children", [])) for i, n in enumerate(self.noeuds)}
        cites = {c for liste in enfants.values() for c in liste}
        self.parent: dict[int, int] = {c: i for i, liste in enfants.items() for c in liste}
        self.racines_libres = [i for i in range(len(self.noeuds)) if i not in cites]
        scenes = doc.get("scenes") or []
        if scenes:
            scene = scenes[int(doc.get("scene", 0) or 0)]
            racines = list(scene.get("nodes", []))
        else:
            racines = list(self.racines_libres)
        self.racines_scene = racines
        ordre, pile = [], list(reversed(racines))
        while pile:
            i = pile.pop()
            ordre.append(i)
            pile.extend(reversed(enfants.get(i, [])))
        self.ordre_scene = ordre
        self.maillages = [i for i in ordre if "mesh" in self.noeuds[i]]
        self._prims: dict[int, list[dict[str, Any]]] = {}
        self._ibm: dict[int, np.ndarray] = {}

    # — transformations —
    def _locale(self, i: int, t: float | None) -> np.ndarray:
        noeud = self.noeuds[i]
        animees = {} if t is None else {chemin: self.pistes[(i, chemin)].valeur(t)
                                        for chemin in ("translation", "rotation", "scale")
                                        if (i, chemin) in self.pistes}
        if not animees:
            return _matrice(noeud)
        # Un nœud animé n'a pas de matrice (spécification) : ses TRS fixes, remplacés par les pistes.
        trs = {"translation": noeud.get("translation", [0.0, 0.0, 0.0]),
               "rotation": noeud.get("rotation", [0.0, 0.0, 0.0, 1.0]),
               "scale": noeud.get("scale", [1.0, 1.0, 1.0])}
        trs.update({chemin: [float(x) for x in valeur] for chemin, valeur in animees.items()})
        return _matrice(trs)

    def mondes(self, t: float | None) -> dict[int, np.ndarray]:
        """Matrice monde de chaque nœud (toutes les racines, pas seulement celles de la scène)."""
        mondes: dict[int, np.ndarray] = {}
        pile = [(r, np.eye(4)) for r in self.racines_libres]
        while pile:
            i, parent = pile.pop()
            mondes[i] = parent @ self._locale(i, t)
            pile.extend((c, mondes[i]) for c in self.noeuds[i].get("children", []))
        return mondes

    def poids_morph(self, i: int, t: float | None) -> np.ndarray:
        """Poids de morphing du nœud i : animés, sinon ceux du nœud, sinon ceux du maillage, sinon 0."""
        noeud = self.noeuds[i]
        maillage = self.doc["meshes"][noeud["mesh"]] if "mesh" in noeud else {}
        cibles = max((len(p.get("targets", [])) for p in maillage.get("primitives", [])), default=0)
        if t is not None and (i, "weights") in self.pistes:
            poids = self.pistes[(i, "weights")].valeur(t)
        elif "weights" in noeud:
            poids = np.array(noeud["weights"], dtype=np.float64)
        elif "weights" in maillage:
            poids = np.array(maillage["weights"], dtype=np.float64)
        else:
            poids = np.zeros(cibles)
        complet = np.zeros(cibles)
        complet[:min(cibles, len(poids))] = poids[:cibles]
        return complet

    # — données statiques —
    def _primitives(self, mesh_index: int) -> list[dict[str, Any]]:
        if mesh_index in self._prims:
            return self._prims[mesh_index]
        sortie = []
        for prim in self.doc["meshes"][mesh_index].get("primitives", []):
            attrs = prim["attributes"]
            pos = lire_accesseur(self.doc, self.blob, attrs["POSITION"])
            choix = _indices_echantillon(len(pos), self.echantillon)
            prendre = (lambda a: a) if choix is None else (lambda a: a[choix])
            cibles = []
            for cible in prim.get("targets", []):
                cibles.append(prendre(lire_accesseur(self.doc, self.blob, cible["POSITION"]))
                              if "POSITION" in cible else None)
            jeux = []
            n = 0
            while f"JOINTS_{n}" in attrs and f"WEIGHTS_{n}" in attrs:
                articulations = prendre(lire_accesseur(self.doc, self.blob, attrs[f"JOINTS_{n}"])).astype(np.intp)
                poids = prendre(lire_accesseur(self.doc, self.blob, attrs[f"WEIGHTS_{n}"]))
                jeux.append((articulations, poids))
                n += 1
            sans_poids = None
            if jeux:
                total = sum(p.sum(axis=1) for _, p in jeux)
                # Les poids doivent sommer à 1 ; des poids entiers non déclarés normalisés (vus sur des
                # exports, cf. boite_repos) ou arrondis sont ramenés à 1 ligne par ligne.
                jeux = [(a, np.divide(p, total[:, None], out=np.zeros_like(p), where=total[:, None] > 0))
                        for a, p in jeux]
                sans_poids = total <= 0
            sortie.append({"positions": prendre(pos), "cibles": cibles, "jeux": jeux, "sans_poids": sans_poids})
        self._prims[mesh_index] = sortie
        return sortie

    def _inverses_liaison(self, peau_index: int) -> np.ndarray:
        if peau_index not in self._ibm:
            peau = self.doc["skins"][peau_index]
            if "inverseBindMatrices" in peau:
                brut = lire_accesseur(self.doc, self.blob, peau["inverseBindMatrices"])
                self._ibm[peau_index] = brut.reshape(-1, 4, 4).transpose(0, 2, 1)   # colonnes majeures
            else:
                self._ibm[peau_index] = np.tile(np.eye(4), (len(peau["joints"]), 1, 1))
        return self._ibm[peau_index]

    # — positions —
    @staticmethod
    def _deformer(positions: np.ndarray, jeux: list, matrices: np.ndarray) -> np.ndarray:
        """Σ poids · (monde_os · inverse_de_liaison) · sommet, par blocs de sommets."""
        sortie = np.empty_like(positions)
        for debut in range(0, len(positions), _BLOC_SOMMETS):
            fin = min(debut + _BLOC_SOMMETS, len(positions))
            melange = np.zeros((fin - debut, 3, 4))
            for articulations, poids in jeux:
                for k in range(articulations.shape[1]):
                    w = poids[debut:fin, k]
                    if not w.any():
                        continue
                    melange += w[:, None, None] * matrices[articulations[debut:fin, k]]
            p = positions[debut:fin]
            sortie[debut:fin] = np.einsum("nij,nj->ni", melange[:, :, :3], p) + melange[:, :, 3]
        return sortie

    def points_noeud(self, i: int, t: float | None, mondes: dict[int, np.ndarray] | None = None) -> np.ndarray:
        mondes = self.mondes(t) if mondes is None else mondes
        noeud = self.noeuds[i]
        poids = self.poids_morph(i, t)
        morceaux = []
        for prim in self._primitives(int(noeud["mesh"])):
            base = prim["positions"]
            if poids.size and np.any(poids):
                base = base.copy()
                for w, delta in zip(poids, prim["cibles"]):
                    if w != 0.0 and delta is not None:
                        base += w * delta
            if "skin" in noeud and prim["jeux"]:
                peau = self.doc["skins"][int(noeud["skin"])]
                os_mondes = np.array([mondes.get(j, np.eye(4)) for j in peau["joints"]])
                matrices = (os_mondes @ self._inverses_liaison(int(noeud["skin"])))[:, :3, :]
                points = self._deformer(base, prim["jeux"], matrices)
                if prim["sans_poids"] is not None and prim["sans_poids"].any():
                    m = mondes[i]                # un sommet sans poids suit son nœud au lieu de l'origine
                    seuls = base[prim["sans_poids"]]
                    points[prim["sans_poids"]] = seuls @ m[:3, :3].T + m[:3, 3]
            else:
                m = mondes[i]
                points = base @ m[:3, :3].T + m[:3, 3]
            morceaux.append(points)
        return np.concatenate(morceaux) if morceaux else np.zeros((0, 3))

    def points(self, t: float | None, noeuds: Iterable[int] | None = None) -> list[tuple[int, np.ndarray]]:
        """[(indice du nœud maillé, positions monde (N, 3))] pour les maillages de la scène."""
        mondes = self.mondes(t)
        if noeuds is None:
            retenus = self.maillages
        else:
            voulus = {int(i) for i in noeuds}
            retenus = [i for i in self.maillages if i in voulus]
        return [(i, self.points_noeud(i, t, mondes)) for i in retenus]

    def boite(self, instants: Sequence[float | None], noeuds: Iterable[int] | None = None
              ) -> tuple[np.ndarray, np.ndarray] | None:
        lo, hi = None, None
        noeuds = None if noeuds is None else [int(i) for i in noeuds]
        for t in instants:
            for _, p in self.points(t, noeuds):
                if not len(p):
                    continue
                pmin, pmax = p.min(axis=0), p.max(axis=0)
                lo = pmin if lo is None else np.minimum(lo, pmin)
                hi = pmax if hi is None else np.maximum(hi, pmax)
        return None if lo is None else (lo, hi)


# ── API fonctionnelle ───────────────────────────────────────────────────────────────────────────
def points_animes(doc: dict, blob: bytes, t: float | None, *, echantillon: int | None = None,
                  animation: int = 0) -> list[tuple[int, np.ndarray]]:
    """[(indice du nœud maillé, positions monde (N, 3) à l'instant t)] ; t=None : pose de repos."""
    return Echantillonneur(doc, blob, echantillon=echantillon, animation=animation).points(t)


def boite_balayee(doc: dict, blob: bytes, instants: Sequence[float | None], *, echantillon: int | None = None,
                  animation: int = 0) -> tuple[np.ndarray, np.ndarray] | None:
    """(min, max) monde de tous les sommets sur l'ensemble des instants donnés."""
    return Echantillonneur(doc, blob, echantillon=echantillon, animation=animation).boite(list(instants))
