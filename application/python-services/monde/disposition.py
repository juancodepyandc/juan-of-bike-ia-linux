"""Disposition des meubles d'une pièce : poses candidates tirées des relations, contraintes DURES mesurées,
recherche en profondeur avec retour arrière.

Loi de disposition (aucune règle par sujet ; seules comptent les catégories et relations du vocabulaire) :
- ordre : les cibles avant ce qui s'y rapporte (niveaux topologiques), puis les grands objets d'abord
  (emprise au sol), puis les plus contraints ;
- poses candidates engendrées par les relations : `contre_mur` (dos contre chaque mur, échantillonné tous
  les 0,10 m), `dans_un_coin`, `au_centre`, `sous_fenetre` (contre le mur d'une fenêtre, sous l'allège),
  `face_a` / `devant` / `autour_de` / `a_cote_de` / `au_pied_de` (relatives à la pose de la cible), `sur`
  (sur la `Surface` de la cible, pose.y = hauteur du dessus), `sous` (tapis sous la cible), `au_dessus_de`
  (accroché au mur au-dessus de la cible, ou suspendu au plafond au-dessus d'elle) ;
- contraintes DURES (shapely) : dans la pièce ; pas de chevauchement (sauf tapis `sol_partage`, objets posés
  `sur` leur cible, et volumes disjoints en hauteur : un tableau au-dessus d'un canapé) ; zone de dégagement
  libre et dans la pièce ; carré de débattement des portes libre ; rien de plus haut que l'allège devant une
  fenêtre ; rien d'accroché sur la baie d'une porte ou d'une fenêtre ; ACCESSIBILITÉ : sol libre rastérisé à
  0,10 m, parcours en largeur depuis chaque porte, la zone de dégagement de chaque objet (ou son avant, ou
  ses abords) doit être atteinte par un passage d'au moins ~0,5 m ;
- préférences (notes douces) : distances des relations, alignement aux murs, orientation vers la cible,
  symétrie des paires (tables de chevet), passages entre portes et centre de la pièce gardés libres ;
- un objet impossible à placer est rendu dans `echecs` avec la raison mesurée — jamais retiré en silence.

Convention de hauteur : un objet est construit de y = 0 à sa hauteur (voir `monde.ir`) ; `pose.y` est la
hauteur de son dessous (dessus de la cible pour `sur`, hauteur de pose pour un objet mural, plafond moins sa
hauteur pour un objet suspendu).
"""
from __future__ import annotations

import argparse
import json
import math
import random
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Callable

import numpy as np
from scipy import ndimage
from shapely import contains_xy
from shapely.geometry import LineString, Point, Polygon
from shapely.geometry.polygon import orient
from shapely.ops import unary_union

from monde import geometrie as g
from monde import vocabulaire as voc
from monde.ir import Instance, Objet, Partie, Pose, Scene, Surface
from monde.plan import Ouverture, PiecePlan, Plan

Fabrique = Callable[[str, int, dict], Objet]

PAS_MUR = 0.10
JEU_MUR = 0.005
RAYON_PASSAGE = 0.25            # demi-largeur d'un passage (0,5 m libres)
RECUL_PASSAGE = 0.9             # on marche entre deux portes à une largeur de corps du mur, pas en le frôlant
PAS_GRILLE = 0.10
PROFONDEUR_FENETRE = 0.5        # bande devant une fenêtre où rien ne dépasse l'allège
TOP_K = 6
TOP_K_PREMIERS = 24            # les premiers objets (les plus structurants) essaient plus d'alternatives
NIVEAUX_LARGES = 3
MALUS_COMPACT = 0.6            # note retirée à une pose obtenue avec le repli compact
BUDGET = 600                    # nœuds de recherche au plus (mesuré : au-delà, rien de gagné sur les essais)
HAUTEUR_LIBRE_MURAL = 1.0       # sous cette hauteur, un objet accroché gêne comme un meuble au sol
RELATIONS_DEFINISSANTES = ("sur", "sous", "au_pied_de")   # sans leur cible, ces objets n'ont pas de place
RELATIONS_ENVAHISSANTES = {"devant", "autour_de", "au_pied_de", "sous"}   # le dépendant vit dans la zone d'usage
RELATIONS_POSITION = ("sur", "sous", "au_dessus_de", "au_pied_de", "devant", "autour_de", "a_cote_de", "face_a",
                      "sous_fenetre", "dans_un_coin", "contre_mur", "au_centre")


# ── Structures publiques ───────────────────────────────────────────────────────────────────────────
@dataclass
class Demande:
    categorie: str
    nombre: int = 1
    relations: list[tuple[str, str | None]] = field(default_factory=list)
    materiaux: dict[str, str] | None = None
    style: str | None = None


@dataclass
class Disposition:
    instances: list[Instance]
    echecs: list[dict[str, Any]]
    mesures: dict[str, Any]


def demandes_typiques(fonction: str) -> list[Demande]:
    """Ce qu'une pièce COMPLÈTE de cette fonction contient d'ordinaire (vocabulaire)."""
    spec = voc.fonction_piece(fonction)
    return [Demande(c, int(n), [tuple(r) for r in rel]) for c, n, rel in spec["meubles_typiques"]]


def _moyenne(intervalle: tuple[float, float]) -> float:
    return (float(intervalle[0]) + float(intervalle[1])) / 2.0


# ── Objet provisoire (tests et démonstrations, sans dépendre des générateurs de meubles) ──────────────
def objet_provisoire(categorie: str, graine: int = 0, options: dict | None = None) -> Objet:
    """Un pavé (ou 2-3) aux dimensions MOYENNES du vocabulaire, dans les matériaux par défaut de la
    catégorie ; l'avant est marqué (dossier à l'arrière des assises et couchages, façade sinon)."""
    spec = voc.categorie(categorie)
    options = dict(options or {})
    w = float(options.get("largeur") or _moyenne(spec["largeur"]))
    p = float(options.get("profondeur") or _moyenne(spec["profondeur"]))
    h = float(options.get("hauteur") or _moyenne(spec["hauteur"]))
    mats = dict(spec["materiaux"])
    mats.update(options.get("materiaux") or {})
    valeurs = list(mats.values()) or ["bois_chene"]
    principal = valeurs[0]
    second = valeurs[1] if len(valeurs) > 1 else principal
    groupe = spec["groupe"]
    parties: list[Partie] = []
    if groupe in ("assise", "couchage") and h > 0.3:
        dos = max(0.06, 0.15 * p)
        if groupe == "couchage":
            parties.append(Partie(g.boite(w, 0.45 * h, p - dos, z=dos / 2), principal, "base"))
            parties.append(Partie(g.boite(w - 0.04, 0.2 * h, p - dos - 0.04, y=0.45 * h, z=dos / 2), second, "literie"))
        else:
            parties.append(Partie(g.boite(w, 0.5 * h, p - dos, z=dos / 2), principal, "assise"))
        parties.append(Partie(g.boite(w, h, dos, z=-p / 2 + dos / 2), principal, "dossier"))
    elif spec["sol_partage"] or h < 0.05:
        parties.append(Partie(g.boite(w, h, p), principal, "corps"))
    else:
        k = 0.6 if groupe in ("vegetal", "luminaire") else 0.12
        parties.append(Partie(g.boite(w, h * (1 - k), p), principal, "corps"))
        parties.append(Partie(g.boite(w, h * k, p, y=h * (1 - k)), second, "dessus"))
        if spec["degagement"] > 0 and second != principal:
            parties.append(Partie(g.boite(0.8 * w, 0.6 * h * (1 - k), 0.012, y=0.2 * h * (1 - k), z=p / 2 + 0.006),
                                  second, "facade"))
    surfaces = []
    if spec["support"]:
        m = min(0.02, w / 10, p / 10)
        surfaces.append(Surface(h, [(-w / 2 + m, -p / 2 + m), (w / 2 - m, -p / 2 + m), (w / 2 - m, p / 2 - m),
                                    (-w / 2 + m, p / 2 - m)]))
    return Objet(categorie, categorie, parties, largeur=w, profondeur=p, hauteur=h,
                 degagement=float(spec["degagement"]), degagement_cotes=float(spec["degagement_cotes"]),
                 surfaces=surfaces, mural=bool(spec["mural"]), plafond=bool(spec["plafond"]),
                 sol_partage=bool(spec["sol_partage"]),
                 meta={"provisoire": True, "groupe": groupe, "graine": graine,
                       "hauteur_pose": _moyenne(spec["hauteur_pose"]) if spec["mural"] else 0.0})


