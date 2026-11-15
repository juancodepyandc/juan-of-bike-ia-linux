"""Représentation intermédiaire du moteur de scènes : ce que toutes les briques échangent.

Conventions (aucune brique n'en change ; toute nouvelle brique les respecte) :
- unités : mètres ; repère glTF : Y vers le haut, main droite ; le sol est le plan XZ.
- un plan 2D s'écrit en (x, z) — le même x et le même z que la 3D (pas de (x, y) au sol).
- un objet est construit dans son repère LOCAL : origine au centre de son emprise, au niveau du sol
  (y = 0) ; sa FACE (le côté par lequel on l'utilise : l'assise d'un canapé, les portes d'une armoire,
  l'écran d'une télévision, le pied d'un lit, l'avant d'une voiture) regarde +Z ; son dos regarde -Z.
- une pose (x, z, lacet, y) : rotation de `lacet` radians autour de +Y, puis translation. Après rotation,
  la face regarde (sin lacet, 0, cos lacet). lacet = 0 : face vers +Z ; lacet = pi/2 : face vers +X.
- les UV des maillages sont en MÈTRES (1 unité = 1 m, projection triplanaire de `geometrie.uv_metres`) ;
  l'exporteur les divise par `taille_m` du matériau. La densité de texture est donc la même partout.
- un matériau est une clé de `vocabulaire.MATERIAUX`, éventuellement « cle:couleur ».
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import trimesh
from shapely.geometry import Polygon


@dataclass
class Partie:
    """Un maillage d'un seul matériau, dans le repère de son propriétaire (objet local ou monde)."""
    maillage: trimesh.Trimesh
    materiau: str
    nom: str = ""


@dataclass
class Surface:
    """Dessus utilisable d'un objet (pour y poser un petit objet) : hauteur et polygone local (x, z)."""
    hauteur: float
    polygone: list[tuple[float, float]]


@dataclass
class Pose:
    x: float = 0.0
    z: float = 0.0
    lacet: float = 0.0
    y: float = 0.0

    def matrice(self) -> np.ndarray:
        c, s = math.cos(self.lacet), math.sin(self.lacet)
        m = np.eye(4)
        m[:3, :3] = [[c, 0.0, s], [0.0, 1.0, 0.0], [-s, 0.0, c]]
        m[:3, 3] = [self.x, self.y, self.z]
        return m

    def vers_monde(self, lx: float, lz: float) -> tuple[float, float]:
        """Un point local (lx, lz) au sol, exprimé dans le monde."""
        c, s = math.cos(self.lacet), math.sin(self.lacet)
        return self.x + c * lx + s * lz, self.z - s * lx + c * lz

    def face(self) -> tuple[float, float]:
        return math.sin(self.lacet), math.cos(self.lacet)


@dataclass
class Objet:
    """Un meuble ou un objet, construit dans son repère local (voir conventions)."""
    nom: str
    categorie: str
    parties: list[Partie]
    largeur: float
    profondeur: float
    hauteur: float
    degagement: float = 0.0
    degagement_cotes: float = 0.0
    surfaces: list[Surface] = field(default_factory=list)
    mural: bool = False
    plafond: bool = False
    sol_partage: bool = False
    meta: dict[str, Any] = field(default_factory=dict)

    def rectangle(self, pose: Pose, *, marge_avant: float = 0.0, marge_cotes: float = 0.0,
                  marge_arriere: float = 0.0) -> Polygon:
        """Emprise au sol dans le monde, éventuellement élargie (dégagements)."""
        hx, hz = self.largeur / 2.0 + marge_cotes, self.profondeur / 2.0
        coins = [(-hx, -hz - marge_arriere), (hx, -hz - marge_arriere), (hx, hz + marge_avant), (-hx, hz + marge_avant)]
        return Polygon([pose.vers_monde(x, z) for x, z in coins])

    def emprise(self, pose: Pose) -> Polygon:
        return self.rectangle(pose)

    def zone_degagement(self, pose: Pose) -> Polygon | None:
        """Bande libre devant la face (et sur les côtés si degagement_cotes) ; None si aucune."""
        if self.degagement <= 0.0 and self.degagement_cotes <= 0.0:
            return None
        hx, hz = self.largeur / 2.0, self.profondeur / 2.0
        morceaux = []
        if self.degagement > 0.0:
            morceaux.append(Polygon([pose.vers_monde(x, z) for x, z in
                                     [(-hx, hz), (hx, hz), (hx, hz + self.degagement), (-hx, hz + self.degagement)]]))
        if self.degagement_cotes > 0.0:
            d = self.degagement_cotes
            for signe in (-1.0, 1.0):
                x0, x1 = (hx, hx + d) if signe > 0 else (-hx - d, -hx)
                morceaux.append(Polygon([pose.vers_monde(x, z) for x, z in [(x0, -hz), (x1, -hz), (x1, hz), (x0, hz)]]))
        from shapely.ops import unary_union
        return unary_union(morceaux)


@dataclass
class Instance:
    """Un objet posé dans la scène."""
    objet: Objet
    pose: Pose
    nom: str = ""
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class Noeud:
    """Nœud de la hiérarchie exportée : géométrie fixe en coordonnées MONDE (murs, sols, routes) et
    objets posés. `fusion=True` fusionne la géométrie par matériau à l'export (villes, forêts) ; sinon
    chaque objet reste un nœud nommé, prêt à animer (intérieurs)."""
    nom: str
    parties: list[Partie] = field(default_factory=list)
    instances: list[Instance] = field(default_factory=list)
    enfants: list["Noeud"] = field(default_factory=list)
    fusion: bool = False
    extras: dict[str, Any] = field(default_factory=dict)

    def parcourir(self):
        yield self
        for enfant in self.enfants:
            yield from enfant.parcourir()


@dataclass
class Scene:
    racine: Noeud
    extras: dict[str, Any] = field(default_factory=dict)
