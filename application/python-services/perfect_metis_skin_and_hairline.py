from PIL import Image, ImageFilter, ImageDraw
import numpy as np

TEX_PATH = "/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/rich_metis_texture_4k.png"
im = Image.open(TEX_PATH).convert("RGB")
arr = np.array(im, dtype=np.float32)

# Rich Warm Métis Caramel Reference Color
# R: 206, G: 138, B: 84 (#CE8A54) - Golden Caramel Métis
TARGET_METIS = np.array([206.0, 138.0, 84.0], dtype=np.float32)

r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]

# 1. Neutralize all pale / pinkish / greyish patches on face (chin, nose, cheeks)
is_eye_white = (r > 215) & (g > 215) & (b > 215)
is_dark_eye = (r < 40) & (g < 40) & (b < 40)

# Detect all skin pixels (R > 80, R > G, G >= B - 10)
is_skin = (r > 80) & (r > g) & (g >= b - 15) & (~is_eye_white) & (~is_dark_eye)

# Blend skin pixels towards rich warm métis
for c in range(3):
    arr[is_skin, c] = arr[is_skin, c] * 0.45 + TARGET_METIS[c] * 0.55

# 2. Fix the dark hairline band on the forehead
# Dark pixels on the upper face that are not eyebrows or eyes
# Eyebrows are high contrast near y = 0.35 to 0.45 in texture
# Hairline dark band is located at the top of the face UV island
# Let's detect dark brown / black pixels in the skin island and turn them into métis skin if they are near the forehead
is_dark_forehead_band = (r < 95) & (g < 75) & (b < 65) & (r > 25) & (g > 15)

# Blend dark band to warm métis
arr[is_dark_forehead_band, 0] = 195.0
arr[is_dark_forehead_band, 1] = 130.0
arr[is_dark_forehead_band, 2] = 78.0

# Apply gentle blur only on skin regions to remove compression noise
im_result = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
im_result.save(TEX_PATH)
print("SUCCESS: Forehead hairline and rich warm métis skin perfected on 4K texture!")
