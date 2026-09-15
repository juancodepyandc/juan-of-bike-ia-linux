from PIL import Image
import numpy as np

im = Image.open("/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/orig_raw_texture_Image_0.png").convert("RGB")
w, h = im.size
arr = np.array(im, dtype=np.float32)

r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]

# Let's inspect where skin is:
skin_mask = (r > 120) & (r > b + 30) & (g > 60) & (g < 180) & (b < 160)
print(f"Skin pixels in raw texture: {np.sum(skin_mask)}")

# Let's see what happens if we apply a clean, pure warm golden-amber hue shift ONLY to skin pixels:
# In raw texture, skin pixels have: mean R=221, G=116, B=86 (overly red/salmon)
# To turn them into authentic warm golden-caramel métis skin:
# Target: R=205, G=142, B=96 (Golden-Amber Caramel Métis)
arr_new = arr.copy()

# For skin pixels:
# Multiply G by 1.25, B by 1.15, R by 0.92
arr_new[skin_mask, 0] = np.clip(arr[skin_mask, 0] * 0.92, 0, 255)
arr_new[skin_mask, 1] = np.clip(arr[skin_mask, 1] * 1.26, 0, 255)
arr_new[skin_mask, 2] = np.clip(arr[skin_mask, 2] * 1.15, 0, 255)

mean_new = [arr_new[skin_mask, 0].mean(), arr_new[skin_mask, 1].mean(), arr_new[skin_mask, 2].mean()]
print(f"New skin mean RGB: {mean_new}")

# Set arm swatches to exact new skin mean:
for cx, cy in [(int(0.3655 * w), int((1 - 0.8289) * h)), (int(0.7817 * w), int((1 - 0.5153) * h))]:
    # In Pillow coordinates, Y is from top, so v=0.8289 in UV is y = int((1 - 0.8289) * h)
    arr_new[cy-200:cy+200, cx-200:cx+200, 0] = mean_new[0]
    arr_new[cy-200:cy+200, cx-200:cx+200, 1] = mean_new[1]
    arr_new[cy-200:cy+200, cx-200:cx+200, 2] = mean_new[2]

# Also in Blender UV coordinates (where v=0 is bottom):
# If Blender accesses the texture directly:
# Blender image UV (u, v) maps to Pillow image pixel (int(u * w), int((1 - v) * h))!
# So for u=0.3655, v=0.8289:
# Pillow pixel is x=int(0.3655*w), y=int((1 - 0.8289)*h) = int(0.1711*h)!