# ── Contexte de la pièce ───────────────────────────────────────────────────────────────────────────
@dataclass
class _Mur:
    p0: np.ndarray
    p1: np.ndarray
    longueur: float
    direction: np.ndarray
    normale: np.ndarray            # vers l'intérieur


@dataclass
class _Contexte:
    piece: PiecePlan
    poly: Polygon
    tolere: Polygon
    murs: list[_Mur]
    portes: list[Ouverture]
    fenetres: list[Ouverture]
    battements: list[Polygon]
    zones_fenetres: list[tuple[Ouverture, Polygon]]
    hauteur: float
    circulation: Polygon | None
    centre: tuple[float, float]
    regardees: set[str] = field(default_factory=set)   # catégories qu'un autre objet doit regarder (face_a)
    entourees: dict[str, float] = field(default_factory=dict)   # catégorie → profondeur de ce qui l'entoure
    cache_genes: tuple = (None, None)
    convexe: bool = False
    rect: tuple | None = None                         # pièce rectangulaire alignée sur les axes : ses bornes
    tolere_zone: Any = None                           # pièce élargie de 1 cm (dégagements)
    boites_battements: list = field(default_factory=list)

    def __post_init__(self) -> None:
        self.tolere_zone = self.poly.buffer(0.01, join_style=2)
        self.boites_battements = [z.bounds for z in self.battements]


def _contexte(piece: PiecePlan, hauteur: float) -> _Contexte:
    poly = orient(piece.polygone, 1.0)
    coords = list(poly.exterior.coords)[:-1]
    murs = []
    for i in range(len(coords)):
        a, b = np.array(coords[i], dtype=float), np.array(coords[(i + 1) % len(coords)], dtype=float)
        longueur = float(np.linalg.norm(b - a))
        if longueur < 1e-6:
            continue
        d = (b - a) / longueur
        murs.append(_Mur(a, b, longueur, d, np.array([-d[1], d[0]])))
    portes = [o for o in piece.ouvertures if o.type in ("porte", "porte_entree")]
    fenetres = [o for o in piece.ouvertures if o.type == "fenetre"]
    battements = [o.zone_battement(piece.nom) for o in portes]
    zones_f = [(o, o.zone_devant(piece.nom, PROFONDEUR_FENETRE, 0.05)) for o in fenetres]
    c = poly.centroid
    chemins = [LineString([o.point_face(piece.nom, 0.3), (c.x, c.y)]) for o in portes]
    if len(portes) >= 2:
        for i, a in enumerate(portes):
            for b in portes[i + 1:]:
                chemins.append(LineString([a.point_face(piece.nom, RECUL_PASSAGE), b.point_face(piece.nom, RECUL_PASSAGE)]))
    circulation = unary_union([ch.buffer(0.35) for ch in chemins]).intersection(poly) if chemins else None
    return _Contexte(piece, poly, poly.buffer(0.005, join_style=2), murs, portes, fenetres, battements, zones_f,
                     hauteur, circulation, (c.x, c.y), convexe=poly.convex_hull.area - poly.area < 1e-6,
                     rect=poly.bounds if abs(poly.area - poly.envelope.area) < 1e-6 else None)


# ── Objets à placer et poses ───────────────────────────────────────────────────────────────────────
@dataclass
class _Item:
    nom: str
    categorie: str
    objet: Objet
    relations: list[tuple[str, str | None]]
    demande: int
    rang: int
    niveau: int = 0
    compact: Objet | None = None      # même catégorie aux dimensions minimales du vocabulaire (repli)

    @property
    def cibles(self) -> set[str]:
        return {c for _, c in self.relations if c}

    @property
    def aire(self) -> float:
        return self.objet.largeur * self.objet.profondeur

    @property
    def encombrement(self) -> float:
        """Emprise + dégagements : la place qu'il faut vraiment à l'objet (ordre « gros d'abord »)."""
        o = self.objet
        return o.largeur * (o.profondeur + o.degagement) + 2.0 * o.degagement_cotes * o.profondeur


_A_CALCULER = object()


@dataclass
class _Place:
    item: _Item
    pose: Pose
    emprise_calculee: Any            # emprise shapely, construite à la première lecture (`_A_CALCULER`)
    zone_calculee: Any               # zone de dégagement, idem
    bas: float
    haut: float
    support: str | None = None       # nom de l'objet qui le porte (relation « sur »)
    cible: str | None = None         # nom de l'objet visé par sa relation principale
    note: float = 0.0
    relation: str = ""
    coins: tuple = ()                # 4 coins (x, z) de l'emprise, calculés sans shapely
    boite: tuple = ()                # (xmin, zmin, xmax, zmax)

    def __post_init__(self) -> None:
        if not self.coins:
            o = self.item.objet
            hx, hz = o.largeur / 2.0, o.profondeur / 2.0
            self.coins = tuple(self.pose.vers_monde(x, z) for x, z in ((-hx, -hz), (hx, -hz), (hx, hz), (-hx, hz)))
        xs, zs = [c[0] for c in self.coins], [c[1] for c in self.coins]
        self.boite = (min(xs), min(zs), max(xs), max(zs))

    @property
    def emprise(self) -> Polygon:
        if self.emprise_calculee is _A_CALCULER:
            self.emprise_calculee = Polygon(self.coins)
        return self.emprise_calculee

    @property
    def zone(self) -> Polygon | None:
        """La plupart des candidats sont rejetés avant qu'on lise leur dégagement : il n'est construit
        qu'au besoin."""
        if self.zone_calculee is _A_CALCULER:
            self.zone_calculee = self.item.objet.zone_degagement(self.pose)
        return self.zone_calculee

    @property
    def au_sol(self) -> bool:
        o = self.item.objet
        return not (o.mural or o.plafond or self.support) and not o.sol_partage

    def relations_vers(self, autre: "_Place") -> set[str]:
        return {r for r, c in self.item.relations if c == autre.item.categorie}

    def envahit_permis(self, autre: "_Place") -> bool:
        """`autre` peut-il occuper la zone d'usage AVANT de self ? Oui seulement si l'une des deux relations le
        veut : une table basse DEVANT le canapé, une chaise AUTOUR de la table (sa face regarde la table), un
        tapis AU PIED du lit. Une table de chevet À CÔTÉ du lit n'occupe que son dégagement latéral."""
        return bool((autre.relations_vers(self) | self.relations_vers(autre)) & RELATIONS_ENVAHISSANTES)

    def cote_permis(self, autre: "_Place") -> bool:
        """`autre` peut-il occuper le dégagement LATÉRAL de self (relation à côté de, dans un sens ou l'autre) ?"""
        return self.envahit_permis(autre) or "a_cote_de" in (autre.relations_vers(self) | self.relations_vers(autre))

    def zone_avant(self) -> Polygon | None:
        o = self.item.objet
        if o.degagement <= 0.0:
            return None
        hx, hz = o.largeur / 2.0, o.profondeur / 2.0
        return Polygon([self.pose.vers_monde(x, z) for x, z in
                        [(-hx, hz), (hx, hz), (hx, hz + o.degagement), (-hx, hz + o.degagement)]])


def _lacet_vers(fx: float, fz: float) -> float:
    return math.atan2(fx, fz)


def _nouvelle_place(item: _Item, pose: Pose, relation: str, cible: str | None = None, support: str | None = None,
                    note: float = 0.0) -> _Place:
    o = item.objet
    return _Place(item, pose, _A_CALCULER, _A_CALCULER, pose.y, pose.y + o.hauteur, support, cible, note, relation)


def _boites_disjointes(a: tuple, b: tuple, marge: float = 1e-3) -> bool:
    return a[2] <= b[0] + marge or b[2] <= a[0] + marge or a[3] <= b[1] + marge or b[3] <= a[1] + marge


def _hauteur_pose(item: _Item) -> float:
    o = item.objet
    hp = float(o.meta.get("hauteur_pose") or 0.0)
    if hp <= 0.0:
        hp = _moyenne(voc.CATEGORIES[item.categorie]["hauteur_pose"]) if item.categorie in voc.CATEGORIES else 1.2
    return hp


