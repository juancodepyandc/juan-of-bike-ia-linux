"""mia_mocap_retarget.py — Blender headless: retarget a MoMask BVH onto a
MIA-rigged (Mixamo) GLB and export the animated GLB.

This is the GENUINE motion path (vs a hand-authored procedural walk): the motion
comes from MoMask text-to-motion (any described motion), is retargeted onto the
Mixamo skeleton via retarget_bvh (MakeWalk), and the Mixamo spine over-rotation
is bake-clamped (see mocap_bake_bpy._clamp_mixamo_spine) so the waist doesn't
shatter. Works for walk/run/dance/wave/etc. — whatever MoMask produced.

Usage: blender -b -P mia_mocap_retarget.py -- IN_RIGGED.glb BVH.bvh OUT.glb
Emits: MIA_MOCAP_OK glb=<OUT> frames=<N>  or  MIA_MOCAP_FAIL: <reason>
"""
from __future__ import annotations

import os
import sys

import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
if len(argv) < 3:
    print("MIA_MOCAP_FAIL: usage IN.glb BVH OUT.glb", flush=True)
    sys.exit(2)
IN_GLB, BVH, OUT_GLB = argv[0], argv[1], argv[2]

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=IN_GLB)
meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
arms = [o for o in bpy.context.scene.objects if o.type == "ARMATURE"]
if not arms:
    print("MIA_MOCAP_FAIL: no armature", flush=True)
    sys.exit(3)
rig = next((a for a in arms if any("mixamo" in b.name.lower() for b in a.data.bones)), arms[0])

# ground z = mesh minimum (world)
ground_z = 0.0
try:
    zs = []
    for m in meshes:
        for c in m.bound_box:
            zs.append((m.matrix_world @ __import__("mathutils").Vector(c)).z)
    ground_z = min(zs) if zs else 0.0
except Exception:
    ground_z = 0.0


def _purger_meshes_morts() -> int:
    """Supprime les objets mesh SANS AUCUN poids (widgets residuels type
    Icosphere): ils ne suivent pas l'armature et polluent la livraison."""
    morts = [o for o in bpy.context.scene.objects
             if o.type == "MESH" and o.data.vertices
             and not any(v.groups for v in o.data.vertices)]
    for o in morts:
        bpy.data.objects.remove(o, do_unlink=True)
    return len(morts)


def _souder(obj, dist: float = 0.0008) -> tuple[int, int]:
    """Fusionne les sommets dedoubles (coutures UV, aller-retour FBX de MIA:
    verifie 41 097 ilots sur le yeti, plus gros = 0,7%). bpy fusionne aussi
    les poids; les UV vivent sur les coins de face -> texture intacte
    (approche deja prouvee par la soudure amont 0,8 mm)."""
    avant = len(obj.data.vertices)
    bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.remove_doubles(threshold=dist)
    bpy.ops.object.mode_set(mode="OBJECT")
    return avant, len(obj.data.vertices)


def _couper_ponts(obj, seuil_d: float = 0.3) -> int:
    """Coupe les PONTS de geometrie entre parties du corps en CONTACT au repos
    (mains contre cuisses du yeti: 3546 aretes Hand<->UpLeg mesurees). La
    surface TRELLIS est fusionnee a travers le contact; les poids changent
    brutalement d'un bout a l'autre de l'arete -> dechirure x313 des que le
    bras bouge. Critere 100% general: discontinuite du profil de poids a
    travers l'arete. Les transitions articulaires legitimes s'etalent sur
    ~50 aretes (d~0.04/arete sur un maillage dense); un pont de contact, meme
    ADOUCI par le melange de poids MIA, concentre d>=0.3 sur 1-2 aretes —
    marge 10x, aucun risque pour les coudes/epaules."""
    me = obj.data

    def profil(v):
        return {g.group: g.weight for g in v.groups}

    def dist(pa, pb):
        ks = set(pa) | set(pb)
        return sum(abs(pa.get(k, 0.0) - pb.get(k, 0.0)) for k in ks)

    mauvais = []
    for e in me.edges:
        ia, ib = e.vertices[0], e.vertices[1]
        if dist(profil(me.vertices[ia]), profil(me.vertices[ib])) > seuil_d:
            mauvais.append(e.index)
    if not mauvais:
        return 0
    bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_mode(type="EDGE")
    bpy.ops.mesh.select_all(action="DESELECT")
    bpy.ops.object.mode_set(mode="OBJECT")
    for i in mauvais:
        me.edges[i].select = True
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.delete(type="EDGE")
    bpy.ops.object.mode_set(mode="OBJECT")
    return len(mauvais)


