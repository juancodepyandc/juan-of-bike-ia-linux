"""Procedural steel-chain pendulum generator (Blender headless).

Builds a 20-link interlocked steel chain hanging from a hook fixture, with
a gentle pendulum swing animation. Exports a single GLB.

Materials are PBR (metal=1.0 rough=0.18) so the existing viewer's
RoomEnvironment gives real reflections — no Hunyuan paint, no VRAM contention.

CLI:
  python proc_cable_chain.py <output_glb>
"""
from __future__ import annotations
import argparse, json, os, shutil, subprocess, sys, tempfile, time
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_APP = _HERE.parent  # application/


def _find_blender() -> str | None:
    for sub in (_APP / "_blender").glob("blender-*-windows-x64"):
        exe = sub / "blender.exe"
        if exe.is_file():
            return str(exe)
    return shutil.which("blender")


_BLENDER_SCRIPT = r'''
import bpy, math, sys

def _argv():
    a = sys.argv
    return a[a.index("--")+1:] if "--" in a else []

out_glb = _argv()[0] if _argv() else "chain.glb"

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.context.scene.render.engine = "CYCLES"

def pbr_mat(name, color, metal, rough):
    m = bpy.data.materials.new(name); m.use_nodes = True
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (*color, 1.0)
        bsdf.inputs["Metallic"].default_value = metal
        bsdf.inputs["Roughness"].default_value = rough
    return m

mat_steel = pbr_mat("steel_polished", (0.62, 0.64, 0.66), 1.0, 0.18)
mat_steel_dark = pbr_mat("steel_dark",  (0.32, 0.32, 0.34), 1.0, 0.32)

# --- pivot empty at the anchor point (top of chain) -------------------------
ANCHOR_Z = 1.55
bpy.ops.object.empty_add(type="PLAIN_AXES", location=(0, 0, ANCHOR_Z))
anchor = bpy.context.active_object
anchor.name = "chain_pivot"

# --- ceiling plate ----------------------------------------------------------
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, ANCHOR_Z + 0.08))
plate = bpy.context.active_object
plate.name = "ceiling_plate"
plate.scale = (0.30, 0.30, 0.04)
bpy.ops.object.transform_apply(scale=True)
plate.data.materials.append(mat_steel_dark)
mod = plate.modifiers.new("Bevel", "BEVEL"); mod.width = 0.008; mod.segments = 2

# --- hook ring (small torus hooked through the top of the chain) -----------
bpy.ops.mesh.primitive_torus_add(major_radius=0.09, minor_radius=0.014,
                                  location=(0, 0, ANCHOR_Z),
                                  rotation=(math.radians(90), 0, 0))
hook = bpy.context.active_object
hook.name = "hook_ring"
hook.parent = anchor
hook.matrix_parent_inverse = anchor.matrix_world.inverted()
hook.data.materials.append(mat_steel_dark)

# --- chain links (alternating orientations so they interlock) --------------
N_LINKS = 20
LINK_R_MAJOR = 0.075
LINK_R_MINOR = 0.018
# Spacing : about 2 * (R_major - R_minor) so consecutive links share their
# inner clearance and the alternating axes interlock visually.
SPACING = (LINK_R_MAJOR - LINK_R_MINOR) * 2.0 + LINK_R_MINOR * 1.6
TOP_LINK_Z = ANCHOR_Z - 0.08

links = []
for i in range(N_LINKS):
    z = TOP_LINK_Z - i * SPACING
    # alternate : even rings lie in YZ plane (axis X), odd in XZ plane (axis Y)
    if i % 2 == 0:
        rot = (math.radians(90), 0, 0)
    else:
        rot = (0, math.radians(90), 0)
    bpy.ops.mesh.primitive_torus_add(major_radius=LINK_R_MAJOR, minor_radius=LINK_R_MINOR,
                                      location=(0, 0, z), rotation=rot,
                                      major_segments=24, minor_segments=10)
    link = bpy.context.active_object
    link.name = f"link_{i:02d}"
    link.parent = anchor
    link.matrix_parent_inverse = anchor.matrix_world.inverted()
    link.data.materials.append(mat_steel)
    links.append(link)

# --- end-of-chain weight (small steel ball) --------------------------------
weight_z = TOP_LINK_Z - N_LINKS * SPACING + LINK_R_MINOR
bpy.ops.mesh.primitive_uv_sphere_add(radius=0.06, location=(0, 0, weight_z - 0.04),
                                      segments=24, ring_count=14)
weight = bpy.context.active_object
weight.name = "chain_weight"
weight.parent = anchor
weight.matrix_parent_inverse = anchor.matrix_world.inverted()
weight.data.materials.append(mat_steel_dark)

# --- animation : pendulum swing -------------------------------------------
FPS = 30
DURATION = 3.0
NFR = int(FPS * DURATION)
bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = NFR

# Anchor swings around X (so the chain swings in YZ plane) with amplitude 12 deg,
# one full oscillation per loop.
SWING_AMP_DEG = 12.0
for f in range(1, NFR + 1, 2):
    phase = (f / NFR) * math.pi * 2
    bpy.context.scene.frame_set(f)
    anchor.rotation_euler = (math.sin(phase) * math.radians(SWING_AMP_DEG), 0, 0)
    anchor.keyframe_insert("rotation_euler", frame=f)
if anchor.animation_data and anchor.animation_data.action:
    for fc in anchor.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"

# Tiny per-link rotational lag (whip effect): each link adds a phase-shifted
# rotation around X in its OWN local frame on top of the pivot swing.
# Lag grows linearly down the chain : top links barely lag, weight lags most.
LAG_MAX_DEG = 3.0
PHASE_PER_LINK = 0.06  # radians of phase per link below top
for i, link in enumerate(links + [weight]):
    base_rot = list(link.rotation_euler)
    for f in range(1, NFR + 1, 4):
        phase = (f / NFR) * math.pi * 2 - i * PHASE_PER_LINK
        bpy.context.scene.frame_set(f)
        lag = math.sin(phase) * math.radians(LAG_MAX_DEG) * (i / N_LINKS)
        link.rotation_euler = (base_rot[0] + lag, base_rot[1], base_rot[2])
        link.keyframe_insert("rotation_euler", frame=f)
    if link.animation_data and link.animation_data.action:
        for fc in link.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"

# --- export ----------------------------------------------------------------
bpy.context.scene.frame_set(1)
bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB",
                            export_animations=True, export_apply=False)
print(f"CHAIN_OK: {out_glb}", flush=True)
'''