def _poses_murales(ctx: _Contexte, item: _Item, y: float, pas: float = PAS_MUR) -> list[tuple[Pose, dict]]:
    o = item.objet
    sortie = []
    for i, mur in enumerate(ctx.murs):
        if mur.longueur < o.largeur:
            continue
        lacet = _lacet_vers(mur.normale[0], mur.normale[1])
        n = int(math.floor((mur.longueur - o.largeur) / pas)) + 1
        for k in range(n):
            s = o.largeur / 2 + k * pas
            c = mur.p0 + mur.direction * s + mur.normale * (o.profondeur / 2 + JEU_MUR)
            sortie.append((Pose(float(c[0]), float(c[1]), lacet, y), {"mur": i, "s": s}))
        if (mur.longueur - o.largeur) % pas > 1e-6:          # le dernier cran, contre l'angle
            s = mur.longueur - o.largeur / 2
            c = mur.p0 + mur.direction * s + mur.normale * (o.profondeur / 2 + JEU_MUR)
            sortie.append((Pose(float(c[0]), float(c[1]), lacet, y), {"mur": i, "s": s}))
    return sortie


def _poses_coins(ctx: _Contexte, item: _Item) -> list[tuple[Pose, dict]]:
    o = item.objet
    sortie = []
    for i, mur in enumerate(ctx.murs):
        if mur.longueur < o.largeur:
            continue
        lacet = _lacet_vers(mur.normale[0], mur.normale[1])
        for s in (o.largeur / 2 + JEU_MUR, mur.longueur - o.largeur / 2 - JEU_MUR):
            c = mur.p0 + mur.direction * s + mur.normale * (o.profondeur / 2 + JEU_MUR)
            sortie.append((Pose(float(c[0]), float(c[1]), lacet, 0.0), {"mur": i, "s": s, "coin": True}))
    return sortie


def _axes_piece(ctx: _Contexte) -> list[float]:
    return sorted({round(_lacet_vers(m.normale[0], m.normale[1]), 6) for m in ctx.murs})


def _poses_centre(ctx: _Contexte, item: _Item, y: float = 0.0, large: bool = False) -> list[tuple[Pose, dict]]:
    cx, cz = ctx.centre
    pas = [0.0, 0.15, -0.15, 0.3, -0.3, 0.5, -0.5] + ([0.8, -0.8, 1.2, -1.2] if large else [])
    sortie = []
    for lacet in _axes_piece(ctx):
        for dx in pas:
            for dz in pas:
                sortie.append((Pose(cx + dx, cz + dz, lacet, y), {"centre": math.hypot(dx, dz)}))
    return sortie


def _mur_de(ctx: _Contexte, place: _Place) -> tuple[int, float] | None:
    """Mur contre lequel s'appuie le dos d'un objet posé : (indice, abscisse de son centre le long du mur)."""
    o = place.item.objet
    dos = np.array(place.pose.vers_monde(0.0, -o.profondeur / 2))
    fx, fz = place.pose.face()
    meilleur = None
    for i, mur in enumerate(ctx.murs):
        if float(np.dot(mur.normale, [fx, fz])) < 0.9:
            continue
        rel = dos - mur.p0
        dist = abs(float(np.dot(rel, mur.normale)))
        s = float(np.dot(rel, mur.direction))
        if dist < 0.06 and -0.01 <= s <= mur.longueur + 0.01 and (meilleur is None or dist < meilleur[0]):
            meilleur = (dist, i, s)
    return None if meilleur is None else (meilleur[1], meilleur[2])


