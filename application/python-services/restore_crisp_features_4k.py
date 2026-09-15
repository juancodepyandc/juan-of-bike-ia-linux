from PIL import Image
import numpy as np

# Load clean texture
im_clean = Image.open("/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/clean_dilated_texture_4k.png").convert("RGB")
arr_clean = np.array(im_clean, dtype=np.float32)

# Rich Warm Métis Caramel Reference: R: 208, G: 140, B: 85 (#D08C55)
r, g, b = arr_clean[:, :, 0], arr_clean[:, :, 1], arr_clean[:, :, 2]

# Detect skin (exclude dark eyebrows r < 60 and white sclera r > 215)
is_eyebrows_or_eyes = (r < 65) & (g < 65) & (b < 65)
is_sclera = (r > 215) & (g > 215) & (b > 215)
is_skin = (r > 75) & (r > g) & (g >= b - 15) & (~is_eyebrows_or_eyes) & (~is_sclera)

# Smoothly shift skin to warm golden métis
arr_clean[is_skin, 0] = np.clip(arr_clean[is_skin, 0] * 0.40 + 208.0 * 0.60, 0, 255)
arr_clean[is_skin, 1] = np.clip(arr_clean[is_skin, 1] * 0.40 + 140.0 * 0.60, 0, 255)
arr_clean[is_skin, 2] = np.clip(arr_clean[is_skin, 2] * 0.40 + 85.0 * 0.60, 0, 255)

# Keep eyebrows jet black
arr_clean[is_eyebrows_or_eyes, 0] = 18.0
arr_clean[is_eyebrows_or_eyes, 1] = 12.0
arr_clean[is_eyebrows_or_eyes, 2] = 8.0

im_out = Image.fromarray(arr_clean.astype(np.uint8))
OUT_TEX = "/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/rich_metis_texture_4k.png"
im_out.save(OUT_TEX)
print(f"SUCCESS: Restored crisp dark eyebrows, expressive eyes, and rich métis skin on: {OUT_TEX}")
