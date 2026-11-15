"""Plan d'un logement complet : emprise, pièces, murs, portes, fenêtres, puis géométrie 3D des pièces.

Loi de plan (aucune règle par sujet ; seules les fonctions de pièces du vocabulaire comptent) :
- emprise rectangulaire d'aire = somme des surfaces demandées (+ part de circulation quand un couloir est
  ajouté), rapport longueur/largeur 1,2 à 1,7 tiré selon la graine ;
- pièces placées par découpage récursif (« slicing ») de l'emprise, dans l'ordre d'un parcours en largeur
  du graphe des adjacences depuis l'entrée, si bien que des pièces liées tombent côte à côte ;
- un couloir (fonction « couloir ») sert d'épine quand il y a plus de 5 pièces ou quand une pièce qui
  demande le jour (`FONCTIONS_PIECES[f]["fenetre"]`) ne toucherait pas la façade ;
- des centaines de découpages candidats sont MESURÉS (largeurs minimales, jour en façade, portes possibles,
  proportions, adjacences demandées, coût des passages) et le meilleur valide est gardé ;
- portes : un arbre couvrant du graphe des murs partagés relie TOUTES les pièces à l'entrée (Prim, coûts de
  liaison entre fonctions : une pièce d'eau s'ouvre sur un couloir, une entrée ou une chambre, pas sur la
  cuisine ; traverser une pièce privée coûte cher), plus les adjacences demandées que le mur permet ;
- fenêtres sur les murs extérieurs des pièces à jour : environ une par 3 m de façade, jamais devant une
  porte, loin des angles ; les pièces d'eau en façade reçoivent un petit jour haut.

Conventions de murs : les cellules des pièces pavent l'emprise et leurs frontières intérieures sont les axes
des cloisons (0,10 m) ; les murs extérieurs (0,25 m) sont entièrement à l'extérieur de l'emprise. Le
polygone d'une pièce (`PiecePlan.polygone`) est son sol LIBRE, entre les faces des murs : c'est ce que la
disposition des meubles utilise.

Géométrie (`construire_geometrie`) : un nœud par pièce (sol, demi-murs du côté de la pièce dans le
matériau de la pièce, plinthes, fenêtres, huisseries, vantaux de porte en `Instance` pivotant sur la
charnière), un nœud « facades » (demi-épaisseur extérieure) et un nœud « plafonds ». Les ouvertures sont de
vrais vides : chaque mur est extrudé par tranches de hauteur, ouvertures soustraites.
"""
from __future__ import annotations

import math
import random
from collections import deque
from dataclasses import dataclass, field
from typing import Any

from shapely.geometry import Polygon
from shapely.ops import unary_union

from monde import geometrie as g
from monde import vocabulaire as voc
from monde.ir import Instance, Noeud, Objet, Partie, Pose

# ── Constantes physiques (connaissance générale du bâtiment) ─────────────────────────────────────────
EP_EXT = 0.25                    # mur extérieur
EP_INT = 0.10                    # cloison
DEMI_INT = EP_INT / 2.0
LARGEUR_MIN_DEFAUT = 1.8
LARGEUR_MIN = {"wc": 0.9, "couloir": 0.9, "salle_d_eau": 0.9}
MARGE_PORTE = 0.15               # d'un bord de porte à l'extrémité du mur
LARGEUR_PORTE = (0.83, 0.9)
HAUTEUR_PORTE = 2.04
LARGEUR_PORTE_ENTREE = (0.9, 1.0)
HAUTEUR_PORTE_ENTREE = 2.15
LARGEUR_FENETRE = (1.0, 1.4)
HAUTEUR_FENETRE = (1.2, 1.4)
ALLEGE = 0.9
JOUR_HAUT = {"largeur": 0.6, "hauteur": 0.6, "allege": 1.5}
MARGE_ANGLE_FENETRE = 0.4
PAS_FENETRE = 3.0
EPAISSEUR_SOL = 0.04
COULOIR_LIBRE = (1.0, 1.2)
TOLERANCE_DIVERSITE = 0.8       # écart de note admis autour du meilleur plan (choix par la graine)
GRANDE_PIECE = 18.0             # m² : au-delà, une pièce d'angle prend le jour sur deux façades

PUBLIQUES = {"entree", "couloir", "salon", "salle_a_manger", "cuisine", "bureau"}
HUMIDES = {"salle_de_bain", "salle_d_eau", "wc", "buanderie"}
PRIVEES = {"chambre", "chambre_enfant", "dressing"}
VIVRE = ("salon", "salle_a_manger")

# Coût d'une porte entre deux fonctions (symétrique). Ce sont des usages d'habitat généraux.
_COUTS: dict[frozenset, float] = {}


def _cout(a: str, b: str, valeur: float) -> None:
    _COUTS[frozenset((a, b))] = valeur


for _f in voc.FONCTIONS_PIECES:
    _cout("couloir", _f, 1.0)
    _cout("entree", _f, 1.0)
_cout("entree", "couloir", 0.6)
for _a, _b, _v in [("salon", "salle_a_manger", 0.8), ("salon", "cuisine", 1.0), ("cuisine", "salle_a_manger", 0.8),
                   ("salon", "bureau", 1.6), ("cuisine", "buanderie", 1.4), ("chambre", "dressing", 1.0),
                   ("chambre", "salle_d_eau", 1.8), ("chambre", "salle_de_bain", 2.2), ("chambre", "wc", 4.0),
                   ("chambre_enfant", "salle_de_bain", 3.0), ("salon", "chambre", 3.5), ("salon", "chambre_enfant", 3.5),
                   ("salon", "wc", 5.0), ("salon", "salle_de_bain", 6.0), ("salon", "salle_d_eau", 6.0),
                   ("entree", "wc", 0.9), ("entree", "salle_de_bain", 1.4), ("entree", "chambre", 1.5),
                   ("entree", "chambre_enfant", 1.5)]:
    _cout(_a, _b, _v)
COUT_INTERDIT = 14.0             # pièce d'eau ↔ cuisine, chambre ↔ cuisine…
PENALITE_TRAVERSEE = 7.0         # passer par une pièce privée ou d'eau pour en atteindre une autre


def cout_liaison(fa: str, fb: str) -> float:
    if frozenset((fa, fb)) in _COUTS:
        return _COUTS[frozenset((fa, fb))]
    if fa == fb and fa in PRIVEES | HUMIDES:
        return 9.0
    if ("cuisine" in (fa, fb)) and ({fa, fb} & (HUMIDES | PRIVEES)):
        return COUT_INTERDIT
    if {fa, fb} & HUMIDES and {fa, fb} & HUMIDES == {fa, fb}:
        return 7.0
    if {fa, fb} <= PUBLIQUES:
        return 2.0
    return 4.0


def _largeur_meubles(fonction: str) -> float:
    """Largeur libre qu'exige le plus encombrant des meubles typiques posés dos au mur : le petit côté de son
    rectangle d'usage (dimensions moyennes + dégagements). Un lit double et ses passages imposent ~2,6 m."""
    besoin = 0.0
    for categorie, _, relations in voc.FONCTIONS_PIECES[fonction]["meubles_typiques"]:
        c = voc.CATEGORIES[categorie]
        if c["mural"] or c["plafond"] or c["sol_partage"]:
            continue
        if c["contre_mur"] != "oui" and not any(r == "contre_mur" for r, _ in relations):
            continue
        w = (c["largeur"][0] + c["largeur"][1]) / 2 + 2 * c["degagement_cotes"]
        p = (c["profondeur"][0] + c["profondeur"][1]) / 2 + c["degagement"]
        besoin = max(besoin, min(w, p))
    return besoin


