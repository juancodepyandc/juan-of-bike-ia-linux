"""Mondes à visiter à pied : une ville posée dans sa campagne, avec des maisons où l'on entre.

Créé le 15/11/2026 (demande : « des vrais mondes où l'on peut se balader »). Trois lois générales :
1. La ville s'installe sur un replat : un relief vallonné l'entoure (campagne, prairie, arbres) et le terrain
   s'abaisse en pente douce sous l'emprise bâtie, juste sous son sol.
2. Les maisons les plus proches du point de départ deviennent VISITABLES : un logement planifié (pièces selon
   la surface au sol, portes, fenêtres) et meublé remplace l'enveloppe ; le plan tourne pour que sa porte
   d'entrée regarde la rue ; le volume du bâtiment épouse le plan et garde sa toiture.
3. On part dehors, sur le trottoir, face à la première maison visitable.

Rien n'est propre à un sujet : programmes de pièces tirés des fonctions et surfaces du vocabulaire.
"""
from __future__ import annotations

import math
from typing import Any, Callable

import numpy as np
from shapely import contains_xy
from shapely.geometry import Point, Polygon
from shapely.ops import nearest_points

from monde import geometrie as g
from monde.ir import Instance, Noeud, Objet, Partie, Pose, Scene

NOMBRE_VISITABLES = 4
# Les végétaux dispersés par centaines sont allégés (décimation quadrique) : le feuillage pesait 1,2 M de
# triangles sur 1,7 M dans le premier village visitable (15/11/2026), au point d'éclaircir la campagne.
CATEGORIES_LEGERES = {"arbre", "buisson", "rocher"}
FRACTION_LEGERE = 0.35
PLAFOND_MAISON = 2.6
MARGE_CAMPAGNE = 0.30            # la campagne déborde de 30 % de la ville de chaque côté
PENTE_REPLAT_M = 45.0            # distance sur laquelle le terrain rejoint le replat de la ville


# ── Programme de pièces d'une maison selon sa surface au sol ───────────────────────────────────────
def programme_maison(surface_interieure: float) -> list[tuple[str, str, float, list[str]]]:
    """Pièces (nom, fonction, surface, adjacences) d'un logement de plain-pied tenant dans `surface_interieure`.

    Loi : séjour, cuisine et entrée toujours ; chambres et pièces d'eau selon la place ; surfaces au milieu des
    fourchettes du vocabulaire, puis mises à l'échelle pour remplir la surface disponible.
    """
    from monde import vocabulaire as voc
    if surface_interieure < 38:
        liste = [("entrée", "entree"), ("séjour", "salon"), ("cuisine", "cuisine"), ("chambre", "chambre"),
                 ("salle d'eau", "salle_d_eau")]
    elif surface_interieure < 70:
        liste = [("entrée", "entree"), ("séjour", "salon"), ("cuisine", "cuisine"), ("chambre", "chambre"),
                 ("salle de bain", "salle_de_bain"), ("wc", "wc")]
    elif surface_interieure < 110:
        liste = [("entrée", "entree"), ("séjour", "salon"), ("cuisine", "cuisine"), ("chambre 1", "chambre"),
                 ("chambre 2", "chambre_enfant"), ("salle de bain", "salle_de_bain"), ("wc", "wc")]
    else:
        liste = [("entrée", "entree"), ("séjour", "salon"), ("cuisine", "cuisine"), ("salle à manger", "salle_a_manger"),
                 ("chambre 1", "chambre"), ("chambre 2", "chambre_enfant"), ("bureau", "bureau"),
                 ("salle de bain", "salle_de_bain"), ("wc", "wc")]
    typiques = [sum(voc.FONCTIONS_PIECES[f]["surface"]) / 2.0 for _, f in liste]
    echelle = surface_interieure / sum(typiques)
    pieces = []
    for (nom, fonction), s in zip(liste, typiques):
        lo, hi = voc.FONCTIONS_PIECES[fonction]["surface"]
        pieces.append((nom, fonction, round(min(hi, max(lo, s * echelle)), 1), []))
    adjacences = {"séjour": ["entrée", "cuisine"], "salle à manger": ["séjour", "cuisine"]}
    return [(n, f, s, adjacences.get(n, [])) for n, f, s, _ in pieces]


# ── Déplacer un sous-arbre (parties en coordonnées monde, poses d'instances) ───────────────────────
def _tourner(x: float, z: float, angle: float) -> tuple[float, float]:
    c, s = math.cos(angle), math.sin(angle)            # même convention que ir.Pose (lacet autour de +Y)
    return c * x + s * z, -s * x + c * z


