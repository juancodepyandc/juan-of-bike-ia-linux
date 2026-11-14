"""Liaisons : dimensionnement par règles et usinages produits sur LES DEUX pièces.

Chaque liaison part d'une interface MESURÉE entre deux solides (faces en contact ou face à face)
et décide comme un ingénieur : type de vis selon la matière qui reçoit le filet, diamètre selon
les distances au bord et l'effort, longueur prise dans la série normalisée, jeu selon le procédé.
Elle rend les enlèvements et ajouts de matière de chaque pièce, la quincaillerie normalisée posée
en place, les interférences VOULUES (ajustements serrés, déformation d'un clip) pour que le contrôle
puisse les distinguer d'une collision, les contraintes de montage et les calculs justificatifs.

Les efforts calculés sont des estimations de conception (méthodes usuelles, coefficients de
sécurité explicites) : aucune résistance n'est certifiée sans essai.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from application import engineering_standards as normes
from application.engineering_assembly import (COTES, ErreurConception, Interface, Piece, cone,
                                              cylindre, extrusion_profil, interface_principale, prisme_hexagonal,
                                              profondeur, union, volume)

G = 9.81


@dataclass
class Resultat:
    id: str
    type: str
    entre: list[str]
    ajouts: dict[str, list[Any]] = field(default_factory=dict)
    retraits: dict[str, list[Any]] = field(default_factory=dict)
    quincaillerie: list[Piece] = field(default_factory=list)
    cinematique: dict[str, Any] | None = None
    interferences: list[dict[str, Any]] = field(default_factory=list)
    elastiques: list[dict[str, Any]] = field(default_factory=list)
    trous: list[dict[str, Any]] = field(default_factory=list)
    contraintes: list[dict[str, Any]] = field(default_factory=list)
    calculs: dict[str, Any] = field(default_factory=dict)
    decisions: list[dict[str, Any]] = field(default_factory=list)
    etapes: list[str] = field(default_factory=list)
    interface: dict[str, Any] = field(default_factory=dict)
    trous_existants: set[str] = field(default_factory=set)   # achats dont on ne modélise que des trous déclarés

    def ajouter(self, piece: str, solide) -> None:
        self.ajouts.setdefault(piece, []).append(solide)

    def retirer(self, piece: str, solide) -> None:
        self.retraits.setdefault(piece, []).append(solide)


# --------------------------------------------------------------------------- outils communs

def mat(p: Piece) -> dict[str, Any]:
    return normes.MATIERES[p.matiere]


def proc(p: Piece) -> dict[str, Any]:
    return normes.PROCEDES[p.procede]


def famille(p: Piece) -> str:
    return mat(p)["famille"]


def cyl_entre(p0, p1, rayon: float, nseg: int | None = None):
    p0, p1 = np.asarray(p0, dtype=float), np.asarray(p1, dtype=float)
    axe = p1 - p0
    h = float(np.linalg.norm(axe))
    return cylindre(rayon, h, axe / h, (p0 + p1) / 2.0, nseg)


def ligament_min(p: Piece, d: float) -> float:
    k = {"metal": 1.0, "composite": 1.0, "bois": 0.6, "polymere": 0.5}[famille(p)]
    return max(proc(p)["paroi_min"], k * d)


def masse_piece(p: Piece) -> float:
    return volume(p.solide) * mat(p)["densite"] * 1e-3


def effort(liaison: dict[str, Any], *pieces: Piece) -> tuple[float, str]:
    if liaison.get("effort_N"):
        return float(liaison["effort_N"]), "effort donné par la demande"
    poids = max(masse_piece(p) for p in pieces) * 1e-3 * G
    f = max(20.0, 3.0 * poids)
    return f, f"hypothèse : max(20 N, 3 × poids de la pièce la plus lourde = {poids:.1f} N)"


def direction_plan(itf: Interface, cote: str | None) -> np.ndarray | None:
    if not cote or cote not in COTES:
        return None
    s = COTES[cote]
    v = np.array([float(s @ itf.e1), float(s @ itf.e2)])
    n = float(np.linalg.norm(v))
    return v / n if n > 0.3 else None


def restreindre_bord(region, itf: Interface, cote: str | None, bande: float):
    from shapely.geometry import Polygon
    d = direction_plan(itf, cote)
    if d is None or region.is_empty:
        return region
    xs = np.array(region.exterior.coords if region.geom_type == "Polygon" else
                  [c for g in region.geoms for c in g.exterior.coords])
    proj = xs @ d
    seuil = float(proj.max()) - bande
    grand = 1e5
    t = np.array([-d[1], d[0]])
    demi = Polygon([tuple(d * seuil + t * grand), tuple(d * seuil - t * grand),
                    tuple(d * (seuil + grand) - t * grand), tuple(d * (seuil + grand) + t * grand)])
    r = region.intersection(demi)
    return r if not r.is_empty else region


def retirer_exclusions(region, itf: Interface, liaison: dict[str, Any], marge: float):
    """Enlève de la région les zones où une autre liaison a déjà posé un article ou un perçage."""
    from shapely.geometry import MultiPoint
    from shapely.ops import unary_union
    zones = []
    for solide in liaison.get("_exclusions") or []:
        m = solide.to_mesh64()
        v = np.asarray(m.vert_properties, dtype=float)[:, :3]
        if len(v) < 3:
            continue
        pts = [itf.plan(q) for q in v]
        zones.append(MultiPoint(pts).convex_hull.buffer(marge))
    if not zones:
        return region
    reste = region.difference(unary_union(zones))
    return reste


def repartir(region, n: int) -> list[tuple[float, float]]:
    """n points dans une région 2D : le long de sa ligne médiane si elle est mince, en grille sinon."""
    from shapely.geometry import Point
    from shapely.ops import nearest_points
    if region.is_empty or n <= 0:
        return []
    if n == 1:
        q = region.representative_point() if not region.contains(region.centroid) else region.centroid
        return [(q.x, q.y)]
    rect = region.minimum_rotated_rectangle
    coins = np.array(rect.exterior.coords[:4]) if rect.geom_type == "Polygon" else None
    if coins is None:
        q = region.representative_point()
        return [(q.x, q.y)] * n
    a1, a2 = coins[1] - coins[0], coins[2] - coins[1]
    long_, court = (a1, a2) if np.linalg.norm(a1) >= np.linalg.norm(a2) else (a2, a1)
    L, l = float(np.linalg.norm(long_)), float(np.linalg.norm(court))
    centre = coins.mean(axis=0)
    u = long_ / max(L, 1e-9)
    w = court / max(l, 1e-9)
    largeur_moyenne = region.area / max(1e-9, region.length / 2.0)
    anneau = region.geom_type == "Polygon" and len(region.interiors) > 0
    if anneau or (largeur_moyenne < 0.2 * L and l > 0.5 * L):
        # anneau ou cadre : abscisse curviligne le long du contour extérieur
        contour = region.exterior
        pts = [contour.interpolate((k + 0.5) / n, normalized=True) for k in range(n)]
        sortie = []
        for q in pts:
            if not region.contains(q):
                q = nearest_points(region, q)[0]
            sortie.append((q.x, q.y))
        return sortie
    if L / max(l, 1e-9) >= 2.0 or n <= 3:
        pts = [centre + u * (-L / 2 + L * (k + 0.5) / n) for k in range(n)]
    else:
        nx = math.ceil(math.sqrt(n * L / max(l, 1e-9)))
        ny = math.ceil(n / nx)
        pts = []
        for i in range(nx):
            for j in range(ny):
                if len(pts) < n:
                    pts.append(centre + u * (-L / 2 + L * (i + 0.5) / nx) + w * (-l / 2 + l * (j + 0.5) / ny))
    sortie = []
    for q in pts:
        point = Point(float(q[0]), float(q[1]))
        if not region.contains(point):
            point = nearest_points(region, point)[0]
        sortie.append((point.x, point.y))
    return sortie


def longueur_utile(region) -> float:
    rect = region.minimum_rotated_rectangle
    if rect.geom_type != "Polygon":
        return 0.0
    c = np.array(rect.exterior.coords[:4])
    return float(max(np.linalg.norm(c[1] - c[0]), np.linalg.norm(c[2] - c[1])))


def article(nom: str, norme: str, d: float, longueur: float | None = None, **autres) -> dict[str, Any]:
    a = {"norme": norme, "d": d, "longueur": longueur, "designation": nom}
    a.update(autres)
    return a


def quincaillerie(id_: str, nom: str, solide, matiere: str, art: dict[str, Any], hote: str, approche, liaison: str,
                  origine: str = "standard", groupe: str | None = None, rang: int = 0) -> Piece:
    """Article posé en place. `groupe` réunit les articles d'un même point de fixation, `rang` dit
    dans quel ordre ils se posent (rondelle sous tête, vis, rondelle, écrou)."""
    art = {**art, "groupe": groupe or id_, "rang": rang}
    p = Piece(id=id_, nom=nom, forme="bloc", dims=[1, 1, 1], matiere=matiere, procede="achat", origine=origine)
    p.solide = solide
    p.article = art
    p.hote = hote
    p.approche = np.asarray(approche, dtype=float)
    p.liaison = liaison
    return p


def _tete_iso4762(d: float, appui, axe):
    dk, k, s, t, _ = normes.ISO4762[d]
    axe = np.asarray(axe, dtype=float)
    tete = cyl_entre(appui, np.asarray(appui) - axe * k, dk / 2.0)
    empreinte = prisme_hexagonal(s, 2 * t, axe, np.asarray(appui) - axe * k)
    return tete - empreinte


def _tete_fraisee(dk: float, d: float, k: float, sommet, axe):
    axe = np.asarray(axe, dtype=float)
    return cone(dk / 2.0, d / 2.0, k, axe, sommet)


# --------------------------------------------------------------------------- vis

def liaison_vis(liaison: dict[str, Any], a: Piece, b: Piece, itf: Interface, pieces: dict[str, Piece]) -> Resultat:
    """A (côté tête) vissé dans B (qui reçoit le filet). La normale de l'interface va de A vers B."""
    r = Resultat(liaison["id"], "vis", [a.id, b.id])
    n = itf.normale
    F, source_F = effort(liaison, a, b)
    existants = b.trous_existants if b.origine == "achete" else None
    fam_b = famille(b)
    if existants:
        mode = "filetage_existant"
    elif fam_b == "bois":
        mode = "bois"
    elif fam_b == "polymere":
        mode = "insert" if liaison.get("demontable") and proc(b)["imprime"] else "autotaraudeuse"
    elif fam_b == "metal":
        mode = "taraudage"
    else:
        raise ErreurConception(f"{liaison['id']} : on ne taraude pas {mat(b)['nom']} ; utiliser un boulon et un écrou")
    # Diamètre proportionné aux pièces (règle d'atelier : d ≈ 0,3 × l'épaisseur en bois, 0,4 × ailleurs),
    # puis les plus proches au-dessus, enfin au-dessous si la place manque.
    centre = itf.monde(*_centre(itf))
    t_ref = min(profondeur(a.solide, centre, -n), profondeur(b.solide, centre + n * itf.ecart, n) + itf.ecart)
    if mode == "bois":
        serie = sorted(normes.DIN7997)
        cible = t_ref * 0.3
    elif mode == "filetage_existant":
        d_impose = _diametre_vis(existants.get("vis"))
        serie = [d_impose] if d_impose else [3.0]
        cible = serie[0]
    else:
        serie = [d for d in normes.DIAMETRES if d >= 2.0]
        cible = min(12.0, max(2.5, 0.4 * t_ref))
    candidats = [d for d in serie if d >= cible - 1e-9] + sorted([d for d in serie if d < cible - 1e-9], reverse=True)
    raisons = []
    for d in candidats:
        choix = _essayer_vis(liaison, a, b, itf, d, mode, F, existants)
        if choix.get("ok"):
            break
        raisons.append(f"M{d:g} : {choix['raison']}" if mode != "bois" else f"Ø{d:g} : {choix['raison']}")
    else:
        raise ErreurConception(f"{liaison['id']} : aucune vis ne convient ({' ; '.join(raisons[-3:])})")
    r.decisions.append({"sujet": liaison["id"], "decision": choix["resume"], "raison": choix["justification"]})
    r.calculs.update({"effort_N": round(F, 1), "source_effort": source_F, **choix["calculs"]})
    if mode == "filetage_existant":
        r.trous_existants.add(b.id)
    if a.origine == "achete":
        r.trous_existants.add(a.id)
    if choix.get("renfort") is not None:
        (cu, cv), rayon = choix["renfort"]
        C0 = itf.monde(cu, cv)
        r.ajouter(a.id, cyl_entre(C0 + n * 0.0, C0 - n * choix["ep_renfort"], rayon))
        r.calculs["renfort_diametre_mm"] = round(2 * rayon, 2)
        r.decisions.append({"sujet": liaison["id"], "decision": f"platine de renfort Ø{2 * rayon:.0f} mm ajoutée à {a.nom}",
                            "raison": f"le motif de fixation imposé par {b.nom} sort de {a.nom} : il faut de la matière autour de chaque trou"})
    if isinstance(choix.get("degagement"), (int, float)) and choix["degagement"] > 0:
        C1 = itf.monde(*itf.plan(np.asarray(b.centre, dtype=float)))
        r.retirer(a.id, cyl_entre(C1 + n * 1.0, C1 - n * (profondeur(a.solide, C1, -n) + 1.0), choix["degagement"] / 2.0))
    if a.origine == "achete" and not a.trous_existants:
        r.decisions.append({"sujet": liaison["id"], "decision": f"trous de fixation aux coins de {a.nom}",
                            "raison": "composant sans motif de fixation déclaré : positions à vérifier sur la pièce réelle"})
    # géométrie
    for k, (u, v) in enumerate(choix["points"]):
        P = itf.monde(u, v)
        ep_a = profondeur(a.solide, P, -n)
        dos = P - n * ep_a                       # face d'appui de la tête sur A
        g = choix
        # A : passage, lamage ou fraisure
        r.retirer(a.id, cyl_entre(dos - n * 1.0, P + n * 0.5, g["r_passage"]))
        # perçage simple : de l'interface jusqu'au lamage (le lamage est du côté de la tête, au dos de A)
        r.trous.append({"piece": a.id, "centre": P.tolist(), "axe": (-n).tolist(), "rayon": g["r_passage"],
                        "de": 0.0, "a": ep_a - g["noyage"] - (g["k"] if g["tete"] in ("ISO 10642", "DIN 7997") else 0.0),
                        "liaison": liaison["id"]})
        if g["tete"] in ("ISO 4762",) and g["noyage"] > 0:
            r.retirer(a.id, cyl_entre(dos - n * 1.0, dos + n * g["noyage"], g["r_lamage"]))
        if g["tete"] in ("ISO 10642", "DIN 7997"):
            # fraisure à 90° plus large de 0,1 mm au rayon que la tête posée 0,2 mm sous la surface
            rk = g["dk"] / 2.0 + 0.3
            r.retirer(a.id, cone(rk, g["r_passage"], rk - g["r_passage"], n, dos))
            r.retirer(a.id, cyl_entre(dos - n * 1.0, dos + n * 0.01, rk))
        # B : bossage si écart, puis avant-trou / taraudage / logement d'insert
        face_b = P + n * itf.ecart
        if itf.ecart > 1e-3:
            r.ajouter(b.id, cyl_entre(P, face_b + n * 0.3, g["r_bossage"]))
        prof_trou = g["prof_trou"]
        r.retirer(b.id, cyl_entre(P - n * 0.5, P + n * prof_trou, g["r_trou_b"]))
        r.trous.append({"piece": b.id, "centre": P.tolist(), "axe": n.tolist(), "rayon": g["r_trou_b"],
                        "de": itf.ecart, "a": prof_trou, "liaison": liaison["id"], "bossage": itf.ecart > 1e-3})
        # quincaillerie
        appui = dos + n * g["noyage"]            # face d'appui sous tête (après noyage)
        if g["tete"] == "ISO 4762":
            tete = _tete_iso4762(d, appui, n)
            fut = cyl_entre(appui - n * 0.01, appui + n * g["L"], g["r_fut"])
        elif g["tete"] == "ISO 7380":
            dk, kk, _s = normes.ISO7380[d]
            tete = cone(dk / 2.0, dk * 0.3, kk, -n, appui)
            fut = cyl_entre(appui - n * 0.01, appui + n * g["L"], g["r_fut"])
        else:
            sommet = dos + n * 0.2               # tête fraisée affleurante (0,2 mm sous la surface)
            tete = _tete_fraisee(g["dk"], g["r_fut"] * 2.0, g["k"], sommet, n)
            fut = cyl_entre(sommet + n * (g["k"] - 0.01), sommet + n * g["L"], g["r_fut"])
        vis = union([tete, fut])
        art = article(g["designation"], g["norme"], d, g["L"], classe=g.get("classe"))
        r.quincaillerie.append(quincaillerie(f"{liaison['id']}_vis_{k + 1}", g["nom_vis"], vis,
                                             g["matiere_vis"], art, a.id, -n, liaison["id"],
                                             groupe=f"{liaison['id']}#{k + 1}", rang=1))
        if mode == "insert":
            Li, OD, logement = normes.INSERTS_CHAUD[d]
            debut = P + n * 0.0
            insert = cyl_entre(debut, debut + n * Li, logement / 2.0 - 0.02) - cyl_entre(
                debut - n * 1, debut + n * (Li + 1), g["r_fut"] + 0.03)
            art_i = article(f"insert fileté M{normes.format_mm(d)} (à chaud)", "insert à chaud", d, Li, od=OD)
            r.quincaillerie.append(quincaillerie(f"{liaison['id']}_insert_{k + 1}", f"insert M{d:g}", insert, "laiton",
                                                 art_i, b.id, -n, liaison["id"], groupe=f"{liaison['id']}#{k + 1}", rang=0))
    r.etapes.append(choix["etape"])
    r.interface = _resume_interface(itf)
    return r


