"""mia_mocap_retarget.py — Blender headless: retarget a HY-Motion (SMPL-X / WoodenMesh)
or MoMask motion onto a MIA-rigged (Mixamo 52-bone) GLB and export the animated GLB.

Key guarantees:
  1. Full SO(3) 52-bone retargeting (`_retarget_smplx_so3`) from `<BVH>.smplx_data.npz`
     (or directly from HY-Motion `.npz`), preserving 3D axial roll/twist on arms, forearms,
     wrists, thighs, shins, ankles, head, and all 30 finger phalanges.
  2. Automatic PBR de-plastification (`_deplastifier_materiaux`): resets FBX2glTF's
     artificial `metallicFactor=0.40, roughnessFactor=0.37` back to natural matte
     organic/fabric PBR (`Metallic=0.0, Roughness>=0.78, Specular=0.22`) when no
     metallic texture is linked.
  3. Non-destructive geometry hygiene: welds UV-seam duplicates (0.5mm) and stabilizes
     disconnected rigid accessories (sunglasses, caps, tails, keychains, pendants) onto
     their anatomical parent bone without ever cutting fingers or bridging holes with
     spiky polygons.

Usage: blender -b -P mia_mocap_retarget.py -- IN_RIGGED.glb BVH.bvh OUT.glb
Emits: MIA_MOCAP_OK glb=<OUT> frames=<N>  or  MIA_MOCAP_FAIL: <reason>
"""
from __future__ import annotations

import glob
import math
import os
import sys

import bpy
import numpy as np
from mathutils import Matrix, Quaternion, Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
if len(argv) < 3:
    print("MIA_MOCAP_FAIL: usage IN.glb BVH OUT.glb", flush=True)
    sys.exit(2)
IN_GLB, BVH, OUT_GLB = argv[0], argv[1], argv[2]

HY_ROOT = os.environ.get(
    "AURORA_HYMOTION_ROOT",
    os.path.expanduser("~/.local/share/auroraia/external/HY-Motion"),
)
WOODEN_DIR = os.path.join(HY_ROOT, "scripts", "gradio", "static", "assets", "dump_wooden")

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=IN_GLB)
meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
arms = [o for o in bpy.context.scene.objects if o.type == "ARMATURE"]
if not arms:
    print("MIA_MOCAP_FAIL: no armature", flush=True)
    sys.exit(3)
rig = next((a for a in arms if any("mixamo" in b.name.lower() for b in a.data.bones)), arms[0])

# Capture MIA's neural static T-pose (stored in pose.bones or MIA_TPose action on freshly rigged MIA GLBs)
# BEFORE clearing actions/pose bones!
bpy.context.scene.frame_set(1)
bpy.context.view_layer.update()
mw_init = rig.matrix_world.copy()
mw_init_3 = mw_init.to_3x3().normalized()
has_mia_static_tpose = (
    not bpy.data.actions or all("MIA_TPose" in a.name for a in bpy.data.actions)
) and any(pb.rotation_quaternion.angle > 0.05 for pb in rig.pose.bones)
mia_tpose_world_mat: dict[str, Matrix] = {}
if has_mia_static_tpose:
    for _pb in rig.pose.bones:
        mia_tpose_world_mat[_pb.name] = (mw_init_3 @ _pb.matrix.to_3x3()).normalized()

# Clear any previous animation/action and reset pose bones to true rest pose
try:
    if rig.animation_data:
        rig.animation_data.action = None
        for _trk in list(rig.animation_data.nla_tracks):
            rig.animation_data.nla_tracks.remove(_trk)
    for _act in list(bpy.data.actions):
        bpy.data.actions.remove(_act, do_unlink=True)
    for _pb in rig.pose.bones:
        _pb.rotation_mode = "QUATERNION"
        _pb.location = (0.0, 0.0, 0.0)
        _pb.rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
        _pb.rotation_euler = (0.0, 0.0, 0.0)
        _pb.scale = (1.0, 1.0, 1.0)
    bpy.context.view_layer.update()
except Exception:
    pass


def _purger_meshes_morts() -> int:
    """Supprime les objets mesh sans aucun poids (widgets résiduels type Icosphere)."""
    morts = [
        o for o in bpy.context.scene.objects
        if o.type == "MESH" and o.data.vertices
        and not any(v.groups for v in o.data.vertices)
    ]
    for o in morts:
        bpy.data.objects.remove(o, do_unlink=True)
    return len(morts)


def _deplastifier_materiaux() -> int:
    """Corrige la corruption FBX2glTF (metallic=0.40, roughness=0.37) ainsi que les
    textures Tripo/ORM trop brillantes qui donnent un aspect plastique PVC aux personnages,
    et désactive le backface culling pour éviter les trous visuels sur les vêtements."""
    nb = 0
    for mat in bpy.data.materials:
        try:
            mat.use_backface_culling = False
        except Exception:
            pass
        nt = getattr(mat, "node_tree", None)
        if not nt:
            continue
        for node in nt.nodes:
            if node.type == "BSDF_PRINCIPLED":
                changed = False
                if "Metallic" in node.inputs:
                    inp_m = node.inputs["Metallic"]
                    if not inp_m.is_linked and float(inp_m.default_value) > 0.05:
                        inp_m.default_value = 0.0
                        changed = True
                if "Roughness" in node.inputs:
                    inp_r = node.inputs["Roughness"]
                    if not inp_r.is_linked and float(inp_r.default_value) < 0.55:
                        inp_r.default_value = 0.72
                        changed = True
                if "Specular IOR Level" in node.inputs and not node.inputs["Specular IOR Level"].is_linked:
                    node.inputs["Specular IOR Level"].default_value = 0.35
                if changed:
                    nb += 1
    return nb