def deplacer(noeud: Noeud, angle: float, avant: tuple[float, float], apres: tuple[float, float, float]) -> None:
    """Translate de -avant, tourne de `angle` autour de +Y, puis translate de `apres` (x, y, z), en place."""
    bx, bz = avant
    ax, ay, az = apres
    m = np.eye(4)
    m[:3, 3] = [-bx, 0.0, -bz]
    m = g.rotation_y(angle) @ m
    t = np.eye(4)
    t[:3, 3] = [ax, ay, az]
    m = t @ m
    for nd in noeud.parcourir():
        nd.parties = [Partie(g.transformer(p.maillage, m), p.materiau, p.nom) for p in nd.parties]
        for inst in nd.instances:
            x, z = _tourner(inst.pose.x - bx, inst.pose.z - bz, angle)
            inst.pose = Pose(x + ax, z + az, inst.pose.lacet + angle, inst.pose.y + ay)


def _angle(vx: float, vz: float) -> float:
    return math.atan2(vx, vz)                          # angle depuis +Z vers +X (ir.Pose.face)


# ── Maisons visitables ─────────────────────────────────────────────────────────────────────────────
def _candidates(plan_ville, reference: tuple[float, float]) -> list:
    choix = []
    for ilot, lot, b in plan_ville.batiments():
        if len(b.volumes) != 1 or b.volumes[0].libre is not None or b.commerce:
            continue
        v = b.volumes[0]
        if not 35.0 <= v.lu * v.lv <= 230.0 or b.etages > 3:
            continue
        choix.append((math.hypot(v.cx - reference[0], v.cz - reference[1]), ilot, lot, b))
    choix.sort(key=lambda c: c[0])
    return choix


def maison_visitable(b, lot, plan_ville, *, graine: int, fabrique) -> dict[str, Any] | None:
    """Planifie, meuble et pose un logement dans le bâtiment `b` ; None s'il ne tient pas dans sa parcelle."""
    from monde import disposition, plan as plan_mod
    v = b.volumes[0]
    centre = np.array([v.cx, v.cz])
    rue = nearest_points(plan_ville.chaussee, Point(v.cx, v.cz))[0]
    vers_rue = np.array([rue.x - v.cx, rue.y - v.cz])
    if np.linalg.norm(vers_rue) < 1e-6:
        return None
    vers_rue /= np.linalg.norm(vers_rue)
    surface = v.lu * v.lv * 0.78
    for essai in range(3):
        pieces = [plan_mod.PieceDemandee(nom=n, fonction=f, surface=s, adjacente_a=a)
                  for n, f, s, a in programme_maison(surface * (0.88 ** essai))]
        rapport = max(v.lu, v.lv) / max(1e-6, min(v.lu, v.lv))
        try:
            plan = plan_mod.concevoir_plan(pieces, hauteur_plafond=PLAFOND_MAISON, rapport=min(1.8, rapport),
                                           graine=graine + essai)
        except (KeyError, ValueError):
            continue
        entree = next((o for o in plan.ouvertures if o.type == "porte_entree"), None)
        if entree is None:
            continue
        x0, z0, x1, z1 = plan.emprise.bounds
        milieu = ((x0 + x1) / 2.0, (z0 + z1) / 2.0)
        exterieur = plan.emprise.buffer(0.25, join_style=2)
        # la porte d'entrée regarde la rue ; sinon un quart de tour, faute de place dans la parcelle
        base_angle = _angle(*vers_rue) - _angle(*entree.normale)
        for quart in (0.0, math.pi / 2, -math.pi / 2, math.pi):
            angle = base_angle + quart
            coins = [_tourner(x - milieu[0], z - milieu[1], angle) for x, z in exterieur.exterior.coords]
            empreinte = Polygon([(cx + v.cx, cz + v.cz) for cx, cz in coins])
            if empreinte.within(lot.polygone.buffer(0.05)):
                break
        else:
            continue
        from monde.composer import meubler_par_priorite
        demandes = {pp.nom: disposition.demandes_typiques(pp.fonction) for pp in plan.pieces}
        origines = {nom: ["typique"] * len(liste) for nom, liste in demandes.items()}
        dispositions, _ = meubler_par_priorite(plan, demandes, origines, fabrique=fabrique, graine=graine,
                                               hauteur=PLAFOND_MAISON)
        noeud = plan_mod.construire_geometrie(plan, plafond=True)
        for nom, dispo in dispositions.items():
            cible = next((n for n in noeud.parcourir() if n.nom == nom), None)
            if cible is not None:
                cible.instances.extend(dispo.instances)
        mesures = {"chevauchements": 0, "hors_piece": 0, "portes_bloquees": 0, "fenetres_bloquees": 0,
                   "inaccessibles": [], "meubles_places": 0, "meubles_demandes": 0}
        for nom, dispo in dispositions.items():
            piece = plan.piece(nom)
            m = disposition.mesurer_instances(piece, dispo.instances, PLAFOND_MAISON) if piece is not None else {}
            for cle in ("chevauchements", "hors_piece", "portes_bloquees", "fenetres_bloquees"):
                mesures[cle] += int(m.get(cle) or 0)
            mesures["inaccessibles"] += list(m.get("inaccessibles") or [])
            mesures["meubles_places"] += len(dispo.instances)
            mesures["meubles_demandes"] += int((dispo.mesures or {}).get("demandes") or 0)
        deplacer(noeud, angle, milieu, (v.cx, b.base, v.cz))
        # le volume épouse le logement (couverture posée sur ses murs), il reste dans la parcelle
        largeur, profondeur = (x1 - x0) + 0.5, (z1 - z0) + 0.5
        ux, uz = _tourner(1.0, 0.0, angle)
        v.theta = math.atan2(uz, ux)
        v.lu, v.lv = largeur, profondeur
        v.y0 = b.base
        v.y1 = b.base + PLAFOND_MAISON + 0.06
        b.etages = 1
        b.hauteur_rdc = v.y1 - b.base
        b.visitable = True
        cx, cz = _tourner(entree.centre[0] - milieu[0], entree.centre[1] - milieu[1], angle)
        nx, nz = _tourner(entree.normale[0], entree.normale[1], angle)
        noeud.nom = f"maison_visitable_{abs(hash((round(v.cx, 1), round(v.cz, 1)))) % 10000}"
        return {"noeud": noeud, "porte": (cx + v.cx, cz + v.cz), "normale": (nx, nz), "base": b.base,
                "pieces": [{"nom": p.nom, "fonction": p.fonction, "surface": round(float(p.surface), 1)} for p in plan.pieces],
                "mesures": mesures}
    return None


