from PIL import Image, ImageDraw
import numpy as np

# 1. Soften ears in clean_dilated_texture_4k.png
TEX_PATH = "/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/clean_dilated_texture_4k.png"
im = Image.open(TEX_PATH).convert("RGB")
arr = np.array(im, dtype=np.float32)
h, w, _ = arr.shape

r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
is_upper = np.repeat(np.arange(h)[:, None] < int(0.70 * h), w, axis=1)

# Any strong red in upper texture gets blended to warm golden métis (#D28A58)
is_red_ear = is_upper & (r > 150) & (g < 120) & (r > g + 40)
arr[is_red_ear, 0] = 205.0
arr[is_red_ear, 1] = 138.0
arr[is_red_ear, 2] = 88.0

im_clean = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
im_clean.save(TEX_PATH)
print("SUCCESS: Softened ear redness!")

# 2. Add Cyber Matrix Grid to Front T-Shirt 4K
FRONT_PATH = "/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/solid_tshirt_front_4k.png"
front_im = Image.open(FRONT_PATH).convert("RGBA")
draw_f = ImageDraw.Draw(front_im)
fw, fh = front_im.size

# Draw cyber matrix grid from y=2400 to y=3800
grid_color = (0, 190, 235, 220) # Bright Cyan
dot_color = (0, 230, 255, 255)

# Horizontal and vertical circuit traces
y_start = 2400
for y in range(y_start, 3800, 120):
    draw_f.line([(400, y), (fw - 400, y)], fill=(0, 140, 180, 140), width=4)
for x in range(500, fw - 400, 160):
    draw_f.line([(x, y_start), (x, 3800)], fill=(0, 140, 180, 140), width=4)

# Circuit nodes and diagonal traces
for i in range(12):
    cx = 600 + (i * 240) % (fw - 1200)
    cy = y_start + 100 + (i * 110) % 1200
    draw_f.ellipse([cx-12, cy-12, cx+12, cy+12], fill=dot_color)
    draw_f.line([(cx, cy), (cx + 80, cy - 60), (cx + 200, cy - 60)], fill=grid_color, width=6)
    draw_f.ellipse([cx+200-10, cy-60-10, cx+200+10, cy-60+10], fill=dot_color)

front_im.save(FRONT_PATH)
print("SUCCESS: Updated Front T-Shirt with Cyber Matrix!")

# 3. Add Cyber Matrix Grid to Back T-Shirt 4K
BACK_PATH = "/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/solid_tshirt_back_4k.png"
back_im = Image.open(BACK_PATH).convert("RGBA")
draw_b = ImageDraw.Draw(back_im)
for y in range(y_start, 3800, 120):
    draw_b.line([(400, y), (fw - 400, y)], fill=(0, 140, 180, 140), width=4)
for x in range(500, fw - 400, 160):
    draw_b.line([(x, y_start), (x, 3800)], fill=(0, 140, 180, 140), width=4)
for i in range(12):
    cx = 600 + (i * 240) % (fw - 1200)
    cy = y_start + 100 + (i * 110) % 1200
    draw_b.ellipse([cx-12, cy-12, cx+12, cy+12], fill=dot_color)
    draw_b.line([(cx, cy), (cx - 80, cy - 60), (cx - 200, cy - 60)], fill=grid_color, width=6)
    draw_b.ellipse([cx-200-10, cy-60-10, cx-200+10, cy-60+10], fill=dot_color)

back_im.save(BACK_PATH)
print("SUCCESS: Updated Back T-Shirt with Cyber Matrix!")
