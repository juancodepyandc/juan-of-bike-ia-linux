#!/usr/bin/env python3
"""
Mesh Screenshot Renderer — Renders a 3D mesh (GLB/OBJ) to a PNG screenshot
using trimesh for loading and matplotlib for headless rendering.

This avoids OpenGL/pyrender dependencies and works in headless environments.
Used by the auto-correction loop to capture real mesh renders for vision-based
fidelity comparison (instead of comparing the reference image against itself).

Usage:
  python mesh_screenshot.py --mesh path/to/mesh.glb --output path/to/screenshot.png
  python mesh_screenshot.py --mesh path/to/mesh.glb --output path/to/screenshot.png --views front,left,back

Output (JSON on last line):
  {"ok": true, "screenshots": [{"view": "front_3q", "path": "..."}], "vertex_count": 1234, "face_count": 5678}
"""

import argparse
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


def _find_blender_executable() -> str | None:
    env_path = os.environ.get("BLENDER_BIN") or os.environ.get("BLENDER_EXE")
    if env_path and os.path.isfile(env_path):
        return env_path
    for candidate in ("blender", "blender.exe"):
        path = shutil.which(candidate)
        if path:
            return path
    if os.name == "nt":
        root = Path(r"C:\Program Files\Blender Foundation")
        if root.is_dir():
            matches = sorted(root.glob("Blender */blender.exe"), reverse=True)
            if matches:
                return str(matches[0])
    return None


def _png_looks_blank(path: str) -> bool:
    try:
        from PIL import Image, ImageStat

        with Image.open(path) as im:
            stat = ImageStat.Stat(im.convert("RGB").resize((64, 64)))
        return max(stat.var) < 1.0
    except Exception:
        return False


