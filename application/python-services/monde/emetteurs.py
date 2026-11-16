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

from monde import geometrie as g, vocabulaire
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
    rayon_buse: float = 0.0     # liquide : rayon de la bouche d'un jet continu (m, taille réelle)


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
                       (0.0, -9.81, 0.0), (0.0, 0.0, 0.0), (0.028, 0.028), "constante", rayon_buse=0.011),
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


# ── liquide continu : la veine d'un jet ─────────────────────────────────────────────────────────────
# 16/11/2026, Juan : « pas un effet bulle mais un vrai effet, comme les rivières et fontaines qui coulent ».
# Un jet d'eau n'est pas un chapelet de billes : c'est une VEINE continue, cohérente sur toute sa montée,
# qui ne se brise qu'en ralentissant. Lois :
# - trajectoire balistique de l'axe (gravité ; la traînée de l'air est négligeable pour une veine pleine) ;
# - rayon par conservation du débit : r = r₀·√(v₀/v) (la veine s'amincit en accélérant, s'épaissit en
#   ralentissant) ;
# - ondulation de Plateau-Rayleigh : longueur d'onde la plus instable ≈ 9,02 rayons, amplitude qui croît
#   le long de la veine (l'instabilité grandit avec le temps de vol) ;
# - là où la veine est trop lente (sommet d'un jet vertical, 25 % de v₀) ou atteint le niveau de réception,
#   l'eau se brise en GOUTTES balistiques (couronne qui retombe dans la vasque) et ÉCLABOUSSE en touchant
#   la surface ;
# - la surface de la veine porte des UV le long de l'écoulement (u autour, v le long, en mètres) et un
#   matériau d'eau vive qui défile à la vitesse du jet (aurora.flow.v1, défilement continu) : elle COULE.
LONGUEUR_ONDE_RAYLEIGH = 9.02
SECTIONS_VEINE = 18
RUPTURE = 0.25                     # fraction de v₀ sous laquelle la veine se brise en gouttes


