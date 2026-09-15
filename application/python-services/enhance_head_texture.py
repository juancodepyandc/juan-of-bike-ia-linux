import cv2
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter

tex_path = "/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/orig_raw_texture_Image_0.png"
tex = Image.open(tex_path).convert("RGB")
w, h = tex.size

z_map = Image.open("/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/uv_z_map.png").convert("L").resize((w, h))

tex_arr = np.array(tex, dtype=np.float32) / 255.0
z_arr = np.array(z_map, dtype=np.float32) / 255.0

# Head mask
head_mask = (z_arr > 0.68).astype(np.float32)

# Convert head RGB to HSV for precise color grading
hsv = cv2.cvtColor((tex_arr * 255.0).astype(np.uint8), cv2.COLOR_RGB2HSV).astype(np.float32)

# Skin detection in HSV:
# Hue 0..25 (Red/Orange/Caramel), Saturation 20..180, Value 80..255
is_skin = (hsv[:, :, 0] < 25) & (hsv[:, :, 1] > 20) & (hsv[:, :, 2] > 70) & (head_mask > 0.5)
is_hair = (hsv[:, :, 2] < 70) & (head_mask > 0.5)

# 1. Warm caramel color grade on skin
# Shift hue slightly towards golden warm orange (+2), increase saturation (+35%), lower lightness to caramel richness (-15%)
hsv[:, :, 0][is_skin] = np.clip(hsv[:, :, 0][is_skin] * 0.95 + 1.5, 0, 179)
hsv[:, :, 1][is_skin] = np.clip(hsv[:, :, 1][is_skin] * 1.45 + 15, 0, 255)
hsv[:, :, 2][is_skin] = np.clip(hsv[:, :, 2][is_skin] * 0.88, 0, 255)

# 2. Deep rich curl contrast on hair
hsv[:, :, 2][is_hair] = np.clip(hsv[:, :, 2][is_hair] * 0.85, 0, 255)

graded_rgb = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2RGB).astype(np.float32) / 255.0

# 3. Add freckles & high-frequency micro-texture on skin
# Procedural subtle freckles and pore texture
np.random.seed(42)
noise = np.random.normal(0, 0.04, (h, w, 1)).astype(np.float32)
# Apply noise only to skin
graded_rgb[is_skin] = np.clip(graded_rgb[is_skin] + noise[is_skin] * 0.35, 0.0, 1.0)

# Smooth blend between head mask and rest of body
head_mask_3d = np.repeat(head_mask[:, :, np.newaxis], 3, axis=2)
# Blur mask slightly to avoid seams
blurred_mask = cv2.GaussianBlur(head_mask, (15, 15), 0)[:, :, np.newaxis]
final_rgb = tex_arr * (1.0 - blurred_mask) + graded_rgb * blurred_mask

out_img = Image.fromarray((np.clip(final_rgb, 0.0, 1.0) * 255.0).astype(np.uint8))
out_tex_path = "/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/enhanced_base_texture_4k.png"
out_img.save(out_tex_path, quality=100)
print(f"Saved enhanced base texture: {out_tex_path}")