def largeur_min(fonction: str) -> float:
    return max(LARGEUR_MIN.get(fonction, LARGEUR_MIN_DEFAUT), round(_largeur_meubles(fonction), 2))


# ── Structures ─────────────────────────────────────────────────────────────────────────────────────
@dataclass
class PieceDemandee:
    nom: str
    fonction: str
    surface: float
    adjacente_a: list[str] = field(default_factory=list)
    sol: str | None = None
    murs: str | None = None


@dataclass
class Ouverture:
    """Porte ou fenêtre. `centre` est sur l'AXE du mur (milieu de son épaisseur), `direction` le long du
    mur, `normale` de pieces[0] vers pieces[1] (ou vers l'extérieur si pieces[1] est None)."""
    type: str                                   # 'porte' | 'porte_entree' | 'fenetre'
    pieces: tuple[str, str | None]
    centre: tuple[float, float]
    direction: tuple[float, float]
    largeur: float
    hauteur: float
    allege: float = 0.0
    normale: tuple[float, float] = (0.0, 0.0)
    epaisseur: float = EP_INT
    ouvre_vers: str | None = None               # pièce dans laquelle le vantail débat
    charniere: int = 1                          # +1 : charnière à l'extrémité +direction
    nom: str = ""

    def _point(self, u: float, v: float) -> tuple[float, float]:
        (dx, dz), (nx, nz) = self.direction, self.normale
        return self.centre[0] + u * dx + v * nx, self.centre[1] + u * dz + v * nz

    def rectangle(self, marge_long: float = 0.0, marge_ep: float = 0.02) -> Polygon:
        """Vide de l'ouverture au sol, à travers toute l'épaisseur du mur."""
        hu, hv = self.largeur / 2.0 + marge_long, self.epaisseur / 2.0 + marge_ep
        return Polygon([self._point(u, v) for u, v in [(-hu, -hv), (hu, -hv), (hu, hv), (-hu, hv)]])

    def cote(self, piece: str | None) -> float:
        """+1 si `piece` est du côté de la normale, -1 sinon."""
        return 1.0 if piece == self.pieces[1] else -1.0

    def zone_devant(self, piece: str | None, profondeur: float, marge_long: float = 0.0) -> Polygon:
        """Bande au sol devant l'ouverture, du côté de `piece`, depuis la face du mur."""
        s = self.cote(piece)
        v0 = s * self.epaisseur / 2.0
        v1 = v0 + s * profondeur
        hu = self.largeur / 2.0 + marge_long
        return Polygon([self._point(u, v) for u, v in [(-hu, v0), (hu, v0), (hu, v1), (-hu, v1)]])

    def zone_battement(self, piece: str | None) -> Polygon:
        """Carré de la largeur de la porte devant elle, côté `piece` (débattement et passage)."""
        return self.zone_devant(piece, self.largeur)

    def point_face(self, piece: str | None, recul: float = 0.0) -> tuple[float, float]:
        s = self.cote(piece)
        return self._point(0.0, s * (self.epaisseur / 2.0 + recul))


@dataclass
class Mur:
    p0: tuple[float, float]                      # axe du mur
    p1: tuple[float, float]
    epaisseur: float
    pieces: tuple[str, str | None]
    exterieur: bool


@dataclass
class PiecePlan:
    nom: str
    fonction: str
    polygone: Polygon                            # sol libre, entre les faces des murs
    sol: str
    murs: str
    ouvertures: list[Ouverture]
    surface: float
    cellule: Polygon | None = None               # jusqu'aux axes des cloisons
    demandee: float | None = None                # surface demandée (None : couloir ajouté)


@dataclass
class Plan:
    pieces: list[PiecePlan]
    emprise: Polygon
    ouvertures: list[Ouverture]
    murs: list[Mur]
    entree: str                                  # pièce qui porte la porte d'entrée
    hauteur_plafond: float
    materiau_exterieur: str = "platre_peint"
    mesures: dict[str, Any] = field(default_factory=dict)

    def piece(self, nom: str) -> PiecePlan:
        for p in self.pieces:
            if p.nom == nom:
                return p
        raise KeyError(f"pièce inconnue : {nom!r}")


# ── Découpage ──────────────────────────────────────────────────────────────────────────────────────
Rect = tuple[float, float, float, float]          # x0, z0, x1, z1 (cellule : axes des cloisons)
EPS = 1e-6


def _cellule_min(fonction: str) -> float:
    """Côté minimal d'une cellule : largeur libre minimale, assez pour une porte de côté, + deux demi-cloisons."""
    porte = LARGEUR_PORTE[0] + 2 * MARGE_PORTE
    return max(largeur_min(fonction), porte) + EP_INT


def _trancher(rect: Rect, noms: list[str], aires: dict[str, float], fonctions: dict[str, str],
              rng: random.Random, axe_bande: bool) -> dict[str, Rect]:
    if len(noms) == 1:
        return {noms[0]: rect}
    x0, z0, x1, z1 = rect
    w, d = x1 - x0, z1 - z0
    if axe_bande:
        coupe_x = rng.random() < 0.85                       # coupe perpendiculaire à la bande (le long de x)
    else:
        coupe_x = (w >= d) if rng.random() < 0.8 else (w < d)
    total = sum(aires[n] for n in noms)
    cumul, options = 0.0, []
    for k in range(1, len(noms)):
        cumul += aires[noms[k - 1]]
        options.append((abs(cumul / total - 0.5), k))
    options.sort()
    poids = [0.6, 0.3, 0.1][:len(options)]
    k = rng.choices([o[1] for o in options[:len(poids)]], weights=poids)[0]
    a, b = noms[:k], noms[k:]
    if rng.random() < 0.5:
        a, b = b, a
    fraction = sum(aires[n] for n in a) / total
    etendue = w if coupe_x else d

    def minimum(groupe: list[str]) -> float:
        valeurs = [_cellule_min(fonctions[n]) for n in groupe]
        return sum(valeurs) if axe_bande else max(valeurs)

    pos = etendue * fraction
    bas, haut = minimum(a), etendue - minimum(b)
    if bas <= haut:
        pos = min(max(pos, bas), haut)
    if coupe_x:
        ra, rb = (x0, z0, x0 + pos, z1), (x0 + pos, z0, x1, z1)
    else:
        ra, rb = (x0, z0, x1, z0 + pos), (x0, z0 + pos, x1, z1)
    sortie = _trancher(ra, a, aires, fonctions, rng, axe_bande)
    sortie.update(_trancher(rb, b, aires, fonctions, rng, axe_bande))
    return sortie


def _nom_libre(base: str, pris: set[str]) -> str:
    if base not in pris:
        return base
    i = 2
    while f"{base}_{i}" in pris:
        i += 1
    return f"{base}_{i}"


