import math
from PIL import Image, ImageDraw, ImageFont

def draw_tiktok_icon(draw, x, y, size):
    s = size
    for off_x, off_y, col in [(int(s*0.09), int(-s*0.05), (255, 0, 95, 255)), 
                              (int(-s*0.09), int(s*0.05), (0, 245, 255, 255)), 
                              (0, 0, (255, 255, 255, 255))]:
        draw.arc([x + s*0.14 + off_x, y + s*0.34 + off_y, x + s*0.70 + off_x, y + s*0.90 + off_y], 
                 start=0, end=360, fill=col, width=max(16, int(s*0.18)))
        draw.rectangle([x + s*0.50 + off_x, y + s*0.05 + off_y, x + s*0.68 + off_x, y + s*0.65 + off_y], fill=col)
        draw.arc([x + s*0.50 + off_x, y + s*0.05 + off_y, x + s*1.02 + off_x, y + s*0.58 + off_y], 
                 start=270, end=360, fill=col, width=max(16, int(s*0.18)))

def draw_instagram_icon(img, draw, x, y, size):
    s = size
    grad = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    gdraw = ImageDraw.Draw(grad)
    for i in range(s):
        t = i / s
        r = int(145 + (255 - 145) * t)
        g = int(40 + (70 - 40) * t)
        b = int(200 + (240 - 200) * (1.0 - t))
        gdraw.line([(0, i), (s, i)], fill=(r, g, b, 255))
    
    mask = Image.new("L", (s, s), 0)
    mdraw = ImageDraw.Draw(mask)
    mdraw.rounded_rectangle([0, 0, s, s], radius=int(s*0.28), fill=255)
    img.paste(grad, (x, y), mask)

    draw.rounded_rectangle([x + s*0.08, y + s*0.08, x + s*0.92, y + s*0.92], 
                           radius=int(s*0.24), outline=(255, 255, 255, 255), width=max(14, int(s*0.13)))
    draw.ellipse([x + s*0.26, y + s*0.26, x + s*0.74, y + s*0.74], 
                 outline=(255, 255, 255, 255), width=max(14, int(s*0.13)))
    draw.ellipse([x + s*0.73, y + s*0.17, x + s*0.85, y + s*0.29], fill=(255, 255, 255, 255))


