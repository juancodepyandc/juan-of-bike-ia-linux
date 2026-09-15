from PIL import Image, ImageDraw, ImageFont
import os

# Create clean, properly proportioned 4K T-shirt graphics
# Chest Graphic (Front): Focused on upper chest, pure black background
img_front = Image.new("RGBA", (4096, 4096), (18, 18, 18, 255))
draw_f = ImageDraw.Draw(img_front)

# Center of chest is around Y = 1600 (upper half of 4096)
# Load font
try:
    font_vizion = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 360)
    font_sub = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 190)
    font_handle = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 110)
except:
    font_vizion = ImageFont.load_default()
    font_sub = font_vizion
    font_handle = font_vizion

# Draw VIZION (Glitch / Chrome Style on Chest)
# Cyan offset
draw_f.text((2048 - 620 - 18, 1200), "VIZION", fill=(0, 220, 255, 255), font=font_vizion)
# Magenta offset
draw_f.text((2048 - 620 + 18, 1200), "VIZION", fill=(255, 0, 120, 255), font=font_vizion)
# White main
draw_f.text((2048 - 620, 1200), "VIZION", fill=(255, 255, 255, 255), font=font_vizion)

# JUANDIGITS
draw_f.text((2048 - 670, 1620), "JUANDIGITS", fill=(255, 255, 255, 255), font=font_sub)

# Pink/Cyan separator bars
draw_f.rectangle([(2048 - 670, 1860), (2048 + 670, 1876)], fill=(0, 220, 255, 255))
draw_f.rectangle([(2048 - 670, 1886), (2048 + 670, 1900)], fill=(255, 0, 120, 255))

# Social Handle
draw_f.text((2048 - 480, 1950), "@python_viziondigits", fill=(0, 220, 255, 255), font=font_handle)

# Save Front Chest Graphic (No grid extending into jeans, pure solid black shirt)
OUT_FRONT = "/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/solid_tshirt_front_4k.png"
img_front.save(OUT_FRONT)
print(f"Saved clean front chest graphic: {OUT_FRONT}")

# Back Graphic
img_back = Image.new("RGBA", (4096, 4096), (18, 18, 18, 255))
draw_b = ImageDraw.Draw(img_back)

draw_b.text((2048 - 670, 1200), "JUANDIGITS", fill=(255, 255, 255, 255), font=font_sub)

# VIZION
draw_b.text((2048 - 620 - 18, 1460), "VIZION", fill=(0, 220, 255, 255), font=font_vizion)
draw_b.text((2048 - 620 + 18, 1460), "VIZION", fill=(255, 0, 120, 255), font=font_vizion)
draw_b.text((2048 - 620, 1460), "VIZION", fill=(255, 255, 255, 255), font=font_vizion)

# Bars & Handle
draw_b.rectangle([(2048 - 670, 1880), (2048 + 670, 1896)], fill=(255, 0, 120, 255))
draw_b.rectangle([(2048 - 670, 1906), (2048 + 670, 1920)], fill=(0, 220, 255, 255))
draw_b.text((2048 - 480, 1960), "@python_viziondigits", fill=(255, 255, 255, 255), font=font_handle)

OUT_BACK = "/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/solid_tshirt_back_4k.png"
img_back.save(OUT_BACK)
print(f"Saved clean back graphic: {OUT_BACK}")