def _candidat(demandes: list[PieceDemandee], ordre: list[str], mode: str, rapport: float, rng: random.Random,
              echelle: float, nom_couloir: str) -> tuple[dict[str, Rect], Rect, dict[str, str], float]:
    """Un découpage candidat : cellules par pièce, emprise, fonctions (couloir compris), largeur du couloir."""
    fonctions = {d.nom: d.fonction for d in demandes}
    aires = {d.nom: d.surface * echelle for d in demandes}
    total = sum(aires.values())
    if mode == "decoupage":
        longueur = math.sqrt(total * rapport)
        profondeur = total / longueur
        emprise = (-longueur / 2, -profondeur / 2, longueur / 2, profondeur / 2)
        return _trancher(emprise, ordre, aires, fonctions, rng, False), emprise, fonctions, 0.0

    largeur_c = rng.uniform(*COULOIR_LIBRE) + EP_INT
    vivre = [n for n in ordre if fonctions[n] in VIVRE]
    fin: list[str] = []
    if vivre and rng.random() < 0.6:
        fin = [vivre[0]]
        voisins = [n for n in ordre if n not in fin and fonctions[n] in ("cuisine", "salle_a_manger", "salon")]
        if voisins and rng.random() < 0.35:
            fin.append(voisins[0])
    bandes: dict[int, list[str]] = {0: [], 1: []}
    aires_b = {0: 0.0, 1: 0.0}
    for n in ordre:
        if n in fin:
            continue
        petite = 0 if aires_b[0] <= aires_b[1] else 1
        cote = petite if rng.random() < 0.7 else 1 - petite
        bandes[cote].append(n)
        aires_b[cote] += aires[n]
    if not bandes[0] or not bandes[1]:
        plein = 0 if bandes[0] else 1
        if len(bandes[plein]) >= 2:
            bandes[1 - plein].append(bandes[plein].pop())
            aires_b = {c: sum(aires[n] for n in bandes[c]) for c in (0, 1)}
    a_fin = sum(aires[n] for n in fin)
    longueur = math.sqrt(total * rapport)
    for _ in range(30):
        profondeur = longueur / rapport
        l_fin = a_fin / profondeur
        longueur = math.sqrt(rapport * (total + largeur_c * (longueur - l_fin)))
    profondeur = longueur / rapport
    l_fin = a_fin / profondeur
    if profondeur - largeur_c < 2 * _cellule_min("salon"):
        return {}, (0, 0, 0, 0), fonctions, largeur_c
    x0, z0, x1, z1 = -longueur / 2, -profondeur / 2, longueur / 2, profondeur / 2
    fin_a_droite = rng.random() < 0.5
    if fin_a_droite:
        xa, xb = x0, x1 - l_fin
        rect_fin = (x1 - l_fin, z0, x1, z1)
    else:
        xa, xb = x0 + l_fin, x1
        rect_fin = (x0, z0, x0 + l_fin, z1)
    somme = aires_b[0] + aires_b[1]
    d0 = (profondeur - largeur_c) * (aires_b[0] / somme if somme > 0 else 0.5)
    cellules: dict[str, Rect] = {}
    if bandes[0]:
        cellules.update(_trancher((xa, z0, xb, z0 + d0), bandes[0], aires, fonctions, rng, True))
    cellules[nom_couloir] = (xa, z0 + d0, xb, z0 + d0 + largeur_c)
    if bandes[1]:
        cellules.update(_trancher((xa, z0 + d0 + largeur_c, xb, z1), bandes[1], aires, fonctions, rng, True))
    if fin:
        cellules.update(_trancher(rect_fin, fin, aires, fonctions, rng, False))
    fonctions = dict(fonctions, **{nom_couloir: "couloir"})
    return cellules, (x0, z0, x1, z1), fonctions, largeur_c


# ── Mesures d'un découpage ─────────────────────────────────────────────────────────────────────────
def _libre(cell: Rect, emprise: Rect) -> Rect:
    """Rectangle libre : la cellule moins une demi-cloison sur chaque côté intérieur."""
    x0, z0, x1, z1 = cell
    ex0, ez0, ex1, ez1 = emprise
    return (x0 + (0 if abs(x0 - ex0) < EPS else DEMI_INT), z0 + (0 if abs(z0 - ez0) < EPS else DEMI_INT),
            x1 - (0 if abs(x1 - ex1) < EPS else DEMI_INT), z1 - (0 if abs(z1 - ez1) < EPS else DEMI_INT))


def _cotes_exterieurs(cell: Rect, libre: Rect, emprise: Rect) -> list[tuple[str, float, float]]:
    """Côtés de la cellule sur la façade : (côté 'x0'|'x1'|'z0'|'z1', début, fin le long du côté, en libre)."""
    x0, z0, x1, z1 = cell
    lx0, lz0, lx1, lz1 = libre
    ex0, ez0, ex1, ez1 = emprise
    sortie = []
    if abs(x0 - ex0) < EPS:
        sortie.append(("x0", lz0, lz1))
    if abs(x1 - ex1) < EPS:
        sortie.append(("x1", lz0, lz1))
    if abs(z0 - ez0) < EPS:
        sortie.append(("z0", lx0, lx1))
    if abs(z1 - ez1) < EPS:
        sortie.append(("z1", lx0, lx1))
    return sortie


def _mur_partage(ca: Rect, cb: Rect, la: Rect, lb: Rect) -> tuple[str, float, float, float] | None:
    """Mur commun de deux cellules : (axe 'x' si le mur est à x constant, coordonnée de l'axe, début, fin de la
    portée libre commune)."""
    if abs(ca[2] - cb[0]) < EPS or abs(cb[2] - ca[0]) < EPS:
        x = ca[2] if abs(ca[2] - cb[0]) < EPS else ca[0]
        s0, s1 = max(la[1], lb[1]), min(la[3], lb[3])
        if s1 - s0 > EPS:
            return ("x", x, s0, s1)
    if abs(ca[3] - cb[1]) < EPS or abs(cb[3] - ca[1]) < EPS:
        z = ca[3] if abs(ca[3] - cb[1]) < EPS else ca[1]
        s0, s1 = max(la[0], lb[0]), min(la[2], lb[2])
        if s1 - s0 > EPS:
            return ("z", z, s0, s1)
    return None


def _arbre_portes(noms: list[str], fonctions: dict[str, str], voisins: dict[str, dict[str, float]], racine: str,
                  demandees: set[frozenset]) -> tuple[list[tuple[str, str]], float, set[str]]:
    """Prim depuis l'entrée ; une pièce privée ou d'eau ne sert de passage qu'au prix fort."""
    dans = {racine}
    aretes: list[tuple[str, str]] = []
    cout_total = 0.0
    while len(dans) < len(noms):
        meilleur = None
        for a in dans:
            traverse = 0.0 if (a == racine or fonctions[a] in PUBLIQUES) else PENALITE_TRAVERSEE
            for b in voisins[a]:
                if b in dans:
                    continue
                c = cout_liaison(fonctions[a], fonctions[b])
                if frozenset((a, b)) in demandees:
                    c *= 0.4
                c += traverse
                if meilleur is None or c < meilleur[0]:
                    meilleur = (c, a, b)
        if meilleur is None:
            break
        c, a, b = meilleur
        dans.add(b)
        aretes.append((a, b))
        cout_total += c
    return aretes, cout_total, set(noms) - dans


def _racine(noms: list[str], fonctions: dict[str, str]) -> str:
    for f in ("entree", "salon", "salle_a_manger", "cuisine", "couloir"):
        for n in noms:
            if fonctions[n] == f:
                return n
    return noms[0]


