"""Gaz simulés par les équations de Navier-Stokes : brume d'un vaporisateur, fumée, vapeur, flamme.

16/11/2026, Juan : « pas un effet bulle mais un vrai effet, comme les rivières et fontaines qui coulent ; même
si c'est lourd, la qualité se paye ». Une émission gazeuse n'est plus un nuage de petites sphères : c'est un
VOLUME calculé par un solveur eulérien de fluide incompressible (Stam 1999, Fedkiw 2001) :
- grille MAC (vitesses sur les faces des cellules), cellules cubiques ; le domaine est la boîte que la loi
  cinématique de l'émission (`monde.emetteurs.LOIS`) prévoit d'occuper, agrandie d'une marge ;
- à chaque pas : injection (bouffée ou flux continu, dans un cône autour de la direction d'émission, agitée par
  quelques modes de Fourier tirés de la graine), forces (poussée d'Archimède d'un gaz chaud, lourdeur d'un
  aérosol), confinement de vorticité (les volutes que la grille efface), advection semi-lagrangienne RK2
  (MacCormack limitée pour la densité : le détail fin reste), projection exacte (équation de Poisson résolue
  par transformées en sinus : bords ouverts, le gaz sort librement de la boîte) ;
- le vent est l'écoulement ambiant (champ initial uniforme, invariant par la projection) ;
- dissipation : la brume s'évapore, la fumée se dilue, la flamme se refroidit.
Le gaz est simulé à sa TAILLE RÉELLE (un vaporisateur de 15 cm, une cheminée…) puis placé à l'échelle du modèle :
la physique ne dépend pas de l'unité du maillage reconstruit.

Sortie : images de densité (et de chaleur pour une flamme) recadrées sur la région occupée, quantifiées sur 8
bits en racine (les volutes ténues gardent leur précision) et bouclées sans saut (fondu enchaîné d'un flux
continu, extinction d'une bouffée). `monde.volume_gltf` les écrit dans le GLB ; le viewer les rend par lancer
de rayons (diffusion simple ombrée, fonction de phase de Henyey-Greenstein, émission de corps noir).
"""
from __future__ import annotations

import base64
import math
import os
import struct
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

import numpy as np
from scipy import fft as sfft
from scipy import ndimage

from monde import emetteurs

GAZ = ("brume", "fumee", "vapeur", "flamme")
RESOLUTION_DEFAUT = 128            # cellules sur le plus grand côté de la boîte
RESOLUTION_PRE = 40                # pré-simulation qui mesure la région réellement occupée par le gaz
CFL = 2.5                          # cellules parcourues au plus par pas (semi-lagrangien : stable au-delà de 1)
SOUS_PAS_MAX = 24
EPONGE_CELLULES = 5.0              # épaisseur de la couche où le gaz s'efface avant de sortir de la boîte
EPONGE_S = 0.12                    # temps d'effacement au bord


@dataclass(frozen=True)
class Milieu:
    """Comportement et aspect d'un gaz : ordres de grandeur physiques, jamais un sujet."""
    description: str
    dissipation_s: float        # temps caractéristique de disparition de la densité (évaporation, dilution)
    refroidissement_s: float    # idem pour la charge qui porte la poussée (chaleur, gouttelettes en suspension)
    confinement: float          # intensité des volutes (confinement de vorticité)
    rayon_source: float         # rayon de la bouche d'émission à taille réelle (m)
    turbulence_source: float    # agitation de l'injection (fraction de la vitesse d'émission)
    albedo: tuple[float, float, float]     # couleur diffusée (linéaire)
    extinction: float           # coefficient d'extinction à densité 1 (m⁻¹, taille réelle)
    anisotropie: float          # Henyey-Greenstein g : > 0, la lumière est diffusée vers l'avant (gouttelettes)
    emission: float = 0.0       # flamme : luminance propre de la chaleur (corps noir)
    longueur_injection: float = 2.5   # longueur du cône d'injection, en rayons de source
    freinage_s: float | None = None   # mélange turbulent plus fin que la grille : une bouffée (anneau de
    # tourbillon) qui se brise perd sa quantité de mouvement en ~τ ; sans lui l'anneau simulé, trop régulier,
    # file deux fois trop loin (vaporisateur : 0,68 m simulés contre 20 à 30 cm observés)