def make_chain(out_glb: str) -> dict:
    t0 = time.time()
    blender = _find_blender()
    if not blender:
        return {"ok": False, "error": "no Blender found"}
    work = Path(tempfile.mkdtemp(prefix="proc_chain_"))
    try:
        script_path = work / "build.py"
        script_path.write_text(_BLENDER_SCRIPT, encoding="utf-8")
        out_glb_abs = os.path.abspath(out_glb)
        os.makedirs(os.path.dirname(out_glb_abs), exist_ok=True)
        cmd = [blender, "--background", "--python", str(script_path), "--", out_glb_abs]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        ok = proc.returncode == 0 and "CHAIN_OK" in (proc.stdout or "") and os.path.isfile(out_glb_abs)
        elapsed = round(time.time() - t0, 1)
        if ok:
            return {"ok": True, "glb": out_glb_abs, "elapsed_s": elapsed, "size_bytes": os.path.getsize(out_glb_abs)}
        tail = "\n".join((proc.stdout or "").splitlines()[-20:] + (proc.stderr or "").splitlines()[-20:])
        return {"ok": False, "error": f"Blender exit {proc.returncode}", "log_tail": tail, "elapsed_s": elapsed}
    finally:
        shutil.rmtree(work, ignore_errors=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("output", help="output GLB path")
    args = ap.parse_args()
    r = make_chain(args.output)
    print(json.dumps(r))
    sys.exit(0 if r.get("ok") else 1)


if __name__ == "__main__":
    main()