def _diametre_vis(texte: Any) -> float | None:
    import re
    if isinstance(texte, (int, float)) and float(texte) in normes.FILETAGE:
        return float(texte)
    m = re.search(r"m\s*(\d+(?:[.,]\d)?)", str(texte or "").lower())
    if m:
        d = float(m.group(1).replace(",", "."))
        return d if d in normes.FILETAGE else None
    return None


def _essayer_vis(liaison, a: Piece, b: Piece, itf: Interface, d: float, mode: str, F: float,
                 existants: dict[str, Any] | None) -> dict[str, Any]:
    """Essaie un diamètre : rend le dimensionnement complet, ou la raison du refus."""
    n = itf.normale
    pa, pb = proc(a), proc(b)
    comp_a = pa["compensation_trou"]
    # 1. trous : passage dans A, trou récepteur dans B
    if mode == "bois":
        r_passage = (d + 0.5) / 2.0 + comp_a / 2.0
        dur = mat(b)["densite"] > 0.55 or b.matiere in ("mdf", "contreplaque")
        avant_trou = round(d * (0.7 if dur else 0.6) * 2) / 2
        r_trou_b = avant_trou / 2.0
    else:
        r_passage = normes.trou_passage(d, "moyen") / 2.0 + comp_a / 2.0
        if mode in ("taraudage", "filetage_existant"):
            r_trou_b = normes.FILETAGE[d][1] / 2.0
        elif mode == "autotaraudeuse":
            r_trou_b = 0.85 * d / 2.0 + pb["compensation_trou"] / 4.0
        else:
            if d not in normes.INSERTS_CHAUD:
                return {"ok": False, "raison": "pas d'insert à chaud de ce diamètre"}
            r_trou_b = normes.INSERTS_CHAUD[d][2] / 2.0
    # 2. tête, choisie sur l'épaisseur de A au centre de l'interface
    centre = itf.monde(*_centre(itf))
    ep_centre = profondeur(a.solide, centre, -n)
    paroi_sous_tete = max(pa["paroi_min"], 0.5 * d)
    k = 0.0
    if mode == "bois":
        dk = normes.DIN7997[d]
        k = (dk - d) / 2.0
        tete, norme, noyage, r_tete = "DIN 7997", "DIN 7997", 0.0, dk / 2.0 + 0.3
    else:
        k4762 = normes.ISO4762[d][1]
        if ep_centre >= k4762 + 0.4 + paroi_sous_tete:
            tete, norme, noyage = "ISO 4762", "ISO 4762", k4762 + 0.4
            dk = normes.ISO4762[d][0]
            r_tete = (normes.ISO4762[d][4] + 0.2 + comp_a) / 2.0
        elif d in normes.ISO10642 and ep_centre >= normes.ISO10642[d][1] + paroi_sous_tete:
            tete, norme, noyage = "ISO 10642", "ISO 10642", 0.0
            dk, k = normes.ISO10642[d][0], normes.ISO10642[d][1]
            r_tete = dk / 2.0 + 0.3
        elif d in normes.ISO7380:
            tete, norme, noyage = "ISO 7380", "ISO 7380", 0.0
            dk = normes.ISO7380[d][0]
            r_tete = dk / 2.0
        else:
            tete, norme, noyage = "ISO 4762", "ISO 4762", 0.0
            dk = normes.ISO4762[d][0]
            r_tete = dk / 2.0
    # 3. distances au bord : trou, tête noyée, bossage
    marge = max(r_passage + ligament_min(a, d), r_trou_b + ligament_min(b, d),
                (r_tete + 0.5 * pa["paroi_min"]) if noyage > 0 or k > 0 else 0.0)
    r_bossage = 0.0
    if itf.ecart > 1e-3:
        if b.origine != "fabrique":
            return {"ok": False, "raison": f"{b.nom} est acheté : on ne peut pas y ajouter de bossage"}
        r_bossage = r_trou_b + max(pb["paroi_min"] * 1.3, 0.6 * d)
        marge = max(marge, r_bossage + 0.5)
    motif_a = a.trous_existants if a.origine == "achete" else None
    renfort = None
    if existants or motif_a:
        porteur = b if existants else a
        points = _points_motif(existants or motif_a, itf, porteur)
        if not points:
            return {"ok": False, "raison": "motif de trous existants illisible"}
        nombre = len(points)
        region = None
        if existants:
            # le motif est imposé par le composant : la pièce fabriquée doit l'entourer de matière
            from shapely.geometry import Point
            besoin = r_passage + ligament_min(a, d)
            face_a = itf.face_a if itf.face_a is not None else itf.polygone
            if any(not face_a.buffer(-besoin + 0.05).contains(Point(q)) for q in points):
                if a.origine != "fabrique":
                    return {"ok": False, "raison": f"le motif de {b.nom} déborde de {a.nom}, qui n'est pas modifiable"}
                centre_m = np.mean(np.array(points), axis=0)
                rayon = max(math.dist(q, centre_m) for q in points) + besoin + 1.0
                renfort = (tuple(centre_m), rayon)
    elif a.origine == "achete":
        # composant sans motif déclaré (carte, module) : une vis à chaque coin, à vérifier sur la pièce réelle
        region = itf.polygone.buffer(-(marge - 0.05))
        if region.is_empty:
            return {"ok": False, "raison": f"{a.nom} trop petit pour des trous de fixation M{d:g}"}
        rect = region.minimum_rotated_rectangle
        coins = list(rect.exterior.coords)[:4] if rect.geom_type == "Polygon" else []
        points = [(float(x), float(y)) for x, y in coins] if len(coins) == 4 and region.area > 1.0 else repartir(region, 2)
        nombre = len(points)
    else:
        region = itf.polygone.buffer(-(marge - 0.05))
        if region.is_empty:
            return {"ok": False, "raison": f"interface trop étroite ({marge:.1f} mm du bord exigés)"}
        region = restreindre_bord(region, itf, liaison.get("bord"), max(3 * marge, 15.0))
        region = retirer_exclusions(region, itf, liaison, marge)
        if region.is_empty:
            return {"ok": False, "raison": "interface déjà occupée par d'autres fixations"}
        L_utile = longueur_utile(region) + 2 * marge
        espacement = min(160.0, max(40.0, 25.0 * d))
        nombre = int(liaison.get("nombre") or max(2 if L_utile >= 4 * marge else 1, math.ceil(L_utile / espacement)))
        points = repartir(region, nombre)
    # 4. profondeurs réelles aux points retenus (sous un renfort : épaisseur de A au centre du motif)
    if renfort is not None:
        ep_a = profondeur(a.solide, itf.monde(*renfort[0]), -n)
    else:
        ep_a = min(profondeur(a.solide, itf.monde(u, v), -n) for u, v in points)
    ep_b = min(profondeur(b.solide, itf.monde(u, v, itf.ecart), n) for u, v in points)
    if ep_a < noyage + paroi_sous_tete * (1.0 if noyage else 0.0) + 0.2:
        return {"ok": False, "raison": f"{a.nom} trop mince sous la tête ({ep_a:.1f} mm)"}
    disponible_b = ep_b + itf.ecart
    if mode == "bois":
        e_min, e_cible = 3.0 * d, 5.0 * d
        e_max = disponible_b - max(2.0, pb["paroi_min"] * 0.5)
    elif mode == "insert":
        Li = normes.INSERTS_CHAUD[d][0]
        if disponible_b < Li + pb["paroi_min"]:
            return {"ok": False, "raison": f"{b.nom} trop mince pour un insert de {Li} mm"}
        e_min, e_cible, e_max = 0.8 * Li, Li, Li + 0.8
    elif mode == "autotaraudeuse":
        e_min, e_cible = 2.0 * d, 2.5 * d
        e_max = disponible_b - pb["paroi_min"]
    elif mode == "taraudage":
        coef = 1.5 if b.matiere == "aluminium" else 1.0
        e_min, e_cible = coef * d, coef * d + 2 * normes.FILETAGE[d][0]
        e_max = disponible_b - pb["paroi_min"]
    else:
        declare = existants.get("profondeur_mm")
        e_max = float(declare) if isinstance(declare, (int, float)) and declare > 0 else 1.5 * d
        e_min, e_cible = min(1.0 * d, e_max), min(1.5 * d, e_max)
    if e_max < e_min:
        return {"ok": False, "raison": f"{b.nom} n'offre que {disponible_b:.1f} mm pour le filet (≥ {e_min:.1f} mm requis)"}
    # 5. longueur normalisée (une vis fraisée se mesure tête comprise)
    prise = ep_a - 0.2 if tete in ("ISO 10642", "DIN 7997") else ep_a - noyage
    if mode == "bois":
        serie, plage = normes.SERIE_VIS_BOIS, None
    else:
        serie, plage = normes.SERIE_LONGUEURS, normes.PLAGE_LONGUEURS[norme].get(d)
    L = normes.longueur_normalisee(serie, prise + e_cible, prise + e_max, plage) or \
        normes.longueur_normalisee(serie, prise + e_min, prise + e_max, plage)
    if L is None:
        return {"ok": False, "raison": f"aucune longueur de la série entre {prise + e_min:.1f} et {prise + e_max:.1f} mm"}
    engagement = L - prise
    # 6. capacité par vis (estimations de conception, coefficients explicites)
    if mode == "bois":
        cap, methode = normes.arrachement_bois(d, engagement, mat(b)["densite"]) / 2.0, "EN 1995 éq. 8.40a (Rk / 2)"
    elif mode == "insert":
        OD, Li = normes.INSERTS_CHAUD[d][1], normes.INSERTS_CHAUD[d][0]
        tau = normes.resistance_effective(b.matiere, b.procede, "cisaillement")
        cap, methode = normes.arrachement_plastique(OD, Li, tau) / 2.5, "cisaillement du plastique autour de l'insert (/ 2,5)"
    elif mode == "autotaraudeuse":
        tau = normes.resistance_effective(b.matiere, b.procede, "cisaillement")
        cap, methode = normes.arrachement_plastique(d, engagement, tau) / 2.5, "cisaillement du filet formé (/ 2,5)"
    else:
        tau = normes.resistance_effective(b.matiere, b.procede, "cisaillement") if b.origine != "achete" else 100.0
        cap = min(normes.capacite_traction_vis(d, "8.8"), normes.arrachement_plastique(d, engagement, tau)) / 2.0
        methode = "min(charge d'épreuve 8.8, arrachement du filet) / 2"
    if not existants:
        while nombre * cap < F and nombre < 16:
            nombre += 1
            points = repartir(region, nombre)
        if nombre * cap < F:
            return {"ok": False, "raison": f"capacité {cap:.0f} N par vis insuffisante pour {F:.0f} N"}
        for i in range(len(points)):
            for j in range(i + 1, len(points)):
                if math.dist(points[i], points[j]) < 2 * marge:
                    return {"ok": False, "raison": "vis trop rapprochées pour cette interface"}
    classe = "8.8" if mode != "bois" else "acier zingué"
    if mode == "bois":
        designation = f"vis à bois tête fraisée Ø{normes.format_mm(d)}×{L} (DIN 7997)"
        nom_vis = f"vis à bois {normes.format_mm(d)}×{L}"
        r_fut = min(normes.NOYAU_VIS_BOIS * d, r_trou_b * 2.0 - 0.04) / 2.0
    else:
        designation = normes.designation_vis(norme, d, L, classe)
        nom_vis = f"vis M{normes.format_mm(d)}×{L}"
        r_fut = min(normes.diametre_noyau(d), r_trou_b * 2.0 - 0.04) / 2.0
    marge_fond = 2.0 if mode == "bois" else 1.0
    if mode == "filetage_existant":
        prof_trou = itf.ecart + e_max
    else:
        prof_trou = itf.ecart + min(e_max, engagement + marge_fond)
    justification = {
        "bois": f"{b.nom} est en {mat(b)['nom']} : vis à bois avec avant-trou Ø{2 * r_trou_b:.1f} mm, tête fraisée affleurante",
        "insert": f"{b.nom} est imprimé et la liaison est démontable : insert laiton posé à chaud, la vis ne s'use pas dans le plastique",
        "autotaraudeuse": f"{b.nom} est en {mat(b)['nom']} : vis qui forme son filet dans un avant-trou Ø{2 * r_trou_b:.2f} mm",
        "taraudage": f"{b.nom} est en {mat(b)['nom']} : trou taraudé M{d:g} (perçage Ø{2 * r_trou_b:.2f} mm)",
        "filetage_existant": f"{b.nom} est un composant acheté avec ses trous taraudés : filet engagé de {engagement:.1f} mm au plus {e_max:.1f} mm",
    }[mode]
    resume = f"{nombre} × {designation}" + (f" + insert M{d:g}" if mode == "insert" else "")
    etape = (f"Fixer {a.nom} sur {b.nom} : {nombre} × {designation}"
             + (f", inserts M{d:g} posés à chaud dans {b.nom} au préalable" if mode == "insert" else "")
             + (f", avant-trous Ø{2 * r_trou_b:.1f} mm" if mode in ("bois", "autotaraudeuse") else "")
             + (f", taraudage M{d:g}" if mode == "taraudage" else "") + ".")
    if renfort is not None:
        resume += f" ; platine de renfort Ø{2 * renfort[1]:.0f} mm sur {a.nom}"
    return {"ok": True, "points": points, "renfort": renfort, "ep_renfort": ep_a if renfort is not None else None,
            "degagement": (existants or {}).get("degagement_central_mm"), "r_passage": r_passage, "r_trou_b": r_trou_b, "r_lamage": r_tete,
            "r_bossage": r_bossage, "noyage": noyage, "tete": tete, "norme": norme, "dk": dk, "k": k, "L": L,
            "r_fut": r_fut, "prof_trou": prof_trou, "designation": designation, "nom_vis": nom_vis, "classe": classe,
            "matiere_vis": "acier_zingue", "resume": resume, "justification": justification, "etape": etape,
            "calculs": {"mode": mode, "diametre_mm": d, "longueur_mm": L, "nombre": nombre, "engagement_mm": round(engagement, 2),
                        "capacite_par_vis_N": round(cap, 1), "capacite_totale_N": round(cap * nombre, 1),
                        "methode_capacite": methode, "trou_passage_mm": round(2 * r_passage, 2),
                        "trou_recepteur_mm": round(2 * r_trou_b, 2), "tete": tete,
                        "marge_bord_mm": round(marge, 2), "bossage": itf.ecart > 1e-3}}