MILIEUX: dict[str, Milieu] = {
    # brume de vaporisateur : gouttelettes de 10 à 50 µm qui s'évaporent en ~1 s ; diffusion de Mie vers l'avant
    "brume": Milieu("brume de vaporisateur", 0.85, 0.7, 3.0, 0.004, 0.5, (0.93, 0.95, 1.0), 300.0, 0.55,
                    longueur_injection=1.5, freinage_s=0.22),
    # fumée : suie grise, se dilue lentement, monte tant qu'elle est chaude
    "fumee": Milieu("fumée", 7.0, 2.5, 2.8, 0.10, 0.14, (0.40, 0.41, 0.43), 16.0, 0.25),
    # vapeur d'eau : se condense en gouttelettes visibles au-dessus de la source puis se réévapore
    "vapeur": Milieu("vapeur d'eau", 1.3, 1.8, 2.2, 0.03, 0.16, (0.96, 0.97, 1.0), 40.0, 0.45),
    # flamme : gaz brûlant qui monte vite, se refroidit en quelques dixièmes de seconde, laisse un peu de suie
    "flamme": Milieu("flamme", 0.55, 0.20, 3.4, 0.016, 0.28, (0.22, 0.21, 0.20), 7.0, 0.0, emission=7.0,
                     longueur_injection=1.5),
}


@dataclass
class VolumeAnime:
    """Volume animé prêt à écrire : images (nz, ny, nx[, canaux]) en uint8, x varie le plus vite."""
    nom: str
    milieu: str
    coin: tuple[float, float, float]      # coin minimal de la boîte, centre de la première cellule − pas/2 (m)
    pas: float                            # côté d'une cellule (m)
    dims: tuple[int, int, int]            # (nx, ny, nz)
    fps: int
    images: list[np.ndarray]
    canaux: tuple[str, ...]
    mesures: dict[str, Any] = field(default_factory=dict)
    echelle: float = 1.0                  # rapport taille du modèle / taille réelle
    densite_max: float = 1.0              # densité codée par 255 (l'opacité réelle en dépend)
    direction: tuple[float, float, float] = (0.0, 1.0, 0.0)   # sens d'émission (le viewer y fait dériver le détail)

    @property
    def boite(self) -> tuple[list[float], list[float]]:
        mn = np.asarray(self.coin, dtype=np.float64)
        return mn.tolist(), (mn + self.pas * np.asarray(self.dims, dtype=np.float64)).tolist()

    @property
    def duree_s(self) -> float:
        return len(self.images) / float(self.fps)

    def place(self, origine, echelle: float) -> "VolumeAnime":
        """Le volume simulé à taille réelle autour de (0, 0, 0), posé à `origine` et agrandi de `echelle`."""
        coin = tuple(float(o + echelle * c) for o, c in zip(origine, self.coin))
        return replace(self, coin=coin, pas=float(self.pas * echelle), echelle=float(self.echelle * echelle))

    def optique(self) -> dict[str, Any]:
        m = MILIEUX[self.milieu]
        # l'épaisseur optique d'un nuage ne dépend pas de l'unité : σ est divisé par l'agrandissement ; elle
        # s'applique à la densité décodée (0..1), donc multipliée par la densité que code 255
        return {"albedo": [round(c, 4) for c in m.albedo],
                "extinction": round(m.extinction * self.densite_max / self.echelle, 5),
                "anisotropie": m.anisotropie, "emission": m.emission}


