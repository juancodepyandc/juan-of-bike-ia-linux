#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""meshy_client — reconstruction 3D par le service Meshy.

Voie principale de creation quand le service repond. La cle n'est jamais
ecrite dans le code : elle vient de la variable MESHY_API_KEY, sinon du
fichier .secrets/meshy.key (ignore par git).

Deux entrees, selon ce dont on dispose :
  - `depuis_image` quand une reference existe (le cas courant : le pipeline
    fabrique et valide une reference avant de reconstruire) ;
  - `depuis_texte` sinon.

Chaque tache passe par deux etapes cote service : `preview` produit la
geometrie, `refine` y applique les textures. On attend la premiere avant de
lancer la seconde, puis on telecharge le GLB.
"""
from __future__ import annotations

import base64
import json
import mimetypes
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable, Dict, Optional

BASE = "https://api.meshy.ai/openapi"
FICHIER_CLE = Path(__file__).resolve().parents[2] / ".secrets" / "meshy.key"
# Reglages de qualite. Valeurs permises rendues par le service lui-meme
# (une valeur invalide fait lister les valeurs acceptees):
#   ai_model         meshy-4 | meshy-5 | meshy-6 | meshy-7 | latest | meshy-t1 | meshy-t2
#   topology         quad | triangle
#   texture_richness none | low | medium | high
#   symmetry_mode    off | auto | on
#   target_polycount 300 000 au maximum
#   texture_resolution 2k | 4k | 8k
# On vise le haut de chaque echelle: palier le plus recent, topologie en
# quadrangles (propre a rigger et a subdiviser), densite au plafond,
# textures les plus riches. Chaque valeur reste surchargeable par
# l'environnement pour ne pas avoir a toucher au code.
PALIER = os.environ.get("MESHY_MODELE", "meshy-7")
TOPOLOGIE = os.environ.get("MESHY_TOPOLOGIE", "quad")
DENSITE = int(os.environ.get("MESHY_POLYCOUNT", "300000"))
RICHESSE = os.environ.get("MESHY_TEXTURES", "high")
SYMETRIE = os.environ.get("MESHY_SYMETRIE", "auto")
# Ce reglage n'etait PAS transmis: le service retombait donc sur son defaut,
# 2k, et TOUTE la scene sortait en 2048x2048 alors que l'echelle monte a 8k
# (verifie en interrogeant l'API: "TextureResolution must be one of
# [2k 4k 8k]", accepte sur image-to-3d comme sur refine). C'est un facteur 16
# en surface de texte perdu en silence sur chaque objet.
RESOLUTION = os.environ.get("MESHY_RESOLUTION", "8k")


def reglages_qualite() -> Dict[str, Any]:
    """Reglages communs aux deux voies, pour qu'elles ne divergent pas."""
    return {"ai_model": PALIER, "topology": TOPOLOGIE,
            "target_polycount": DENSITE, "texture_richness": RICHESSE,
            "texture_resolution": RESOLUTION,
            "symmetry_mode": SYMETRIE, "should_remesh": True}


DELAI_SONDAGE = 5.0
ATTENTE_MAX = 1800.0


def cle() -> str:
    """Cle d'API, ou chaine vide si aucune n'est configuree."""
    depuis_env = os.environ.get("MESHY_API_KEY", "").strip()
    if depuis_env:
        return depuis_env
    try:
        return FICHIER_CLE.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def _appel(chemin: str, corps: Optional[dict] = None, methode: str = "GET",
           timeout: float = 30.0) -> Dict[str, Any]:
    jeton = cle()
    if not jeton:
        raise RuntimeError("aucune cle d'API configuree")
    donnees = json.dumps(corps).encode() if corps is not None else None
    requete = urllib.request.Request(
        BASE + chemin, data=donnees, method=methode,
        headers={"Authorization": "Bearer " + jeton,
                 "Content-Type": "application/json"})
    with urllib.request.urlopen(requete, timeout=timeout) as reponse:
        brut = reponse.read().decode("utf-8")
    return json.loads(brut) if brut else {}