def _points_motif(existants: dict[str, Any], itf: Interface, b: Piece) -> list[tuple[float, float]]:
    """Trous existants d'un composant acheté (entraxe carré/rectangulaire ou cercle) dans le plan."""
    centre = np.asarray(b.centre, dtype=float)
    u0, v0 = itf.plan(centre)
    entraxe = existants.get("entraxe_mm")
    pts = []
    if isinstance(entraxe, (int, float)):
        entraxe = [float(entraxe), float(entraxe)]
    if isinstance(entraxe, list) and len(entraxe) == 2 and all(isinstance(x, (int, float)) and x > 0 for x in entraxe):
        a_, b_ = float(entraxe[0]) / 2.0, float(entraxe[1]) / 2.0
        pts = [(-a_, -b_), (a_, -b_), (a_, b_), (-a_, b_)]
    diam = existants.get("diametre_cercle_mm")
    if not pts and isinstance(diam, (int, float)) and diam > 0:
        nb = int(existants.get("nombre") or 4)
        pts = [(diam / 2 * math.cos(2 * math.pi * k / nb), diam / 2 * math.sin(2 * math.pi * k / nb)) for k in range(nb)]
    if not pts:
        return []
    # orientation du motif : celle qui laisse le plus de matière dans la pièce qui porte la tête
    from shapely.geometry import Point
    meilleur, score = None, -1e9
    for angle in (0.0, 45.0, 90.0, 22.5, 67.5):
        c, s = math.cos(math.radians(angle)), math.sin(math.radians(angle))
        cand = [(u0 + x * c - y * s, v0 + x * s + y * c) for x, y in pts]
        sc = min(itf.polygone.boundary.distance(Point(q)) if itf.polygone.contains(Point(q)) else -1.0 for q in cand)
        if sc > score:
            meilleur, score = cand, sc
    return meilleur


# --------------------------------------------------------------------------- boulon + écrou

