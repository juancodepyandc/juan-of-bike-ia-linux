"""Meubles, objets et végétation paramétriques du moteur « monde ».

Une seule entrée, `generer(categorie, ...)`, pour toutes les catégories de `vocabulaire.CATEGORIES` :
chaque catégorie a un constructeur qui assemble les primitives de `monde.geometrie` (coussins et matelas
arrondis, pieds tournés ou fuselés, abat-jour au tour, façades à joints, livres variés, couronnes
bosselées...) à partir de LOIS GÉNÉRALES : dimensions réelles tirées dans la fourchette du vocabulaire,
proportions relatives (une assise à 43 cm, un plan de travail à hauteur du coude, des montants espacés
d'un module de 60 cm), styles de mobilier (pieds, arrondis, poignées, essences). Aucune règle ne nomme un
sujet, un lieu ou une scène ; aucune coordonnée n'est figée pour un livrable.

Contrat (voir `monde.ir`) :
- repère local : emprise centrée sur l'origine en x et z, géométrie de y = 0 à y = hauteur, face vers +Z ;
- largeur / profondeur / hauteur de l'`Objet` = étendue RÉELLE de la géométrie (x, z, y) : le constructeur
  vise les dimensions demandées, puis une loi d'ajustement recale l'enveloppe au millimètre ;
- objets muraux : dos à z = -profondeur/2 (le placeur les monte à `hauteur_pose`) ; objets de plafond :
  point bas à y = 0, attache à y = hauteur (le placeur pose y = plafond - hauteur) ;
- chaque `Partie` porte le nom de son emplacement de matériau et la clé de matériau de cet emplacement.

Exception documentée : pour le linéaire de cuisine (`plan_de_travail`), la hauteur demandée est la
HAUTEUR DU PLAN (celle de la cuisinière et du lave-vaisselle voisins) ; le robinet dépasse au-dessus et la
hauteur déclarée de l'objet reste son étendue réelle. La surface utilisable est à la hauteur du plan.
"""
from __future__ import annotations

import argparse
import math
from dataclasses import dataclass, field
from typing import Any, Callable, Sequence

import numpy as np
import trimesh
from shapely.geometry import Point, Polygon, box as rect_shapely
from trimesh.visual import TextureVisuals

from monde import geometrie as g
from monde import vocabulaire as voc
from monde.ir import Objet, Partie, Surface

# ── Styles de mobilier ─────────────────────────────────────────────────────────────────────────────
# Lois de style (connaissance générale du mobilier) : forme des pieds, arrondi des coussins et chants,
# poignées, essence de bois et métal substitués aux emplacements que le programme n'a pas fixés.
STYLES_MEUBLES: dict[str, dict[str, Any]] = {
    "moderne": {"pied": "fin", "poignee": "barre", "arrondi": 0.02, "haut_pied": 0.12, "socle": True,
                "moulures": False, "bois": None, "pieds": "metal_noir", "metal": None, "tissu": None},
    "classique": {"pied": "tourne", "poignee": "bouton", "arrondi": 0.055, "haut_pied": 0.12, "socle": False,
                  "moulures": True, "bois": "bois_noyer", "pieds": "bois_noyer", "metal": "laiton", "tissu": None},
    "scandinave": {"pied": "fuseau", "poignee": "bouton", "arrondi": 0.045, "haut_pied": 0.18, "socle": False,
                   "moulures": False, "bois": "bois_clair", "pieds": "bois_clair", "metal": None, "tissu": None},
    "industriel": {"pied": "tube", "poignee": "barre", "arrondi": 0.012, "haut_pied": 0.14, "socle": False,
                   "moulures": False, "bois": None, "pieds": "metal_noir", "metal": "metal_noir", "tissu": "cuir"},
}
# Groupes de catégories auxquels le style substitue essences et métaux (le mobilier ; pas l'électroménager,
# les sanitaires, l'urbain ni les véhicules, dont le style ne change que la forme).
GROUPES_STYLES = {"assise", "table", "rangement", "couchage", "luminaire"}
EMPLACEMENTS_PIEDS = ("pieds", "montants")

# Styles d'arbres (vocabulaire.CATEGORIES["arbre"]["styles"]) : matériaux par défaut propres à l'essence
# (écorce blanche du bouleau, feuillage sombre des conifères), appliqués si le programme ne les fixe pas.
STYLES_ARBRES: dict[str, dict[str, str]] = {
    "feuillu": {},
    "conifere": {"feuillage": "feuillage:vert_foret"},
    "palmier": {"feuillage": "feuillage:#5f8a37"},
    "fruitier": {"feuillage": "feuillage:#4d7d34"},
    "bouleau": {"tronc": "bois_peint:blanc_casse", "feuillage": "feuillage:#7ea24a"},
}

# Emplacements secondaires (pièces que le vocabulaire ne détaille pas : poignées d'un chevet, terreau d'un
# pot, feux d'une voiture). « =x » reprend le matériau résolu de l'emplacement x.
SECONDAIRES: dict[str, dict[str, str]] = {
    "lit_simple": {"plaid": "laine:gris", "pieds": "=structure"},
    "lit_double": {"pieds": "=structure"},
    "table_de_chevet": {"poignees": "laiton", "pieds": "=structure"},
    "armoire": {"pieds": "=structure"},
    "commode": {"pieds": "=structure"},
    "meuble_tv": {"poignees": "metal_noir", "pieds": "=structure"},
    "bibliotheque": {"montants": "=structure"},
    "etagere_murale": {"montants": "=structure"},
    "console": {"pieds": "=structure", "poignees": "laiton"},
    "buffet": {"pieds": "=structure"},
    "chaise": {"pieds": "=structure"},
    "banc": {"pieds": "=structure", "coussin": "tissu:bordeaux"},
    "porte_manteau": {"pieds": "=structure"},
    "tapis": {"bordure": "laine"},
    "lampadaire": {"ampoule": "lumiere:blanc"},
    "suspension": {"ampoule": "lumiere:blanc"},
    "plante_en_pot": {"terreau": "terre", "tige": "ecorce"},
    "cheminee": {"buches": "ecorce"},
    "piano": {"pieds": "=structure", "pedales": "laiton"},
    "plan_de_travail": {"plaque": "ecran", "robinet": "metal_chrome"},
    "placard_haut": {},
    "ilot_cuisine": {"poignees": "metal_noir"},
    "hotte": {"filtre": "metal_noir"},
    "wc": {"bouton": "metal_chrome"},
    "poubelle_rue": {"sac": "plastique:anthracite"},
    "lave_vaisselle": {"poignees": "=caisse", "socle": "metal_noir", "bandeau": "ecran"},
    "lave_linge": {"joint": "caoutchouc"},
    "lavabo": {"poignees": "=robinet"},
    "abribus": {"affiche": "lumiere:blanc_casse", "banc": "=structure"},
    "feu_tricolore": {"feu_rouge": "lumiere:rouge", "feu_vert": "lumiere:#3daa55"},
    "voiture": {"feux_avant": "lumiere:blanc", "feux_arriere": "lumiere:rouge", "interieur": "caoutchouc"},
    "arbre": {"fruits": "plastique:rouge", "marques": "ecorce"},
    "fontaine": {},
}

# Teintes de reliures et de compositions (couleurs de la palette qu'on trouve sur des livres, des toiles).
TEINTES_RELIURES = ("bordeaux", "bleu_marine", "vert_foret", "creme", "ocre", "rouge_brique", "noir",
                    "bleu_canard", "beige", "jaune_moutarde", "gris", "terracotta", "blanc_casse", "taupe")
TEINTES_TOILE = ("terracotta", "bleu_nuit", "jaune_moutarde", "vert_sauge", "rose_poudre", "noir", "ocre",
                 "bleu_ciel", "blanc_casse")

# Catégories à emprise ronde ou carrée : une seule dimension au sol (la profondeur suit la largeur).
EMPRISE_RONDE = {"lampadaire", "lampe_de_table", "suspension", "plante_en_pot", "poubelle_rue", "fontaine",
                 "parasol", "arbre", "porte_manteau", "feu_tricolore"}

BUDGET_TRIANGLES = {"vehicule": 9000, "arbre": 15000}
BUDGET_DEFAUT = 6000


def categories_disponibles() -> list[str]:
    return sorted(voc.CATEGORIES)


def budget_triangles(categorie: str) -> int:
    if categorie == "arbre":
        return BUDGET_TRIANGLES["arbre"]
    return BUDGET_TRIANGLES.get(voc.CATEGORIES[categorie]["groupe"], BUDGET_DEFAUT)


# ── Outils géométriques locaux ─────────────────────────────────────────────────────────────────────
def _pave(x0: float, x1: float, y0: float, y1: float, z0: float, z1: float) -> trimesh.Trimesh:
    """Pavé donné par ses bornes (x0 < x1, y0 < y1, z0 < z1)."""
    return g.boite(abs(x1 - x0), abs(y1 - y0), abs(z1 - z0), x=(x0 + x1) / 2, y=min(y0, y1), z=(z0 + z1) / 2)


def _arrondi(x0: float, x1: float, y0: float, y1: float, z0: float, z1: float, r: float,
             sub: int = 1) -> trimesh.Trimesh:
    return g.boite_arrondie(abs(x1 - x0), abs(y1 - y0), abs(z1 - z0), r, x=(x0 + x1) / 2, y=min(y0, y1),
                            z=(z0 + z1) / 2, subdivisions=sub)


def _tourner(m: trimesh.Trimesh, axe: Sequence[float], angle: float,
             pivot: Sequence[float] = (0.0, 0.0, 0.0)) -> trimesh.Trimesh:
    return g.transformer(m, trimesh.transformations.rotation_matrix(angle, axe, pivot))


def _etirer(m: trimesh.Trimesh, sx: float, sy: float, sz: float,
            pivot: Sequence[float] = (0.0, 0.0, 0.0)) -> trimesh.Trimesh:
    """Mise à l'échelle non uniforme (facteurs > 0) ; les normales suivent la transposée inverse."""
    if m is None or not len(m.faces):
        return m
    s = np.array([sx, sy, sz], dtype=np.float64)
    p = np.asarray(pivot, dtype=np.float64)
    v = (np.asarray(m.vertices) - p) * s + p
    n = np.asarray(m.vertex_normals) / s
    n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
    sortie = trimesh.Trimesh(vertices=v, faces=np.asarray(m.faces), vertex_normals=n, process=False)
    uv = getattr(m.visual, "uv", None)
    sortie.visual = TextureVisuals(uv=np.zeros((len(v), 2)) if uv is None else np.asarray(uv))
    return sortie


def _aligner(m: trimesh.Trimesh, depart: Sequence[float], direction: Sequence[float]) -> trimesh.Trimesh:
    """Oriente une forme construite le long de +Y vers `direction`, sa base en `depart`."""
    d = np.asarray(direction, dtype=np.float64)
    d /= max(np.linalg.norm(d), 1e-12)
    matrice = trimesh.geometry.align_vectors([0.0, 1.0, 0.0], d)
    matrice[:3, 3] = depart
    return g.transformer(m, matrice)


def _cone_entre(p0: Sequence[float], p1: Sequence[float], r0: float, r1: float,
                sections: int = 12) -> trimesh.Trimesh:
    """Tronc de cône entre deux points 3D (pieds fuselés, troncs, branches effilées)."""
    a, b = np.asarray(p0, dtype=np.float64), np.asarray(p1, dtype=np.float64)
    longueur = float(np.linalg.norm(b - a))
    if longueur < 1e-6:
        return trimesh.Trimesh()
    return _aligner(g.tronc_de_cone(r0, r1, longueur, sections=sections), a, b - a)


def _coque(points: Sequence[Sequence[float]], rayon: float, sub: int = 1,
           lissage: float = 40.0) -> trimesh.Trimesh:
    """Enveloppe convexe de sphères placées aux coins donnés : volume arrondi de profil quelconque
    (carrosserie, habitacle, capot de hotte)."""
    sphere = trimesh.creation.icosphere(subdivisions=sub, radius=max(rayon, 1e-4))
    nuage = np.vstack([sphere.vertices + np.asarray(p, dtype=np.float64) for p in points])
    return g.finaliser(trimesh.convex.convex_hull(nuage), lissage_deg=lissage)


def _extruder(geometrie, hauteur: float, *, y: float = 0.0) -> trimesh.Trimesh:
    """`geometrie.extrusion` acceptant aussi un MultiPolygon (une extrusion par morceau)."""
    morceaux = list(getattr(geometrie, "geoms", [geometrie]))
    return g.fusionner(g.extrusion(p, hauteur, y=y) for p in morceaux if not p.is_empty and p.area > 1e-9)


def _panneau_xy(polygone: Polygon, z0: float, epaisseur: float) -> trimesh.Trimesh:
    """Panneau vertical : polygone dans le plan (x, y), épais de z0 à z0 + epaisseur (vers +Z)."""
    if polygone.is_empty or polygone.area <= 1e-9:
        return trimesh.Trimesh()
    m = trimesh.creation.extrude_polygon(polygone, max(epaisseur, 1e-4))
    m.apply_translation([0.0, 0.0, z0])
    return g.finaliser(m)


def _rect_arrondi(x0: float, y0: float, x1: float, y1: float, r: float) -> Polygon:
    r = max(0.0, min(r, (x1 - x0) / 2 - 1e-4, (y1 - y0) / 2 - 1e-4))
    base = rect_shapely(x0 + r, y0 + r, x1 - r, y1 - r)
    return base.buffer(r, resolution=4) if r > 0 else rect_shapely(x0, y0, x1, y1)


def _coquille(profil_ext: Sequence[tuple[float, float]], epaisseur: float, *, y: float = 0.0, x: float = 0.0,
              z: float = 0.0, sections: int = 32) -> trimesh.Trimesh:
    """Coquille de révolution (abat-jour, vasque, bassin) : profil extérieur (rayon, hauteur) de bas en
    haut, paroi d'épaisseur constante vers l'axe, bord refermé."""
    ext = [(max(r, 0.0), h) for r, h in profil_ext]
    inte = [(max(r - epaisseur, 0.0), h) for r, h in reversed(ext)]
    boucle = ext + inte + [ext[0]]
    return g.revolution(boucle, x=x, y=y, z=z, sections=sections)


def _bosseler(m: trimesh.Trimesh, amplitude: float, rng: np.random.Generator,
              lissage: float = 60.0) -> trimesh.Trimesh:
    """Bosselage radial (autour de l'axe vertical) par somme de sinus : feuillage de conifère, rocher."""
    v = np.asarray(m.vertices, dtype=np.float64).copy()
    centre = v.mean(axis=0)
    rel = v - centre
    echelle = max(np.ptp(v, axis=0).max(), 1e-6)
    defo = np.zeros(len(v))
    for _ in range(5):
        f = rng.normal(size=3) * 3.0 / echelle
        defo += np.sin(rel @ f + rng.uniform(0, 2 * math.pi))
    defo /= 5.0
    radial = rel.copy()
    radial[:, 1] = 0.0
    v += radial * (amplitude * defo)[:, None]
    brut = trimesh.Trimesh(vertices=v, faces=np.asarray(m.faces), process=True)
    return g.finaliser(brut, lissage_deg=lissage)


def _masse_feuillage(rx: float, ry: float, rz: float, centre: Sequence[float], rng: np.random.Generator, *,
                     sub: int = 2, bruit: float = 0.2) -> trimesh.Trimesh:
    """Masse de feuillage : ellipsoïde déformé par un bruit à trois octaves (grosses touffes, rameaux,
    bouquets de feuilles), pour que la silhouette se lise comme un feuillage et non comme une bulle."""
    base = trimesh.creation.icosphere(subdivisions=sub, radius=1.0)
    v = base.vertices.copy()
    d = np.zeros(len(v))
    for amp, freq in ((bruit, 2.0), (bruit * 0.5, 4.5), (bruit * 0.25, 9.0)):
        for _ in range(3):
            d += amp / 3.0 * np.sin(v @ (rng.normal(size=3) * freq) + rng.uniform(0, 2 * math.pi))
    v *= (1.0 + d)[:, None]
    v *= [rx, ry, rz]
    v += np.asarray(centre, dtype=np.float64)
    return g.finaliser(trimesh.Trimesh(vertices=v, faces=base.faces, process=False), lissage_deg=55.0)


def _directions_sphere(n: int, rng: np.random.Generator, haut_min: float = -0.3) -> np.ndarray:
    """n directions réparties (spirale de Fibonacci) sur la part de sphère y > haut_min, tournées au hasard."""
    k = np.arange(n) + 0.5
    y = 1.0 - (1.0 - haut_min) * k / n
    r = np.sqrt(np.maximum(0.0, 1.0 - y * y))
    phi = k * math.pi * (3.0 - math.sqrt(5.0)) + rng.uniform(0, 2 * math.pi)
    return np.column_stack([r * np.cos(phi), y, r * np.sin(phi)])


def _couronne(a: "_Atelier", emplacement: str, centre: Sequence[float], rx: float, ry: float, n: int, *,
              rz: float | None = None, bruit: float = 0.22, part_centrale: float = 0.7, sub_centre: int = 3,
              sub_peri: int = 2, haut_min: float = -0.3) -> list[np.ndarray]:
    """Couronne de feuillage : une masse centrale et n masses périphériques dont les bords touchent
    l'enveloppe (rx, ry, rx) ; rend les centres périphériques (points d'attache des branches)."""
    rz = rx if rz is None else rz
    c = np.asarray(centre, dtype=np.float64)
    masses = [_masse_feuillage(rx * part_centrale, ry * part_centrale, rz * part_centrale, c, a.rng,
                               sub=sub_centre, bruit=bruit)]
    centres = []
    for d in _directions_sphere(n, a.rng, haut_min=haut_min):
        rm = a.u(0.38, 0.5)
        rmx, rmy, rmz = rx * rm, ry * rm, rz * rm
        p = c + d * np.array([rx - rmx, ry - rmy, rz - rmz])
        masses.append(_masse_feuillage(rmx, rmy, rmz, p, a.rng, sub=sub_peri, bruit=bruit))
        centres.append(p)
    # la couronne remplit exactement son enveloppe (le reste de l'objet, pot ou tronc, n'est pas étiré)
    tous = np.vstack([m.vertices for m in masses])
    bas, haut = tous.min(axis=0), tous.max(axis=0)
    cible_bas = c - np.array([rx, ry, rz])
    f = 2.0 * np.array([rx, ry, rz]) / np.maximum(haut - bas, 1e-6)
    for m in masses:
        a(emplacement, g.translation(_etirer(g.translation(m, *(-bas)), *f), *cible_bas))
    return [cible_bas + (p - bas) * f for p in centres]