def joignable(timeout: float = 8.0) -> Dict[str, Any]:
    """Le service repond-il, avec une cle valide ?

    Rend {"ok": bool, "motif": str}. Un service injoignable ou une cle
    refusee n'est pas une erreur : c'est le signal de passer sur la voie
    locale.
    """
    if not cle():
        return {"ok": False, "motif": "aucune cle configuree"}
    try:
        _appel("/v2/text-to-3d?page_size=1", timeout=timeout)
        return {"ok": True, "motif": ""}
    except urllib.error.HTTPError as err:
        if err.code in (401, 403):
            return {"ok": False, "motif": "cle refusee (%d)" % err.code}
        if err.code == 404:
            return {"ok": True, "motif": ""}
        return {"ok": False, "motif": "reponse %d" % err.code}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "motif": repr(exc)}


def _image_en_uri(chemin: str) -> str:
    donnees = Path(chemin).read_bytes()
    type_mime = mimetypes.guess_type(chemin)[0] or "image/png"
    return "data:%s;base64,%s" % (type_mime,
                                  base64.b64encode(donnees).decode("ascii"))


def _attendre(chemin_tache: str, progression: Optional[Callable[[str], None]],
              etiquette: str) -> Dict[str, Any]:
    """Sonde une tache jusqu'a son terme. Rend le dernier etat connu."""
    debut = time.time()
    dernier = -1
    while time.time() - debut < ATTENTE_MAX:
        etat = _appel(chemin_tache)
        statut = str(etat.get("status") or "").upper()
        avancement = int(etat.get("progress") or 0)
        if progression and avancement != dernier:
            progression("%s %d%%" % (etiquette, avancement))
            dernier = avancement
        if statut == "SUCCEEDED":
            return {"ok": True, "tache": etat}
        if statut in ("FAILED", "CANCELED", "EXPIRED"):
            message = ""
            erreur = etat.get("task_error")
            if isinstance(erreur, dict):
                message = str(erreur.get("message") or "")
            return {"ok": False, "erreur": message or statut, "tache": etat}
        time.sleep(DELAI_SONDAGE)
    return {"ok": False, "erreur": "delai depasse (%.0f s)" % ATTENTE_MAX}


def _telecharger(url: str, sortie: Path) -> None:
    sortie.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url, timeout=300) as reponse:
        sortie.write_bytes(reponse.read())


def _produire(chemin_creation: str, corps_apercu: dict, sortie: str | Path,
              progression: Optional[Callable[[str], None]] = None,
              texturer: bool = True) -> Dict[str, Any]:
    """Apercu -> affinage -> telechargement du GLB."""
    sortie = Path(sortie)
    cree = _appel(chemin_creation, corps_apercu, methode="POST", timeout=60.0)
    tache = str(cree.get("result") or "")
    if not tache:
        return {"ok": False, "erreur": "aucun identifiant de tache rendu"}
    fin = _attendre("%s/%s" % (chemin_creation, tache), progression, "geometrie")
    if not fin["ok"]:
        return {"ok": False, "erreur": fin.get("erreur", "apercu en echec"),
                "tache_apercu": tache}

    tache_finale, etat = tache, fin["tache"]
    if texturer:
        corps_affinage = {"mode": "refine", "preview_task_id": tache}
        try:
            affine = _appel(chemin_creation, corps_affinage, methode="POST",
                            timeout=60.0)
            suite = str(affine.get("result") or "")
            if suite:
                fin2 = _attendre("%s/%s" % (chemin_creation, suite), progression,
                                 "textures")
                if fin2["ok"]:
                    tache_finale, etat = suite, fin2["tache"]
                elif progression:
                    progression("textures indisponibles (%s) — geometrie conservee"
                                % fin2.get("erreur", ""))
        except Exception as exc:  # noqa: BLE001
            if progression:
                progression("affinage impossible (%r) — geometrie conservee" % exc)

    liens = etat.get("model_urls") or {}
    url_glb = liens.get("glb")
    if not url_glb:
        return {"ok": False, "erreur": "aucun GLB dans la reponse",
                "tache": tache_finale}
    _telecharger(url_glb, sortie)
    octets = sortie.stat().st_size if sortie.is_file() else 0
    if octets < 1024:
        return {"ok": False, "erreur": "GLB vide (%d octets)" % octets}
    return {"ok": True, "glb": str(sortie), "octets": octets,
            "tache": tache_finale,
            "texture": bool(etat.get("texture_urls") or texturer)}


