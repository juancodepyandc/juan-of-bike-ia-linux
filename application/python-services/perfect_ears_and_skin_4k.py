from PIL import Image
import numpy as np

TEX_PATH = "/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/rich_metis_texture_4k.png"
im = Image.open(TEX_PATH).convert("RGB")
arr = np.array(im, dtype=np.float32)

r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]

# Target golden-caramel métis skin color
TARGET_SKIN = np.array([205.0, 138.0, 85.0], dtype=np.float32)

# Detect oversaturated red or pale ear/skin regions
is_sclera = (r > 218) & (g > 218) & (b > 218)
is_dark = (r < 40) & (g < 40) & (b < 40)

# Reddish ear cartilage (R > 140, R - G > 40)
is_red_cartilage = (r > 130) & (r - g > 35) & (~is_sclera)
for c in range(3):
    arr[is_red_cartilage, c] = arr[is_red_cartilage, c] * 0.35 + TARGET_SKIN[c] * 0.65

# Pale ear lobe / skin patches (B > 115 and R > 150)
is_pale_patch = (b > 115) & (r > 150) & (~is_sclera) & (~is_dark)
for c in range(3):
    arr[is_pale_patch, c] = arr[is_pale_patch, c] * 0.30 + TARGET_SKIN[c] * 0.70

im_out = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
im_out.save(TEX_PATH)
print("SUCCESS: Ears and skin perfected on 4K texture!")