def _reboucher(obj, cotes_max: int = 64) -> None:
    """Referme les petites boucles de bord laissees par les coupes de ponts.
    Sans cela, les coupes livrent un modele TROUE (constate par l'utilisateur
    sur les deux generations du 24/07). Les faces de rebouchage heritent des
    poids/UV voisins par interpolation — sous la dilatation d'atlas, la
    couleur locale suit."""
    bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.fill_holes(sides=cotes_max)
    bpy.ops.object.mode_set(mode="OBJECT")


def _solidariser_ilots(obj, seuil_ratio: float = 0.01) -> int:
    """Les PETITS ilots deconnectes (meches de fourrure, accessoires) recoivent
    les poids du sommet LE PLUS PROCHE du gros corps. Sans cela, une meche
    skinnee a sa facon s'etire en TIGE rigide qui traverse le corps pendant le
    mouvement (constate: yeti 24/07). General: aucun nom d'os, aucune classe de
    sujet — pure topologie + proximite."""
    import numpy as np
    from mathutils import kdtree

    me = obj.data
    n = len(me.verts) if hasattr(me, "verts") else len(me.vertices)
    if n == 0:
        return 0
    # composantes connexes via union-find sur les aretes
    parent = list(range(n))

    def find(a):
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
    if len(gros) < n * 0.3:
        return 0   # pas de corps dominant: on ne touche a rien
    kt = kdtree.KDTree(len(gros))
    for i, vi in enumerate(gros):
        kt.insert(me.vertices[vi].co, vi)
    kt.balance()
    # TOUT ilot non dominant est solidarise (pas seulement les poussieres):
    # une meche de 3-4k sommets gardait ses poids a elle et, soudee au corps
    # par des aretes sub-millimetriques, s'ecartait de 30 cm en accroupi
    # (mesure x313). Une piece separee legitime > 25% du total est preservee.
    seuil = int(n * 0.25)
    corriges = 0
    for racine, verts in comp.items():
        if verts is gros or len(verts) > seuil:
            continue
        for vi in verts:
            _co, proche, _d = kt.find(me.vertices[vi].co)
            if proche is None:
                continue
            src = me.vertices[proche]
            dst = me.vertices[vi]
            # recopie des poids du voisin du corps
            for g in list(dst.groups):
                obj.vertex_groups[g.group].remove([vi])
            for g in src.groups:
                obj.vertex_groups[g.group].add([vi], g.weight, "REPLACE")
            corriges += 1
    return corriges


try:
    _np = _purger_meshes_morts()
    if _np:
        print("MIA_MOCAP_INFO: %d mesh(es) sans poids purge(s)" % _np, flush=True)
        meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    for _m in meshes:
        _av, _ap = _souder(_m)
        if _ap < _av:
            print("MIA_MOCAP_INFO: soudure %s: %d -> %d sommets"
                  % (_m.name, _av, _ap), flush=True)
    for _m in meshes:
        _nc = _couper_ponts(_m)
        if _nc:
            print("MIA_MOCAP_INFO: %d pont(s) de contact coupe(s) (aretes a "
                  "poids incompatibles)" % _nc, flush=True)
            _reboucher(_m)
            print("MIA_MOCAP_INFO: trous des coupes rebouches", flush=True)
    _tot = 0
    for _m in meshes:
        _tot += _solidariser_ilots(_m)
    if _tot:
        print("MIA_MOCAP_INFO: %d sommets d'ilots fins solidarises au corps"
              % _tot, flush=True)
except Exception as _se:  # noqa: BLE001
    print("MIA_MOCAP_INFO: soudure/solidarisation indisponible (%r)" % (_se,),
          flush=True)

try:
    import mocap_bake_bpy as mb
    rep = mb.run_mocap_bake(rig, BVH, [m.name for m in meshes], ground_z,
                            mesh_fallback=meshes[0] if meshes else None)
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