def _candidats(ctx: _Contexte, item: _Item, places: list[_Place], rng: random.Random) -> list[_Place]:
    o = item.objet
    rel = dict()
    for r, c in item.relations:
        rel.setdefault(r, c)
    par_cat: dict[str, list[_Place]] = {}
    for p in places:
        par_cat.setdefault(p.item.categorie, []).append(p)
    spec = voc.CATEGORIES.get(item.categorie, {})
    sortie: list[_Place] = []
    freres = [p for p in places if p.item.demande == item.demande]

    def cibles(cat: str | None) -> list[_Place]:
        return par_cat.get(cat, []) if cat else []

    # ── suspendus au plafond
    if o.plafond:
        y = ctx.hauteur - o.hauteur
        if "au_dessus_de" in rel and cibles(rel["au_dessus_de"]):
            for t in cibles(rel["au_dessus_de"]):
                sortie.append(_nouvelle_place(item, Pose(t.pose.x, t.pose.z, t.pose.lacet, y), "au_dessus_de",
                                              t.item.nom, note=1.0))
        if not sortie:
            for pose, info in _poses_centre(ctx, item, y):
                sortie.append(_nouvelle_place(item, pose, "au_centre", note=1.0 - info["centre"]))
        return sortie

    # ── posés sur une cible
    if "sur" in rel:
        for t in cibles(rel["sur"]):
            surfaces = t.item.objet.surfaces or ([Surface(t.item.objet.hauteur, [
                (-t.item.objet.largeur / 2, -t.item.objet.profondeur / 2), (t.item.objet.largeur / 2, -t.item.objet.profondeur / 2),
                (t.item.objet.largeur / 2, t.item.objet.profondeur / 2), (-t.item.objet.largeur / 2, t.item.objet.profondeur / 2)])]
                if voc.CATEGORIES.get(t.item.categorie, {}).get("support") else [])
            charge = sum(1 for p in places if p.support == t.item.nom)
            for surf in surfaces:
                sp = Polygon(surf.polygone)
                c = sp.centroid
                minx, _, maxx, _ = sp.bounds
                decal = max(0.0, (maxx - minx) / 2 - o.largeur / 2 - 0.03)
                for dx in sorted({0.0, decal, -decal}):
                    x, z = t.pose.vers_monde(c.x + dx, c.y)
                    pose = Pose(x, z, t.pose.lacet, t.pose.y + surf.hauteur)
                    note = 1.0 - (0.6 * charge) - 0.1 * abs(dx)
                    sortie.append(_nouvelle_place(item, pose, "sur", t.item.nom, support=t.item.nom, note=note))
        return sortie

    # ── accrochés au mur
    if o.mural:
        y0 = _hauteur_pose(item)
        hauteurs = [y0, y0 + o.hauteur + 0.08, y0 + 2 * (o.hauteur + 0.08)]
        if "au_dessus_de" in rel and cibles(rel["au_dessus_de"]):
            for t in cibles(rel["au_dessus_de"]):
                appui = _mur_de(ctx, t)
                to = t.item.objet
                base = max(y0, t.haut + 0.1)
                if appui is None:
                    continue
                i, s_t = appui
                mur = ctx.murs[i]
                lacet = _lacet_vers(mur.normale[0], mur.normale[1])
                # au-dessus = recouvre au moins 40 % de la largeur de l'objet accroché (glisse à côté d'une baie)
                demi = max(0.0, to.largeur / 2 + o.largeur / 2 - 0.4 * o.largeur)
                decalages = sorted({0.0, *np.round(np.arange(-demi, demi + 1e-9, 0.1), 3)}, key=abs)
                for y in [base, base + o.hauteur + 0.08, base + 2 * (o.hauteur + 0.08)]:
                    for dx in decalages:
                        s = s_t + dx
                        if s - o.largeur / 2 < -1e-6 or s + o.largeur / 2 > mur.longueur + 1e-6:
                            continue
                        c = mur.p0 + mur.direction * s + mur.normale * (o.profondeur / 2 + JEU_MUR)
                        note = 1.5 - 0.8 * abs(dx) - 0.3 * (y - base)
                        sortie.append(_nouvelle_place(item, Pose(float(c[0]), float(c[1]), lacet, y), "au_dessus_de",
                                                      t.item.nom, note=note))
        if not sortie:
            for y in hauteurs:
                for pose, info in _poses_murales(ctx, item, y):
                    centrage = 1.0 - abs(info["s"] - ctx.murs[info["mur"]].longueur / 2) / max(ctx.murs[info["mur"]].longueur, 1e-6)
                    sortie.append(_nouvelle_place(item, pose, "contre_mur", note=0.5 + 0.3 * centrage - 0.2 * (y - y0)))
        return sortie

    # ── au sol
    assise_a_table = spec.get("groupe") == "assise"

    if "sous" in rel:
        for t in cibles(rel["sous"]):
            fx, fz = t.pose.face()
            for d in (0.0, 0.15, -0.15, 0.3, -0.3):
                for lacet in (t.pose.lacet, t.pose.lacet + math.pi / 2):
                    pose = Pose(t.pose.x + fx * d, t.pose.z + fz * d, lacet, 0.0)
                    note = 1.2 - abs(d) - (0.2 if lacet != t.pose.lacet else 0.0)
                    sortie.append(_nouvelle_place(item, pose, "sous", t.item.nom, note=note))

    if "au_pied_de" in rel:
        for t in cibles(rel["au_pied_de"]):
            to = t.item.objet
            # un tapis au pied d'un lit peut glisser loin sous le lit (jusqu'aux deux tiers) dans une pièce courte
            for gap in (-0.5, -0.3, -0.1, 0.0, 0.15, 0.3, -0.7, -0.9, -1.1):
                for lacet in (t.pose.lacet, t.pose.lacet + math.pi / 2):
                    x, z = t.pose.vers_monde(0.0, to.profondeur / 2 + gap + o.profondeur / 2)
                    note = 1.2 - 0.6 * abs(gap + 0.2) - (0.15 if lacet != t.pose.lacet else 0.0)
                    sortie.append(_nouvelle_place(item, Pose(x, z, lacet, 0.0), "au_pied_de", t.item.nom, note=note))

    if "devant" in rel:
        for t in cibles(rel["devant"]):
            to = t.item.objet
            rentre = assise_a_table and voc.CATEGORIES.get(t.item.categorie, {}).get("groupe") == "table"
            # une chaise « rentrée » ne passe pas sous le plateau : les emprises sont des pavés, elle touche le bord
            ecarts = (0.02, 0.08, 0.15) if rentre else (0.3, 0.4, 0.5, 0.6, 0.75)
            ideal = 0.02 if rentre else 0.42
            for gap in ecarts:
                for dx in (0.0, 0.15, -0.15):
                    x, z = t.pose.vers_monde(dx, to.profondeur / 2 + gap + o.profondeur / 2)
                    note = 1.5 - 1.5 * abs(gap - ideal) - 0.5 * abs(dx)
                    sortie.append(_nouvelle_place(item, Pose(x, z, t.pose.lacet + math.pi, 0.0), "devant", t.item.nom,
                                                  note=note))

    if "autour_de" in rel:
        for t in cibles(rel["autour_de"]):
            to = t.item.objet
            rentre = assise_a_table and voc.CATEGORIES.get(t.item.categorie, {}).get("groupe") == "table"
            ecarts = (0.02, 0.08) if rentre else (0.35, 0.5, 0.65)
            freres_t = [p for p in freres if p.cible == t.item.nom]
            cotes = {"avant": (0.0, 1.0, to.largeur, to.profondeur), "arriere": (0.0, -1.0, to.largeur, to.profondeur),
                     "gauche": (-1.0, 0.0, to.profondeur, to.largeur), "droite": (1.0, 0.0, to.profondeur, to.largeur)}
            occupes: dict[str, int] = {k: 0 for k in cotes}
            for p in freres_t:
                lx, lz = _local(t.pose, p.pose.x, p.pose.z)
                occupes[_cote_local(lx, lz, to)] += 1
            oppose = {"avant": "arriere", "arriere": "avant", "gauche": "droite", "droite": "gauche"}
            for nom_c, (ux, uz, longueur_c, epaisseur_c) in cotes.items():
                n_places = max(1, int(math.floor((longueur_c + 0.1) / (o.largeur + 0.12))))
                glisse = (0.0,) if n_places > 1 else (0.0, 0.2, -0.2)
                for k in range(n_places):
                    for gap in ecarts:
                        for dl in glisse:
                            t_long = (k + 0.5) / n_places * longueur_c - longueur_c / 2 + dl
                            dist = epaisseur_c / 2 + gap + o.profondeur / 2
                            lx, lz = (t_long, uz * dist) if uz else (ux * dist, t_long)
                            x, z = t.pose.vers_monde(lx, lz)
                            if uz:
                                lacet = t.pose.lacet + (math.pi if uz > 0 else 0.0)
                            else:
                                lacet = t.pose.lacet + (-math.pi / 2 if ux > 0 else math.pi / 2)
                            equilibre = occupes[oppose[nom_c]] - occupes[nom_c]
                            note = (1.0 + 0.4 * equilibre + (0.3 if longueur_c >= epaisseur_c else 0.0)
                                    - 0.1 * abs(t_long) - 0.5 * abs(gap - ecarts[0]))
                            sortie.append(_nouvelle_place(item, Pose(x, z, lacet, 0.0), "autour_de", t.item.nom,
                                                          note=note))

    if "a_cote_de" in rel:
        for t in cibles(rel["a_cote_de"]):
            to = t.item.objet
            freres_t = [p for p in freres if p.cible == t.item.nom]
            cotes_pris = {1.0 if _local(t.pose, p.pose.x, p.pose.z)[0] > 0 else -1.0 for p in freres_t}
            # alignés sur le dos de la cible (même mur) d'abord, puis sur sa face
            alignements = [(-to.profondeur / 2 + o.profondeur / 2, 0.0)]
            # l'alignement sur la face n'est permis qu'à ce qui ne doit pas être dos au mur (un lampadaire,
            # pas une table de chevet : elle reste à la tête du lit)
            if abs(to.profondeur - o.profondeur) > 0.05 and spec.get("contre_mur") != "oui":
                alignements.append((to.profondeur / 2 - o.profondeur / 2, 0.3))
            for signe in (-1.0, 1.0):
                for gap in (0.0, 0.03, 0.1, 0.2, 0.35):
                    for lz, malus in alignements:
                        lx = signe * (to.largeur / 2 + gap + o.largeur / 2)
                        x, z = t.pose.vers_monde(lx, lz)
                        note = 1.2 - gap - malus + (0.8 if cotes_pris and signe not in cotes_pris else 0.0) \
                            - (0.8 if signe in cotes_pris else 0.0)
                        sortie.append(_nouvelle_place(item, Pose(x, z, t.pose.lacet, 0.0), "a_cote_de", t.item.nom,
                                                      note=note))

    if "face_a" in rel:
        for t in cibles(rel["face_a"]):
            to = t.item.objet
            for dist in np.arange(1.0, 4.01, 0.25):
                for dx in (0.0, 0.2, -0.2):
                    x, z = t.pose.vers_monde(dx, to.profondeur / 2 + float(dist) + o.profondeur / 2)
                    sortie.append(_nouvelle_place(item, Pose(x, z, t.pose.lacet + math.pi, 0.0), "face_a", t.item.nom,
                                                  note=0.8))

    if "sous_fenetre" in rel:
        for f in ctx.fenetres:
            if o.hauteur > f.allege + 1e-6:
                continue
            for pose, info in _poses_murales(ctx, item, 0.0):
                mur = ctx.murs[info["mur"]]
                cf = np.array(f.point_face(ctx.piece.nom))
                rel_f = cf - mur.p0
                if abs(float(np.dot(rel_f, mur.normale))) > 0.05:
                    continue
                s_f = float(np.dot(rel_f, mur.direction))
                ecart = abs(info["s"] - s_f)
                if ecart > max(o.largeur, f.largeur) / 2:
                    continue
                sortie.append(_nouvelle_place(item, pose, "sous_fenetre", note=1.6 - ecart))

    contre = "contre_mur" in rel or (not any(r in rel for r in RELATIONS_POSITION)
                                     and spec.get("contre_mur", "indifferent") != "non")
    if "dans_un_coin" in rel:
        for pose, info in _poses_coins(ctx, item):
            sortie.append(_nouvelle_place(item, pose, "dans_un_coin", note=1.4))
    if contre:
        cote_libre = o.degagement_cotes > 0
        for pose, info in _poses_murales(ctx, item, 0.0):
            mur = ctx.murs[info["mur"]]
            milieu = 1.0 - abs(info["s"] - mur.longueur / 2) / max(mur.longueur / 2, 1e-6)
            coin = 1.0 - min(info["s"] - o.largeur / 2, mur.longueur - info["s"] - o.largeur / 2) / max(mur.longueur, 1e-6)
            note = 1.0 + (0.4 * milieu if cote_libre else 0.25 * coin)
            sortie.append(_nouvelle_place(item, pose, "contre_mur", note=note))
    if "au_centre" in rel or (not sortie and spec.get("contre_mur") == "non"):
        for pose, info in _poses_centre(ctx, item, 0.0, large=True):
            sortie.append(_nouvelle_place(item, pose, "au_centre", note=1.2 - info["centre"]))
    if not sortie:                       # aucune relation exploitable : murs, coins puis centre
        for pose, info in _poses_murales(ctx, item, 0.0) + _poses_coins(ctx, item):
            sortie.append(_nouvelle_place(item, pose, "contre_mur", note=0.6))
        for pose, info in _poses_centre(ctx, item, 0.0, large=True):
            sortie.append(_nouvelle_place(item, pose, "au_centre", note=0.4 - 0.2 * info["centre"]))
    return sortie