def _anneau_vertical(r_ext: float, r_int: float, epaisseur: float, *, x: float, y: float, z0: float,
                     sections: int = 32) -> trimesh.Trimesh:
    """Anneau face à +Z (hublot, jante, feu) : couronne dans le plan (x, y), épaisse vers +Z depuis z0."""
    couronne = Point(x, y).buffer(r_ext, resolution=max(4, sections // 4))
    if r_int > 0:
        couronne = couronne.difference(Point(x, y).buffer(r_int, resolution=max(4, sections // 4)))
    return _panneau_xy(couronne, z0, epaisseur)


def _disque_vertical(r: float, epaisseur: float, *, x: float, y: float, z0: float,
                     sections: int = 24) -> trimesh.Trimesh:
    return _panneau_xy(Point(x, y).buffer(r, resolution=max(4, sections // 4)), z0, epaisseur)


# ── Atelier : collecte des pièces par emplacement ──────────────────────────────────────────────────
@dataclass
class _Atelier:
    categorie: str
    L: float                     # largeur visée (x)
    P: float                     # profondeur visée (z)
    H: float                     # hauteur visée (y)
    style: str
    mats: dict[str, str]
    rng: np.random.Generator
    pieces: list[tuple[str, str, trimesh.Trimesh]] = field(default_factory=list)
    hauteur_surface: float | None = None      # dessus utilisable (par défaut le haut de l'objet)

    @property
    def sty(self) -> dict[str, Any]:
        return STYLES_MEUBLES.get(self.style, STYLES_MEUBLES["moderne"])

    def __call__(self, emplacement: str, *maillages: trimesh.Trimesh, materiau: str | None = None) -> None:
        cle = materiau or self.mats[emplacement]
        for m in maillages:
            if m is not None and len(m.faces):
                self.pieces.append((emplacement, cle, m))

    def u(self, a: float = 0.0, b: float = 1.0) -> float:
        return float(self.rng.uniform(a, b))

    def teintes(self, emplacement: str, n: int, palette: Sequence[str]) -> list[str]:
        """Matériau coloriable sans teinte imposée → une teinte de `palette` par élément ; sinon le même."""
        cle = self.mats[emplacement]
        base, _, teinte = cle.partition(":")
        if teinte or not voc.MATERIAUX[base]["coloriable"]:
            return [cle] * n
        return [f"{base}:{palette[int(i)]}" for i in self.rng.integers(0, len(palette), size=n)]

    def teintes_libres(self, emplacement: str, n: int, palette: Sequence[str]) -> list[str]:
        """Teintes de `palette` sur la base de l'emplacement, même s'il porte déjà une teinte (la peinture
        d'une toile n'a pas la couleur de la toile)."""
        base = self.mats[emplacement].partition(":")[0]
        if not voc.MATERIAUX[base]["coloriable"]:
            return [self.mats[emplacement]] * n
        return [f"{base}:{palette[int(i)]}" for i in self.rng.integers(0, len(palette), size=n)]


# ── Éléments réutilisés (pieds, poignées, façades) ─────────────────────────────────────────────────
def _pied(a: _Atelier, x: float, z: float, h: float, emplacement: str, r: float = 0.02,
          y0: float = 0.0, forme: str | None = None) -> trimesh.Trimesh:
    """Pied posé au sol en (x, z), de hauteur h, selon la forme du style :
    fin (fuseau mince), tourne (balustre au tour), fuseau (fuselé et évasé vers l'extérieur), tube (carré)."""
    forme = forme or a.sty["pied"]
    if forme == "tourne":
        profil = [(0.0, 0.0), (0.75 * r, 0.0), (0.6 * r, 0.06 * h), (0.75 * r, 0.12 * h), (1.15 * r, 0.32 * h),
                  (0.7 * r, 0.52 * h), (0.6 * r, 0.62 * h), (0.95 * r, 0.75 * h), (1.1 * r, 0.82 * h),
                  (1.1 * r, h), (0.0, h)]
        return g.revolution(profil, x=x, y=y0, z=z, sections=12)
    if forme == "fuseau":
        evase = 0.12 * h
        sx = -math.copysign(1.0, x) if abs(x) > 1e-6 else 0.0
        sz = -math.copysign(1.0, z) if abs(z) > 1e-6 else 0.0
        n = math.hypot(sx, sz) or 1.0
        return _cone_entre((x, y0, z), (x + sx / n * evase, y0 + h, z + sz / n * evase), 0.6 * r, 1.05 * r)
    if forme == "tube":
        c = 1.2 * r
        return _pave(x - c, x + c, y0, y0 + h, z - c, z + c)
    return g.tronc_de_cone(0.55 * r, 0.8 * r, h, x=x, y=y0, z=z, sections=12)


def _poignee(a: _Atelier, emplacement: str, x: float, y: float, zf: float, *, verticale: bool,
             longueur: float = 0.14, saillie: float = 0.028) -> None:
    """Poignée posée sur une façade dont la face avant est à zf ; elle dépasse de `saillie` vers +Z."""
    if a.sty["poignee"] == "bouton":
        r = min(0.013, saillie * 0.45)
        a(emplacement, _cone_entre((x, y, zf), (x, y, zf + saillie - r), 0.35 * r, 0.6 * r, sections=10),
          g.sphere(r, x=x, y=y, z=zf + saillie - r, subdivisions=1))
        return
    epaisse = a.style == "industriel"
    rb = 0.007 if epaisse else 0.0055
    zb = zf + saillie - rb
    d = longueur / 2.0
    p0, p1 = ((x, y - d, zb), (x, y + d, zb)) if verticale else ((x - d, y, zb), (x + d, y, zb))
    a(emplacement, g.segment(p0, p1, rb, sections=10))
    for p in (p0, p1):
        a(emplacement, g.segment((p[0], p[1], zf), (p[0], p[1], zb), rb * 0.8, sections=8))


def _facade(a: _Atelier, emp_facade: str, emp_poignee: str | None, x0: float, x1: float, y0: float, y1: float,
            zf: float, ef: float = 0.019, *, poignee: str = "centre", jeu: float = 0.003,
            saillie: float = 0.028) -> None:
    """Façade de porte ou de tiroir (panneau à joints de `jeu`), dos à zf, épaisse de ef vers +Z.
    Moulures (style classique) : panneau central en relief. `poignee` : centre (tiroir), gauche, droite
    (porte, poignée verticale du côté de l'ouverture), haut, bas (placards hauts), aucune."""
    x0j, x1j, y0j, y1j = x0 + jeu, x1 - jeu, y0 + jeu, y1 - jeu
    a(emp_facade, _pave(x0j, x1j, y0j, y1j, zf, zf + ef))
    zface = zf + ef
    if a.sty["moulures"] and (x1j - x0j) > 0.16 and (y1j - y0j) > 0.12:
        m = min(0.06, 0.18 * (x1j - x0j), 0.18 * (y1j - y0j))
        a(emp_facade, _pave(x0j + m, x1j - m, y0j + m, y1j - m, zface, zface + 0.008))
        zface += 0.008
    if emp_poignee is None or poignee == "aucune":
        return
    largeur, hauteur = x1j - x0j, y1j - y0j
    s = max(0.012, saillie - (zface - zf - ef))
    if poignee == "centre":
        _poignee(a, emp_poignee, (x0j + x1j) / 2, (y0j + y1j) / 2 + (0.0 if hauteur < 0.3 else hauteur * 0.3),
                 zface, verticale=False, longueur=min(0.32, 0.45 * largeur), saillie=s)
    elif poignee in ("gauche", "droite"):
        xp = x0j + 0.045 if poignee == "gauche" else x1j - 0.045
        yp = min(y1j - 0.12, y0j + max(0.2, min(1.05, 0.55 * hauteur)))
        _poignee(a, emp_poignee, xp, yp, zface, verticale=True, longueur=min(0.3, 0.35 * hauteur), saillie=s)
    elif poignee in ("haut", "bas"):
        yp = y1j - 0.05 if poignee == "haut" else y0j + 0.05
        _poignee(a, emp_poignee, (x0j + x1j) / 2, yp, zface, verticale=False, longueur=min(0.2, 0.5 * largeur),
                 saillie=s)


def _pietement(a: _Atelier, emplacement: str, x: float, z: float, h: float, r: float = 0.022) -> None:
    """Quatre pieds aux coins (±x, ±z) ; le pied tube du style industriel devient un cadre soudé."""
    for sx in (-1, 1):
        for sz in (-1, 1):
            a(emplacement, _pied(a, sx * x, sz * z, h, emplacement, r))
    if a.sty["pied"] == "tube" and h > 0.08:
        c = 1.2 * r
        for sz in (-1, 1):
            a(emplacement, _pave(-x - c, x + c, h - 2 * c, h, sz * z - c, sz * z + c))
        for sx in (-1, 1):
            a(emplacement, _pave(sx * x - c, sx * x + c, h - 2 * c, h, -z - c, z + c))


def _soubassement(a: _Atelier, emp_pieds: str, x0: float, x1: float, z0: float, z1: float) -> float:
    """Sous un meuble de rangement : socle en retrait (moderne), pieds (autres styles). Rend sa hauteur."""
    if a.sty["socle"]:
        h = 0.07
        a(emp_pieds, _pave(x0 + 0.03, x1 - 0.03, 0.0, h, z0 + 0.01, z1 - 0.04))
        return h
    h = a.sty["haut_pied"] * (0.9 if a.H > 1.2 else 0.75)
    if a.style == "classique":
        h = 0.09
    r = 0.022 if a.style != "industriel" else 0.016
    xi, zi = (x1 - x0) / 2 - 0.05, (z1 - z0) / 2 - 0.05
    cx, cz = (x0 + x1) / 2, (z0 + z1) / 2
    for sx in (-1, 1):
        for sz in (-1, 1):
            a(emp_pieds, _pied(a, cx + sx * xi, cz + sz * zi, h, emp_pieds, r))
    return h


def _corps_rangement(a: _Atelier, emp: str, emp_pieds: str, *, saillie: float = 0.028,
                     ef: float = 0.019) -> tuple[float, float, float, float, float]:
    """Caisson plein posé sur son soubassement, avec dessus débordant (moulure en style classique).
    Rend (y_bas, y_haut des façades, zf dos des façades, x0, x1 intérieurs)."""
    L, P, H = a.L, a.P, a.H
    zb, zf = -P / 2, P / 2 - saillie - ef
    hb = _soubassement(a, emp_pieds, -L / 2, L / 2, zb, zf)
    dessus = 0.025 if not a.sty["moulures"] else 0.035
    retrait = 0.0 if not a.sty["moulures"] else 0.012
    a(emp, _pave(-L / 2 + retrait, L / 2 - retrait, hb, H - dessus, zb, zf))
    r = min(a.sty["arrondi"] * 0.25, dessus * 0.45)
    a(emp, _arrondi(-L / 2, L / 2, H - dessus, H, zb, zf + ef + min(0.012, saillie * 0.4), max(r, 0.002)))
    return hb, H - dessus, zf, -L / 2 + retrait, L / 2 - retrait


# ── Couchage ───────────────────────────────────────────────────────────────────────────────────────
def _b_lit(a: _Atelier) -> None:
    L, P, H = a.L, a.P, a.H
    st = a.sty
    e_tete = 0.06 if a.style != "industriel" else 0.04
    zt = -P / 2 + e_tete
    y_sommier = 0.32 if a.style != "moderne" else 0.26
    h_cadre = 0.16
    # cadre (structure) : plinthe pleine en moderne, sur pieds ailleurs
    if st["socle"]:
        a("structure", _pave(-L / 2 + 0.06, L / 2 - 0.06, 0.0, y_sommier - h_cadre, zt + 0.06, P / 2 - 0.08))
    else:
        hp = y_sommier - h_cadre
        for sz in (zt + 0.06, P / 2 - 0.05):
            for sx in (-1, 1):
                a("pieds", _pied(a, sx * (L / 2 - 0.05), sz, hp, "pieds", 0.028))
    a("structure", _arrondi(-L / 2, L / 2, y_sommier - h_cadre, y_sommier, zt, P / 2, max(0.004, st["arrondi"] * 0.3)))
    # matelas, couette au rebord replié, oreillers
    y_mat = y_sommier + 0.2
    a("literie", _arrondi(-L / 2 + 0.03, L / 2 - 0.03, y_sommier, y_mat, zt + 0.01, P / 2 - 0.03, 0.05, sub=2))
    z_pli = zt + min(0.62, 0.3 * P)
    a("literie", _arrondi(-L / 2 + 0.012, L / 2 - 0.012, y_sommier + 0.05, y_mat + 0.045, z_pli, P / 2 - 0.012,
                          0.045, sub=2))
    a("literie", _arrondi(-L / 2 + 0.01, L / 2 - 0.01, y_mat - 0.02, y_mat + 0.075, z_pli - 0.2, z_pli + 0.05,
                          0.04, sub=2))
    n_or = 2 if L >= 1.25 else 1
    l_or = min(0.66, (L - 0.12) / n_or - 0.05)
    for i in range(n_or):
        cx = -L / 2 + 0.06 + (i + 0.5) * (L - 0.12) / n_or
        oreiller = _arrondi(cx - l_or / 2, cx + l_or / 2, y_mat, y_mat + 0.14, zt + 0.04, zt + 0.42, 0.06, sub=2)
        a("literie", _tourner(oreiller, [1, 0, 0], -0.22, (cx, y_mat, zt + 0.42)))
    # plaid replié au pied du lit
    a("plaid", _arrondi(-L / 2 + 0.004, L / 2 - 0.004, y_sommier + 0.04, y_mat + 0.06, P / 2 - 0.5,
                        P / 2 - 0.004, 0.02))
    # tête de lit selon le style
    zb = -P / 2
    if a.style == "classique":
        r_m = 0.035
        for sx in (-1, 1):
            x = sx * (L / 2 - r_m)
            a("structure", g.cylindre(r_m, H - 0.05, x=x, z=zb + e_tete / 2, sections=16),
              g.sphere(r_m * 1.25, x=x, y=H - r_m * 1.25, z=zb + e_tete / 2, subdivisions=1))
        a("structure", _arrondi(-L / 2 + 2 * r_m, L / 2 - 2 * r_m, y_sommier, H - 0.12, zb + 0.008, zb + e_tete - 0.008,
                                0.02))
        a("structure", _arrondi(-L / 2 + 2 * r_m, L / 2 - 2 * r_m, H - 0.16, H - 0.07, zb, zb + e_tete, 0.02))
    elif a.style == "industriel":
        r_t = 0.018
        for sx in (-1, 1):
            a("pieds", g.segment((sx * (L / 2 - r_t), 0.0, zb + r_t), (sx * (L / 2 - r_t), H - r_t, zb + r_t), r_t))
        a("pieds", g.segment((-L / 2 + r_t, H - r_t, zb + r_t), (L / 2 - r_t, H - r_t, zb + r_t), r_t))
        n_b = max(4, int(L / 0.16))
        for i in range(1, n_b):
            x = -L / 2 + i * L / n_b
            a("pieds", g.segment((x, y_sommier, zb + r_t), (x, H - r_t, zb + r_t), 0.008, sections=8))
    elif a.style == "scandinave":
        a("structure", _arrondi(-L / 2, L / 2, y_sommier - h_cadre, H, zb, zb + e_tete, min(0.18, L * 0.1), sub=2))
    else:
        a("structure", _arrondi(-L / 2, L / 2, 0.0, H, zb, zb + e_tete, 0.03, sub=2))
        a("structure", _arrondi(-L / 2 + 0.04, L / 2 - 0.04, y_mat - 0.05, H - 0.05, zb + e_tete - 0.01,
                                zb + e_tete + 0.02, 0.03))


def _b_table_de_chevet(a: _Atelier) -> None:
    hb, yh, zf, x0, x1 = _corps_rangement(a, "structure", "pieds")
    n = 2 if (yh - hb) > 0.3 else 1
    hauteur_t = (yh - hb) / n
    for i in range(n):
        _facade(a, "structure", "poignees", x0, x1, hb + i * hauteur_t, hb + (i + 1) * hauteur_t, zf)


def _b_armoire(a: _Atelier) -> None:
    L, P, H = a.L, a.P, a.H
    saillie, ef = 0.03, 0.02
    zb, zf = -P / 2, P / 2 - saillie - ef
    hb = _soubassement(a, "pieds", -L / 2, L / 2, zb, zf)
    corniche = 0.07 if a.sty["moulures"] else 0.0
    retrait = 0.02 if a.sty["moulures"] else 0.0
    yh = H - corniche
    a("structure", _pave(-L / 2 + retrait, L / 2 - retrait, hb, yh, zb, zf))
    if corniche:
        a("structure", _pave(-L / 2 + 0.005, L / 2 - 0.005, yh, yh + 0.025, zb, zf + ef + 0.008),
          _pave(-L / 2, L / 2, yh + 0.025, H, zb, zf + ef + 0.016))
    x0, x1 = -L / 2 + retrait, L / 2 - retrait
    # tiroirs bas sur les grandes armoires, portes au-dessus
    y_portes = hb
    if L >= 1.2 and a.u() < 0.6:
        y_portes = hb + 0.24
        for i in range(2):
            xa = x0 + i * (x1 - x0) / 2
            _facade(a, "structure", "poignees", xa, xa + (x1 - x0) / 2, hb, y_portes, zf, ef)
    n = int(np.clip(round((x1 - x0) / 0.5), 2, 4))
    lp = (x1 - x0) / n
    for i in range(n):
        cote = "droite" if i % 2 == 0 else "gauche"
        if n % 2 == 1 and i == n - 1:
            cote = "gauche"
        _facade(a, "structure", "poignees", x0 + i * lp, x0 + (i + 1) * lp, y_portes, yh, zf, ef, poignee=cote)


def _b_commode(a: _Atelier) -> None:
    hb, yh, zf, x0, x1 = _corps_rangement(a, "structure", "pieds")
    n = int(np.clip(round((yh - hb) / 0.2), 3, 5))
    ht = (yh - hb) / n
    for i in range(n):
        y0 = yh - (i + 1) * ht
        if i == 0 and (x1 - x0) > 0.95:
            for j in range(2):
                xa = x0 + j * (x1 - x0) / 2
                _facade(a, "structure", "poignees", xa, xa + (x1 - x0) / 2, y0, y0 + ht, zf)
        else:
            _facade(a, "structure", "poignees", x0, x1, y0, y0 + ht, zf)


# ── Séjour ─────────────────────────────────────────────────────────────────────────────────────────
def _b_assise_rembourree(a: _Atelier, places: int) -> None:
    """Canapé ou fauteuil : socle, accoudoirs, coussins d'assise et de dossier inclinés, pieds."""
    L, P, H = a.L, a.P, a.H
    st = a.sty
    r = st["arrondi"]
    hp = {"moderne": 0.1, "classique": 0.09, "scandinave": 0.16, "industriel": 0.12}[a.style]
    bras = float(np.clip({"moderne": 0.11, "classique": 0.17, "scandinave": 0.13, "industriel": 0.16}[a.style]
                         * (1.0 if places > 1 else 0.85), 0.08, 0.3 * L))
    h_bras = hp + 0.47 * (H - hp) + 0.1
    e_dos = 0.2
    zb = -P / 2
    y_assise_bas = hp + 0.14
    y_assise = 0.44 if hp < 0.15 else 0.45
    # socle et dossier (structure)
    a("structure", _arrondi(-L / 2 + bras - 0.01, L / 2 - bras + 0.01, hp, y_assise_bas, zb + 0.02, P / 2 - 0.02,
                            min(0.02, r)))
    y_dos = hp + 0.72 * (H - hp)
    a("structure", _arrondi(-L / 2 + bras - 0.01, L / 2 - bras + 0.01, hp, y_dos, zb, zb + e_dos, min(0.04, r), sub=2))
    # accoudoirs
    for sx in (-1, 1):
        xa0, xa1 = (L / 2 - bras, L / 2) if sx > 0 else (-L / 2, -L / 2 + bras)
        if a.style == "classique":
            a("structure", _arrondi(xa0 + 0.015 * sx, xa1 - 0.015 * sx if sx < 0 else xa1 - 0.015, hp, h_bras - 0.06,
                                    zb, P / 2 - 0.01, 0.03, sub=2))
            rr = bras * 0.55
            xc = (xa0 + xa1) / 2 + sx * 0.012
            rouleau = g.cylindre(rr, P - 0.02, sections=20)
            rouleau = _tourner(rouleau, [1, 0, 0], math.pi / 2)
            a("structure", g.translation(rouleau, xc, h_bras - rr, zb + 0.01))
        else:
            a("structure", _arrondi(xa0, xa1, hp, h_bras, zb, P / 2, max(0.008, r), sub=2))
    # coussins d'assise
    xi0, xi1 = -L / 2 + bras, L / 2 - bras
    lc = (xi1 - xi0) / places
    for i in range(places):
        cx0 = xi0 + i * lc
        a("structure", _arrondi(cx0 + 0.004, cx0 + lc - 0.004, y_assise_bas, y_assise, zb + e_dos - 0.01,
                                P / 2 - 0.005, max(0.02, r), sub=2))
    # coussins de dossier, inclinés vers l'arrière
    e_c = 0.17
    for i in range(places):
        cx0 = xi0 + i * lc
        h_c = H - y_assise - 0.02
        coussin = _arrondi(cx0 + 0.006, cx0 + lc - 0.006, y_assise, y_assise + h_c, zb + e_dos - 0.01,
                           zb + e_dos - 0.01 + e_c, max(0.03, r * 1.2), sub=2)
        a("structure", _tourner(coussin, [1, 0, 0], -0.16, (0.0, y_assise, zb + e_dos - 0.01 + e_c)))
    # pieds
    n_x = 3 if L > 2.2 else 2
    xs = np.linspace(-L / 2 + 0.07, L / 2 - 0.07, n_x)
    for x in xs:
        for z in (zb + 0.07, P / 2 - 0.07):
            a("pieds", _pied(a, float(x), z, hp, "pieds", 0.022))


def _b_canape(a: _Atelier) -> None:
    _b_assise_rembourree(a, 3 if a.L >= 1.95 else 2)


def _b_fauteuil(a: _Atelier) -> None:
    _b_assise_rembourree(a, 1)


def _plateau_sur_pieds(a: _Atelier, emp_plateau: str, emp_pieds: str, *, epaisseur: float,
                       retrait: float, ceinture: bool = True, tablette: bool = False) -> None:
    """Table : plateau (chants arrondis selon le style), ceinture, pieds selon le style."""
    L, P, H = a.L, a.P, a.H
    r = a.sty["arrondi"]
    if a.style == "scandinave":
        a(emp_plateau, _arrondi(-L / 2, L / 2, H - epaisseur, H, -P / 2, P / 2, min(r, epaisseur * 0.48), sub=2))
    else:
        a(emp_plateau, _arrondi(-L / 2, L / 2, H - epaisseur, H, -P / 2, P / 2, max(0.003, min(0.012, epaisseur * 0.3))))
    hp = H - epaisseur
    xi, zi = L / 2 - retrait, P / 2 - retrait
    if a.style == "industriel":
        c = 0.02
        for sx in (-1, 1):
            x = sx * xi
            a(emp_pieds, _pave(x - c, x + c, 0, hp, -zi - c, -zi + c), _pave(x - c, x + c, 0, hp, zi - c, zi + c),
              _pave(x - c, x + c, hp - 0.04, hp, -zi, zi), _pave(x - c, x + c, 0.0, 0.04, -zi, zi))
        a(emp_pieds, _pave(-xi, xi, hp - 0.04, hp, -c, c))
    else:
        for sx in (-1, 1):
            for sz in (-1, 1):
                a(emp_pieds, _pied(a, sx * xi, sz * zi, hp, emp_pieds, 0.026 if a.style != "moderne" else 0.02))
    if ceinture and a.style in ("classique", "scandinave"):
        hc = 0.08 if a.style == "classique" else 0.05
        e = 0.02
        a(emp_plateau, _pave(-xi, xi, hp - hc, hp, -zi - e / 2, -zi + e / 2),
          _pave(-xi, xi, hp - hc, hp, zi - e / 2, zi + e / 2),
          _pave(-xi - e / 2, -xi + e / 2, hp - hc, hp, -zi, zi), _pave(xi - e / 2, xi + e / 2, hp - hc, hp, -zi, zi))
    if tablette:
        yt = min(0.12, hp * 0.35)
        a(emp_plateau, _pave(-xi + 0.02, xi - 0.02, yt, yt + 0.018, -zi + 0.02, zi - 0.02))


def _b_table_basse(a: _Atelier) -> None:
    _plateau_sur_pieds(a, "plateau", "pieds", epaisseur=0.035, retrait=0.06, ceinture=a.style == "classique",
                       tablette=a.style in ("moderne", "industriel"))


def _b_table_a_manger(a: _Atelier) -> None:
    _plateau_sur_pieds(a, "plateau", "pieds", epaisseur=0.035 if a.style != "industriel" else 0.045, retrait=0.07)


def _b_bureau(a: _Atelier) -> None:
    L, P, H = a.L, a.P, a.H
    _plateau_sur_pieds(a, "plateau", "pieds", epaisseur=0.03, retrait=0.05, ceinture=False)
    if a.style in ("classique", "scandinave"):
        # caisson à tiroirs suspendu sous le plateau, côté droit
        lc = min(0.42, 0.33 * L)
        x1 = L / 2 - 0.09
        y1, y0 = H - 0.03, H - 0.03 - (0.36 if a.style == "classique" else 0.14)
        a("plateau", _pave(x1 - lc, x1, y0, y1, -P / 2 + 0.06, P / 2 - 0.06))
        n = 2 if a.style == "classique" else 1
        for i in range(n):
            yy = y0 + i * (y1 - y0) / n
            _facade(a, "plateau", "pieds", x1 - lc, x1, yy, yy + (y1 - y0) / n, P / 2 - 0.06, 0.018, saillie=0.025)


def _b_console(a: _Atelier) -> None:
    L, P, H = a.L, a.P, a.H
    _plateau_sur_pieds(a, "structure", "pieds", epaisseur=0.03, retrait=0.035, ceinture=False, tablette=True)
    yc = H - 0.03
    _facade(a, "structure", None, -L / 2 + 0.06, L / 2 - 0.06, yc - 0.11, yc, -P / 2 + 0.05, P - 0.1 - 0.025,
            jeu=0.0)
    _facade(a, "structure", "poignees", -L / 2 + 0.07, L / 2 - 0.07, yc - 0.105, yc - 0.005, P / 2 - 0.05, 0.02,
            saillie=0.025)


def _b_meuble_tv(a: _Atelier) -> None:
    hb, yh, zf, x0, x1 = _corps_rangement(a, "structure", "pieds")
    n = int(np.clip(round((x1 - x0) / 0.45), 2, 4))
    lp = (x1 - x0) / n
    niche = int(a.rng.integers(0, n))
    for i in range(n):
        xa, xb = x0 + i * lp, x0 + (i + 1) * lp
        if i == niche:
            # niche ouverte (box, console de jeu) : pas de façade, fond en retrait
            continue
        _facade(a, "structure", "poignees", xa, xb, hb, yh, zf, poignee="centre")


def _b_television(a: _Atelier) -> None:
    L, P, H = a.L, a.P, a.H
    e = min(0.045, P * 0.5)
    h_pied = min(0.09, 0.12 * H)
    yp0 = h_pied
    # pied : plaque au sol et colonne
    lp = min(0.4, 0.38 * L)
    a("cadre", _arrondi(-lp / 2, lp / 2, 0.0, 0.012, -P / 2, P / 2, 0.005))
    a("cadre", _pave(-0.035, 0.035, 0.012, yp0 + 0.08, -0.015 - e / 2, 0.015 - e / 2))
    # dalle et écran, face vers +Z
    zc = -e / 2
    a("cadre", _arrondi(-L / 2, L / 2, yp0, H, zc - e / 2, zc + e / 2 - 0.002, 0.004))
    bord = 0.012
    a("ecran", _pave(-L / 2 + bord, L / 2 - bord, yp0 + bord + 0.012, H - bord, zc + e / 2 - 0.004, zc + e / 2))


def _livres(a: _Atelier, x0: float, x1: float, y0: float, h_libre: float, z_dos: float, prof_max: float) -> None:
    """Rangée de livres entre x0 et x1 sur une tablette à y0 : épaisseurs, hauteurs et reliures variées,
    trous, piles couchées et dernier livre penché."""
    x = x0 + a.u(0.0, 0.06)
    items: list[tuple[float, float, float, float]] = []
    while x < x1 - 0.03:
        if a.u() < 0.08 and x1 - x > 0.2:      # pile couchée (tient dans la place restante)
            hp = min(a.u(0.15, min(0.28, h_libre - 0.02)), x1 - x - 0.005)
            n = int(a.rng.integers(2, 6))
            ep = 0.0
            for _ in range(n):
                e = a.u(0.02, 0.04)
                items.append((x, x + hp, y0 + ep, e))
                ep += e
            x += hp + a.u(0.01, 0.04)
            continue
        if a.u() < 0.07:                       # trou
            x += a.u(0.05, 0.16)
            continue
        e = a.u(0.018, 0.05)
        if x + e > x1:
            break
        items.append((x, x + e, y0, -a.u(0.62, 0.95) * h_libre))
        x += e + (0.0 if a.u() < 0.8 else a.u(0.002, 0.01))
    teintes = a.teintes("livres", len(items), TEINTES_RELIURES)
    for (xa, xb, yb, code), mat in zip(items, teintes):
        prof = a.u(0.65, 1.0) * prof_max
        if code > 0:                           # couché : code = épaisseur
            m = _pave(xa, xb, yb, yb + code * 0.98, z_dos, z_dos + prof)
        else:
            m = _pave(xa, xb, yb, yb - code, z_dos, z_dos + prof)
        a("livres", m, materiau=mat)


def _b_bibliotheque(a: _Atelier) -> None:
    L, P, H = a.L, a.P, a.H
    e = 0.022
    zb, zf = -P / 2, P / 2
    socle = 0.07 if a.style != "industriel" else 0.02
    n = int(np.clip(round((H - socle) / 0.36), 4, 7))
    if a.style == "industriel":
        c = 0.018
        for sx in (-1, 1):
            for sz in (-1, 1):
                a("montants", _pave(sx * (L / 2 - c) - c, sx * (L / 2 - c) + c, 0.0, H, sz * (P / 2 - c) - c,
                                    sz * (P / 2 - c) + c))
        xi0, xi1 = -L / 2 + 2 * c, L / 2 - 2 * c
        for sx in (-1, 1):
            a("montants", g.segment((sx * (L / 2 - c), 0.1, zb + c), (sx * (L / 2 - c), H - 0.1, zb + c), 0.006))
    else:
        for sx in (-1, 1):
            a("structure", _pave(sx * L / 2 - e if sx > 0 else -L / 2, L / 2 if sx > 0 else -L / 2 + e, 0.0, H, zb, zf))
        a("structure", _pave(-L / 2 + e, L / 2 - e, 0.0, socle, zb, zf - 0.02))
        a("structure", _pave(-L / 2 + e, L / 2 - e, 0.01, H - 0.01, zb, zb + 0.008))
        xi0, xi1 = -L / 2 + e, L / 2 - e
        if a.sty["moulures"]:
            a("structure", _pave(-L / 2, L / 2, H - 0.05, H, zb, zf))
    y_haut = H - (0.05 if a.sty["moulures"] else 0.0)
    pas = (y_haut - socle) / n
    for i in range(n + 1):
        y = socle + i * pas
        ep = e if i not in (0, n) else (e if a.style == "industriel" else (0.0 if i == 0 else e))
        if ep <= 0:
            continue
        yy = min(y, H - e) if i == n else y - e / 2
        a("structure", _pave(xi0, xi1, max(0.0, yy), max(0.0, yy) + e, zb + 0.008, zf - (0.005 if i else 0.0)))
    for i in range(n):
        y0 = socle + i * pas + e / 2
        h_libre = pas - e
        _livres(a, xi0 + 0.005, xi1 - 0.005, y0 + (e / 2 if i == 0 else 0.0), h_libre - 0.01, zb + 0.012,
                min(0.25, P - 0.05))


def _b_etagere_murale(a: _Atelier) -> None:
    L, P, H = a.L, a.P, a.H
    e = 0.022
    a("structure", _pave(-L / 2, L / 2, 0.0, e, -P / 2, P / 2), _pave(-L / 2, L / 2, H - e, H, -P / 2, P / 2))
    for sx in (-1, 1):
        a("montants", _pave(sx * L / 2 - e if sx > 0 else -L / 2, L / 2 if sx > 0 else -L / 2 + e, e, H - e,
                            -P / 2, P / 2))
    _livres(a, -L / 2 + e + 0.004, L / 2 - e - 0.004, e, H - 2 * e - 0.008, -P / 2 + 0.005, min(0.2, P - 0.02))


def _b_tapis(a: _Atelier) -> None:
    L, P, H = a.L, a.P, a.H
    frange = 0.04 if a.u() < 0.6 else 0.0
    poly = _rect_arrondi(-L / 2, -P / 2 + frange, L / 2, P / 2 - frange, 0.03)
    a("surface", g.extrusion(poly, H * 0.8))
    # bordure tissée d'une teinte contrastée (tirée dans la palette si l'emplacement n'en impose pas)
    m = min(0.18, 0.08 * min(L, P))
    bord = poly.difference(poly.buffer(-m)).union(poly.buffer(-2.2 * m).difference(poly.buffer(-2.6 * m)))
    a("bordure", _extruder(bord, H), materiau=a.teintes("bordure", 1, TEINTES_TOILE)[0])
    if frange:
        n = int(L / 0.025)
        for sz in (-1, 1):
            for i in range(n):
                x = -L / 2 + 0.02 + i * (L - 0.04) / max(n - 1, 1)
                z0 = sz * (P / 2 - frange)
                a("surface", _pave(x - 0.004, x + 0.004, 0.0, H * 0.4, min(z0, sz * P / 2), max(z0, sz * P / 2)))


def _profil_abat_jour(a: _Atelier, r_bas: float, h: float) -> list[tuple[float, float]]:
    forme = {"moderne": "cylindre", "classique": "cone", "scandinave": "cloche", "industriel": "cone"}[a.style]
    if forme == "cylindre":
        return [(r_bas, 0.0), (r_bas, h)]
    if forme == "cloche":
        return [(r_bas, 0.0), (r_bas * 0.92, 0.25 * h), (r_bas * 0.7, 0.7 * h), (r_bas * 0.45, h)]
    return [(r_bas, 0.0), (r_bas * 0.62, h)]


def _b_lampadaire(a: _Atelier) -> None:
    L, P, H = a.L, a.P, a.H
    R = min(L, P) / 2
    h_aj = min(0.36, 0.22 * H)
    y_aj = H - h_aj
    if a.style == "scandinave":                 # trépied
        for k in range(3):
            ang = k * 2 * math.pi / 3 + math.pi / 6
            a("structure", _cone_entre((R * 0.92 * math.sin(ang), 0.0, R * 0.92 * math.cos(ang)),
                                       (0.0, y_aj * 0.62, 0.0), 0.011, 0.015))
        a("structure", g.cylindre(0.012, y_aj - y_aj * 0.62, y=y_aj * 0.62, sections=12))
    else:
        if a.style == "classique":
            a("structure", g.revolution([(0, 0), (R * 0.75, 0), (R * 0.72, 0.03), (R * 0.3, 0.07), (0.03, 0.12),
                                         (0.0, 0.12)], sections=24))
            a("structure", g.revolution([(0, 0.12), (0.016, 0.12), (0.012, 0.4 * y_aj), (0.022, 0.45 * y_aj),
                                         (0.012, 0.5 * y_aj), (0.01, y_aj), (0, y_aj)], sections=12))
        else:
            a("structure", g.cylindre(min(0.15, R * 0.8), 0.022, sections=28))
            a("structure", g.cylindre(0.011, y_aj, y=0.02, sections=12))
    r_aj = R
    a("abat_jour", _coquille(_profil_abat_jour(a, r_aj, h_aj), 0.004, y=y_aj, sections=32))
    a("ampoule", g.sphere(0.04, y=y_aj + 0.06, subdivisions=1))
    a("structure", g.segment((0.0, y_aj + 0.02, 0.0), (0.0, y_aj + 0.1, 0.0), 0.008, sections=8))


def _b_lampe_de_table(a: _Atelier) -> None:
    L, P, H = a.L, a.P, a.H
    R = min(L, P) / 2
    h_aj = 0.42 * H
    y_aj = H - h_aj
    h_pied = y_aj + 0.05 * H
    rb = R * a.u(0.38, 0.55)
    forme = int(a.rng.integers(0, 3))
    hp = h_pied * 0.82
    if forme == 0:      # jarre
        profil = [(0, 0), (rb * 0.6, 0), (rb, 0.3 * hp), (rb * 0.95, 0.6 * hp), (rb * 0.35, 0.92 * hp), (rb * 0.3, hp), (0, hp)]
    elif forme == 1:    # cylindre
        profil = [(0, 0), (rb * 0.8, 0), (rb * 0.8, hp), (0, hp)]
    else:               # cône renversé
        profil = [(0, 0), (rb, 0), (rb * 0.35, hp), (0, hp)]
    a("pied", g.revolution(profil, sections=24))
    a("pied", g.cylindre(0.008, h_pied - hp + 0.06, y=hp, sections=8))
    a("abat_jour", _coquille(_profil_abat_jour(a, R, h_aj), 0.003, y=y_aj, sections=32))


def _b_suspension(a: _Atelier) -> None:
    L, P, H = a.L, a.P, a.H
    R = min(L, P) / 2
    h_c = 0.025
    a("structure", g.cylindre(0.06, h_c, y=H - h_c, sections=20))           # pavillon au plafond
    forme = {"moderne": "dome", "classique": "tambour", "scandinave": "etages", "industriel": "cone"}[a.style]
    h_aj = min(0.55 * H, 0.3 if forme != "tambour" else 0.24)
    y_aj = 0.0
    if forme == "dome":
        profil = [(R * math.cos(t), y_aj + h_aj * math.sin(t)) for t in np.linspace(0.0, math.pi / 2 - 0.15, 7)]
        a("abat_jour" if a.style != "industriel" else "structure", _coquille(profil, 0.004, sections=32))
    elif forme == "cone":
        a("structure", _coquille([(R, 0.0), (R * 0.85, 0.03), (R * 0.2, h_aj * 0.9), (0.03, h_aj)], 0.003))
    elif forme == "tambour":
        a("abat_jour", _coquille([(R, 0.0), (R, h_aj)], 0.003))
        a("structure", g.cylindre(R * 0.98, 0.006, y=h_aj * 0.5, sections=24))
    else:
        for k, (rr, hh) in enumerate(((R, 0.0), (R * 0.72, 0.09), (R * 0.45, 0.17))):
            a("abat_jour", _coquille([(rr, hh), (rr * 0.82, hh + 0.08)], 0.003, sections=32))
        h_aj = 0.25
    a("ampoule", g.sphere(0.045, y=0.06, subdivisions=2))
    a("structure", g.cylindre(0.004, H - h_c - h_aj + 0.01, y=h_aj - 0.01, sections=6))


def _b_plante_en_pot(a: _Atelier) -> None:
    """Plante en pot : pot au tour avec rebord, terreau, puis un des trois ports courants (arbuste à
    couronne ou touffe, grandes feuilles sur tiges, feuilles en lame dressées), qui remplit l'emprise."""
    L, P, H = a.L, a.P, a.H
    R = min(L, P) / 2
    rp = R * a.u(0.5, 0.66)
    hp = min(0.45, max(0.18, 0.28 * H))
    profil = [(0, 0), (rp * 0.72, 0), (rp, hp * 0.88), (rp * 1.08, hp * 0.9), (rp * 1.08, hp), (rp * 0.96, hp),
              (rp * 0.92, hp * 0.93), (0, hp * 0.93)]
    a("pot", g.revolution(profil, sections=24))
    a("terreau", g.cylindre(rp * 0.92, 0.01, y=hp * 0.93 - 0.005, sections=20))
    y0 = hp * 0.9
    hf = H - y0
    sorte = int(a.rng.integers(0, 3))
    debut = len(a.pieces)
    if sorte == 0:
        if hf > 0.75:                                  # arbuste : tige nue puis couronne
            ry = min(R * 1.05, hf * 0.42)
            yc = H - ry
            a("tige", _cone_entre((0.0, y0, 0.0), (0.0, yc, 0.0), 0.018, 0.01, sections=8))
            _couronne(a, "feuillage", (0.0, yc, 0.0), R, ry, int(a.rng.integers(5, 8)), bruit=0.24,
                      sub_centre=2)
        else:                                           # touffe posée sur le terreau
            ry = hf / 2
            _couronne(a, "feuillage", (0.0, y0 + ry * 0.92, 0.0), R, ry, int(a.rng.integers(5, 8)), bruit=0.24,
                      sub_centre=2)
    elif sorte == 1:                                    # grandes feuilles au bout de tiges arquées
        n = int(a.rng.integers(8, 13))
        lf = min(R * 0.55, hf * 0.32)
        for i in range(n):
            ang = i * 2.39996 + a.u(-0.3, 0.3)
            chute = a.u(0.15, 0.6)
            portee = R * a.u(0.75, 1.0) - lf * math.cos(chute)
            yt = y0 + hf * a.u(0.45, 1.0) - lf * 0.15
            dx, dz = math.cos(ang), math.sin(ang)
            bout = np.array([dx * max(portee, 0.02), min(yt, H - 0.03), dz * max(portee, 0.02)])
            mi = np.array([dx * portee * 0.25, (y0 + bout[1]) * 0.5 + hf * 0.1, dz * portee * 0.25])
            a("feuillage", g.segment((0.0, y0, 0.0), mi, 0.005, sections=6), g.segment(mi, bout, 0.004, sections=6))
            feuille = g.ellipsoide(lf / 2, 0.006, lf * 0.3, x=lf / 2, subdivisions=2)
            feuille = _tourner(feuille, [0, 0, 1], -chute)
            feuille = _tourner(feuille, [0, 1, 0], -ang)
            a("feuillage", g.translation(feuille, *bout))
    else:                                               # feuilles en lame, dressées et évasées
        n = int(a.rng.integers(10, 16))
        for i in range(n):
            ang = i * 2.39996
            d = a.u(0.0, rp * 0.55)
            hl = hf * a.u(0.6, 1.0)
            cible = R * a.u(0.5, 1.0)
            incl = math.asin(float(np.clip((cible - d) / hl, 0.0, 0.55)))
            c, s = math.cos(ang), math.sin(ang)
            lame = g.ellipsoide(min(0.05, R * 0.16), hl / 2, 0.012, y=hl / 2, subdivisions=2)
            lame = _tourner(lame, [0, 1, 0], math.pi / 2 - ang)
            lame = _tourner(lame, [s, 0.0, -c], incl)
            a("feuillage", g.translation(lame, d * c, y0, d * s))
    if sorte != 0:
        _remplir_emprise(a, debut, R, R)


def _remplir_emprise(a: _Atelier, debut: int, demi_x: float, demi_z: float) -> None:
    """Le feuillage ajouté depuis `debut` atteint l'emprise (portée maximale autour de l'axe vertical),
    pour que l'ajustement final n'étire pas le pot ou le tronc qui le portent."""
    pieces = a.pieces[debut:]
    if not pieces:
        return
    v = np.vstack([np.asarray(m.vertices) for _, _, m in pieces])
    fx = demi_x / max(float(np.abs(v[:, 0]).max()), 1e-6)
    fz = demi_z / max(float(np.abs(v[:, 2]).max()), 1e-6)
    a.pieces[debut:] = [(e, k, _etirer(m, fx, 1.0, fz)) for e, k, m in pieces]


def _b_tableau(a: _Atelier) -> None:
    L, P, H = a.L, a.P, a.H
    c = min(0.06, 0.09 * min(L, H))
    zb = -P / 2
    for (x0, x1, y0, y1) in ((-L / 2, L / 2, 0.0, c), (-L / 2, L / 2, H - c, H), (-L / 2, -L / 2 + c, c, H - c),
                             (L / 2 - c, L / 2, c, H - c)):
        a("cadre", _pave(x0, x1, y0, y1, zb, P / 2))
    zt = zb + P * 0.45
    a("toile", _pave(-L / 2 + c, L / 2 - c, c, H - c, zb, zt))
    # composition abstraite : aplats de couleur sur la toile
    n = int(a.rng.integers(3, 6))
    teintes = a.teintes_libres("toile", n, TEINTES_TOILE)
    li, hi = L - 2 * c, H - 2 * c
    for k in range(n):
        w, h = a.u(0.2, 0.6) * li, a.u(0.2, 0.6) * hi
        x0 = -L / 2 + c + a.u(0.05, 0.95) * (li - w)
        y0 = c + a.u(0.05, 0.95) * (hi - h)
        a("toile", _pave(x0, x0 + w, y0, y0 + h, zt, zt + 0.0015 * (k + 1)), materiau=teintes[k])


def _b_miroir(a: _Atelier) -> None:
    L, P, H = a.L, a.P, a.H
    zb = -P / 2
    c = 0.035 if a.style != "industriel" else 0.015
    if a.style in ("classique", "scandinave"):
        from shapely import affinity
        ext = affinity.scale(Point(0.0, H / 2).buffer(1.0, resolution=16), L / 2, H / 2)
        if a.style == "scandinave":
            ext = _rect_arrondi(-L / 2, 0.0, L / 2, H, min(L, H) * 0.45)
    else:
        ext = _rect_arrondi(-L / 2, 0.0, L / 2, H, 0.02 if a.style == "moderne" else 0.0)
    inte = ext.buffer(-c)
    a("cadre", _panneau_xy(ext.difference(inte), zb, P))
    a("glace", _panneau_xy(inte.buffer(0.002), zb, P * 0.55))


def _b_cheminee(a: _Atelier) -> None:
    L, P, H = a.L, a.P, a.H
    zb, zf = -P / 2, P / 2
    tab = 0.06
    lp = 0.18 if a.sty["moulures"] or a.style != "moderne" else 0.22
    y_lin = H - tab - 0.22
    ouverture = (L - 2 * lp)
    # tablette, linteau, jambages
    a("structure", _pave(-L / 2, L / 2, H - tab, H, zb, zf))
    a("structure", _pave(-L / 2 + 0.03, L / 2 - 0.03, y_lin, H - tab, zb, zf - 0.04))
    for sx in (-1, 1):
        x0 = sx * (L / 2 - 0.03) if sx < 0 else L / 2 - 0.03 - lp
        a("structure", _pave(min(x0, x0 + lp), max(x0, x0 + lp), 0.0, y_lin, zb, zf - 0.04))
        if a.sty["moulures"]:
            a("structure", _pave(min(x0, x0 + lp) + 0.03, max(x0, x0 + lp) - 0.03, 0.06, y_lin - 0.04, zf - 0.04,
                                 zf - 0.025))
    # foyer en fonte au fond, sole, bûches
    xi0, xi1 = -L / 2 + 0.03 + lp, L / 2 - 0.03 - lp
    a("foyer", _pave(xi0, xi1, 0.0, y_lin, zb, zb + 0.06))
    a("foyer", _pave(xi0, xi1, 0.0, 0.02, zb, zf - 0.04))
    for k in range(3):
        lb = ouverture * 0.6
        b = g.cylindre(0.045, lb, sections=10)
        b = _tourner(b, [0, 0, 1], math.pi / 2 + (k - 1) * 0.15)
        a("buches", g.translation(b, lb / 2 * (1 if k != 1 else 0.9), 0.065 + (0.07 if k == 1 else 0.0),
                                  zb + 0.18 + (k - 1) * 0.04 if k != 1 else zb + 0.17))


def _b_piano(a: _Atelier) -> None:
    L, P, H = a.L, a.P, a.H
    zb = -P / 2
    p_caisse = min(0.36, P * 0.6)
    zc = zb + p_caisse
    y_clavier = 0.72
    # caisse haute, joues, couvercle
    a("structure", _pave(-L / 2 + 0.03, L / 2 - 0.03, 0.04, H - 0.03, zb, zc))
    a("structure", _pave(-L / 2 + 0.01, L / 2 - 0.01, H - 0.03, H, zb, zc + 0.02))
    for sx in (-1, 1):
        x0 = -L / 2 if sx < 0 else L / 2 - 0.05
        a("structure", _pave(x0, x0 + 0.05, 0.0, H - 0.04, zb, P / 2 - 0.02 if True else zc))
    # lit du clavier, touches blanches, touches noires, cylindre (cache-clavier ouvert)
    xi0, xi1 = -L / 2 + 0.05, L / 2 - 0.05
    a("structure", _pave(xi0, xi1, y_clavier - 0.06, y_clavier, zc, P / 2 - 0.02))
    a("touches", _pave(xi0 + 0.01, xi1 - 0.01, y_clavier, y_clavier + 0.022, zc + 0.04, P / 2 - 0.03))
    n_blanches = 52
    pas = (xi1 - xi0 - 0.02) / n_blanches
    for i in range(n_blanches - 1):
        if i % 7 in (2, 6):
            continue
        x = xi0 + 0.01 + (i + 1) * pas
        a("structure", _pave(x - pas * 0.28, x + pas * 0.28, y_clavier + 0.022, y_clavier + 0.034, zc + 0.04,
                             zc + 0.13))
    a("structure", _pave(xi0, xi1, y_clavier + 0.02, y_clavier + 0.14, zc - 0.02, zc + 0.03))
    a("structure", _pave(xi0 + 0.1, xi1 - 0.1, y_clavier + 0.14, y_clavier + 0.36, zc - 0.01, zc + 0.012))
    # consoles avant
    for sx in (-1, 1):
        a("pieds", g.cylindre(0.03, y_clavier - 0.06, x=sx * (L / 2 - 0.09), z=P / 2 - 0.06, sections=12))
    # pédales
    for k in (-1, 0, 1):
        a("pedales", _pave(k * 0.07 - 0.015, k * 0.07 + 0.015, 0.05, 0.065, zc, zc + 0.08))


def _b_chaise(a: _Atelier) -> None:
    L, P, H = a.L, a.P, a.H
    y_ass = min(0.46, 0.52 * H)
    e_ass = 0.04
    zb = -P / 2
    hp = y_ass - e_ass
    r = 0.017 if a.style != "classique" else 0.02
    # pieds avant et arrière ; les pieds arrière montent en montants de dossier
    xi, zi = L / 2 - 0.03, P / 2 - 0.03
    for sx in (-1, 1):
        a("pieds", _pied(a, sx * xi, zi, hp, "pieds", r))
        if a.style == "industriel":
            a("pieds", _pave(sx * xi - 0.012, sx * xi + 0.012, 0.0, H, -zi - 0.012, -zi + 0.012))
        elif a.style == "scandinave":
            a("pieds", _cone_entre((sx * xi, 0.0, -zi), (sx * (xi - 0.01), H, -zi + 0.04), 0.012, 0.016))
        else:
            a("pieds", _cone_entre((sx * xi, 0.0, -zi), (sx * xi, H, -zi + 0.02), 0.016, 0.014))
    # entretoises
    if a.style in ("classique", "industriel"):
        for sx in (-1, 1):
            a("pieds", g.segment((sx * xi, 0.15, -zi), (sx * xi, 0.15, zi), 0.008, sections=8))
    # assise rembourrée sur cadre
    a("pieds", _pave(-xi, xi, hp - 0.05, hp, -zi, zi))
    a("assise", _arrondi(-L / 2 + 0.01, L / 2 - 0.01, hp, y_ass, zb + 0.02, P / 2 - 0.005, 0.015))
    # dossier selon le style
    zd = -zi + 0.02
    if a.style == "classique":
        a("assise", _arrondi(-xi + 0.02, xi - 0.02, y_ass + 0.08, H - 0.04, zd - 0.015, zd + 0.02, 0.015))
        a("pieds", _pave(-xi, xi, H - 0.05, H, zd - 0.02, zd + 0.02))
    elif a.style == "scandinave":
        traverse = g.cylindre(0.035, 2 * xi, sections=16)
        traverse = _tourner(traverse, [0, 0, 1], math.pi / 2)
        a("pieds", g.translation(_etirer(traverse, 1.0, 1.0, 0.6), xi, H - 0.11, zd + 0.02))
        for k in range(-1, 2):
            a("pieds", g.segment((k * 0.06, y_ass + 0.02, zd), (k * 0.06, H - 0.1, zd + 0.02), 0.007, sections=8))
    elif a.style == "industriel":
        a("pieds", _pave(-xi, xi, H - 0.16, H - 0.02, -zi - 0.004, -zi + 0.004))
    else:
        a("structure", _arrondi(-xi, xi, H - 0.2, H - 0.01, zd - 0.012, zd + 0.012, 0.01))


def _b_banc(a: _Atelier) -> None:
    L, P, H = a.L, a.P, a.H
    e = 0.04
    if a.style == "scandinave" or a.style == "moderne":
        n = 5 if a.style == "scandinave" else 1
        jeu = 0.012 if n > 1 else 0.0
        lz = (P - jeu * (n - 1)) / n
        for i in range(n):
            z0 = -P / 2 + i * (lz + jeu)
            a("structure", _arrondi(-L / 2, L / 2, H - e, H, z0, z0 + lz, 0.008))
    else:
        if a.style == "classique":            # assise rembourrée sur un plateau
            a("structure", _arrondi(-L / 2, L / 2, H - e - 0.05, H - 0.05, -P / 2, P / 2, 0.01))
            a("coussin", _arrondi(-L / 2 + 0.015, L / 2 - 0.015, H - 0.05, H, -P / 2 + 0.015, P / 2 - 0.015, 0.02, sub=2))
            e += 0.05
        else:
            a("structure", _arrondi(-L / 2, L / 2, H - e, H, -P / 2, P / 2, 0.01))
    if a.style == "industriel":
        for sx in (-1, 1):
            x = sx * (L / 2 - 0.08)
            c = 0.015
            a("pieds", _pave(x - c, x + c, 0, H - e, -P / 2 + 0.02, -P / 2 + 0.05),
              _pave(x - c, x + c, 0, H - e, P / 2 - 0.05, P / 2 - 0.02),
              _pave(x - c, x + c, 0, 0.03, -P / 2 + 0.02, P / 2 - 0.02),
              _pave(x - c, x + c, H - e - 0.03, H - e, -P / 2 + 0.02, P / 2 - 0.02))
    else:
        _pietement_simple(a, "pieds", L / 2 - 0.08, P / 2 - 0.06, H - e, 0.022)


def _pietement_simple(a: _Atelier, emp: str, x: float, z: float, h: float, r: float) -> None:
    for sx in (-1, 1):
        for sz in (-1, 1):
            a(emp, _pied(a, sx * x, sz * z, h, emp, r))


def _b_porte_manteau(a: _Atelier) -> None:
    L, P, H = a.L, a.P, a.H
    R = min(L, P) / 2
    # piètement en croix ou trépied
    n = 3 if a.style == "scandinave" else 4
    for k in range(n):
        ang = k * 2 * math.pi / n
        a("pieds", _cone_entre(((R - 0.012) * math.sin(ang), 0.0, (R - 0.012) * math.cos(ang)), (0.0, 0.32, 0.0),
                               0.012, 0.018))
    a("structure", g.cylindre(0.02, H - 0.3 - 0.03, y=0.3, sections=14))
    a("structure", g.sphere(0.03, y=H - 0.03, subdivisions=1))
    for k in range(6):
        ang = k * math.pi / 3
        for y, lng in ((H - 0.1, R * 0.62), (H - 0.32, R * 0.42)):
            if y == H - 0.32 and k % 2:
                continue
            a("structure", g.segment((0.0, y, 0.0), (lng * math.sin(ang), y + 0.08, lng * math.cos(ang)), 0.008,
                                     sections=8),
              g.sphere(0.013, x=lng * math.sin(ang), y=y + 0.08, z=lng * math.cos(ang), subdivisions=1))


def _b_buffet(a: _Atelier) -> None:
    hb, yh, zf, x0, x1 = _corps_rangement(a, "structure", "pieds")
    n = int(np.clip(round((x1 - x0) / 0.45), 3, 4))
    lp = (x1 - x0) / n
    y_tir = yh - 0.16
    for i in range(n):
        xa, xb = x0 + i * lp, x0 + (i + 1) * lp
        _facade(a, "structure", "poignees", xa, xb, y_tir, yh, zf)
        _facade(a, "structure", "poignees", xa, xb, hb, y_tir, zf, poignee="droite" if i % 2 == 0 else "gauche")


# ── Cuisine ────────────────────────────────────────────────────────────────────────────────────────
def _meubles_bas(a: _Atelier, x0: float, x1: float, h_plan: float, zf: float, z_dos: float,
                 types: list[str]) -> None:
    """Rangée de meubles bas : socle en retrait, caissons, façades (tiroirs / portes) selon `types`."""
    socle = 0.1
    a("facades", _pave(x0, x1, 0.0, socle, z_dos, zf - 0.06))
    ef = 0.019
    a("facades", _pave(x0, x1, socle, h_plan, z_dos, zf - ef))
    n = len(types)
    lm = (x1 - x0) / n
    for i, t in enumerate(types):
        xa, xb = x0 + i * lm, x0 + (i + 1) * lm
        if t == "tiroirs":
            hs = [0.18, 0.27, 0.29]
            tot = h_plan - socle
            ys = [socle] + list(np.cumsum([tot * h / sum(hs) for h in reversed(hs)]) + socle)
            for k in range(3):
                _facade(a, "facades", "poignees", xa, xb, ys[k], ys[k + 1], zf - ef, ef, saillie=0.02)
        elif t == "evier":
            for k, cote in ((0, "droite"), (1, "gauche")):
                _facade(a, "facades", "poignees", xa + k * lm / 2, xa + (k + 1) * lm / 2, socle, h_plan, zf - ef, ef,
                        poignee="haut" if a.style != "classique" else cote, saillie=0.02)
        else:
            _facade(a, "facades", "poignees", xa, xb, h_plan - 0.15, h_plan, zf - ef, ef, saillie=0.02)
            _facade(a, "facades", "poignees", xa, xb, socle, h_plan - 0.15, zf - ef, ef,
                    poignee="droite" if i % 2 == 0 else "gauche", saillie=0.02)


def _evier(a: _Atelier, cx: float, cz: float, lx: float, lz: float, y_plan: float) -> None:
    """Cuve d'évier encastrée sous l'ouverture du plan : fond, quatre parois, rebord, bonde."""
    prof = 0.18
    e = 0.004
    x0, x1, z0, z1 = cx - lx / 2, cx + lx / 2, cz - lz / 2, cz + lz / 2
    a("evier", _pave(x0, x1, y_plan - prof, y_plan - prof + e, z0, z1))
    a("evier", _pave(x0, x0 + e, y_plan - prof, y_plan, z0, z1), _pave(x1 - e, x1, y_plan - prof, y_plan, z0, z1),
      _pave(x0, x1, y_plan - prof, y_plan, z0, z0 + e), _pave(x0, x1, y_plan - prof, y_plan, z1 - e, z1))
    rebord = rect_shapely(x0 - 0.02, z0 - 0.02, x1 + 0.02, z1 + 0.02).difference(rect_shapely(x0, z0, x1, z1))
    a("evier", g.extrusion(rebord, 0.003, y=y_plan))
    a("robinet", g.cylindre(0.025, 0.002, x=cx, y=y_plan - prof + e, z=cz, sections=12))


def _robinet(a: _Atelier, x: float, y: float, z: float, hauteur: float, portee: float) -> None:
    """Robinet col de cygne : embase, fût, arc vers l'avant (+Z), bec vers le bas."""
    a("robinet", g.cylindre(0.025, 0.04, x=x, y=y, z=z, sections=14))
    pts = [(x, y + 0.04, z), (x, y + hauteur * 0.75, z)]
    for t in np.linspace(0.0, math.pi, 6)[1:]:
        pts.append((x, y + hauteur * 0.75 + math.sin(t) * portee * 0.5, z + (1 - math.cos(t)) * portee * 0.5))
    pts.append((x, y + hauteur * 0.75 - 0.05, z + portee))
    for p, q in zip(pts[:-1], pts[1:]):
        a("robinet", g.segment(p, q, 0.011, sections=10), g.sphere(0.011, x=q[0], y=q[1], z=q[2], subdivisions=1))


def _b_plan_de_travail(a: _Atelier) -> None:
    L, P, H = a.L, a.P, a.H
    ep = 0.035
    debord = 0.025
    zb, zf = -P / 2, P / 2 - debord
    h_caisson = H - ep
    n = max(2, int(round(L / 0.6)))
    lm = L / n
    i_evier = int(a.rng.integers(0, n))
    i_plaque = (i_evier + max(1, n // 2)) % n
    types = ["tiroirs" if i == i_plaque else ("evier" if i == i_evier else "porte") for i in range(n)]
    _meubles_bas(a, -L / 2, L / 2, h_caisson, zf, zb, types)
    # plan de travail percé pour la cuve
    cx = -L / 2 + (i_evier + 0.5) * lm
    lx, lz = min(lm - 0.14, 0.72), min(0.42, P - 0.2)
    cz = zb + 0.06 + lz / 2 + 0.04
    poly = rect_shapely(-L / 2, zb, L / 2, P / 2).difference(rect_shapely(cx - lx / 2, cz - lz / 2, cx + lx / 2,
                                                                       cz + lz / 2))
    a("plan", g.plaque(poly, ep, y=H))
    _evier(a, cx, cz, lx, lz, H)
    _robinet(a, cx, H, zb + 0.06, 0.24, min(0.22, lz * 0.55))
    # plaque de cuisson (vitrocéramique) et foyers
    px = -L / 2 + (i_plaque + 0.5) * lm
    lpx, lpz = min(lm - 0.06, 0.6), min(0.52, P - 0.08)
    pz = zb + 0.04 + lpz / 2
    a("plaque", _arrondi(px - lpx / 2, px + lpx / 2, H, H + 0.006, pz - lpz / 2, pz + lpz / 2, 0.002))
    for dx, dz, rr in ((-0.14, -0.11, 0.09), (0.14, -0.11, 0.075), (-0.14, 0.12, 0.075), (0.14, 0.12, 0.1)):
        a("evier", _anneau_plat(px + dx * lpx / 0.6, pz + dz * lpz / 0.52, rr, rr - 0.006, H + 0.006))
    a.hauteur_surface = H


def _anneau_plat(x: float, z: float, r_ext: float, r_int: float, y: float) -> trimesh.Trimesh:
    couronne = Point(x, z).buffer(r_ext, resolution=8).difference(Point(x, z).buffer(r_int, resolution=8))
    return g.extrusion(couronne, 0.001, y=y)


def _b_placard_haut(a: _Atelier) -> None:
    L, P, H = a.L, a.P, a.H
    saillie, ef = 0.022, 0.019
    zb, zf = -P / 2, P / 2 - saillie - ef
    a("facades", _pave(-L / 2, L / 2, 0.0, H, zb, zf))
    n = int(np.clip(round(L / 0.5), 1, 6))
    lp = L / n
    for i in range(n):
        _facade(a, "facades", "poignees", -L / 2 + i * lp, -L / 2 + (i + 1) * lp, 0.0, H, zf, ef, poignee="bas",
                saillie=saillie)


def _b_ilot_cuisine(a: _Atelier) -> None:
    L, P, H = a.L, a.P, a.H
    ep = 0.04
    p_meubles = 0.6
    zf = P / 2 - 0.025
    z_dos = zf - p_meubles
    n = max(2, int(round((L - 0.04) / 0.6)))
    types = ["tiroirs" if i % 2 == 0 else "porte" for i in range(n)]
    _meubles_bas(a, -L / 2 + 0.02, L / 2 - 0.02, H - ep, zf, z_dos, types)
    # joues latérales et fond côté bar (-Z), plan débordant côté bar
    for sx in (-1, 1):
        a("facades", _pave(sx * L / 2 - 0.02 if sx > 0 else -L / 2, L / 2 if sx > 0 else -L / 2 + 0.02, 0.0, H - ep,
                           z_dos - 0.02, zf))
    a("facades", _pave(-L / 2 + 0.02, L / 2 - 0.02, 0.0, H - ep, z_dos - 0.02, z_dos))
    a("plan", _arrondi(-L / 2, L / 2, H - ep, H, -P / 2, P / 2, 0.006))
    a("plan", _pave(-L / 2, -L / 2 + 0.04, 0.0, H - ep, -P / 2, z_dos - 0.02),
      _pave(L / 2 - 0.04, L / 2, 0.0, H - ep, -P / 2, z_dos - 0.02))


def _b_refrigerateur(a: _Atelier) -> None:
    L, P, H = a.L, a.P, a.H
    saillie, ep_porte = 0.035, 0.05
    zb, zf = -P / 2, P / 2 - saillie - ep_porte
    a("caisse", _arrondi(-L / 2, L / 2, 0.02, H, zb, zf + 0.01, 0.02))
    for sx in (-1, 1):
        for sz in (zb + 0.05, zf - 0.05):
            a("poignees", g.cylindre(0.02, 0.02, x=sx * (L / 2 - 0.05), z=sz, sections=10))
    y_cong = 0.02 + (H - 0.02) * 0.36
    jeu = 0.004
    a("caisse", _arrondi(-L / 2 + jeu, L / 2 - jeu, 0.02 + jeu, y_cong - jeu, zf, zf + ep_porte, 0.015))
    a("caisse", _arrondi(-L / 2 + jeu, L / 2 - jeu, y_cong + jeu, H - jeu, zf, zf + ep_porte, 0.015))
    xp = L / 2 - 0.06
    for y0, y1 in ((y_cong - 0.38, y_cong - 0.06), (y_cong + 0.06, y_cong + 0.5)):
        a("poignees", g.segment((xp, y0, zf + ep_porte + saillie - 0.012), (xp, y1, zf + ep_porte + saillie - 0.012),
                                0.012, sections=10))
        for y in (y0 + 0.02, y1 - 0.02):
            a("poignees", g.segment((xp, y, zf + ep_porte), (xp, y, zf + ep_porte + saillie - 0.012), 0.008, sections=8))


def _b_cuisiniere(a: _Atelier) -> None:
    L, P, H = a.L, a.P, a.H
    saillie = 0.04
    zb, zf = -P / 2, P / 2 - saillie
    a("caisse", _pave(-L / 2, L / 2, 0.0, H - 0.006, zb, zf))
    a("plaque", _arrondi(-L / 2 + 0.005, L / 2 - 0.005, H - 0.006, H, zb + 0.005, zf, 0.002))
    for dx, dz, rr in ((-0.25, -0.24, 0.09), (0.25, -0.24, 0.075), (-0.25, 0.24, 0.075), (0.25, 0.24, 0.1)):
        a("caisse", _anneau_plat(dx * L / 1.1, (zb + zf) / 2 + dz * (zf - zb) / 1.15, rr, rr - 0.006, H))
    # bandeau de commande et boutons
    y_b = H - 0.1
    a("plaque", _pave(-L / 2 + 0.01, L / 2 - 0.01, y_b, H - 0.012, zf, zf + 0.004))
    for k in range(5):
        x = -L / 2 + (k + 1) * L / 6
        a("caisse", _cone_entre((x, (y_b + H - 0.012) / 2, zf), (x, (y_b + H - 0.012) / 2, zf + 0.03), 0.018, 0.016,
                                sections=12))
    # porte du four avec hublot, poignée, tiroir bas
    y_tir = 0.13
    a("caisse", _pave(-L / 2 + 0.01, L / 2 - 0.01, y_tir + 0.005, y_b - 0.01, zf, zf + 0.012))
    a("plaque", _pave(-L / 2 + 0.07, L / 2 - 0.07, y_tir + 0.08, y_b - 0.12, zf + 0.012, zf + 0.015))
    a("caisse", g.segment((-L / 2 + 0.08, y_b - 0.055, zf + 0.035), (L / 2 - 0.08, y_b - 0.055, zf + 0.035), 0.01))
    for sx in (-1, 1):
        a("caisse", g.segment((sx * (L / 2 - 0.1), y_b - 0.055, zf + 0.012), (sx * (L / 2 - 0.1), y_b - 0.055, zf + 0.035),
                              0.008, sections=8))
    a("caisse", _pave(-L / 2 + 0.01, L / 2 - 0.01, 0.02, y_tir, zf, zf + 0.012))


def _b_hotte(a: _Atelier) -> None:
    L, P, H = a.L, a.P, a.H
    zb = -P / 2
    h_jupe = 0.07
    h_trans = min(0.2, 0.4 * H)
    a("caisse", _pave(-L / 2, L / 2, 0.0, h_jupe, zb, P / 2))
    lc, pc = min(0.3, L * 0.4), min(0.26, P * 0.6)
    coins = [(sx * (L / 2 - 0.004), h_jupe, z) for sx in (-1, 1) for z in (zb + 0.004, P / 2 - 0.004)]
    coins += [(sx * lc / 2, h_jupe + h_trans, z) for sx in (-1, 1) for z in (zb + 0.004, zb + pc)]
    a("caisse", _coque(coins, 0.004, sub=0, lissage=20.0))
    a("caisse", _pave(-lc / 2, lc / 2, h_jupe + h_trans - 0.01, H, zb, zb + pc))
    a("filtre", _pave(-L / 2 + 0.03, L / 2 - 0.03, -0.0005, 0.002, zb + 0.03, P / 2 - 0.03))


def _b_lave_vaisselle(a: _Atelier) -> None:
    L, P, H = a.L, a.P, a.H
    saillie = 0.03
    zb, zf = -P / 2, P / 2 - saillie
    a("caisse", _pave(-L / 2, L / 2, 0.0, H, zb, zf - 0.02))
    a("caisse", _pave(-L / 2 + 0.003, L / 2 - 0.003, 0.1, H - 0.003, zf - 0.02, zf))
    a("socle", _pave(-L / 2 + 0.01, L / 2 - 0.01, 0.0, 0.1, zb, zf - 0.05))
    a("bandeau", _pave(-L / 2 + 0.003, L / 2 - 0.003, H - 0.09, H - 0.003, zf, zf + 0.004))
    _poignee(a, "poignees", 0.0, H - 0.13, zf, verticale=False, longueur=0.3, saillie=saillie)


def _b_lave_linge(a: _Atelier) -> None:
    L, P, H = a.L, a.P, a.H
    saillie = 0.05
    zb, zf = -P / 2, P / 2 - saillie
    a("caisse", _arrondi(-L / 2, L / 2, 0.0, H, zb, zf, 0.015))
    rh = min(0.2, L * 0.33)
    yh = H * 0.45
    a("caisse", _anneau_vertical(rh + 0.035, rh - 0.01, 0.03, x=0.0, y=yh, z0=zf))
    a("joint", _disque_vertical(rh - 0.005, 0.005, x=0.0, y=yh, z0=zf - 0.002))
    hublot = g.ellipsoide(rh - 0.01, rh - 0.01, 0.02, x=0.0, y=yh, z=zf + 0.02, subdivisions=2)
    a("hublot", hublot)
    a("caisse", _pave(-L / 2 + 0.03, -L / 2 + 0.2, H - 0.1, H - 0.03, zf, zf + 0.01))
    a("caisse", _cone_entre((L / 2 - 0.12, H - 0.065, zf), (L / 2 - 0.12, H - 0.065, zf + 0.025), 0.03, 0.028, sections=16))
    a("joint", _pave(-L / 2 + 0.25, L / 2 - 0.2, H - 0.09, H - 0.04, zf, zf + 0.004))


# ── Salle de bain ──────────────────────────────────────────────────────────────────────────────────
def _creuser(plein: trimesh.Trimesh, vide: trimesh.Trimesh, lissage: float = 35.0) -> trimesh.Trimesh:
    """Différence booléenne (manifold) ; repli sur le plein si le moteur échoue (jamais d'objet vide)."""
    try:
        a = trimesh.Trimesh(vertices=plein.vertices, faces=plein.faces, process=True)
        b = trimesh.Trimesh(vertices=vide.vertices, faces=vide.faces, process=True)
        r = trimesh.boolean.difference([a, b], engine="manifold")
        if r is not None and len(r.faces):
            return g.finaliser(r, lissage_deg=lissage)
    except Exception:  # noqa: BLE001 — le plein reste un objet lisible
        pass
    return plein


def _b_baignoire(a: _Atelier) -> None:
    L, P, H = a.L, a.P, a.H
    h_bord = H - 0.07
    ext = _arrondi(-L / 2, L / 2, 0.0, h_bord, -P / 2, P / 2, 0.04, sub=1)
    e = 0.07
    cuve = g.boite_arrondie(L - 2 * e, h_bord, P - 2 * e, 0.16, y=0.12, subdivisions=2)
    a("cuve", _creuser(ext, cuve))
    xr = -L / 2 + 0.035
    zr = -P / 2 + P * 0.5
    a("robinet", g.cylindre(0.022, 0.07, x=xr, y=h_bord, z=zr, sections=12))
    a("robinet", g.segment((xr, h_bord + 0.055, zr), (xr + 0.12, h_bord + 0.055, zr), 0.012, sections=10))
    for dz in (-0.07, 0.07):
        a("robinet", g.cylindre(0.018, 0.05, x=xr, y=h_bord, z=zr + dz, sections=10))


def _b_douche(a: _Atelier) -> None:
    L, P, H = a.L, a.P, a.H
    h_rec = 0.05
    a("receveur", _arrondi(-L / 2, L / 2, 0.0, h_rec, -P / 2, P / 2, 0.01))
    a("robinet", _pave(-0.04, 0.04, h_rec + 0.001, h_rec + 0.004, -0.04, 0.04))
    e = 0.008
    # paroi avant (fixe sur 60 %), paroi latérale droite, profilés
    zf = P / 2 - e
    xa = -L / 2 + 0.01
    xb = xa + 0.6 * L
    a("paroi", _pave(xa, xb, h_rec, H - 0.02, zf, zf + e))
    a("paroi", _pave(L / 2 - e - 0.005, L / 2 - 0.005, h_rec, H - 0.02, -P / 2 + 0.01, zf))
    a("robinet", _pave(xa, xb, H - 0.02, H, zf - 0.004, P / 2), _pave(L / 2 - 0.02, L / 2, H - 0.02, H, -P / 2 + 0.01, P / 2))
    a("robinet", _pave(-L / 2, -L / 2 + 0.015, h_rec, H, zf - 0.004, P / 2))
    a("robinet", g.segment((xb, H - 0.01, zf + e / 2), (L / 2 - 0.01, H - 0.01, -P / 2 + 0.2), 0.008))
    # colonne de douche au mur du fond
    zc = -P / 2 + 0.03
    xc = -L * 0.15
    a("robinet", g.segment((xc, 0.95, zc), (xc, H - 0.12, zc), 0.012))
    a("robinet", g.segment((xc, H - 0.12, zc), (xc, H - 0.12, zc + 0.3), 0.01))
    a("robinet", g.cylindre(0.12, 0.012, x=xc, y=H - 0.14, z=zc + 0.3, sections=24))
    a("robinet", _pave(xc - 0.12, xc + 0.12, 0.98, 1.06, zc - 0.01, zc + 0.05))


def _b_lavabo(a: _Atelier) -> None:
    L, P, H = a.L, a.P, a.H
    h_vasque = 0.14
    h_tap = 0.03
    y_plan = H - h_vasque - h_tap
    ep = 0.03
    saillie = 0.025
    zb, zf = -P / 2, P / 2 - 0.02 - saillie
    # meuble sur socle en retrait (moderne) ou sur pieds (autres styles)
    y_bas = _soubassement(a, "meuble", -L / 2 + 0.02, L / 2 - 0.02, zb, zf)
    a("meuble", _pave(-L / 2 + 0.02, L / 2 - 0.02, y_bas, y_plan - ep, zb, zf - 0.019))
    n = 2 if L > 0.75 else 1
    lp = (L - 0.04) / n
    for i in range(n):
        _facade(a, "meuble", "poignees", -L / 2 + 0.02 + i * lp, -L / 2 + 0.02 + (i + 1) * lp, y_bas, y_plan - ep,
                zf - 0.019, 0.019, poignee="centre" if n == 1 else ("droite" if i == 0 else "gauche"), saillie=saillie)
    a("meuble", _arrondi(-L / 2, L / 2, y_plan - ep, y_plan, zb, P / 2 - 0.02, 0.005))
    # vasque à poser et robinet
    rv = min(0.21, L / 2 - 0.05, (P - 0.12) / 2)
    cz = zb + 0.08 + rv
    a("vasque", _coquille([(rv * 0.55, 0.0), (rv * 0.9, 0.04), (rv, h_vasque * 0.75), (rv, h_vasque)], 0.012,
                          y=y_plan, z=cz, sections=32))
    a("vasque", g.cylindre(rv * 0.56, 0.012, y=y_plan, z=cz, sections=24))
    zr = zb + 0.035
    hr = H - y_plan
    _robinet(a, 0.0, y_plan, zr, hr - 0.012, min(0.16, cz - zr + rv * 0.2))


def _b_wc(a: _Atelier) -> None:
    L, P, H = a.L, a.P, a.H
    zb = -P / 2
    p_res = 0.17
    y_ab = 0.4
    rb = L / 2 - 0.01
    long_cuvette = P - p_res + 0.04
    sz = long_cuvette / (2 * rb)
    cz = zb + p_res - 0.04 + long_cuvette / 2
    corps = g.revolution([(0, 0), (rb * 0.55, 0), (rb * 0.5, 0.12), (rb * 0.75, 0.26), (rb * 0.97, y_ab - 0.04),
                          (rb, y_ab - 0.02), (0, y_ab - 0.02)], sections=28)
    a("cuvette", g.translation(_etirer(corps, 1.0, 1.0, sz), 0.0, 0.0, cz))
    abattant = g.ellipsoide(rb, 0.022, rb * sz, x=0.0, y=y_ab, z=cz, subdivisions=2)
    a("cuvette", abattant)
    a("cuvette", _arrondi(-L / 2, L / 2, y_ab - 0.06, H, zb, zb + p_res, 0.03, sub=2))
    a("bouton", g.cylindre(0.025, 0.006, x=0.0, y=H - 0.003, z=zb + p_res / 2, sections=14))


# ── Extérieur et mobilier urbain ───────────────────────────────────────────────────────────────────
def _lanterne(a: _Atelier, x: float, y_haut: float, z: float, r: float, h: float) -> None:
    """Lanterne de style ancien : chapeau, cage vitrée lumineuse hexagonale, culot."""
    a("mat", g.revolution([(0, 0), (r * 0.45, 0), (r * 0.75, 0.07), (0, 0.07)], x=x, y=y_haut - h, z=z, sections=6))
    a("lanterne", g.revolution([(0, 0), (r * 0.75, 0), (r, h * 0.62), (0, h * 0.62)], x=x, y=y_haut - h + 0.07, z=z,
                               sections=6))
    a("mat", g.revolution([(0, 0), (r * 1.15, 0), (r * 0.3, h * 0.3), (0.02, h * 0.38), (0, h * 0.38)], x=x,
                          y=y_haut - h * 0.38 - 0.0, z=z, sections=6))


def _b_lampadaire_rue(a: _Atelier) -> None:
    L, P, H = a.L, a.P, a.H
    base = min(P, 0.42) / 2
    a("mat", g.revolution([(0, 0), (base, 0), (base, 0.12), (base * 0.6, 0.35), (0.08, 0.6), (0, 0.6)], sections=12))
    if L < 0.7:                    # lanterne au sommet du mât
        h_l = min(0.9, 0.16 * H)
        a("mat", g.tronc_de_cone(0.075, 0.045, H - h_l - 0.6, y=0.6, sections=12))
        _lanterne(a, 0.0, H, 0.0, L / 2 * 0.95, h_l)
        return
    # deux crosses symétriques vers ±X, têtes suspendues
    h_mat = H - 0.12
    a("mat", g.tronc_de_cone(0.075, 0.045, h_mat - 0.6, y=0.6, sections=12))
    portee = L / 2 - 0.12
    y_bras = H - 0.25
    for sx in (-1, 1):
        pts = [(0.0, y_bras - 0.35, 0.0)]
        for t in np.linspace(0.0, math.pi / 2, 5)[1:]:
            pts.append((sx * portee * (1 - math.cos(t)) * 0.9, y_bras - 0.35 + math.sin(t) * 0.35, 0.0))
        pts.append((sx * portee, y_bras, 0.0))
        for p, q in zip(pts[:-1], pts[1:]):
            a("mat", g.segment(p, q, 0.025, sections=8))
        if a.style == "classique":
            _lanterne(a, sx * portee, y_bras + 0.06, 0.0, 0.12, 0.5)
        else:
            a("mat", _arrondi(sx * portee - 0.12, sx * portee + 0.12, y_bras - 0.06, y_bras + 0.05, -0.12, 0.12, 0.03))
            a("lanterne", _pave(sx * portee - 0.1, sx * portee + 0.1, y_bras - 0.068, y_bras - 0.06, -0.1, 0.1))
    a("mat", g.sphere(0.06, y=H - 0.06, subdivisions=1))


def _b_banc_public(a: _Atelier) -> None:
    L, P, H = a.L, a.P, a.H
    zb = -P / 2
    y_ass = 0.45
    xs = [-L / 2 + 0.06, L / 2 - 0.06] + ([0.0] if L > 1.8 else [])
    for x in xs:
        aux = x in (-L / 2 + 0.06, L / 2 - 0.06)
        # flasque en fonte : pied avant, pied arrière prolongé en montant de dossier incliné, appui de l'assise
        a("structure", g.segment((x, 0.0, P / 2 - 0.1), (x, y_ass - 0.03, P / 2 - 0.12), 0.025))
        a("structure", g.segment((x, 0.0, zb + 0.12), (x, y_ass - 0.03, zb + 0.16), 0.025))
        a("structure", g.segment((x, y_ass - 0.03, zb + 0.16), (x, H - 0.03, zb + 0.03), 0.022))
        a("structure", g.segment((x, y_ass - 0.04, zb + 0.14), (x, y_ass - 0.04, P / 2 - 0.06), 0.02))
        if aux:
            a("structure", g.segment((x, H * 0.82, zb + 0.12), (x, 0.66, P / 2 - 0.05), 0.02),
              g.segment((x, 0.66, P / 2 - 0.05), (x, y_ass - 0.03, P / 2 - 0.12), 0.02))
    # lattes d'assise et de dossier
    n = 4
    for i in range(n):
        z0 = zb + 0.12 + i * (P / 2 - 0.02 - zb - 0.12) / n
        a("lattes", _arrondi(-L / 2, L / 2, y_ass - 0.02, y_ass + 0.015, z0, z0 + 0.075, 0.006))
    for i in range(3):
        t = 0.3 + 0.22 * i
        yb = y_ass + t * (H - 0.03 - y_ass)
        zl = zb + 0.16 + t * (0.03 - 0.16)
        latte = _arrondi(-L / 2, L / 2, -0.04, 0.04, -0.012, 0.012, 0.006)
        latte = _tourner(latte, [1, 0, 0], -0.3)
        a("lattes", g.translation(latte, 0.0, yb, zl + 0.012))


def _b_poubelle_rue(a: _Atelier) -> None:
    L, P, H = a.L, a.P, a.H
    R = min(L, P) / 2
    a("structure", _coquille([(R * 0.9, 0.12), (R, H - 0.06), (R, H - 0.02)], 0.01, sections=24))
    a("structure", g.cylindre(R * 0.88, 0.01, y=0.12, sections=24))
    a("structure", g.revolution([(0, 0), (R * 0.55, 0), (R * 0.5, 0.12), (0, 0.12)], sections=16))
    a("structure", _coquille([(R * 1.0, H - 0.04), (R * 1.0, H)], 0.03, sections=24))
    a("sac", _pave(-R * 0.82, R * 0.82, H - 0.15, H - 0.13, -R * 0.82, R * 0.82))
    for k in range(10):
        ang = k * math.pi / 5
        x, z = (R + 0.002) * math.sin(ang), (R + 0.002) * math.cos(ang)
        a("structure", g.segment((x, 0.16, z), (x, H - 0.08, z), 0.006, sections=6))


def _b_abribus(a: _Atelier) -> None:
    L, P, H = a.L, a.P, a.H
    zb = -P / 2
    c = 0.04
    xs, zs = (-L / 2 + 0.1, L / 2 - 0.1), (zb + 0.15, P / 2 - 0.35)
    for x in xs:
        for z in zs:
            a("structure", _pave(x - c, x + c, 0.0, H - 0.08, z - c, z + c))
    # toit en pente douce, débordant
    toit = _arrondi(-L / 2, L / 2, -0.04, 0.04, zb, P / 2, 0.02)
    toit = _tourner(toit, [1, 0, 0], -0.05)
    a("toit", g.translation(toit, 0.0, H - 0.08, 0.0))
    # paroi vitrée du fond, paroi latérale, affiche lumineuse de l'autre côté
    zp = zs[0] - c
    a("parois", _pave(xs[0] + c, xs[1] - c, 0.12, H - 0.25, zp, zp + 0.012))
    a("structure", _pave(xs[0], xs[1], H - 0.25, H - 0.2, zp - 0.005, zp + 0.017), _pave(xs[0], xs[1], 0.08, 0.12, zp - 0.005,
                                                                                         zp + 0.017))
    a("parois", _pave(xs[0] - 0.006, xs[0] + 0.006, 0.12, H - 0.25, zs[0] + c, zs[1] - c))
    a("structure", _pave(xs[1] - 0.06, xs[1] + 0.06, 0.1, H - 0.4, zs[0] + c, zs[1] - c))
    a("affiche", _pave(xs[1] - 0.065, xs[1] + 0.065, 0.3, H - 0.6, zs[0] + c + 0.05, zs[1] - c - 0.05))
    # banc adossé au fond
    a("banc", _pave(-L / 4, L / 4, 0.45, 0.48, zp + 0.05, zp + 0.4))
    for x in (-L / 4 + 0.1, L / 4 - 0.1):
        a("banc", _pave(x - 0.02, x + 0.02, 0.0, 0.45, zp + 0.15, zp + 0.3))


def _b_feu_tricolore(a: _Atelier) -> None:
    L, P, H = a.L, a.P, a.H
    lb = L
    h_boite = min(0.95, 0.3 * H)
    y0 = H - h_boite
    a("mat", g.tronc_de_cone(0.07, 0.055, y0, sections=14))
    p_b = min(0.22, P * 0.7)
    zb = -P / 2
    a("mat", _arrondi(-lb / 2 + 0.02, lb / 2 - 0.02, y0, H, zb, zb + p_b, 0.03))
    for k, emp in enumerate(("feu_vert", "feux", "feu_rouge")):
        yk = y0 + (k + 0.5) * h_boite / 3
        rr = min(0.1, lb * 0.32)
        a(emp, _disque_vertical(rr, 0.01, x=0.0, y=yk, z0=zb + p_b))
        visiere = _coquille([(rr + 0.012, 0.0), (rr + 0.012, P - p_b - 0.002)], 0.006, sections=16)
        visiere = _tourner(visiere, [1, 0, 0], math.pi / 2)
        a("mat", g.translation(visiere, 0.0, yk, zb + p_b))


def _b_panneau(a: _Atelier) -> None:
    L, P, H = a.L, a.P, a.H
    zb = -P / 2
    r_mat = min(0.03, P * 0.3)
    a("mat", g.cylindre(r_mat, H - 0.05, z=zb + r_mat, sections=12))
    forme = int(a.rng.integers(0, 3))
    zp = zb + 2 * r_mat + 0.01
    ep = max(0.004, P / 2 - zp)
    yc = H - L / 2
    if forme == 0:
        poly = Point(0.0, yc).buffer(L / 2, resolution=12)
    elif forme == 1:
        poly = _rect_arrondi(-L / 2, H - L * 0.75, L / 2, H, 0.03)
    else:
        poly = Polygon([(-L / 2, H), (L / 2, H), (0.0, H - L * 0.866)]).buffer(-0.01).buffer(0.01, resolution=3)
    a("plaque", _panneau_xy(poly, zp, P / 2 - zp))
    a("mat", _panneau_xy(poly.boundary.buffer(0.02), zp + (P / 2 - zp) * 0.5, (P / 2 - zp) * 0.5 + 0.002))
    for y in (yc - L * 0.25, yc + L * 0.2):
        a("mat", _pave(-0.04, 0.04, y - 0.02, y + 0.02, zb + r_mat, zp))


def _b_fontaine(a: _Atelier) -> None:
    L, P, H = a.L, a.P, a.H
    R = min(L, P) / 2
    sections = 8 if a.style in ("classique", "industriel") else 40
    h_b = float(np.clip(0.18 * R + 0.25, 0.4, 0.7))
    e = 0.18
    a("structure", g.revolution([(0, 0), (R, 0), (R, h_b - 0.04), (R + 0.0, h_b), (R - e, h_b), (R - e, 0.12),
                                 (0, 0.12)], sections=sections))
    a("eau", g.cylindre(R - e - 0.005, 0.01, y=h_b - 0.12, sections=sections))
    if H < h_b + 0.35:
        a("structure", g.cylindre(0.08, H - 0.12, y=0.12, sections=12))
        return
    h_col = max(h_b + 0.1, H * 0.62)
    a("structure", g.revolution([(0, 0.12), (R * 0.2, 0.12), (R * 0.12, 0.3), (R * 0.07, h_col - 0.2), (R * 0.1, h_col - 0.08),
                                 (0, h_col - 0.08)], sections=16))
    r2 = min(R * 0.42, 0.9)
    a("structure", _coquille([(r2 * 0.25, 0.0), (r2 * 0.75, 0.05), (r2, 0.18), (r2, 0.22)], 0.04, y=h_col - 0.1,
                             sections=sections))
    a("structure", g.cylindre(r2 * 0.26, 0.04, y=h_col - 0.1, sections=16))
    a("eau", g.cylindre(r2 - 0.045, 0.008, y=h_col + 0.06, sections=sections))
    a("structure", g.revolution([(0, h_col), (0.07, h_col), (0.05, H - 0.15), (0.08, H - 0.1), (0.0, H)], sections=12))


def _b_table_pique_nique(a: _Atelier) -> None:
    L, P, H = a.L, a.P, a.H
    lt = min(0.8, P - 0.6)
    y_banc = 0.45
    zb_banc = P / 2 - 0.13
    for i in range(5):
        z0 = -lt / 2 + i * lt / 5
        a("structure", _arrondi(-L / 2, L / 2, H - 0.04, H, z0 + 0.004, z0 + lt / 5 - 0.004, 0.006))
    for s in (-1, 1):
        for k in range(2):
            z0 = s * zb_banc - 0.13 + k * 0.13
            a("structure", _arrondi(-L / 2 + 0.05, L / 2 - 0.05, y_banc - 0.04, y_banc, z0 + 0.004, z0 + 0.126, 0.006))
    for x in (-L / 2 + 0.3, L / 2 - 0.3):
        for s in (-1, 1):
            a("structure", g.segment((x, 0.02, s * (P / 2 - 0.05)), (x, H - 0.04, s * lt * 0.25), 0.035, sections=8))
        a("structure", _pave(x - 0.035, x + 0.035, y_banc - 0.12, y_banc - 0.04, -P / 2 + 0.01, P / 2 - 0.01))
        a("structure", _pave(x - 0.035, x + 0.035, H - 0.1, H - 0.04, -lt / 2, lt / 2))


def _roue(a: _Atelier, x: float, z: float, r: float, largeur: float, cote: int) -> None:
    """Pneu (profil arrondi) et jante, axe selon X ; `cote` = ±1 côté extérieur."""
    profil = [(r * 0.62, -largeur / 2), (r * 0.9, -largeur / 2), (r, -largeur * 0.3), (r, largeur * 0.3),
              (r * 0.9, largeur / 2), (r * 0.62, largeur / 2), (r * 0.62, -largeur / 2)]
    pneu = g.revolution([(rr, h + largeur / 2) for rr, h in profil], sections=20)
    pneu = g.translation(pneu, 0.0, -largeur / 2, 0.0)
    pneu = _tourner(pneu, [0, 0, 1], -math.pi / 2)
    a("pneus", g.translation(pneu, x, r, z))
    jante = g.revolution([(0, 0), (r * 0.64, 0), (r * 0.62, largeur * 0.82), (r * 0.25, largeur * 0.9), (0, largeur * 0.9)],
                         sections=20)
    jante = g.translation(jante, 0.0, -largeur * 0.45, 0.0)
    jante = _tourner(jante, [0, 0, 1], -math.pi / 2 * cote)
    a("jantes", g.translation(jante, x, r, z))


def _b_voiture(a: _Atelier) -> None:
    L, P, H = a.L, a.P, a.H
    r_roue = float(np.clip(0.19 * H + 0.03, 0.28, 0.34))
    garde = 0.16
    y_ceint = garde + 0.55
    zf, zr = P / 2, -P / 2
    rr = 0.07
    # caisse basse : capot qui plonge vers l'avant, coffre arrière
    caisse = [(sx * (L / 2 - rr) * (1.0 if y < garde + 0.2 else 0.965), y, z) for sx in (-1, 1) for (y, z) in (
        (garde + rr, zf - rr), (garde + rr + 0.02, zr + rr), (y_ceint - rr - 0.06, zf - rr - 0.02),
        (y_ceint - rr, zf - 0.5), (y_ceint - rr, zr + rr + 0.02), (y_ceint - rr - 0.03, zr + rr))]
    corps = _coque(caisse, rr, sub=1)
    # passages de roue : cylindres d'axe X soustraits à la caisse
    empattement = P * 0.62
    passages = []
    for sz in (-1, 1):
        zc = sz * empattement / 2 - 0.03 * sz
        cyl = trimesh.creation.cylinder(radius=r_roue + 0.03, height=L + 0.2, sections=24)
        cyl.apply_transform(trimesh.transformations.rotation_matrix(math.pi / 2, [0, 1, 0]))
        cyl.apply_translation([0.0, r_roue, zc])
        passages.append(cyl)
    a("carrosserie", _creuser(corps, trimesh.util.concatenate(passages), lissage=40.0))
    # habitacle vitré (pare-brise incliné), intérieur sombre, toit
    l_hab = L / 2 - 0.12
    z_av, z_ar = zf - 0.42 * P, zr + 0.16 * P
    y_toit = H
    r_h = 0.05
    hab = [(sx * l_hab, y, z) for sx in (-1, 1) for (y, z) in (
        (y_ceint - 0.02, z_av - 0.02), (y_ceint - 0.02, z_ar), (y_toit - r_h - 0.012, z_av - 0.42),
        (y_toit - r_h - 0.012, z_ar + 0.2))]
    hab = [(x, y, z) for x, y, z in hab]
    a("vitres", _coque([(x * 0.985, y, z) for x, y, z in hab], r_h, sub=1))
    a("interieur", _pave(-l_hab + 0.08, l_hab - 0.08, y_ceint - 0.05, y_toit - 0.18, z_ar + 0.12, z_av - 0.25))
    toit = [(sx * (l_hab - 0.04), y, z) for sx in (-1, 1) for (y, z) in (
        (y_toit - 0.03, z_av - 0.47), (y_toit - 0.03, z_ar + 0.24), (y_toit - 0.02, z_av - 0.5), (y_toit - 0.02, z_ar + 0.27))]
    a("carrosserie", _coque(toit, 0.02, sub=1))
    # montants de pare-brise et de lunette
    for sx in (-1, 1):
        a("carrosserie", g.segment((sx * l_hab, y_ceint - 0.02, z_av - 0.02), (sx * (l_hab - 0.03), y_toit - 0.03, z_av - 0.45),
                                   0.03, sections=8))
        a("carrosserie", g.segment((sx * l_hab, y_ceint - 0.02, z_ar + 0.0), (sx * (l_hab - 0.03), y_toit - 0.03, z_ar + 0.22),
                                   0.035, sections=8))
    # roues
    for sz in (-1, 1):
        for sx in (-1, 1):
            _roue(a, sx * (L / 2 - 0.11), sz * empattement / 2 - 0.03 * sz, r_roue, 0.2, sx)
    # optiques, boucliers, rétroviseurs
    for sx in (-1, 1):
        a("feux_avant", _arrondi(sx * (L / 2 - 0.12) - 0.13, sx * (L / 2 - 0.12) + 0.13, y_ceint - 0.2, y_ceint - 0.12,
                                 zf - 0.06, zf - 0.005, 0.02))
        a("feux_arriere", _arrondi(sx * (L / 2 - 0.1) - 0.11, sx * (L / 2 - 0.1) + 0.11, y_ceint - 0.14, y_ceint - 0.06,
                                   zr + 0.005, zr + 0.06, 0.02))
        a("carrosserie", _arrondi(sx * (L / 2 + 0.0) - (0.06 if sx > 0 else 0.0), sx * L / 2 + (0.06 if sx < 0 else 0.0),
                                  y_ceint + 0.05, y_ceint + 0.13, z_av - 0.1, z_av - 0.02, 0.02))
    a("interieur", _arrondi(-L / 2 + 0.05, L / 2 - 0.05, garde + 0.05, garde + 0.2, zf - 0.08, zf, 0.03))
    a("interieur", _arrondi(-L / 2 + 0.05, L / 2 - 0.05, garde + 0.05, garde + 0.2, zr, zr + 0.08, 0.03))
    a("interieur", _pave(-0.3, 0.3, y_ceint - 0.28, y_ceint - 0.2, zf - 0.03, zf - 0.005))


def _b_parasol(a: _Atelier) -> None:
    L, P, H = a.L, a.P, a.H
    R = min(L, P) / 2
    h_toile = min(0.55, 0.28 * R + 0.2)
    y_bord = H - 0.06 - h_toile
    a("mat", g.cylindre(0.24, 0.06, sections=20), g.cylindre(0.02, H - 0.06, y=0.06, sections=10))
    a("mat", g.sphere(0.035, y=H - 0.035, subdivisions=1))
    toile = _coquille([(R, y_bord), (R * 0.97, y_bord + 0.06), (R * 0.55, y_bord + h_toile * 0.7), (0.03, y_bord + h_toile)],
                      0.006, sections=8)
    a("toile", toile)
    a("toile", _coquille([(R, y_bord - 0.08), (R, y_bord + 0.01)], 0.004, sections=8))
    for k in range(8):
        ang = (k + 0.5) * math.pi / 4
        a("mat", g.segment((0.0, y_bord + h_toile - 0.04, 0.0), (R * 0.97 * math.sin(ang), y_bord - 0.005,
                                                                 R * 0.97 * math.cos(ang)), 0.006, sections=6))
        a("mat", g.segment((0.0, y_bord - 0.4, 0.0), (R * 0.5 * math.sin(ang), y_bord + h_toile * 0.35 - 0.02,
                                                      R * 0.5 * math.cos(ang)), 0.005, sections=6))


def _b_transat(a: _Atelier) -> None:
    L, P, H = a.L, a.P, a.H
    y_ch = 0.3 if H > 0.45 else max(0.15, H - 0.12)
    xi = L / 2 - 0.025
    l_dos = min(0.8, P * 0.42)
    ang = math.asin(float(np.clip((H - y_ch - 0.03) / l_dos, 0.05, 0.95)))
    z_art = -P / 2 + l_dos * math.cos(ang) + 0.02          # le dossier incliné tient dans la profondeur
    # longerons et pieds
    for sx in (-1, 1):
        a("structure", _pave(sx * xi - 0.02, sx * xi + 0.02, y_ch - 0.06, y_ch, z_art, P / 2))
        for z in (z_art + 0.08, P / 2 - 0.06):
            a("structure", _pave(sx * xi - 0.02, sx * xi + 0.02, 0.0, y_ch - 0.06, z - 0.025, z + 0.025))
    # toile de l'assise et dossier incliné (pivot à l'articulation)
    a("toile", _arrondi(-xi + 0.02, xi - 0.02, y_ch - 0.02, y_ch + 0.04, z_art, P / 2 - 0.02, 0.015))
    dos = _arrondi(-xi, xi, y_ch - 0.04, y_ch + 0.03, z_art - l_dos, z_art, 0.015)
    dos = _tourner(dos, [1, 0, 0], ang, (0.0, y_ch, z_art))
    a("toile", dos)
    for sx in (-1, 1):
        bras = _pave(sx * xi - 0.02, sx * xi + 0.02, y_ch - 0.06, y_ch, z_art - l_dos, z_art)
        a("structure", _tourner(bras, [1, 0, 0], ang, (0.0, y_ch, z_art)))
        bequille = g.segment((sx * xi, 0.0, -P / 2 + l_dos * 0.15), (sx * xi, y_ch + math.sin(ang) * l_dos * 0.5,
                                                                    z_art - math.cos(ang) * l_dos * 0.5), 0.015)
        a("structure", bequille)


# ── Végétation et minéral ──────────────────────────────────────────────────────────────────────────
def _cone_feuillu(rng: np.random.Generator, r: float, h: float, y0: float, bruit: float) -> trimesh.Trimesh:
    profil = [(0.0, 0.0), (r * 0.9, 0.0), (r, 0.08 * h), (r * 0.55, 0.5 * h), (r * 0.12, 0.92 * h), (0.0, h)]
    brut = trimesh.creation.revolve(np.array(profil), sections=16)
    brut.apply_transform(trimesh.transformations.rotation_matrix(-math.pi / 2, [1, 0, 0]))
    brut.apply_translation([0.0, y0, 0.0])
    return _bosseler(brut, bruit, rng)


def _b_arbre(a: _Atelier) -> None:
    L, P, H = a.L, a.P, a.H
    R = min(L, P) / 2
    s = a.style
    graine = lambda: int(a.rng.integers(1 << 30))  # noqa: E731
    if s == "conifere":
        h_tronc = H * 0.18
        rt = max(0.08, H * 0.022)
        a("tronc", _cone_entre((0, 0, 0), (0, H * 0.7, 0), rt, rt * 0.3, sections=10))
        n = int(np.clip(round(H / 2.2), 4, 7))
        for i in range(n):
            t = i / n
            y0 = h_tronc + t * (H - h_tronc) * 0.82
            r = R * (1.0 - 0.8 * t)
            hc = (H - y0) if i == n - 1 else (H - h_tronc) * 0.34
            a("feuillage", _cone_feuillu(a.rng, r, min(hc, H - y0), y0, 0.12))
        return
    if s == "palmier":
        rt = max(0.12, H * 0.018)
        courbe = a.u(0.08, 0.2) * H
        dirx = a.u(0, 2 * math.pi)
        n_seg = 8
        pts = []
        lf = R * 1.0
        h_stipe = H - 0.3 * lf
        for i in range(n_seg + 1):
            t = i / n_seg
            off = courbe * t * t
            pts.append((off * math.cos(dirx), t * h_stipe, off * math.sin(dirx)))
        for i in range(n_seg):
            r0 = rt * (1.25 - 0.4 * i / n_seg)
            a("tronc", _cone_entre(pts[i], pts[i + 1], r0, r0 * 0.93, sections=10))
            a("tronc", g.cylindre(r0 * 1.08, 0.06, x=pts[i][0], y=pts[i][1], z=pts[i][2], sections=10))
        sommet = np.array(pts[-1])
        a("tronc", g.sphere(rt * 1.4, x=sommet[0], y=sommet[1], z=sommet[2], subdivisions=1))
        n_f = int(a.rng.integers(11, 16))
        for k in range(n_f):                      # palmes adultes, arquées puis retombantes
            ang = k * 2 * math.pi / n_f + a.u(-0.15, 0.15)
            elev = a.u(0.2, 0.75)
            a("feuillage", _palme(sommet, ang, elev, lf * a.u(0.85, 1.0), lf * 0.2))
        for k in range(4):                        # jeunes palmes dressées au cœur
            ang = k * math.pi / 2 + a.u(0, 1.0)
            a("feuillage", _palme(sommet, ang, a.u(1.05, 1.3), lf * a.u(0.45, 0.6), lf * 0.12))
        return
    # feuillus, fruitiers, bouleaux : tronc effilé, charpentières, couronne de masses bosselées
    elance = s == "bouleau"
    h_tronc = H * {"fruitier": 0.3, "bouleau": 0.3}.get(s, 0.34)
    rt = max(0.06, H * (0.03 if not elance else 0.016))
    ry = (H - h_tronc) / 2
    yc = h_tronc + ry
    a("tronc", _cone_entre((0, 0, 0), (0, yc + 0.3 * ry, 0), rt, rt * 0.35, sections=12))
    a("tronc", g.revolution([(0, 0), (rt * 1.6, 0), (rt * 1.05, 0.25), (0, 0.3)], sections=12))
    n = {"fruitier": 5, "bouleau": 8}.get(s, 7) + int(a.rng.integers(0, 2))
    centres = _couronne(a, "feuillage", (0.0, yc, 0.0), R, ry, n, bruit=0.26 if elance else 0.22,
                        sub_peri=3 if n <= 8 else 2)
    for c in centres:
        if c[1] < yc - 0.6 * ry:
            continue
        depart = (0.0, h_tronc + a.u(0.15, 0.6) * ry, 0.0)
        a("tronc", _cone_entre(depart, (c[0] * 0.8, c[1], c[2] * 0.8), rt * 0.45, rt * 0.15, sections=8))
    if s == "fruitier":
        for k in range(int(a.rng.integers(18, 30))):
            th, ph = a.u(0, 2 * math.pi), a.u(0.35, 2.1)
            a("fruits", g.sphere(0.045, x=R * 0.9 * math.sin(ph) * math.cos(th), y=yc + ry * 0.9 * math.cos(ph),
                                 z=R * 0.9 * math.sin(ph) * math.sin(th), subdivisions=1))
    if elance:
        # lenticelles sombres sur l'écorce blanche
        h_fut = yc + 0.3 * ry
        for k in range(int(a.rng.integers(16, 26))):
            y = a.u(0.3, h_fut * 0.9)
            ang = a.u(0, 2 * math.pi)
            rloc = rt + (rt * 0.35 - rt) * y / h_fut
            m = _pave(-rloc * 0.5, rloc * 0.5, y, y + a.u(0.008, 0.02), rloc * 0.9, rloc + 0.004)
            a("marques", _tourner(m, [0, 1, 0], ang))


def _palme(sommet: np.ndarray, ang: float, elev: float, longueur: float, largeur: float) -> trimesh.Trimesh:
    """Palme de palmier : ruban en V, effilé, qui s'arque puis retombe (ballistique de la nervure)."""
    n = 16
    d = np.array([math.cos(ang), 0.0, math.sin(ang)])
    lat = np.array([-math.sin(ang), 0.0, math.cos(ang)])
    sommets, faces = [], []
    for i in range(n + 1):
        t = i / n
        horiz = t * longueur * math.cos(elev * 0.6)
        vert = t * longueur * math.sin(elev) - (t ** 2) * longueur * 0.75
        c = sommet + d * horiz + np.array([0.0, vert, 0.0])
        # folioles : bord en dents de scie (une foliole sur deux plus courte)
        w = largeur * math.sin(math.pi * min(1.0, t * 1.15 + 0.08)) * (1.0 - 0.5 * t) * (1.0 if i % 2 else 0.55)
        sommets += [c + lat * w - np.array([0, w * 0.35, 0]), c + np.array([0, 0.01, 0]), c - lat * w - np.array([0, w * 0.35, 0])]
    for i in range(n):
        b = 3 * i
        for j in range(2):
            faces += [[b + j, b + j + 3, b + j + 1], [b + j + 1, b + j + 3, b + j + 4]]
    m = trimesh.Trimesh(vertices=np.array(sommets), faces=np.array(faces), process=False)
    dos = trimesh.Trimesh(vertices=np.array(sommets) - np.array([0, 0.004, 0]), faces=np.array(faces)[:, ::-1],
                          process=False)
    return g.finaliser(trimesh.util.concatenate([m, dos]), lissage_deg=50.0)


def _b_buisson(a: _Atelier) -> None:
    L, P, H = a.L, a.P, a.H
    _couronne(a, "feuillage", (0.0, H / 2, 0.0), L / 2, H / 2, int(a.rng.integers(6, 9)), rz=P / 2, bruit=0.26,
              sub_peri=2, haut_min=-0.75)


def _b_rocher(a: _Atelier) -> None:
    L, P, H = a.L, a.P, a.H
    base = trimesh.creation.icosphere(subdivisions=2, radius=1.0)
    v = base.vertices.copy()
    defo = np.zeros(len(v))
    for octave in range(4):
        f = a.rng.normal(size=3) * (1.5 * 2 ** octave)
        defo += np.sin(v @ f + a.u(0, 6.28)) / (2 ** octave)
    v *= (1.0 + 0.18 * defo)[:, None]
    v[:, 1] = np.maximum(v[:, 1], -0.35)               # assise aplatie, enterrée
    v *= [L / 2, H / 1.35, P / 2]
    m = trimesh.Trimesh(vertices=v, faces=base.faces, process=True)
    a("surface", g.finaliser(m, lissage_deg=28.0))


# ── Table des constructeurs ────────────────────────────────────────────────────────────────────────
CONSTRUCTEURS: dict[str, Callable[[_Atelier], None]] = {
    "lit_simple": _b_lit, "lit_double": _b_lit, "table_de_chevet": _b_table_de_chevet, "armoire": _b_armoire,
    "commode": _b_commode, "canape": _b_canape, "fauteuil": _b_fauteuil, "table_basse": _b_table_basse,
    "meuble_tv": _b_meuble_tv, "television": _b_television, "bibliotheque": _b_bibliotheque,
    "etagere_murale": _b_etagere_murale, "tapis": _b_tapis, "lampadaire": _b_lampadaire,
    "lampe_de_table": _b_lampe_de_table, "suspension": _b_suspension, "plante_en_pot": _b_plante_en_pot,
    "tableau": _b_tableau, "miroir": _b_miroir, "console": _b_console, "cheminee": _b_cheminee, "piano": _b_piano,
    "table_a_manger": _b_table_a_manger, "chaise": _b_chaise, "bureau": _b_bureau, "buffet": _b_buffet,
    "banc": _b_banc, "porte_manteau": _b_porte_manteau, "plan_de_travail": _b_plan_de_travail,
    "placard_haut": _b_placard_haut, "ilot_cuisine": _b_ilot_cuisine, "refrigerateur": _b_refrigerateur,
    "cuisiniere": _b_cuisiniere, "hotte": _b_hotte, "lave_vaisselle": _b_lave_vaisselle, "lave_linge": _b_lave_linge,
    "baignoire": _b_baignoire, "douche": _b_douche, "lavabo": _b_lavabo, "wc": _b_wc,
    "lampadaire_rue": _b_lampadaire_rue, "banc_public": _b_banc_public, "poubelle_rue": _b_poubelle_rue,
    "abribus": _b_abribus, "feu_tricolore": _b_feu_tricolore, "panneau": _b_panneau, "fontaine": _b_fontaine,
    "table_pique_nique": _b_table_pique_nique, "voiture": _b_voiture, "parasol": _b_parasol, "transat": _b_transat,
    "arbre": _b_arbre, "buisson": _b_buisson, "rocher": _b_rocher,
}


# ── Résolution des paramètres ──────────────────────────────────────────────────────────────────────
def _borner(valeur: float, fourchette: tuple[float, float]) -> float:
    lo, hi = fourchette
    return float(np.clip(valeur, 0.7 * lo, 1.4 * hi))


# Allométrie (connaissance générale) : pour le végétal et le minéral, une dimension non donnée suit les
# autres au lieu d'être tirée indépendamment (un arbre de 4 m n'a pas une couronne de 9 m ; un rocher n'est
# ni une dalle ni une aiguille). Rapport largeur / hauteur de la couronne par essence (fourchette).
RAPPORT_COURONNE = {"feuillu": (0.55, 0.8), "conifere": (0.32, 0.45), "palmier": (0.5, 0.7),
                    "fruitier": (0.8, 1.05), "bouleau": (0.35, 0.5)}
RAPPORT_HAUTEUR_EMPRISE = {"buisson": (0.55, 1.0), "rocher": (0.3, 0.8), "plante_en_pot": (1.4, 2.6)}


def _dimensions(cat: dict[str, Any], categorie: str, tirages: np.ndarray, style: str, largeur: float | None,
                profondeur: float | None, hauteur: float | None) -> tuple[float, float, float]:
    lo_l, hi_l = cat["largeur"]
    lo_p, hi_p = cat["profondeur"]
    lo_h, hi_h = cat["hauteur"]
    L = _borner(largeur, cat["largeur"]) if largeur is not None else lo_l + tirages[0] * (hi_l - lo_l)
    P = _borner(profondeur, cat["profondeur"]) if profondeur is not None else lo_p + tirages[1] * (hi_p - lo_p)
    H = _borner(hauteur, cat["hauteur"]) if hauteur is not None else lo_h + tirages[2] * (hi_h - lo_h)
    if categorie in EMPRISE_RONDE:
        if largeur is None and profondeur is not None:
            L = P
        elif profondeur is None:
            P = float(np.clip(L, 0.7 * lo_p, 1.4 * hi_p))
    if categorie == "arbre" and style in RAPPORT_COURONNE:
        r0, r1 = RAPPORT_COURONNE[style]
        rapport = r0 + tirages[0] * (r1 - r0)
        if largeur is None and profondeur is None:
            L = P = float(np.clip(H * rapport, lo_l, hi_l))
        elif hauteur is None:
            H = float(np.clip(max(L, P) / rapport, lo_h, hi_h))
    elif categorie in RAPPORT_HAUTEUR_EMPRISE and hauteur is None:
        r0, r1 = RAPPORT_HAUTEUR_EMPRISE[categorie]
        H = float(np.clip((L + P) / 2 * (r0 + tirages[2] * (r1 - r0)), lo_h, hi_h))
    return L, P, H


def _resoudre_style(categorie: str, cat: dict[str, Any], style: str | None, rng: np.random.Generator) -> str:
    propres = tuple(cat.get("styles") or ())
    if propres:
        if style is None:
            return str(propres[int(rng.integers(0, len(propres)))])
        if style not in propres:
            raise KeyError(f"style {style!r} hors vocabulaire pour {categorie!r} (choix : {propres})")
        return style
    noms = tuple(STYLES_MEUBLES)
    if style is None:
        return noms[int(rng.integers(0, len(noms)))]
    if style not in STYLES_MEUBLES:
        raise KeyError(f"style de mobilier hors vocabulaire : {style!r} (choix : {noms})")
    return style


def _substituer(cle: str, emplacement: str, groupe: str, style: str) -> str:
    """Essence et métal du style pour un emplacement que le programme n'a pas fixé."""
    if groupe not in GROUPES_STYLES or style not in STYLES_MEUBLES:
        return cle
    sty = STYLES_MEUBLES[style]
    spec = voc.materiau(cle)
    if emplacement in EMPLACEMENTS_PIEDS and sty["pieds"]:
        return sty["pieds"]
    if spec["famille"] == "bois" and sty["bois"]:
        return sty["bois"]
    if spec["famille"] == "metal" and sty["metal"] and emplacement in ("poignees", "structure", "cadre", "pied"):
        return sty["metal"]
    if spec["famille"] == "tissu" and sty["tissu"] and emplacement == "structure" and groupe == "assise":
        return sty["tissu"]
    return cle


def _resoudre_materiaux(categorie: str, cat: dict[str, Any], style: str,
                        demandes: dict[str, str] | None) -> dict[str, str]:
    demandes = dict(demandes or {})
    secondaires = SECONDAIRES.get(categorie, {})
    connus = set(cat["materiaux"]) | set(secondaires)
    for emplacement, cle in demandes.items():
        if emplacement not in connus:
            raise KeyError(f"emplacement de matériau inconnu pour {categorie!r} : {emplacement!r} "
                           f"(connus : {sorted(connus)})")
        voc.materiau(cle)
    groupe = cat["groupe"]
    mats: dict[str, str] = {}
    for emplacement, defaut in cat["materiaux"].items():
        if emplacement in demandes:
            mats[emplacement] = demandes[emplacement]
            continue
        cle = _substituer(defaut, emplacement, groupe, style)
        if categorie == "arbre":
            cle = STYLES_ARBRES.get(style, {}).get(emplacement, cle)
        mats[emplacement] = cle
    for emplacement, defaut in secondaires.items():
        if emplacement in demandes:
            mats[emplacement] = demandes[emplacement]
            continue
        cle = mats[defaut[1:]] if defaut.startswith("=") else defaut
        if emplacement in EMPLACEMENTS_PIEDS:
            cle = _substituer(cle, emplacement, groupe, style)
        mats[emplacement] = cle
    for cle in mats.values():
        voc.materiau(cle)
    return mats


def _ajuster(pieces: list[tuple[str, str, trimesh.Trimesh]], L: float, P: float, H: float
             ) -> tuple[list[tuple[str, str, trimesh.Trimesh]], np.ndarray, np.ndarray]:
    """Loi d'ajustement : recentre l'emprise sur l'origine, pose le point bas à y = 0 et recale l'enveloppe
    sur les dimensions visées (facteurs d'échelle par axe, normales corrigées). Rend aussi l'enveloppe
    brute et les facteurs, mesure de fidélité du constructeur."""
    tous = np.vstack([np.asarray(m.vertices) for _, _, m in pieces])
    bas, haut = tous.min(axis=0), tous.max(axis=0)
    etendue = np.maximum(haut - bas, 1e-6)
    cible = np.array([L, H, P])
    facteurs = cible / etendue
    pivot = np.array([(bas[0] + haut[0]) / 2, bas[1], (bas[2] + haut[2]) / 2])
    sortie = []
    for emp, cle, m in pieces:
        m2 = _etirer(g.translation(m, *(-pivot)), *facteurs)
        sortie.append((emp, cle, m2))
    return sortie, etendue, facteurs


@dataclass
class Brouillon:
    """Résultat brut d'un constructeur avant ajustement (pour les tests de fidélité)."""
    atelier: _Atelier
    etendue_brute: np.ndarray
    facteurs: np.ndarray


def _construire(categorie: str, largeur: float | None, profondeur: float | None, hauteur: float | None,
                style: str | None, materiaux: dict[str, str] | None, graine: int) -> tuple[Objet, Brouillon]:
    cat = voc.categorie(categorie)
    rng = np.random.default_rng(graine)
    tirages = rng.uniform(size=3)        # toujours trois tirages : une dimension donnée ne décale pas les autres
    style_r = _resoudre_style(categorie, cat, style, rng)
    L, P, H = _dimensions(cat, categorie, tirages, style_r, largeur, profondeur, hauteur)
    mats = _resoudre_materiaux(categorie, cat, style_r, materiaux)
    atelier = _Atelier(categorie, L, P, H, style_r, mats, np.random.default_rng([graine, 7919]))
    CONSTRUCTEURS[categorie](atelier)
    hauteur_cible = H
    if atelier.hauteur_surface is not None:
        # objet dont un accessoire dépasse du plan (robinet) : l'enveloppe brute garde son dépassement
        tous = np.vstack([np.asarray(m.vertices) for _, _, m in atelier.pieces])
        hauteur_cible = float(tous[:, 1].max() - tous[:, 1].min())
    pieces, etendue, facteurs = _ajuster(atelier.pieces, L, P, hauteur_cible)
    groupes: dict[tuple[str, str], list[trimesh.Trimesh]] = {}
    for emp, cle, m in pieces:
        groupes.setdefault((emp, cle), []).append(m)
    parties = [Partie(g.fusionner(liste), cle, emp) for (emp, cle), liste in groupes.items()]
    tous = np.vstack([np.asarray(p.maillage.vertices) for p in parties])
    ext = tous.max(axis=0) - tous.min(axis=0)
    surfaces = []
    if cat["support"]:
        hs = H if atelier.hauteur_surface is not None else float(ext[1])
        surfaces.append(Surface(hauteur=hs, polygone=[(-ext[0] / 2, -ext[2] / 2), (ext[0] / 2, -ext[2] / 2),
                                                      (ext[0] / 2, ext[2] / 2), (-ext[0] / 2, ext[2] / 2)]))
    objet = Objet(nom=categorie, categorie=categorie, parties=parties, largeur=float(ext[0]),
                  profondeur=float(ext[2]), hauteur=float(ext[1]), degagement=float(cat["degagement"]),
                  degagement_cotes=float(cat["degagement_cotes"]), surfaces=surfaces, mural=bool(cat["mural"]),
                  plafond=bool(cat["plafond"]), sol_partage=bool(cat["sol_partage"]),
                  meta={"style": style_r, "graine": int(graine), "materiaux": dict(mats)})
    return objet, Brouillon(atelier, etendue, facteurs)


def generer(categorie: str, *, largeur: float | None = None, profondeur: float | None = None,
            hauteur: float | None = None, style: str | None = None, materiaux: dict[str, str] | None = None,
            graine: int = 0) -> Objet:
    """Construit un objet de la catégorie (clé de `vocabulaire.CATEGORIES`) dans son repère local.

    Dimensions non données : tirées dans la fourchette du vocabulaire (graine) ; données : respectées,
    bornées à [0,7 × min ; 1,4 × max]. `style` : style de mobilier (STYLES_MEUBLES) ou, pour les catégories
    qui ont leurs propres styles (arbre), l'un d'eux ; None → tiré. `materiaux` : emplacement → clé de
    matériau (validée), par-dessus les valeurs par défaut du vocabulaire et du style.
    """
    objet, _ = _construire(categorie, largeur, profondeur, hauteur, style, materiaux, graine)
    return objet


# ── Démonstration : catalogues rendus par f3d ──────────────────────────────────────────────────────
SORTIE_DEMO = "/home/juan/AuroraIA/application/output/3d/essais/monde/meubles"


def _catalogue(specs: Sequence[tuple[str, str | None, int]], *, ecart: float = 0.6, colonnes: int = 8,
               sol: str = "parquet_chene"):
    """Scène de catalogue : une grille d'objets (Instance) sur un sol ; muraux devant un pan de mur, suspensions
    sous un carré de plafond. `specs` : (catégorie, style ou None, graine)."""
    from monde.ir import Instance, Noeud, Pose, Scene
    objets = [generer(c, style=st, graine=gr) for c, st, gr in specs]
    rangs = [objets[i:i + colonnes] for i in range(0, len(objets), colonnes)]
    instances, parties = [], []
    z = 0.0
    largeur_max = 0.0
    for rang in rangs:
        prof = max(max(o.profondeur for o in rang), 0.5)
        z += prof / 2
        x = 0.0
        for o in rang:
            x += o.largeur / 2
            y = 0.0
            if o.mural:
                y = float(np.mean(voc.CATEGORIES[o.categorie]["hauteur_pose"]))
                parties.append(Partie(g.boite(o.largeur + 0.3, y + o.hauteur + 0.3, 0.08, x=x,
                                              z=z - o.profondeur / 2 - 0.04), "platre_peint", "mur"))
            if o.plafond:
                y = 2.5 - o.hauteur
                parties.append(Partie(g.boite(o.largeur + 0.3, 0.05, o.profondeur + 0.3, x=x, y=2.5, z=z),
                                      "platre_peint", "plafond"))
            instances.append(Instance(o, Pose(x=x, z=z, y=y), nom=f"{o.categorie}_{o.meta['style']}"))
            x += o.largeur / 2 + ecart
        largeur_max = max(largeur_max, x)
        z += prof / 2 + ecart * 1.6
    parties.append(Partie(g.plaque(g.rectangle_xz(-1.0, -1.5, largeur_max + 1.0, z + 0.5), 0.05), sol, "sol"))
    return Scene(Noeud("catalogue", parties=parties, instances=instances))


def demo(sortie: str = SORTIE_DEMO, resolution: tuple[int, int] = (1600, 1100)) -> dict[str, Any]:
    """Deux catalogues exportés en GLB et rendus par f3d (vue aérienne, rasante, plan) : tout le mobilier
    intérieur (un objet par catégorie, styles alternés) et tout l'extérieur (mobilier urbain, véhicule,
    minéral, buissons, puis les cinq essences d'arbres)."""
    from pathlib import Path
    from monde import export_gltf, rendu
    racine = Path(sortie)
    styles = tuple(STYLES_MEUBLES)
    interieur = [(c, styles[i % len(styles)], 0) for i, c in enumerate(sorted(
        (c for c, v in voc.CATEGORIES.items() if not v["exterieur"]), key=lambda c: voc.CATEGORIES[c]["groupe"]))]
    exterieur = [(c, None, 0) for c, v in voc.CATEGORIES.items() if v["exterieur"] and c != "arbre"]
    exterieur += [("arbre", s, 1) for s in voc.CATEGORIES["arbre"]["styles"]]
    rapport = {}
    for nom, specs, colonnes, sol, ecart in (("interieur", interieur, 9, "parquet_chene", 0.6),
                                             ("exterieur", exterieur, 8, "herbe", 1.2)):
        scene = _catalogue(specs, colonnes=colonnes, sol=sol, ecart=ecart)
        glb = racine / nom / f"{nom}.glb"
        stats = export_gltf.exporter(scene, glb, resolution=64)
        vues = rendu.rendre_vues(glb, racine / nom, vues=("aerienne_sud_est", "rasante", "plan"),
                                 resolution=resolution)
        rapport[nom] = {"glb": str(glb), "objets": stats["objets"], "triangles": stats["triangles"],
                        "planche": vues["planche"], "blanc_pur_max": vues["blanc_pur_max"]}
    return rapport


def _variantes(categorie: str) -> list[tuple[str | None, int]]:
    """Variantes montrées pour une catégorie : ses styles propres, les styles de mobilier si elle en dépend,
    sinon trois graines."""
    propres = voc.CATEGORIES[categorie].get("styles") or ()
    if propres:
        return [(s, 0) for s in propres]
    if voc.CATEGORIES[categorie]["groupe"] in GROUPES_STYLES or categorie in ("lavabo", "lampadaire_rue", "fontaine"):
        return [(s, i) for i, s in enumerate(STYLES_MEUBLES)]
    return [(None, i) for i in range(3)]


def inspecter(categories: Sequence[str], sortie: str = SORTIE_DEMO, nom: str = "inspection",
              resolution: tuple[int, int] = (760, 480)) -> str:
    """Une scène par catégorie (ses variantes côte à côte), rendue par f3d (vue aérienne + rasante), puis une
    mosaïque légendée de toutes les catégories : l'outil de contrôle visuel objet par objet."""
    from pathlib import Path
    from PIL import Image, ImageDraw
    from monde import export_gltf, rendu
    from monde.ir import Instance, Noeud, Pose, Scene
    racine = Path(sortie) / nom
    bandes = []
    for c in categories:
        objets = [generer(c, style=s, graine=gr) for s, gr in _variantes(c)]
        x = 0.0
        instances = []
        ecart = max(0.25, 0.25 * max(o.largeur for o in objets))
        for o in objets:
            x += o.largeur / 2
            y = float(np.mean(voc.CATEGORIES[c]["hauteur_pose"])) if o.mural else (1.0 if o.plafond else 0.0)
            instances.append(Instance(o, Pose(x=x, y=y), nom=f"{c}_{o.meta['style']}"))
            x += o.largeur / 2 + ecart
        prof = max(o.profondeur for o in objets)
        sol = "herbe" if voc.CATEGORIES[c]["exterieur"] else "parquet_chene"
        parties = [Partie(g.plaque(g.rectangle_xz(-ecart, -prof, x, prof), 0.02), sol, "sol")]
        scene = Scene(Noeud(c, parties=parties, instances=instances))
        glb = racine / c / f"{c}.glb"
        export_gltf.exporter(scene, glb, resolution=64)
        res = rendu.rendre_vues(glb, racine / c, vues=("aerienne_sud_est", "rasante"), resolution=resolution)
        if res["planche"]:
            image = Image.open(res["planche"]).convert("RGB")
            dessin = ImageDraw.Draw(image)
            legende = f"{c} : " + ", ".join(f"{o.meta['style']}" for o in objets)
            dessin.rectangle([0, 0, image.width, 26], fill=(24, 24, 24))
            dessin.text((8, 7), legende, fill=(255, 220, 120))
            bandes.append(image)
    if not bandes:
        return ""
    mosaique = Image.new("RGB", (max(b.width for b in bandes), sum(b.height for b in bandes)), (24, 24, 24))
    y = 0
    for b in bandes:
        mosaique.paste(b, (0, y))
        y += b.height
    chemin = racine / f"mosaique_{nom}.png"
    mosaique.save(chemin)
    return str(chemin)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Meubles paramétriques du moteur « monde »")
    parser.add_argument("--demo", action="store_true", help="catalogues GLB + planches f3d")
    parser.add_argument("--inspecter", nargs="*", help="mosaïques de contrôle par catégorie (toutes si vide)")
    parser.add_argument("--par", type=int, default=3, help="catégories par mosaïque")
    parser.add_argument("--sortie", default=SORTIE_DEMO)
    args = parser.parse_args(argv)
    if args.demo:
        import json
        print(json.dumps(demo(args.sortie), indent=2, ensure_ascii=False))
    if args.inspecter is not None:
        cats = args.inspecter or categories_disponibles()
        for i in range(0, len(cats), args.par):
            lot = cats[i:i + args.par]
            print(inspecter(lot, args.sortie, nom="inspection_" + "_".join(lot)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