# ── domaine ─────────────────────────────────────────────────────────────────────────────────────────
def _boite_de_la_loi(type_: str, direction: np.ndarray, graine: int) -> tuple[np.ndarray, np.ndarray]:
    """Boîte qu'occupe l'émission d'après sa loi cinématique (trajectoires des parcelles ± leur rayon)."""
    _, pistes, _ = emetteurs.construire(emetteurs.Emission(type_, origine=(0.0, 0.0, 0.0),
                                                            direction=tuple(direction), graine=graine))
    points = []
    for piste in pistes.values():
        pos = np.asarray(piste["translation"])
        r = np.asarray(piste["scale"])[:, :1]
        vivant = r[:, 0] > 1e-3
        points.append(pos[vivant] - r[vivant])
        points.append(pos[vivant] + r[vivant])
    p = np.concatenate(points) if points else np.zeros((1, 3))
    mn, mx = np.minimum(p.min(axis=0), 0.0), np.maximum(p.max(axis=0), 0.0)
    marge = 0.3 * (mx - mn).max()
    # le gaz continue de dériver après la bouffée : la marge est doublée dans le sens où il part
    avant = np.where(direction > 0.3, marge * (1.0 + direction), marge)
    arriere = np.where(direction < -0.3, marge * (1.0 - direction), marge)
    return mn - arriere, mx + avant


# ── opérateurs ──────────────────────────────────────────────────────────────────────────────────────
class _Grille:
    def __init__(self, n: tuple[int, int, int], h: float):
        self.n, self.h = n, h
        nx, ny, nz = n
        self.decalages = {"c": (0.5, 0.5, 0.5), "u": (0.0, 0.5, 0.5), "v": (0.5, 0.0, 0.5), "w": (0.5, 0.5, 0.0)}
        formes = {"c": (nx, ny, nz), "u": (nx + 1, ny, nz), "v": (nx, ny + 1, nz), "w": (nx, ny, nz + 1)}
        self.formes = formes
        self.positions = {}
        for cle, forme in formes.items():
            d = self.decalages[cle]
            idx = np.indices(forme, dtype=np.float32)
            self.positions[cle] = np.stack([idx[a] + d[a] for a in range(3)])
        # valeurs propres du laplacien discret, bords ouverts (pression nulle sur les faces du domaine)
        lam = [2.0 * np.cos(np.pi * (np.arange(m) + 1) / m) - 2.0 for m in n]
        self.lam = (lam[0][:, None, None] + lam[1][None, :, None] + lam[2][None, None, :]).astype(np.float64)

    def echantillon(self, champ: np.ndarray, cle: str, positions: np.ndarray) -> np.ndarray:
        d = self.decalages[cle]
        coords = np.stack([positions[a] - d[a] for a in range(3)])
        return ndimage.map_coordinates(champ, coords, order=1, mode="nearest", prefilter=False)

    def vitesse(self, u, v, w, positions: np.ndarray) -> np.ndarray:
        """Vitesse (cellules par seconde) aux positions données (unités de grille)."""
        return np.stack([self.echantillon(u, "u", positions), self.echantillon(v, "v", positions),
                         self.echantillon(w, "w", positions)]) / self.h


def _centres(u, v, w):
    return 0.5 * (u[1:] + u[:-1]), 0.5 * (v[:, 1:] + v[:, :-1]), 0.5 * (w[:, :, 1:] + w[:, :, :-1])


def _vers_faces(fx, fy, fz):
    """Champ aux centres → composantes sur les faces (moyenne des deux cellules voisines, bord recopié)."""
    gx = np.concatenate([fx[:1], 0.5 * (fx[1:] + fx[:-1]), fx[-1:]], axis=0)
    gy = np.concatenate([fy[:, :1], 0.5 * (fy[:, 1:] + fy[:, :-1]), fy[:, -1:]], axis=1)
    gz = np.concatenate([fz[:, :, :1], 0.5 * (fz[:, :, 1:] + fz[:, :, :-1]), fz[:, :, -1:]], axis=2)
    return gx, gy, gz


