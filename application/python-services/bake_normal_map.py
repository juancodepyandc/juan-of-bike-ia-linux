"""bake_normal_map — bake a tangent-space normal map from a dense high-poly
mesh onto the UVs of a decimated low-poly mesh.

Used as Stage 3.6 of the AuroraIA 3D pipeline: after `paint_pbr_v21` produces
a clean ~40k-face textured GLB (low-poly), we bake the surface detail of the
raw ~700k-1M-face Hunyuan shape (high-poly) into a normal map so the viewer
gets the visual richness of the dense mesh on the light geometry.

Backend: a vendored portable Blender (`application/_blender/blender-x.y.z-
windows-x64/blender.exe`). Headless: `blender --background --python <script>`.
We can't `pip install bpy` here because no 3.12 wheel exists; the portable
install ships its own Python 3.11 + bpy.

Usage:
  python bake_normal_map.py <highpoly_path> <lowpoly_glb> <out_normal_png> [res]
  -> prints a JSON line {"ok": bool, "normal_png": "...", "elapsed_s": ...}

Programmatic:
  from bake_normal_map import bake_normal
  res = bake_normal(highpoly_path, lowpoly_glb_path, out_normal_png, res=2048)
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parents[1]  # .../AuroraIA-v2

# locate the portable Blender we shipped under application/_blender/
def _find_blender() -> str | None:
    for sub in (_REPO_ROOT / "application" / "_blender").glob("blender-*-windows-x64"):
        exe = sub / "blender.exe"
        if exe.is_file():
            return str(exe)
    on_path = shutil.which("blender")
    return on_path


# ---------- Blender-side script (written to a tmp file, run with `blender --background`) ----------
_BLENDER_SCRIPT = r'''
import bpy, sys, os, traceback

def _argv():
    # passed after "--"
    a = sys.argv
    if "--" in a:
        return a[a.index("--") + 1:]
    return []

def main():
    args = _argv()
    if len(args) < 4:
        print("BAKE_FAIL: not enough args", flush=True); sys.exit(2)
    high, low, out_png, res_s = args[0], args[1], args[2], args[3]
    res = int(res_s)

    bpy.ops.wm.read_factory_settings(use_empty=True)
    # render engine that supports baking
    bpy.context.scene.render.engine = "CYCLES"
    # CPU fine for a one-off bake; GPU adds complexity
    try:
        bpy.context.scene.cycles.device = "CPU"
    except Exception:
        pass

    def _import(path):
        ext = os.path.splitext(path)[1].lower()
        if ext == ".obj":
            bpy.ops.wm.obj_import(filepath=path)
        elif ext == ".glb" or ext == ".gltf":
            bpy.ops.import_scene.gltf(filepath=path)
        else:
            print(f"BAKE_FAIL: unsupported ext {ext} for {path}", flush=True); sys.exit(3)

    # import high then low; track which mesh objects came from which import
    before = set(o.name for o in bpy.data.objects)
    _import(high)
    high_names = set(o.name for o in bpy.data.objects if o.name not in before and o.type == "MESH")
    before = set(o.name for o in bpy.data.objects)
    _import(low)
    low_names = set(o.name for o in bpy.data.objects if o.name not in before and o.type == "MESH")

    if not high_names:
        print("BAKE_FAIL: no high-poly mesh imported", flush=True); sys.exit(4)
    if not low_names:
        print("BAKE_FAIL: no low-poly mesh imported", flush=True); sys.exit(5)

    high_objs = [bpy.data.objects[n] for n in high_names]
    low_objs = [bpy.data.objects[n] for n in low_names]
    # the low-poly we bake onto is the active object; pick the largest by face count
    low = max(low_objs, key=lambda o: len(o.data.polygons))

    # for the bake target, we need a material with an image-texture node selected
    img = bpy.data.images.new("BakeNormal", width=res, height=res, alpha=False, float_buffer=False)
    img.colorspace_settings.name = "Non-Color"  # normals are linear data

    mat = bpy.data.materials.new("BakeMat")
    mat.use_nodes = True
    nt = mat.node_tree
    # add an Image Texture node and SELECT it (Cycles bakes into the selected image)
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = img
    for n in nt.nodes:
        n.select = False
    tex.select = True
    nt.nodes.active = tex
    # replace material on the low-poly
    low.data.materials.clear()
    low.data.materials.append(mat)

    # selection: every high-poly selected, low-poly active and also selected
    bpy.ops.object.select_all(action="DESELECT")
    for o in high_objs:
        o.select_set(True)
    low.select_set(True)
    bpy.context.view_layer.objects.active = low

    # ensure the low has a UV map (paint_pbr_v21 outputs UVs, so it should)
    if not low.data.uv_layers:
        print("BAKE_FAIL: low-poly has no UV map", flush=True); sys.exit(6)

    size_ref = max(max(low.dimensions), 1e-4)
    try:
        bpy.ops.object.bake(
            type="NORMAL",
            use_selected_to_active=True,
            cage_extrusion=size_ref * 0.006,
            max_ray_distance=size_ref * 0.02,
            margin=8,
            normal_space="TANGENT",
        )
    except Exception as exc:
        traceback.print_exc()
        print(f"BAKE_FAIL: bake exception: {exc!r}", flush=True); sys.exit(7)

    # save the image
    img.filepath_raw = out_png
    img.file_format = "PNG"
    img.save()
    print(f"BAKE_OK: {out_png}", flush=True)


try:
    main()
except SystemExit:
    raise
except Exception as exc:
    import traceback; traceback.print_exc()
    print(f"BAKE_FAIL: top-level exception: {exc!r}", flush=True)
    sys.exit(99)
'''


def _glb_to_obj(glb_path: str, out_obj: str) -> bool:
    """Use trimesh to convert a GLB to OBJ while preserving UVs. Returns True if OK."""
    try:
        import trimesh
        m = trimesh.load(glb_path, force="mesh", process=False)
        m.export(out_obj)
        return os.path.isfile(out_obj)
    except Exception:
        return False


def bake_normal(
    highpoly_path: str,
    lowpoly_glb_path: str,
    out_normal_png: str,
    res: int = 2048,
    timeout_s: int = 600,
    log=print,
) -> dict[str, Any]:
    """Bake a tangent-space normal map. Returns {ok, normal_png, elapsed_s, ...}."""
    t0 = time.time()
    blender = _find_blender()
    if not blender:
        return {"ok": False, "error": "no Blender found (expected application/_blender/blender-*-windows-x64/blender.exe)"}

    workdir = Path(tempfile.mkdtemp(prefix="bake_normal_"))
    try:
        # Pass mesh files directly to Blender (it imports .obj/.ply/.glb/.gltf
        # natively via bpy.ops). Skipping a trimesh→OBJ conversion here avoids
        # multi-minute trimesh.load hangs we've seen on this machine.
        high_in = highpoly_path
        low_in = lowpoly_glb_path

        script = workdir / "bake.py"
        script.write_text(_BLENDER_SCRIPT, encoding="utf-8")
        os.makedirs(os.path.dirname(out_normal_png) or ".", exist_ok=True)
        cmd = [blender, "--background", "--python", str(script), "--", high_in, low_in, out_normal_png, str(res)]
        log(f"PROGRESS:bake_normal:Blender bake (high={Path(highpoly_path).name}, low={Path(lowpoly_glb_path).name}, res={res})...")
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s)
        except subprocess.TimeoutExpired:
            return {"ok": False, "error": f"Blender bake timeout after {timeout_s}s"}

        ok = proc.returncode == 0 and "BAKE_OK" in (proc.stdout or "") and os.path.isfile(out_normal_png)
        elapsed = round(time.time() - t0, 1)
        if ok:
            return {
                "ok": True,
                "normal_png": out_normal_png,
                "elapsed_s": elapsed,
                "size_bytes": os.path.getsize(out_normal_png),
            }
        # collect a short tail of stdout/stderr for the audit trail
        tail = "\n".join((proc.stdout or "").splitlines()[-12:] + (proc.stderr or "").splitlines()[-12:])
        return {"ok": False, "error": f"Blender bake failed (exit {proc.returncode})", "log_tail": tail, "elapsed_s": elapsed}
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def main() -> None:
    if len(sys.argv) < 4:
        print("usage: bake_normal_map.py <highpoly> <lowpoly_glb> <out_normal_png> [res]")
        sys.exit(2)
    high, low, out = sys.argv[1], sys.argv[2], sys.argv[3]
    res = int(sys.argv[4]) if len(sys.argv) >= 5 else 2048
    r = bake_normal(high, low, out, res=res)
    print(json.dumps(r, default=str))
    sys.exit(0 if r.get("ok") else 1)


if __name__ == "__main__":
    main()
