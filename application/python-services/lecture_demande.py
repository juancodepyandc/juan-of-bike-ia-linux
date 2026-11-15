#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Lecture structurée d'une demande 3D : ce qu'il faut MONTRER et ce qui doit BOUGER.

Une image de référence décrit un objet, pas un film. Tant que la demande entière
(« coffre avec une animation d'ouverture ») servait à chercher, juger et synthétiser la
référence, une planche de six coffres à six stades d'ouverture était la réponse la plus
fidèle à la phrase — et le pipeline la reconstruisait telle quelle (run du 13/11/2026).

La lecture sépare donc trois choses, par compréhension de la phrase et non par liste de mots :
  - le sujet tel qu'il doit apparaître sur la référence, dans l'état où le mouvement commence ;
  - le mouvement demandé, qui ne concerne que l'étage d'animation ;
  - le nombre d'exemplaires du sujet que la demande attend réellement.

Aucune règle ici ne dépend d'un sujet particulier. Quand le modèle de langage ne répond pas
ou répond de travers, la lecture le dit (`source: "indisponible"`) et rend la demande
inchangée : l'appelant décide alors par prudence, il ne reçoit jamais une lecture inventée.
"""
from __future__ import annotations

import json
import urllib.request
from typing import Any, Callable

OLLAMA_URL = "http://127.0.0.1:11434"
SCHEMA = "aurora.lecture-demande.v2"
MODELE_SOUHAITE = "orcarouter/Qwen3.8-27B-Uncensored:latest"
MAX_EXEMPLAIRES = 64

_CONSIGNE = (
    "Tu lis une demande de création 3D et tu la sépares en informations. "
    "Réponds UNIQUEMENT par un objet JSON de cette forme exacte :\n"
    '{"sujet": "...", "sujet_en": "...", "mouvement": "...", "exemplaires": 1, "corps_articule": false, '
    '"conception": false, "sujets": [{"nom": "...", "nomme": true, "nature": "...", "nature_en": "...", '
    '"clause": "...", "mouvement": "...", "mouvement_en": "...", "milieu": {"matiere": "solide", '
    '"relation": "sur", "justification": "..."}}], "style": {"texte": "...", "cible": null, '
    '"justification": "..."}}\n'
    "- sujet : ce qu'une photo de référence doit montrer — l'objet, l'être ou la scène, nommés avec les "
    "mots de la demande, avec SEULEMENT les matières, couleurs et détails que la demande donne, dans "
    "l'état où le sujet se trouve AVANT que le mouvement commence. N'ajoute aucune apparence que la "
    "demande ne donne pas (vêtements, couleurs, coiffure, matière) : l'apparence d'un personnage, d'un "
    "produit ou d'une marque connus est retrouvée ensuite sur de vraies images, jamais de mémoire. "
    "Aucun mot de mouvement, d'action, de posture d'action, d'animation, de durée ou de caméra. "
    "Même langue que la demande.\n"
    "- sujet_en : la même description en anglais, courte, utilisable comme recherche d'image.\n"
    "- mouvement : ce qui doit bouger et comment, repris fidèlement de la demande ; chaîne vide "
    "si la demande ne décrit aucun mouvement.\n"
    "- exemplaires : combien d'objets physiques distincts du sujet la demande veut voir en même "
    "temps (un objet = 1 ; « une paire de… » = 2 ; « trois… » = 3). Les étapes successives d'un "
    "mouvement ne sont PAS des exemplaires : un objet qui s'anime reste 1.\n"
    "- corps_articule : true si le sujet, ou l'un des sujets, est un être — personne, personnage, animal, "
    "créature, robot humanoïde — dont le mouvement passe par son propre corps (membres, colonne, queue, "
    "nageoires, ailes) ; false pour un objet, un mécanisme, un véhicule, une plante, un liquide, un gaz "
    "ou un décor sans être.\n"
    "- conception : true si la demande porte sur la CONCEPTION d'un objet à fabriquer et assembler — elle parle "
    "de pièces, de fixations ou d'assemblage (vis, charnière, loquet, clips, collage, soudure), de fabrication, de "
    "cotes ou de fonctionnement mécanique ; false pour un personnage, un animal, une créature, une sculpture, une "
    "scène, ou un objet demandé seulement pour son apparence ou son animation.\n"
    "- sujets : UN élément par sujet distinct de la demande, dans l'ordre où elle les nomme.\n"
    "  · nom : le nom propre du sujet tel qu'écrit dans la demande (« Zig », « Natsu Dragneel »), "
    "null s'il n'a pas de nom propre ; nomme : true s'il a un nom propre.\n"
    "  · nature : ce qu'est le sujet en deux à quatre mots (espèce, type d'être ou d'objet), telle que la "
    "demande la dit, sinon ce que le nom désigne ; nature_en : la même chose en anglais.\n"
    "  · clause : le morceau EXACT de la demande qui parle de ce sujet (copié mot pour mot).\n"
    "  · mouvement : son action, reprise de la demande ; chaîne vide s'il n'en a pas. mouvement_en : "
    "cette action en une courte phrase anglaise de capture de mouvement, au présent, avec « a person » "
    "comme acteur (« a person runs forward », « a person swims ») ; chaîne vide sans mouvement.\n"
    "  · milieu : où se fait ce mouvement. matiere ∈ solide|liquide|gaz|null, relation ∈ "
    "sur|immerge|a_la_surface|dans_l_air|null ; justification : les mots de la demande qui l'impliquent. "
    "Le milieu peut être impliqué par le verbe (nager se fait dans un liquide, voler dans l'air) ; null "
    "s'il n'y a ni mouvement ni lieu.\n"
    "- style : le rendu demandé, séparé des sujets. texte : les mots EXACTS de la demande qui le "
    "décrivent (« en version réaliste »), chaîne vide sinon ; cible ∈ photo|cel_2d|cgi_3d|figurine|autre|"
    "null ; justification : ces mêmes mots. Le style n'apparaît jamais dans un nom ni dans une nature.\n"
    "N'ajoute rien que la demande ne dit pas. Pas de texte hors du JSON."
)

# Valeurs fermées et cohérence physique du milieu (contrat v2, 15/11/2026).
MATIERES = {"solide", "liquide", "gaz"}
RELATIONS = {"sur", "immerge", "a_la_surface", "dans_l_air"}
CIBLES_STYLE = {"photo", "cel_2d", "cgi_3d", "figurine", "autre"}
_MATIERE_DE_RELATION = {"sur": "solide", "immerge": "liquide", "a_la_surface": "liquide", "dans_l_air": "gaz"}
MAX_SUJETS = 8

_cache: dict[tuple[str, str], dict[str, Any]] = {}


# Un modèle 27B chargé à froid pendant que FLUX occupe la mémoire a mis 47 s à répondre via le pont
# (15/11/2026) ; à 90 s par appel, la lecture tombait en « indisponible » au début d'un run chargé.
DELAI_S = 240.0


def _interroger_ollama(demande: str, modele: str, timeout_s: float = DELAI_S) -> str:
    corps = json.dumps({
        "model": modele,
        "stream": False,
        "format": "json",
        "think": False,
        "options": {"temperature": 0.0, "num_predict": 1100},
        "messages": [
            {"role": "system", "content": _CONSIGNE},
            {"role": "user", "content": demande},
        ],
    }).encode("utf-8")
    requete = urllib.request.Request(f"{OLLAMA_URL}/api/chat", data=corps,
                                     headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(requete, timeout=timeout_s) as reponse:
        return str(json.loads(reponse.read().decode("utf-8")).get("message", {}).get("content", ""))


def _extraire_json(texte: str) -> dict[str, Any] | None:
    debut, fin = texte.find("{"), texte.rfind("}")
    if debut < 0 or fin <= debut:
        return None
    try:
        valeur = json.loads(texte[debut:fin + 1])
    except ValueError:
        return None
    return valeur if isinstance(valeur, dict) else None


def _plat(texte: str) -> str:
    """Forme comparable d'un texte : sans accents, sans casse, espaces réduits."""
    import unicodedata
    sans = "".join(c for c in unicodedata.normalize("NFD", str(texte)) if unicodedata.category(c) != "Mn")
    return " ".join(sans.casefold().replace("’", "'").split())


def _dans(morceau: str, demande: str) -> bool:
    return bool(morceau) and _plat(morceau) in _plat(demande)


def _valider_sujets(brut: dict[str, Any], demande: str) -> tuple[list[dict[str, Any]] | None, dict[str, Any] | None, str]:
    """Contrat v2 : un élément par sujet, le style à part. Rend (sujets, style, "") ou la règle enfreinte."""
    bruts = brut.get("sujets")
    if not isinstance(bruts, list) or not bruts or len(bruts) > MAX_SUJETS:
        return None, None, f"sujets doit être une liste de 1 à {MAX_SUJETS} éléments"
    style_brut = brut.get("style") if isinstance(brut.get("style"), dict) else {}
    style_texte = " ".join(str(style_brut.get("texte") or "").split())
    if style_texte and not _dans(style_texte, demande):
        return None, None, "style.texte doit être copié mot pour mot de la demande"
    cible = style_brut.get("cible")
    if cible is not None and cible not in CIBLES_STYLE:
        return None, None, "style.cible doit être photo, cel_2d, cgi_3d, figurine, autre ou null"
    sujets = []
    for i, s in enumerate(bruts):
        if not isinstance(s, dict):
            return None, None, f"sujets[{i}] n'est pas un objet"
        nom = s.get("nom")
        nom = " ".join(nom.split()) if isinstance(nom, str) and nom.strip() else None
        if nom and not _dans(nom, demande):
            return None, None, f"sujets[{i}].nom doit être écrit tel quel dans la demande"
        clause = " ".join(str(s.get("clause") or "").split())
        if not _dans(clause, demande):
            return None, None, f"sujets[{i}].clause doit être un morceau exact de la demande"
        nature = " ".join(str(s.get("nature") or "").split())
        nature_en = " ".join(str(s.get("nature_en") or "").split())
        if not nature or not nature_en:
            return None, None, f"sujets[{i}] doit donner nature et nature_en"
        if style_texte and (_plat(style_texte) in _plat(nature) or (nom and _plat(style_texte) in _plat(nom))):
            return None, None, "le style ne doit apparaître ni dans un nom ni dans une nature"
        milieu_brut = s.get("milieu") if isinstance(s.get("milieu"), dict) else {}
        matiere, relation = milieu_brut.get("matiere"), milieu_brut.get("relation")
        if matiere is not None and matiere not in MATIERES:
            return None, None, f"sujets[{i}].milieu.matiere doit être solide, liquide, gaz ou null"
        if relation is not None and relation not in RELATIONS:
            return None, None, f"sujets[{i}].milieu.relation doit être sur, immerge, a_la_surface, dans_l_air ou null"
        if relation is not None and matiere != _MATIERE_DE_RELATION[relation]:
            return None, None, (f"sujets[{i}].milieu incohérent : {relation} implique la matière "
                                f"{_MATIERE_DE_RELATION[relation]}")
        sujets.append({
            "nom": nom, "nomme": bool(nom) and s.get("nomme") is not False,
            "nature": nature, "nature_en": nature_en, "clause": clause,
            "mouvement": " ".join(str(s.get("mouvement") or "").split()),
            "mouvement_en": " ".join(str(s.get("mouvement_en") or "").split()),
            "milieu": {"matiere": matiere, "relation": relation,
                       "justification": " ".join(str(milieu_brut.get("justification") or "").split())},
        })
    style = {"texte": style_texte, "cible": cible,
             "justification": " ".join(str(style_brut.get("justification") or "").split())}
    return sujets, style, ""


def _valider(brut: dict[str, Any] | None, demande: str) -> tuple[dict[str, Any] | None, str]:
    """Rend (lecture normalisée, "") ou (None, la règle du contrat qui n'est pas respectée)."""
    if not isinstance(brut, dict):
        return None, "la réponse n'est pas un objet JSON"
    sujet = brut.get("sujet")
    if not isinstance(sujet, str) or not sujet.strip():
        return None, "le champ sujet est vide"
    sujet = " ".join(sujet.split())
    # Une « lecture » plus longue que la demande n'en est pas une : le modèle a brodé (15/11/2026 :
    # « natsu Dragneel qui cours » est revenu avec une tenue rouge inventée et la posture de course).
    if len(sujet) > max(2 * len(demande), len(demande) + 80):
        return None, ("le sujet est bien plus long que la demande : il ajoute une apparence ou une "
                      "posture que la demande ne donne pas")
    exemplaires = brut.get("exemplaires")
    if type(exemplaires) is not int or not 1 <= exemplaires <= MAX_EXEMPLAIRES:
        return None, f"exemplaires doit être un entier entre 1 et {MAX_EXEMPLAIRES}"
    mouvement = brut.get("mouvement", "")
    if not isinstance(mouvement, str):
        return None, "mouvement doit être une chaîne"
    sujet_en = brut.get("sujet_en", "")
    if not isinstance(sujet_en, str):
        sujet_en = ""
    sujets, style, raison_v2 = _valider_sujets(brut, demande)
    if sujets is None:
        return None, raison_v2
    return {
        "schema": SCHEMA,
        "source": "llm",
        "demande": demande,
        "sujet": sujet,
        "sujet_en": " ".join(sujet_en.split()),
        "mouvement": " ".join(mouvement.split()),
        "exemplaires": exemplaires,
        # champs ajoutés les 14 et 15/11/2026 : absent ou non booléen = faux
        "corps_articule": brut.get("corps_articule") is True,
        "conception": brut.get("conception") is True,
        # contrat v2 (15/11/2026) : un élément par sujet, le style à part
        "sujets": sujets,
        "style": style,
    }, ""


def _correction(demande: str, reponse: str, raison: str) -> str:
    """Deuxième tour : la même demande, la réponse refusée et la règle enfreinte, nommément."""
    return (f"{demande}\n\n---\nTa réponse précédente était : {reponse.strip()[:900]}\n"
            f"Elle ne respecte pas le contrat : {raison}. Rends le JSON corrigé, avec le sujet "
            "nommé par les seuls mots de la demande.")


def lecture_indisponible(demande: str, raison: str) -> dict[str, Any]:
    """La demande telle quelle, marquée comme non lue : l'appelant ne doit rien en déduire."""
    return {"schema": SCHEMA, "source": "indisponible", "raison": raison[:200], "demande": demande,
            "sujet": demande, "sujet_en": "", "mouvement": "", "exemplaires": None, "corps_articule": None,
            "conception": None, "sujets": [], "style": {"texte": "", "cible": None, "justification": ""}}


def lire_demande(demande: str, *, interroger: Callable[[str], str] | None = None,
                 modele: str | None = None) -> dict[str, Any]:
    """Sépare apparence, mouvement et nombre d'exemplaires d'une demande.

    `interroger` reçoit la demande et rend le texte du modèle ; il est injectable pour les
    tests et pour un appelant qui dispose déjà de son accès au modèle.
    """
    demande = " ".join(str(demande or "").split())
    if not demande:
        return lecture_indisponible("", "demande vide")
    if interroger is None:
        if modele is None:
            try:
                from llm_disponible import resoudre_modele
                modele = resoudre_modele(MODELE_SOUHAITE, "texte", bavard=False)
            except Exception:  # noqa: BLE001 — sans résolveur, on tente le modèle souhaité
                modele = MODELE_SOUHAITE
        cle = (modele, demande)
        if cle in _cache:
            return dict(_cache[cle])
        modele_choisi = modele

        def interroger(texte: str) -> str:
            return _interroger_ollama(texte, modele_choisi)
    else:
        cle = None
    try:
        reponse = str(interroger(demande))
        lecture, raison = _valider(_extraire_json(reponse), demande)
        if lecture is None:
            # Une seule correction, la règle enfreinte nommée : un refus muet renvoyait toute la
            # phrase, mouvement compris, vers la référence (personnage reconstruit en pleine course).
            reponse = str(interroger(_correction(demande, reponse, raison)))
            lecture, raison = _valider(_extraire_json(reponse), demande)
    except Exception as exc:  # noqa: BLE001 — modèle injoignable : lecture non disponible, pas inventée
        return lecture_indisponible(demande, f"{type(exc).__name__}: {exc}")
    if lecture is None:
        return lecture_indisponible(demande, f"réponse du modèle hors contrat : {raison}")
    if cle is not None:
        _cache[cle] = dict(lecture)
    return lecture


def main() -> int:
    import argparse
    analyseur = argparse.ArgumentParser(description="Sépare apparence, mouvement et exemplaires d'une demande 3D")
    analyseur.add_argument("--prompt", required=True)
    analyseur.add_argument("--model", default=None)
    analyseur.add_argument("--sortie", default=None, help="écrit aussi le contrat dans ce fichier JSON")
    arguments = analyseur.parse_args()
    lecture = lire_demande(arguments.prompt, modele=arguments.model)
    if arguments.sortie:
        from pathlib import Path
        cible = Path(arguments.sortie)
        cible.parent.mkdir(parents=True, exist_ok=True)
        cible.write_text(json.dumps(lecture, ensure_ascii=False, indent=2), encoding="utf-8")
    # une seule ligne : les appelants (interface, pont) lisent la dernière ligne JSON de la sortie
    print(json.dumps(lecture, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