def alleger(fabrique, *, categories=CATEGORIES_LEGERES, fraction: float = FRACTION_LEGERE, seuil: int = 1500):
    """Fabrique dont les objets des `categories` gardent `fraction` de leurs triangles (UV et normales refaites)."""
    def fabriquer(categorie: str, graine: int, options: dict | None = None) -> Objet:
        objet = fabrique(categorie, graine, options or {})
        if categorie not in categories:
            return objet
        parties = []
        for p in objet.parties:
            m = p.maillage
            if len(m.faces) > seuil:
                try:
                    simple = m.simplify_quadric_decimation(percent=1.0 - fraction)
                    if len(simple.faces) >= 0.2 * fraction * len(m.faces):
                        m = g.finaliser(simple, lissage_deg=60.0)
                except Exception:  # noqa: BLE001 — sans décimation, l'objet complet reste juste, seulement lourd
                    pass
            parties.append(Partie(m, p.materiau, p.nom))
        objet.parties = parties
        return objet
    return fabriquer


# ── Campagne autour de la ville ────────────────────────────────────────────────────────────────────
def campagne(plan_ville, *, graine: int, fabrique, relief: str = "vallonne", biome: str = "prairie") -> tuple[Noeud, Any]:
    from monde import paysage
    W, D = plan_ville.taille
    taille = max(W, D) * (1.0 + 2.0 * MARGE_CAMPAGNE)
    rel, _ = paysage.relief_carre(taille, relief, eau="aucune", graine=graine)
    emprise_ville = plan_ville.rectangle.buffer(6.0, join_style=2)
    n = rel.n
    coord = np.linspace(-taille / 2.0, taille / 2.0, n + 1)
    xx, zz = np.meshgrid(coord, coord, indexing="ij")
    from shapely import distance as distance_shapely, points
    d = distance_shapely(emprise_ville, points(xx.ravel(), zz.ravel())).reshape(xx.shape)
    t = np.clip(d / PENTE_REPLAT_M, 0.0, 1.0)
    poids = t * t * (3.0 - 2.0 * t)                    # raccord doux (smoothstep)
    h = rel.h - float(np.percentile(rel.h, 20))
    hauteurs = (1.0 - poids) * (-0.14) + poids * np.maximum(h, -0.14)
    rel2 = paysage.Relief(hauteurs, taille, None, float(hauteurs.max() - hauteurs.min()))
    # pas de terrain sous la ville : elle a son propre sol, et un terrain glissé dessous recouvrait le lit
    # de sa rivière (village du 15/11/2026, rivière verte)
    trou = plan_ville.rectangle.buffer(-0.5, join_style=2)
    parties = []
    for p in paysage.maillage_terrain(rel2, biome, "aucune", graine):
        m = p.maillage.copy()
        garder = ~contains_xy(trou, m.triangles_center[:, 0], m.triangles_center[:, 2])
        if garder.any():
            m.update_faces(garder)
            m.remove_unreferenced_vertices()
            parties.append(Partie(m, p.materiau, p.nom))
    sol = Noeud("sol", parties=parties, fusion=True)
    hors_ville = plan_ville.rectangle.buffer(14.0, join_style=2)

    def accepter(x, z):
        return ~contains_xy(hors_ville, x, z)

    from monde import vocabulaire as voc
    especes = [paysage.Espece(cat, style, float(dens) * (6.0 if cat == "arbre" else 1.5))
               for cat, style, dens in voc.BIOMES[biome]["vegetation"]]
    instances, _ = paysage.disperser((-taille / 2.0, -taille / 2.0, taille / 2.0, taille / 2.0), especes,
                                     fabrique=fabrique, graine=graine + 17, hauteur=rel2, accepter=accepter,
                                     pente_deg=rel2.pente_deg, budget_triangles=500_000)
    return Noeud("campagne", enfants=[sol, Noeud("vegetation", instances=instances, fusion=True)]), rel2


