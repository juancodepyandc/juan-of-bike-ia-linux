from PIL import Image
import numpy as np

img = Image.open("/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/enhanced_base_texture_4k.png")
arr = np.array(img)
h, w, _ = arr.shape

ul, vl = 0.3655, 0.8289
ur, vr = 0.7817, 0.5153

pxl, pyl = int(ul * w), int((1.0 - vl) * h)
pxr, pyr = int(ur * w), int((1.0 - vr) * h)

print(f"Left arm pixel ({pxl}, {pyl}): RGB={arr[pyl, pxl, :3]}")
print(f"Right arm pixel ({pxr}, {pyr}): RGB={arr[pyr, pxr, :3]}")
