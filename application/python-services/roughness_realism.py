"""roughness_realism.py — Blender headless pass: fix the "wet plastic" look.

The generated PBR materials come out FAR too glossy (effective roughness ~0.35):
under the viewer's studio IBL every surface reads as wet plastic — a T-shirt
looks like latex, an apple like a mirror-ball. Real fabric/skin/organic surfaces
are matte-to-satin. This pass raises the roughness of OPAQUE DIELECTRIC materials
(metalness ~0, no transmission) to a realistic satin floor while leaving genuine
glossy surfaces (metal via metalness>0, glass via transmission) untouched. It
lifts the roughness where it is texture-driven (remaps the roughness image toward
matte) or where it is a flat factor.

Usage: blender -b -P roughness_realism.py -- IN.glb OUT.glb [floor=0.55]
Emits: ROUGH_REALISM_OK glb=<OUT> lifted=<n>
"""
from __future__ import annotations

import os
import sys

import bpy

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
if len(argv) < 2:
    print("ROUGH_REALISM_FAIL: usage IN.glb OUT.glb [floor]", flush=True)
    sys.exit(2)
IN_GLB, OUT_GLB = argv[0], argv[1]
# 27/07: 0.55 global ecrasait le CONTRASTE de matiere (fourrure 0.75,
# coton 0.85, soie 0.52, peau 0.5, plastique 0.4 finissaient identiques
# -> tout parait peint et plat). Filet bas seul; la valeur juste vient
# du manifeste matiere, par zone.
FLOOR = float(argv[2]) if len(argv) > 2 else float(
    os.environ.get("AURORA_ROUGHNESS_FLOOR", "0.30"))

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=IN_GLB)

lifted = 0
for mat in bpy.data.materials:
    if not mat.use_nodes:
        continue
    nt = mat.node_tree
    bsdf = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if bsdf is None:
        continue
    # Skip genuine glossy materials: metallic (metalness>0.4) or transmissive (glass).
    metal_in = bsdf.inputs.get("Metallic")
    trans_in = bsdf.inputs.get("Transmission Weight") or bsdf.inputs.get("Transmission")
    # A combined metallicRoughness texture links BOTH metalness(B) and
    # roughness(G) even for a DIELECTRIC (metalnessFactor 0, texture B just
    # unused) — so "metalness is linked" does NOT mean metal. Only skip when
    # metalness is a FLAT high value (genuine metal) or the material is glass.
    metal_v = metal_in.default_value if (metal_in and not metal_in.is_linked) else 0.0
    trans_v = trans_in.default_value if (trans_in and not trans_in.is_linked) else 0.0
    if metal_v > 0.5 or trans_v > 0.3:
        continue
    rough_in = bsdf.inputs.get("Roughness")
    if rough_in is None:
        continue
    if rough_in.is_linked:
        # roughness is texture-driven: lift the source image pixels toward matte.
        src = rough_in.links[0].from_node
        # walk back through a possible Separate/Math node to the image
        img_node = None
        stack = [src]
        seen = set()
        while stack:
            n = stack.pop()
            if n in seen:
                continue
            seen.add(n)
            if n.type == "TEX_IMAGE" and n.image is not None:
                img_node = n
                break
            for inp in n.inputs:
                for lk in inp.links:
                    stack.append(lk.from_node)
        if img_node is None:
            # can't find image — just clamp the factor path off and set a matte value
            continue
        img = img_node.image
        try:
            import numpy as np
            n = len(img.pixels)
            arr = np.empty(n, dtype=np.float32)
            img.pixels.foreach_get(arr)
            arr = arr.reshape(-1, 4)
            # Lift ONLY the G channel: glTF packs roughness in G, and the SAME
            # ORM/MR image carries occlusion in R (glb_material_writer._pack_ao_into_mr)
            # and metalness in B. Blender's glTF import always routes G -> Roughness
            # (Separate Color node), so lifting R,G,B would wash out the AO and inflate
            # metalness in EVERY renderer while only G actually drives roughness.
            arr[:, 1] = FLOOR + (1.0 - FLOOR) * arr[:, 1]
            img.pixels.foreach_set(arr.reshape(-1))
            img.update()
            lifted += 1
        except Exception as exc:  # noqa: BLE001
            print("ROUGH_REALISM_WARN: image lift failed: %s" % exc, flush=True)
    else:
        v = rough_in.default_value
        if v < FLOOR:
            rough_in.default_value = FLOOR
            lifted += 1

bpy.ops.object.select_all(action="SELECT")
# OMBRAGE LISSE AVANT EXPORT (27/07, mesure): sans normales lisses,
# l'exporteur glTF ecrit UNE NORMALE PAR FACE et DEDOUBLE tous les sommets
# (mesure: 1,25 M -> 2,95 M sommets pour 985 k faces, ratio 2.99 = chaque
# triangle isole -> 982 835 ilots). Resultat livre: surface facettee, rendu
# sombre et dur, fichier 3x plus lourd. C'est LE defaut que l'utilisateur
# voyait sur la geometrie pure. L'angle preserve les vraies aretes dures.
for _o in bpy.context.scene.objects:
    if _o.type != "MESH":
        continue
    bpy.context.view_layer.objects.active = _o
    try:
        bpy.ops.object.shade_auto_smooth(angle=0.523599)   # 30 deg
    except Exception:
        try:
            bpy.ops.object.shade_smooth()
        except Exception:
            pass
bpy.ops.export_scene.gltf(filepath=OUT_GLB, export_format="GLB", export_yup=True,
                          export_animations=True, export_morph=True, export_extras=True)
print("ROUGH_REALISM_OK glb=%s lifted=%d floor=%.2f" % (OUT_GLB, lifted, FLOOR), flush=True)
