"""
AuroraIA — Mesh post-processing pipeline for AI-generated meshes.

Purpose: kill the typical Hunyuan3D / DreamGaussian artefacts
(holes, lumps, isolated floaters, sharp angular triangles, broken normals,
flying micro-shells) before exporting the mesh to the viewer.

Pipeline (in order, each stage opt-out via flags):
  1. Load mesh (any format trimesh supports)
  2. Drop disconnected micro-shells (floaters)
  3. Fill holes (close watertight surface where possible)
  4. Laplacian smoothing (anti-blob, anti-spike)
  5. Taubin smoothing (volume-preserving, kills high-frequency noise without shrinking)
  6. Remesh / decimate to a target face count when over-tessellated
  7. Fix face winding + recompute normals (kills flipped triangles -> dark patches)
  8. Optional: subdivision-surface single pass (smooth round shapes for organic subjects)
  9. Re-validate and export

Usage:
  python mesh_postprocess.py \
      --input <mesh.glb|obj|ply> \
      --output <smoothed.glb> \
      --intent-purpose character|product|mechanical_part|... \
      --motion-readiness static_only|articulated|rig_candidate \
      [--floater-ratio 0.005] \
      [--smooth-iterations auto] \
      [--target-faces auto] \
      [--subdivide]
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from typing import Any

from cache_paths import configure_ml_cache_environment


def emit(stage: str, detail: str) -> None:
    print(f"PROGRESS:{stage}:{detail}", flush=True)


def emit_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload), flush=True)


# ---------------------------------------------------------------------------
# Smoothing presets per intent — different subjects need different treatment.
# Mechanical parts must keep sharp corners, characters must lose noise but
# preserve volume, products want a polished but flat-shaded look.
# ---------------------------------------------------------------------------

SMOOTHING_PROFILES: dict[str, dict[str, Any]] = {
    "character": {
        # Anti-shrinkage tuning v55: laplacian iterations dropped from 4 to 2
        # (Laplacian shrinks volume linearly, Taubin doesn't — fewer laplacian
        # passes = less skinny character). Taubin mu pushed slightly stronger
        # negative (-0.55) so the back-pass actively re-expands after each
        # forward pass. Volume preservation pass added after smoothing.
        "laplacian_iterations": 2,
        "taubin_iterations": 22,
        "taubin_lamb": 0.5,
        "taubin_mu": -0.55,
        "decimate_target_faces": 150_000,
        "floater_ratio": 0.004,
        "fill_holes": True,
        "preserve_features": False,
        "subdivide_pass": False,
        "preserve_volume": True,
    },
    "creature": {
        "laplacian_iterations": 1,
        "taubin_iterations": 20,
        "taubin_lamb": 0.5,
        "taubin_mu": -0.55,
        "decimate_target_faces": 120_000,
        "floater_ratio": 0.005,
        "fill_holes": True,
        "preserve_features": False,
        "subdivide_pass": False,
        "preserve_volume": True,
    },
    "product": {
        "laplacian_iterations": 1,
        "taubin_iterations": 8,
        "taubin_lamb": 0.45,
        "taubin_mu": -0.50,
        "decimate_target_faces": 80_000,
        "floater_ratio": 0.005,
        "fill_holes": True,
        "preserve_features": True,
        "subdivide_pass": False,
    },
    "mechanical_part": {
        "laplacian_iterations": 0,
        "taubin_iterations": 4,
        "taubin_lamb": 0.4,
        "taubin_mu": -0.45,
        "decimate_target_faces": 140_000,
        "floater_ratio": 0.003,
        "fill_holes": True,
        "preserve_features": True,
        "subdivide_pass": False,
    },
    "body_part": {
        "laplacian_iterations": 1,
        "taubin_iterations": 18,
        "taubin_lamb": 0.5,
        "taubin_mu": -0.55,
        "decimate_target_faces": 120_000,
        "floater_ratio": 0.004,
        "fill_holes": True,
        "preserve_features": False,
        "subdivide_pass": False,
        "preserve_volume": True,
    },
    "vehicle": {
        "laplacian_iterations": 1,
        "taubin_iterations": 8,
        "taubin_lamb": 0.45,
        "taubin_mu": -0.50,
        "decimate_target_faces": 150_000,
        "floater_ratio": 0.005,
        "fill_holes": True,
        "preserve_features": True,
        "subdivide_pass": False,
    },
    "default": {
        "laplacian_iterations": 2,
        "taubin_iterations": 12,
        "taubin_lamb": 0.5,
        "taubin_mu": -0.53,
        "decimate_target_faces": 120_000,
        "floater_ratio": 0.005,
        "fill_holes": True,
        "preserve_features": False,
        "subdivide_pass": False,
    },
}


def resolve_profile(intent_purpose: str, motion_readiness: str) -> dict[str, Any]:
    profile = dict(SMOOTHING_PROFILES.get(intent_purpose, SMOOTHING_PROFILES["default"]))
    if motion_readiness in {"rig_candidate", "articulated"}:
        # A rigged mesh needs slightly cleaner topology (fewer faces, evenly distributed) so
        # automatic weight painting does not produce spaghetti deformations. Push the
        # decimation target slightly down and ensure a proper smoothing.
        profile["decimate_target_faces"] = min(profile["decimate_target_faces"], 90_000)
        profile["taubin_iterations"] = max(profile["taubin_iterations"], 14)
    if intent_purpose == "mechanical_part":
        profile["preserve_features"] = True
    # PLAFOND DE DECIMATION REGLABLE. Les cibles ci-dessus (80 000 a 150 000,
    # ramenees a 90 000 des qu'un rig est prevu) ont ete choisies pour que le
    # calcul automatique des poids ne parte pas en spaghetti. Mais le
    # generateur livre desormais 300 000 faces, et TOUT ce qui est fin — une
    # meche bouclee, une lanniere, une grille — passe sous la maille a 90 000
    # et ressort en bloc ou en confettis. Le rig venant maintenant du service
    # (qui remaille lui-meme avant de poser le squelette), ce plafond n'a plus
    # la meme utilite. On le laisse par defaut, mais AURORA_DECIMATE_TARGET
    # permet de demander la geometrie pleine sans toucher au code.
    _cible = os.environ.get("AURORA_DECIMATE_TARGET")
    if _cible:
        try:
            profile["decimate_target_faces"] = int(_cible)
        except ValueError:
            pass
    return profile


# ---------------------------------------------------------------------------
# Trimesh helpers (used as the fallback path when pymeshlab is unavailable
# or fails on a given mesh).
# ---------------------------------------------------------------------------


def _trimesh_drop_floaters(mesh, ratio: float):
    """Retire les petites composantes detachees (artefacts de generation).

    SANS `mesh.split()`. Celui-ci construit un sous-maillage par composante et
    RECOPIE l'atlas pour chacun (trimesh/util.py -> material.copy() -> PIL
    Image.copy()). Mesure du 05/09: 7 208 composantes sur un maillage de
    personnage, 50 Mo par copie d'atlas 4096 = 360 Go demandes, processus tue
    par le noyau a 30 Go. Huit lancements perdus, tous a cause de ce motif.

    On lit la connectivite sur le graphe d'adjacence des faces, on mesure
    chaque composante sur ses SOMMETS, puis on applique un masque de faces:
    `update_faces` conserve les UV et la texture unique, sans aucune copie.
    """
    try:
        import numpy as np
        from trimesh.graph import connected_components as _cc

        faces = np.asarray(mesh.faces)
        if len(faces) == 0:
            return mesh, 0
        comps = _cc(mesh.face_adjacency, nodes=np.arange(len(faces)))
        if len(comps) <= 1:
            return mesh, 0

        verts = np.asarray(mesh.vertices)
        mesures = []
        for c in comps:
            vi = np.unique(faces[c].ravel())
            pts = verts[vi]
            etendue = pts.max(axis=0) - pts.min(axis=0)
            vol = float(np.prod(np.maximum(etendue, 1e-12)))
            mesures.append(vol)
        plus_gros = max(mesures) if mesures else 0.0
        if plus_gros <= 0:
            return mesh, 0
        seuil = max(1e-9, plus_gros * ratio)

        garder = np.zeros(len(faces), dtype=bool)
        jetes = 0
        for c, vol in zip(comps, mesures):
            if vol >= seuil:
                garder[c] = True
            else:
                jetes += 1
        if not garder.any() or jetes == 0:
            return mesh, 0
        mesh.update_faces(garder)
        mesh.remove_unreferenced_vertices()
        return mesh, jetes
    except Exception:  # noqa: BLE001 — en cas de doute on ne touche pas au maillage
        return mesh, 0

def _trimesh_taubin_smoothing(mesh, iterations: int, lamb: float, mu: float):
    """Pure trimesh Taubin smoothing fallback (volume preserving)."""
    if iterations <= 0:
        return mesh
    try:
        import trimesh

        # trimesh 4.x : le 2e param de Taubin s'appelle `nu` (positif), pas `mu`.
        # Les profils stockent `mu` négatif (magnitude de la passe arrière) → val. absolue.
        # (Avant : "unexpected keyword 'mu'" → lissage Taubin silencieusement skippé.)
        return trimesh.smoothing.filter_taubin(mesh, lamb=lamb, nu=abs(mu), iterations=iterations)
    except Exception as exc:
        emit("post_warn", f"taubin smoothing skipped ({exc})")
        return mesh


def _trimesh_laplacian_smoothing(mesh, iterations: int):
    """Pure trimesh Laplacian smoothing fallback."""
    if iterations <= 0:
        return mesh
    try:
        import trimesh

        return trimesh.smoothing.filter_laplacian(mesh, iterations=iterations)
    except Exception as exc:
        emit("post_warn", f"laplacian smoothing skipped ({exc})")
        return mesh


def _trimesh_fix_normals(mesh):
    try:
        mesh.fix_normals()
        mesh.merge_vertices()
        mesh.process(validate=True)
    except Exception as exc:
        emit("post_warn", f"normal fix skipped ({exc})")
    return mesh


def _trimesh_fill_holes(mesh):
    try:
        mesh.fill_holes()
    except Exception as exc:
        emit("post_warn", f"fill_holes skipped ({exc})")
    return mesh


def _measure_bilateral_asymmetry(mesh) -> float:
    """v77zi: max RMS distance between every vertex and the closest mesh
    vertex to its YZ-plane mirror. Returns 0.0 for a perfectly symmetric mesh
    centered on x=0 and increases with the worst-offset asymmetric vertex.
    Reported in the same units as the mesh (meters once dimension scaling
    has run).
    """
    import numpy as np

    verts = np.asarray(mesh.vertices)
    if len(verts) < 4:
        return 0.0
    mirrored = verts.copy()
    mirrored[:, 0] = -mirrored[:, 0]
    try:
        kd = mesh.kdtree
    except Exception:
        try:
            from scipy.spatial import cKDTree
            kd = cKDTree(verts)
        except Exception:
            # Brute-force fallback only if mesh is small (< 6k verts).
            if len(verts) > 6000:
                return -1.0
            diffs = verts[:, None, :] - mirrored[None, :, :]
            dists = np.sqrt((diffs ** 2).sum(axis=2)).min(axis=1)
            return float(np.sqrt((dists ** 2).mean()))
    distances, _idx = kd.query(mirrored, k=1)
    return float(np.sqrt((distances ** 2).mean()))


def _trimesh_apply_bilateral_symmetry(mesh, blend: float = 0.55):
    """v77zi: enforce bilateral symmetry across the YZ plane on character /
    creature / body_part meshes. Hunyuan3D occasionally outputs subtle
    left-right asymmetries (different shoulder height, one ear larger,
    facial features drifting off-axis); this averages each vertex with
    the mirror of its bilateral pair so the mesh ships with the kind of
    perfect symmetry Meshy enforces by default.

    Pre-step: re-center the vertex cloud on the YZ plane so x=0 is the
    actual symmetry axis, even when Hunyuan output drifted off-center.

    blend in [0, 1]:
      0.5 → perfect symmetric mean (most aggressive)
      0.55 → slightly biased toward the original (default — keeps subtle
             organic micro-detail while killing macro asymmetry)
      0.7  → light correction only
    """
    import numpy as np

    verts = np.asarray(mesh.vertices).copy()
    if len(verts) < 4:
        return mesh

    # Re-center on x=0 so the YZ plane is the actual symmetry axis.
    x_mean = float(verts[:, 0].mean())
    if abs(x_mean) > 1e-6:
        verts[:, 0] -= x_mean

    mirrored = verts.copy()
    mirrored[:, 0] = -mirrored[:, 0]

    try:
        kd = mesh.kdtree
    except Exception:
        try:
            from scipy.spatial import cKDTree
            kd = cKDTree(verts)
        except Exception:
            emit("symmetry_skip", f"no kdtree available, mesh has {len(verts)} verts")
            return mesh

    _dists, idx = kd.query(mirrored, k=1)
    matched_mirrored = verts[idx].copy()
    matched_mirrored[:, 0] = -matched_mirrored[:, 0]

    blend = max(0.0, min(1.0, float(blend)))
    new_verts = blend * verts + (1.0 - blend) * matched_mirrored

    if abs(x_mean) > 1e-6:
        new_verts[:, 0] += x_mean

    mesh.vertices = new_verts
    return mesh


_SCRIPT_DECIMATE_BLENDER = r"""
import bpy, sys
src, dst, ratio = sys.argv[-3], sys.argv[-2], float(sys.argv[-1])
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=src)
objs = [o for o in bpy.context.scene.objects if o.type == "MESH"]
if not objs:
    print("DECIM_FAIL: aucun maillage", flush=True); sys.exit(3)