# =========================================================================
# 1. FRONT ARTWORK : ULTRA-BOLD, CLEAN & HIGHLY VISIBLE (CYBER CYAN/MAGENTA)
# =========================================================================
def create_front_art(out_path):
    W, H = 4096, 4096
    cx = W // 2
    
    base = Image.new("RGBA", (W, H), (8, 9, 14, 255))
    draw = ImageDraw.Draw(base)

    font_bold = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"

    # 1. VIZION (820pt)
    font_v = ImageFont.truetype(font_bold, 820)
    txt_v = "VIZION"
    bb_v = draw.textbbox((0, 0), txt_v, font=font_v)
    tw_v = bb_v[2] - bb_v[0]
    th_v = bb_v[3] - bb_v[1]
    vx = cx - tw_v // 2
    vy = 520

    for off, col in [(-35, (0, 245, 255, 255)), (35, (255, 0, 110, 255)), (-18, (0, 180, 255, 255)), (18, (255, 0, 180, 255))]:
        draw.text((vx + off, vy), txt_v, font=font_v, fill=col)
    
    draw.text((vx, vy - 10), txt_v, font=font_v, fill=(0, 0, 0, 255))
    draw.text((vx, vy), txt_v, font=font_v, fill=(255, 255, 255, 255))

    # 2. JUANDIGITS (420pt)
    font_j = ImageFont.truetype(font_bold, 420)
    txt_j = "JUANDIGITS"
    bb_j = draw.textbbox((0, 0), txt_j, font=font_j)
    tw_j = bb_j[2] - bb_j[0]
    th_j = bb_j[3] - bb_j[1]
    jy = vy + th_v + 120

    draw.text((cx - tw_j // 2 + 6, jy + 6), txt_j, font=font_j, fill=(0, 245, 255, 220))
    draw.text((cx - tw_j // 2, jy), txt_j, font=font_j, fill=(255, 255, 255, 255))

    # Glowing Neon Accent Bar
    bar_y = jy + 440
    draw.line([(cx - 850, bar_y), (cx + 850, bar_y)], fill=(0, 245, 255, 255), width=22)
    draw.line([(cx - 450, bar_y + 26), (cx + 450, bar_y + 26)], fill=(255, 0, 110, 255), width=12)

    # 3. SOCIAL ICONS (TIKTOK & INSTAGRAM - 280px)
    icon_sz = 280
    total_ic_w = icon_sz + 70 + icon_sz
    ic_x = cx - total_ic_w // 2
    ic_y = bar_y + 120
    draw_tiktok_icon(draw, ic_x, ic_y, icon_sz)
    draw_instagram_icon(base, draw, ic_x + icon_sz + 70, ic_y, icon_sz)

    # 4. @python_viziondigits (240pt)
    font_soc = ImageFont.truetype(font_bold, 240)
    txt_soc = "@python_viziondigits"
    bb_s = draw.textbbox((0, 0), txt_soc, font=font_soc)
    tw_s = bb_s[2] - bb_s[0]
    sy = ic_y + icon_sz + 80

    for dx, dy in [(-6,0),(6,0),(0,-6),(0,6),(-4,-4),(4,4),(-4,4),(4,-4)]:
        draw.text((cx - tw_s // 2 + dx, sy + dy), txt_soc, font=font_soc, fill=(0, 245, 255, 255))
    draw.text((cx - tw_s // 2, sy), txt_soc, font=font_soc, fill=(255, 255, 255, 255))

    base_y = sy + 320
    draw.line([(cx - 950, base_y), (cx + 950, base_y)], fill=(0, 245, 255, 255), width=20)
    draw.line([(cx - 450, base_y + 24), (cx + 450, base_y + 24)], fill=(255, 0, 110, 255), width=10)

    base.save(out_path, quality=100)
    print(f"Saved Front Art: {out_path}")


# =========================================================================
# 2. BACK ARTWORK : ULTRA-BOLD STREETWEAR (JUANDIGITS + VIZION XXL)
# =========================================================================
def create_back_art(out_path):
    W, H = 4096, 4096
    cx = W // 2
    
    base = Image.new("RGBA", (W, H), (8, 9, 14, 255))
    draw = ImageDraw.Draw(base)

    font_bold = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"

    # 1. JUANDIGITS (480pt)
    font_jb = ImageFont.truetype(font_bold, 480)
    txt_jb = "JUANDIGITS"
    bb_jb = draw.textbbox((0, 0), txt_jb, font=font_jb)
    tw_jb = bb_jb[2] - bb_jb[0]
    th_jb = bb_jb[3] - bb_jb[1]
    jx = cx - tw_jb // 2
    jy = 650

    draw.text((jx - 30, jy), txt_jb, font=font_jb, fill=(255, 0, 110, 240))
    draw.text((jx + 30, jy), txt_jb, font=font_jb, fill=(0, 245, 255, 240))
    draw.text((jx, jy - 10), txt_jb, font=font_jb, fill=(0, 0, 0, 255))
    draw.text((jx, jy), txt_jb, font=font_jb, fill=(255, 255, 255, 255))

    # Sleek Divider Bar
    bar1_y = jy + th_jb + 100
    draw.line([(cx - 900, bar1_y), (cx + 900, bar1_y)], fill=(255, 215, 0, 255), width=22)
    draw.line([(cx - 450, bar1_y + 26), (cx + 450, bar1_y + 26)], fill=(255, 0, 110, 255), width=12)

    # 2. VIZION (820pt)
    font_vb = ImageFont.truetype(font_bold, 820)
    txt_vb = "VIZION"
    bb_vb = draw.textbbox((0, 0), txt_vb, font=font_vb)
    tw_vb = bb_vb[2] - bb_vb[0]
    th_vb = bb_vb[3] - bb_vb[1]
    vy_b = bar1_y + 100

    for off, col in [(-35, (255, 0, 110, 255)), (35, (255, 215, 0, 255)), (-18, (255, 0, 180, 255)), (18, (0, 245, 255, 255))]:
        draw.text((cx - tw_vb // 2 + off, vy_b), txt_vb, font=font_vb, fill=col)
    
    draw.text((cx - tw_vb // 2, vy_b - 10), txt_vb, font=font_vb, fill=(0, 0, 0, 255))
    draw.text((cx - tw_vb // 2, vy_b), txt_vb, font=font_vb, fill=(255, 255, 255, 255))

    # Sleek Divider Bar 2
    bar2_y = vy_b + th_vb + 100
    draw.line([(cx - 850, bar2_y), (cx + 850, bar2_y)], fill=(0, 245, 255, 255), width=22)
    draw.line([(cx - 400, bar2_y + 26), (cx + 400, bar2_y + 26)], fill=(255, 0, 110, 255), width=12)

    # 3. SOCIAL ICONS (TIKTOK & INSTAGRAM - 280px)
    icon_sz = 280
    total_ic_w = icon_sz + 70 + icon_sz
    ic_x = cx - total_ic_w // 2
    ic_y = bar2_y + 100
    draw_tiktok_icon(draw, ic_x, ic_y, icon_sz)
    draw_instagram_icon(base, draw, ic_x + icon_sz + 70, ic_y, icon_sz)

    # 4. @python_viziondigits (240pt)
    font_soc_back = ImageFont.truetype(font_bold, 240)
    txt_sb = "@python_viziondigits"
    bb_sb = draw.textbbox((0, 0), txt_sb, font=font_soc_back)
    tw_sb = bb_sb[2] - bb_sb[0]
    sy_b = ic_y + icon_sz + 80

    for dx, dy in [(-6,0),(6,0),(0,-6),(0,6),(-4,-4),(4,4),(-4,4),(4,-4)]:
        draw.text((cx - tw_sb // 2 + dx, sy_b + dy), txt_sb, font=font_soc_back, fill=(255, 0, 110, 255))
    draw.text((cx - tw_sb // 2, sy_b), txt_sb, font=font_soc_back, fill=(255, 255, 255, 255))

    bot_y = sy_b + 320
    draw.line([(cx - 950, bot_y), (cx + 950, bot_y)], fill=(255, 215, 0, 255), width=20)
    draw.line([(cx - 450, bot_y + 24), (cx + 450, bot_y + 24)], fill=(0, 245, 255, 255), width=10)

    base.save(out_path, quality=100)
    print(f"Saved Back Art: {out_path}")

create_front_art("/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/solid_tshirt_front_4k.png")
create_back_art("/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/solid_tshirt_back_4k.png")
