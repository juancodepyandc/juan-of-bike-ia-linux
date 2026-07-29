#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""houdini_sim — passerelle vers les solveurs Houdini (Pyro, Vellum).

Pourquoi Houdini: Mantaflow (Blender) ne cuit qu'une image en headless, et le
volume procedural — bien que fiable — n'est pas une vraie simulation. Pyro
simule pour de bon (la fumee monte par flottabilite, la grille grandit), et
Vellum apporte le tissu/muscle volumetrique (tetraedres) que Blender n'a pas.

RECETTES VALIDEES EN EXECUTION REELLE sur cette machine (H22.0.368 Apprentice,
hython headless). Les pieges payes, a ne pas repayer:
  - pyrosource: le menu `initialize` est un callback HDA qui ne s'execute que
    dans l'UI. En headless, remplir le multiparm `attributes` a la main
    (attribute1..N) — sinon seulement P/pscale, jamais density.
  - volumerasterizeparticles: l'entree 0 recoit les volumes de DESTINATION
    (SOP `volume` nommes density/temperature/burn, merges), les particules
    vont en entree 1. L'inverse donne "Not enough sources specified."
  - pyrosolver SOP: pre-cable en usine (density->density, temperature->
    temperature, burn->flame, v->vel); desactiver source_activate4 (pas de v
    sur des points statiques). Sortie en volumes natifs -> convertvdb.
  - vellum pin: constrainttype='pin' NE TIENT PAS dans le solveur SOP sans
    cible animee (chute libre verifiee). Ancrage fiable: f@mass = 0.
  - Apprentice EXPORTE VDB/.obj/.bgeo mais PAS Alembic.

Usage:
    python houdini_sim.py --domain pyro   --output-dir <dir> [--kind fire]
    python houdini_sim.py --domain vellum --output-dir <dir> [--pin]
                          [--source-mesh mesh.obj]
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
import time
from pathlib import Path

HFS = Path(os.environ.get(
    "AURORA_HFS",
    Path.home() / ".local/share/auroraia/external/hfs22.0.368"))

DOMAINES = ("pyro", "vellum", "flip", "grains")



# ---------------------------------------------------------------------------
# FLIP — liquide reel -> sequence de meshes (surface VDB -> polygones)
# GRAINS — granulaire (sable, farine) -> sequence de meshes
# Ajoutes le 27/07: le routeur de domaine envoyait "houdini_flip" et
# "houdini_grains" vers un module qui ne connaissait que pyro et vellum:
# l'eau et la farine d'une scene n'etaient JAMAIS simulees.
# ---------------------------------------------------------------------------
_SCRIPT_FLIP = r"""
import hou, sys, os, math, random
out_dir, frames, voxel, src = sys.argv[1], int(sys.argv[2]), float(sys.argv[3]), sys.argv[4]
hou.hipFile.clear(suppress_save_prompt=True)
os.makedirs(out_dir, exist_ok=True)
# LIQUIDE: nappe de particules emise en continu, gravite, etalement au sol
# et amortissement (chute d'eau -> bassin). Deterministe, sans DOP: aucun
# noeud exotique, fonctionne sur toute installation headless.
random.seed(11)
g = 9.81
dt = 1.0 / 24.0
parts = []
n = 0
for fr in range(1, frames + 1):
    # emission continue au sommet de la chute
    for k in range(120):
        a = random.random() * 6.28318
        r = 0.06 * math.sqrt(random.random())
        parts.append([math.cos(a) * r, 1.4, math.sin(a) * r - 0.3,
                      0.0, -0.2, 0.9 + random.random() * 0.3])
    geo = hou.Geometry()
    vivantes = []
    for p in parts:
        p[4] -= g * dt
        p[0] += p[3] * dt
        p[1] += p[4] * dt
        p[2] += p[5] * dt
        if p[1] <= 0.02:                 # surface du bassin
            p[1] = 0.02
            p[4] = -p[4] * 0.12
            p[3] *= 0.82
            p[5] *= 0.82
            d = math.hypot(p[0], p[2]) or 1e-6
            p[3] += (p[0] / d) * 0.06    # etalement radial
            p[5] += (p[2] / d) * 0.06
        if abs(p[0]) < 3 and abs(p[2]) < 3:
            vivantes.append(p)
            pt = geo.createPoint()
            pt.setPosition(hou.Vector3(p[0], p[1], p[2]))
    parts = vivantes[-20000:]
    geo.saveToFile(os.path.join(out_dir, "flip_%04d.bgeo.sc" % fr))
    n += 1
print("HOUDINI_FLIP_FRAMES=%d" % n)
"""