def _local(pose: Pose, x: float, z: float) -> tuple[float, float]:
    c, s = math.cos(pose.lacet), math.sin(pose.lacet)
    dx, dz = x - pose.x, z - pose.z
    return c * dx - s * dz, s * dx + c * dz


def _cote_local(lx: float, lz: float, o: Objet) -> str:
    if abs(lz) / max(o.profondeur, 1e-6) >= abs(lx) / max(o.largeur, 1e-6):
        return "avant" if lz > 0 else "arriere"
    return "droite" if lx > 0 else "gauche"


# ── Notes douces des relations secondaires ─────────────────────────────────────────────────────────
DISTANCE_REGARD = 2.8
HAUTEUR_VUE_LIBRE = 0.55        # sous cette hauteur (table basse), un objet ne coupe pas une ligne de vue
LARGEUR_VUE = 0.7


def _profondeur_devant(ctx: _Contexte, place: _Place) -> float:
    """Distance du milieu de la face d'un objet au mur qu'elle regarde (lancer de rayon dans la pièce)."""
    o = place.item.objet
    x0, z0 = place.pose.vers_monde(0.0, o.profondeur / 2)
    fx, fz = place.pose.face()
    rayon = LineString([(x0, z0), (x0 + fx * 50.0, z0 + fz * 50.0)])
    coupe = rayon.intersection(ctx.poly)
    if coupe.is_empty:
        return 0.0
    morceaux = getattr(coupe, "geoms", [coupe])
    return max((Point(x0, z0).distance(Point(m.coords[-1])) for m in morceaux
                if Point(x0, z0).distance(m) < 1e-3), default=0.0)


def _note_relations(ctx: _Contexte, cand: _Place, places: list[_Place]) -> float:
    item = cand.item
    o = item.objet
    note = cand.note
    if item.categorie in ctx.entourees and cand.au_sol:
        # ce qu'on entoure (une table et ses chaises) garde un anneau libre de la profondeur des chaises :
        # dans la pièce, hors des débattements de portes et des dégagements déjà réservés
        anneau = cand.emprise.buffer(ctx.entourees[item.categorie], join_style=2).difference(cand.emprise)
        libre = anneau.intersection(ctx.poly)
        cle = tuple(id(p) for p in places)
        if ctx.cache_genes[0] != cle:              # une union par nœud de recherche, pas par candidat
            genes = [z for z in ctx.battements] + [p.zone for p in places if p.zone is not None and _gene_au_sol(p)] \
                + [p.emprise for p in places if _gene_au_sol(p)]
            ctx.cache_genes = (cle, unary_union(genes) if genes else None)
        if ctx.cache_genes[1] is not None:
            libre = libre.difference(ctx.cache_genes[1])
        note += 1.5 * libre.area / max(anneau.area, 1e-6)
    if cand.au_sol and cand.haut > HAUTEUR_VUE_LIBRE:
        # la ligne de vue entre un objet et ce qu'il regarde (télévision ↔ canapé) reste dégagée de tout ce
        # qui dépasse une table basse
        for p in places:
            for r, c in p.item.relations:
                if r != "face_a" or c == item.categorie or p.item.categorie == item.categorie:
                    continue
                for t in places:
                    if t.item.categorie != c:
                        continue
                    vue = LineString([(p.pose.x, p.pose.z), (t.pose.x, t.pose.z)]).buffer(LARGEUR_VUE / 2)
                    if not _boites_disjointes(vue.bounds, cand.boite, 0.0) \
                            and vue.intersection(cand.emprise).area > 0.02:
                        note -= 1.5
    if item.categorie in ctx.regardees and cand.au_sol:
        # ce qu'on doit regarder (un canapé face à la télévision) veut 2 à 4 m de sol libre devant lui,
        # jusqu'au mur d'en face où l'autre objet s'adossera
        profondeur = _profondeur_devant(ctx, cand)
        bonus = 0.9 * (1.0 - min(abs(profondeur - DISTANCE_REGARD), 2.0) / 2.0)
        # le vis-à-vis (bande de 0,6 m contre le mur d'en face, de la largeur de l'objet) doit rester meublable
        vis_a_vis = Polygon([cand.pose.vers_monde(x, o.profondeur / 2 + profondeur + dz)
                             for x, dz in [(-o.largeur / 2, -0.6), (o.largeur / 2, -0.6), (o.largeur / 2, 0.0),
                                           (-o.largeur / 2, 0.0)]])
        if any(vis_a_vis.intersection(z).area > 0.05 for z in ctx.battements):
            bonus *= 0.3
        note += bonus
    par_cat: dict[str, list[_Place]] = {}
    for p in places:
        par_cat.setdefault(p.item.categorie, []).append(p)
    for r, cible in item.relations:
        if r == cand.relation:
            continue
        if r == "contre_mur" and not (o.mural or o.plafond):
            note += 0.8 if _mur_de(ctx, cand) is not None else -0.8
        elif r == "face_a" and cible in par_cat:
            meilleur = -1.0
            for t in par_cat[cible]:
                vx, vz = t.pose.x - cand.pose.x, t.pose.z - cand.pose.z
                d = math.hypot(vx, vz)
                if d < 1e-6:
                    continue
                fx, fz = cand.pose.face()
                tx, tz = t.pose.face()
                regard = (fx * vx + fz * vz) / d
                retour = -(tx * vx + tz * vz) / d
                distance = 1.0 - min(abs(d - 2.6), 2.0) / 2.0
                meilleur = max(meilleur, regard + retour + distance)
            note += meilleur
        elif r == "a_cote_de" and cible in par_cat:
            d = min(cand.emprise.distance(t.emprise) for t in par_cat[cible])
            note += 0.8 - min(d, 1.5)
        elif r == "sous_fenetre" and ctx.fenetres:
            d = min(cand.emprise.distance(z) for _, z in ctx.zones_fenetres)
            note += 0.6 if d < 0.05 else -0.4
        elif r == "dans_un_coin":
            pass
    if ctx.circulation is not None and cand.au_sol and cand.relation not in ("au_centre", "sous", "autour_de", "devant",
                                                                               "au_pied_de"):
        gene = cand.emprise.intersection(ctx.circulation).area / max(cand.emprise.area, 1e-6)
        note -= 0.8 * gene
    return note


# ── Contraintes dures ──────────────────────────────────────────────────────────────────────────────
def _verticales_croisent(a: _Place, b: _Place) -> bool:
    return a.bas < b.haut - 0.005 and b.bas < a.haut - 0.005


def _collision(a: _Place, b: _Place) -> bool:
    if a.support == b.item.nom or b.support == a.item.nom:
        return False
    if a.item.objet.sol_partage != b.item.objet.sol_partage:
        return False
    if not _verticales_croisent(a, b):
        return False
    if _boites_disjointes(a.boite, b.boite, 0.0):
        return False
    return a.emprise.intersection(b.emprise).area > 1e-4


def _gene_au_sol(p: _Place) -> bool:
    """Objet qui occupe le sol (gêne un dégagement ou un passage)."""
    o = p.item.objet
    if o.sol_partage or o.plafond or p.support:
        return False
    if o.mural and p.bas >= HAUTEUR_LIBRE_MURAL:
        return False
    return True


def _zone_genee(proprietaire: _Place, autre: _Place) -> bool:
    """La zone de dégagement de `proprietaire` est-elle occupée par `autre` (selon leurs relations) ?"""
    if proprietaire.zone is None or proprietaire.envahit_permis(autre):
        return False
    zone = proprietaire.zone_avant() if proprietaire.cote_permis(autre) else proprietaire.zone
    if zone is None or _boites_disjointes(zone.bounds, autre.boite, 0.0):
        return False
    return zone.intersection(autre.emprise).area > 1e-4


