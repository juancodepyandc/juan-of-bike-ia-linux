import numpy as np
from PIL import Image

ORIG_TEX = "/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/orig_raw_texture_Image_0.png"
im = Image.open(ORIG_TEX).convert("RGB")
w, h = im.size
print("Size:", (w, h))

arr = np.array(im, dtype=np.float32)
r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]

# Eyebrows & Hair: dark (r < 65, g < 65, b < 65)
# Sclera (eye white): bright (r > 210, g > 210, b > 210, abs(r-g) < 15, abs(r-b) < 15)
# Iris (eye brown/black): dark/amber in small eye region
# Clothes / Jeans: blue (b > r + 10)
# T-Shirt: black (r < 40, g < 40, b < 40)
# Skin: r in [110, 240], r > b + 25, g in [60, 180]

skin_mask = (r > 100) & (r > b + 25) & (g > 55) & (b < 190) & (r > g) & ~((r > 215) & (g > 215) & (b > 215))

print(f"Skin pixels count: {np.sum(skin_mask)} / {w*h} ({np.sum(skin_mask)/(w*h)*100:.1f}%)")
mean_skin = [arr[skin_mask, 0].mean(), arr[skin_mask, 1].mean(), arr[skin_mask, 2].mean()]
print(f"Current Skin Mean RGB in raw texture: {mean_skin}")