def liaison_boulon(liaison: dict[str, Any], pile: list[Piece], pieces: dict[str, Piece]) -> Resultat:
    """Boulon traversant une pile de pièces (côté tête = première), écrou sur la dernière."""
    r = Resultat(liaison["id"], "boulon_ecrou", [p.id for p in pile])
    itfs = []
    for x, y in zip(pile, pile[1:]):
        itf = interface_principale(x, y)
        if itf is None or itf.ecart > 1e-3:
            raise ErreurConception(f"{liaison['id']} : {x.nom} et {y.nom} ne sont pas en contact")
        itfs.append(itf)
    n = itfs[0].normale
    if any(abs(float(i.normale @ n)) < 0.999 for i in itfs):
        raise ErreurConception(f"{liaison['id']} : les contacts de la pile ne sont pas parallèles")
    ref = itfs[0]
    # région commune dans le repère de la première interface
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    commun = ref.polygone
    for itf in itfs[1:]:
        polys = []
        for poly in getattr(itf.polygone, "geoms", [itf.polygone]):
            pts = [ref.plan(itf.monde(u, v)) for u, v in poly.exterior.coords]
            polys.append(Polygon(pts))
        commun = commun.intersection(unary_union(polys))
    if commun.is_empty:
        raise ErreurConception(f"{liaison['id']} : aucune zone commune à toute la pile")
    F, source_F = effort(liaison, *pile)
    tete_p, dernier = pile[0], pile[-1]
    achats = [p for p in pile if p.origine == "achete"]
    motif_achat = next((p for p in achats if p.trous_existants), None)
    if any(not p.trous_existants for p in achats):
        nom = next(p.nom for p in achats if not p.trous_existants)
        raise ErreurConception(f"{liaison['id']} : on ne perce pas un composant acheté ({nom}) sans trous de fixation déclarés")
    if motif_achat:
        r.trous_existants.update(p.id for p in achats)
    c0 = ref.monde(*_centre(ref))
    epaisseurs_c = [profondeur(tete_p.solide, c0, -n)]
    for p in pile[1:]:
        epaisseurs_c.append(profondeur(p.solide, c0 + n * sum(epaisseurs_c[1:]), n))
    t_min = max(1.0, min(epaisseurs_c))
    cible = min(12.0, max(2.5, min(t_min, 3.0 + 0.25 * t_min)))
    serie = [x for x in normes.DIAMETRES if x >= 2.0]
    for d in [x for x in serie if x >= cible - 1e-9] + sorted([x for x in serie if x < cible - 1e-9], reverse=True):
        r_pass = max(normes.trou_passage(d, "moyen") / 2.0 + proc(p)["compensation_trou"] / 2.0 for p in pile)
        marge = r_pass + max(ligament_min(p, d) for p in pile)
        s_ecrou, m_ecrou = normes.ISO4032[d]
        marge = max(marge, s_ecrou / math.sqrt(3) + 0.6)
        region = commun.buffer(-(marge - 0.05))
        if region.is_empty:
            continue
        region = restreindre_bord(region, ref, liaison.get("bord"), max(3 * marge, 15.0))
        region = retirer_exclusions(region, ref, liaison, marge)
        if region.is_empty:
            continue
        if motif_achat:
            if _diametre_vis(motif_achat.trous_existants.get("vis")) not in (None, d):
                continue
            pts = _points_motif(motif_achat.trous_existants, ref, motif_achat)
            nombre = len(pts)
        L_utile = longueur_utile(region) + 2 * marge
        nombre = liaison.get("nombre") or max(2 if L_utile >= 4 * marge else 1, math.ceil(L_utile / min(160.0, max(40.0, 25.0 * d))))
        cap = normes.capacite_traction_vis(d, "8.8") / 2.0
        appui_mou = [p for p in pile if famille(p) in ("bois", "polymere")]
        if appui_mou:
            sigma = min(normes.resistance_effective(p.matiere, p.procede) for p in appui_mou)
            d1, d2, _h = normes.ISO7089[d]
            cap = min(cap, math.pi / 4 * (d2 * d2 - d1 * d1) * sigma / 2.0)
        if not motif_achat:
            while nombre * cap < F and nombre < 16:
                nombre += 1
            pts = repartir(region, int(nombre))
        if len(pts) < nombre or any(math.dist(pts[i], pts[j]) < 2 * marge for i in range(len(pts)) for j in range(i + 1, len(pts))):
            continue
        epaisseurs = []
        for u, v in pts:
            P = ref.monde(u, v)
            ep0 = profondeur(tete_p.solide, P, -n)
            total = ep0
            for p in pile[1:]:
                total += profondeur(p.solide, P + n * (total - ep0), n)
            epaisseurs.append((ep0, total))
        ep_tete, total = min(e[0] for e in epaisseurs), max(e[1] for e in epaisseurs)
        k = normes.ISO4762[d][1]
        noyage = k + 0.4 if ep_tete >= k + 0.4 + max(proc(tete_p)["paroi_min"], 0.5 * d) else 0.0
        rondelle_tete = noyage == 0.0 and famille(tete_p) in ("bois", "polymere")
        ep_dernier = profondeur(dernier.solide, ref.monde(*pts[0]) + n * (total - ep_tete) - n * 1e-3, -n)
        piege = proc(dernier)["imprime"] and ep_dernier >= m_ecrou + 0.3 + proc(dernier)["paroi_min"]
        d1, d2, h_r = normes.ISO7089[d]
        prise = total - noyage + (h_r if rondelle_tete else 0.0)
        besoin = prise + (0.0 if piege else h_r + m_ecrou) + 2 * normes.FILETAGE[d][0]
        if piege:
            besoin = total - noyage - 0.3 + 2 * normes.FILETAGE[d][0]
        plage = normes.PLAGE_LONGUEURS["ISO 4762"].get(d)
        L = normes.longueur_normalisee(normes.SERIE_LONGUEURS, besoin, besoin + 1.2 * d + 6, plage)
        if L is None:
            continue
        break
    else:
        raise ErreurConception(f"{liaison['id']} : aucun boulon ne tient dans la zone commune de la pile")
    designation = normes.designation_vis("ISO 4762", d, L, "8.8")
    for i, (u, v) in enumerate(pts):
        P = ref.monde(u, v)
        dos = P - n * profondeur(tete_p.solide, P, -n)
        bout = dos + n * total
        for p in pile:
            r.retirer(p.id, cyl_entre(dos - n * 1.0, bout + n * 1.0, r_pass))
            r.trous.append({"piece": p.id, "centre": P.tolist(), "axe": n.tolist(), "rayon": r_pass, "liaison": liaison["id"],
                            "traversant": True})
        if noyage:
            r.retirer(tete_p.id, cyl_entre(dos - n, dos + n * noyage, (normes.ISO4762[d][4] + 0.2) / 2.0))
        appui = dos + n * noyage
        hardware = []
        if rondelle_tete:
            rond = cyl_entre(dos - n * h_r, dos, d2 / 2.0) - cyl_entre(dos - n * (h_r + 1), dos + n, d1 / 2.0)
            hardware.append(("rondelle_tete", rond, article(f"rondelle ISO 7089 – {normes.format_mm(d)}", "ISO 7089", d), -n, tete_p.id, 0))
            appui = dos - n * h_r
        vis = union([_tete_iso4762(d, appui, n), cyl_entre(appui - n * 0.01, appui + n * L, normes.diametre_noyau(d) / 2.0)])
        hardware.append(("vis", vis, article(designation, "ISO 4762", d, L, classe="8.8"), -n, tete_p.id, 1))
        s, m = normes.ISO4032[d]
        if piege:
            fond_piege = bout - n * 0.3
            r.retirer(dernier.id, prisme_hexagonal(s + 0.3, m + 0.6, n, fond_piege - n * (m / 2.0) + n * 0.3))
            r.retirer(dernier.id, prisme_hexagonal(s + 0.3, 2.0, n, bout + n * 0.9))
            ecrou_c = fond_piege - n * (m / 2.0)
        else:
            rond = cyl_entre(bout, bout + n * h_r, d2 / 2.0) - cyl_entre(bout - n, bout + n * (h_r + 1), d1 / 2.0)
            hardware.append(("rondelle", rond, article(f"rondelle ISO 7089 – {normes.format_mm(d)}", "ISO 7089", d), n, dernier.id, 2))
            ecrou_c = bout + n * (h_r + m / 2.0)
        ecrou = prisme_hexagonal(s, m, n, ecrou_c) - cyl_entre(ecrou_c - n * m, ecrou_c + n * m, d / 2.0)
        hardware.append(("ecrou", ecrou, article(f"écrou hexagonal ISO 4032 – M{normes.format_mm(d)} – 8", "ISO 4032", d), n, dernier.id, 3))
        for nom, solide, art, approche, hote, rang in hardware:
            r.quincaillerie.append(quincaillerie(f"{liaison['id']}_{nom}_{i + 1}", f"{nom.split('_')[0]} M{d:g}", solide,
                                                 "acier_zingue", art, hote, approche, liaison["id"],
                                                 groupe=f"{liaison['id']}#{i + 1}", rang=rang))
    r.calculs.update({"effort_N": round(F, 1), "source_effort": source_F, "diametre_mm": d, "longueur_mm": L,
                      "nombre": len(pts), "capacite_par_boulon_N": round(cap, 1),
                      "methode_capacite": "min(charge d'épreuve 8.8, matage sous rondelle) / 2",
                      "ecrou_noye": piege, "epaisseur_serree_mm": round(total, 2)})
    r.decisions.append({"sujet": liaison["id"], "decision": f"{len(pts)} × {designation} + écrous ISO 4032",
                        "raison": "pile traversée de part en part : boulon et écrou"
                                  + (" logé dans une empreinte hexagonale imprimée" if piege else " sur rondelle")})
    r.etapes.append(f"Boulonner {' / '.join(p.nom for p in pile)} : {len(pts)} × {designation}, écrous M{d:g}"
                    + (" glissés dans leurs empreintes" if piege else " sur rondelles") + ".")
    r.interface = _resume_interface(ref)
    return r


# --------------------------------------------------------------------------- emmanchement (tourillons, goupilles)

def liaison_emmanchement(liaison: dict[str, Any], a: Piece, b: Piece, itf: Interface, pieces: dict[str, Piece]) -> Resultat:
    """Goupilles ou tourillons perpendiculaires à l'interface, à cheval sur les deux pièces."""
    r = Resultat(liaison["id"], "emmanchement", [a.id, b.id])
    n = itf.normale
    bois = famille(a) == "bois" and famille(b) == "bois"
    serrage = 0.0 if bois else max(proc(a)["serrage"], proc(b)["serrage"])
    F, source_F = effort(liaison, a, b)
    if bois:
        candidats = sorted({d for d, _ in normes.DIN68150}, reverse=True)
    else:
        candidats = sorted(normes.ISO2338, reverse=True)
    raisons = []
    for d in candidats:
        marge = d / 2.0 + max(ligament_min(a, d) if not bois else proc(a)["paroi_min"],
                              ligament_min(b, d) if not bois else proc(b)["paroi_min"])
        region = itf.polygone.buffer(-(marge - 0.05))
        region = retirer_exclusions(region, itf, liaison, marge) if not region.is_empty else region
        if region.is_empty:
            raisons.append(f"Ø{d:g} : interface trop étroite")
            continue
        L_utile = longueur_utile(region) + 2 * marge
        nombre = liaison.get("nombre") or max(2 if L_utile >= 3 * marge else 1, math.ceil(L_utile / (120.0 if bois else 60.0)))
        pts = repartir(region, int(nombre))
        if any(math.dist(pts[i], pts[j]) < 2 * marge for i in range(len(pts)) for j in range(i + 1, len(pts))):
            nombre = 1
            pts = repartir(region, 1)
        ep_a = min(profondeur(a.solide, itf.monde(u, v), -n) for u, v in pts)
        ep_b = min(profondeur(b.solide, itf.monde(u, v), n) for u, v in pts)
        max_a = ep_a - (proc(a)["paroi_min"] if ep_a < 4 * d else 0.0) - 1.0
        max_b = ep_b - (proc(b)["paroi_min"] if ep_b < 4 * d else 0.0) - 1.0
        if bois:
            longueurs = sorted(L for dd, L in normes.DIN68150 if dd == d)
        else:
            lo, hi = normes.ISO2338[d]
            longueurs = [L for L in normes.SERIE_GOUPILLES if lo <= L <= hi]
        choix = None
        e_min = 1.2 * d                          # enfoncement minimal de chaque côté
        for L in sorted(longueurs, reverse=True):
            e_b = min(max_b, L - e_min)
            e_a = L - e_b
            if e_a > max_a:
                e_a = max_a
                e_b = L - e_a
            if e_b >= e_min and e_a >= e_min and e_a <= max_a + 1e-9 and e_b <= max_b + 1e-9:
                choix = (L, e_a, e_b)
                break
        if choix is None:
            raisons.append(f"Ø{d:g} : profondeurs {ep_a:.1f}/{ep_b:.1f} mm insuffisantes")
            continue
        break
    else:
        raise ErreurConception(f"{liaison['id']} : aucun tourillon ni goupille ne convient ({' ; '.join(raisons[-3:])})")
    L, e_a, e_b = choix
    trou = d - serrage
    for k, (u, v) in enumerate(pts):
        P = itf.monde(u, v)
        r.retirer(a.id, cyl_entre(P + n * 0.5, P - n * (e_a + 1.0), trou / 2.0))
        r.retirer(b.id, cyl_entre(P - n * 0.5, P + n * (e_b + 1.0), trou / 2.0))
        r.trous.append({"piece": a.id, "centre": P.tolist(), "axe": (-n).tolist(), "rayon": trou / 2.0, "de": 0.0,
                        "a": e_a + 1.0, "liaison": liaison["id"]})
        r.trous.append({"piece": b.id, "centre": P.tolist(), "axe": n.tolist(), "rayon": trou / 2.0, "de": 0.0,
                        "a": e_b + 1.0, "liaison": liaison["id"]})
        rayon_cheville = d / 2.0 - (0.02 if serrage == 0 else 0.0)
        cheville = cyl_entre(P - n * e_a, P + n * e_b, rayon_cheville)
        if bois:
            art = article(f"tourillon hêtre cannelé Ø{d:g}×{L} (DIN 68150)", "DIN 68150", d, L)
            nom, matiere_ = f"tourillon {d:g}×{L}", "hetre"
        else:
            art = article(f"goupille cylindrique ISO 2338 – {normes.format_mm(d)} m6 × {L} – acier", "ISO 2338", d, L)
            nom, matiere_ = f"goupille {d:g}×{L}", "acier"
        hote = a.id
        r.quincaillerie.append(quincaillerie(f"{liaison['id']}_{'tourillon' if bois else 'goupille'}_{k + 1}", nom, cheville,
                                             matiere_, art, hote, n, liaison["id"]))
        if serrage > 0:
            for p, e in ((a, e_a), (b, e_b)):
                r.interferences.append({"pieces": [f"{liaison['id']}_goupille_{k + 1}", p.id], "nature": "serrage",
                                        "volume_attendu_mm3": math.pi * d * (serrage / 2.0) * e,
                                        "liaison": liaison["id"]})
    tau = 4.0 if bois else min(normes.resistance_effective(p.matiere, p.procede, "cisaillement") for p in (a, b))
    cap = math.pi * d * min(e_a, e_b) * tau * (0.5 if bois else 0.3) / 2.0
    r.calculs.update({"effort_N": round(F, 1), "source_effort": source_F, "diametre_mm": d, "longueur_mm": L,
                      "nombre": len(pts), "enfoncement_mm": [round(e_a, 2), round(e_b, 2)],
                      "serrage_diametral_mm": serrage, "trou_mm": round(trou, 3),
                      "capacite_estimee_N": round(cap * len(pts), 1)})
    r.decisions.append({"sujet": liaison["id"], "decision": f"{len(pts)} × {'tourillon' if bois else 'goupille'} Ø{d:g}×{L}",
                        "raison": ("bois sur bois : tourillons collés, trous au diamètre nominal (le hêtre gonfle à la colle)"
                                   if bois else f"ajustement serré de {serrage:.2f} mm au diamètre ({normes.PROCEDES[a.procede]['nom']})")})
    # Les goupilles posées dans A imposent l'approche de B selon leur axe.
    # `approche` : direction d'où arrive la pièce (elle part de +D·approche et rejoint sa place).
    r.contraintes.append({"piece": b.id, "par_rapport_a": a.id, "approche": n.tolist(), "exacte": True})
    r.contraintes.append({"piece": a.id, "par_rapport_a": b.id, "approche": (-n).tolist(), "exacte": True})
    r.etapes.append(f"Emmancher {len(pts)} {'tourillons' if bois else 'goupilles'} Ø{d:g}×{L} entre {a.nom} et {b.nom}"
                    + (" (encollés)" if bois else " à la presse") + ".")
    r.interface = _resume_interface(itf)
    return r


