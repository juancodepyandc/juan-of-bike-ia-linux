from PIL import Image, ImageEnhance, ImageFilter
import numpy as np

TEX_PATH = "/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/clean_dilated_texture_4k.png"
im = Image.open(TEX_PATH).convert("RGB")
arr = np.array(im, dtype=np.float32)

# Warm Métis Caramel Color Grading
# Target métis skin: R ~ 190-215, G ~ 130-155, B ~ 85-110 (Golden caramel / métis chaud)
r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]

# Detect skin pixels (warm tones where R > G > B and brightness > 60 and not pure white sclera)
is_eye_white = (r > 210) & (g > 210) & (b > 210)
is_dark_pupil = (r < 45) & (g < 45) & (b < 45)
is_skin = (r > 70) & (r > g) & (g > b - 15) & (~is_eye_white) & (~is_dark_pupil)

# Apply warm métis golden-caramel color shift
# Increase melanin warmth (boost red-gold, reduce pale blue/grey)
arr_skin_r = arr[:, :, 0]
arr_skin_g = arr[:, :, 1]
arr_skin_b = arr[:, :, 2]

# Target luminance scaling towards rich warm caramel
# For pale pixels (r > 180, g > 150, b > 140), tint towards warm caramel (#C98251 -> r:201, g:130, b:81)
is_pale_skin = is_skin & (b > 120) & (r > 160)
arr[is_pale_skin, 0] = arr[is_pale_skin, 0] * 0.95 + 205 * 0.05
arr[is_pale_skin, 1] = arr[is_pale_skin, 1] * 0.82 + 138 * 0.18
arr[is_pale_skin, 2] = arr[is_pale_skin, 2] * 0.65 + 88 * 0.35

# General skin warming across all skin pixels
skin_mask = is_skin & (~is_pale_skin)
arr[skin_mask, 0] = np.clip(arr[skin_mask, 0] * 1.04 + 12, 0, 255)
arr[skin_mask, 1] = np.clip(arr[skin_mask, 1] * 0.96 + 4, 0, 255)
arr[skin_mask, 2] = np.clip(arr[skin_mask, 2] * 0.88 - 6, 0, 255)

im_out = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
OUT_TEX = "/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/rich_metis_texture_4k.png"
im_out.save(OUT_TEX)
print(f"SUCCESS: Generated rich métis 4K texture: {OUT_TEX}")