def _repere_transporte(tangentes: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Repère par transport parallèle le long d'une courbe (pas de vrille de la section)."""
    n = np.zeros_like(tangentes)
    a = np.array([1.0, 0.0, 0.0]) if abs(tangentes[0][0]) < 0.9 else np.array([0.0, 0.0, 1.0])
    n[0] = np.cross(tangentes[0], a)
    n[0] /= np.linalg.norm(n[0])
    for i in range(1, len(tangentes)):
        v = n[i - 1] - (n[i - 1] @ tangentes[i]) * tangentes[i]
        norme = np.linalg.norm(v)
        n[i] = v / norme if norme > 1e-9 else n[i - 1]
    return n, np.cross(tangentes, n)


def _tube(points: np.ndarray, rayons: np.ndarray, abscisses: np.ndarray) -> "trimesh.Trimesh":
    import trimesh
    from trimesh.visual import TextureVisuals
    t = np.gradient(points, axis=0)
    t /= np.linalg.norm(t, axis=1, keepdims=True)
    n, b = _repere_transporte(t)
    theta = np.linspace(0.0, 2.0 * math.pi, SECTIONS_VEINE + 1)
    c, s = np.cos(theta), np.sin(theta)
    radial = c[None, :, None] * n[:, None, :] + s[None, :, None] * b[:, None, :]
    sommets = points[:, None, :] + rayons[:, None, None] * radial
    m, k = len(points), SECTIONS_VEINE + 1
    i, j = np.meshgrid(np.arange(m - 1), np.arange(SECTIONS_VEINE), indexing="ij")
    a0, a1 = i * k + j, i * k + j + 1
    b0, b1 = (i + 1) * k + j, (i + 1) * k + j + 1
    faces = np.concatenate([np.stack([a0, b0, a1], -1).reshape(-1, 3), np.stack([a1, b0, b1], -1).reshape(-1, 3)])
    perimetre = 2.0 * math.pi * float(np.mean(rayons))
    uv = np.stack(np.broadcast_arrays((theta / (2.0 * math.pi) * perimetre)[None, :], abscisses[:, None]), -1)
    maillage = trimesh.Trimesh(vertices=sommets.reshape(-1, 3), faces=faces,
                               vertex_normals=radial.reshape(-1, 3), process=False)
    maillage.visual = TextureVisuals(uv=uv.reshape(-1, 2))     # en mètres : l'exporteur divise par taille_m
    return maillage


def veine(emission: Emission, *, niveau: float, receptacle: float | None = None
          ) -> tuple[Noeud, dict[str, dict[str, Any]], dict[str, Any]]:
    """Jet liquide continu : (nœud veine + gouttes, pistes des gouttes, mesures). `niveau` : hauteur de la
    surface qui reçoit l'eau (vasque, sol) ; `receptacle` : rayon dans lequel la couronne doit retomber."""
    loi = LOIS[emission.type]
    if not loi.rayon_buse:
        raise KeyError(f"{emission.type!r} n'est pas un liquide en veine")
    rng = np.random.default_rng(emission.graine)
    k = emission.echelle
    d = np.asarray(emission.direction, dtype=np.float64)
    d /= np.linalg.norm(d) or 1.0
    o = np.asarray(emission.origine, dtype=np.float64)
    gvec = np.asarray(loi.acceleration, dtype=np.float64)
    v0 = loi.vitesse * math.sqrt(k)                               # similitude de Froude
    r0 = loi.rayon_buse * k
    dt = 0.002
    t = np.arange(0.0, 6.0, dt)
    pos = o + np.outer(t, v0 * d) + 0.5 * np.outer(t * t, gvec)
    vit = v0 * d + np.outer(t, gvec)
    vitesse = np.linalg.norm(vit, axis=1)
    lent = np.flatnonzero(vitesse < RUPTURE * v0)
    recu = np.flatnonzero((vit[:, 1] < 0) & (pos[:, 1] <= niveau))
    fin = int(min(lent[0] if len(lent) else len(t) - 1, recu[0] if len(recu) else len(t) - 1))
    fin = max(fin, 2)
    brisee = len(lent) > 0 and lent[0] <= fin                      # sommet d'un jet : la veine se brise
    # rééchantillonnage régulier en abscisse curviligne
    pas = np.linalg.norm(np.diff(pos[:fin + 1], axis=0), axis=1)
    abscisse = np.concatenate([[0.0], np.cumsum(pas)])
    longueur = float(abscisse[-1])
    n_anneaux = int(np.clip(longueur / (0.7 * r0), 12, 420))
    s_r = np.linspace(0.0, longueur, n_anneaux)
    points = np.stack([np.interp(s_r, abscisse, pos[:fin + 1, a]) for a in range(3)], axis=1)
    v_r = np.interp(s_r, abscisse, vitesse[:fin + 1])
    rayons = r0 * np.sqrt(v0 / np.maximum(v_r, RUPTURE * v0))
    phase = rng.uniform(0, 2 * math.pi)
    amplitude = 0.03 + 0.12 * (s_r / max(longueur, 1e-6))
    rayons = rayons * (1.0 + amplitude * np.sin(2 * math.pi * s_r / (LONGUEUR_ONDE_RAYLEIGH * r0) + phase))
    rayons[-1] *= 0.35 if brisee else 1.0                          # la veine s'ouvre en couronne au sommet
    veine_m = _tube(points, rayons, s_r)

    # gouttes : couronne (veine brisée) ou rupture au point de réception, puis éclaboussures
    p_fin, v_fin = pos[fin], vit[fin]
    temps = np.arange(0.0, loi.duree_boucle + 1e-9, 1.0 / IMAGES_PAR_SECONDE)
    temps[-1] = loi.duree_boucle
    chute = max(1e-3, p_fin[1] - niveau)
    t_chute = (v_fin[1] + math.sqrt(max(0.0, v_fin[1] ** 2 + 2.0 * abs(gvec[1]) * chute))) / abs(gvec[1])
    ouverture = (0.8 * receptacle / t_chute) if receptacle else 0.25 * v0
    sphere = g.sphere(1.0, subdivisions=1)                         # une goutte de quelques mm : 80 faces suffisent
    objet = Objet("goutte", "goutte", [Partie(sphere, "eau_vive", "goutte")], 2.0, 2.0, 2.0)
    instances, pistes, impacts = [], {}, []
    n_gouttes = loi.particules

    def goutte(nom: str, depart: np.ndarray, v_init: np.ndarray, rayon: float, naissance: float, vie_max: float):
        age = (temps - naissance) % loi.duree_boucle
        x = depart + np.outer(age, v_init) + 0.5 * np.outer(age * age, gvec)
        # temps de vol jusqu'au niveau de réception
        a_, b_, c_ = 0.5 * gvec[1], v_init[1], depart[1] - niveau
        disc = b_ * b_ - 4 * a_ * c_
        vol = (-b_ - math.sqrt(disc)) / (2 * a_) if disc > 0 and a_ != 0 else vie_max
        vie = float(np.clip(vol, 0.05, vie_max))
        vivant = age < vie
        r = np.where(vivant, rayon, 1e-4)
        x = np.where(vivant[:, None], x, depart)
        instances.append(Instance(objet, Pose(float(depart[0]), float(depart[2]), 0.0, float(depart[1])), nom,
                                  meta={"emission": emission.type}))
        pistes[nom] = {"temps": temps.tolist(), "translation": x.tolist(), "scale": np.repeat(r[:, None], 3, 1).tolist()}
        return depart + v_init * vie + 0.5 * gvec * vie * vie

    for i in range(n_gouttes):
        phi = rng.uniform(0, 2 * math.pi)
        horizontale = np.array([math.cos(phi), 0.0, math.sin(phi)])
        v_i = v_fin + horizontale * ouverture * math.sqrt(rng.uniform(0.15, 1.0)) \
            + np.array([0.0, rng.normal(0, 0.05 * v0), 0.0])            # la couronne retombe DANS la vasque
        naissance = (i / n_gouttes) * loi.duree_boucle + rng.uniform(0, 0.02)
        impacts.append(goutte(f"{emission.nom}_goutte_{i:03d}", p_fin, v_i, r0 * rng.uniform(0.25, 0.55), naissance,
                              loi.duree_boucle * 0.95))
    # éclaboussures : là où retombent les gouttes, de petites gouttes rebondissent (vitesse ~ un tiers)
    for i in range(n_gouttes // 3):
        point = impacts[int(rng.integers(len(impacts)))].copy()
        point[1] = niveau
        phi = rng.uniform(0, 2 * math.pi)
        incl = math.radians(rng.uniform(15, 40))
        v_e = 0.3 * math.sqrt(2 * abs(gvec[1]) * chute) * np.array([math.cos(phi) * math.sin(incl), math.cos(incl),
                                                                   math.sin(phi) * math.sin(incl)])
        goutte(f"{emission.nom}_eclat_{i:03d}", point + np.array([0, 0.002, 0]), v_e, r0 * rng.uniform(0.12, 0.25),
               rng.uniform(0, loi.duree_boucle), 0.35)

    vitesse_moyenne = float(np.mean(v_r))
    taille_uv = float(vocabulaire.materiau("eau_vive")["taille_m"])
    ecoulement = {"schema": "aurora.flow.v1", "vitesse": round(vitesse_moyenne, 3),
                  "vitesse_uv": round(vitesse_moyenne / taille_uv, 4), "direction": [0.0, -1.0],
                  "masque": "aucun", "defilement": "continu"}
    noeud = Noeud(emission.nom, parties=[Partie(veine_m, "eau_vive", "veine")], instances=instances,
                  extras={"emission": emission.type, "loi": "veine liquide continue", "ecoulement_materiaux":
                          {"eau_vive": ecoulement}})
    mesures = {"type": emission.type, "rendu": "veine", "longueur_veine_m": round(longueur, 3),
               "hauteur_max_m": round(float((points[:, 1] - o[1]).max()), 3), "brisee_au_sommet": bool(brisee),
               "rayon_buse_m": round(r0, 4), "rayon_max_m": round(float(rayons.max()), 4), "gouttes": len(instances),
               "rayon_couronne_m": round(float(np.max([np.linalg.norm((q - p_fin)[[0, 2]]) for q in impacts])), 3),
               "vitesse_moyenne_m_s": round(vitesse_moyenne, 3)}
    return noeud, pistes, mesures
