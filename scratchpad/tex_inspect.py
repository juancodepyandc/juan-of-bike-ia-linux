import pygltflib, io
from PIL import Image
p = "application/output/3d/generations/realpath_homme4_021313/realpath_homme4_021313_final_materials.glb"
g = pygltflib.GLTF2().load(p)
blob = g.binary_blob()
im0 = g.images[0]
bv = g.bufferViews[im0.bufferView]
off = bv.byteOffset or 0
data = blob[off:off+bv.byteLength]
img = Image.open(io.BytesIO(data))
print("mode",img.mode,"size",img.size,"format",img.format)
# check ICC / gamma chunks
print("info keys:", list(img.info.keys()))
print("icc?", 'icc_profile' in img.info, "gamma", img.info.get('gamma'))
img.convert("RGB").save("scratchpad/basecolor.png")
# stats
import numpy as np
a=np.asarray(img.convert("RGB")).astype(float)
print("mean RGB", a.reshape(-1,3).mean(0))
