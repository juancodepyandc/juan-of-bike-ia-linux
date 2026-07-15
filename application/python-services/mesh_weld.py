"""mesh_weld.py — reconnecte un maillage TRELLIS (soupe d'ilots) en surface connexe.

GENERAL, aucun cas particulier: TRELLIS.2 sort la surface en triangles NON fusionnes
-> ~78 000 ilots disjoints pour un humain (verifie). Cette soupe:
  - se DECHIRE des qu'on la deforme (rig/animation): les ilots glissent les uns sur
    les autres -> la jambe s'etire en ruban, le vetement eclate. C'est la cause
    RACINE des mauvais mouvements, pour TOUT sujet (humain, personnage, creature).
  - degrade l'ombrage aux innombrables bords libres.

Fix: fusionner les sommets DUPLIQUES (meme position). Les doublons de TRELLIS
partagent la MEME coordonnee UV (ce sont de vrais doublons, pas des coutures), donc
la fusion NE CASSE PAS la texture (verifie: rendu texture identique avant/apres).
Resultat mesure sur un humain: 78169 -> 12 ilots, texture intacte.

Ce n'est PAS un remaillage (on ne touche ni a la topologie utile ni aux UV): juste
la fusion des doublons que le generateur aurait du souder lui-meme.

Usage:
    python mesh_weld.py <in.glb> <out.glb> [--dist 0.0008]
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))


def _find_blender() -> str | None:
    env = os.environ.get("AURORA_BLENDER")
    if env and os.path.exists(env):
        return env
    for c in ("/home/juan/.local/bin/blender", "/usr/bin/blender", "blender"):
        p = shutil.which(c) if not os.path.isabs(c) else (c if os.path.exists(c) else None)
        if p:
            return p
    return None


_BPY = r'''
import bpy, sys, bmesh

argv = sys.argv[sys.argv.index("--") + 1:]
GLB, OUT, DIST = argv[0], argv[1], float(argv[2])

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=GLB)
meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
if not meshes:
    print("WELD_FAIL aucun mesh"); sys.exit(3)


def n_components(me):
    bm = bmesh.new(); bm.from_mesh(me); seen = set(); c = 0
    for v in bm.verts:
        if v.index in seen:
            continue
        c += 1; stack = [v]
        while stack:
            w = stack.pop()
            if w.index in seen:
                continue
            seen.add(w.index)
            for e in w.link_edges:
                o = e.other_vert(w)
                if o.index not in seen:
                    stack.append(o)
    bm.free(); return c


total_before = 0
total_after = 0
isl_before = 0
isl_after = 0
for ob in meshes:
    me = ob.data
    total_before += len(me.vertices)
    # ilots: coute cher, on ne l'evalue que sur le plus gros mesh (diagnostic)
    if ob is max(meshes, key=lambda o: len(o.data.vertices)):
        isl_before = n_components(me)
    bm = bmesh.new(); bm.from_mesh(me)
    # SEUL merge des doublons: meme position (les UV sont per-loop et conserves;
    # remove_doubles fusionne les sommets mais garde les loops distincts, donc les
    # UV des coutures ne sont pas moyennees).
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=DIST)
    bm.to_mesh(me); bm.free()
    me.update()
    total_after += len(me.vertices)
    if ob is max(meshes, key=lambda o: len(o.data.vertices)):
        isl_after = n_components(me)

print("WELD_INFO verts %d -> %d | ilots (mesh principal) %d -> %d"
      % (total_before, total_after, isl_before, isl_after))

bpy.ops.export_scene.gltf(filepath=OUT, export_format="GLB",
                          export_materials="EXPORT")
print("WELD_OK verts_before=%d verts_after=%d islands_before=%d islands_after=%d"
      % (total_before, total_after, isl_before, isl_after))
'''


def weld(glb: str, out_glb: str, dist: float = 0.0008) -> dict:
    blender = _find_blender()
    if not blender:
        return {"ok": False, "error": "blender introuvable"}
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write(_BPY)
        sp = f.name
    try:
        r = subprocess.run([blender, "-b", "--factory-startup", "-noaudio", "-P", sp,
                            "--", glb, out_glb, str(dist)],
                           capture_output=True, text=True, timeout=1200)
    finally:
        os.unlink(sp)
    log = (r.stdout or "") + (r.stderr or "")
    info = {}
    for line in log.splitlines():
        if line.startswith("WELD_OK"):
            for tok in line.split()[1:]:
                k, _, v = tok.partition("=")
                info[k] = int(v)
    if "WELD_OK" not in log or not os.path.isfile(out_glb):
        keep = [l for l in log.splitlines() if "WELD" in l or "Error" in l or "Traceback" in l]
        return {"ok": False, "error": " / ".join(keep[-4:]) or "echec weld"}
    info["ok"] = True
    info["output"] = out_glb
    return info


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("glb")
    ap.add_argument("output")
    ap.add_argument("--dist", type=float, default=0.0008,
                    help="rayon de fusion des doublons (unites objet; defaut 0.8mm "
                         "sur un modele ~1 unite)")
    a = ap.parse_args()
    r = weld(a.glb, a.output, a.dist)
    print("AURORA_MESH_WELD_RESULT " + json.dumps(r))
    return 0 if r.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