def _evaluer(cellules: dict[str, Rect], emprise: Rect, fonctions: dict[str, str], demandes: list[PieceDemandee],
             rng: random.Random) -> dict[str, Any]:
    noms = list(cellules)
    libres = {n: _libre(cellules[n], emprise) for n in noms}
    violations: list[str] = []
    score = 0.0
    voulues = {d.nom: d.surface for d in demandes}
    for n in noms:
        lx0, lz0, lx1, lz1 = libres[n]
        w, d = lx1 - lx0, lz1 - lz0
        petit, grand = min(w, d), max(w, d)
        f = fonctions[n]
        if petit < largeur_min(f) - 1e-6:
            violations.append(f"{n} trop étroite ({petit:.2f} m < {largeur_min(f):.2f} m)")
        if f != "couloir" and petit > 0:
            limite = 2.6 if f in HUMIDES else 2.0
            ratio = grand / petit
            score += 0.3 * (ratio - 1.0) + (8.0 * (ratio - limite) if ratio > limite else 0.0)
        if n in voulues:
            score += 2.0 * abs(w * d - voulues[n]) / voulues[n]
        ext = _cotes_exterieurs(cellules[n], libres[n], emprise)
        plus_long = max((s1 - s0 for _, s0, s1 in ext), default=0.0)
        if voc.FONCTIONS_PIECES[f]["fenetre"] and plus_long < LARGEUR_FENETRE[0] + 2 * MARGE_ANGLE_FENETRE:
            violations.append(f"{n} n'a pas de façade pour une fenêtre")
    racine = _racine(noms, fonctions)
    ext_racine = _cotes_exterieurs(cellules[racine], libres[racine], emprise)
    if max((s1 - s0 for _, s0, s1 in ext_racine), default=0.0) < LARGEUR_PORTE_ENTREE[0] + 2 * MARGE_PORTE:
        violations.append(f"{racine} n'a pas de façade pour la porte d'entrée")
    voisins: dict[str, dict[str, float]] = {n: {} for n in noms}
    for i, a in enumerate(noms):
        for b in noms[i + 1:]:
            mur = _mur_partage(cellules[a], cellules[b], libres[a], libres[b])
            if mur and mur[3] - mur[2] >= LARGEUR_PORTE[0] + 2 * MARGE_PORTE - 1e-9:
                voisins[a][b] = voisins[b][a] = mur[3] - mur[2]
    demandees = {frozenset((d.nom, v)) for d in demandes for v in d.adjacente_a}
    aretes, cout, isolees = _arbre_portes(noms, fonctions, voisins, racine, demandees)
    if isolees:
        violations.append("pièces sans porte possible : " + ", ".join(sorted(isolees)))
    score += cout
    for paire in demandees:
        a, b = tuple(paire)
        if b not in voisins.get(a, {}):
            score += 3.0
    score += rng.random() * 0.05
    return {"valide": not violations, "violations": violations, "score": score, "aretes": aretes,
            "voisins": voisins, "racine": racine, "libres": libres}


def _ordre_bfs(demandes: list[PieceDemandee], rng: random.Random) -> list[str]:
    noms = [d.nom for d in demandes]
    fonctions = {d.nom: d.fonction for d in demandes}
    liens: dict[str, list[tuple[float, str]]] = {n: [] for n in noms}
    demandees = {frozenset((d.nom, v)) for d in demandes for v in d.adjacente_a}
    for i, a in enumerate(noms):
        for b in noms[i + 1:]:
            c = cout_liaison(fonctions[a], fonctions[b])
            if frozenset((a, b)) in demandees:
                c = 0.0
            if c <= 2.2:
                liens[a].append((c, b))
                liens[b].append((c, a))
    racine = _racine(noms, fonctions)
    vus, ordre, file = {racine}, [], deque([racine])
    while file:
        n = file.popleft()
        ordre.append(n)
        suivants = sorted(liens[n], key=lambda cb: cb[0] + rng.random() * 0.8)
        for _, m in suivants:
            if m not in vus:
                vus.add(m)
                file.append(m)
    reste = [n for n in noms if n not in vus]
    rng.shuffle(reste)
    return ordre + reste


# ── Plan complet ───────────────────────────────────────────────────────────────────────────────────
def _materiau_facade(style: str | None, rng: random.Random) -> str:
    """Les façades du vocabulaire peignent des fenêtres dans leur motif ; un logement a de VRAIES fenêtres :
    on prend le parement uni de la même famille."""
    if not style:
        return "platre_peint"
    if style not in voc.STYLES_ARCHI:
        raise KeyError(f"style d'architecture hors vocabulaire : {style!r}")
    uni = {"facade_enduit": "platre_peint:creme", "facade_brique": "brique", "facade_pierre": "pierre",
           "facade_beton": "beton_cire", "facade_bois": "lambris", "mur_rideau": "beton_cire",
           "vitrine": "beton_cire"}
    return uni.get(rng.choice(voc.STYLES_ARCHI[style]["facades"]), "platre_peint")


def _verifier_entree(pieces: list[PieceDemandee]) -> None:
    if not pieces:
        raise ValueError("aucune pièce demandée")
    noms = [p.nom for p in pieces]
    if len(set(noms)) != len(noms):
        raise ValueError(f"noms de pièces en double : {noms}")
    for p in pieces:
        voc.fonction_piece(p.fonction)
        if p.surface <= 0:
            raise ValueError(f"surface non positive pour {p.nom!r}")
        for v in p.adjacente_a:
            if v not in noms:
                raise KeyError(f"adjacence vers une pièce inconnue : {p.nom!r} → {v!r}")
        for m in (p.sol, p.murs):
            if m:
                voc.materiau(m)


def _rechercher(demandes: list[PieceDemandee], mode: str, rapport: float | None, graine: int,
                essais: int, nom_couloir: str) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    meilleur, moins_mauvais = None, None
    valides: list[dict[str, Any]] = []
    total_voulu = sum(d.surface for d in demandes)
    for t in range(essais):
        germe = (graine * 1_000_003 + t * 7919 + (0 if mode == "decoupage" else 500_009)) & 0xFFFFFFFF
        echelle = 1.0
        for _passe in range(2):                     # 2e passe : compense l'emprise perdue par les cloisons
            rng = random.Random(germe)
            r = rapport if rapport else rng.uniform(1.2, 1.7)
            ordre = _ordre_bfs(demandes, rng)
            cellules, emprise, fonctions, largeur_c = _candidat(demandes, ordre, mode, r, rng, echelle, nom_couloir)
            if not cellules:
                break
            libres = {n: _libre(cellules[n], emprise) for n in cellules}
            voulus = {d.nom for d in demandes}
            obtenu = sum((l[2] - l[0]) * (l[3] - l[1]) for n, l in libres.items() if n in voulus)
            echelle *= total_voulu / max(obtenu, 1e-6)
        if not cellules:
            continue
        ev = _evaluer(cellules, emprise, fonctions, demandes, rng)
        ev.update(cellules=cellules, emprise=emprise, fonctions=fonctions, rapport=r, mode=mode, germe=germe)
        if ev["valide"]:
            valides.append(ev)
        elif moins_mauvais is None or len(ev["violations"]) < len(moins_mauvais["violations"]):
            moins_mauvais = ev
    if valides:
        # Diversité : la graine choisit parmi les plans valides PROCHES du meilleur (écart de note borné), pas
        # toujours l'unique optimum — deux graines donnent deux logements différents et tous deux bons.
        valides.sort(key=lambda e: e["score"])
        seuil = valides[0]["score"] + max(TOLERANCE_DIVERSITE, 0.1 * abs(valides[0]["score"]))
        proches = [e for e in valides if e["score"] <= seuil][:12]
        meilleur = random.Random(graine * 2_654_435_761 + len(demandes)).choice(proches)
    return meilleur, moins_mauvais


