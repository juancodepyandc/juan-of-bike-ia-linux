#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""motion_clay_render — le MOUVEMENT en argile, sans couleurs.

Pendant statique: {run}_GEOMETRIE.png (4 vues clay). Ici, la meme chose pour
l'ANIMATION: on rend N instants du mouvement en blanc mat (moteur Workbench,
matiere ignoree, cavites accentuees) et on assemble une planche-contact. Les
couleurs et textures masquent les defauts de deformation — dechirures aux
aisselles, plis qui traversent, pieds qui glissent. En argile, ils sautent aux
yeux.

Usage:
    python motion_clay_render.py --input <rigged.glb> --output <planche.png>
                                 [--frames 8] [--res 560]

Sortie: la planche PNG + le dossier <planche>_frames/ avec chaque instant.
Verifie que le mouvement est VISIBLE (les instants different) — sinon erreur.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

_BLENDER_CANDIDATES = [
    os.path.expanduser("~/.local/bin/blender"),
    "/usr/bin/blender", "/snap/bin/blender", "blender",
]

_SCRIPT = r'''
import bpy, sys, os, math
argv = sys.argv[sys.argv.index("--") + 1:]
src, out_dir, n_frames, res = argv[0], argv[1], int(argv[2]), int(argv[3])

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=src)
sc = bpy.context.scene

# GARDE ALPHA: TRELLIS encode les cheveux en semi-transparent (alpha ~69 sur
# la tete du guerrier, mesure) mais exporte OPAQUE. Cycles honore l'entree
# Alpha du Principled -> la chevelure entiere disparaitrait au rendu. On force
# l'opacite sur tous les materiaux importes.
for _m in bpy.data.materials:
    if not _m.use_nodes:
        continue
    for _n in _m.node_tree.nodes:
        if _n.type == "BSDF_PRINCIPLED" and "Alpha" in _n.inputs:
            for _lk in list(_n.inputs["Alpha"].links):
                _m.node_tree.links.remove(_lk)
            _n.inputs["Alpha"].default_value = 1.0
    try:
        _m.blend_method = "OPAQUE"
    except Exception:
        pass


# Etendue de l'animation: la plus longue action importee.
f_end = 2
for a in bpy.data.actions:
    try:
        f_end = max(f_end, int(a.frame_range[1]))
    except Exception:
        pass
f_end = max(f_end, 2)
sc.frame_start, sc.frame_end = 1, f_end

meshes = [o for o in bpy.data.objects if o.type == "MESH"]
if not meshes:
    print("CLAY_FAIL: aucun maillage")
    sys.exit(2)

# Cadre: englober le mouvement ENTIER (bbox sur plusieurs instants), sinon le
# sujet sort du cadre des qu'il se deplace.
def scene_bbox_at(fr):
    sc.frame_set(fr)
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    lo = [1e9] * 3; hi = [-1e9] * 3
    for o in meshes:
        ev = o.evaluated_get(dg)
        m = ev.to_mesh()
        for v in m.vertices:
            w = ev.matrix_world @ v.co
            for i in range(3):
                lo[i] = min(lo[i], w[i]); hi[i] = max(hi[i], w[i])
        ev.to_mesh_clear()
    return lo, hi

los, his = [1e9]*3, [-1e9]*3
probe = sorted(set([1, max(1, f_end // 2), f_end]))
for fr in probe:
    lo, hi = scene_bbox_at(fr)
    for i in range(3):
        los[i] = min(los[i], lo[i]); his[i] = max(his[i], hi[i])
cx = [(los[i] + his[i]) / 2 for i in range(3)]
span = max(his[i] - los[i] for i in range(3))
span = max(span, 0.2)

# Camera de face, orthographique: pas de deformation de perspective, on juge la
# geometrie seule.
bpy.ops.object.camera_add(location=(cx[0], cx[1] - span * 3.0, cx[2]))
cam = bpy.context.object
cam.rotation_euler = (math.pi / 2, 0.0, 0.0)
cam.data.type = "ORTHO"
cam.data.ortho_scale = span * 1.35
sc.camera = cam

# Workbench = rendu "argile" natif: matiere unique, cavites, pas d'eclairage a
# regler, rapide et deterministe.
sc.render.engine = "BLENDER_WORKBENCH"
sh = sc.display.shading
sh.light = "STUDIO"
sh.color_type = "SINGLE"
sh.single_color = (0.82, 0.82, 0.82)
sh.show_cavity = True
sh.show_object_outline = True
sc.display.render_aa = "8"
sc.render.resolution_x = res
sc.render.resolution_y = res
sc.render.film_transparent = False
sc.render.image_settings.file_format = "PNG"

os.makedirs(out_dir, exist_ok=True)
if n_frames < 2:
    n_frames = 2
for k in range(n_frames):
    fr = 1 + int(round(k * (f_end - 1) / float(n_frames - 1)))
    sc.frame_set(fr)
    sc.render.filepath = os.path.join(out_dir, "clay_%03d.png" % fr)
    bpy.ops.render.render(write_still=True)
print("CLAY_OK frames=%d f_end=%d" % (n_frames, f_end))
'''