def _projeter(g: _Grille, u, v, w, dt: float) -> None:
    """Rend la vitesse incompressible (div = 0 exactement) ; pression nulle hors du domaine (bords ouverts)."""
    h = g.h
    div = (u[1:] - u[:-1] + v[:, 1:] - v[:, :-1] + w[:, :, 1:] - w[:, :, :-1]) / h
    rhs = div * (h * h / dt)
    p = sfft.idstn(sfft.dstn(rhs, type=2, norm="ortho", workers=-1) / g.lam, type=2, norm="ortho", workers=-1)
    p = p.astype(np.float32)
    k = dt / h
    u[1:-1] -= k * (p[1:] - p[:-1])
    u[0] -= k * 2.0 * p[0]
    u[-1] += k * 2.0 * p[-1]
    v[:, 1:-1] -= k * (p[:, 1:] - p[:, :-1])
    v[:, 0] -= k * 2.0 * p[:, 0]
    v[:, -1] += k * 2.0 * p[:, -1]
    w[:, :, 1:-1] -= k * (p[:, :, 1:] - p[:, :, :-1])
    w[:, :, 0] -= k * 2.0 * p[:, :, 0]
    w[:, :, -1] += k * 2.0 * p[:, :, -1]


def _confinement(g: _Grille, u, v, w, presence: np.ndarray, epsilon: float):
    """Force qui ravive les tourbillons à l'échelle de la grille (Fedkiw, Stam, Jensen 2001), là où est le gaz."""
    h = g.h
    uc, vc, wc = _centres(u, v, w)
    wx = np.gradient(wc, h, axis=1) - np.gradient(vc, h, axis=2)
    wy = np.gradient(uc, h, axis=2) - np.gradient(wc, h, axis=0)
    wz = np.gradient(vc, h, axis=0) - np.gradient(uc, h, axis=1)
    mag = np.sqrt(wx * wx + wy * wy + wz * wz)
    gx, gy, gz = np.gradient(mag, h)
    norme = np.sqrt(gx * gx + gy * gy + gz * gz) + 1e-6
    nx_, ny_, nz_ = gx / norme, gy / norme, gz / norme
    k = epsilon * h * presence
    return k * (ny_ * wz - nz_ * wy), k * (nz_ * wx - nx_ * wz), k * (nx_ * wy - ny_ * wx)


# ── simulation ──────────────────────────────────────────────────────────────────────────────────────
def _modes(rng: np.random.Generator, n: int = 6) -> list[tuple[np.ndarray, float, float, np.ndarray]]:
    """Quelques ondes planes aléatoires (vecteur d'onde, pulsation, phase, direction) : une agitation lisse."""
    modes = []
    for _ in range(n):
        k = rng.normal(size=3)
        k /= np.linalg.norm(k)
        a = rng.normal(size=3)
        a -= a.dot(k) * k                      # transverse : n'ajoute pas de divergence
        a /= np.linalg.norm(a) or 1.0
        modes.append((k * rng.uniform(0.6, 1.6), rng.uniform(4.0, 14.0), rng.uniform(0, 2 * np.pi), a))
    return modes


