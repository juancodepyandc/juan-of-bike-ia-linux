"""Volumes animés (gaz simulés par `monde.gaz`) écrits dans un GLB existant.

glTF 2.0 ne porte pas de volume : chaque gaz devient un nœud vide nommé dont les extras `aurora_volume`
(schéma `aurora.volume.v1`) décrivent la boîte, la cadence, l'optique du milieu, et désignent une vue du
tampon binaire où sont rangées ses images (uint8 en racine de la densité, compressées zlib une à une, x varie le
plus vite, canaux entrelacés). Le GLB reste lisible partout (un nœud vide de plus) ; le viewer d'AuroraIA lit la
vue par le parseur glTF et rend le gaz par lancer de rayons (`src/services/matterVolume.ts`).
"""
from __future__ import annotations

import zlib
from pathlib import Path
from typing import Any

import numpy as np

from monde import animation_gltf

SCHEMA = "aurora.volume.v1"


def extras(volume, vue: int, decalages: list[int]) -> dict[str, Any]:
    mn, mx = volume.boite
    return {"schema": SCHEMA, "milieu": volume.milieu, "dims": [int(v) for v in volume.dims],
            "boite": {"min": [round(v, 6) for v in mn], "max": [round(v, 6) for v in mx]},
            "fps": int(volume.fps), "images": len(volume.images), "boucle": True, "canaux": list(volume.canaux),
            "codage": "zlib-u8-racine", "bufferView": int(vue), "decalages": [int(v) for v in decalages],
            "direction": [round(float(c), 4) for c in getattr(volume, "direction", (0.0, 1.0, 0.0))],
            "optique": volume.optique(), "mesures": volume.mesures}


def injecter(chemin: str | Path, volumes: list, *, sortie: str | Path | None = None) -> dict[str, Any]:
    """Ajoute chaque volume (nœud à la racine de la scène, boîte en coordonnées de la scène)."""
    chemin = Path(chemin)
    gltf, binaire = animation_gltf._lire(chemin)
    scenes = gltf.setdefault("scenes", [{"nodes": []}])
    racine = scenes[int(gltf.get("scene", 0))].setdefault("nodes", [])
    rapport = []
    for volume in volumes:
        while len(binaire) % 4:
            binaire.append(0)
        debut = len(binaire)
        decalages = [0]
        brut = 0
        for image in volume.images:
            octets = np.ascontiguousarray(image).tobytes()
            brut += len(octets)
            binaire += zlib.compress(octets, 6)
            decalages.append(len(binaire) - debut)
        gltf.setdefault("bufferViews", []).append({"buffer": 0, "byteOffset": debut, "byteLength": len(binaire) - debut})
        vue = len(gltf["bufferViews"]) - 1
        gltf.setdefault("nodes", []).append({"name": volume.nom, "extras": {"aurora_volume": extras(volume, vue, decalages)}})
        racine.append(len(gltf["nodes"]) - 1)
        rapport.append({"nom": volume.nom, "milieu": volume.milieu, "dims": list(volume.dims), "images": len(volume.images),
                        "octets_compresses": decalages[-1], "octets_bruts": brut})
    octets = animation_gltf._ecrire(Path(sortie) if sortie else chemin, gltf, binaire)
    return {"ok": bool(volumes), "volumes": rapport, "octets": octets}


def lire(chemin: str | Path) -> list[dict[str, Any]]:
    """Relit les volumes d'un GLB (extras + images décompressées) : la preuve que le fichier les contient."""
    gltf, binaire = animation_gltf._lire(Path(chemin))
    sortie = []
    for noeud in gltf.get("nodes", []):
        meta = (noeud.get("extras") or {}).get("aurora_volume")
        if not meta or meta.get("schema") != SCHEMA:
            continue
        vue = gltf["bufferViews"][meta["bufferView"]]
        base = vue.get("byteOffset", 0)
        nx, ny, nz = meta["dims"]
        c = len(meta["canaux"])
        images = []
        for a, b in zip(meta["decalages"][:-1], meta["decalages"][1:]):
            brut = zlib.decompress(bytes(binaire[base + a:base + b]))
            images.append(np.frombuffer(brut, np.uint8).reshape((nz, ny, nx, c) if c > 1 else (nz, ny, nx)))
        sortie.append({"nom": noeud.get("name"), "meta": meta, "images": images})
    return sortie