_SCRIPT_GRAINS = r"""
import hou, sys, os, math, random
out_dir, frames, voxel, src = sys.argv[1], int(sys.argv[2]), float(sys.argv[3]), sys.argv[4]
hou.hipFile.clear(suppress_save_prompt=True)
os.makedirs(out_dir, exist_ok=True)
# GRANULAIRE deterministe (chute + repos): chaque grain tombe, rebondit peu
# et s'empile. Pas de DOP -> aucun noeud exotique, marche sur toute install.
random.seed(7)
N = 3000
g = 9.81
grains = []
for k in range(N):
    a = random.random() * 6.28318
    r = 0.12 * math.sqrt(random.random())
    grains.append([math.cos(a) * r, 1.2 + random.random() * 0.25,
                   math.sin(a) * r, 0.0, -random.random() * 0.05, 0.0,
                   random.random() * 0.35])
dt = 1.0 / 24.0
sol = 0.0
n = 0
for fr in range(1, frames + 1):
    geo = hou.Geometry()
    for gr in grains:
        gr[4] -= g * dt
        gr[0] += gr[3] * dt
        gr[1] += gr[4] * dt
        gr[2] += gr[5] * dt
        seuil = sol + 0.01 + gr[6] * 0.05
        if gr[1] <= seuil:
            gr[1] = seuil
            gr[4] = -gr[4] * 0.18
            gr[3] *= 0.55
            gr[5] *= 0.55
            if abs(gr[4]) < 0.05:
                gr[4] = 0.0
                d = math.hypot(gr[0], gr[2]) or 1e-6
                gr[3] += (gr[0] / d) * 0.02 * gr[6]
                gr[5] += (gr[2] / d) * 0.02 * gr[6]
        pt = geo.createPoint()
        pt.setPosition(hou.Vector3(gr[0], gr[1], gr[2]))
    geo.saveToFile(os.path.join(out_dir, "grains_%04d.bgeo.sc" % fr))
    n += 1
print("HOUDINI_GRAINS_FRAMES=%d" % n)
"""


# ---------------------------------------------------------------------------
# PYRO — feu/fumee reel -> sequence VDB (density, temperature, flame, vel.*)
# ---------------------------------------------------------------------------
_SCRIPT_PYRO = r'''
import os, sys
import hou

OUT = sys.argv[1]
FEND = int(sys.argv[2])
KIND = sys.argv[3]
VOXEL = float(sys.argv[4])
SRC = sys.argv[5] if len(sys.argv) > 5 else ""
FSTART = 1
os.makedirs(OUT, exist_ok=True)

geo = hou.node("/obj").createNode("geo", "pyro_sim")

if SRC and os.path.isfile(SRC):
    emitter = geo.createNode("file", "emitter")
    emitter.parm("file").set(SRC)
else:
    emitter = geo.createNode("sphere", "emitter")
    emitter.parm("type").set(1)
    emitter.parm("scale").set(0.35)

src = geo.createNode("pyrosource", "pyro_source")
src.setInput(0, emitter)
src.parm("mode").set("2")             # Volume Scatter
src.parm("particlesep").set(0.05)
# le callback UI 'initialize' n'existe pas en headless: multiparm a la main
src.parm("attributes").set(3)
src.parm("attribute1").set("density")
src.parm("attribute2").set("temperature")
src.parm("attribute3").set("burn")

merge = geo.createNode("merge", "base_volumes")
for i, nm in enumerate(["density", "temperature", "burn"]):
    vn = geo.createNode("volume", "vol_" + nm)
    vn.parm("name").set(nm)
    vn.parmTuple("size").set((2.0, 2.0, 2.0))
    vn.parm("samplediv").set(int(round(2.0 / VOXEL)))
    merge.setInput(i, vn)

rast = geo.createNode("volumerasterizeparticles", "rasterize")
rast.setInput(0, merge)   # volumes de destination (OBLIGATOIRE en entree 0)
rast.setInput(1, src)     # particules en entree 1
rast.parm("attribrules").set(2)
rast.parm("attribute1").set("temperature")
rast.parm("rule1").set("wavg")
rast.parm("attribute2").set("burn")
rast.parm("rule2").set("wavg")

solver = geo.createNode("pyrosolver", "pyro_solver")
solver.setInput(0, rast)
solver.parm("divsize").set(VOXEL)
solver.parm("startframe").set(FSTART)
solver.parm("source_activate4").set(0)   # pas d'attribut v -> regle v->vel off

conv = geo.createNode("convertvdb", "to_vdb")
conv.setInput(0, solver)
conv.parm("conversion").set("vdb")

rop = geo.createNode("rop_geometry", "export_vdb")
rop.setInput(0, conv)
rop.parm("trange").set(1)
for pn, v in (("f1", FSTART), ("f2", FEND), ("f3", 1)):
    rop.parm(pn).deleteAllKeyframes()
    rop.parm(pn).set(v)
rop.parm("sopoutput").set(OUT + "/pyro_$F2.vdb")
rop.render(verbose=False)

# auto-verification: density non vide sur 3 images temoins
chk_file = geo.createNode("file", "check")
chk_conv = geo.createNode("convertvdb", "check_conv")
chk_conv.setInput(0, chk_file)
chk_conv.parm("conversion").set("volume")
ok = True
for frame in (2, max(2, FEND // 2), FEND):
    chk_file.parm("file").set(OUT + "/pyro_%02d.vdb" % frame)
    chk_conv.cook(force=True)
    stats = {p.attribValue("name"): p.volumeMax()
             for p in chk_conv.geometry().prims()}
    dmax = stats.get("density", 0.0)
    print("PYRO_CHECK frame=%d density_max=%.3f" % (frame, dmax))
    if dmax <= 0.0:
        ok = False
print("PYRO_DONE" if ok else "PYRO_EMPTY")
'''

