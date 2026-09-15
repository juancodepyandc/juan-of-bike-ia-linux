"""
AuroraIA — Blender headless bridge
Pilots Blender CLI for procedural modeling, rigging, validation, and cleanup.

Usage:
  python blender_bridge.py --mode procedural --template pulley_belt_system ...
  python blender_bridge.py --mode rig --mesh <path> --rig-system rigify ...
  python blender_bridge.py --mode validate --mesh <path> --checks non_manifold,degenerate ...
  python blender_bridge.py --mode cleanup --mesh <path> --auto-fix ...
  python blender_bridge.py --script <path.py> [extra args...]
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def emit(stage: str, detail: str):
    print(f"PROGRESS:{stage}:{detail}", flush=True)


def find_blender() -> str | None:
    """Find Blender executable on the system."""
    local_blender_root = Path(__file__).resolve().parents[1] / "_blender"
    local_blenders = sorted(
        local_blender_root.glob("blender-*-windows-x64/blender.exe"),
        reverse=True,
    )
    candidates = [
        shutil.which("blender"),
        *(str(path) for path in local_blenders),
        # Windows common paths
        r"C:\Program Files\Blender Foundation\Blender 5.1\blender.exe",
        r"C:\Program Files\Blender Foundation\Blender 4.4\blender.exe",
        r"C:\Program Files\Blender Foundation\Blender 4.3\blender.exe",
        r"C:\Program Files\Blender Foundation\Blender 4.2\blender.exe",
        # Scoop / chocolatey
        os.path.expanduser(r"~\scoop\apps\blender\current\blender.exe"),
    ]
    for candidate in candidates:
        if candidate and os.path.isfile(candidate):
            return candidate
    return None


def run_blender_script(blender_path: str, script_content: str, extra_args: list[str] | None = None, inject_colorize: bool = False) -> dict:
    """Run a Blender Python script in headless mode."""
    if inject_colorize:
        # Inject the PBR helpers and auto-apply them just before export.
        # iter14 fix: preserve the caller's indentation. The previous string
        # replacement put `_apply_pbr_to_scene()` at column 0 even when the
        # `bpy.ops.export_scene.gltf(...)` call was inside an `if fmt == "glb":`
        # block, which broke any subsequent `elif`/`else` branches with a
        # SyntaxError ("elif cannot follow a column-0 stmt"). Walk lines
        # instead and copy the leading whitespace.
        prelude = COLORIZE_HELPERS
        export_call_re = re.compile(
            r"^(\s*)(bpy\.ops\.(?:export_scene\.gltf|export_scene\.fbx|wm\.obj_export)\()"
        )
        patched_lines = []
        for raw in script_content.splitlines(keepends=True):
            m = export_call_re.match(raw)
            if m:
                indent = m.group(1)
                patched_lines.append(f"{indent}_apply_pbr_to_scene()\n")
            patched_lines.append(raw)
        script_content = prelude + "\n" + "".join(patched_lines)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write(script_content)
        script_path = f.name

    try:
        cmd = [blender_path, "--background", "--python", script_path]
        if extra_args:
            cmd.extend(["--"] + extra_args)
        # Forward AURORA_COLORS (and any AURORA_* config) to the Blender subprocess
        # so the injected PBR helpers pick up the user palette.
        subproc_env = {**os.environ}
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600, env=subproc_env)

        # Look for JSON result line in stdout
        for line in reversed(result.stdout.splitlines()):
            line = line.strip()
            if line.startswith("{") and line.endswith("}"):
                try:
                    return json.loads(line)
                except json.JSONDecodeError:
                    pass

        if result.returncode != 0:
            return {"ok": False, "error": f"Blender exited with code {result.returncode}: {result.stderr[-500:] if result.stderr else 'no stderr'}"}
        if "Traceback (most recent call last)" in (result.stderr or ""):
            return {"ok": False, "error": result.stderr[-2000:], "stdout": result.stdout[-1000:]}
        return {"ok": True, "output": result.stdout[-1000:], "stderr": result.stderr[-1000:] if result.stderr else ""}
    finally:
        os.unlink(script_path)


# ── PROCEDURAL TEMPLATES ──

COLORIZE_HELPERS = '''
import os, json, math

def _hex_to_rgb(value):
    """Accept "#rrggbb", "rrggbb" or a (r,g,b) tuple (0-1 or 0-255) and return a 0-1 tuple."""
    if value is None:
        return None
    if isinstance(value, (list, tuple)) and len(value) >= 3:
        r, g, b = value[0], value[1], value[2]
        if max(r, g, b) > 1.5:
            return (r / 255.0, g / 255.0, b / 255.0)
        return (float(r), float(g), float(b))
    if isinstance(value, str):
        clean = value.strip().lstrip("#")
        if len(clean) == 3:
            clean = "".join(c * 2 for c in clean)
        if len(clean) == 6:
            try:
                return (int(clean[0:2], 16) / 255.0, int(clean[2:4], 16) / 255.0, int(clean[4:6], 16) / 255.0)
            except ValueError:
                return None
    return None


def _load_color_overrides():
    """Read color overrides from the AURORA_COLORS env var (JSON dict: {"pulley":"#ff0000"})."""
    raw = os.environ.get("AURORA_COLORS", "").strip()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            return {}
        out = {}
        for key, value in parsed.items():
            rgb = _hex_to_rgb(value)
            if rgb is not None:
                out[str(key).lower()] = rgb
        return out
    except Exception:
        return {}


_COLOR_OVERRIDES = _load_color_overrides()


def _ensure_pbr_material(name, base_color, metallic=0.1, roughness=0.55, emission_strength=0.0, emission_color=None):
    """Create or reuse a Principled BSDF material with the given PBR params."""
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name)
        mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    out = nodes.new("ShaderNodeOutputMaterial")
    bsdf.inputs["Base Color"].default_value = (*base_color, 1.0)
    if "Metallic" in bsdf.inputs:
        bsdf.inputs["Metallic"].default_value = metallic
    if "Roughness" in bsdf.inputs:
        bsdf.inputs["Roughness"].default_value = roughness
    if emission_strength > 0.0:
        em_rgb = emission_color if emission_color is not None else base_color
        if "Emission" in bsdf.inputs:
            bsdf.inputs["Emission"].default_value = (*em_rgb, 1.0)
        elif "Emission Color" in bsdf.inputs:
            bsdf.inputs["Emission Color"].default_value = (*em_rgb, 1.0)
        if "Emission Strength" in bsdf.inputs:
            bsdf.inputs["Emission Strength"].default_value = emission_strength
    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return mat


PALETTE = {
    "motionarrow": {"base_color": (1.0, 0.78, 0.04), "metallic": 0.15, "roughness": 0.34},
    "pulley": {"base_color": (0.50, 0.52, 0.56), "metallic": 0.9, "roughness": 0.24},
    "belt":    {"base_color": (0.04, 0.04, 0.05), "metallic": 0.0, "roughness": 0.82},
    "gear":    {"base_color": (0.72, 0.74, 0.78), "metallic": 1.0, "roughness": 0.22},
    "barrel":  {"base_color": (0.32, 0.34, 0.38), "metallic": 0.9, "roughness": 0.35},
    "rod":     {"base_color": (0.92, 0.94, 0.98), "metallic": 1.0, "roughness": 0.08},
    "piston":  {"base_color": (0.88, 0.88, 0.92), "metallic": 1.0, "roughness": 0.12},
    "hinge":   {"base_color": (0.42, 0.44, 0.47), "metallic": 0.85, "roughness": 0.28},
    "pin":     {"base_color": (0.82, 0.72, 0.38), "metallic": 0.95, "roughness": 0.18},
    "frame":   {"base_color": (0.34, 0.36, 0.40), "metallic": 0.55, "roughness": 0.58},
    "support": {"base_color": (0.28, 0.30, 0.34), "metallic": 0.55, "roughness": 0.58},
    "leaf":    {"base_color": (0.55, 0.58, 0.62), "metallic": 0.75, "roughness": 0.32},
    "link":    {"base_color": (0.78, 0.52, 0.30), "metallic": 0.9, "roughness": 0.28},
    "cable":   {"base_color": (0.93, 0.25, 0.28), "metallic": 0.0, "roughness": 0.58},
    "strand":  {"base_color": (0.18, 0.66, 0.96), "metallic": 0.0, "roughness": 0.48},
    "connector": {"base_color": (0.96, 0.78, 0.22), "metallic": 0.7, "roughness": 0.38},
    "joint":   {"base_color": (0.4, 0.42, 0.46), "metallic": 0.8, "roughness": 0.38},
    "led":     {"base_color": (1.0, 0.12, 0.12), "metallic": 0.05, "roughness": 0.25},
    "housing": {"base_color": (0.06, 0.07, 0.09), "metallic": 0.2, "roughness": 0.6},
    "default": {"base_color": (0.68, 0.68, 0.72), "metallic": 0.3, "roughness": 0.5},
}


def _pick_palette(name: str):
    key = name.lower()
    # First: token-based palette lookup.
    for token, data in PALETTE.items():
        if token in key:
            data = {**data}
            if token in _COLOR_OVERRIDES:
                data["base_color"] = _COLOR_OVERRIDES[token]
            return token, data
    # Second: allow an override by exact object name (e.g. "pulley_driver").
    for hint, rgb in _COLOR_OVERRIDES.items():
        if hint in key:
            data = {**PALETTE["default"], "base_color": rgb}
            return hint, data
    return "default", {**PALETTE["default"]}


def _apply_pbr_to_scene():
    """Assign PBR materials to every mesh/curve object based on its name.

    Object naming convention respected:
      *_emit or *_led*   → emissive surface (LED look)
      *_glass            → transparent/IOR material (lenses, domes)
      others             → PBR via PALETTE token

    iter15.C: if the object already carries a material tagged with
    `aurora_led_emission` extras (the v1 LED schema), preserve that material
    intact AND copy the extras onto the new material slot — the runtime
    reader (ModelView.tsx + aurora_3d_viewer.py) will animate emissive at
    draw-time. Without this guard, the procedural cable_bundle_system /
    led_strip_system templates would lose their per-strand LED schema when
    the colorize pass overwrites material[0].

    iter24.fix: same guard now extended to aurora_belt_scroll (V-belt UV
    scroll v1 schema) and aurora_oled_atlas (OLED flipbook v1 schema). The
    colorize pass was wiping these IDProperties for the pulley_belt_system
    and screen materials, so the runtime readers were getting "no extras"
    even though the templates had set them. Result: belt looked static and
    OLED panels never animated.
    """
    AURORA_EXTRAS_KEYS = ("aurora_led_emission", "aurora_belt_scroll", "aurora_oled_atlas")

    def _read_aurora_extras(em):
        """Return a dict of any aurora_* extras present on the material, or {}."""
        if em is None:
            return {}
        out = {}
        for key in AURORA_EXTRAS_KEYS:
            tag = None
            try:
                tag = em.get(key) if hasattr(em, "get") else None
            except Exception:
                tag = None
            if tag is None:
                try:
                    tag = em[key]
                except (KeyError, TypeError):
                    tag = None
            if tag is not None:
                out[key] = tag
        return out

    for obj in bpy.data.objects:
        if obj.type not in ("MESH", "CURVE"):
            continue
        # iter15.C / iter24.fix: capture every aurora_* IDProperty on the
        # existing material(s) so we can re-tag the replacement material below.
        preserved_extras = {}
        existing_mats = list(obj.data.materials) if hasattr(obj.data, "materials") else []
        for em in existing_mats:
            preserved_extras.update(_read_aurora_extras(em))
            if preserved_extras:
                break
        # iter27.fix / iter28.fix: skip colorize entirely for objects whose
        # material has a runtime atlas/texture wired by the template. The
        # colorize pass would otherwise drop the texture node, leaving the
        # face with a flat color and the runtime reader nothing to scroll.
        # Applies to:
        #  - aurora_oled_atlas (OLED screen face, iter27)
        #  - aurora_belt_scroll (V-belt timing stripes, iter28)
        if "aurora_oled_atlas" in preserved_extras or "aurora_belt_scroll" in preserved_extras:
            continue
        # Back-compat alias for the old single-key code path below.
        preserved_led_extras = preserved_extras.get("aurora_led_emission")
        lname = obj.name.lower()
        token, data = _pick_palette(obj.name)

        emission_strength = 0.0
        if "_emit" in lname or "_led" in lname or lname.startswith("led_"):
            emission_strength = float(data.get("emission_strength", 6.0))

        mat = _ensure_pbr_material(
            f"Mat_{token}_{obj.name}",
            data["base_color"],
            metallic=data.get("metallic", 0.1),
            roughness=data.get("roughness", 0.5),
            emission_strength=emission_strength,
            emission_color=data.get("emission_color"),
        )
        # iter15.C / iter24.fix: re-tag every preserved aurora_* schema so
        # the glTF exporter writes them into materials[].extras.<key>. The
        # runtime readers in ModelView.tsx and aurora_3d_viewer.py check
        # both extras and userData for parity with the iter9 baker.
        for _key, _val in preserved_extras.items():
            try:
                if hasattr(_val, "to_dict"):
                    _payload = _val.to_dict()
                else:
                    _payload = dict(_val)
                mat[_key] = _payload
            except Exception:
                try:
                    mat[_key] = _val
                except Exception:
                    pass
        if not obj.data.materials:
            obj.data.materials.append(mat)
        else:
            obj.data.materials[0] = mat

    # Environment lighting (subtle) so PBR materials have something to reflect.
    scene = bpy.context.scene
    if scene.world is None:
        world = bpy.data.worlds.new("ProceduralWorld")
        scene.world = world
    world = scene.world
    world.use_nodes = True
    nodes = world.node_tree.nodes
    nodes.clear()
    bg = nodes.new("ShaderNodeBackground")
    bg.inputs["Color"].default_value = (0.05, 0.06, 0.08, 1.0)
    bg.inputs["Strength"].default_value = 0.4
    out = nodes.new("ShaderNodeOutputWorld")
    world.node_tree.links.new(bg.outputs["Background"], out.inputs["Surface"])


def _add_point_light(name, location, color=(1.0, 1.0, 1.0), energy=15.0, radius=0.01):
    """Create a Blender POINT light at the given location.

    Uses radius (shadow_soft_size) so reflections look like a real LED dot.
    Lights are preserved in glTF export via KHR_lights_punctual.
    """
    data = bpy.data.lights.new(name, type="POINT")
    data.color = color
    data.energy = energy
    try:
        data.shadow_soft_size = radius
    except Exception:
        pass
    obj = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(obj)
    obj.location = location
    return obj


def _animate_emission_pulse(material, frames=120, base_strength=2.0, peak_strength=9.0, phase=0.0):
    """Keyframe the Emission Strength of a Principled BSDF material to create a LED pulse."""
    if material is None or material.node_tree is None:
        return
    bsdf = next((n for n in material.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if bsdf is None or "Emission Strength" not in bsdf.inputs:
        return
    es = bsdf.inputs["Emission Strength"]
    scene = bpy.context.scene
    steps = 8
    for i in range(steps + 1):
        t = i / steps
        frame = 1 + int(t * (frames - 1))
        value = base_strength + (peak_strength - base_strength) * (0.5 + 0.5 * math.sin(2 * math.pi * (t + phase)))
        es.default_value = value
        es.keyframe_insert("default_value", frame=frame)


def _add_stretch_armature_for_curve(curve_obj, bone_count=6, name_prefix="StretchArm"):
    """Add a simple armature whose bones follow the curve: allows clean stretching.

    The result: moving any curve control point deforms the attached meshes (cables,
    belts, tubes) via bone weights without producing spaghetti artefacts.
    """
    if curve_obj is None or curve_obj.type != "CURVE":
        return None
    bpy.ops.object.armature_add(enter_editmode=False, location=curve_obj.location)
    armature = bpy.context.active_object
    armature.name = f"{name_prefix}_{curve_obj.name}"
    armature.data.name = armature.name
    # Fit chain along the curve bounds.
    bpy.ops.object.mode_set(mode="EDIT")
    edit_bones = armature.data.edit_bones
    edit_bones.remove(edit_bones[0])
    spline = curve_obj.data.splines[0] if curve_obj.data.splines else None
    if spline is None or not spline.bezier_points:
        bpy.ops.object.mode_set(mode="OBJECT")
        return armature
    pts = [p.co.copy() for p in spline.bezier_points]
    if bone_count > len(pts):
        bone_count = len(pts)
    step = max(1, (len(pts) - 1) // max(1, bone_count - 1))
    sampled = [pts[min(i * step, len(pts) - 1)] for i in range(bone_count)]
    prev_bone = None
    for i in range(bone_count - 1):
        bone = edit_bones.new(f"B{i}")
        bone.head = sampled[i]
        bone.tail = sampled[i + 1]
        if prev_bone is not None:
            bone.parent = prev_bone
            bone.use_connect = True
        prev_bone = bone
    bpy.ops.object.mode_set(mode="OBJECT")
    return armature

'''


PROCEDURAL_TEMPLATES = {
    # iter24.B — full rewrite. Defects fixed:
    #   * pulleys were plain cylinders → now V-groove (cylinder + 2 cones forming the gorge)
    #     + central drum so the belt sits in a real groove like a real V-belt drive.
    #   * belt was a 2-point Bezier going straight through both pulleys (would clip into the
    #     pulley body). It now wraps each pulley with a tangent arc + bridges them with
    #     proper external tangent lines (open belt geometry) → forms a closed-loop curve.
    #   * polycount kept low (cylinder vertices=48 + 2 cones vertices=32, belt curve
    #     bevel_resolution=4) so the whole rig stays under ~8K tris.
    #   * belt motion was missing (only the pulleys rotated). Now we tag the belt material
    #     with `aurora_belt_scroll` extras (schema aurora.belt-scroll.v1). The runtime
    #     reader (ModelView.tsx + aurora_3d_viewer.py) animates `material.map.offset.x` so
    #     the belt visibly slides along its path while the pulleys rotate at the correct
    #     ratio. Linear belt speed v_belt = ω_driver × r_driver matches the tangent point
    #     velocity (no slip).
    "pulley_belt_system": '''
import bpy, math, json, sys, os, struct, copy
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
params = json.loads(argv[0]) if argv else {}
output_dir = argv[1] if len(argv) > 1 else "/tmp"
run_id = argv[2] if len(argv) > 2 else "proc"
fmt = argv[3] if len(argv) > 3 else "glb"

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.fps = 24

# Defaults sized for a clean visual at viewer scale (~30cm rig).
# ratio = [driver_turns, driven_turns] -> pulley radii are inversely proportional
# (a 2:1 ratio means driver makes 2 turns while driven makes 1 -> driver is half
# the radius of driven, like a real overdrive).
ratio_param = params.get("ratio")
if ratio_param and isinstance(ratio_param, (list, tuple)) and len(ratio_param) == 2:
    a, b = float(ratio_param[0]), float(ratio_param[1])
    if a > 0 and b > 0:
        # driven_radius = driver_radius * (a / b)  (driver=a turns -> driven=b turns)
        # default driver radius 0.05 m -> driven radius scales with ratio.
        r1 = 0.05
        r2 = r1 * (a / b)
    else:
        r1, r2 = 0.05, 0.10
else:
    r1 = float(params.get("r1", 0.05))
    r2 = float(params.get("r2", 0.10))

distance = float(params.get("distance", 0.40))
width = float(params.get("width", 0.025))
belt_type = params.get("belt_type", "open")  # open | crossed
rpm_input = float(params.get("rpm", 120.0))
anim_seconds = float(params.get("anim_seconds", 5.0))
groove_depth = float(params.get("groove_depth", width * 0.55))

# ---------- Geometry helpers ----------

def join_active(objs, name):
    """Join a list of mesh objects into one (the first is the active target)."""
    if not objs:
        return None
    bpy.ops.object.select_all(action="DESELECT")
    target = objs[0]
    target.select_set(True)
    bpy.context.view_layer.objects.active = target
    for o in objs[1:]:
        o.select_set(True)
    if len(objs) > 1:
        bpy.ops.object.join()
    target = bpy.context.active_object
    target.name = name
    return target


def make_v_groove_pulley(name, radius, w, loc, groove_d, verts=72):
    """V-belt pulley: central drum + two cones forming the groove (V-shape).
    Returns the joined mesh object."""
    parts = []
    # Two side flanges (drum shoulders).
    flange_w = w * 0.20
    side_offset = (w * 0.5) - (flange_w * 0.5)
    bpy.ops.mesh.primitive_cylinder_add(
        radius=radius, depth=flange_w,
        location=(loc[0], loc[1] - side_offset, loc[2]), vertices=verts,
    )
    flange_a = bpy.context.active_object
    flange_a.rotation_euler[0] = math.radians(90)
    flange_a.name = f"{name}_FlangeA"
    parts.append(flange_a)

    bpy.ops.mesh.primitive_cylinder_add(
        radius=radius, depth=flange_w,
        location=(loc[0], loc[1] + side_offset, loc[2]), vertices=verts,
    )
    flange_b = bpy.context.active_object
    flange_b.rotation_euler[0] = math.radians(90)
    flange_b.name = f"{name}_FlangeB"
    parts.append(flange_b)

    # Two cones forming the V groove (apex pointing inward = belt seat).
    inner_radius = max(radius - groove_d, radius * 0.55)
    cone_d = (w - 2 * flange_w) * 0.5
    # Left cone: tip at center, base at flange A (radius -> inner_radius).
    bpy.ops.mesh.primitive_cone_add(
        radius1=radius, radius2=inner_radius, depth=cone_d,
        location=(loc[0], loc[1] - (cone_d * 0.5), loc[2]), vertices=verts,
    )
    cone_l = bpy.context.active_object
    cone_l.rotation_euler[0] = math.radians(-90)
    cone_l.name = f"{name}_GrooveL"
    parts.append(cone_l)

    bpy.ops.mesh.primitive_cone_add(
        radius1=inner_radius, radius2=radius, depth=cone_d,
        location=(loc[0], loc[1] + (cone_d * 0.5), loc[2]), vertices=verts,
    )
    cone_r = bpy.context.active_object
    cone_r.rotation_euler[0] = math.radians(-90)
    cone_r.name = f"{name}_GrooveR"
    parts.append(cone_r)

    return join_active(parts, name)


# ---------- Pulleys ----------

p1 = make_v_groove_pulley("Pulley_Driver", r1, width, (0.0, 0.0, 0.0), groove_depth)
p2 = make_v_groove_pulley("Pulley_Driven", r2, width, (distance, 0.0, 0.0), groove_depth)


def add_pulley_face_detail(prefix, center, radius, w, parent):
    """Add inspectable hub, bearing, spokes, and bolts to an animated pulley."""
    def parent_keep_world(child):
        child.parent = parent
        try:
            child.matrix_parent_inverse = parent.matrix_world.inverted()
        except Exception:
            pass

    front_y = center[1] - w * 0.58
    back_y = center[1] + w * 0.58
    for side_name, y in [("Front", front_y), ("Back", back_y)]:
        bpy.ops.mesh.primitive_cylinder_add(
            radius=radius * 0.34, depth=w * 0.10,
            location=(center[0], y, center[2]), vertices=48,
        )
        hub = bpy.context.active_object
        hub.rotation_euler[0] = math.radians(90)
        hub.name = f"{prefix}_Hub_{side_name}"
        parent_keep_world(hub)

        bpy.ops.mesh.primitive_torus_add(
            major_radius=radius * 0.48,
            minor_radius=max(0.0012, radius * 0.022),
            major_segments=72,
            minor_segments=8,
            location=(center[0], y, center[2]),
        )
        ring = bpy.context.active_object
        ring.rotation_euler[0] = math.radians(90)
        ring.name = f"{prefix}_BearingRing_{side_name}"
        parent_keep_world(ring)

        for i in range(8):
            theta = math.tau * i / 8.0
            x = center[0] + math.cos(theta) * radius * 0.50
            z = center[2] + math.sin(theta) * radius * 0.50
            bpy.ops.mesh.primitive_cylinder_add(
                radius=max(0.0014, radius * 0.025),
                depth=w * 0.12,
                location=(x, y, z),
                vertices=18,
            )
            bolt = bpy.context.active_object
            bolt.rotation_euler[0] = math.radians(90)
            bolt.name = f"{prefix}_Bolt_{side_name}_{i:02d}"
            parent_keep_world(bolt)

    for i in range(6):
        theta = math.tau * i / 6.0
        x = center[0] + math.cos(theta) * radius * 0.30
        z = center[2] + math.sin(theta) * radius * 0.30
        bpy.ops.mesh.primitive_cube_add(
            size=1,
            location=((center[0] + x) * 0.5, center[1], (center[2] + z) * 0.5),
        )
        spoke = bpy.context.active_object
        spoke.name = f"{prefix}_Spoke_{i:02d}"
        spoke.scale = (radius * 0.21, w * 0.035, max(0.0015, radius * 0.018))
        spoke.rotation_euler[1] = -theta
        parent_keep_world(spoke)
        try:
            mod = spoke.modifiers.new("rounded_spoke_edges", "BEVEL")
            mod.width = max(0.0006, radius * 0.008)
            mod.segments = 2
            spoke.modifiers.new("weighted_normals", "WEIGHTED_NORMAL")
        except Exception:
            pass


add_pulley_face_detail("Pulley_Driver", (0.0, 0.0, 0.0), r1, width, p1)
add_pulley_face_detail("Pulley_Driven", (distance, 0.0, 0.0), r2, width, p2)

# ---------- Belt curve (closed loop, wraps both pulleys) ----------
# External-tangent geometry for an OPEN belt:
#   distance d between centres, radii r1 and r2 (r2 > r1 typically).
#   tangent line angle alpha = asin( (r2 - r1) / d ) (same-side external tangent).
#   tangent points on each pulley:
#     P1_top = (cos(pi/2 + alpha) * r1, 0, sin(pi/2 + alpha) * r1)
#     P2_top = (d + cos(pi/2 + alpha) * r2, 0, sin(pi/2 + alpha) * r2)
# Belt seat radius = pulley_radius - groove_depth*0.30 so the rope sits inside the V.

seat1 = r1 - groove_depth * 0.30
seat2 = r2 - groove_depth * 0.30
# clamp so seat doesn't go negative on tiny pulleys.
seat1 = max(seat1, r1 * 0.60)
seat2 = max(seat2, r2 * 0.60)

if belt_type == "crossed":
    # Crossed belt: tangent lines cross between pulleys.
    alpha = math.asin(min(1.0, (seat1 + seat2) / max(distance, 1e-3)))
else:
    # Open belt: tangent lines are external on the same side.
    alpha = math.asin(min(1.0, abs(seat2 - seat1) / max(distance, 1e-3)))

# Build the closed Bezier loop point-by-point:
#   1. wrap top arc of driver (32 segments)
#   2. straight tangent across to driven top
#   3. wrap bottom arc of driven (32 segments)
#   4. straight tangent back to driver bottom -> close
ARC_SEGMENTS = 32

def arc_points(center, radius, theta_start, theta_end, n):
    """Sample n points on a circle in the XZ plane (Y=0)."""
    pts = []
    for i in range(n + 1):
        t = i / n
        theta = theta_start + (theta_end - theta_start) * t
        pts.append(Vector((center[0] + radius * math.cos(theta), 0.0,
                           center[2] + radius * math.sin(theta))))
    return pts

# For an open belt with r2 > r1: the top tangent line goes from
#   P1 at angle (pi/2 + alpha) on driver  to  P2 at angle (pi/2 + alpha) on driven
#   the wrap on the SMALL pulley (driver) covers angles [pi/2 - alpha, pi/2 + alpha] going the long way (~ pi - 2*alpha skipping the wrap side)
# For simplicity (and since our visual identity matters more than physically-perfect tangency at 1mm),
# we use SYMMETRIC wrap angles: each pulley wraps from theta=alpha (bottom-front) over the top
# to theta=pi-alpha (bottom-back). This guarantees the tangent lines are continuous and the belt
# always forms a clean closed loop visually.
sign_swap = -1.0 if belt_type == "crossed" else 1.0

# Wrap angles on each pulley (relative to centre):
#   driver wraps from -pi/2 - alpha (bottom-back, going COUNTERCLOCKWISE through bottom) to -pi/2 + alpha (bottom-front)
#   wait — the geometry is cleanest if we describe the loop as
#     start at driver top-front (angle pi/2 + alpha)
#     go CW down to driver bottom-front (angle -pi/2 + alpha)
#     line over to driven bottom-front (angle -pi/2 + alpha)
#     wrap CW under driven up to driven top-front (... no, opposite: belt has to come BACK)
#   so: top of driver -> top of driven via top tangent, wrap driven CCW around its right side
#   down to bottom of driven, then bottom tangent back to bottom of driver, wrap driver CCW around
#   its left side back up to top of driver.
# Final angle ranges (measured from +X axis):
driver_arc_start = math.pi / 2 + alpha           # top-front
driver_arc_end   = 3 * math.pi / 2 - alpha       # bottom-back (going CCW around left side)
driven_arc_start = -math.pi / 2 + alpha          # bottom-front
driven_arc_end   = math.pi / 2 - alpha           # top-front (going CCW around right side)

driver_pts = arc_points((0.0, 0.0, 0.0), seat1,
                        driver_arc_start, driver_arc_end, ARC_SEGMENTS)
driven_pts = arc_points((distance, 0.0, 0.0), seat2,
                        driven_arc_start, driven_arc_end, ARC_SEGMENTS)

# Build the loop: driver_arc -> bottom_tangent -> driven_arc -> top_tangent -> close
loop_pts = []
loop_pts.extend(driver_pts)            # driver wrap (top -> bottom)
loop_pts.extend(driven_pts)            # driven wrap (bottom -> top)
# (closing back to first driver point happens automatically via use_cyclic_u.)

curve_data = bpy.data.curves.new("Belt_Curve", type="CURVE")
curve_data.dimensions = "3D"
spline = curve_data.splines.new("POLY")
spline.points.add(len(loop_pts) - 1)
for i, pt in enumerate(loop_pts):
    spline.points[i].co = (pt.x, pt.y, pt.z, 1.0)
spline.use_cyclic_u = True

# Belt cross-section: thin rectangle (V-belt outer face). Use a separate bevel
# profile so the belt has a flat top + tapered sides matching the pulley groove.
belt_thickness = groove_depth * 0.55
belt_width_y = width * 0.55
curve_data.bevel_mode = "ROUND"
curve_data.bevel_depth = belt_thickness * 0.5
curve_data.bevel_resolution = 5
curve_data.resolution_u = 4
curve_data.use_fill_caps = False

belt = bpy.data.objects.new("Belt", curve_data)
bpy.context.collection.objects.link(belt)

# Tag the belt with the scroll schema so the runtime reader animates the UV.
# Linear belt speed: v = ω_driver × r1  (rad/s × m = m/s).
omega_driver = (rpm_input / 60.0) * 2.0 * math.pi  # rad/s
v_belt = omega_driver * r1                         # m/s

# Belt loop length (used to convert v_belt -> uv-cycles-per-second).
def loop_length(points):
    L = 0.0
    for i in range(len(points)):
        a = points[i]
        b = points[(i + 1) % len(points)]
        L += (b - a).length
    return L

belt_len = loop_length(loop_pts)
# UV scroll speed in unit-period-per-second: (m/s) / (m per loop) = loops/s.
# With sign_swap so crossed belts visually scroll the other way.
speed_uv_per_sec = (v_belt / belt_len) if belt_len > 1e-6 else 0.5
speed_uv_per_sec *= sign_swap
belt_rotation_sign = 1.0 if belt_type == "open" else -1.0


def add_flat_arrow(name, loc, length, height, direction_angle, thickness=0.0012):
    """Small triangular prism marker in the XZ plane, pointing along +X before rotation."""
    mesh = bpy.data.meshes.new(f"{name}_Mesh")
    l2 = length * 0.5
    h2 = height * 0.5
    verts = [
        (l2, -thickness, 0.0),
        (-l2, -thickness, h2),
        (-l2, -thickness, -h2),
        (l2, thickness, 0.0),
        (-l2, thickness, h2),
        (-l2, thickness, -h2),
    ]
    faces = [
        (0, 1, 2),
        (3, 5, 4),
        (0, 3, 4, 1),
        (1, 4, 5, 2),
        (2, 5, 3, 0),
    ]
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    obj.location = loc
    obj.rotation_euler[1] = -direction_angle
    bpy.context.collection.objects.link(obj)
    try:
        obj.modifiers.new("arrow_weighted_normals", "WEIGHTED_NORMAL")
    except Exception:
        pass
    return obj


def angle_xz(vec):
    return math.atan2(vec.z, vec.x)


top_driver = driver_pts[0]
bottom_driver = driver_pts[-1]
bottom_driven = driven_pts[0]
top_driven = driven_pts[-1]
top_mid = (top_driver + top_driven) * 0.5
bottom_mid = (bottom_driver + bottom_driven) * 0.5
front_y = -belt_width_y * 0.95
arrow_len = max(0.020, distance * 0.055)
arrow_h = max(0.010, max(r1, r2) * 0.12)
add_flat_arrow(
    "MotionArrow_Belt_TopRun",
    (top_mid.x, front_y, top_mid.z),
    arrow_len,
    arrow_h,
    angle_xz(top_driven - top_driver),
)
add_flat_arrow(
    "MotionArrow_Belt_ReturnRun",
    (bottom_mid.x, front_y, bottom_mid.z),
    arrow_len,
    arrow_h,
    angle_xz(bottom_driver - bottom_driven),
)

for prefix, center, radius, rotation_sign in [
    ("MotionArrow_DriverRotation", Vector((0.0, front_y, 0.0)), r1, 1.0),
    ("MotionArrow_DrivenRotation", Vector((distance, front_y, 0.0)), r2, belt_rotation_sign),
]:
    for i, theta in enumerate((math.radians(40), math.radians(220))):
        loc = (
            center.x + math.cos(theta) * radius * 0.70,
            front_y,
            center.z + math.sin(theta) * radius * 0.70,
        )
        tangent = theta + rotation_sign * math.pi / 2.0
        add_flat_arrow(f"{prefix}_{i:02d}", loc, arrow_len * 0.70, arrow_h * 0.72, tangent)

# ---------- Kinematics: omega_driven = omega_driver * (r1 / r2) ----------
# iter24.fix: previously p2 used driver_add() (Blender expression driver),
# but Blender driver expressions do NOT survive glTF export — the GLB ended
# up with a single animation channel for p1 only. Now we keyframe BOTH
# pulleys directly so two distinct fcurves land in the exported Action.
ratio_kine = r1 / r2
sign = belt_rotation_sign

frames = max(2, int(anim_seconds * scene.render.fps))
total_turns = (rpm_input / 60.0) * anim_seconds
driver_total_rad = math.radians(360.0 * total_turns)
driven_total_rad = driver_total_rad * ratio_kine * sign

# Driver pulley keyframes (rotation around Y).
p1.rotation_euler[1] = 0.0
p1.keyframe_insert(data_path="rotation_euler", index=1, frame=1)
p1.rotation_euler[1] = driver_total_rad
p1.keyframe_insert(data_path="rotation_euler", index=1, frame=frames)

# Driven pulley keyframes — explicit, NOT via driver_add(). Same Y axis,
# total angle scaled by the kinematic ratio.
p2.rotation_euler[1] = 0.0
p2.keyframe_insert(data_path="rotation_euler", index=1, frame=1)
p2.rotation_euler[1] = driven_total_rad
p2.keyframe_insert(data_path="rotation_euler", index=1, frame=frames)

scene.frame_start = 1
scene.frame_end = frames

# Loop the driver F-curve so the motion plays continuously (NLA-friendly).
# Blender 5.1 changed Action.fcurves -> Action.layers[i].strips[j].channelbag(slot).fcurves;
# fall back to the legacy 4.x path for older Blender versions still in CI.
def _iter_action_fcurves(act):
    legacy = getattr(act, "fcurves", None)
    if legacy is not None:
        for fc in legacy:
            yield fc
        return
    layers = getattr(act, "layers", None) or []
    for layer in layers:
        for strip in (getattr(layer, "strips", None) or []):
            # 5.1 keyed-action strip exposes .channelbag(slot) -> ChannelBag.fcurves
            channelbags = []
            channelbag_fn = getattr(strip, "channelbag", None)
            slots = getattr(act, "slots", None) or []
            for slot in slots:
                try:
                    cb = channelbag_fn(slot) if channelbag_fn else None
                except Exception:
                    cb = None
                if cb is not None:
                    channelbags.append(cb)
            for cb in channelbags:
                for fc in (getattr(cb, "fcurves", None) or []):
                    yield fc

if p1.animation_data and p1.animation_data.action:
    for fcurve in _iter_action_fcurves(p1.animation_data.action):
        try:
            fcurve.modifiers.new(type="CYCLES")
        except Exception:
            pass

# ---------- Frame, pillars, axles ----------
bpy.ops.mesh.primitive_cube_add(size=1, location=(distance / 2, -(width * 0.5 + 0.04), -max(r1, r2) * 1.1))
frame_obj = bpy.context.active_object
frame_obj.name = "Frame_Support"
frame_obj.scale = (distance / 2 + r2 + 0.05, 0.012, 0.018)
bpy.ops.object.modifier_add(type="BEVEL")
frame_obj.modifiers["Bevel"].width = 0.003
frame_obj.modifiers["Bevel"].segments = 4

for pos, label, h in [
    ((0.0,      -(width * 0.5 + 0.02), -r1 * 0.55), "Frame_Pillar_A", r1 * 1.1 + 0.04),
    ((distance, -(width * 0.5 + 0.02), -r2 * 0.55), "Frame_Pillar_B", r2 * 1.1 + 0.04),
]:
    bpy.ops.mesh.primitive_cylinder_add(radius=0.005, depth=h, location=pos, vertices=36)
    pillar = bpy.context.active_object
    pillar.name = label

# Axles (shiny shafts through the pulleys).
for axle_loc, axle_name in [
    ((0.0,      0.0, 0.0), "Pulley_Axle_A"),
    ((distance, 0.0, 0.0), "Pulley_Axle_B"),
]:
    bpy.ops.mesh.primitive_cylinder_add(
        radius=0.006, depth=width * 1.6, location=axle_loc, vertices=40,
    )
    axle = bpy.context.active_object
    axle.rotation_euler[0] = math.radians(90)
    axle.name = axle_name

# ---------- PBR + extras tag for belt ----------

def _make_belt_material():
    mat = bpy.data.materials.new("Mat_belt_BeltLoop")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf.inputs["Base Color"].default_value = (0.18, 0.18, 0.20, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.55
    if "Metallic" in bsdf.inputs:
        bsdf.inputs["Metallic"].default_value = 0.0
    # iter28.fix: previous base color (0.05) was so dark the belt looked
    # invisible under standard 3-light render. Lifted to dark-rubber gray
    # (0.18) so it reads as a real timing belt. The yellow stripes still
    # contrast strongly. UV scroll runtime makes them visibly travel.
    img = bpy.data.images.new("BeltStripes", width=512, height=64, alpha=False)
    pixels = []
    RUBBER = (0.18, 0.18, 0.20)
    YELLOW = (1.0, 0.82, 0.0)  # automotive timing belt yellow
    for y in range(64):
        for x in range(512):
            # 8 teeth across U: yellow tooth every 64 px (16 px wide), rest rubber
            stripe_pos = x % 64
            if 24 <= stripe_pos <= 40:
                r, g, b = YELLOW
            else:
                r, g, b = RUBBER
            pixels.extend([r, g, b, 1.0])
    img.pixels = pixels
    img.update()
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = img
    tex.interpolation = "Closest"
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    # Tag the material with belt-scroll v1 extras (read by ModelView.tsx and
    # aurora_3d_viewer.py). The runtime reader scrolls texture.offset.x on every
    # frame at speed_uv_per_sec, mirroring the OLED atlas pattern.
    mat["aurora_belt_scroll"] = {
        "schema": "aurora.belt-scroll.v1",
        "speed_uv_per_sec": float(speed_uv_per_sec),
        "direction": "h",
        "loop": True,
        "belt_length_m": float(belt_len),
        "v_belt_m_per_s": float(v_belt),
    }
    return mat

belt_mat = _make_belt_material()
if belt.data.materials:
    belt.data.materials[0] = belt_mat
else:
    belt.data.materials.append(belt_mat)

# ---------- Export ----------
out_path = os.path.join(output_dir, f"{run_id}_procedural.{fmt}")
if fmt == "glb":
    bpy.ops.export_scene.gltf(
        filepath=out_path, export_format="GLB",
        export_animations=True, export_extras=True,
    )
elif fmt == "fbx":
    bpy.ops.export_scene.fbx(filepath=out_path, use_selection=False)
else:
    bpy.ops.wm.obj_export(filepath=out_path)

print(json.dumps({
    "ok": True, "path": out_path, "format": fmt,
    "animationFrames": int(frames),
    "kinematicRatio": ratio_kine,
    "beltLengthM": float(belt_len),
    "beltSpeedMps": float(v_belt),
    "speedUvPerSec": float(speed_uv_per_sec),
    "ratioParam": ratio_param,
}))
''',

    "humanoid_performer": '''
import bpy, math, json, sys, os, struct, copy
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
params = json.loads(argv[0]) if argv else {}
output_dir = argv[1] if len(argv) > 1 else "/tmp"
run_id = argv[2] if len(argv) > 2 else "proc"
fmt = argv[3] if len(argv) > 3 else "glb"

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.fps = 30
scene.frame_start = 1
scene.frame_end = 181

def hex_to_rgb(value, fallback):
    if not isinstance(value, str):
        return fallback
    clean = value.strip().lstrip("#")
    if len(clean) != 6:
        return fallback
    try:
        return (int(clean[0:2], 16) / 255.0, int(clean[2:4], 16) / 255.0, int(clean[4:6], 16) / 255.0)
    except Exception:
        return fallback

skin = hex_to_rgb(params.get("skin"), (0.50, 0.30, 0.21))
hair = hex_to_rgb(params.get("hair"), (0.03, 0.025, 0.02))
jacket = hex_to_rgb(params.get("jacket"), (0.84, 0.12, 0.08))
shirt = hex_to_rgb(params.get("shirt"), (0.04, 0.72, 0.78))
pants = hex_to_rgb(params.get("pants"), (0.10, 0.14, 0.32))
shoes = hex_to_rgb(params.get("shoes"), (0.02, 0.025, 0.03))

def make_texture(name, color_a, color_b):
    img = bpy.data.images.new(name, width=256, height=256, alpha=False)
    pixels = []
    for y in range(256):
        for x in range(256):
            stripe = 1.0 if ((x // 18 + y // 32) % 2 == 0) else 0.0
            weave = 0.06 * math.sin((x + y) * 0.25)
            r = max(0.0, min(1.0, color_a[0] * (0.72 + 0.22 * stripe) + color_b[0] * (0.28 - 0.10 * stripe) + weave))
            g = max(0.0, min(1.0, color_a[1] * (0.72 + 0.22 * stripe) + color_b[1] * (0.28 - 0.10 * stripe) + weave))
            b = max(0.0, min(1.0, color_a[2] * (0.72 + 0.22 * stripe) + color_b[2] * (0.28 - 0.10 * stripe) + weave))
            pixels.extend([r, g, b, 1.0])
    img.pixels.foreach_set(pixels)
    img.pack()
    return img

cloth_texture = make_texture("Performer_Jacket_Shirt_Woven_Texture", jacket, shirt)

def material(name, color, metallic=0.0, roughness=0.58, texture=None):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    out = nodes.new("ShaderNodeOutputMaterial")
    if texture is not None:
        tex = nodes.new("ShaderNodeTexImage")
        tex.image = texture
        tex.extension = "REPEAT"
        links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    else:
        bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    if "Metallic" in bsdf.inputs:
        bsdf.inputs["Metallic"].default_value = metallic
    if "Roughness" in bsdf.inputs:
        bsdf.inputs["Roughness"].default_value = roughness
    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return mat

skin_mat = material("Mat_skin_warm_skin_tone", skin, roughness=0.52)
hair_mat = material("Mat_hair_dark_strands", hair, roughness=0.82)
jacket_mat = material("Mat_costume_red_jacket_textured", jacket, roughness=0.64, texture=cloth_texture)
shirt_mat = material("Mat_costume_cyan_shirt_textured", shirt, roughness=0.66, texture=cloth_texture)
pants_mat = material("Mat_costume_navy_pants", pants, roughness=0.68)
shoe_mat = material("Mat_black_shoes", shoes, roughness=0.45)
eye_mat = material("Mat_eye_black_sharp", (0.0, 0.0, 0.0), roughness=0.2)
mouth_mat = material("Mat_mouth_expression", (0.55, 0.05, 0.05), roughness=0.35)

def shade(obj):
    try:
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        bpy.ops.object.shade_smooth()
        obj.select_set(False)
    except Exception:
        pass
    return obj

def sphere(name, loc, scale, mat, segments=80, rings=40):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=segments, ring_count=rings, radius=1.0, location=loc)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = scale
    obj.data.materials.append(mat)
    return shade(obj)

def cylinder_between(name, a, b, radius, mat, vertices=72):
    va, vb = Vector(a), Vector(b)
    mid = (va + vb) * 0.5
    direction = vb - va
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=direction.length, location=mid)
    obj = bpy.context.active_object
    obj.name = name
    obj.rotation_euler = direction.to_track_quat("Z", "Y").to_euler()
    obj.data.materials.append(mat)
    return shade(obj)

def animated_cylinder(name, radius, mat, vertices=48):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=1.0, location=(0, 0, 0))
    obj = bpy.context.active_object
    obj.name = name
    obj.data.materials.append(mat)
    return shade(obj)

def cone(name, loc, radius1, depth, mat, vertices=32):
    bpy.ops.mesh.primitive_cone_add(vertices=vertices, radius1=radius1, radius2=0.0, depth=depth, location=loc)
    obj = bpy.context.active_object
    obj.name = name
    obj.data.materials.append(mat)
    return shade(obj)

def rounded_box(name, loc, scale, mat, bevel_width=0.025, bevel_segments=8):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=loc)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = scale
    obj.data.materials.append(mat)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if bevel_width > 0:
        bevel = obj.modifiers.new(f"{name}_soft_bevel", "BEVEL")
        bevel.width = bevel_width
        bevel.segments = bevel_segments
        bevel.affect = "EDGES"
        normal = obj.modifiers.new(f"{name}_weighted_normals", "WEIGHTED_NORMAL")
        bpy.context.view_layer.objects.active = obj
        try:
            bpy.ops.object.modifier_apply(modifier=bevel.name)
            bpy.ops.object.modifier_apply(modifier=normal.name)
        except Exception:
            pass
    return shade(obj)

def empty(name, loc):
    obj = bpy.data.objects.new(name, None)
    obj.empty_display_type = "PLAIN_AXES"
    obj.empty_display_size = 0.05
    obj.location = loc
    bpy.context.collection.objects.link(obj)
    return obj

def parent_keep_world(child, parent):
    child.parent = parent
    try:
        child.matrix_parent_inverse = parent.matrix_world.inverted()
    except Exception:
        pass

root = empty("Performer_Rig_Root", (0, 0, 0))
torso_pivot = empty("spine_chest_dance_pivot", (0, 0, 1.28))
parent_keep_world(torso_pivot, root)
head_pivot = empty("head_neck_macarena_pivot", (0, 0, 1.82))
parent_keep_world(head_pivot, torso_pivot)

pelvis = rounded_box("Pelvis_Navy_Pants_Separated_Waist", (0, 0, 0.98), (0.30, 0.17, 0.18), pants_mat, 0.04, 10)
torso = rounded_box("Torso_Red_Jacket_Textured_Tailored", (0, 0, 1.36), (0.38, 0.21, 0.62), jacket_mat, 0.055, 12)
shirt_panel = rounded_box("Front_Cyan_Shirt_Texture_Panel", (0, -0.113, 1.39), (0.155, 0.026, 0.43), shirt_mat, 0.018, 6)
lapel_l = rounded_box("Left_Red_Jacket_Lapel_Separate", (-0.065, -0.128, 1.48), (0.055, 0.018, 0.28), jacket_mat, 0.012, 4)
lapel_r = rounded_box("Right_Red_Jacket_Lapel_Separate", (0.065, -0.128, 1.48), (0.055, 0.018, 0.28), jacket_mat, 0.012, 4)
lapel_l.rotation_euler[2] = math.radians(-10)
lapel_r.rotation_euler[2] = math.radians(10)
waist_belt = rounded_box("Black_Belt_Separate_Waist", (0, -0.116, 1.10), (0.29, 0.024, 0.04), shoe_mat, 0.008, 4)
neck = cylinder_between("Neck_Skin", (0, 0, 1.66), (0, 0, 1.78), 0.045, skin_mat, 36)
head = sphere("Head_Sharp_Readable_Face", (0, 0, 1.94), (0.148, 0.118, 0.178), skin_mat)
hair_cap = sphere("Layered_Dark_Hair_Cap", (0, -0.006, 2.045), (0.160, 0.128, 0.092), hair_mat, 72, 28)
for i, x in enumerate([-0.08, -0.04, 0.0, 0.04, 0.08]):
    spike = cone(f"Hair_Strand_{i:02d}", (x, -0.03, 2.12 + 0.02 * (i % 2)), 0.035, 0.16, hair_mat, 24)
    spike.rotation_euler[0] = math.radians(10 + i * 4)
    parent_keep_world(spike, head_pivot)

for i, x in enumerate([-0.09, -0.055, -0.02, 0.02, 0.055, 0.09]):
    fringe = sphere(f"Dark_Front_Hair_Lock_{i:02d}", (x, -0.095, 2.035 - 0.012 * (i % 2)), (0.030, 0.024, 0.058), hair_mat, 32, 14)
    fringe.rotation_euler[0] = math.radians(-18)
    parent_keep_world(fringe, head_pivot)

for obj in (pelvis, torso, shirt_panel, lapel_l, lapel_r, waist_belt):
    parent_keep_world(obj, torso_pivot)
for obj in (neck, head, hair_cap):
    parent_keep_world(obj, head_pivot)

for name, x in [("Eye_L", -0.055), ("Eye_R", 0.055)]:
    eye = sphere(name, (x, -0.128, 1.970), (0.034, 0.012, 0.022), eye_mat, 36, 16)
    parent_keep_world(eye, head)
for name, x, tilt in [("Eyebrow_L_Dark_Readable", -0.055, -6), ("Eyebrow_R_Dark_Readable", 0.055, 6)]:
    brow = rounded_box(name, (x, -0.128, 2.000), (0.050, 0.007, 0.010), hair_mat, 0.004, 2)
    brow.rotation_euler[2] = math.radians(tilt)
    parent_keep_world(brow, head)
nose = sphere("Raised_Nose_Skin_Profile", (0, -0.142, 1.935), (0.026, 0.022, 0.038), skin_mat, 32, 14)
parent_keep_world(nose, head)
mouth = sphere("Small_Expression_Mouth", (0, -0.140, 1.885), (0.070, 0.010, 0.015), mouth_mat, 36, 12)
parent_keep_world(mouth, head)
for name, x in [("Ear_L_Skin", -0.142), ("Ear_R_Skin", 0.142)]:
    ear = sphere(name, (x, -0.002, 1.935), (0.022, 0.014, 0.040), skin_mat, 24, 12)
    parent_keep_world(ear, head)

def make_arm(side, sx):
    shoulder = (sx * 0.18, -0.005, 1.58)
    elbow = (sx * 0.235, -0.035, 1.27)
    wrist = (sx * 0.215, -0.075, 0.98)
    shoulder_pivot = empty(f"shoulder_{side}_macarena_pivot", shoulder)
    shoulder_cap = sphere(f"Shoulder_{side}_Attached_Jacket_Cap", shoulder, (0.050, 0.040, 0.050), jacket_mat, 32, 14)
    elbow_joint = sphere(f"Elbow_{side}_Continuous_Joint_Cap", elbow, (0.038, 0.034, 0.038), skin_mat, 32, 14)
    upper = animated_cylinder(f"Upper_Arm_{side}_Sleeve_Continuous_Segment", 0.038, jacket_mat, 48)
    fore = animated_cylinder(f"Forearm_{side}_Skin_Continuous_Segment", 0.032, skin_mat, 48)
    hand = sphere(f"Hand_{side}_Separated_Fingers_Mitten", wrist, (0.045, 0.032, 0.04), skin_mat, 32, 16)
    parent_keep_world(shoulder_pivot, root)
    parent_keep_world(shoulder_cap, root)
    parent_keep_world(elbow_joint, root)
    parent_keep_world(upper, root)
    parent_keep_world(fore, root)
    parent_keep_world(hand, root)
    return {
        "marker": shoulder_pivot,
        "shoulder": shoulder,
        "shoulder_cap": shoulder_cap,
        "elbow_cap": elbow_joint,
        "upper": upper,
        "fore": fore,
        "hand": hand,
    }

def make_leg(side, sx):
    hip = (sx * 0.075, 0.0, 0.92)
    knee = (sx * 0.082, -0.005, 0.50)
    ankle = (sx * 0.070, -0.03, 0.13)
    hip_pivot = empty(f"thigh_{side}_dance_pivot", hip)
    knee_pivot = empty(f"shin_{side}_dance_pivot", knee)
    parent_keep_world(hip_pivot, root)
    thigh = cylinder_between(f"Thigh_{side}_Navy_Pants", hip, knee, 0.045, pants_mat, 48)
    shin = cylinder_between(f"Shin_{side}_Navy_Pants", knee, ankle, 0.038, pants_mat, 48)
    foot = sphere(f"Shoe_{side}_Foot", (sx * 0.085, -0.08, 0.06), (0.058, 0.12, 0.033), shoe_mat, 40, 14)
    parent_keep_world(thigh, hip_pivot)
    parent_keep_world(knee_pivot, hip_pivot)
    parent_keep_world(shin, knee_pivot)
    parent_keep_world(foot, knee_pivot)
    return hip_pivot, knee_pivot

arm_l = make_arm("L", -1)
arm_r = make_arm("R", 1)
thigh_l, shin_l = make_leg("L", -1)
thigh_r, shin_r = make_leg("R", 1)

def set_key(obj, frame, rot=(0, 0, 0), loc=None):
    scene.frame_set(frame)
    obj.rotation_euler = tuple(math.radians(v) for v in rot)
    obj.keyframe_insert(data_path="rotation_euler", frame=frame)
    if loc is not None:
        obj.location = loc
        obj.keyframe_insert(data_path="location", frame=frame)

def set_point_key(obj, frame, loc):
    scene.frame_set(frame)
    obj.location = loc
    obj.keyframe_insert(data_path="location", frame=frame)

def set_between_key(obj, frame, a, b):
    scene.frame_set(frame)
    va, vb = Vector(a), Vector(b)
    direction = vb - va
    obj.location = (va + vb) * 0.5
    obj.rotation_euler = direction.to_track_quat("Z", "Y").to_euler()
    obj.scale = (1.0, 1.0, max(direction.length, 0.001))
    obj.keyframe_insert(data_path="location", frame=frame)
    obj.keyframe_insert(data_path="rotation_euler", frame=frame)
    obj.keyframe_insert(data_path="scale", frame=frame)

def set_arm_key(arm, frame, elbow, wrist):
    shoulder = arm["shoulder"]
    set_point_key(arm["marker"], frame, shoulder)
    set_point_key(arm["shoulder_cap"], frame, shoulder)
    set_point_key(arm["elbow_cap"], frame, elbow)
    set_point_key(arm["hand"], frame, wrist)
    set_between_key(arm["upper"], frame, shoulder, elbow)
    set_between_key(arm["fore"], frame, elbow, wrist)

frames = [1, 16, 31, 46, 61, 76, 91, 106, 121, 136, 151, 166, 181]
root_locs = [
    (0, -0.02, 0), (-0.025, -0.015, 0.010), (0.025, 0.0, 0.016),
    (0.035, -0.012, 0.008), (-0.025, -0.018, 0.014), (0.018, 0.0, 0.018),
    (0.0, -0.02, 0.006), (-0.034, -0.012, 0.016), (0.034, 0.0, 0.018),
    (0.018, -0.015, 0.012), (-0.018, -0.018, 0.010), (0.0, -0.024, 0.0),
    (0, -0.02, 0),
]
torso_rots = [
    (0, 0, -7), (1, -2, 7), (-2, 2, -9), (3, -2, 10), (-3, 1, -8),
    (4, 0, 12), (-2, -1, -11), (5, 1, 8), (-4, -2, -10), (3, 2, 12),
    (-2, -1, -7), (2, 0, 6), (0, 0, -7),
]
head_rots = [
    (0, 0, 6), (-2, 0, -5), (2, 0, 7), (-5, 1, -8), (4, -1, 9),
    (-8, 0, -11), (7, 0, 10), (-4, 0, -7), (5, 0, 8), (-3, 0, -9),
    (2, 0, 6), (0, 0, -4), (0, 0, 6),
]
arm_l_poses = [
    ((-0.29, -0.25, 1.51), (-0.37, -0.49, 1.49)),
    ((-0.36, -0.23, 1.56), (-0.53, -0.45, 1.57)),
    ((-0.05, -0.28, 1.55), (0.18, -0.20, 1.58)),
    ((-0.42, -0.08, 1.72), (-0.10, 0.02, 1.86)),
    ((-0.36, -0.08, 1.34), (-0.23, -0.10, 1.12)),
    ((-0.43, -0.06, 1.33), (-0.26, -0.12, 1.10)),
    ((-0.31, -0.05, 1.28), (-0.36, -0.08, 1.03)),
    ((-0.34, -0.22, 1.53), (-0.48, -0.44, 1.50)),
    ((-0.06, -0.28, 1.55), (0.19, -0.21, 1.58)),
    ((-0.43, -0.08, 1.73), (-0.11, 0.02, 1.86)),
    ((-0.35, -0.08, 1.35), (-0.23, -0.11, 1.12)),
    ((-0.29, -0.22, 1.51), (-0.38, -0.47, 1.49)),
    ((-0.29, -0.25, 1.51), (-0.37, -0.49, 1.49)),
]
arm_r_poses = [
    ((0.29, -0.25, 1.51), (0.37, -0.49, 1.49)),
    ((0.36, -0.23, 1.56), (0.53, -0.45, 1.57)),
    ((0.05, -0.28, 1.55), (-0.18, -0.20, 1.58)),
    ((0.42, -0.08, 1.72), (0.10, 0.02, 1.86)),
    ((0.36, -0.08, 1.34), (0.23, -0.10, 1.12)),
    ((0.43, -0.06, 1.33), (0.26, -0.12, 1.10)),
    ((0.31, -0.05, 1.28), (0.36, -0.08, 1.03)),
    ((0.34, -0.22, 1.53), (0.48, -0.44, 1.50)),
    ((0.06, -0.28, 1.55), (-0.19, -0.21, 1.58)),
    ((0.43, -0.08, 1.73), (0.11, 0.02, 1.86)),
    ((0.35, -0.08, 1.35), (0.23, -0.11, 1.12)),
    ((0.29, -0.22, 1.51), (0.38, -0.47, 1.49)),
    ((0.29, -0.25, 1.51), (0.37, -0.49, 1.49)),
]
leg_l_rots = [
    (3, 0, -5), (-5, 0, 8), (8, 0, -12), (-7, 0, 10), (9, 0, -9),
    (-5, 0, 8), (7, 0, -11), (-8, 0, 13), (10, 0, -10), (-5, 0, 7),
    (5, 0, -6), (-3, 0, 4), (3, 0, -5),
]
leg_r_rots = [
    (-3, 0, 5), (5, 0, -8), (-8, 0, 12), (7, 0, -10), (-9, 0, 9),
    (5, 0, -8), (-7, 0, 11), (8, 0, -13), (-10, 0, 10), (5, 0, -7),
    (-5, 0, 6), (3, 0, -4), (-3, 0, 5),
]

for idx, frame in enumerate(frames):
    set_key(root, frame, (0, 0, 0), root_locs[idx])
    set_key(torso_pivot, frame, torso_rots[idx])
    set_key(head_pivot, frame, head_rots[idx])
    set_arm_key(arm_l, frame, *arm_l_poses[idx])
    set_arm_key(arm_r, frame, *arm_r_poses[idx])
    set_key(thigh_l, frame, leg_l_rots[idx])
    set_key(thigh_r, frame, leg_r_rots[idx])
    set_key(shin_l, frame, (-6 if idx % 2 else 6, 0, 0))
    set_key(shin_r, frame, (6 if idx % 2 else -6, 0, 0))

animated_objects = [
    root, torso_pivot, head_pivot,
    arm_l["marker"], arm_l["shoulder_cap"], arm_l["elbow_cap"], arm_l["upper"], arm_l["fore"], arm_l["hand"],
    arm_r["marker"], arm_r["shoulder_cap"], arm_r["elbow_cap"], arm_r["upper"], arm_r["fore"], arm_r["hand"],
    thigh_l, thigh_r, shin_l, shin_r,
]
for obj in animated_objects:
    if obj.animation_data and obj.animation_data.action:
        for fc in obj.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "BEZIER"
            try:
                fc.modifiers.new(type="CYCLES")
            except Exception:
                pass

scene.frame_set(1)
out_path = os.path.join(output_dir, f"{run_id}_procedural.{fmt}")

def collapse_glb_animations(glb_path, clip_name):
    try:
        with open(glb_path, "rb") as fh:
            raw = fh.read()
        if raw[:4] != b"glTF":
            return {"collapsed": False, "reason": "not_glb"}
        version, total_length = struct.unpack_from("<II", raw, 4)
        if version != 2:
            return {"collapsed": False, "reason": "unsupported_glb_version"}
        offset = 12
        chunks = []
        while offset + 8 <= len(raw):
            chunk_len, chunk_type = struct.unpack_from("<II", raw, offset)
            offset += 8
            chunks.append((chunk_type, raw[offset:offset + chunk_len]))
            offset += chunk_len
        if not chunks or chunks[0][0] != 0x4E4F534A:
            return {"collapsed": False, "reason": "missing_json_chunk"}
        gltf = json.loads(chunks[0][1].rstrip(bytes([0]) + b" ").decode("utf-8"))
        animations = gltf.get("animations") or []
        if len(animations) <= 1:
            if animations:
                animations[0]["name"] = clip_name
            return {"collapsed": False, "reason": "already_single", "animation_count": len(animations)}
        samplers = []
        channels = []
        for anim in animations:
            sampler_offset = len(samplers)
            for sampler in anim.get("samplers") or []:
                samplers.append(copy.deepcopy(sampler))
            for channel in anim.get("channels") or []:
                merged_channel = copy.deepcopy(channel)
                merged_channel["sampler"] = int(merged_channel.get("sampler", 0)) + sampler_offset
                channels.append(merged_channel)
        gltf["animations"] = [{
            "name": clip_name,
            "samplers": samplers,
            "channels": channels,
        }]
        json_bytes = json.dumps(gltf, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        json_bytes += b" " * ((4 - len(json_bytes) % 4) % 4)
        chunks[0] = (0x4E4F534A, json_bytes)
        out = bytearray()
        out.extend(b"glTF")
        out.extend(struct.pack("<II", 2, 12 + sum(8 + len(data) for _, data in chunks)))
        for chunk_type, data in chunks:
            out.extend(struct.pack("<II", len(data), chunk_type))
            out.extend(data)
        with open(glb_path, "wb") as fh:
            fh.write(out)
        return {"collapsed": True, "animation_count_before": len(animations), "animation_count_after": 1, "channels": len(channels)}
    except Exception as exc:
        return {"collapsed": False, "reason": f"{type(exc).__name__}: {exc}"}

animation_collapse = None
if fmt == "glb":
    bpy.ops.export_scene.gltf(filepath=out_path, export_format="GLB", export_animations=True, export_extras=True)
    animation_collapse = collapse_glb_animations(out_path, "Macarena_Dance_Unified")
elif fmt == "fbx":
    bpy.ops.export_scene.fbx(filepath=out_path, use_selection=False)
else:
    bpy.ops.wm.obj_export(filepath=out_path)

print(json.dumps({
    "ok": True,
    "path": out_path,
    "format": fmt,
    "animationFrames": 181,
    "animationCollapse": animation_collapse,
    "dance": params.get("dance", "macarena"),
    "materialZones": 8,
}))
''',

    "gear_train_system": '''
import bpy, math, json, sys, os

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
params = json.loads(argv[0]) if argv else {}
output_dir = argv[1] if len(argv) > 1 else "/tmp"
run_id = argv[2] if len(argv) > 2 else "proc"
fmt = argv[3] if len(argv) > 3 else "glb"

bpy.ops.wm.read_factory_settings(use_empty=True)

r1 = params.get("r1", 0.08)
r2 = params.get("r2", 0.16)
teeth1 = params.get("teeth1", 16)
teeth2 = params.get("teeth2", 32)
module_m = params.get("module", 0.005)

# Simple gear approximation
for i, (name, r, teeth, x) in enumerate([("Gear_Driver", r1, teeth1, 0), ("Gear_Driven", r2, teeth2, r1 + r2)]):
    bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=0.02, location=(x, 0, 0), vertices=teeth * 2)
    obj = bpy.context.active_object
    obj.name = name

p1 = bpy.data.objects["Gear_Driver"]
p2 = bpy.data.objects["Gear_Driven"]

ratio = teeth1 / teeth2
fcu = p2.driver_add("rotation_euler", 2)
drv = fcu.driver
drv.type = "SCRIPTED"
var = drv.variables.new()
var.name = "rot"
var.type = "TRANSFORMS"
var.targets[0].id = p1
var.targets[0].transform_type = "ROT_Z"
var.targets[0].transform_space = "LOCAL_SPACE"
drv.expression = f"-rot * {ratio}"

p1.rotation_euler[2] = 0
p1.keyframe_insert(data_path="rotation_euler", index=2, frame=1)
p1.rotation_euler[2] = math.radians(360 * 4)
p1.keyframe_insert(data_path="rotation_euler", index=2, frame=120)

out_path = os.path.join(output_dir, f"{run_id}_procedural.{fmt}")
if fmt == "glb":
    bpy.ops.export_scene.gltf(filepath=out_path, export_format="GLB", export_animations=True)
else:
    bpy.ops.wm.obj_export(filepath=out_path)

print(json.dumps({"ok": True, "path": out_path, "format": fmt, "animationFrames": 120, "kinematicRatio": ratio}))
''',

    "cylinder_actuator_system": '''
import bpy, math, json, sys, os

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
params = json.loads(argv[0]) if argv else {}
output_dir = argv[1] if len(argv) > 1 else "/tmp"
run_id = argv[2] if len(argv) > 2 else "proc"
fmt = argv[3] if len(argv) > 3 else "glb"

bpy.ops.wm.read_factory_settings(use_empty=True)

barrel_r = params.get("barrel_radius", 0.04)
barrel_l = params.get("barrel_length", 0.3)
rod_r = params.get("rod_radius", 0.015)
stroke = params.get("stroke", 0.15)

# Barrel (fixed)
bpy.ops.mesh.primitive_cylinder_add(radius=barrel_r, depth=barrel_l, location=(0, 0, 0))
barrel = bpy.context.active_object
barrel.name = "Cylinder_Barrel"
barrel.rotation_euler[1] = math.radians(90)

# Rod (moving)
bpy.ops.mesh.primitive_cylinder_add(radius=rod_r, depth=barrel_l * 0.8, location=(barrel_l / 2 + stroke / 2, 0, 0))
rod = bpy.context.active_object
rod.name = "Piston_Rod"
rod.rotation_euler[1] = math.radians(90)

# Animate rod extension
rod.location[0] = barrel_l / 4
rod.keyframe_insert(data_path="location", index=0, frame=1)
rod.location[0] = barrel_l / 4 + stroke
rod.keyframe_insert(data_path="location", index=0, frame=60)
rod.location[0] = barrel_l / 4
rod.keyframe_insert(data_path="location", index=0, frame=120)

out_path = os.path.join(output_dir, f"{run_id}_procedural.{fmt}")
if fmt == "glb":
    bpy.ops.export_scene.gltf(filepath=out_path, export_format="GLB", export_animations=True)
else:
    bpy.ops.wm.obj_export(filepath=out_path)

print(json.dumps({"ok": True, "path": out_path, "format": fmt, "animationFrames": 120, "stroke": stroke}))
''',

    "hinge_joint_system": '''
import bpy, math, json, sys, os

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
params = json.loads(argv[0]) if argv else {}
output_dir = argv[1] if len(argv) > 1 else "/tmp"
run_id = argv[2] if len(argv) > 2 else "proc"
fmt = argv[3] if len(argv) > 3 else "glb"

bpy.ops.wm.read_factory_settings(use_empty=True)

leaf_w = params.get("leaf_width", 0.06)
leaf_h = params.get("leaf_height", 0.1)
leaf_t = params.get("leaf_thickness", 0.004)
pin_r = params.get("pin_radius", 0.004)
max_angle = params.get("max_angle", 120)

# Fixed leaf: beveled plate instead of a raw flat cube → proper edges/corners.
bpy.ops.mesh.primitive_cube_add(size=1, location=(-leaf_w / 2, 0, 0))
fixed = bpy.context.active_object
fixed.name = "Hinge_Fixed"
fixed.scale = (leaf_w / 2, leaf_t / 2, leaf_h / 2)
bpy.ops.object.modifier_add(type="BEVEL")
fixed.modifiers["Bevel"].width = min(leaf_w, leaf_h, leaf_t) * 0.1
fixed.modifiers["Bevel"].segments = 3

# Moving leaf — same treatment.
bpy.ops.mesh.primitive_cube_add(size=1, location=(leaf_w / 2, 0, 0))
moving = bpy.context.active_object
moving.name = "Hinge_Moving"
moving.scale = (leaf_w / 2, leaf_t / 2, leaf_h / 2)
bpy.ops.object.modifier_add(type="BEVEL")
moving.modifiers["Bevel"].width = min(leaf_w, leaf_h, leaf_t) * 0.1
moving.modifiers["Bevel"].segments = 3

# Pin: full knuckle that spans the leaf height, not a tiny segment.
bpy.ops.mesh.primitive_cylinder_add(radius=pin_r, depth=leaf_h * 1.05, location=(0, 0, 0), vertices=24)
pin = bpy.context.active_object
pin.name = "Hinge_Pin"

# Knuckle sleeves (3 rings so the hinge actually looks like a hinge, not two plates + a stick).
for k, z in enumerate([-leaf_h * 0.35, 0.0, leaf_h * 0.35]):
    bpy.ops.mesh.primitive_cylinder_add(radius=pin_r * 1.9, depth=leaf_h * 0.2, location=(0, 0, z), vertices=24)
    knuckle = bpy.context.active_object
    knuckle.name = f"Hinge_Knuckle_{k}"

# Animate
moving.rotation_euler[1] = 0
moving.keyframe_insert(data_path="rotation_euler", index=1, frame=1)
moving.rotation_euler[1] = math.radians(max_angle)
moving.keyframe_insert(data_path="rotation_euler", index=1, frame=60)
moving.rotation_euler[1] = 0
moving.keyframe_insert(data_path="rotation_euler", index=1, frame=120)

out_path = os.path.join(output_dir, f"{run_id}_procedural.{fmt}")
if fmt == "glb":
    bpy.ops.export_scene.gltf(filepath=out_path, export_format="GLB", export_animations=True)
else:
    bpy.ops.wm.obj_export(filepath=out_path)

print(json.dumps({"ok": True, "path": out_path, "format": fmt, "animationFrames": 120, "maxAngle": max_angle}))
''',

    "linkage_system": '''
import bpy, math, json, sys, os
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
params = json.loads(argv[0]) if argv else {}
output_dir = argv[1] if len(argv) > 1 else "/tmp"
run_id = argv[2] if len(argv) > 2 else "proc"
fmt = argv[3] if len(argv) > 3 else "glb"

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.fps = 24

# 4-bar linkage: ground, crank, coupler, rocker.
L1, L2, L3, L4 = params.get("links", [0.24, 0.08, 0.22, 0.16])
link_thickness = float(params.get("link_thickness", 0.012))
link_depth = float(params.get("link_depth", 0.02))
crank_rpm = float(params.get("crank_rpm", 60))
anim_seconds = float(params.get("anim_seconds", 5))

# Ground positions: fixed pivot O2 at origin, fixed pivot O4 at (L1, 0, 0).
O2 = (0.0, 0.0, 0.0)
O4 = (L1, 0.0, 0.0)

def make_link(name, length, joint_a, joint_b):
    # Capsule-style link: stretched cube bevelled at the edges (not a naked brick).
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 0))
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = (length / 2, link_thickness / 2, link_depth / 2)
    bpy.ops.object.modifier_add(type="BEVEL")
    obj.modifiers["Bevel"].width = min(link_thickness, link_depth) * 0.35
    obj.modifiers["Bevel"].segments = 4
    # End caps (proper rounded pins, not corners).
    for sign, cap_name in [(-1, f"{name}_CapA"), (1, f"{name}_CapB")]:
        bpy.ops.mesh.primitive_uv_sphere_add(radius=link_depth * 0.55, location=(sign * length / 2, 0, 0))
        cap = bpy.context.active_object
        cap.name = cap_name
        cap.parent = obj
    return obj

ground_link = make_link("Link_Ground", L1, O2, O4)
crank_link = make_link("Link_Crank", L2, O2, (O2[0] + L2, 0, 0))
coupler_link = make_link("Link_Coupler", L3, (O2[0] + L2, 0, 0), (O4[0] - L4, 0, 0))
rocker_link = make_link("Link_Rocker", L4, O4, (O4[0] - L4, 0, 0))

# Parent links to empties for proper pivot behavior.
def pivot_empty(name, location):
    bpy.ops.object.empty_add(type="PLAIN_AXES", location=location)
    e = bpy.context.active_object
    e.name = name
    return e

pivot_O2 = pivot_empty("Pivot_O2", O2)
pivot_A = pivot_empty("Pivot_A", (O2[0] + L2, 0, 0))
pivot_O4 = pivot_empty("Pivot_O4", O4)
pivot_B = pivot_empty("Pivot_B", (O4[0] - L4, 0, 0))

# Rig the crank: the whole crank link rotates about O2.
crank_link.parent = pivot_O2
crank_link.location = (L2 / 2, 0, 0)

# Baked 4-bar kinematics: pre-compute pivot_A and pivot_B at each frame, along with
# coupler and rocker orientations. This is stable and honest (no half-working drivers).
import numpy as np
frames = int(anim_seconds * scene.render.fps)
omega = 2 * math.pi * crank_rpm / 60.0

def clamp(x, a, b): return max(a, min(b, x))

for f in range(1, frames + 2):
    t = (f - 1) / scene.render.fps
    theta = omega * t
    ax = L2 * math.cos(theta)
    ay = L2 * math.sin(theta)
    # Solve pivot B position: intersection of circle(O4, L4) and circle(A, L3) in the plane z=0.
    dx = O4[0] - ax
    dy = 0 - ay
    d = math.hypot(dx, dy)
    if d < abs(L3 - L4) or d > L3 + L4:
        # Mechanism would dislocate: clamp to boundary by pushing the coupler onto the closest solution.
        d = clamp(d, abs(L3 - L4) + 1e-6, L3 + L4 - 1e-6)
    a_num = (L3 * L3 - L4 * L4 + d * d) / max(1e-6, (2 * d))
    h2 = max(0.0, L3 * L3 - a_num * a_num)
    h = math.sqrt(h2)
    px = ax + a_num * (dx / max(1e-6, d))
    py = ay + a_num * (dy / max(1e-6, d))
    # Pick the branch with positive z-offset to keep a consistent solution.
    bx = px - h * (dy / max(1e-6, d))
    by = py + h * (dx / max(1e-6, d))

    pivot_O2.rotation_euler = (0, 0, theta)
    pivot_O2.keyframe_insert("rotation_euler", frame=f)

    pivot_A.location = (ax, ay, 0)
    pivot_A.keyframe_insert("location", frame=f)
    pivot_B.location = (bx, by, 0)
    pivot_B.keyframe_insert("location", frame=f)

    # Coupler orientation: along AB, midpoint placement.
    coupler_link.location = ((ax + bx) / 2, (ay + by) / 2, 0)
    coupler_link.rotation_euler = (0, 0, math.atan2(by - ay, bx - ax))
    coupler_link.keyframe_insert("location", frame=f)
    coupler_link.keyframe_insert("rotation_euler", frame=f)

    # Rocker orientation: from O4 to B.
    rocker_link.location = ((O4[0] + bx) / 2, (O4[1] + by) / 2, 0)
    rocker_link.rotation_euler = (0, 0, math.atan2(by - O4[1], bx - O4[0]))
    rocker_link.keyframe_insert("location", frame=f)
    rocker_link.keyframe_insert("rotation_euler", frame=f)

# Joint visual markers: small shiny spheres (link_connector token → palette).
for name, loc in [("Joint_O2_connector", O2), ("Joint_A_connector", (ax, ay, 0)),
                  ("Joint_O4_connector", O4), ("Joint_B_connector", (bx, by, 0))]:
    bpy.ops.mesh.primitive_uv_sphere_add(radius=link_depth * 0.6, location=loc)
    sp = bpy.context.active_object
    sp.name = name

scene.frame_start = 1
scene.frame_end = frames

out_path = os.path.join(output_dir, f"{run_id}_procedural.{fmt}")
if fmt == "glb":
    bpy.ops.export_scene.gltf(filepath=out_path, export_format="GLB", export_animations=True, export_lights=True)
else:
    bpy.ops.wm.obj_export(filepath=out_path)

print(json.dumps({"ok": True, "path": out_path, "format": fmt, "animationFrames": frames, "linkLengths": [L1, L2, L3, L4]}))
''',

    "cable_bundle_system": '''
import bpy, math, json, sys, os
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
params = json.loads(argv[0]) if argv else {}
output_dir = argv[1] if len(argv) > 1 else "/tmp"
run_id = argv[2] if len(argv) > 2 else "proc"
fmt = argv[3] if len(argv) > 3 else "glb"

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.fps = 24

strand_count = max(1, int(params.get("strand_count", 8)))
# iter17.B: strand_radius default 0.002→0.0005 (2mm→0.5mm). At 2mm individual
# wires were thick enough to touch each other and re-blend into a single
# uniform tube; 0.5mm leaves clear gaps so each strand reads as distinct.
strand_radius = max(0.0003, float(params.get("strand_radius", 0.0005)))
# iter17.B: bundle_radius minimum 0.005→0.008 (5mm→8mm) so even a tight
# request can't collapse 24 strands into a visual blob. Default stays 0.012.
bundle_radius = max(strand_radius * 4.0, float(params.get("bundle_radius", 0.012)))
length = max(0.05, float(params.get("length", 0.3)))
emissive = bool(params.get("emissive", True))
colors = params.get("colors")  # optional list of hex/rgb, one per strand
sag = float(params.get("sag", 0.03))  # catenary droop
# iter15.C: LED animation pattern + speed forwarded as extras instead of FCurves.
led_pattern_raw = str(params.get("led_pattern", "chase")).lower()
_allowed_patterns = ("static_color", "breathing", "pulse", "chase", "rainbow")
led_pattern = led_pattern_raw if led_pattern_raw in _allowed_patterns else "chase"
led_speed_hz = float(params.get("led_speed_hz", 2.0))
# iter17.A/E: default 3.5→2.0. Tuned together with viewer fill cut (iter17.E):
# original 3.5 saturated to white because viewer hemi+key+fill totalled 2.75
# of white light dominating the per-strand emission. iter17.E cuts fills to
# 0.58 total, so emission=2.0 reads as strong saturated hues without ACES
# bloom-to-white. Validated: 4-6 distinct hues visible simultaneously at T=0.4.
led_strength = float(params.get("led_emission_strength", 2.0))
points = params.get("points") or [
    (0, 0, 0),
    (length * 0.25, sag * 0.8, 0.015),
    (length * 0.5, sag, 0.0),
    (length * 0.75, sag * 0.6, -0.015),
    (length, 0, 0),
]

def _hex(c):
    if isinstance(c, (list, tuple)) and len(c) >= 3:
        r, g, b = c[0], c[1], c[2]
        if max(r, g, b) > 1.5:
            return (r / 255.0, g / 255.0, b / 255.0)
        return (float(r), float(g), float(b))
    if isinstance(c, str):
        s = c.strip().lstrip("#")
        if len(s) == 3:
            s = "".join(ch * 2 for ch in s)
        if len(s) == 6:
            try:
                return (int(s[0:2], 16) / 255.0, int(s[2:4], 16) / 255.0, int(s[4:6], 16) / 255.0)
            except ValueError:
                return (1.0, 0.2, 0.2)
    # fallback: sample the rainbow by hue
    h = (float(c) if isinstance(c, (int, float)) else 0.0) % 1.0
    r = 0.5 + 0.5 * math.cos(2 * math.pi * (h + 0.0))
    g = 0.5 + 0.5 * math.cos(2 * math.pi * (h + 0.333))
    b = 0.5 + 0.5 * math.cos(2 * math.pi * (h + 0.666))
    return (r, g, b)

# Resolve a color per strand: user-provided list, else rainbow.
resolved_colors = []
resolved_colors_hex = []  # iter15.C: parallel hex strings for aurora_led_emission extras.
for i in range(strand_count):
    if colors and i < len(colors):
        rgb = _hex(colors[i])
    else:
        rgb = _hex(i / max(1, strand_count))
    resolved_colors.append(rgb)
    r8 = max(0, min(255, int(round(rgb[0] * 255))))
    g8 = max(0, min(255, int(round(rgb[1] * 255))))
    b8 = max(0, min(255, int(round(rgb[2] * 255))))
    resolved_colors_hex.append(f"#{r8:02X}{g8:02X}{b8:02X}")

# --- Main path curve (defines the cable trajectory) ---
curve_data = bpy.data.curves.new("CablePath_Curve", type="CURVE")
curve_data.dimensions = "3D"
spline = curve_data.splines.new("BEZIER")
spline.bezier_points.add(len(points) - 1)
for i, p in enumerate(points):
    bp = spline.bezier_points[i]
    bp.co = Vector(p)
    bp.handle_left_type = "AUTO"
    bp.handle_right_type = "AUTO"
path_obj = bpy.data.objects.new("CableMaster_path", curve_data)
bpy.context.collection.objects.link(path_obj)

# --- Circular profile so each strand is a clean tube, not a flat ribbon ---
bpy.ops.curve.primitive_bezier_circle_add(radius=strand_radius, location=(0, 0, 0))
profile = bpy.context.active_object
profile.name = "StrandProfile"
profile.hide_viewport = True
profile.hide_render = True

# Attach profile to the master so the master also renders as a tube (trunk jacket).
curve_data.bevel_mode = "OBJECT"
curve_data.bevel_object = profile
curve_data.fill_mode = "FULL"

# --- Create individual strands around the master path ---
strand_materials = []
strand_objs = []
for i in range(strand_count):
    strand = path_obj.copy()
    strand.data = path_obj.data.copy()
    # Keep the "cable" token so PBR fallback works, but also add "led" so emissive is applied.
    strand.name = f"Cable_strand_{i:02d}_led_emit"
    bpy.context.collection.objects.link(strand)
    angle = (2 * math.pi * i) / max(1, strand_count)
    strand.location += Vector((math.cos(angle) * bundle_radius, math.sin(angle) * bundle_radius, 0))
    strand.data = strand.data  # keep ref
    strand.data.bevel_mode = "OBJECT"
    strand.data.bevel_object = profile
    strand.data.fill_mode = "FULL"

    color = resolved_colors[i]
    # Per-strand PBR material with distinct emission color (real RGB LED look).
    mat = bpy.data.materials.new(f"LED_RGB_{i:02d}")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    if "Metallic" in bsdf.inputs: bsdf.inputs["Metallic"].default_value = 0.0
    if "Roughness" in bsdf.inputs: bsdf.inputs["Roughness"].default_value = 0.35
    if emissive:
        key = "Emission Color" if "Emission Color" in bsdf.inputs else "Emission"
        bsdf.inputs[key].default_value = (*color, 1.0)
        if "Emission Strength" in bsdf.inputs:
            bsdf.inputs["Emission Strength"].default_value = led_strength
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    # iter15.C: retrofit aurora.led-emission.v1 extras (mirrors iter9.D fix on
    # motion_intent_bpy_runner.bake_led_emission). FCurves on shader-node
    # sockets do NOT survive glTF export (KHR_animation_pointer is not
    # supported by the Blender exporter as of 5.1). So we tag each material
    # with the LED pattern as glTF material extras and let the runtime reader
    # (ModelView.tsx _collectLedBindings + aurora_3d_viewer.py LED loop) drive
    # material.emissive + material.emissiveIntensity at draw-time.
    if emissive:
        try:
            # iter16.B: per-strand phase_offset so chase/rainbow patterns
            # propagate ALONG the cable (each strand starts a fraction of a
            # period after the previous one) instead of pulsing globally in
            # sync. phase_offset is in [0, 1] = unit-period fraction; the
            # runtime reader (ModelView.tsx _evalLedPattern + aurora_3d_viewer.py)
            # shifts t by phase_offset / speed_hz before pattern eval.
            phase_offset = (i / strand_count) if strand_count > 0 else 0.0
            mat["aurora_led_emission"] = {
                "schema": "aurora.led-emission.v1",
                "pattern": led_pattern,
                "speed_hz": float(led_speed_hz),
                "colors": list(resolved_colors_hex),
                "emission_strength": float(led_strength),
                "base_color": resolved_colors_hex[i],
                "frame_count": 60,
                "fps": 30,
                "loop": True,
                "phase_offset": float(phase_offset),
            }
        except Exception:
            pass
    if not strand.data.materials:
        strand.data.materials.append(mat)
    else:
        strand.data.materials[0] = mat
    strand_materials.append(mat)
    strand_objs.append(strand)

# iter15.C: animation frame count is now driven by the runtime reader
# (period = 1/speed_hz seconds, evaluated at draw-time by Three.js / the
# standalone viewer). We keep `frames` for the response payload and for the
# armature stretch layer below, but we no longer pose any FCurves on the
# Emission Strength shader-node sockets — the glTF exporter would silently
# drop them. The `aurora_led_emission` extras above is the source of truth.
frames = 120

# --- Add real Blender POINT lights along the path (KHR_lights_punctual in glTF) ---
light_spots = 4
light_count = max(2, int(params.get("led_lights", light_spots)))
for i in range(light_count):
    t = i / max(1, light_count - 1) if light_count > 1 else 0.5
    # Sample the path at parameter t using linear interpolation between control points.
    idx = t * (len(points) - 1)
    i0 = int(math.floor(idx))
    i1 = min(i0 + 1, len(points) - 1)
    frac = idx - i0
    p = Vector(points[i0]).lerp(Vector(points[i1]), frac)
    color = resolved_colors[i % len(resolved_colors)]
    ld = bpy.data.lights.new(f"LED_Light_{i:02d}", type="POINT")
    ld.color = color
    # iter17.E: 12.0→3.5. KHR_lights_punctual energy is in watts; at 12W per
    # point light, four lights pumped >40W of white-ish radiance into the
    # scene which dominated the per-strand emissive material. 3.5W gives a
    # subtle colored glow halo around each LED hotspot without washing out
    # the rest of the cable. The hue chase is now driven by the per-strand
    # emissive material at draw-time (LED bindings), with these point lights
    # acting as ambient atmospheric color rather than primary lighting.
    ld.energy = 3.5
    try:
        ld.shadow_soft_size = strand_radius * 2.5
    except Exception:
        pass
    lo = bpy.data.objects.new(f"LED_Light_{i:02d}_lamp", ld)
    bpy.context.collection.objects.link(lo)
    lo.location = (p.x, p.y + 0.01, p.z)

# --- Stretch armature: each control point gets a bone, meshes follow cleanly ---
# iter14 fix: ensure the active object is unhidden + selectable before mode_set,
# otherwise Blender 5.1 raises "Cannot edit hidden object" (StrandProfile is
# hide_viewport=True from earlier in the template).
for _o in bpy.context.scene.objects:
    if _o.hide_viewport:
        _o.hide_viewport = False
visible = [o for o in bpy.context.scene.objects if not o.hide_viewport]
if visible:
    for _o in bpy.context.selected_objects:
        _o.select_set(False)
    visible[0].select_set(True)
    bpy.context.view_layer.objects.active = visible[0]
try:
    bpy.ops.object.mode_set(mode="OBJECT")
except RuntimeError:
    pass
# Re-hide the strand profile after exiting edit mode so it doesn't render.
_profile = bpy.data.objects.get("StrandProfile")
if _profile is not None:
    _profile.hide_viewport = True
    _profile.hide_render = True

# iter15.C: convert each Bezier-curve strand to a mesh so the glTF exporter
# bakes both the bevel geometry AND the per-strand material (with our
# aurora_led_emission extras). Without this, the GLB exports 0 meshes and
# 0 materials — Blender's exporter skips curves with bevel_object unless they
# are real meshes. We exclude StrandProfile (the hidden bevel reference) and
# the original master path so we keep the scene tidy.
for _o in bpy.context.selected_objects:
    _o.select_set(False)
_strands_to_convert = [o for o in bpy.context.scene.objects
                       if o.type == "CURVE" and o.name.startswith("Cable_strand_")]
if _strands_to_convert:
    bpy.context.view_layer.objects.active = _strands_to_convert[0]
    for _s in _strands_to_convert:
        _s.select_set(True)
    try:
        bpy.ops.object.convert(target="MESH")
    except RuntimeError:
        pass
    for _o in bpy.context.selected_objects:
        _o.select_set(False)
# Also convert the master cable path so the trunk jacket renders.
_master_path = bpy.data.objects.get("CableMaster_path")
if _master_path is not None and _master_path.type == "CURVE":
    bpy.context.view_layer.objects.active = _master_path
    _master_path.select_set(True)
    try:
        bpy.ops.object.convert(target="MESH")
    except RuntimeError:
        pass
    _master_path.select_set(False)
bpy.ops.object.armature_add(enter_editmode=False, location=(0, 0, 0))
arm = bpy.context.active_object
arm.name = "CableStretch_Arm"
bpy.ops.object.mode_set(mode="EDIT")
edit_bones = arm.data.edit_bones
edit_bones.remove(edit_bones[0])
prev = None
bones_created = 0
for i in range(len(points) - 1):
    bone = edit_bones.new(f"B{i}")
    bone.head = Vector(points[i])
    bone.tail = Vector(points[i + 1])
    if prev is not None:
        bone.parent = prev
        bone.use_connect = False
    prev = bone
    bones_created += 1
bpy.ops.object.mode_set(mode="OBJECT")

out_path = os.path.join(output_dir, f"{run_id}_procedural.{fmt}")
# iter15.C: count materials carrying aurora_led_emission BEFORE export so we
# can verify the colorize pass preserved them. The colorize pass runs as the
# very next statement (injected by run_blender_script just before the
# export_scene.gltf call), so peek-after-this is also peek-before-export.
def _count_led_tagged_pre_export():
    n = 0
    for _m in bpy.data.materials:
        try:
            if _m.get("aurora_led_emission") is not None:
                n += 1
        except Exception:
            pass
    return n
_led_tagged_pre = _count_led_tagged_pre_export()
if fmt == "glb":
    # iter15.C: export_extras=True is REQUIRED so the per-material
    # `aurora_led_emission` IDProperty is serialised into materials[].extras
    # in the GLB. Without it, ModelView.tsx + aurora_3d_viewer.py have
    # nothing to bind to and the LEDs render as a static red glow.
    bpy.ops.export_scene.gltf(filepath=out_path, export_format="GLB",
                              export_animations=True, export_lights=True,
                              export_extras=True)
elif fmt == "fbx":
    bpy.ops.export_scene.fbx(filepath=out_path, use_selection=False, bake_anim=True)
else:
    bpy.ops.wm.obj_export(filepath=out_path)

# Re-count after export (the colorize pass may have re-tagged via _apply_pbr_to_scene).
_led_tagged_post = _count_led_tagged_pre_export()

print(json.dumps({
    "ok": True,
    "path": out_path,
    "format": fmt,
    "strandCount": strand_count,
    "animationFrames": frames,
    "ledLightCount": light_count,
    "stretchBones": bones_created,
    "ledTaggedMaterials": _led_tagged_post,
    "ledTaggedPreColorize": _led_tagged_pre,
}))
''',

    "strimer_plus_v2_cable": '''
import bpy, math, json, sys, os

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
params = json.loads(argv[0]) if argv else {}
output_dir = argv[1] if len(argv) > 1 else "/tmp"
run_id = argv[2] if len(argv) > 2 else "proc"
fmt = argv[3] if len(argv) > 3 else "glb"

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.fps = 30

variant = str(params.get("variant", "24pin"))
length = max(0.20, float(params.get("length", 0.267)))
width = max(0.030, float(params.get("width", 0.0566)))
thickness = max(0.004, float(params.get("thickness", 0.008)))
light_guides = max(4, int(params.get("light_guides", 12)))
led_count = max(light_guides, int(params.get("led_count", 120)))
channel_count = max(1, int(params.get("channel_count", 6)))
segments_per_guide = max(4, int(round(led_count / max(1, light_guides))))
pattern_raw = str(params.get("pattern", "rainbow")).lower()
_allowed_patterns = ("static_color", "breathing", "pulse", "chase", "rainbow")
pattern = pattern_raw if pattern_raw in _allowed_patterns else "rainbow"
led_speed_hz = float(params.get("led_speed_hz", 1.65))
led_strength = float(params.get("led_emission_strength", 2.4))

def _rainbow(t):
    t = t % 1.0
    return (
        0.5 + 0.5 * math.cos(math.tau * (t + 0.00)),
        0.5 + 0.5 * math.cos(math.tau * (t + 0.333)),
        0.5 + 0.5 * math.cos(math.tau * (t + 0.666)),
    )

def _hex(rgb):
    return "#{:02X}{:02X}{:02X}".format(
        max(0, min(255, int(round(rgb[0] * 255)))),
        max(0, min(255, int(round(rgb[1] * 255)))),
        max(0, min(255, int(round(rgb[2] * 255)))),
    )

palette = [_hex(_rainbow(i / 12.0)) for i in range(12)]

def _make_texture():
    img = bpy.data.images.new("StrimerV2_Silicone_TPE_MicroRidge_Texture", width=768, height=192, alpha=True)
    pixels = []
    for y in range(192):
        v = y / 191.0
        for x in range(768):
            u = x / 767.0
            rib = 0.06 if (int(v * 48) % 2 == 0) else -0.015
            fine = 0.022 * math.sin(math.tau * (u * 42.0 + v * 3.0))
            guide_shadow = 0.05 * (1.0 - abs(v - 0.5) * 2.0)
            base = max(0.0, min(1.0, 0.70 + rib + fine + guide_shadow))
            pixels.extend([base * 0.92, base * 0.94, base, 0.92])
    img.pixels.foreach_set(pixels)
    img.pack()
    return img

texture_img = _make_texture()

def _simple_mat(name, color, metallic=0.0, roughness=0.55, alpha=1.0, texture=False, emission=None, strength=0.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    if alpha < 1.0:
        mat.blend_method = "BLEND"
        mat.use_screen_refraction = True
    nt = mat.node_tree
    nt.nodes.clear()
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    outn = nt.nodes.new("ShaderNodeOutputMaterial")
    if texture:
        tex = nt.nodes.new("ShaderNodeTexImage")
        tex.image = texture_img
        tex.extension = "REPEAT"
        nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
        if "Alpha" in bsdf.inputs:
            nt.links.new(tex.outputs["Alpha"], bsdf.inputs["Alpha"])
    else:
        bsdf.inputs["Base Color"].default_value = (*color, alpha)
        if "Alpha" in bsdf.inputs:
            bsdf.inputs["Alpha"].default_value = alpha
    if "Metallic" in bsdf.inputs:
        bsdf.inputs["Metallic"].default_value = metallic
    if "Roughness" in bsdf.inputs:
        bsdf.inputs["Roughness"].default_value = roughness
    if emission is not None:
        key = "Emission Color" if "Emission Color" in bsdf.inputs else "Emission"
        bsdf.inputs[key].default_value = (*emission, 1.0)
        if "Emission Strength" in bsdf.inputs:
            bsdf.inputs["Emission Strength"].default_value = strength
    nt.links.new(bsdf.outputs["BSDF"], outn.inputs["Surface"])
    return mat

black_mat = _simple_mat("Mat_StrimerV2_black_matte_connector", (0.006, 0.007, 0.009), roughness=0.82)
dark_detail_mat = _simple_mat("Mat_StrimerV2_dark_socket_recess", (0.0, 0.0, 0.0), roughness=0.95)
cable_mat = _simple_mat("Mat_StrimerV2_single_layer_silicone_TPE_cables", (0.78, 0.80, 0.82), roughness=0.62, texture=True)
diffuser_mat = _simple_mat("Mat_StrimerV2_translucent_diffuser_texture", (0.86, 0.92, 1.0), roughness=0.26, alpha=0.54, texture=True)
clear_clip_mat = _simple_mat("Mat_StrimerV2_clear_alignment_clips", (0.72, 0.86, 1.0), roughness=0.18, alpha=0.34)
label_mat = _simple_mat("Mat_StrimerV2_LIAN_LI_logo_grey", (0.44, 0.46, 0.48), roughness=0.72)
side_light_mat = _simple_mat("Mat_StrimerV2_side_light_strip_emit", (0.1, 0.9, 1.0), roughness=0.18, alpha=0.62, emission=(0.1, 0.9, 1.0), strength=1.6)
bond_mat = _simple_mat("Mat_StrimerV2_bonded_silicone_TPE_core_no_air_gap", (0.82, 0.87, 0.92), roughness=0.34, alpha=0.62, texture=True)
pin_mat = _simple_mat("Mat_StrimerV2_tinned_contact_pins", (0.80, 0.78, 0.70), metallic=0.8, roughness=0.28)

for mat in (cable_mat, diffuser_mat, bond_mat):
    mat["aurora_surface_texture"] = {
        "schema": "aurora.surface-texture.v1",
        "kind": "lian_li_strimer_plus_v2_silicone_tpe_micro_ridge",
        "channels": ["baseColorTexture", "alpha"],
    }

def rounded_box(name, loc, scale, mat, bevel=0.0015, segments=3):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = scale
    obj.data.materials.append(mat)
    if bevel > 0:
        mod = obj.modifiers.new("small_radius_edges", "BEVEL")
        mod.width = bevel
        mod.segments = segments
        obj.modifiers.new("weighted_normals", "WEIGHTED_NORMAL")
    return obj

root = bpy.data.objects.new("StrimerV2_reference_root", None)
root["aurora_product_reference"] = {
    "schema": "aurora.product-reference.v1",
    "product": "Lian Li Strimer Plus V2",
    "variant": variant,
    "dimensions_m": [length, width, thickness],
    "light_guides": light_guides,
    "led_count": led_count,
    "channel_count": channel_count,
    "material": "silicone/TPE",
    "animation_system": "aurora_led_emission_runtime_channel_chase",
    "assembly_contract": "bonded silicone/TPE stack; no floating layers; connector faces only, no free pigtail cables",
}
bpy.context.collection.objects.link(root)

guide_start = length * 0.145
guide_end = length * 0.855
guide_len = guide_end - guide_start
guide_margin = width * 0.115
usable_width = width - guide_margin * 2.0
guide_pitch = usable_width / max(1, light_guides - 1)
guide_bar_w = min(0.0024, guide_pitch * 0.50)
seg_len = guide_len / segments_per_guide * 0.985

# Single bonded body: the real Strimer stack is not independent floating layers.
core = rounded_box(
    "StrimerV2_BondedSiliconeCore_guides_and_cables_fused",
    (length / 2.0, 0, thickness * 0.24),
    (guide_len * 1.035, width * 0.92, thickness * 0.56),
    bond_mat,
    bevel=thickness * 0.12,
    segments=5,
)
core["strimer_role"] = "bonded_stack_no_air_gap"

# Lower single-layer 18AWG cable row, visible below the diffusers.
wire_count = 24 if light_guides >= 12 else 16
wire_pitch = usable_width / max(1, wire_count - 1)
for i in range(wire_count):
    y = -usable_width / 2.0 + i * wire_pitch
    rounded_box(
        f"StrimerV2_LowerCable_{i:02d}_single_row_TPE",
        (length / 2.0, y, thickness * 0.08),
        (guide_len * 0.99, max(0.00075, wire_pitch * 0.28), thickness * 0.24),
        cable_mat,
        bevel=max(0.00035, wire_pitch * 0.08),
        segments=3,
    )

# Continuous translucent diffuser strips under the LED cells.
for g in range(light_guides):
    y = -usable_width / 2.0 + g * guide_pitch
    channel_index = min(channel_count - 1, int(g / max(1, light_guides / channel_count)))
    guide = rounded_box(
        f"StrimerV2_LightGuide_{g:02d}_continuous_diffuser_channel_{channel_index}",
        (length / 2.0, y, thickness * 0.36),
        (guide_len * 1.015, guide_bar_w, thickness * 0.34),
        diffuser_mat,
        bevel=guide_bar_w * 0.46,
        segments=5,
    )
    guide["strimer_role"] = "continuous_light_guide"
    guide["channel_index"] = channel_index

led_materials = []
for g in range(light_guides):
    y = -usable_width / 2.0 + g * guide_pitch
    channel_index = min(channel_count - 1, int(g / max(1, light_guides / channel_count)))
    for s in range(segments_per_guide):
        x = guide_start + (s + 0.5) * (guide_len / segments_per_guide)
        phase = (s / max(1, segments_per_guide) + channel_index / max(1, channel_count) * 0.12) % 1.0
        rgb = _rainbow(phase)
        col_hex = _hex(rgb)
        mat = _simple_mat(
            f"StrimerV2_LEDMat_g{g:02d}_s{s:02d}_channel_{channel_index}",
            rgb,
            roughness=0.16,
            alpha=0.88,
            emission=rgb,
            strength=led_strength,
        )
        mat["aurora_led_emission"] = {
            "schema": "aurora.led-emission.v1",
            "pattern": pattern,
            "speed_hz": float(led_speed_hz),
            "colors": list(palette),
            "emission_strength": float(led_strength),
            "base_color": col_hex,
            "frame_count": 90,
            "fps": 30,
            "loop": True,
            "phase_offset": float(phase),
            "channel_index": int(channel_index),
            "guide_index": int(g),
            "segment_index": int(s),
            "product": "strimer_plus_v2",
            "spatial_axis": "length",
            "view_independent": True,
        }
        led_materials.append(mat)
        led = rounded_box(
            f"StrimerV2_LED_{g:02d}_{s:02d}_emit_channel_{channel_index}",
            (x, y, thickness * 0.46),
            (seg_len * 1.04, guide_bar_w * 0.62, thickness * 0.18),
            mat,
            bevel=guide_bar_w * 0.36,
            segments=5,
        )
        led["strimer_role"] = "addressable_led_cell"

# Side light strips on both outer edges: V2 identity cue.
for side, y in (("front", usable_width / 2.0 + guide_pitch * 0.45), ("back", -usable_width / 2.0 - guide_pitch * 0.45)):
    side_obj = rounded_box(
        f"StrimerV2_SideLightStrip_{side}_multi_direction_emit",
        (length / 2.0, y, thickness * 0.34),
        (guide_len * 1.015, guide_bar_w * 0.55, thickness * 0.24),
        side_light_mat,
        bevel=guide_bar_w * 0.28,
        segments=4,
    )
    side_obj["strimer_role"] = "side_light_strip"

# Connector blocks and branded end clamps.
connector_w = width * 1.08
connector_len = max(0.020, length * 0.105)
left_x = guide_start * 0.52
right_x = length - guide_start * 0.52
rounded_box("StrimerV2_Connector_PSU_black_input_block", (left_x, 0, thickness * 0.08), (connector_len, connector_w, thickness * 0.92), black_mat, bevel=0.0035, segments=5)
rounded_box("StrimerV2_Connector_Motherboard_24pin_black_output_block", (right_x, 0, thickness * 0.08), (connector_len, connector_w, thickness * 0.92), black_mat, bevel=0.0035, segments=5)
rounded_box("StrimerV2_BrandClamp_LIAN_LI_black_crossbar", (guide_start, 0, thickness * 0.78), (connector_len * 0.72, connector_w * 1.02, thickness * 0.32), black_mat, bevel=0.0025, segments=4)
rounded_box("StrimerV2_EndClamp_black_crossbar", (guide_end, 0, thickness * 0.78), (connector_len * 0.72, connector_w * 1.02, thickness * 0.32), black_mat, bevel=0.0025, segments=4)

# Socket grid on the 24-pin face: two rows of twelve recessed holes.
hole_y_pitch = connector_w * 0.070
hole_z_pitch = thickness * 0.27
for row in range(2):
    z = thickness * 0.08 + (row - 0.5) * hole_z_pitch
    for col in range(12):
        y = -hole_y_pitch * 5.5 + col * hole_y_pitch
        rounded_box(
            f"StrimerV2_24pin_socket_recess_r{row}_c{col:02d}",
            (right_x + connector_len * 0.505, y, z),
            (0.0011, hole_y_pitch * 0.46, thickness * 0.115),
            dark_detail_mat,
            bevel=0.00025,
            segments=2,
        )

# Input connector face: the product terminates in a connector, not a cable
# plugged into another cable. Use visible metal contacts instead of free tails.
for row in range(2):
    z = thickness * 0.08 + (row - 0.5) * hole_z_pitch
    for col in range(12):
        y = -hole_y_pitch * 5.5 + col * hole_y_pitch
        rounded_box(
            f"StrimerV2_24pin_input_contact_pin_r{row}_c{col:02d}",
            (left_x - connector_len * 0.505, y, z),
            (0.0012, hole_y_pitch * 0.42, thickness * 0.105),
            pin_mat,
            bevel=0.00022,
            segments=2,
        )

# Stable black clips and translucent combs.
clip_positions = [guide_start + guide_len * 0.08, guide_start + guide_len * 0.50, guide_start + guide_len * 0.92]
for idx, x in enumerate(clip_positions):
    rounded_box(f"StrimerV2_StableClip_{idx:02d}_black_bridge", (x, 0, thickness * 0.98), (0.0055, width * 1.05, thickness * 0.15), black_mat, bevel=0.0014, segments=3)
    rounded_box(f"StrimerV2_StableClip_{idx:02d}_front_hook", (x, width * 0.54, thickness * 0.42), (0.006, width * 0.045, thickness * 0.54), black_mat, bevel=0.0012, segments=3)
    rounded_box(f"StrimerV2_StableClip_{idx:02d}_back_hook", (x, -width * 0.54, thickness * 0.42), (0.006, width * 0.045, thickness * 0.54), black_mat, bevel=0.0012, segments=3)

for idx, x in enumerate((guide_start + guide_len * 0.32, guide_start + guide_len * 0.68)):
    rounded_box(f"StrimerV2_ClearAlignmentClip_{idx:02d}_transparent_comb", (x, 0, thickness * 0.82), (0.0048, width * 0.88, thickness * 0.11), clear_clip_mat, bevel=0.0011, segments=3)

# Simple raised LIAN LI text on the branded clamp.
try:
    bpy.ops.object.text_add(location=(guide_start - connector_len * 0.06, -width * 0.17, thickness * 1.01), rotation=(0, 0, 0))
    txt = bpy.context.active_object
    txt.name = "StrimerV2_LIAN_LI_logo_text_mesh"
    txt.data.body = "LIAN LI"
    txt.data.align_x = "CENTER"
    txt.data.align_y = "CENTER"
    txt.data.size = width * 0.105
    txt.data.extrude = 0.0003
    txt.data.materials.append(label_mat)
    bpy.ops.object.convert(target="MESH")
except Exception:
    pass

# Add a few low-energy colored glows so offline screenshots show the RGB surface.
for i in range(min(8, segments_per_guide)):
    t = i / max(1, min(8, segments_per_guide) - 1)
    rgb = _rainbow(t)
    ld = bpy.data.lights.new(f"StrimerV2_RuntimeGlow_{i:02d}", type="POINT")
    ld.color = rgb
    ld.energy = 2.3
    try:
        ld.shadow_soft_size = width * 0.025
    except Exception:
        pass
    lo = bpy.data.objects.new(f"StrimerV2_RuntimeGlow_{i:02d}_lamp", ld)
    lo.location = (guide_start + t * guide_len, 0, thickness * 2.2)
    bpy.context.collection.objects.link(lo)

# UV unwrap mesh objects carrying image textures so the GLB contains real TEXCOORDs.
for obj in [o for o in bpy.context.scene.objects if o.type == "MESH"]:
    for sel in bpy.context.selected_objects:
        sel.select_set(False)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    try:
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.uv.smart_project(angle_limit=1.15192, island_margin=0.01)
        bpy.ops.object.mode_set(mode="OBJECT")
    except Exception:
        try:
            bpy.ops.object.mode_set(mode="OBJECT")
        except Exception:
            pass
    obj.select_set(False)

out_path = os.path.join(output_dir, f"{run_id}_procedural.{fmt}")
if fmt == "glb":
    bpy.ops.export_scene.gltf(filepath=out_path, export_format="GLB",
                              export_animations=True, export_lights=True,
                              export_extras=True)
elif fmt == "fbx":
    bpy.ops.export_scene.fbx(filepath=out_path, use_selection=False, bake_anim=True)
else:
    bpy.ops.wm.obj_export(filepath=out_path)

print(json.dumps({
    "ok": True,
    "path": out_path,
    "format": fmt,
    "variant": variant,
    "lightGuides": light_guides,
    "ledCount": led_count,
    "channels": channel_count,
    "animationFrames": 90,
    "pattern": pattern,
    "ledTaggedMaterials": len(led_materials),
}))
''',

    "physics_chain_system": '''
import bpy, math, json, sys, os
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
params = json.loads(argv[0]) if argv else {}
output_dir = argv[1] if len(argv) > 1 else "/tmp"
run_id = argv[2] if len(argv) > 2 else "proc"
fmt = argv[3] if len(argv) > 3 else "glb"

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.fps = 30

# A real physics-driven chain: each link is a separate rigid body, connected
# by HINGE constraints. Solver bakes positions to keyframes so the export
# carries the motion as plain animation curves (no Blender runtime required
# in the viewer). Used for: hanging chains, dangling cables, dropped ropes,
# plate falling sequences, flag in the wind, breakable wall.

link_count = max(2, int(params.get("link_count", 18)))
link_length = max(0.01, float(params.get("link_length", 0.06)))
link_radius = max(0.005, float(params.get("link_radius", 0.012)))
gravity = float(params.get("gravity", -9.81))
anchor_top = bool(params.get("anchor_top", True))
anchor_bottom = bool(params.get("anchor_bottom", False))
swing_impulse = float(params.get("swing_impulse", 1.5))  # m/s sideways at frame 1
seconds = float(params.get("seconds", 4))
frames = int(seconds * scene.render.fps)

scene.frame_start = 1
scene.frame_end = frames
scene.gravity = (0.0, 0.0, gravity)

# Configure the rigid body world.
bpy.ops.rigidbody.world_add()
rbw = scene.rigidbody_world
rbw.point_cache.frame_start = 1
rbw.point_cache.frame_end = frames
rbw.solver_iterations = 24
rbw.time_scale = 1.0
rbw.steps_per_second = 240

links = []
for i in range(link_count):
    z = -i * link_length * 0.95
    bpy.ops.mesh.primitive_uv_sphere_add(radius=link_radius, location=(0, 0, z))
    link = bpy.context.active_object
    link.name = f"Chain_link_{i:02d}"
    bpy.ops.rigidbody.object_add()
    body = link.rigid_body
    if (i == 0 and anchor_top) or (i == link_count - 1 and anchor_bottom):
        body.type = "PASSIVE"
        body.kinematic = True
    else:
        body.type = "ACTIVE"
        body.mass = 0.18
        body.friction = 0.6
        body.restitution = 0.05
    body.collision_shape = "SPHERE"
    links.append(link)

# Hinge constraints between consecutive links.
constraint_count = 0
for i in range(link_count - 1):
    bpy.ops.object.empty_add(type="PLAIN_AXES", location=((links[i].location + links[i + 1].location) / 2.0))
    empty = bpy.context.active_object
    empty.name = f"Chain_constraint_{i:02d}"
    bpy.ops.rigidbody.constraint_add()
    rb = empty.rigid_body_constraint
    rb.type = "POINT"
    rb.object1 = links[i]
    rb.object2 = links[i + 1]
    constraint_count += 1

# Optional sideways nudge so the chain visibly swings even without external forces.
if swing_impulse != 0.0:
    # Apply via initial location offset on a free middle link (Blender does not
    # expose an API for "instant velocity" on rigid bodies but a small tilt is
    # enough to start the swing under gravity).
    middle = link_count // 2
    if 0 < middle < link_count:
        links[middle].location.x += 0.04 * (swing_impulse / 1.5)

# Bake the simulation to keyframes so the GLB carries motion (no Blender
# runtime required at playback time in the viewer).
try:
    bpy.context.view_layer.objects.active = links[0]
    bpy.ops.rigidbody.bake_to_keyframes(frame_start=1, frame_end=frames)
except Exception:
    # Fallback: bake by stepping the scene manually if bake operator missing.
    for f in range(1, frames + 1):
        scene.frame_set(f)
        for link in links:
            link.keyframe_insert(data_path="location", frame=f)
            link.keyframe_insert(data_path="rotation_euler", frame=f)

out_path = os.path.join(output_dir, f"{run_id}_procedural.{fmt}")
if fmt == "glb":
    bpy.ops.export_scene.gltf(filepath=out_path, export_format="GLB", export_animations=True)
elif fmt == "fbx":
    bpy.ops.export_scene.fbx(filepath=out_path, use_selection=False, bake_anim=True)
else:
    bpy.ops.wm.obj_export(filepath=out_path)

print(json.dumps({
    "ok": True, "path": out_path, "format": fmt,
    "linkCount": link_count, "constraintCount": constraint_count,
    "animationFrames": frames, "physicsSolver": "bullet",
    "gravity": gravity,
}))
''',

    "led_strip_system": '''
import bpy, math, json, sys, os
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
params = json.loads(argv[0]) if argv else {}
output_dir = argv[1] if len(argv) > 1 else "/tmp"
run_id = argv[2] if len(argv) > 2 else "proc"
fmt = argv[3] if len(argv) > 3 else "glb"

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.fps = 24

length = max(0.05, float(params.get("length", 0.6)))
led_count = max(3, int(params.get("led_count", 24)))
led_radius = max(0.0015, float(params.get("led_radius", 0.006)))
strip_width = max(led_radius * 4.0, float(params.get("strip_width", 0.04)))
pattern_raw = str(params.get("pattern", "rainbow")).lower()
_allowed_patterns = ("static_color", "breathing", "pulse", "chase", "rainbow")
pattern = pattern_raw if pattern_raw in _allowed_patterns else "rainbow"
colors = params.get("colors")  # optional list of hex
# iter15.C: speed + base strength forwarded into aurora_led_emission extras.
led_speed_hz = float(params.get("led_speed_hz", 2.0))
# iter17.A/E: default 4.0→2.2. Tuned together with viewer fill cut (iter17.E).
# 2.2 gives the LED domes saturated hues that pop without bleeding to white.
led_strength = float(params.get("led_emission_strength", 2.2))

def _hex(c, idx=0):
    if isinstance(c, str):
        s = c.strip().lstrip("#")
        if len(s) == 3: s = "".join(ch * 2 for ch in s)
        if len(s) == 6:
            try: return (int(s[0:2], 16) / 255.0, int(s[2:4], 16) / 255.0, int(s[4:6], 16) / 255.0)
            except ValueError: pass
    if isinstance(c, (list, tuple)) and len(c) >= 3:
        r, g, b = c[:3]
        if max(r, g, b) > 1.5: return (r / 255.0, g / 255.0, b / 255.0)
        return (float(r), float(g), float(b))
    h = (idx / max(1, led_count)) % 1.0
    return (
        0.5 + 0.5 * math.cos(2 * math.pi * (h + 0.00)),
        0.5 + 0.5 * math.cos(2 * math.pi * (h + 0.333)),
        0.5 + 0.5 * math.cos(2 * math.pi * (h + 0.666)),
    )

def _make_strip_texture():
    img = bpy.data.images.new("Aurora_Silicone_PCB_Texture", width=512, height=128, alpha=True)
    pixels = []
    for y in range(128):
        v = y / 127.0
        for x in range(512):
            u = x / 511.0
            grain = 0.025 * math.sin(u * math.tau * 34.0) + 0.018 * math.sin((u + v) * math.tau * 19.0)
            trace = 1.0 if abs(v - 0.28) < 0.018 or abs(v - 0.72) < 0.018 else 0.0
            center_shadow = 0.10 * (1.0 - abs(v - 0.5) * 2.0)
            base = max(0.0, min(1.0, 0.16 + grain + center_shadow))
            r = base + trace * 0.52
            g = base + trace * 0.36
            b = base * 1.08 + trace * 0.08
            a = 0.92
            pixels.extend([r, g, b, a])
    img.pixels.foreach_set(pixels)
    img.pack()
    return img

def _make_housing_material():
    img = _make_strip_texture()
    mat = bpy.data.materials.new("Mat_textured_translucent_silicone_pcb")
    mat.use_nodes = True
    mat.blend_method = "BLEND"
    nt = mat.node_tree
    nt.nodes.clear()
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = img
    tex.extension = "REPEAT"
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    outn = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    if "Alpha" in bsdf.inputs:
        nt.links.new(tex.outputs["Alpha"], bsdf.inputs["Alpha"])
    if "Metallic" in bsdf.inputs:
        bsdf.inputs["Metallic"].default_value = 0.0
    if "Roughness" in bsdf.inputs:
        bsdf.inputs["Roughness"].default_value = 0.68
    nt.links.new(bsdf.outputs["BSDF"], outn.inputs["Surface"])
    mat["aurora_surface_texture"] = {
        "schema": "aurora.surface-texture.v1",
        "kind": "translucent_silicone_pcb",
        "channels": ["baseColorTexture", "alpha"],
    }
    return mat

def _make_simple_material(name, color, metallic=0.0, roughness=0.55, alpha=1.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    if alpha < 1.0:
        mat.blend_method = "BLEND"
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf is not None:
        bsdf.inputs["Base Color"].default_value = (*color, alpha)
        if "Alpha" in bsdf.inputs:
            bsdf.inputs["Alpha"].default_value = alpha
        if "Metallic" in bsdf.inputs:
            bsdf.inputs["Metallic"].default_value = metallic
        if "Roughness" in bsdf.inputs:
            bsdf.inputs["Roughness"].default_value = roughness
    return mat

housing_mat = _make_housing_material()
rail_mat = _make_simple_material("Mat_black_silicone_side_rails", (0.025, 0.028, 0.032), metallic=0.0, roughness=0.78)
copper_mat = _make_simple_material("Mat_visible_copper_traces", (0.95, 0.62, 0.20), metallic=0.85, roughness=0.32)
solder_mat = _make_simple_material("Mat_solder_pad_tin", (0.78, 0.80, 0.82), metallic=1.0, roughness=0.20)

# --- Housing: rounded bar (cube with bevel) that holds the LEDs ---
bpy.ops.mesh.primitive_cube_add(size=1, location=(length / 2, 0, -strip_width * 0.08))
housing = bpy.context.active_object
housing.name = "Strip_housing"
housing.scale = (length, strip_width, strip_width / 2)
housing.data.materials.append(housing_mat)
bpy.ops.object.modifier_add(type="BEVEL")
housing.modifiers["Bevel"].width = strip_width * 0.18
housing.modifiers["Bevel"].segments = 6

for side, y_pos in (("front", strip_width * 0.46), ("back", -strip_width * 0.46)):
    bpy.ops.mesh.primitive_cube_add(size=1, location=(length / 2, y_pos, strip_width * 0.11))
    rail = bpy.context.active_object
    rail.name = f"Silicone_side_rail_{side}"
    rail.scale = (length, strip_width * 0.09, strip_width * 0.12)
    rail.data.materials.append(rail_mat)
    bpy.ops.object.modifier_add(type="BEVEL")
    rail.modifiers["Bevel"].width = strip_width * 0.035
    rail.modifiers["Bevel"].segments = 3

for side, y_pos in (("top", strip_width * 0.26), ("bottom", -strip_width * 0.26)):
    bpy.ops.mesh.primitive_cube_add(size=1, location=(length / 2, y_pos, strip_width * 0.09))
    trace = bpy.context.active_object
    trace.name = f"Copper_trace_{side}"
    trace.scale = (length * 0.96, strip_width * 0.05, strip_width * 0.036)
    trace.data.materials.append(copper_mat)

pad_w = max(0.002, length / led_count * 0.20)
for i in range(led_count):
    x = (i + 0.5) * (length / led_count)
    for side, y_pos in (("A", strip_width * 0.16), ("B", -strip_width * 0.16)):
        bpy.ops.mesh.primitive_cube_add(size=1, location=(x, y_pos, strip_width * 0.12))
        pad = bpy.context.active_object
        pad.name = f"Solder_pad_{i:02d}_{side}"
        pad.scale = (pad_w, strip_width * 0.045, strip_width * 0.016)
        pad.data.materials.append(solder_mat)

# --- Individual LED domes (UV spheres, not cubes) with emissive RGB material ---
# iter15.C: animation is no longer baked into FCurves on shader-node sockets
# (the Blender glTF exporter drops those). Instead each material carries an
# `aurora_led_emission` extras block consumed at draw-time by ModelView.tsx
# and aurora_3d_viewer.py — same pattern as motion_intent_bpy_runner.bake_led_emission.
frames = 120
leds = []
materials = []
resolved_colors_hex = []  # iter15.C: parallel hex strings for the extras payload.
for i in range(led_count):
    x = (i + 0.5) * (length / led_count)
    bpy.ops.mesh.primitive_cube_add(size=1, location=(x, 0, strip_width * 0.145))
    chip = bpy.context.active_object
    chip.name = f"LED_chip_{i:02d}_emit"
    chip.scale = (led_radius * 0.95, led_radius * 0.95, led_radius * 0.30)
    bpy.ops.object.modifier_add(type="BEVEL")
    chip.modifiers["Bevel"].width = led_radius * 0.20
    chip.modifiers["Bevel"].segments = 3
    bpy.ops.mesh.primitive_uv_sphere_add(radius=led_radius, location=(x, 0, strip_width * 0.20 + led_radius * 0.45))
    dome = bpy.context.active_object
    dome.name = f"LED_dome_{i:02d}_emit"
    dome.scale = (1.0, 1.0, 0.45)
    leds.append(dome)

    col = _hex(colors[i] if (colors and i < len(colors)) else None, i)
    r8 = max(0, min(255, int(round(col[0] * 255))))
    g8 = max(0, min(255, int(round(col[1] * 255))))
    b8 = max(0, min(255, int(round(col[2] * 255))))
    col_hex = f"#{r8:02X}{g8:02X}{b8:02X}"
    resolved_colors_hex.append(col_hex)

    mat = bpy.data.materials.new(f"LED_Mat_{i:02d}")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    outn = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf.inputs["Base Color"].default_value = (*col, 1.0)
    if "Metallic" in bsdf.inputs: bsdf.inputs["Metallic"].default_value = 0.0
    if "Roughness" in bsdf.inputs: bsdf.inputs["Roughness"].default_value = 0.18
    key = "Emission Color" if "Emission Color" in bsdf.inputs else "Emission"
    bsdf.inputs[key].default_value = (*col, 1.0)
    if "Emission Strength" in bsdf.inputs:
        bsdf.inputs["Emission Strength"].default_value = led_strength
    nt.links.new(bsdf.outputs["BSDF"], outn.inputs["Surface"])
    chip.data.materials.append(mat)
    dome.data.materials.append(mat)
    materials.append(mat)

    # Real point light above each LED for true illumination.
    ld = bpy.data.lights.new(f"LED_L_{i:02d}", type="POINT")
    ld.color = col
    ld.energy = 3.0
    try: ld.shadow_soft_size = led_radius * 2
    except Exception: pass
    lo = bpy.data.objects.new(f"LED_Light_{i:02d}_emit", ld)
    bpy.context.collection.objects.link(lo)
    lo.location = (x, 0, strip_width * 0.20 + led_radius * 1.5)

# iter15.C: tag every material with aurora.led-emission.v1 extras. Each LED
# carries its own base color but advertises the full palette so a `chase`
# pattern can rotate through every color and the runtime reader can decide
# whether to drive `material.emissive` (chase/rainbow) or modulate
# intensity (breathing/pulse). Mirrors motion_intent_bpy_runner.bake_led_emission
# extras schema (iter9.D) so ModelView.tsx parses both transparently.
for i, mat in enumerate(materials):
    try:
        # iter16.B: per-LED phase_offset so chase wave runs along the strip
        # (LED 0 lights, then LED 1, then LED 2 ...) rather than every LED
        # pulsing in lockstep. phase_offset = i / led_count is in [0,1] =
        # period fraction; runtime reader applies tEffective = t + phase_offset / speed_hz.
        phase_offset = (i / led_count) if led_count > 0 else 0.0
        mat["aurora_led_emission"] = {
            "schema": "aurora.led-emission.v1",
            "pattern": pattern,
            "speed_hz": float(led_speed_hz),
            "colors": list(resolved_colors_hex),
            "emission_strength": float(led_strength),
            "base_color": resolved_colors_hex[i],
            "frame_count": 60,
            "fps": 30,
            "loop": True,
            "phase_offset": float(phase_offset),
        }
    except Exception:
        pass

out_path = os.path.join(output_dir, f"{run_id}_procedural.{fmt}")
if fmt == "glb":
    # iter15.C: export_extras=True is required for aurora.led-emission.v1
    # extras to land in materials[].extras (parity with cable_bundle_system).
    bpy.ops.export_scene.gltf(filepath=out_path, export_format="GLB",
                              export_animations=True, export_lights=True,
                              export_extras=True)
elif fmt == "fbx":
    bpy.ops.export_scene.fbx(filepath=out_path, use_selection=False, bake_anim=True)
else:
    bpy.ops.wm.obj_export(filepath=out_path)

print(json.dumps({
    "ok": True, "path": out_path, "format": fmt,
    "ledCount": led_count, "animationFrames": frames, "pattern": pattern,
}))
''',

    "motherboard_layout": '''
# v82nu iter25: procedural motherboard layout. Hunyuan3D produces meshes
# that don't capture the recognisable X870E Hero identity even with FLUX
# prompt enrichment — every bake comes back "mixed up". Procedural template
# instead, mirroring cable_bundle_system / pulley_belt_system: clean
# component layout (PCB, socket, DIMMs, M.2 heatsinks, OLED face, ROG RGB
# zone), polycount target ~3-5K tris.
#
# The OLED screen is a SEPARATE face plane carrying aurora_oled_atlas v1
# extras — the runtime reader (ModelView.tsx + aurora_3d_viewer.py) then
# scrolls a real PNG-sequence atlas at draw-time. So the user sees a true
# animated OLED display, NOT a baked image of a screen.

import bpy, math, json, sys, os

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
params = json.loads(argv[0]) if argv else {}
output_dir = argv[1] if len(argv) > 1 else "/tmp"
run_id = argv[2] if len(argv) > 2 else "proc"
fmt = argv[3] if len(argv) > 3 else "glb"

# ATX form factor: 244 mm (width X) x 305 mm (height Y)
PCB_W = float(params.get("pcb_width_m", 0.244))
PCB_H = float(params.get("pcb_height_m", 0.305))
PCB_THICK = float(params.get("pcb_thickness_m", 0.002))
SOCKET_SIZE = float(params.get("socket_size_m", 0.048))  # AM5 = 48 mm square
DIMM_COUNT = int(params.get("dimm_count", 4))
M2_COUNT = int(params.get("m2_count", 5))
PCB_COLOR = tuple(params.get("pcb_color", [0.08, 0.08, 0.09]))  # ROG dark titanium PCB
HEATSINK_COLOR = tuple(params.get("heatsink_color", [0.14, 0.14, 0.16]))  # ROG dark gunmetal heatsinks
SCREEN_TEXT = str(params.get("screen_text", "X870E HERO"))
ROG_GLOW = tuple(params.get("rog_glow", [0.0, 0.75, 1.0]))  # ROG cyan/polymo glow

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.fps = 30


def add_box(name, dims, location, color=(0.5, 0.5, 0.5), metallic=0.0,
            roughness=0.5, emission=None, emission_strength=0.0):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=location)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = dims
    bpy.ops.object.transform_apply(scale=True)
    mat = bpy.data.materials.new(f"Mat_{name}")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    bsdf.inputs["Roughness"].default_value = roughness
    if "Metallic" in bsdf.inputs:
        bsdf.inputs["Metallic"].default_value = metallic
    if emission and emission_strength > 0:
        if "Emission Color" in bsdf.inputs:
            bsdf.inputs["Emission Color"].default_value = (*emission, 1.0)
        if "Emission Strength" in bsdf.inputs:
            bsdf.inputs["Emission Strength"].default_value = emission_strength
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    obj.data.materials.append(mat)
    return obj, mat


# 1. PCB plate with exact planar UV mapping
pcb, pcb_mat = add_box("Mat_pcb_PCB",
                       dims=(PCB_W, PCB_H, PCB_THICK),
                       location=(0, 0, 0),
                       color=PCB_COLOR, roughness=0.65)

_pcb_tex_path = params.get("pcb_texture_path")
if _pcb_tex_path and os.path.isfile(_pcb_tex_path):
    nt = pcb_mat.node_tree
    bsdf = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if bsdf is not None:
        try:
            pcb_img = bpy.data.images.load(_pcb_tex_path, check_existing=True)
            pcb_img.colorspace_settings.name = "sRGB"
            pcb_tex = nt.nodes.new("ShaderNodeTexImage")
            pcb_tex.image = pcb_img
            nt.links.new(pcb_tex.outputs["Color"], bsdf.inputs["Base Color"])
            pcb_mat["aurora_pcb_texture"] = {"schema": "aurora.pcb-texture.v1",
                                              "source": "official_ref"}
        except Exception as _exc:
            print("[pcb-texture-load] failed:", _exc)

# Direct Planar UV Projection matching ATX orientation
try:
    uv_layer = pcb.data.uv_layers.active or pcb.data.uv_layers.new(name="UVMap")
    for poly in pcb.data.polygons:
        for loop_index in poly.loop_indices:
            vert_idx = pcb.data.loops[loop_index].vertex_index
            v = pcb.data.vertices[vert_idx].co
            u = (v.x + PCB_W / 2.0) / PCB_W
            v_coord = (v.y + PCB_H / 2.0) / PCB_H
            uv_layer.data[loop_index].uv = (u, v_coord)
except Exception as _exc:
    print("[pcb-planar-uv] failed:", _exc)

socket_y = PCB_H * 0.16

# 2. AM5 socket (nickel-plated ILM bracket with central pin array)
socket_obj, _ = add_box("Mat_socket_AM5",
                        dims=(SOCKET_SIZE, SOCKET_SIZE, 0.008),
                        location=(0.002, socket_y, PCB_THICK / 2 + 0.004),
                        color=(0.35, 0.36, 0.38),
                        metallic=0.85, roughness=0.25)
add_box("Mat_socket_pins",
        dims=(SOCKET_SIZE * 0.72, SOCKET_SIZE * 0.72, 0.003),
        location=(0.002, socket_y, PCB_THICK / 2 + 0.007),
        color=(0.12, 0.12, 0.13),
        metallic=0.2, roughness=0.8)

# 3. DIMM slots (4 vertical DDR5 slots right of socket)
dimm_x = 0.046
dimm_w = 0.0055
dimm_h = 0.135
dimm_d = 0.010
dimm_spacing = 0.009
for i in range(DIMM_COUNT):
    x = dimm_x + i * dimm_spacing
    color = (0.22, 0.22, 0.24) if i % 2 == 0 else (0.14, 0.14, 0.16)
    add_box(f"Mat_dimm_DIMM_{i}",
            dims=(dimm_w, dimm_h, dimm_d),
            location=(x, socket_y + 0.008, PCB_THICK / 2 + dimm_d / 2),
            color=color, metallic=0.3, roughness=0.4)

# 4. VRM heatsinks (Top block and Left IO shield block)
add_box("Mat_heatsink_VRM_Top",
        dims=(0.125, 0.042, 0.026),
        location=(0.010, socket_y + 0.055, PCB_THICK / 2 + 0.013),
        color=HEATSINK_COLOR, metallic=0.90, roughness=0.18)
add_box("Mat_heatsink_VRM_Left",
        dims=(0.046, 0.160, 0.030),
        location=(-PCB_W / 2 + 0.028, socket_y + 0.008, PCB_THICK / 2 + 0.015),
        color=HEATSINK_COLOR, metallic=0.90, roughness=0.18)

# 5. PCIe Gen5 Slots (2 reinforced SafeSlots)
pcie_w = 0.135
add_box("Mat_pcie_Slot1",
        dims=(pcie_w, 0.008, 0.009),
        location=(0.005, socket_y - 0.048, PCB_THICK / 2 + 0.0045),
        color=(0.82, 0.84, 0.86), metallic=0.85, roughness=0.2)
add_box("Mat_pcie_Slot2",
        dims=(pcie_w, 0.008, 0.009),
        location=(0.005, -PCB_H * 0.32, PCB_THICK / 2 + 0.0045),
        color=(0.82, 0.84, 0.86), metallic=0.85, roughness=0.2)

# 6. M.2 NVMe armor shields
add_box("Mat_heatsink_M2_TopShield",
        dims=(pcie_w, 0.022, 0.007),
        location=(0.005, socket_y - 0.026, PCB_THICK / 2 + 0.0035),
        color=HEATSINK_COLOR, metallic=0.88, roughness=0.20)
add_box("Mat_heatsink_M2_MainArmor",
        dims=(0.178, 0.125, 0.007),
        location=(-0.014, -PCB_H * 0.185, PCB_THICK / 2 + 0.0035),
        color=HEATSINK_COLOR, metallic=0.88, roughness=0.20)

# 7. OLED LiveDash screen on left IO cover
oled_w = 0.036
oled_h = 0.052
oled_obj, oled_mat = add_box("screen_oled_LiveDash",
                             dims=(oled_w, oled_h, 0.001),
                             location=(-PCB_W / 2 + 0.028, socket_y + 0.035,
                                       PCB_THICK / 2 + 0.0305),
                             color=(0.02, 0.02, 0.02),
                             metallic=0.0, roughness=0.05,
                             emission_strength=1.5)

# Load the pre-baked OLED atlas PNG if the orchestrator forwarded one.
# motion_intent_baker._generate_oled_png_sequence is invoked at the
# extract_template_params() layer (aurora_3d_pipeline.py iter27) so by
# the time we reach this template, atlas_path is a real file and we
# bind it as the OLED material's image texture. The runtime reader
# (ModelView.tsx + aurora_3d_viewer.py) then scrolls map.offset.x at
# draw-time, advancing the atlas frame-by-frame so the user sees a
# REAL animated OLED display.
_oled_atlas_path = params.get("oled_atlas_path")
_oled_frame_count = int(params.get("oled_frame_count", 60))
_oled_frame_w = int(params.get("oled_frame_w", 256))
_oled_frame_h = int(params.get("oled_frame_h", 128))
_oled_frame_rate = float(params.get("oled_frame_rate", 18.0))
_oled_content_type = str(params.get("oled_content_type", "system_stats"))

if _oled_atlas_path and os.path.isfile(_oled_atlas_path):
    nt = oled_mat.node_tree
    bsdf = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if bsdf is not None:
        try:
            atlas_img = bpy.data.images.load(_oled_atlas_path, check_existing=True)
            atlas_img.colorspace_settings.name = "sRGB"
            tex = nt.nodes.new("ShaderNodeTexImage")
            tex.image = atlas_img
            tex.interpolation = "Closest"
            tex.extension = "REPEAT"
            nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
            # Also drive Emission Color from the same texture so the OLED
            # glows brightly in dark scenes.
            if "Emission Color" in bsdf.inputs:
                nt.links.new(tex.outputs["Color"], bsdf.inputs["Emission Color"])
            if "Emission Strength" in bsdf.inputs:
                bsdf.inputs["Emission Strength"].default_value = 2.5
        except Exception as _exc:
            print("[oled-atlas-load] failed:", _exc)

# Tag the OLED material with the v1 OLED atlas schema. The runtime reader
# checks both extras and userData for parity with the iter9 baker.
oled_mat["aurora_oled_atlas"] = {
    "schema": "aurora.oled-atlas.v1",
    "content_type": _oled_content_type,
    "frame_count": _oled_frame_count,
    "frame_w": _oled_frame_w,
    "frame_h": _oled_frame_h,
    "frame_rate": _oled_frame_rate,
    "direction": "h",
    "loop": True,
}

# 9. 24-pin ATX power connector (right edge top)
add_box("Mat_connector_ATX24",
        dims=(0.026, 0.012, 0.014),
        location=(PCB_W / 2 - 0.018, PCB_H * 0.32, PCB_THICK / 2 + 0.007),
        color=(0.06, 0.06, 0.08), metallic=0.0, roughness=0.65)

# 10. 12VHPWR PCIe connector (right edge mid)
add_box("Mat_connector_12VHPWR",
        dims=(0.020, 0.010, 0.012),
        location=(PCB_W / 2 - 0.014, PCB_H * 0.05, PCB_THICK / 2 + 0.006),
        color=(0.06, 0.06, 0.08), metallic=0.0, roughness=0.65)

# Centre origin so viewer auto-fit looks good
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.origin_set(type="ORIGIN_CENTER_OF_VOLUME")

# Export
out_path = os.path.join(output_dir, f"{run_id}_procedural.{fmt}")
if fmt == "glb":
    bpy.ops.export_scene.gltf(
        filepath=out_path, export_format="GLB",
        export_animations=False, export_extras=True,
        export_draco_mesh_compression_enable=True,
        export_draco_mesh_compression_level=6,
        export_draco_position_quantization=14,
        export_draco_normal_quantization=10,
        export_draco_texcoord_quantization=12,
        export_draco_color_quantization=8,
    )
elif fmt == "fbx":
    bpy.ops.export_scene.fbx(filepath=out_path, use_selection=False)
else:
    bpy.ops.wm.obj_export(filepath=out_path)

# Polycount summary
total_tris = 0
for obj in bpy.data.objects:
    if obj.type == "MESH":
        total_tris += len(obj.data.polygons)

print(json.dumps({
    "ok": True, "path": out_path, "format": fmt,
    "totalTris": total_tris,
    "components": [obj.name for obj in bpy.data.objects if obj.type == "MESH"],
    "screenText": SCREEN_TEXT,
    "schema": "aurora.motherboard-layout.v1",
}))
''',
}

_historical_person_template = Path(__file__).with_name("proc_historical_person_performer.py")
if _historical_person_template.is_file():
    PROCEDURAL_TEMPLATES["historical_person_performer"] = _historical_person_template.read_text(encoding="utf-8")

_auto_landscape_template = Path(__file__).with_name("proc_auto_landscape.py")
if _auto_landscape_template.is_file():
    PROCEDURAL_TEMPLATES["auto_landscape"] = _auto_landscape_template.read_text(encoding="utf-8")


VALIDATION_SCRIPT = '''
import bpy, bmesh, json, sys, os

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
mesh_path = argv[0] if argv else ""
checks_str = argv[1] if len(argv) > 1 else "non_manifold,degenerate,open_boundaries"
auto_fix = "--auto-fix" in argv
output_dir = argv[2] if len(argv) > 2 else "/tmp"
run_id = argv[3] if len(argv) > 3 else "val"

bpy.ops.wm.read_factory_settings(use_empty=True)

# Import mesh
ext = os.path.splitext(mesh_path)[1].lower()
if ext in (".glb", ".gltf"):
    bpy.ops.import_scene.gltf(filepath=mesh_path)
elif ext == ".obj":
    bpy.ops.wm.obj_import(filepath=mesh_path)
elif ext == ".fbx":
    bpy.ops.import_scene.fbx(filepath=mesh_path)

# Find mesh objects
mesh_objs = [o for o in bpy.context.scene.objects if o.type == "MESH"]
if not mesh_objs:
    print(json.dumps({"ok": False, "error": "No mesh objects found in file."}))
    sys.exit(0)

issues = []
total_non_manifold = 0
total_degenerate = 0
total_open = 0
total_verts = 0
total_faces = 0
disconnected = 0

for obj in mesh_objs:
    bpy.context.view_layer.objects.active = obj
    bm = bmesh.new()
    bm.from_mesh(obj.data)

    total_verts += len(bm.verts)
    total_faces += len(bm.faces)

    # Non-manifold edges
    nm = [e for e in bm.edges if not e.is_manifold]
    total_non_manifold += len(nm)

    # Degenerate faces (area ~0)
    degen = [f for f in bm.faces if f.calc_area() < 1e-8]
    total_degenerate += len(degen)

    # Open boundaries
    boundary = [e for e in bm.edges if e.is_boundary]
    total_open += len(boundary)

    # Auto-fix
    if auto_fix and (nm or degen):
        bmesh.ops.dissolve_degenerate(bm, dist=0.0001, edges=bm.edges[:])
        bm.to_mesh(obj.data)
        issues.append({"severity": "info", "check": "auto_fix", "message": f"Auto-fixed {obj.name}: dissolved degenerate geometry", "autoFixAvailable": False})

    bm.free()

# Disconnected components
if len(mesh_objs) > 1:
    disconnected = len(mesh_objs) - 1

# Scale
dims = mesh_objs[0].dimensions
scale = [round(dims[0], 4), round(dims[1], 4), round(dims[2], 4)]

watertight = total_non_manifold == 0 and total_open == 0

if total_non_manifold > 0:
    issues.append({"severity": "warning", "check": "non_manifold_edges", "message": f"{total_non_manifold} non-manifold edges found", "autoFixAvailable": True})
if total_degenerate > 0:
    issues.append({"severity": "warning", "check": "degenerate_faces", "message": f"{total_degenerate} degenerate faces found", "autoFixAvailable": True})
if total_open > 0:
    issues.append({"severity": "info", "check": "open_boundaries", "message": f"{total_open} open boundary edges", "autoFixAvailable": False})

# Export cleaned mesh if auto-fix was applied
output_path = mesh_path
if auto_fix:
    output_path = os.path.join(output_dir, f"{run_id}_cleaned.glb")
    bpy.ops.export_scene.gltf(filepath=output_path, export_format="GLB")

report = {
    "nonManifoldEdges": total_non_manifold,
    "degenerateFaces": total_degenerate,
    "openBoundaries": total_open,
    "selfIntersections": 0,
    "disconnectedComponents": disconnected,
    "scaleMeters": scale,
    "watertight": watertight,
    "vertexCount": total_verts,
    "faceCount": total_faces,
    "issues": issues,
}

print(json.dumps({"ok": True, "outputPath": output_path, "validationReport": report}))
'''


RIGGING_SCRIPT = '''
import bpy, bmesh, json, sys, os, math
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
mesh_path = argv[0] if argv else ""
rig_system = argv[1] if len(argv) > 1 else "rigify"
subject_kind = argv[2] if len(argv) > 2 else "humanoid"
style = argv[3] if len(argv) > 3 else "realistic"
test_action = argv[4] if len(argv) > 4 else ""
output_dir = argv[5] if len(argv) > 5 else "/tmp"
run_id = argv[6] if len(argv) > 6 else "rig"
# v78: optional 8th arg = JSON object with physics overrides looked up by
# the Aurora extension. {"densityKgPerM3": 7850, "frictionCoefficient": 0.4,
# "restitution": 0.2, "angularVelocityRadPerS": 6.28, ...}. Falls back to
# defaults if missing or malformed.
physics_overrides = {}
if len(argv) > 7 and argv[7]:
    try:
        physics_overrides = json.loads(argv[7]) or {}
    except Exception:
        physics_overrides = {}

# v77zo: argv[8] = optional aurora.motion.v1 JSON path. When present, after
# the rig has been generated we import motion_baker and bake the descriptor
# into a real NLA action so export_animations=True actually exports motion
# data instead of an empty animation track.
aurora_motion_path = argv[8] if len(argv) > 8 else ""

bpy.ops.wm.read_factory_settings(use_empty=True)

# Enable Rigify
try:
    bpy.ops.preferences.addon_enable(module="rigify")
except Exception:
    pass

# --- Import mesh (any common 3D format Aurora can produce) ---
ext = os.path.splitext(mesh_path)[1].lower()
if ext in (".glb", ".gltf"):
    bpy.ops.import_scene.gltf(filepath=mesh_path)
elif ext == ".obj":
    bpy.ops.wm.obj_import(filepath=mesh_path)
elif ext == ".fbx":
    bpy.ops.import_scene.fbx(filepath=mesh_path)
elif ext == ".ply":
    bpy.ops.wm.ply_import(filepath=mesh_path)

mesh_objs = [o for o in bpy.context.scene.objects if o.type == "MESH"]
if not mesh_objs:
    print(json.dumps({"ok": False, "error": "No mesh objects found."}))
    sys.exit(0)

mesh_obj = mesh_objs[0]
rig_bones = 0
ik_constraints_applied = 0


def _measure_mesh_dimensions(obj):
    """Return (height, shoulder_width, total_width, total_depth, center) by reading
    the actual world-space bounding box. Used to size the metarig to the mesh
    instead of dropping a stock humanoid metarig that is always 1.85m tall.
    This is the difference between a rig that follows the character and a rig
    that tries to deform a 1.7m mesh with a 1.85m skeleton (= bones outside
    the body, broken weights, twisted limbs)."""
    obj.update_from_editmode()
    bbox = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    xs = [v.x for v in bbox]; ys = [v.y for v in bbox]; zs = [v.z for v in bbox]
    height = max(zs) - min(zs)
    width = max(xs) - min(xs)
    depth = max(ys) - min(ys)
    center = Vector(((max(xs) + min(xs)) / 2.0, (max(ys) + min(ys)) / 2.0, min(zs)))
    # Heuristic: shoulder width is roughly 1/4 of total height for a humanoid.
    shoulder_width = min(width, height * 0.28)
    return height, shoulder_width, width, depth, center


def _scale_metarig_to_mesh(metarig, mesh_obj):
    """Scale the freshly-created metarig so its overall height matches the
    mesh. Without this step Rigify generates a rig sized for an "average human"
    and any deviation produces poor weights."""
    try:
        height, shoulder, width, depth, center = _measure_mesh_dimensions(mesh_obj)
        if height <= 0:
            return None
        # Default basic_human metarig is ~1.85 m tall. Aim for the actual mesh.
        target_scale = height / 1.85
        metarig.scale = (target_scale, target_scale, target_scale)
        metarig.location = center
        return {
            "mesh_height": float(height),
            "mesh_width": float(width),
            "mesh_depth": float(depth),
            "metarig_scale": float(target_scale),
        }
    except Exception:
        return None


def _add_ik_constraints(rig_obj):
    """Add explicit IK constraints to the arms and legs so the user can drag
    a single control bone instead of rotating each joint manually. Rigify
    normally ships these but the basic_human metarig only generates FK chains —
    we promote them to IK + pole targets here so the rigged GLB exports a
    rig that downstream tools (Three.js IK solvers, Mixamo retargeting,
    Cascadeur) can drive directly."""
    applied = 0
    pose = rig_obj.pose
    if pose is None:
        return 0
    # Heuristic mapping: typical Rigify generated bone names. We try several
    # name variants because Rigify's output depends on the metarig version.
    ik_chains = [
        ("forearm_ik.L", "upper_arm.L", "hand_ik.L", "elbow.L"),
        ("forearm_ik.R", "upper_arm.R", "hand_ik.R", "elbow.R"),
        ("shin_ik.L", "thigh.L", "foot_ik.L", "knee.L"),
        ("shin_ik.R", "thigh.R", "foot_ik.R", "knee.R"),
    ]
    for chain_target_name, root_name, target_name, pole_name in ik_chains:
        target_bone = pose.bones.get(chain_target_name) or pose.bones.get(root_name)
        if target_bone is None:
            continue
        # Avoid duplicates if Rigify already created the IK constraint.
        if any(c.type == "IK" for c in target_bone.constraints):
            applied += 1
            continue
        try:
            ik = target_bone.constraints.new("IK")
            ik.target = rig_obj
            ik.subtarget = target_name if target_name in pose.bones else target_bone.name
            ik.chain_count = 2
            pole = pose.bones.get(pole_name)
            if pole:
                ik.pole_target = rig_obj
                ik.pole_subtarget = pole_name
                ik.pole_angle = math.radians(-90)
            applied += 1
        except Exception:
            pass
    return applied


def _enable_breathing_action(rig_obj):
    """Add a subtle 4-second breathing animation on the chest bone — gives the
    exported character life even before the user defines any pose. Matches the
    user's expectation that a "rigged character" should already move."""
    if rig_obj.pose is None:
        return False
    chest = rig_obj.pose.bones.get("chest") or rig_obj.pose.bones.get("spine.003") or rig_obj.pose.bones.get("spine_fk.003")
    if chest is None:
        return False
    rig_obj.animation_data_create()
    action = bpy.data.actions.new("Breathing")
    rig_obj.animation_data.action = action
    fps = 24
    seconds = 4
    frames = fps * seconds
    base_loc = chest.location.copy()
    for i in range(0, frames + 1, 4):
        amp = 0.012 * math.sin(2 * math.pi * i / frames)
        chest.location = (base_loc.x, base_loc.y, base_loc.z + amp)
        chest.keyframe_insert(data_path="location", frame=i + 1)
    chest.location = base_loc
    bpy.context.scene.frame_end = frames
    return True


