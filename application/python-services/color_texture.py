import numpy as np
from PIL import Image

ORIG_TEX = "/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/orig_raw_texture_Image_0.png"
OUT_TEX = "/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/enhanced_base_texture_4k.png"

im = Image.open(ORIG_TEX).convert("RGB")
w, h = im.size
arr = np.array(im, dtype=np.float32)

r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]

# Exclusions
is_dark = (r < 65) & (g < 65) & (b < 65)
is_white = (r > 210) & (g > 210) & (b > 210) & (abs(r - g) < 20) & (abs(r - b) < 20)
is_jeans = (b > r + 5) | ((b > 90) & (r < 140))

# Precise skin mask
skin_mask = (~is_dark) & (~is_white) & (~is_jeans) & (r > 90) & (r > b + 20) & (g > 50) & (b < 190)

# Authentic Warm Golden-Bronze Métis skin tone (#BF7848)
# R: 191, G: 120, B: 72
arr[skin_mask, 0] = np.clip(arr[skin_mask, 0] * 0.86, 0, 255)
arr[skin_mask, 1] = np.clip(arr[skin_mask, 1] * 1.05, 0, 255)
arr[skin_mask, 2] = np.clip(arr[skin_mask, 2] * 0.85, 0, 255)

mean_skin = [arr[skin_mask, 0].mean(), arr[skin_mask, 1].mean(), arr[skin_mask, 2].mean()]
print(f"Transformed Golden-Bronze Métis Skin Mean RGB: {mean_skin}")

# Fill Arm Swatches in correct Pillow coordinates (y = (1 - v) * h)
cx_l, cy_l = int(0.3655 * w), int((1.0 - 0.8289) * h)
cx_r, cy_r = int(0.7817 * w), int((1.0 - 0.5153) * h)

for cx, cy in [(cx_l, cy_l), (cx_r, cy_r)]:
    arr[cy-250:cy+250, cx-250:cx+250, 0] = mean_skin[0]
    arr[cy-250:cy+250, cx-250:cx+250, 1] = mean_skin[1]
    arr[cy-250:cy+250, cx-250:cx+250, 2] = mean_skin[2]

# Clean dark espresso hair swatch
cx_h, cy_h = int(0.120 * w), int((1.0 - 0.136) * h)
arr[cy_h-200:cy_h+200, cx_h-200:cx_h+200, 0] = 22.0
arr[cy_h-200:cy_h+200, cx_h-200:cy_h+200, 1] = 16.0
arr[cy_h-200:cy_h+200, cx_h-200:cx_h+200, 2] = 12.0

# Clean pure blue denim swatch
cx_d, cy_d = int(0.500 * w), int((1.0 - 0.100) * h)
arr[cy_d-200:cy_d+200, cx_d-200:cx_d+200, 0] = 45.0
arr[cy_d-200:cy_d+200, cx_d-200:cx_d+200, 1] = 85.0
arr[cy_d-200:cy_d+200, cx_d-200:cx_d+200, 2] = 145.0

out_im = Image.fromarray(arr.astype(np.uint8))
out_im.save(OUT_TEX)
print("SUCCESS: 100% Golden-Bronze Métis Texture generated with pristine swatches!")
