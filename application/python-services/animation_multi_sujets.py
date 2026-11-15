#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Animer plusieurs sujets d'une même demande, chacun avec SON mouvement, puis les recomposer.

15/11/2026 — « Zig la hyène qui court et Sharko le requin qui nage » : la reconstruction rend
déjà chaque personnage séparément (trellis_multi_character), mais l'étape d'animation recevait
la scène fusionnée et la traitait comme UN seul corps (un squelette pour deux personnages). Ici :

  1. la phrase est répartie entre ses sujets par le modèle de langage (qui fait quoi) ;
  2. chaque personnage reconstruit est reconnu sur SA découpe de la référence par le modèle de
     vision, qui dit aussi comment il se tient (deux jambes, quatre pattes, sans pattes) ;
  3. chacun est animé seul par semantic_animation avec son propre mouvement ;
  4. les résultats sont recomposés dans un seul GLB, chacun remis à sa place, leurs pistes
     réunies dans une seule animation.

Aucune règle ne dépend d'un sujet ou d'un mouvement nommé. Quand un modèle ne répond pas, le
rapport le dit et l'ordre de mention est utilisé, annoncé comme une supposition.
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any, Callable

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import glb_io  # noqa: E402

SCHEMA = "aurora.animation-multi-sujets.v1"
APPUIS = {"deux_jambes": "humanoid", "quatre_pattes": "quadruped", "sans_pattes": "creature"}

_CONSIGNE_REPARTITION = (
    "Tu lis une demande d'animation 3D qui met en scène plusieurs sujets. Pour CHAQUE sujet nommé, "
    "dis quel mouvement la demande lui donne. Réponds UNIQUEMENT par un JSON de la forme exacte "
    '{"sujets": [{"nom": "...", "nature": "...", "mouvement": "..."}]}. '
    "nom : le sujet avec les mots de la demande. nature : ce qu'est le sujet en deux à quatre mots (espèce, "
    "type d'être ou d'objet : « une hyène », « un requin », « un robot »), telle que la demande la dit, sinon "
    "ce que le nom désigne. mouvement : son action, reprise fidèlement ; chaîne vide si la demande ne lui en "
    "donne aucune. Dans l'ordre où la demande les nomme. Rien d'autre."
)


# ── 1. Qui fait quoi ────────────────────────────────────────────────────────────────────────────
def _ollama_json(consigne: str, texte: str, modele: str, timeout_s: float = 120.0) -> str:
    import urllib.request
    corps = json.dumps({"model": modele, "stream": False, "format": "json", "think": False,
                        "options": {"temperature": 0.0, "num_predict": 400},
                        "messages": [{"role": "system", "content": consigne},
                                     {"role": "user", "content": texte}]}).encode("utf-8")
    req = urllib.request.Request("http://127.0.0.1:11434/api/chat", data=corps,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout_s) as rep:
        return str(json.loads(rep.read().decode("utf-8")).get("message", {}).get("content", ""))


def _json(texte: str) -> Any:
    debut, fin = texte.find("{"), texte.rfind("}")
    if debut < 0 or fin <= debut:
        return None
    try:
        return json.loads(texte[debut:fin + 1])
    except ValueError:
        return None