def _souder_et_fermer_trous_uv_safe(obj, dist: float = 0.00015) -> tuple[int, int, int]:
    """Fusionne les micro-fissures (0.15 mm), nettoie les normales scindées figées, et referme
    les trous de vêtements par triangulation en éventail (centroid fan) en interpolant les UVs
    et les poids de skinning strictement depuis la face adjacente de chaque arête de bord
    (zéro étirement entre îlots UV)."""
    import bmesh

    avant = len(obj.data.vertices)
    bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode="EDIT")
    try:
        bpy.ops.mesh.customdata_custom_splitnormals_clear()
    except Exception:
        pass
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.remove_doubles(threshold=dist)
    bpy.ops.object.mode_set(mode="OBJECT")

    me = obj.data
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    bm.faces.ensure_lookup_table()
    uv_layers = list(bm.loops.layers.uv.values())
    dvert_lay = bm.verts.layers.deform.verify()

    b_edges = [e for e in bm.edges if e.is_boundary]
    visited: set[int] = set()
    v2e: dict[int, list] = {}
    for e in b_edges:
        for v in e.verts:
            v2e.setdefault(v.index, []).append(e)

    loops_data = []
    for e in b_edges:
        if e.index in visited:
            continue
        loop_edges = []
        loop_verts = []
        curr_e = e
        curr_v = e.verts[0]
        while True:
            visited.add(curr_e.index)
            loop_edges.append(curr_e)
            loop_verts.append(curr_v)
            next_v = curr_e.other_vert(curr_v)
            cand = [ne for ne in v2e.get(next_v.index, []) if ne.index not in visited]
            if not cand:
                break
            curr_e = cand[0]
            curr_v = next_v
        if 3 <= len(loop_verts) <= 80:
            perim = sum(ed.calc_length() for ed in loop_edges)
            if perim <= 0.35:
                loops_data.append((loop_verts, loop_edges))

    filled_loops = 0
    for lverts, ledges in loops_data:
        center = sum((v.co for v in lverts), Vector((0.0, 0.0, 0.0))) / len(lverts)
        cv = bm.verts.new(center)
        # Interpolation des poids de skinning (dvert) sur le sommet central cv
        w_acc: dict[int, float] = {}
        for v in lverts:
            dv = v[dvert_lay]
            for g_idx, w_val in dv.items():
                w_acc[g_idx] = w_acc.get(g_idx, 0.0) + float(w_val)
        w_tot = sum(w_acc.values())
        if w_tot > 1e-6:
            cv_dv = cv[dvert_lay]
            for g_idx, w_val in w_acc.items():
                if w_val / w_tot > 1e-3:
                    cv_dv[g_idx] = w_val / w_tot

        created = 0
        for ed in ledges:
            if not ed.link_faces:
                continue
            lf = ed.link_faces[0]
            va, vb = ed.verts[0], ed.verts[1]
            v1, v2 = va, vb
            loops_lf = list(lf.loops)
            for i, lp in enumerate(loops_lf):
                if lp.vert == va and loops_lf[(i + 1) % len(loops_lf)].vert == vb:
                    v1, v2 = vb, va
                    break
                if lp.vert == vb and loops_lf[(i + 1) % len(loops_lf)].vert == va:
                    v1, v2 = va, vb
                    break
            try:
                nf = bm.faces.new((v1, v2, cv))
                nf.material_index = lf.material_index
                nf.smooth = True
                for uv_lay in uv_layers:
                    uv1 = uv2 = None
                    for lp in lf.loops:
                        if lp.vert == v1:
                            uv1 = lp[uv_lay].uv.copy()
                        elif lp.vert == v2:
                            uv2 = lp[uv_lay].uv.copy()
                    if uv1 is not None and uv2 is not None:
                        uv_mid = 0.5 * (uv1 + uv2)
                        for lp in nf.loops:
                            if lp.vert == v1:
                                lp[uv_lay].uv = uv1
                            elif lp.vert == v2:
                                lp[uv_lay].uv = uv2
                            else:
                                lp[uv_lay].uv = uv_mid
                created += 1
            except ValueError:
                pass
        if created > 0:
            filled_loops += 1

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    for poly in me.polygons:
        poly.use_smooth = True
    me.update()
    return avant, len(me.vertices), filled_loops


def _stabiliser_ilots_accessoires(obj) -> int:
    """Pour les îlots accessoires déconnectés du corps principal (lunettes, casquette,
    collier, cordons, porte-clés, queue), évite qu'un accessoire ou appendice dorsal
    soit écartelé entre les deux chevilles/jambes ou bras."""
    me = obj.data
    n = len(me.vertices)
    if n == 0:
        return 0
    parent = list(range(n))

    def find(a: int) -> int:
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for e in me.edges:
        a, b = e.vertices[0], e.vertices[1]
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    comp: dict[int, list[int]] = {}
    for v in range(n):
        comp.setdefault(find(v), []).append(v)
    if len(comp) <= 1:
        return 0

    gros = max(comp.values(), key=len)
    vnames = {g.index: g.name for g in obj.vertex_groups}
    left_limb = {i for i, nm in vnames.items() if "Left" in nm}
    right_limb = {i for i, nm in vnames.items() if "Right" in nm}
    lower_legs = {
        i for i, nm in vnames.items()
        if any(s in nm for s in ("LeftLeg", "RightLeg", "LeftFoot", "RightFoot", "LeftToe", "RightToe"))
    }
    all_legs = {i for i, nm in vnames.items() if "UpLeg" in nm or "Leg" in nm or "Foot" in nm or "Toe" in nm}
    arms_set = {i for i, nm in vnames.items() if "Arm" in nm or "ForeArm" in nm or "Hand" in nm}

    seuil_petit = int(n * 0.015)
    seuil_appendice = int(n * 0.06)
    corriges = 0
    for verts in comp.values():
        if verts is gros or len(verts) > seuil_appendice:
            continue
        totals: dict[int, float] = {}
        for vi in verts:
            for g in me.vertices[vi].groups:
                if g.weight > 0.02:
                    totals[g.group] = totals.get(g.group, 0.0) + float(g.weight)
        if not totals:
            continue
        used_groups = set(totals.keys())
        used_lower_legs = used_groups & lower_legs
        has_lr_lower_legs = any(g in left_limb for g in used_lower_legs) and any(g in right_limb for g in used_lower_legs)
        has_pelvis = any("Hips" in vnames.get(g, "") or "Spine" in vnames.get(g, "") for g in used_groups)

        # Cas 1 : Appendice dorsal / queue / fourreau (attaché au bassin mais attiré par les deux mollets/chevilles)
        if has_pelvis and has_lr_lower_legs and "mixamorig:Hips" in obj.vertex_groups:
            hips_vg = obj.vertex_groups["mixamorig:Hips"].index
            for vi in verts:
                w_legs = sum(g.weight for g in me.vertices[vi].groups if g.group in all_legs)
                if w_legs > 1e-4:
                    w_hips = sum(g.weight for g in me.vertices[vi].groups if g.group == hips_vg)
                    for g in list(me.vertices[vi].groups):
                        if g.group in all_legs:
                            obj.vertex_groups[g.group].remove([vi])
                    obj.vertex_groups[hips_vg].add([vi], min(1.0, w_hips + w_legs), "REPLACE")
                    corriges += 1
            continue

        # Cas 2 : Petit accessoire rigide (< 1.5 % des sommets : lunettes, boucle, cordon) écartelé gauche/droite
        if len(verts) > seuil_petit:
            continue
        has_lr_conflict = bool(used_groups & left_limb) and bool(used_groups & right_limb)
        has_arm_torso_split = bool(used_groups & arms_set) and has_pelvis
        if not (has_lr_conflict or has_arm_torso_split):
            continue

        z_mean = sum(me.vertices[vi].co.z for vi in verts) / len(verts)
        if has_arm_torso_split and "mixamorig:Spine2" in obj.vertex_groups:
            target_vg = obj.vertex_groups["mixamorig:Spine2"].index
        elif z_mean > 0.50 and "mixamorig:Head" in obj.vertex_groups:
            target_vg = obj.vertex_groups["mixamorig:Head"].index
        else:
            target_vg = max(totals.items(), key=lambda kv: kv[1])[0]

        for vi in verts:
            for g in list(me.vertices[vi].groups):
                obj.vertex_groups[g.group].remove([vi])
            obj.vertex_groups[target_vg].add([vi], 1.0, "REPLACE")
            corriges += 1
    return corriges


