from PIL import Image
import numpy as np

# Load the original pristine 4K texture
im_orig = Image.open("/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/orig_raw_texture_Image_0.png").convert("RGB")
arr = np.array(im_orig, dtype=np.float32)

r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]

# Detect skin regions (warm tones where R > G and brightness > 40, excluding sclera and pupils)
is_sclera = (r > 215) & (g > 215) & (b > 215)
is_pupil = (r < 40) & (g < 40) & (b < 40)
is_skin = (r > 60) & (r > g) & (g >= b - 20) & (~is_sclera) & (~is_pupil)

# Enrich skin with authentic golden-caramel melanin (warm golden undertones)
# Boost warmth, reduce chalkiness/pale tones
arr[is_skin, 0] = np.clip(arr[is_skin, 0] * 1.08 + 10, 0, 255)
arr[is_skin, 1] = np.clip(arr[is_skin, 1] * 0.98 + 4, 0, 255)
arr[is_skin, 2] = np.clip(arr[is_skin, 2] * 0.82 - 8, 0, 255)

# Also fix the ears to have smooth golden-caramel skin (not harsh bright red)
is_ear_red = is_skin & (r > 160) & (r - g > 55)
arr[is_ear_red, 0] = np.clip(arr[is_ear_red, 0] * 0.95, 0, 255)
arr[is_ear_red, 1] = np.clip(arr[is_ear_red, 1] * 1.15 + 10, 0, 255)
arr[is_ear_red, 2] = np.clip(arr[is_ear_red, 2] * 1.10 + 8, 0, 255)

im_out = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
OUT_TEX = "/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/rich_metis_texture_4k.png"
im_out.save(OUT_TEX)
print(f"SUCCESS: Created pristine golden-caramel métis 4K texture: {OUT_TEX}")
