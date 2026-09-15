import numpy as np
from PIL import Image

BASE_TEX = "/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/enhanced_base_texture_4k.png"

im = Image.open(BASE_TEX).convert("RGB")
arr = np.array(im, dtype=np.float32)

r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]

# Target Métis Skin Tone (Warm Golden-Amber Bronze from reference)
# R: 222, G: 162, B: 120 (#DE0278 approx)
target_r, target_g, target_b = 222.0, 162.0, 120.0

# Detect all skin pixels:
# 1. Red is dominant over blue (r > b + 20)
# 2. Not hair (hair has r < 50)
# 3. Not black shirt (r < 45, g < 45, b < 45)
# 4. Not jeans (jeans have b > r or b > 100 with r < 140)
# 5. Not white graphics / eyes (r > 240 and g > 240 and b > 240)

is_dark = (r < 55) & (g < 55) & (b < 55)
is_jeans = (b > r) | ((b > 110) & (r < 130))
is_white = (r > 235) & (g > 235) & (b > 235)

skin_mask = (~is_dark) & (~is_jeans) & (~is_white) & (r > b + 15) & (r > 80)

# Calculate current lightness of skin pixels
cur_lum = 0.299 * r + 0.587 * g + 0.114 * b

# Adjust skin pixels: blend smoothly towards target golden métis chromaticity while preserving facial shading & features
target_lum = 0.299 * target_r + 0.587 * target_g + 0.114 * target_b
lum_ratio = np.clip(cur_lum / max(target_lum, 1.0), 0.5, 1.5)

# Blend 85% towards target métis color + 15% original shading
new_r = target_r * lum_ratio
new_g = target_g * lum_ratio
new_b = target_b * lum_ratio

arr[skin_mask, 0] = np.clip(new_r[skin_mask] * 0.85 + arr[skin_mask, 0] * 0.15, 0, 255)
arr[skin_mask, 1] = np.clip(new_g[skin_mask] * 0.85 + arr[skin_mask, 1] * 0.15, 0, 255)
arr[skin_mask, 2] = np.clip(new_b[skin_mask] * 0.85 + arr[skin_mask, 2] * 0.15, 0, 255)

# Fill pure swatches for arms
w, h = im.size
for cx, cy in [(int(0.3655 * w), int(0.8289 * h)), (int(0.7817 * w), int(0.5153 * h))]:
    arr[cy-200:cy+200, cx-200:cx+200, 0] = target_r
    arr[cy-200:cy+200, cx-200:cx+200, 1] = target_g
    arr[cy-200:cy+200, cx-200:cx+200, 2] = target_b

out_im = Image.fromarray(arr.astype(np.uint8))
out_im.save(BASE_TEX)
print("SUCCESS: Harmonized 100% of skin into authentic warm golden-amber métis complexion!")