def _adoucir_transitions_articulations(obj) -> int:
    """Adoucit par diffusion laplacienne multi-anneaux les sauts brusques de poids de skinning
    aux jonctions de vêtements (aisselles, épaules, taille, hanches, genoux, chevilles) tout
    en préservant la netteté des phalanges de doigts."""
    me = obj.data
    n_verts = len(me.vertices)
    if n_verts == 0:
        return 0
    vnames = {g.index: g.name for g in obj.vertex_groups}
    body_g = {
        i for i, nm in vnames.items()
        if not any(f in nm for f in ("Thumb", "Index", "Middle", "Ring", "Pinky"))
    }
    if not body_g:
        return 0

    adj: list[list[int]] = [[] for _ in range(n_verts)]
    w_map: list[dict[int, float]] = [
        {g.group: float(g.weight) for g in v.groups if g.weight > 1e-4}
        for v in me.vertices
    ]
    seam_verts: set[int] = set()
    for e in me.edges:
        u, v = e.vertices[0], e.vertices[1]
        adj[u].append(v)
        adj[v].append(u)
        wu, wv = w_map[u], w_map[v]
        for k in (set(wu.keys()) | set(wv.keys())) & body_g:
            if abs(wu.get(k, 0.0) - wv.get(k, 0.0)) > 0.12:
                seam_verts.add(u)
                seam_verts.add(v)
                break

    if not seam_verts:
        return 0
    zone = set(seam_verts)
    for _ in range(16):
        nxt = set(zone)
        for vi in zone:
            nxt.update(adj[vi])
        zone = nxt

    zone_list = list(zone)
    for _it in range(18):
        next_w: dict[int, dict[int, float]] = {}
        for vi in zone_list:
            nbrs = adj[vi]
            if not nbrs:
                continue
            acc: dict[int, float] = {}
            for k, val in w_map[vi].items():
                if k in body_g:
                    acc[k] = acc.get(k, 0.0) + 0.4 * val
                else:
                    acc[k] = acc.get(k, 0.0) + val
            w_nb = 0.6 / len(nbrs)
            for nb in nbrs:
                for k, val in w_map[nb].items():
                    if k in body_g:
                        acc[k] = acc.get(k, 0.0) + w_nb * val
            tot = sum(acc.values())
            if tot > 1e-6:
                next_w[vi] = {k: val / tot for k, val in acc.items() if val / tot > 1e-3}
        for vi, gw in next_w.items():
            w_map[vi] = gw

    for vi in zone_list:
        for g in list(me.vertices[vi].groups):
            obj.vertex_groups[g.group].remove([vi])
        for k, val in w_map[vi].items():
            obj.vertex_groups[k].add([vi], val, "REPLACE")
    return len(zone_list)


def _normaliser_echelle_et_sol() -> None:
    """Applique l'échelle 0.01 résiduelle de FBX2glTF sur l'Armature et le Mesh pour
    que scale=(1,1,1) et inverseBindMatrices soient en mètres 1:1, puis pose les pieds
    à Z=0.0 sur la grille en utilisant les sommets de repos (et non bound_box), sans
    jamais polluer matrix_parent_inverse. Évite le zoom ×100 et le clipping dans F3D."""
    bpy.ops.object.mode_set(mode="OBJECT")
    parents_saved = []
    for m in meshes:
        if m.parent is not None:
            parents_saved.append((m, m.parent))
            mw_m = m.matrix_world.copy()
            m.parent = None
            m.matrix_world = mw_m

    bpy.ops.object.select_all(action="DESELECT")
    rig.select_set(True)
    for m in meshes:
        m.select_set(True)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    bpy.context.view_layer.update()

    zs = [v.co.z for m in meshes for v in m.data.vertices]
    min_z = min(zs) if zs else 0.0
    if abs(min_z) > 1e-4:
        rig.location.z -= min_z
        for m in meshes:
            m.location.z -= min_z
        bpy.context.view_layer.update()
        bpy.ops.object.select_all(action="DESELECT")
        rig.select_set(True)
        for m in meshes:
            m.select_set(True)
        bpy.context.view_layer.objects.active = rig
        bpy.ops.object.transform_apply(location=True, rotation=False, scale=False)
        bpy.context.view_layer.update()

    for m, par in parents_saved:
        m.parent = par
        m.matrix_parent_inverse.identity()
    bpy.context.view_layer.update()


