"""rigify_autorig — auto-rigs a humanoid GLB using Blender + Rigify addon.

Design:
  - Detects `blender` on PATH or common Windows install directories
  - If missing → returns actionable JSON telling the user to install Blender
  - Otherwise runs Blender in background with an embedded Python script that:
      1. imports the input GLB
      2. enables the "Rigify" addon (bundled with Blender)
      3. adds a human meta-rig, scales it to match the mesh bbox
      4. generates the rig
      5. parents the mesh to the rig with "Armature Deform With Automatic Weights"
      6. exports the result as GLB with animations-ready bones

Usage :
  python rigify_autorig.py --input model.glb --output rigged.glb
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent

BLENDER_CANDIDATES = [
    r"C:\Program Files\Blender Foundation\Blender 5.1\blender.exe",
    r"C:\Program Files\Blender Foundation\Blender 5.0\blender.exe",
    r"C:\Program Files\Blender Foundation\Blender 4.4\blender.exe",
    r"C:\Program Files\Blender Foundation\Blender 4.3\blender.exe",
    r"C:\Program Files\Blender Foundation\Blender 4.2\blender.exe",
    r"C:\Program Files\Blender Foundation\Blender 4.1\blender.exe",
    r"C:\Program Files\Blender Foundation\Blender 4.0\blender.exe",
    r"C:\Program Files\Blender Foundation\Blender 3.6\blender.exe",
    r"/Applications/Blender.app/Contents/MacOS/Blender",
    r"/usr/bin/blender",
    r"/usr/local/bin/blender",
]


def find_blender() -> str | None:
    # 0. portable Blender shipped under application/_blender/
    for portable in (WORKSPACE / "_blender").glob("blender-*-windows-x64"):
        exe = portable / "blender.exe"
        if exe.is_file():
            return str(exe)
    # 1. PATH
    found = shutil.which("blender")
    if found:
        return found
    # 2. Well-known Windows paths
    for cand in BLENDER_CANDIDATES:
        if os.path.isfile(cand):
            return cand
    return None


# -------------------- embedded Blender Python --------------------
# Saved to disk then passed via `blender --python <file>`
BLENDER_SCRIPT = r'''
import bpy, sys, os
argv = sys.argv
if "--" in argv:
    argv = argv[argv.index("--") + 1:]
else:
    argv = []
input_glb  = argv[0] if len(argv) > 0 else ""
output_glb = argv[1] if len(argv) > 1 else ""
if not input_glb or not os.path.isfile(input_glb):
    print("RIGIFY_ERROR: input GLB missing: %s" % input_glb)
    sys.exit(2)

# Clean default scene
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False, confirm=False)

# Import GLB
bpy.ops.import_scene.gltf(filepath=input_glb)
meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
if not meshes:
    print("RIGIFY_ERROR: no MESH in the imported GLB")
    sys.exit(3)

# Apply smooth shading to all meshes to fix faceted appearance
for m in meshes:
    bpy.ops.object.select_all(action="DESELECT")
    m.select_set(True)
    bpy.context.view_layer.objects.active = m
    bpy.ops.object.shade_smooth()

# Enable Rigify (bundled addon)
try:
    bpy.ops.preferences.addon_enable(module="rigify")
except Exception as e:
    print("RIGIFY_ERROR: cannot enable Rigify addon: %s" % e)
    sys.exit(4)

# Add a humanoid metarig at origin
bpy.ops.object.armature_human_metarig_add()
metarig = bpy.context.object
metarig.name = "aurora_metarig"

# Compute mesh bounding box height, scale metarig to match
mesh = meshes[0]
bb = [mesh.matrix_world @ v.co for v in mesh.data.vertices]
if bb:
    ys = [v.z for v in bb]
    height = max(ys) - min(ys)
    if height > 0.01:
        metarig.scale = (height, height, height)
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        metarig.location.z = min(ys)

# Generate the rig via Rigify
bpy.context.view_layer.objects.active = metarig
try:
    bpy.ops.pose.rigify_generate()
except Exception as e:
    print("RIGIFY_ERROR: rigify_generate failed: %s" % e)
    sys.exit(5)

# v77zal: Rigify naming changed in Blender 5.1 — the generated rig may be
# named "RIG-aurora_metarig", "rig_aurora", "rig", or just inherit a custom
# name. Find the rig as "any armature that is NOT our metarig", which is the
# robust convention across all Blender versions.
all_armatures = [o for o in bpy.context.scene.objects if o.type == "ARMATURE"]
rig_candidates = [o for o in all_armatures if o.name != "aurora_metarig" and "metarig" not in o.name.lower()]
if not rig_candidates:
    # Fallback: prefer one that starts with "rig" (legacy convention)
    rig_candidates = [o for o in all_armatures if o.name.lower().startswith("rig")]
if not rig_candidates:
    armature_names = [o.name for o in all_armatures]
    print("RIGIFY_ERROR: generated rig not found among armatures: %s" % armature_names)
    sys.exit(6)
rig = rig_candidates[0]
print("RIGIFY_INFO: generated rig found: %s" % rig.name)

# v77zal: Blender 5.1 — rigify_generate leaves us in POSE mode. Force OBJECT
# mode before select_all to avoid "context is incorrect" runtime error.
try:
    if bpy.context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
except Exception:
    pass

# Parent mesh to rig with automatic weights
bpy.ops.object.select_all(action="DESELECT")
mesh.select_set(True)
rig.select_set(True)
bpy.context.view_layer.objects.active = rig
try:
    bpy.ops.object.parent_set(type="ARMATURE_AUTO")
except Exception as e:
    print("RIGIFY_ERROR: parenting failed: %s" % e)
    sys.exit(7)


def _skin_ok(m):
    if len(m.vertex_groups) < 4:
        return False
    counted = 0
    for v in m.data.vertices[:2000]:
        if len(v.groups):
            counted += 1
    return counted > 200


if not _skin_ok(mesh):
    print("RIGIFY_INFO: bone-heat vide (mesh dense) -> proxy decime + transfert de poids")
    dup = mesh.copy()
    dup.data = mesh.data.copy()
    bpy.context.scene.collection.objects.link(dup)
    for vg in list(dup.vertex_groups):
        dup.vertex_groups.remove(vg)
    if len(dup.data.polygons) > 40000:
        dec = dup.modifiers.new("dec", "DECIMATE")
        dec.ratio = 40000.0 / len(dup.data.polygons)
        with bpy.context.temp_override(object=dup, active_object=dup, selected_editable_objects=[dup]):
            bpy.ops.object.modifier_apply(modifier=dec.name)
    ok_proxy = False
    try:
        with bpy.context.temp_override(active_object=rig, object=rig,
                                       selected_editable_objects=[dup, rig],
                                       selected_objects=[dup, rig]):
            bpy.ops.object.parent_set(type="ARMATURE_AUTO")
        ok_proxy = len(dup.vertex_groups) > 3
    except Exception as e:
        print("RIGIFY_INFO: bone-heat proxy echec: %s" % e)
    if ok_proxy:
        for vg in list(mesh.vertex_groups):
            mesh.vertex_groups.remove(vg)
        for vg in dup.vertex_groups:
            mesh.vertex_groups.new(name=vg.name)
        dt = mesh.modifiers.new("dt", "DATA_TRANSFER")
        dt.object = dup
        dt.use_vert_data = True
        dt.data_types_verts = {"VGROUP_WEIGHTS"}
        dt.vert_mapping = "NEAREST"
        dt.layers_vgroup_select_src = "ALL"
        dt.layers_vgroup_select_dst = "NAME"
        with bpy.context.temp_override(object=mesh, active_object=mesh, selected_editable_objects=[mesh]):
            bpy.ops.object.modifier_apply(modifier=dt.name)
        has_arm = any(m2.type == "ARMATURE" for m2 in mesh.modifiers)
        if not has_arm:
            am = mesh.modifiers.new("aurora_arm", "ARMATURE")
            am.object = rig
        print("RIGIFY_INFO: transfert de poids applique (%d groupes)" % len(mesh.vertex_groups))
    try:
        bpy.data.objects.remove(dup, do_unlink=True)
    except Exception:
        pass
    if not _skin_ok(mesh):
        print("RIGIFY_ERROR: skinning toujours vide apres proxy")
        sys.exit(8)

# v77zn: optional motion baking — bake an aurora.motion.v1 descriptor into
# an NLA action on the freshly generated rig before exporting.
motion_path = argv[2] if len(argv) > 2 else ""
motion_report = None
if motion_path and os.path.isfile(motion_path):
    try:
        import json as _json
        here = os.environ.get("AURORA_PYTHON_SERVICES")
        if here and here not in sys.path:
            sys.path.insert(0, here)
        import motion_baker as _mb  # noqa: E402
        with open(motion_path, "r", encoding="utf-8") as _fp:
            _motion = _json.load(_fp)
        _compiled = _mb.compile_motion_payload(_motion)
        # v77zq: forward primary mesh as fallback so mechanism primitives
        # (rotate/translate/extend on __object_root__) can mesh-direct
        # keyframe instead of being skipped.
        _mesh_fallback = next(
            (o for o in bpy.context.scene.objects if o.type == "MESH"), None,
        )
        # FORCE RIGIFY TO FK MODE!
        print("--- RIG PROPERTIES ---")
        for pb in rig.pose.bones:
            keys = list(pb.keys())
            if len(keys) > 0:
                print("BONE:", pb.name, "KEYS:", keys)
            for k in keys:
                if k == 'IK_FK' or k == 'ik_fk' or 'FK' in k.upper():
                    pb[k] = 1.0  # 1.0 is usually FK in Rigify
                    try:
                        pb.keyframe_insert(data_path=f'["{k}"]', frame=1)
                    except:
                        pass
        print("----------------------")
        
        motion_report = _mb.apply_compiled_motion(rig, _compiled, fallback_object=_mesh_fallback)
        print("MOTION_BAKED:", _compiled.get("id"),
              "applied=%d skipped=%d warnings=%d mech=%d" % (
                  motion_report.get("applied", 0),
                  motion_report.get("skipped", 0),
                  len(motion_report.get("warnings", [])),
                  len(motion_report.get("mechanism_actions", [])),
              ))
    except Exception as exc:
        print("MOTION_BAKE_WARN: %s" % exc)

# v77zal: Blender 5.1 — apply_compiled_motion leaves us in POSE mode if a
# motion was baked. Force OBJECT mode before select_all for export.
try:
    if bpy.context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
except Exception:
    pass

# Export rigged GLB
bpy.ops.object.select_all(action="SELECT")
try:
    # v80z: Blender 5.1 glTF I/O default animation mode dropped cross-object
    # actions when motion_baker assigned actions to multiple objects (rig +
    # mechanism mesh roots). Explicit ACTIVE_ACTIONS + NLA fallback so every
    # animated object's action survives export. Confirmed v5.1.19 generator.
    export_kwargs = dict(
        filepath=output_glb,
        export_format="GLB",
        export_skins=True,
        export_animations=True,
        use_selection=False,
    )
    try:
        # Blender 5.1+ accepts these knobs; older versions ignore unknown kw.
        export_kwargs["export_animation_mode"] = "ACTIVE_ACTIONS"
    except Exception:
        pass
    # Draco keeps files small, but the local acceptance/visual-audit path uses
    # trimesh and many UI viewers do not attach a DRACO loader by default. When
    # compressed, those readers see a zero-size mesh. Keep rigged exports plain
    # unless explicitly requested.
    if os.environ.get("AURORA_RIGIFY_DRACO", "").strip() == "1":
        export_kwargs["export_draco_mesh_compression_enable"] = True
        export_kwargs["export_draco_mesh_compression_level"] = 6
        export_kwargs["export_draco_position_quantization"] = 14
        export_kwargs["export_draco_normal_quantization"] = 10
        export_kwargs["export_draco_texcoord_quantization"] = 12
        export_kwargs["export_draco_color_quantization"] = 8
        export_kwargs["export_draco_generic_quantization"] = 12
    export_kwargs["export_optimize_animation_size"] = True
    try:
        bpy.ops.export_scene.gltf(**export_kwargs)
    except TypeError as draco_exc:
        # libdraco missing or older Blender: retry without Draco kwargs.
        for k in list(export_kwargs):
            if k.startswith("export_draco_") or k == "export_optimize_animation_size":
                del export_kwargs[k]
        bpy.ops.export_scene.gltf(**export_kwargs)
        print("RIGIFY_WARN: draco unavailable, exported uncompressed: %s" % draco_exc)
except Exception as e:
    print("RIGIFY_ERROR: export failed: %s" % e)
    sys.exit(8)

print("RIGIFY_OK: rigged GLB saved to %s" % output_glb)
'''


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input",  required=True, help="input GLB path")
    ap.add_argument("--output", required=True, help="output rigged GLB path")
    ap.add_argument("--motion", default="", help="optional aurora.motion.v1 JSON to bake as NLA action")
    args = ap.parse_args()

    blender = find_blender()
    if not blender:
        print(json.dumps({
            "ok": False,
            "error": "Blender n'est pas installé. Télécharge-le sur blender.org (Rigify est inclus par défaut). Chemins détectés testés : " + ", ".join(BLENDER_CANDIDATES[:3]),
        }, ensure_ascii=False))
        return 10

    input_abs  = os.path.abspath(args.input)
    output_abs = os.path.abspath(args.output)
    if not os.path.isfile(input_abs):
        print(json.dumps({"ok": False, "error": f"input GLB missing: {input_abs}"}))
        return 11
    os.makedirs(os.path.dirname(output_abs), exist_ok=True)

    # Write script to temp .py
    with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w", encoding="utf-8") as fp:
        fp.write(BLENDER_SCRIPT)
        script_path = fp.name

    motion_abs = ""
    if args.motion:
        motion_abs = os.path.abspath(args.motion)
        if not os.path.isfile(motion_abs):
            print(json.dumps({"ok": False, "error": f"motion JSON missing: {motion_abs}"}))
            return 14

    # Forward the python-services directory to the embedded Blender script so
    # it can `import motion_baker` (Blender's bundled python has no notion of
    # our project layout).
    env = os.environ.copy()
    env["AURORA_PYTHON_SERVICES"] = os.path.dirname(os.path.abspath(__file__))

    cmd = [blender, "--background", "--python", script_path, "--", input_abs, output_abs, motion_abs]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600, env=env)
    except subprocess.TimeoutExpired:
        print(json.dumps({"ok": False, "error": "Blender timed out after 10 min"}))
        return 12
    finally:
        try: os.unlink(script_path)
        except Exception: pass

    out = (proc.stdout or "") + "\n" + (proc.stderr or "")
    print("--- BLENDER OUTPUT ---", file=sys.stderr)
    print(out, file=sys.stderr)
    print("----------------------", file=sys.stderr)
    if "RIGIFY_OK" in out and os.path.isfile(output_abs):
        url = "/" + os.path.relpath(output_abs, os.path.join(str(WORKSPACE), "public")).replace(os.sep, "/") \
            if output_abs.startswith(os.path.join(str(WORKSPACE), "public") + os.sep) else None
        print(json.dumps({
            "ok": True,
            "blender": blender,
            "path": output_abs,
            "url": url,
            "size_bytes": os.path.getsize(output_abs),
        }, ensure_ascii=False))
        return 0
    err_line = next((l for l in out.splitlines() if "RIGIFY_ERROR" in l), None)
    reason = err_line or (out.splitlines()[-5:] if out.splitlines() else ["unknown"])
    print(json.dumps({
        "ok": False,
        "error": f"Blender finished with exit={proc.returncode}: {reason}"[:600],
    }, ensure_ascii=False))
    return proc.returncode or 13


if __name__ == "__main__":
    sys.exit(main())