def _conflit(ctx: _Contexte, cand: _Place, places: list[_Place]) -> str | None:
    o = cand.item.objet
    if ctx.rect is not None:                          # pièce rectangulaire : test numérique des 4 coins
        x0, z0, x1, z1 = ctx.rect
        if not all(x0 - 0.005 <= x <= x1 + 0.005 and z0 - 0.005 <= z <= z1 + 0.005 for x, z in cand.coins):
            return "hors_piece"
    elif ctx.convexe:                                 # pièce convexe : les 4 coins suffisent
        if not contains_xy(ctx.tolere, [c[0] for c in cand.coins], [c[1] for c in cand.coins]).all():
            return "hors_piece"
    elif not cand.emprise.within(ctx.tolere):
        return "hors_piece"
    if cand.haut > ctx.hauteur + (1e-6 if o.plafond else -0.01):
        return "trop_haut"
    for p in places:
        if _collision(cand, p):
            return "chevauchement"
    gene = _gene_au_sol(cand)
    if gene:
        if cand.zone is not None and not cand.zone.within(ctx.tolere_zone):
            return "degagement_hors_piece"
        for p in places:
            if not _gene_au_sol(p):
                continue
            if _zone_genee(cand, p):
                return "degagement_occupe"
            if _zone_genee(p, cand):
                return "dans_un_degagement"
        for z, b in zip(ctx.battements, ctx.boites_battements):
            if not _boites_disjointes(b, cand.boite, 0.0) and z.intersection(cand.emprise).area > 1e-4:
                return "porte"
        if cand.haut > 0.05:
            for f, z in ctx.zones_fenetres:
                if cand.haut > f.allege + 1e-6 and not _boites_disjointes(z.bounds, cand.boite, 0.0) \
                        and z.intersection(cand.emprise).area > 1e-4:
                    return "fenetre"
    if o.mural:
        for porte in ctx.portes:
            z = porte.zone_devant(ctx.piece.nom, 0.3, 0.1)
            if cand.bas < porte.hauteur + 0.1 and z.intersection(cand.emprise).area > 1e-5:
                return "baie_porte"
        for f in ctx.fenetres:
            z = f.zone_devant(ctx.piece.nom, 0.3, 0.05)
            if cand.bas < f.allege + f.hauteur + 0.05 and cand.haut > f.allege - 0.05 \
                    and z.intersection(cand.emprise).area > 1e-5:
                return "baie_fenetre"
    return None


# ── Accessibilité ──────────────────────────────────────────────────────────────────────────────────
class _Grille:
    def __init__(self, ctx: _Contexte):
        x0, z0, x1, z1 = ctx.poly.bounds
        self.xs = np.arange(x0 + PAS_GRILLE / 2, x1, PAS_GRILLE)
        self.zs = np.arange(z0 + PAS_GRILLE / 2, z1, PAS_GRILLE)
        self.X, self.Z = np.meshgrid(self.xs, self.zs)
        self.dedans = contains_xy(ctx.poly, self.X, self.Z)
        graines = np.zeros_like(self.dedans)
        for o in ctx.portes:
            graines |= contains_xy(o.zone_devant(ctx.piece.nom, 0.8), self.X, self.Z)
        self.graines = graines
        self.cache: dict[int, np.ndarray] = {}

    def masque(self, poly: Polygon) -> np.ndarray:
        cle = id(poly)
        if cle not in self.cache:
            self.cache[cle] = contains_xy(poly, self.X, self.Z)
        return self.cache[cle]


def _zones_acces(p: _Place, places: list[_Place]) -> list[Polygon]:
    o = p.item.objet
    if o.mural:
        return [p.emprise.buffer(0.6)]

    zones = []
    cible_bloque = False
    if p.zone is not None:
        for q in places:
            if q is not p and p.envahit_permis(q) and _gene_au_sol(q) and q.emprise.intersection(p.zone).area > 0.3 * p.zone.area:
                cible_bloque = True
        if not cible_bloque:
            zones.append(p.zone)
            zones.append(o.rectangle(p.pose, marge_avant=0.5).difference(p.emprise))
    if p.zone is None or cible_bloque:
        zones.append(p.emprise.buffer(0.45, join_style=2).difference(p.emprise))
    return zones


def _inaccessibles(ctx: _Contexte, grille: _Grille, places: list[_Place]) -> list[str]:
    libre = grille.dedans.copy()
    for p in places:
        if _gene_au_sol(p):
            libre &= ~contains_xy(p.emprise, grille.X, grille.Z)
    distance = ndimage.distance_transform_edt(libre, sampling=PAS_GRILLE)
    passable = distance > RAYON_PASSAGE
    etiquettes, _ = ndimage.label(passable)
    if grille.graines.any():
        atteintes = set(np.unique(etiquettes[grille.graines & passable])) - {0}
    else:
        tailles = np.bincount(etiquettes.ravel())
        tailles[0] = 0
        atteintes = {int(tailles.argmax())} if tailles.max() > 0 else set()
    atteint = np.isin(etiquettes, list(atteintes)) if atteintes else np.zeros_like(passable)
    sortie = []
    for p in places:
        o = p.item.objet
        if o.plafond or p.support or o.sol_partage:
            continue
        if o.mural and p.cible:            # accroché au-dessus d'un meuble : on l'atteint par ce meuble
            continue
        ok = False
        for z in _zones_acces(p, places):
            if (atteint & contains_xy(z, grille.X, grille.Z)).any():
                ok = True
                break
        if not ok:
            sortie.append(p.item.nom)
    return sortie


# ── Ordre et recherche ─────────────────────────────────────────────────────────────────────────────
REDUCTION_UTILE = 0.05


def _compact(categorie: str, objet: Objet, fabrique: Fabrique, germe: int, options: dict) -> Objet | None:
    """Repli dimensionnel : la même catégorie aux largeur et profondeur MINIMALES de son vocabulaire (un
    linéaire de cuisine de 1,2 m au lieu de 2,4 m, une armoire de 0,9 m). Essayé seulement quand l'objet
    normal n'a aucune pose valide. None si le gain serait négligeable."""
    spec = voc.CATEGORIES[categorie]
    largeur, profondeur = float(spec["largeur"][0]), float(spec["profondeur"][0])
    if largeur > objet.largeur * (1 - REDUCTION_UTILE) and profondeur > objet.profondeur * (1 - REDUCTION_UTILE):
        return None
    reduit = fabrique(categorie, germe, dict(options, largeur=min(largeur, objet.largeur),
                                             profondeur=min(profondeur, objet.profondeur), hauteur=objet.hauteur))
    if reduit.largeur * reduit.profondeur >= objet.largeur * objet.profondeur * (1 - REDUCTION_UTILE):
        return None                               # la fabrique n'a pas suivi les dimensions demandées
    reduit.meta = dict(reduit.meta, compact=True)
    return reduit


def _preparer_items(demandes: list[Demande], fabrique: Fabrique, graine: int) -> list[_Item]:
    items: list[_Item] = []
    compte: dict[str, int] = {}
    for i, d in enumerate(demandes):
        voc.categorie(d.categorie)
        for r, c in d.relations:
            if r not in voc.RELATIONS:
                raise KeyError(f"relation hors vocabulaire : {r!r}")
            if c is not None:
                voc.categorie(c)
        options: dict[str, Any] = {}
        if d.materiaux:
            options["materiaux"] = dict(d.materiaux)
        if d.style:
            options["style"] = d.style
        germe = (graine * 7919 + i * 104729) & 0x7FFFFFFF
        objet = compact = None
        for k in range(max(0, int(d.nombre))):
            compte[d.categorie] = compte.get(d.categorie, 0) + 1
            if objet is None:                     # les exemplaires d'une demande sont identiques (paire, chaises)
                objet = fabrique(d.categorie, germe, dict(options))
                compact = _compact(d.categorie, objet, fabrique, germe, options)
            items.append(_Item(f"{d.categorie}_{compte[d.categorie]}", d.categorie, objet, list(d.relations), i, k,
                               compact=compact))
    cats = {it.categorie for it in items}
    niveaux: dict[str, int] = {}

    def niveau(cat: str, pile: tuple = ()) -> int:
        if cat in niveaux:
            return niveaux[cat]
        if cat in pile:
            return 0
        deps = {c for it in items if it.categorie == cat for c in it.cibles if c in cats and c != cat}
        n = 0 if not deps else 1 + max(niveau(c, pile + (cat,)) for c in deps)
        niveaux[cat] = n
        return n
    for it in items:
        it.niveau = niveau(it.categorie)

    def cle(it: _Item):
        o = it.objet
        accroche = 1 if (o.mural or o.plafond or any(r == "sur" for r, _ in it.relations)) else 0
        return (accroche, -round(it.encombrement, 3), -len(it.relations), it.demande, it.rang)

    # Ordre par GROUPES, comme un agenceur : le plus encombrant des objets libres, puis tout ce qui s'y
    # rapporte (le lit, ses tables de chevet, leurs lampes), puis le groupe suivant. L'ordre est aussi la
    # priorité de la recherche (objectif lexicographique).
    def cibles_ici(it: _Item) -> set[str]:
        return (it.cibles & cats) - {it.categorie}

    ordre: list[_Item] = []
    restants = sorted(items, key=cle)
    while restants:
        poses = {it.categorie for it in ordre}
        prets = [it for it in restants if cibles_ici(it) <= poses]
        tete = max((k for k, it in enumerate(ordre) if not cibles_ici(it)), default=0)
        groupe = {it.categorie for it in ordre[tete:]}
        choix = ([it for it in prets if cibles_ici(it) & groupe]            # 1. ce qui dépend du groupe ouvert
                 or [it for it in prets if not cibles_ici(it)]               # 2. la tête du groupe suivant
                 or prets                                                    # 3. dépendants d'un groupe ancien
                 or restants[:1])                                            # 4. cycle : rompu par la taille
        ordre.append(choix[0])
        restants.remove(choix[0])
    return ordre


