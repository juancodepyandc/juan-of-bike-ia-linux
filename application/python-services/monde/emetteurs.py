"""Émissions animées de matière : gaz (brume de vaporisateur, fumée, vapeur, flamme) et liquides (jet, gouttes).

Créé le 15/11/2026 (« un coup de parfum… tout liquide, gaz et solide doit être compris »). Chaque émission est
une LOI PHYSIQUE paramétrée, jamais un effet dessiné à la main :
- trajectoire d'une particule : vitesse initiale dans un cône autour de la direction d'émission, freinage par
  la traînée de l'air (temps caractéristique τ), poussée d'Archimède (gaz chaud) ou gravité (gouttes), dérive
  du vent ; x(a) = x0 + v0·τ·(1 − e^(−a/τ)) + ½·(g + b)·a² + w·a ;
- taille : diffusion (rayon ∝ √âge) pour un gaz, rétrécissement pour une flamme, constante pour une goutte ;
- naissance : bouffée (vaporisateur : une impulsion de 0,35 s) ou flux continu ; durée de vie finie ; boucle.

Les particules sont de petits volumes translucides (ou lumineux) ; leur mouvement est une animation glTF
d'échelle et de translation (rejouée par three.js et f3d), échantillonnée à 30 images par seconde.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from monde import geometrie as g
from monde.ir import Instance, Noeud, Objet, Partie, Pose

IMAGES_PAR_SECONDE = 30


@dataclass(frozen=True)
class Loi:
    description: str
    materiau: str
    particules: int
    duree_boucle: float          # s
    vie: float                   # durée de vie d'une particule (s)
    bouffee: float               # durée d'émission dans la boucle (s) ; = duree_boucle pour un flux continu
    vitesse: float               # m/s
    cone_deg: float              # demi-angle du cône
    trainee: float               # τ (s) ; grand = peu freiné
    acceleration: tuple[float, float, float]   # gravité + poussée (m/s²)
    vent: tuple[float, float, float]           # m/s
    rayon: tuple[float, float]  # rayon à la naissance, rayon en fin de vie (m)
    croissance: str = "diffusion"              # diffusion | lineaire | constante | retrecit


LOIS: dict[str, Loi] = {
    # vaporisateur (parfum, aérosol) : jet rapide très freiné, nuage qui s'étale et retombe à peine
    # (portée ≈ v·τ ≈ 0,4 m, nuage de 10 à 15 cm, dissipé en ~2 s : ordres de grandeur d'un vrai vaporisateur)
    "brume": Loi("brume fine d'un vaporisateur", "brume", 110, 3.0, 2.0, 0.35, 7.0, 9.0, 0.06,
                 (0.0, -0.12, 0.0), (0.03, 0.0, 0.0), (0.003, 0.06)),
    # fumée : gaz chaud qui monte en ralentissant, poussé par le vent, en bouffées qui gonflent
    "fumee": Loi("panache de fumée", "fumee", 42, 4.0, 4.0, 4.0, 0.6, 12.0, 1.5,
                 (0.0, 0.55, 0.0), (0.35, 0.0, 0.08), (0.10, 0.75)),
    # vapeur d'eau : volutes lentes au-dessus d'une boisson ou d'une casserole
    "vapeur": Loi("vapeur d'eau", "vapeur", 26, 2.6, 2.4, 2.6, 0.25, 15.0, 2.0,
                  (0.0, 0.25, 0.0), (0.03, 0.0, 0.0), (0.012, 0.10)),
    # flamme : langues lumineuses qui montent vite et s'éteignent en rétrécissant
    "flamme": Loi("flamme", "flamme", 34, 0.8, 0.55, 0.8, 0.6, 14.0, 3.0,
                  (0.0, 2.2, 0.0), (0.0, 0.0, 0.0), (0.06, 0.005), "retrecit"),
    # jet d'eau : gouttes balistiques (fontaine, robinet, arrosoir), sans freinage notable
    "jet_liquide": Loi("jet d'eau", "eau", 90, 1.0, 0.95, 1.0, 4.4, 6.0, 50.0,
                       (0.0, -9.81, 0.0), (0.0, 0.0, 0.0), (0.028, 0.028), "constante"),
    # gouttes : chute libre une à une (fuite, robinet qui goutte)
    "gouttes": Loi("gouttes qui tombent", "eau", 6, 1.2, 0.6, 1.2, 0.0, 0.0, 50.0,
                   (0.0, -9.81, 0.0), (0.0, 0.0, 0.0), (0.018, 0.018), "constante"),
}
TYPES = tuple(LOIS)


def _base_orthonormee(d: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    a = np.array([1.0, 0.0, 0.0]) if abs(d[0]) < 0.9 else np.array([0.0, 0.0, 1.0])
    u = np.cross(d, a)
    u /= np.linalg.norm(u)
    return u, np.cross(d, u)


def _rayon(loi: Loi, age: np.ndarray) -> np.ndarray:
    r0, r1 = loi.rayon
    f = np.clip(age / loi.vie, 0.0, 1.0)
    if loi.croissance == "diffusion":
        return r0 + (r1 - r0) * np.sqrt(f)
    if loi.croissance == "retrecit":
        return r0 + (r1 - r0) * f ** 0.7
    if loi.croissance == "lineaire":
        return r0 + (r1 - r0) * f
    return np.full_like(age, r0)


@dataclass
class Emission:
    type: str
    origine: tuple[float, float, float]
    direction: tuple[float, float, float] = (0.0, 1.0, 0.0)
    echelle: float = 1.0                     # 1 = taille réelle ; une grande cheminée fume plus large
    nom: str = "emission"
    graine: int = 0
    pistes: dict[str, dict[str, Any]] = field(default_factory=dict)


def construire(emission: Emission) -> tuple[Noeud, dict[str, dict[str, Any]], dict[str, Any]]:
    """(nœud des particules, pistes d'animation par nom de nœud, mesures physiques)."""
    if emission.type not in LOIS:
        raise KeyError(f"émission hors vocabulaire : {emission.type!r}")
    loi = LOIS[emission.type]
    rng = np.random.default_rng(emission.graine)
    d = np.asarray(emission.direction, dtype=np.float64)
    d = d / (np.linalg.norm(d) or 1.0)
    u, v = _base_orthonormee(d)
    o = np.asarray(emission.origine, dtype=np.float64)
    k = emission.echelle
    temps = np.arange(0.0, loi.duree_boucle + 1e-9, 1.0 / IMAGES_PAR_SECONDE)
    temps[-1] = loi.duree_boucle
    sphere = g.sphere(1.0, subdivisions=2)
    objet = Objet("particule", "particule", [Partie(sphere, loi.materiau, "particule")], 2.0, 2.0, 2.0)
    instances, pistes = [], {}
    hauteurs, portees = [], []
    for i in range(loi.particules):
        naissance = (i / loi.particules) * loi.bouffee + rng.uniform(0, 0.02)
        theta = math.radians(loi.cone_deg) * math.sqrt(rng.uniform())
        phi = rng.uniform(0, 2 * math.pi)
        dir_i = math.cos(theta) * d + math.sin(theta) * (math.cos(phi) * u + math.sin(phi) * v)
        # similitude : un écoulement mené par la GRAVITÉ (jet, gouttes) garde ses proportions quand les vitesses
        # suivent la racine de la taille (Froude) ; un jet freiné par l'air (brume) quand elles suivent la taille
        gravitaire = loi.acceleration[1] < 0 and loi.trainee > 5.0
        v0 = loi.vitesse * (math.sqrt(k) if gravitaire else k) * rng.uniform(0.8, 1.15) * dir_i
        acc = np.asarray(loi.acceleration) * (k if loi.acceleration[1] > 0 else 1.0)
        vent = np.asarray(loi.vent) * k
        age = (temps - naissance) % loi.duree_boucle
        vivant = age < loi.vie
        tau = loi.trainee
        frein = tau * (1.0 - np.exp(-age / tau))
        pos = o + np.outer(frein, v0) + 0.5 * np.outer(age ** 2, acc) + np.outer(age, vent)
        r = _rayon(loi, age) * k * rng.uniform(0.85, 1.2)
        r = np.where(vivant, r, 1e-4)                         # jamais 0 : une matrice dégénérée gêne certains moteurs
        pos = np.where(vivant[:, None], pos, o)                # morte : rangée à l'émetteur, invisible
        nom = f"{emission.nom}_{i:03d}"
        instances.append(Instance(objet, Pose(float(o[0]), float(o[2]), 0.0, float(o[1])), nom,
                                  meta={"emission": emission.type}))
        # les poses des instances sont relatives : l'animation donne la position absolue du nœud
        pistes[nom] = {"temps": temps.tolist(), "translation": pos.tolist(),
                       "scale": np.repeat(r[:, None], 3, axis=1).tolist()}
        if vivant.any():
            hauteurs.append(float((pos[vivant, 1] - o[1]).max()))
            portees.append(float(np.linalg.norm((pos[vivant] - o)[:, [0, 2]], axis=1).max()))
    noeud = Noeud(emission.nom, instances=instances, extras={"emission": emission.type, "loi": loi.description})
    mesures = {"type": emission.type, "particules": loi.particules, "duree_boucle_s": loi.duree_boucle,
               "hauteur_max_m": round(max(hauteurs or [0.0]), 3), "portee_max_m": round(max(portees or [0.0]), 3)}
    return noeud, pistes, mesures