def depuis_image(image: str, sortie: str | Path,
                 progression: Optional[Callable[[str], None]] = None,
                 texturer: bool = True) -> Dict[str, Any]:
    """Reconstruit un GLB texture a partir d'une image de reference."""
    if not Path(image).is_file():
        return {"ok": False, "erreur": "reference introuvable: %s" % image}
    # `enable_pbr` texture en une seule passe: cet endpoint n'a pas d'etape
    # d'affinage separee, et la demander rend un 400 (mesure le 26/08 — la
    # geometrie arrivait bien avec ses 3 textures, l'appel en trop ne
    # servait qu'a produire une erreur dans le journal).
    corps = {"image_url": _image_en_uri(image),
             "enable_pbr": bool(texturer), **reglages_qualite()}
    return _produire("/v1/image-to-3d", corps, sortie, progression,
                     texturer=False)


def depuis_texte(prompt: str, sortie: str | Path,
                 progression: Optional[Callable[[str], None]] = None,
                 texturer: bool = True) -> Dict[str, Any]:
    """Reconstruit un GLB a partir d'une description."""
    prompt = (prompt or "").strip()
    if not prompt:
        return {"ok": False, "erreur": "prompt vide"}
    corps = {"mode": "preview", "prompt": prompt, **reglages_qualite()}
    return _produire("/v2/text-to-3d", corps, sortie, progression, texturer)


# --- Rig et animation -------------------------------------------------------
# Un personnage fabrique DEJA dans sa pose ne peut plus rien faire: il est
# fige. La voie propre est celle du metier — le construire en T, lui poser un
# squelette, puis lui appliquer une action. Contraintes du service, lues dans
# sa documentation: humanoide TEXTURE, oriente vers +Z, 300 000 faces au plus
# (c'est le plafond que `reglages_qualite` applique deja).
# Catalogue d'actions du service (~600 entrees, cf. sa bibliotheque
# d'animations). Les identifiants sont GENRES: "marche" pointait sur 1 =
# Walking_Woman, une marche feminine appliquee telle quelle a un homme —
# demarche visiblement fausse, signalee par l'utilisateur le 28/08. Chaque
# entree porte desormais le nom EXACT du service en commentaire, pour qu'une
# erreur de ce type se voie a la lecture.
ACTIONS = {
    "attente": 0,                 # Idle
    "marche": 30,                 # Casual_Walk (neutre)
    "marche_femme": 1,            # Walking_Woman
    "marche_assuree": 106,        # Confident_Walk
    "marche_rapide": 115,         # Quick_Walk
    "assis_chaise_femme": 32,     # Chair_Sit_Idle_F
    "assis_chaise_homme": 33,     # Chair_Sit_Idle_M
    "assis_bras_croises": 364,
    "debout_a_assis": 57,         # Stand_to_Sit_Transition_M
    "debout_a_assis_femme": 56,   # Stand_to_Sit_Transition_F
    "assis_a_debout": 53,         # Sit_to_Stand_Transition_M
    "assis_a_debout_femme": 52,   # Sit_to_Stand_Transition_F
    "marche_puis_assis": 60,      # Walk_to_Sit — marche PUIS s'assoit
    "assis_repond": 307,          # Sitting_Answering_Questions
    "assis_boit": 343,            # Sit_and_Drink
}