def concevoir_plan(pieces: list[PieceDemandee], *, hauteur_plafond: float = 2.5, rapport: float | None = None,
                   graine: int = 0, style: str | None = None, essais: int = 240) -> Plan:
    """Conçoit le plan (pièces, murs, portes, fenêtres). Si aucun découpage ne respecte toutes les règles,
    le moins mauvais est rendu avec ses violations dans `plan.mesures["violations"]` (jamais en silence)."""
    _verifier_entree(pieces)
    demandes = list(pieces)
    nom_couloir = _nom_libre("couloir", {p.nom for p in demandes})
    modes = ["couloir"] if len(demandes) > 5 else ["decoupage", "couloir"]
    choisi, repli = None, None
    for mode in modes:
        if mode == "couloir" and len(demandes) < 2:
            continue
        meilleur, moins_mauvais = _rechercher(demandes, mode, rapport, graine, essais, nom_couloir)
        if meilleur is not None:
            choisi = meilleur
            break
        if moins_mauvais is not None and (repli is None or len(moins_mauvais["violations"]) < len(repli["violations"])):
            repli = moins_mauvais
    if choisi is None:
        if repli is None:
            raise ValueError("aucun découpage constructible pour ce programme")
        choisi = repli
    rng = random.Random(choisi["germe"] ^ 0x5F3759DF)
    return _construire_plan(demandes, choisi, hauteur_plafond, rng, _materiau_facade(style, rng), style)