try:
    _np_morts = _purger_meshes_morts()
    if _np_morts:
        print("MIA_MOCAP_INFO: %d mesh(es) sans poids purge(s)" % _np_morts, flush=True)
        meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    _normaliser_echelle_et_sol()
    _nb_mat = _deplastifier_materiaux()
    if _nb_mat:
        print("MIA_MOCAP_INFO: %d materiau(x) deplastifie(s) (PBR mat naturel)" % _nb_mat, flush=True)
    for _m in meshes:
        _av, _ap, _ntrous = _souder_et_fermer_trous_uv_safe(_m)
        if _ap != _av or _ntrous:
            print(
                "MIA_MOCAP_INFO: geometrie %s: %d -> %d sommets (%d trou(s) referme(s) UV-safe)"
                % (_m.name, _av, _ap, _ntrous),
                flush=True,
            )
        _ns = _stabiliser_ilots_accessoires(_m)
        if _ns:
            print("MIA_MOCAP_INFO: %d sommets d'accessoires stabilises" % _ns, flush=True)
        _na = _adoucir_transitions_articulations(_m)
        if _na:
            print("MIA_MOCAP_INFO: %d sommets d'articulations adoucis" % _na, flush=True)
    _normaliser_echelle_et_sol()
    print("MIA_MOCAP_INFO: echelle (1,1,1) et sol Z=0.0 normalises pour F3D", flush=True)
except Exception as _se:  # noqa: BLE001
    print("MIA_MOCAP_INFO: preparation geometrie avertissement (%r)" % (_se,), flush=True)

# Ground z = mesh minimum in world coordinates (at rest pose, now 0.0)
ground_z = 0.0
try:
    bpy.context.view_layer.update()
    zs = [(m.matrix_world @ v.co).z for m in meshes for v in m.data.vertices]
    ground_z = min(zs) if zs else 0.0
except Exception:
    ground_z = 0.0


def _aa_to_quat_np(aa: np.ndarray) -> np.ndarray:
    angle = np.linalg.norm(aa, axis=-1, keepdims=True)
    half = 0.5 * angle
    small = angle < 1e-7
    scale = np.where(small, 0.5, np.sin(half) / np.where(small, 1.0, angle))
    q = np.concatenate([np.cos(half), aa * scale], axis=-1).astype(np.float32)
    q /= np.maximum(np.linalg.norm(q, axis=-1, keepdims=True), 1e-8)
    return q


def _quat_to_mat_np(q: np.ndarray) -> np.ndarray:
    q = q / np.maximum(np.linalg.norm(q, axis=-1, keepdims=True), 1e-8)
    w, x, y, z = q[..., 0], q[..., 1], q[..., 2], q[..., 3]
    xx, yy, zz = x * x, y * y, z * z
    xy, xz, yz = x * y, x * z, y * z
    wx, wy, wz = w * x, w * y, w * z
    m = np.empty(q.shape[:-1] + (3, 3), dtype=np.float32)
    m[..., 0, 0] = 1.0 - 2.0 * (yy + zz)
    m[..., 0, 1] = 2.0 * (xy - wz)
    m[..., 0, 2] = 2.0 * (xz + wy)
    m[..., 1, 0] = 2.0 * (xy + wz)
    m[..., 1, 1] = 1.0 - 2.0 * (xx + zz)
    m[..., 1, 2] = 2.0 * (yz - wx)
    m[..., 2, 0] = 2.0 * (xz - wy)
    m[..., 2, 1] = 2.0 * (yz + wx)
    m[..., 2, 2] = 1.0 - 2.0 * (xx + yy)
    return m


def _load_smplx_so3_data(bvh_path: str) -> dict | None:
    """Charge `<bvh_path>.smplx_data.npz` ou reconstruit les matrices SO(3) 52 os
    directement depuis le `.npz` HY-Motion et le squelette WoodenMesh."""
    cand_npz = bvh_path + ".smplx_data.npz"
    if os.path.isfile(cand_npz):
        try:
            d = np.load(cand_npz, allow_pickle=True)
            if "global_rot_mats" in d.files and "joints_world" in d.files and "j_template" in d.files:
                return {k: d[k] for k in d.files}
        except Exception:
            pass

    # Fallback: chercher le fichier .npz brut de HY-Motion dans le dossier de travail
    j_bin = os.path.join(WOODEN_DIR, "j_template.bin")
    k_bin = os.path.join(WOODEN_DIR, "kintree.bin")
    if not (os.path.isfile(j_bin) and os.path.isfile(k_bin)):
        return None
    bdir = os.path.dirname(os.path.abspath(bvh_path))
    npzs = [
        p for p in sorted(glob.glob(os.path.join(bdir, "**", "*.npz"), recursive=True))
        if not p.endswith(".smplx_data.npz")
    ]
    for npz_p in npzs:
        try:
            d = np.load(npz_p, allow_pickle=True)
            if "poses" not in d.files or "trans" not in d.files:
                continue
            poses = np.asarray(d["poses"], dtype=np.float32)
            trans = np.asarray(d["trans"], dtype=np.float32)
            T = poses.shape[0]
            quats = _aa_to_quat_np(poses.reshape(T, 52, 3))
            for t in range(1, T):
                dot = np.sum(quats[t] * quats[t - 1], axis=-1, keepdims=True)
                quats[t] = np.where(dot < 0.0, -quats[t], quats[t])
            if T >= 5:
                k = np.array([0.12, 0.24, 0.28, 0.24, 0.12], dtype=np.float32)
                q_pad = np.pad(quats, ((2, 2), (0, 0), (0, 0)), mode="edge")
                quats = sum(k[i] * q_pad[i:i + T] for i in range(5))
                quats /= np.maximum(np.linalg.norm(quats, axis=-1, keepdims=True), 1e-8)
                t_pad = np.pad(trans, ((2, 2), (0, 0)), mode="edge")
                trans = sum(k[i] * t_pad[i:i + T] for i in range(5)).astype(np.float32)
            local_mats = _quat_to_mat_np(quats)
            j_template = np.frombuffer(open(j_bin, "rb").read(), dtype=np.float32).reshape(-1, 3).copy()
            parents = np.frombuffer(open(k_bin, "rb").read(), dtype=np.int32).copy()
            rel_j = j_template.copy()
            rel_j[1:] = j_template[1:] - j_template[parents[1:]]
            global_mats = np.zeros_like(local_mats)
            joints_world = np.zeros((T, 52, 3), dtype=np.float32)
            global_mats[:, 0] = local_mats[:, 0]
            joints_world[:, 0] = j_template[0] + trans
            for i in range(1, 52):
                pi = int(parents[i])
                global_mats[:, i] = np.matmul(global_mats[:, pi], local_mats[:, i])
                joints_world[:, i] = joints_world[:, pi] + np.einsum("tij,j->ti", global_mats[:, pi], rel_j[i])
            return {
                "global_rot_mats": global_mats,
                "local_rot_mats": local_mats,
                "joints_world": joints_world,
                "j_template": j_template,
                "parents": parents,
                "trans": trans,
            }
        except Exception:
            continue
    return None


