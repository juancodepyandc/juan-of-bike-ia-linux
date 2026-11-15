#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Juge d'identité, de style et de demande : une référence générée, puis le modèle livré, contre la PREUVE.

15/11/2026 — « Zig et Sharko en version réaliste : Zig la hyène qui court et Sharko le requin qui
nage ». FLUX a dessiné, d'après une description TEXTUELLE de l'identité, une hyène tachetée réelle et
un requin générique, tous deux avec le même short rayé. La porte qualité a noté 100/100 parce qu'elle
comparait le modèle à cette référence synthétique elle-même (`_ref_juge = front_ref`) : aucun juge ne
regardait de vraies images des personnages.

Loi : on juge contre la preuve — les ancres du dossier d'identité (`aurora.identite-visuelle.v1`,
images réelles retenues par accord entre sources) — et contre la demande — le contrat
`aurora.lecture-demande.v2` —, jamais contre sa propre sortie. Un juge muet ou illisible n'est jamais
un accord. Tant que les seuils absolus ne sont pas étalonnés, seules des règles RELATIVES décident :
l'enquête du 15/11 a mesuré en DINOv2 Sharko réel contre Sharko réel 0,56, requin synthétique contre
Sharko 0,61 et Zig contre Sharko 0,48 à 0,66, si bien qu'aucun seuil absolu de similarité ne tient.

  1. Découpes : exactement celles que TRELLIS reconstruira (`trellis_multi_character.
     detect_and_crop_characters`, appelée par le pipeline sur la même image source). Leur nombre doit
     égaler le nombre de sujets du contrat (axe « nombre »).
  2. Attribution biunivoque : la permutation découpes → sujets qui maximise la similarité moyenne aux
     ancres de chaque sujet, avec une marge sur la meilleure permutation concurrente (axe
     « attribution »). Une ressemblance n'est PAS un verdict d'identité : le requin générique ressemble
     plus à Sharko qu'à Zig sans être Sharko ; c'est la vision qui tranche l'identité.
  3. Par sujet, des votes de vision décorrélés (ordre des images permuté à chaque vote, 4 images au plus :
     la découpe et jusqu'à 3 ancres) : même personnage en ignorant le style voulu, plan du corps,
     vêtement ajouté, nature, style conforme au contrat. Décision à la majorité requise par le cliquet.
  4. Verdict : « accepte », « refuse » (axes et raisons en français, utilisables comme correction
     ciblée) ou « indisponible » (entrée incomplète, modèle absent, juge muet), jamais une acceptation
     par défaut.

Les seuils (votes requis, marge d'attribution) forment une famille de cliquet SÉPARÉE,
`modele/renforce/judge_ratchet_identite.json`, lue et avancée par `agi_core.judge_ratchet` avec son
propre chemin : le cliquet global est au niveau 878, tous ses seuils sont saturés et il ne peut plus
rien durcir. Les seuils de cette famille sont bornés : votes requis 2/3 → 3/3, marge 0,02 → 0,08.

Chaque appel de modèle est injectable (`decouper`, `embarquer`, `voter`) : les tests passent des faux,
et aucun appel réel n'est fait sans que l'appelant l'ait voulu.
"""
from __future__ import annotations

import argparse
import itertools
import json
import math
import re
import sys
import time
import unicodedata
from pathlib import Path
from typing import Any, Callable, Iterable

import numpy as np

ICI = Path(__file__).resolve().parent
RACINE = ICI.parents[1]
if str(ICI) not in sys.path:
    sys.path.insert(0, str(ICI))

SCHEMA = "aurora.juge-identite.v1"
SCHEMA_DOSSIER = "aurora.identite-visuelle.v1"
SCHEMA_CONTRAT = "aurora.lecture-demande.v2"

AXES = ("identite", "plan_du_corps", "vetement", "nature", "style", "attribution", "nombre")
# (clé du vote, axe qu'elle juge, réponse favorable) — « vetement_ajoute » est favorable quand il est FAUX.
QUESTIONS = (
    ("meme_personnage", "identite", True),
    ("plan_du_corps_conforme", "plan_du_corps", True),
    ("vetement_ajoute", "vetement", False),
    ("nature_conforme", "nature", True),
    ("style_conforme", "style", True),
)
QUESTIONS_SUR_ANCRES = ("meme_personnage", "plan_du_corps_conforme", "vetement_ajoute")

# `vlm_judge._encode_images` ne garde que 4 images et jette les autres en silence (la vue de face az000
# a ainsi disparu des jugements de perfection) : on n'en envoie jamais plus de 4.
MAX_IMAGES_VISION = 4
MAX_ANCRES_PAR_VOTE = MAX_IMAGES_VISION - 1
# 8! = 40 320 permutations, énumérées sans peine ; le découpage n'en sépare de toute façon que 2 ou 3.
MAX_SUJETS_ENUMERES = 8
EGALITE = 1e-9

CHEMIN_CLIQUET = RACINE / "modele" / "renforce" / "judge_ratchet_identite.json"
FRACTION_VOTES = (2.0 / 3.0, 1.0)        # part des votes favorables requise : 2/3 → 3/3
MARGE_ATTRIBUTION = (0.02, 0.08)         # marge minimale sur la 2e permutation : 0,02 → 0,08
PAS_SATURATION = 12                      # tours validés pour atteindre les bornes hautes
# L'axe « identité » est jugé à l'UNANIMITÉ, quel que soit le pas du cliquet (durcissement du 15/11/2026).
# Essai réel Zig et Sharko : une hyène tachetée générique, sans aucun trait de la hyène brune des ancres, a
# été acceptée par 2 votes contre 1. Sur « même personnage ? », le modèle de vision accorde facilement un
# individu de la même espèce : un seul vote contre est le signal qu'il ne faut pas laisser passer.
AXES_UNANIMES = ("identite",)

# Définition des valeurs fermées de `style.cible` du contrat, telles qu'un œil les vérifie. « image » :
# la référence générée ; « modele » : un rendu f3d du modèle livré, toujours une image de synthèse, ce
# qui ne doit jamais compter contre un style « photo ».
_STYLE = {
    "image": {
        "photo": "une PHOTOGRAPHIE réaliste : matières, lumière et ombres d'une vraie prise de vue, sans "
                 "contour encré ni aplat de dessin animé",
        "cel_2d": "un DESSIN ANIMÉ 2D : aplats de couleur et contours encrés",
        "cgi_3d": "une IMAGE DE SYNTHÈSE 3D stylisée, comme un film d'animation en images de synthèse",
        "figurine": "une FIGURINE ou un jouet physique (plastique, résine, vinyle) photographié",
    },
    "modele": {
        "photo": "des matières RÉALISTES et crédibles (surface, yeux), sans aplat ni contour de dessin "
                 "animé ; c'est un rendu 3D, ce qui est normal",
        "cel_2d": "un aspect DESSIN ANIMÉ (aplats de couleur, rendu toon) ; c'est un rendu 3D, ce qui est "
                  "normal",
        "cgi_3d": "un personnage 3D STYLISÉ de film d'animation",
        "figurine": "une FIGURINE ou un jouet (plastique, résine, vinyle)",
    },
}
_CANDIDAT = {
    "image": "un sujet découpé dans l'image générée pour la demande",
    "modele": "le rendu 3D, sans décor, du personnage livré pour la demande",
}


class _Indisponible(Exception):
    """Un outil manque ou ne répond pas : ce n'est pas un défaut de l'image, c'est une absence de mesure."""


# ── Outils de lecture ──────────────────────────────────────────────────────────────────────────────
def _normaliser(texte: Any) -> str:
    """Casse, accents et espaces neutralisés : « Même_Personnage » et « meme_personnage » se valent."""
    decompose = unicodedata.normalize("NFD", str(texte or ""))
    sans_accents = "".join(c for c in decompose if unicodedata.category(c) != "Mn")
    return " ".join(sans_accents.casefold().split())


def _mots(texte: Any) -> list[str]:
    """Les mots d'une phrase, ponctuation ignorée : « réaliste: » et « réaliste : » disent la même chose."""
    return re.findall(r"\w+", _normaliser(texte))


def _extraire_json(texte: str) -> dict[str, Any] | None:
    debut, fin = texte.find("{"), texte.rfind("}")
    if debut < 0 or fin <= debut:
        return None
    try:
        valeur = json.loads(texte[debut:fin + 1])
    except ValueError:
        return None
    return valeur if isinstance(valeur, dict) else None


_OUI = {"true", "oui", "yes", "vrai"}
_NON = {"false", "non", "no", "faux"}


def _booleen(valeur: Any) -> bool | None:
    """Un booléen lisible, sinon None : une réponse ambiguë est un vote muet, jamais un accord."""
    if isinstance(valeur, bool):
        return valeur
    if isinstance(valeur, str):
        mot = _normaliser(valeur)
        if mot in _OUI:
            return True
        if mot in _NON:
            return False
    return None


def _virgule(valeur: float) -> str:
    return f"{valeur:.3f}".replace(".", ",")


def _borner(valeur: float, bornes: tuple[float, float]) -> float:
    return min(bornes[1], max(bornes[0], float(valeur)))


# ── Cliquet de la famille « identité » ─────────────────────────────────────────────────────────────
def seuils_au_pas(pas: int) -> dict[str, Any]:
    """Seuils bornés après `pas` tours validés : jamais plus lâches que la base, jamais au-delà du plafond."""
    pas = max(0, int(pas))
    progression = min(1.0, pas / float(PAS_SATURATION))
    return {
        "pas": pas,
        "fraction_votes": FRACTION_VOTES[0] + (FRACTION_VOTES[1] - FRACTION_VOTES[0]) * progression,
        "marge_attribution_min": MARGE_ATTRIBUTION[0] + (MARGE_ATTRIBUTION[1] - MARGE_ATTRIBUTION[0]) * progression,
    }


def votes_requis(fraction: float, essais: int) -> int:
    """Votes favorables requis sur `essais` : au moins la majorité des 2/3, au plus l'unanimité.

    Arrondi vers le bas sur la grille des votes, pour qu'à 3 votes on passe de 2/3 à 3/3 seulement au
    plafond du cliquet, et non dès le premier tour où la fraction dépasse 2/3.
    """
    essais = int(essais)
    plancher = (2 * essais + 2) // 3                      # ⌈2E/3⌉
    return max(1, min(essais, max(plancher, math.floor(_borner(fraction, FRACTION_VOTES) * essais + EGALITE))))


def cliquet_identite(*, avancer: bool = False, chemin: str | Path | None = None) -> dict[str, Any]:
    """État de la famille « identité » ; `avancer=True` ajoute un tour, persistant et sous verrou.

    `agi_core.judge_ratchet` sert tel quel avec son propre chemin : niveau strictement croissant, état
    corrompu jamais remis à zéro. Le pas est compté depuis la base de CETTE famille : il ne dépend jamais
    de l'état global, saturé au niveau 878.
    """
    if str(RACINE) not in sys.path:
        sys.path.append(str(RACINE))
    from agi_core.judge_ratchet import BASE_LEVEL, DEFAULT_STATE, judge_ratchet
    cible = Path(chemin) if chemin is not None else CHEMIN_CLIQUET
    if cible.resolve() == Path(DEFAULT_STATE).resolve():
        raise ValueError("la famille « identité » ne lit jamais l'état global saturé du cliquet")
    etat = judge_ratchet(advance=bool(avancer), path=cible)
    pas = int(etat["ratchet_level"]) - int(BASE_LEVEL)
    return {"famille": "identite", "chemin": str(cible), "ratchet_level": int(etat["ratchet_level"]),
            "history_runs": int(etat["history_runs"]), "pas": pas, "seuils": seuils_au_pas(pas)}


def avancer_cliquet(resultat: dict[str, Any], *, chemin: str | Path | None = None) -> dict[str, Any]:
    """+1 par tour validé, jamais de relâchement : seul un verdict « accepte » de ce juge fait avancer.

    À appeler par la boucle une fois la livraison acceptée (`juger_modele`). Un refus ou un juge
    indisponible laisse le niveau tel quel : durcir sur des échecs verrouillerait le générateur.
    """
    valide = (isinstance(resultat, dict) and resultat.get("schema") == SCHEMA
              and resultat.get("verdict") == "accepte")
    etat = cliquet_identite(avancer=valide, chemin=chemin)
    etat["avance"] = valide
    return etat


def _seuils_effectifs(seuils: dict[str, Any] | None, chemin_cliquet: str | Path | None,
                      essais: int) -> dict[str, Any]:
    """Seuils de ce jugement : injectés (tests, boucle), sinon lus dans la famille, sinon le plafond.

    Des seuils injectés sont toujours ramenés dans les bornes de la famille : personne ne peut juger plus
    lâchement que la base. Un cliquet illisible ne se remet jamais à la base (ce serait relâcher) : le
    juge prend alors les seuils les plus stricts et le dit.
    """
    chemin = str(Path(chemin_cliquet) if chemin_cliquet is not None else CHEMIN_CLIQUET)
    niveau = pas = None
    if seuils is not None:
        fraction = _borner(seuils.get("fraction_votes", FRACTION_VOTES[0]), FRACTION_VOTES)
        marge = _borner(seuils.get("marge_attribution_min", MARGE_ATTRIBUTION[0]), MARGE_ATTRIBUTION)
        niveau, pas, source = seuils.get("ratchet_level"), seuils.get("pas"), "injecte"
    else:
        try:
            etat = cliquet_identite(chemin=chemin_cliquet)
            fraction = etat["seuils"]["fraction_votes"]
            marge = etat["seuils"]["marge_attribution_min"]
            niveau, pas, source = etat["ratchet_level"], etat["pas"], "cliquet"
        except Exception as exc:  # noqa: BLE001 — un état illisible n'autorise aucun relâchement
            plafond = seuils_au_pas(PAS_SATURATION)
            fraction, marge = plafond["fraction_votes"], plafond["marge_attribution_min"]
            source = f"plafond : cliquet illisible ({type(exc).__name__}: {exc})"[:200]
    return {"source": source, "chemin_cliquet": chemin, "ratchet_level": niveau, "pas": pas,
            "fraction_votes": round(float(fraction), 6), "essais_votes": int(essais),
            "votes_requis": votes_requis(fraction, essais),
            "votes_requis_axes_unanimes": int(essais), "axes_unanimes": list(AXES_UNANIMES),
            "marge_attribution_min": round(float(marge), 6)}


# ── Entrées : contrat de demande et dossier d'identité ─────────────────────────────────────────────
def _probleme_entrees(dossier: Any, contrat: Any) -> str | None:
    """Rend la raison pour laquelle on ne peut pas juger, ou None si les deux contrats sont lisibles."""
    if not isinstance(contrat, dict) or contrat.get("schema") != SCHEMA_CONTRAT:
        return f"contrat de demande absent ou hors schéma {SCHEMA_CONTRAT}"
    if contrat.get("source") != "llm":
        return "la demande n'a pas été lue (contrat « indisponible ») : sujets, nature et style inconnus"
    sujets = contrat.get("sujets")
    if not isinstance(sujets, list) or not sujets or not all(isinstance(s, dict) for s in sujets):
        return "le contrat ne contient aucun sujet"
    if not isinstance(dossier, dict) or dossier.get("schema") != SCHEMA_DOSSIER:
        return f"dossier d'identité absent ou hors schéma {SCHEMA_DOSSIER}"
    if not isinstance(dossier.get("sujets"), list):
        return "le dossier d'identité ne contient aucune liste de sujets"
    demande_d, demande_c = _mots(dossier.get("demande")), _mots(contrat.get("demande"))
    if demande_d and demande_c and demande_d != demande_c:
        return "le dossier d'identité a été établi pour une autre demande"
    return None


def _sujets(dossier: dict[str, Any], contrat: dict[str, Any]) -> list[dict[str, Any]]:
    """Un sujet du contrat, son entrée du dossier (par indice, sinon par nom) et ses ancres lisibles."""
    entrees = [e for e in dossier.get("sujets") or [] if isinstance(e, dict)]
    par_indice = {e["index"]: e for e in entrees if type(e.get("index")) is int}
    specs = []
    for i, sujet in enumerate(contrat["sujets"]):
        nom = " ".join(str(sujet.get("nom") or "").split()) or None
        entree = par_indice.get(i)
        if entree is not None and nom and entree.get("nom") and _normaliser(entree["nom"]) != _normaliser(nom):
            entree = None                       # l'indice désigne un autre nom : on cherche par le nom
        if entree is None and nom:
            entree = next((e for e in entrees if _normaliser(e.get("nom")) == _normaliser(nom)), None)
        etabli = bool(entree) and entree.get("etabli") is True
        ancres = []
        if etabli:
            for chemin in entree.get("ancres") or []:
                if isinstance(chemin, str) and Path(chemin).is_file() and chemin not in ancres:
                    ancres.append(chemin)
        attributs = (entree or {}).get("attributs") if etabli else None
        if entree is None:
            raison_dossier = "aucune entrée du dossier pour ce sujet"
        elif etabli and not ancres:
            raison_dossier = "ancres du dossier introuvables sur le disque"
        else:
            raison_dossier = entree.get("raison")
        specs.append({
            "index": i,
            "nom": nom,
            "nomme": sujet.get("nomme") is True or bool(nom),
            "nature": " ".join(str(sujet.get("nature") or "").split()),
            "nature_en": " ".join(str(sujet.get("nature_en") or "").split()),
            "ancres": ancres,
            "etabli": etabli and bool(ancres),
            "raison_dossier": raison_dossier,
            "attributs": attributs if isinstance(attributs, dict) and attributs.get("source") == "vision" else {},
        })
    return specs


def _libelle(spec: dict[str, Any]) -> str:
    base = spec["nom"] or f"le sujet {spec['index'] + 1}"
    return f"{base} ({spec['nature']})" if spec["nature"] else base


def _style(contrat: dict[str, Any]) -> tuple[str | None, str]:
    style = contrat.get("style") if isinstance(contrat.get("style"), dict) else {}
    cible = style.get("cible") if isinstance(style.get("cible"), str) else None
    return cible, " ".join(str(style.get("texte") or "").split())


def _description_style(contrat: dict[str, Any], mode: str) -> str | None:
    cible, texte = _style(contrat)
    if cible in _STYLE[mode]:
        return _STYLE[mode][cible]
    return f"conforme au style demandé « {texte} »" if texte else None


# ── Défauts injectables (les seuls points qui touchent un modèle) ──────────────────────────────────
def _decouper_defaut(image: str, dossier: str, run_id: str) -> list[dict[str, Any]]:
    """Les découpes que TRELLIS reconstruira : la même fonction que le pipeline, pas une copie."""
    from trellis_multi_character import detect_and_crop_characters
    return detect_and_crop_characters(image, dossier, run_id)


def _embarquer_defaut(chemins: list[str]) -> Any:
    """Plongements locaux (module frère `modeles_locaux` : DINOv2/CLIP chargés en local seulement).

    `embed_images` attend des images PIL : on les ouvre ici (il pose lui-même la transparence sur blanc).
    """
    import modeles_locaux  # ImportError rapportée comme « indisponible » par `_plongements`
    from PIL import Image
    images = []
    for chemin in chemins:
        with Image.open(chemin) as im:
            images.append(im.copy())
    return modeles_locaux.embed_images(images)


def _aplatir_pour_vision(chemin: str) -> str:
    """Une découpe RGBA montre au modèle de vision la couleur cachée sous l'alpha (souvent le décor
    d'origine) : on lui donne une copie posée sur blanc, comme aux plongements (relecture du 15/11/2026)."""
    from PIL import Image
    try:
        with Image.open(chemin) as im:
            if im.mode not in ("RGBA", "LA") and not (im.mode == "P" and "transparency" in im.info):
                return chemin
            rgba = im.convert("RGBA")
        fond = Image.new("RGB", rgba.size, (255, 255, 255))
        fond.paste(rgba, mask=rgba.getchannel("A"))
        cible = str(Path(chemin).with_name(Path(chemin).stem + "_sur_blanc.png"))
        fond.save(cible)
        return cible
    except OSError:
        return chemin


def _voter_defaut(images: list[str], question: str) -> Any:
    """Le modèle de vision local (`vlm_judge.ask_vlm`), 4 images au plus, JSON strict exigé."""
    from vlm_judge import ask_vlm
    return ask_vlm([_aplatir_pour_vision(i) for i in images], question, timeout=180)


# ── Attribution biunivoque découpes → sujets ───────────────────────────────────────────────────────
def _plongements(embarquer: Callable[[list[str]], Any], chemins: list[str]) -> np.ndarray:
    """Plongements L2-normalisés, ou `_Indisponible` : un modèle absent ne vaut jamais une mesure."""
    try:
        brut = embarquer(list(chemins))
    except ImportError as exc:
        raise _Indisponible(f"modèle de plongement indisponible ({type(exc).__name__}: {exc})"[:240]) from exc
    except Exception as exc:  # noqa: BLE001
        raise _Indisponible(f"plongement impossible ({type(exc).__name__}: {exc})"[:240]) from exc
    try:
        matrice = np.asarray(brut, dtype=np.float64)
    except (TypeError, ValueError) as exc:
        raise _Indisponible(f"plongements illisibles ({type(exc).__name__})") from exc
    if matrice.ndim != 2 or matrice.shape[0] != len(chemins) or matrice.shape[1] == 0:
        raise _Indisponible(f"plongements de forme {tuple(matrice.shape)} pour {len(chemins)} images")
    if not np.all(np.isfinite(matrice)):
        raise _Indisponible("plongements non finis")
    normes = np.linalg.norm(matrice, axis=1, keepdims=True)
    if np.any(normes <= 1e-12):
        raise _Indisponible("plongement nul")
    return matrice / normes


def _similarites(embarquer: Callable[[list[str]], Any], candidats: list[list[str]],
                 specs: list[dict[str, Any]]) -> np.ndarray:
    """`sim[k, s]` : similarité cosinus moyenne du candidat k aux ancres du sujet s (NaN : aucune ancre).

    Un candidat à plusieurs images (rendus d'un même personnage) est la moyenne normalisée de leurs
    plongements. Toutes les images partent en un seul appel : un seul chargement du modèle.
    """
    chemins: list[str] = []
    for groupe in candidats:
        chemins.extend(groupe)
    for spec in specs:
        chemins.extend(spec["ancres"])
    plong = _plongements(embarquer, chemins)
    curseur, vecteurs = 0, []
    for groupe in candidats:
        moyenne = plong[curseur:curseur + len(groupe)].mean(axis=0)
        curseur += len(groupe)
        norme = float(np.linalg.norm(moyenne))
        if norme <= 1e-12:
            raise _Indisponible("plongements opposés pour un même candidat")
        vecteurs.append(moyenne / norme)
    sim = np.full((len(candidats), len(specs)), np.nan)
    for s, spec in enumerate(specs):
        n_ancres = len(spec["ancres"])
        if n_ancres:
            ancres = plong[curseur:curseur + n_ancres]
            curseur += n_ancres
            for k, vecteur in enumerate(vecteurs):
                sim[k, s] = float((ancres @ vecteur).mean())
    return sim


def attribuer(sim: np.ndarray) -> dict[str, Any]:
    """La permutation découpes → sujets la plus proche des ancres, et sa marge sur les concurrentes.

    `sim[k, s]` : similarité de la découpe k aux ancres du sujet s, NaN pour un sujet sans ancre. Le score
    d'une permutation est la similarité moyenne sur les sujets qui ont des ancres. La marge d'un sujet est
    l'écart entre la meilleure permutation et la meilleure de celles qui lui donnent une AUTRE découpe ;
    la marge globale est la plus petite d'entre elles (écart à la seconde permutation qui compte).

    Un sujet sans ancre prend la découpe laissée par les autres quand il est le seul dans ce cas ; à deux
    ou plus, leur répartition n'est pas mesurable : ils sont « non déterminés », ce qui n'est pas un refus.
    Rend {"permutation": [sujet de la découpe k | None], "marge": float|None, "sujets": [...]}.

    Pourquoi une permutation et pas « la meilleure découpe de chaque sujet » (mesuré le 15/11/2026, DINOv2-
    base sur les découpes réelles du run Zig et Sharko, contre de vraies images de la série) : la découpe
    du requin ressemble PLUS aux ancres de Zig (0,359) que celle de la hyène (0,306) ; chaque sujet pris
    seul aurait donc reçu le requin. La permutation, elle, attribue hyène → Zig et requin → Sharko avec une
    marge de 0,213. Et le requin générique obtient 0,61 contre Sharko sans être Sharko : la similarité
    attribue, elle ne juge jamais l'identité.
    """
    n = int(sim.shape[0])
    if sim.ndim != 2 or sim.shape != (n, n) or n == 0:
        raise ValueError(f"matrice de similarité {tuple(sim.shape)} : il faut autant de découpes que de sujets")
    if n > MAX_SUJETS_ENUMERES:
        raise _Indisponible(f"{n} sujets : au-delà de {MAX_SUJETS_ENUMERES}, l'énumération n'est pas faite")
    avec = [s for s in range(n) if bool(np.all(np.isfinite(sim[:, s])))]
    sans = [s for s in range(n) if s not in avec]
    candidates = []
    for decoupe_de in itertools.permutations(range(n)):       # decoupe_de[s] = découpe du sujet s
        score = float(np.mean([sim[decoupe_de[s], s] for s in avec])) if avec else 0.0
        candidates.append((score, decoupe_de))
    meilleur_score = max(score for score, _ in candidates)
    # à égalité, l'ordre de mention départage, mais la marge nulle qui en résulte reste visible
    meilleure = min(p for score, p in candidates if score >= meilleur_score - EGALITE)

    def marge(s: int) -> float | None:
        autres = [score for score, p in candidates if p[s] != meilleure[s]]
        return max(0.0, meilleur_score - max(autres)) if autres else None

    sujets = []
    permutation: list[int | None] = [None] * n
    for s in range(n):
        determinee = s in avec or len(sans) == 1
        m = marge(s) if determinee else None
        sujets.append({"indice_decoupe": int(meilleure[s]) if determinee else None,
                       "similarite": round(float(sim[meilleure[s], s]), 6) if s in avec else None,
                       "marge": None if m is None else round(m, 6),
                       "determinee": determinee})
        if determinee:
            permutation[meilleure[s]] = s
    marges = [sujets[s]["marge"] for s in avec if sujets[s]["marge"] is not None]
    return {"permutation": permutation, "marge": min(marges) if marges else None, "sujets": sujets,
            "similarites": [[None if not np.isfinite(v) else round(float(v), 6) for v in ligne] for ligne in sim]}


# ── Votes de vision ────────────────────────────────────────────────────────────────────────────────
def _positions(numeros: list[int]) -> str:
    if len(numeros) == 1:
        return f"Image {numeros[0]}"
    return "Images " + ", ".join(str(n) for n in numeros[:-1]) + f" et {numeros[-1]}"


def _questions_posees(spec: dict[str, Any], contrat: dict[str, Any], mode: str) -> list[str]:
    posees = []
    for cle, _, _ in QUESTIONS:
        if cle in QUESTIONS_SUR_ANCRES and not spec["ancres"]:
            continue                            # rien à comparer : la question n'a pas de sens
        if cle == "nature_conforme" and not (spec["nature"] or spec["nature_en"]):
            continue
        if cle == "style_conforme" and _description_style(contrat, mode) is None:
            continue
        posees.append(cle)
    return posees


def _question(spec: dict[str, Any], contrat: dict[str, Any], mode: str, position: int, n_images: int,
              posees: list[str]) -> str:
    """La question d'un vote, les numéros d'images recalculés pour la position du candidat."""
    candidat = position + 1
    lignes = ["Tu vérifies, image à l'appui, qu'un sujet généré correspond à la demande.",
              f"Image {candidat} = CANDIDAT : {_CANDIDAT[mode]}."]
    ancres = [i + 1 for i in range(n_images) if i != position]
    nature = spec["nature"] + (f" ({spec['nature_en']})" if spec["nature_en"] else "") if spec["nature"] else spec["nature_en"]
    if ancres:
        qui = f"« {spec['nom']} »" if spec["nom"] else "ce sujet"
        lignes.append(f"{_positions(ancres)} = ANCRES : de vraies images de {qui}"
                      + (f" ({nature})" if nature else "")
                      + ", retenues parce que plusieurs sources indépendantes concordent.")
        _, texte = _style(contrat)
        if texte:
            lignes.append(f"La demande veut ce personnage en « {texte} » : un changement de style de rendu par "
                          "rapport aux ancres est voulu et ne compte jamais contre l'identité.")
        attributs = spec["attributs"]
        releves = []
        if isinstance(attributs.get("plan_du_corps"), str) and attributs["plan_du_corps"].strip():
            releves.append(f"plan du corps : {attributs['plan_du_corps'].strip()}")
        if isinstance(attributs.get("vetements"), str) and attributs["vetements"].strip():
            releves.append(f"vêtements : {attributs['vetements'].strip()}")
        couleurs = [c for c in attributs.get("couleurs") or [] if isinstance(c, str) and c.strip()]
        if couleurs:
            releves.append("couleurs : " + ", ".join(c.strip() for c in couleurs))
        if releves:
            lignes.append("Relevé sur les ancres — " + " ; ".join(releves) + ".")
    lignes.append("Réponds STRICTEMENT en JSON par des booléens factuels :")
    textes = {
        "meme_personnage": "en ignorant le style de rendu, le CANDIDAT est-il le MÊME personnage que les ANCRES "
                           "(forme de la tête et du corps, proportions, couleurs et motifs, signes distinctifs) ? "
                           "Un autre individu de la même espèce n'est PAS le même personnage.",
        "plan_du_corps_conforme": "le CANDIDAT a-t-il le même plan du corps que les ANCRES (nombre et type de "
                                  "membres, nageoires, queue ; appui sur deux jambes, sur quatre pattes ou sans "
                                  "pattes) ?",
        "vetement_ajoute": "le CANDIDAT porte-t-il un vêtement ou un accessoire qu'AUCUNE ancre ne montre ?",
        "nature_conforme": f"le CANDIDAT est-il bien {nature} ?",
        "style_conforme": f"le CANDIDAT a-t-il {_description_style(contrat, mode)} ?",
    }
    for cle in posees:
        lignes.append(f"- {cle} : {textes[cle]}")
    lignes.append("JSON strict : {" + ", ".join(f'"{cle}": true|false' for cle in posees) + "}")
    return "\n".join(lignes)


def _lire_vote(reponse: Any, posees: list[str]) -> dict[str, Any]:
    """Les booléens des questions posées ; tout le reste (non posé, illisible, erreur) vaut None."""
    if isinstance(reponse, BaseException):
        donnees, brut = None, f"erreur : {type(reponse).__name__}: {reponse}"
    elif isinstance(reponse, dict):
        donnees, brut = reponse, json.dumps(reponse, ensure_ascii=False, default=str)
    elif isinstance(reponse, str):
        donnees, brut = _extraire_json(reponse), reponse
    else:
        donnees, brut = None, repr(reponse)
    lues = {_normaliser(k).replace(" ", "_"): v for k, v in (donnees or {}).items()}
    vote: dict[str, Any] = {cle: (_booleen(lues.get(cle)) if cle in posees else None) for cle, _, _ in QUESTIONS}
    vote["brut"] = brut[:600]
    return vote


def _decider(valeurs: list[bool | None], favorable: bool, essais: int, requis: int) -> dict[str, Any]:
    """Accepté si `requis` votes sont favorables ; refusé si, même en comptant favorables tous les votes
    muets ou non exprimés, on ne peut plus les atteindre ; indisponible sinon (un juge muet n'accorde rien)."""
    pour = sum(1 for v in valeurs if v is favorable)
    contre = sum(1 for v in valeurs if v is (not favorable))
    if pour >= requis:
        decision = "accepte"
    elif contre > essais - requis:
        decision = "refuse"
    else:
        decision = "indisponible"
    return {"decision": decision, "favorables": pour, "defavorables": contre,
            "muets": len(valeurs) - pour - contre, "non_exprimes": essais - len(valeurs)}


def _voter_sujet(spec: dict[str, Any], candidats: list[str], contrat: dict[str, Any], mode: str,
                 voter: Callable[[list[str], str], Any], essais: int,
                 requis: int) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    """Jusqu'à `essais` votes décorrélés : à chaque vote, le candidat change de place, les ancres
    tournent (et un autre rendu sert de candidat s'il y en a plusieurs). On s'arrête dès que chaque axe
    est tranché — un vote de plus ne pourrait plus changer le verdict — pour épargner le modèle de vision
    (15 à 70 s par appel sur ce poste)."""
    posees = _questions_posees(spec, contrat, mode)
    votes: list[dict[str, Any]] = []
    decisions: dict[str, dict[str, Any]] = {}
    if not posees:
        return votes, decisions
    for tour in range(essais):
        candidat = candidats[tour % len(candidats)]
        ancres = spec["ancres"]
        if ancres:
            decalage = tour % len(ancres)
            choisies = (ancres[decalage:] + ancres[:decalage])[:MAX_ANCRES_PAR_VOTE]
        else:
            choisies = []
        position = tour % (len(choisies) + 1)
        images = choisies[:position] + [candidat] + choisies[position:]
        question = _question(spec, contrat, mode, position, len(images), posees)
        try:
            reponse = voter(list(images), question)
        except Exception as exc:  # noqa: BLE001 — un juge qui plante est un vote muet
            reponse = exc
        vote = _lire_vote(reponse, posees)
        vote["images"] = list(images)
        votes.append(vote)
        decisions = {}
        for cle, axe, favorable in QUESTIONS:
            if cle in posees:
                decisions[axe] = _decider([v[cle] for v in votes], favorable, essais,
                                          essais if axe in AXES_UNANIMES else requis)
        if all(d["decision"] != "indisponible" for d in decisions.values()):
            break
    return votes, decisions


def _raison_axe(axe: str, spec: dict[str, Any], decision: dict[str, Any], contrat: dict[str, Any],
                mode: str) -> str:
    """Une raison en français, formulée comme la correction à apporter au prochain essai."""
    qui = _libelle(spec)
    compte = f"{decision['defavorables']} vote(s) contre, {decision['favorables']} pour"
    # Ces raisons repartent dans la consigne du rendu suivant (« CORRECTIONS ») : elles renvoient aux
    # ancres et ne recopient JAMAIS les attributs lus par la vision (vêtements, plan du corps). Recopiés,
    # « aucun » devenait un ordre de dévêtir et un attribut d'un sujet fuyait vers l'autre (15/11/2026).
    if axe == "identite":
        return (f"{qui} : le candidat n'est pas reconnu comme le personnage des ancres ({compte}) — reprendre "
                "ses invariants d'identité : forme de la tête et du corps, proportions, couleurs et motifs, "
                "signes distinctifs.")
    if axe == "plan_du_corps":
        return f"{qui} : plan du corps différent des ancres ({compte}) — reprendre exactement celui des ancres."
    if axe == "vetement":
        return (f"{qui} : vêtement ou accessoire absent des ancres ({compte}) — reprendre exactement la tenue "
                "et les accessoires visibles sur les ancres, sans rien ajouter.")
    if axe == "nature":
        nature = spec["nature"] or spec["nature_en"]
        return f"{qui} : le candidat n'est pas {nature} ({compte}) — le sujet doit être {nature}."
    if axe == "style":
        _, texte = _style(contrat)
        return (f"{qui} : rendu différent du style demandé" + (f" « {texte} »" if texte else "")
                + f" ({compte}) — viser {_description_style(contrat, mode)}.")
    return f"{qui} : axe {axe} refusé ({compte})."


# ── Assemblage du verdict ──────────────────────────────────────────────────────────────────────────
def _entree_sujet(spec: dict[str, Any], candidats: list[str] | None,
                  attribution: dict[str, Any] | None, attr_sujet: dict[str, Any] | None) -> dict[str, Any]:
    return {
        "index": spec["index"],
        "nom": spec["nom"],
        "decoupe": candidats[0] if candidats else None,
        "attribution": {
            "permutation": attribution["permutation"] if attribution else None,
            "marge": attr_sujet["marge"] if attr_sujet else None,
            "indice_decoupe": attr_sujet["indice_decoupe"] if attr_sujet else None,
            "similarite": attr_sujet["similarite"] if attr_sujet else None,
            "determinee": attr_sujet["determinee"] if attr_sujet else False,
        },
        "votes": [],
        "axes": {},
        "axes_refuses": [],
        "raisons": [],
        "non_juges": [],
        "statut": "indisponible",
    }


def _conclure(entree: dict[str, Any], indisponibles: list[str]) -> None:
    """`raisons` : les corrections d'un refus, ou ce qui manque pour juger ; `non_juges` : toujours ce
    qui n'a pas pu être jugé, pour qu'un refus ne cache pas une identité restée non vérifiée."""
    entree["non_juges"] = list(dict.fromkeys(indisponibles))
    if entree["axes_refuses"]:
        entree["statut"] = "refuse"
    elif indisponibles:
        entree["statut"] = "indisponible"
        entree["raisons"].extend(r for r in entree["non_juges"] if r not in entree["raisons"])
    else:
        entree["statut"] = "accepte"


def _verdict(base: dict[str, Any], entrees: list[dict[str, Any]], t0: float) -> dict[str, Any]:
    """Refus dès qu'un axe mesuré échoue ; indisponible si quelque chose n'a pu être jugé ; accepté sinon."""
    refuses = [e for e in entrees if e["statut"] == "refuse"]
    indispo = [e for e in entrees if e["statut"] == "indisponible"]
    if refuses:
        verdict = "refuse"
        raison = "Refusé — " + " ; ".join(
            f"{e['nom'] or 'sujet ' + str(e['index'] + 1)} : {', '.join(e['axes_refuses'])}" for e in refuses)
    elif indispo:
        verdict = "indisponible"
        raison = "Non jugé — " + " ; ".join(
            f"{e['nom'] or 'sujet ' + str(e['index'] + 1)} : {(e['raisons'] or ['raison inconnue'])[0]}"
            for e in indispo)
    else:
        verdict, raison = "accepte", None
    axes = sorted({a for e in entrees for a in e["axes_refuses"]}, key=AXES.index)
    return {**base, "verdict": verdict, "sujets": entrees, "axes_refuses": axes, "raison": raison,
            "duree_s": round(time.monotonic() - t0, 3)}


def _indisponible(base: dict[str, Any], specs: list[dict[str, Any]] | None, raison: str,
                  t0: float) -> dict[str, Any]:
    entrees = []
    for spec in specs or []:
        entree = _entree_sujet(spec, None, None, None)
        entree["raisons"].append(raison)
        entree["non_juges"].append(raison)
        entrees.append(entree)
    return {**base, "verdict": "indisponible", "sujets": entrees, "axes_refuses": [], "raison": raison,
            "duree_s": round(time.monotonic() - t0, 3)}


def _refus_nombre(base: dict[str, Any], specs: list[dict[str, Any]], raison: str,
                  candidats: dict[int, list[str]] | None, t0: float) -> dict[str, Any]:
    """Le nombre ne correspond pas : personne n'est jugé, chaque sujet porte le refus « nombre »."""
    entrees = []
    for spec in specs:
        entree = _entree_sujet(spec, (candidats or {}).get(spec["index"]) or None, None, None)
        if candidats is not None:
            entree["rendus"] = list((candidats or {}).get(spec["index"]) or [])
        entree["axes_refuses"].append("nombre")
        entree["raisons"].append(raison)
        entree["statut"] = "refuse"
        entrees.append(entree)
    resultat = _verdict(base, entrees, t0)
    resultat["raison"] = f"Refusé — nombre : {raison}"
    return resultat


def _raison_nombre_decoupes(n_trouves: int, n_sujets: int) -> str:
    if n_trouves == 0 and n_sujets >= 2:
        return (f"aucune séparation nette entre les {n_sujets} sujets demandés : la reconstruction traiterait "
                f"l'image comme un seul corps — montrer exactement {n_sujets} sujets entiers, séparés par un "
                "écart net, sans contact.")
    if n_trouves < n_sujets:
        return (f"{n_trouves} silhouette(s) séparable(s) pour {n_sujets} sujets demandés : un sujet manque ou "
                f"deux sujets se touchent — montrer exactement {n_sujets} sujets entiers, séparés par un écart "
                "net, sans contact.")
    return (f"{n_trouves} silhouettes séparables pour {n_sujets} sujet(s) demandé(s) : un sujet en trop ou un "
            f"élément détaché — montrer exactement {n_sujets} sujet(s) entier(s), rien d'autre.")


def _juger(mode: str, base: dict[str, Any], specs: list[dict[str, Any]], candidats: list[list[str]],
           contrat: dict[str, Any], seuils: dict[str, Any], embarquer: Callable[[list[str]], Any] | None,
           voter: Callable[[list[str], str], Any] | None, vision: bool, exiger_ordre_mention: bool,
           attribution_revendiquee: bool, t0: float) -> dict[str, Any]:
    """Tronc commun : attribution par les ancres, puis votes de vision sur les sujets bien attribués."""
    n = len(specs)
    attribution: dict[str, Any] | None = None
    if n == 1:
        attribution = {"permutation": [0], "marge": None, "similarites": None,
                       "sujets": [{"indice_decoupe": 0, "similarite": None, "marge": None, "determinee": True}]}
    else:
        if not any(spec["ancres"] for spec in specs):
            return _indisponible(base, specs, f"aucun des {n} sujets n'a d'ancre établie : impossible de dire "
                                              "quelle découpe montre quel sujet", t0)
        try:
            attribution = attribuer(_similarites(embarquer or _embarquer_defaut, candidats, specs))
        except _Indisponible as exc:
            return _indisponible(base, specs, f"attribution non mesurée : {exc}", t0)
    base = {**base, "attribution": {k: attribution[k] for k in ("permutation", "marge", "similarites")}}
    marge_min = seuils["marge_attribution_min"]
    entrees = []
    for spec in specs:
        s = spec["index"]
        attr = attribution["sujets"][s]
        k = attr["indice_decoupe"]
        # juger_modele : le candidat de s est revendiqué ; juger_reference : celui que l'attribution désigne
        mes_candidats = candidats[s] if attribution_revendiquee else (candidats[k] if k is not None else None)
        entree = _entree_sujet(spec, mes_candidats, attribution, attr)
        if mode == "modele":
            entree["rendus"] = list(candidats[s])
        indisponibles: list[str] = []
        attribution_sure = False
        if not attr["determinee"]:
            indisponibles.append("attribution indéterminée : plusieurs sujets sans ancre établie")
        elif attribution_revendiquee and k != s:
            autre = next((sp for sp in specs if attribution["sujets"][sp["index"]]["indice_decoupe"] == s), None)
            entree["axes_refuses"].append("attribution")
            entree["raisons"].append(
                f"{_libelle(spec)} : le personnage livré pour ce sujet ressemble davantage aux ancres de "
                f"{_libelle(autre) if autre else 'un autre sujet'} — personnages échangés ou identités mêlées "
                "à la reconstruction.")
        elif attr["marge"] is not None and attr["marge"] < marge_min:
            ecart = f"(marge {_virgule(attr['marge'])} < {_virgule(marge_min)})"
            entree["axes_refuses"].append("attribution")
            if spec["ancres"]:
                rivaux = [_libelle(sp) for sp in specs if sp["index"] != s and sp["ancres"]]
                entree["raisons"].append(
                    f"{_libelle(spec)} : attribution ambiguë, son candidat ressemble presque autant aux ancres de "
                    + (" ou ".join(rivaux) if rivaux else "un autre sujet")
                    + f" {ecart} — distinguer nettement les sujets, sans attribut partagé.")
            else:
                entree["raisons"].append(
                    f"{_libelle(spec)} : candidat attribué par élimination, sur une attribution ambiguë des autres "
                    f"sujets {ecart} — distinguer nettement les sujets, sans attribut partagé.")
        elif exiger_ordre_mention and not attribution_revendiquee and k != s:
            entree["axes_refuses"].append("attribution")
            entree["raisons"].append(
                f"{_libelle(spec)} : placé en position {k + 1} au lieu de {s + 1} — respecter l'ordre de "
                "mention de la demande, de gauche à droite.")
        else:
            attribution_sure = True
        if spec["nomme"] and not spec["etabli"]:
            indisponibles.append(f"identité de {_libelle(spec)} non établie"
                                 + (f" : {spec['raison_dossier']}" if spec["raison_dossier"] else "")
                                 + " — joindre une image du sujet ou continuer sans vérification d'identité.")
        if attribution_sure and mes_candidats:
            if not vision:
                indisponibles.append("vision désactivée : identité, plan du corps, vêtement, nature et style "
                                     "non jugés.")
            else:
                votes, decisions = _voter_sujet(spec, mes_candidats, contrat, mode, voter or _voter_defaut,
                                                seuils["essais_votes"], seuils["votes_requis"])
                entree["votes"], entree["axes"] = votes, decisions
                if not decisions:
                    indisponibles.append("aucune question applicable : ni ancre, ni nature, ni style à juger.")
                for axe, decision in decisions.items():
                    if decision["decision"] == "refuse":
                        entree["axes_refuses"].append(axe)
                        entree["raisons"].append(_raison_axe(axe, spec, decision, contrat, mode))
                    elif decision["decision"] == "indisponible":
                        indisponibles.append(
                            f"juge muet ou illisible sur l'axe {axe} ({decision['favorables']} vote(s) pour, "
                            f"{decision['muets']} muet(s), {decision['non_exprimes']} non exprimé(s)).")
        _conclure(entree, indisponibles)
        entrees.append(entree)
    return _verdict(base, entrees, t0)


def _base(mode: str, seuils: dict[str, Any], **champs: Any) -> dict[str, Any]:
    return {"schema": SCHEMA, "mode": mode, **champs, "seuils": seuils}


# ── API ────────────────────────────────────────────────────────────────────────────────────────────
def juger_reference(image_path: str | Path, dossier: dict[str, Any], contrat: dict[str, Any], *,
                    decouper: Callable[[str, str, str], list[dict[str, Any]]] | None = None,
                    embarquer: Callable[[list[str]], Any] | None = None,
                    voter: Callable[[list[str], str], Any] | None = None,
                    essais_votes: int = 3,
                    seuils: dict[str, Any] | None = None,
                    chemin_cliquet: str | Path | None = None,
                    dossier_decoupes: str | Path | None = None,
                    run_id: str | None = None,
                    vision: bool = True,
                    exiger_ordre_mention: bool = False) -> dict[str, Any]:
    """Juge une référence générée contre le dossier d'identité et le contrat de demande.

    `image_path` doit être l'image que le pipeline découpera pour TRELLIS (sa source RGBA). Les découpes
    du juge sont écrites dans `dossier_decoupes` (par défaut `<dossier de l'image>/<nom>_juge_identite/`)
    et restent la preuve de ce qui a été jugé. `decouper(image, dossier, run_id)`, `embarquer(chemins)`
    et `voter(images, question)` remplacent les modèles réels ; `seuils` remplace la lecture du cliquet.
    `exiger_ordre_mention` : à n'utiliser que si le générateur a reçu l'ordre gauche-droite à respecter ;
    sinon l'attribution mesurée suffit, elle est transmise telle quelle à la suite (animation, milieu).
    """
    t0 = time.monotonic()
    if int(essais_votes) < 3:
        # un seul vote n'est ni une majorité ni décorrélé : jamais moins de trois (relecture du 15/11/2026)
        raise ValueError("essais_votes doit valoir au moins 3")
    seuils_e = _seuils_effectifs(seuils, chemin_cliquet, int(essais_votes))
    image = Path(image_path)
    base = _base("reference", seuils_e, image=str(image))
    probleme = _probleme_entrees(dossier, contrat)
    if probleme:
        return _indisponible(base, None, probleme, t0)
    specs = _sujets(dossier, contrat)
    if not image.is_file():
        return _indisponible(base, specs, f"image à juger introuvable : {image}", t0)
    sortie = Path(dossier_decoupes) if dossier_decoupes else image.parent / f"{image.stem}_juge_identite"
    try:
        decoupes = (decouper or _decouper_defaut)(str(image), str(sortie), run_id or image.stem)
    except Exception as exc:  # noqa: BLE001 — l'outil a échoué, l'image n'est pas jugée fautive pour autant
        return _indisponible(base, specs, f"découpage impossible ({type(exc).__name__}: {exc})"[:240], t0)
    chemins = [str(d.get("ref_path")) for d in decoupes or [] if isinstance(d, dict) and d.get("ref_path")]
    if not chemins and len(specs) == 1:
        chemins = [str(image)]                  # un seul sujet : TRELLIS reconstruit l'image entière
    base["nombre"] = {"decoupes": len(chemins), "sujets": len(specs)}
    if len(chemins) != len(specs):
        return _refus_nombre(base, specs, _raison_nombre_decoupes(len(chemins), len(specs)), None, t0)
    manquantes = [c for c in chemins if not Path(c).is_file()]
    if manquantes:
        return _indisponible(base, specs, f"découpe annoncée mais absente : {manquantes[0]}", t0)
    return _juger("image", base, specs, [[c] for c in chemins], contrat, seuils_e, embarquer, voter,
                  vision, exiger_ordre_mention, False, t0)


def juger_modele(renders: dict[int, list[str]], dossier: dict[str, Any], contrat: dict[str, Any], *,
                 embarquer: Callable[[list[str]], Any] | None = None,
                 voter: Callable[[list[str], str], Any] | None = None,
                 essais_votes: int = 3,
                 seuils: dict[str, Any] | None = None,
                 chemin_cliquet: str | Path | None = None,
                 vision: bool = True) -> dict[str, Any]:
    """Juge les personnages LIVRÉS : `renders[s]` = rendus f3d du personnage livré pour le sujet s.

    La géométrie reste jugée ailleurs contre la référence ; ici l'identité, contre les ancres. Les clés
    sont les indices des sujets du contrat (l'attribution acceptée sur la référence) : un personnage
    livré qui ressemble davantage aux ancres d'un autre sujet est refusé (axe « attribution »), un sujet
    sans personnage livré aussi (axe « nombre »).
    """
    t0 = time.monotonic()
    if int(essais_votes) < 3:
        # un seul vote n'est ni une majorité ni décorrélé : jamais moins de trois (relecture du 15/11/2026)
        raise ValueError("essais_votes doit valoir au moins 3")
    seuils_e = _seuils_effectifs(seuils, chemin_cliquet, int(essais_votes))
    base = _base("modele", seuils_e)
    probleme = _probleme_entrees(dossier, contrat)
    if probleme:
        return _indisponible(base, None, probleme, t0)
    specs = _sujets(dossier, contrat)
    rendus: dict[int, list[str]] = {}
    for cle, chemins in (renders or {}).items():
        try:
            indice = int(cle)
        except (TypeError, ValueError):
            return _indisponible(base, specs, f"clé de rendu illisible : {cle!r}", t0)
        liste = [chemins] if isinstance(chemins, (str, Path)) else list(chemins or [])
        rendus[indice] = [str(p) for p in liste if isinstance(p, (str, Path))]
    livres = {s for s, liste in rendus.items() if liste}
    attendus = set(range(len(specs)))
    base["nombre"] = {"personnages": len(livres), "sujets": len(specs)}
    if livres != attendus:
        morceaux = []
        if attendus - livres:
            morceaux.append("aucun personnage livré pour " + ", ".join(
                _libelle(specs[s]) for s in sorted(attendus - livres)))
        if livres - attendus:
            morceaux.append(f"rendus pour des sujets que la demande ne contient pas {sorted(livres - attendus)}")
        raison = (" ; ".join(morceaux) + f" — livrer exactement {len(specs)} personnage(s), un par sujet, "
                  "chacun reconstruit séparément.")
        return _refus_nombre(base, specs, raison, rendus, t0)
    absents = [p for s in range(len(specs)) for p in rendus[s] if not Path(p).is_file()]
    if absents:
        return _indisponible(base, specs, f"rendu f3d absent : {absents[0]}", t0)
    return _juger("modele", base, specs, [rendus[s] for s in range(len(specs))], contrat, seuils_e,
                  embarquer, voter, vision, False, True, t0)


# ── Ligne de commande ──────────────────────────────────────────────────────────────────────────────
def _lire_json(chemin: str) -> Any:
    return json.loads(Path(chemin).read_text(encoding="utf-8"))


def _rendus(arguments: Iterable[str]) -> dict[int, list[str]]:
    rendus: dict[int, list[str]] = {}
    for texte in arguments:
        indice, _, chemins = texte.partition("=")
        rendus.setdefault(int(indice), []).extend(c for c in chemins.split(",") if c)
    return rendus


def main(argv: list[str] | None = None) -> int:
    analyseur = argparse.ArgumentParser(description="Juge une référence (ou les personnages livrés) contre "
                                                    "le dossier d'identité et le contrat de demande")
    analyseur.add_argument("--image", help="référence à juger (la source RGBA que TRELLIS découpera)")
    analyseur.add_argument("--rendu", action="append", default=[],
                           help="rendus f3d d'un personnage livré : <indice du sujet>=<png>[,<png>…]")
    analyseur.add_argument("--dossier", required=True, help="identite.json (aurora.identite-visuelle.v1)")
    analyseur.add_argument("--contrat", required=True, help="contrat de demande (aurora.lecture-demande.v2)")
    analyseur.add_argument("--decoupes", default=None, help="dossier où écrire les découpes jugées")
    analyseur.add_argument("--run-id", default=None)
    analyseur.add_argument("--essais-votes", type=int, default=3)
    analyseur.add_argument("--sans-vision", action="store_true",
                           help="nombre et attribution seulement (CPU) : le verdict ne peut pas être accepté")
    analyseur.add_argument("--exiger-ordre", action="store_true",
                           help="refuser un ordre gauche-droite différent de l'ordre de mention")
    analyseur.add_argument("--cliquet", default=None,
                           help="état de la famille « identité » (par défaut modele/renforce/judge_ratchet_identite.json)")
    analyseur.add_argument("--sortie", default=None, help="fichier JSON où écrire le verdict")
    arguments = analyseur.parse_args(argv)
    if bool(arguments.image) == bool(arguments.rendu):
        analyseur.error("donner --image (référence) OU --rendu (personnages livrés)")
    dossier, contrat = _lire_json(arguments.dossier), _lire_json(arguments.contrat)
    if arguments.image:
        resultat = juger_reference(arguments.image, dossier, contrat, essais_votes=arguments.essais_votes,
                                   chemin_cliquet=arguments.cliquet, dossier_decoupes=arguments.decoupes,
                                   run_id=arguments.run_id, vision=not arguments.sans_vision,
                                   exiger_ordre_mention=arguments.exiger_ordre)
    else:
        resultat = juger_modele(_rendus(arguments.rendu), dossier, contrat, essais_votes=arguments.essais_votes,
                                chemin_cliquet=arguments.cliquet, vision=not arguments.sans_vision)
    if arguments.sortie:
        Path(arguments.sortie).parent.mkdir(parents=True, exist_ok=True)
        Path(arguments.sortie).write_text(json.dumps(resultat, ensure_ascii=False, indent=2), encoding="utf-8")
    # une seule ligne : les appelants (interface, pont) lisent la dernière ligne JSON de la sortie ; le
    # verdict est dans ce JSON, le code de sortie ne signale qu'un plantage
    print(json.dumps(resultat, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