# --------------------------------------------------------------------------- colle

ADHESIFS = {
    ("bois", "bois"): ("colle vinylique D3", 3.0),
    ("polymere", "polymere"): ("époxy bicomposant", 5.0),
    ("metal", "metal"): ("époxy structurale", 15.0),
}


def liaison_colle(liaison: dict[str, Any], a: Piece, b: Piece, itf: Interface, pieces: dict[str, Piece]) -> Resultat:
    r = Resultat(liaison["id"], "colle", [a.id, b.id])
    fa, fb = famille(a), famille(b)
    nom, tau = ADHESIFS.get((fa, fb)) or ADHESIFS.get((fb, fa)) or ("époxy bicomposant", 5.0)
    tau = min(tau, normes.resistance_effective(a.matiere, a.procede, "cisaillement"),
              normes.resistance_effective(b.matiere, b.procede, "cisaillement"))
    F, source_F = effort(liaison, a, b)
    if itf.ecart > 0.5:
        raise ErreurConception(f"{liaison['id']} : on ne colle pas deux faces écartées de {itf.ecart:.1f} mm")
    aire = itf.aire
    capacite = aire * tau / 3.0
    r.calculs.update({"adhesif": nom, "aire_collee_mm2": round(aire, 1), "cisaillement_retenu_MPa": tau,
                      "capacite_estimee_N": round(capacite, 1), "effort_N": round(F, 1), "source_effort": source_F,
                      "coefficient_securite": 3.0})
    if capacite < F:
        r.decisions.append({"sujet": liaison["id"], "decision": "collage seul insuffisant",
                            "raison": f"{capacite:.0f} N < {F:.0f} N : prévoir une fixation mécanique en plus"})
    r.decisions.append({"sujet": liaison["id"], "decision": f"collage {nom} sur {aire:.0f} mm²",
                        "raison": "surface d'appui mesurée sur l'interface des deux pièces"})
    r.etapes.append(f"Encoller l'interface {a.nom} / {b.nom} ({nom}, {aire:.0f} mm²), presser jusqu'à la prise.")
    r.interface = _resume_interface(itf)
    return r


# --------------------------------------------------------------------------- soudure

def liaison_soudure(liaison: dict[str, Any], a: Piece, b: Piece, itf: Interface, pieces: dict[str, Piece]) -> Resultat:
    """Cordons d'angle le long des arêtes rentrantes de l'interface (A porte, B posé dessus)."""
    from shapely.geometry import Point
    r = Resultat(liaison["id"], "soudure", [a.id, b.id])
    fa, fb = mat(a).get("soudage"), mat(b).get("soudage")
    if not fa or fa != fb:
        raise ErreurConception(f"{liaison['id']} : {mat(a)['nom']} et {mat(b)['nom']} ne se soudent pas ensemble")
    if itf.ecart > 0.3:
        raise ErreurConception(f"{liaison['id']} : les pièces ne se touchent pas")
    n = itf.normale
    t_min = min(profondeur(a.solide, itf.monde(*_centre(itf)), -n), profondeur(b.solide, itf.monde(*_centre(itf)), n))
    gorge = min(0.7 * t_min, max(3.0, 0.5 * t_min)) if t_min >= 4 else 0.7 * t_min
    cote = gorge * math.sqrt(2.0)
    face_a = itf.face_a
    lignes = []
    for poly in getattr(itf.polygone, "geoms", [itf.polygone]):
        coords = list(poly.exterior.coords)
        oriente = 1.0 if poly.exterior.is_ccw else -1.0
        for (x0, y0), (x1, y1) in zip(coords, coords[1:]):
            seg = np.array([x1 - x0, y1 - y0])
            L = float(np.linalg.norm(seg))
            if L < 2 * cote:
                continue
            t = seg / L
            dehors = np.array([t[1], -t[0]]) * oriente      # normale sortante (contour anti-horaire)
            milieu = np.array([(x0 + x1) / 2, (y0 + y1) / 2])
            test = milieu + dehors * (cote * 0.5 + 0.05)
            if face_a.contains(Point(*test)) and not itf.face_b.contains(Point(*test)):
                lignes.append((np.array([x0, y0]), np.array([x1, y1]), dehors))
    if not lignes:
        raise ErreurConception(f"{liaison['id']} : aucune arête rentrante à souder (pièces bout à bout : chanfreiner en V)")
    longueur = 0.0
    for k, (p0, p1, dehors) in enumerate(lignes):
        P0, P1 = itf.monde(*p0), itf.monde(*p1)
        axe = (P1 - P0) / np.linalg.norm(P1 - P0)
        o = itf.e1 * dehors[0] + itf.e2 * dehors[1]
        # profil triangulaire (o, n) extrudé le long de l'arête
        M = np.eye(4)
        M[:3, 0], M[:3, 1], M[:3, 2], M[:3, 3] = o, n, axe, P0
        if np.linalg.det(M[:3, :3]) < 0:
            M[:3, 0] = -o
            profil = [(0.0, 0.0), (-cote, 0.0), (0.0, cote)]
        else:
            profil = [(0.0, 0.0), (cote, 0.0), (0.0, cote)]
        L = float(np.linalg.norm(P1 - P0))
        cordon = extrusion_profil(profil, L, M)
        longueur += L
        r.quincaillerie.append(quincaillerie(f"{liaison['id']}_cordon_{k + 1}", f"cordon de soudure a{gorge:.1f}",
                                             cordon, a.matiere, article(f"cordon d'angle a = {gorge:.1f} mm, L = {L:.0f} mm",
                                                                         "cordon de soudure", gorge, L),
                                             a.id, n, liaison["id"], origine="procede"))
    fu = {"acier": 360.0, "inox": 520.0, "aluminium": 180.0}.get(fa, 300.0)
    f_vw = fu / (math.sqrt(3) * 0.8 * 1.25)
    cap = gorge * longueur * f_vw
    F, source_F = effort(liaison, a, b)
    r.calculs.update({"gorge_mm": round(gorge, 2), "longueur_cordons_mm": round(longueur, 1), "f_vw_MPa": round(f_vw, 1),
                      "capacite_estimee_N": round(cap, 0), "methode": "EN 1993-1-8 méthode simplifiée",
                      "effort_N": round(F, 1), "source_effort": source_F})
    r.decisions.append({"sujet": liaison["id"], "decision": f"{len(lignes)} cordon(s) d'angle a{gorge:.1f}",
                        "raison": f"même famille soudable ({fa}) ; gorge ≈ 0,7 × épaisseur la plus mince ({t_min:.1f} mm)"})
    r.etapes.append(f"Pointer puis souder {b.nom} sur {a.nom} : cordons d'angle a{gorge:.1f} sur {longueur:.0f} mm.")
    r.interface = _resume_interface(itf)
    return r


def _centre(itf: Interface) -> tuple[float, float]:
    q = itf.polygone.representative_point()
    return q.x, q.y


# --------------------------------------------------------------------------- queue d'aronde

def liaison_queue_aronde(liaison: dict[str, Any], parent: Piece, enfant: Piece, itf: Interface,
                         pieces: dict[str, Piece]) -> Resultat:
    """Tenon trapézoïdal sur l'enfant (normale de l'interface : parent → enfant), rainure dans le parent."""
    r = Resultat(liaison["id"], "queue_aronde", [parent.id, enfant.id])
    if itf.ecart > 1e-3:
        raise ErreurConception(f"{liaison['id']} : pièces non jointives")
    jeu = proc(parent)["queue_aronde"]
    if jeu is None:
        raise ErreurConception(f"{liaison['id']} : la queue d'aronde ne se fait pas en {normes.PROCEDES[parent.procede]['nom']}")
    n = itf.normale          # du parent vers l'enfant
    rect = itf.polygone.minimum_rotated_rectangle
    c = np.array(rect.exterior.coords[:4])
    a1, a2 = c[1] - c[0], c[2] - c[1]
    long_, court = (a1, a2) if np.linalg.norm(a1) >= np.linalg.norm(a2) else (a2, a1)
    s2 = long_ / np.linalg.norm(long_)
    largeur = float(np.linalg.norm(court))
    longueur = float(np.linalg.norm(long_))
    centre2 = c.mean(axis=0)
    s = itf.e1 * s2[0] + itf.e2 * s2[1]                  # direction de glissement
    t = np.cross(n, s)                                   # travers
    ep_parent = profondeur(parent.solide, itf.monde(*centre2), -n)
    if famille(parent) == "bois":
        alpha = math.degrees(math.atan(1 / 8.0)) if mat(parent)["densite"] > 0.6 else math.degrees(math.atan(1 / 6.0))
    else:
        alpha = 15.0
    paroi = proc(parent)["paroi_min"]
    h = min(ep_parent / 3.0, 0.45 * largeur)
    w_racine = 0.5 * largeur
    w_tete = w_racine + 2 * h * math.tan(math.radians(alpha))
    lig = (largeur - w_tete) / 2.0 - jeu
    if h < 1.5 * proc(parent)["detail_min"] or ep_parent - h < paroi or lig < proc(enfant)["paroi_min"] * 0.5:
        raise ErreurConception(f"{liaison['id']} : queue d'aronde impossible ({largeur:.1f} × {ep_parent:.1f} mm disponibles)")
    O = itf.monde(*centre2) - s * (longueur / 2.0)
    M = np.eye(4)
    M[:3, 0], M[:3, 1], M[:3, 2], M[:3, 3] = t, -n, s, O
    if np.linalg.det(M[:3, :3]) < 0:
        M[:3, 0] = -t
    # profil (travers, profondeur dans le parent) ; profondeur 0 = interface
    tenon = [(-w_racine / 2, -0.02), (w_racine / 2, -0.02), (w_tete / 2, h), (-w_tete / 2, h)]
    rainure = [(-w_racine / 2 - jeu, -0.5), (w_racine / 2 + jeu, -0.5), (w_tete / 2 + jeu, h + jeu), (-w_tete / 2 - jeu, h + jeu)]
    M_r = M.copy()
    M_r[:3, 3] = O - s * 1.0
    r.ajouter(enfant.id, extrusion_profil(tenon, longueur, M))
    r.retirer(parent.id, extrusion_profil(rainure, longueur + 2.0, M_r))
    r.contraintes.append({"piece": enfant.id, "par_rapport_a": parent.id, "glissement": s.tolist(), "exacte": True})
    r.calculs.update({"angle_deg": round(alpha, 2), "profondeur_mm": round(h, 2), "largeur_racine_mm": round(w_racine, 2),
                      "largeur_tete_mm": round(w_tete, 2), "jeu_par_flanc_mm": jeu, "longueur_mm": round(longueur, 1)})
    r.decisions.append({"sujet": liaison["id"], "decision": f"queue d'aronde glissée {alpha:.1f}°, profondeur {h:.1f} mm",
                        "raison": ("pente 1:8 (bois dur)" if alpha < 8 else "pente 1:6 (résineux)" if alpha < 12 else "pente 15° (pièce non bois)")})
    r.etapes.append(f"Glisser {enfant.nom} dans la rainure en queue d'aronde de {parent.nom}.")
    r.interface = _resume_interface(itf)
    return r


