import numpy as np
from PIL import Image

ORIG_TEX = "/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/orig_raw_texture_Image_0.png"
OUT_TEX = "/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/enhanced_base_texture_4k.png"

im = Image.open(ORIG_TEX).convert("RGB")
arr = np.array(im, dtype=np.float32)

r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]

# Exclusions
is_dark = (r < 65) & (g < 65) & (b < 65)
is_white = (r > 210) & (g > 210) & (b > 210) & (abs(r - g) < 20) & (abs(r - b) < 20)
is_jeans = (b > r + 5) | ((b > 90) & (r < 140))

# Precise skin mask
skin_mask = (~is_dark) & (~is_white) & (~is_jeans) & (r > 90) & (r > b + 20) & (g > 50) & (b < 190)

# Golden-amber métis transformation
arr[skin_mask, 0] = np.clip(arr[skin_mask, 0] * 0.96, 0, 255)
arr[skin_mask, 1] = np.clip(arr[skin_mask, 1] * 1.36, 0, 255)
arr[skin_mask, 2] = np.clip(arr[skin_mask, 2] * 1.28, 0, 255)

mean_skin = [arr[skin_mask, 0].mean(), arr[skin_mask, 1].mean(), arr[skin_mask, 2].mean()]
print(f"Transformed Skin Mean RGB: {mean_skin}")

# Fill Arm Swatches with matching mean skin
w, h = im.size
swatch_col = [mean_skin[0], mean_skin[1], mean_skin[2]]
for cx, cy in [(int(0.3655 * w), int(0.8289 * h)), (int(0.7817 * w), int(0.5153 * h))]:
    arr[cy-250:cy+250, cx-250:cx+250, 0] = swatch_col[0]
    arr[cy-250:cy+250, cx-250:cx+250, 1] = swatch_col[1]
    arr[cy-250:cy+250, cx-250:cx+250, 2] = swatch_col[2]

out_im = Image.fromarray(arr.astype(np.uint8))
out_im.save(OUT_TEX)
print("SUCCESS: Saved perfect métis 4K base texture!")