def _construire_plan(demandes: list[PieceDemandee], ev: dict[str, Any], hauteur: float, rng: random.Random,
                     materiau_ext: str, style: str | None) -> Plan:
    cellules: dict[str, Rect] = ev["cellules"]
    emprise: Rect = ev["emprise"]
    fonctions: dict[str, str] = ev["fonctions"]
    libres: dict[str, Rect] = ev["libres"]
    par_nom = {d.nom: d for d in demandes}
    noms = list(cellules)
    racine = ev["racine"]
    interieur_style = voc.STYLES_ARCHI[style]["interieur"] if style else {}

    # Murs
    murs: list[Mur] = []
    for i, a in enumerate(noms):
        for b in noms[i + 1:]:
            ca, cb = cellules[a], cellules[b]
            if abs(ca[2] - cb[0]) < EPS or abs(cb[2] - ca[0]) < EPS:
                x = ca[2] if abs(ca[2] - cb[0]) < EPS else ca[0]
                s0, s1 = max(ca[1], cb[1]), min(ca[3], cb[3])
                if s1 - s0 > EPS:
                    murs.append(Mur((x, s0), (x, s1), EP_INT, (a, b), False))
            if abs(ca[3] - cb[1]) < EPS or abs(cb[3] - ca[1]) < EPS:
                z = ca[3] if abs(ca[3] - cb[1]) < EPS else ca[1]
                s0, s1 = max(ca[0], cb[0]), min(ca[2], cb[2])
                if s1 - s0 > EPS:
                    murs.append(Mur((s0, z), (s1, z), EP_INT, (a, b), False))
    ex0, ez0, ex1, ez1 = emprise
    demi_ext = EP_EXT / 2.0
    for n in noms:
        x0, z0, x1, z1 = cellules[n]
        if abs(x0 - ex0) < EPS:
            murs.append(Mur((x0 - demi_ext, z0), (x0 - demi_ext, z1), EP_EXT, (n, None), True))
        if abs(x1 - ex1) < EPS:
            murs.append(Mur((x1 + demi_ext, z0), (x1 + demi_ext, z1), EP_EXT, (n, None), True))
        if abs(z0 - ez0) < EPS:
            murs.append(Mur((x0, z0 - demi_ext), (x1, z0 - demi_ext), EP_EXT, (n, None), True))
        if abs(z1 - ez1) < EPS:
            murs.append(Mur((x0, z1 + demi_ext), (x1, z1 + demi_ext), EP_EXT, (n, None), True))

    ouvertures: list[Ouverture] = []
    par_piece: dict[str, list[Ouverture]] = {n: [] for n in noms}

    def profondeur_libre(n: str, axe: str) -> float:
        lx0, lz0, lx1, lz1 = libres[n]
        return (lx1 - lx0) if axe == "x" else (lz1 - lz0)

    def placer_porte(a: str, b: str, parent: str) -> Ouverture | None:
        mur = _mur_partage(cellules[a], cellules[b], libres[a], libres[b])
        if mur is None:
            return None
        axe, coord, s0, s1 = mur
        portee = s1 - s0
        largeur = LARGEUR_PORTE[1] if portee >= LARGEUR_PORTE[1] + 2 * MARGE_PORTE else LARGEUR_PORTE[0]
        if portee < largeur + 2 * MARGE_PORTE - 1e-9:
            return None
        lo, hi = s0 + MARGE_PORTE + largeur / 2, s1 - MARGE_PORTE - largeur / 2
        options = sorted({lo, hi, (lo + hi) / 2})
        existantes = par_piece[a] + par_piece[b]

        def point(s: float) -> tuple[float, float]:
            return (coord, s) if axe == "x" else (s, coord)

        def note(s: float) -> float:
            # près d'un angle (le reste du mur reste meublable), loin des autres portes (débattements séparés)
            p = point(s)
            dist = min((math.dist(p, o.centre) for o in existantes), default=9.0)
            bord = min(s - lo, hi - s)
            return -min(dist, 2.0) + 0.8 * bord + rng.random() * 0.01
        s = min(options, key=note)
        centre = point(s)
        # normale de a vers b
        ca, cb = cellules[a], cellules[b]
        if axe == "x":
            direction, normale = (0.0, 1.0), ((1.0, 0.0) if ca[0] < cb[0] else (-1.0, 0.0))
        else:
            direction, normale = (1.0, 0.0), ((0.0, 1.0) if ca[1] < cb[1] else (0.0, -1.0))
        enfant = b if parent == a else a
        autre = a if enfant == b else b
        axe_profondeur = "x" if axe == "x" else "z"
        # le vantail débat dans la pièce desservie, sauf si elle est trop courte pour son carré de débattement
        ouvre = enfant if profondeur_libre(enfant, axe_profondeur) >= largeur + 0.3 else autre
        charniere = 1 if (s1 - s) < (s - s0) else -1               # côté de l'angle le plus proche
        o = Ouverture("porte", (a, b), centre, direction, largeur, HAUTEUR_PORTE, 0.0, normale, EP_INT, ouvre,
                      charniere, f"porte_{a}_{b}")
        return o

    for parent, enfant in ev["aretes"]:
        o = placer_porte(parent, enfant, parent)
        if o is None:
            continue
        ouvertures.append(o)
        par_piece[o.pieces[0]].append(o)
        par_piece[o.pieces[1]].append(o)
    deja = {frozenset(o.pieces) for o in ouvertures}
    for d in demandes:
        for v in d.adjacente_a:
            if frozenset((d.nom, v)) in deja:
                continue
            fa, fb = fonctions[d.nom], fonctions[v]
            o = placer_porte(d.nom, v, d.nom if fa in PUBLIQUES or fb not in PUBLIQUES else v)
            if o is not None:
                ouvertures.append(o)
                par_piece[d.nom].append(o)
                par_piece[v].append(o)
                deja.add(frozenset((d.nom, v)))

    def point_facade(n: str, cote: str, s: float) -> tuple[tuple[float, float], tuple[float, float], tuple[float, float]]:
        x0, z0, x1, z1 = cellules[n]
        if cote == "x0":
            return (x0 - demi_ext, s), (0.0, 1.0), (-1.0, 0.0)
        if cote == "x1":
            return (x1 + demi_ext, s), (0.0, 1.0), (1.0, 0.0)
        if cote == "z0":
            return (s, z0 - demi_ext), (1.0, 0.0), (0.0, -1.0)
        return (s, z1 + demi_ext), (1.0, 0.0), (0.0, 1.0)

    # Porte d'entrée. Dans un hall (fonction « entree ») : façade la plus longue, au milieu. Dans une pièce de
    # vie qui sert d'entrée : la façade la plus COURTE qui la reçoit, près d'un angle — les grandes façades
    # restent aux fenêtres et les murs pleins aux meubles.
    ext_racine = _cotes_exterieurs(cellules[racine], libres[racine], emprise)
    largeur_e = rng.uniform(*LARGEUR_PORTE_ENTREE)
    hall = fonctions[racine] == "entree"
    possibles = [c for c in ext_racine if c[2] - c[1] >= LARGEUR_PORTE_ENTREE[0] + 2 * MARGE_PORTE]
    if possibles:
        cote, s0, s1 = (max if hall else min)(possibles, key=lambda c: c[2] - c[1])
        largeur = min(largeur_e, s1 - s0 - 2 * MARGE_PORTE)
        if hall:
            s, charniere = (s0 + s1) / 2.0, (1 if rng.random() < 0.5 else -1)
        else:
            pres_debut = rng.random() < 0.5
            marge = min(MARGE_PORTE + 0.15, (s1 - s0 - largeur) / 2)
            s = s0 + marge + largeur / 2 if pres_debut else s1 - marge - largeur / 2
            charniere = -1 if pres_debut else 1
        centre, direction, normale = point_facade(racine, cote, s)
        o = Ouverture("porte_entree", (racine, None), centre, direction, largeur, HAUTEUR_PORTE_ENTREE, 0.0, normale,
                      EP_EXT, racine, charniere, f"porte_{racine}_exterieur")
        ouvertures.append(o)
        par_piece[racine].append(o)

    # Fenêtres.
    for n in noms:
        f = fonctions[n]
        jour = voc.FONCTIONS_PIECES[f]["fenetre"]
        haut = (not jour) and f in HUMIDES
        if not jour and not haut:
            continue
        cotes = _cotes_exterieurs(cellules[n], libres[n], emprise)
        if not cotes:
            continue
        # Une pièce prend le jour sur UNE façade (deux pour une pièce de vie ou une grande pièce d'angle) :
        # les plus longues, de préférence sans la porte d'entrée. Les autres murs restent pleins (lit, armoire).
        normales_entree = {o.normale for o in par_piece[n] if o.type == "porte_entree"}
        minimum = 0.5 if haut else LARGEUR_FENETRE[0] * 0.8
        cotes = [c for c in cotes if c[2] - c[1] - 2 * MARGE_ANGLE_FENETRE >= minimum]
        cotes.sort(key=lambda c: (point_facade(n, c[0], 0.0)[2] in normales_entree, -(c[2] - c[1])))
        surface_n = (libres[n][2] - libres[n][0]) * (libres[n][3] - libres[n][1])
        cotes = cotes[:1 if haut else (2 if f in VIVRE or surface_n > GRANDE_PIECE else 1)]
        allege = JOUR_HAUT["allege"] if haut else _allege(f)
        largeur_voulue = JOUR_HAUT["largeur"] if haut else rng.uniform(*LARGEUR_FENETRE)
        hauteur_voulue = JOUR_HAUT["hauteur"] if haut else rng.uniform(*HAUTEUR_FENETRE)
        hauteur_f = max(0.4, min(hauteur_voulue, hauteur - allege - 0.15))
        for cote, s0, s1 in cotes:
            portee = s1 - s0
            utile = portee - 2 * MARGE_ANGLE_FENETRE
            if utile < (0.5 if haut else LARGEUR_FENETRE[0] * 0.8):
                continue
            nombre = 1 if haut else max(1, int(round(portee / PAS_FENETRE)))
            largeur = min(largeur_voulue, utile)
            while nombre > 1 and nombre * (largeur + 0.6) > utile:
                nombre -= 1
            portes_facade = [o for o in par_piece[n] if o.type == "porte_entree"
                             and point_facade(n, cote, 0.0)[2] == o.normale]
            for i in range(nombre):
                s = s0 + MARGE_ANGLE_FENETRE + utile * (i + 0.5) / nombre
                centre, direction, normale = point_facade(n, cote, s)
                conflit = False
                for p in portes_facade:
                    sp = p.centre[1] if cote in ("x0", "x1") else p.centre[0]
                    ecart = abs(s - sp) - (largeur + p.largeur) / 2.0
                    if ecart < 0.4:
                        # on glisse la fenêtre du côté le plus libre, sinon on la retire
                        decal = (largeur + p.largeur) / 2.0 + 0.4
                        candidats = [sp - decal, sp + decal]
                        candidats = [c for c in candidats if s0 + MARGE_ANGLE_FENETRE + largeur / 2 <= c
                                     <= s1 - MARGE_ANGLE_FENETRE - largeur / 2]
                        if candidats:
                            s = min(candidats, key=lambda c: abs(c - s))
                            centre, direction, normale = point_facade(n, cote, s)
                        else:
                            conflit = True
                if conflit:
                    continue
                o = Ouverture("fenetre", (n, None), centre, direction, largeur, hauteur_f, allege, normale, EP_EXT,
                              None, 1, f"fenetre_{n}_{len([x for x in par_piece[n] if x.type == 'fenetre']) + 1}")
                ouvertures.append(o)
                par_piece[n].append(o)

    pieces_plan: list[PiecePlan] = []
    for n in noms:
        d = par_nom.get(n)
        f = fonctions[n]
        spec = voc.FONCTIONS_PIECES[f]
        sol = (d.sol if d and d.sol else None) or (interieur_style.get("sol") if f not in HUMIDES and interieur_style
                                                    else None) or spec["sol"]
        murs_m = (d.murs if d and d.murs else None) or (interieur_style.get("murs") if f not in HUMIDES
                                                        and interieur_style else None) or spec["murs"]
        poly = g.rectangle_xz(*libres[n])
        pieces_plan.append(PiecePlan(n, f, poly, sol, murs_m, par_piece[n], float(poly.area), g.rectangle_xz(*cellules[n]),
                                     d.surface if d else None))

    voulu = sum(d.surface for d in demandes)
    obtenu = sum(p.surface for p in pieces_plan if p.demandee is not None)
    mesures = {"mode": ev["mode"], "rapport": round(ev["rapport"], 3), "score": round(ev["score"], 3),
               "violations": list(ev["violations"]), "valide": bool(ev["valide"]),
               "surface_demandee": round(voulu, 2), "surface_obtenue": round(obtenu, 2),
               "ecart_surface": round((obtenu - voulu) / voulu, 4),
               "couloir_ajoute": ev["mode"] == "couloir",
               "surface_circulation": round(sum(p.surface for p in pieces_plan if p.demandee is None), 2),
               "emprise_m2": round((emprise[2] - emprise[0]) * (emprise[3] - emprise[1]), 2),
               "portes": sum(1 for o in ouvertures if o.type == "porte"),
               "fenetres": sum(1 for o in ouvertures if o.type == "fenetre")}
    return Plan(pieces_plan, g.rectangle_xz(*emprise), ouvertures, murs, racine, hauteur, materiau_ext, mesures)