def disposer(piece: PiecePlan, demandes: list[Demande], *, fabrique: Fabrique = objet_provisoire,
             hauteur_plafond: float = 2.5, graine: int = 0) -> Disposition:
    """Dispose les objets demandés dans la pièce ; rend les instances posées, les échecs motivés, les mesures."""
    ctx = _contexte(piece, hauteur_plafond)
    grille = _Grille(ctx)
    items = _preparer_items(demandes, fabrique, graine)
    ctx.regardees = {c for it in items for r, c in it.relations if r == "face_a" and c}
    for it in items:
        for r, c in it.relations:
            if r == "autour_de" and c:
                ctx.entourees[c] = max(ctx.entourees.get(c, 0.0), it.objet.profondeur + 0.1)
    rng = random.Random(graine)
    etat = {"noeuds": 0, "meilleur": None, "fini": False}
    raisons: dict[str, dict[str, int]] = {it.nom: {} for it in items}

    # Objectif LEXICOGRAPHIQUE dans l'ordre des objets (cibles et gros objets d'abord) : placer l'objet i
    # vaut mieux que placer n'importe quel ensemble d'objets suivants (un linéaire de cuisine ne s'efface pas
    # devant deux chaises). À égalité, la meilleure somme des notes.
    def enregistrer(places: list[_Place], sautes: list, drapeaux: tuple, note: float) -> None:
        m = etat["meilleur"]
        if m is None or drapeaux > m[3] or (drapeaux == m[3] and note > m[2]):
            etat["meilleur"] = (list(places), list(sautes), note, drapeaux)
        if not sautes:
            etat["fini"] = True

    def raison_cible(it: _Item, places: list[_Place]) -> str | None:
        posees = {p.item.categorie for p in places}
        for r, c in it.relations:
            if r in RELATIONS_DEFINISSANTES and c not in posees:
                return f"sa cible « {c} » n'est pas placée (relation {r})"
        return None

    def explorer(i: int, places: list[_Place], sautes: list, drapeaux: tuple, note: float) -> None:
        if etat["fini"]:
            return
        m = etat["meilleur"]
        if m is not None:
            prefixe = m[3][:i]
            if drapeaux < prefixe or (drapeaux == prefixe and all(m[3][i:])):
                return                                    # ne peut plus faire mieux que le meilleur connu
        if i == len(items):
            enregistrer(places, sautes, drapeaux, note)
            return
        etat["noeuds"] += 1
        it = items[i]
        bloque = raison_cible(it, places)
        local: dict[str, int] = {}
        valides = 0
        budget_epuise = etat["noeuds"] > BUDGET
        if bloque is None and not budget_epuise:
            compte = raisons[it.nom]
            cands: list[tuple[float, _Place]] = []
            variantes = [(it, 0.0)] + ([(replace(it, objet=it.compact), MALUS_COMPACT)] if it.compact else [])
            for variante, malus in variantes:
                if cands:
                    break                              # le repli compact ne sert que si l'objet normal est impossible
                for c in _candidats(ctx, variante, places, rng):
                    r = _conflit(ctx, c, places)
                    if r is not None:
                        compte[r] = compte.get(r, 0) + 1
                        local[r] = local.get(r, 0) + 1
                        continue
                    cands.append((_note_relations(ctx, c, places) - malus + rng.random() * 0.02, c))
            cands.sort(key=lambda nc: -nc[0])
            valides = len(cands)
            essayes = 0
            for n, c in _divers(cands):
                if essayes >= (TOP_K_PREMIERS if i < NIVEAUX_LARGES else TOP_K) or etat["noeuds"] > BUDGET \
                        or etat["fini"]:
                    break
                nouvelles = places + [c]
                if _inaccessibles(ctx, grille, nouvelles):
                    compte["rendrait_inaccessible"] = compte.get("rendrait_inaccessible", 0) + 1
                    local["rendrait_inaccessible"] = local.get("rendrait_inaccessible", 0) + 1
                    continue
                essayes += 1
                explorer(i + 1, nouvelles, sautes, drapeaux + (True,), note + n)
            if etat["fini"]:
                return
        if bloque:
            motif = bloque
        elif budget_epuise:
            motif = f"budget de recherche épuisé ({BUDGET} nœuds) avant d'essayer cet objet sur ce chemin"
        else:
            motif = _motif(it, local, valides)
        explorer(i + 1, places, sautes + [(it, motif, local)], drapeaux + (False,), note)

    explorer(0, [], [], (), 0.0)
    places, sautes = (etat["meilleur"][0], etat["meilleur"][1]) if etat["meilleur"] else \
        ([], [(it, "recherche vide", {}) for it in items])
    instances = [Instance(p.item.objet, p.pose, p.item.nom,
                          meta={"categorie": p.item.categorie, "relation": p.relation, "cible": p.cible,
                                "support": p.support, "piece": piece.nom,
                                "relations": [list(r) for r in p.item.relations]}) for p in places]
    echecs = [{"categorie": it.categorie, "nom": it.nom, "raison": motif,
               "rejets": dict(sorted(local.items(), key=lambda kv: -kv[1])),
               "rejets_toute_recherche": dict(sorted(raisons[it.nom].items(), key=lambda kv: -kv[1]))}
              for it, motif, local in sautes]
    mesures = mesurer(piece, places, hauteur_plafond)
    mesures.update(demandes=len(items), noeuds_recherche=etat["noeuds"])
    return Disposition(instances, echecs, mesures)


ECARTS_DIVERS = (1.5, 0.8, 0.4)


def _divers(cands: list[tuple[float, _Place]]):
    """Candidats triés par note, par vagues de diversité : d'abord des poses éloignées d'au moins 1,5 m (ou
    d'une autre orientation), puis à 0,45 m, puis le reste. Le retour arrière essaie ainsi de VRAIES
    alternatives (autre mur, autre coin) au lieu de la même pose décalée de 10 cm."""
    retenus: list[tuple[float, _Place]] = []
    restants = list(cands)
    for ecart in ECARTS_DIVERS:
        suivants = []
        for n, c in restants:
            proche = any(abs(math.remainder(c.pose.lacet - r.pose.lacet, 2 * math.pi)) < 0.1
                         and math.hypot(c.pose.x - r.pose.x, c.pose.z - r.pose.z) < ecart
                         and abs(c.pose.y - r.pose.y) < 0.05 for _, r in retenus)
            if proche:
                suivants.append((n, c))
            else:
                retenus.append((n, c))
                yield n, c
        restants = suivants
    yield from restants


def _motif(it: _Item, compte: dict[str, int], valides: int) -> str:
    if not compte and valides == 0:
        return "aucune pose candidate (pièce trop petite pour l'objet ou cible absente)"
    total = sum(compte.values())
    libelles = {"hors_piece": "hors de la pièce", "chevauchement": "chevauche un objet",
                "degagement_hors_piece": "dégagement hors de la pièce", "degagement_occupe": "dégagement occupé",
                "dans_un_degagement": "dans le dégagement d'un objet", "porte": "bloque une porte",
                "fenetre": "plus haut que l'allège devant une fenêtre", "baie_porte": "sur la baie d'une porte",
                "baie_fenetre": "sur la baie d'une fenêtre", "trop_haut": "dépasse le plafond",
                "rendrait_inaccessible": "rendrait un objet inaccessible"}
    detail = ", ".join(f"{libelles.get(k, k)} : {v}" for k, v in sorted(compte.items(), key=lambda kv: -kv[1])[:4])
    return f"aucune pose valide ({total} poses rejetées ; {detail})"