def rigger(sortie: str | Path, tache_source: str = "", url_modele: str = "",
           hauteur_m: float = 1.7,
           progression: Optional[Callable[[str], None]] = None) -> Dict[str, Any]:
    """Pose un squelette sur un humanoide et telecharge le GLB rige."""
    if not tache_source and not url_modele:
        return {"ok": False, "erreur": "ni tache source ni URL de modele"}
    corps: Dict[str, Any] = {"height_meters": float(hauteur_m)}
    if tache_source:
        corps["input_task_id"] = tache_source
    if url_modele:
        corps["model_url"] = url_modele
    try:
        cree = _appel("/v1/rigging", corps, methode="POST", timeout=60.0)
    except urllib.error.HTTPError as err:
        return {"ok": False, "erreur": "%d %s" % (err.code,
                                                  err.read().decode()[:200])}
    tache = str(cree.get("result") or "")
    if not tache:
        return {"ok": False, "erreur": "aucun identifiant de tache rendu"}
    fin = _attendre("/v1/rigging/%s" % tache, progression, "squelette")
    if not fin["ok"]:
        return {"ok": False, "erreur": fin.get("erreur", "rig en echec"),
                "tache": tache}
    # Le rig ne range pas ses liens comme les autres taches: `result` porte
    # `rigged_character_glb_url` (et son pendant FBX), plus un jeu
    # d'animations de base marche/course.
    res = fin["tache"].get("result") or {}
    url = res.get("rigged_character_glb_url") if isinstance(res, dict) else None
    if not url:
        return {"ok": False, "erreur": "aucun GLB rige dans la reponse",
                "tache": tache, "reponse": str(fin["tache"])[:300]}
    sortie = Path(sortie)
    _telecharger(url, sortie)
    return {"ok": True, "glb": str(sortie), "tache": tache,
            "fbx": res.get("rigged_character_fbx_url"),
            "animations_de_base": list((res.get("basic_animations") or {}).keys()),
            "octets": sortie.stat().st_size}


def animer(tache_rig: str, action: int | str, sortie: str | Path,
           progression: Optional[Callable[[str], None]] = None) -> Dict[str, Any]:
    """Applique une action du catalogue au personnage rige."""
    identifiant = ACTIONS.get(action, action) if isinstance(action, str) else action
    try:
        identifiant = int(identifiant)
    except (TypeError, ValueError):
        return {"ok": False, "erreur": "action inconnue: %r" % (action,)}
    corps = {"rig_task_id": tache_rig, "action_id": identifiant}
    try:
        cree = _appel("/v1/animations", corps, methode="POST", timeout=60.0)
    except urllib.error.HTTPError as err:
        return {"ok": False, "erreur": "%d %s" % (err.code,
                                                  err.read().decode()[:200])}
    tache = str(cree.get("result") or "")
    if not tache:
        return {"ok": False, "erreur": "aucun identifiant de tache rendu"}
    fin = _attendre("/v1/animations/%s" % tache, progression, "animation")
    if not fin["ok"]:
        return {"ok": False, "erreur": fin.get("erreur", "animation en echec"),
                "tache": tache}
    # Comme le rig, l'animation range ses liens sous `result`, avec ses
    # propres noms de champs (`animation_glb_url`).
    res = fin["tache"].get("result") or {}
    url = res.get("animation_glb_url") if isinstance(res, dict) else None
    if not url:
        return {"ok": False, "erreur": "aucun GLB anime dans la reponse",
                "tache": tache, "reponse": str(fin["tache"])[:300]}
    sortie = Path(sortie)
    _telecharger(url, sortie)
    return {"ok": True, "glb": str(sortie), "tache": tache,
            "action_id": identifiant, "fbx": res.get("animation_fbx_url"),
            "octets": sortie.stat().st_size}