def _allege(fonction: str) -> float:
    """Allège : 0,9 m, relevée au-dessus des meubles qu'on place sous la fenêtre dans cette fonction (plan de
    travail d'une cuisine : 0,92 m → 1,02 m). Connaissance tirée du vocabulaire, pas d'une liste."""
    hauteurs = [voc.CATEGORIES[c]["hauteur"][1] for c, _, rel in voc.FONCTIONS_PIECES[fonction]["meubles_typiques"]
                if any(r == "sous_fenetre" for r, _ in rel)]
    return max([ALLEGE] + [h + 0.1 for h in hauteurs])


# ── Vérification indépendante d'un plan ────────────────────────────────────────────────────────────
def verifier_plan(plan: Plan) -> dict[str, Any]:
    """Mesures recalculées depuis le plan livré (pas depuis la recherche) : accessibilité par les portes,
    largeurs, jour, fenêtres en façade, surfaces."""
    noms = [p.nom for p in plan.pieces]
    graphe: dict[str, set[str]] = {n: set() for n in noms}
    for o in plan.ouvertures:
        if o.type == "porte":
            a, b = o.pieces
            graphe[a].add(b)
            graphe[b].add(a)
    vus, file = {plan.entree}, deque([plan.entree])
    while file:
        n = file.popleft()
        for m in graphe[n]:
            if m not in vus:
                vus.add(m)
                file.append(m)
    contour = plan.emprise.exterior
    etroites, sans_jour, sans_fenetre, fenetres_interieures = [], [], [], []
    for p in plan.pieces:
        x0, z0, x1, z1 = p.polygone.bounds
        if min(x1 - x0, z1 - z0) < largeur_min(p.fonction) - 1e-6:
            etroites.append(p.nom)
        if voc.FONCTIONS_PIECES[p.fonction]["fenetre"]:
            if p.polygone.distance(contour) > 1e-6 or p.polygone.intersection(contour).length < 1.0:
                sans_jour.append(p.nom)
            if not any(o.type == "fenetre" for o in p.ouvertures):
                sans_fenetre.append(p.nom)
    for o in plan.ouvertures:
        if o.type == "fenetre":
            from shapely.geometry import Point
            if o.pieces[1] is not None or abs(Point(o.centre).distance(contour) - EP_EXT / 2.0) > 1e-6:
                fenetres_interieures.append(o.nom)
    entree = [o for o in plan.ouvertures if o.type == "porte_entree"]
    return {"inaccessibles": sorted(set(noms) - vus), "etroites": etroites, "sans_jour": sans_jour,
            "sans_fenetre": sans_fenetre, "fenetres_interieures": fenetres_interieures,
            "porte_entree": len(entree), "surface_obtenue": plan.mesures.get("surface_obtenue"),
            "surface_demandee": plan.mesures.get("surface_demandee")}


# ── Géométrie ──────────────────────────────────────────────────────────────────────────────────────
MATERIAU_PLINTHE = "bois_peint"
MATERIAU_HUISSERIE = "bois_peint"
MATERIAU_VANTAIL = "bois_peint"
MATERIAU_VANTAIL_ENTREE = "bois_chene"
MATERIAU_POIGNEE = "metal_noir"
MATERIAU_APPUI = "pierre"
MATERIAU_PLAFOND = "platre_peint:blanc"
HAUTEUR_MAQUETTE = 1.2


def _polygones(geom) -> list[Polygon]:
    if geom.is_empty:
        return []
    if isinstance(geom, Polygon):
        return [geom]
    return [p for p in getattr(geom, "geoms", []) if isinstance(p, Polygon) and p.area > 1e-7]


def _mur_par_tranches(region, ouvertures: list[Ouverture], y_bas: float, y_haut: float, materiau: str,
                      nom: str) -> list[Partie]:
    """Extrude `region` de y_bas à y_haut en tranches ; chaque ouverture active dans une tranche y est un vide."""
    if region.is_empty or y_haut <= y_bas:
        return []
    utiles = [o for o in ouvertures if o.rectangle().intersects(region)]
    niveaux = {y_bas, y_haut}
    for o in utiles:
        for y in (o.allege, o.allege + o.hauteur):
            if y_bas < y < y_haut:
                niveaux.add(y)
    niveaux = sorted(niveaux)
    maillages = []
    for ya, yb in zip(niveaux, niveaux[1:]):
        ym = (ya + yb) / 2.0
        trous = [o.rectangle() for o in utiles if o.allege < ym < o.allege + o.hauteur]
        geom = region.difference(unary_union(trous)) if trous else region
        for p in _polygones(geom):
            maillages.append(g.extrusion(p, yb - ya, y=ya))
    m = g.fusionner(maillages)
    return [Partie(m, materiau, nom)] if len(m.faces) else []


def _repere(o: Ouverture):
    """Matrice monde d'un repère local d'ouverture : x le long du mur, z selon la normale, y vertical."""
    (dx, dz), (nx, nz) = o.direction, o.normale
    import numpy as np
    m = np.eye(4)
    m[:3, 0] = [dx, 0.0, dz]
    m[:3, 1] = [0.0, 1.0, 0.0]
    m[:3, 2] = [nx, 0.0, nz]
    m[:3, 3] = [o.centre[0], 0.0, o.centre[1]]
    if np.linalg.det(m[:3, :3]) < 0:            # repère gauche : on retourne x, on garde la normale
        m[:3, 0] = -m[:3, 0]
    return m


def _huisserie(o: Ouverture) -> list[Partie]:
    """Chambranle autour d'une porte, dépassant de 1,5 cm de chaque face du mur."""
    w, h, t = o.largeur, o.hauteur, o.epaisseur + 0.03
    p = 0.07
    morceaux = [g.boite(p, h + p, t, x=-w / 2 - p / 2), g.boite(p, h + p, t, x=w / 2 + p / 2),
                g.boite(w + 2 * p, p, t, y=h)]
    m = g.transformer(g.fusionner(morceaux), _repere(o))
    return [Partie(m, MATERIAU_HUISSERIE, f"huisserie_{o.nom}")]


