"""Rendus de contrôle f3d d'une scène du moteur « monde » : plan vu de dessus et vues aériennes.

f3d (OpenGL/VTK PBR) est le juge indépendant des matériaux glTF, des normales et du relief (règle du
projet). Rendu logiciel (Mesa) par défaut, comme `milieu_scene.rendre_f3d`, pour ne pas disputer la carte
graphique à un autre travail. Chaque rendu mesure la part de blanc pur (#FFFFFF), signe de surexposition.

Pièges f3d 2.5 mesurés dans ce projet : l'alpha du facteur de couleur est ignoré (seul celui de la texture
compte) ; la direction de caméra par défaut du poste peut cacher un sujet derrière un autre.
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Iterable

from PIL import Image, ImageDraw

import milieu_scene

HDRI = Path(__file__).resolve().parents[3] / "modele" / "external" / "TRELLIS.2" / "assets" / "hdri"
OPTIONS_BASE = ("-a", "-q", "-t")          # anti-crénelage, occlusion ambiante, tone mapping


def _direction(azimut_deg: float, elevation_deg: float) -> str:
    """Direction de vue (de la caméra vers la scène) : azimut autour de +Y depuis +Z, plongée en degrés."""
    a, e = math.radians(azimut_deg), math.radians(elevation_deg)
    d = (-math.sin(a) * math.cos(e), -math.sin(e), -math.cos(a) * math.cos(e))
    return ",".join(f"{c:.4f}" for c in d)


VUES: dict[str, tuple[str, ...]] = {
    # plan : caméra orthographique au zénith, le nord (-Z) en haut de l'image. Mesuré sur f3d 2.5 : avec
    # --camera-view-up explicite ou une direction exactement verticale, l'image sort VIDE ; un infime
    # penché vers le nord donne la bonne orientation sans rien d'autre.
    "plan": ("--camera-orthographic", "--camera-direction=0,-1,-0.001"),
    "aerienne_sud_est": (f"--camera-direction={_direction(35.0, 42.0)}",),
    "aerienne_nord_ouest": (f"--camera-direction={_direction(215.0, 42.0)}",),
    "rasante": (f"--camera-direction={_direction(20.0, 14.0)}",),
}


def rendre_vues(glb: str | Path, dossier: str | Path, *, vues: Iterable[str] = ("plan", "aerienne_sud_est",
                                                                                   "aerienne_nord_ouest"),
                resolution: tuple[int, int] = (900, 700), hdri: str | None = None, logiciel: bool = True,
                prefixe: str = "vue") -> dict[str, Any]:
    """Un PNG par vue + une planche légendée ; rapport avec la part de blanc pur de chaque rendu."""
    dossier = Path(dossier)
    dossier.mkdir(parents=True, exist_ok=True)
    options_hdri: tuple[str, ...] = ()
    eclairage = None
    if hdri:
        chemin = HDRI / f"{hdri}.exr"
        if chemin.is_file():
            options_hdri = (f"--hdri-file={chemin}", "-f")
            eclairage = str(chemin)
        else:
            # jamais en silence : un rendu sans l'éclairage demandé est signalé dans le rapport
            eclairage = f"absente : {chemin}"
    rendus = []
    for nom in vues:
        png = dossier / f"{prefixe}_{nom}.png"
        res = milieu_scene.rendre_f3d(glb, png, 0.0, resolution=resolution, logiciel=logiciel,
                                      options=(*OPTIONS_BASE, *options_hdri, *VUES[nom]))
        res["vue"] = nom
        rendus.append(res)
    reussis = [r for r in rendus if r.get("ok")]
    planche = None
    if reussis:
        images = [Image.open(r["png"]).convert("RGB") for r in reussis]
        largeur = sum(i.width for i in images)
        hauteur = max(i.height for i in images)
        toile = Image.new("RGB", (largeur, hauteur + 28), (24, 24, 24))
        x = 0
        dessin = ImageDraw.Draw(toile)
        for image, r in zip(images, reussis):
            toile.paste(image, (x, 28))
            dessin.text((x + 8, 7), f"{r['vue']}  (blanc pur {100 * r.get('part_blanc_pur', 0):.2f} %)",
                        fill=(235, 235, 235))
            x += image.width
        planche = dossier / f"planche_{prefixe}.png"
        toile.save(planche)
    return {"ok": len(reussis) == len(rendus), "rendus": rendus, "planche": str(planche) if planche else None,
            "hdri": eclairage,
            "blanc_pur_max": max((r.get("part_blanc_pur", 0.0) for r in reussis), default=None)}