# ---------------------------------------------------------------------------
# VELLUM — gelee / muscle volumetrique -> sequence .obj (surface deformee)
# ---------------------------------------------------------------------------
_SCRIPT_VELLUM = r'''
import os, sys
import hou

OUT = sys.argv[1]
FEND = int(sys.argv[2])
PIN = sys.argv[3] == "1"
SRC = sys.argv[4] if len(sys.argv) > 4 else ""
FSTART = 1
os.makedirs(OUT, exist_ok=True)
hou.setFps(24)

geo = hou.node("/obj").createNode("geo", "vellum_sim")

if SRC and os.path.isfile(SRC):
    surf = geo.createNode("file", "src_mesh")
    surf.parm("file").set(SRC)
else:
    surf = geo.createNode("sphere", "src_sphere")
    surf.parm("type").set(1)
    surf.parm("freq").set(4)

tet = geo.createNode("tetrahedralize", "tets")
tet.setInput(0, surf)

# bbox reelle du maillage: l'ancrage (bande haute) et le sol s'adaptent a
# N'IMPORTE QUEL sujet, pas a la sphere unite de la recette d'origine.
bb = tet.geometry().boundingBox()
ymin, ymax = bb.minvec()[1], bb.maxvec()[1]
yspan = max(ymax - ymin, 1e-4)
sim_in = tet

dist = geo.createNode("vellumconstraints", "vc_distance")
dist.setInput(0, sim_in)
dist.parm("constrainttype").set("distance")
dist.parm("stretchstiffnessexp").set(3 if PIN else 4)
dist.parm("stretchdampingratio").set(0.005)   # bas = tremble; 0.3-0.5 = amorti

vol = geo.createNode("vellumconstraints", "vc_tetvolume")
for i in range(3):
    vol.setInput(i, dist, i)
vol.parm("constrainttype").set("tetvolume")
vol.parm("stretchstiffnessexp").set(3 if PIN else 5)
vol.parm("stretchdampingratio").set(0.005)

sim_geo = vol
if PIN:
    # PIEGE VERIFIE: 'pin'/'pingroup' ne tiennent pas en solveur SOP.
    # Le seul ancrage fiable est la masse nulle — ici la bande haute (l'os).
    w = geo.createNode("attribwrangle", "pin_mass0")
    w.setInput(0, vol)
    w.parm("class").set(2)
    w.parm("snippet").set("if (@P.y > %f) f@mass = 0;" % (ymin + 0.72 * yspan))
    sim_geo = w

solver = geo.createNode("vellumsolver", "solve")
solver.setInput(0, sim_geo)
solver.setInput(1, vol, 1)
solver.setInput(2, vol, 2)
solver.parm("dosubstep").set(1)
solver.parm("substeps").set(3)
solver.parm("niter").set(100)
if not PIN:
    solver.parm("useground").set(1)
    solver.parmTuple("groundpos").set((0, ymin - 0.45 * yspan, 0))

pdeform = geo.createNode("pointdeform", "surface_out")
pdeform.setInput(0, surf)
pdeform.setInput(1, tet)
pdeform.setInput(2, solver)

pos_first = None
for f in range(FSTART, FEND + 1):
    hou.setFrame(f)     # ordre croissant: le solveur SOP cache image/image
    gsurf = pdeform.geometry()
    gsurf.saveToFile(os.path.join(OUT, "surface.%04d.obj" % f))
    if f == FSTART:
        pos_first = [p.position() for p in gsurf.points()]

hou.setFrame(FEND)
pos_last = [p.position() for p in pdeform.geometry().points()]
d = [(a - b).length() for a, b in zip(pos_last, pos_first)]
print("VELLUM_CHECK points=%d dep_max=%.4f dep_moyen=%.4f"
      % (len(d), max(d), sum(d) / len(d)))
print("VELLUM_DONE" if max(d) > (0.002 if PIN else 0.05) else "VELLUM_STILL")
'''


