"""Matériaux PBR du moteur de scènes : une clé du vocabulaire → un matériau glTF (trimesh PBRMaterial).

Interface stable (toutes les briques et l'exporteur s'y fient) :
- `materiau_trimesh(cle, resolution=512) -> PBRMaterial`, mis en cache par (cle, resolution) ;
- `couleur_srgb(hex)`, `couleur_lineaire(hex) -> (r, g, b)` : sRGB → linéaire (les facteurs glTF sont
  linéaires, les textures de couleur sont en sRGB) ;
- `textures(cle, resolution) -> dict[str, PIL.Image]` : {"couleur", "orm", "normale"} pour TOUTE clé de
  `vocabulaire.MATERIAUX` (avec ou sans « :couleur ») ;
- `planche(cles, resolution)` : planche de contrôle ; `_verifier_repetable(img)` : bords raccordés.

Les textures sont des MOTIFS RÉPÉTABLES (bords raccordés) dont un carreau couvre `taille_m` mètres :
l'exporteur divise les UV (en mètres) par `taille_m`. Les motifs sont donc dessinés à l'échelle réelle,
en mètres, puis échantillonnés : lames de parquet de 12 à 20 cm, briques de 21,5 × 6,5 cm, carreaux métro
de 7,5 × 15 cm, une travée × un étage pour les façades. Lois générales, aucune scène particulière :

- périodicité : tout motif est construit sur le TORE du carreau. Bruits = bruit blanc filtré par FFT
  (périodique par construction) ; pavages = nombre ENTIER de modules par carreau (le module réel est
  ajusté au plus proche diviseur) ; Voronoï périodique (`cKDTree(boxsize=T)`) ; gradients enroulés ;
- couleur : `spec["couleur"]` (« :couleur » déjà appliqué) est la couleur MOYENNE perçue de loin ; le
  motif module autour d'elle en linéaire, puis un gain par canal ramène la moyenne sRGB sur la cible.
  L'albédo est borné à 0,90 (linéaire) : aucun matériau réel ne renvoie toute la lumière, et une
  texture #FFFFFF est la première cause de blanc pur au rendu ;
- rugosité : modulée (joints plus rugueux, vernis plus lisse) puis recentrée sur `spec["rugosite"]` ;
  métal : `spec["metal"]` ; occlusion : cavités du relief (255 = aucune) ;
- normales : carte tangente convention OpenGL (+Y vert = haut de l'image = +v), tirée d'un relief en
  MÈTRES par gradients enroulés : la pente d'un joint de 2 mm est réelle, pas un effet réglé à l'œil.
  L'exporteur trimesh retourne v (v glTF = 1 − v) : la ligne 0 de l'image est donc le haut du motif.

Chaque clé a une recette (motif + paramètres) ; une clé future sans recette reçoit celle de sa famille.
"""
from __future__ import annotations

import math
import zlib
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Callable

import numpy as np
from PIL import Image, ImageDraw
from scipy.spatial import cKDTree
from trimesh.visual.material import PBRMaterial

from monde import vocabulaire

ALBEDO_MAX = 0.90          # albédo linéaire maximal d'une surface réelle (neige fraîche ≈ 0,9)
ALBEDO_MIN = 0.003         # noir le plus profond (verre noir, caoutchouc chargé au carbone)


# ── Couleurs ───────────────────────────────────────────────────────────────────────────────────────
def couleur_srgb(hexa: str) -> tuple[float, float, float]:
    h = hexa.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))  # type: ignore[return-value]


def couleur_lineaire(hexa: str) -> tuple[float, float, float]:
    def lin(c: float) -> float:
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    return tuple(lin(c) for c in couleur_srgb(hexa))  # type: ignore[return-value]


def _vers_lineaire(s: np.ndarray) -> np.ndarray:
    s = np.asarray(s, dtype=np.float32)
    return np.where(s <= 0.04045, s / 12.92, ((s + 0.055) / 1.055) ** 2.4)


def _vers_srgb(l: np.ndarray) -> np.ndarray:
    l = np.clip(np.asarray(l, dtype=np.float32), 0.0, 1.0)
    return np.where(l <= 0.0031308, l * 12.92, 1.055 * np.power(l, 1.0 / 2.4) - 0.055)


def _lin(hexa: str) -> np.ndarray:
    return np.asarray(couleur_lineaire(hexa), dtype=np.float32)


def _palette(nom: str) -> np.ndarray:
    return _lin(vocabulaire.PALETTE[nom])


# ── Toile : la grille d'un carreau, en mètres, et ses outils périodiques ───────────────────────────
@dataclass
class _Toile:
    res: int
    T: float                       # côté du carreau en mètres
    graine: int
    peint: bool = False            # couleur imposée (« :couleur ») : la maçonnerie est peinte, joints compris
    u: np.ndarray = field(init=False)   # (res, res) mètres, croît vers la droite
    v: np.ndarray = field(init=False)   # (res, res) mètres, croît vers le HAUT (ligne 0 = haut)
    px: float = field(init=False)

    def __post_init__(self) -> None:
        self.px = self.T / self.res
        c = (np.arange(self.res, dtype=np.float32) + 0.5) * self.px
        self.u = np.broadcast_to(c[None, :], (self.res, self.res))
        self.v = np.broadcast_to(c[::-1, None], (self.res, self.res))

    def sel(self, *sels: Any) -> int:
        return zlib.crc32(repr((self.graine,) + sels).encode()) & 0x7FFFFFFF

    # bruit blanc filtré sur le tore : longueur caractéristique lu (le long de u) et lv (le long de v)
    def bruit(self, lu: float, lv: float | None = None, *, sel: Any = 0, octaves: int = 1,
              persistance: float = 0.5) -> np.ndarray:
        lv = lu if lv is None else lv
        total = np.zeros((self.res, self.res), dtype=np.float32)
        amp, somme = 1.0, 0.0
        for o in range(octaves):
            total += amp * _bruit_filtre(self.res, self.T, lu / 2 ** o, lv / 2 ** o, self.sel("bruit", sel, o))
            somme += amp * amp
            amp *= persistance
        return total / math.sqrt(somme)

    def flou(self, a: np.ndarray, sigma_m: float) -> np.ndarray:
        return _flou_periodique(a, sigma_m / self.px)


@lru_cache(maxsize=256)
def _spectre_blanc(res: int, graine: int) -> np.ndarray:
    return np.fft.rfft2(np.random.default_rng(graine).standard_normal((res, res)).astype(np.float32))


@lru_cache(maxsize=64)
def _frequences(res: int) -> tuple[np.ndarray, np.ndarray]:
    fu = (np.fft.rfftfreq(res) * res).astype(np.float32)[None, :]      # cycles par carreau (colonnes)
    fv = (np.fft.fftfreq(res) * res).astype(np.float32)[:, None]       # (lignes)
    return fu, fv


def _bruit_filtre(res: int, T: float, lu: float, lv: float, graine: int) -> np.ndarray:
    """Bruit gaussien périodique, de structure ~lu × lv mètres, moyenne 0 et écart-type 1."""
    fu, fv = _frequences(res)
    su, sv = max(lu, 1e-6) / (2.0 * math.pi), max(lv, 1e-6) / (2.0 * math.pi)
    filtre = np.exp(-2.0 * math.pi ** 2 * ((su * fu / T) ** 2 + (sv * fv / T) ** 2)).astype(np.float32)
    filtre[0, 0] = 0.0
    a = np.fft.irfft2(_spectre_blanc(res, graine) * filtre, s=(res, res)).astype(np.float32)
    ecart = float(a.std())
    return a / ecart if ecart > 1e-12 else a


def _flou_periodique(a: np.ndarray, sigma_px: float) -> np.ndarray:
    if sigma_px <= 0.05:
        return a
    res = a.shape[0]
    fu, fv = _frequences(res)
    filtre = np.exp(-2.0 * math.pi ** 2 * sigma_px ** 2 * ((fu / res) ** 2 + (fv / res) ** 2))
    return np.fft.irfft2(np.fft.rfft2(a) * filtre, s=a.shape).astype(np.float32)


def _diviseur(T: float, module: float, *, pair: bool = False) -> int:
    """Nombre entier de modules par carreau le plus proche du module réel (pair si le motif décale une
    rangée sur deux, sinon le décalage ne se raccorde pas au bord)."""
    n = max(1, int(round(T / max(module, 1e-6))))
    if pair and n % 2:
        n = n + 1 if (T / module) > n else max(2, n - 1)
    return n


def _hache(*entiers: Any, graine: int = 0) -> np.ndarray:
    """Hachage entier → [0, 1) vectorisé (splitmix64), stable d'une exécution à l'autre."""
    x = np.uint64(((graine & 0xFFFFFFFF) * 0x9E3779B97F4A7C15) & 0xFFFFFFFFFFFFFFFF)
    with np.errstate(over="ignore"):
        for e in entiers:
            x = x ^ (np.asarray(e).astype(np.uint64) + np.uint64(0x9E3779B97F4A7C15))
            x = (x ^ (x >> np.uint64(30))) * np.uint64(0xBF58476D1CE4E5B9)
            x = (x ^ (x >> np.uint64(27))) * np.uint64(0x94D049BB133111EB)
            x = x ^ (x >> np.uint64(31))
    return ((x >> np.uint64(11)).astype(np.float64) / float(1 << 53)).astype(np.float32)