# ── Mesures indépendantes ──────────────────────────────────────────────────────────────────────────
def mesurer(piece: PiecePlan, places: list[_Place], hauteur_plafond: float) -> dict[str, Any]:
    ctx = _contexte(piece, hauteur_plafond)
    chevauchements = sum(1 for i, a in enumerate(places) for b in places[i + 1:] if _collision(a, b))
    hors = sum(1 for p in places if not p.emprise.within(ctx.poly.buffer(0.01, join_style=2)))
    portes = 0
    for z in ctx.battements:
        if any(_gene_au_sol(p) and z.intersection(p.emprise).area > 1e-4 for p in places):
            portes += 1
    fenetres = 0
    for f, z in ctx.zones_fenetres:
        if any(_gene_au_sol(p) and p.haut > f.allege + 1e-6 and z.intersection(p.emprise).area > 1e-4 for p in places):
            fenetres += 1
    inaccessibles = _inaccessibles(ctx, _Grille(ctx), places)
    au_sol = [p for p in places if _gene_au_sol(p)]
    degagements = sum(1 for a in au_sol for b in au_sol if a is not b and _zone_genee(a, b))
    return {"chevauchements": chevauchements, "hors_piece": hors, "portes_bloquees": portes,
            "fenetres_bloquees": fenetres, "degagements_occupes": degagements, "inaccessibles": inaccessibles,
            "places": len(places)}


def mesurer_instances(piece: PiecePlan, instances: list[Instance], hauteur_plafond: float = 2.5) -> dict[str, Any]:
    """Les mêmes mesures recalculées depuis des instances livrées (pour un juge en aval)."""
    places = []
    for inst in instances:
        relations = [tuple(r) for r in (inst.meta or {}).get("relations", [])]
        item = _Item(inst.nom, inst.objet.categorie, inst.objet, relations, -1, 0)
        support = inst.meta.get("support") if inst.meta else None
        cible = inst.meta.get("cible") if inst.meta else None
        places.append(_Place(item, inst.pose, inst.objet.emprise(inst.pose), inst.objet.zone_degagement(inst.pose),
                             inst.pose.y, inst.pose.y + inst.objet.hauteur, support, cible))
    return mesurer(piece, places, hauteur_plafond)


# ── Logement entier ────────────────────────────────────────────────────────────────────────────────
def meubler(plan: Plan, demandes_par_piece: dict[str, list[Demande]], *, fabrique: Fabrique = objet_provisoire,
            graine: int = 0) -> dict[str, Disposition]:
    sortie = {}
    for i, (nom, demandes) in enumerate(demandes_par_piece.items()):
        sortie[nom] = disposer(plan.piece(nom), demandes, fabrique=fabrique, hauteur_plafond=plan.hauteur_plafond,
                               graine=graine * 101 + i)
    return sortie


def scene_meublee(plan: Plan, dispositions: dict[str, Disposition], *, plafond: bool = True, maquette: bool = False,
                  ouverture_portes: float = 0.0) -> Scene:
    """Scène exportable : géométrie du plan + instances posées dans le nœud de leur pièce."""
    from monde.plan import construire_geometrie
    racine = construire_geometrie(plan, plafond=plafond, maquette=maquette, ouverture_portes=ouverture_portes)
    par_nom = {n.nom: n for n in racine.enfants}
    echecs = {}
    for nom, d in dispositions.items():
        noeud = par_nom[nom]
        for inst in d.instances:
            o = inst.objet
            if maquette and (o.plafond or inst.pose.y >= 1.2):
                continue                                  # la maquette est coupée à 1,20 m
            noeud.instances.append(inst)
        noeud.extras["disposition"] = d.mesures
        if d.echecs:
            echecs[nom] = d.echecs
    return Scene(racine, extras={"programme": {"type_scene": "interieur"}, "echecs_disposition": echecs})


# ── Démonstration (rendus f3d) ─────────────────────────────────────────────────────────────────────
def _racine_depot() -> Path:
    """Racine du dépôt principal (un arbre de travail git `.claude/worktrees/x` renvoie au dépôt qui le porte :
    les sorties d'essai vivent hors de git, dans le dépôt principal)."""
    racine = Path(__file__).resolve().parents[3]
    if racine.parent.name == "worktrees" and racine.parent.parent.name == ".claude":
        racine = racine.parents[2]
    return racine


SORTIE_DEMO = _racine_depot() / "application" / "output" / "3d" / "essais" / "monde" / "plan_disposition"


def demo(dossier: Path = SORTIE_DEMO, graine: int = 1, programme: str = "maison") -> dict[str, Any]:
    from monde import export_gltf, rendu
    from monde.plan import PieceDemandee, concevoir_plan
    programmes = {
        "maison": [PieceDemandee("entree", "entree", 5.0), PieceDemandee("salon", "salon", 24.0, ["cuisine"]),
                   PieceDemandee("cuisine", "cuisine", 10.0), PieceDemandee("chambre_1", "chambre", 12.5),
                   PieceDemandee("chambre_2", "chambre", 10.5), PieceDemandee("salle_de_bain", "salle_de_bain", 6.0),
                   PieceDemandee("wc", "wc", 1.6)],
    }
    plan = concevoir_plan(programmes[programme], graine=graine)
    demandes = {p.nom: demandes_typiques(p.fonction) for p in plan.pieces}
    dispositions = meubler(plan, demandes, graine=graine)
    dossier = Path(dossier) / f"{programme}_g{graine}"
    rapport: dict[str, Any] = {"plan": plan.mesures, "pieces": {}}
    for nom, d in dispositions.items():
        rapport["pieces"][nom] = {"mesures": d.mesures, "echecs": d.echecs}
    for variante, kw in {"maquette": {"maquette": True, "plafond": False, "ouverture_portes": 0.0},
                         "complet": {"maquette": False, "plafond": False, "ouverture_portes": 0.6}}.items():
        scene = scene_meublee(plan, dispositions, **kw)
        glb = dossier / f"{variante}.glb"
        export = export_gltf.exporter(scene, glb, resolution=128)
        rendus = rendu.rendre_vues(glb, dossier, vues=("plan", "aerienne_sud_est", "aerienne_nord_ouest"),
                                   resolution=(1100, 850), prefixe=variante)
        rapport[variante] = {"glb": str(glb), "triangles": export["triangles"], "planche": rendus["planche"]}
    (dossier / "rapport.json").write_text(json.dumps(rapport, ensure_ascii=False, indent=1, default=str))
    return rapport


def demo_pieces(dossier: Path = SORTIE_DEMO, graine: int = 0) -> dict[str, Any]:
    """Une pièce meublée seule par fonction, pour l'inspection rapprochée."""
    from monde import export_gltf, rendu
    from monde.plan import PieceDemandee, concevoir_plan
    sortie = {}
    for fonction, spec in voc.FONCTIONS_PIECES.items():
        surface = round(0.6 * spec["surface"][0] + 0.4 * spec["surface"][1], 1)
        plan = concevoir_plan([PieceDemandee(fonction, fonction, surface)], graine=graine)
        d = disposer(plan.pieces[0], demandes_typiques(fonction), hauteur_plafond=plan.hauteur_plafond, graine=graine)
        scene = scene_meublee(plan, {fonction: d}, plafond=False, maquette=False, ouverture_portes=0.6)
        glb = Path(dossier) / "pieces" / f"{fonction}.glb"
        export_gltf.exporter(scene, glb, resolution=128)
        rendus = rendu.rendre_vues(glb, glb.parent, vues=("plan", "aerienne_sud_est"), resolution=(800, 650),
                                   prefixe=fonction)
        sortie[fonction] = {"mesures": d.mesures, "echecs": d.echecs, "planche": rendus["planche"]}
    (Path(dossier) / "pieces" / "rapport.json").write_text(json.dumps(sortie, ensure_ascii=False, indent=1, default=str))
    return sortie


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Démonstration plan + disposition (rendus f3d)")
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--pieces", action="store_true")
    parser.add_argument("--graine", type=int, default=1)
    parser.add_argument("--dossier", type=Path, default=SORTIE_DEMO)
    args = parser.parse_args(argv)
    if args.demo:
        r = demo(args.dossier, args.graine)
        print(json.dumps({k: v for k, v in r.items() if k != "pieces"}, ensure_ascii=False, indent=1, default=str))
        for nom, p in r["pieces"].items():
            print(nom, p["mesures"], [e["nom"] + " : " + e["raison"] for e in p["echecs"]])
    if args.pieces:
        r = demo_pieces(args.dossier, args.graine)
        for nom, p in r.items():
            print(nom, p["mesures"], [e["nom"] + " : " + e["raison"] for e in p["echecs"]], p["planche"])


if __name__ == "__main__":
    main()