# --------------------------------------------------------------------------- aimants

def _taquet_aimants(liaison, a: Piece, b: Piece, itf: Interface, F: float, jeu_poche: float, retrait: float):
    """Élargit localement la pièce fabriquée la plus étroite (taquet collé côté intérieur) pour un aimant.

    Le côté intérieur est celui où l'autre pièce continue au-delà de l'interface (un couvercle qui
    couvre toute la caisse) ; le taquet affleure la face de contact et descend sous elle.
    """
    rect = itf.polygone.minimum_rotated_rectangle
    if rect.geom_type != "Polygon":
        return None
    c = np.array(rect.exterior.coords[:4])
    a1, a2 = c[1] - c[0], c[2] - c[1]
    long_, court = (a1, a2) if np.linalg.norm(a1) >= np.linalg.norm(a2) else (a2, a1)
    largeur = float(np.linalg.norm(court))
    w = court / largeur
    t = long_ / np.linalg.norm(long_)
    centre2 = c.mean(axis=0)
    cibles = []
    for porteur, autre_face, sens in ((b, itf.face_a, 1.0), (a, itf.face_b, -1.0)):
        if porteur.origine != "fabrique" or autre_face is None:
            continue
        g = np.array(autre_face.centroid.coords[0])
        dedans = w if float((g - centre2) @ w) >= 0 else -w
        cibles.append((porteur, dedans, sens))
    for porteur, dedans, sens in cibles:
        paroi = max(proc(porteur)["paroi_min"], 2.0)
        candidats = []
        for d, h in normes.AIMANTS:
            f_paire = normes.force_aimants(d, h, 2 * retrait + itf.ecart)
            nombre = max(2 if longueur_utile(itf.polygone) > 6 * d else 1, math.ceil(2.0 * F / f_paire))
            if nombre <= 4:
                candidats.append((nombre, d * d * h, d, h, f_paire))
        # le moins d'aimants possible, puis le plus petit qui suffit
        for nombre, _, d, h, f_paire in sorted(candidats):
            centre_bord = restreindre_bord(itf.polygone, itf, liaison.get("bord"), largeur + 1.0)
            lignes = repartir(centre_bord.buffer(-0.01) if not centre_bord.is_empty else itf.polygone, nombre)
            pts = []
            for q in lignes:
                q = np.array(q)
                axe_long = float((q - centre2) @ t)
                pts.append(tuple(centre2 + t * axe_long + dedans * (largeur / 2.0 + d / 2.0 + jeu_poche - paroi * 0.25)))
            # l'aimant de l'autre pièce doit tenir dans son épaisseur
            autre = a if porteur is b else b
            ep_autre = min(profondeur(autre.solide, itf.monde(*q, 0.0 if autre is a else itf.ecart), -itf.normale if autre is a else itf.normale)
                           for q in pts)
            if ep_autre < h + retrait + proc(autre)["paroi_min"]:
                continue
            solides = []
            hauteur = h + retrait + paroi + 1.0
            for q in pts:
                q = np.array(q)
                cote_pad = d + 2 * paroi
                debut = largeur / 2.0 - 0.3
                fin = largeur / 2.0 + d + 2 * paroi
                centre_pad = centre2 + t * float((q - centre2) @ t) + dedans * ((debut + fin) / 2.0)
                M = np.eye(4)
                n = itf.normale * sens
                M[:3, 0] = itf.e1 * t[0] + itf.e2 * t[1]
                M[:3, 1] = itf.e1 * dedans[0] + itf.e2 * dedans[1]
                M[:3, 2] = np.cross(M[:3, 0], M[:3, 1])
                if float(M[:3, 2] @ n) < 0:
                    M[:3, 1] = -M[:3, 1]
                    M[:3, 2] = -M[:3, 2]
                base = itf.monde(*centre_pad, 0.0 if porteur is a else itf.ecart)
                M[:3, 3] = base + n * (hauteur / 2.0)
                from application.engineering_assembly import boite as _boite, matrice_vers_3x4
                solides.append(_boite([cote_pad, fin - debut, hauteur]).transform(matrice_vers_3x4(M)))
            return {"piece": porteur, "solides": solides, "choix": (d, h, f_paire, pts), "largeur": largeur}
    return None


def liaison_aimant(liaison: dict[str, Any], a: Piece, b: Piece, itf: Interface, pieces: dict[str, Piece]) -> Resultat:
    r = Resultat(liaison["id"], "aimant", [a.id, b.id])
    n = itf.normale
    F, source_F = effort(liaison, a, b)
    if not liaison.get("effort_N"):
        F, source_F = max(4.0, 0.5 * masse_piece(b) * 1e-3 * G * 4), "hypothèse : maintien de fermeture (≥ 4 N)"
    jeu_poche = max(proc(a)["aimant"], proc(b)["aimant"])
    retrait = 0.3
    options = []
    for d, h in normes.AIMANTS:
        marge = d / 2.0 + jeu_poche + max(proc(a)["paroi_min"], proc(b)["paroi_min"]) * 0.75
        region = itf.polygone.buffer(-(marge - 0.05))
        if region.is_empty:
            continue
        region = restreindre_bord(region, itf, liaison.get("bord"), max(3 * marge, 20.0))
        region = retirer_exclusions(region, itf, liaison, marge)
        if region.is_empty:
            continue
        q = repartir(region, 1)[0]
        ep_a = profondeur(a.solide, itf.monde(*q), -n)
        ep_b = profondeur(b.solide, itf.monde(*q, itf.ecart), n)
        if ep_a < h + retrait + proc(a)["paroi_min"] or ep_b < h + retrait + proc(b)["paroi_min"]:
            continue
        f_paire = normes.force_aimants(d, h, 2 * retrait + itf.ecart)
        n_min = 2 if longueur_utile(region) > 4 * marge else 1
        nombre = int(liaison.get("nombre") or max(n_min, math.ceil(2.0 * F / f_paire)))
        if nombre > 6:
            continue
        pts = repartir(region, nombre)
        if any(math.dist(pts[i], pts[j]) < 2 * marge for i in range(len(pts)) for j in range(i + 1, len(pts))):
            continue
        options.append((nombre, f_paire, d, h, f_paire, pts))
    meilleurs = None
    taquet = None
    if options:
        # le moins d'aimants possible, puis le plus petit aimant qui suffit (fermeture franche sans excès)
        options.sort(key=lambda o: (o[0], o[1]))
        _, _, d, h, f_paire, pts = options[0]
        meilleurs = (d, h, f_paire, pts)
    else:
        taquet = _taquet_aimants(liaison, a, b, itf, F, jeu_poche, retrait)
        if taquet:
            d, h, f_paire, pts = taquet["choix"]
            meilleurs = (d, h, f_paire, pts)
            for solide in taquet["solides"]:
                r.ajouter(taquet["piece"].id, solide)
            r.decisions.append({"sujet": liaison["id"], "decision": f"{len(taquet['solides'])} taquet(s) collé(s) contre {taquet['piece'].nom}",
                                "raison": f"la tranche ({taquet['largeur']:.1f} mm) est trop étroite pour loger un aimant : "
                                          "un taquet intérieur élargit localement l'appui"})
    if not meilleurs:
        raise ErreurConception(f"{liaison['id']} : aucun aimant de catalogue ne tient dans l'interface")
    d, h, f_paire, pts = meilleurs
    for k, (u, v) in enumerate(pts):
        P = itf.monde(u, v)
        for p, sens, decal in ((a, -n, 0.0), (b, n, itf.ecart)):
            base = P + n * decal
            if taquet and p is taquet["piece"]:
                base = P + n * decal
            r.retirer(p.id, cyl_entre(base - sens * 0.5, base + sens * (h + retrait), (d + jeu_poche) / 2.0))
            r.trous.append({"piece": p.id, "centre": base.tolist(), "axe": sens.tolist(), "rayon": (d + jeu_poche) / 2.0,
                            "de": 0.0, "a": h + retrait, "liaison": liaison["id"]})
            aimant = cyl_entre(base + sens * retrait, base + sens * (retrait + h), d / 2.0)
            art = article(f"aimant néodyme N42 disque Ø{d}×{h} mm, nickelé", "aimant N42", float(d), float(h), h=h)
            r.quincaillerie.append(quincaillerie(f"{liaison['id']}_aimant_{p.id}_{k + 1}", f"aimant {d}×{h}", aimant, "neodyme",
                                                 art, p.id, -sens, liaison["id"]))
    r.calculs.update({"aimant": f"Ø{d}×{h} N42", "paires": len(pts), "force_par_paire_N": round(f_paire, 2),
                      "force_totale_N": round(f_paire * len(pts), 2), "ecart_entre_aimants_mm": round(2 * retrait + itf.ecart, 2),
                      "effort_N": round(F, 1), "source_effort": source_F,
                      "methode": "champ axial du cylindre aimanté + pression de Maxwell (±50 %)"})
    r.decisions.append({"sujet": liaison["id"], "decision": f"{len(pts)} paire(s) d'aimants Ø{d}×{h} N42",
                        "raison": f"≈ {f_paire:.1f} N par paire à {2 * retrait + itf.ecart:.1f} mm d'écart, coefficient 2 sur {F:.1f} N"})
    r.etapes.append(f"Coller les aimants Ø{d}×{h} dans leurs logements de {a.nom} et {b.nom} (époxy), "
                    "en ATTRACTION : présenter chaque paire avant collage.")
    r.interface = _resume_interface(itf)
    return r


# --------------------------------------------------------------------------- clip (crochet en porte-à-faux)

