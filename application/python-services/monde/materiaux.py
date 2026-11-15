"""Matériaux PBR du moteur de scènes : une clé du vocabulaire → un matériau glTF (trimesh PBRMaterial).

Interface stable (toutes les briques et l'exporteur s'y fient) :
- `materiau_trimesh(cle, resolution=512) -> PBRMaterial`, mis en cache par (cle, resolution) ;
- `couleur_lineaire(hex) -> (r, g, b)` : sRGB → linéaire (les facteurs glTF sont linéaires, les
  textures de couleur sont en sRGB) ;
- `textures(cle, resolution) -> dict[str, PIL.Image]` : {"couleur", "orm", "normale"} ou {} si le
  matériau n'a pas encore de texture procédurale (couleur unie alors, jamais d'échec).

Les textures sont des MOTIFS RÉPÉTABLES (bords raccordés) dont un carreau couvre `taille_m` mètres :
l'exporteur divise les UV (en mètres) par `taille_m`.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Any

import numpy as np
from PIL import Image
from trimesh.visual.material import PBRMaterial

from monde import vocabulaire


def couleur_srgb(hexa: str) -> tuple[float, float, float]:
    h = hexa.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))  # type: ignore[return-value]


def couleur_lineaire(hexa: str) -> tuple[float, float, float]:
    def lin(c: float) -> float:
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    return tuple(lin(c) for c in couleur_srgb(hexa))  # type: ignore[return-value]


def textures(cle: str, resolution: int = 512) -> dict[str, Image.Image]:
    """Textures procédurales du matériau (motif répétable). Couleur unie tant qu'aucune n'est définie."""
    return {}


@lru_cache(maxsize=512)
def materiau_trimesh(cle: str, resolution: int = 512) -> PBRMaterial:
    spec: dict[str, Any] = vocabulaire.materiau(cle)
    r, g, b = couleur_lineaire(spec["couleur"])
    alpha = float(spec.get("alpha", 1.0))
    images = dict(textures(cle, resolution))
    if alpha < 0.999:
        # f3d 2.5 ignore l'alpha du facteur (mesuré dans ce projet) : la translucidité passe par la texture,
        # et le facteur garde alpha = 1 pour que tous les visualiseurs montrent la même chose.
        base = images.get("couleur")
        if base is None:
            base = Image.new("RGB", (4, 4), tuple(int(round(c * 255)) for c in couleur_srgb(spec["couleur"])))
        rgba = base.convert("RGBA")
        rgba.putalpha(int(round(alpha * 255)))
        images["couleur"] = rgba
        alpha = 1.0
    famille = spec["famille"]
    double = famille in {"verre", "vegetal", "eau", "lumiere"}
    options: dict[str, Any] = {
        "name": cle.replace(":", "_"),
        "baseColorFactor": [r, g, b, alpha] if "couleur" not in images else [1.0, 1.0, 1.0, alpha],
        "metallicFactor": float(spec["metal"]) if "orm" not in images else 1.0,
        "roughnessFactor": float(spec["rugosite"]) if "orm" not in images else 1.0,
        "doubleSided": double,
        "alphaMode": "BLEND" if float(spec.get("alpha", 1.0)) < 0.999 else "OPAQUE",
    }
    if "couleur" in images:
        options["baseColorTexture"] = images["couleur"]
    if "orm" in images:
        options["metallicRoughnessTexture"] = images["orm"]
    if "normale" in images:
        options["normalTexture"] = images["normale"]
    if spec.get("emissif"):
        k = float(spec["emissif"])
        options["emissiveFactor"] = [r * k, g * k, b * k]
    return PBRMaterial(**options)


def planche(cles: list[str], resolution: int = 256) -> Image.Image:
    """Planche de contrôle : une vignette de couleur de base par matériau (vérification à l'œil)."""
    cote = resolution
    colonnes = 8
    lignes = (len(cles) + colonnes - 1) // colonnes
    image = Image.new("RGB", (colonnes * cote, max(1, lignes) * cote), (40, 40, 40))
    for i, cle in enumerate(cles):
        tex = textures(cle, resolution).get("couleur")
        if tex is None:
            tex = Image.new("RGB", (cote, cote), tuple(int(c * 255) for c in couleur_srgb(vocabulaire.materiau(cle)["couleur"])))
        image.paste(tex.convert("RGB").resize((cote, cote)), ((i % colonnes) * cote, (i // colonnes) * cote))
    return image


def _verifier_repetable(img: Image.Image, tolerance: float = 0.12) -> bool:
    """Un motif répétable a des bords qui se raccordent : écart moyen bord gauche/droit et haut/bas."""
    a = np.asarray(img.convert("RGB"), dtype=np.float32) / 255.0
    return float(np.abs(a[:, 0] - a[:, -1]).mean()) < tolerance and float(np.abs(a[0] - a[-1]).mean()) < tolerance