def simuler(type_: str, *, direction=(0.0, 1.0, 0.0), graine: int = 0, resolution: int | None = None,
            nom: str = "gaz", duree_s: float | None = None, boite: tuple | None = None) -> VolumeAnime:
    """Simule l'émission `type_` à taille réelle, source en (0, 0, 0). Rend le volume animé bouclé.

    Le domaine est d'abord celui que prévoit la loi cinématique ; une pré-simulation grossière mesure où va
    vraiment le gaz, et la simulation finale ne couvre que cette région (avec une marge) : toutes les cellules
    servent au nuage, deux à trois fois plus fines à coût égal."""
    if type_ not in MILIEUX:
        raise KeyError(f"gaz hors vocabulaire : {type_!r}")
    loi, milieu = emetteurs.LOIS[type_], MILIEUX[type_]
    n_max = int(resolution or os.environ.get("AURORA_GAZ_RESOLUTION") or RESOLUTION_DEFAUT)
    rng = np.random.default_rng(graine)
    d = np.asarray(direction, dtype=np.float64)
    d /= np.linalg.norm(d) or 1.0
    if boite is not None:
        mn, mx = (np.asarray(b, dtype=np.float64) for b in boite)
    elif n_max > RESOLUTION_PRE:
        essai = simuler(type_, direction=tuple(d), graine=graine, resolution=RESOLUTION_PRE, duree_s=duree_s)
        bas, haut = (np.asarray(b, dtype=np.float64) for b in essai.boite)
        marge = 0.15 * (haut - bas).max()
        mn = np.minimum(bas - marge, -3.0 * milieu.rayon_source)
        mx = np.maximum(haut + marge, 3.0 * milieu.rayon_source)
    else:
        mn, mx = _boite_de_la_loi(type_, d, graine)
    h = float((mx - mn).max() / n_max)
    n = tuple(int(max(8, math.ceil((mx[a] - mn[a]) / h))) for a in range(3))
    g = _Grille(n, h)
    coin = mn.astype(np.float64)

    fps = emetteurs.IMAGES_PAR_SECONDE
    boucle = float(duree_s or loi.duree_boucle)
    continu = loi.bouffee >= loi.duree_boucle - 1e-6
    chauffe = min(4.0, max(1.0, milieu.dissipation_s)) if continu else 0.0
    fondu = min(0.6, 0.25 * boucle) if continu else 0.0
    n_images = int(round((chauffe + boucle + fondu) * fps))

    vent = np.asarray(loi.vent, dtype=np.float32)
    u = np.full(g.formes["u"], vent[0], np.float32)
    v = np.full(g.formes["v"], vent[1], np.float32)
    w = np.full(g.formes["w"], vent[2], np.float32)
    rho = np.zeros(g.formes["c"], np.float32)
    charge = np.zeros(g.formes["c"], np.float32)

    # région d'injection : cône court autour de la direction, à partir de la bouche. Une bouche plus petite
    # que la grille garde le flux de quantité de mouvement (ρv²A) et le débit de matière (ρvA) de la taille
    # réelle : le jet lointain (turbulent, auto-semblable) ne dépend que d'eux, pas de la résolution.
    rs = max(milieu.rayon_source, 1.5 * h)
    reduction = milieu.rayon_source / rs
    vitesse_source = loi.vitesse * reduction
    densite_source = reduction
    longueur = milieu.longueur_injection * rs
    tan_c = math.tan(math.radians(loi.cone_deg))
    o_grille = (-coin) / h                                     # la source, en unités de grille

    def poids(cle: str) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        pos = g.positions[cle].reshape(3, -1).T
        rel = (pos - o_grille) * h
        le_long = rel @ d
        radial = rel - np.outer(le_long, d)
        dist = np.linalg.norm(radial, axis=1)
        r_eff = rs + np.maximum(le_long, 0.0) * tan_c
        wgt = np.exp(-2.0 * (dist / r_eff) ** 2) * np.exp(-2.0 * (np.maximum(le_long, 0.0) / longueur) ** 2)
        wgt[le_long < -0.75 * rs] = 0.0
        ici = np.flatnonzero(wgt > 1e-3)                       # seules ces cellules sont touchées
        ouverture = np.where(dist[ici, None] > 1e-9, radial[ici] / np.maximum(dist[ici], 1e-9)[:, None], 0.0)
        cible = d[None, :] + ouverture * (tan_c * np.clip(dist[ici] / r_eff[ici], 0.0, 1.0))[:, None]
        cible /= np.linalg.norm(cible, axis=1, keepdims=True)
        return ici, wgt[ici].astype(np.float32), cible.astype(np.float32), (pos[ici] * h).astype(np.float32)

    injection = {cle: poids(cle) for cle in ("c", "u", "v", "w")}
    # couche éponge : près des faces de la boîte le gaz s'efface doucement (jamais de coupure nette visible)
    bord = np.minimum.reduce([np.minimum(g.positions["c"][a], n[a] - g.positions["c"][a]) for a in range(3)])
    taux_eponge = ((1.0 - np.clip(bord / EPONGE_CELLULES, 0.0, 1.0)) ** 2 / EPONGE_S).astype(np.float32)
    modes = _modes(rng)
    acc = np.asarray(loi.acceleration, dtype=np.float32)
    echelle_agitation = max(rs * 4.0, 2.0 * h)

    def activite(t: float) -> float:
        if continu:
            return float(max(0.0, 1.0 + 0.22 * math.sin(2 * math.pi * 1.3 * t + graine)
                             + 0.12 * math.sin(2 * math.pi * 3.1 * t + 2.0 * graine)))
        b = loi.bouffee
        return float(np.clip(t / 0.03, 0.0, 1.0) * np.clip((b - t) / 0.06, 0.0, 1.0))

    def agitation(x: np.ndarray, t: float) -> np.ndarray:
        x = x / echelle_agitation
        tot = np.zeros((x.shape[0], 3), np.float32)
        for k, om, ph, a in modes:
            tot += np.sin(x @ k + om * t + ph)[:, None].astype(np.float32) * a[None, :].astype(np.float32)
        return tot / math.sqrt(len(modes))

    def injecter(t: float, dt: float) -> None:
        a = activite(t)
        if a <= 0.0:
            return
        vitesse = vitesse_source * (0.75 + 0.25 * a)
        gamma = 1.0 - math.exp(-dt / 0.008)
        for axe, (cle, champ) in enumerate((("u", u), ("v", v), ("w", w))):
            ici, wgt, cible, x = injection[cle]
            vt = vitesse * (cible[:, axe] + milieu.turbulence_source * agitation(x, t)[:, axe]) + vent[axe]
            k = np.clip(wgt * a, 0.0, 1.0) * gamma
            plat = champ.reshape(-1)
            plat[ici] += k * (vt - plat[ici])
        ici, wgt, _, _ = injection["c"]
        apport = wgt * min(a, 1.0) * densite_source
        for champ in (rho, charge):
            plat = champ.reshape(-1)
            plat[ici] = np.maximum(plat[ici], apport)

    def advecter_vitesse(dt: float):
        nouveaux = []
        for cle, champ in (("u", u), ("v", v), ("w", w)):
            p = g.positions[cle]
            k1 = g.vitesse(u, v, w, p)
            k2 = g.vitesse(u, v, w, p - 0.5 * dt * k1)
            nouveaux.append(g.echantillon(champ, cle, p - dt * k2))
        return nouveaux

    def advecter_scalaires(dt: float, champs: list[np.ndarray]) -> list[np.ndarray]:
        p = g.positions["c"]
        uc, vc, wc = _centres(u, v, w)
        k1 = np.stack([uc, vc, wc]) / h
        arriere = p - dt * g.vitesse(u, v, w, p - 0.5 * dt * k1)
        avant = p + dt * g.vitesse(u, v, w, p + 0.5 * dt * k1)
        sortie = []
        for q in champs:
            q1 = g.echantillon(q, "c", arriere)
            q0 = g.echantillon(q1, "c", avant)
            mc = q1 + 0.5 * (q - q0)                           # MacCormack (Selle 2008)
            lo = g.echantillon(ndimage.minimum_filter(q, size=3), "c", arriere)
            hi = g.echantillon(ndimage.maximum_filter(q, size=3), "c", arriere)
            sortie.append(np.clip(mc, lo, hi))
        return sortie

    images_rho, images_chaleur = [], []
    t = 0.0
    tau_rho, tau_charge = milieu.dissipation_s, milieu.refroidissement_s
    for f in range(n_images):
        fin = (f + 1) / fps
        while t < fin - 1e-9:
            vmax = max(float(np.abs(u).max()), float(np.abs(v).max()), float(np.abs(w).max()),
                       vitesse_source * (1.0 if activite(t) > 0 else 0.0), 1e-3)
            dt = min(fin - t, max(CFL * h / vmax, (1.0 / fps) / SOUS_PAS_MAX))
            injecter(t, dt)
            presence = np.clip(4.0 * (rho + charge), 0.0, 1.0)
            fx, fy, fz = _confinement(g, u, v, w, presence, milieu.confinement)
            fx = fx + acc[0] * charge
            fy = fy + acc[1] * charge
            fz = fz + acc[2] * charge
            gx, gy, gz = _vers_faces(fx, fy, fz)
            u += dt * gx
            v += dt * gy
            w += dt * gz
            if milieu.freinage_s:
                kx, ky, kz = _vers_faces(*(presence * (1.0 - math.exp(-dt / milieu.freinage_s)),) * 3)
                u += kx * (vent[0] - u)
                v += ky * (vent[1] - v)
                w += kz * (vent[2] - w)
            u[...], v[...], w[...] = advecter_vitesse(dt)
            _projeter(g, u, v, w, dt)
            rho[...], charge[...] = advecter_scalaires(dt, [rho, charge])
            eponge = np.exp(-dt * taux_eponge)
            rho *= math.exp(-dt / tau_rho) * eponge
            charge *= math.exp(-dt / tau_charge) * eponge
            np.clip(rho, 0.0, None, out=rho)
            np.clip(charge, 0.0, None, out=charge)
            t += dt
        if t >= chauffe - 1e-9:
            images_rho.append(rho.copy())
            if type_ == "flamme":
                images_chaleur.append(charge.copy())

    images_rho, images_chaleur = _boucler(images_rho, images_chaleur, int(round(boucle * fps)), continu)
    mesures = _mesurer(images_rho, coin, h, d, continu)
    volume = _quantifier(nom, type_, coin, h, fps, images_rho, images_chaleur, mesures)
    volume.direction = tuple(float(c) for c in d)
    return volume


