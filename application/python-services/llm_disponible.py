#!/usr/bin/env python3
"""Resout un nom de modele Ollama vers un modele REELLEMENT installe.

Pourquoi ce module existe. Plusieurs sous-systemes appelaient un modele
absent de la machine, chacun echouait en silence, et la panne remontait
transformee en « pas de resultat » plutot qu'en « modele introuvable » :

  - `_character_visual_desc` demandait `devstral:latest` -> Ollama repond
    {"error":"model not found"}, l'exception est avalee, la description du
    personnage revient VIDE. Or toute la chaine de fidelite en depend: les
    requetes web sont enrichies avec elle, le juge d'image la recoit comme
    critere visuel, et la verification d'identite ne s'active que si elle
    existe. Resultat mesure le 04/09: une photo d'avion des annees 30
    acceptee comme reference pour « Caine ».
  - `material_intel_classifier` et `motion_intent_classifier` demandaient
    `gemma3:27b`, absent lui aussi -> repli `fallback:regex`, d'ou des zones
    de matiere generiques (eau turquoise sur un parfum ambre).

Un modele absent n'est pas une opinion, c'est un fait verifiable. On demande
donc la liste a Ollama, on resout, et on le DIT quand on doit substituer.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request

_BASE = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
_CACHE: list | None = None


def modeles_installes(force: bool = False) -> list:
    """Liste des modeles presents sur la machine (mise en cache)."""
    global _CACHE
    if _CACHE is not None and not force:
        return _CACHE
    try:
        with urllib.request.urlopen(_BASE + "/api/tags", timeout=8) as r:
            _CACHE = [m.get("name", "") for m in json.loads(r.read().decode()).get("models", [])]
    except Exception:  # noqa: BLE001 — Ollama injoignable: on ne bloque pas
        _CACHE = []
    return _CACHE


def resoudre_modele(souhaite: str, role: str = "texte", bavard: bool = True) -> str:
    """Rend un modele installe. `souhaite` d'abord, sinon le meilleur substitut.

    `role` oriente le substitut: "vision" pour juger une image, "texte" sinon.
    Rend `souhaite` inchange si la liste est indisponible — mieux vaut tenter
    que refuser de travailler.
    """
    dispo = modeles_installes()
    if not dispo:
        return souhaite
    if souhaite in dispo:
        return souhaite
    base = souhaite.split(":")[0]
    for m in dispo:                       # meme famille, autre etiquette
        if m.split(":")[0] == base:
            _dire(souhaite, m, role, bavard)
            return m
    # substitut par role, du plus capable au plus leger
    prefs = (["qwen3-vl:30b", "qwen3-vl:8b"] if role == "vision"
             else ["qwen3-coder:30b", "orcarouter/Qwen3.8-27B-Uncensored:latest",
                   "deepseek-r1:32b", "qwen3-coder-next:q4_K_M"])
    for p in prefs:
        if p in dispo:
            _dire(souhaite, p, role, bavard)
            return p
    for m in dispo:                       # dernier recours: tout sauf l'embedding
        if "embed" not in m:
            _dire(souhaite, m, role, bavard)
            return m
    return souhaite


def _dire(souhaite: str, retenu: str, role: str, bavard: bool) -> None:
    if bavard:
        print("PROGRESS:llm:modele '%s' absent — remplace par '%s' (%s). "
              "Sans ce message l'appel echouait en silence."
              % (souhaite, retenu, role), flush=True)


def main() -> int:
    dispo = modeles_installes()
    print("modeles installes (%d):" % len(dispo))
    for m in dispo:
        print("  ", m)
    print()
    for souhaite, role in (("devstral:latest", "texte"), ("gemma3:27b", "texte"),
                           ("qwen3-vl:8b", "vision"), ("qwen3-coder:30b", "texte")):
        print("  %-38s -> %s" % (souhaite, resoudre_modele(souhaite, role, bavard=False)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