# STABILITE DE LA RACINE: un bipede qui danse garde le bassin quasi
# vertical. Les excursions de tangage/roulis du BVH (bruit video, IK)
# faisaient BASCULER le sujet sur quelques frames (constate: Pikachu tete en
# bas par instants). On borne tangage et roulis a +/-25 deg — le LACET reste
# libre (les tours de la danse sont a lui).
try:
    import math as _math
    import mathutils as _mu
    _racines2 = [b for b in rig.pose.bones if b.parent is None]
    _cibles = {b.name for b in _racines2}
    _cibles |= {b.name for b in rig.pose.bones
                if b.parent in _racines2 and "hip" in b.name.lower()}
    _lim = _math.radians(25.0)
    _nb_st = 0
    for _nom_b in _cibles:
        _dp = 'pose.bones["%s"].rotation_quaternion' % _nom_b
        _fcs = {fc.array_index: fc for fc in act.fcurves if fc.data_path == _dp}
        if len(_fcs) < 4:
            continue
        _xs = sorted({kp.co.x for fc in _fcs.values()
                      for kp in fc.keyframe_points})
        for _f in _xs:
            _q = _mu.Quaternion((_fcs[0].evaluate(_f), _fcs[1].evaluate(_f),
                                 _fcs[2].evaluate(_f), _fcs[3].evaluate(_f)))
            _e = _q.to_euler("YXZ")
            _ch = False
            for _ax in (0, 2):   # X = tangage, Z = roulis (Y = lacet libre)
                if abs(_e[_ax]) > _lim:
                    _e[_ax] = _lim if _e[_ax] > 0 else -_lim
                    _ch = True
            if _ch:
                _q2 = _e.to_quaternion()
                for _i, _v in enumerate((_q2.w, _q2.x, _q2.y, _q2.z)):
                    for kp in _fcs[_i].keyframe_points:
                        if abs(kp.co.x - _f) < 0.5:
                            kp.co.y = _v
                _nb_st += 1
    for _fc in act.fcurves:
        _fc.update()
    if _nb_st:
        print("MIA_MOCAP_INFO: racine stabilisee (%d cles bornees a 25 deg "
              "tangage/roulis)" % _nb_st, flush=True)
except Exception as _ste:  # noqa: BLE001
    print("MIA_MOCAP_INFO: stabilisation racine indisponible (%r)" % (_ste,),
          flush=True)

# HYGIENE DE RETARGET: ne garder que les ROTATIONS sur les os non-racine.
# Les cles de POSITION (verrou de pied per-frame, retarget brut) supposent les
# proportions du squelette BVH; sur le sujet reel elles ECARTELENT les membres
# (mesure: genou x313, main x141 — poids sains, os fous). La racine garde
# position+echelle: c'est elle qui porte saut et deplacement.
try:
    _racines = {b.name for b in rig.pose.bones if b.parent is None}
    _loc = _ech = 0
    for _fc in list(act.fcurves):
        _dp = _fc.data_path
        if not _dp.startswith('pose.bones["'):
            continue
        _nom = _dp.split('"')[1]
        if _nom in _racines:
            continue
        if _dp.endswith(".location"):
            act.fcurves.remove(_fc)
            _loc += 1
        elif _dp.endswith(".scale"):
            act.fcurves.remove(_fc)
            _ech += 1
    if _loc or _ech:
        print("MIA_MOCAP_INFO: canaux nettoyes (%d position, %d echelle "
              "sur os non-racine)" % (_loc, _ech), flush=True)
except Exception as _ce:  # noqa: BLE001
    print("MIA_MOCAP_INFO: nettoyage des canaux indisponible (%r)" % (_ce,),
          flush=True)
try:
    nf = int(act.frame_range[1] - act.frame_range[0])
except Exception:
    nf = 0
if nf < 2:
    # une action d'1 frame = pose de repos, pas un mouvement: exporter ce GLB
    # ferait livrer une statue estampillee "OK" (piege deja paye en prod).
    print("MIA_MOCAP_FAIL: action degeneree (%d frame(s))" % nf, flush=True)
    sys.exit(6)

