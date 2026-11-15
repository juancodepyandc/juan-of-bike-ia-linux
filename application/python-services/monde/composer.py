"""Composition d'une scène « monde » de bout en bout, depuis une phrase.

programme (LLM, vocabulaire fermé) → intérieur : plan + disposition mesurée ; ville : réseau, îlots,
bâtiments ; nature : relief, eau, végétation → objets paramétriques (`monde.meubles.generer`) →
export glTF (`modele/scene_monde.glb`, et `modele/scene_maquette.glb` pour un intérieur : murs coupés,
sans plafond) → rendus f3d (`apercus/`) → porte mesurée (`monde.porte`) → journal (`journal/scene_monde.json`).

Rien ici ne dépend d'un sujet : le programme porte toute la demande, les briques sont des lois générales.
Une étape impossible est rapportée comme telle (ok: False et la raison), jamais remplacée en silence.
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any, Callable

from monde import export_gltf, porte
from monde import rendu as rendu_f3d
from monde.ir import Noeud, Objet, Scene


def graine_de(demande: str) -> int:
    return int(hashlib.sha256(demande.encode("utf-8")).hexdigest()[:8], 16)


def fabrique_meubles() -> Callable[[str, int, dict], Objet]:
    """Les vrais générateurs paramétriques, au format (categorie, graine, options) des briques."""
    from monde import meubles
    permis = {"largeur", "profondeur", "hauteur", "style", "materiaux"}

    def fabriquer(categorie: str, graine: int, options: dict | None = None) -> Objet:
        return meubles.generer(categorie, graine=graine, **{k: v for k, v in (options or {}).items() if k in permis and v is not None})
    return fabriquer


def _noeud_nomme(racine: Noeud, nom: str) -> Noeud | None:
    return next((n for n in racine.parcourir() if n.nom == nom), None)


# ── Meubler par priorité ───────────────────────────────────────────────────────────────────────────
# Loi (15/11/2026) : une pièce pose d'abord ce qui la définit — les meubles que la demande nomme, puis les
# meubles typiques dans l'ordre d'importance de sa fonction. Quand un meuble prioritaire ne trouve pas de
# place, le typique le moins important posé est retiré et la pièce est redisposée (3 essais) ; un typique qui
# ne tient pas est écarté FAUTE DE PLACE et dit comme tel. Jamais un meuble demandé n'est écarté. (Salle de
# bain : le lave-linge, posé avant le WC, lui prenait sa place ; petite cuisine : la table ne tenait pas.)
def _priorite(categorie: str, fonction: str, origine: str | None) -> int:
    from monde import vocabulaire as voc
    if origine == "demande":
        return 0
    ordre = [c for c, _, _ in voc.FONCTIONS_PIECES.get(fonction, {}).get("meubles_typiques", [])]
    return 1 + ordre.index(categorie) if categorie in ordre else 60


def meubler_par_priorite(plan, demandes: dict[str, list], origines: dict[str, list[str | None]], *, fabrique,
                         graine: int, hauteur: float) -> tuple[dict, list[dict]]:
    """`demandes[piece]` : Demande ; `origines[piece]` : origine de chacune (demande | typique | None)."""
    from monde import disposition
    dispositions = disposition.meubler(plan, demandes, fabrique=fabrique, graine=graine)
    ecartes: list[dict] = []
    for nom, dispo in list(dispositions.items()):
        piece = plan.piece(nom)
        if piece is None:
            continue
        liste = list(demandes.get(nom) or [])
        orig = list(origines.get(nom) or [None] * len(liste))
        prio = [_priorite(d.categorie, piece.fonction, o) for d, o in zip(liste, orig)]
        for _ in range(3):
            echecs = {e.get("categorie") for e in (dispo.echecs or []) if isinstance(e, dict)}
            if not echecs:
                break
            urgence = min((p for d, p in zip(liste, prio) if d.categorie in echecs), default=None)
            places = {i.objet.categorie for i in dispo.instances}
            def au_sol(c: str) -> bool:                   # retirer un plafonnier ou un tableau ne libère rien
                from monde import vocabulaire as voc
                cat = voc.CATEGORIES.get(c, {})
                return not (cat.get("plafond") or cat.get("mural") or cat.get("sol_partage") or cat.get("pose_sur"))
            candidats = [k for k, (d, o, p) in enumerate(zip(liste, orig, prio))
                         if o != "demande" and urgence is not None and p > urgence and d.categorie in places
                         and au_sol(d.categorie)]
            if not candidats:
                break
            retire = max(candidats, key=lambda k: prio[k])
            ecartes.append({"piece": nom, "categorie": liste[retire].categorie,
                            "raison": "retiré pour faire place à un meuble plus important"})
            del liste[retire], orig[retire], prio[retire]
            dispo = disposition.disposer(piece, liste, fabrique=fabrique, hauteur_plafond=hauteur, graine=graine)
        for e in list(dispo.echecs or []):
            if not isinstance(e, dict):
                continue
            k = next((i for i, d in enumerate(liste) if d.categorie == e.get("categorie")), None)
            if k is not None and orig[k] != "demande":
                ecartes.append({"piece": nom, "categorie": e.get("categorie"), "raison": "faute de place (typique)",
                                "detail": (e.get("raison") or "")[:160]})
                dispo.echecs.remove(e)
                if dispo.mesures:
                    dispo.mesures["demandes"] = max(0, int(dispo.mesures.get("demandes") or 0) - 1)
        dispositions[nom] = dispo
    return dispositions, ecartes


# ── Intérieur ──────────────────────────────────────────────────────────────────────────────────────
def construire_interieur(programme: dict, graine: int, fabrique) -> dict[str, Any]:
    from monde import disposition, plan as plan_mod
    from monde import vocabulaire as voc
    interieur = programme["interieur"]
    style = (programme.get("style") or {}).get("architecture")
    defauts = voc.STYLES_ARCHI.get(style or "", {}).get("interieur", {})
    pieces = [plan_mod.PieceDemandee(nom=p["nom"], fonction=p["fonction"], surface=float(p["surface_m2"]),
                                     adjacente_a=list(p.get("adjacente_a") or []),
                                     sol=p.get("sol") or None, murs=p.get("murs") or defauts.get("murs"))
              for p in interieur["pieces"]]
    hauteur = float(interieur.get("hauteur_plafond") or 2.5)
    plan = plan_mod.concevoir_plan(pieces, hauteur_plafond=hauteur, graine=graine, style=style)
    demandes = {p["nom"]: [disposition.Demande(categorie=m["categorie"], nombre=int(m.get("nombre") or 1),
                                               relations=[(r[0], r[1]) for r in m.get("relations") or []],
                                               materiaux=m.get("materiaux") or None, style=None)
                           for m in p.get("meubles") or []] for p in interieur["pieces"]}
    origines = {p["nom"]: [m.get("origine") for m in p.get("meubles") or []] for p in interieur["pieces"]}
    dispositions, ecartes = meubler_par_priorite(plan, demandes, origines, fabrique=fabrique, graine=graine,
                                                 hauteur=hauteur)
    complet = plan_mod.construire_geometrie(plan, plafond=True)
    maquette = plan_mod.construire_geometrie(plan, plafond=False, maquette=True)
    for nom, dispo in dispositions.items():
        for arbre in (complet, maquette):
            noeud = _noeud_nomme(arbre, nom)
            if noeud is not None:
                noeud.instances.extend(dispo.instances)
    # Les mesures sont RECALCULÉES depuis les instances livrées (juge indépendant de la recherche).
    mesures: dict[str, Any] = {"chevauchements": 0, "hors_piece": 0, "portes_bloquees": 0, "fenetres_bloquees": 0,
                               "degagements_occupes": 0, "inaccessibles": [], "meubles_demandes": 0,
                               "meubles_places": 0, "echecs": []}
    for nom, dispo in dispositions.items():
        piece = plan.piece(nom)
        m = disposition.mesurer_instances(piece, dispo.instances, hauteur) if piece is not None else {}
        for cle in ("chevauchements", "hors_piece", "portes_bloquees", "fenetres_bloquees", "degagements_occupes"):
            mesures[cle] += int(m.get(cle) or 0)
        mesures["inaccessibles"] += [f"{x} ({nom})" for x in (m.get("inaccessibles") or [])]
        mesures["meubles_demandes"] += int((dispo.mesures or {}).get("demandes") or 0)
        mesures["meubles_places"] += len(dispo.instances)
        mesures["echecs"] += [{"piece": nom, **e} if isinstance(e, dict) else {"piece": nom, "raison": str(e)}
                              for e in (dispo.echecs or [])]
    mesures["ecartes_faute_de_place"] = ecartes
    verification = plan_mod.verifier_plan(plan)
    noms_plan = {pp.nom for pp in plan.pieces}
    mesures["pieces_manquantes"] = [p.nom for p in pieces if p.nom not in noms_plan]
    mesures["pieces_isolees"] = list(verification.get("inaccessibles") or [])
    mesures["fenetres_interieures"] = list(verification.get("fenetres_interieures") or [])
    mesures["violations_plan"] = list((plan.mesures or {}).get("violations") or [])
    mesures["pieces"] = [{"nom": pp.nom, "fonction": pp.fonction, "surface": round(float(pp.surface), 1)}
                         for pp in plan.pieces]
    return {"scene": Scene(complet), "maquette": Scene(maquette), "mesures": mesures, "plan": plan,
            "depart": depart_interieur(plan)}


def depart_interieur(plan) -> dict[str, Any] | None:
    """Point de départ d'une visite : juste derrière la porte d'entrée, tourné vers l'intérieur."""
    entree = next((o for o in plan.ouvertures if o.type == "porte_entree"), None)
    if entree is None:
        return None
    (cx, cz), (nx, nz) = entree.centre, entree.normale      # normale : de la pièce vers l'extérieur
    return {"x": round(cx - 1.1 * nx, 3), "y": 0.0, "z": round(cz - 1.1 * nz, 3),
            "direction": [round(-nx, 4), round(-nz, 4)], "lieu": f"entrée ({entree.pieces[0]})"}