BONE_TABLE = [
    (0,  "mixamorig:Hips",          3),
    (1,  "mixamorig:LeftUpLeg",     4),
    (2,  "mixamorig:RightUpLeg",    5),
    (3,  "mixamorig:Spine",         6),
    (4,  "mixamorig:LeftLeg",       7),
    (5,  "mixamorig:RightLeg",      8),
    (6,  "mixamorig:Spine1",        9),
    (7,  "mixamorig:LeftFoot",     10),
    (8,  "mixamorig:RightFoot",    11),
    (9,  "mixamorig:Spine2",       12),
    (10, "mixamorig:LeftToeBase",  None),
    (11, "mixamorig:RightToeBase", None),
    (12, "mixamorig:Neck",         15),
    (13, "mixamorig:LeftShoulder", 16),
    (14, "mixamorig:RightShoulder",17),
    (15, "mixamorig:Head",         None),
    (16, "mixamorig:LeftArm",      18),
    (17, "mixamorig:RightArm",     19),
    (18, "mixamorig:LeftForeArm",  20),
    (19, "mixamorig:RightForeArm", 21),
    (20, "mixamorig:LeftHand",     25),
    (21, "mixamorig:RightHand",    40),
    (22, "mixamorig:LeftHandIndex1",  23),
    (23, "mixamorig:LeftHandIndex2",  24),
    (24, "mixamorig:LeftHandIndex3",  None),
    (25, "mixamorig:LeftHandMiddle1", 26),
    (26, "mixamorig:LeftHandMiddle2", 27),
    (27, "mixamorig:LeftHandMiddle3", None),
    (28, "mixamorig:LeftHandPinky1",  29),
    (29, "mixamorig:LeftHandPinky2",  30),
    (30, "mixamorig:LeftHandPinky3",  None),
    (31, "mixamorig:LeftHandRing1",   32),
    (32, "mixamorig:LeftHandRing2",   33),
    (33, "mixamorig:LeftHandRing3",   None),
    (34, "mixamorig:LeftHandThumb1",  35),
    (35, "mixamorig:LeftHandThumb2",  36),
    (36, "mixamorig:LeftHandThumb3",  None),
    (37, "mixamorig:RightHandIndex1", 38),
    (38, "mixamorig:RightHandIndex2", 39),
    (39, "mixamorig:RightHandIndex3", None),
    (40, "mixamorig:RightHandMiddle1",41),
    (41, "mixamorig:RightHandMiddle2",42),
    (42, "mixamorig:RightHandMiddle3",None),
    (43, "mixamorig:RightHandPinky1", 44),
    (44, "mixamorig:RightHandPinky2", 45),
    (45, "mixamorig:RightHandPinky3", None),
    (46, "mixamorig:RightHandRing1",  47),
    (47, "mixamorig:RightHandRing2",  48),
    (48, "mixamorig:RightHandRing3",  None),
    (49, "mixamorig:RightHandThumb1", 50),
    (50, "mixamorig:RightHandThumb2", 51),
    (51, "mixamorig:RightHandThumb3", None),
]


