#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""motion_timeline_planner — decoupe une demande en PISTES simultanees.

Le probleme qu'il resout: "un guerrier qui attaque avec une flamme" produisait
l'attaque et jetait la flamme. Une seule categorie etait choisie pour toute la
phrase, alors que la demande en contient DEUX — un corps qui bouge et un
phenomene physique — qui vivent sur des supports differents (le personnage
tient dans un GLB, le feu non).

Methode volontairement DETERMINISTE: on coupe sur les liens de la langue
("avec", "en", "puis", "pendant que", "sous", "dans"), on classe chaque
fragment, et on rend une frise. Aucun modele de langue n'invente ici de valeur
physique — il n'y a rien a halluciner, seulement des morceaux de phrase a
ranger.

Usage:
    python motion_timeline_planner.py --prompt "un guerrier attaque avec une flamme"
"""

from __future__ import annotations

import argparse
import json
import re

# Marqueurs de SIMULTANEITE (les deux pistes tournent ensemble) et de
# SUCCESSION (l'une puis l'autre). La distinction change la frise, pas les
# pistes elles-memes.
_SIMULTANE = r"(?:\s+avec\s+|\s+en\s+train\s+de\s+|\s+pendant\s+que\s+|\s+tout\s+en\s+|\s+sous\s+|\s+dans\s+|\s+entour[ée]\s+de\s+|\s+couvert\s+de\s+|\s+en\s+feu\b|\s+with\s+|\s+while\s+|\s+surrounded\s+by\s+)"
_SUCCESSIF = r"(?:\s+puis\s+|\s+ensuite\s+|\s+apr[eè]s\s+quoi\s+|\s+then\s+|\s+and\s+then\s+)"

# Un fragment appartient a une piste EFFET s'il nomme un phenomene physique.
# La liste suit les categories du classifieur, pas des mots choisis au hasard.
_EFFETS = (
    (r"(flamme|feu|brasier|incendie|embras|braise|fire|flame|burning)", "smoke_fire"),
    (r"(fum[ée]e|vapeur|brume|brouillard|smoke|steam|fog|mist)", "smoke_fire"),
    (r"(explosion|explose|d[ée]tonation|blast|explode)", "smoke_fire"),
    (r"(eau|liquide|pluie\s+battante|cascade|vague|water|liquid|"
     r"fontaine|jet\s+d'eau|geyser|coule|couler|ruissel|s'[ée]coule|"
     r"d[ée]verse|fountain|pour|flow|stream)", "fluid_flow"),
    (r"(oc[ée]an|mer\b|houle|ocean|sea\b|swell)", "ocean_surface"),
    (r"([ée]tincelle|pluie|neige|poussi[eè]re|d[ée]bris|spark|rain|snow|dust)", "particles"),
    (r"(sable|terre|gravier|poudre|sand|gravel|powder)", "particles"),
    (r"(verre\s+bris|se\s+brise|[ée]clate|fracasse|shatter|break\s+apart)", "fracture_debris"),
    (r"(cape|manteau|drapeau|voile|tissu|cloak|cape|flag|cloth)", "cloth_drape"),
    (r"(cheveux|criniere|crini[eè]re|fourrure|hair|fur|mane)", "hair_fur"),
    (r"(rouille|corrosion|oxyd|gel\b|givre|rust|freez)", "chemistry"),
    (r"(cristal|prisme|reflet|r[ée]fraction|crystal|prism|refract)", "optics"),
    (r"(tornade|vortex|tourbillon|cyclone|typhon|whirlwind|tornado|whirlpool)", "vortex_tornado"),
    (r"(essaim|nu[ée]e|vol[ée]e\s+d|banc\s+de|papillons|abeilles|oiseaux\s+en\s+vol|"
     r"swarm|flock|school\s+of|boids)", "swarm_flock"),
    (r"((flotte|flottant|d[ée]rive|tangue)\b.*(eau|mer|oc[ée]an|lac|rivi[eè]re|vague)|"
     r"bou[ée]e|radeau|barque)", "buoyancy_float"),
    (r"([ée]clair|foudre|arc\s+[ée]lectrique|lightning|plasma|[ée]nergie\s+[ée]lectrique)", "plasma"),
)

# Un fragment appartient a la piste CORPS s'il decrit un geste. On ne cherche
# pas a etre exhaustif ici: le parseur de mouvement et HY-Motion s'en chargent
# ensuite. Il s'agit seulement de savoir OU envoyer le fragment.
_CORPS = re.compile(
    r"(court|courir|marche|marcher|saute|sauter|tombe|tomber|attaque|attaquer|"
    r"frappe|frapper|esquive|esquiver|pare|parer|se\s+bat|combat|danse|danser|"
    r"s'assoit|assis|s'agenouille|rampe|nage|nager|grimpe|grimper|pousse|tire|"
    r"lance|lancer|pivote|tourne|roule|se\s+rue|charge|salue|s'incline|"
    r"run|walk|jump|fall|attack|strike|punch|kick|dodge|parry|fight|dance|"
    r"sit|kneel|crawl|swim|climb|push|pull|throw|spin|roll)", re.I)


def _classe_effet(fragment: str) -> str | None:
    f = fragment.lower()
    for motif, categorie in _EFFETS:
        if re.search(motif, f, re.I):
            return categorie
    return None


def plan(prompt: str, duration_s: float | None = None) -> dict:
    texte = (prompt or "").strip()
    if not texte:
        return {"schema": "aurora.motion-timeline.v1", "tracks": [], "duree_s": 0.0}

    # 1) succession: chaque segment occupe sa part de la duree
    segments = [s for s in re.split(_SUCCESSIF, texte, flags=re.I) if s.strip()]
    tracks: list[dict] = []
    n = max(len(segments), 1)
    if duration_s is None:
        # duree AUTO derivee du decoupage grammatical: ~3 s par action
        # enchainee. La constante 4.0 tronquait toute sequence multi-phases
        # (l'accroupi+frappe+bond du yeti tenait dans la fenetre d'UN geste).
        duration_s = min(30.0, max(4.0, 3.0 * n))
    for i, seg in enumerate(segments):
        t0 = duration_s * i / n
        t1 = duration_s * (i + 1) / n
        # 2) simultaneite a l'interieur d'un segment: les morceaux partagent la
        #    MEME fenetre de temps, ils ne se suivent pas.
        parts = [p for p in re.split(_SIMULTANE, seg, flags=re.I) if p and p.strip()]
        if not parts:
            parts = [seg]
        # le "en feu" de "il court en feu" est coupe par le separateur: on le
        # rattrape en cherchant l'effet dans le segment ENTIER aussi.
        effet_global = _classe_effet(seg)
        vus = set()
        for part in parts:
            frag = part.strip(" ,.;")
            if not frag:
                continue
            cat = _classe_effet(frag)
            if cat:
                if cat in vus:
                    continue
                vus.add(cat)
                tracks.append({"piste": "effet", "categorie": cat,
                               "texte": frag, "t0": round(t0, 2), "t1": round(t1, 2)})
            elif _CORPS.search(frag):
                tracks.append({"piste": "corps", "categorie": "creature_organic",
                               "texte": frag, "t0": round(t0, 2), "t1": round(t1, 2)})
            else:
                tracks.append({"piste": "sujet", "categorie": None,
                               "texte": frag, "t0": round(t0, 2), "t1": round(t1, 2)})
        if effet_global and effet_global not in vus:
            tracks.append({"piste": "effet", "categorie": effet_global,
                           "texte": seg.strip(), "t0": round(t0, 2), "t1": round(t1, 2)})

    corps = [t for t in tracks if t["piste"] == "corps"]
    effets = [t for t in tracks if t["piste"] == "effet"]
    return {
        "schema": "aurora.motion-timeline.v1",
        "prompt": texte,
        "duree_s": duration_s,
        "tracks": tracks,
        "composite": bool(corps and effets),
        "resume": "%d piste(s) corps, %d piste(s) effet, %d segment(s)"
                  % (len(corps), len(effets), n),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--duration", type=float, default=4.0)
    a = ap.parse_args()
    print(json.dumps(plan(a.prompt, a.duration), ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