# ── Ville ──────────────────────────────────────────────────────────────────────────────────────────
def construire_ville(programme: dict, graine: int, fabrique) -> dict[str, Any]:
    from monde import ville as ville_mod
    v = programme["ville"]
    plan = ville_mod.concevoir_ville(
        taille=tuple(float(x) for x in v["taille_m"]), trame=v.get("trame") or "grille",
        zones=[ville_mod.ZoneDemandee(z["type"], float(z["part"])) for z in v.get("zones") or []],
        etages=tuple(v["etages"]) if v.get("etages") else None, largeur_rues=float(v.get("largeur_rues_m") or 12.0),
        style=v.get("style") or (programme.get("style") or {}).get("architecture") or "moderne",
        riviere=bool(v.get("riviere")), arbres_alignement=bool(v.get("arbres_alignement", True)),
        voitures=bool(v.get("voitures", True)), graine=graine)
    noeud = ville_mod.construire_ville(plan, fabrique=fabrique)
    jets, pistes = jets_des_fontaines(plan)
    noeud.enfants.extend(jets)
    return {"scene": Scene(noeud), "mesures": mesurer_ville(plan), "plan": plan, "depart": depart_ville(plan),
            "pistes": pistes}


def depart_ville(plan) -> dict[str, Any] | None:
    """Sur le trottoir le plus proche du centre, tourné vers le centre (la rue la plus vivante)."""
    from shapely.geometry import Point
    from shapely.ops import nearest_points
    if plan.trottoirs is None or plan.trottoirs.is_empty:
        return None
    centre = plan.rectangle.centroid
    p = nearest_points(plan.trottoirs.buffer(-0.6) if not plan.trottoirs.buffer(-0.6).is_empty else plan.trottoirs,
                       centre)[0]
    dx, dz = centre.x - p.x, centre.y - p.y
    norme = (dx * dx + dz * dz) ** 0.5
    direction = [round(dx / norme, 4), round(dz / norme, 4)] if norme > 1e-6 else [0.0, -1.0]
    return {"x": round(p.x, 3), "y": 0.0, "z": round(p.y, 3), "direction": direction, "lieu": "trottoir central"}


