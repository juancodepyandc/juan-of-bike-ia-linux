"""Villes procédurales du moteur « monde » : réseau de rues, îlots, zones, parcelles, bâtiments, mobilier.

Toutes les lois sont générales (aucune règle par sujet ni par lieu) et tirent leurs paramètres des
vocabulaires fermés (ZONES_VILLE, STYLES_ARCHI, MATERIAUX, CATEGORIES) :

- RÉSEAU selon la trame : « grille » (pas d'îlot déduit des parcelles des zones demandées), « grille_irreguliere »
  (nœuds décalés, rues supprimées donc îlots fusionnés), « radiale » (anneaux et rayons autour d'un centre,
  rayons dédoublés quand l'arc devient trop long), « organique » (rues germes sinueuses puis découpe
  récursive de tout îlot trop grand par une rue courbe raccordée aux rues existantes). Toute rue a un profil :
  deux trottoirs de 2 à 4 m, des voies de circulation, du stationnement si la chaussée le permet.
- ÎLOTS = rectangle de la ville moins l'emprise des rues (et de la rivière avec ses quais) ; chaque îlot
  touche une rue. ZONES : chaque zone reçoit sa part de surface (± 15 %), les plus intenses (étages × commerce)
  au centre, les moins intenses en périphérie, la place au cœur, les parcs en îlots entiers à mi-distance ;
  un îlot frontière est coupé pour tenir les parts. L'EAU est une rivière qui traverse la ville, bordée de
  quais et de rues de quai ; les rues qui la franchissent sont des ponts espacés, les autres s'arrêtent au quai.
- PARCELLES par découpe récursive orientée (perpendiculaire au grand axe) jusqu'à la surface de parcelle
  de la zone ; une parcelle sans façade sur rue reste un jardin ou une cour.
- BÂTIMENTS dans le repère de la façade sur rue : retrait de la zone, écarts latéraux, profondeur bâtie ;
  formes rectangle, L (toujours sur une parcelle d'angle mitoyenne), U, cour, tour (socle + fût en retrait).
  Étages tirés dans la fourchette de la zone (plus hauts vers le centre), hauteur d'étage, toits et façades
  du style ; rez-de-chaussée en « vitrine » selon la part de commerce de la zone.
- UV DE FAÇADE (exception volontaire à la convention « UV en mètres » de `monde.ir`) : un carreau de matériau
  de façade = une travée × un étage. On écrit v (en mètres-motif) = (y − y_ref) × taille_m / hauteur_d_étage et
  u part de 0 à chaque coin de façade, mis à l'échelle pour qu'une façade compte un nombre ENTIER de travées.
  L'exporteur divisant par taille_m, chaque étage occupe exactement une rangée de fenêtres.
- RUES : chaussée en asphalte, pointillés de voies, passages piétons aux carrefours, trottoirs surélevés
  avec bordures ; lampadaires tous les ~30 m en quinconce tournés vers la chaussée ; arbres d'alignement tous
  les ~12 m le long des îlots qui en portent ; bancs et corbeilles de loin en loin ; voitures garées le long
  des bordures à stationnement, dans le sens de la circulation. PARCS : herbe, allées en gravier, arbres,
  bancs, fontaine ; PLACES : pavés, fontaine, bancs tournés vers elle, arbres en bordure.

Le mobilier et la végétation sont fabriqués par `fabrique(categorie, graine, options) -> Objet` (le vrai
générateur d'objets à l'intégration, `objet_provisoire` sinon) ; un petit nombre de variantes par catégorie
est réutilisé et le budget de triangles est tenu en éclaircissant la végétation (rapporté).
"""
from __future__ import annotations

import colorsys
import math
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import trimesh
from shapely import contains_xy
from shapely.geometry import LineString, MultiPolygon, Point, Polygon, box
from shapely.geometry.base import BaseGeometry
from shapely.ops import linemerge, substring, unary_union
from shapely.strtree import STRtree

from monde import geometrie as g
from monde import vocabulaire as voc
from monde.ir import Instance, Noeud, Objet, Partie, Pose
from monde.paysage import (Espece, Fabrique, _graine, disperser_positions, maillage_brut, objet_provisoire,
                           triangles_objet)

__all__ = ["ZoneDemandee", "PlanVille", "concevoir_ville", "construire_ville", "objet_provisoire",
           "maillage_batiment", "profil_rue"]

HAUT_TROTTOIR = 0.15            # dessus des trottoirs, îlots, quais (m) ; chaussée à 0
NIVEAU_RIVIERE = -1.8           # surface de l'eau
FOND_RIVIERE = -3.4
LARGEUR_QUAI = 4.0              # promenade de quai entre l'eau et la rue de quai
BUDGET_VILLE = 1_500_000

# Connaissances générales sur les zones (une ligne par clé de ZONES_VILLE, testé) — ce que le vocabulaire
# ne dit pas encore : sol de l'îlot, écart latéral entre bâtiments, profondeur bâtie (None : toute la
# parcelle), largeur maximale d'une maison, formes possibles, rues bordées d'arbres.
GABARITS_ZONE: dict[str, dict[str, Any]] = {
    "pavillonnaire": {"sol": "herbe", "ecart_lateral": 3.0, "profondeur_bati": (9.0, 12.0), "largeur_max": 14.0,
                      "formes": ("rect", "L"), "arbres_rue": True, "jardin": True},
    "residentiel": {"sol": "herbe", "ecart_lateral": 0.0, "profondeur_bati": (12.0, 16.0), "largeur_max": None,
                    "formes": ("rect", "L", "U", "cour"), "arbres_rue": True, "jardin": True},
    "centre": {"sol": "paves", "ecart_lateral": 0.0, "profondeur_bati": (14.0, 20.0), "largeur_max": None,
               "formes": ("rect", "L", "cour"), "arbres_rue": True, "jardin": False},
    "affaires": {"sol": "paves", "ecart_lateral": 10.0, "profondeur_bati": None, "largeur_max": None,
                 "formes": ("tour",), "arbres_rue": False, "jardin": False},
    "industriel": {"sol": "asphalte", "ecart_lateral": 6.0, "profondeur_bati": None, "largeur_max": None,
                   "formes": ("rect",), "arbres_rue": False, "jardin": False},
    "parc": {"sol": "herbe", "arbres_rue": True},
    "place": {"sol": "paves", "arbres_rue": True},
    "eau": {"sol": "terre", "arbres_rue": False},
}

# Matériau uni d'un matériau de façade (acrotères, pignons, lucarnes) : même famille, sans fenêtres.
MATERIAU_UNI = {"facade_enduit": "platre_peint", "facade_brique": "brique", "facade_pierre": "pierre",
                "facade_beton": "beton_cire", "facade_bois": "lambris", "mur_rideau": "metal_noir",
                "vitrine": "metal_noir"}
FACADES_TEINTABLES = ("facade_enduit",)        # l'enduit se peint ; pierre, brique et béton restent naturels
PENTES_TOITURE = {"tuile": (28.0, 38.0), "ardoise": (38.0, 50.0), "zinc": (25.0, 35.0)}
TEINTES_AUTOMOBILES = ("blanc", "noir", "gris", "gris_clair", "anthracite", "bleu_marine", "rouge", "bordeaux",
                       "bleu_nuit", "beige")
VEGETATION_PARC = [("arbre", "feuillu", 70.0), ("arbre", "bouleau", 12.0), ("buisson", None, 50.0)]
VEGETATION_JARDIN = [("arbre", "fruitier", 35.0), ("arbre", "feuillu", 15.0), ("buisson", None, 80.0)]
ETAGES_TOUR = 9                 # à partir de là : toit plat, façade de tour, socle et fût


# ── Programme ──────────────────────────────────────────────────────────────────────────────────────
@dataclass
class ZoneDemandee:
    type: str
    part: float

    def __post_init__(self) -> None:
        if self.type not in voc.ZONES_VILLE:
            raise KeyError(f"zone de ville hors vocabulaire : {self.type!r}")
        if not (self.part > 0):
            raise ValueError(f"part de zone non positive : {self.part!r}")


