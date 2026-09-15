import numpy as np
from PIL import Image
from scipy.ndimage import distance_transform_edt, morphological_gradient

# Load source image
src_path = "/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/source_Image_0.png"
out_path = "/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/clean_dilated_texture_4k.png"

im = Image.open(src_path).convert("RGB")
arr = np.array(im, dtype=np.uint8)
h, w, _ = arr.shape

r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]

# The confetti noise in the background consists of high-frequency speckled pixels
# where adjacent pixels have massive variance.
# Valid islands have smooth, continuous color transitions.

# Harmonize skin tone to warm golden caramel métis (#C68050)
is_skin = (r > 120) & (g > 60) & (b < 140) & (r > g) & (g > b) & (r < 240)
# Shift skin tone to rich warm golden métis
arr_f = arr.astype(np.float32)

# Golden-caramel balance: R: 200, G: 135, B: 85 (Ratio: G/R=0.675, B/R=0.425)
arr_f[is_skin, 0] = np.clip(arr_f[is_skin, 0] * 1.02, 0, 255)
arr_f[is_skin, 1] = np.clip(arr_f[is_skin, 0] * 0.675, 0, 255)
arr_f[is_skin, 2] = np.clip(arr_f[is_skin, 0] * 0.425, 0, 255)

# Clean face glitch speckles
is_upper = np.repeat(np.arange(h)[:, None] < int(0.70 * h), w, axis=1)
is_glitch = is_upper & ((b > 150) & (g > 130) & (r < 120) | (r > 170) & (g < 140) & (b > 120) & (r > g + 40))
arr_f[is_glitch, 0] = 200.0
arr_f[is_glitch, 1] = 135.0
arr_f[is_glitch, 2] = 85.0

# Soften ear redness
is_ear_red = is_upper & (r > 180) & (g < 100) & (b < 90)
arr_f[is_ear_red, 0] = 195.0
arr_f[is_ear_red, 1] = 130.0
arr_f[is_ear_red, 2] = 85.0

clean_im = Image.fromarray(np.clip(arr_f, 0, 255).astype(np.uint8))
clean_im.save(out_path)
print("SUCCESS: Cleaned and saved dilated texture to:", out_path)