def jets_des_fontaines(plan) -> tuple[list, dict[str, dict]]:
    """Chaque fontaine de la ville jaillit : un jet d'eau balistique au-dessus de sa vasque (monde animé)."""
    from monde import emetteurs
    noeuds, pistes = [], {}
    for k, pl in enumerate(p for p in plan.mobilier if p.categorie == "fontaine"):
        hauteur = float((pl.options or {}).get("hauteur") or 1.2)
        noeud, p, _ = emetteurs.construire(emetteurs.Emission(
            "jet_liquide", origine=(pl.x, pl.y + 0.75 * hauteur, pl.z), direction=(0.0, 1.0, 0.0),
            echelle=max(0.6, hauteur / 1.4), nom=f"jet_fontaine_{k}", graine=k + 7))
        noeuds.append(noeud)
        pistes.update(p)
    return noeuds, pistes


def mesurer_ville(plan) -> dict[str, Any]:
    """Invariants d'une ville mesurés sur son plan (les mêmes lois que ses tests, au moment de livrer)."""
    from shapely.geometry import Point
    from shapely.ops import unary_union
    from shapely.strtree import STRtree
    voirie = unary_union([plan.chaussee, plan.trottoirs])
    batiments = list(plan.batiments())
    emprises = [b.emprise for _, _, b in batiments]
    sur_voirie = sum(1 for e in emprises if e.intersection(voirie).area >= 0.01)
    chevauchants = 0
    if emprises:
        arbre = STRtree(emprises)
        for i, e in enumerate(emprises):
            chevauchants += sum(1 for j in arbre.query(e) if int(j) > i and e.intersection(emprises[int(j)]).area >= 0.01)
    au_bord = ("arbre", "lampadaire_rue", "banc_public", "poubelle_rue", "buisson")
    sur_chaussee = sum(1 for pl in plan.mobilier if pl.categorie in au_bord and plan.chaussee.contains(Point(pl.x, pl.z)))
    ecarts = [abs(plan.parts_mesurees.get(z, 0.0) - part) / part for z, part in plan.parts_demandees.items() if part > 0]
    return {"batiments_sur_voirie": sur_voirie, "batiments_chevauchants": chevauchants,
            "objets_sur_chaussee": sur_chaussee, "ecart_zones": round(max(ecarts), 4) if ecarts else 0.0,
            "batiments": len(batiments), "ilots": len(plan.ilots), "ponts": len(getattr(plan, "ponts", []) or []),
            "mobilier": len(plan.mobilier),
            "parts_zones": {z: round(float(v), 3) for z, v in plan.parts_mesurees.items()}}


