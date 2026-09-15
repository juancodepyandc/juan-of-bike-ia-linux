#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""domain_router — décompose une demande en ACTEURS typés par la PHYSIQUE.

Verrou n°1 leve (27/07): `motion_intent_classifier` choisit UNE categorie
parmi 39 pour toute la demande. Un sujet multi-domaine ("la chute d'eau fait
tourner la roue qui entraine la meule, la lanterne vacille, la banniere
ondule") est donc STRUCTURELLEMENT impossible: un seul solveur est appele et
tout le reste est perdu en silence.

Ici on ne classe pas le SUJET, on decrit le COMPORTEMENT DE LA MATIERE sur
des axes orthogonaux enumeres. Aucune liste de sujets: un objet jamais vu ne
"matche" pas un mot, il tombe dans une CELLULE de la matrice.

  A1 matiere     : rigide | articule | deformable_constant | deformable_variable
                   | granulaire | liquide | gazeux | champ
  A2 origine     : interne | contrainte | champ_externe | phase | aucune
  A4 topologie   : constante | variable
  A5 regime      : cyclique | transitoire | stationnaire
  A6 hors_geom   : aucun | emission | materiau | optique
  A7 portee      : sujet | environnant
  A8 couplages   : entraine | met_en_mouvement | emet | collisionne | attache_a

La table de decision (deterministe) fait le reste: solveur + representation
glTF + famille de metriques pour la porte de qualite.

Usage:
    python domain_router.py --prompt "..." [--kind character]
Sortie: aurora.scene-plan.v1
"""
from __future__ import annotations

import argparse
import json
import os
import re
import urllib.request

OLLAMA = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
MODEL = os.environ.get("AURORA_MOTION_LLM", "orcarouter/Qwen3.8-27B-Uncensored")

SCHEMA_ID = "aurora.scene-plan.v1"

# Raccord vers les bakers EXISTANTS (motion_intent_classifier.CATEGORIES):
# le routeur decide QUOI animer, ces categories disent COMMENT le baker le
# fait. Sans ce pont, le plan de scene restait une intention non executee.
SOLVEUR_CATEGORIE = {
    "mecanisme": "articulated_rig",
    "rbd": "rigid_bodies",
    "houdini_flip": "fluid_flow",
    "houdini_grains": "granular",
    "houdini_pyro": "smoke_fire",
    "tissu": "cloth_drape",
    "emissif": "led_emission",
    "materiau_anime": "thermal_melt",
    "rig_squelette": "creature_organic",
    "champ": "led_emission",
}

# --- table de decision: (predicat) -> (solveur, representation, famille) ----
# R1 squelette+skin | R2 noeuds rigides | R3 morph targets
# R4 sequence de meshes | R6 animation de materiau (pointer) | R8 hors-GLB
TABLE = [
    (lambda a: a["matiere"] == "liquide",
     ("houdini_flip", "R4_sequence", "fluide")),
    (lambda a: a["matiere"] == "granulaire",
     ("houdini_grains", "R4_sequence", "granulaire")),
    (lambda a: a["matiere"] == "gazeux",
     ("houdini_pyro", "R8_hors_glb", "volume")),
    (lambda a: a["matiere"] == "rigide" and a["origine"] in ("contrainte",
                                                             "interne"),
     ("mecanisme", "R2_noeuds_rigides", "mecanisme")),
    (lambda a: a["matiere"] == "rigide" and a["origine"] == "champ_externe",
     ("rbd", "R2_noeuds_rigides", "rigides")),
    (lambda a: a["matiere"] == "articule",
     ("rig_squelette", "R1_squelette", "creature")),
    (lambda a: a["matiere"] == "deformable_constant",
     ("tissu", "R3_morph", "tissu")),
    (lambda a: a["matiere"] == "deformable_variable",
     ("houdini_flip", "R4_sequence", "fluide")),
    (lambda a: a["hors_geom"] == "emission",
     ("emissif", "R6_materiau", "lumineux")),
    (lambda a: a["hors_geom"] == "materiau",
     ("materiau_anime", "R6_materiau", "materiau")),
    (lambda a: a["matiere"] == "champ",
     ("champ", "R6_materiau", "champ")),
]

AXES_DEFAUT = {
    "matiere": "rigide", "origine": "aucune", "cohesion": "cohesif",
    "topologie": "constante", "regime": "cyclique", "hors_geom": "aucun",
    "portee": "sujet",
}

# Repli SANS LLM: mots de COMPORTEMENT/MATIERE (jamais de nom de sujet).
_MOTS = [
    ("liquide", r"\b(eau|water|liquide|liquid|couler?|s'?[ée]coule|flots?|"
                r"cascade|chute d'eau|jet|fontaine|vague|onde de mer|pluie|"
                r"rain|verse|deverse|ruissel)"),
    ("granulaire", r"\b(sable|sand|farine|flour|poudre|powder|grains?|"
                   r"gravier|gravel|billes?|cendres?|ash|neige qui tombe|"
                   r"s'?amoncel|tas de)"),
    ("gazeux", r"\b(fum[ée]e|smoke|vapeur|steam|brume|fog|nuage|cloud|gaz|"
               r"souffle de|explosion)"),
    ("deformable_constant", r"\b(tissu|cloth|toile|banni[èe]re|drapeau|flag|"
                            r"rideau|cape|voile|corde|rope|cha[îi]ne souple|"
                            r"ondule|flotte au vent|claque au vent)"),
    ("articule", r"\b(marche|court|danse|saute|bondit|s'?accroupit|frappe|"
                 r"agite|walks?|runs?|jumps?|dances?|attaque|se penche|"
                 r"tourne la t[êe]te|respire)"),
    ("rigide", r"\b(tourne|rotation|pivote|engrenages?|gears?|roues?|wheels?|"
               r"pistons?|bielles?|meule|h[ée]lice|rotor|turbine|essuie|"
               r"balancier|pendule|axe|manivelle|spins?|rotates?)"),
]
_EMISSION = (r"\b(lumi[èe]re|lumineu|light|lampe|lanterne|led|n[ée]on|"
             r"[ée]claire|brille|glow|luit|flamme|braise|clignote|vacille|"
             r"pulse|phare|projecteur)")
_CONTRAINTE = (r"\b(entra[îi]ne|fait tourner|actionne|met en mouvement|"
               r"transmet|engr[èe]ne|couple|relie|drives?|turns the)")
_CHAMP = (r"\b(vent|wind|gravit|tombe|chute|courant|souffle|pouss[ée]e|"
          r"pesanteur|s'?[ée]croule)")


def _llm(prompt: str, timeout_s: int = 120) -> str:
    body = json.dumps({"model": MODEL, "prompt": prompt, "stream": False,
                       "format": "json", "options": {"temperature": 0.1},
                       "keep_alive": 0}).encode()
    req = urllib.request.Request(OLLAMA + "/api/generate", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout_s) as r:
        return json.loads(r.read().decode()).get("response", "")


_INSTRUCTION = """You decompose a 3D generation request into ACTORS described
by the PHYSICAL BEHAVIOUR of their matter. You never name a solver and never
invent numbers. Answer ONLY with JSON.

For EACH thing in the request that moves, changes or emits, output one actor:
{
 "id": "<short name>",
 "matiere": "rigide|articule|deformable_constant|deformable_variable|granulaire|liquide|gazeux|champ",
 "origine": "interne|contrainte|champ_externe|phase|aucune",
 "cohesion": "cohesif|fragmentable|non_cohesif",
 "topologie": "constante|variable",
 "regime": "cyclique|transitoire|stationnaire",
 "hors_geom": "aucun|emission|materiau|optique",
 "portee": "sujet|environnant",
 "texte": "<the words of the request this actor comes from>"
}

Meaning of the axes:
- matiere: how matter is conserved. A gear/wheel/piston is "rigide". A living
  body that bends at joints is "articule". Cloth/rope keeps its topology ->
  "deformable_constant". Water/foam changes topology -> "liquide". Sand,
  flour, powder -> "granulaire". Smoke/steam -> "gazeux".
- origine: what causes the motion. "interne" = the thing moves itself
  (muscle, motor). "contrainte" = it is driven by another part (gear train,
  belt, axle). "champ_externe" = gravity, wind, a current push it.
- hors_geom: what changes that is NOT geometry. A lamp, flame, LED, glow ->
  "emission". Rust/frost/ember spreading -> "materiau".

Also output the couplings between actors:
"couplages": [{"type":"entraine|met_en_mouvement|emet|collisionne|attache_a",
               "de":"<actor id>","vers":"<actor id>"}]

Output: {"acteurs": [...], "couplages": [...]}"""


def _repli_regex(prompt: str, kind: str | None = None) -> dict:
    """Decoupe par comportement, sans LLM. Sert de filet et de verification."""
    texte = (prompt or "").lower()
    acteurs = []
    vus = set()
    for matiere, motif in _MOTS:
        if not re.search(motif, texte, re.I):
            continue
        if matiere in vus:
            continue
        vus.add(matiere)
        origine = "aucune"
        if matiere in ("liquide", "granulaire", "gazeux"):
            origine = "champ_externe"
        elif matiere == "articule":
            origine = "interne"
        elif matiere == "rigide":
            origine = ("contrainte" if re.search(_CONTRAINTE, texte, re.I)
                       else "interne")
        elif matiere == "deformable_constant":
            origine = "champ_externe"
        acteurs.append({**AXES_DEFAUT, "id": matiere, "matiere": matiere,
                        "origine": origine,
                        "topologie": ("variable" if matiere in
                                      ("liquide", "granulaire", "gazeux")
                                      else "constante"),
                        "portee": ("environnant" if matiere in
                                   ("liquide", "gazeux") else "sujet"),
                        "texte": prompt[:120]})
    if re.search(_EMISSION, texte, re.I):
        acteurs.append({**AXES_DEFAUT, "id": "emission",
                        "hors_geom": "emission", "origine": "phase",
                        "texte": prompt[:120]})
    if not acteurs and kind:
        acteurs.append({**AXES_DEFAUT, "id": "sujet",
                        "matiere": ("articule" if str(kind).lower() in
                                    ("character", "creature", "human",
                                     "humanoid", "animal") else "rigide"),
                        "origine": "interne", "texte": prompt[:120]})
    return {"acteurs": acteurs, "couplages": [], "source": "regex"}


def _router(acteur: dict) -> dict:
    a = {**AXES_DEFAUT, **{k: v for k, v in acteur.items() if v}}
    for predicat, (solveur, repr_, famille) in TABLE:
        try:
            if predicat(a):
                return {"solveur": solveur, "representation": repr_,
                        "famille_metriques": famille}
        except Exception:  # noqa: BLE001
            continue
    return {"solveur": "aucun", "representation": "R0_statique",
            "famille_metriques": "statique"}


def plan(prompt: str, kind: str | None = None, use_llm: bool = True) -> dict:
    """Rend un aurora.scene-plan.v1: acteurs typés + solveur/representation."""
    brut = None
    if use_llm and os.environ.get("AURORA_DOMAIN_LLM", "1") == "1":
        try:
            brut = json.loads(_llm(
                "%s\n\nRequest (French or English): %r%s"
                % (_INSTRUCTION, prompt,
                   ("\nSubject kind: " + kind) if kind else "")))
        except Exception:  # noqa: BLE001
            brut = None
    acteurs = []
    if isinstance(brut, dict) and isinstance(brut.get("acteurs"), list):
        for a in brut["acteurs"]:
            if isinstance(a, dict) and a.get("matiere"):
                acteurs.append({**AXES_DEFAUT, **a})
    source = "llm" if acteurs else "regex"
    repli = _repli_regex(prompt, kind)
    if not acteurs:
        acteurs = repli["acteurs"]
    else:
        # FUSION: le repli attrape ce que le LLM oublie (un domaine manquant
        # est une perte SILENCIEUSE de tout un pan de la demande).
        # FUSION PAR DOMAINE, pas par matiere (27/07): le LLM est instable
        # (7 acteurs sur un run, 3 sur le suivant, MEME phrase). Le repli
        # regex est deterministe: tout domaine qu'il detecte et que le LLM a
        # oublie est AJOUTE. Sinon la farine, la banniere et la lanterne
        # disparaissaient selon l'humeur du modele.
        def _cle_dom(a):
            return (a.get("matiere"), a.get("hors_geom") == "emission")
        deja = {_cle_dom(a) for a in acteurs}
        for a in repli["acteurs"]:
            if _cle_dom(a) not in deja:
                acteurs.append(a)
                deja.add(_cle_dom(a))
        source = "llm+regex"
    for a in acteurs:
        a.update(_router(a))
        a["categorie_baker"] = SOLVEUR_CATEGORIE.get(a.get("solveur"))
        # UN ACTEUR PEUT CUMULER: une lanterne BOUGE et EMET. La table rend un
        # solveur de mouvement; l'aspect hors-geometrie s'AJOUTE au lieu de se
        # faire ecraser (sinon la lumiere disparait en silence).
        sup = []
        if a.get("hors_geom") == "emission" and a["solveur"] != "emissif":
            sup.append({"solveur": "emissif", "representation": "R6_materiau",
                        "famille_metriques": "lumineux"})
        elif a.get("hors_geom") == "materiau" and a["solveur"] != "materiau_anime":
            sup.append({"solveur": "materiau_anime",
                        "representation": "R6_materiau",
                        "famille_metriques": "materiau"})
        if sup:
            a["solveurs_supplementaires"] = sup
    couplages = [c for c in (brut or {}).get("couplages", [])
                 if isinstance(c, dict) and c.get("de") and c.get("vers")]
    return {"schema": SCHEMA_ID, "prompt": prompt, "source": source,
            "acteurs": acteurs, "couplages": couplages,
            "domaines": sorted({a["famille_metriques"] for a in acteurs}
                               | {s["famille_metriques"] for a in acteurs
                                  for s in a.get("solveurs_supplementaires", [])}),
            "multi_domaine": len({a["famille_metriques"] for a in acteurs}) > 1}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--kind", default=None)
    ap.add_argument("--no-llm", action="store_true")
    a = ap.parse_args()
    print(json.dumps(plan(a.prompt, a.kind, use_llm=not a.no_llm),
                     ensure_ascii=False, indent=1))