def remailler(sortie: str | Path, tache_source: str = "", url_modele: str = "",
              densite: int = 300000, topologie: str = "quad",
              progression: Optional[Callable[[str], None]] = None) -> Dict[str, Any]:
    """Redescend un maillage sous le plafond du rig.

    `target_polycount` a la creation ne borne que l'apercu: apres texturation
    le maillage remonte, et le rig refuse au-dela de 320 000. Le service
    expose son propre remailleur pour cela — on l'utilise plutot que de
    decimer nous memes, ce qui casserait les UV.

    A savoir en lisant les chiffres: `target_polycount` compte des
    QUADRANGLES. 300 000 quads ressortent a ~600 000 triangles une fois le
    GLB triangule (596 771 mesures), ce qui donne l'impression que le
    remaillage n'a rien reduit. Le rig, lui, compte en quads: il accepte.

    `origin_at="bottom"` place l'origine aux pieds de l'objet, ce qui evite
    au compositeur de deviner ou est le sol.
    """
    if not tache_source and not url_modele:
        return {"ok": False, "erreur": "ni tache source ni URL de modele"}
    corps: Dict[str, Any] = {"target_polycount": int(densite),
                             "topology": topologie, "origin_at": "bottom",
                             "target_formats": ["glb"]}
    if tache_source:
        corps["input_task_id"] = tache_source
    if url_modele:
        corps["model_url"] = url_modele
    try:
        cree = _appel("/v1/remesh", corps, methode="POST", timeout=60.0)
    except urllib.error.HTTPError as err:
        return {"ok": False, "erreur": "%d %s" % (err.code,
                                                  err.read().decode()[:200])}
    tache = str(cree.get("result") or "")
    if not tache:
        return {"ok": False, "erreur": "aucun identifiant de tache rendu"}
    fin = _attendre("/v1/remesh/%s" % tache, progression, "remaillage")
    if not fin["ok"]:
        return {"ok": False, "erreur": fin.get("erreur", "remaillage en echec"),
                "tache": tache}
    liens = fin["tache"].get("model_urls") or {}
    url = liens.get("glb") if isinstance(liens, dict) else None
    if not url:
        return {"ok": False, "erreur": "aucun GLB remaille dans la reponse",
                "tache": tache}
    sortie = Path(sortie)
    _telecharger(url, sortie)
    return {"ok": True, "glb": str(sortie), "tache": tache,
            "octets": sortie.stat().st_size}


def reporter_le_materiau(source: str | Path, cible: str | Path) -> Dict[str, Any]:
    """Remet sur `cible` les facteurs PBR que `source` portait.

    Les etapes de rig et d'animation reecrivent le materiau: mesure du 27/08
    sur un personnage — le maillage texture sortait a metallic=0.0 /
    roughness=0.80 (tissu mat, juste), le rige a metallic=1.0 / roughness=1.0
    et l'anime a metallic=1.0 / roughness=0.41. Un t-shirt et une peau a
    metallic=1 deviennent du metal poli: c'est le rendu "plastique".

    On ne devine aucune valeur — on reporte celles que le service avait
    lui-meme choisies en texturant, avant de les perdre.
    """
    from pygltflib import GLTF2

    src = GLTF2().load(str(source))
    dst = GLTF2().load(str(cible))
    mats_src = src.materials or []
    mats_dst = dst.materials or []
    if not mats_src or not mats_dst:
        return {"ok": False, "erreur": "aucun materiau a reporter"}

    corriges = []
    for i, mat in enumerate(mats_dst):
        ref = mats_src[i] if i < len(mats_src) else mats_src[0]
        p_ref, p_dst = ref.pbrMetallicRoughness, mat.pbrMetallicRoughness
        if p_ref is None or p_dst is None:
            continue
        avant = (p_dst.metallicFactor, p_dst.roughnessFactor)
        p_dst.metallicFactor = (p_ref.metallicFactor
                                if p_ref.metallicFactor is not None else 0.0)
        p_dst.roughnessFactor = (p_ref.roughnessFactor
                                 if p_ref.roughnessFactor is not None else 0.8)
        apres = (p_dst.metallicFactor, p_dst.roughnessFactor)
        if avant != apres:
            corriges.append({"materiau": i, "avant": avant, "apres": apres})
    if corriges:
        dst.save(str(cible))
    return {"ok": True, "corriges": corriges}