def _render_with_blender(
    mesh_path: str,
    output_path: str,
    views: list[str],
    resolution: tuple[int, int],
) -> dict[str, Any] | None:
    blender = _find_blender_executable()
    if not blender:
        return None

    script = f"""
import json
import math
import os
import sys

import bpy
import mathutils

mesh_path = {json.dumps(os.path.abspath(mesh_path))}
output_path = {json.dumps(os.path.abspath(output_path))}
views = {json.dumps(views)}
resolution = {json.dumps(list(resolution))}

view_positions = {{
    "front": (0.0, -3.2, 0.12),
    "front_3q": (1.55, -3.0, 0.22),
    "back": (0.0, 3.2, 0.12),
    "back_3q": (-1.55, 3.0, 0.22),
    "left": (-3.2, 0.0, 0.12),
    "right": (3.2, 0.0, 0.12),
    "top": (0.0, -0.05, 3.4),
    "bottom": (0.0, -0.05, -3.4),
    "iso": (2.3, -2.6, 1.4),
}}


def view_output(view_name):
    base, ext = os.path.splitext(output_path)
    return f"{{base}}_{{view_name}}{{ext}}" if len(views) > 1 else output_path


def look_at(obj, target):
    direction = mathutils.Vector(target) - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete()

ext = os.path.splitext(mesh_path)[1].lower()
if ext in (".glb", ".gltf"):
    bpy.ops.import_scene.gltf(filepath=mesh_path)
elif ext == ".stl":
    if hasattr(bpy.ops.wm, "stl_import"):
        bpy.ops.wm.stl_import(filepath=mesh_path)
    else:
        bpy.ops.import_mesh.stl(filepath=mesh_path)
elif ext == ".obj":
    if hasattr(bpy.ops.wm, "obj_import"):
        bpy.ops.wm.obj_import(filepath=mesh_path)
    else:
        bpy.ops.import_scene.obj(filepath=mesh_path)
else:
    raise RuntimeError(f"Unsupported mesh extension for Blender fallback: {{ext}}")

bpy.context.scene.frame_set(1)
bpy.context.view_layer.update()

meshes = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
if not meshes:
    raise RuntimeError("Blender import produced no mesh objects")

vertices = sum(len(obj.data.vertices) for obj in meshes)
faces = sum(len(obj.data.polygons) for obj in meshes)


def scene_bounds():
    bpy.context.view_layer.update()
    coords = []
    depsgraph = bpy.context.evaluated_depsgraph_get()
    for obj in meshes:
        evaluated = obj.evaluated_get(depsgraph)
        matrix = evaluated.matrix_world.copy()
        coords.extend(matrix @ mathutils.Vector(corner) for corner in evaluated.bound_box)
    if not coords:
        raise RuntimeError("Imported mesh has no bounding box coordinates")
    min_v = mathutils.Vector((min(v[i] for v in coords) for i in range(3)))
    max_v = mathutils.Vector((max(v[i] for v in coords) for i in range(3)))
    center = (min_v + max_v) * 0.5
    extents = max_v - min_v
    size = max(extents[:]) or 1.0
    return center, extents, size


center, extents, size = scene_bounds()

bpy.context.scene.render.resolution_x = int(resolution[0])
bpy.context.scene.render.resolution_y = int(resolution[1])
bpy.context.scene.render.film_transparent = False
bpy.context.scene.world = bpy.context.scene.world or bpy.data.worlds.new("World")
bpy.context.scene.world.color = (0.035, 0.055, 0.07)
try:
    bpy.context.scene.render.engine = "BLENDER_EEVEE_NEXT"
except Exception:
    pass
bpy.context.scene.view_settings.view_transform = "Filmic"
bpy.context.scene.view_settings.look = "Medium High Contrast"
bpy.context.scene.view_settings.exposure = 0
bpy.context.scene.view_settings.gamma = 1

camera = bpy.data.objects.new("capture_camera", bpy.data.cameras.new("capture_camera"))
bpy.context.collection.objects.link(camera)
camera.data.type = "ORTHO"
camera.data.ortho_scale = max(size * 1.18, 0.5)
bpy.context.scene.camera = camera

key_data = bpy.data.lights.new("capture_key", "AREA")
key_data.energy = 520
key_data.size = 4.5
key = bpy.data.objects.new("capture_key", key_data)
bpy.context.collection.objects.link(key)
key.location = center + mathutils.Vector((0.9 * size, -1.2 * size, 1.4 * size))
look_at(key, center)

fill_data = bpy.data.lights.new("capture_fill", "POINT")
fill_data.energy = 80
fill = bpy.data.objects.new("capture_fill", fill_data)
bpy.context.collection.objects.link(fill)
fill.location = center + mathutils.Vector((-1.0 * size, 0.9 * size, 0.7 * size))

screenshots = []
for view_name in views:
    bpy.context.scene.frame_set(1)
    bpy.context.view_layer.update()
    center, extents, size = scene_bounds()
    camera.data.ortho_scale = max(size * 1.18, 0.5)
    offset = mathutils.Vector(view_positions.get(view_name, view_positions["front_3q"]))
    camera.location = center + offset.normalized() * (size * 2.4)
    look_at(camera, center + mathutils.Vector((0, 0, 0.02 * size)))
    bpy.context.scene.render.filepath = view_output(view_name)
    bpy.ops.render.render(write_still=True)
    screenshots.append({{"view": view_name, "path": bpy.context.scene.render.filepath}})

print(json.dumps({{
    "ok": True,
    "screenshots": screenshots,
    "vertex_count": vertices,
    "face_count": faces,
    "renderer": "blender",
}}))
"""

    script_path = None
    try:
        with tempfile.NamedTemporaryFile("w", suffix="_aurora_mesh_capture.py", encoding="utf-8", delete=False) as fh:
            fh.write(script)
            script_path = fh.name
        proc = subprocess.run(
            [blender, "--background", "--factory-startup", "--python", script_path],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=180,
        )
        if proc.returncode != 0:
            return {
                "ok": False,
                "error": f"Blender fallback failed ({proc.returncode}): {(proc.stderr or proc.stdout)[-1200:]}",
            }
        for line in reversed((proc.stdout or "").splitlines()):
            line = line.strip()
            if line.startswith("{") and line.endswith("}"):
                return json.loads(line)
        return {"ok": False, "error": "Blender fallback did not emit JSON"}
    except Exception as exc:
        return {"ok": False, "error": f"Blender fallback exception: {exc}"}
    finally:
        if script_path:
            try:
                os.remove(script_path)
            except OSError:
                pass


