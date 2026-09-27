"""Blender subprocess: deterministic views and BVH intersection inspection."""
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree


def main():
    mesh_path, out_dir, views, size = sys.argv[sys.argv.index("--") + 1:]
    root = Path(out_dir)
    root.mkdir(parents=True, exist_ok=True)
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    bpy.ops.import_scene.gltf(filepath=mesh_path)
    objects = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    vertices, faces = [], []
    for obj in objects:
        obj.data.calc_loop_triangles()
        offset = len(vertices)
        vertices.extend([obj.matrix_world @ v.co for v in obj.data.vertices])
        faces.extend([tuple(offset + i for i in tri.vertices) for tri in obj.data.loop_triangles])
    if not vertices or not faces:
        raise ValueError("Maillage vide")
    # Avoid quadratic pathological meshes; an unavailable metric cannot pass a gate.
    intersections = None
    if len(faces) <= 250000:
        tree = BVHTree.FromPolygons(vertices, faces, all_triangles=True, epsilon=0.0)
        intersections = sum(1 for a, b in tree.overlap(tree)
                            if a < b and not set(faces[a]).intersection(faces[b]))
    # Cadrage robuste: on ignore les 2 % extremes de chaque axe, qui sont des debris.
    # Avant, l'AABB global etait dilate par ces debris puis multiplie par 2.5, donc
    # l'objet n'occupait que ~10 % du cadre. Mesure sur tools/clip_cadrage_exp.py:
    # clip_moyen +0.017, clip_pire +0.032, 6/6 graines ameliorlees. Le BVH ci-dessus
    # reste mesure sur la geometrie complete: cette metrique n'est pas modifiee.
    axes = []
    for i in range(3):
        column = sorted(v[i] for v in vertices)
        n = len(column)
        axes.append((column[min(n - 1, int(n * 0.02))], column[min(n - 1, int(n * 0.98))]))
    center = Vector(tuple((lo + hi) / 2 for lo, hi in axes))
    extent = max(max(hi - lo for lo, hi in axes), 1e-5)
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.shading.light = "STUDIO"
    scene.display.shading.color_type = "TEXTURE"
    scene.display.shading.show_shadows = True
    scene.display.shading.show_cavity = True
    scene.display.shading.background_type = "WORLD"
    scene.world.color = (0.18, 0.18, 0.18)
    scene.render.resolution_x = scene.render.resolution_y = int(size)
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    bpy.ops.object.camera_add()
    camera = bpy.context.object
    scene.camera = camera
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = extent * 1.6
    camera.data.clip_end = extent * 100 + 100
    for i in range(int(views)):
        angle = i * 2 * math.pi / int(views)
        camera.location = center + Vector((math.cos(angle), math.sin(angle), 0.55)) * extent * 3.0
        camera.rotation_euler = (center - camera.location).to_track_quat("-Z", "Y").to_euler()
        scene.render.filepath = str(root / f"view_{i:02d}.png")
        bpy.ops.render.render(write_still=True)
    (root / "geometry.json").write_text(json.dumps({"self_intersections": intersections,
                                                    "triangles": len(faces)}))


if __name__ == "__main__":
    main()
