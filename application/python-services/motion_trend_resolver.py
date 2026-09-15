#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""motion_trend_resolver — comprend un mouvement NOMME sans liste codee en dur.

Le probleme: "fais le 67", "danse la macarena", "fais le dab" ne sont pas des
verbes de geste — ce sont des NOMS de mouvements (trends, danses, memes). Le
parseur de prefixages n'y voit rien, et le generateur texte->mouvement ne
connait pas les noms culturels: il connait la BIOMECANIQUE ("both palms up at
chest height, alternately raised and lowered").

La resolution se fait donc en deux temps, sans aucune liste de trends:
  1. (best-effort) recherche web DuckDuckGo pour recuperer des bribes de
     description — couvre les trends POSTERIEURS aux connaissances du modele;
  2. le LLM local decide si le prompt reference un mouvement nomme, et si oui
     le traduit en description biomecanique anglaise precise (postures,
     trajectoires, tempo, repetitions) prete pour le generateur.

Rien n'est memorise en dur: un trend inconnu aujourd'hui sera couvert par la
recherche web, ou echouera EXPLICITEMENT (jamais un geste invente a la place).

Usage:
    python motion_trend_resolver.py --prompt "fais le 67"
Sortie JSON: {named_move: bool, name: str, description_en: str, source: str}
"""

from __future__ import annotations

import argparse
import json
import os
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

OLLAMA = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
MODEL = os.environ.get("AURORA_MOTION_LLM", "orcarouter/Qwen3.8-27B-Uncensored")

# MEMOIRE DES MOUVEMENTS APPRIS. Sans elle, le systeme re-payait la recherche
# (LLM + Wikipedia, ~30-60 s) A CHAQUE generation du meme mouvement, et les
# autres etages (questions de clarification) n'avaient aucun moyen de savoir
# que "6-7" etait deja compris — l'utilisateur se faisait re-questionner sur
# un mouvement resolu la veille. Ce n'est PAS du dur-codage: c'est le fruit de
# ses propres recherches, revisable (supprimer l'entree = re-recherche).
CONNAISSANCES = Path(os.environ.get(
    "AURORA_CONNAISSANCES",
    Path.home() / ".local/share/auroraia/connaissances")) / "mouvements.json"


def _cle(nom: str) -> str:
    """'6-7', '67', '6 7', 'Six Seven' -> une seule cle."""
    return re.sub(r"[\s_-]+", "", (nom or "").lower())


def _memoire_lire() -> dict:
    try:
        return json.loads(CONNAISSANCES.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def _memoire_ecrire(nom: str, entree: dict) -> None:
    try:
        CONNAISSANCES.parent.mkdir(parents=True, exist_ok=True)
        d = _memoire_lire()
        d[_cle(nom)] = {**entree, "nom": nom,
                        "appris_le": time.strftime("%Y-%m-%d")}
        CONNAISSANCES.write_text(json.dumps(d, ensure_ascii=False, indent=1),
                                 encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass


def _wiki_snippets(name: str, timeout_s: float = 10.0) -> str:
    """Article Wikipedia du mouvement (API propre, sans cle). C'est la source
    qui couvre les trends: '6-7', 'Griddy (dance)', 'Macarena'... La recherche
    trouve le titre, l'extrait donne la matiere au LLM."""
    try:
        base = "https://en.wikipedia.org/w/api.php"
        # requete SIMPLE: "griddy dance" trouve l'article, la requete longue
        # bourree de mots-cles ne trouvait rien.
        q = urllib.parse.urlencode({
            "action": "query", "list": "search", "format": "json",
            "srlimit": 3, "srsearch": "%s dance" % name})
        req = urllib.request.Request(base + "?" + q,
                                     headers={"User-Agent": "AuroraIA/1.0"})
        with urllib.request.urlopen(req, timeout=timeout_s) as r:
            hits = json.loads(r.read().decode()).get(
                "query", {}).get("search", [])
        if not hits:
            return ""
        # priorite au titre qui contient le nom demande
        low = name.lower().replace("-", "").replace(" ", "")
        title = next((h["title"] for h in hits
                      if low in h["title"].lower().replace("-", "")
                      .replace(" ", "")), hits[0]["title"])
        # article ENTIER: la description du geste du "6-7" vit au milieu de
        # l'article (section 67 Kid) — un extrait de 2400 caracteres la ratait.
        q2 = urllib.parse.urlencode({
            "action": "query", "prop": "extracts", "explaintext": 1,
            "redirects": 1, "format": "json",
            "titles": title})
        req2 = urllib.request.Request(base + "?" + q2,
                                      headers={"User-Agent": "AuroraIA/1.0"})
        with urllib.request.urlopen(req2, timeout=timeout_s) as r:
            pages = json.loads(r.read().decode()).get(
                "query", {}).get("pages", {})
        ext = next(iter(pages.values()), {}).get("extract", "")
        return ("[%s] " % title) + re.sub(r"\s+", " ", ext)[:6000]
    except Exception:  # noqa: BLE001
        return ""


def _wikihow_pas(name: str, timeout_s: float = 12.0) -> str:
    """Pas-a-pas wikiHow — LA source des gestes ("how to do the X").

    Les encyclopedies racontent l'HISTOIRE d'un mouvement, jamais ses pas
    (verifie: article Macarena 16k caracteres, zero "right arm"). wikiHow
    publie la sequence exacte en schema HowTo JSON-LD structure. General:
    n'importe quel mouvement nomme, aucune liste en dur."""
    ua = {"User-Agent": ("Mozilla/5.0 (X11; Linux x86_64; rv:132.0) "
                         "Gecko/20100101 Firefox/132.0")}

    def _cherche(q: str) -> list[str]:
        url = ("https://www.wikihow.com/wikiHowTo?search="
               + urllib.parse.quote_plus(q))
        req = urllib.request.Request(url, headers=ua)
        with urllib.request.urlopen(req, timeout=timeout_s) as r:
            html = r.read().decode("utf-8", errors="replace")
        return [u for u in re.findall(
            r'class="result_link"[^>]*href="(https://www\.wikihow\.com/[^"]+)"',
            html) if "/Category:" not in u]

    def _pertinent(url: str) -> bool:
        slug = url.rsplit("/", 1)[-1].lower()
        return any(m and m in slug for m in re.split(r"[\s_-]+", name.lower()))

    try:
        liens: list[str] = []
        for q in (name, "%s dance" % name, "do the %s" % name):
            liens = [u for u in _cherche(q) if _pertinent(u)]
            if liens:
                break
        if not liens:
            return ""
        req = urllib.request.Request(liens[0], headers=ua)
        with urllib.request.urlopen(req, timeout=timeout_s) as r:
            art = r.read().decode("utf-8", errors="replace")
        pas: list[str] = []
        for b in re.findall(
                r'<script type="application/ld\+json"[^>]*>(.*?)</script>',
                art, re.S):
            try:
                d = json.loads(b)
            except Exception:  # noqa: BLE001
                continue
            for it in (d if isinstance(d, list) else [d]):
                if it.get("@type") != "HowTo":
                    continue
                for s in it.get("step", []):
                    if s.get("@type") == "HowToSection":
                        for e in s.get("itemListElement", []):
                            pas.append(str(e.get("text") or ""))
                    elif s.get("@type") == "HowToStep":
                        pas.append(str(s.get("text") or ""))
        pas = [re.sub(r"\s+", " ", p).strip() for p in pas if p.strip()]
        if not pas:
            return ""
        return ("[wikiHow %s] " % liens[0].rsplit("/", 1)[-1]
                + " || ".join(p[:260] for p in pas[:20]))[:5000]
    except Exception:  # noqa: BLE001
        return ""


def _web_snippets(query: str, timeout_s: float = 10.0) -> str:
    """Bribes web, best-effort: '' si indisponible.

    C'est ce qui couvre les trends plus recents que le LLM — le "67" d'une
    annee donnee, le defi du moment. DuckDuckGo HTML repond 202 (anti-robot)
    sur cette machine, verifie: on lit donc les LEGENDES des resultats Bing,
    qui repondent 200 sans cle.
    """
    try:
        url = ("https://www.bing.com/search?q="
               + urllib.parse.quote_plus(query))
        req = urllib.request.Request(url, headers={
            "User-Agent": ("Mozilla/5.0 (X11; Linux x86_64; rv:132.0) "
                           "Gecko/20100101 Firefox/132.0"),
            "Accept-Language": "en-US,en;q=0.8,fr;q=0.6"})
        with urllib.request.urlopen(req, timeout=timeout_s) as r:
            html = r.read().decode("utf-8", errors="replace")
        # UNIQUEMENT les legendes de resultats: le 1er <p> de chaque bloc
        # b_caption — un <p> global ramasse le javascript de la page.
        outs = []
        for chunk in html.split('class="b_caption"')[1:8]:
            m = re.search(r"<p[^>]*>(.*?)</p>", chunk, re.S)
            if not m:
                continue
            t = re.sub(r"&#\d+;", " ", re.sub(r"<[^>]+>", "", m.group(1))).strip()
            if len(t) > 40 and "function" not in t and "sj_" not in t:
                outs.append(t)
        return re.sub(r"\s+", " ", " | ".join(outs))[:1400]
    except Exception:  # noqa: BLE001
        return ""


def _llm(prompt: str, timeout_s: int = 90) -> str:
    body = json.dumps({"model": MODEL, "prompt": prompt, "stream": False,
                       "format": "json",
                       "options": {"temperature": 0.1},
                       "keep_alive": 0}).encode()
    req = urllib.request.Request(
        OLLAMA + "/api/generate", data=body,
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout_s) as r:
        return json.loads(r.read().decode()).get("response", "")


def resolve(prompt: str, use_web: bool = True) -> dict:
    """Rend {named_move, name, description_en, source}.

    named_move=False -> le prompt decrit un geste generique (marcher, sauter):
    la chaine normale (prefixages puis generation) suffit.
    named_move=True  -> description_en est la traduction biomecanique du
    mouvement nomme, a donner TELLE QUELLE au generateur texte->mouvement.
    """
    p = (prompt or "").strip()
    if not p:
        return {"named_move": False, "name": "", "description_en": "",
                "source": "vide"}

    # GRAMMAIRE + MEMOIRE AVANT TOUT LLM: un mouvement deja appris repond
    # instantanement, meme a froid (zero chargement de modele).
    _m0 = re.search(
        r"\b(?:fais|refais|danse|execute|ex[ée]cute|fait)\s+"
        r"(?:le|la|l'|un|une)\s*([\w\d][\w\d -]{0,22})", p, re.I)
    if _m0:
        _nom0 = _m0.group(1).strip()
        _connu0 = _memoire_lire().get(_cle(_nom0))
        if _connu0 and len(_connu0.get("description_en") or "") >= 40:
            return {"named_move": True, "name": _connu0.get("nom", _nom0),
                    "description_en": _connu0["description_en"],
                    **{k: _connu0[k] for k in ("phases", "duration_s")
                       if _connu0.get(k)},
                    "source": "memoire (appris le %s via %s)"
                              % (_connu0.get("appris_le", "?"),
                                 _connu0.get("source", "?"))}

    ask = (
        "You are a motion analyst for a 3D animation pipeline.\n"
        "User request (French): \"%s\"\n\n"
        "Question 1: does this request reference a SPECIFIC NAMED move — a "
        "dance, meme, trend, sport celebration or signature move (examples of "
        "the KIND of thing: a named dance craze, a viral gesture, a named "
        "celebration) — as opposed to a GENERIC action (walk, jump, sit, "
        "attack)?\n"
        "Question 2: if yes, describe HOW A HUMAN PERFORMS IT, precisely and "
        "mechanically, in English: starting pose, exact arm/hand trajectories, "
        "leg/hip motion, head, timing and repetitions. NO cultural context, "
        "no history — ONLY the biomechanics, 2-4 sentences, as input for a "
        "text-to-motion model.\n"
        "If you do not reliably know the named move, set known=false — NEVER "
        "invent a movement.\n\n"
        'Answer as JSON: {"named_move": true|false, "name": "<move name or '
        'empty>", "known": true|false, "description_en": "<biomechanical '
        'description or empty>"}'
        % p)

    src = "llm"
    try:
        out = json.loads(_llm(ask))
    except Exception as exc:  # noqa: BLE001
        return {"named_move": False, "name": "", "description_en": "",
                "source": "llm_indisponible: %r" % (exc,)}

    named = bool(out.get("named_move"))
    known = bool(out.get("known"))
    name = str(out.get("name") or "").strip()
    desc = str(out.get("description_en") or "").strip()

    # GRAMMAIRE, pas liste: "fais le X" / "la trend X" designent PAR
    # CONSTRUCTION un mouvement nomme (imperatif + article + nom). Si le LLM
    # ne l'a pas reconnu (trend trop recent, nom numerique comme "67"), on le
    # traite quand meme comme nomme et la recherche web prend le relais.
    if not named:
        m = re.search(
            r"\b(?:fais|refais|danse|execute|ex[ée]cute|fait)\s+"
            r"(?:le|la|l'|un|une)\s*([\w\d][\w\d -]{0,22})\s*$", p, re.I)
        if m is None:
            m = re.search(
                r"\b(?:trend|tendance|meme|m[eè]me|d[ée]fi|challenge|"
                r"mouvement|danse)\s+(?:du|de\s+la|de\s+l'|le|la)?\s*"
                r"[«\"']?([\w\d][\w\d -]{0,22})[»\"']?", p, re.I)
        if m:
            named, known = True, False
            name = m.group(1).strip()

    # MEMOIRE D'ABORD: un mouvement deja appris ne se re-recherche pas.
    if named and name:
        _connu = _memoire_lire().get(_cle(name))
        if _connu and len(_connu.get("description_en") or "") >= 40:
            return {"named_move": True, "name": name,
                    "description_en": _connu["description_en"],
                    **{k: _connu[k] for k in ("phases", "duration_s")
                       if _connu.get(k)},
                    "source": "memoire (appris le %s via %s)"
                              % (_connu.get("appris_le", "?"),
                                 _connu.get("source", "?"))}

    # RECHERCHE DOCUMENTAIRE D'ABORD pour tout mouvement nomme: le LLM
    # "connait" souvent le nom mais restitue une approximation (constate le
    # 24/07: macarena resumee en un balancement de bras — la vraie sequence
    # compte ~16 temps: bras tendus l'un apres l'autre paumes bas, paumes
    # hautes, mains croisees aux epaules, derriere la tete, hanches, saut).
    # La source documentaire prime; la connaissance LLM n'est qu'un repli.
    extra: dict = {}
    if named and use_web and name:
        # ORDRE DES SOURCES: wikiHow (les PAS exacts, JSON-LD structure) >
        # Wikipedia si le texte parle du CORPS > legendes Bing. La page
        # encyclopedique raconte l'histoire, jamais la sequence (verifie:
        # Macarena 16k caracteres, zero "right arm" — le LLM en tirait une
        # approximation et la memoire l'a fige).
        _forts = ("arm", "palm", "hip", "shoulder", "knee", "elbow",
                  "wrist", "leg", "foot", "head")

        def _parle_du_corps(t: str) -> int:
            tl = t.lower()
            return sum(1 for w in _forts if w in tl)

        snips = _wikihow_pas(name)
        if not snips:
            _wiki = _wiki_snippets(name)
            snips = _wiki if _parle_du_corps(_wiki) >= 3 else ""
            if _parle_du_corps(snips) < 3:
                for q in ("how to do the %s dance step by step" % name,
                          "\"%s\" dance move how to do it" % name,
                          "%s tiktok dance move tutorial" % name):
                    part = _web_snippets(q)
                    if part:
                        snips += (" | " if snips else "") + part
                    if _parle_du_corps(snips) >= 3 and len(snips) > 700:
                        break
            if not snips:
                snips = _wiki   # a defaut de mieux, l'histoire du geste
        if snips:
            ask2 = (
                "Web snippets about the move \"%s\": %s\n\n"
                "From these snippets ONLY, extract how a human performs this "
                "move, as input for a text-to-motion model:\n"
                "- description_en: the biomechanics IN PERFORMANCE ORDER "
                "(starting pose, then EACH arm/hand placement in sequence, "
                "leg/hip motion, head, repetitions), English, 3-6 sentences, "
                "no cultural context;\n"
                "- phases: ordered list of the elementary movements, one "
                "short clause each;\n"
                "- duration_s: realistic seconds for ONE full sequence at "
                "performance tempo.\n"
                "If the snippets do not describe the movement, answer "
                '{"known": false}.\n'
                'JSON: {"known": true|false, "description_en": "...", '
                '"phases": ["..."], "duration_s": 0.0}'
                % (name, snips))
            try:
                out2 = json.loads(_llm(ask2))
                if out2.get("known") and len(str(out2.get("description_en") or "")) >= 40:
                    desc = str(out2["description_en"]).strip()
                    known = True
                    src = "web+llm"
                    try:
                        _ph = [str(x).strip() for x in (out2.get("phases") or [])
                               if str(x).strip()]
                        if _ph:
                            extra["phases"] = _ph[:24]
                        _du = float(out2.get("duration_s") or 0.0)
                        if 1.0 <= _du <= 60.0:
                            extra["duration_s"] = round(_du, 1)
                    except Exception:  # noqa: BLE001
                        pass
            except Exception:  # noqa: BLE001
                pass

    if named and known and desc:
        _memoire_ecrire(name, {"description_en": desc, "source": src, **extra})
        return {"named_move": True, "name": name,
                "description_en": desc, "source": src, **extra}
    if named and not known:
        return {"named_move": True, "name": name, "description_en": "",
                "source": "inconnu",
                "error": "mouvement nomme '%s' non resolu — rien n'est "
                         "invente a sa place" % (name or p)}
    return {"named_move": False, "name": "", "description_en": "",
            "source": src}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--no-web", action="store_true")
    a = ap.parse_args()
    r = resolve(a.prompt, use_web=not a.no_web)
    print(json.dumps(r, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