def _boucler(rhos: list, chaleurs: list, n: int, continu: bool) -> tuple[list, list]:
    """Boucle sans saut : fondu enchaîné de la fin sur le début (flux continu) ou extinction finale (bouffée)."""
    def fondre(images: list) -> list:
        if not images:
            return images
        if continu:
            m = len(images) - n
            sortie = [im.copy() for im in images[:n]]
            for i in range(m):
                a = (i + 0.5) / m                              # 0 → image de la fin, 1 → image du début
                sortie[i] = a * images[i] + (1.0 - a) * images[n + i]
            return sortie
        sortie = [im.copy() for im in images[:n]]
        k = max(1, int(0.15 * n))
        for i in range(k):
            sortie[n - k + i] *= 0.5 * (1.0 + math.cos(math.pi * (i + 1) / k))
        return sortie
    return fondre(rhos), fondre(chaleurs)


def _mesurer(images: list[np.ndarray], coin: np.ndarray, h: float, d: np.ndarray, continu: bool) -> dict[str, Any]:
    """Portée (le long de la direction), hauteur et largeur où se trouve la MASSE du gaz (centiles pondérés :
    une volute isolée ne fait pas la mesure) ; raccord de la boucle."""
    forme = images[0].shape
    idx = np.indices(forme, dtype=np.float32).reshape(3, -1).T
    pos = np.asarray(coin, dtype=np.float32) + (idx + 0.5) * h
    le_long = pos @ d.astype(np.float32)
    radial = np.linalg.norm(pos - np.outer(le_long, d.astype(np.float32)), axis=1)

    def centile(valeurs: np.ndarray, masse: np.ndarray, q: float) -> float:
        ordre = np.argsort(valeurs)
        cumul = np.cumsum(masse[ordre])
        return float(valeurs[ordre][np.searchsorted(cumul, q * cumul[-1])])

    portee = hauteur = largeur = 0.0
    masses = []
    for im in images:
        m = im.reshape(-1).astype(np.float64)
        total = float(m.sum())
        masses.append(total)
        if total <= 1e-9:
            continue
        portee = max(portee, centile(le_long, m, 0.98))
        hauteur = max(hauteur, centile(pos[:, 1], m, 0.98))
        largeur = max(largeur, 2.0 * centile(radial, m, 0.90))
    pic = max(masses) or 1.0
    if continu:
        # un raccord sans saut change autant que deux images voisines quelconques (rapport ≈ 1)
        voisins = [float(np.abs(images[i + 1] - images[i]).sum()) for i in range(len(images) - 1)]
        raccord = float(np.abs(images[0] - images[-1]).sum()) / (float(np.median(voisins)) or 1.0)
    else:
        raccord = masses[-1] / pic                              # une bouffée est éteinte avant de recommencer
    return {"portee_m": round(portee, 4), "hauteur_m": round(hauteur, 4), "largeur_m": round(largeur, 4),
            "masse_pic_image": int(np.argmax(masses)), "raccord_boucle": round(raccord, 4), "images": len(images)}