def liaison_clip(liaison: dict[str, Any], a: Piece, b: Piece, itf: Interface, pieces: dict[str, Piece]) -> Resultat:
    """Crochets sur A (qui ferme) plongeant dans la cavité de B, becs dans des fenêtres de la paroi de B."""
    from shapely.geometry import Point
    r = Resultat(liaison["id"], "clip", [a.id, b.id])
    eps = mat(a)["clip"]
    if not eps or eps < 0.01:
        raise ErreurConception(f"{liaison['id']} : {mat(a)['nom']} ne supporte pas la flexion d'un clip")
    if itf.ecart > 1e-3:
        raise ErreurConception(f"{liaison['id']} : les pièces ne se touchent pas")
    n = itf.normale                       # de A vers B : le crochet plonge selon +n
    trous = [ring for poly in getattr(itf.polygone, "geoms", [itf.polygone]) for ring in poly.interiors]
    if not trous:
        raise ErreurConception(f"{liaison['id']} : {b.nom} n'a pas de cavité sous {a.nom} pour loger un crochet")
    anneau = max(trous, key=lambda ring: abs(_aire_anneau(ring)))
    coords = list(anneau.coords)
    segments_ = []
    for (x0, y0), (x1, y1) in zip(coords, coords[1:]):
        L = math.hypot(x1 - x0, y1 - y0)
        if L > 8.0:
            segments_.append((np.array([x0, y0]), np.array([x1, y1]), L))
    segments_.sort(key=lambda s: -s[2])
    if not segments_:
        raise ErreurConception(f"{liaison['id']} : bord de cavité trop court pour un crochet")
    longs = [segments_[0]]
    for s in segments_[1:]:
        t0 = (longs[0][1] - longs[0][0]) / longs[0][2]
        t1 = (s[1] - s[0]) / s[2]
        if abs(float(t0 @ t1)) > 0.99 and abs(s[2] - longs[0][2]) < 0.2 * longs[0][2]:
            longs.append(s)
            break
    from shapely.geometry import Polygon
    poly_cavite = Polygon(anneau)
    jeu = proc(a)["clip"] or 0.3
    paroi_b = []
    pc = proc(a)
    E = mat(a)["module"]
    for (p0, p1, L) in longs:
        t2 = (p1 - p0) / L
        dedans = np.array([-t2[1], t2[0]])
        milieu = (p0 + p1) / 2.0
        if not poly_cavite.contains(Point(*(milieu + dedans * 0.5))):
            dedans = -dedans
        # épaisseur de la paroi de B derrière ce bord, profondeur libre de la cavité
        Pm = itf.monde(*milieu)
        mur = itf.e1 * (-dedans[0]) + itf.e2 * (-dedans[1])
        ep_mur = profondeur(b.solide, Pm + n * 1.0 + mur * 0.01, mur) + 0.01
        libre = min(profondeur_libre(q, itf.monde(*(milieu + dedans * 3.0)), n)
                    for q in pieces.values() if q.id != a.id and q.solide is not None)
        paroi_b.append((p0, p1, L, t2, dedans, ep_mur, libre))
    calculs = []
    for (p0, p1, L, t2, dedans, ep_mur, libre) in paroi_b:
        l = min(22.0, max(8.0, 0.6 * libre))
        if libre < 8.0 + 2.0:
            raise ErreurConception(f"{liaison['id']} : cavité trop peu profonde ({libre:.1f} mm) pour un crochet")
        y = min(1.0, 0.6 * ep_mur)
        h_min = max(pc["paroi_min"], 1.5 * pc["detail_min"])
        h = None
        while y >= 0.5:
            h_eps = eps * l * l / (1.5 * y)
            h = min(h_eps, 0.35 * l, 4.0)
            if h >= h_min:
                break
            y -= 0.1
        if h is None or h < h_min:
            raise ErreurConception(f"{liaison['id']} : déformation admissible de {mat(a)['nom']} trop faible pour un crochet")
        b_l = min(15.0, max(6.0, 0.15 * L))
        lip = y / math.tan(math.radians(30.0))
        nombre = 1 if L < 100 else 2
        res = normes.clip_cantilever(l, h, b_l, y, E, 30.0, 0.4)
        calculs.append({"longueur_mm": round(l, 2), "epaisseur_mm": round(h, 2), "largeur_mm": round(b_l, 2),
                        "contre_depouille_mm": round(y, 2), "deformation": round(res["deformation"], 4),
                        "deformation_admissible": eps, "effort_emboitement_N": round(res["effort_emboitement_N"], 1),
                        "nombre": nombre, "paroi_mm": round(ep_mur, 2)})
        retenue = 45.0 if liaison.get("demontable") else 90.0
        for k in range(nombre):
            f = (k + 1) / (nombre + 1)
            c2 = p0 + (p1 - p0) * f
            # repère : x = dedans (vers la cavité), y = profondeur (+n), z = le long du bord
            Xd = itf.e1 * dedans[0] + itf.e2 * dedans[1]
            Z = np.cross(Xd, n)
            O = itf.monde(*c2) - Z * (b_l / 2.0)
            M = np.eye(4)
            M[:3, 0], M[:3, 1], M[:3, 2], M[:3, 3] = Xd, n, Z, O
            if np.linalg.det(M[:3, :3]) < 0:
                M[:3, 2] = -Z
                M[:3, 3] = itf.monde(*c2) + Z * (b_l / 2.0)
            poutre = [(jeu, -0.4), (jeu + h, -0.4), (jeu + h, l), (jeu, l)]
            d_ret = l - lip
            if retenue >= 89:
                bec = [(jeu + 0.01, d_ret), (jeu - y, d_ret), (jeu + 0.01, l)]
            else:
                bec = [(jeu + 0.01, d_ret - y), (jeu - y, d_ret), (jeu + 0.01, l)]
            r.ajouter(a.id, extrusion_profil(poutre, b_l, M))
            levre = extrusion_profil(bec, b_l, M)
            r.ajouter(a.id, levre)
            r.elastiques.append({"piece": a.id, "solide": levre, "contre": b.id, "liaison": liaison["id"]})
            # fenêtre traversant la paroi de B, avec jeu
            haut = (d_ret - jeu - (y if retenue < 89 else 0.0))
            fen = [(0.5, haut), (-ep_mur - 1.0, haut), (-ep_mur - 1.0, l + jeu + 0.6), (0.5, l + jeu + 0.6)]
            Mf = M.copy()
            Mf[:3, 3] = M[:3, 3] - M[:3, 2] * jeu
            r.retirer(b.id, extrusion_profil(fen, b_l + 2 * jeu, Mf))
            if haut < proc(b)["paroi_min"]:
                raise ErreurConception(f"{liaison['id']} : la fenêtre du crochet entamerait le bord de {b.nom}")
    r.contraintes.append({"piece": a.id, "par_rapport_a": b.id, "approche": (-n).tolist(), "exacte": True})
    r.calculs.update({"crochets": calculs, "methode": "poutre encastrée de section constante : ε = 1,5 y h / l²"})
    nb = sum(c["nombre"] for c in calculs)
    r.decisions.append({"sujet": liaison["id"], "decision": f"{nb} crochet(s) en porte-à-faux, fenêtres dans {b.nom}",
                        "raison": f"{mat(a)['nom']} admet ε = {eps:.1%} en flexion répétée ; "
                                  f"ε calculée {max(c['deformation'] for c in calculs):.2%}"})
    r.etapes.append(f"Clipser {a.nom} sur {b.nom} : pousser jusqu'au déclic ({nb} crochet(s) ; "
                    "démontage en poussant les becs par les fenêtres).")
    r.interface = _resume_interface(itf)
    return r


def _aire_anneau(ring) -> float:
    c = list(ring.coords)
    return 0.5 * sum(c[i][0] * c[i + 1][1] - c[i + 1][0] * c[i][1] for i in range(len(c) - 1))


def profondeur_libre(p: Piece, point, direction, maximum: float = 500.0) -> float:
    """Distance libre (sans matière de p) depuis `point` selon `direction`."""
    d = np.asarray(direction, dtype=float)
    p0 = np.asarray(point, dtype=float) + d * 1e-3
    hits = p.solide.ray_cast(tuple(map(float, p0)), tuple(map(float, p0 + d * maximum)))
    return float(hits[0].distance) * maximum if hits else maximum


# --------------------------------------------------------------------------- charnière à broche

def liaison_charniere(liaison: dict[str, Any], fixe: Piece, mobile: Piece, itf: Interface,
                      pieces: dict[str, Piece]) -> Resultat:
    """Charnière à nœuds alternés et broche : nœuds et âmes sur les deux pièces, broche normalisée.

    L'axe longe le bord `bord` de l'interface, à un rayon de nœud à l'extérieur des faces : chaque
    point de la pièce mobile reste à au moins un rayon de l'axe, si bien que la rotation ne fait
    entrer ni la pièce dans les nœuds fixes ni l'âme mobile dans la pièce fixe (vérifié ensuite par
    balayage réel de l'angle).
    """
    r = Resultat(liaison["id"], "charniere", [fixe.id, mobile.id])
    if itf.ecart > 1e-3:
        raise ErreurConception(f"{liaison['id']} : les pièces doivent être en contact")
    n = itf.normale                          # de la pièce fixe vers la pièce mobile
    bord = liaison.get("bord") or "arriere"
    d2 = direction_plan(itf, bord)
    if d2 is None:
        raise ErreurConception(f"{liaison['id']} : le bord « {bord} » n'est pas dans le plan de l'interface")
    sortie = itf.e1 * d2[0] + itf.e2 * d2[1]  # direction vers l'extérieur, dans le plan
    axe = np.cross(n, sortie)
    axe /= np.linalg.norm(axe)
    # bord extérieur : plus loin des deux pièces dans la direction `sortie`, au plan de l'interface
    proj = lambda s: max(float(v @ sortie) for v in _sommets(s))
    face_fixe, face_mobile = proj(fixe.solide), proj(mobile.solide)
    limite = max(face_fixe, face_mobile)
    # étendue le long de l'axe : celle de l'interface
    xs = [itf.monde(*c) for poly in getattr(itf.polygone, "geoms", [itf.polygone]) for c in poly.exterior.coords]
    t_axe = [float(x @ axe) for x in xs]
    t0, t1 = min(t_axe), max(t_axe)
    longueur_bord = t1 - t0
    ep_mob = profondeur(mobile.solide, itf.monde(*_centre(itf)), n)
    ep_fix = _epaisseur_bord(fixe, itf, sortie, n)
    pc = proc(fixe)
    paroi = max(pc["paroi_min"], proc(mobile)["paroi_min"]) * (0.8 if famille(fixe) == "bois" else 1.0)
    rayon = max(0.5 * min(ep_mob, ep_fix) + 0.5, 2.0 + paroi)
    rayon = min(rayon, 0.75 * max(ep_mob, ep_fix))
    goupilles = [dd for dd in sorted(normes.ISO2338) if dd <= min(2 * (rayon - paroi), rayon) + 1e-9]
    if not goupilles:
        raise ErreurConception(f"{liaison['id']} : nœuds trop petits pour une broche normalisée")
    d_broche = goupilles[-1]
    # nombre de charnières et nœuds
    if longueur_bord > 160.0:
        longueur = min(0.3 * longueur_bord, 90.0)
        centres = [t0 + 0.16 * longueur_bord + longueur / 2, t1 - 0.16 * longueur_bord - longueur / 2]
    else:
        longueur = 0.8 * longueur_bord
        centres = [(t0 + t1) / 2.0]
    jeu_ax = pc["axial"]
    lo, hi = normes.ISO2338[d_broche]
    if longueur > hi:
        longueur = float(hi)                 # une charnière ne dépasse pas la plus longue broche normalisée
    nb_noeuds = max(3, min(9, int(round(longueur / (2.5 * rayon)))))
    if nb_noeuds % 2 == 0:
        nb_noeuds += 1
    l_noeud = (longueur - (nb_noeuds - 1) * jeu_ax) / nb_noeuds
    if l_noeud < 2 * pc["detail_min"]:
        raise ErreurConception(f"{liaison['id']} : nœuds trop courts")
    L_broche = normes.plus_grande_longueur(normes.SERIE_GOUPILLES, longueur - 0.5, (lo, hi))
    if L_broche is None or L_broche < longueur - 0.5 * l_noeud - 1e-9:
        L_broche = normes.longueur_normalisee(normes.SERIE_GOUPILLES, longueur - 0.5 * l_noeud, longueur, (lo, hi))
    if L_broche is None:
        raise ErreurConception(f"{liaison['id']} : aucune broche ISO 2338 Ø{d_broche:g} de longueur ≈ {longueur:.0f} mm")
    serrage = pc["serrage"]
    jeu_rot = proc(mobile)["rotation"]
    pivot_plan = limite + rayon                              # position de l'axe le long de `sortie`
    origine_plan = itf.origine + n * 0.0
    # point de l'axe : sur le plan de l'interface, à `pivot_plan` selon `sortie`
    base_axe = origine_plan + sortie * (pivot_plan - float(origine_plan @ sortie))
    base_axe = base_axe - axe * float(base_axe @ axe)
    cinematiques = []
    for i_c, c in enumerate(centres):
        A0 = base_axe + axe * (c - longueur / 2.0)
        for k in range(nb_noeuds):
            s0 = k * (l_noeud + jeu_ax)
            P0, P1 = A0 + axe * s0, A0 + axe * (s0 + l_noeud)
            noeud = cyl_entre(P0, P1, rayon)
            pour_fixe = k % 2 == 0                           # nœuds extrêmes sur la pièce fixe
            # âme : de la face extérieure de la pièce jusqu'à l'axe, du côté de la pièce concernée
            cote = -n if pour_fixe else n
            ame = _ame(P0, P1, sortie, cote, rayon, face_fixe if pour_fixe else face_mobile, pivot_plan)
            cible = fixe if pour_fixe else mobile
            r.ajouter(cible.id, union([noeud, ame]))
            alesage = (d_broche - serrage) / 2.0 if pour_fixe else (d_broche + jeu_rot) / 2.0
            r.retirer(cible.id, cyl_entre(P0 - axe * 0.2, P1 + axe * 0.2, alesage))
            r.trous.append({"piece": cible.id, "centre": ((P0 + P1) / 2).tolist(), "axe": axe.tolist(), "rayon": alesage,
                            "de": -l_noeud / 2, "a": l_noeud / 2, "liaison": liaison["id"], "noeud": True})
            if pour_fixe and serrage > 0:
                r.interferences.append({"pieces": [f"{liaison['id']}_broche_{i_c + 1}", fixe.id], "nature": "serrage",
                                        "volume_attendu_mm3": math.pi * d_broche * (serrage / 2.0) * l_noeud,
                                        "liaison": liaison["id"], "cumul": True})
        debut = A0 + axe * ((longueur - L_broche) / 2.0)
        broche = cyl_entre(debut, debut + axe * L_broche, d_broche / 2.0 - (0.02 if serrage == 0 else 0.0))
        art = article(f"goupille cylindrique ISO 2338 – {normes.format_mm(d_broche)} m6 × {L_broche} – acier (broche)",
                      "ISO 2338", d_broche, L_broche)
        r.quincaillerie.append(quincaillerie(f"{liaison['id']}_broche_{i_c + 1}", f"broche Ø{d_broche:g}×{L_broche}", broche,
                                             "acier", art, fixe.id, axe, liaison["id"]))
    # sens d'ouverture : la rotation éloigne le centre de la pièce mobile de l'interface (+n)
    pivot = base_axe + axe * float(np.mean(centres))
    centre_mob = np.asarray(mobile.centre, dtype=float)
    from application.engineering_assembly import rotation_axe
    essai = rotation_axe(axe, math.radians(3.0), pivot)
    tourne = essai[:3, :3] @ centre_mob + essai[:3, 3]
    signe = 1.0 if float((tourne - centre_mob) @ n) > 0 else -1.0
    amplitude = float(liaison.get("amplitude_deg") or 105.0)
    r.cinematique = {"type": "charniere", "fixe": fixe.id, "mobile": mobile.id, "axe": (axe * signe).tolist(),
                     "pivot": pivot.tolist(), "amplitude_demandee_deg": amplitude, "cote": bord}
    r.calculs.update({"rayon_noeud_mm": round(rayon, 2), "broche": f"Ø{d_broche:g}×{L_broche}", "noeuds_par_charniere": nb_noeuds,
                      "longueur_noeud_mm": round(l_noeud, 2), "jeu_axial_mm": jeu_ax, "jeu_rotation_diametral_mm": jeu_rot,
                      "serrage_broche_mm": serrage, "charnieres": len(centres)})
    r.decisions.append({"sujet": liaison["id"],
                        "decision": f"{len(centres)} charnière(s) à {nb_noeuds} nœuds, broche ISO 2338 Ø{d_broche:g}×{L_broche}",
                        "raison": f"axe sur le bord {bord}, à un rayon ({rayon:.1f} mm) hors des faces ; broche "
                                  + ("serrée dans les nœuds fixes" if serrage > 0 else "collée dans les nœuds fixes")
                                  + f", jeu de {jeu_rot:.2f} mm dans les nœuds mobiles"})
    r.etapes.append(f"Présenter {mobile.nom} sur {fixe.nom}, nœuds alternés, puis enfoncer la broche Ø{d_broche:g} "
                    f"({len(centres)} charnière(s)).")
    r.interface = _resume_interface(itf)
    return r


