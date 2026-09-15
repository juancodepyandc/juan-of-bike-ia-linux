import numpy as np
from PIL import Image
from scipy.ndimage import median_filter

BASE_TEX = "/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/enhanced_base_texture_4k.png"

im = Image.open(BASE_TEX).convert("RGB")
arr = np.array(im, dtype=np.float32)
w, h = im.size

r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]

# Target rich golden-caramel métis tone
target_metis = np.array([195.0, 128.0, 80.0])

# 1. Clean glitch speckles in face skin region (y <= 0.70 * h)
y_coords, x_coords = np.mgrid[0:h, 0:w]
is_upper_half = y_coords <= int(0.70 * h)

# Detect magenta/cyan glitch speckles on face
is_magenta_glitch = is_upper_half & (r > 180) & (g < 130) & (b > 130) & (r > g + 50)
is_cyan_glitch = is_upper_half & (b > 160) & (g > 140) & (r < 130)
is_black_glitch_face = is_upper_half & (r < 40) & (g < 40) & (b < 40) & (y_coords > int(0.25 * h)) & (x_coords > int(0.40 * w)) & (x_coords < int(0.85 * w))

glitch_mask = is_magenta_glitch | is_cyan_glitch

# Soften ear redness
is_ear_red = is_upper_half & (r > 180) & (g < 100) & (b < 90) & (r > 2.0 * g)
arr[is_ear_red, 0] = np.clip(arr[is_ear_red, 0] * 0.88, 0, 255)
arr[is_ear_red, 1] = np.clip(arr[is_ear_red, 1] * 1.35, 0, 255)
arr[is_ear_red, 2] = np.clip(arr[is_ear_red, 2] * 1.20, 0, 255)

# Replace glitch speckles with surrounding skin tone
arr[glitch_mask, 0] = target_metis[0]
arr[glitch_mask, 1] = target_metis[1]
arr[glitch_mask, 2] = target_metis[2]

# Fill Arm Swatches with target rich golden-caramel métis tone
cx_l, cy_l = int(0.3655 * w), int((1.0 - 0.8289) * h)
cx_r, cy_r = int(0.7817 * w), int((1.0 - 0.5153) * h)

for cx, cy in [(cx_l, cy_l), (cx_r, cy_r)]:
    arr[cy-260:cy+260, cx-260:cx+260, 0] = target_metis[0]
    arr[cy-260:cy+260, cx-260:cx+260, 1] = target_metis[1]
    arr[cy-260:cy+260, cx-260:cx+260, 2] = target_metis[2]

out_im = Image.fromarray(arr.astype(np.uint8))
out_im.save(BASE_TEX)
print("SUCCESS: Cleaned face glitch artifacts and harmonized skin swatches!")