def _quantifier(nom, type_, coin, h, fps, rhos, chaleurs, mesures) -> VolumeAnime:
    """Recadre sur la région occupée, quantifie en racine sur 8 bits, x le plus rapide (texture 3D)."""
    pic = max(float(im.max()) for im in rhos) or 1.0
    occupe = np.zeros(rhos[0].shape, bool)
    for im in rhos:
        occupe |= im > 0.004 * pic
    for im in chaleurs:
        occupe |= im > 0.004 * (max(float(c.max()) for c in chaleurs) or 1.0)
    idx = np.argwhere(occupe)
    if not len(idx):
        lo, hi = np.zeros(3, int), np.array(rhos[0].shape)
    else:
        lo = np.maximum(idx.min(axis=0) - 1, 0)
        hi = np.minimum(idx.max(axis=0) + 2, np.array(rhos[0].shape))
    tranche = tuple(slice(int(a), int(b)) for a, b in zip(lo, hi))
    pic_c = max((float(c.max()) for c in chaleurs), default=1.0) or 1.0

    def coder(im: np.ndarray, echelle: float) -> np.ndarray:
        q = np.sqrt(np.clip(im[tranche] / echelle, 0.0, 1.0)) * 255.0
        return np.ascontiguousarray(np.round(q).astype(np.uint8).transpose(2, 1, 0))     # (nz, ny, nx)

    images = []
    for i, im in enumerate(rhos):
        dens = coder(im, pic)
        images.append(np.ascontiguousarray(np.stack([dens, coder(chaleurs[i], pic_c)], axis=-1)) if chaleurs else dens)
    dims = tuple(int(b - a) for a, b in zip(lo, hi))
    coin_r = tuple(float(c + a * h) for c, a in zip(coin, lo))
    canaux = ("densite", "chaleur") if chaleurs else ("densite",)
    return VolumeAnime(nom, type_, coin_r, float(h), dims, fps, images, canaux, mesures, densite_max=pic)


