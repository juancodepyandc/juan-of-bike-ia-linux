import numpy as np
from PIL import Image

tex_orig = "/home/juan/AuroraIA/application/output/3d/perso_soude/perso_soude.png"
tex_enh = "/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/enhanced_base_texture_4k.png"

im_o = Image.open(tex_orig).convert("RGB")
im_e = Image.open(tex_enh).convert("RGB")

arr_o = np.array(im_o)
arr_e = np.array(im_e)

print(f"Orig size: {im_o.size}, Mean RGB: {arr_o.mean(axis=(0,1))}")
print(f"Enh size: {im_e.size}, Mean RGB: {arr_e.mean(axis=(0,1))}")