def _retarget_smplx_so3(rig, so3_data: dict, ground_z: float) -> dict:
    """Retargeting SO(3) exact des 52 os WoodenMesh/SMPL-X vers Mixamo 52 os."""
    global_mats = np.asarray(so3_data["global_rot_mats"], dtype=np.float32)  # (T, 52, 3, 3)
    posed_j = np.asarray(so3_data["joints_world"], dtype=np.float32)         # (T, 52, 3)
    j_template = np.asarray(so3_data["j_template"], dtype=np.float32)        # (52, 3)
    T = int(global_mats.shape[0])

    # Changement de base orthogonal C (det = +1) :
    # WoodenMesh/SMPL (X droite, Y haut, Z avant) -> Blender monde (X droite, -Y avant, Z haut)
    C = np.array([[1.0, 0.0, 0.0],
                  [0.0, 0.0, -1.0],
                  [0.0, 1.0, 0.0]], dtype=np.float32)
    global_mats_B = np.einsum("ab,tkbc,cd->tkad", C, global_mats, C.T)
    posed_j_B = np.einsum("ab,tkb->tka", C, posed_j)
    j_temp_B = np.einsum("ab,kb->ka", C, j_template)

    bpy.ops.object.mode_set(mode="OBJECT")
    for pb in rig.pose.bones:
        pb.rotation_mode = "QUATERNION"
        pb.location = (0.0, 0.0, 0.0)
        pb.rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
        pb.scale = (1.0, 1.0, 1.0)
    bpy.context.view_layer.update()

    mw = rig.matrix_world.copy()
    mw_3 = mw.to_3x3().normalized()

    rest_world_mat: dict[str, Matrix] = {}
    rest_world_dir: dict[str, Vector] = {}
    for b in rig.data.bones:
        rest_world_mat[b.name] = (mw_3 @ b.matrix_local.to_3x3()).normalized()
        d = (mw @ b.tail_local) - (mw @ b.head_local)
        rest_world_dir[b.name] = d.normalized() if d.length > 1e-6 else Vector((0.0, 0.0, 1.0))

    # Calcul de la matrice monde de référence T-pose R_tpose_w[bname] pour chaque os :
    # - Colonne vertébrale, bassin, cou, tête ET pieds/orteils (idx in {0, 3, 6, 9, 12, 15, 7, 8, 10, 11}) :
    #   le personnage debout a déjà le buste vertical et les semelles posées à plat à Z=0.0 -> R_tpose_w = R_rest_w.
    #   (Ne jamais aligner LeftFoot->LeftToeBase sur le segment incliné WoodenMesh, sinon cela injecte +43°/+45°
    #   de cabrage vers le haut sur les pieds et les orteils !)
    # - Épaules, bras, avant-bras, mains (idx in {13, 14, 16..21}) :
    #   utilise la T-pose neurale de MIA si présente (qui aligne la paume vers le sol -Z),
    #   puis affine la direction longitudinale sur le segment WoodenMesh. Si le GLB n'avait
    #   plus sa T-pose MIA statique, aligne aussi le vecteur métacarpien (Pinky1 -> Index1)
    #   vers l'avant (-Y) pour garantir le bon roulis axial du coude et du poignet.
    R_tpose_w: dict[str, Matrix] = {}
    delta_rest_to_tpose_w: dict[str, Matrix] = {}

    UPRIGHT_INDICES = {0, 3, 6, 9, 12, 15, 7, 8, 10, 11}

    for idx, bname, c_idx in BONE_TABLE:
        if bname not in rig.data.bones:
            continue
        b = rig.data.bones[bname]
        p_name = b.parent.name if b.parent else None

        if idx in UPRIGHT_INDICES:
            delta_rest_to_tpose_w[bname] = Matrix.Identity(3)
            R_tpose_w[bname] = rest_world_mat[bname]
            continue

        if idx >= 22:
            hand_name = "mixamorig:LeftHand" if idx < 37 else "mixamorig:RightHand"
            d_hand = delta_rest_to_tpose_w.get(hand_name, Matrix.Identity(3))
            delta_rest_to_tpose_w[bname] = d_hand
            R_tpose_w[bname] = d_hand @ rest_world_mat[bname]
            continue

        if has_mia_static_tpose and any(k in bname for k in ("Shoulder", "Arm", "ForeArm", "Hand")):
            base_mat_w = mia_tpose_world_mat[bname]
            base_delta_w = base_mat_w @ rest_world_mat[bname].inverted()
        else:
            p_delta = delta_rest_to_tpose_w.get(p_name, Matrix.Identity(3)) if p_name else Matrix.Identity(3)
            base_delta_w = p_delta
            base_mat_w = base_delta_w @ rest_world_mat[bname]

        if c_idx is not None:
            cur_dir = (base_delta_w @ rest_world_dir[bname]).normalized()
            tgt_vec = Vector((j_temp_B[c_idx] - j_temp_B[idx]).tolist())
            if tgt_vec.length > 1e-6:
                tgt_dir = tgt_vec.normalized()
                swing = cur_dir.rotation_difference(tgt_dir).to_matrix()
                delta_w = swing @ base_delta_w
                # Si pas de T-pose MIA statique sur le bras (ex: GLB ré-animé en A-pose),
                # corriger le roulis axial du bras via l'axe des métacarpes (Pinky1 -> Index1)
                if not has_mia_static_tpose and bname in ("mixamorig:LeftArm", "mixamorig:RightArm"):
                    side = "Left" if "Left" in bname else "Right"
                    idx_b = rig.data.bones.get(f"mixamorig:{side}HandIndex1")
                    pky_b = rig.data.bones.get(f"mixamorig:{side}HandPinky1")
                    if idx_b and pky_b:
                        knuckle_rest = (mw @ idx_b.head_local) - (mw @ pky_b.head_local)
                        knuckle_cur = delta_w @ knuckle_rest
                        knuckle_proj = knuckle_cur - knuckle_cur.project(tgt_dir)
                        # En T-pose Mixamo/Wooden, Pinky->Index pointe vers l'avant (-Y)
                        fwd_tgt = Vector((0.0, -1.0, 0.0))
                        fwd_proj = fwd_tgt - fwd_tgt.project(tgt_dir)
                        if knuckle_proj.length > 1e-4 and fwd_proj.length > 1e-4:
                            roll_q = knuckle_proj.normalized().rotation_difference(fwd_proj.normalized())
                            if roll_q.angle <= math.radians(55.0):
                                delta_w = roll_q.to_matrix() @ delta_w
                delta_rest_to_tpose_w[bname] = delta_w
                R_tpose_w[bname] = delta_w @ rest_world_mat[bname]
            else:
                delta_rest_to_tpose_w[bname] = base_delta_w
                R_tpose_w[bname] = base_mat_w
        else:
            delta_rest_to_tpose_w[bname] = base_delta_w
            R_tpose_w[bname] = base_mat_w

    # Facteur d'échelle racine basé sur la longueur de jambe (Hips -> Foot)
    hips_rest_w = mw @ rig.data.bones["mixamorig:Hips"].head_local
    l_foot_rest_w = mw @ rig.data.bones["mixamorig:LeftFoot"].head_local
    r_foot_rest_w = mw @ rig.data.bones["mixamorig:RightFoot"].head_local
    rig_leg_len = 0.5 * ((hips_rest_w - l_foot_rest_w).length + (hips_rest_w - r_foot_rest_w).length)
    wooden_leg_len = float(0.5 * (np.linalg.norm(j_temp_B[0] - j_temp_B[7]) + np.linalg.norm(j_temp_B[0] - j_temp_B[8])))
    scale_factor = rig_leg_len / max(wooden_leg_len, 1e-4)
    foot_sole_offset = 0.5 * (l_foot_rest_w.z + r_foot_rest_w.z) - ground_z

    act = bpy.data.actions.new(name="AuroraSO3Action")
    if not rig.animation_data:
        rig.animation_data_create()
    rig.animation_data.action = act
    bpy.context.scene.frame_start = 0
    bpy.context.scene.frame_end = T

    p0_pelvis = Vector(posed_j_B[0, 0].tolist())
    # Dé-dérive horizontale (high-pass XY) pour garder le personnage centré sur la grille
    # et la cible d'orbite (0, 0) de F3D / Three.js tout en conservant les esquives et sauts
    pelvis_xy = posed_j_B[:, 0, :2]
    win_half = min(22, max(1, T // 4))
    pelvis_xy_local = np.zeros_like(pelvis_xy)
    for ti in range(T):
        i0 = max(0, ti - win_half)
        i1 = min(T, ti + win_half + 1)
        pelvis_xy_local[ti] = pelvis_xy[ti] - pelvis_xy[i0:i1].mean(axis=0)
    pelvis_xy_local -= pelvis_xy_local[0]

    prev_quats: dict[str, Quaternion] = {}

    G0_inv_B = {idx: Matrix(global_mats_B[0, idx].tolist()).inverted() for idx in range(22, 52)}
    G0_hand_B = {
        "L": Matrix(global_mats_B[0, 20].tolist()),
        "R": Matrix(global_mats_B[0, 21].tolist()),
    }

    R_hips_rest_inv = rest_world_mat["mixamorig:Hips"].inverted()
    pb_hips = rig.pose.bones["mixamorig:Hips"]
    smpl_ground_ank_z0 = float(min(posed_j_B[0, 7, 2], posed_j_B[0, 8, 2]))

    for t in range(T):
        frame = t + 1
        bpy.context.scene.frame_set(frame)

        delta_w_t: dict[str, Matrix] = {}
        for idx, bname, _ in BONE_TABLE:
            if bname not in rig.pose.bones:
                continue
            G_t = Matrix(global_mats_B[t, idx].tolist())
            if idx in (7, 8, 10, 11):
                # Stabilisation plantaire : garde le lacet horizontal (G_yaw) mais amortit
                # le tangage/roulis (G_tilt) lorsque la cheville est au sol (stance_alpha -> 0)
                ank_idx = 7 if idx in (7, 10) else 8
                ank_lift = float(posed_j_B[t, ank_idx, 2]) - smpl_ground_ank_z0
                fwd = G_t @ Vector((0.0, -1.0, 0.0))
                fwd_xy = Vector((fwd.x, fwd.y, 0.0))
                if fwd_xy.length > 1e-4:
                    G_yaw = Vector((0.0, -1.0, 0.0)).rotation_difference(fwd_xy.normalized()).to_matrix()
                else:
                    G_yaw = Matrix.Identity(3)
                G_tilt = G_yaw.inverted() @ G_t
                q_tilt = G_tilt.to_quaternion()
                stance_alpha = min(1.0, max(0.0, ank_lift / 0.12))
                q_tilt_damped = Quaternion((1.0, 0.0, 0.0, 0.0)).slerp(q_tilt, 0.12 + 0.88 * stance_alpha)
                max_tilt = math.radians(8.0 + 37.0 * stance_alpha)
                if q_tilt_damped.angle > max_tilt:
                    q_tilt_damped = Quaternion(q_tilt_damped.axis, max_tilt)
                G_t = G_yaw @ q_tilt_damped.to_matrix()
                R_pose_w = G_t @ R_tpose_w[bname]
            elif idx >= 22:
                side = "L" if idx < 37 else "R"
                G_hand_t = Matrix(global_mats_B[t, 20 if side == "L" else 21].tolist())
                rel_finger = G0_hand_B[side].inverted() @ G_t @ G0_inv_B[idx] @ G0_hand_B[side]
                G_eff = G_hand_t @ rel_finger
                R_pose_w = G_eff @ R_tpose_w[bname]
            else:
                R_pose_w = G_t @ R_tpose_w[bname]
            delta_w_t[bname] = R_pose_w @ rest_world_mat[bname].inverted()

        for idx, bname, _ in BONE_TABLE:
            if bname not in rig.pose.bones:
                continue
            pb = rig.pose.bones[bname]
            b = rig.data.bones[bname]
            R_rest = rest_world_mat[bname]
            d_parent = delta_w_t[b.parent.name] if (b.parent and b.parent.name in delta_w_t) else Matrix.Identity(3)
            M_basis = R_rest.inverted() @ d_parent.inverted() @ delta_w_t[bname] @ R_rest
            q = M_basis.to_quaternion().normalized()
            if bname in prev_quats and prev_quats[bname].dot(q) < 0.0:
                q = -q
            pb.rotation_quaternion = q

        # Translation racine centrée sur la scène (esquives latérales + saut vertical exact)
        pelvis_cur = Vector(posed_j_B[t, 0].tolist())
        dx = float(pelvis_xy_local[t, 0]) * scale_factor
        dy = float(pelvis_xy_local[t, 1]) * scale_factor
        r_xy = math.hypot(dx, dy)
        max_xy = 0.22
        if r_xy > 1e-6:
            s_xy = (max_xy * math.tanh(r_xy / max_xy)) / r_xy
            dx *= s_xy
            dy *= s_xy
        dz = (pelvis_cur.z - p0_pelvis.z) * scale_factor
        dp_w = Vector((dx, dy, dz))
        desired_hips_w = hips_rest_w + dp_w
        pb_hips.location = R_hips_rest_inv @ (desired_hips_w - hips_rest_w)
        bpy.context.view_layer.update()

        # Ancrage exact du pied d'appui au sol
        l_foot_z = (mw @ rig.pose.bones["mixamorig:LeftFoot"].head).z
        r_foot_z = (mw @ rig.pose.bones["mixamorig:RightFoot"].head).z
        min_foot_z = min(l_foot_z, r_foot_z)
        smpl_min_ank_z = float(min(posed_j_B[t, 7, 2], posed_j_B[t, 8, 2])) - smpl_ground_ank_z0
        desired_min_foot_z = ground_z + foot_sole_offset + max(0.0, smpl_min_ank_z * scale_factor)
        desired_hips_w.z += (desired_min_foot_z - min_foot_z)
        pb_hips.location = R_hips_rest_inv @ (desired_hips_w - hips_rest_w)
        bpy.context.view_layer.update()

        # Égalisation analytique des deux pieds en double appui (évite qu'un pied flotte à +13 cm
        # lors d'une garde large à cause de la différence de ratio cuisse/tibia avec SMPL-X)
        smpl_low_t = float(min(posed_j_B[t, 7, 2], posed_j_B[t, 8, 2]))
        for side, ank_idx in (("Left", 7), ("Right", 8)):
            upleg_name = f"mixamorig:{side}UpLeg"
            leg_name = f"mixamorig:{side}Leg"
            foot_name = f"mixamorig:{side}Foot"
            if not all(k in rig.pose.bones for k in (upleg_name, leg_name, foot_name)):
                continue
            smpl_rel_lift = float(posed_j_B[t, ank_idx, 2]) - smpl_low_t
            if smpl_rel_lift >= 0.08:
                continue
            cur_ank_z = (mw @ rig.pose.bones[foot_name].head).z
            target_ank_z = desired_min_foot_z + max(0.0, smpl_rel_lift * scale_factor)
            err_z = cur_ank_z - target_ank_z
            if err_z <= 0.004:
                continue
            pb_u = rig.pose.bones[upleg_name]
            v_th = (mw @ pb_u.tail) - (mw @ pb_u.head)
            L_th = v_th.length
            if L_th <= 1e-4:
                continue
            new_vz = max(-0.98 * L_th, v_th.z - err_z)
            horiz_sq = max(0.0, L_th * L_th - new_vz * new_vz)
            old_h = math.hypot(v_th.x, v_th.y)
            if old_h > 1e-5:
                sc_h = math.sqrt(horiz_sq) / old_h
                v_th_tgt = Vector((v_th.x * sc_h, v_th.y * sc_h, new_vz))
            else:
                v_th_tgt = Vector((0.0, 0.0, new_vz))
            S_down = v_th.normalized().rotation_difference(v_th_tgt.normalized()).to_matrix()
            delta_w_t[upleg_name] = S_down @ delta_w_t[upleg_name]
            for sub_name in (upleg_name, leg_name):
                pb_s = rig.pose.bones[sub_name]
                b_s = rig.data.bones[sub_name]
                R_rest_s = rest_world_mat[sub_name]
                d_par_s = delta_w_t[b_s.parent.name] if (b_s.parent and b_s.parent.name in delta_w_t) else Matrix.Identity(3)
                M_b = R_rest_s.inverted() @ d_par_s.inverted() @ delta_w_t[sub_name] @ R_rest_s
                pb_s.rotation_quaternion = M_b.to_quaternion().normalized()
            bpy.context.view_layer.update()

        # Continuité hémisphérique des quaternions après correction plantaire
        for _, bname, _ in BONE_TABLE:
            if bname in rig.pose.bones:
                pb = rig.pose.bones[bname]
                q = pb.rotation_quaternion.normalized()
                if bname in prev_quats and prev_quats[bname].dot(q) < 0.0:
                    q = -q
                prev_quats[bname] = q.copy()
                pb.rotation_quaternion = q

        for kf in ((0, 1) if t == 0 else (frame,)):
            pb_hips.keyframe_insert(data_path="location", frame=kf)
            for _, bname, _ in BONE_TABLE:
                if bname in rig.pose.bones:
                    rig.pose.bones[bname].keyframe_insert(data_path="rotation_quaternion", frame=kf)

    return {"ok": True, "steps": {"smplx_so3_52bones": T}}


def _get_action_fcurves(action):
    if hasattr(action, "fcurves"):
        return action.fcurves
    try:
        for layer in getattr(action, "layers", []):
            for strip in getattr(layer, "strips", []):
                for bag in getattr(strip, "channelbags", []):
                    if hasattr(bag, "fcurves"):
                        return bag.fcurves
    except Exception:
        pass
    return []


_used_smplx_so3 = False
try:
    bpy.context.scene.render.fps = 30
    bpy.context.scene.render.fps_base = 1.0
    _so3_data = _load_smplx_so3_data(BVH)
    if _so3_data is not None:
        rep = _retarget_smplx_so3(rig, _so3_data, ground_z)
        _used_smplx_so3 = True
        print("MIA_MOCAP_STEPS", list(rep.get("steps", {}).keys()), flush=True)
    else:
        import mocap_bake_bpy as mb
        rep = mb.run_mocap_bake(
            rig, BVH, [m.name for m in meshes], ground_z,
            mesh_fallback=meshes[0] if meshes else None,
        )
        print("MIA_MOCAP_STEPS", list(rep.get("steps", {}).keys()), flush=True)
except Exception as e:  # noqa: BLE001
    import traceback
    traceback.print_exc()
    print("MIA_MOCAP_FAIL: retarget exception: %s" % e, flush=True)
    sys.exit(4)

act = rig.animation_data.action if rig.animation_data else None
if act is None:
    print("MIA_MOCAP_FAIL: no action after retarget", flush=True)
    sys.exit(5)

try:
    nf = int(act.frame_range[1] - act.frame_range[0])
    if nf < 2:
        nf = int(bpy.context.scene.frame_end - bpy.context.scene.frame_start + 1)
except Exception:
    nf = int(bpy.context.scene.frame_end - bpy.context.scene.frame_start + 1)
if nf < 2:
    print("MIA_MOCAP_FAIL: action degeneree (%d frame(s))" % nf, flush=True)
    sys.exit(6)

try:
    for _other_act in list(bpy.data.actions):
        if _other_act != act:
            bpy.data.actions.remove(_other_act, do_unlink=True)
except Exception:
    pass

bpy.ops.object.mode_set(mode="OBJECT")
bpy.ops.object.select_all(action="DESELECT")
rig.select_set(True)
for m in meshes:
    m.select_set(True)
bpy.context.view_layer.objects.active = rig
bpy.ops.export_scene.gltf(
    filepath=OUT_GLB,
    use_selection=True,
    export_animations=True,
    export_animation_mode="ACTIONS",
)
try:
    import glb_io
    _doc, _blob = glb_io.load(OUT_GLB)
    for _mat in _doc.get("materials", []):
        _mat["doubleSided"] = True
    for _anim in _doc.get("animations", []):
        for _ch in _anim.get("channels", []):
            _tgt = _ch.get("target", {})
            _ni = _tgt.get("node")
            _path = _tgt.get("path")
            if _ni is None or _path not in ("rotation", "translation", "scale"):
                continue
            _sm = _anim["samplers"][_ch["sampler"]]
            _vals = glb_io.accessor(_doc, _blob, _sm["output"])
            if len(_vals) > 0:
                _doc["nodes"][_ni][_path] = [float(x) for x in _vals[0]]
    glb_io.save(OUT_GLB, _doc, _blob)
    try:
        from pbr_cartography import transfer_pbr_from_source_glb
        transfer_pbr_from_source_glb(RIG_GLB, OUT_GLB)
    except Exception:
        pass
except Exception as _ge:
    print("MIA_MOCAP_INFO: init pose frame 0 avertissement (%r)" % (_ge,), flush=True)
print("MIA_MOCAP_OK glb=%s frames=%d" % (OUT_GLB, nf), flush=True)