def render_mesh_screenshots(
    mesh_path: str,
    output_path: str,
    views: list[str] | None = None,
    resolution: tuple[int, int] = (1024, 1024),
) -> dict[str, Any]:
    """Load a mesh and render screenshots from specified view angles."""
    try:
        import trimesh
        import numpy as np
    except ImportError as exc:
        return {"ok": False, "error": f"Missing dependency: {exc}"}

    # Load mesh — keep the Scene intact so PBR materials / textures survive.
    try:
        scene_or_mesh = trimesh.load(mesh_path)
    except Exception as exc:
        return {"ok": False, "error": f"Failed to load mesh: {exc}"}

    if scene_or_mesh is None:
        return {"ok": False, "error": "Mesh loaded as None"}

    if isinstance(scene_or_mesh, trimesh.Scene):
        src_scene = scene_or_mesh
        meshes = [g for g in src_scene.geometry.values() if isinstance(g, trimesh.Trimesh)]
        if not meshes:
            return {"ok": False, "error": "Scene contains no valid meshes"}
        # A concatenated copy is only used for stats / matplotlib fallback.
        mesh = trimesh.util.concatenate(meshes) if len(meshes) > 1 else meshes[0]
    elif isinstance(scene_or_mesh, trimesh.Trimesh):
        mesh = scene_or_mesh
        src_scene = trimesh.Scene(mesh)
    else:
        return {"ok": False, "error": f"Unexpected mesh type: {type(scene_or_mesh)}"}

    vertex_count = len(mesh.vertices) if hasattr(mesh, "vertices") else 0
    face_count = len(mesh.faces) if hasattr(mesh, "faces") else 0

    if face_count < 10:
        return {"ok": False, "error": f"Degenerate mesh with only {face_count} faces"}

    # Default views: front 3/4 view (best for comparison)
    if not views:
        views = ["front_3q"]

    # Animated GLB/GLTF files need a renderer that preserves the scene graph.
    # The trimesh path is still useful as a fallback, but it can flatten
    # transforms in ways that hide hierarchy or motion defects.
    if Path(mesh_path).suffix.lower() in {".glb", ".gltf"}:
        blender_result = _render_with_blender(mesh_path, output_path, views, resolution)
        if blender_result and blender_result.get("ok"):
            return blender_result

    try:
        scene_extent = float((src_scene.bounds[1] - src_scene.bounds[0]).max())
    except Exception:
        scene_extent = 0.0
    try:
        mesh_extent = float(mesh.extents.max())
    except Exception:
        mesh_extent = 0.0
    if max(scene_extent, mesh_extent) <= 1e-9:
        blender_result = _render_with_blender(mesh_path, output_path, views, resolution)
        if blender_result and blender_result.get("ok"):
            return blender_result
        if blender_result and blender_result.get("error"):
            return blender_result

    # View angle definitions (azimuth around +Y, elevation tilt in degrees)
    view_angles: dict[str, tuple[float, float]] = {
        "front": (0, 12),
        "front_3q": (35, 18),
        "back": (180, 12),
        "back_3q": (215, 18),
        "left": (90, 12),
        "right": (-90, 12),
        "top": (0, 80),
        "bottom": (0, -80),
        "iso": (45, 30),
    }

    screenshots: list[dict[str, str]] = []

    def _view_output(view_name: str) -> str:
        base, ext = os.path.splitext(output_path)
        return f"{base}_{view_name}{ext}" if len(views) > 1 else output_path

    # --- Preferred path: real GL renderer via trimesh.Scene.save_image (pyglet).
    # This is the only path that honours PBR baseColor textures / vertex colors,
    # which is what we actually want to inspect on Hunyuan-painted meshes.
    try:
        import trimesh.transformations as tf

        scene = src_scene.copy()
        # Recenter the whole scene at the origin and normalise its size.
        bounds = scene.bounds
        center = (bounds[0] + bounds[1]) / 2.0
        size = float((bounds[1] - bounds[0]).max()) or 1.0
        scene.apply_transform(tf.translation_matrix(-center))
        scene.apply_transform(tf.scale_matrix(1.0 / size))

        rendered_any = False
        for view_name in views:
            azimuth, elevation = view_angles.get(view_name, (35, 18))
            posed = scene.copy()
            # Rotate around +Y (turntable), then tilt around +X (camera elevation).
            posed.apply_transform(tf.rotation_matrix(math.radians(azimuth), [0, 1, 0]))
            posed.apply_transform(tf.rotation_matrix(math.radians(elevation), [1, 0, 0]))
            try:
                png = posed.save_image(resolution=resolution, visible=True)
            except Exception:
                png = None
            if not png:
                rendered_any = False
                break
            view_output = _view_output(view_name)
            with open(view_output, "wb") as fh:
                fh.write(png)
            if _png_looks_blank(view_output):
                rendered_any = False
                break
            screenshots.append({"view": view_name, "path": view_output})
            rendered_any = True

        if rendered_any and len(screenshots) == len(views):
            return {
                "ok": True,
                "screenshots": screenshots,
                "vertex_count": vertex_count,
                "face_count": face_count,
                "renderer": "trimesh-gl",
            }
        screenshots = []
    except Exception:
        screenshots = []

    blender_result = _render_with_blender(mesh_path, output_path, views, resolution)
    if blender_result and blender_result.get("ok"):
        return blender_result

    # --- Fallback: matplotlib (untextured, neutral shading). Last resort only.
    # Center and normalize the mesh for the matplotlib path.
    mesh = mesh.copy()
    mesh.vertices = mesh.vertices - mesh.centroid
    scale = mesh.extents.max()
    if scale > 0:
        mesh.vertices = mesh.vertices / scale

    try:
        import matplotlib
        matplotlib.use("Agg")  # Headless backend
        import matplotlib.pyplot as plt
        from mpl_toolkits.mplot3d import Axes3D  # noqa: F401
        from mpl_toolkits.mplot3d.art3d import Poly3DCollection

        for view_name in views:
            azimuth, elevation = view_angles.get(view_name, (35, 20))

            fig = plt.figure(figsize=(resolution[0] / 100, resolution[1] / 100), dpi=100)
            ax = fig.add_subplot(111, projection="3d")

            # Render mesh faces
            verts = mesh.vertices
            faces = mesh.faces

            # Sample faces if too many (for performance)
            max_faces = 50000
            if len(faces) > max_faces:
                indices = np.random.choice(len(faces), max_faces, replace=False)
                faces_to_render = faces[indices]
            else:
                faces_to_render = faces

            # Build polygon collection
            polygons = verts[faces_to_render]

            # Compute face normals for simple lighting
            v0 = polygons[:, 0]
            v1 = polygons[:, 1]
            v2 = polygons[:, 2]
            normals = np.cross(v1 - v0, v2 - v0)
            norms = np.linalg.norm(normals, axis=1, keepdims=True)
            norms[norms == 0] = 1
            normals = normals / norms

            # Light direction from camera angle
            az_rad = math.radians(azimuth)
            el_rad = math.radians(elevation)
            light_dir = np.array([
                math.cos(el_rad) * math.sin(az_rad),
                math.sin(el_rad),
                math.cos(el_rad) * math.cos(az_rad),
            ])

            # Diffuse lighting
            intensity = np.clip(np.dot(normals, light_dir), 0.15, 1.0)
            # Color: neutral grey with lighting
            face_colors = np.zeros((len(faces_to_render), 4))
            face_colors[:, 0] = 0.6 * intensity + 0.15
            face_colors[:, 1] = 0.65 * intensity + 0.15
            face_colors[:, 2] = 0.7 * intensity + 0.15
            face_colors[:, 3] = 1.0

            # Apply vertex colors if available
            if hasattr(mesh, "visual") and hasattr(mesh.visual, "vertex_colors"):
                try:
                    vc = mesh.visual.vertex_colors[:, :3].astype(float) / 255.0
                    face_vc = vc[faces_to_render].mean(axis=1)  # Average per face
                    face_colors[:, :3] = face_vc * intensity[:, np.newaxis] * 0.8 + 0.1
                except Exception:
                    pass  # Fall back to grey

            collection = Poly3DCollection(polygons, facecolors=face_colors, edgecolors="none", linewidths=0.0)
            ax.add_collection3d(collection)

            # Set axis limits
            max_range = 0.7
            ax.set_xlim(-max_range, max_range)
            ax.set_ylim(-max_range, max_range)
            ax.set_zlim(-max_range, max_range)
            ax.view_init(elev=elevation, azim=azimuth)

            # Clean appearance
            ax.set_facecolor("#091116")
            fig.patch.set_facecolor("#091116")
            ax.grid(False)
            ax.set_axis_off()

            # Tight layout
            plt.subplots_adjust(left=0, right=1, top=1, bottom=0)

            # Generate output path for this view
            base, ext = os.path.splitext(output_path)
            if len(views) > 1:
                view_output = f"{base}_{view_name}{ext}"
            else:
                view_output = output_path

            fig.savefig(view_output, dpi=100, facecolor=fig.get_facecolor(), bbox_inches="tight", pad_inches=0.05)
            plt.close(fig)

            screenshots.append({"view": view_name, "path": view_output})

    except ImportError:
        # Matplotlib fallback: try trimesh's built-in export
        try:
            scene = trimesh.Scene(mesh)
            # Try to export a simple image
            png_data = scene.save_image(resolution=resolution)
            if png_data:
                with open(output_path, "wb") as f:
                    f.write(png_data)
                screenshots.append({"view": "default", "path": output_path})
            else:
                return {"ok": False, "error": "trimesh save_image returned empty data"}
        except Exception as exc:
            return {"ok": False, "error": f"No rendering backend available: {exc}"}
    except Exception as exc:
        return {"ok": False, "error": f"Rendering failed: {exc}"}

    return {
        "ok": True,
        "screenshots": screenshots,
        "vertex_count": vertex_count,
        "face_count": face_count,
    }


def main():
    parser = argparse.ArgumentParser(description="Render mesh screenshots")
    parser.add_argument("--mesh", required=True, help="Path to mesh file (GLB/OBJ)")
    parser.add_argument("--output", required=True, help="Output PNG path")
    parser.add_argument("--views", default="front_3q", help="Comma-separated view names: front,front_3q,back,left,right,top,bottom,iso")
    parser.add_argument("--width", type=int, default=1024, help="Image width")
    parser.add_argument("--height", type=int, default=1024, help="Image height")
    args = parser.parse_args()

    if not os.path.isfile(args.mesh):
        print(json.dumps({"ok": False, "error": f"Mesh file not found: {args.mesh}"}))
        sys.exit(1)

    # Ensure output directory exists
    output_dir = os.path.dirname(args.output)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    views = [v.strip() for v in args.views.split(",") if v.strip()]
    result = render_mesh_screenshots(
        mesh_path=args.mesh,
        output_path=args.output,
        views=views,
        resolution=(args.width, args.height),
    )
    print(json.dumps(result))


if __name__ == "__main__":
    main()