# ── Nature ─────────────────────────────────────────────────────────────────────────────────────────
def construire_nature(programme: dict, graine: int, fabrique) -> dict[str, Any]:
    from monde import paysage
    n = programme["nature"]
    noeud, relief = paysage.terrain(float(n["taille_m"]), n["relief"], n["biome"], eau=n.get("eau") or "aucune",
                                    graine=graine, fabrique=fabrique)
    vegetation = [inst for nd in noeud.parcourir() if nd.nom == "vegetation" for inst in nd.instances]
    dans_eau = sum(1 for inst in vegetation if bool(relief.dans_eau(inst.pose.x, inst.pose.z, 0.0)))
    mesures = {"vegetation_dans_eau": dans_eau, "vegetation": len(vegetation),
               "amplitude_m": round(float(relief.amplitude), 1),
               "niveau_eau_m": None if relief.niveau_eau is None else round(float(relief.niveau_eau), 1)}
    return {"scene": Scene(noeud), "mesures": mesures, "depart": depart_nature(relief, float(n["taille_m"]))}


def depart_nature(relief, taille: float) -> dict[str, Any] | None:
    """Le point sec et doux le plus proche du centre (spirale), tourné vers l'eau ou vers le centre."""
    import math
    niveau = relief.niveau_eau
    meilleur = None
    for k in range(400):
        r, a = 2.0 * math.sqrt(k), k * 2.39996
        x, z = r * math.cos(a), r * math.sin(a)
        if max(abs(x), abs(z)) > 0.45 * taille:
            break
        if niveau is not None and float(relief(x, z)) < niveau + 0.8:
            continue
        if float(relief.pente_deg(x, z)) < 18.0:
            meilleur = (x, z)
            break
    if meilleur is None:
        return None
    x, z = meilleur
    cible = (0.0, 0.0)
    if niveau is not None:                                   # regarder vers l'eau la plus proche
        for k in range(1, 400):
            r, a = 3.0 * math.sqrt(k), k * 2.39996
            xx, zz = x + r * math.cos(a), z + r * math.sin(a)
            if max(abs(xx), abs(zz)) < 0.5 * taille and float(relief(xx, zz)) < niveau:
                cible = (xx, zz)
                break
    dx, dz = cible[0] - x, cible[1] - z
    norme = math.hypot(dx, dz)
    direction = [round(dx / norme, 4), round(dz / norme, 4)] if norme > 1e-6 else [0.0, -1.0]
    return {"x": round(x, 3), "y": round(float(relief(x, z)), 3), "z": round(z, 3), "direction": direction,
            "lieu": "replat sec près du centre"}