def profil_rue(largeur: float) -> dict[str, Any]:
    """Profil en travers d'une rue de `largeur` m : trottoirs (2-4 m), chaussée, voies, stationnement."""
    trottoir = float(np.clip(largeur / 6.0, 2.0, 4.0))
    chaussee = max(3.0, largeur - 2.0 * trottoir)
    stationnement = 2 if chaussee >= 10.0 else (1 if chaussee >= 8.0 else 0)
    reste = chaussee - 2.1 * stationnement
    voies = max(1 if reste < 5.5 else 2, int(reste // 3.0))
    if voies > 2 and voies % 2:
        voies -= 1                                     # sens équilibrés
    return {"largeur": float(largeur), "trottoir": trottoir, "chaussee": chaussee, "voies": voies,
            "largeur_voie": reste / voies, "stationnement": stationnement}


# ── Plan ───────────────────────────────────────────────────────────────────────────────────────────
@dataclass
class Rue:
    ligne: LineString
    largeur: float
    rang: str = "secondaire"            # principale | secondaire | quai
    pont: bool = False

    @property
    def profil(self) -> dict[str, Any]:
        return profil_rue(self.largeur)


@dataclass
class Volume:
    """Pavé orienté d'un bâtiment : centre (cx, cz), axe u d'angle `theta` (longueur `lu`), axe v à +90°
    (profondeur `lv`), de y0 à y1, coiffé de `toit` (None : couvert par un autre volume).
    `libre` : prisme sur un polygone quelconque (bande bâtie le long d'une rue courbe, cour) — seuls les toits
    plat, terrasse et mansarde s'y appliquent ; les toits à pans exigent un pavé."""
    cx: float
    cz: float
    theta: float
    lu: float
    lv: float
    y0: float
    y1: float
    toit: str | None
    libre: Polygon | None = None

    @property
    def axes(self) -> tuple[np.ndarray, np.ndarray]:
        t = np.array([math.cos(self.theta), math.sin(self.theta)])
        return t, np.array([-t[1], t[0]])

    def coins(self) -> np.ndarray:
        t, n = self.axes
        c = np.array([self.cx, self.cz])
        hu, hv = self.lu / 2.0, self.lv / 2.0
        return np.array([c - hu * t - hv * n, c + hu * t - hv * n, c + hu * t + hv * n, c - hu * t + hv * n])

    @property
    def polygone(self) -> Polygon:
        return self.libre if self.libre is not None else Polygon(self.coins())


@dataclass
class Batiment:
    volumes: list[Volume]
    etages: int
    hauteur_etage: float
    hauteur_rdc: float
    facade: str
    toiture: str
    toit: str
    commerce: bool
    forme: str
    base: float = HAUT_TROTTOIR
    # maison VISITABLE (monde.univers) : un logement planifié et meublé, aux vrais murs percés, remplace
    # l'enveloppe ; seule la couverture reste dessinée ici
    visitable: bool = False

    @property
    def emprise(self) -> Polygon:
        return unary_union([v.polygone for v in self.volumes])

    @property
    def hauteur(self) -> float:
        return max(v.y1 for v in self.volumes) - self.base


@dataclass
class Lot:
    polygone: Polygon
    batiment: Batiment | None = None


@dataclass
class Ilot:
    polygone: Polygon
    zone: str = ""
    lots: list[Lot] = field(default_factory=list)
    distance: float = 0.0               # du centre de la ville (centroïde), en m


@dataclass
class Placement:
    """Objet à poser : catégorie du vocabulaire, position (x, z), lacet (face, voir monde.ir), options."""
    categorie: str
    x: float
    z: float
    lacet: float
    options: dict = field(default_factory=dict)
    y: float = HAUT_TROTTOIR


@dataclass
class PlanVille:
    taille: tuple[float, float]
    trame: str
    style: str
    graine: int
    rues: list[Rue]
    chaussee: BaseGeometry
    trottoirs: BaseGeometry
    emprise_rues: BaseGeometry
    ilots: list[Ilot]
    eau: Polygon | None
    quais: BaseGeometry | None
    ponts: list[dict]
    intersections: list[tuple[float, float]]
    segments: list[dict]
    passages: list[Polygon]
    marquages: list[Polygon]
    allees: BaseGeometry | None
    mobilier: list[Placement]
    parts_demandees: dict[str, float]
    parts_mesurees: dict[str, float]
    centre: tuple[float, float] = (0.0, 0.0)
    options: dict = field(default_factory=dict)
    rapport: dict = field(default_factory=dict)

    @property
    def rectangle(self) -> Polygon:
        w, d = self.taille
        return box(-w / 2.0, -d / 2.0, w / 2.0, d / 2.0)

    def batiments(self) -> list[tuple[Ilot, Lot, Batiment]]:
        return [(i, l, l.batiment) for i in self.ilots for l in i.lots if l.batiment is not None]


# ── Outils géométriques ────────────────────────────────────────────────────────────────────────────
def _polygones(geom) -> list[Polygon]:
    if geom is None or geom.is_empty:
        return []
    if isinstance(geom, Polygon):
        return [geom]
    if isinstance(geom, MultiPolygon):
        return list(geom.geoms)
    return [p for p in getattr(geom, "geoms", []) if isinstance(p, Polygon)]


def _lignes(geom) -> list[LineString]:
    if geom is None or geom.is_empty:
        return []
    if isinstance(geom, LineString):
        return [geom]
    sortie = []
    for p in getattr(geom, "geoms", []):
        sortie.extend(_lignes(p))
    return sortie


def _grand_axe(poly: Polygon) -> tuple[np.ndarray, float, float]:
    """Direction unitaire du grand côté du rectangle orienté minimal, longueur et largeur."""
    mrr = poly.minimum_rotated_rectangle
    c = np.asarray(mrr.exterior.coords)[:4]
    a, b = c[1] - c[0], c[2] - c[1]
    la, lb = float(np.hypot(*a)), float(np.hypot(*b))
    if la >= lb:
        return a / max(la, 1e-12), la, lb
    return b / max(lb, 1e-12), lb, la


def _demi_plan(point: np.ndarray, normale: np.ndarray, etendue: float) -> Polygon:
    """Demi-plan {p : (p − point)·normale ≥ 0} borné à `etendue`."""
    t = np.array([-normale[1], normale[0]])
    p = np.asarray(point)
    return Polygon([p - t * etendue, p + t * etendue, p + t * etendue + normale * etendue,
                    p - t * etendue + normale * etendue])


def _couper(poly: Polygon, fraction: float, axe: np.ndarray | None = None) -> tuple[Polygon, Polygon] | None:
    """Coupe perpendiculairement au grand axe pour que la première part fasse `fraction` de l'aire."""
    if axe is None:
        axe, _, _ = _grand_axe(poly)
    pts = np.asarray(poly.exterior.coords)
    proj = pts @ axe
    lo, hi = float(proj.min()), float(proj.max())
    etendue = 4.0 * (hi - lo + 10.0)
    centre = np.asarray(poly.centroid.coords[0])
    base = centre - (centre @ axe) * axe
    a, b = lo, hi
    for _ in range(32):
        m = 0.5 * (a + b)
        gauche = poly.difference(_demi_plan(base + m * axe, axe, etendue))
        if gauche.area / poly.area < fraction:
            a = m
        else:
            b = m
    m = 0.5 * (a + b)
    gauche = poly.difference(_demi_plan(base + m * axe, axe, etendue))
    droite = poly.intersection(_demi_plan(base + m * axe, axe, etendue))
    pg, pd = _polygones(gauche), _polygones(droite)
    if not pg or not pd:
        return None
    return max(pg, key=lambda p: p.area), max(pd, key=lambda p: p.area)


def _orienter_up(faces: np.ndarray, sommets: np.ndarray, normale: np.ndarray) -> np.ndarray:
    """Retourne les faces dont l'ordre ne donne pas la normale voulue."""
    faces = np.asarray(faces).copy()
    v = sommets[faces]
    nf = np.cross(v[:, 1] - v[:, 0], v[:, 2] - v[:, 0])
    mauvais = (nf @ normale) < 0
    faces[mauvais] = faces[mauvais][:, ::-1]
    return faces


def dalle_plate(geom, y: float) -> trimesh.Trimesh:
    """Surface horizontale sans épaisseur (marquages, chaussée, toits) à y, normale +Y, UV (x, −z) m."""
    morceaux = []
    for poly in _polygones(geom):
        if poly.area < 1e-4:
            continue
        v2, f = trimesh.creation.triangulate_polygon(poly)
        v2 = np.asarray(v2, dtype=np.float64)
        if not len(f):
            continue
        v = np.column_stack([v2[:, 0], np.full(len(v2), y), v2[:, 1]])
        f = _orienter_up(np.asarray(f), v, np.array([0.0, 1.0, 0.0]))
        morceaux.append(maillage_brut(v, f, np.tile([0.0, 1.0, 0.0], (len(v), 1)), np.column_stack([v2[:, 0], -v2[:, 1]])))
    return g.fusionner(morceaux)


def dalle(geom, y_dessus: float, epaisseur: float) -> trimesh.Trimesh:
    """Dalle (trottoir, îlot, quai) : dessus à y_dessus, chants verticaux (les bordures)."""
    return g.fusionner([g.plaque(p, epaisseur, y=y_dessus) for p in _polygones(geom) if p.area > 1e-3])


def _quad(p0, p1, p2, p3, normale, uv) -> trimesh.Trimesh:
    v = np.array([p0, p1, p2, p3], dtype=np.float64)
    f = _orienter_up(np.array([[0, 1, 2], [0, 2, 3]]), v, np.asarray(normale, dtype=np.float64))
    return maillage_brut(v, f, np.tile(normale, (4, 1)), np.asarray(uv, dtype=np.float64))


def _repere(m: trimesh.Trimesh, cx: float, cz: float, theta: float) -> trimesh.Trimesh:
    """Local (x le long de u, z le long de v = u tourné de +90° dans le plan (x, z)) → monde. Rotation propre :
    l'ordre des faces et les normales restent cohérents."""
    if m is None or not len(m.faces):
        return m
    c, s = math.cos(theta), math.sin(theta)
    R = np.array([[c, 0.0, -s], [0.0, 1.0, 0.0], [s, 0.0, c]])     # colonnes : u, y, v  (v = (−s, c))
    v = np.asarray(m.vertices) @ R.T + np.array([cx, 0.0, cz])
    nrm = np.asarray(m.vertex_normals) @ R.T
    uv = getattr(m.visual, "uv", None)
    return maillage_brut(v, m.faces, nrm, np.zeros((len(v), 2)) if uv is None else uv)


# ── Réseaux de rues ────────────────────────────────────────────────────────────────────────────────
def _parcelle_moyenne(zones: list[ZoneDemandee]) -> float:
    """Moyenne GÉOMÉTRIQUE pondérée des parcelles des zones bâties : une zone à très grandes parcelles
    (tours, entrepôts) ne doit pas imposer ses îlots géants à toute la ville."""
    baties = [(z, voc.ZONES_VILLE[z.type]) for z in zones if voc.ZONES_VILLE[z.type]["batie"]]
    if not baties:
        return 900.0
    total = sum(z.part for z, _ in baties)
    return math.exp(sum(z.part * math.log(0.5 * (s["parcelle"][0] + s["parcelle"][1])) for z, s in baties) / total)


def dimensions_ilot(zones: list[ZoneDemandee]) -> tuple[float, float]:
    """(longueur, profondeur) d'îlot : deux rangées de parcelles moyennes (façade f, profondeur 1,25 f),
    bornées aux îlots urbains réels (40-110 m de profondeur, 60-170 m de longueur)."""
    a = _parcelle_moyenne(zones)
    facade = math.sqrt(a / 1.25)
    profondeur = float(np.clip(2.0 * 1.25 * facade, 40.0, 110.0))
    longueur = float(np.clip(1.6 * profondeur, 60.0, 170.0))
    return longueur, profondeur


def _trame_grille(W: float, D: float, lx: float, lz: float, largeur: float, rng: np.random.Generator,
                  irreguliere: bool) -> list[tuple[LineString, str]]:
    """Treillis de rues : chaque axe est divisé en un nombre ENTIER d'îlots (pas d'îlot rogné en bordure) ;
    la rue la plus proche du centre est principale. Irrégulière : nœuds décalés, rues retirées."""
    nx, nz = max(1, int(round(W / (lx + largeur)))), max(1, int(round(D / (lz + largeur))))
    xs = [-W / 2.0 + W * i / nx for i in range(nx + 1)]
    zs = [-D / 2.0 + D * j / nz for j in range(nz + 1)]
    i_princ = min(range(1, nx), key=lambda i: abs(xs[i]), default=-1)
    j_princ = min(range(1, nz), key=lambda j: abs(zs[j]), default=-1)
    noeuds = {}
    for i, x in enumerate(xs):
        for j, z in enumerate(zs):
            if irreguliere and 0 < i < nx and 0 < j < nz:
                x2, z2 = x + rng.normal(0.0, 0.1 * W / nx), z + rng.normal(0.0, 0.1 * D / nz)
            elif irreguliere and (0 < i < nx or 0 < j < nz):       # sur un bord : glisse le long du bord
                x2 = x + (rng.normal(0.0, 0.1 * W / nx) if 0 < i < nx else 0.0)
                z2 = z + (rng.normal(0.0, 0.1 * D / nz) if 0 < j < nz else 0.0)
            else:
                x2, z2 = x, z
            noeuds[(i, j)] = (x2, z2)
    aretes = []
    for (i, j) in noeuds:
        for di, dj in ((1, 0), (0, 1)):
            if (i + di, j + dj) not in noeuds:
                continue
            if (dj == 1 and i in (0, nx)) or (di == 1 and j in (0, nz)):
                continue                                        # pas de rue le long du bord de la ville
            principale = (di == 1 and j == j_princ) or (dj == 1 and i == i_princ)
            aretes.append(((i, j), (i + di, j + dj), principale))
    if irreguliere:
        import networkx as nx
        graphe = nx.Graph()
        graphe.add_edges_from((a, b) for a, b, _ in aretes)
        touches: set = set()
        retirees = set()
        ordre = rng.permutation(len(aretes))
        for k in ordre:
            a, b, principale = aretes[k]
            interieur = all(abs(noeuds[n][0]) < W / 2.0 - 10 and abs(noeuds[n][1]) < D / 2.0 - 10 for n in (a, b))
            if principale or not interieur or a in touches or b in touches or rng.random() > 0.22:
                continue
            graphe.remove_edge(a, b)
            if nx.is_connected(graphe) and graphe.degree(a) >= 2 and graphe.degree(b) >= 2:
                retirees.add(k)
                touches.update((a, b))
            else:
                graphe.add_edge(a, b)
        aretes = [a for k, a in enumerate(aretes) if k not in retirees]
    # Une rue = une ligne du treillis, d'un seul tenant tant qu'aucune arête n'en a été retirée.
    groupes: dict[tuple, list] = defaultdict(list)
    for a, b, p in aretes:
        cle = ("x", a[0]) if a[0] == b[0] else ("z", a[1])
        groupes[cle].append((a, b, p))
    sortie = []
    for cle, liste in groupes.items():
        fusion = linemerge([LineString([noeuds[a], noeuds[b]]) for a, b, _ in liste])
        rang = "principale" if any(p for _, _, p in liste) else "secondaire"
        sortie.extend((l, rang) for l in _lignes(fusion))
    return sortie


def _cercle(r: float, theta0: float = 0.0, pas: float = 8.0) -> LineString:
    n = max(16, int(2 * math.pi * r / pas))
    t = theta0 + np.linspace(0.0, 2 * math.pi, n + 1)
    return LineString(np.column_stack([r * np.cos(t), r * np.sin(t)]))


def _trame_radiale(W: float, D: float, longueur: float, profondeur: float, largeur: float,
                   rng: np.random.Generator) -> list[tuple[LineString, str]]:
    r_max = math.hypot(W, D) / 2.0 + largeur
    r0 = float(np.clip(0.45 * profondeur, 18.0, 40.0))
    pas = profondeur + largeur
    rayons = []
    r = r0
    while r < r_max:
        rayons.append(r)
        r += pas
    theta0 = rng.uniform(0.0, 2 * math.pi)
    lignes = [(_cercle(r, theta0), "secondaire") for r in rayons]
    n = 8 if 2 * math.pi * r0 / 8 > 0.0 else 6
    angles = [theta0 + 2 * math.pi * k / n for k in range(n)]
    debut = {a: r0 for a in angles}
    for r in rayons[1:]:
        if 2 * math.pi * r / len(angles) > 1.6 * longueur:
            nouveaux = [a + math.pi / len(angles) for a in angles]
            for a in nouveaux:
                debut[a] = r
            angles = sorted(angles + nouveaux)
    for a in angles:
        d = np.array([math.cos(a), math.sin(a)])
        lignes.append((LineString([d * debut[a], d * r_max]), "principale" if debut[a] == r0 else "secondaire"))
    return lignes


def _marche(depart: np.ndarray, cap: float, rect: Polygon, rng: np.random.Generator, pas: float = 20.0,
            bruit_deg: float = 7.0) -> list[np.ndarray]:
    pts = [depart]
    p = depart.copy()
    for _ in range(400):
        cap += math.radians(rng.normal(0.0, bruit_deg))
        p = p + pas * np.array([math.cos(cap), math.sin(cap)])
        pts.append(p.copy())
        if not rect.buffer(30.0).contains(Point(p)):
            break
    return pts


def _trame_organique(W: float, D: float, longueur: float, profondeur: float, largeur: float,
                     rng: np.random.Generator) -> list[tuple[LineString, str]]:
    rect = box(-W / 2.0, -D / 2.0, W / 2.0, D / 2.0)
    lignes: list[tuple[LineString, str]] = []
    cap0 = rng.uniform(0, math.pi)
    for k in range(2):
        cap = cap0 + k * math.pi / 2.0 + rng.normal(0, 0.2)
        depart = rng.normal(0.0, 0.08 * min(W, D), 2)
        aller = _marche(depart, cap, rect, rng)
        retour = _marche(depart, cap + math.pi, rect, rng)
        lignes.append((LineString(retour[::-1] + aller[1:]), "principale"))
    aire_max = longueur * profondeur
    reseau = unary_union([l for l, _ in lignes] + [rect.exterior])
    ilots = [p for p in _polygones(rect.difference(unary_union([l.buffer(largeur / 2.0) for l, _ in lignes])))]
    essais = 0
    while essais < 400:
        essais += 1
        facteurs = [0.75 + 0.6 * ((_graine(round(p.centroid.x), round(p.centroid.y)) % 1000) / 1000.0) for p in ilots]
        grands = [(p.area / f, p) for p, f in zip(ilots, facteurs) if p.area > aire_max * f]
        if not grands:
            break
        _, b = max(grands, key=lambda t: t[0])
        axe, la, lb = _grand_axe(b)
        perp = np.array([-axe[1], axe[0]])
        c = np.asarray(b.representative_point().coords[0]) if not b.contains(b.centroid) else np.asarray(b.centroid.coords[0])
        angle = math.radians(rng.normal(0.0, 12.0))
        d = perp * math.cos(angle) + axe * math.sin(angle)
        n = np.array([-d[1], d[0]])
        T = lb + 2.0 * largeur
        t = np.linspace(-1.6, 1.6, 17) * T
        courbure = rng.normal(0.0, 0.08) * T
        pts = c[None, :] + t[:, None] * d[None, :] + (courbure * (t / T) ** 2)[:, None] * n[None, :]
        longue = LineString(pts)
        inter = longue.intersection(reseau)
        candidats = [q for q in getattr(inter, "geoms", [inter]) if not q.is_empty]
        params = sorted(longue.project(Point(q.coords[0])) for q in candidats if hasattr(q, "coords"))
        milieu = longue.project(Point(c))
        avant = [p for p in params if p < milieu - 1.0]
        apres = [p for p in params if p > milieu + 1.0]
        ilots.remove(b)
        if not avant or not apres:
            continue
        rue = substring(longue, avant[-1], apres[0])
        if rue.length < 15.0:
            continue
        lignes.append((rue, "secondaire"))
        reseau = unary_union([reseau, rue])
        ilots.extend(p for p in _polygones(b.difference(rue.buffer(largeur / 2.0))) if p.area > 50.0)
    return lignes


# ── Rivière ────────────────────────────────────────────────────────────────────────────────────────
def _courbe_riviere(W: float, D: float, rng: np.random.Generator) -> LineString:
    long_x = rng.random() < 0.5
    L, l = (W, D) if long_x else (D, W)
    t = np.linspace(-0.7 * L, 0.7 * L, 80)
    angle = rng.normal(0.0, 0.25)
    amp = rng.uniform(0.05, 0.1) * l
    lam = rng.uniform(0.9, 1.4) * L
    ph = rng.uniform(0, 2 * math.pi)
    off = rng.uniform(-0.12, 0.12) * l + amp * np.sin(2 * math.pi * t / lam + ph)
    u = np.array([math.cos(angle), math.sin(angle)])
    v = np.array([-u[1], u[0]])
    pts = t[:, None] * u[None, :] + off[:, None] * v[None, :]
    if not long_x:
        pts = pts[:, ::-1]
    return LineString(pts)


# ── Zones ──────────────────────────────────────────────────────────────────────────────────────────
def intensite_zone(zone: str) -> float:
    """Intensité urbaine d'une zone bâtie (log des étages moyens + part de commerce) : plus c'est intense,
    plus près du centre. Place : cœur ; parc : mi-distance (traité à part) ; eau : hors classement."""
    s = voc.ZONES_VILLE[zone]
    if zone == "place":
        return 10.0
    if not s["batie"]:
        return -1.0
    return math.log1p(0.5 * (s["etages"][0] + s["etages"][1])) + s["commerce"]


def _affecter_zones(ilots: list[Ilot], cibles: dict[str, float], centre: np.ndarray, rmax: float,
                    rng: np.random.Generator) -> list[Ilot]:
    """Affecte une zone à chaque îlot pour approcher les aires cibles (m²). Îlots entiers d'abord ; un
    îlot frontière est coupé (perpendiculairement à son grand axe) quand cela rapproche de la cible."""
    libres = sorted(ilots, key=lambda i: i.distance)
    affectes: list[Ilot] = []
    reste = {z: a for z, a in cibles.items()}

    def prendre(ilot: Ilot, zone: str) -> None:
        ilot.zone = zone
        affectes.append(ilot)
        reste[zone] -= ilot.polygone.area
        libres.remove(ilot)

    def couper_et_prendre(ilot: Ilot, zone: str, besoin: float) -> bool:
        f = besoin / ilot.polygone.area
        if not (0.15 < f < 0.85) or besoin < 600.0:
            return False
        parts = _couper(ilot.polygone, f)
        if parts is None:
            return False
        a, b = parts
        # la part prise est la plus proche du centre de la zone voulue (près du centre si intense)
        da, db = Point(a.centroid).distance(Point(centre)), Point(b.centroid).distance(Point(centre))
        prise, laissee = (a, b) if (da <= db) == (intensite_zone(zone) >= 1.5) else (b, a)
        if prise is b:
            parts2 = _couper(ilot.polygone, 1.0 - f)
            if parts2 is None:
                return False
            laissee, prise = parts2
        i1 = Ilot(prise, zone, distance=Point(prise.centroid).distance(Point(centre)))
        i2 = Ilot(laissee, "", distance=Point(laissee.centroid).distance(Point(centre)))
        libres.remove(ilot)
        libres.append(i2)
        libres.sort(key=lambda i: i.distance)
        i1.zone = zone
        affectes.append(i1)
        reste[zone] -= prise.area
        return True

    # Place(s) : les îlots les plus centraux dont l'aire approche la cible.
    def entier_ou_coupe(ilot: Ilot, zone: str) -> bool:
        """Prend l'îlot entier s'il tient dans la cible (+10 %), sinon le coupe ; à défaut, le prend entier
        seulement si cela rapproche de la cible. Rend False quand la zone est servie."""
        a, besoin = ilot.polygone.area, reste[zone]
        if a <= 1.1 * besoin:
            prendre(ilot, zone)
            return True
        if couper_et_prendre(ilot, zone, besoin):
            return False
        if a - besoin < besoin:
            prendre(ilot, zone)
        return False

    if "place" in reste:
        while reste["place"] > 300.0 and libres:
            candidats = libres[: max(3, len(libres) // 6)]
            meilleur = min(candidats, key=lambda i: abs(i.polygone.area - reste["place"]) + 0.5 * i.distance)
            if not entier_ou_coupe(meilleur, "place"):
                break
    # Parcs : îlots ENTIERS à mi-distance, éloignés les uns des autres.
    if "parc" in reste:
        parcs: list[Ilot] = []
        while reste["parc"] > 0.08 * cibles["parc"] and libres:
            def score(i: Ilot) -> float:
                ecart = abs(i.polygone.area - reste["parc"]) / max(reste["parc"], 1.0)
                mi = abs(i.distance / max(rmax, 1.0) - 0.45)
                eloigne = min((Point(i.polygone.centroid).distance(p.polygone.centroid) for p in parcs), default=rmax)
                return ecart + mi - 0.5 * eloigne / max(rmax, 1.0)
            meilleur = min(libres, key=score)
            a_m, besoin = meilleur.polygone.area, reste["parc"]
            if a_m <= 1.15 * besoin:                          # un îlot entier tient dans la tolérance
                prendre(meilleur, "parc")
                parcs.append(meilleur)
                continue
            if couper_et_prendre(meilleur, "parc", besoin):   # sinon le parc ne prend qu'une part de l'îlot
                parcs.append(affectes[-1])
                break
            if a_m - besoin < besoin:
                prendre(meilleur, "parc")
                parcs.append(meilleur)
            break
    # Zones bâties : par intensité décroissante, du centre vers la périphérie.
    baties = sorted((z for z in reste if voc.ZONES_VILLE[z]["batie"]), key=lambda z: -intensite_zone(z))
    for k, zone in enumerate(baties):
        derniere = k == len(baties) - 1
        while libres and (derniere or reste[zone] > 0.05 * cibles[zone]):
            ilot = libres[0] if intensite_zone(zone) >= 1.0 or derniere else libres[-1]
            a = ilot.polygone.area
            if derniere or a <= reste[zone] + 0.08 * cibles[zone]:      # l'îlot entier reste dans la tolérance
                prendre(ilot, zone)
                continue
            if not couper_et_prendre(ilot, zone, reste[zone]) and a - reste[zone] < reste[zone]:
                prendre(ilot, zone)                                     # entier : plus juste que rien
            break
    # Reliquats : à la zone bâtie la plus déficitaire (ou à la plus intense).
    for ilot in list(libres):
        zone = max(baties, key=lambda z: reste[z]) if baties else next(iter(cibles))
        prendre(ilot, zone)
    return affectes


# ── Parcelles et bâtiments ─────────────────────────────────────────────────────────────────────────
def _lotir(ilot: Polygon, amin: float, amax: float, rng: np.random.Generator, profondeur: int = 0) -> list[Polygon]:
    if ilot.area <= amax or profondeur > 12:
        return [ilot]
    axe, la, lb = _grand_axe(ilot)
    f = float(np.clip(rng.normal(0.5, 0.08), 0.32, 0.68))
    parts = _couper(ilot, f, axe)
    if parts is None:
        return [ilot]
    a, b = parts
    if min(a.area, b.area) < 0.45 * amin:
        return [ilot]
    return _lotir(a, amin, amax, rng, profondeur + 1) + _lotir(b, amin, amax, rng, profondeur + 1)


def _facade_sur_rue(lot: Polygon, ilot: Polygon) -> list[tuple[np.ndarray, np.ndarray]]:
    """Segments du contour du lot qui bordent l'îlot (donc la rue), du plus long au plus court."""
    bord = ilot.exterior.buffer(0.6)
    segs = []
    c = np.asarray(lot.exterior.coords)
    for p, q in zip(c[:-1], c[1:]):
        if np.hypot(*(q - p)) < 0.5:
            continue
        s = LineString([p, q])
        if s.intersection(bord).length > 0.6 * s.length:
            segs.append((p, q))
    return sorted(segs, key=lambda pq: -np.hypot(*(pq[1] - pq[0])))


def _rect_cadre(m: np.ndarray, t: np.ndarray, n: np.ndarray, u0, u1, v0, v1) -> Polygon:
    return Polygon([m + u0 * t + v0 * n, m + u1 * t + v0 * n, m + u1 * t + v1 * n, m + u0 * t + v1 * n])


def _ajuster(m, t, n, u0, u1, v0, v1, permis: Polygon) -> tuple[float, float, float, float] | None:
    """Rétrécit le rectangle de cadre jusqu'à ce qu'il tienne dans `permis` (côté rue tenu le plus longtemps)."""
    for k in range(30):
        if u1 - u0 < 4.0 or v1 - v0 < 4.0:
            return None
        r = _rect_cadre(m, t, n, u0, u1, v0, v1)
        if r.within(permis):
            return u0, u1, v0, v1
        du, dv = 0.04 * (u1 - u0), 0.04 * (v1 - v0)
        u0, u1, v1 = u0 + du, u1 - du, v1 - dv
        if k > 10:
            v0 += dv
    return None


def _style_toit(style: dict, etages: int, rng: np.random.Generator) -> str:
    if etages >= ETAGES_TOUR:
        return "terrasse" if "terrasse" in style["toits"] else "plat"
    return str(rng.choice(style["toits"]))


def _teintes(rng: np.random.Generator, nombre: int = 5) -> list[str]:
    """Teintes de façade : couleurs claires et peu saturées de la palette (loi sur la couleur, pas une liste)."""
    choix = []
    for nom, hexa in voc.PALETTE.items():
        r, gg, b = (int(hexa[i:i + 2], 16) / 255.0 for i in (1, 3, 5))
        h, s, v = colorsys.rgb_to_hsv(r, gg, b)
        if v > 0.72 and s < 0.38:
            choix.append(nom)
    rng.shuffle(choix)
    return choix[:nombre]


def _concevoir_batiment(lot: Polygon, ilot: Polygon, zone: str, style_cle: str, rng: np.random.Generator,
                        etages_force: tuple[int, int] | None, centralite: float, teintes: list[str]) -> Batiment | None:
    zs, gab, style = voc.ZONES_VILLE[zone], GABARITS_ZONE[zone], voc.STYLES_ARCHI[style_cle]
    facades = _facade_sur_rue(lot, ilot)
    if not facades:
        return None
    p, q = facades[0]
    t = (q - p) / np.hypot(*(q - p))
    n = np.array([-t[1], t[0]])
    m = 0.5 * (p + q)
    if (np.asarray(lot.centroid.coords[0]) - m) @ n < 0:          # v vers l'intérieur de la parcelle
        t, n = -t, -n
    c = np.asarray(lot.exterior.coords)
    us, vs = (c - m) @ t, (c - m) @ n
    umin, umax, vmax = float(us.min()), float(us.max()), float(vs.max())
    ecart = gab["ecart_lateral"] / 2.0 + 0.05
    permis = lot.buffer(-ecart, join_style=2) if ecart > 0.06 else lot.buffer(-0.05, join_style=2)
    if permis.is_empty:
        return None
    permis = max(_polygones(permis), key=lambda pp: pp.area)
    retrait = zs["retrait"] * (1.0 + 0.2 * rng.uniform(-1, 1)) if zs["retrait"] > 0 else 0.0
    lo, hi = etages_force or zs["etages"]
    etages = int(lo + math.floor((hi - lo + 1) * rng.random() ** (0.6 + 1.6 * (1.0 - centralite))))
    etages = int(np.clip(etages, lo, hi))
    he = float(style["hauteur_etage"])
    commerce = bool(rng.random() < zs["commerce"])
    hrdc = 1.3 * he if commerce else he
    toit = _style_toit(style, etages, rng)
    if etages >= ETAGES_TOUR:
        # Une tour est en mur-rideau ou en béton, quel que soit le style (structure porteuse) ; le style
        # garde la main s'il en propose une des deux.
        facade = str(rng.choice(["mur_rideau", "facade_beton"]))
    else:
        facade = str(rng.choice(style["facades"]))
    if facade in FACADES_TEINTABLES and teintes:
        facade = f"{facade}:{rng.choice(teintes)}"
    base = HAUT_TROTTOIR
    haut = base + hrdc + (etages - 1) * he
    prof = gab["profondeur_bati"]
    # Bâti continu (zones mitoyennes à toit plat ou mansardé) : la bande de profondeur bâtie le long du bord
    # de l'îlot, découpée par la parcelle. Elle suit les rues courbes et tourne aux angles d'elle-même ;
    # une grande parcelle peut porter un bâtiment sur cour (bande le long de tout son contour).
    if gab["ecart_lateral"] == 0.0 and prof and toit in ("plat", "terrasse", "mansarde") and etages < ETAGES_TOUR:
        p_bati = float(rng.uniform(*prof))
        lot_in = lot.buffer(-0.05, join_style=2)
        bord = ilot.exterior
        bande = bord.buffer(retrait + p_bati, quad_segs=3)
        forme = "bande"
        if "cour" in gab.get("formes", ()) and lot.area > 1100.0 and rng.random() < 0.5:
            interieur = lot_in.buffer(-p_bati, join_style=2)
            if interieur.area > 80.0:
                bande = lot_in.difference(interieur)
                forme = "cour"
        emprise = lot_in.intersection(bande)
        if retrait > 0:
            emprise = emprise.difference(bord.buffer(retrait))
        morceaux = []
        for pp in _polygones(emprise):
            if pp.area > 30.0:            # allégé, puis recoupé par la parcelle : jamais de débord
                morceaux.extend(_polygones(pp.simplify(0.15, preserve_topology=True).intersection(lot_in)))
        morceaux = [pp for pp in morceaux if pp.is_valid and pp.area > 30.0]
        if not morceaux:
            return None
        vols = []
        for pp in morceaux:
            x0, z0, x1, z1 = pp.bounds
            vols.append(Volume(float(pp.centroid.x), float(pp.centroid.y), 0.0, x1 - x0, z1 - z0, base, haut, toit, pp))
        return Batiment(vols, etages, he, hrdc, facade, style["toiture"], toit, commerce, forme, base)
    # Rectangle de base dans le cadre de la façade.
    u0, u1 = umin + ecart, umax - ecart
    if gab.get("largeur_max") and u1 - u0 > gab["largeur_max"]:
        cu = 0.5 * (u0 + u1) + rng.uniform(-0.15, 0.15) * (u1 - u0 - gab["largeur_max"])
        u0, u1 = cu - gab["largeur_max"] / 2.0, cu + gab["largeur_max"] / 2.0
    v0 = max(retrait, 0.05)
    arriere = max(3.0, zs["retrait"])
    v1 = min(v0 + rng.uniform(*prof), vmax - arriere) if prof else vmax - max(arriere, 0.5 * zs["retrait"])
    rect = _ajuster(m, t, n, u0, u1, v0, v1, permis)
    if rect is None:
        return None
    u0, u1, v0, v1 = rect
    volumes: list[tuple[float, float, float, float, float, float, str | None]] = []   # u0,u1,v0,v1,y0,y1,toit
    formes_possibles = list(gab.get("formes", ("rect",)))
    angle = len(facades) > 1 and abs(float(np.dot((facades[1][1] - facades[1][0]) / max(1e-9, np.hypot(*(facades[1][1] - facades[1][0]))), t))) < 0.7
    forme = "rect"
    if "tour" in formes_possibles and etages >= ETAGES_TOUR:
        forme = "tour"
    elif prof:
        d = v1 - v0
        lot_prof = vmax - arriere
        options = ["rect"]
        if "L" in formes_possibles and lot_prof - v0 > 2.0 * d:
            options.append("L")
        if "U" in formes_possibles and lot_prof - v0 > 2.0 * d and u1 - u0 > 3.0 * d:
            options.append("U")
        if "cour" in formes_possibles and lot_prof - v0 > 2.0 * d + 8.0 and u1 - u0 > 2.0 * d + 8.0:
            options.append("cour")
        forme = "L" if (angle and "L" in options and gab["ecart_lateral"] == 0.0) else str(rng.choice(options))
    if forme == "tour":
        socle = int(min(3, max(1, etages // 6)))
        y_socle = base + hrdc + (socle - 1) * he
        volumes.append((u0, u1, v0, v1, base, y_socle, "plat"))
        retrait_fut = float(rng.uniform(3.0, 6.0))
        fu0, fu1, fv0, fv1 = u0 + retrait_fut, u1 - retrait_fut, v0 + retrait_fut, v1 - retrait_fut
        cote_max = 42.0
        if fu1 - fu0 > cote_max:
            cu = 0.5 * (fu0 + fu1)
            fu0, fu1 = cu - cote_max / 2.0, cu + cote_max / 2.0
        if fv1 - fv0 > cote_max:
            cv = 0.5 * (fv0 + fv1)
            fv0, fv1 = cv - cote_max / 2.0, cv + cote_max / 2.0
        if fu1 - fu0 >= 12.0 and fv1 - fv0 >= 12.0:
            coupure = int(round(etages * rng.uniform(0.62, 0.8)))
            if etages >= 16 and min(fu1 - fu0, fv1 - fv0) > 22.0:
                y_c = base + hrdc + (coupure - 1) * he
                volumes.append((fu0, fu1, fv0, fv1, y_socle, y_c, "plat"))
                r2 = float(rng.uniform(2.5, 4.0))
                volumes.append((fu0 + r2, fu1 - r2, fv0 + r2, fv1 - r2, y_c, haut, toit))
            else:
                volumes.append((fu0, fu1, fv0, fv1, y_socle, haut, toit))
        else:
            volumes[0] = (u0, u1, v0, v1, base, haut, toit)
    else:
        volumes.append((u0, u1, v0, v1, base, haut, toit))
        d = v1 - v0
        lot_prof = vmax - arriere
        if forme in ("L", "U"):
            cotes = [0, 1] if forme == "U" else [int(rng.integers(2))]
            if forme == "L" and angle:
                pa, qa = facades[1]
                cotes = [0 if (0.5 * (pa + qa) - m) @ t < 0.5 * (u0 + u1) else 1]
            for cote in cotes:
                a0, a1 = (u0, u0 + d) if cote == 0 else (u1 - d, u1)
                aile = _ajuster(m, t, n, a0, a1, v1 - 0.5, min(lot_prof, v1 + rng.uniform(1.0, 2.5) * d), permis)
                if aile is not None:
                    volumes.append((*aile, base, haut, toit))
        elif forme == "cour":
            fond = _ajuster(m, t, n, u0, u1, lot_prof - d, lot_prof, permis)
            if fond is not None:
                volumes.append((*fond, base, haut, toit))
                for a0, a1 in ((u0, u0 + d), (u1 - d, u1)):
                    aile = _ajuster(m, t, n, a0, a1, v1 - 0.5, fond[2] + 0.5, permis)
                    if aile is not None:
                        volumes.append((*aile, base, haut, toit))
    theta = math.atan2(t[1], t[0])
    vols = []
    for a0, a1, b0, b1, y0, y1, tt in volumes:
        cu, cv = 0.5 * (a0 + a1), 0.5 * (b0 + b1)
        centre = m + cu * t + cv * n
        vols.append(Volume(float(centre[0]), float(centre[1]), theta, a1 - a0, b1 - b0, y0, y1, tt))
    return Batiment(vols, etages, he, hrdc, facade, style["toiture"], toit, commerce, forme, base)


# ── Conception ─────────────────────────────────────────────────────────────────────────────────────
def _rues_et_riviere(lignes: list[tuple[LineString, str]], rect: Polygon, largeur: float, riviere: LineString | None,
                     demi_riviere: float, espacement_ponts: float, centre: np.ndarray):
    rues: list[Rue] = []
    for ligne, rang in lignes:
        coupee = ligne.intersection(rect)
        for l in _lignes(coupee):
            if l.length > 1.0:
                rues.append(Rue(l, largeur * (1.4 if rang == "principale" else 1.0), rang))
    eau = quais = None
    ponts: list[dict] = []
    if riviere is not None:
        eau_brute = riviere.buffer(demi_riviere, cap_style=2)
        eau = eau_brute.intersection(rect)
        couloir_quai = riviere.buffer(demi_riviere + LARGEUR_QUAI, cap_style=2)
        # Franchissements, traversée par traversée (une rue en anneau franchit deux fois) : les principales et
        # les plus centrales d'abord, espacées le long de la rivière ; les autres s'arrêtent à la rue de quai.
        demi_coupe = demi_riviere + LARGEUR_QUAI + largeur / 2.0
        coupe = riviere.buffer(demi_coupe, cap_style=2)
        traversees = []
        for k, r in enumerate(rues):
            for j, morceau in enumerate(_lignes(r.ligne.intersection(coupe))):
                mouille = morceau.intersection(eau_brute)
                if mouille.length < demi_riviere or not morceau.intersects(riviere):
                    continue
                a, b = Point(morceau.coords[0]), Point(morceau.coords[-1])
                if eau_brute.contains(a) or eau_brute.contains(b):
                    continue                    # ne relie pas deux rives : rue qui longe l'eau
                p = mouille.interpolate(0.5, normalized=True)
                s_p = riviere.project(p)
                tangente = np.subtract(riviere.interpolate(s_p + 1.0).coords[0], riviere.interpolate(s_p - 1.0).coords[0])
                corde = np.subtract(b.coords[0], a.coords[0])
                cosinus = abs(float(tangente @ corde)) / max(np.hypot(*tangente) * np.hypot(*corde), 1e-9)
                if cosinus > math.cos(math.radians(40.0)):
                    continue                    # trop rasant pour un pont
                traversees.append((0 if r.rang == "principale" else 1, Point(p).distance(Point(centre)), k, j,
                                   riviere.project(p), morceau))
        traversees.sort(key=lambda t: (t[0], t[1]))
        gardees: list[float] = []
        garder: dict[int, list] = defaultdict(list)
        for rang, dist, k, j, s_riv, morceau in traversees:
            if all(abs(s_riv - s2) >= espacement_ponts for s2 in gardees):
                gardees.append(s_riv)
                garder[k].append(morceau)
        # Toute autre portion de rue dans le couloir (traversée écartée, rue qui longe l'eau) disparaît.
        nouvelles: list[Rue] = []
        for k, r in enumerate(rues):
            ponts_rue = garder.get(k, [])
            a_retirer = [m for m in _lignes(r.ligne.intersection(coupe))
                         if not any(m.equals_exact(pm, 1e-6) for pm in ponts_rue)]
            reste = r.ligne.difference(unary_union(a_retirer).buffer(0.01)) if a_retirer else r.ligne
            for l in _lignes(reste):
                pont = any(l.buffer(0.05).intersection(pm).length > 0.5 * pm.length for pm in ponts_rue)
                if l.length <= 12.0 and not pont:
                    continue
                nouvelles.append(Rue(l, r.largeur, r.rang, pont=pont))
            for pm in ponts_rue:
                for seg in _lignes(pm.intersection(eau_brute.buffer(0.8))):
                    ponts.append({"ligne": seg, "largeur": r.largeur,
                                  "polygone": seg.buffer(r.largeur / 2.0, cap_style=2)})
        rues = nouvelles
        for signe in (-1.0, 1.0):
            quai = riviere.offset_curve(signe * demi_coupe, quad_segs=4, join_style=2)
            for l in _lignes(quai.intersection(rect)):
                if l.length > 20.0:
                    rues.append(Rue(l, largeur, "quai"))
        quais = couloir_quai.difference(eau_brute).intersection(rect)
    return rues, eau, quais, ponts


def _segments(rues: list[Rue], rect: Polygon) -> tuple[list[dict], list[tuple[float, float]]]:
    """Réseau noué : segments entre carrefours (avec leur rue) et carrefours (degré ≥ 3)."""
    noue = unary_union([r.ligne for r in rues])
    segs = [s for s in _lignes(noue) if s.length > 0.5]
    arbre = STRtree([r.ligne for r in rues])
    degre: dict[tuple[float, float], int] = defaultdict(int)
    for s in segs:
        for p in (s.coords[0], s.coords[-1]):
            degre[(round(p[0], 2), round(p[1], 2))] += 1
    sortie = []
    for s in segs:
        milieu = s.interpolate(0.5, normalized=True)
        k = int(arbre.nearest(milieu))
        a, b = (round(s.coords[0][0], 2), round(s.coords[0][1], 2)), (round(s.coords[-1][0], 2), round(s.coords[-1][1], 2))
        sortie.append({"ligne": s, "rue": rues[k], "carrefour_debut": degre[a] >= 3, "carrefour_fin": degre[b] >= 3})
    carrefours = [p for p, d in degre.items() if d >= 3 and rect.buffer(-1.0).contains(Point(p))]
    return sortie, carrefours


def _point_cote(ligne: LineString, s: float, decalage: float) -> tuple[np.ndarray, np.ndarray]:
    """Point à l'abscisse s, décalé de `decalage` sur la normale gauche ; et la direction locale."""
    s = float(np.clip(s, 0.0, ligne.length))
    a = np.asarray(ligne.interpolate(max(0.0, s - 0.5)).coords[0])
    b = np.asarray(ligne.interpolate(min(ligne.length, s + 0.5)).coords[0])
    d = b - a
    d = d / max(np.hypot(*d), 1e-9)
    n = np.array([-d[1], d[0]])
    p = np.asarray(ligne.interpolate(s).coords[0])
    return p + decalage * n, d


def _lacet_vers(direction: np.ndarray) -> float:
    """Lacet tel que la face (sin l, cos l) regarde `direction` (x, z)."""
    return float(math.atan2(direction[0], direction[1]))


def concevoir_ville(*, taille: tuple[float, float] = (400.0, 400.0), trame: str = "grille",
                    zones: list[ZoneDemandee] | None = None, etages: tuple[int, int] | None = None,
                    largeur_rues: float = 12.0, style: str = "moderne", riviere: bool = False,
                    arbres_alignement: bool = True, voitures: bool = True, graine: int = 0) -> PlanVille:
    """Plan complet d'une ville (aucune géométrie 3D) : rues, îlots zonés, parcelles, bâtiments, mobilier."""
    if trame not in voc.TRAMES:
        raise KeyError(f"trame hors vocabulaire : {trame!r}")
    if style not in voc.STYLES_ARCHI:
        raise KeyError(f"style d'architecture hors vocabulaire : {style!r}")
    zones = list(zones or [ZoneDemandee("centre", 0.3), ZoneDemandee("residentiel", 0.5), ZoneDemandee("parc", 0.2)])
    if etages is not None and not (1 <= etages[0] <= etages[1]):
        raise ValueError(f"fourchette d'étages invalide : {etages!r}")
    fusion: dict[str, float] = defaultdict(float)
    for z in zones:
        fusion[z.type] += float(z.part)
    total = sum(fusion.values())
    parts = {k: v / total for k, v in fusion.items()}
    if not any(voc.ZONES_VILLE[k]["batie"] for k in parts) and not any(k in ("parc", "place") for k in parts):
        raise ValueError("aucune zone terrestre demandée")
    W, D = float(taille[0]), float(taille[1])
    rect = box(-W / 2.0, -D / 2.0, W / 2.0, D / 2.0)
    rng = np.random.default_rng(_graine("ville", graine, trame, style))
    centre = np.zeros(2)
    longueur, profondeur = dimensions_ilot(zones)
    avec_riviere = riviere or "eau" in parts
    part_eau = parts.get("eau", 0.0)
    if trame in ("grille", "grille_irreguliere"):
        lignes = _trame_grille(W, D, longueur, profondeur, largeur_rues, rng, trame == "grille_irreguliere")
    elif trame == "radiale":
        lignes = _trame_radiale(W, D, longueur, profondeur, largeur_rues, rng)
    else:
        lignes = _trame_organique(W, D, longueur, profondeur, largeur_rues, rng)
    courbe = _courbe_riviere(W, D, rng) if avec_riviere else None
    longueur_eau = courbe.intersection(rect).length if courbe is not None else 0.0
    demi = 0.0
    if courbe is not None:
        visee = part_eau if part_eau > 0 else 0.08
        demi = float(np.clip(visee * 0.75 * W * D / max(longueur_eau, 1.0) / 2.0, 7.0, 0.15 * min(W, D)))
    espacement_ponts = max(80.0, 0.9 * (longueur + largeur_rues))      # un pont tous les ~1 îlot

    def reseau(demi_r: float):
        rues, eau, quais, ponts = _rues_et_riviere(lignes, rect, largeur_rues, courbe, demi_r, espacement_ponts, centre)
        chaussee = unary_union([r.ligne.buffer(r.profil["chaussee"] / 2.0, quad_segs=3) for r in rues]).intersection(rect)
        emprise = unary_union([r.ligne.buffer(r.largeur / 2.0, quad_segs=3) for r in rues]).intersection(rect)
        reste = rect.difference(emprise)
        if eau is not None:
            reste = reste.difference(unary_union([eau, quais]).buffer(0.01))
        trottoirs = emprise.difference(chaussee)
        if eau is not None:
            ponts_poly = unary_union([p["polygone"] for p in ponts]) if ponts else Polygon()
            trottoirs = trottoirs.difference(eau.difference(ponts_poly.buffer(0.5)))
        return rues, eau, quais, ponts, chaussee, emprise, trottoirs, reste

    rues, eau, quais, ponts, chaussee, emprise, trottoirs, reste = reseau(demi)
    if courbe is not None and part_eau > 0:
        for _ in range(2):           # la largeur de la rivière tient la part d'eau demandée
            aire_terre = sum(p.area for p in _polygones(reste) if p.area >= 300.0)
            mesure = eau.area / max(aire_terre + eau.area, 1.0)
            if abs(mesure - part_eau) / part_eau < 0.05:
                break
            demi = float(np.clip(demi * part_eau / max(mesure, 1e-3) * (1 - mesure) / max(1 - part_eau, 1e-3),
                                 6.0, 0.2 * min(W, D)))
            rues, eau, quais, ponts, chaussee, emprise, trottoirs, reste = reseau(demi)
    segments, carrefours = _segments(rues, rect)
    # Îlots : touchent une rue (sinon : terrain vague, laissé au sol).
    ilots: list[Ilot] = []
    vagues = []
    trottoirs_b = trottoirs.buffer(0.8)
    for brut in _polygones(reste):
        # Contour allégé SANS déborder sur le trottoir : léger retrait, simplification, puis découpe par l'original.
        morceaux = _polygones(brut.buffer(-0.3, join_style=2).simplify(0.2, preserve_topology=True).intersection(brut))
        if not morceaux:
            continue
        p = max(morceaux, key=lambda q: q.area)
        if p.area < 300.0:
            continue
        if p.intersection(trottoirs_b).area < 2.0:
            vagues.append(p)
            continue
        ilots.append(Ilot(p, distance=Point(p.centroid).distance(Point(centre))))
    rmax = math.hypot(W, D) / 2.0
    aire_ilots = sum(i.polygone.area for i in ilots)
    terre = {k: v for k, v in parts.items() if k != "eau"}
    s_terre = sum(terre.values())
    cibles = {k: v / s_terre * aire_ilots for k, v in terre.items()}
    ilots = _affecter_zones(ilots, cibles, centre, rmax, rng)
    denominateur = aire_ilots + (eau.area if (eau is not None and part_eau > 0) else 0.0)
    mesurees: dict[str, float] = defaultdict(float)
    for i in ilots:
        mesurees[i.zone] += i.polygone.area / denominateur
    if eau is not None and part_eau > 0:
        mesurees["eau"] = eau.area / denominateur
    # Parcelles et bâtiments.
    teintes = _teintes(np.random.default_rng(_graine(graine, "teintes")))
    for i in ilots:
        zs = voc.ZONES_VILLE[i.zone]
        if not zs["batie"]:
            continue
        r_lot = np.random.default_rng(_graine(graine, "lots", round(i.polygone.centroid.x, 1), round(i.polygone.centroid.y, 1)))
        amin, amax = zs["parcelle"]
        for lp in _lotir(i.polygone, amin, amax, r_lot):
            lot = Lot(lp)
            centralite = float(np.clip(1.0 - Point(lp.centroid).distance(Point(centre)) / rmax, 0.0, 1.0))
            lot.batiment = _concevoir_batiment(lp, i.polygone, i.zone, style, r_lot, etages, centralite, teintes)
            i.lots.append(lot)
    plan = PlanVille(taille=(W, D), trame=trame, style=style, graine=graine, rues=rues, chaussee=chaussee,
                     trottoirs=trottoirs, emprise_rues=emprise, ilots=ilots, eau=eau, quais=quais, ponts=ponts,
                     intersections=carrefours, segments=segments, passages=[], marquages=[], allees=None, mobilier=[],
                     parts_demandees=parts, parts_mesurees=dict(mesurees), centre=(0.0, 0.0),
                     options={"arbres_alignement": arbres_alignement, "voitures": voitures, "largeur_rues": largeur_rues,
                              "etages": etages, "riviere": avec_riviere},
                     rapport={"dimensions_ilot": (longueur, profondeur), "terrains_vagues": len(vagues),
                              "demi_largeur_riviere": demi})
    _marquages(plan)
    _mobilier_rues(plan, rng)
    _amenager_espaces(plan, rng)
    return plan


# ── Marquages et mobilier ──────────────────────────────────────────────────────────────────────────
def _marge_carrefour(plan: PlanVille) -> float:
    return 0.5 * max((r.largeur for r in plan.rues), default=12.0) + 2.0


def _marquages(plan: PlanVille) -> None:
    """Pointillés de voies (3 m tous les 8 m), ligne de stationnement, passages piétons aux carrefours."""
    marge = _marge_carrefour(plan)
    marques, passages = [], []
    for seg in plan.segments:
        ligne, pr = seg["ligne"], seg["rue"].profil
        L = ligne.length
        s0 = marge + 3.5 if seg["carrefour_debut"] else 1.0
        s1 = L - (marge + 3.5 if seg["carrefour_fin"] else 1.0)
        if s1 - s0 < 4.0:
            continue
        ch, nv, lv, st = pr["chaussee"], pr["voies"], pr["largeur_voie"], pr["stationnement"]
        bord_gauche = ch / 2.0 - (2.1 if st >= 1 else 0.0)      # côté +n : stationnement si st ≥ 1
        bord_droit = -ch / 2.0 + (2.1 if st >= 2 else 0.0)
        decalages = [bord_droit + k * lv for k in range(1, nv)]
        for dec in decalages:
            s = s0
            while s + 3.0 <= s1:
                morceau = substring(ligne, s, s + 3.0)
                if morceau.length > 0.5:
                    m = morceau.offset_curve(dec) if abs(dec) > 1e-6 else morceau
                    if not m.is_empty:
                        marques.append(m.buffer(0.075, cap_style=2))
                s += 8.0
        for dec, actif in ((bord_gauche, st >= 1), (bord_droit, st >= 2)):
            if actif:
                m = substring(ligne, s0, s1).offset_curve(dec)
                if not m.is_empty:
                    marques.append(m.buffer(0.06, cap_style=2))
        # Passages piétons : bandes parallèles à la rue, juste avant chaque carrefour.
        for est_carrefour, s_centre in ((seg["carrefour_debut"], marge + 1.5), (seg["carrefour_fin"], L - marge - 1.5)):
            if not est_carrefour or L < 2 * marge + 6.0:
                continue
            p, d = _point_cote(ligne, s_centre, 0.0)
            n = np.array([-d[1], d[0]])
            k = -ch / 2.0 + 0.6
            while k + 0.5 <= ch / 2.0 - 0.4:
                c = p + (k + 0.25) * n
                passages.append(Polygon([c - 1.5 * d - 0.25 * n, c + 1.5 * d - 0.25 * n, c + 1.5 * d + 0.25 * n,
                                         c - 1.5 * d + 0.25 * n]))
                k += 1.0
    plan.marquages = marques
    plan.passages = passages


def _zone_du_cote(arbre: STRtree, ilots: list[Ilot], p: np.ndarray) -> str | None:
    pt = Point(p)
    for k in arbre.query(pt.buffer(1.5)):
        if ilots[int(k)].polygone.distance(pt) < 1.5:
            return ilots[int(k)].zone
    return None


def _mobilier_rues(plan: PlanVille, rng: np.random.Generator) -> None:
    arbre_ilots = STRtree([i.polygone for i in plan.ilots]) if plan.ilots else None
    marge = _marge_carrefour(plan)
    eau = plan.eau
    places: list[Placement] = []
    hauteur_lampe = 0.5 * sum(voc.CATEGORIES["lampadaire_rue"]["hauteur"])
    cote = 1.0
    for kseg, seg in enumerate(plan.segments):
        ligne, rue = seg["ligne"], seg["rue"]
        pr = rue.profil
        L = ligne.length
        s0 = marge if seg["carrefour_debut"] else 2.0
        s1 = L - (marge if seg["carrefour_fin"] else 2.0)
        if s1 - s0 < 3.0:
            continue
        ch, tr = pr["chaussee"], pr["trottoir"]

        def sur_eau(p: np.ndarray) -> bool:
            return eau is not None and eau.buffer(1.0).contains(Point(p))

        def sur_trottoir(p: np.ndarray) -> bool:
            pt = Point(p)
            return plan.trottoirs.buffer(0.05).contains(pt) and not plan.chaussee.contains(pt)

        lampes: list[np.ndarray] = []
        s = s0 + rng.uniform(0.0, 6.0)
        while s <= s1:
            p, d = _point_cote(ligne, s, cote * (ch / 2.0 + 0.5))
            if sur_trottoir(p) and not (rue.pont and sur_eau(p)):
                vers_rue = -cote * np.array([-d[1], d[0]])
                places.append(Placement("lampadaire_rue", float(p[0]), float(p[1]), _lacet_vers(vers_rue),
                                        {"hauteur": hauteur_lampe}))
                lampes.append(p)
                if len(lampes) % 3 == 0:
                    pb, _ = _point_cote(ligne, s + 1.2, cote * (ch / 2.0 + 0.5))
                    if sur_trottoir(pb):
                        places.append(Placement("poubelle_rue", float(pb[0]), float(pb[1]), _lacet_vers(vers_rue)))
            cote = -cote
            s += 30.0
        for c_side in (-1.0, 1.0):
            n_side = c_side * (ch / 2.0 + tr + 2.0)
            zone = _zone_du_cote(arbre_ilots, plan.ilots, _point_cote(ligne, 0.5 * L, n_side)[0]) if arbre_ilots else None
            gab = GABARITS_ZONE.get(zone or "", {})
            if plan.options["arbres_alignement"] and gab.get("arbres_rue") and tr >= 2.0 and not rue.pont:
                dec = c_side * (ch / 2.0 + min(1.3, 0.45 * tr))
                s = s0 + 4.0
                while s <= s1 - 2.0:
                    p, _ = _point_cote(ligne, s, dec)
                    if sur_trottoir(p) and all(np.hypot(*(p - q)) > 4.0 for q in lampes):
                        places.append(Placement("arbre", float(p[0]), float(p[1]), float(rng.uniform(0, 2 * math.pi)),
                                                {"style": "feuillu", "hauteur": float(rng.choice([7.0, 8.5, 10.0])),
                                                 "largeur": 4.5}))
                    s += 12.0
            if zone in ("centre", "residentiel", "parc", "place") and tr >= 2.5:
                s = s0 + rng.uniform(10.0, 40.0)
                while s <= s1 - 5.0:
                    p, d = _point_cote(ligne, s, c_side * (ch / 2.0 + tr - 0.6))
                    if sur_trottoir(p) and all(np.hypot(*(p - q)) > 3.0 for q in lampes):
                        vers_rue = -c_side * np.array([-d[1], d[0]])
                        places.append(Placement("banc_public", float(p[0]), float(p[1]), _lacet_vers(vers_rue)))
                    s += float(rng.uniform(60.0, 90.0))
        # Voitures garées : dans la file de stationnement, dans le sens de la circulation du côté.
        if plan.options["voitures"] and pr["stationnement"] > 0 and not rue.pont:
            cotes = [1.0] if pr["stationnement"] == 1 else [1.0, -1.0]
            for c_side in cotes:
                dec = c_side * (ch / 2.0 - 1.05)
                s = s0 + 3.0 + rng.uniform(0.0, 3.0)
                while s <= s1 - 3.0:
                    if rng.random() < 0.6:
                        p, d = _point_cote(ligne, s, dec)
                        if plan.chaussee.contains(Point(p)) and not sur_eau(p):
                            sens = d if c_side > 0 else -d
                            couleur = str(rng.choice(TEINTES_AUTOMOBILES))
                            places.append(Placement("voiture", float(p[0]), float(p[1]), _lacet_vers(sens),
                                                    {"materiaux": {"carrosserie": f"carrosserie:{couleur}"},
                                                     "couleur": couleur}, y=0.0))
                    s += float(rng.uniform(5.8, 6.6))
    plan.mobilier.extend(places)


def _amenager_espaces(plan: PlanVille, rng: np.random.Generator) -> None:
    """Parcs (allées, fontaine, bancs, arbres), places (fontaine, bancs, arbres en bordure), jardins."""
    allees = []
    fontaine = voc.CATEGORIES["fontaine"]
    for i in plan.ilots:
        poly = i.polygone
        if i.zone not in ("parc", "place"):
            continue
        axe, la, lb = _grand_axe(poly)
        perp = np.array([-axe[1], axe[0]])
        c = np.asarray(poly.representative_point().coords[0]) if not poly.contains(poly.centroid) else np.asarray(poly.centroid.coords[0])
        diam = float(np.clip(0.12 * lb, fontaine["largeur"][0], fontaine["largeur"][1]))
        avec_fontaine = lb > 25.0
        objets_fixes: list[tuple[float, float, float]] = []
        if avec_fontaine:
            plan.mobilier.append(Placement("fontaine", float(c[0]), float(c[1]), float(rng.uniform(0, 2 * math.pi)),
                                           {"largeur": diam, "profondeur": diam,
                                            "hauteur": float(np.clip(diam * 0.45, *fontaine["hauteur"]))}))
            objets_fixes.append((float(c[0]), float(c[1]), diam / 2.0 + 2.5))
        if i.zone == "parc":
            # Allées : une croix suivant les axes et une boucle intérieure.
            lignes = [LineString([c - axe * la, c + axe * la]), LineString([c - perp * lb, c + perp * lb])]
            interieur = poly.buffer(-min(14.0, 0.22 * lb))
            for p in _polygones(interieur):
                lignes.append(p.exterior)
            reseau = unary_union([l.buffer(1.6, quad_segs=2) for l in lignes])
            if avec_fontaine:
                reseau = unary_union([reseau, Point(c).buffer(diam / 2.0 + 3.0, quad_segs=6)])
            allee = reseau.intersection(poly.buffer(-0.5))
            allees.append(allee)
            # Bancs le long de la boucle, tournés vers l'allée.
            for p in _polygones(interieur):
                anneau = p.exterior
                s = rng.uniform(0.0, 10.0)
                while s < anneau.length:
                    q, d = _point_cote(anneau, s, 0.0)
                    nrm = np.array([-d[1], d[0]])
                    dehors = q + 2.4 * nrm if not p.contains(Point(q + 2.4 * nrm)) else q - 2.4 * nrm
                    vers = (q - dehors) / max(np.hypot(*(q - dehors)), 1e-9)
                    if poly.buffer(-1.0).contains(Point(dehors)):
                        plan.mobilier.append(Placement("banc_public", float(dehors[0]), float(dehors[1]), _lacet_vers(vers)))
                        objets_fixes.append((float(dehors[0]), float(dehors[1]), 1.5))
                    s += 28.0
                s = 5.0
                while s < anneau.length:
                    q, d = _point_cote(anneau, s, 2.2)
                    if poly.buffer(-1.0).contains(Point(q)) and not allee.contains(Point(q)):
                        plan.mobilier.append(Placement("lampadaire_rue", float(q[0]), float(q[1]),
                                                       float(rng.uniform(0, 2 * math.pi)), {"hauteur": 4.5}))
                        objets_fixes.append((float(q[0]), float(q[1]), 1.0))
                    s += 32.0
            allee_b = allee.buffer(1.0)
            positions = disperser_positions(poly.buffer(-1.0), [Espece(*e) for e in VEGETATION_PARC],
                                            graine=_graine(plan.graine, "parc", round(c[0]), round(c[1])),
                                            accepter=lambda x, z, a=allee_b: ~contains_xy(a, x, z),
                                            obstacles=objets_fixes)
            _ajouter_vegetation(plan, positions, rng)
        else:
            allees.append(poly.buffer(-0.01))
            # Bancs en couronne autour de la fontaine, tournés vers elle ; arbres en bordure.
            if avec_fontaine:
                r = diam / 2.0 + 4.0
                nb = max(4, int(2 * math.pi * r / 7.0))
                for k in range(nb):
                    a = 2 * math.pi * k / nb
                    q = c + r * np.array([math.cos(a), math.sin(a)])
                    if poly.buffer(-1.0).contains(Point(q)):
                        plan.mobilier.append(Placement("banc_public", float(q[0]), float(q[1]), _lacet_vers(c - q)))
            bord = poly.buffer(-3.5)
            for p in _polygones(bord):
                anneau = p.exterior
                s = 0.0
                while s < anneau.length:
                    q, _ = _point_cote(anneau, s, 0.0)
                    plan.mobilier.append(Placement("arbre", float(q[0]), float(q[1]), float(rng.uniform(0, 2 * math.pi)),
                                                   {"style": "feuillu", "hauteur": 7.0, "largeur": 4.0}))
                    s += 11.0
    plan.allees = unary_union(allees) if allees else None
    # Jardins : les parcelles des zones à jardin reçoivent arbres fruitiers et buissons derrière le bâti.
    for i in plan.ilots:
        if not GABARITS_ZONE[i.zone].get("jardin"):
            continue
        for lot in i.lots:
            libre = lot.polygone.buffer(-1.0)
            if lot.batiment is not None:
                libre = libre.difference(lot.batiment.emprise.buffer(2.5))
            if libre.is_empty or libre.area < 80.0:
                continue
            positions = disperser_positions(libre, [Espece(*e) for e in VEGETATION_JARDIN],
                                            graine=_graine(plan.graine, "jardin", round(lot.polygone.centroid.x, 1),
                                                           round(lot.polygone.centroid.y, 1)))
            _ajouter_vegetation(plan, positions, rng)


def _ajouter_vegetation(plan: PlanVille, positions: list[dict], rng: np.random.Generator) -> None:
    for p in positions:
        e = p["espece"]
        spec = voc.categorie(e.categorie)
        lo, hi = spec["hauteur"]
        for x, z in p["points"]:
            h = float(round(lo + rng.random() ** 1.3 * (hi - lo) * (0.75 if e.categorie == "arbre" else 1.0), 0))
            opts = {"hauteur": max(lo, h)}
            if e.style:
                opts["style"] = e.style
            plan.mobilier.append(Placement(e.categorie, float(x), float(z), float(rng.uniform(0, 2 * math.pi)), opts))


# ── Maillage des bâtiments ─────────────────────────────────────────────────────────────────────────
ANGLE_COIN_DEG = 28.0           # un changement de direction plus fort est un coin de façade (u repart de 0)


def _anneaux(poly: Polygon) -> list[np.ndarray]:
    """Anneaux (extérieur puis cours) sans point de fermeture répété."""
    return [np.asarray(r.coords)[:-1] for r in [poly.exterior, *poly.interiors]]


def _normales_dehors(poly: Polygon, anneau: np.ndarray) -> np.ndarray:
    """Normale horizontale sortante (hors de la matière) de chaque arête de l'anneau."""
    p, q = anneau, np.roll(anneau, -1, axis=0)
    d = q - p
    d /= np.maximum(np.hypot(d[:, 0], d[:, 1]), 1e-12)[:, None]
    n = np.column_stack([d[:, 1], -d[:, 0]])
    milieux = 0.5 * (p + q)
    eps = 0.02
    dedans = contains_xy(poly, milieux[:, 0] + eps * n[:, 0], milieux[:, 1] + eps * n[:, 1])
    n[dedans] = -n[dedans]
    return n


def _courses(anneau: np.ndarray) -> list[list[int]]:
    """Arêtes regroupées en façades continues : une nouvelle façade commence à chaque vrai coin."""
    p, q = anneau, np.roll(anneau, -1, axis=0)
    d = q - p
    ang = np.arctan2(d[:, 1], d[:, 0])
    virage = np.degrees(np.abs((ang - np.roll(ang, 1) + math.pi) % (2 * math.pi) - math.pi))
    coins = [k for k in range(len(anneau)) if virage[k] > ANGLE_COIN_DEG]
    if not coins:
        return [list(range(len(anneau)))]
    courses = []
    for a, b in zip(coins, coins[1:] + [coins[0] + len(anneau)]):
        courses.append([k % len(anneau) for k in range(a, b)])
    return courses


def _murs_volume(v: Volume, b: Batiment, mat_facade: str) -> dict[str, list[trimesh.Trimesh]]:
    """Murs d'un volume (pavé ou polygone libre, cours comprises).

    UV de façade (exception documentée en tête de module) : v = (y − y_ref) × taille_m / hauteur d'étage, et u
    part de 0 à chaque coin de façade puis court le long de la façade (même courbe), mis à l'échelle pour
    que la façade compte un nombre entier de travées : les fenêtres tombent sur les étages et aucune
    travée n'est coupée à un angle."""
    sortie: dict[str, list[trimesh.Trimesh]] = defaultdict(list)
    poly = v.polygone
    t_fac = voc.materiau(mat_facade)["taille_m"]
    t_vit = voc.materiau("vitrine")["taille_m"]
    y_ref = b.base + (b.hauteur_rdc if b.commerce else 0.0)
    bandes = []
    if b.commerce and v.y0 <= b.base + 1e-6:
        bandes.append((v.y0, b.base + b.hauteur_rdc, "vitrine", t_vit, lambda y: (y - b.base) * t_vit / b.hauteur_rdc))
        bandes.append((b.base + b.hauteur_rdc, v.y1, mat_facade, t_fac, lambda y: (y - y_ref) * t_fac / b.hauteur_etage))
    else:
        bandes.append((v.y0, v.y1, mat_facade, t_fac, lambda y: (y - y_ref) * t_fac / b.hauteur_etage))
    for anneau in _anneaux(poly):
        if len(anneau) < 3:
            continue
        normales = _normales_dehors(poly, anneau)
        longueurs = np.hypot(*(np.roll(anneau, -1, axis=0) - anneau).T)
        for course in _courses(anneau):
            L_course = float(sum(longueurs[k] for k in course))
            if L_course < 1e-3:
                continue
            for y0, y1, mat, taille, fv in bandes:
                if y1 - y0 < 1e-3:
                    continue
                echelle_u = max(1, int(round(L_course / taille))) * taille / L_course
                u = 0.0
                for k in course:
                    p, q = anneau[k], anneau[(k + 1) % len(anneau)]
                    L = float(longueurs[k])
                    if L < 1e-4:
                        continue
                    normale = np.array([normales[k][0], 0.0, normales[k][1]])
                    ua, ub = u * echelle_u, (u + L) * echelle_u
                    sortie[mat].append(_quad((p[0], y0, p[1]), (q[0], y0, q[1]), (q[0], y1, q[1]), (p[0], y1, p[1]),
                                             normale, [(ua, fv(y0)), (ub, fv(y0)), (ub, fv(y1)), (ua, fv(y1))]))
                    u += L
    return sortie


def _decaler_anneau(poly: Polygon, anneau: np.ndarray, r: float) -> np.ndarray:
    """Décalage en onglet de chaque sommet de `r` vers l'intérieur de la matière (borné aux angles aigus)."""
    n_dehors = _normales_dehors(poly, anneau)
    n1, n2 = -np.roll(n_dehors, 1, axis=0), -n_dehors                 # normales entrantes des deux arêtes
    s = n1 + n2
    cos_demi = np.clip((1.0 + np.einsum("ij,ij->i", n1, n2)) / 2.0, 1e-6, 1.0)
    longueur = np.minimum(r / np.sqrt(cos_demi), 3.0 * r)
    s /= np.maximum(np.hypot(s[:, 0], s[:, 1]), 1e-12)[:, None]
    return anneau + s * longueur[:, None]


def _toit_libre(v: Volume, b: Batiment, rng: np.random.Generator) -> dict[str, list[trimesh.Trimesh]]:
    """Toit plat, terrasse (acrotère) ou mansarde (brisis en onglet + terrasson + lucarnes par travée) sur un
    polygone quelconque, en coordonnées monde."""
    out: dict[str, list[trimesh.Trimesh]] = defaultdict(list)
    poly, y = v.polygone, v.y1
    if v.toit in ("plat", "terrasse"):
        out["terrasse"].append(dalle_plate(poly, y))
        h_ac = 1.0 if v.toit == "terrasse" else 0.45
        anneau = poly.difference(poly.buffer(-0.25, join_style=2))
        for pp in _polygones(anneau):
            out["uni"].append(g.extrusion(pp, h_ac, y=y))
        if b.etages >= 4 and poly.area > 150.0:
            c = poly.buffer(-4.0).representative_point() if not poly.buffer(-4.0).is_empty else None
            if c is not None:
                out["uni"].append(g.boite(4.0, 2.6, 3.5, x=c.x, y=y, z=c.y))
        return out
    # Mansarde.
    h_m = 0.9 * b.hauteur_etage
    r = float(min(1.6, 0.18 * math.sqrt(poly.area) / 2.0 + 0.6))
    anneaux_bas = _anneaux(poly)
    anneaux_haut = [_decaler_anneau(poly, a, r) for a in anneaux_bas]
    for bas, haut in zip(anneaux_bas, anneaux_haut):
        m = len(bas)
        for k in range(m):
            a, bb = bas[k], bas[(k + 1) % m]
            c, d = haut[(k + 1) % m], haut[k]
            pts = np.array([(a[0], y, a[1]), (bb[0], y, bb[1]), (c[0], y + h_m, c[1]), (d[0], y + h_m, d[1])])
            nrm = np.cross(pts[1] - pts[0], pts[3] - pts[0])
            ln = np.linalg.norm(nrm)
            if ln < 1e-9:
                continue
            nrm /= ln
            dehors = np.array([0.5 * (a[0] + bb[0]) - 0.5 * (c[0] + d[0]), 0.0, 0.5 * (a[1] + bb[1]) - 0.5 * (c[1] + d[1])])
            if nrm @ dehors < 0:
                nrm = -nrm
            au = (pts[1] - pts[0]) / max(np.linalg.norm(pts[1] - pts[0]), 1e-12)
            av = np.cross(nrm, au)
            out["toiture"].append(maillage_brut(pts, _orienter_up(np.array([[0, 1, 2], [0, 2, 3]]), pts, nrm),
                                                np.tile(nrm, (4, 1)),
                                                np.column_stack([(pts - pts[0]) @ au, (pts - pts[0]) @ av])))
    try:
        dessus = Polygon(anneaux_haut[0], [a for a in anneaux_haut[1:]])
        if not dessus.is_valid:
            dessus = dessus.buffer(0)
        out["toiture"].append(dalle_plate(dessus, y + h_m))
    except Exception:  # noqa: BLE001 — terrasson dégénéré (parcelle en pointe) : brisis seul
        pass
    # Lucarnes : une par travée sur chaque arête assez longue des façades sur rue et sur cour.
    travee = voc.materiau(b.facade)["taille_m"]
    for anneau in anneaux_bas:
        normales = _normales_dehors(poly, anneau)
        for k in range(len(anneau)):
            p, q = anneau[k], anneau[(k + 1) % len(anneau)]
            L = float(np.hypot(*(q - p)))
            n_l = int((L - 1.5) // travee)
            if n_l < 1:
                continue
            d = (q - p) / L
            nrm = normales[k]
            theta = math.atan2(d[1], d[0])
            for j in range(n_l):
                s = (L - n_l * travee) / 2.0 + travee * (j + 0.5)
                c = p + d * s - nrm * 0.55
                boite = g.boite(1.1, 1.5, 0.9, y=y + 0.2)
                out["uni"].append(_repere(boite, float(c[0]), float(c[1]), theta))
    return out


def _boite_locale(lx, ly, lz, x=0.0, y=0.0, z=0.0) -> trimesh.Trimesh:
    return g.boite(lx, ly, lz, x=x, y=y, z=z)


def _pente_toit(toiture: str, rng: np.random.Generator) -> float:
    lo, hi = PENTES_TOITURE.get(toiture.partition(":")[0], (30.0, 40.0))
    return math.radians(float(rng.uniform(lo, hi)))


def _pans(L: float, D: float, y: float, pente: float, debord: float, croupe: bool) -> tuple[list, list]:
    """Toit à deux pans (croupe=False) ou quatre pans, faîtage selon x (L ≥ D), repère local centré.
    Rend (pans de toiture, pignons) en maillages locaux ; dessous fermé (vu d'en bas)."""
    h = D / 2.0 * math.tan(pente)
    ye = y - debord * math.tan(pente)
    ex, ez = L / 2.0 + debord, D / 2.0 + debord
    r = (L - D) / 2.0 if croupe else ex
    toit, pignons = [], []

    def poly_plan(pts, normale_haut=True):
        pts = np.asarray(pts, dtype=np.float64)
        nrm = np.cross(pts[1] - pts[0], pts[2] - pts[0])
        nrm /= max(np.linalg.norm(nrm), 1e-12)
        if (nrm[1] < 0) == normale_haut:
            nrm = -nrm
        f = np.array([[0, k, k + 1] for k in range(1, len(pts) - 1)])
        f = _orienter_up(f, pts, nrm)
        # UV : u le long de l'égout, v le long de la pente (en mètres)
        axe_u = pts[1] - pts[0]
        axe_u /= max(np.linalg.norm(axe_u), 1e-12)
        axe_v = np.cross(nrm, axe_u)
        uv = np.column_stack([(pts - pts[0]) @ axe_u, (pts - pts[0]) @ axe_v])
        return maillage_brut(pts, f, np.tile(nrm, (len(pts), 1)), uv)

    if croupe and r <= 0.0:
        sommet = (0.0, y + h, 0.0)
        coins = [(-ex, ye, -ez), (ex, ye, -ez), (ex, ye, ez), (-ex, ye, ez)]
        for k in range(4):
            toit.append(poly_plan([coins[k], coins[(k + 1) % 4], sommet]))
    else:
        toit.append(poly_plan([(-ex, ye, -ez), (ex, ye, -ez), (r, y + h, 0.0), (-r, y + h, 0.0)]))
        toit.append(poly_plan([(ex, ye, ez), (-ex, ye, ez), (-r, y + h, 0.0), (r, y + h, 0.0)]))
        if croupe:
            toit.append(poly_plan([(ex, ye, -ez), (ex, ye, ez), (r, y + h, 0.0)]))
            toit.append(poly_plan([(-ex, ye, ez), (-ex, ye, -ez), (-r, y + h, 0.0)]))
        else:
            for sx in (-1.0, 1.0):
                x = sx * L / 2.0
                pts = np.array([(x, y, -D / 2.0), (x, y, D / 2.0), (x, y + h, 0.0)])
                nrm = np.array([sx, 0.0, 0.0])
                f = _orienter_up(np.array([[0, 1, 2]]), pts, nrm)
                pignons.append(maillage_brut(pts, f, np.tile(nrm, (3, 1)), pts[:, [2, 1]]))
    dessous = np.array([(-ex, ye, -ez), (ex, ye, -ez), (ex, ye, ez), (-ex, ye, ez)])
    f = _orienter_up(np.array([[0, 1, 2], [0, 2, 3]]), dessous, np.array([0.0, -1.0, 0.0]))
    toit.append(maillage_brut(dessous, f, np.tile([0.0, -1.0, 0.0], (4, 1)), dessous[:, [0, 2]]))
    return toit, pignons


def _tourner_local(m: trimesh.Trimesh) -> trimesh.Trimesh:
    """Rotation locale de +90° (x → z) : sert à mettre le faîtage le long du grand côté."""
    R = np.array([[0.0, 0.0, -1.0], [0.0, 1.0, 0.0], [1.0, 0.0, 0.0]])
    return maillage_brut(np.asarray(m.vertices) @ R.T, m.faces, np.asarray(m.vertex_normals) @ R.T, m.visual.uv)


def _toit_volume(v: Volume, b: Batiment, rng: np.random.Generator) -> dict[str, list[trimesh.Trimesh]]:
    """Couverture d'un volume dans son repère local (x le long de u), puis passage au monde."""
    out: dict[str, list[trimesh.Trimesh]] = defaultdict(list)
    if v.toit is None:
        return out
    if v.libre is not None or v.toit in ("plat", "terrasse", "mansarde"):
        return _toit_libre(v, b, rng)
    L, D, y = v.lu, v.lv, v.y1
    uni = "uni"
    if v.toit in ("deux_pans", "quatre_pans"):
        tourne = D > L
        LL, DD = (D, L) if tourne else (L, D)
        toit, pignons = _pans(LL, DD, y, _pente_toit(b.toiture, rng), 0.4, v.toit == "quatre_pans")
        if tourne:
            toit, pignons = [_tourner_local(m) for m in toit], [_tourner_local(m) for m in pignons]
        out["toiture"].extend(toit)
        out[uni].extend(pignons)
    monde: dict[str, list[trimesh.Trimesh]] = defaultdict(list)
    for role, ms in out.items():
        monde[role].extend(_repere(m, v.cx, v.cz, v.theta) for m in ms if m is not None and len(m.faces))
    return monde


def maillage_batiment(b: Batiment, graine: int = 0) -> list[Partie]:
    """Parties d'un bâtiment : façades (UV d'étage), vitrines, couverture, toit-terrasse, matériau uni."""
    rng = np.random.default_rng(graine)
    base, _, teinte = b.facade.partition(":")
    uni = MATERIAU_UNI.get(base, "beton_cire")
    if teinte and voc.MATERIAUX[uni]["coloriable"]:
        uni = f"{uni}:{teinte}"
    roles = {"terrasse": "toit_terrasse", "toiture": b.toiture, "uni": uni}
    par_mat: dict[str, list[trimesh.Trimesh]] = defaultdict(list)
    for v in b.volumes:
        if not b.visitable:
            for mat, ms in _murs_volume(v, b, b.facade).items():
                par_mat[mat].extend(ms)
        for role, ms in _toit_volume(v, b, rng).items():
            par_mat[roles[role]].extend(ms)
    return [Partie(g.fusionner(ms), mat, mat) for mat, ms in par_mat.items() if ms]


# ── Construction 3D ────────────────────────────────────────────────────────────────────────────────
def _cle_options(options: dict) -> tuple:
    return tuple(sorted((k, repr(v)) for k, v in options.items()))


def construire_ville(plan: PlanVille, *, fabrique: Fabrique = objet_provisoire,
                     budget_triangles: int = BUDGET_VILLE) -> Noeud:
    """Géométrie de la ville (nœuds en fusion, peu nombreux) : sol, voirie, eau, bâtiments par zone,
    végétation, mobilier, véhicules. Le budget de triangles est tenu en éclaircissant la végétation."""
    W, D = plan.taille
    rect = plan.rectangle
    enfants: list[Noeud] = []
    # Sol : prairie autour, îlots au niveau des trottoirs avec le sol de leur zone, quais.
    marge = 0.04 * max(W, D)
    sol = [Partie(dalle_plate(rect.buffer(marge, join_style=2).difference(rect.buffer(-0.5)), -0.02), "herbe", "abords"),
           Partie(dalle_plate(rect.difference(plan.eau) if plan.eau is not None else rect, -0.05), "terre", "fond")]
    par_sol: dict[str, list] = defaultdict(list)
    for i in plan.ilots:
        poly = i.polygone
        mat = GABARITS_ZONE[i.zone]["sol"]
        if i.zone == "parc" and plan.allees is not None:
            allee = plan.allees.intersection(poly)
            par_sol["gravier"].append(allee)
            poly = poly.difference(allee)
        par_sol[mat].append(poly)
    for mat, geoms in par_sol.items():
        sol.append(Partie(dalle(unary_union(geoms), HAUT_TROTTOIR, 0.4), mat, f"ilots_{mat}"))
    if plan.quais is not None and not plan.quais.is_empty:
        sol.append(Partie(dalle(plan.quais.difference(plan.emprise_rues), HAUT_TROTTOIR, 0.4), "paves", "quais"))
    # Délaissés (reliquats trop petits ou sans accès pour être des îlots) : pelouse au niveau des trottoirs.
    occupe = unary_union([plan.emprise_rues, *(i.polygone for i in plan.ilots),
                          *([plan.eau.buffer(0.6, join_style=2)] if plan.eau is not None else []),
                          *([plan.quais] if plan.quais is not None else [])])
    delaisses = [p for p in _polygones(rect.difference(occupe)) if p.area > 2.0]
    if delaisses:
        sol.append(Partie(dalle(unary_union(delaisses), HAUT_TROTTOIR, 0.4), "herbe", "delaisses"))
    enfants.append(Noeud("sol", parties=sol, fusion=True))
    # Voirie.
    voirie = [Partie(dalle_plate(plan.chaussee, 0.0), "asphalte", "chaussee"),
              Partie(dalle(plan.trottoirs, HAUT_TROTTOIR, 0.25), "trottoir", "trottoirs")]
    bordures = plan.trottoirs.intersection(plan.chaussee.buffer(0.25, join_style=2))
    voirie.append(Partie(dalle(bordures, HAUT_TROTTOIR + 0.012, 0.27), "pierre", "bordures"))
    if plan.marquages:
        voirie.append(Partie(dalle_plate(unary_union(plan.marquages).intersection(plan.chaussee), 0.012), "marquage", "lignes"))
    if plan.passages:
        voirie.append(Partie(dalle_plate(unary_union(plan.passages).intersection(plan.chaussee), 0.014), "marquage", "passages"))
    # Ponts : tablier en pierre sous la chaussée, garde-corps, piles.
    style_pierre = any(voc.materiau(f)["famille"] == "facade" and f.startswith("facade_pierre")
                       for f in voc.STYLES_ARCHI[plan.style]["facades"])
    garde_corps = "pierre" if style_pierre else "metal_noir"
    for p in plan.ponts:
        ligne, L = p["ligne"], p["largeur"]
        voirie.append(Partie(dalle(p["polygone"].intersection(rect), -0.03, 1.1), "pierre", "tablier"))   # sous la chaussée
        for cote in (-1.0, 1.0):
            bord = ligne.offset_curve(cote * (L / 2.0 - 0.15))
            if not bord.is_empty:
                voirie.append(Partie(dalle(bord.buffer(0.15, cap_style=2).intersection(rect), HAUT_TROTTOIR + 1.0, 1.0),
                                     garde_corps, "garde_corps"))
        if ligne.length > 18.0 and plan.eau is not None:
            n_piles = int(ligne.length // 16.0)
            for k in range(1, n_piles + 1):
                c, d = _point_cote(ligne, ligne.length * k / (n_piles + 1), 0.0)
                nrm = np.array([-d[1], d[0]])
                pile = Polygon([c - 1.0 * d - (L / 2.0) * nrm, c + 1.0 * d - (L / 2.0) * nrm,
                                c + 1.0 * d + (L / 2.0) * nrm, c - 1.0 * d + (L / 2.0) * nrm])
                voirie.append(Partie(dalle(pile, -1.1, -1.1 - FOND_RIVIERE), "pierre", "pile"))
    enfants.append(Noeud("voirie", parties=voirie, fusion=True))
    # Eau : surface, lit, murs de quai.
    if plan.eau is not None and not plan.eau.is_empty:
        eau = [Partie(dalle_plate(plan.eau, NIVEAU_RIVIERE), "eau", "riviere"),
               Partie(dalle_plate(plan.eau, FOND_RIVIERE), "terre", "lit")]
        murs = plan.eau.buffer(0.6, join_style=2).difference(plan.eau).intersection(rect).difference(plan.emprise_rues)
        eau.append(Partie(dalle(murs, HAUT_TROTTOIR + 0.02, HAUT_TROTTOIR + 0.02 - FOND_RIVIERE), "pierre", "murs_de_quai"))
        enfants.append(Noeud("eau", parties=eau, fusion=True))
    # Bâtiments, un nœud par zone.
    par_zone: dict[str, list[Partie]] = defaultdict(list)
    for k, (ilot, lot, b) in enumerate(plan.batiments()):
        par_zone[ilot.zone].extend(maillage_batiment(b, graine=_graine(plan.graine, "toit", k)))
    for zone, parties in par_zone.items():
        enfants.append(Noeud(f"batiments_{zone}", parties=parties, fusion=True))
    tri_fixes = sum(len(p.maillage.faces) for n in enfants for p in n.parties)
    # Objets : variantes fabriquées une fois et réutilisées.
    cache: dict[tuple, Objet] = {}

    def objet(pl: Placement) -> Objet:
        opts = {k: v for k, v in pl.options.items() if k != "couleur"}
        cle = (pl.categorie, _cle_options(opts))
        if cle not in cache:
            cache[cle] = fabrique(pl.categorie, _graine(plan.graine, "objet", *cle), opts)
        return cache[cle]

    groupes = {"vegetation": [], "mobilier": [], "vehicules": []}
    for pl in plan.mobilier:
        groupe = voc.categorie(pl.categorie)["groupe"]
        nom = "vegetation" if groupe in ("vegetal", "mineral") else ("vehicules" if groupe == "vehicule" else "mobilier")
        groupes[nom].append(Instance(objet(pl), Pose(pl.x, pl.z, pl.lacet, pl.y), meta={"categorie": pl.categorie}))
    tri_objets = {k: sum(triangles_objet(i.objet) for i in v) for k, v in groupes.items()}
    eclaircissement = 1.0
    disponible = budget_triangles - tri_fixes - tri_objets["mobilier"] - tri_objets["vehicules"]
    if tri_objets["vegetation"] > max(0, disponible):
        # Éclaircissement uniforme EXACT : ordre aléatoire, on garde tant que le budget le permet.
        rng = np.random.default_rng(_graine(plan.graine, "eclaircir"))
        gardees, cumul = [], 0
        for k in rng.permutation(len(groupes["vegetation"])):
            inst = groupes["vegetation"][int(k)]
            t = triangles_objet(inst.objet)
            if cumul + t <= disponible:
                gardees.append(int(k))
                cumul += t
        groupes["vegetation"] = [groupes["vegetation"][k] for k in sorted(gardees)]
        eclaircissement = cumul / max(tri_objets["vegetation"], 1)
    for nom, instances in groupes.items():
        if instances:
            enfants.append(Noeud(nom, instances=instances, fusion=True))
    racine = Noeud("ville", enfants=enfants, extras={
        "taille": list(plan.taille), "trame": plan.trame, "style": plan.style, "graine": plan.graine,
        "parts_demandees": plan.parts_demandees, "parts_mesurees": plan.parts_mesurees,
        "batiments": len(plan.batiments()), "objets_fabriques": len(cache), "eclaircissement_vegetation":
            round(eclaircissement, 4), "triangles_fixes": int(tri_fixes)})
    return racine


# ── Démonstration et mire de façade ────────────────────────────────────────────────────────────────
SORTIE_DEMO = "/home/juan/AuroraIA/application/output/3d/essais/monde/ville_paysage"


class mire_facades:
    """Contrôle visuel des UV de façade : pendant le bloc, les matériaux de famille « facade » reçoivent une
    mire (une fenêtre sombre centrée par carreau = une travée × un étage). Outil de vérification seulement :
    les vraies textures viennent de `monde.materiaux`."""

    def __enter__(self):
        from PIL import Image, ImageDraw

        from monde import materiaux
        self._m = materiaux
        self._orig = materiaux.textures

        def textures(cle: str, resolution: int = 512):
            spec = voc.materiau(cle)
            if spec["famille"] != "facade":
                return self._orig(cle, resolution)
            r = 64
            fond = tuple(int(spec["couleur"][i:i + 2], 16) for i in (1, 3, 5))
            img = Image.new("RGB", (r, r), fond)
            d = ImageDraw.Draw(img)
            if spec["cle"] == "vitrine":
                d.rectangle([4, 10, r - 5, r - 6], fill=(40, 52, 60))
            elif spec["cle"] == "mur_rideau":
                d.rectangle([2, 4, r - 3, r - 3], fill=(60, 90, 115))
            else:
                d.rectangle([int(0.3 * r), int(0.2 * r), int(0.7 * r), int(0.72 * r)], fill=(38, 44, 52))
            return {"couleur": img}

        materiaux.textures = textures
        materiaux.materiau_trimesh.cache_clear()
        return self

    def __exit__(self, *exc):
        self._m.textures = self._orig
        self._m.materiau_trimesh.cache_clear()
        return False


def triangles_noeud(noeud: Noeud) -> int:
    total = 0
    for n in noeud.parcourir():
        total += sum(len(p.maillage.faces) for p in n.parties)
        total += sum(triangles_objet(i.objet) for i in n.instances)
    return total


def demo(nom: str, *, taille, trame, zones, style, riviere=False, graine=0, etages=None, mire=True, hdri="city",
         vues=("plan", "aerienne_sud_est", "aerienne_nord_ouest", "rasante")) -> dict[str, Any]:
    import time
    from pathlib import Path

    from monde import export_gltf, rendu
    from monde.ir import Scene

    t0 = time.monotonic()
    plan = concevoir_ville(taille=taille, trame=trame, zones=zones, style=style, riviere=riviere, graine=graine,
                           etages=etages)
    t1 = time.monotonic()
    racine = construire_ville(plan)
    t2 = time.monotonic()
    dossier = Path(SORTIE_DEMO) / nom
    glb = dossier / "ville.glb"
    if mire:
        with mire_facades():
            rapport = export_gltf.exporter(Scene(racine, extras={"programme": racine.extras}), glb)
    else:
        rapport = export_gltf.exporter(Scene(racine, extras={"programme": racine.extras}), glb)
    t3 = time.monotonic()
    rendus = rendu.rendre_vues(glb, dossier, vues=vues, resolution=(1100, 850), hdri=hdri)
    return {"conception_s": round(t1 - t0, 2), "construction_s": round(t2 - t1, 2), "export_s": round(t3 - t2, 2),
            "triangles": rapport["triangles"], "noeuds": rapport["noeuds"], "maillages": rapport["maillages"],
            "batiments": len(plan.batiments()), "parts_demandees": plan.parts_demandees,
            "parts_mesurees": plan.parts_mesurees, "planche": rendus.get("planche"),
            "blanc_pur_max": rendus.get("blanc_pur_max"), "extras": racine.extras, "ponts": len(plan.ponts)}


DEMOS = {
    "moderne_grille_400": dict(taille=(400.0, 400.0), trame="grille", style="moderne",
                               zones=[ZoneDemandee("centre", 0.25), ZoneDemandee("residentiel", 0.35),
                                      ZoneDemandee("parc", 0.15), ZoneDemandee("affaires", 0.25)]),
    "haussmannien_radiale_300": dict(taille=(300.0, 300.0), trame="radiale", style="haussmannien", riviere=True,
                                     zones=[ZoneDemandee("residentiel", 0.6), ZoneDemandee("centre", 0.3),
                                            ZoneDemandee("place", 0.1)]),
    "traditionnel_organique_300": dict(taille=(300.0, 300.0), trame="organique", style="traditionnel",
                                       zones=[ZoneDemandee("pavillonnaire", 0.88), ZoneDemandee("place", 0.12)]),
}


if __name__ == "__main__":
    import argparse
    import json

    p = argparse.ArgumentParser(description="Ville procédurale de contrôle (rendus f3d)")
    p.add_argument("demo", choices=sorted(DEMOS))
    p.add_argument("--graine", type=int, default=0)
    p.add_argument("--sans-mire", action="store_true")
    a = p.parse_args()
    res = demo(f"{a.demo}_{a.graine}", graine=a.graine, mire=not a.sans_mire, **DEMOS[a.demo])
    print(json.dumps(res, ensure_ascii=False, default=str, indent=1))
