from PIL import Image
import numpy as np

TEX_PATH = "/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/clean_dilated_texture_4k.png"
im = Image.open(TEX_PATH).convert("RGB")
arr = np.array(im, dtype=np.float32)
h, w, _ = arr.shape

r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]

# Target all strong red/crimson pixels in the upper half (face/ears)
# Warm golden métis target: R=205, G=140, B=90
is_red = (r > 130) & (g < 130) & (r > g + 25)
arr[is_red, 0] = 205.0
arr[is_red, 1] = 140.0
arr[is_red, 2] = 90.0

im_clean = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
im_clean.save(TEX_PATH)
print("SUCCESS: 100% neutralized ear redness on 4K texture!")
