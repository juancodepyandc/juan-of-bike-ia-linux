from PIL import Image, ImageEnhance
import numpy as np

# Load original clean texture
im_orig = Image.open("/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/clean_dilated_texture_4k.png").convert("RGB")
arr = np.array(im_orig, dtype=np.float32)

r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]

# Compute luminance (perceived brightness)
lum = 0.299 * r + 0.587 * g + 0.114 * b

# Detect skin regions (warm tones where R > G and brightness > 40, excluding sclera and pupils)
is_sclera = (r > 218) & (g > 218) & (b > 218)
is_pupil_or_brows = (r < 48) & (g < 48) & (b < 48)
is_skin = (r > 60) & (r > g) & (g >= b - 20) & (~is_sclera) & (~is_pupil_or_brows)

# Authentic Golden-Caramel Métis Palette Transfer:
# We preserve the relative luminance and micro-details (freckles, lip texture, skin pores, shadows)
# Target métis hue: Warm caramel with golden undertones (R: 1.0, G: 0.68, B: 0.44)
norm_lum = lum[is_skin] / 255.0

# Natural tone curve: rich warm shadows, radiant golden midtones, soft highlights
target_r = np.clip(norm_lum ** 0.82 * 255.0 * 1.04, 0, 255)
target_g = np.clip(norm_lum ** 0.96 * 255.0 * 0.74, 0, 255)
target_b = np.clip(norm_lum ** 1.15 * 255.0 * 0.52, 0, 255)

# Smooth blend preserving original contrast and freckles
arr[is_skin, 0] = arr[is_skin, 0] * 0.25 + target_r * 0.75
arr[is_skin, 1] = arr[is_skin, 1] * 0.25 + target_g * 0.75
arr[is_skin, 2] = arr[is_skin, 2] * 0.25 + target_b * 0.75

# Preserve clean deep dark tones for pupils & eyebrows
arr[is_pupil_or_brows, 0] = 16.0
arr[is_pupil_or_brows, 1] = 12.0
arr[is_pupil_or_brows, 2] = 10.0

# Preserve crisp white sclera
arr[is_sclera, 0] = np.clip(arr[is_sclera, 0] * 1.02, 0, 255)
arr[is_sclera, 1] = np.clip(arr[is_sclera, 1] * 1.02, 0, 255)
arr[is_sclera, 2] = np.clip(arr[is_sclera, 2] * 1.02, 0, 255)

im_out = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
OUT_TEX = "/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/rich_metis_texture_4k.png"
im_out.save(OUT_TEX)
print(f"SUCCESS: Generated natural Pixar métis skin texture with preserved freckles & details: {OUT_TEX}")
