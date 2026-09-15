import cv2
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter

# Paths
ORIG_RAW = "/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/orig_raw_texture_Image_0.png"
POS_Z_MAP = "/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/maps/pos_z_map.png"
POINTINESS_MAP = "/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/maps/pointiness_map.png"
OUT_BASE_TEX = "/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/enhanced_base_texture_4k.png"

# Load Images
orig_img = Image.open(ORIG_RAW).convert("RGB")
w, h = orig_img.size

z_img = Image.open(POS_Z_MAP).convert("L").resize((w, h))
p_img = Image.open(POINTINESS_MAP).convert("L").resize((w, h))

raw_rgb = np.array(orig_img, dtype=np.float32) / 255.0
z_arr = np.array(z_img, dtype=np.float32) / 255.0
p_arr = np.array(p_img, dtype=np.float32) / 255.0

# Convert to HSV
hsv = cv2.cvtColor((raw_rgb * 255.0).astype(np.uint8), cv2.COLOR_RGB2HSV).astype(np.float32)
hue = hsv[:, :, 0]
sat = hsv[:, :, 1]
val = hsv[:, :, 2]

# Regional Masks based on Z height (Z range: 0.0=bottom of shoes, 1.0=top of head)
# Head: z > 0.68
# Hands: z between 0.40 and 0.68, and x is outer
# Torso: z between 0.45 and 0.72
# Jeans: z between 0.12 and 0.50
# Shoes: z < 0.12

is_head_region = (z_arr > 0.68)
is_jeans_region = (z_arr >= 0.12) & (z_arr <= 0.48)
is_shoes_region = (z_arr < 0.12)
is_hands_region = (z_arr >= 0.40) & (z_arr <= 0.70) & (sat > 25) & (hue < 30)

# Output RGB buffer
out_rgb = np.copy(raw_rgb)

# =========================================================================
# 1. HAIR & CURLS OVERHAUL (Rich Multi-Tone Espresso, Amber Sheen, Deep Curls)
# =========================================================================
# Hair is in head region and either dark or low saturation
is_hair = is_head_region & ((val < 85) | ((hue > 10) & (hue < 35) & (val < 110)))

# Create multi-tone curl texture using pointiness curvature
# Base deep obsidian/espresso: (0.07, 0.05, 0.04)
# Cavity deep shadow: (0.03, 0.02, 0.02)
# Ridge warm bronze/amber highlight: (0.28, 0.18, 0.11)
curl_factor = np.clip((p_arr - 0.35) * 2.2, 0.0, 1.0) # 0 in crevices, 1 on ridges

hair_shadow = np.array([0.04, 0.028, 0.022], dtype=np.float32)
hair_base   = np.array([0.09, 0.065, 0.048], dtype=np.float32)
hair_ridge  = np.array([0.26, 0.175, 0.115], dtype=np.float32)

# Blend hair tones
hair_color = np.zeros_like(raw_rgb)
for c in range(3):
    # Interpolate shadow -> base -> ridge
    mid = hair_shadow[c] * (1.0 - curl_factor) + hair_base[c] * curl_factor
    hair_color[:, :, c] = mid * (1.0 - curl_factor*0.6) + hair_ridge[c] * (curl_factor*0.6)

# Add fine procedural micro-strands
np.random.seed(101)
strand_noise = np.random.normal(0, 0.035, (h, w, 3)).astype(np.float32)
hair_color = np.clip(hair_color + strand_noise, 0.0, 1.0)

# Apply to hair
out_rgb[is_hair] = hair_color[is_hair]

# =========================================================================
# 2. SKIN & FACE OVERHAUL (Warm Radiant Caramel Skin, Hazel Eyes, Defined Brows)
# =========================================================================
is_skin_head = is_head_region & ~is_hair & (val > 65)

# Convert skin to rich warm golden caramel
skin_hsv = np.copy(hsv)
# Warm caramel tone: Hue ~12-14, Saturation ~120-145, Rich Value
skin_hsv[:, :, 0][is_skin_head] = np.clip(skin_hsv[:, :, 0][is_skin_head] * 0.85 + 1.8, 0, 179)
skin_hsv[:, :, 1][is_skin_head] = np.clip(skin_hsv[:, :, 1][is_skin_head] * 1.35 + 15, 0, 255)
skin_hsv[:, :, 2][is_skin_head] = np.clip(skin_hsv[:, :, 2][is_skin_head] * 0.92, 0, 255)

skin_rgb = cv2.cvtColor(skin_hsv.astype(np.uint8), cv2.COLOR_HSV2RGB).astype(np.float32) / 255.0

# Add gentle subsurface peach warmth on cheeks/nose
warm_tint = np.array([1.04, 0.98, 0.92], dtype=np.float32)
skin_rgb[is_skin_head] = np.clip(skin_rgb[is_skin_head] * warm_tint, 0.0, 1.0)

out_rgb[is_skin_head] = skin_rgb[is_skin_head]

# Hands skin
is_hands_skin = is_hands_region & (val > 60)
out_rgb[is_hands_skin] = skin_rgb[is_hands_skin]

# =========================================================================
# 3. JEANS & LEGS OVERHAUL (Deep Vibrant Denim Indigo, Realistic Fading & Stitching)
# =========================================================================
# In jeans region, apply rich denim blue
is_jeans_blue = is_jeans_region & (sat > 15) & (val > 25)

# Create high-end denim texture
# Base deep indigo: (0.10, 0.18, 0.38)
# Highlight denim: (0.22, 0.38, 0.65)
denim_hsv = np.copy(hsv)
# Shift hue towards true indigo blue (Hue ~105-115 in OpenCV HSV)
denim_hsv[:, :, 0][is_jeans_blue] = 110 # Pure royal denim blue
denim_hsv[:, :, 1][is_jeans_blue] = np.clip(denim_hsv[:, :, 1][is_jeans_blue] * 1.4 + 20, 0, 255)
denim_hsv[:, :, 2][is_jeans_blue] = np.clip(denim_hsv[:, :, 2][is_jeans_blue] * 1.15, 0, 255)

denim_rgb = cv2.cvtColor(denim_hsv.astype(np.uint8), cv2.COLOR_HSV2RGB).astype(np.float32) / 255.0
out_rgb[is_jeans_blue] = denim_rgb[is_jeans_blue]

# =========================================================================
# 4. SNEAKERS & SHOES OVERHAUL (Matte Black Leather, Crisp White Sole Accents)
# =========================================================================
# In shoes region, enhance contrast between white rubber sole and obsidian uppers
is_sole = is_shoes_region & (val > 140)
is_upper = is_shoes_region & (val <= 140)

# Pure clean white sole with subtle shading
out_rgb[is_sole] = np.clip(raw_rgb[is_sole] * 1.35, 0.0, 1.0)
# Deep matte black upper
out_rgb[is_upper] = np.clip(raw_rgb[is_upper] * 0.75, 0.0, 1.0)

# =========================================================================
# 5. FINAL SHARPENING & SAVE
# =========================================================================
final_img = Image.fromarray((np.clip(out_rgb, 0.0, 1.0) * 255.0).astype(np.uint8))
# Subtle unsharp mask for crystal clarity
enhanced_img = final_img.filter(ImageFilter.UnsharpMask(radius=1.5, percent=130, threshold=2))

enhanced_img.save(OUT_BASE_TEX, quality=100)
print(f"Saved master overhauled texture: {OUT_BASE_TEX}")