def _lisse(a: np.ndarray, b: np.ndarray | float, x: np.ndarray) -> np.ndarray:
    t = np.clip((x - a) / np.maximum(np.asarray(b) - a, 1e-9), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def _bande(x: np.ndarray, demi: float, flou: float) -> np.ndarray:
    """1 au cœur d'une bande |x| < demi, transition anticrénelée de largeur `flou`."""
    return 1.0 - _lisse(demi - flou / 2, demi + flou / 2, np.abs(x))


# ── Pavages par rangées : briques, lames, dalles, pavés, tuiles, ardoises, pierre de taille ────────
@dataclass
class _Cellules:
    id: np.ndarray        # identifiant unique (rangée, élément)
    x: np.ndarray         # position locale dans l'élément, mètres, le long de la rangée
    y: np.ndarray         # position locale verticale dans la rangée, mètres (0 = bas)
    l: np.ndarray         # longueur de l'élément
    h: np.ndarray         # hauteur de la rangée
    rang: np.ndarray      # indice de rangée

    def bord(self) -> np.ndarray:
        """Distance au bord le plus proche de l'élément (mètres)."""
        return np.minimum(np.minimum(self.x, self.l - self.x), np.minimum(self.y, self.h - self.y))


def _rangees(t: _Toile, hauteurs: list[float], longueurs: Callable[[int], list[float]],
             decalages: Callable[[int], float], *, dephasage: bool = True) -> _Cellules:
    """Rangées horizontales (le long de u) de hauteurs données (somme = T) ; chaque rangée découpée en
    éléments de longueurs données (somme = T), décalés de `decalages(j)` mètres. Raccord exact au bord."""
    res, T = t.res, t.T
    bornes = np.concatenate([[0.0], np.cumsum(hauteurs)])
    bornes *= T / bornes[-1]
    # déphasage d'une demi-rangée : aucun joint ne tombe sur le bord du carreau (raccord plus robuste au
    # filtrage des mipmaps, et bords comparables pour `_verifier_repetable`)
    v = np.mod(t.v[:, 0] + (0.5 * (bornes[1] - bornes[0]) if dephasage else 0.0), T)
    rang_lignes = np.clip(np.searchsorted(bornes, v, side="right") - 1, 0, len(hauteurs) - 1)
    ids = np.zeros((res, res), np.int64)
    xs = np.zeros((res, res), np.float32)
    ls = np.zeros((res, res), np.float32)
    u = t.u[0]
    for j in range(len(hauteurs)):
        lignes = np.nonzero(rang_lignes == j)[0]
        if not len(lignes):
            continue
        ll = np.asarray(longueurs(j), dtype=np.float64)
        ll *= T / ll.sum()
        cum = np.concatenate([[0.0], np.cumsum(ll)])
        xp = np.mod(u - decalages(j), T)
        k = np.clip(np.searchsorted(cum, xp, side="right") - 1, 0, len(ll) - 1)
        ids[lignes] = j * 4096 + k
        xs[lignes] = (xp - cum[k])
        ls[lignes] = ll[k]
    y = (v - bornes[rang_lignes]).astype(np.float32)
    h = (bornes[rang_lignes + 1] - bornes[rang_lignes]).astype(np.float32)
    return _Cellules(ids, xs, np.broadcast_to(y[:, None], (res, res)), ls,
                     np.broadcast_to(h[:, None], (res, res)), np.broadcast_to(rang_lignes[:, None], (res, res)))


def _appareil(t: _Toile, longueur: float, hauteur: float, *, decalage: float = 0.5,
              alea: float = 0.0, l_min: float | None = None, l_max: float | None = None,
              h_alea: float = 0.0) -> _Cellules:
    """Appareil régulier (briques, carreaux) ou à longueurs aléatoires (parquet, pierre de taille)."""
    n_r = _diviseur(t.T, hauteur, pair=decalage not in (0.0, 1.0) and alea == 0.0)
    if h_alea > 0:
        rng_h = np.random.default_rng(t.sel("hauteurs"))
        hauteurs = list(1.0 + h_alea * (rng_h.random(n_r) - 0.5))
    else:
        hauteurs = [1.0] * n_r
    n_l = _diviseur(t.T, longueur)
    mod = t.T / n_l

    def longueurs(j: int) -> list[float]:
        if l_min is None:
            return [1.0] * n_l
        rng = np.random.default_rng(t.sel("rangee", j))
        out, total = [], 0.0
        while total < t.T - l_min * 0.5:
            x = float(rng.uniform(l_min, l_max))
            out.append(x)
            total += x
        return out

    def decalages(j: int) -> float:
        if l_min is not None:
            return float(np.random.default_rng(t.sel("decalage", j)).uniform(0, t.T))
        return (j % 2) * decalage * mod

    return _rangees(t, hauteurs, longueurs, decalages)


def _voronoi(t: _Toile, points: np.ndarray, k: int = 2) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Voronoï périodique : distances aux k germes les plus proches, leurs indices et le vecteur (enroulé)
    pixel → germe le plus proche."""
    T = t.T
    pts = np.mod(np.asarray(points, dtype=np.float64), T)
    arbre = cKDTree(pts, boxsize=T)
    q = np.column_stack([t.u.reshape(-1), t.v.reshape(-1)]).astype(np.float64) % T
    d, i = arbre.query(q, k=k, workers=-1)
    d = d.reshape(t.res, t.res, k).astype(np.float32)
    i = i.reshape(t.res, t.res, k)
    vec = q.reshape(t.res, t.res, 2) - pts[i[..., 0]]
    vec = (np.mod(vec + T / 2, T) - T / 2).astype(np.float32)
    return d, i, vec


def _germes(t: _Toile, espacement: float, sel: Any, *, regularite: float = 0.0) -> np.ndarray:
    """Germes répartis (grille perturbée : pas d'amas ni de trous) à ~`espacement` mètres."""
    n = _diviseur(t.T, espacement)
    rng = np.random.default_rng(t.sel("germes", sel))
    g = (np.stack(np.meshgrid(np.arange(n), np.arange(n)), -1).reshape(-1, 2) + 0.5) * (t.T / n)
    return g + (1.0 - regularite) * (rng.random(g.shape) - 0.5) * (t.T / n)


# ── Couches d'un matériau ──────────────────────────────────────────────────────────────────────────
@dataclass
class _Couches:
    couleur: np.ndarray                    # (H, W, 3) linéaire
    hauteur: np.ndarray                    # (H, W) mètres
    rugosite: np.ndarray                   # (H, W) écart à la rugosité de la spec (recentré)
    variable: np.ndarray                   # (H, W) bool : pixels dont la couleur suit la cible
    moyenne: np.ndarray                    # (H, W) bool : zone dont la moyenne doit égaler la cible
    rugosite_fixe: np.ndarray | None = None   # (H, W) valeur absolue (NaN = suit la spec)
    occlusion: np.ndarray | None = None       # (H, W) 0..1 multiplicatif supplémentaire
    alpha: np.ndarray | None = None           # (H, W) 0..1 pour les translucides


def _couches(t: _Toile, base: np.ndarray) -> _Couches:
    z = np.zeros((t.res, t.res), np.float32)
    un = np.ones((t.res, t.res), bool)
    return _Couches(np.broadcast_to(base, (t.res, t.res, 3)).astype(np.float32).copy(), z.copy(), z.copy(),
                    un.copy(), un.copy())


def _ton(c: np.ndarray, facteur: np.ndarray, teinte: tuple[float, float, float] = (1.0, 1.0, 1.0)) -> np.ndarray:
    """Module une couleur : facteur de luminance (H, W), teinte = sensibilité par canal."""
    f = np.asarray(facteur, dtype=np.float32)[..., None]
    return c * (1.0 + (f - 1.0) * np.asarray(teinte, dtype=np.float32))


# ── Motifs de surface (chacun une loi générale paramétrée) ─────────────────────────────────────────
def _veinage(t: _Toile, coord_perp: np.ndarray, coord_long: np.ndarray, cerne: float, sel: Any,
             decalage: np.ndarray | float = 0.0) -> tuple[np.ndarray, np.ndarray]:
    """Fil du bois : cernes (bois final sombre) déformés par un bruit allongé dans le sens du fil ; renvoie
    (facteur de luminance, relief des pores)."""
    torsion = 2.2 * t.bruit(max(0.25, t.T / 3), 0.05, sel=(sel, "torsion"))
    fibres = t.bruit(0.12, 0.0012, sel=(sel, "fibres"))
    phase = coord_perp / cerne + torsion + decalage + 0.15 * t.bruit(0.6, 0.01, sel=(sel, "ondes"))
    f = np.mod(phase, 1.0)
    final = _lisse(0.55, 0.92, f) * (1.0 - _lisse(0.92, 1.0, f))
    lum = 1.0 + 0.07 * fibres - 0.22 * final + 0.05 * t.bruit(0.4, 0.08, sel=(sel, "taches"))
    pores = -0.00012 * np.clip(fibres - 0.8, 0, None) - 0.00006 * final
    return lum, pores


def _bois_massif(t: _Toile, s: _Couches, sel: Any = "fil") -> None:
    cerne = t.T / _diviseur(t.T, 0.007)
    lum, pores = _veinage(t, t.v, t.u, cerne, sel)
    s.couleur = _ton(s.couleur, lum, (1.0, 1.05, 1.15))
    s.hauteur += pores
    s.rugosite += 0.05 * (1.0 - lum)


def _lames(t: _Toile, s: _Couches, *, largeur: float, l_min: float, l_max: float, joint: float,
           verticales: bool = False, rainure: float = 0.0004, contraste: float = 0.12) -> None:
    """Parquet, lambris, bardage : lames à longueurs aléatoires, fil propre à chaque lame, joint sombre."""
    cel = _appareil(t, (l_min + l_max) / 2, largeur, l_min=l_min, l_max=l_max)
    r1 = _hache(cel.id, graine=t.sel("lame", 1))
    r2 = _hache(cel.id, graine=t.sel("lame", 2))
    cerne = 0.007
    lum, pores = _veinage(t, cel.y + 0.0, cel.x, cerne, "lames", decalage=r1 * 41.0)
    lum = lum * (1.0 + contraste * (r2 - 0.5) * 2.0)
    d = cel.bord()
    j = _lisse(joint * 0.5, joint * 0.5 + t.px * 1.2, d)
    couleur = _ton(s.couleur, lum, (1.0, 1.06, 1.18))
    couleur = couleur * (0.25 + 0.75 * j[..., None])
    hauteur = pores - rainure * (1.0 - _lisse(0.0, joint * 0.5 + t.px * 1.5, d))
    rug = 0.06 * (r1 - 0.5) + 0.2 * (1.0 - j)
    if verticales:                      # lames verticales (lambris) : le même pavage tourné d'un quart de tour
        couleur, hauteur, rug = (np.ascontiguousarray(np.rot90(a)) for a in (couleur, hauteur, rug))
    s.couleur, s.hauteur, s.rugosite = couleur, s.hauteur + hauteur, s.rugosite + rug


def _joints(t: _Toile, s: _Couches, cel: _Cellules, *, joint: float, couleur_joint: np.ndarray,
            profondeur: float, biseau: float = 0.0, variation: float = 0.08, teinte=(1.0, 1.0, 1.0),
            bombe: float = 0.0) -> np.ndarray:
    """Éléments séparés par un joint d'une autre couleur (fixe) ; variation de ton par élément ; biseau
    ou bombé (relief) ; renvoie le masque des éléments (1) / joints (0)."""
    d = cel.bord()
    m = _lisse(joint * 0.5 - t.px * 0.6, joint * 0.5 + t.px * 0.6, d)
    r = _hache(cel.id, graine=t.sel("element"))
    s.couleur = _ton(s.couleur, 1.0 + variation * 2.0 * (r - 0.5), teinte)
    s.couleur = s.couleur * m[..., None] + couleur_joint * (1.0 - m[..., None])
    s.variable = m > 0.5
    relief = np.zeros_like(d)
    if biseau > 0:
        relief += biseau * _lisse(joint * 0.5, joint * 0.5 + biseau * 4, d) - biseau
    if bombe > 0:
        nx = (cel.x / np.maximum(cel.l, 1e-6) - 0.5) * 2
        ny = (cel.y / np.maximum(cel.h, 1e-6) - 0.5) * 2
        relief += bombe * np.sqrt(np.clip(1.0 - 0.5 * (nx ** 4 + ny ** 4), 0, 1))
    s.hauteur += m * relief - profondeur * (1.0 - m)
    s.rugosite += 0.25 * (1.0 - m)
    return m


def _carreaux(t: _Toile, s: _Couches, spec: dict, *, longueur: float, hauteur: float, decalage: float,
              joint: float, biseau: float, variation: float = 0.04) -> None:
    cel = _appareil(t, longueur, hauteur, decalage=decalage)
    joint_c = _lin(vocabulaire.PALETTE["gris_clair"]) * 0.85
    s.couleur = _ton(s.couleur, 1.0 + 0.025 * t.bruit(0.08, sel="nuage"))
    _joints(t, s, cel, joint=joint, couleur_joint=joint_c, profondeur=0.0015, biseau=biseau, variation=variation)


def _marbre(t: _Toile, s: _Couches) -> None:
    turb = np.abs(t.bruit(0.5, sel="t1", octaves=4, persistance=0.55))
    phase = 2.0 * math.pi * t.u / t.T * _diviseur(t.T, t.T / 2) + 5.0 * t.bruit(0.6, sel="t2", octaves=3)
    veine = np.power(np.abs(np.sin(phase + 3.0 * turb)), 0.18)
    fines = 1.0 - _lisse(0.0, 0.08, np.abs(t.bruit(0.25, sel="t3", octaves=3)))
    lum = 0.62 + 0.38 * veine - 0.18 * fines * (1 - veine) + 0.03 * t.bruit(0.05, sel="grain")
    s.couleur = _ton(s.couleur, lum, (1.0, 1.0, 0.95))
    s.rugosite += 0.05 * (1 - lum)


def _nuages(t: _Toile, s: _Couches, *, echelle: float, force: float, fin: float = 0.0, relief: float = 0.0,
            teinte=(1.0, 1.0, 1.0)) -> np.ndarray:
    n = t.bruit(echelle, sel="nuage", octaves=4, persistance=0.55)
    lum = 1.0 + force * n
    if fin:
        lum = lum + fin * t.bruit(t.px * 2.5, sel="fin")
    s.couleur = _ton(s.couleur, lum, teinte)
    if relief:
        s.hauteur += relief * t.bruit(t.px * 3.0, sel="peau")
    s.rugosite += 0.04 * n
    return n


def _beton(t: _Toile, s: _Couches, *, banches: tuple[float, float] | None = None) -> None:
    _nuages(t, s, echelle=1.2, force=0.035, fin=0.02, relief=0.00008)
    pores = np.clip(t.bruit(t.px * 1.2, sel="bulles") - 2.3, 0, None)
    s.couleur = s.couleur * (1.0 - 0.35 * np.clip(pores, 0, 1))[..., None]
    s.hauteur -= 0.0006 * np.clip(pores, 0, 1)
    if banches:
        cel = _appareil(t, banches[0], banches[1], decalage=0.0)
        d = cel.bord()
        ligne = 1.0 - _lisse(0.002, 0.002 + t.px * 1.2, d)
        s.couleur = s.couleur * (1.0 - 0.25 * ligne)[..., None]
        s.hauteur -= 0.002 * ligne
        r = _hache(cel.id, graine=t.sel("banche"))
        s.couleur = _ton(s.couleur, 1.0 + 0.06 * (r - 0.5))
        # trous de banche aux quarts de chaque panneau
        for fx in (0.2, 0.8):
            for fy in (0.25, 0.75):
                dd = np.hypot(cel.x - fx * cel.l, cel.y - fy * cel.h)
                trou = 1.0 - _lisse(0.012, 0.012 + t.px, dd)
                s.couleur = s.couleur * (1.0 - 0.45 * trou)[..., None]
                s.hauteur -= 0.004 * trou


def _enduit(t: _Toile, s: _Couches, *, grain: float = 0.0012, force: float = 0.05) -> None:
    _nuages(t, s, echelle=max(0.3, t.T / 4), force=force, fin=0.02)
    s.hauteur += grain * 0.15 * t.bruit(t.px * 2.0, sel="grain", octaves=2)


def _joint_maconnerie(t: _Toile, s: _Couches, mortier: np.ndarray) -> np.ndarray:
    """Joint d'une maçonnerie : mortier nu, ou nuance claire de la peinture si la couleur est imposée
    (une façade peinte l'est joints compris)."""
    if not t.peint:
        return mortier
    return np.minimum(s.couleur.reshape(-1, 3).mean(axis=0) * 1.35 + 0.01, ALBEDO_MAX)


def _brique(t: _Toile, s: _Couches, *, longueur=0.215, hauteur=0.065, joint=0.01) -> None:
    cel = _appareil(t, longueur + joint, hauteur + joint, decalage=0.5)
    r = _hache(cel.id, graine=t.sel("brique"))
    cuisson = 1.0 + 0.22 * (r - 0.5) + 0.06 * t.bruit(0.05, sel="b") + 0.05 * t.bruit(0.01, sel="bb")
    s.couleur = _ton(s.couleur, cuisson, (1.0, 1.2, 1.35))
    mortier = _joint_maconnerie(t, s, _lin(vocabulaire.PALETTE["gris_clair"]) * 0.75)
    _joints(t, s, cel, joint=joint, couleur_joint=mortier, profondeur=0.004, variation=0.0, bombe=0.0005)
    s.hauteur += 0.0004 * t.bruit(0.008, sel="rugueux")


def _pierre_taille(t: _Toile, s: _Couches, *, assise: float, l_min: float, l_max: float, joint: float,
                   h_alea: float = 0.35) -> None:
    n = _diviseur(t.T, assise)
    rng = np.random.default_rng(t.sel("assises"))
    hauteurs = list(1.0 + h_alea * (rng.random(n) - 0.5))

    def longueurs(j: int) -> list[float]:
        r = np.random.default_rng(t.sel("pierres", j))
        out, tot = [], 0.0
        while tot < t.T - l_min * 0.5:
            x = float(r.uniform(l_min, l_max))
            out.append(x)
            tot += x
        return out

    cel = _rangees(t, hauteurs, longueurs, lambda j: float(np.random.default_rng(t.sel("dec", j)).uniform(0, t.T)))
    r = _hache(cel.id, graine=t.sel("pierre"))
    lum = 1.0 + 0.10 * (r - 0.5) + 0.05 * t.bruit(0.15, sel="p", octaves=3) + 0.03 * t.bruit(t.px * 2, sel="pp")
    s.couleur = _ton(s.couleur, lum, (1.0, 1.04, 1.1))
    joint_c = _joint_maconnerie(t, s, _lin(vocabulaire.PALETTE["beige"]) * 0.7)
    _joints(t, s, cel, joint=joint, couleur_joint=joint_c, profondeur=0.003, variation=0.0, bombe=0.001)
    s.hauteur += 0.0006 * t.bruit(0.01, sel="taille", octaves=2)


def _tissage(t: _Toile, s: _Couches, *, fil: float, force: float, relief: float, flamme: float = 0.06) -> None:
    """Toile (lin, coton) : fils de chaîne et de trame irréguliers (bruits très allongés), armure toile."""
    n = _diviseur(t.T, fil * 2)
    pas = t.T / n
    chaine = np.cos(2 * math.pi * t.u / pas)
    trame = np.cos(2 * math.pi * t.v / pas)
    armure = 0.5 + 0.5 * chaine * trame
    flammes = t.bruit(0.25, t.px * 0.9, sel="flammes_trame") + 0.7 * t.bruit(t.px * 0.9, 0.25, sel="flammes_chaine")
    lum = 1.0 + force * (armure - 0.5) + flamme * flammes + 0.03 * t.bruit(0.2, sel="nuage")
    s.couleur = _ton(s.couleur, lum)
    s.hauteur += relief * (armure - 0.5) + relief * 0.5 * flammes
    s.rugosite += 0.03 * flammes


def _laine(t: _Toile, s: _Couches) -> None:
    """Laine tissée de tapis : armure natté (2 × 2) de grosses mèches, poil irrégulier."""
    pas = t.T / _diviseur(t.T, 0.012)
    iu, iv = np.floor(t.u / pas), np.floor(t.v / pas)
    fu, fv = t.u / pas - iu, t.v / pas - iv
    sens = ((np.floor(iu / 2) + np.floor(iv / 2)) % 2) == 0
    meche = np.where(sens, np.sin(math.pi * fv), np.sin(math.pi * fu))
    poil = t.bruit(t.px * 1.5, sel="poil")
    lum = 0.9 + 0.18 * meche + 0.06 * poil + 0.05 * t.bruit(0.3, sel="nuage")
    s.couleur = _ton(s.couleur, lum, (1.0, 1.0, 0.95))
    s.hauteur += 0.0012 * meche + 0.0003 * poil
    s.rugosite += 0.02 * poil


def _cuir(t: _Toile, s: _Couches) -> None:
    pts = _germes(t, 0.004, "grain")
    d, _, _ = _voronoi(t, pts)
    bord = d[..., 1] - d[..., 0]
    pli = 1.0 - _lisse(0.0, 0.0012, bord)
    s.couleur = _ton(s.couleur, 1.0 - 0.18 * pli + 0.06 * t.bruit(0.2, sel="patine", octaves=2))
    s.hauteur += -0.00025 * pli
    s.rugosite += 0.12 * pli


def _brosse(t: _Toile, s: _Couches, *, force: float) -> None:
    """Acier brossé : rayures très allongées le long de u."""
    rayures = t.bruit(t.T, t.px * 0.8, sel="rayures") + 0.5 * t.bruit(t.T / 3, t.px * 0.8, sel="r2")
    s.couleur = _ton(s.couleur, 1.0 + force * 0.5 * rayures)
    s.rugosite += force * rayures
    s.hauteur += 0.00001 * rayures


def _patine(t: _Toile, s: _Couches, *, force: float, rugo: float) -> None:
    n = t.bruit(0.25, sel="patine", octaves=3)
    s.couleur = _ton(s.couleur, 1.0 + force * n, (1.0, 1.0, 1.1))
    s.rugosite += rugo * n
    s.hauteur += 0.00002 * t.bruit(t.px * 2, sel="micro")


def _fonte(t: _Toile, s: _Couches) -> None:
    n = t.bruit(t.px * 2.0, sel="sable", octaves=2)
    s.couleur = _ton(s.couleur, 1.0 + 0.08 * n + 0.06 * t.bruit(0.2, sel="nuage"))
    s.hauteur += 0.00015 * n
    s.rugosite += 0.06 * n


def _hexagones(t: _Toile, s: _Couches, *, cote: float, joint: float) -> None:
    """Tomettes : pavage hexagonal (Voronoï d'une grille décalée), terre cuite nuancée par carreau."""
    a = cote
    nc = _diviseur(t.T, a * math.sqrt(3.0))
    nr = _diviseur(t.T, 1.5 * a, pair=True)
    sx, sy = t.T / nc, t.T / nr
    centres = np.array([[(i + 0.5 * (j % 2)) * sx, j * sy] for j in range(nr) for i in range(nc)])
    d, idx, _ = _voronoi(t, centres)
    bord = (d[..., 1] - d[..., 0]) * 0.5
    m = _lisse(joint * 0.5 - t.px * 0.6, joint * 0.5 + t.px * 0.6, bord)
    r = _hache(idx[..., 0], graine=t.sel("tomette"))
    lum = 1.0 + 0.3 * (r - 0.5) + 0.08 * t.bruit(0.04, sel="t", octaves=2)
    s.couleur = _ton(s.couleur, lum, (1.0, 1.25, 1.4))
    joint_c = _lin(vocabulaire.PALETTE["beige"]) * 0.55
    s.couleur = s.couleur * m[..., None] + joint_c * (1 - m[..., None])
    s.variable = m > 0.5
    s.hauteur += -0.003 * (1 - m) + 0.0008 * _lisse(0, 0.02, bord) * m
    s.rugosite += 0.2 * (1 - m) + 0.08 * (r - 0.5)


def _ciment_motif(t: _Toile, s: _Couches) -> None:
    """Carreaux de ciment : chaque carreau porte une rosace (distances signées), trois tons dérivés de la
    couleur (fond, accent sombre, clair)."""
    cel = _appareil(t, 0.2, 0.2, decalage=0.0)
    x = cel.x / cel.l - 0.5
    y = cel.y / cel.h - 0.5
    r = np.hypot(x, y)
    th = np.arctan2(y, x)
    losange = np.abs(np.abs(x) + np.abs(y) - 0.32)
    petales = r - (0.17 + 0.07 * np.cos(4 * th))
    coins = np.hypot(np.abs(x) - 0.5, np.abs(y) - 0.5) - 0.2
    w = t.px / 0.2 * 0.8
    accent = np.clip(_bande(losange, 0.035, w) + (1 - _lisse(-w, w, coins)), 0, 1)
    clair = 1 - _lisse(-w, w, petales)
    base = s.couleur
    sombre = base * 0.35 * np.asarray([0.9, 1.0, 1.15], np.float32)
    leger = np.minimum(base * 1.8 + 0.05, ALBEDO_MAX)
    c = base * (1 - accent[..., None]) + sombre * accent[..., None]
    s.couleur = c * (1 - clair[..., None]) + leger * clair[..., None]
    s.couleur = _ton(s.couleur, 1.0 + 0.05 * t.bruit(0.05, sel="mat"))
    joint_c = _lin(vocabulaire.PALETTE["gris_clair"]) * 0.7
    d = cel.bord()
    m = _lisse(0.001 - t.px * 0.6, 0.001 + t.px * 0.6, d)
    s.couleur = s.couleur * m[..., None] + joint_c * (1 - m[..., None])
    s.hauteur += -0.001 * (1 - m)
    s.rugosite += 0.1 * (1 - m)


def _papier_peint(t: _Toile, s: _Couches) -> None:
    """Papier peint : rayures larges ton sur ton et motif floral en quinconce (raccord sauté)."""
    n = _diviseur(t.T, 0.15)
    pas = t.T / n
    rayure = (np.floor(t.u / (pas / 2)) % 2).astype(np.float32)
    fu = np.mod(t.u, pas) - pas / 2
    rang = np.floor(t.v / pas)
    fv = np.mod(t.v + (np.mod(np.floor(t.u / pas), 2)) * pas / 2, pas) - pas / 2
    r = np.hypot(fu, fv)
    th = np.arctan2(fv, fu)
    fleur = r - pas * (0.12 + 0.09 * np.abs(np.cos(2.5 * th)))
    coeur = r - pas * 0.05
    w = t.px * 0.8
    m_fleur = 1 - _lisse(-w, w, fleur)
    m_coeur = 1 - _lisse(-w, w, coeur)
    base = s.couleur
    lum = 1.0 + 0.05 * (rayure - 0.5)
    c = _ton(base, lum)
    accent = base * np.asarray([0.62, 0.66, 0.72], np.float32)
    c = c * (1 - m_fleur[..., None]) + accent * m_fleur[..., None]
    c = c * (1 - m_coeur[..., None]) + np.minimum(base * 1.3, ALBEDO_MAX) * m_coeur[..., None]
    del rang
    s.couleur = _ton(c, 1.0 + 0.015 * t.bruit(t.px * 3, sel="papier"))
    s.hauteur += 0.00008 * m_fleur + 0.00003 * t.bruit(t.px * 2, sel="fibre")


def _livres(t: _Toile, s: _Couches) -> None:
    """Dos de livres alignés sur des rayons : largeurs 1,5-5 cm, hauteurs 18-30 cm, teintes variées
    autour de la couleur, bandeaux de titre ; rangées = rayons."""
    hauteur_rayon = t.T / _diviseur(t.T, 0.3)

    def longueurs(j: int) -> list[float]:
        r = np.random.default_rng(t.sel("livres", j))
        out, tot = [], 0.0
        while tot < t.T - 0.01:
            x = float(r.uniform(0.015, 0.05))
            out.append(x)
            tot += x
        return out

    # décalage d'une demi-largeur minimale : le bord du carreau tombe dans un dos, jamais entre deux
    cel = _rangees(t, [1.0] * int(round(t.T / hauteur_rayon)), longueurs, lambda j: 0.0075, dephasage=False)
    r1 = _hache(cel.id, graine=t.sel("l1"))
    r2 = _hache(cel.id, graine=t.sel("l2"))
    r3 = _hache(cel.id, graine=t.sel("l3"))
    haut = 0.6 + 0.37 * r2
    dedans = ((cel.y < cel.h * haut) & (cel.y > 0.006)).astype(np.float32)
    base = s.couleur
    import colorsys
    ids, inverse = np.unique(cel.id, return_inverse=True)
    h0, _, _ = colorsys.rgb_to_hsv(*[float(c) for c in _vers_srgb(base[0, 0])])
    rr = np.stack([_hache(ids, graine=t.sel("h", k)) for k in range(3)], -1)
    couleurs_livres = np.array([colorsys.hsv_to_rgb((h0 + 0.7 * (a - 0.5)) % 1.0, 0.25 + 0.45 * b, 0.25 + 0.5 * c)
                                for a, b, c in rr], np.float32)
    dos = _vers_lineaire(couleurs_livres)[inverse.reshape(cel.id.shape)]
    xs = cel.x / cel.l
    arrondi = np.sin(math.pi * np.clip(xs, 0, 1)) ** 0.5
    bandeau = (_bande(cel.y / cel.h - haut * 0.75, 0.04, 0.02) * (r1 > 0.4)).astype(np.float32)
    dos = dos * (1 - 0.5 * bandeau[..., None]) + np.minimum(base * 1.5, ALBEDO_MAX) * 0.5 * bandeau[..., None]
    fond = base * 0.08
    s.couleur = dos * (arrondi[..., None] * 0.6 + 0.4) * dedans[..., None] + fond * (1 - dedans[..., None])
    s.hauteur += 0.003 * arrondi * dedans - 0.01 * (1 - dedans)
    s.occlusion = 0.35 + 0.65 * dedans
    s.rugosite += 0.1 * (r2 - 0.5)


def _feuilles(t: _Toile, s: _Couches, *, longueur: float, densite: float = 2.6) -> None:
    """Feuillage : feuilles elliptiques pointues (nervure, ton propre, base plus sombre), superposées par
    profondeur ; les vides sont l'ombre du feuillage."""
    largeur = 0.42 * longueur
    pts = _germes(t, math.sqrt(longueur * largeur / densite), "feuilles")
    k = 5
    d, idx, _ = _voronoi(t, pts, k=k)
    T = t.T
    q = np.stack([t.u, t.v], -1)
    rng = np.random.default_rng(t.sel("angles"))
    angles = rng.uniform(0, 2 * math.pi, len(pts)).astype(np.float32)
    profondeur = rng.random(len(pts)).astype(np.float32)
    echelle = (0.7 + 0.6 * rng.random(len(pts))).astype(np.float32)
    meilleur = np.full((t.res, t.res), -1.0, np.float32)
    lx = np.zeros((t.res, t.res), np.float32)
    ly = np.zeros((t.res, t.res), np.float32)
    choisi = np.full((t.res, t.res), -1, np.int64)
    for c in range(k):
        i = idx[..., c]
        vec = np.mod(q - pts[i] + T / 2, T) - T / 2
        a = angles[i]
        L = longueur * echelle[i]
        x = (vec[..., 0] * np.cos(a) + vec[..., 1] * np.sin(a)) / L
        y = (-vec[..., 0] * np.sin(a) + vec[..., 1] * np.cos(a)) / L
        demi = (largeur / longueur) * 0.5 * np.power(np.clip(np.cos(math.pi * x), 0, 1), 0.7)
        dedans = (np.abs(x) < 0.5) & (np.abs(y) < demi)
        mieux = dedans & (profondeur[i] > meilleur)
        meilleur = np.where(mieux, profondeur[i], meilleur)
        lx = np.where(mieux, x, lx)
        ly = np.where(mieux, y, ly)
        choisi = np.where(mieux, i, choisi)
    feuille = choisi >= 0
    r = _hache(np.maximum(choisi, 0), graine=t.sel("ton"))
    lum = (0.75 + 0.5 * r) * (0.8 + 0.4 * (lx + 0.5)) * (0.75 + 0.45 * meilleur)
    nervure = _bande(ly * longueur, 0.0012, t.px)
    lum = lum * (1 + 0.25 * nervure)
    base = s.couleur
    teinte = np.stack([1.0 + 0.5 * (r - 0.5), np.ones_like(r), 1.0 - 0.6 * (r - 0.5)], -1)
    vif = base * teinte * lum[..., None]
    ombre = base * 0.22
    s.couleur = np.where(feuille[..., None], vif, ombre).astype(np.float32)
    bombe = np.sqrt(np.clip(1 - (2 * lx) ** 2, 0, 1)) * (1 - np.abs(ly) * 4)
    s.hauteur += np.where(feuille, 0.004 * meilleur + 0.0015 * bombe - 0.0004 * nervure, -0.004)
    s.occlusion = np.where(feuille, 0.6 + 0.4 * meilleur, 0.3)
    s.rugosite += np.where(feuille, -0.05, 0.2)


def _herbe(t: _Toile, s: _Couches) -> None:
    touffes = t.bruit(0.06, sel="touffes", octaves=2)
    brins = t.bruit(t.px * 0.9, t.px * 3, sel="brins") + 0.8 * t.bruit(t.px * 3, t.px * 0.9, sel="brins2")
    sec = _lisse(0.6, 1.6, t.bruit(0.8, sel="sec", octaves=3))
    lum = 1.0 + 0.18 * touffes + 0.22 * brins
    base = s.couleur
    jaune = base * np.asarray([1.8, 1.25, 0.6], np.float32)
    c = _ton(base, lum, (1.0, 1.0, 1.3))
    s.couleur = c * (1 - 0.6 * sec[..., None]) + jaune * lum[..., None] * 0.6 * sec[..., None]
    s.hauteur += 0.003 * brins + 0.004 * touffes
    s.rugosite += 0.03 * brins


def _graviers(t: _Toile, s: _Couches, *, taille: float, liant: np.ndarray | None = None, ton: float = 0.35,
              relief: float = 1.0) -> None:
    pts = _germes(t, taille, "cailloux")
    d, idx, _ = _voronoi(t, pts)
    bord = (d[..., 1] - d[..., 0]) * 0.5
    rayon = taille * 0.5
    dome = np.sqrt(np.clip(bord / (rayon * 0.6), 0, 1))
    r = _hache(idx[..., 0], graine=t.sel("ton"))
    r2 = _hache(idx[..., 0], graine=t.sel("teinte"))
    lum = 1.0 + ton * 2 * (r - 0.5)
    teinte = np.stack([1 + 0.15 * (r2 - 0.5), np.ones_like(r2), 1 - 0.2 * (r2 - 0.5)], -1)
    c = s.couleur * teinte * lum[..., None] * (0.55 + 0.45 * dome[..., None])
    if liant is not None:
        dedans = _lisse(t.px * 0.3, t.px * 1.5, bord)
        c = c * dedans[..., None] + liant * (1 - dedans[..., None])
    s.couleur = c
    s.hauteur += relief * rayon * 0.6 * dome
    s.rugosite += 0.06 * (r - 0.5)


def _asphalte(t: _Toile, s: _Couches) -> None:
    granulat = t.bruit(t.px * 0.8, sel="granulat")
    clairs = np.clip(granulat - 1.3, 0, None)
    taches = t.bruit(1.2, sel="taches", octaves=3)
    usure = _lisse(0.5, 1.8, t.bruit(2.0, 0.6, sel="usure"))
    lum = 1.0 + 0.10 * granulat + 0.9 * clairs + 0.08 * taches + 0.12 * usure
    s.couleur = _ton(s.couleur, lum)
    s.hauteur += 0.0015 * granulat + 0.001 * t.bruit(0.04, sel="r")
    s.rugosite += 0.04 * granulat - 0.05 * usure
    # fissures : bords de Voronoï grossiers, rares
    pts = _germes(t, 1.7, "fissures")
    d, _, _ = _voronoi(t, pts)
    fissure = (1 - _lisse(0.0, t.px * 1.2, d[..., 1] - d[..., 0])) * _lisse(0.8, 1.4, t.bruit(1.0, sel="ou"))
    s.couleur = s.couleur * (1 - 0.6 * fissure)[..., None]
    s.hauteur -= 0.003 * fissure


def _terre(t: _Toile, s: _Couches) -> None:
    mottes = t.bruit(0.05, sel="mottes", octaves=3)
    humide = t.bruit(0.8, sel="humide", octaves=2)
    lum = 1.0 + 0.18 * mottes + 0.12 * humide
    s.couleur = _ton(s.couleur, lum, (1.0, 1.05, 1.1))
    s.hauteur += 0.004 * mottes
    s.rugosite += -0.06 * humide
    cailloux = np.clip(t.bruit(t.px * 2.5, sel="cx") - 2.2, 0, 1)
    s.couleur = s.couleur * (1 + 0.8 * cailloux)[..., None]
    s.hauteur += 0.003 * cailloux


def _sable(t: _Toile, s: _Couches) -> None:
    ondes = _diviseur(t.T, 0.09)
    phase = 2 * math.pi * (t.v / t.T * ondes + 0.8 * t.bruit(0.7, sel="vent"))
    ride = np.sin(phase + 0.5 * np.sin(phase))
    grain = t.bruit(t.px * 0.9, sel="grain")
    s.couleur = _ton(s.couleur, 1.0 + 0.05 * ride + 0.07 * grain + 0.05 * t.bruit(0.6, sel="n"))
    s.hauteur += 0.004 * ride + 0.0003 * grain


def _roche(t: _Toile, s: _Couches, *, strates: bool = True) -> None:
    n = t.bruit(0.6, sel="masse", octaves=5, persistance=0.55)
    s.couleur = _ton(s.couleur, 1.0 + 0.16 * n, (1.0, 1.03, 1.06))
    s.hauteur += 0.02 * n
    pts = _germes(t, 0.5, "fractures")
    d, _, _ = _voronoi(t, pts)
    fracture = (1 - _lisse(0.0, 0.004 + t.px, d[..., 1] - d[..., 0])) * _lisse(-0.3, 0.6, t.bruit(0.6, sel="ouv"))
    s.couleur = s.couleur * (1 - 0.3 * fracture)[..., None]
    s.hauteur -= 0.015 * fracture
    if strates:
        lit = np.sin(2 * math.pi * t.v / t.T * _diviseur(t.T, 0.25) + 2 * t.bruit(0.8, sel="ondul"))
        s.couleur = _ton(s.couleur, 1.0 + 0.06 * lit)
    lichen = _lisse(1.2, 1.8, t.bruit(0.3, sel="lichen", octaves=2))
    s.couleur = s.couleur * (1 - lichen[..., None]) + s.couleur * np.asarray([1.15, 1.2, 0.85], np.float32) * lichen[..., None]
    s.rugosite += 0.05 * n


def _neige(t: _Toile, s: _Couches) -> None:
    n = t.bruit(0.5, sel="congeres", octaves=4)
    s.couleur = _ton(s.couleur, 1.0 + 0.035 * n + 0.01 * t.bruit(t.px * 1.5, sel="cristaux"), (1.0, 0.98, 0.95))
    s.hauteur += 0.03 * n + 0.0004 * t.bruit(t.px * 2, sel="c2")
    s.rugosite += 0.08 * t.bruit(t.px * 2, sel="scintillement")


def _eau(t: _Toile, s: _Couches) -> None:
    houle = t.bruit(1.4, 0.5, sel="houle", octaves=3, persistance=0.6)
    rides = t.bruit(0.25, 0.12, sel="rides", octaves=3)
    s.hauteur += 0.035 * houle + 0.006 * rides
    s.couleur = _ton(s.couleur, 1.0 + 0.10 * houle + 0.05 * rides, (1.0, 0.9, 0.8))
    s.rugosite += 0.02 * rides


def _eau_vive(t: _Toile, s: _Couches) -> None:
    """Eau vive d'une veine ou d'une cascade (16/11/2026) : filets étirés dans le sens de l'écoulement (v) et
    rides fines, à l'échelle du centimètre — celle d'un jet. La houle d'un lac (1,4 m) sur une tuile de 30 cm
    n'était qu'une pente : la normale moyenne penchait."""
    filets = t.bruit(0.012, 0.08, sel="filets", octaves=3, persistance=0.55)
    rides = t.bruit(0.02, 0.02, sel="rides", octaves=2)
    s.hauteur += 0.0008 * filets + 0.0004 * rides
    s.couleur = _ton(s.couleur, 1.0 + 0.16 * filets + 0.05 * rides, (1.0, 1.0, 1.0))
    s.rugosite += 0.015 * np.abs(rides)


def _ecorce(t: _Toile, s: _Couches) -> None:
    sillons = t.bruit(0.02, 0.25, sel="sillons", octaves=3)
    cretes = np.abs(sillons)
    plaques = _lisse(-0.2, 0.6, sillons)
    s.couleur = _ton(s.couleur, 0.62 + 0.55 * plaques + 0.08 * t.bruit(t.px * 2, sel="g"), (1.0, 1.05, 1.1))
    s.hauteur += 0.008 * plaques - 0.003 * cretes
    s.occlusion = 0.55 + 0.45 * plaques
    s.rugosite += 0.05 * (1 - plaques)


def _tuiles(t: _Toile, s: _Couches) -> None:
    """Tuiles canal en rangs : bombé transversal, ombre portée du rang supérieur, nuances par tuile."""
    cel = _appareil(t, 0.2, 0.25, decalage=0.5)
    xs = cel.x / cel.l
    ys = cel.y / cel.h
    galbe = np.sin(math.pi * xs)
    r = _hache(cel.id, graine=t.sel("tuile"))
    lum = (0.62 + 0.38 * galbe) * (1 + 0.25 * (r - 0.5)) * (0.55 + 0.45 * _lisse(0.0, 0.25, ys))
    s.couleur = _ton(s.couleur, lum + 0.05 * t.bruit(0.04, sel="mousse"), (1.0, 1.2, 1.4))
    s.hauteur += 0.02 * galbe + 0.012 * ys
    s.occlusion = 0.55 + 0.45 * _lisse(0.0, 0.2, ys)
    s.rugosite += 0.08 * (r - 0.5)


def _ardoises(t: _Toile, s: _Couches) -> None:
    cel = _appareil(t, 0.25, 0.2, decalage=0.5)
    r = _hache(cel.id, graine=t.sel("ardoise"))
    feuillet = t.bruit(0.15, t.px * 1.5, sel="feuillet")
    ys = cel.y / cel.h
    bas_irregulier = 0.04 * t.bruit(0.03, sel="bas")
    ombre = _lisse(0.0, 0.18, ys + bas_irregulier)
    s.couleur = _ton(s.couleur, (1 + 0.14 * (r - 0.5) + 0.05 * feuillet) * (0.55 + 0.45 * ombre), (1.0, 1.0, 1.08))
    d = np.minimum(cel.x, cel.l - cel.x)
    fente = 1 - _lisse(0.0015, 0.0015 + t.px, d)
    s.couleur = s.couleur * (1 - 0.6 * fente)[..., None]
    s.hauteur += 0.006 * ys - 0.003 * fente + 0.0003 * feuillet
    s.occlusion = 0.6 + 0.4 * ombre
    s.rugosite += 0.06 * (r - 0.5)


def _zinc(t: _Toile, s: _Couches) -> None:
    """Zinc à joint debout : agrafures tous les 50 cm environ (relief réel en normale), patine."""
    pas = t.T / _diviseur(t.T, 0.5)
    x = np.mod(t.u, pas) - pas / 2
    d = np.abs(np.abs(x) - pas / 2)              # distance à l'agrafure (bord du bac)
    agrafe = 1 - _lisse(0.006, 0.006 + t.px * 1.5, d)
    tole = 0.0008 * t.bruit(pas * 0.8, 0.6, sel="ondulation")
    s.hauteur += 0.012 * agrafe + tole
    _patine(t, s, force=0.06, rugo=0.06)
    s.couleur = _ton(s.couleur, 1.0 + 0.12 * agrafe)
    s.occlusion = 1.0 - 0.3 * (1 - _lisse(0.006, 0.03, d)) * (1 - agrafe)


def _pave(t: _Toile, s: _Couches) -> None:
    cel = _appareil(t, 0.13, 0.1, alea=1.0, l_min=0.09, l_max=0.17)
    r = _hache(cel.id, graine=t.sel("pave"))
    s.couleur = _ton(s.couleur, 1.0 + 0.06 * t.bruit(0.03, sel="p"), (1.0, 1.05, 1.1))
    joint_c = s.couleur.mean(axis=(0, 1)) * 0.45
    _joints(t, s, cel, joint=0.012, couleur_joint=joint_c, profondeur=0.006, variation=0.18,
            teinte=(1.0, 1.04, 1.08), bombe=0.006)
    del r


def _dalles(t: _Toile, s: _Couches, *, cote: float) -> None:
    cel = _appareil(t, cote, cote, decalage=0.0)
    s.couleur = _ton(s.couleur, 1.0 + 0.05 * t.bruit(0.08, sel="d", octaves=2) + 0.05 * t.bruit(t.px, sel="gr"))
    joint_c = s.couleur.mean(axis=(0, 1)) * 0.55
    _joints(t, s, cel, joint=0.006, couleur_joint=joint_c, profondeur=0.003, variation=0.10, biseau=0.0008)
    taches = _lisse(1.0, 2.2, t.bruit(0.15, sel="taches"))
    s.couleur = s.couleur * (1 - 0.18 * taches)[..., None]


def _uni(t: _Toile, s: _Couches, *, force: float = 0.015, peau: float = 0.00002) -> None:
    s.couleur = _ton(s.couleur, 1.0 + force * t.bruit(0.3, sel="uni", octaves=2))
    s.hauteur += peau * t.bruit(t.px * 2.5, sel="peau")
    s.rugosite += 0.03 * t.bruit(0.2, sel="traces")


def _marquage(t: _Toile, s: _Couches) -> None:
    usure = _lisse(1.3, 2.2, t.bruit(0.08, sel="usure", octaves=3) + 0.4 * t.bruit(t.px, sel="grains"))
    asphalte = _lin(MATERIAUX_COULEUR("asphalte"))
    s.couleur = s.couleur * (1 - 0.8 * usure[..., None]) + asphalte * 0.8 * usure[..., None]
    s.variable = usure < 0.5
    s.moyenne = usure < 0.5                       # la couleur de la spec est celle de la peinture
    s.hauteur += 0.0006 * t.bruit(t.px * 0.8, sel="billes")


def MATERIAUX_COULEUR(cle: str) -> str:
    return vocabulaire.MATERIAUX[cle]["couleur"]


def _depoli(t: _Toile, s: _Couches) -> None:
    s.hauteur += 0.00003 * t.bruit(t.px * 1.2, sel="sable")
    s.couleur = _ton(s.couleur, 1.0 + 0.02 * t.bruit(t.px * 2, sel="d"))


# ── Façades : une travée × un étage, fenêtre centrée ───────────────────────────────────────────────
def _fenetre(t: _Toile, s: _Couches, *, menuiserie: str, appui: str = "pierre", balcon: bool = False,
             linteau: bool = False) -> None:
    """Fenêtre centrée dans le module : tableau (ombre de l'ébrasement), dormant + battants, vitrage au
    reflet de ciel dégradé (clair en haut), appui saillant ; garde-corps en fer forgé si `balcon`.
    Proportions de la construction courante (allège ~0,9-1 m, linteau ~2,3-2,5 m pour 3 m d'étage)."""
    T = t.T
    u, v = t.u, t.v
    largeur = 0.42 * T
    bas, haut = 0.31 * T, 0.81 * T
    if balcon:
        bas = 0.06 * T
    x0, x1 = (T - largeur) / 2, (T + largeur) / 2
    dans = (u > x0) & (u < x1) & (v > bas) & (v < haut)
    du = np.minimum(u - x0, x1 - u)
    dv = np.minimum(v - bas, haut - v)
    d_bord = np.minimum(du, dv)
    dormant = 0.06
    battant = 0.05
    claire = _lin(vocabulaire.PALETTE["blanc_casse"]) * 0.92 if menuiserie == "claire" else _palette("anthracite")
    # vitrage : reflet de ciel + intérieur sombre
    hauteur_rel = np.clip((v - bas) / (haut - bas), 0, 1)
    ciel = _palette("bleu_gris") * 0.9
    interieur = _palette("anthracite") * 0.25
    reflet = 0.25 + 0.6 * hauteur_rel ** 1.5 + 0.06 * t.bruit(0.4, 0.15, sel="nuages_reflet")
    vitre = interieur[None, None] * (1 - reflet[..., None]) + ciel[None, None] * reflet[..., None]
    # menuiserie : dormant au pourtour, montant central et traverse haute (fenêtre à deux battants + imposte)
    xc = T / 2
    montant = np.abs(u - xc) < battant * 0.9
    traverse = np.abs(v - (haut - 0.22 * (haut - bas))) < battant * 0.6
    cadre = (d_bord < dormant) | ((d_bord < dormant + battant) & ~(d_bord < dormant)) | montant | traverse
    cadre = cadre & dans
    vitrage = dans & ~cadre
    # ombre de l'ébrasement : le tableau assombrit le haut et le côté gauche du vitrage (soleil d'ouest)
    ombre = 1.0 - 0.5 * (1.0 - _lisse(0.0, 0.2, haut - v)) - 0.25 * (1.0 - _lisse(0.0, 0.12, u - x0))
    c = s.couleur
    c = np.where(vitrage[..., None], vitre * ombre[..., None], c)
    joue = (dv < dormant * 0.4) | (du < dormant * 0.4)
    c = np.where(cadre[..., None], claire * np.where(joue, 0.65, 1.0)[..., None], c)
    # appui saillant sous la fenêtre, avec ombre portée dessous
    if not balcon:
        appui_c = _lin(vocabulaire.PALETTE["gris_clair"]) * 0.85 if appui == "pierre" else claire
        m_appui = (u > x0 - 0.06) & (u < x1 + 0.06) & (v > bas - 0.07) & (v <= bas)
        ombre_appui = (u > x0 - 0.06) & (u < x1 + 0.06) & (v > bas - 0.07 - 0.12) & (v <= bas - 0.07)
        degrade = np.clip((v - (bas - 0.19)) / 0.12, 0, 1)
        c = np.where(ombre_appui[..., None], c * (0.55 + 0.45 * (1 - degrade))[..., None], c)
        c = np.where(m_appui[..., None], appui_c, c)
        s.hauteur = np.where(m_appui, s.hauteur + 0.01, s.hauteur)
        s.variable &= ~m_appui & ~ombre_appui
    if linteau:
        m_lin = (u > x0 - 0.1) & (u < x1 + 0.1) & (v >= haut) & (v < haut + 0.16)
        c = np.where(m_lin[..., None], _lin(vocabulaire.PALETTE["beige"]) * 0.8, c)
        s.variable &= ~m_lin
    s.couleur = c
    s.hauteur = np.where(dans, -0.02 + 0.006 * cadre, s.hauteur)
    rf = np.full((t.res, t.res), np.nan, np.float32)
    rf[vitrage] = 0.06
    rf[cadre] = 0.45
    s.rugosite_fixe = rf
    s.variable &= ~dans
    s.moyenne &= ~dans
    s.occlusion = np.where(dans & (d_bord < 0.04), 0.6, 1.0).astype(np.float32)
    if balcon:
        _garde_corps(t, s, x0 - 0.15, x1 + 0.15, bas, bas + 1.0)


def _garde_corps(t: _Toile, s: _Couches, x0: float, x1: float, y0: float, y1: float) -> None:
    """Garde-corps en fer forgé : lisse haute et basse, barreaux, volutes entre barreaux ; dalle de balcon
    en pierre sous le garde-corps (ombre portée)."""
    u, v = t.u, t.v
    fer = _palette("noir") * 1.2
    zone = (u > x0) & (u < x1) & (v > y0) & (v < y1)
    lisse_h = np.abs(v - y1 + 0.025) < 0.025
    lisse_b = np.abs(v - y0 - 0.12) < 0.015
    pas = 0.11
    xb = np.mod(u - x0, pas) - pas / 2
    barreau = np.abs(xb) < 0.009
    yc = (y0 + 0.12 + y1 - 0.05) / 2
    r = np.hypot(xb, (v - yc) * 0.5)
    volute = np.abs(r - 0.035) < 0.0065
    fer_m = zone & (lisse_h | lisse_b | (barreau & (v > y0 + 0.12)) | volute)
    s.couleur = np.where(fer_m[..., None], fer, s.couleur)
    dalle = (u > x0 - 0.05) & (u < x1 + 0.05) & (v > y0 - 0.14) & (v <= y0 + 0.0)
    pierre = _lin(vocabulaire.PALETTE["gris_clair"]) * 0.8
    s.couleur = np.where(dalle[..., None], pierre, s.couleur)
    ombre = (u > x0 - 0.05) & (u < x1 + 0.05) & (v > y0 - 0.34) & (v <= y0 - 0.14)
    degrade = np.clip((v - (y0 - 0.34)) / 0.2, 0, 1)
    s.couleur = np.where(ombre[..., None], s.couleur * (1 - 0.5 * degrade)[..., None], s.couleur)
    s.hauteur = np.where(fer_m, 0.03, s.hauteur)
    s.hauteur = np.where(dalle, 0.02, s.hauteur)
    rf = s.rugosite_fixe if s.rugosite_fixe is not None else np.full((t.res, t.res), np.nan, np.float32)
    rf[fer_m] = 0.5
    s.rugosite_fixe = rf
    s.variable &= ~(fer_m | dalle | ombre)
    s.moyenne &= ~(fer_m | dalle | ombre)


def _mur_rideau(t: _Toile, s: _Couches) -> None:
    """Mur-rideau : vitrages de vision (reflet de ciel), allège opaque au niveau du plancher, meneaux et
    traverses métalliques ; deux panneaux par travée."""
    T = t.T
    u, v = t.u, t.v
    n = _diviseur(T, 1.5)
    pas = T / n
    du = np.abs(np.mod(u, pas) - pas / 2)
    meneau = du > pas / 2 - 0.035
    allege_h = 0.3 * T
    traverse = (np.abs(v - allege_h) < 0.03) | (v < 0.03) | (v > T - 0.03)
    allege = v < allege_h
    base = s.couleur
    hauteur_rel = np.clip((v - allege_h) / (T - allege_h), 0, 1)
    panneau = np.floor(u / pas)
    teinte = 1.0 + 0.08 * (_hache(panneau.astype(np.int64), graine=t.sel("panneau")) - 0.5)
    reflet = (0.55 + 0.75 * hauteur_rel + 0.15 * t.bruit(T, T / 3, sel="ciel")) * teinte
    vitre = base * reflet[..., None]
    allege_c = base * 0.45
    metal = _lin(vocabulaire.PALETTE["gris_clair"]) * 0.7
    c = np.where(allege[..., None], allege_c, vitre)
    cadre = meneau | traverse
    c = np.where(cadre[..., None], metal, c)
    s.couleur = c.astype(np.float32)
    s.hauteur += 0.02 * cadre
    rf = np.full((t.res, t.res), np.nan, np.float32)
    rf[cadre] = 0.35
    s.rugosite_fixe = rf
    s.variable = ~cadre
    s.moyenne = np.ones_like(cadre)


def _vitrine(t: _Toile, s: _Couches) -> None:
    """Rez-de-chaussée commercial : soubassement, grande vitrine (intérieur éclairé, reflet), porte, bandeau
    d'enseigne en haut ; la couleur de la spec est celle de la devanture (cadre, bandeau)."""
    T = t.T
    u, v = t.u, t.v
    soub = 0.08 * T
    bandeau_bas = 0.76 * T
    marge = 0.05 * T
    vitre = (v > soub) & (v < bandeau_bas - 0.08) & (u > marge) & (u < T - marge)
    porte = (u > 0.66 * T) & (u < 0.66 * T + 0.25 * T) & (v > 0.01) & (v < bandeau_bas - 0.08)
    ouvert = vitre | porte
    base = s.couleur
    hauteur_rel = np.clip(v / bandeau_bas, 0, 1)
    # intérieur de boutique : rayonnages (tablettes éclairées) portant des articles de 10-25 cm, aux
    # teintes sourdes tirées autour de la couleur de la devanture
    pas_rayon = 0.45
    rang = np.floor((v - soub) / pas_rayon).astype(np.int64)
    yr = np.mod(v - soub, pas_rayon)
    tablette = _bande(yr - 0.02, 0.015, t.px)

    def longueurs(j: int) -> list[float]:
        r = np.random.default_rng(t.sel("articles", j))
        return list(r.uniform(0.10, 0.25, int(T / 0.12) + 2))

    cel = _rangees(t, [1.0] * _diviseur(T, pas_rayon), longueurs, lambda j: 0.0, dephasage=False)
    hauteur_art = (0.35 + 0.45 * _hache(cel.id, graine=t.sel("haut"))) * pas_rayon
    articles = ((yr > 0.04) & (yr < 0.04 + hauteur_art) & (cel.x > 0.01)).astype(np.float32)
    teinte_article = base * (0.6 + 0.9 * np.stack([_hache(cel.id, graine=t.sel("art", k)) for k in range(3)], -1)) \
        + _palette("creme") * 0.15 * _hache(cel.id, graine=t.sel("lum"))[..., None]
    del rang
    eclairage = _palette("creme") * 0.45
    interieur = (_palette("anthracite") * 0.3 * (1 - articles[..., None]) + teinte_article * 0.7 * articles[..., None]
                 + eclairage * tablette[..., None]) * (0.55 + 0.45 * (1 - hauteur_rel))[..., None]
    ciel = _palette("bleu_gris") * (0.15 + 0.55 * hauteur_rel ** 2)[..., None]
    c = np.where(ouvert[..., None], interieur + ciel, base)
    bord = np.minimum(np.minimum(np.abs(u - marge), np.abs(u - (T - marge))), np.abs(v - soub))
    cadre = ~ouvert & (v < bandeau_bas) & (bord < 0.06)
    montant = porte & ((np.abs(u - 0.66 * T) < 0.04) | (np.abs(u - 0.91 * T) < 0.04) | (np.abs(v - 0.45 * T) < 0.02))
    c = np.where(montant[..., None], base * 0.6, c)
    enseigne = (v > bandeau_bas) & (v < 0.94 * T)
    c = np.where(enseigne[..., None], _ton(base, 1.0 + 0.03 * t.bruit(0.3, sel="tole")), c)
    corniche = v >= 0.94 * T
    c = np.where(corniche[..., None], base * 0.7, c)
    s.couleur = np.where(cadre[..., None], base * 0.8, c).astype(np.float32)
    s.hauteur = np.where(ouvert & ~montant, -0.03, 0.0).astype(np.float32) + 0.01 * corniche
    rf = np.full((t.res, t.res), np.nan, np.float32)
    rf[ouvert & ~montant] = 0.05
    s.rugosite_fixe = rf
    s.variable = ~ouvert
    s.moyenne = ~ouvert
    s.occlusion = np.where(ouvert & (v > bandeau_bas - 0.25), 0.7, 1.0).astype(np.float32)


def _bardage(t: _Toile, s: _Couches) -> None:
    cel = _appareil(t, 3.0, 0.15, decalage=0.0)
    ys = cel.y / cel.h
    lum, pores = _veinage(t, t.v, t.u, 0.008, "bardage")
    r = _hache(cel.rang, graine=t.sel("planche"))
    ombre = 0.55 + 0.45 * _lisse(0.0, 0.12, ys)
    s.couleur = _ton(s.couleur, lum * ombre * (1 + 0.12 * (r - 0.5)), (1.0, 1.05, 1.15))
    s.hauteur += 0.012 * ys + pores
    s.occlusion = ombre


# ── Recettes : chaque clé du vocabulaire → (motif, variante de couleur) ───────────────────────────
def _r_parquet(t, s, spec):
    _lames(t, s, largeur=0.15, l_min=0.5, l_max=1.2, joint=0.0015)


RECETTES: dict[str, Callable[[_Toile, _Couches, dict], None]] = {
    "parquet_chene": _r_parquet,
    "parquet_fonce": _r_parquet,
    "carrelage": lambda t, s, spec: (_nuages(t, s, echelle=0.2, force=0.02),
                                     _carreaux(t, s, spec, longueur=0.6, hauteur=0.6, decalage=0.0,
                                               joint=0.003, biseau=0.0003, variation=0.0)),
    "carrelage_metro": lambda t, s, spec: _carreaux(t, s, spec, longueur=0.15, hauteur=0.075, decalage=0.5,
                                                    joint=0.002, biseau=0.0015, variation=0.035),
    "carreaux_ciment": lambda t, s, spec: _ciment_motif(t, s),
    "tomette": lambda t, s, spec: _hexagones(t, s, cote=0.095, joint=0.006),
    "marbre": lambda t, s, spec: _marbre(t, s),
    "beton_cire": lambda t, s, spec: (_nuages(t, s, echelle=0.6, force=0.09, fin=0.01),
                                      _nuages(t, s, echelle=0.12, force=0.04)),
    "platre_peint": lambda t, s, spec: _enduit(t, s, grain=0.0003, force=0.015),
    "papier_peint": lambda t, s, spec: _papier_peint(t, s),
    "lambris": lambda t, s, spec: _lames(t, s, largeur=0.1, l_min=1.0, l_max=1.0001, joint=0.004,
                                         verticales=True, rainure=0.002, contraste=0.06),
    "brique": lambda t, s, spec: _brique(t, s),
    "pierre": lambda t, s, spec: _pierre_taille(t, s, assise=0.3, l_min=0.35, l_max=0.8, joint=0.008),
    "moquette": lambda t, s, spec: (_nuages(t, s, echelle=0.3, force=0.04),
                                    setattr(s, "couleur", _ton(s.couleur, 1 + 0.12 * t.bruit(t.px * 1.2, sel="boucles")))),
    "bois_chene": lambda t, s, spec: _bois_massif(t, s),
    "bois_noyer": lambda t, s, spec: _bois_massif(t, s),
    "bois_clair": lambda t, s, spec: _bois_massif(t, s),
    "bois_peint": lambda t, s, spec: (_uni(t, s, force=0.01),
                                      setattr(s, "hauteur", s.hauteur + 0.00004 * t.bruit(0.1, 0.0015, sel="fil"))),
    "laque": lambda t, s, spec: _uni(t, s, force=0.006, peau=0.000005),
    "tissu": lambda t, s, spec: _tissage(t, s, fil=0.0012, force=0.10, relief=0.00025),
    "velours": lambda t, s, spec: (_nuages(t, s, echelle=0.08, force=0.08),
                                   setattr(s, "hauteur", s.hauteur + 0.00006 * t.bruit(t.px, sel="poil"))),
    "cuir": lambda t, s, spec: _cuir(t, s),
    "laine": lambda t, s, spec: _laine(t, s),
    "metal_chrome": lambda t, s, spec: _patine(t, s, force=0.01, rugo=0.02),
    "inox": lambda t, s, spec: _brosse(t, s, force=0.12),
    "metal_noir": lambda t, s, spec: _fonte(t, s),
    "laiton": lambda t, s, spec: (_patine(t, s, force=0.10, rugo=0.08), _brosse(t, s, force=0.04)),
    "cuivre": lambda t, s, spec: (_patine(t, s, force=0.12, rugo=0.08), _brosse(t, s, force=0.04)),
    "fonte": lambda t, s, spec: _fonte(t, s),
    "verre": lambda t, s, spec: _uni(t, s, force=0.004, peau=0.0),
    "verre_depoli": lambda t, s, spec: _depoli(t, s),
    "miroir": lambda t, s, spec: _uni(t, s, force=0.003, peau=0.0),
    "ceramique": lambda t, s, spec: _uni(t, s, force=0.008, peau=0.000004),
    "plastique": lambda t, s, spec: _uni(t, s, force=0.01, peau=0.00002),
    "ecran": lambda t, s, spec: _uni(t, s, force=0.02, peau=0.0),
    "lumiere": lambda t, s, spec: _tissage(t, s, fil=0.0015, force=0.05, relief=0.0001, flamme=0.03),
    "plante": lambda t, s, spec: _feuilles(t, s, longueur=0.09),
    "terre_cuite": lambda t, s, spec: (_nuages(t, s, echelle=0.08, force=0.08, fin=0.04, relief=0.0001,
                                               teinte=(1.0, 1.2, 1.3))),
    "papier": lambda t, s, spec: _livres(t, s),
    "asphalte": lambda t, s, spec: _asphalte(t, s),
    "marquage": lambda t, s, spec: _marquage(t, s),
    "trottoir": lambda t, s, spec: _dalles(t, s, cote=0.5),
    "paves": lambda t, s, spec: _pave(t, s),
    "gravier": lambda t, s, spec: _graviers(t, s, taille=0.022, ton=0.3),
    "herbe": lambda t, s, spec: _herbe(t, s),
    "terre": lambda t, s, spec: _terre(t, s),
    "sable": lambda t, s, spec: _sable(t, s),
    "roche": lambda t, s, spec: _roche(t, s),
    "neige": lambda t, s, spec: _neige(t, s),
    "eau": lambda t, s, spec: _eau(t, s),
    "eau_vive": lambda t, s, spec: _eau_vive(t, s),
    "ecorce": lambda t, s, spec: _ecorce(t, s),
    "feuillage": lambda t, s, spec: _feuilles(t, s, longueur=0.07),
    "facade_enduit": lambda t, s, spec: (_enduit(t, s), _fenetre(t, s, menuiserie="claire")),
    "facade_brique": lambda t, s, spec: (_brique(t, s), _fenetre(t, s, menuiserie="claire", linteau=True)),
    "facade_pierre": lambda t, s, spec: (_pierre_taille(t, s, assise=0.5, l_min=0.7, l_max=1.3, joint=0.006,
                                                        h_alea=0.0),
                                         _fenetre(t, s, menuiserie="claire", balcon=True)),
    "facade_beton": lambda t, s, spec: (_beton(t, s, banches=(1.5, 0.75)), _fenetre(t, s, menuiserie="sombre",
                                                                                   appui="metal")),
    "facade_bois": lambda t, s, spec: (_bardage(t, s), _fenetre(t, s, menuiserie="sombre", appui="metal")),
    "mur_rideau": lambda t, s, spec: _mur_rideau(t, s),
    "vitrine": lambda t, s, spec: _vitrine(t, s),
    "tuile": lambda t, s, spec: _tuiles(t, s),
    "ardoise": lambda t, s, spec: _ardoises(t, s),
    "zinc": lambda t, s, spec: _zinc(t, s),
    "toit_terrasse": lambda t, s, spec: _graviers(t, s, taille=0.018, ton=0.35, relief=0.8),
    "carrosserie": lambda t, s, spec: _uni(t, s, force=0.005, peau=0.00001),
    "caoutchouc": lambda t, s, spec: _fonte(t, s),
}

# Repli par famille : une clé future sans recette reçoit le motif de sa famille (jamais d'échec).
RECETTES_FAMILLE: dict[str, Callable[[_Toile, _Couches, dict], None]] = {
    "bois": lambda t, s, spec: _bois_massif(t, s),
    "ceramique": lambda t, s, spec: _uni(t, s, force=0.01),
    "pierre": lambda t, s, spec: _nuages(t, s, echelle=0.3, force=0.08, fin=0.02),
    "peinture": lambda t, s, spec: _uni(t, s),
    "tissu": lambda t, s, spec: _tissage(t, s, fil=0.0012, force=0.08, relief=0.0002),
    "metal": lambda t, s, spec: _patine(t, s, force=0.04, rugo=0.04),
    "verre": lambda t, s, spec: _uni(t, s, force=0.004, peau=0.0),
    "plastique": lambda t, s, spec: _uni(t, s),
    "lumiere": lambda t, s, spec: _uni(t, s),
    "vegetal": lambda t, s, spec: _feuilles(t, s, longueur=0.08),
    "sol_ext": lambda t, s, spec: _terre(t, s),
    "eau": lambda t, s, spec: _eau(t, s),
    "eau_vive": lambda t, s, spec: _eau_vive(t, s),
    "facade": lambda t, s, spec: (_enduit(t, s), _fenetre(t, s, menuiserie="claire")),
}


# ── Assemblage des images ──────────────────────────────────────────────────────────────────────────
def _caler_moyenne(couleur: np.ndarray, variable: np.ndarray, moyenne: np.ndarray, cible_srgb: np.ndarray) -> np.ndarray:
    """Gain linéaire par canal sur les pixels variables pour que la moyenne sRGB de la zone `moyenne`
    égale la cible (bornée à l'albédo physique)."""
    c = couleur.copy()
    if not moyenne.any():
        moyenne = np.ones_like(moyenne)
    if not variable.any():
        return np.clip(c, ALBEDO_MIN, ALBEDO_MAX)
    for _ in range(12):
        c = np.clip(c, ALBEDO_MIN, ALBEDO_MAX)
        m = _vers_srgb(c[moyenne]).mean(axis=0)
        gain = _vers_lineaire(np.clip(cible_srgb, 0.01, 1.0)) / np.maximum(_vers_lineaire(m), 1e-5)
        if np.all(np.abs(m - cible_srgb) < 0.002):
            break
        c[variable] *= gain
    return np.clip(c, ALBEDO_MIN, ALBEDO_MAX)


def _normales(hauteur: np.ndarray, px: float) -> np.ndarray:
    """Carte de normales tangente (OpenGL, +Y = haut de l'image) d'un relief en mètres, gradients enroulés."""
    dhu = (np.roll(hauteur, -1, axis=1) - np.roll(hauteur, 1, axis=1)) / (2 * px)
    dhv = (np.roll(hauteur, 1, axis=0) - np.roll(hauteur, -1, axis=0)) / (2 * px)   # ligne 0 = haut = +v
    n = np.stack([-dhu, -dhv, np.ones_like(hauteur)], -1)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    return n


def _graine(cle: str) -> int:
    return zlib.crc32(cle.partition(":")[0].encode()) & 0x7FFFFFFF


@lru_cache(maxsize=256)
def _calculer(cle: str, resolution: int) -> dict[str, np.ndarray]:
    spec = vocabulaire.materiau(cle)
    base = spec["cle"]
    t = _Toile(int(resolution), float(spec["taille_m"]), _graine(cle), peint=":" in cle)
    cible = np.asarray(couleur_srgb(spec["couleur"]), np.float32)
    s = _couches(t, np.minimum(_vers_lineaire(cible), ALBEDO_MAX))
    recette = RECETTES.get(base) or RECETTES_FAMILLE.get(spec["famille"]) or RECETTES_FAMILLE["peinture"]
    recette(t, s, spec)
    couleur = _caler_moyenne(s.couleur.astype(np.float32), s.variable, s.moyenne, cible)
    # relief : adouci d'un demi-pixel (anticrénelage), puis normales et cavités
    hauteur = t.flou(s.hauteur.astype(np.float32), t.px * 0.6)
    normale = _normales(hauteur, t.px)
    cavite = np.clip((t.flou(hauteur, t.px * 6) - hauteur) / max(t.px * 0.8, 1e-4), 0.0, 1.0)
    occlusion = np.clip(1.0 - 0.6 * cavite, 0.0, 1.0)
    if s.occlusion is not None:
        occlusion = occlusion * np.clip(s.occlusion, 0.0, 1.0)
    rug = s.rugosite.astype(np.float32)
    zone = s.moyenne if s.moyenne.any() else np.ones_like(s.moyenne)
    # variation RELATIVE : ±0,03 est invisible sur un plâtre (0,85) mais tache un miroir (0,02) ; l'écart
    # suit la rugosité de base (une surface polie ne varie qu'en proportion de son poli)
    echelle_rug = float(np.clip(float(spec["rugosite"]) / 0.4, 0.1, 1.0))
    rug = float(spec["rugosite"]) + echelle_rug * (rug - float(rug[zone].mean()))
    if s.rugosite_fixe is not None:
        fixe = ~np.isnan(s.rugosite_fixe)
        rug = np.where(fixe, s.rugosite_fixe, rug)
        libre = zone & ~fixe
        if libre.any():
            rug = np.where(fixe, rug, rug + float(spec["rugosite"]) - float(rug[libre].mean()))
    rug = np.clip(rug, 0.02, 1.0)
    metal = np.full_like(rug, float(spec["metal"]))
    sortie = {
        "couleur": np.round(_vers_srgb(couleur) * 255.0).astype(np.uint8),
        "orm": np.round(np.stack([occlusion, rug, metal], -1) * 255.0).astype(np.uint8),
        "normale": np.round((normale * 0.5 + 0.5) * 255.0).astype(np.uint8),
        "moyenne": zone,
    }
    alpha = float(spec.get("alpha", 1.0))
    if alpha < 0.999:
        a = np.full(rug.shape, alpha, np.float32)
        if s.alpha is not None:
            a = np.clip(s.alpha, 0, 1)
        sortie["alpha"] = np.round(a * 255.0).astype(np.uint8)
    return sortie


def textures(cle: str, resolution: int = 512) -> dict[str, Image.Image]:
    """Textures procédurales répétables du matériau : {"couleur" (RGB, RGBA si translucide) sRGB,
    "orm" (R occlusion, G rugosité, B métal), "normale" (tangente, OpenGL)}. Copies : l'appelant peut
    les modifier sans toucher au cache."""
    d = _calculer(cle, int(resolution))
    if "alpha" in d:
        couleur = Image.fromarray(np.dstack([d["couleur"], d["alpha"]]), "RGBA")
    else:
        couleur = Image.fromarray(d["couleur"], "RGB")
    return {"couleur": couleur, "orm": Image.fromarray(d["orm"], "RGB"),
            "normale": Image.fromarray(d["normale"], "RGB")}


def zone_moyenne(cle: str, resolution: int = 512) -> np.ndarray:
    """Masque des pixels dont la moyenne de couleur égale la spec (le mur d'une façade, sans la fenêtre)."""
    return _calculer(cle, int(resolution))["moyenne"].copy()


# ── Rendu demandé : réaliste, animé (3D d'animation haut de gamme) ou toon (dessin animé 2D) ───────
# Loi générale (15/11/2026, « le plus réaliste À LA DEMANDE ») : la même scène se rend dans le médium que la
# demande vise. Réaliste : textures physiques telles quelles. Animé : le grain fin disparaît, les couleurs
# gagnent en saturation et en lumière, les matières s'adoucissent (rugosité moyenne, relief léger), comme
# dans un long métrage d'animation 3D. Toon : en plus, les couleurs se posent en aplats (postérisation).
RENDUS = ("realiste", "anime", "toon")


def rendu_depuis_cible(cible: str | None) -> str:
    """Le médium visé par le contrat de demande (`style.cible`) → rendu des matériaux."""
    return {"photo": "realiste", "cgi_3d": "anime", "figurine": "anime", "cel_2d": "toon"}.get(cible or "", "realiste")


def styliser(images: dict[str, Image.Image], rendu: str) -> dict[str, Image.Image]:
    """Textures réalistes → textures du médium d'animation (mêmes motifs, sans le grain photographique)."""
    if rendu == "realiste" or not images:
        return images
    from PIL import ImageEnhance, ImageFilter
    sortie = dict(images)
    if "couleur" in images:
        base = images["couleur"]
        alpha = base.getchannel("A") if base.mode == "RGBA" else None
        rgb = base.convert("RGB")
        rayon = max(1.0, rgb.width / 170.0)
        rgb = rgb.filter(ImageFilter.GaussianBlur(rayon)).filter(ImageFilter.MedianFilter(3))
        rgb = ImageEnhance.Color(rgb).enhance(1.35 if rendu == "anime" else 1.5)
        rgb = ImageEnhance.Brightness(rgb).enhance(1.06)
        rgb = ImageEnhance.Contrast(rgb).enhance(1.05)
        if rendu == "toon":
            rgb = rgb.quantize(colors=6, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE).convert("RGB")
        if alpha is not None:
            rgb.putalpha(alpha)
        sortie["couleur"] = rgb
    if "orm" in images:
        a = np.asarray(images["orm"].convert("RGB"), dtype=np.float32)
        a[..., 0] = 255.0                                        # pas d'occlusion photographique gravée
        a[..., 1] = 0.55 * a[..., 1] + 0.45 * 0.62 * 255.0       # matières adoucies
        sortie["orm"] = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(2))
    if "normale" in images:
        n = np.asarray(images["normale"].convert("RGB"), dtype=np.float32) / 127.5 - 1.0
        force = 0.3 if rendu == "anime" else 0.15
        n[..., :2] *= force
        n /= np.linalg.norm(n, axis=2, keepdims=True) + 1e-9
        sortie["normale"] = Image.fromarray(np.clip((n + 1.0) * 127.5, 0, 255).astype(np.uint8))
    return sortie


def _saturer(rgb: tuple[float, float, float], rendu: str) -> tuple[float, float, float]:
    if rendu == "realiste":
        return rgb
    gris = sum(rgb) / 3.0
    k = 1.35 if rendu == "anime" else 1.5
    return tuple(min(1.0, max(0.0, (gris + (c - gris) * k) * 1.06)) for c in rgb)  # type: ignore[return-value]


@lru_cache(maxsize=512)
def materiau_trimesh(cle: str, resolution: int = 512, rendu: str = "realiste") -> PBRMaterial:
    spec: dict[str, Any] = vocabulaire.materiau(cle)
    r, g, b = couleur_lineaire(spec["couleur"])
    alpha = float(spec.get("alpha", 1.0))
    if rendu not in RENDUS:
        raise KeyError(f"rendu hors vocabulaire : {rendu!r}")
    images = styliser(dict(textures(cle, resolution)), rendu)
    r, g, b = _saturer((r, g, b), rendu)
    if alpha < 0.999:
        # f3d 2.5 ignore l'alpha du facteur (mesuré dans ce projet) : la translucidité passe par la texture,
        # et le facteur garde alpha = 1 pour que tous les visualiseurs montrent la même chose.
        base = images.get("couleur")
        if base is None:
            base = Image.new("RGB", (4, 4), tuple(int(round(c * 255)) for c in couleur_srgb(spec["couleur"])))
        if base.mode != "RGBA":
            base = base.convert("RGBA")
            base.putalpha(int(round(alpha * 255)))
        images["couleur"] = base
        alpha = 1.0
    famille = spec["famille"]
    double = famille in {"verre", "vegetal", "eau", "lumiere"}
    options: dict[str, Any] = {
        "name": cle.replace(":", "_"),
        "baseColorFactor": [r, g, b, alpha] if "couleur" not in images else [1.0, 1.0, 1.0, alpha],
        "metallicFactor": float(spec["metal"]) if "orm" not in images else 1.0,
        "roughnessFactor": float(spec["rugosite"]) if "orm" not in images else 1.0,
        "doubleSided": double,
        "alphaMode": "BLEND" if float(spec.get("alpha", 1.0)) < 0.999 else "OPAQUE",
    }
    if "couleur" in images:
        options["baseColorTexture"] = images["couleur"]
    if "orm" in images:
        options["metallicRoughnessTexture"] = images["orm"]
    if "normale" in images:
        options["normalTexture"] = images["normale"]
    if spec.get("emissif"):
        k = float(spec["emissif"])
        options["emissiveFactor"] = [r * k, g * k, b * k]
    return PBRMaterial(**options)


def planche(cles: list[str], resolution: int = 256) -> Image.Image:
    """Planche de contrôle : par matériau, la couleur de base, puis normale | rugosité en bandeau, et le
    nom de la clé (vérification à l'œil de l'échelle, des raccords et des couleurs)."""
    cote = resolution
    colonnes = 8
    lignes = (len(cles) + colonnes - 1) // colonnes
    haut = cote + cote // 3 + 14
    image = Image.new("RGB", (colonnes * cote, max(1, lignes) * haut), (40, 40, 40))
    dessin = ImageDraw.Draw(image)
    for i, cle in enumerate(cles):
        x, y = (i % colonnes) * cote, (i // colonnes) * haut
        tex = textures(cle, resolution)
        image.paste(tex["couleur"].convert("RGB").resize((cote, cote)), (x, y + 14))
        demi = cote // 2
        image.paste(tex["normale"].resize((demi, cote // 3)), (x, y + 14 + cote))
        rug = tex["orm"].split()[1].convert("RGB")
        image.paste(rug.resize((cote - demi, cote // 3)), (x + demi, y + 14 + cote))
        dessin.text((x + 3, y + 1), cle, fill=(235, 235, 235))
    return image


def _verifier_repetable(img: Image.Image, tolerance: float = 0.12) -> bool:
    """Un motif répétable a des bords qui se raccordent : écart moyen bord gauche/droit et haut/bas."""
    a = np.asarray(img.convert("RGB"), dtype=np.float32) / 255.0
    return float(np.abs(a[:, 0] - a[:, -1]).mean()) < tolerance and float(np.abs(a[0] - a[-1]).mean()) < tolerance


# ── Démonstration et contrôle visuel (rendu f3d) ───────────────────────────────────────────────────
def demo(dossier: str, *, resolution: int = 512, rendu_px: tuple[int, int] = (1500, 1050)) -> dict[str, Any]:
    """Trois scènes de contrôle exportées en GLB et rendues par f3d : nuancier (une dalle de 1 m et une
    sphère par clé, plus les façades en panneaux verticaux de 2 × 2 modules), un salon (parquet, plâtre,
    canapé en tissu, tapis en laine, table en chêne, bibliothèque garnie) et une rue (façades, trottoir,
    chaussée). Planche des textures à côté. Aucune valeur propre à une scène : les matériaux viennent du
    vocabulaire, les dimensions sont celles d'objets courants."""
    from pathlib import Path

    from monde import export_gltf, geometrie as g, rendu
    from monde.ir import Instance, Noeud, Objet, Partie, Pose, Scene

    sortie = Path(dossier)
    sortie.mkdir(parents=True, exist_ok=True)
    rapport: dict[str, Any] = {}
    cles = list(vocabulaire.MATERIAUX)
    planche(cles, 192).save(sortie / "planche_textures.png")
    rapport["planche_textures"] = {"planche": str(sortie / "planche_textures.png")}

    # 1. nuancier
    parties, colonnes, pas = [], 10, 1.5
    simples = [c for c in cles if vocabulaire.MATERIAUX[c]["famille"] != "facade"]
    for i, cle in enumerate(simples):
        x, z = (i % colonnes) * pas, (i // colonnes) * pas
        parties.append(Partie(g.plaque(g.rectangle_xz(x - 0.5, z - 0.5, x + 0.5, z + 0.5), 0.04, y=0.04), cle, cle))
        parties.append(Partie(g.sphere(0.3, x=x + 0.15, y=0.34, z=z + 0.1), cle, cle + "_sphere"))
    facades = [c for c in cles if vocabulaire.MATERIAUX[c]["famille"] == "facade"]
    glb = sortie / "nuancier.glb"
    rapport["nuancier"] = export_gltf.exporter(Scene(Noeud("nuancier", parties=parties)), glb, resolution=resolution)
    rapport["nuancier_rendu"] = rendu.rendre_vues(glb, sortie, vues=("plan", "rasante", "aerienne_sud_est"),
                                                  resolution=rendu_px, prefixe="nuancier")

    # 2. salon
    L, P, H = 5.0, 4.0, 2.6
    murs = [Partie(g.plaque(g.rectangle_xz(0, 0, L, P), 0.05), "parquet_chene", "sol"),
            Partie(g.boite(L, H, 0.1, x=L / 2, z=-0.05), "platre_peint", "mur_nord"),
            Partie(g.boite(0.1, H, P, x=-0.05, z=P / 2), "platre_peint", "mur_ouest"),
            Partie(g.boite(0.1, H, P, x=L + 0.05, z=P / 2), "platre_peint", "mur_est")]
    canape = Objet("canape", "canape", [
        Partie(g.boite_arrondie(2.2, 0.42, 0.9, 0.05), "tissu", "socle"),
        Partie(g.boite_arrondie(1.9, 0.14, 0.62, 0.06, y=0.42, z=0.1), "tissu", "assise"),
        Partie(g.boite_arrondie(1.9, 0.42, 0.2, 0.08, y=0.42, z=-0.33), "tissu", "dossier"),
        Partie(g.boite_arrondie(0.16, 0.24, 0.9, 0.06, x=-1.02, y=0.4), "tissu", "accoudoir_g"),
        Partie(g.boite_arrondie(0.16, 0.24, 0.9, 0.06, x=1.02, y=0.4), "tissu", "accoudoir_d")],
        largeur=2.2, profondeur=0.9, hauteur=0.82)
    tapis = Objet("tapis", "tapis", [Partie(g.boite(2.4, 0.012, 1.7), "laine", "surface")],
                  largeur=2.4, profondeur=1.7, hauteur=0.012, sol_partage=True)
    pieds = [Partie(g.boite(0.05, 0.38, 0.05, x=sx * 0.5, z=sz * 0.27), "bois_chene", "pied")
             for sx in (-1, 1) for sz in (-1, 1)]
    table = Objet("table_basse", "table_basse", [Partie(g.boite(1.1, 0.04, 0.6, y=0.38), "bois_chene", "plateau"),
                                                 *pieds], largeur=1.1, profondeur=0.6, hauteur=0.42)
    biblio_parties = [Partie(g.boite(0.9, 2.0, 0.02, z=-0.15), "bois_clair", "fond")]
    for k in range(6):
        biblio_parties.append(Partie(g.boite(0.9, 0.025, 0.32, y=k * 0.38), "bois_clair", "rayon"))
    for k in range(5):
        biblio_parties.append(Partie(g.boite(0.86, 0.3, 0.22, y=k * 0.38 + 0.025, z=-0.03), "papier", "livres"))
    biblio = Objet("bibliotheque", "bibliotheque", biblio_parties, largeur=0.9, profondeur=0.32, hauteur=2.0)
    salon = Noeud("salon", parties=murs, instances=[
        Instance(canape, Pose(2.5, 0.55, 0.0), "canape"), Instance(tapis, Pose(2.5, 1.9), "tapis"),
        Instance(table, Pose(2.5, 2.0), "table_basse"),
        Instance(biblio, Pose(0.18, 2.6, math.pi / 2), "bibliotheque")])
    glb = sortie / "salon.glb"
    rapport["salon"] = export_gltf.exporter(Scene(salon), glb, resolution=resolution)
    rapport["salon_rendu"] = rendu.rendre_vues(glb, sortie, vues=("plan", "rasante", "aerienne_sud_est"),
                                               resolution=(1100, 850), prefixe="salon")

    # 3. rue : un immeuble par matériau de façade, trottoir et chaussée devant
    parties, x = [], 0.0
    for cle in facades:
        T = vocabulaire.MATERIAUX[cle]["taille_m"]
        largeur, hauteur = 3 * T, (4 if T < 3.5 else 1) * T
        parties.append(Partie(g.boite(largeur, hauteur, 8.0, x=x + largeur / 2, z=-4.0), cle, cle))
        parties.append(Partie(g.plaque(g.rectangle_xz(x, -8.0, x + largeur, 0.0), 0.05, y=hauteur + 0.05),
                              "toit_terrasse", "toit"))
        x += largeur
    parties.append(Partie(g.plaque(g.rectangle_xz(-2, 0, x + 2, 3.0), 0.15, y=0.15), "trottoir", "trottoir"))
    parties.append(Partie(g.plaque(g.rectangle_xz(-2, 3.0, x + 2, 10.0), 0.05, y=0.0), "asphalte", "chaussee"))
    parties.append(Partie(g.plaque(g.rectangle_xz(-2, 6.42, x + 2, 6.58), 0.01, y=0.005), "marquage", "axe"))
    glb = sortie / "rue.glb"
    rapport["rue"] = export_gltf.exporter(Scene(Noeud("rue", parties=parties)), glb, resolution=resolution)
    rapport["rue_rendu"] = rendu.rendre_vues(glb, sortie, vues=("rasante", "aerienne_sud_est"),
                                             resolution=(1400, 800), prefixe="rue")
    return rapport


if __name__ == "__main__":
    import argparse
    import json

    analyse = argparse.ArgumentParser(description="Textures procédurales PBR du moteur « monde »")
    analyse.add_argument("--demo", metavar="DOSSIER", help="exporte et rend le nuancier, le salon et la rue")
    analyse.add_argument("--resolution", type=int, default=512)
    arguments = analyse.parse_args()
    if arguments.demo:
        res = demo(arguments.demo, resolution=arguments.resolution)
        print(json.dumps({k: (v.get("planche") if "planche" in v else
                              {kk: v[kk] for kk in ("triangles", "octets", "blanc_pur_max") if kk in v})
                          for k, v in res.items()}, ensure_ascii=False, indent=1))
