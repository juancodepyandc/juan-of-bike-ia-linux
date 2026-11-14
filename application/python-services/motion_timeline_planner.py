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
    (r"\b(flammes?|feu|brasier|incendie|embrase\w*|braises?|fire|flames?|burning)\b", "smoke_fire"),
    (r"\b(fum[ée]es?|vapeurs?|brumes?|brouillard|smoke|steam|fog|mist)\b", "smoke_fire"),
    (r"\b(explosions?|explose\w*|d[ée]tonations?|blast|explodes?|exploding)\b", "smoke_fire"),
    (r"\b(eau|liquides?|pluie\s+battante|cascades?|vagues?\s+d'eau|water|liquid|"
     r"fontaines?|jets?\s+d'eau|geysers?|coule|coulent|couler|ruisselle\w*|s'[ée]coule\w*|"
     r"d[ée]verse\w*|fountains?|pours?\s+(?:water|liquid|out)|flowing\s+water|stream\s+of\s+water)\b", "fluid_flow"),
    (r"\b(oc[ée]ans?|mer|houle|ocean|sea|swell)\b", "ocean_surface"),
    (r"\b([ée]tincelles?|pluie|neige|poussi[eè]res?|d[ée]bris|sparks?|rain|snow|dust)\b", "particles"),
    (r"\b(sable|gravier|poudre|sand|gravel|powder)\b", "particles"),
    (r"\b(verre\s+bris\w*|se\s+brise\w*|[ée]clate\w*|fracasse\w*|shatters?|breaks?\s+apart)\b", "fracture_debris"),
    (r"\b(cape|manteau|drapeau|voile|tissu|cloak|flag|cloth)\b", "cloth_drape"),
    (r"\b(cheveux|crini[eè]re|fourrure|hair|fur|mane)\b", "hair_fur"),
    (r"\b(rouille|corrosion|oxyd\w*|gel|givre|rust|freez\w*)\b", "chemistry"),
    (r"\b(cristal|prisme|reflets?|r[ée]fraction|crystal|prism|refract\w*)\b", "optics"),
    (r"\b(tornades?|vortex|tourbillons?|cyclones?|typhons?|whirlwinds?|tornado\w*|whirlpools?)\b", "vortex_tornado"),
    (r"\b(essaims?|nu[ée]es?|vol[ée]es?\s+d|bancs?\s+de|papillons|abeilles|oiseaux\s+en\s+vol|"
     r"swarms?|flocks?|schools?\s+of|boids)\b", "swarm_flock"),
    (r"\b((flotte|flottant|d[ée]rive|tangue)\b.*(eau|mer|oc[ée]an|lac|rivi[eè]re|vague)|"
     r"bou[ée]es?|radeaux?|barques?)\b", "buoyancy_float"),
    (r"\b([ée]clairs?|foudre|arcs?\s+[ée]lectriques?|lightning|plasma|[ée]nergie\s+[ée]lectrique)\b", "plasma"),
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