for o in objs:
    bpy.context.view_layer.objects.active = o
    m = o.modifiers.new(name="decim", type="DECIMATE")
    m.decimate_type = "COLLAPSE"
    m.ratio = ratio
    m.use_collapse_triangulate = True
    bpy.ops.object.modifier_apply(modifier=m.name)
bpy.ops.export_scene.gltf(filepath=dst, export_format="GLB",
                          export_materials="EXPORT", export_texcoords=True,
                          export_normals=True, export_yup=True)
print("DECIM_OK", flush=True)
"""


def _decimate_texture_preservee(mesh, target_faces: int):
    """Decime SANS perdre les UV ni l'atlas.

    `simplify_quadric_decimation` de trimesh ne transporte pas les
    coordonnees de texture: mesure du 05/09 sur le personnage Caine,
    TextureVisuals (252 637 UV, atlas 2048) ressort en ColorVisuals avec
    uv=None. Tout ce qui suit devient impossible — le bake de normales
    s'arrete sur "low-poly has no UV map" et le GLB livre n'a plus AUCUN
    materiau: three.js retombe sur son materiau par defaut (metalness 1) et
    le personnage sort gris metallique. Ce defaut etait masque tant que
    le post-traitement mourait en OOM avant d'arriver ici.

    Blender interpole les UV a travers son modificateur Decimate. On lui
    confie donc l'operation quand le maillage est texture. Rend (mesh, jetes)
    ou None si la voie Blender n'est pas disponible.
    """
    import subprocess
    import tempfile
    from pathlib import Path
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from bake_normal_map import _find_blender
        exe = _find_blender()
        if not exe:
            return None
        import trimesh
        ratio = max(0.01, min(0.99, float(target_faces) / float(len(mesh.faces))))
        with tempfile.TemporaryDirectory() as td:
            src = str(Path(td) / "avant.glb")
            dst = str(Path(td) / "apres.glb")
            script = Path(td) / "decim.py"
            script.write_text(_SCRIPT_DECIMATE_BLENDER, encoding="utf-8")
            mesh.export(src)
            r = subprocess.run([exe, "-b", "-P", str(script), "--", src, dst,
                                "%.6f" % ratio],
                               capture_output=True, text=True, timeout=1800)
            if "DECIM_OK" not in (r.stdout or "") or not Path(dst).is_file():
                emit("post_warn", "decimation Blender indisponible (%s)"
                     % ((r.stdout or r.stderr or "")[-120:].replace("\n", " ")))
                return None
            rendu = trimesh.load(dst, force="mesh", process=False)
            if getattr(getattr(rendu, "visual", None), "uv", None) is None:
                emit("post_warn", "decimation Blender sans UV — ecartee")
                return None
            return rendu, len(mesh.faces) - len(rendu.faces)
    except Exception as exc:  # noqa: BLE001
        emit("post_warn", "decimation Blender echouee (%r)" % (exc,))
        return None


def _trimesh_decimate(mesh, target_faces: int):
    if target_faces <= 0 or len(mesh.faces) <= target_faces:
        return mesh, 0
    _texture = getattr(getattr(mesh, "visual", None), "uv", None) is not None
    if _texture:
        _via_blender = _decimate_texture_preservee(mesh, target_faces)
        if _via_blender is not None:
            emit("decimate", "decimation Blender (UV et atlas conserves)")
            return _via_blender
        # UN MODELE DENSE VAUT MIEUX QU'UN MODELE NU. Decimer ici couterait
        # la texture entiere; on garde donc la geometrie telle quelle.
        emit("post_warn", "decimation ecartee: elle detruirait les UV et "
                          "l'atlas (maillage dense conserve)")
        return mesh, 0
    try:
        new_mesh = mesh.simplify_quadric_decimation(face_count=target_faces)
        return new_mesh, len(mesh.faces) - len(new_mesh.faces)
    except Exception:
        # trimesh<4 used a slightly different name. Try the legacy path.
        try:
            new_mesh = mesh.simplify_quadratic_decimation(target_faces)  # type: ignore[attr-defined]
            return new_mesh, len(mesh.faces) - len(new_mesh.faces)
        except Exception as exc:
            emit("post_warn", f"decimation skipped ({exc})")
            return mesh, 0


# ---------------------------------------------------------------------------
# pymeshlab acceleration path — exposes more aggressive (and faster) filters
# than trimesh. We use it when available because:
#   - Screened Poisson reconstruction repairs holes and floaters in one pass
#   - HC Laplacian smoothing keeps volume better than trimesh laplacian
#   - Quadric edge collapse decimation preserves features
# ---------------------------------------------------------------------------


def _try_pymeshlab(input_path: str, output_path: str, profile: dict[str, Any]) -> dict[str, Any] | None:
    try:
        import pymeshlab
    except Exception:
        return None

    try:
        ms = pymeshlab.MeshSet()
        ms.load_new_mesh(input_path)
        before_faces = ms.current_mesh().face_number()
        before_verts = ms.current_mesh().vertex_number()

        # 1. Drop tiny disconnected components.
        try:
            ms.apply_filter(
                "remove_isolated_pieces_wrt_diameter",
                mincomponentdiag=pymeshlab.PercentageValue(profile["floater_ratio"] * 100.0),
                removeunref=True,
            )
        except Exception as exc:
            emit("post_warn", f"pymeshlab floater drop fallback ({exc})")

        # 2. Fill holes (close as many as possible — limit by hole size to avoid weird
        # interior surfaces being re-closed).
        if profile["fill_holes"]:
            try:
                ms.apply_filter("close_holes", maxholesize=120, selected=False)
            except Exception as exc:
                emit("post_warn", f"pymeshlab close_holes fallback ({exc})")

        # 3. HC Laplacian smoothing — preserves volume far better than vanilla laplacian.
        if profile["laplacian_iterations"] > 0:
            try:
                ms.apply_filter(
                    "apply_coord_hc_laplacian_smoothing",
                    iterations=int(profile["laplacian_iterations"]),
                )
            except Exception as exc:
                emit("post_warn", f"pymeshlab HC laplacian fallback ({exc})")

        # 4. Taubin smoothing — kills high-frequency noise.
        if profile["taubin_iterations"] > 0:
            try:
                ms.apply_filter(
                    "apply_coord_taubin_smoothing",
                    lambda_=float(profile["taubin_lamb"]),
                    mu=float(profile["taubin_mu"]),
                    stepsmoothnum=int(profile["taubin_iterations"]),
                )
            except Exception as exc:
                emit("post_warn", f"pymeshlab taubin fallback ({exc})")

        # 4b. v77zi: bilateral symmetry enforcement before decimation.
        # pymeshlab does not expose a vertex-pair averaging filter, so we
        # round-trip through trimesh: export current state, run the trimesh
        # symmetry pass, re-import. Best-effort — falls back silently if
        # trimesh isn't installed alongside pymeshlab.
        if profile.get("enforce_symmetry"):
            try:
                import trimesh as _tm
                import tempfile

                with tempfile.NamedTemporaryFile(suffix=".ply", delete=False) as tmp_handle:
                    sym_tmp_path = tmp_handle.name
                ms.save_current_mesh(sym_tmp_path)
                tm_mesh = _tm.load(sym_tmp_path)
                if isinstance(tm_mesh, _tm.Trimesh):
                    before_asym = _measure_bilateral_asymmetry(tm_mesh)
                    tm_mesh = _trimesh_apply_bilateral_symmetry(tm_mesh, blend=profile.get("symmetry_blend", 0.55))
                    after_asym = _measure_bilateral_asymmetry(tm_mesh)
                    tm_mesh.export(sym_tmp_path)
                    ms.load_new_mesh(sym_tmp_path)
                    emit("symmetry", f"bilateral RMS asym {before_asym:.5f} -> {after_asym:.5f}")
                try:
                    os.unlink(sym_tmp_path)
                except Exception:
                    pass
            except Exception as exc:
                emit("post_warn", f"pymeshlab symmetry round-trip fallback ({exc})")

        # 5. Decimation to target face count when over-tessellated.
        if profile["decimate_target_faces"] > 0 and before_faces > profile["decimate_target_faces"]:
            try:
                ms.apply_filter(
                    "meshing_decimation_quadric_edge_collapse",
                    targetfacenum=int(profile["decimate_target_faces"]),
                    qualitythr=0.6,
                    preserveboundary=True,
                    boundaryweight=2.0,
                    preservenormal=True,
                    preservetopology=True,
                    optimalplacement=True,
                    planarquadric=True,
                    qualityweight=False,
                    autoclean=True,
                )
            except Exception as exc:
                emit("post_warn", f"pymeshlab decimation fallback ({exc})")

        # 6. Recompute normals (kills flipped triangles → dark patches in the viewer).
        try:
            ms.apply_filter("compute_normal_per_face")
            ms.apply_filter("compute_normal_per_vertex", weightmode=2)
        except Exception as exc:
            emit("post_warn", f"pymeshlab normal recompute ignored ({exc})")

        # 7. Optional subdivision pass for organic subjects only.
        if profile["subdivide_pass"]:
            try:
                ms.apply_filter("meshing_surface_subdivision_loop", iterations=1)
            except Exception as exc:
                emit("post_warn", f"pymeshlab subdivision fallback ({exc})")

        ms.save_current_mesh(output_path)
        after_faces = ms.current_mesh().face_number()
        after_verts = ms.current_mesh().vertex_number()
        emit("post_done", f"pymeshlab pipeline: {before_faces}→{after_faces} faces, {before_verts}→{after_verts} verts")
        return {
            "engine": "pymeshlab",
            "before_faces": before_faces,
            "after_faces": after_faces,
            "before_verts": before_verts,
            "after_verts": after_verts,
        }
    except Exception as exc:
        emit("post_warn", f"pymeshlab pipeline failed, falling back to trimesh ({exc})")
        return None


def _capture_mesh_dimensions(mesh) -> tuple[float, list[float]]:
    """Return (volume_or_area, bounding_box_extents) for the mesh — used to
    compute a volume-preservation scale factor after smoothing."""
    try:
        if hasattr(mesh, "is_volume") and mesh.is_volume:
            return float(mesh.volume), [float(e) for e in mesh.extents]
    except Exception:
        pass
    try:
        return float(mesh.area), [float(e) for e in mesh.extents]
    except Exception:
        return 1.0, [1.0, 1.0, 1.0]


def _restore_mesh_volume(mesh, before_size: float, after_size: float):
    """Apply a uniform scale to bring the mesh back to its pre-smoothing
    volume (or surface area for non-watertight meshes). Without this step
    the character's torso, head, and limbs look slightly skinnier than the
    silhouette captured by Hunyuan3D — visible on full-body renders."""
    if before_size <= 0 or after_size <= 0:
        return mesh
    ratio = before_size / after_size
    # Compute scale: volume scales with cube of linear, area with square.
    # Use cube root for volume, square root for area as a heuristic.
    scale = ratio ** (1.0 / 3.0) if ratio > 1e-6 else 1.0
    if 0.985 < scale < 1.015:
        # Sub-1.5% drift — not worth correcting (risks introducing tiny seams).
        return mesh
    try:
        mesh.apply_scale(scale)
        emit("volume_restore", f"applied uniform scale {scale:.4f} to restore volume")
    except Exception as exc:
        emit("post_warn", f"volume restore skipped ({exc})")
    return mesh


def _apply_target_dimension(mesh, target_meters: float, axis: str = "max"):
    """v81: scale the mesh so its largest extent (or specified axis) matches
    the target dimension in meters. The user typing '30cm pendule' or '1m
    sword' triggers a deterministic resize so downstream rigging (pendulum
    period via T=2pi*sqrt(L/g), vehicle wheel radius) uses real units instead
    of whatever Hunyuan3D-2.1 emitted at unit-cube scale."""
    try:
        extents = list(mesh.extents)
    except Exception:
        return mesh
    if not extents or all(e <= 0 for e in extents):
        return mesh
    if axis == "x":
        current = float(extents[0])
    elif axis == "y":
        current = float(extents[1])
    elif axis == "z":
        current = float(extents[2])
    else:
        current = float(max(extents))
    if current <= 0 or target_meters <= 0:
        return mesh
    scale = target_meters / current
    if 0.99 < scale < 1.01:
        return mesh
    try:
        mesh.apply_scale(scale)
        emit("target_dimension", f"scaled mesh by {scale:.4f} -> {axis}={target_meters:.3f}m")
    except Exception as exc:
        emit("post_warn", f"target dimension scale skipped ({exc})")
    return mesh


def _trimesh_pipeline(input_path: str, output_path: str, profile: dict[str, Any]) -> dict[str, Any]:
    import trimesh

    raw = trimesh.load(input_path)
    if isinstance(raw, trimesh.Scene):
        meshes = [g for g in raw.geometry.values() if isinstance(g, trimesh.Trimesh)]
        if not meshes:
            raise RuntimeError("Scene without any usable mesh")
        mesh = trimesh.util.concatenate(meshes) if len(meshes) > 1 else meshes[0]
    else:
        mesh = raw

    before_faces = len(mesh.faces)
    before_verts = len(mesh.vertices)
    before_size, _ = _capture_mesh_dimensions(mesh) if profile.get("preserve_volume") else (0.0, [])

    mesh, dropped = _trimesh_drop_floaters(mesh, profile["floater_ratio"])
    if dropped:
        emit("floaters", f"{dropped} disconnected micro-shells dropped")

    if profile["fill_holes"]:
        mesh = _trimesh_fill_holes(mesh)

    mesh = _trimesh_laplacian_smoothing(mesh, profile["laplacian_iterations"])
    mesh = _trimesh_taubin_smoothing(
        mesh,
        profile["taubin_iterations"],
        profile["taubin_lamb"],
        profile["taubin_mu"],
    )

    if profile.get("preserve_volume") and before_size > 0:
        after_size, _ = _capture_mesh_dimensions(mesh)
        mesh = _restore_mesh_volume(mesh, before_size, after_size)

    # v77zi: bilateral symmetry enforcement after smoothing — kills the
    # subtle Hunyuan3D left-right drift on characters / creatures /
    # body_parts before decimation locks the topology.
    if profile.get("enforce_symmetry"):
        before_asym = _measure_bilateral_asymmetry(mesh)
        mesh = _trimesh_apply_bilateral_symmetry(mesh, blend=profile.get("symmetry_blend", 0.55))
        after_asym = _measure_bilateral_asymmetry(mesh)
        emit("symmetry", f"bilateral RMS asym {before_asym:.5f} -> {after_asym:.5f}")

    mesh, decimated = _trimesh_decimate(mesh, profile["decimate_target_faces"])
    if decimated:
        emit("decimate", f"{decimated} faces removed by decimation")

    mesh = _trimesh_fix_normals(mesh)

    # v81: optional target dimension scaling (last step before export so the
    # GLB ships at the user-requested size).
    target_dim = profile.get("target_dimension_meters")
    if target_dim and target_dim > 0:
        target_axis = profile.get("target_dimension_axis", "max")
        mesh = _apply_target_dimension(mesh, float(target_dim), str(target_axis))

    mesh.export(output_path)
    after_faces = len(mesh.faces)
    after_verts = len(mesh.vertices)
    emit("post_done", f"trimesh pipeline: {before_faces}→{after_faces} faces, {before_verts}→{after_verts} verts")
    return {
        "engine": "trimesh",
        "before_faces": before_faces,
        "after_faces": after_faces,
        "before_verts": before_verts,
        "after_verts": after_verts,
        "dropped_floaters": dropped,
        "target_dimension_meters": target_dim,
    }


def post_process(
    input_path: str,
    output_path: str,
    intent_purpose: str = "default",
    motion_readiness: str = "static_only",
    overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"input mesh not found: {input_path}")

    profile = resolve_profile(intent_purpose, motion_readiness)
    if overrides:
        profile.update({k: v for k, v in overrides.items() if v is not None})

    emit("post_start", f"profile={intent_purpose}/{motion_readiness} — taubin {profile['taubin_iterations']}, decimate target {profile['decimate_target_faces']}")

    pml_result = _try_pymeshlab(input_path, output_path, profile)
    if pml_result is not None:
        return {"ok": True, **pml_result}

    tm_result = _trimesh_pipeline(input_path, output_path, profile)
    return {"ok": True, **tm_result}


def main():
    configure_ml_cache_environment()
    parser = argparse.ArgumentParser(description="Aurora mesh post-processing")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--intent-purpose", default="default")
    parser.add_argument("--motion-readiness", default="static_only")
    parser.add_argument("--floater-ratio", type=float, default=None)
    parser.add_argument("--smooth-iterations", type=int, default=None)
    parser.add_argument("--target-faces", type=int, default=None)
    parser.add_argument("--no-fill-holes", action="store_true")
    parser.add_argument("--subdivide", action="store_true")
    parser.add_argument(
        "--target-dimension-meters",
        type=float,
        default=None,
        help="v81: scale the exported mesh so its largest extent (or chosen axis) matches this size in meters",
    )
    parser.add_argument(
        "--target-dimension-axis",
        choices=["max", "x", "y", "z"],
        default="max",
        help="Axis used by --target-dimension-meters (default: max bounding-box axis)",
    )
    parser.add_argument(
        "--enforce-symmetry",
        action="store_true",
        help="v77zi: bilateral symmetry enforcement across YZ plane (recommended for character/creature/body_part)",
    )
    parser.add_argument(
        "--symmetry-blend",
        type=float,
        default=0.55,
        help="Symmetry blend in [0..1]: 0.5 perfect symmetric mean, 0.55 default (lean original), 0.7 light correction only",
    )
    args = parser.parse_args()

    overrides: dict[str, Any] = {}
    if args.floater_ratio is not None:
        overrides["floater_ratio"] = args.floater_ratio
    if args.smooth_iterations is not None:
        overrides["taubin_iterations"] = args.smooth_iterations
    if args.target_faces is not None:
        overrides["decimate_target_faces"] = args.target_faces
    if args.no_fill_holes:
        overrides["fill_holes"] = False
    if args.subdivide:
        overrides["subdivide_pass"] = True
    if args.target_dimension_meters is not None and args.target_dimension_meters > 0:
        overrides["target_dimension_meters"] = args.target_dimension_meters
        overrides["target_dimension_axis"] = args.target_dimension_axis
    if args.enforce_symmetry:
        overrides["enforce_symmetry"] = True
        overrides["symmetry_blend"] = float(args.symmetry_blend)

    try:
        result = post_process(
            args.input,
            args.output,
            intent_purpose=args.intent_purpose,
            motion_readiness=args.motion_readiness,
            overrides=overrides,
        )
        emit_json({"ok": True, "outputPath": args.output, **result})
        return 0
    except Exception as exc:
        emit_json({"ok": False, "error": str(exc)[-500:]})
        return 1


if __name__ == "__main__":
    sys.exit(main())
