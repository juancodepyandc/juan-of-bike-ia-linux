"""Porte mesurée d'une scène du moteur « monde » : elle accepte ou refuse, et dit pourquoi.

Elle ne juge que des MESURES : contraintes de disposition comptées par le solveur (chevauchements,
objets hors pièce, portes ou fenêtres bloquées, objets inaccessibles), couverture du programme (pièces et
meubles demandés réellement présents), gabarit du fichier, et rendus f3d (une image vide ou surexposée
n'est pas une scène livrable). Un compte « dur » doit valoir zéro ; une absence de mesure n'est jamais un
succès.

Les seuils forment une famille de cliquet SÉPARÉE (`modele/renforce/judge_ratchet_monde.json`, même
mécanique que `agi_core.judge_ratchet`) : ils vont de la base vers le plafond, jamais en arrière, et
n'avancent que sur une livraison acceptée. Un cliquet illisible donne les seuils les plus stricts.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import numpy as np

SCHEMA = "aurora.porte-monde.v1"
RACINE = Path(__file__).resolve().parents[3]
CHEMIN_CLIQUET = RACINE / "modele" / "renforce" / "judge_ratchet_monde.json"
PAS_SATURATION = 12

# (base, plafond) : le pas du cliquet interpole de l'un à l'autre.
BORNES: dict[str, tuple[float, float]] = {
    "part_places_min": (0.85, 1.0),          # meubles demandés réellement posés (intérieur)
    "blanc_pur_max": (0.01, 0.002),          # part de pixels #FFFFFF dans un rendu f3d
    "contenu_plan_min": (0.10, 0.25),        # part de l'image de plan couverte par la scène
    "triangles_max": (3_000_000, 1_500_000),
    "ecart_zones_max": (0.15, 0.08),         # écart entre parts de zones demandées et obtenues (ville)
}
# Comptes qui doivent valoir zéro, quand la mesure existe pour ce type de scène.
DURS: dict[str, str] = {
    "chevauchements": "meubles qui se chevauchent",
    "hors_piece": "meubles hors de leur pièce",
    "portes_bloquees": "portes bloquées",
    "fenetres_bloquees": "fenêtres masquées par un meuble haut",
    "inaccessibles": "meubles inaccessibles depuis une porte",
    "pieces_isolees": "pièces sans accès depuis l'entrée",
    "fenetres_interieures": "fenêtres percées dans un mur intérieur",
    "violations_plan": "règles du plan non tenues",
    "degagements_occupes": "dégagements de meubles occupés",
    "batiments_sur_voirie": "bâtiments empiétant sur la voirie",
    "batiments_chevauchants": "bâtiments qui se chevauchent",
    "vegetation_dans_eau": "végétation posée dans l'eau",
    "objets_sur_chaussee": "arbres ou mobilier sur la chaussée",
}
MESURES_REQUISES = {
    "interieur": ("chevauchements", "hors_piece", "portes_bloquees", "inaccessibles", "pieces_isolees",
                  "meubles_demandes", "meubles_places"),
    "ville": ("batiments_sur_voirie", "batiments_chevauchants", "objets_sur_chaussee"),
    "nature": ("vegetation_dans_eau",),
}


def seuils_au_pas(pas: int) -> dict[str, Any]:
    pas = max(0, int(pas))
    t = min(1.0, pas / float(PAS_SATURATION))
    seuils = {cle: lo + (hi - lo) * t for cle, (lo, hi) in BORNES.items()}
    seuils["triangles_max"] = int(round(seuils["triangles_max"]))
    seuils["pas"] = pas
    return seuils


def cliquet(*, avancer: bool = False, chemin: str | Path | None = None) -> dict[str, Any]:
    if str(RACINE) not in sys.path:
        sys.path.append(str(RACINE))
    from agi_core.judge_ratchet import BASE_LEVEL, DEFAULT_STATE, judge_ratchet
    cible = Path(chemin) if chemin is not None else CHEMIN_CLIQUET
    if cible.resolve() == Path(DEFAULT_STATE).resolve():
        raise ValueError("la famille « monde » ne lit jamais l'état global du cliquet")
    etat = judge_ratchet(advance=bool(avancer), path=cible)
    pas = int(etat["ratchet_level"]) - int(BASE_LEVEL)
    return {"famille": "monde", "chemin": str(cible), "ratchet_level": int(etat["ratchet_level"]), "pas": pas,
            "seuils": seuils_au_pas(pas)}


def avancer_cliquet(verdict: dict[str, Any], *, chemin: str | Path | None = None) -> dict[str, Any]:
    """+1 par livraison acceptée, jamais de relâchement ; un refus laisse le niveau tel quel."""
    valide = isinstance(verdict, dict) and verdict.get("schema") == SCHEMA and verdict.get("verdict") == "accepte"
    etat = cliquet(avancer=valide, chemin=chemin)
    etat["avance"] = valide
    return etat


def _seuils(seuils: dict | None, chemin_cliquet: str | Path | None) -> dict[str, Any]:
    if seuils is not None:
        sortie = dict(seuils_au_pas(0))
        for cle, (lo, hi) in BORNES.items():
            if cle in seuils:
                # ramené entre la base (la plus lâche) et le plafond (la plus stricte), dans les deux sens
                sortie[cle] = min(max(lo, hi), max(min(lo, hi), float(seuils[cle])))
        sortie["source"] = "injecte"
        return sortie
    try:
        etat = cliquet(chemin=chemin_cliquet)
        return {**etat["seuils"], "source": "cliquet", "ratchet_level": etat["ratchet_level"]}
    except Exception as exc:  # noqa: BLE001 — illisible : les seuils les plus stricts, et on le dit
        return {**seuils_au_pas(PAS_SATURATION), "source": f"plafond : cliquet illisible ({type(exc).__name__})"}


def contenu_image(png: str | Path) -> float:
    """Part de l'image qui n'est pas le fond (couleur du coin) : une scène absente donne ~0."""
    from PIL import Image
    with Image.open(png) as image:
        a = np.asarray(image.convert("RGB"), dtype=np.int32)
    fond = a[2, 2]
    return float((np.abs(a - fond).sum(axis=2) > 24).mean())


def juger(type_scene: str, mesures: dict[str, Any], export: dict[str, Any] | None,
          rendus: dict[str, Any] | None, *, seuils: dict | None = None,
          chemin_cliquet: str | Path | None = None) -> dict[str, Any]:
    s = _seuils(seuils, chemin_cliquet)
    raisons: list[str] = []
    manquantes = [m for m in MESURES_REQUISES.get(type_scene, ()) if m not in mesures]
    if manquantes:
        raisons.append("mesures absentes (une absence n'est pas un succès) : " + ", ".join(manquantes))
    for cle, libelle in DURS.items():
        valeur = mesures.get(cle)
        if valeur is None:
            continue
        n = len(valeur) if isinstance(valeur, (list, tuple, set, dict)) else int(valeur)
        if n:
            raisons.append(f"{n} {libelle}")
    if type_scene == "interieur" and "meubles_demandes" in mesures:
        demandes = max(1, int(mesures["meubles_demandes"]))
        part = int(mesures.get("meubles_places", 0)) / demandes
        if part < s["part_places_min"]:
            raisons.append(f"meubles posés {part:.0%} < {s['part_places_min']:.0%} des meubles demandés")
    for piece in mesures.get("pieces_manquantes") or []:
        raisons.append(f"pièce demandée absente du plan : {piece}")
    if type_scene == "ville" and mesures.get("ecart_zones") is not None:
        if float(mesures["ecart_zones"]) > s["ecart_zones_max"]:
            raisons.append(f"parts de zones écartées de {float(mesures['ecart_zones']):.0%} > {s['ecart_zones_max']:.0%}")
    if not export or not export.get("octets"):
        raisons.append("fichier glTF absent ou vide")
    elif int(export.get("triangles", 0)) > s["triangles_max"]:
        raisons.append(f"{export['triangles']} triangles > {s['triangles_max']}")
    if not rendus or not rendus.get("rendus"):
        raisons.append("aucun rendu f3d : la scène n'a pas été vérifiée")
    else:
        echecs = [r.get("vue") for r in rendus["rendus"] if not r.get("ok")]
        if echecs:
            raisons.append("rendu f3d impossible : " + ", ".join(map(str, echecs)))
        blanc = max((float(r.get("part_blanc_pur") or 0.0) for r in rendus["rendus"] if r.get("ok")), default=0.0)
        if blanc > s["blanc_pur_max"]:
            raisons.append(f"surexposition f3d : {blanc:.2%} de blanc pur > {s['blanc_pur_max']:.2%}")
        plan = next((r for r in rendus["rendus"] if r.get("ok") and r.get("vue") == "plan"), None)
        if plan is not None:
            contenu = contenu_image(plan["png"])
            mesures = {**mesures, "contenu_plan": round(contenu, 4)}
            if contenu < s["contenu_plan_min"]:
                raisons.append(f"plan f3d presque vide : {contenu:.0%} de l'image < {s['contenu_plan_min']:.0%}")
    return {"schema": SCHEMA, "type_scene": type_scene, "verdict": "refuse" if raisons else "accepte",
            "raisons": raisons, "mesures": mesures, "seuils": s}