# ── Monde complet ──────────────────────────────────────────────────────────────────────────────────
def construire_monde(programme: dict, graine: int, fabrique) -> dict[str, Any]:
    """Ville du programme + campagne autour + maisons visitables ; mêmes mesures que la ville, plus celles
    des intérieurs, et un départ dehors face à la première maison."""
    from monde import composer, ville as ville_mod
    v = programme["ville"]
    plan_ville = ville_mod.concevoir_ville(
        taille=tuple(float(x) for x in v["taille_m"]), trame=v.get("trame") or "grille",
        zones=[ville_mod.ZoneDemandee(z["type"], float(z["part"])) for z in v.get("zones") or []],
        etages=tuple(v["etages"]) if v.get("etages") else None, largeur_rues=float(v.get("largeur_rues_m") or 12.0),
        style=v.get("style") or (programme.get("style") or {}).get("architecture") or "moderne",
        riviere=bool(v.get("riviere")), arbres_alignement=bool(v.get("arbres_alignement", True)),
        voitures=bool(v.get("voitures", True)), graine=graine)
    fabrique_legere = alleger(fabrique)
    depart_rue = composer.depart_ville(plan_ville)
    reference = (depart_rue["x"], depart_rue["z"]) if depart_rue else (0.0, 0.0)
    maisons = []
    for _, ilot, lot, b in _candidates(plan_ville, reference):
        if len(maisons) >= NOMBRE_VISITABLES:
            break
        maison = maison_visitable(b, lot, plan_ville, graine=graine + len(maisons) * 101, fabrique=fabrique)
        if maison is not None:
            maisons.append(maison)
    noeud_ville = ville_mod.construire_ville(plan_ville, fabrique=fabrique_legere)
    noeud_campagne, _ = campagne(plan_ville, graine=graine, fabrique=fabrique_legere)
    habite = Noeud("habite", enfants=[noeud_campagne, noeud_ville, *[m["noeud"] for m in maisons]])
    jets, pistes = composer.emissions_des_objets(habite)
    racine = Noeud("monde", enfants=[noeud_campagne, noeud_ville, *[m["noeud"] for m in maisons], *jets],
                   extras={"maisons_visitables": [m["pieces"] for m in maisons]})
    mesures = composer.mesurer_ville(plan_ville)
    for cle in ("chevauchements", "hors_piece", "portes_bloquees", "fenetres_bloquees"):
        mesures[cle] = sum(m["mesures"][cle] for m in maisons)
    mesures["inaccessibles"] = [x for m in maisons for x in m["mesures"]["inaccessibles"]]
    mesures["maisons_visitables"] = len(maisons)
    mesures["meubles_places"] = sum(m["mesures"]["meubles_places"] for m in maisons)
    mesures["meubles_demandes"] = sum(m["mesures"]["meubles_demandes"] for m in maisons)
    depart = depart_rue
    if maisons:
        (px, pz), (nx, nz) = maisons[0]["porte"], maisons[0]["normale"]
        depart = {"x": round(px + 4.0 * nx, 3), "y": round(maisons[0]["base"], 3), "z": round(pz + 4.0 * nz, 3),
                  "direction": [round(-nx, 4), round(-nz, 4)], "lieu": "devant une maison visitable"}
    mesures["jets_de_fontaine"] = len(jets)
    return {"scene": Scene(racine), "mesures": mesures, "plan": plan_ville, "depart": depart, "pistes": pistes}