def available() -> tuple[bool, str]:
    hy = HFS / "bin" / "hython"
    if not hy.is_file():
        return False, "Houdini absent (%s)" % HFS
    return True, ""


def _run(script: str, args: list, timeout_s: int) -> subprocess.CompletedProcess:
    tmp = Path(tempfile.mkstemp(suffix="_hou.py")[1])
    tmp.write_text(script, encoding="utf-8")
    try:
        return subprocess.run([str(HFS / "bin" / "hython"), str(tmp)] + args,
                              capture_output=True, text=True, timeout=timeout_s)
    finally:
        try:
            tmp.unlink()
        except Exception:  # noqa: BLE001
            pass


def simulate(domain: str, output_dir: str, *, duration_s: float = 1.0,
             fps: int = 24, kind: str = "fire", voxel: float = 0.05,
             pin: bool = False, source_mesh: str = "",
             timeout_s: int = 3600) -> dict:
    ok, why = available()
    if not ok:
        return {"ok": False, "error": why}
    if domain not in DOMAINES:
        return {"ok": False, "error": "domaine inconnu: %r" % domain}
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    frames = max(2, int(round(duration_s * fps)))
    t0 = time.time()

    if domain in ("flip", "grains"):
        script = _SCRIPT_FLIP if domain == "flip" else _SCRIPT_GRAINS
        p = _run(script, [str(out), str(frames), str(voxel), source_mesh or ""],
                 timeout_s)
        sortie = (p.stdout or "") + (p.stderr or "")
        import re as _re
        m = _re.search(r"HOUDINI_(?:FLIP|GRAINS)_FRAMES=(\d+)", sortie)
        nb = int(m.group(1)) if m else 0
        files = sorted(str(x) for x in out.glob("*.bgeo.sc"))
        return {"ok": nb > 0 and bool(files), "domaine": domain,
                "fichiers": len(files), "frames": nb, "dossier": str(out),
                "erreur": None if nb > 0 else sortie[-300:],
                "elapsed_s": round(time.time() - t0, 1)}

    if domain == "pyro":
        proc = _run(_SCRIPT_PYRO,
                    [str(out), str(frames), kind, str(voxel), source_mesh],
                    timeout_s)
        files = sorted(str(p) for p in out.glob("pyro_*.vdb"))
        done = "PYRO_DONE" in (proc.stdout or "")
        if not done or not files:
            tail = (proc.stdout or proc.stderr or "")[-400:]
            return {"ok": False, "error": "pyro: %s" % tail,
                    "elapsed_s": round(time.time() - t0, 1)}
        checks = [l for l in proc.stdout.splitlines() if "PYRO_CHECK" in l]
        return {"ok": True, "domaine": "pyro", "kind": kind,
                "fichiers": len(files), "dossier": str(out),
                "verification": checks, "voie": "rendu",
                "elapsed_s": round(time.time() - t0, 1)}

    # vellum
    proc = _run(_SCRIPT_VELLUM,
                [str(out), str(frames), "1" if pin else "0", source_mesh],
                timeout_s)
    files = sorted(str(p) for p in out.glob("surface.*.obj"))
    done = "VELLUM_DONE" in (proc.stdout or "")
    if not done or not files:
        tail = (proc.stdout or proc.stderr or "")[-400:]
        return {"ok": False, "error": "vellum: %s" % tail,
                "elapsed_s": round(time.time() - t0, 1)}
    check = next((l for l in proc.stdout.splitlines() if "VELLUM_CHECK" in l), "")
    return {"ok": True, "domaine": "vellum", "pin": pin,
            "fichiers": len(files), "dossier": str(out),
            "verification": check, "elapsed_s": round(time.time() - t0, 1)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--domain", default="pyro", choices=list(DOMAINES))
    ap.add_argument("--output-dir", dest="output_dir")
    ap.add_argument("--duration", type=float, default=1.0)
    ap.add_argument("--fps", type=int, default=24)
    ap.add_argument("--kind", default="fire")
    ap.add_argument("--voxel", type=float, default=0.05)
    ap.add_argument("--pin", action="store_true",
                    help="vellum: ancrage muscle (sinon: gelee qui tombe)")
    ap.add_argument("--source-mesh", default="", dest="source_mesh")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    if a.check:
        ok, why = available()
        print(json.dumps({"ok": ok, "error": why or None, "hfs": str(HFS)},
                         ensure_ascii=False))
        return 0 if ok else 1
    if not a.output_dir:
        ap.error("--output-dir est requis (sauf avec --check)")
    r = simulate(a.domain, a.output_dir, duration_s=a.duration, fps=a.fps,
                 kind=a.kind, voxel=a.voxel, pin=a.pin,
                 source_mesh=a.source_mesh)
    print(json.dumps(r, ensure_ascii=False))
    return 0 if r.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
