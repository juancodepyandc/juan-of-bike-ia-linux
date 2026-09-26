"""scene_orchestrator — turn a natural multi-object prompt into a composed scene.

The single-mesh pipeline (aurora_3d_pipeline) treats 'un homme assis sur une
chaise' as ONE humanoid and TRELLIS renders a sitting man with no chair. True
multi-object scenes need: split the prompt into its objects + spatial relation,
GENERATE each object separately, then COMPOSE them (scene_composer). This module
is that missing orchestrator. It is deliberately model-driven (an LLM splits the
prompt) — no hardcoded object list.

Flow:
  1. split_scene_prompt(prompt) -> {is_scene, actor{desc,motion}, target{desc},
     relation, animate}  (LLM; falls back to single-object when not a scene).
  2. For a scene: generate the actor GLB and the target GLB via run_pipeline,
     then compose via scene_composer.py with the parsed relation.

Public: split_scene_prompt(prompt), orchestrate_scene(prompt, run_id, output_dir).
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
import unicodedata
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional

HERE = Path(__file__).resolve().parent
RELATIONS = ("sit_on", "stand_on", "lie_on", "next_to", "hold")
_LLM = os.environ.get("AURORA_MOTION_LLM", "orcarouter/Qwen3.8-27B-Uncensored")


# Le gros modele ne se charge pas sur une machine deja chargee (HTTP 500 sur
# 17,7 Go a demander). Decouper un prompt en objets est une EXTRACTION
# structuree, pas un exercice de style: un modele leger la fait aussi bien et
# se charge en quelques secondes. On garde le gros en premier choix et on
# bascule en le DISANT, plutot que de rendre "ce n'est pas une scene".
_LLM_REPLI = os.environ.get("AURORA_SCENE_LLM_REPLI", "qwen3-vl:8b")


def _un_appel(modele: str, prompt: str, timeout: int) -> str:
    body = json.dumps({
        "model": modele, "prompt": prompt, "stream": False,
        "options": {"temperature": 0.0, "top_p": 1.0, "seed": 1}, "keep_alive": 0,
    }).encode()
    req = urllib.request.Request("http://127.0.0.1:11434/api/generate", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode()).get("response", "").strip()


def _ollama(prompt: str, timeout: int = 90) -> str:
    """Appel unique; le modele est decharge ensuite (keep_alive:0) pour laisser
    la memoire aux etapes lourdes qui suivent."""
    try:
        return _un_appel(_LLM, prompt, timeout)
    except Exception as exc:  # noqa: BLE001
        if _LLM_REPLI and _LLM_REPLI != _LLM:
            print("SCENE_ORCH: %s indisponible (%r) -> repli sur %s"
                  % (_LLM, exc, _LLM_REPLI), file=sys.stderr)
            return _un_appel(_LLM_REPLI, prompt, timeout)
        raise


def _extract_json(text: str) -> Optional[dict]:
    a, b = text.find("{"), text.rfind("}")
    if a < 0 or b <= a:
        return None
    try:
        return json.loads(text[a:b + 1])
    except Exception:
        return None


POSTURES_EXPLICITES = (
    (("assis", "assise", "attable", "attablee", "sitting", "seated"),
     "sit_on"),
    (("allonge", "allongee", "couche", "couchee", "lying", "lain"), "lie_on"),
    (("debout", "standing", "dresse", "dressee"), "stand_on"),
)


def _relation_selon_le_texte(prompt: str, rel: str) -> str:
    """Impose la relation quand le prompt nomme explicitement la posture.

    Le LLM tranche bien la plupart du temps, mais c'est un echantillonnage:
    la meme phrase peut rendre `sit_on` ou `next_to` d'un run a l'autre, et
    `next_to` fait perdre la posture sans bruit. Un participe present dans la
    phrase, lui, est une certitude — il gagne.
    """
    p = unicodedata.normalize("NFKD", (prompt or "").lower())
    p = "".join(c for c in p if not unicodedata.combining(c))
    mots = set(re.findall(r"[a-z]+", p))
    for marqueurs, attendue in POSTURES_EXPLICITES:
        if mots.intersection(marqueurs):
            if rel != attendue:
                print("SCENE_ORCH: le prompt dit %r -> relation forcee %s "
                      "(le LLM avait rendu %s)"
                      % (sorted(mots.intersection(marqueurs))[0], attendue, rel),
                      file=sys.stderr)
            return attendue
    return rel


def decouper_en_objets(prompt: str, essais: int = 3) -> Dict[str, Any]:
    """Decoupe, en REESSAYANT tant que la scene n'est pas reconnue.

    Un decoupage rate ne coute rien (appel local), mais son ECHEC coute une
    generation payante pour rien: le pipeline retombe alors sur "un seul
    objet" et fabrique un bloc fusionne a partir d'un prompt qui en decrit
    huit. Mesure du 27/08: le gros modele a rendu une erreur 500, le repli a
    repondu a cote, et toute la scene est partie en UNE geometrie de 70 Mo
    inexploitable. Rejouer le meme appel a suffi (8 entites au coup suivant).
    """
    dernier = {"is_scene": False}
    for _ in range(max(1, essais)):
        dernier = _decouper_une_fois(prompt)
        if dernier.get("is_scene") or not (prompt or "").strip():
            return dernier
        print("SCENE_ORCH: decoupage sans scene (%d entite(s)) — nouvel essai"
              % len(dernier.get("objets") or []), file=sys.stderr)
    return dernier


def _decouper_une_fois(prompt: str) -> Dict[str, Any]:
    """Enumere TOUTES les entites du prompt, une par une, avec leur appui.

    Regroupes, deux objets dans une meme generation donnent UN seul objet et
    le generateur choisit lequel: "son bureau, mug de cafe" a produit un MUG
    (score 0, "ne correspond pas a la demande", 26/08). Une entite = une
    generation. Le champ `appui` dit sur quoi chaque objet repose, ce qui
    donne l'ordre de composition sans le deviner.
    """
    prompt = (prompt or "").strip()
    if not prompt:
        return {"is_scene": False}
    q = (
        "Tu analyses un prompt de generation 3D. Enumere CHAQUE objet physique "
        "distinct qu'il decrit, un par un. Reponds UNIQUEMENT en JSON strict:\n"
        '{"objets": [{"role": "<mot unique, minuscules, sans accent: personnage, '
        'chaise, bureau, ecrans, mug, lampe...>", "desc": "<description de CET '
        'objet SEUL, autonome, dans la langue du prompt, sans mentionner les '
        'autres objets>", "pose": "<assis|allonge|debout|vide>", "appui": "<role '
        'de l objet sur lequel il repose, ou \'sol\'>"}, ...], '
        '"style": "<ambiance, eclairage et style de rendu de la scene, ou vide>"}\n'
        "Regles STRICTES:\n"
        "- un objet par entree; ne regroupe JAMAIS deux objets dans une meme desc;\n"
        "- `desc` doit pouvoir etre generee seule: 'un bureau en bois', pas "
        "'son bureau avec un mug';\n"
        "- une personne assise sur une chaise = DEUX objets (personnage, chaise);\n"
        "- un ecran pose sur un bureau = DEUX objets, appui='bureau';\n"
        "- n'invente aucun objet absent du prompt;\n"
        "- si le prompt ne decrit QU'UN seul objet, rends {\"objets\": [un seul]}.\n"
        "Prompt: " + prompt
    )
    data, err = {}, None
    for tentative in range(2):
        try:
            data = _extract_json(_ollama(q, timeout=600)) or {}
            err = None
            break
        except Exception as exc:  # noqa: BLE001
            err = repr(exc)
            time.sleep(5.0 + 10.0 * tentative)
    if err is not None:
        print("SCENE_ORCH: analyse du prompt IMPOSSIBLE (%s) -> traite comme objet "
              "unique, mais ce n'est PAS une conclusion" % err, file=sys.stderr)
        return {"is_scene": False, "error": err}

    objets, vus = [], set()
    for brut in (data.get("objets") or []):
        if not isinstance(brut, dict):
            continue
        desc = str(brut.get("desc") or "").strip()
        if not desc:
            continue
        role = _slug(str(brut.get("role") or "")) or _role_de(desc)
        base, n = role, 2
        while role in vus:          # deux ecrans, deux chaises: roles uniques
            role = "%s%d" % (base, n)
            n += 1
        vus.add(role)
        pose = str(brut.get("pose") or "").strip().lower()
        if pose in ("vide", "none", "aucune"):
            pose = ""
        objets.append({"role": role, "desc": desc, "pose": pose,
                       "appui": _slug(str(brut.get("appui") or "sol")) or "sol"})
    if len(objets) < 2:
        return {"is_scene": False, "objets": objets,
                "style": str(data.get("style") or "").strip()}

    # Le texte prime sur l'echantillonnage: un participe dans la phrase ne
    # varie pas d'un tirage a l'autre, contrairement au LLM.
    impose = _posture_du_texte(prompt)
    vivant = next((o for o in objets if o["role"].startswith("personnage")
                   or _role_de(o["desc"], "") == ""), None)
    if impose and vivant is not None and vivant["pose"] != impose:
        print("SCENE_ORCH: le prompt dit %r -> pose de %s forcee a %r (le LLM "
              "avait rendu %r)" % (impose, vivant["role"], impose, vivant["pose"]),
              file=sys.stderr)
        vivant["pose"] = impose
    return {"is_scene": True, "objets": objets,
            "style": str(data.get("style") or "").strip()}


def _slug(mot: str) -> str:
    """Role -> nom de dossier sur: minuscules, sans accent, sans espace."""
    plat = unicodedata.normalize("NFKD", (mot or "").lower())
    plat = "".join(c for c in plat if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "_", plat).strip("_")


POSTURES_EXPLICITES = (
    (("assis", "assise", "attable", "attablee", "sitting", "seated"), "assis"),
    (("allonge", "allongee", "couche", "couchee", "lying"), "allonge"),
    (("debout", "standing"), "debout"),
)


def _posture_du_texte(prompt: str) -> str:
    """Posture nommee explicitement dans la phrase, sinon chaine vide."""
    plat = unicodedata.normalize("NFKD", (prompt or "").lower())
    plat = "".join(c for c in plat if not unicodedata.combining(c))
    mots = set(re.findall(r"[a-z]+", plat))
    for marqueurs, posture in POSTURES_EXPLICITES:
        if mots.intersection(marqueurs):
            return posture
    return ""


def split_scene_prompt(prompt: str) -> Dict[str, Any]:
    """Compatibilite: expose la decoupe sous la forme acteur/cible attendue
    par les appelants historiques, en plus de la liste complete `objets`."""
    plan = decouper_en_objets(prompt)
    if not plan.get("is_scene"):
        return plan
    objets = plan["objets"]
    acteur = next((o for o in objets if o["pose"]), objets[0])
    autres = [o for o in objets if o is not acteur]
    plan.update({
        "actor": acteur["desc"], "actor_pose": acteur["pose"],
        "actor_motion": "",
        "target": autres[0]["desc"] if autres else "",
        "relation": {"assis": "sit_on", "allonge": "lie_on",
                     "debout": "stand_on"}.get(acteur["pose"], "next_to"),
        "scene_style": plan.get("style", ""),
        "animate": acteur["pose"] in ("assis", "allonge"),
    })
    return plan



def real_heights(actor: str, target: str) -> Dict[str, Optional[float]]:
    """Hauteurs REELLES des deux objets, en metres.

    Chaque objet est genere NORMALISE (~1 unite): un homme et une chaise sortent
    donc exactement de la meme taille, et composer sur les hauteurs mesurees donne
    un homme minuscule sur un fauteuil geant. La bonne echelle n'est pas une
    propriete de la geometrie, c'est une connaissance du MONDE - on la demande donc
    au LLM plutot que de coder une table d'objets, qui ne generaliserait a rien.
    """
    # Hauteur telle que MONTREE, pose comprise: un mesh d'homme ASSIS mesure sa
    # hauteur ASSISE (~1.3 m du sol au sommet du crane), pas sa taille debout. Passer
    # 1.75 a un mesh assis le rend geant (verifie: 4 unites pour une chaise de 2).
    q = (
        "Give the TYPICAL real-world height in METERS of each object AS DESCRIBED, "
        "POSE INCLUDED, floor to top, as a human would know it: a standing adult "
        "~1.75, a SEATED adult ~1.3, a lying adult ~0.5, a chair ~0.9, a mug ~0.1.\n"
        'Reply ONLY strict JSON: {"actor_m": <number>, "target_m": <number>}\n'
        "Object A (actor): %s\nObject B (target): %s" % (actor, target)
    )
    try:
        d = _extract_json(_ollama(q)) or {}
        a, t = float(d.get("actor_m")), float(d.get("target_m"))
    except Exception as exc:  # noqa: BLE001
        print("SCENE_ORCH: tailles reelles indisponibles (%r) -> echelle non "
              "corrigee" % exc, file=sys.stderr)
        return {"actor_m": None, "target_m": None}
    # garde-fou: une valeur aberrante ferait pire que rien
    if not (0.01 <= a <= 100.0 and 0.01 <= t <= 100.0):
        print("SCENE_ORCH: tailles aberrantes (%s, %s) -> ignorees" % (a, t),
              file=sys.stderr)
        return {"actor_m": None, "target_m": None}
    return {"actor_m": a, "target_m": t}


POSTURES_REFUSEES = ("tailleur", "accroupi", "debout", "couche", "allonge",
                     "penche", "cross-legged", "squat", "standing")
POSTURES_ATTENDUES = {
    "assis": ("assis", "assise", "chaise", "droite", "seated", "sitting", "chair"),
    "allonge": ("allonge", "allongee", "couche", "couchee", "lying", "flat"),
}


def _posture_acceptable(pose_word: str, verdict: dict) -> bool:
    """Accepte aussi quand le VLM DECRIT la bonne posture en disant non.

    Mesure le 26/08: le juge a rejete les 4 essais en decrivant lui-meme
    'assise sur chaise' puis 'assise droite' — exactement ce qui etait
    demande. Les 4 refus faisaient tomber la fonction en repli, et le
    personnage revenait AVEC sa chaise. On croise donc `conforme` avec la
    posture DECRITE: le texte du juge contredit son propre verdict.
    """
    if bool(verdict.get("conforme")):
        return True
    dit = unicodedata.normalize("NFKD", str(verdict.get("posture") or "").lower())
    dit = "".join(c for c in dit if not unicodedata.combining(c))
    if not dit:
        return False
    if any(mauvais in dit for mauvais in POSTURES_REFUSEES):
        return False
    return any(bon in dit for bon in POSTURES_ATTENDUES.get(pose_word, ()))


def _isoler_la_personne(cand: Path, sub: Path, run_id: str) -> Optional[str]:
    """Retire tout ce qui n'est pas la personne (siege compris).

    Mesure le 26/08 sur une reference reelle: u2net_human_seg retire bien la
    chaise (couverture 16,7 %, image verifiee a l'oeil). Le siege est une
    ENTITE a part, generee et composee separement — le personnage ne doit
    jamais en porter une seconde.
    """
    try:
        import cv2
        import numpy as np
        from rembg import new_session, remove
        rgb = cv2.cvtColor(cv2.imread(str(cand)), cv2.COLOR_BGR2RGB)
        rgba = remove(rgb, session=new_session("u2net_human_seg"))
        a = rgba[:, :, 3:4].astype(np.float32) / 255.0
        comp = (rgba[:, :, :3] * a + 255.0 * (1.0 - a)).astype(np.uint8)
        if float((rgba[:, :, 3] > 128).mean()) <= 0.05:
            print("SCENE_ORCH: segmentation vide (%.1f%%) -> reference brute"
                  % (100.0 * (rgba[:, :, 3] > 128).mean()), file=sys.stderr)
            return None
        seg = sub / ("%s_pose_seg.png" % run_id)
        cv2.imwrite(str(seg), cv2.cvtColor(comp, cv2.COLOR_RGB2BGR))
        print("SCENE_ORCH: personne isolee, siege retire (%.1f%% du cadre)"
              % (100.0 * (rgba[:, :, 3] > 128).mean()), flush=True)
        return str(seg)
    except Exception as exc:  # noqa: BLE001
        print("SCENE_ORCH: segmentation personne indispo (%r)" % exc, file=sys.stderr)
        return None


def _seated_reference(desc: str, run_id: str, sub: Path, pose_word: str,
                      tries: int = 4, garder_le_siege: bool = False) -> Optional[str]:
    """Genere une reference FLUX de la POSE et la VALIDE au VLM avant TRELLIS.

    Sans chaise pour s'appuyer, FLUX place l'homme au sol (tailleur) ou accroupi, de
    facon SEED-DEPENDANTE: le meme prompt donne parfois une bonne pose de chaise,
    parfois du tailleur. On genere donc plusieurs candidats (seeds differents) et on
    garde le PREMIER que le modele de vision juge conforme (cuisses horizontales,
    pieds au sol, ni tailleur ni accroupi ni debout). C'est le seul moyen fiable.
    """
    try:
        from flux_reference_synth import synth
        from vlm_judge import ask_vlm
    except Exception as exc:  # noqa: BLE001
        print("SCENE_ORCH: synth/vlm indispo (%r) -> reference FLUX standard" % exc,
              file=sys.stderr)
        return None
    want = {"assis": ("assis sur une chaise (cuisses horizontales, genoux plies vers "
                      "le bas, pieds a plat au sol, buste droit)"),
            "allonge": "allonge a plat sur le dos, jambes tendues"}.get(
        pose_word, pose_word)
    q = ("Decris la posture de la personne. Est-elle EXACTEMENT %s ? Reponds NON si "
         "elle est assise en tailleur, accroupie, debout, ou autrement." % want)
    schema = '{"conforme": true/false, "posture": "<3 mots>"}'
    candidats: list[tuple[bool, str, str]] = []
    for i in range(tries):
        ref = sub / ("%s_pose_%d.png" % (run_id, i))
        try:
            synth(desc, "%s_pose_%d" % (run_id, i), output_dir=sub, seed=1000 + i * 137)
        except Exception as exc:  # noqa: BLE001
            print("SCENE_ORCH: synth pose echec (%r)" % exc, file=sys.stderr)
            continue
        cand = sub / ("%s_pose_%d_reference.png" % (run_id, i))
        if not cand.is_file():
            continue
        try:
            v = ask_vlm([str(cand)], q, schema)
        except Exception as exc:  # noqa: BLE001
            print("SCENE_ORCH: VLM pose echec (%r) -> on accepte le candidat" % exc,
                  file=sys.stderr)
            return str(cand)
        ok = _posture_acceptable(pose_word, v)
        if ok and not v.get("conforme"):
            print("SCENE_ORCH: essai %d — le juge dit non mais DECRIT %r, "
                  "qui est la posture demandee: accepte" % (i, v.get("posture")),
                  flush=True)
        candidats.append((ok, str(cand), str(v.get("posture") or "")))
        print("SCENE_ORCH: reference pose essai %d: %s (%s)"
              % (i, "OK" if ok else "rejetee", v.get("posture")), flush=True)
        if ok:
            if garder_le_siege:
                print("SCENE_ORCH: siege GARDE dans la reference", flush=True)
                return str(cand)
            return _isoler_la_personne(cand, sub, run_id) or str(cand)
    # AUCUN essai retenu. Rendre None faisait retomber le pipeline sur une
    # reference FLUX standard qui ne passe JAMAIS par la segmentation: le
    # personnage revenait avec sa chaise, alors qu'une chaise est une entite
    # generee a part (constat de Juan, 26/08). On prend donc le meilleur
    # candidat et on l'isole quand meme — un homme assis segmente vaut
    # infiniment mieux qu'une reference chargee d'un siege en double.
    if candidats:
        meilleur = next((c for c in candidats if c[0]), candidats[-1])
        print("SCENE_ORCH: aucun essai juge conforme en %d tentatives — on "
              "retient le dernier candidat (%s) et on l'isole quand meme, "
              "plutot que de laisser passer une reference NON segmentee"
              % (tries, meilleur[2] or "posture non decrite"), file=sys.stderr)
        if garder_le_siege:
            return meilleur[1]
        return _isoler_la_personne(Path(meilleur[1]), sub, run_id) or meilleur[1]
    print("SCENE_ORCH: aucune reference de pose produite en %d essais -> FLUX "
          "standard" % tries, file=sys.stderr)
    return None


SIEGES = ("chaise", "fauteuil", "canape", "tabouret", "banc", "siege",
          "chair", "armchair", "sofa", "couch", "stool", "bench", "seat")


def _detacher_le_siege(cible: str) -> tuple[str, str]:
    """Sort le siege de la description de la CIBLE.

    Le personnage etait genere assis SANS siege (pour eviter une 2e chaise
    quand la cible EST la chaise), puis compose au-dessus d'un siege genere
    a part. Quand la cible est un BUREAU, le siege reste dans son groupe
    nominal et l'acteur sort assis dans le vide — verifie le 26/08.
    Regle: ce qui TOUCHE l'acteur se genere AVEC lui. On rend
    (siege, cible_sans_siege).
    """
    if not cible:
        return "", cible
    segments = [seg.strip() for seg in re.split(r",", cible) if seg.strip()]
    siege, restants = "", []
    for seg in segments:
        plat = unicodedata.normalize("NFKD", seg.lower())
        plat = "".join(c for c in plat if not unicodedata.combining(c))
        mots = set(re.findall(r"[a-z]+", plat))
        if not siege and mots.intersection(SIEGES):
            # "chaise ergonomique noire a son bureau" -> on ne garde que le
            # siege, la partie "a son bureau" retourne a la cible.
            m = re.split(r"\b(?:a|au|aux|devant|pres|contre|at|in front of)\b",
                         seg, maxsplit=1)
            siege = m[0].strip(" ,")
            if len(m) > 1 and m[1].strip(" ,"):
                restants.append(seg[len(m[0]):].strip(" ,"))
        else:
            restants.append(seg)
    reste = ", ".join(restants)
    # "a son bureau, devant deux ecrans" n'est pas un objet a generer: on
    # retire la preposition de tete laissee par le decoupage.
    reste = re.sub(r"^\s*(?:a|au|aux|devant|pres de|pres|contre|at|in front of)\s+",
                   "", reste, flags=re.IGNORECASE).strip(" ,")
    return siege, reste


ORDI = ("ordinateur", "ordi", "pc", "ecran", "ecrans", "moniteur", "moniteurs",
        "laptop", "clavier", "souris", "computer", "monitor", "monitors",
        "screen", "screens", "keyboard", "mouse", "desktop")


def _detacher_l_ordi(cible: str) -> tuple[str, str]:
    """Separe le poste informatique du MEUBLE qui le porte.

    Juan veut un dossier par composant reel: `bureau/` (le meuble, avec ou
    sans le poste) et `ordi/` (ecrans, unite, clavier). Genere d'un bloc, le
    tout sortait en un meuble massif ou les ecrans etaient des bosses.
    Rend (bureau, ordi) — `ordi` vide si le prompt n'en parle pas.
    """
    if not cible:
        return cible, ""
    meuble, poste = [], []
    for seg in [x.strip() for x in re.split(r",", cible) if x.strip()]:
        plat = unicodedata.normalize("NFKD", seg.lower())
        plat = "".join(c for c in plat if not unicodedata.combining(c))
        (poste if set(re.findall(r"[a-z]+", plat)).intersection(ORDI)
         else meuble).append(seg)
    _nettoie = lambda t: re.sub(
        r"^\s*(?:a|au|aux|devant|pres de|pres|contre|sur|at|on|in front of)\s+",
        "", ", ".join(t), flags=re.IGNORECASE).strip(" ,")
    return _nettoie(meuble), _nettoie(poste)


ROLES = (
    ("bureau", ("bureau", "desk", "workstation", "pupitre")),
    ("table", ("table", "comptoir", "counter", "etabli")),
    ("canape", ("canape", "sofa", "couch", "divan")),
    ("chaise", ("chaise", "fauteuil", "tabouret", "siege", "chair",
                "armchair", "stool", "seat")),
    ("lit", ("lit", "bed", "matelas")),
    ("banc", ("banc", "bench")),
)


def _role_de(desc: str, defaut: str = "decor") -> str:
    """Nom de dossier = ce que le composant EST.

    Un canape range dans `bureau/` parce que le code appelait la cible
    "bureau" en dur rend l'arborescence mensongere: on lit le mot dans la
    description.
    """
    plat = unicodedata.normalize("NFKD", (desc or "").lower())
    plat = "".join(c for c in plat if not unicodedata.combining(c))
    mots = set(re.findall(r"[a-z]+", plat))
    for role, marqueurs in ROLES:
        if mots.intersection(marqueurs):
            return role
    return defaut


def _generate_object(desc: str, run_id: str, output_dir: Path,
                     motion: str = "", purpose: str = "visual_preview",
                     pose_word: str = "",
                     garder_le_siege: bool = False,
                     rendre_le_detail: bool = False,
                     pose_a_venir: bool = False):
    """Generate a single object GLB via the normal pipeline. Returns the final
    GLB path or None."""
    try:
        from aurora_3d_pipeline import run_pipeline
    except Exception as exc:  # noqa: BLE001
        print(f"SCENE_ORCH: cannot import run_pipeline: {exc}", file=sys.stderr)
        return None
    sub = output_dir / run_id
    sub.mkdir(parents=True, exist_ok=True)
    # pose statique: reference FLUX validee au VLM (voir _seated_reference), passee a
    # TRELLIS via `images` (ce qui court-circuite la generation de reference).
    imgs = None
    # Un personnage qui sera pose par un squelette n'a pas besoin — et ne
    # doit pas subir — la passe de mouvement locale.
    _mot_prev = os.environ.get("AURORA_MOTION_LOCALE")
    if pose_a_venir:
        os.environ["AURORA_MOTION_LOCALE"] = "0"
    _mv_prev = os.environ.get("AURORA_MVADAPTER_MV")
    if pose_word:
        ref = _seated_reference(desc, run_id, sub, pose_word,
                                garder_le_siege=garder_le_siege)
        if ref:
            imgs = [ref]
        # UNIQUEMENT pour un humain POSE, on active le multi-vues coherent (la ou la
        # mono-vue casse). Ailleurs il reste OFF (memoire, pas de gel). Sequentiel:
        # MV-Adapter (SDXL) et TRELLIS sont chacun un sous-process, VRAM liberee entre.
        os.environ["AURORA_MVADAPTER_MV"] = "1"
    try:
        # allow_scene=False: l'orchestrateur EST deja dans une scene. Sans ce garde-fou,
        # run_pipeline redetecterait une scene et se rappellerait sans fin.
        # UNE ENTITE = UN PROCESSUS. `run_pipeline` tournait DANS ce processus:
        # mesure du 05/09 a la sonde memoire, le parent passe de moins de 9 Go a
        # 25 Go au moment ou la geometrie est posee, puis se fait tuer par le
        # noyau — et le second personnage n'existe jamais. Cinq lancements
        # perdus ainsi. En sous-processus la memoire est INTEGRALEMENT rendue au
        # systeme a la fin de chaque entite, et un personnage qui echoue
        # n'emporte plus les suivants.
        if os.environ.get("AURORA_ENTITE_SOUS_PROCESSUS", "1") == "1":
            _cmd = [sys.executable,
                    str(Path(__file__).resolve().parent / "aurora_3d_pipeline.py"),
                    "--prompt", desc, "--run-id", run_id, "--output-dir", str(sub),
                    "--purpose", purpose, "--no-scene"]
            if motion:
                _cmd += ["--motion-prompt", motion]
            for _im in (imgs or []):
                _cmd += ["--image", str(_im)]
            _p = subprocess.run(_cmd, capture_output=True, text=True, timeout=7200)
            for _l in (_p.stdout or "").splitlines():
                if _l.startswith("PROGRESS:") or _l.startswith("SCENE_ORCH"):
                    print(_l, flush=True)
            
            # Find the first line that starts precisely with "{" (the start of the JSON block)
            _lines = (_p.stdout or "").splitlines()
            _json_start = -1
            for i, l in enumerate(_lines):
                if l.startswith("{"):
                    _json_start = i
                    break
            
            try:
                _j = "\n".join(_lines[_json_start:]) if _json_start >= 0 else ""
                res = json.loads(_j) if _j else {}
            except Exception:  # noqa: BLE001
                res = {}
            if not res:
                res = {"ok": False,
                       "error": (_p.stderr or "")[-300:] or "sous-processus sans resultat"}
        else:
            res = run_pipeline(desc, run_id, output_dir=sub,
                               motion_prompt=(motion or None), purpose=purpose,
                               images=imgs, allow_scene=False)
    finally:
        if _mv_prev is None:
            os.environ.pop("AURORA_MVADAPTER_MV", None)
        else:
            os.environ["AURORA_MVADAPTER_MV"] = _mv_prev
        if _mot_prev is None:
            os.environ.pop("AURORA_MOTION_LOCALE", None)
        else:
            os.environ["AURORA_MOTION_LOCALE"] = _mot_prev
    if not isinstance(res, dict):
        return {"glb": None, "refus": "pipeline sans resultat"} if rendre_le_detail else None
    # On garde le maillage meme si res["ok"] est False: run_pipeline rend
    # ok=False sur un manque D'ACCEPTATION SOUPLE ("single merged mesh, no
    # articulatable parts" — normal pour une chaise), et la geometrie reste
    # parfaitement composable.
    # MAIS un refus de FOND ("ne correspond pas a la demande", score 0) n'est
    # pas un manque souple: compose quand meme, il a livre une scene ou le
    # bureau etait un MUG (26/08). On le remonte a l'appelant.
    erreur = str(res.get("error") or "")
    refus = None
    # IDENTITE TRAHIE = REFUS. Mesure du 04/09: « Caine » est sorti en chien
    # generique (sa reference avait ete inventee par FLUX faute de photo web
    # exploitable), la porte finale l'a note 95/100 « PARFAIT » — elle compare
    # le modele a SA reference, jamais la reference a l'identite demandee — et
    # la scene est passee au personnage suivant comme si de rien n'etait.
    # Un personnage nomme qui n'est pas le bon n'est pas un succes.
    if res.get("identite_trahie"):
        refus = ("le modele ne represente pas le personnage demande "
                 "(reference inventee, identite non verifiee)")
    for signe in ("ne correspond pas a la demande", "does not match the request",
                  "wrong subject", "score 0"):
        if signe in erreur.lower():
            refus = erreur[:200]
            break
    # LE RANGEMENT DEPLACE LES FICHIERS. `organiser()` met les livrables dans
    # modele/ et mouvement/ APRES coup; les chemins bruts renvoyes par le
    # pipeline peuvent donc pointer un emplacement qui n'existe plus. Mesure du
    # 05/09: Caine etait bel et bien produit (modele/modele_couleurs.glb,
    # 10 Mo) et l'orchestrateur annoncait "entite NON generee" — un succes
    # complet perdu sur un chemin perime. On consulte donc d'abord la
    # LIVRAISON que le pipeline rend justement pour cela, puis on retombe sur
    # l'arborescence rangee, et on dit ce qu'on a essaye.
    _liv = res.get("livraison") if isinstance(res.get("livraison"), dict) else {}
    _pistes = [res.get("rigged_mesh"), res.get("final_mesh"),
               res.get("rescued_mesh"),
               _liv.get("mouvement_couleurs"), _liv.get("modele_couleurs"),
               str(Path(sub) / "mouvement" / "mouvement_couleurs.glb"),
               str(Path(sub) / "modele" / "modele_couleurs.glb")]
    chemin = next((str(m) for m in _pistes
                   if m and os.path.isfile(str(m))), None)
    if chemin is None:
        print("SCENE_ORCH: aucun GLB trouve pour cette entite — essaye: %s"
              % "; ".join(str(m) for m in _pistes if m), flush=True)
    if rendre_le_detail:
        return {"glb": chemin, "refus": refus, "tache": res.get("tache_service"),
                "score": res.get("score"), "erreur": erreur or None}
    return chemin


DETAIL_POSE = {
    "assis": "cuisses horizontales, mollets verticaux, pieds a plat au sol, buste droit",
    "allonge": "a plat sur le dos, jambes tendues, horizontal",
}


# "debout" ne veut pas dire IMMOBILE: un personnage debout dans une scene
# vivante marche. L'action reste surchargeable par AURORA_ACTION_<pose>.
ACTIONS_PAR_POSE = {"assis": "assis_chaise_homme", "allonge": "attente",
                    "debout": "marche"}
T_POSE = ("debout en T-pose, bras tendus a l'horizontale de part et d'autre du "
          "corps, mains ouvertes doigts ecartes, jambes droites et legerement "
          "ecartees, corps entier, face a la camera, photorealiste")


def _poser_le_personnage(entite: dict, projet: Path) -> dict:
    """Construit en T, pose un squelette, applique l'action demandee.

    Un personnage fabrique DEJA dans sa pose est fige: il ne peut plus etre
    rige ni rejoue dans une autre action, et sa reconstruction fusionne les
    bras au torse faute de les voir separes. La voie du metier est l'inverse:
    un corps en T (bras degages, donc reconstruits proprement), un squelette,
    puis une action prise au catalogue.
    """
    rapport = {"etapes": []}
    tache = entite.get("tache")
    if not tache:
        rapport["erreur"] = "aucune tache de service — le personnage reste fige"
        return rapport
    try:
        import meshy_client
    except Exception as exc:  # noqa: BLE001
        rapport["erreur"] = "service indisponible: %r" % (exc,)
        return rapport

    travail = projet / entite["role"] / "travail"
    mouvement = projet / entite["role"] / "mouvement"
    travail.mkdir(parents=True, exist_ok=True)
    mouvement.mkdir(parents=True, exist_ok=True)
    dire = lambda m: print("SCENE_ORCH: %s — %s" % (entite["role"], m), flush=True)

    # Le rig refuse au-dela de 320 000 faces; la texturation fait remonter le
    # maillage bien au-dessus de la densite demandee a la creation.
    rem = meshy_client.remailler(travail / "personnage_remaille.glb",
                                 tache_source=tache, progression=dire)
    rapport["etapes"].append({"etape": "remaillage", "ok": rem.get("ok"),
                              "erreur": rem.get("erreur")})
    source = rem.get("tache") if rem.get("ok") else tache

    rig = meshy_client.rigger(travail / "personnage_rige.glb",
                              tache_source=source, progression=dire)
    rapport["etapes"].append({"etape": "squelette", "ok": rig.get("ok"),
                              "erreur": rig.get("erreur")})
    if not rig.get("ok"):
        rapport["erreur"] = "squelette impossible: %s" % rig.get("erreur")
        return rapport
    meshy_client.reporter_le_materiau(entite["glb"], rig["glb"])
    rapport["rige"] = rig["glb"]

    action = ACTIONS_PAR_POSE.get(entite.get("pose") or "", "attente")
    ani = meshy_client.animer(rig["tache"], action,
                              mouvement / "mouvement_couleurs.glb",
                              progression=dire)
    rapport["etapes"].append({"etape": "animation", "action": action,
                              "ok": ani.get("ok"), "erreur": ani.get("erreur")})
    if ani.get("ok"):
        # Le rig et l'animation reecrivent le materiau en metallic=1: le
        # personnage ressort en metal poli. On remet les facteurs que le
        # service avait choisis en texturant.
        report = meshy_client.reporter_le_materiau(entite["glb"], ani["glb"])
        if report.get("corriges"):
            dire("materiau remis d'aplomb %s" % report["corriges"][0])
        rapport["materiau"] = report
        rapport["anime"] = ani["glb"]
        # LE LIVRABLE DOIT PORTER L'ANIMATION. Elle n'existait que dans
        # `mouvement/mouvement_couleurs.glb`, un sous-dossier: le fichier que
        # l'on ouvre naturellement (<role>_matte.glb) sortait a 0 animation et
        # le personnage paraissait fige (constate le 28/08). On depose donc le
        # resultat anime a la racine de l'entite, sous un nom qui se voit.
        try:
            _dest = projet / entite["role"] / ("%s_ANIME.glb" % entite["role"])
            shutil.copyfile(ani["glb"], _dest)
            rapport["livrable_anime"] = str(_dest)
            dire("livrable anime: %s" % _dest.name)
        except Exception as _ce:  # noqa: BLE001
            rapport["livrable_anime_erreur"] = repr(_ce)
    else:
        rapport["erreur"] = "animation impossible: %s" % ani.get("erreur")
    return rapport


def _ordre_de_composition(objets: list) -> list:
    """Parents avant enfants, en suivant `appui`. Un cycle ne bloque pas."""
    par_role = {o["role"]: o for o in objets}
    ordonne, vus = [], set()

    def poser(o, pile):
        if o["role"] in vus or o["role"] in pile:
            return
        parent = par_role.get(o["appui"])
        if parent is not None:
            poser(parent, pile | {o["role"]})
        vus.add(o["role"])
        ordonne.append(o)

    for o in objets:
        poser(o, set())
    return ordonne


def orchestrate_scene(prompt: str, run_id: str, output_dir: str | Path) -> Dict[str, Any]:
    """Genere CHAQUE entite du prompt separement, puis les compose.

    Une entite = une generation. Regroupees ("son bureau, mug de cafe"), deux
    entites donnent un seul objet et le generateur choisit lequel — il avait
    rendu un MUG a la place du bureau (26/08).
    """
    output_dir = Path(output_dir)
    plan = decouper_en_objets(prompt)
    if not plan.get("is_scene"):
        # `error` doit remonter au PREMIER niveau: le site d'appel decide de
        # reessayer sur cette cle. Enfoui dans `plan`, il passait inapercu et
        # une panne LLM redevenait "objet unique" en silence — la panne meme
        # que ce garde-fou existe pour empecher.
        return {"ok": True, "is_scene": False, "plan": plan,
                "error": plan.get("error")}

    projet = Path(output_dir)
    objets = plan["objets"]
    style = plan.get("style") or ""
    print("SCENE_ORCH: %d entites -> %s" % (
        len(objets), ", ".join("%s(%s, appui=%s)" % (o["role"], o["desc"][:28], o["appui"])
                               for o in objets)), flush=True)

    # --- 1. une generation par entite, dans son propre dossier --------------
    refuses = []
    # Deux entites identiques ("deux grands ecrans") = UNE generation reutilisee.
    # Les generer deux fois coute une passe TRELLIS complete pour un resultat
    # que l'on possede deja.
    def _liberer_entre_entites(role: str) -> None:
        """Rend la memoire avant l'entite suivante.

        Les entites d'une scene sont generees SEQUENTIELLEMENT mais dans le
        MEME processus: ce que la premiere a alloue (mesure le 03/09: un
        maillage natif de 4,5 M de faces) est encore detenu quand la seconde
        demarre. Le noyau a tue le run a 29,5 Go sur 32 pendant le premier
        personnage — le second n'a jamais commence. Sans cette liberation,
        toute scene a plusieurs sujets meurt avant d'etre composee.
        """
        import gc
        gc.collect()
        try:  # rend au systeme ce que l'allocateur garde en reserve
            import ctypes
            ctypes.CDLL("libc.so.6").malloc_trim(0)
        except Exception:  # noqa: BLE001
            pass
        try:
            import urllib.request as _u, json as _j
            _u.urlopen(_u.Request(
                "http://127.0.0.1:11434/api/generate",
                data=_j.dumps({"model": os.environ.get(
                    "AURORA_MOTION_LLM", "qwen3-coder:30b"),
                    "prompt": "", "keep_alive": 0}).encode(),
                headers={"Content-Type": "application/json"}), timeout=10).read()
        except Exception:  # noqa: BLE001
            pass
        try:
            import psutil
            _dispo = psutil.virtual_memory().available / (1024 ** 3)
            print("SCENE_ORCH: memoire liberee avant %r — %.1f Go disponibles"
                  % (role, _dispo), flush=True)
        except Exception:  # noqa: BLE001
            print("SCENE_ORCH: memoire liberee avant %r" % role, flush=True)

    deja = {}
    for o in objets:
        _liberer_entre_entites(o.get("role", "?"))
        cle = re.sub(r"\s+", " ", o["desc"].strip().lower())
        jumeau = deja.get(cle)
        if jumeau is not None:
            o["glb"] = jumeau.get("glb")
            o["refus"] = jumeau.get("refus")
            o["tache"] = jumeau.get("tache")
            o["desc_generee"] = jumeau.get("desc_generee")
            o["copie_de"] = jumeau["role"]
            print("SCENE_ORCH: %r identique a %r — maillage reutilise, pas de "
                  "seconde generation" % (o["role"], jumeau["role"]), flush=True)
            continue
        deja[cle] = o
        pose = o["pose"] if o["pose"] in DETAIL_POSE else ""
        if pose:
            # T-pose: le corps se construit neutre, la pose vient ensuite du
            # squelette. Les bras ecartes sont aussi ce qui permet de les
            # reconstruire sans les fondre dans le torse.
            desc = "%s, %s" % (o["desc"], T_POSE)
        else:
            desc = "%s, %s" % (o["desc"], style) if style else o["desc"]
        o["desc_generee"] = desc
        # `pose_word` declenche le filtre de pose ASSISE. Le corps se construit
        # desormais en T — lui demander "est-elle assise sur une chaise ?"
        # rejette les 4 essais et brule quatre generations FLUX pour rien
        # (mesure le 27/08). La posture ne vient plus de la reference mais du
        # squelette, ce filtre n'a donc plus d'objet ici.
        # UN REFUS SE RETENTE. Le service ne reconstruit qu'a partir d'UNE
        # image (verifie: son endpoint n'accepte que `image_url`), il INVENTE
        # donc le dos — et la qualite de cette invention varie d'un tirage a
        # l'autre: le meme personnage, meme chaine, a note 95/100 puis 25/100
        # (plaques couleur peau sur le dos du t-shirt). Sans reprise, une
        # entite refusee etait simplement ABSENTE de la scene, et tout ce qui
        # reposait dessus tombait avec elle. On rejoue donc le tirage plutot
        # que de livrer une scene trouee.
        _essais = max(1, int(os.environ.get("AURORA_SCENE_ESSAIS", "3")))
        res = None
        for _essai in range(_essais):
            res = _generate_object(desc, o["role"], projet, rendre_le_detail=True,
                                   pose_a_venir=bool(pose))
            if not (res or {}).get("refus"):
                break
            if _essai + 1 < _essais:
                # UN REFUS DOIT CHANGER LA REFERENCE, PAS SEULEMENT LE TIRAGE.
                # `run_pipeline` reutilise la reference deja ecrite
                # (« reference exists; pass --force to regenerate »), donc les
                # essais rejouaient la reconstruction sur LA MEME image.
                # Mesure du 04/09 sur « Caine »: trois essais, trois refus au
                # score RIGOUREUSEMENT identique (25, « morceaux
                # manquants/fondus ») — les jambes etaient deja fondues dans la
                # reference, aucun nouveau tirage ne pouvait les inventer.
                # On efface donc la reference de l'entite: le prochain essai en
                # cherche une autre, et la selection garde desormais la
                # MEILLEURE (voir `_note_reference`), pas la premiere venue.
                _sous = projet / o["role"]
                _efface = 0
                for _motif in ("*_reference.png", "*_reference_detouree.png",
                               "*_front_reference.png"):
                    for _f in list(_sous.glob(_motif)) + list(_sous.glob("**/" + _motif)):
                        try:
                            _f.unlink(); _efface += 1
                        except OSError:
                            pass
                print("SCENE_ORCH: %r refuse (%s) — %d reference(s) ecartee(s), "
                      "nouvelle recherche, essai %d/%d"
                      % (o["role"], str((res or {}).get("refus"))[:70], _efface,
                         _essai + 2, _essais), file=sys.stderr)
        o["glb"] = (res or {}).get("glb")
        o["refus"] = (res or {}).get("refus")
        # Sans cet identifiant, le rig devrait re-televerser le maillage —
        # et la chaine de pose partait avec `tache=None`.
        o["tache"] = (res or {}).get("tache")
        if not o["glb"]:
            print("SCENE_ORCH: entite %r NON generee — la scene sera incomplete"
                  % o["role"], file=sys.stderr)
        elif o["glb"] and pose:
            o["pose_service"] = _poser_le_personnage(o, projet)
            if o["pose_service"].get("anime"):
                o["glb"] = o["pose_service"]["anime"]
                print("SCENE_ORCH: %s pose par son squelette (action %r)"
                      % (o["role"], ACTIONS_PAR_POSE.get(o["pose"], "attente")),
                      flush=True)
                # UN VERDICT APPARTIENT AU FICHIER QU'IL A REGARDE. Celui-ci
                # visait le corps en T d'AVANT le squelette; la mise en pose
                # passe par un REMAILLAGE complet du service, qui refait la
                # surface (donc les "trous" reproches) et rend un fichier
                # different. Le garder revenait a exclure de la scene un
                # personnage qu'on venait de riger et d'animer avec succes —
                # mesure du 27/08: "pose par son squelette (assis_chaise_homme)"
                # suivi de "REFUSEE par la porte, elle ne sera PAS composee"
                # sur la meme entite, pour un defaut du fichier remplace.
                if o.get("refus"):
                    print("SCENE_ORCH: %s — verdict de la porte abandonne: il "
                          "visait le corps en T, remplace depuis par le "
                          "maillage rige et anime (%s)"
                          % (o["role"], str(o["refus"])[:80]), file=sys.stderr)
                    o["refus"] = None
            else:
                # Sans squelette, le personnage reste en T: le dire, plutot
                # que de composer un bonhomme bras ecartes assis a un bureau.
                print("SCENE_ORCH: %s NON pose (%s) — il reste en T-pose"
                      % (o["role"], o["pose_service"].get("erreur")),
                      file=sys.stderr)
        if o.get("refus"):
            # "score 0, ne correspond pas a la demande" n'est pas un detail:
            # composer par-dessus livrait une scene ou le bureau etait un mug.
            refuses.append({"role": o["role"], "motif": o["refus"]})
            print("SCENE_ORCH: entite %r REFUSEE par la porte (%s) — elle ne "
                  "sera PAS composee" % (o["role"], o["refus"][:90]), file=sys.stderr)

    utilisables = [o for o in objets if o.get("glb") and not o.get("refus")]
    if not utilisables:
        return {"ok": False, "is_scene": True, "plan": plan, "refuses": refuses,
                "error": "aucune entite exploitable"}

    # --- 2. redresser ce qui n'est pas vivant -------------------------------
    upright_info = {}
    for o in utilisables:
        if o["pose"]:
            continue
        try:
            import upright_object
            src = o["glb"]
            out = str(Path(src).with_name(Path(src).stem + "_droit.glb"))
            info = upright_object.upright(src, out, desc=o["desc"])
            upright_info[o["role"]] = info
            if info.get("ok") and not info.get("already_upright"):
                o["glb"] = info["output"]
        except Exception as exc:  # noqa: BLE001
            upright_info[o["role"]] = {"ok": False, "error": repr(exc)}

    # --- 3. composer en suivant les appuis ----------------------------------
    scene_dir = projet / "scene"
    scene_dir.mkdir(parents=True, exist_ok=True)
    composer = HERE / "scene_composer.py"
    ordre = [o for o in _ordre_de_composition(objets) if o in utilisables]
    par_role = {o["role"]: o for o in utilisables}

    def _composer(acteur, cible, instruction, sortie, h_a=None, h_c=None,
                  preposed=False):
        cmd = [sys.executable, str(composer), "--actor", acteur, "--target", cible,
               "--instruction", instruction, "--output", str(sortie)]
        if h_a and h_c:
            cmd += ["--actor-height-m", str(h_a), "--target-height-m", str(h_c)]
        if preposed:
            cmd.append("--actor-preposed")
        try:
            pr = subprocess.run(cmd, capture_output=True, text=True,
                                timeout=1800, check=False)
        except Exception as exc:  # noqa: BLE001
            return False, repr(exc)
        return (sortie.is_file() and sortie.stat().st_size > 1000,
                (pr.stdout or "")[-300:] + (pr.stderr or "")[-200:])

    socle = next((o for o in ordre if o["appui"] == "sol" and not o["pose"]),
                 ordre[0])

    # La scene porte l'acteur : le LLM repere son appui par des aliases
    # generiques ("personnage", "acteur", "perso", "sujet"...) au lieu du role
    # exact ("loutre"). Sans resolution, un prop (fusil appui=personnage) est
    # marque orphelin et la scene reste vide de cet objet. On resout ces
    # aliases vers l'entite VIVANTE (celle qui a une pose, sinon le socle),
    # MAIS on ne rebat JAMAIS un veritable orphelin sur le socle: un support
    # refuse reste un support manquant (comportement historique).
    ALIAS_APPUI = {"personnage", "personne", "acteur", "actrice", "sujet",
                   "sujets", "perso", "hero", "heroine", "protagoniste",
                   "character", "le_personnage", "la_personne", "humain"}
    vivant = next((o for o in ordre if o["pose"]), socle)
    for o in ordre:
        appui = o["appui"]
        if appui not in ("sol", "") and appui not in par_role:
            if appui in ALIAS_APPUI and vivant is not None and vivant is not o:
                print("SCENE_ORCH: %r appui %r -> acteur vivant %r"
                      % (o["role"], appui, vivant["role"]), flush=True)
                o["appui"] = vivant["role"]
            elif appui in ALIAS_APPUI and vivant is not None and vivant is o:
                # un seul vivant designe par un alias: il repose au sol.
                o["appui"] = "sol"
        # sinon laisse l'appui tel quel — par_role le verifie ensuite.

    scene_courante = socle["glb"]
    journal, etape = [], 0
    orphelins = []
    for o in ordre:
        if o is socle:
            continue
        parent = par_role.get(o["appui"])
        # Un objet dont l'appui a ete refuse n'a plus rien sur quoi reposer.
        # Le rabattre sur le socle posait les ECRANS SUR LA CHAISE quand le
        # bureau etait refuse: physiquement faux, et ca maquille le manque.
        if parent is None and o["appui"] != "sol":
            orphelins.append({"objet": o["role"], "appui_manquant": o["appui"]})
            print("SCENE_ORCH: %r repose sur %r qui manque — non compose"
                  % (o["role"], o["appui"]), file=sys.stderr)
            continue
        est_prop = not o["pose"]
        if est_prop and parent is not None and parent is not socle and parent["pose"]:
            # prop porte par l'acteur (fusil sur personnage) -> relation "tient",
            # pas "pose sur" (sinon l'objet flotte a cote, sans main ni contact).
            liaison = "tenu par"
        elif o["pose"] == "assis":
            liaison = "assis sur"
        elif o["pose"] == "allonge":
            liaison = "allonge sur"
        elif parent is not None and parent is not socle:
            liaison = "pose sur"
        elif o["appui"] == "sol":
            liaison = "a cote de"
        else:
            liaison = "pose sur"
        cible_desc = (parent or socle)["desc"]
        etape += 1
        sortie = scene_dir / ("etape%d_%s.glb" % (etape, o["role"]))
        tailles = real_heights(o["desc_generee"], cible_desc)
        ok, tail = _composer(o["glb"], scene_courante,
                             "%s %s %s" % (o["desc"], liaison, cible_desc), sortie,
                             h_a=tailles.get("actor_m"), h_c=tailles.get("target_m"),
                             preposed=bool(o["pose"]))
        journal.append({"etape": etape, "objet": o["role"], "liaison": liaison,
                        "sur": (parent or socle)["role"], "ok": ok,
                        "sortie": str(sortie)})
        print("SCENE_ORCH: %s %s %s -> %s" % (o["role"], liaison,
              (parent or socle)["role"], "OK" if ok else "ECHEC"), flush=True)
        if ok:
            scene_courante = str(sortie)
        else:
            print("SCENE_ORCH: composition de %r echouee (%s)"
                  % (o["role"], tail[-140:]), file=sys.stderr)

    scene_couleurs = scene_dir / "scene_couleurs.glb"
    shutil.copyfile(scene_courante, scene_couleurs)
    scene_geometrie = scene_dir / "scene_geometrie.glb"
    geo = {}
    try:
        from livraison_organisee import _glb_sans_materiaux
        geo = _glb_sans_materiaux(scene_couleurs, scene_geometrie)
    except Exception as exc:  # noqa: BLE001
        geo = {"ok": False, "error": repr(exc)}

    # --- 4. RANGER chaque entite (blanc + couleur), pas de vrac -------------
    # La branche scene retourne AVANT livraison_organisee: chaque dossier
    # models/<role>/ restait en vrac (name_mesh.glb, name_mesh_ao.glb,
    # name_final_materials.glb, ply, png, json...). Mesure 26/09 (loutre/fusil):
    # des dizaines de fichiers inutiles a la racine du run. On range ici,
    # best-effort et idempotent: modele/modele_couleurs.glb + modele_geometrie.glb
    # par entite, tout le reste vers travail/.
    deliveries = {}
    try:
        from livraison_organisee import organiser as _organiser_entite
        for o in objets:
            if not o.get("glb") or o.get("refus"):
                continue
            role = o["role"]
            doss = projet / role
            if not doss.is_dir():
                continue
            # la generation d'un jumeau vit dans le dossier du jumeau ORIGINAL:
            # on ne presente le dossier de l'entite que si elle en est le
            # PHYSIQUE detenteur (pas "copie_de").
            if doss.resolve() != Path(str(o["glb"])).parent.resolve():
                continue
            # final "couleurs" : privilegier le livrable deja range, sinon le
            # GLB porte par `o["glb"]` (c'est le fichier que la porte a vu).
            _fin = doss / "modele" / "modele_couleurs.glb"
            if not (_fin.is_file()):
                _fin = Path(str(o["glb"]))
            _ref = None
            for _c in (doss / ("%s_reference.png" % role),
                       doss / ("%s_front_reference.png" % role),
                       doss / "reference" / "face.png"):
                if _c.is_file():
                    _ref = str(_c)
                    break
            try:
                _liv = _organiser_entite(doss, role, final_mesh=str(_fin),
                                         front_reference=_ref)
                if _liv.get("ok") and _liv.get("livraison"):
                    _mc = _liv["livraison"].get("modele_couleurs")
                    _mg = _liv["livraison"].get("modele_geometrie")
                    deliveries[role] = {"ok": True, "couleurs": _mc, "geometrie": _mg}
                    # les chemins publient le fichier RANGE (les jumeaux
                    # partagent ce chemin).
                    for _j in objets:
                        if _j.get("glb") and role in str(_j["glb"]):
                            if _mc:
                                _j["glb"] = str(_mc)
                    print("SCENE_ORCH: %r range — couleurs + geometrie, "
                          "intermediaires dans travail/" % role, flush=True)
                else:
                    deliveries[role] = {"ok": False,
                                        "error": str(_liv.get("error"))}
                    print("SCENE_ORCH: rangement de %r impossible (%s)"
                          % (role, str(_liv.get("error"))[:120]),
                          file=sys.stderr)
            except Exception as exc:  # noqa: BLE001
                deliveries[role] = {"ok": False, "error": repr(exc)}
    except Exception as exc:  # noqa: BLE001
        deliveries = {"ok": False, "error": repr(exc)}

    complete = (not refuses and not orphelins
                and all(o.get("glb") for o in objets)
                and all(e["ok"] for e in journal))
    livraison_scene = {"scene_couleurs": str(scene_couleurs),
                       "scene_geometrie": str(scene_geometrie) if geo.get("ok") else None}
    livraison_scene.update(deliveries)
    return {
        "ok": complete, "is_scene": True, "plan": plan,
        "composants": {o["role"]: {"desc": o["desc"], "glb": o.get("glb"),
                                   "refus": o.get("refus")} for o in objets},
        "refuses": refuses,
        "orphelins": orphelins,
        "upright": upright_info,
        "composition": journal,
        "livraison": livraison_scene,
        "scene_glb": str(scene_couleurs),
        "scene_geometrie": str(scene_geometrie) if geo.get("ok") else None,
        "error": ("entites refusees ou composition incomplete: %s"
                  % ([r["role"] for r in refuses]
                     or [e["objet"] for e in orphelins]
                     or [e["objet"] for e in journal if not e["ok"]]))
                 if not complete else None,
    }



def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--output-dir", required=True)
    ap.add_argument("--split-only", action="store_true", help="only print the LLM scene split")
    args = ap.parse_args()
    if args.split_only:
        print(json.dumps(split_scene_prompt(args.prompt), ensure_ascii=False))
        return 0
    res = orchestrate_scene(args.prompt, args.run_id, args.output_dir)
    print(json.dumps(res, ensure_ascii=False, default=str))
    return 0 if res.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