def _sommets(solide) -> np.ndarray:
    m = solide.to_mesh64()
    return np.asarray(m.vert_properties, dtype=float)[:, :3]


def _epaisseur_bord(p: Piece, itf: Interface, sortie: np.ndarray, n: np.ndarray) -> float:
    """Épaisseur de la paroi de `p` au bord de l'interface, mesurée vers l'intérieur depuis sa face extérieure."""
    pts = [itf.monde(*c) for poly in getattr(itf.polygone, "geoms", [itf.polygone]) for c in poly.exterior.coords]
    extreme = max(float(q @ sortie) for q in pts)
    milieu = itf.monde(*_centre(itf))
    surface = milieu + sortie * (extreme - float(milieu @ sortie)) - n * 1.0
    return profondeur(p.solide, surface, -sortie)


def _ame(P0, P1, sortie, cote, rayon, limite, pivot_plan):
    """Âme qui relie un nœud à sa pièce : de la face extérieure (`limite`) à l'axe, d'un seul côté du plan."""
    P0, P1 = np.asarray(P0), np.asarray(P1)
    axe = (P1 - P0) / np.linalg.norm(P1 - P0)
    largeur = pivot_plan - limite + 0.4
    centre = (P0 + P1) / 2.0 - sortie * (largeur / 2.0) + np.asarray(cote) * (rayon / 2.0)
    M = np.eye(4)
    M[:3, 0], M[:3, 1], M[:3, 2] = sortie, np.asarray(cote), axe
    if np.linalg.det(M[:3, :3]) < 0:
        M[:3, 0] = -sortie
    M[:3, 3] = centre
    from application.engineering_assembly import boite, matrice_vers_3x4
    return boite([largeur, rayon, float(np.linalg.norm(P1 - P0))]).transform(matrice_vers_3x4(M))


# --------------------------------------------------------------------------- résumé

def _resume_interface(itf: Interface) -> dict[str, Any]:
    c = itf.polygone.centroid
    return {"normale": [round(float(x), 6) for x in itf.normale], "centre": [round(float(x), 3) for x in itf.monde(c.x, c.y)],
            "aire_mm2": round(itf.aire, 2), "ecart_mm": round(itf.ecart, 3)}


# --------------------------------------------------------------------------- répartiteur

# Repli d'un ingénieur quand une liaison est impossible ici : même fonction, autre moyen.
REPLIS = {"clip": ["aimant", "vis"], "queue_aronde": ["emmanchement"], "soudure": ["boulon_ecrou", "vis"],
          "aimant": ["clip", "vis"], "emmanchement": ["vis"], "vis": ["boulon_ecrou"], "boulon_ecrou": ["vis"],
          "colle": [], "charniere": []}
GENERATEURS = {"vis": liaison_vis, "emmanchement": liaison_emmanchement, "colle": liaison_colle,
               "soudure": liaison_soudure, "queue_aronde": liaison_queue_aronde, "aimant": liaison_aimant,
               "clip": liaison_clip, "charniere": liaison_charniere}


def profondeur_arbre(pid: str, pieces: dict[str, Piece], memo: dict[str, int] | None = None) -> int:
    memo = {} if memo is None else memo
    if pid in memo:
        return memo[pid]
    p = pieces.get(pid)
    pos = (p.position or {}) if p else {}
    ref = pos.get("_contenant") or pos.get("par_rapport_a")
    memo[pid] = 0
    if ref and ref != pid:
        ref_id = ref if ref in pieces else next((q.id for q in pieces.values() if q.base_id == ref), None)
        memo[pid] = 1 + (profondeur_arbre(ref_id, pieces, memo) if ref_id else 0)
    return memo[pid]


def _membres(ref: str, pieces: dict[str, Piece]) -> list[str]:
    if ref in pieces:
        return [ref]
    return [p.id for p in pieces.values() if p.base_id == ref and not p.est_quincaillerie]


def _vers_bord(itf: Interface, bord: str) -> float:
    c = itf.polygone.centroid
    return float(itf.monde(c.x, c.y) @ COTES[bord])


def _roles(type_: str, x: Piece, y: Piece, pieces: dict[str, Piece]) -> tuple[Piece, Piece]:
    dx, dy = profondeur_arbre(x.id, pieces), profondeur_arbre(y.id, pieces)
    parent, enfant = (x, y) if dx <= dy else (y, x)
    if type_ == "vis":
        if y.trous_existants and y.origine == "achete":
            return x, y
        if x.trous_existants and x.origine == "achete":
            return y, x
        itf = interface_principale(x, y)
        if itf is None:
            return parent, enfant
        c = itf.monde(*_centre(itf))
        ex = profondeur(x.solide, c, -itf.normale)
        ey = profondeur(y.solide, c + itf.normale * itf.ecart, itf.normale)
        if abs(ex - ey) < 1e-6:
            return enfant, parent
        return (x, y) if ex < ey else (y, x)          # la tête du côté de la pièce la plus mince
    if type_ == "clip":
        if y.forme == "bac" and x.forme != "bac":
            return x, y
        if x.forme == "bac" and y.forme != "bac":
            return y, x
        return enfant, parent
    if type_ in ("queue_aronde", "charniere", "soudure", "emmanchement", "colle", "aimant"):
        return parent, enfant
    return x, y


def generer(liaison: dict[str, Any], pieces: dict[str, Piece]) -> list[Resultat]:
    """Produit la ou les liaisons réelles (avec repli justifié) pour une liaison demandée."""
    type_ = liaison["type"]
    if type_ == "charniere" and not liaison.get("bord"):
        liaison = {**liaison, "bord": "arriere"}
    candidats = [_membres(e, pieces) for e in liaison["entre"]]
    if any(not c for c in candidats):
        raise ErreurConception(f"{liaison['id']} : pièce inconnue dans {liaison['entre']}")
    if type_ == "boulon_ecrou" or not any(len(c) > 1 for c in candidats):
        paires = [[c[0] for c in candidats]]
    else:
        # une référence à un contenant décomposé vise ses panneaux réellement en contact
        fixes = [c[0] for c in candidats if len(c) == 1]
        multiples = [c for c in candidats if len(c) > 1]
        if len(fixes) != 1 or len(multiples) != 1:
            raise ErreurConception(f"{liaison['id']} : liaison entre deux ensembles de panneaux non gérée")
        autre = pieces[fixes[0]]
        contacts = []
        for m in multiples[0]:
            itf = interface_principale(autre, pieces[m])
            if itf is not None and itf.ecart <= 1e-3:
                contacts.append((m, itf))
        if not contacts:
            raise ErreurConception(f"{liaison['id']} : {autre.nom} ne touche aucun panneau de {liaison['entre']}")
        bord = liaison.get("bord")
        if bord:
            meilleur = max(contacts, key=lambda c: _vers_bord(c[1], bord))
            paires = [[autre.id, meilleur[0]]]
        elif type_ in ("vis", "colle"):
            paires = [[autre.id, m] for m, _ in contacts]
        else:
            paires = [[autre.id, max(contacts, key=lambda c: c[1].aire)[0]]]
    resultats: list[Resultat] = []
    for k, paire in enumerate(paires):
        l = {**liaison, "id": liaison["id"] if len(paires) == 1 else f"{liaison['id']}_{k + 1}", "entre": paire}
        resultats.append(_generer_avec_replis(l, pieces))
    return resultats


def _generer_avec_replis(liaison: dict[str, Any], pieces: dict[str, Piece]) -> Resultat:
    essais = [liaison["type"]] + REPLIS.get(liaison["type"], [])
    if not liaison.get("demontable"):
        essais = [t for t in essais if t != "aimant" or t == liaison["type"]]
    echecs = []
    for type_ in essais:
        l = {**liaison, "type": type_}
        try:
            r = _generer_type(l, pieces)
        except ErreurConception as exc:
            echecs.append(f"{type_} : {exc}")
            continue
        if type_ != liaison["type"]:
            r.decisions.insert(0, {"sujet": liaison["id"], "decision": f"{liaison['type']} remplacé par {type_}",
                                   "raison": echecs[-1] if echecs else ""})
        r.calculs["type_demande"] = liaison["type"]
        if echecs:
            r.calculs["replis"] = echecs
        return r
    raise ErreurConception(f"{liaison['id']} : aucune réalisation possible — " + " | ".join(echecs))


def _generer_type(liaison: dict[str, Any], pieces: dict[str, Piece]) -> Resultat:
    type_ = liaison["type"]
    membres = [pieces[e] for e in liaison["entre"]]
    if type_ == "boulon_ecrou":
        pile = list(membres)
        if len(pile) == 2:
            a, b = _roles("vis", pile[0], pile[1], pieces)
            pile = [a, b]
        else:
            itf = interface_principale(pile[0], pile[1])
            n = itf.normale if itf is not None else np.array([0.0, 0.0, 1.0])
            if abs(n[2]) > 0.7:
                pile.sort(key=lambda p: -float(p.centre[2]))   # tête en haut
            else:
                pile.sort(key=lambda p: float(np.asarray(p.centre) @ n))
        return _sans_usiner_les_achats(liaison_boulon(liaison, pile, pieces), pieces)
    if len(membres) != 2:
        raise ErreurConception(f"{liaison['id']} : deux pièces attendues")
    a, b = _roles(type_, membres[0], membres[1], pieces)
    itf = interface_principale(a, b)
    if itf is None:
        raise ErreurConception(f"{liaison['id']} : {a.nom} et {b.nom} ne se touchent ni ne se font face")
    if itf.ecart > 1e-3 and type_ not in ("vis", "aimant"):
        raise ErreurConception(f"{liaison['id']} : {a.nom} et {b.nom} sont écartées de {itf.ecart:.1f} mm")
    return _sans_usiner_les_achats(GENERATEURS[type_](liaison, a, b, itf, pieces), pieces)


def _sans_usiner_les_achats(r: Resultat, pieces: dict[str, Piece]) -> Resultat:
    """Un composant acheté ne se perce, ne se poche ni ne se rallonge : seuls ses trous existants sont modélisés."""
    for pid in set(r.retraits) | set(r.ajouts):
        p = pieces.get(pid)
        if p is not None and p.origine == "achete" and (pid in r.ajouts or pid not in r.trous_existants):
            raise ErreurConception(f"{r.id} : on n'usine pas le composant acheté « {p.nom} » ; choisir une liaison qui "
                                   "n'entame que les pièces fabriquées, ou déclarer ses trous de fixation")
    return r
