"""Ajoute des animations glTF 2.0 (pistes translation / rotation / échelle par nœud nommé) à un GLB existant.

trimesh n'exporte pas d'animation : le GLB est écrit d'abord, puis ses pistes sont ajoutées ici, dans le JSON
et à la fin du tampon binaire (accesseurs, vues, échantillonneurs LINEAR, canaux). Les nœuds sont trouvés par
leur nom ; un nom absent est signalé, jamais ignoré en silence.
"""
from __future__ import annotations

import json
import struct
from pathlib import Path
from typing import Any

import numpy as np

CHEMINS = {"translation": 3, "rotation": 4, "scale": 3}


def _lire(chemin: Path) -> tuple[dict, bytearray]:
    donnees = chemin.read_bytes()
    if donnees[:4] != b"glTF":
        raise ValueError(f"{chemin} n'est pas un GLB")
    longueur_json = struct.unpack_from("<I", donnees, 12)[0]
    gltf = json.loads(donnees[20:20 + longueur_json])
    binaire = bytearray()
    debut = 20 + longueur_json
    if len(donnees) >= debut + 8:
        longueur_bin = struct.unpack_from("<I", donnees, debut)[0]
        binaire = bytearray(donnees[debut + 8:debut + 8 + longueur_bin])
    return gltf, binaire


def _ecrire(chemin: Path, gltf: dict, binaire: bytearray) -> int:
    while len(binaire) % 4:
        binaire.append(0)
    gltf.setdefault("buffers", [{}])
    if not gltf["buffers"]:
        gltf["buffers"].append({})
    gltf["buffers"][0]["byteLength"] = len(binaire)
    texte = json.dumps(gltf, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    texte += b" " * ((4 - len(texte) % 4) % 4)
    total = 12 + 8 + len(texte) + 8 + len(binaire)
    sortie = bytearray(struct.pack("<4sII", b"glTF", 2, total))
    sortie += struct.pack("<I4s", len(texte), b"JSON") + texte
    sortie += struct.pack("<I4s", len(binaire), b"BIN\x00") + binaire
    chemin.write_bytes(bytes(sortie))
    return total


def _ajouter_accesseur(gltf: dict, binaire: bytearray, valeurs: np.ndarray, type_: str, bornes: bool) -> int:
    while len(binaire) % 4:
        binaire.append(0)
    a = np.ascontiguousarray(valeurs, dtype=np.float32)
    debut = len(binaire)
    binaire += a.tobytes()
    gltf.setdefault("bufferViews", []).append({"buffer": 0, "byteOffset": debut, "byteLength": a.nbytes})
    acc = {"bufferView": len(gltf["bufferViews"]) - 1, "componentType": 5126, "count": int(a.shape[0]), "type": type_}
    if bornes:
        acc["min"] = [float(v) for v in np.atleast_1d(a.min(axis=0))]
        acc["max"] = [float(v) for v in np.atleast_1d(a.max(axis=0))]
    gltf.setdefault("accessors", []).append(acc)
    return len(gltf["accessors"]) - 1


def injecter(chemin: str | Path, pistes: dict[str, dict[str, Any]], *, nom: str = "mouvement",
             sortie: str | Path | None = None) -> dict[str, Any]:
    """`pistes` : {nom_du_noeud: {"temps": [...], "translation": [[x,y,z]...], "rotation": [[x,y,z,w]...],
    "scale": [[sx,sy,sz]...]}} (chaque chemin facultatif). Rend {"ok", "canaux", "absents", "duree_s"}."""
    chemin = Path(chemin)
    gltf, binaire = _lire(chemin)
    indices = {n.get("name"): i for i, n in enumerate(gltf.get("nodes", [])) if n.get("name")}
    animation = {"name": nom, "samplers": [], "channels": []}
    absents, duree = [], 0.0
    temps_partages: dict[bytes, int] = {}
    for nom_noeud, piste in pistes.items():
        if nom_noeud not in indices:
            absents.append(nom_noeud)
            continue
        temps = np.asarray(piste["temps"], dtype=np.float32).reshape(-1)
        if len(temps) < 2 or np.any(np.diff(temps) <= 0):
            raise ValueError(f"temps non strictement croissants pour {nom_noeud}")
        duree = max(duree, float(temps[-1]))
        cle = temps.tobytes()
        if cle not in temps_partages:                          # un même découpage du temps n'est écrit qu'une fois
            temps_partages[cle] = _ajouter_accesseur(gltf, binaire, temps, "SCALAR", True)
        entree = temps_partages[cle]
        for chemin_anim, taille in CHEMINS.items():
            if chemin_anim not in piste:
                continue
            valeurs = np.asarray(piste[chemin_anim], dtype=np.float32).reshape(len(temps), taille)
            sortie_acc = _ajouter_accesseur(gltf, binaire, valeurs, "VEC4" if taille == 4 else "VEC3", False)
            animation["samplers"].append({"input": entree, "output": sortie_acc, "interpolation": "LINEAR"})
            animation["channels"].append({"sampler": len(animation["samplers"]) - 1,
                                          "target": {"node": indices[nom_noeud], "path": chemin_anim}})
    if animation["channels"]:
        gltf.setdefault("animations", []).append(animation)
    octets = _ecrire(Path(sortie) if sortie else chemin, gltf, binaire)
    return {"ok": not absents and bool(animation["channels"]), "canaux": len(animation["channels"]),
            "absents": absents, "duree_s": duree, "octets": octets}
