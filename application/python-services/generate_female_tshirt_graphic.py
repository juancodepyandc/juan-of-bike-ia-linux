from PIL import Image, ImageDraw, ImageFont
import numpy as np
import math

W, H = 2048, 2048
img = Image.new("RGBA", (W, H), (15, 12, 20, 255))
draw = ImageDraw.Draw(img)

# Cyberpunk / Synthwave Sunset Geometric Grid
# Background gradient
for y in range(H):
    t = y / H
    r = int(18 + 40 * math.sin(t * math.pi))
    g = int(12 + 15 * (1 - t))
    b = int(28 + 55 * t)
    draw.line([(0, y), (W, y)], fill=(r, g, b, 255))

# Neon Geometric Hexagon / Triangle Wave Matrix
cx, cy = W // 2, int(H * 0.62)
for radius in range(120, 750, 90):
    points = []
    for a in range(0, 360, 60):
        rad = math.radians(a)
        px = cx + radius * math.cos(rad)
        py = cy + radius * 0.65 * math.sin(rad)
        points.append((px, py))
    # Draw glowing neon polygon
    for i in range(len(points)):
        p1 = points[i]
        p2 = points[(i + 1) % len(points)]
        draw.line([p1, p2], fill=(255, 60, 160, 200), width=6)
        draw.line([p1, (cx, cy)], fill=(0, 220, 255, 120), width=3)

# Glowing Sunset Sun Disk in Background
sun_rad = 320
sun_cy = int(H * 0.44)
for r in range(sun_rad, 0, -8):
    t = 1.0 - (r / sun_rad)
    cr = int(255)
    cg = int(60 + 190 * t)
    cb = int(120 * (1 - t))
    draw.ellipse([cx - r, sun_cy - r, cx + r, sun_cy + r], fill=(cr, cg, cb, 255))

# Sun horizontal slice blinds
for sy in range(sun_cy - sun_rad, sun_cy + sun_rad, 36):
    slice_h = int(6 + 18 * ((sy - (sun_cy - sun_rad)) / (2 * sun_rad)))
    draw.rectangle([cx - sun_rad - 20, sy, cx + sun_rad + 20, sy + slice_h], fill=(20, 15, 30, 255))

# Typography: "AURORA AI" & "CYBER CHIC"
try:
    font_main = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 160)
    font_sub = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 68)
    font_tag = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 52)
except Exception:
    font_main = font_sub = font_tag = ImageFont.load_default()

def draw_glow_text(text, font, pos, base_color, glow_color, glow_size=12):
    x, y = pos
    for dx in range(-glow_size, glow_size + 1, 3):
        for dy in range(-glow_size, glow_size + 1, 3):
            if dx*dx + dy*dy <= glow_size*glow_size:
                draw.text((x + dx, y + dy), text, font=font, fill=glow_color)
    draw.text((x, y), text, font=font, fill=base_color)

# Draw AURORA
bbox_a = draw.textbbox((0, 0), "AURORA", font=font_main)
tw_a = bbox_a[2] - bbox_a[0]
draw_glow_text("AURORA", font_main, ((W - tw_a) // 2, int(H * 0.18)), (255, 255, 255, 255), (0, 230, 255, 180), glow_size=16)

# Draw AI (Chrome Gradient look)
bbox_ai = draw.textbbox((0, 0), "CREATIVE AI", font=font_sub)
tw_ai = bbox_ai[2] - bbox_ai[0]
draw_glow_text("CREATIVE AI", font_sub, ((W - tw_ai) // 2, int(H * 0.29)), (255, 230, 80, 255), (255, 40, 160, 200), glow_size=12)

# Draw Bottom Tagline
bbox_tag = draw.textbbox((0, 0), "FUTURE OF 3D SYNTHESIS", font=font_tag)
tw_tag = bbox_tag[2] - bbox_tag[0]
draw_glow_text("FUTURE OF 3D SYNTHESIS", font_tag, ((W - tw_tag) // 2, int(H * 0.86)), (180, 245, 255, 255), (20, 120, 255, 160), glow_size=8)

OUT_PATH = "/home/juan/AuroraIA/application/output/3d/avatar_femelle_tshirt_graphic_4k.png"
img.save(OUT_PATH)
print(f"Generated female graphic t-shirt design: {OUT_PATH}")