def repartir_mouvements(demande: str, *, interroger: Callable[[str], str] | None = None,
                        modele: str | None = None) -> dict[str, Any]:
    """Rend {"source": "llm"|"indisponible", "sujets": [{"nom", "mouvement"}]}."""
    if interroger is None:
        if modele is None:
            try:
                from llm_disponible import resoudre_modele
                modele = resoudre_modele("orcarouter/Qwen3.8-27B-Uncensored:latest", "texte", bavard=False)
            except Exception:  # noqa: BLE001
                modele = "orcarouter/Qwen3.8-27B-Uncensored:latest"
        choisi = modele

        def interroger(texte: str) -> str:
            return _ollama_json(_CONSIGNE_REPARTITION, texte, choisi)
    try:
        brut = _json(str(interroger(demande)))
    except Exception as exc:  # noqa: BLE001
        return {"source": "indisponible", "raison": f"{type(exc).__name__}: {exc}"[:200], "sujets": []}
    sujets = []
    for item in (brut or {}).get("sujets") or []:
        if isinstance(item, dict) and isinstance(item.get("nom"), str) and item["nom"].strip():
            mouvement = item.get("mouvement") if isinstance(item.get("mouvement"), str) else ""
            nature = item.get("nature") if isinstance(item.get("nature"), str) else ""
            sujets.append({"nom": " ".join(item["nom"].split()), "nature": " ".join(nature.split())[:60],
                           "mouvement": " ".join(mouvement.split())})
    if not sujets:
        return {"source": "indisponible", "raison": "réponse hors contrat", "sujets": []}
    return {"source": "llm", "sujets": sujets}


# ── 2. Quel personnage est qui ──────────────────────────────────────────────────────────────────
def identifier_personnages(references: list[str | None], sujets: list[dict[str, str]], *,
                           demander: Callable[[str, str], Any] | None = None) -> list[dict[str, Any]]:
    """Pour chaque découpe : l'indice du sujet qu'elle montre et son appui au sol.

    L'attribution est biunivoque (deux découpes ne prennent jamais le même sujet) ; sans réponse
    du modèle de vision, l'ordre de mention est supposé, et le rapport le dit.
    """
    noms = [s["nom"] for s in sujets]
    # Un nom propre seul ne dit rien au modèle de vision (15/11/2026 : « Zig » et « Sharco » nus, la
    # hyène a été prise pour le requin) ; la nature de chaque sujet l'accompagne.
    libelles = [f"{s['nom']} — {s['nature']}" if s.get("nature") else s["nom"] for s in sujets]
    if demander is None:
        def demander(image: str, question: str) -> Any:
            from vlm_judge import ask_vlm
            return ask_vlm([image], question,
                           schema_hint='{"sujet": 1, "appui": "deux_jambes|quatre_pattes|sans_pattes"}')
    question = ("Cette image montre UN des sujets suivants : "
                + "; ".join(f"{i + 1}) {libelle}" for i, libelle in enumerate(libelles))
                + ". Lequel est-ce (son numéro) ? Et comment se tient-il : sur deux jambes, sur quatre "
                  "pattes, ou sans pattes (corps qui nage, rampe ou vole) ?")
    lus: list[dict[str, Any]] = []
    for idx, ref in enumerate(references):
        verdict: Any = None
        if ref and Path(ref).is_file() and len(noms) > 1:
            try:
                verdict = demander(str(ref), question)
            except Exception:  # noqa: BLE001
                verdict = None
        if isinstance(verdict, str):
            verdict = _json(verdict)
        numero = verdict.get("sujet") if isinstance(verdict, dict) else None
        appui = verdict.get("appui") if isinstance(verdict, dict) else None
        lus.append({"decoupe": idx,
                    "sujet": numero - 1 if isinstance(numero, int) and 1 <= numero <= len(noms) else None,
                    "appui": appui if appui in APPUIS else None})
    pris: set[int] = set()
    for lu in lus:                                   # une réponse lue garde son sujet si libre
        if lu["sujet"] is not None and lu["sujet"] not in pris:
            pris.add(lu["sujet"])
            lu["source"] = "vision"
        else:
            lu["sujet"] = None
    libres = [i for i in range(len(noms)) if i not in pris]
    for lu in lus:                                   # le reste suit l'ordre de mention, dit tel quel
        if lu["sujet"] is None:
            lu["sujet"] = libres.pop(0) if libres else None
            lu["source"] = "ordre_de_mention_suppose"
    return lus