def construire_ville_ou_monde(programme: dict, graine: int, fabrique) -> dict[str, Any]:
    """Une ville est livrée comme un MONDE à visiter (campagne autour, maisons où l'on entre) ;
    AURORA_MONDE_VILLE_SEULE=1 rend la ville seule."""
    import os
    if os.environ.get("AURORA_MONDE_VILLE_SEULE") == "1":
        return construire_ville(programme, graine, fabrique)
    from monde.univers import construire_monde
    return construire_monde(programme, graine, fabrique)


CONSTRUCTEURS = {"interieur": construire_interieur, "ville": construire_ville_ou_monde, "nature": construire_nature}
# Éclairage d'environnement par type de scène (cartes HDRI du poste) : sans lui, les rendus f3d sortaient
# sombres (luminance moyenne 52 contre 74 avec « city », 0 % de blanc pur dans les deux cas, 15/11/2026).
HDRI = {"interieur": "interior", "ville": "city", "nature": "courtyard"}
# Résolution des textures par type : un monde (ville + campagne + maisons) pesait 40 Mo d'images à 512 px.
RESOLUTION = {"interieur": 512, "ville": 256, "nature": 384}
VUES = {"interieur": ("plan", "aerienne_sud_est", "aerienne_nord_ouest"),
        "ville": ("plan", "aerienne_sud_est", "aerienne_nord_ouest", "rasante"),
        "nature": ("plan", "aerienne_sud_est", "rasante")}


def resume(programme: dict, mesures: dict, verdict: dict) -> str:
    type_scene = programme.get("type_scene")
    if type_scene == "interieur":
        pieces = ", ".join(f"{p['nom']} {p['surface']:.0f} m²" for p in mesures.get("pieces", []))
        texte = (f"Intérieur : {len(mesures.get('pieces', []))} pièces ({pieces}) ; "
                 f"{mesures.get('meubles_places', 0)}/{mesures.get('meubles_demandes', 0)} meubles posés")
    elif type_scene == "ville":
        texte = "Ville : " + ", ".join(f"{k} {v}" for k, v in mesures.items() if isinstance(v, (int, float)))[:300]
    else:
        texte = "Paysage : " + ", ".join(f"{k} {v}" for k, v in mesures.items() if isinstance(v, (int, float)))[:300]
    if verdict.get("verdict") == "accepte":
        return texte + " ; porte mesurée acceptée, rendus f3d vérifiés."
    return texte + " ; porte REFUSÉE : " + "; ".join(verdict.get("raisons") or [])[:400]