# ── vérification indépendante (f3d lit les volumes VTK) ─────────────────────────────────────────────
def ecrire_vti(volume: VolumeAnime, indice: int, chemin: str | Path) -> Path:
    """Une image du volume en ImageData VTK (densité décodée, flottants) : f3d --volume la rend sans notre code."""
    chemin = Path(chemin)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    im = volume.images[indice]
    q = (im[..., 0] if im.ndim == 4 else im).astype(np.float32) / 255.0
    dens = np.ascontiguousarray((q * q).astype("<f4"))
    nx, ny, nz = volume.dims
    brut = dens.tobytes()
    donnees = base64.b64encode(struct.pack("<Q", len(brut)) + brut).decode("ascii")
    o = [c + 0.5 * volume.pas for c in volume.coin]
    chemin.write_text(
        '<?xml version="1.0"?>\n'
        '<VTKFile type="ImageData" version="1.0" byte_order="LittleEndian" header_type="UInt64">\n'
        f'  <ImageData WholeExtent="0 {nx - 1} 0 {ny - 1} 0 {nz - 1}" Origin="{o[0]} {o[1]} {o[2]}" '
        f'Spacing="{volume.pas} {volume.pas} {volume.pas}">\n'
        f'    <Piece Extent="0 {nx - 1} 0 {ny - 1} 0 {nz - 1}">\n'
        '      <PointData Scalars="densite">\n'
        f'        <DataArray type="Float32" Name="densite" format="binary">{donnees}</DataArray>\n'
        '      </PointData>\n    </Piece>\n  </ImageData>\n</VTKFile>\n', encoding="ascii")
    return chemin