def _blender() -> str:
    envb = os.environ.get("AURORA_BLENDER")
    if envb and os.path.isfile(envb):
        return envb
    for c in _BLENDER_CANDIDATES:
        if os.path.isfile(c):
            return c
        w = shutil.which(c)
        if w:
            return w
    return "blender"


def render(input_glb: str, output_png: str, *, frames: int = 8,
           res: int = 560, timeout_s: int = 900) -> dict:
    if not os.path.isfile(input_glb):
        return {"ok": False, "error": "GLB introuvable: %s" % input_glb}
    out_png = Path(output_png)
    frames_dir = out_png.with_suffix("")  # <nom>_frames
    frames_dir = Path(str(frames_dir) + "_frames")
    frames_dir.mkdir(parents=True, exist_ok=True)

    fd, script_path = tempfile.mkstemp(suffix="_clay.py")
    os.close(fd)
    Path(script_path).write_text(_SCRIPT, encoding="utf-8")
    try:
        proc = subprocess.run(
            [_blender(), "--background", "--python", script_path, "--",
             os.path.abspath(input_glb), str(frames_dir), str(frames),
             str(res)],
            capture_output=True, text=True, timeout=timeout_s)
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "rendu argile: delai depasse"}
    finally:
        try:
            os.unlink(script_path)
        except Exception:  # noqa: BLE001
            pass

    if "CLAY_OK" not in (proc.stdout or ""):
        return {"ok": False,
                "error": (proc.stdout or proc.stderr or "")[-300:]}
    imgs = sorted(frames_dir.glob("clay_*.png"))
    if len(imgs) < 2:
        return {"ok": False, "error": "moins de 2 instants rendus"}

    # Planche-contact + preuve que le mouvement est VISIBLE. Un baker qui
    # "reussit" sur des images identiques est le piege deja paye 4 fois.
    try:
        from PIL import Image
        import numpy as np
        ims = [Image.open(p).convert("RGB") for p in imgs]
        w, h = ims[0].size
        cols = min(4, len(ims))
        rows = (len(ims) + cols - 1) // cols
        sheet = Image.new("RGB", (w * cols, h * rows), (16, 16, 20))
        for i, im in enumerate(ims):
            sheet.paste(im, ((i % cols) * w, (i // cols) * h))
        sheet.save(str(out_png))
        a = np.asarray(ims[0], dtype=float)
        b = np.asarray(ims[len(ims) // 2], dtype=float)
        moved = float(np.abs(a - b).mean())
    except Exception as exc:  # noqa: BLE001
        return {"ok": True, "sheet": None, "frames_dir": str(frames_dir),
                "frames": len(imgs),
                "note": "assemblage PIL indisponible: %r" % (exc,)}
    out = {"ok": True, "sheet": str(out_png), "frames_dir": str(frames_dir),
           "frames": len(imgs), "variation": round(moved, 2)}
    if moved < 0.5:
        out["ok"] = False
        out["error"] = ("les instants du mouvement sont identiques "
                        "(variation %.2f/255): animation invisible" % moved)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--frames", type=int, default=8)
    ap.add_argument("--res", type=int, default=560)
    a = ap.parse_args()
    r = render(a.input, a.output, frames=a.frames, res=a.res)
    print(json.dumps(r, ensure_ascii=False))
    return 0 if r.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