def _vantail(o: Ouverture, hauteur_plafond: float, ouverture: float = 0.0) -> Instance:
    """Vantail de porte : Objet dont l'origine est SUR LA CHARNIÈRE (rotation autour de +Y = ouverture)."""
    entree = o.type == "porte_entree"
    ep = 0.06 if entree else 0.04
    w = o.largeur - 0.01
    h = o.hauteur - 0.01
    parties = [Partie(g.boite(w, h, ep, x=w / 2, y=0.005), MATERIAU_VANTAIL_ENTREE if entree else MATERIAU_VANTAIL,
                      "vantail")]
    poignees = [g.boite(0.12, 0.025, 0.05, x=w - 0.1, y=1.0, z=s * (ep / 2 + 0.025)) for s in (-1, 1)]
    parties.append(Partie(g.fusionner(poignees), MATERIAU_POIGNEE, "poignee"))
    objet = Objet(o.nom, "porte", parties, largeur=w, profondeur=ep, hauteur=h,
                  meta={"type": o.type, "pieces": list(o.pieces), "ouvre_vers": o.ouvre_vers})
    # position de la charnière : extrémité `charniere` de la baie, vantail affleurant la face du côté où il débat
    s_cote = o.cote(o.ouvre_vers) if o.ouvre_vers else 1.0
    u_ch = o.charniere * (o.largeur / 2.0 - 0.005)
    v = s_cote * (o.epaisseur / 2.0 - ep / 2.0 - 0.005)
    hx, hz = o._point(u_ch, v)
    # le vantail (local +X) va de la charnière vers l'autre montant
    ux, uz = -o.charniere * o.direction[0], -o.charniere * o.direction[1]
    lacet = math.atan2(-uz, ux)
    pose = Pose(hx, hz, lacet, 0.0)
    # sens d'ouverture : l'angle positif amène le vantail vers -Z local ; on veut qu'il aille côté `ouvre_vers`
    zx, zz = math.sin(lacet), math.cos(lacet)
    nx, nz = o.normale[0] * s_cote, o.normale[1] * s_cote
    signe = -1.0 if (zx * nx + zz * nz) > 0 else 1.0
    pose.lacet += signe * math.pi / 2 * max(0.0, min(1.0, ouverture))
    return Instance(objet, pose, o.nom, meta={"pivot": "charniere", "angle_ouverture_rad": signe * math.pi / 2,
                                              "pieces": list(o.pieces), "ouvre_vers": o.ouvre_vers})


def _fenetre(o: Ouverture) -> list[Partie]:
    """Dormant + meneau (baie large) + vitrage + appui extérieur + tablette intérieure."""
    w, h, a, t = o.largeur, o.hauteur, o.allege, o.epaisseur
    p, prof = 0.06, 0.07
    cadre = [g.boite(p, h, prof, x=-w / 2 + p / 2, y=a), g.boite(p, h, prof, x=w / 2 - p / 2, y=a),
             g.boite(w, p, prof, y=a), g.boite(w, p, prof, y=a + h - p)]
    if w > 1.1:
        cadre.append(g.boite(p, h - 2 * p, prof, y=a + p))
    vitre = g.boite(w - 2 * p, h - 2 * p, 0.012, y=a + p)
    # normale vers l'extérieur (+z local) : appui dehors, tablette dedans
    appui = g.boite(w + 0.1, 0.05, t / 2 + 0.05, y=a - 0.05, z=t / 4 + 0.025)
    tablette = g.boite(w + 0.06, 0.025, t / 2 + 0.03, y=a - 0.025, z=-(t / 4 + 0.015))
    m = _repere(o)
    return [Partie(g.transformer(g.fusionner(cadre), m), MATERIAU_HUISSERIE, f"dormant_{o.nom}"),
            Partie(g.transformer(vitre, m), "verre", f"vitrage_{o.nom}"),
            Partie(g.transformer(appui, m), MATERIAU_APPUI, f"appui_{o.nom}"),
            Partie(g.transformer(tablette, m), MATERIAU_HUISSERIE, f"tablette_{o.nom}")]


def construire_geometrie(plan: Plan, *, plafond: bool = True, maquette: bool = False,
                         ouverture_portes: float = 0.0) -> Noeud:
    """Nœud « logement » : un enfant par pièce (nommé comme elle), « facades », et « plafonds » si demandé.
    `maquette=True` coupe tous les murs à 1,20 m (vues de maison de poupée), retire plafonds, huisseries et
    vantaux (plus hauts que la coupe). `ouverture_portes` (0 à 1) entrouvre les vantaux autour de leur
    charnière (vérification visuelle du pivot ; 0 = fermées)."""
    emprise = plan.emprise
    ex0, ez0, ex1, ez1 = emprise.bounds
    hauteur = plan.hauteur_plafond
    y_haut = min(hauteur, HAUTEUR_MAQUETTE) if maquette else hauteur
    y_bas = -EPAISSEUR_SOL
    demi_ext = EP_EXT / 2.0
    portes = [o for o in plan.ouvertures if o.type in ("porte", "porte_entree")]
    racine = Noeud("logement", extras={"plan": {"entree": plan.entree, "hauteur_plafond": hauteur,
                                                 "mesures": plan.mesures}})
    for p in plan.pieces:
        cx0, cz0, cx1, cz1 = p.cellule.bounds
        etendue = g.rectangle_xz(cx0 - (demi_ext if abs(cx0 - ex0) < EPS else 0.0),
                                 cz0 - (demi_ext if abs(cz0 - ez0) < EPS else 0.0),
                                 cx1 + (demi_ext if abs(cx1 - ex1) < EPS else 0.0),
                                 cz1 + (demi_ext if abs(cz1 - ez1) < EPS else 0.0))
        region_murs = etendue.difference(p.polygone)
        parties = [Partie(g.plaque(p.cellule, EPAISSEUR_SOL, y=0.0), p.sol, "sol")]
        parties += _mur_par_tranches(region_murs, plan.ouvertures, y_bas, y_haut, p.murs, "murs")
        # plinthes, interrompues aux portes
        bande = p.polygone.difference(p.polygone.buffer(-0.012, join_style=2))
        trous = [o.rectangle(marge_long=0.0, marge_ep=0.05) for o in portes if p.nom in o.pieces]
        if trous:
            bande = bande.difference(unary_union(trous))
        plinthes = g.fusionner([g.extrusion(q, min(0.08, y_haut)) for q in _polygones(bande)])
        if len(plinthes.faces):
            parties.append(Partie(plinthes, MATERIAU_PLINTHE, "plinthes"))
        instances = []
        for o in p.ouvertures:
            if o.type == "fenetre" and o.allege < y_haut:
                if o.allege + o.hauteur <= y_haut or not maquette:
                    parties += _fenetre(o)
            if o.type in ("porte", "porte_entree") and o.ouvre_vers == p.nom and not maquette:
                parties += _huisserie(o)
                instances.append(_vantail(o, hauteur, ouverture_portes))
        racine.enfants.append(Noeud(p.nom, parties=parties, instances=instances,
                                    extras={"fonction": p.fonction, "surface_m2": round(p.surface, 2)}))
    facade = emprise.buffer(EP_EXT, join_style=2).difference(emprise.buffer(demi_ext, join_style=2))
    haut_facade = y_haut if maquette or not plafond else hauteur + EPAISSEUR_SOL
    racine.enfants.append(Noeud("facades", parties=_mur_par_tranches(facade, plan.ouvertures, y_bas, haut_facade,
                                                                     plan.materiau_exterieur, "facade")))
    if plafond and not maquette:
        plafonds = []
        for p in plan.pieces:
            cx0, cz0, cx1, cz1 = p.cellule.bounds
            etendue = g.rectangle_xz(cx0 - (demi_ext if abs(cx0 - ex0) < EPS else 0.0),
                                     cz0 - (demi_ext if abs(cz0 - ez0) < EPS else 0.0),
                                     cx1 + (demi_ext if abs(cx1 - ex1) < EPS else 0.0),
                                     cz1 + (demi_ext if abs(cz1 - ez1) < EPS else 0.0))
            plafonds.append(Partie(g.plaque(etendue, EPAISSEUR_SOL, y=hauteur + EPAISSEUR_SOL), MATERIAU_PLAFOND,
                                   f"plafond_{p.nom}"))
        racine.enfants.append(Noeud("plafonds", parties=plafonds))
    return racine