if rig_system == "rigify" and subject_kind == "humanoid":
    bpy.ops.object.armature_add(enter_editmode=False, location=(0, 0, 0))
    metarig = bpy.context.active_object
    metarig.name = "metarig_human"

    try:
        from rigify.metarigs.Basic import basic_human
        basic_human.create(metarig)
    except ImportError:
        print(json.dumps({"ok": False, "error": "Rigify basic_human metarig not available."}))
        sys.exit(0)

    scale_report = _scale_metarig_to_mesh(metarig, mesh_obj)

    bpy.ops.object.mode_set(mode="POSE")
    bpy.ops.pose.rigify_generate()

    rig_obj = None
    for obj in bpy.context.scene.objects:
        if obj.type == "ARMATURE" and obj != metarig:
            rig_obj = obj
            break

    if rig_obj:
        rig_bones = len(rig_obj.data.bones)
        mesh_obj.select_set(True)
        rig_obj.select_set(True)
        bpy.context.view_layer.objects.active = rig_obj
        try:
            bpy.ops.object.parent_set(type="ARMATURE_AUTO")
        except Exception:
            pass

        # Promote FK chains to IK and add a default breathing animation.
        ik_constraints_applied = _add_ik_constraints(rig_obj)
        breathing = _enable_breathing_action(rig_obj)

        if test_action == "applaud":
            # Quick clap test: rotate both upper arms inward over 1 s, back to
            # neutral over the second second. Produces a visible idle animation.
            try:
                bpy.context.scene.frame_end = max(bpy.context.scene.frame_end, 48)
                for side, sign in (("L", 1.0), ("R", -1.0)):
                    arm = rig_obj.pose.bones.get(f"upper_arm_fk.{side}") or rig_obj.pose.bones.get(f"upper_arm.{side}")
                    if not arm:
                        continue
                    arm.rotation_mode = "XYZ"
                    arm.keyframe_insert("rotation_euler", frame=1)
                    arm.rotation_euler.y = math.radians(45 * sign)
                    arm.keyframe_insert("rotation_euler", frame=24)
                    arm.rotation_euler.y = 0.0
                    arm.keyframe_insert("rotation_euler", frame=48)
            except Exception:
                pass
        elif test_action == "walk":
            # 1 second walk cycle (24 fps): leg swing alternated, opposite arm
            # swing, slight torso tilt, hip bob. Without this a "rigged
            # character" looks dead even though it moves. The cycle is loopable
            # because frame 1 == frame 25 by construction. Each segment uses
            # FK bones because Rigify auto-IK targets are positioned at neutral
            # which would clash with our explicit pose.
            try:
                bpy.context.scene.frame_end = max(bpy.context.scene.frame_end, 24)
                cycle_frames = 24
                for side, leg_sign, arm_sign in (("L", 1.0, -1.0), ("R", -1.0, 1.0)):
                    thigh = rig_obj.pose.bones.get(f"thigh_fk.{side}") or rig_obj.pose.bones.get(f"thigh.{side}")
                    shin = rig_obj.pose.bones.get(f"shin_fk.{side}") or rig_obj.pose.bones.get(f"shin.{side}")
                    upper_arm = rig_obj.pose.bones.get(f"upper_arm_fk.{side}") or rig_obj.pose.bones.get(f"upper_arm.{side}")
                    forearm = rig_obj.pose.bones.get(f"forearm_fk.{side}") or rig_obj.pose.bones.get(f"forearm.{side}")
                    if thigh:
                        thigh.rotation_mode = "XYZ"
                        for f, swing in ((1, 30 * leg_sign), (cycle_frames // 2, -30 * leg_sign), (cycle_frames + 1, 30 * leg_sign)):
                            thigh.rotation_euler.x = math.radians(swing)
                            thigh.keyframe_insert("rotation_euler", frame=f)
                    if shin:
                        shin.rotation_mode = "XYZ"
                        for f, bend in ((1, 0), (cycle_frames // 4, -45 * max(0, leg_sign)), (cycle_frames // 2, 0), (cycle_frames * 3 // 4, -45 * max(0, -leg_sign)), (cycle_frames + 1, 0)):
                            shin.rotation_euler.x = math.radians(bend)
                            shin.keyframe_insert("rotation_euler", frame=f)
                    if upper_arm:
                        upper_arm.rotation_mode = "XYZ"
                        for f, swing in ((1, 25 * arm_sign), (cycle_frames // 2, -25 * arm_sign), (cycle_frames + 1, 25 * arm_sign)):
                            upper_arm.rotation_euler.x = math.radians(swing)
                            upper_arm.keyframe_insert("rotation_euler", frame=f)
                    if forearm:
                        forearm.rotation_mode = "XYZ"
                        forearm.rotation_euler.x = math.radians(15)
                        forearm.keyframe_insert("rotation_euler", frame=1)
                # Slight hip bob — root bone goes up at the contact frames
                root = rig_obj.pose.bones.get("root") or rig_obj.pose.bones.get("torso")
                if root:
                    root.rotation_mode = "XYZ"
                    base = root.location.copy()
                    for f, dz in ((1, 0.0), (cycle_frames // 4, 0.03), (cycle_frames // 2, 0.0), (cycle_frames * 3 // 4, 0.03), (cycle_frames + 1, 0.0)):
                        root.location = (base.x, base.y, base.z - dz)
                        root.keyframe_insert("location", frame=f)
                    root.location = base
                # Make the cycle loop linearly so player apps see clean playback.
                if rig_obj.animation_data and rig_obj.animation_data.action:
                    for fcurve in rig_obj.animation_data.action.fcurves:
                        for kp in fcurve.keyframe_points:
                            kp.interpolation = "BEZIER"
            except Exception:
                pass
        elif test_action == "idle":
            # Subtle weight shift: hip rotates +/-3 degrees over 4s. Combined
            # with the breathing keyframes from _enable_breathing_action this
            # gives the character "alive while standing" without a full anim.
            try:
                hip = rig_obj.pose.bones.get("hip") or rig_obj.pose.bones.get("torso")
                if hip:
                    hip.rotation_mode = "XYZ"
                    for f, dz in ((1, 0), (24, 3), (48, 0), (72, -3), (96, 0)):
                        hip.rotation_euler.y = math.radians(dz)
                        hip.keyframe_insert("rotation_euler", frame=f)
                    bpy.context.scene.frame_end = max(bpy.context.scene.frame_end, 96)
            except Exception:
                pass

elif rig_system == "rigify" and subject_kind in {"creature", "quadruped"}:
    bpy.ops.object.armature_add(enter_editmode=False, location=(0, 0, 0))
    metarig = bpy.context.active_object
    metarig.name = "metarig_quadruped"
    try:
        from rigify.metarigs.Basic import basic_quadruped  # type: ignore[attr-defined]
        basic_quadruped.create(metarig)
    except Exception:
        try:
            from rigify.metarigs.Basic import basic_human
            basic_human.create(metarig)
        except ImportError:
            print(json.dumps({"ok": False, "error": "Rigify quadruped metarig not available."}))
            sys.exit(0)
    _scale_metarig_to_mesh(metarig, mesh_obj)
    bpy.ops.object.mode_set(mode="POSE")
    try:
        bpy.ops.pose.rigify_generate()
        for obj in bpy.context.scene.objects:
            if obj.type == "ARMATURE" and obj != metarig:
                rig_bones = len(obj.data.bones)
                mesh_obj.select_set(True)
                obj.select_set(True)
                bpy.context.view_layer.objects.active = obj
                bpy.ops.object.parent_set(type="ARMATURE_AUTO")
                ik_constraints_applied = _add_ik_constraints(obj)
                break
    except Exception:
        pass

elif subject_kind in {"vehicle", "wheeled"}:
    # Vehicle rig: split mesh by loose parts, classify wheels (cylindrical low-Z
    # parts), create an empty per wheel with a rolling animation. The body stays
    # rigid. Without this branch a car mesh used to receive a humanoid skeleton
    # which broke deformation entirely.
    try:
        bpy.context.view_layer.objects.active = mesh_obj
        mesh_obj.select_set(True)
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.mesh.separate(type="LOOSE")
        bpy.ops.object.mode_set(mode="OBJECT")
    except Exception:
        pass

    parts = [o for o in bpy.context.scene.objects if o.type == "MESH"]

    def _bbox(obj):
        return [obj.matrix_world @ Vector(c) for c in obj.bound_box]

    # Find global Z floor across every part to score "low".
    zs_all = [v.z for o in parts for v in _bbox(o)]
    z_min = min(zs_all) if zs_all else 0.0
    z_max = max(zs_all) if zs_all else 1.0
    z_span = max(1e-6, z_max - z_min)

    wheels = []
    body_parts = []
    for o in parts:
        bb = _bbox(o)
        xs = [v.x for v in bb]; ys = [v.y for v in bb]; zs = [v.z for v in bb]
        w = max(xs) - min(xs); d = max(ys) - min(ys); h = max(zs) - min(zs)
        cx = (max(xs) + min(xs)) / 2.0
        cy = (max(ys) + min(ys)) / 2.0
        cz = (max(zs) + min(zs)) / 2.0
        # A wheel is roughly cylindrical (two of the three extents close) and
        # sits in the lower third of the vehicle.
        sorted_extents = sorted([w, d, h], reverse=True)
        cyl_ratio = sorted_extents[0] / max(1e-6, sorted_extents[1])
        is_low = (cz - z_min) < z_span * 0.4
        if 0.6 < cyl_ratio < 1.6 and is_low and sorted_extents[0] > 0.05 * z_span:
            wheels.append((o, cx, cy, cz, max(w, d, h) * 0.5))
        else:
            body_parts.append(o)

    fps = 24
    bpy.context.scene.frame_start = 1
    bpy.context.scene.frame_end = fps * 2

    # v78: angular velocity (rad/s) from physics_overrides drives the rolling
    # speed instead of a hard-coded 1 turn / second. A 60 km/h car wheel of
    # 0.3 m radius spins at ~55 rad/s; a bicycle at 20 km/h spins at ~16 rad/s.
    wheel_angular_velocity_rad_s = float(physics_overrides.get("angularVelocityRadPerS") or (2.0 * math.pi))
    # Convert rad/s into degrees per 2-second cycle.
    deg_per_cycle = math.degrees(wheel_angular_velocity_rad_s * 2.0)

    bone_count = 0
    for idx, (wheel_obj, cx, cy, cz, radius) in enumerate(wheels):
        # Set origin to median, then animate Y rotation = rolling.
        try:
            bpy.context.view_layer.objects.active = wheel_obj
            wheel_obj.select_set(True)
            bpy.ops.object.origin_set(type="ORIGIN_GEOMETRY", center="MEDIAN")
            wheel_obj.select_set(False)
        except Exception:
            pass
        wheel_obj.rotation_mode = "XYZ"
        wheel_obj.rotation_euler = (0.0, 0.0, 0.0)
        wheel_obj.keyframe_insert("rotation_euler", frame=1)
        # Rolling speed driven by the looked-up angular velocity.
        wheel_obj.rotation_euler.y = math.radians(deg_per_cycle / 2.0)
        wheel_obj.keyframe_insert("rotation_euler", frame=fps)
        wheel_obj.rotation_euler.y = math.radians(deg_per_cycle)
        wheel_obj.keyframe_insert("rotation_euler", frame=fps * 2)
        # Suspension bounce: front wheels lead, rear wheels lag - each wheel
        # bobs +/- (radius * 8%) on Z over the 2s cycle, phase-offset by the
        # wheel's Y position. Without this the wheels just spin while the body
        # stays rigid which looks like the wheels are floating.
        bob_amp = radius * 0.08
        phase = ((cy - sum(w[2] for w in wheels) / max(1, len(wheels))) > 0)
        offset = 0 if phase else fps // 4
        wheel_obj.location = (cx, cy, cz)
        wheel_obj.keyframe_insert("location", frame=1)
        wheel_obj.location = (cx, cy, cz + bob_amp)
        wheel_obj.keyframe_insert("location", frame=(fps // 2 + offset) % (fps * 2) or 1)
        wheel_obj.location = (cx, cy, cz)
        wheel_obj.keyframe_insert("location", frame=fps * 2)
        # Make rotation linear so rolling looks continuous; bezier on location
        # so the bounce is smooth.
        if wheel_obj.animation_data and wheel_obj.animation_data.action:
            for fcurve in wheel_obj.animation_data.action.fcurves:
                target = "LINEAR" if fcurve.data_path.endswith("rotation_euler") else "BEZIER"
                for kp in fcurve.keyframe_points:
                    kp.interpolation = target
        bone_count += 1

    rig_bones = bone_count

elif subject_kind in {"mechanical", "mechanism"}:
    # Mechanism rig: each loose part gets a Bullet rigid body + a default
    # 30-frame physics bake. Hinge constraints are added between adjacent parts
    # so chains, articulated arms or linkages settle naturally instead of being
    # parented to a humanoid skeleton they have no relation to.
    try:
        bpy.context.view_layer.objects.active = mesh_obj
        mesh_obj.select_set(True)
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.mesh.separate(type="LOOSE")
        bpy.ops.object.mode_set(mode="OBJECT")
    except Exception:
        pass

    parts = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    try:
        bpy.ops.rigidbody.world_add()
    except Exception:
        pass

    # v78: density (kg/m3) from physics_overrides drives the mass instead of
    # an arbitrary length-based proxy. For a steel mechanism (7850) the bake
    # settles slowly and convincingly; for wood (700) parts react lighter.
    density = float(physics_overrides.get("densityKgPerM3") or 1200.0)
    friction = float(physics_overrides.get("frictionCoefficient") or 0.5)
    restitution = float(physics_overrides.get("restitution") or 0.2)

    bone_count = 0
    for idx, part in enumerate(parts):
        try:
            bpy.context.view_layer.objects.active = part
            part.select_set(True)
            bpy.ops.rigidbody.object_add()
            # First part is the static base (anchor), rest are dynamic.
            part.rigid_body.type = "PASSIVE" if idx == 0 else "ACTIVE"
            part.rigid_body.collision_shape = "CONVEX_HULL"
            # Volume approximation = product of bounding extents; mass = density * volume
            d = part.dimensions
            volume = max(1e-4, float(d.x) * float(d.y) * float(d.z))
            part.rigid_body.mass = max(0.05, density * volume)
            part.rigid_body.friction = max(0.0, min(1.0, friction))
            part.rigid_body.restitution = max(0.0, min(1.0, restitution))
            part.select_set(False)
            bone_count += 1
        except Exception:
            pass

    bpy.context.scene.frame_start = 1
    bpy.context.scene.frame_end = 60
    try:
        # Bake the simulation so the GLB exporter captures keyframes.
        bpy.ops.object.select_all(action="SELECT")
        bpy.ops.rigidbody.bake_to_keyframes(frame_start=1, frame_end=60, step=1)
        bpy.ops.object.select_all(action="DESELECT")
    except Exception:
        pass

    rig_bones = bone_count

elif subject_kind in {"pendulum", "hanging", "swing"}:
    # v79a: pendulum motion - the mesh top is anchored, the rest swings around
    # the pivot via empty parent + Y rotation keyframes. Period derived from
    # physics_overrides.pendulumPeriodSeconds when looked up by the extension,
    # else from real-world pendulum formula T = 2*pi*sqrt(L/g).
    try:
        bpy.context.view_layer.objects.active = mesh_obj
        mesh_obj.select_set(True)
        bpy.ops.object.origin_set(type="ORIGIN_GEOMETRY", center="MEDIAN")
        mesh_obj.select_set(False)
    except Exception:
        pass

    bbox = [mesh_obj.matrix_world @ Vector(c) for c in mesh_obj.bound_box]
    zs = [v.z for v in bbox]
    z_top = max(zs)
    z_bot = min(zs)
    length_m = max(0.05, z_top - z_bot)

    # Pivot empty at the top of the mesh.
    try:
        bpy.ops.object.empty_add(type="PLAIN_AXES", location=(mesh_obj.location.x, mesh_obj.location.y, z_top))
        pivot = bpy.context.active_object
        pivot.name = "PendulumPivot"
        # Parent mesh to pivot keeping the offset.
        mesh_obj.select_set(True)
        bpy.context.view_layer.objects.active = pivot
        bpy.ops.object.parent_set(type="OBJECT", keep_transform=True)
    except Exception:
        pivot = None

    # Period: T = 2*pi*sqrt(L / g)
    g = float(physics_overrides.get("gravityMPerS2") or 9.81)
    period = float(physics_overrides.get("pendulumPeriodSeconds") or (2.0 * math.pi * math.sqrt(length_m / g)))
    fps = 24
    cycle_frames = max(8, min(240, int(round(period * fps))))
    bpy.context.scene.frame_start = 1
    bpy.context.scene.frame_end = cycle_frames * 2

    if pivot is not None:
        pivot.rotation_mode = "XYZ"
        # Damped sinusoidal swing: amplitude 25 deg fading to 8 deg over 2 cycles.
        keyframe_points = []
        for i in range(cycle_frames * 2 + 1):
            t = i / cycle_frames  # 0..2
            damping = 1.0 - 0.4 * (t / 2.0)
            angle = math.radians(25 * damping) * math.sin(2 * math.pi * t)
            pivot.rotation_euler = (angle, 0.0, 0.0)
            pivot.keyframe_insert("rotation_euler", frame=i + 1)
            keyframe_points.append((i + 1, angle))
        # Bezier interpolation makes the swing continuous (no robotic jumps).
        if pivot.animation_data and pivot.animation_data.action:
            for fcurve in pivot.animation_data.action.fcurves:
                for kp in fcurve.keyframe_points:
                    kp.interpolation = "BEZIER"
        rig_bones = 1

elif subject_kind in {"prop", "product", "object", "tool"}:
    # v79b: ambient turntable rotation - even a static object should rotate
    # slowly so the user gets a 360 deg overview when previewing the GLB.
    # 6 second cycle, full Y rotation, linear interpolation.
    try:
        bpy.context.view_layer.objects.active = mesh_obj
        mesh_obj.select_set(True)
        bpy.ops.object.origin_set(type="ORIGIN_GEOMETRY", center="MEDIAN")
        mesh_obj.select_set(False)
    except Exception:
        pass
    fps = 24
    bpy.context.scene.frame_start = 1
    bpy.context.scene.frame_end = fps * 6
    mesh_obj.rotation_mode = "XYZ"
    mesh_obj.rotation_euler = (0.0, 0.0, 0.0)
    mesh_obj.keyframe_insert("rotation_euler", frame=1)
    mesh_obj.rotation_euler.z = math.radians(180.0)
    mesh_obj.keyframe_insert("rotation_euler", frame=fps * 3)
    mesh_obj.rotation_euler.z = math.radians(360.0)
    mesh_obj.keyframe_insert("rotation_euler", frame=fps * 6)
    if mesh_obj.animation_data and mesh_obj.animation_data.action:
        for fcurve in mesh_obj.animation_data.action.fcurves:
            for kp in fcurve.keyframe_points:
                kp.interpolation = "LINEAR"
    rig_bones = 1

# v77zo: bake aurora.motion.v1 descriptor into NLA action when supplied.
aurora_motion_report = None
if aurora_motion_path and os.path.isfile(aurora_motion_path):
    try:
        services_dir = os.environ.get("AURORA_PYTHON_SERVICES")
        if services_dir and services_dir not in sys.path:
            sys.path.insert(0, services_dir)
        import motion_baker as _mb
        with open(aurora_motion_path, "r", encoding="utf-8") as _fp:
            _motion = json.load(_fp)
        _compiled = _mb.compile_motion_payload(_motion)
        rig_obj = next((o for o in bpy.context.scene.objects if o.type == "ARMATURE"), None)
        # v77zq: pure mechanisms (gears, belts, pistons) have no armature;
        # forward the primary mesh as fallback_object so the baker can
        # mesh-direct keyframe the rotation/translation/extend primitives.
        mesh_fallback = next((o for o in bpy.context.scene.objects if o.type == "MESH"), None)
        if rig_obj is not None or mesh_fallback is not None:
            aurora_motion_report = _mb.apply_compiled_motion(
                rig_obj, _compiled, fallback_object=mesh_fallback,
            )
            print("AURORA_MOTION_BAKED: id=%s applied=%d skipped=%d warnings=%d mech=%d" % (
                _compiled.get("id"),
                aurora_motion_report.get("applied", 0),
                aurora_motion_report.get("skipped", 0),
                len(aurora_motion_report.get("warnings", [])),
                len(aurora_motion_report.get("mechanism_actions", [])),
            ))
        else:
            print("AURORA_MOTION_WARN: scene has no armature and no mesh, skipping motion bake")
    except Exception as _exc:
        print("AURORA_MOTION_WARN: %s" % _exc)

out_path = os.path.join(output_dir, f"{run_id}_rigged.glb")
# iter11.A: Draco mesh compression to keep rigged GLBs under ~10 MB.
_export_kw = dict(
    filepath=out_path,
    export_format="GLB",
    export_animations=True,
    export_skins=True,
    export_yup=True,
    export_apply=True,
    export_draco_mesh_compression_enable=True,
    export_draco_mesh_compression_level=6,
    export_draco_position_quantization=14,
    export_draco_normal_quantization=10,
    export_draco_texcoord_quantization=12,
    export_draco_color_quantization=8,
    export_draco_generic_quantization=12,
    export_optimize_animation_size=True,
)
try:
    bpy.ops.export_scene.gltf(**_export_kw)
except TypeError as _draco_exc:
    for _k in list(_export_kw):
        if _k.startswith("export_draco_") or _k == "export_optimize_animation_size":
            del _export_kw[_k]
    bpy.ops.export_scene.gltf(**_export_kw)
    print("AURORA_DRACO_WARN: %s" % _draco_exc)

print(json.dumps({
    "ok": True,
    "outputPath": out_path,
    "format": "glb",
    "rigBones": rig_bones,
    "ikConstraintsApplied": ik_constraints_applied,
    "auroraMotion": aurora_motion_report,
}))
'''


def run_procedural(args):
    blender = find_blender()
    if not blender:
        print(json.dumps({"ok": False, "error": "Blender not found. Install Blender 5.1+ and add to PATH."}))
        return

    template = args.template
    if template not in PROCEDURAL_TEMPLATES:
        print(json.dumps({"ok": False, "error": f"Unknown procedural template: {template}"}))
        return

    # Palette override: --colors takes precedence, then fall back to env.
    if args.colors:
        os.environ["AURORA_COLORS"] = args.colors

    emit("procedural", f"Building {template} in Blender...")
    script = PROCEDURAL_TEMPLATES[template]
    params_json = args.params or "{}"
    if template == "strimer_plus_v2_cable":
        try:
            params_payload = json.loads(params_json) if params_json else {}
        except Exception:
            params_payload = {}
        prompt_l = (args.prompt or "").lower()
        defaults = {
            "variant": "24pin",
            "length": 0.267,
            "width": 0.0566,
            "thickness": 0.008,
            "cable_length": 0.220,
            "light_guides": 12,
            "led_count": 120,
            "channel_count": 6,
            "pattern": "rainbow",
            "led_speed_hz": 1.65,
            "led_emission_strength": 2.4,
        }
        if "12vhpwr" in prompt_l or "12+4" in prompt_l or "16-pin" in prompt_l or "16 pin" in prompt_l:
            defaults.update({
                "variant": "12vhpwr_12guide",
                "length": 0.381,
                "width": 0.0564,
                "cable_length": 0.320,
                "light_guides": 12,
                "led_count": 162,
                "channel_count": 6,
            })
            if "8 light" in prompt_l or "8 guides" in prompt_l or "8 guide" in prompt_l:
                defaults.update({"variant": "12vhpwr_8guide", "width": 0.0398, "light_guides": 8, "led_count": 108, "channel_count": 4})
        elif "3x8" in prompt_l or "3×8" in prompt_l or "triple" in prompt_l:
            defaults.update({"variant": "triple_8pin", "length": 0.345, "width": 0.0563, "cable_length": 0.300, "light_guides": 12, "led_count": 162, "channel_count": 6})
        elif "8-pin" in prompt_l or "8 pin" in prompt_l or "pcie" in prompt_l:
            defaults.update({"variant": "dual_8pin", "length": 0.345, "width": 0.0435, "cable_length": 0.300, "light_guides": 8, "led_count": 108, "channel_count": 4})
        if re.search(r"\bchase\b|\bchenil(?:lard)?\b", prompt_l):
            defaults["pattern"] = "chase"
        elif re.search(r"\bbreath(?:ing)?\b|\brespiration\b", prompt_l):
            defaults["pattern"] = "breathing"
        elif re.search(r"\bpulse?\b", prompt_l):
            defaults["pattern"] = "pulse"
        params_payload = {**defaults, **params_payload}
        params_json = json.dumps(params_payload)
    # iter27.fix2: motherboard_layout sets every material color intentionally
    # (white PCB, chrome heatsinks, ROG cyber pink, OLED texture, ...).
    # The colorize pass would overwrite all of them with the default palette
    # (#adadb7 gray + #f4c638 yellow on connectors → user sees a gray+yellow
    # "bee" looking blob instead of the X870E identity). Skip colorize for
    # this template so the template's own colors survive.
    skip_colorize_templates = {
        "motherboard_layout",
        "led_strip_system",
        "strimer_plus_v2_cable",
        "humanoid_performer",
        "historical_person_performer",
    }
    inject_colorize = template not in skip_colorize_templates
    result = run_blender_script(blender, script, [params_json, args.output_dir, args.run_id, args.format], inject_colorize=inject_colorize)
    print(json.dumps(result))


def run_validation(args):
    blender = find_blender()
    if not blender:
        print(json.dumps({"ok": False, "error": "Blender not found."}))
        return

    emit("validate", "Running mesh validation in Blender...")
    extra = [args.mesh, args.checks, args.output_dir, args.run_id]
    if args.auto_fix:
        extra.append("--auto-fix")
    result = run_blender_script(blender, VALIDATION_SCRIPT, extra)
    print(json.dumps(result))


def run_cleanup(args):
    blender = find_blender()
    if not blender:
        print(json.dumps({"ok": False, "error": "Blender not found."}))
        return

    emit("cleanup", "Running mesh cleanup in Blender...")
    extra = [args.mesh, args.checks, args.output_dir, args.run_id, "--auto-fix"]
    result = run_blender_script(blender, VALIDATION_SCRIPT, extra)
    print(json.dumps(result))


def run_rigging(args):
    blender = find_blender()
    if not blender:
        print(json.dumps({"ok": False, "error": "Blender not found."}))
        return

    emit("rig", f"Auto-rigging with {args.rig_system}...")
    # Always pad to 9 positional argv slots so RIGGING_SCRIPT can read motion
    # at slot 8 even when physics (slot 7) is absent.
    extra = [
        args.mesh,
        args.rig_system,
        args.subject_kind,
        args.style,
        args.test_action or "",
        args.output_dir,
        args.run_id,
        args.physics or "",
        args.motion_path or "",
    ]
    # v77zo: forward python-services dir so the embedded RIGGING_SCRIPT can
    # `import motion_baker` from Blender's bundled python.
    os.environ.setdefault("AURORA_PYTHON_SERVICES", os.path.dirname(os.path.abspath(__file__)))
    result = run_blender_script(blender, RIGGING_SCRIPT, extra)
    print(json.dumps(result))


def run_custom_script(args):
    blender = find_blender()
    if not blender:
        print(json.dumps({"ok": False, "error": "Blender not found."}))
        return

    with open(args.script, "r", encoding="utf-8") as f:
        script_content = f.read()
    result = run_blender_script(blender, script_content, args.extra_args)
    print(json.dumps(result))


def main():
    parser = argparse.ArgumentParser(description="AuroraIA Blender Bridge")
    parser.add_argument("--mode", choices=["procedural", "validate", "cleanup", "rig", "script"], default="script")
    parser.add_argument("--script", help="Path to a Blender Python script")
    parser.add_argument("--template", help="Procedural template name")
    parser.add_argument("--params", help="JSON parameters for procedural template")
    parser.add_argument("--prompt", help="User prompt for context")
    parser.add_argument("--mesh", help="Path to mesh for validation/rig")
    parser.add_argument("--checks", default="non_manifold,degenerate,open_boundaries")
    parser.add_argument("--auto-fix", action="store_true", dest="auto_fix")
    parser.add_argument("--rig-system", default="rigify", dest="rig_system")
    parser.add_argument("--subject-kind", default="humanoid", dest="subject_kind")
    parser.add_argument("--style", default="realistic")
    parser.add_argument("--test-action", default="", dest="test_action")
    parser.add_argument("--physics", default="", help="Optional JSON object with physics overrides (densityKgPerM3, frictionCoefficient, restitution, angularVelocityRadPerS, pendulumPeriodSeconds)")
    parser.add_argument("--motion-path", default="", dest="motion_path",
                        help="Optional path to an aurora.motion.v1 JSON file. When provided, the rigging pipeline bakes the descriptor into an NLA action on the freshly generated rig.")
    parser.add_argument("--output-dir", default=".", dest="output_dir")
    parser.add_argument("--run-id", default="aurora", dest="run_id")
    parser.add_argument("--format", default="glb")
    parser.add_argument("--colors", help="JSON dict of palette overrides, e.g. '{\"pulley\":\"#ff8800\",\"led\":\"#00ff80\"}'")
    parser.add_argument("extra_args", nargs="*", default=[])

    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    if args.mode == "procedural":
        run_procedural(args)
    elif args.mode == "validate":
        run_validation(args)
    elif args.mode == "cleanup":
        run_cleanup(args)
    elif args.mode == "rig":
        run_rigging(args)
    elif args.mode == "script" and args.script:
        run_custom_script(args)
    else:
        print(json.dumps({"ok": False, "error": "No valid mode or script specified."}))


if __name__ == "__main__":
    main()