# PORTE D'INTEGRITE AUTO-REPARANTE. Le mouvement ne doit pas DECHIRER le
# maillage. On mesure TOUTES les aretes (numpy, frames evaluees): celles qui
# s'etirent au-dela du seuil sont des PONTS (contact fusionne, meche) — une
# arete etiree x6+ est deja visuellement dechiree, la couper LIBERE la
# traction sans rien abimer de plus. 3 passes maxi, echec explicite sinon.
def _mesurer_aretes(obj, frames):
    import numpy as _n
    me = obj.data
    m, n = len(me.edges), len(me.vertices)
    ed = _n.empty(2 * m, dtype=_n.int64)
    me.edges.foreach_get("vertices", ed)
    ed = ed.reshape(-1, 2)
    rest = _n.empty(3 * n)
    me.vertices.foreach_get("co", rest)
    rest = rest.reshape(-1, 3)
    rl = _n.linalg.norm(rest[ed[:, 0]] - rest[ed[:, 1]], axis=1)
    rl[rl < 1e-9] = 1e-9
    diag = float(_n.linalg.norm(rest.max(0) - rest.min(0))) or 1e-6
    pire = _n.zeros(m)
    sc = bpy.context.scene
    for f in frames:
        sc.frame_set(int(f))
        bpy.context.view_layer.update()
        dg = bpy.context.evaluated_depsgraph_get()
        ev = obj.evaluated_get(dg)
        tm = ev.to_mesh()
        if len(tm.vertices) == n:
            cur = _n.empty(3 * n)
            tm.vertices.foreach_get("co", cur)
            cur = cur.reshape(-1, 3)
            ln = _n.linalg.norm(cur[ed[:, 0]] - cur[ed[:, 1]], axis=1)
            # vraie dechirure: relative ET absolue (>2% de la diagonale)
            ratio = _n.where(ln > 0.02 * diag, ln / rl, 0.0)
            pire = _n.maximum(pire, ratio)
        ev.to_mesh_clear()
    return ed, pire


def _couper_aretes(obj, indices) -> None:
    me = obj.data
    bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_mode(type="EDGE")
    bpy.ops.mesh.select_all(action="DESELECT")
    bpy.ops.object.mode_set(mode="OBJECT")
    for i in indices:
        me.edges[int(i)].select = True
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.delete(type="EDGE")
    bpy.ops.object.mode_set(mode="OBJECT")


try:
    _seuil_etire = float(os.environ.get("AURORA_MOCAP_STRETCH_MAX", "6.0"))
    _gros = max(meshes, key=lambda m: len(m.data.vertices))
    _sc = bpy.context.scene
    _f0, _f1 = _sc.frame_start, _sc.frame_end
    _frames = sorted({_f0, (_f0 + _f1) // 2, max(_f0 + 1, int(_f0 + 0.25 * (_f1 - _f0))),
                      max(_f0 + 1, int(_f0 + 0.75 * (_f1 - _f0))), _f1})
    _pire_final = 0.0
    for _passe in range(3):
        _ed, _pire = _mesurer_aretes(_gros, _frames)
        _pire_final = float(_pire.max()) if len(_pire) else 0.0
        print("MIA_MOCAP_INFO: etirement max des aretes x%.1f (seuil x%.1f, "
              "passe %d)" % (_pire_final, _seuil_etire, _passe + 1), flush=True)
        if _pire_final <= _seuil_etire:
            break
        _coupables = [int(k) for k in _pire.argsort()[::-1] if _pire[k] > _seuil_etire]
        print("MIA_MOCAP_INFO: %d arete(s) dechirees coupees (ponts reveles "
              "par le mouvement)" % len(_coupables), flush=True)
        _couper_aretes(_gros, _coupables)
        _reboucher(_gros)
    if _pire_final > _seuil_etire:
        print("MIA_MOCAP_FAIL: dechirure du maillage (etirement x%.1f > x%.1f "
              "apres 3 passes de coupe)" % (_pire_final, _seuil_etire), flush=True)
        sys.exit(7)
except SystemExit:
    raise
except Exception as _ie:  # noqa: BLE001
    print("MIA_MOCAP_INFO: porte d'integrite indisponible (%r)" % (_ie,),
          flush=True)

bpy.ops.object.mode_set(mode="OBJECT")
bpy.ops.object.select_all(action="DESELECT")
rig.select_set(True)
for m in meshes:
    m.select_set(True)
bpy.context.view_layer.objects.active = rig
bpy.ops.export_scene.gltf(filepath=OUT_GLB, use_selection=True,
                          export_animations=True, export_animation_mode="ACTIONS")
print("MIA_MOCAP_OK glb=%s frames=%d" % (OUT_GLB, nf), flush=True)