def composer(programme: dict, racine_run: str | Path, *, graine: int | None = None, fabrique=None,
             rendre: bool = True, audit: list | None = None, rendu: str = "realiste") -> dict[str, Any]:
    """Construit, exporte, rend et juge la scène d'un programme validé, dans le médium demandé (`rendu` :
    realiste | anime | toon, voir `materiaux.RENDUS`)."""
    debut = time.monotonic()
    racine_run = Path(racine_run)
    type_scene = programme.get("type_scene")
    if programme.get("source") != "llm" or type_scene not in CONSTRUCTEURS or not programme.get(type_scene):
        return {"ok": False, "error": f"programme de scène inutilisable : {programme.get('raison') or type_scene}",
                "programme": programme}
    graine = graine_de(programme.get("demande") or "") if graine is None else int(graine)
    fabrique = fabrique or fabrique_meubles()
    construit = CONSTRUCTEURS[type_scene](programme, graine, fabrique)
    scene: Scene = construit["scene"]
    scene.extras = {"programme": programme, "graine": graine, "depart": construit.get("depart"), "rendu": rendu}
    modele = racine_run / "modele"
    resolution = RESOLUTION.get(type_scene, 512)
    export = export_gltf.exporter(scene, modele / "scene_monde.glb", resolution=resolution, rendu=rendu)
    glb_maquette = None
    if construit.get("maquette") is not None:
        construit["maquette"].extras = scene.extras
        glb_maquette = str(export_gltf.exporter(construit["maquette"], modele / "scene_maquette.glb",
                                                resolution=resolution, rendu=rendu)["chemin"])
    rendus = None
    if rendre:
        cible = glb_maquette or export["chemin"]
        rendus = rendu_f3d.rendre_vues(cible, racine_run / "apercus", vues=VUES[type_scene], prefixe="scene",
                                   hdri=HDRI.get(type_scene))
    verdict = porte.juger(type_scene, construit["mesures"], export, rendus)
    # matière animée (jets des fontaines, émissions) : pistes ajoutées aux GLB écrits
    animations = None
    if construit.get("pistes"):
        from monde import animation_gltf
        animations = animation_gltf.injecter(export["chemin"], construit["pistes"], nom="monde_anime")
        if glb_maquette:
            animation_gltf.injecter(glb_maquette, construit["pistes"], nom="monde_anime")
    sortie = {"ok": verdict["verdict"] == "accepte", "type_scene": type_scene, "glb": export["chemin"],
              "animations": None if animations is None else {k: animations[k] for k in ("canaux", "absents", "duree_s")},
              "depart": construit.get("depart"), "rendu": rendu,
              "glb_maquette": glb_maquette, "planche": (rendus or {}).get("planche"), "export": export,
              "porte": verdict, "mesures": construit["mesures"], "programme": programme, "graine": graine,
              "duree_s": round(time.monotonic() - debut, 1)}
    sortie["resume"] = resume(programme, verdict.get("mesures") or construit["mesures"], verdict)
    journal = racine_run / "journal"
    journal.mkdir(parents=True, exist_ok=True)
    (journal / "scene_monde.json").write_text(json.dumps(sortie, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    sortie["journal"] = str(journal / "scene_monde.json")
    if sortie["ok"]:
        try:
            porte.avancer_cliquet(verdict)
        except Exception:  # noqa: BLE001 — un cliquet illisible n'empêche pas la livraison, il ne durcit pas
            pass
    if audit is not None:
        audit.append({"stage": "monde", "ok": sortie["ok"], "type_scene": type_scene,
                      "raisons": verdict.get("raisons"), "duree_s": sortie["duree_s"]})
    return sortie


def composer_depuis_demande(demande: str, racine_run: str | Path, *, contrat: dict | None = None,
                            programme: dict | None = None, graine: int | None = None, audit: list | None = None,
                            rendre: bool = True, interroger=None) -> dict[str, Any]:
    """Le point d'entrée du pipeline : lit le programme de la phrase puis compose la scène."""
    if programme is None:
        from monde.programme import lire_programme
        programme = lire_programme(demande, interroger=interroger)
    if programme.get("source") != "llm":
        sortie = {"ok": False, "error": f"programme de scène indisponible : {programme.get('raison')}",
                  "programme": programme}
        if audit is not None:
            audit.append({"stage": "monde", "ok": False, "error": sortie["error"]})
        return sortie
    # le médium vient de la lecture de la demande (« en version réaliste » → photo, « animé » → animation 3D,
    # « dessin animé » → toon) : c'est le style demandé qui décide, jamais le sujet
    from monde.materiaux import rendu_depuis_cible
    cible = ((contrat or {}).get("style") or {}).get("cible")
    return composer(programme, racine_run, graine=graine, rendre=rendre, audit=audit, rendu=rendu_depuis_cible(cible))


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Compose une scène entière (intérieur, ville, paysage) depuis une phrase")
    ap.add_argument("--demande", required=True)
    ap.add_argument("--sortie", required=True, help="dossier du run (modele/, apercus/, journal/)")
    ap.add_argument("--programme", default=None, help="programme JSON déjà lu (sinon le LLM le lit)")
    ap.add_argument("--graine", type=int, default=None)
    ap.add_argument("--sans-rendu", action="store_true")
    ap.add_argument("--cible", default=None, help="médium du contrat de demande : photo | cgi_3d | cel_2d | figurine")
    a = ap.parse_args()
    programme = json.loads(Path(a.programme).read_text(encoding="utf-8")) if a.programme else None
    contrat = {"style": {"cible": a.cible}} if a.cible else None
    res = composer_depuis_demande(a.demande, a.sortie, contrat=contrat, programme=programme, graine=a.graine,
                                  rendre=not a.sans_rendu)
    print(json.dumps({k: v for k, v in res.items() if k not in ("programme", "mesures", "export")},
                     ensure_ascii=False, default=str))
    return 0 if res.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