# ── 3. Remettre chaque personnage animé à sa place ─────────────────────────────────────────────
def _matrice(noeud: dict) -> np.ndarray:
    if "matrix" in noeud:
        return np.array(noeud["matrix"], dtype=np.float64).reshape(4, 4).T
    t = np.array(noeud.get("translation", [0, 0, 0]), dtype=np.float64)
    x, y, z, w = noeud.get("rotation", [0, 0, 0, 1])
    r = np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                  [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                  [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])
    s = np.array(noeud.get("scale", [1, 1, 1]), dtype=np.float64)
    m = np.eye(4)
    m[:3, :3] = r * s
    m[:3, 3] = t
    return m


def _mondes(doc: dict) -> dict[int, np.ndarray]:
    noeuds = doc.get("nodes") or []
    scenes = doc.get("scenes") or [{"nodes": list(range(len(noeuds)))}]
    mondes: dict[int, np.ndarray] = {}
    pile = [(i, np.eye(4)) for i in scenes[int(doc.get("scene", 0) or 0)].get("nodes", [])]
    while pile:
        i, parent = pile.pop()
        mondes[i] = parent @ _matrice(noeuds[i])
        pile.extend((c, mondes[i]) for c in noeuds[i].get("children", []))
    return mondes


def boite_repos(doc: dict, blob: bytes | None = None, echantillon: int = 4000) -> tuple[np.ndarray, np.ndarray] | None:
    """Boîte englobante monde du modèle au repos.

    Un maillage avec peau est placé par ses os, pas par son nœud : ses sommets sont passés par
    la peau au repos (Σ poids · monde_os · matrice_inverse_de_liaison), sur un échantillon. Les
    squelettes exportés en centimètres avec une échelle 0,01 sur l'armature sont ainsi mesurés
    tels qu'ils s'affichent.
    """
    mondes = _mondes(doc)
    points = []
    for i, monde in mondes.items():
        noeud = doc["nodes"][i]
        if "mesh" not in noeud:
            continue
        for prim in doc["meshes"][noeud["mesh"]].get("primitives", []):
            attrs = prim["attributes"]
            if "skin" in noeud and blob is not None and "JOINTS_0" in attrs and "WEIGHTS_0" in attrs:
                peau = doc["skins"][noeud["skin"]]
                pos = glb_io.accessor(doc, blob, attrs["POSITION"]).astype(np.float64)
                pas = max(1, len(pos) // echantillon)
                pos = pos[::pas]
                articulations = glb_io.accessor(doc, blob, attrs["JOINTS_0"]).astype(np.int64)[::pas]
                poids = glb_io.accessor(doc, blob, attrs["WEIGHTS_0"]).astype(np.float64)[::pas]
                if poids.max() > 1.5:                      # poids normalisés en entiers
                    poids = poids / poids.sum(axis=1, keepdims=True).clip(1e-9)
                if "inverseBindMatrices" in peau:
                    ibm = glb_io.accessor(doc, blob, peau["inverseBindMatrices"]).astype(np.float64)
                    ibm = ibm.reshape(-1, 4, 4).transpose(0, 2, 1)
                else:
                    ibm = np.tile(np.eye(4), (len(peau["joints"]), 1, 1))
                os_mondes = np.array([mondes.get(j, np.eye(4)) for j in peau["joints"]]) @ ibm
                homog = np.concatenate([pos, np.ones((len(pos), 1))], axis=1)
                total = np.zeros((len(pos), 4))
                for k in range(articulations.shape[1]):
                    m = os_mondes[articulations[:, k]]
                    total += poids[:, k:k + 1] * np.einsum("nij,nj->ni", m, homog)
                points.append(total[:, :3])
            else:
                acc = doc["accessors"][attrs["POSITION"]]
                if "min" in acc and "max" in acc:
                    coins = np.array(np.meshgrid(*zip(acc["min"], acc["max"]))).T.reshape(-1, 3)
                    points.append((monde @ np.concatenate([coins, np.ones((len(coins), 1))], axis=1).T).T[:, :3])
    if not points:
        return None
    p = np.concatenate(points)
    return p.min(axis=0), p.max(axis=0)


def recalage(source: tuple[np.ndarray, np.ndarray], anime: tuple[np.ndarray, np.ndarray]) -> dict | None:
    """Échelle et translation qui ramènent la boîte du modèle animé sur celle du personnage placé
    (même hauteur, même pied, même centre au sol) ; None quand ils coïncident déjà (< 2 %)."""
    (smin, smax), (amin, amax) = source, anime
    hs, ha = float(smax[1] - smin[1]), float(amax[1] - amin[1])
    if hs <= 0 or ha <= 0:
        return None
    echelle = hs / ha
    centre_s = 0.5 * (smin + smax)
    centre_a = 0.5 * (amin + amax) * echelle
    translation = [float(centre_s[0] - centre_a[0]), float(smin[1] - amin[1] * echelle),
                   float(centre_s[2] - centre_a[2])]
    ecart = max(abs(echelle - 1.0), max(abs(t) for t in translation) / hs)
    return None if ecart < 0.02 else {"echelle": echelle, "translation": translation}


# ── 4. Un seul GLB, une seule animation ─────────────────────────────────────────────────────────
def _decaler_textures(objet: Any, decalage: int) -> None:
    if isinstance(objet, dict):
        for cle, valeur in objet.items():
            if isinstance(valeur, dict) and cle.endswith("Texture") and "index" in valeur:
                valeur["index"] += decalage
            _decaler_textures(valeur, decalage)
    elif isinstance(objet, list):
        for valeur in objet:
            _decaler_textures(valeur, decalage)


def composer(entrees: list[dict[str, Any]], sortie: str | Path, nom_animation: str = "mouvement") -> dict:
    """Réunit des GLB (chacun sous un nœud racine optionnellement recalé) dans un seul fichier ;
    les pistes de leurs premières animations forment une seule animation jouée ensemble."""
    out: dict[str, Any] = {"asset": {"version": "2.0", "generator": "AuroraIA animation_multi_sujets"},
                           "scene": 0, "scenes": [{"nodes": []}]}
    for cle in ("nodes", "meshes", "accessors", "bufferViews", "materials", "textures", "images",
                "samplers", "skins"):
        out[cle] = []
    animation = {"name": nom_animation, "channels": [], "samplers": []}
    binaire = bytearray()
    utilisees: set[str] = set()
    requises: set[str] = set()
    for rang, entree in enumerate(entrees):
        doc, blob = glb_io.load(str(entree["glb"]))
        doc = copy.deepcopy(doc)
        while len(binaire) % 4:
            binaire.append(0)
        base_octets = len(binaire)
        binaire.extend(blob)
        d = {cle: len(out[cle]) for cle in ("nodes", "meshes", "accessors", "bufferViews", "materials",
                                             "textures", "images", "samplers", "skins")}
        for bv in doc.get("bufferViews", []):
            bv["buffer"] = 0
            bv["byteOffset"] = int(bv.get("byteOffset", 0)) + base_octets
        for acc in doc.get("accessors", []):
            if "bufferView" in acc:
                acc["bufferView"] += d["bufferViews"]
            for partie in ("indices", "values"):
                if "sparse" in acc and "bufferView" in acc["sparse"].get(partie, {}):
                    acc["sparse"][partie]["bufferView"] += d["bufferViews"]
        for img in doc.get("images", []):
            if "bufferView" in img:
                img["bufferView"] += d["bufferViews"]
        for tex in doc.get("textures", []):
            if "source" in tex:
                tex["source"] += d["images"]
            if "sampler" in tex:
                tex["sampler"] += d["samplers"]
            for ext in (tex.get("extensions") or {}).values():
                if isinstance(ext, dict) and "source" in ext:
                    ext["source"] += d["images"]
        _decaler_textures(doc.get("materials", []), d["textures"])
        for mesh in doc.get("meshes", []):
            for prim in mesh.get("primitives", []):
                prim["attributes"] = {k: v + d["accessors"] for k, v in prim["attributes"].items()}
                if "indices" in prim:
                    prim["indices"] += d["accessors"]
                if "material" in prim:
                    prim["material"] += d["materials"]
                prim["targets"] = [{k: v + d["accessors"] for k, v in t.items()} for t in prim.get("targets", [])] or None
                if prim["targets"] is None:
                    prim.pop("targets")
        for noeud in doc.get("nodes", []):
            if "children" in noeud:
                noeud["children"] = [c + d["nodes"] for c in noeud["children"]]
            if "mesh" in noeud:
                noeud["mesh"] += d["meshes"]
            if "skin" in noeud:
                noeud["skin"] += d["skins"]
            noeud.pop("camera", None)
        for peau in doc.get("skins", []):
            peau["joints"] = [j + d["nodes"] for j in peau["joints"]]
            if "inverseBindMatrices" in peau:
                peau["inverseBindMatrices"] += d["accessors"]
            if "skeleton" in peau:
                peau["skeleton"] += d["nodes"]
        anims = doc.get("animations") or []
        if anims:
            base_samplers = len(animation["samplers"])
            for smp in anims[0].get("samplers", []):
                animation["samplers"].append({**smp, "input": smp["input"] + d["accessors"],
                                              "output": smp["output"] + d["accessors"]})
            for canal in anims[0].get("channels", []):
                cible = dict(canal["target"])
                if "node" in cible:
                    cible["node"] += d["nodes"]
                animation["channels"].append({"sampler": canal["sampler"] + base_samplers, "target": cible})
        for cle in ("nodes", "meshes", "accessors", "bufferViews", "materials", "textures", "images",
                    "samplers", "skins"):
            out[cle].extend(doc.get(cle, []))
        scenes = doc.get("scenes") or [{"nodes": []}]
        racines = [r + d["nodes"] for r in scenes[int(doc.get("scene", 0) or 0)].get("nodes", [])]
        racine = {"name": entree.get("nom") or f"sujet_{rang + 1}", "children": racines}
        if entree.get("recalage"):
            racine["translation"] = entree["recalage"]["translation"]
            racine["scale"] = [entree["recalage"]["echelle"]] * 3
        out["nodes"].append(racine)
        out["scenes"][0]["nodes"].append(len(out["nodes"]) - 1)
        utilisees.update(doc.get("extensionsUsed", []))
        requises.update(doc.get("extensionsRequired", []))
    while len(binaire) % 4:
        binaire.append(0)
    out["buffers"] = [{"byteLength": len(binaire)}]
    if animation["channels"]:
        out["animations"] = [animation]
    for cle in [k for k, v in out.items() if isinstance(v, list) and not v]:
        out.pop(cle)
    if utilisees:
        out["extensionsUsed"] = sorted(utilisees)
    if requises:
        out["extensionsRequired"] = sorted(requises)
    glb_io.save(str(sortie), out, bytes(binaire))
    return {"ok": True, "sortie": str(sortie), "sujets": len(entrees), "pistes": len(animation["channels"])}


# ── 5. Orchestration ────────────────────────────────────────────────────────────────────────────
def animer_sujets(demande: str, personnages: list[dict[str, Any]], dossier: str | Path, modele: str, *,
                  repartir: Callable[[str], dict] | None = None,
                  identifier: Callable[[list, list], list] | None = None,
                  animer: Callable[..., dict] | None = None) -> dict[str, Any]:
    dossier = Path(dossier)
    dossier.mkdir(parents=True, exist_ok=True)
    personnages = sorted(personnages, key=lambda p: int(p.get("index", 0)))
    repartition = (repartir or repartir_mouvements)(demande)
    sujets = repartition.get("sujets") or [{"nom": demande, "mouvement": ""}]
    lus = (identifier or identifier_personnages)([p.get("reference") for p in personnages], sujets)
    if animer is None:
        from semantic_animation import animate_existing as animer
    rapport: dict[str, Any] = {"schema": SCHEMA, "demande": demande, "repartition": repartition, "sujets": []}
    entrees = []
    for perso, lu in zip(personnages, lus):
        sujet = sujets[lu["sujet"]] if lu.get("sujet") is not None and lu["sujet"] < len(sujets) else {"nom": "", "mouvement": ""}
        consigne = f"{sujet['nom']} {sujet['mouvement']}".strip() or demande
        squelette = APPUIS.get(lu.get("appui") or "", "auto")
        sortie = dossier / f"personnage_{int(perso.get('index', 0)) + 1}" / "mouvement.glb"
        print(f"PROGRESS:animation:personnage {int(perso.get('index', 0)) + 1}/{len(personnages)} — "
              f"« {consigne[:70]} » ({lu.get('source')}, squelette {squelette})", flush=True)
        etat = {"index": perso.get("index"), "sujet": sujet["nom"], "mouvement": sujet["mouvement"],
                "attribution": lu.get("source"), "appui": lu.get("appui"), "squelette": squelette}
        try:
            res = animer(perso["glb"], str(sortie), consigne, modele, mode="animation", subject=squelette,
                         source_description=sujet["nom"] or demande)
        except Exception as exc:  # noqa: BLE001 — ce personnage reste statique, et le rapport le dit
            res = {"ok": False, "error": f"{type(exc).__name__}: {exc}"[:300]}
        anime = bool(res.get("ok") and res.get("path") and Path(str(res["path"])).is_file())
        glb = str(res["path"]) if anime else str(perso["glb"])
        etat.update({"anime": anime, "glb": glb, "erreur": None if anime else res.get("error")})
        recal = None
        if anime:
            b_src, b_anim = boite_repos(*glb_io.load(perso["glb"])), boite_repos(*glb_io.load(glb))
            if b_src is not None and b_anim is not None:
                recal = recalage(b_src, b_anim)
        etat["recalage"] = recal
        entrees.append({"glb": glb, "nom": (sujet["nom"] or f"sujet_{len(entrees) + 1}")[:60], "recalage": recal})
        rapport["sujets"].append(etat)
    composition = composer(entrees, dossier / "mouvement_couleurs.glb")
    rapport["composition"] = composition
    animes = sum(1 for s in rapport["sujets"] if s["anime"])
    rapport["ok"] = bool(composition.get("ok")) and animes == len(personnages)
    rapport["path"] = composition.get("sortie")
    rapport["anime"] = animes
    if not rapport["ok"]:
        rapport["error"] = f"{animes}/{len(personnages)} sujet(s) animé(s) ; " + "; ".join(
            f"{s['sujet'] or s['index']}: {s['erreur']}" for s in rapport["sujets"] if not s["anime"])[:400]
    (dossier / "animation_multi_sujets.json").write_text(json.dumps(rapport, ensure_ascii=False, indent=2),
                                                         encoding="utf-8")
    return rapport


def main() -> int:
    ap = argparse.ArgumentParser(description="Anime chaque sujet d'une demande avec son propre mouvement")
    ap.add_argument("--demande", required=True)
    ap.add_argument("--personnage", action="append", default=[], help="GLB d'un personnage placé (répétable)")
    ap.add_argument("--reference", action="append", default=[], help="découpe de référence, même ordre")
    ap.add_argument("--dossier", required=True)
    ap.add_argument("--modele", required=True)
    a = ap.parse_args()
    refs = a.reference + [None] * (len(a.personnage) - len(a.reference))
    personnages = [{"index": i, "glb": g, "reference": r} for i, (g, r) in enumerate(zip(a.personnage, refs))]
    try:
        res = animer_sujets(a.demande, personnages, a.dossier, a.modele)
    except Exception as exc:  # noqa: BLE001
        res = {"ok": False, "error": f"{type(exc).__name__}: {exc}"[:400]}
    print(json.dumps(res, ensure_ascii=False))
    # une composition partielle (un sujet resté statique) est un résultat, rapporté comme tel
    return 0 if res.get("path") else 1


if __name__ == "__main__":
    raise SystemExit(main())
