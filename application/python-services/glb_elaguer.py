#!/usr/bin/env python3
"""Retire les materiaux orphelins et les donnees binaires que plus rien ne
reference. Apres une segmentation, l'ancien materiau unique et sa texture
metallic-roughness restent dans le fichier sans qu'aucune primitive n'y touche.

Usage: python glb_elaguer.py --glb entree.glb --out sortie.glb
"""
import argparse, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import glb_io

_ap = argparse.ArgumentParser()
_ap.add_argument("--glb", required=True)
_ap.add_argument("--out", required=True)
_a = _ap.parse_args()
SRC, DST = _a.glb, _a.out
j,blob=glb_io.load(SRC)
prims=j["meshes"][0]["primitives"]

# 1. materiaux reellement utilises
used_mat=sorted({p["material"] for p in prims})
mat_map={old:i for i,old in enumerate(used_mat)}
j["materials"]=[j["materials"][o] for o in used_mat]
for p in prims: p["material"]=mat_map[p["material"]]

# 2. textures -> images encore referencees
def tex_of(m):
    out=[]
    pbr=m.get("pbrMetallicRoughness",{})
    for k in ("baseColorTexture","metallicRoughnessTexture"):
        if k in pbr: out.append((pbr,k))
    for k in ("normalTexture","occlusionTexture","emissiveTexture"):
        if k in m: out.append((m,k))
    return out
used_tex=sorted({d[k]["index"] for m in j["materials"] for d,k in tex_of(m)})
tex_map={o:i for i,o in enumerate(used_tex)}
j["textures"]=[j["textures"][o] for o in used_tex]
for m in j["materials"]:
    for d,k in tex_of(m): d[k]["index"]=tex_map[d[k]["index"]]
used_img=sorted({t["source"] for t in j["textures"]})
img_map={o:i for i,o in enumerate(used_img)}
j["images"]=[j["images"][o] for o in used_img]
for t in j["textures"]: t["source"]=img_map[t["source"]]

# 3. accesseurs utilises
used_acc=sorted({p["indices"] for p in prims} | {a for p in prims for a in p["attributes"].values()})
acc_map={o:i for i,o in enumerate(used_acc)}
j["accessors"]=[j["accessors"][o] for o in used_acc]
for p in prims:
    p["indices"]=acc_map[p["indices"]]
    p["attributes"]={k:acc_map[v] for k,v in p["attributes"].items()}

# 4. recompose le binaire avec les seules bufferViews vivantes
neuf=bytearray(); nbv=[]
def repack(bvi):
    bv=j["bufferViews"][bvi]
    o=bv.get("byteOffset",0); data=blob[o:o+bv["byteLength"]]
    while len(neuf)%4: neuf.append(0)
    off=len(neuf); neuf.extend(data)
    d={"buffer":0,"byteOffset":off,"byteLength":len(data)}
    for k in ("byteStride","target"):
        if k in bv: d[k]=bv[k]
    nbv.append(d); return len(nbv)-1
for a in j["accessors"]: a["bufferView"]=repack(a["bufferView"])
for im in j["images"]: im["bufferView"]=repack(im["bufferView"])
j["bufferViews"]=nbv
j["buffers"]=[{"byteLength":len(neuf)}]
n=glb_io.save(DST,j,bytes(neuf))
print("materiaux %d | textures %d | images %d"%(len(j["materials"]),len(j["textures"]),len(j["images"])))
print("taille: %.1f Mo -> %.1f Mo"%(len(blob)/1e6,n/1e6))
