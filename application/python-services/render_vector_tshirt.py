import math
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

def draw_tiktok_icon(draw, x, y, size):
    s = size
    # Draw red offset
    draw.arc([x + s*0.2 + 5, y + s*0.4, x + s*0.6 + 5, y + s*0.8], start=0, end=360, fill=(255, 0, 85, 255), width=int(s*0.12))
    draw.rectangle([x + s*0.5 + 5, y + s*0.1, x + s*0.62 + 5, y + s*0.6], fill=(255, 0, 85, 255))
    draw.arc([x + s*0.5 + 5, y + s*0.1, x + s*0.9 + 5, y + s*0.5], start=270, end=360, fill=(255, 0, 85, 255), width=int(s*0.12))
    
    # Draw cyan offset
    draw.arc([x + s*0.2 - 5, y + s*0.4, x + s*0.6 - 5, y + s*0.8], start=0, end=360, fill=(0, 240, 255, 255), width=int(s*0.12))
    draw.rectangle([x + s*0.5 - 5, y + s*0.1, x + s*0.62 - 5, y + s*0.6], fill=(0, 240, 255, 255))
    draw.arc([x + s*0.5 - 5, y + s*0.1, x + s*0.9 - 5, y + s*0.5], start=270, end=360, fill=(0, 240, 255, 255), width=int(s*0.12))

    # Draw white main
    draw.arc([x + s*0.2, y + s*0.4, x + s*0.6, y + s*0.8], start=0, end=360, fill=(255, 255, 255, 255), width=int(s*0.12))
    draw.rectangle([x + s*0.5, y + s*0.1, x + s*0.62, y + s*0.6], fill=(255, 255, 255, 255))
    draw.arc([x + s*0.5, y + s*0.1, x + s*0.9, y + s*0.5], start=270, end=360, fill=(255, 255, 255, 255), width=int(s*0.12))

def draw_instagram_icon(img, draw, x, y, size):
    s = size
    grad = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    gdraw = ImageDraw.Draw(grad)
    for i in range(s):
        r = int(131 + (253 - 131) * (i / s))
        g = int(58 + (29 - 58) * (i / s))
        b = int(180 + (252 - 180) * (i / s))
        gdraw.line([(0, i), (s, i)], fill=(r, g, b, 255))
    
    mask = Image.new("L", (s, s), 0)
    mdraw = ImageDraw.Draw(mask)
    mdraw.rounded_rectangle([0, 0, s, s], radius=int(s*0.25), fill=255)
    img.paste(grad, (x, y), mask)

    draw.rounded_rectangle([x + s*0.18, y + s*0.18, x + s*0.82, y + s*0.82], radius=int(s*0.18), outline=(255, 255, 255, 255), width=int(s*0.07))
    draw.ellipse([x + s*0.35, y + s*0.35, x + s*0.65, y + s*0.65], outline=(255, 255, 255, 255), width=int(s*0.07))
    draw.ellipse([x + s*0.68, y + s*0.26, x + s*0.75, y + s*0.33], fill=(255, 255, 255, 255))


def render_front_tshirt_4k(out_path):
    W, H = 4096, 4096
    img = Image.new("RGBA", (W, H), (12, 12, 14, 255))
    draw = ImageDraw.Draw(img)

    font_vizion = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", 360)
    font_sub = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", 170)
    font_social = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", 120)
    font_chip = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", 100)

    cx = W // 2

    # 1. VIZION
    txt_v = "VIZION"
    bbox_v = draw.textbbox((0, 0), txt_v, font=font_vizion)
    tw_v = bbox_v[2] - bbox_v[0]
    vx = cx - tw_v // 2
    vy = 360

    draw.text((vx - 8, vy), txt_v, font=font_vizion, fill=(0, 240, 255, 255))
    draw.text((vx + 8, vy), txt_v, font=font_vizion, fill=(255, 0, 110, 255))
    draw.text((vx, vy), txt_v, font=font_vizion, fill=(255, 255, 255, 255))

    # 2. juandigits
    txt_j = "juandigits"
    bbox_j = draw.textbbox((0, 0), txt_j, font=font_sub)
    tw_j = bbox_j[2] - bbox_j[0]
    draw.text((cx - tw_j // 2, vy + 380), txt_j, font=font_sub, fill=(245, 245, 245, 255))

    # 3. Social Handles: TikTok & Instagram on a single stylish line or 2 stacked clean lines
    sy = vy + 620
    icon_s = 130
    
    # TikTok row
    tx = cx - 850
    draw_tiktok_icon(draw, tx, sy, icon_s)
    draw.text((tx + icon_s + 40, sy + 15), "python_viziondigits", font=font_social, fill=(255, 255, 255, 255))

    # Instagram row
    sy2 = sy + 175
    draw_instagram_icon(img, draw, tx, sy2, icon_s)
    draw.text((tx + icon_s + 40, sy2 + 15), "python_viziondigits", font=font_social, fill=(255, 255, 255, 255))

    # 4. Electronic PCB Circuit Board Matrix (Cyan glowing traces)
    cy_top = sy2 + 300
    cyan_glow = (0, 229, 255, 255)
    cyan_bright = (180, 250, 255, 255)
    
    gw = 3600
    gx0 = cx - gw // 2
    gx1 = cx + gw // 2
    gy1 = H - 150

    # Vertical bus lines
    for i in range(21):
        lx = gx0 + i * (gw // 20)
        draw.line([(lx, cy_top + (i%5)*35), (lx, gy1)], fill=cyan_glow, width=12)
        draw.ellipse([lx - 15, cy_top + (i%5)*35 - 15, lx + 15, cy_top + (i%5)*35 + 15], fill=cyan_bright)
        draw.ellipse([lx - 15, gy1 - 15, lx + 15, gy1 + 15], fill=cyan_bright)

    # 45-degree circuit tracks
    for k in range(9):
        y_k = cy_top + 100 + k * 160
        draw.line([(gx0 + 100, y_k), (cx - 450, y_k + 180), (cx + 450, y_k + 180), (gx1 - 100, y_k)], fill=cyan_glow, width=14)

    # Two glowing central chip text boxes
    box_w, box_h = 2200, 180
    bx0 = cx - box_w // 2
    by1 = cy_top + 450
    by2 = by1 + 250

    for by, label in [(by1, "python_viziondigits"), (by2, "python_viziondigits")]:
        draw.rounded_rectangle([bx0, by, bx0 + box_w, by + box_h], radius=25, outline=cyan_glow, width=16)
        draw.rounded_rectangle([bx0 + 8, by + 8, bx0 + box_w - 8, by + box_h - 8], radius=20, outline=cyan_bright, width=6)
        
        tb = draw.textbbox((0, 0), label, font=font_chip)
        tw = tb[2] - tb[0]
        th = tb[3] - tb[1]
        draw.text((cx - tw // 2, by + (box_h - th) // 2 - 10), label, font=font_chip, fill=(0, 245, 255, 255))
        for pin_y in [by + 35, by + 90, by + 145]:
            draw.line([(bx0 - 120, pin_y), (bx0, pin_y)], fill=cyan_bright, width=10)
            draw.line([(bx0 + box_w, pin_y), (bx0 + box_w + 120, pin_y)], fill=cyan_bright, width=10)

    img.save(out_path, quality=100)
    print(f"Rendered Front 4K Vector T-Shirt to {out_path}")


def render_back_tshirt_4k(out_path):
    W, H = 4096, 4096
    img = Image.new("RGBA", (W, H), (12, 12, 14, 255))
    draw = ImageDraw.Draw(img)

    font_title = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", 340)
    font_vizion = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", 260)
    font_social = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", 95)

    cx = W // 2

    # 1. Top Title: JUANDIGITS
    txt_j = "JUANDIGITS"
    bbox_j = draw.textbbox((0, 0), txt_j, font=font_title)
    tw_j = bbox_j[2] - bbox_j[0]
    jx = cx - tw_j // 2
    jy = 320

    for off in [12, 8, 4]:
        draw.text((jx - off, jy), txt_j, font=font_title, fill=(0, 229, 255, 120))
        draw.text((jx + off, jy), txt_j, font=font_title, fill=(255, 0, 128, 120))
    draw.text((jx, jy), txt_j, font=font_title, fill=(255, 255, 255, 255))

    # 2. Central Cyber Wings Shield Emblem with VIZION
    ey = jy + 440
    cyan_glow = (0, 229, 255, 255)
    magenta_glow = (255, 0, 128, 255)
    cyan_bright = (180, 250, 255, 255)

    for i in range(8):
        w_len = 380 + i * 95
        ang = math.radians(18 + i * 11)
        lx1 = cx - 480 - int(math.cos(ang) * w_len)
        ly1 = ey + 240 - int(math.sin(ang) * w_len * 0.7)
        draw.line([(cx - 450, ey + 180 + i*40), (lx1, ly1)], fill=cyan_glow if i%2==0 else magenta_glow, width=18)
        rx1 = cx + 480 + int(math.cos(ang) * w_len)
        ry1 = ey + 240 - int(math.sin(ang) * w_len * 0.7)
        draw.line([(cx + 450, ey + 180 + i*40), (rx1, ry1)], fill=cyan_glow if i%2==0 else magenta_glow, width=18)

    sw = 520
    pts = [
        (cx, ey),
        (cx + sw, ey + 260),
        (cx + sw * 0.75, ey + 580),
        (cx, ey + 750),
        (cx - sw * 0.75, ey + 580),
        (cx - sw, ey + 260)
    ]
    draw.polygon(pts, outline=cyan_glow, width=22)
    draw.polygon([(p[0], p[1] + 8) for p in pts], outline=cyan_bright, width=8)

    txt_v = "VIZION"
    bbox_v = draw.textbbox((0, 0), txt_v, font=font_vizion)
    tw_v = bbox_v[2] - bbox_v[0]
    th_v = bbox_v[3] - bbox_v[1]
    draw.text((cx - tw_v // 2, ey + 375 - th_v // 2), txt_v, font=font_vizion, fill=(255, 255, 255, 255))

    # 3. Two App Tiles: TikTok & Instagram with generous width to fit full handle
    ty = ey + 900
    tile_w, tile_h = 1600, 240
    
    # TikTok Tile
    x_tt = cx - tile_w - 40
    draw.rounded_rectangle([x_tt, ty, x_tt + tile_w, ty + tile_h], radius=35, outline=cyan_glow, width=14)
    draw.rounded_rectangle([x_tt + 6, ty + 6, x_tt + tile_w - 6, ty + tile_h - 6], radius=30, fill=(18, 22, 28, 255))
    draw_tiktok_icon(draw, x_tt + 40, ty + 40, 160)
    draw.text((x_tt + 230, ty + 70), "python_viziondigits", font=font_social, fill=(255, 255, 255, 255))

    # Instagram Tile
    x_ig = cx + 40
    draw.rounded_rectangle([x_ig, ty, x_ig + tile_w, ty + tile_h], radius=35, outline=magenta_glow, width=14)
    draw.rounded_rectangle([x_ig + 6, ty + 6, x_ig + tile_w - 6, ty + tile_h - 6], radius=30, fill=(18, 22, 28, 255))
    draw_instagram_icon(img, draw, x_ig + 40, ty + 40, 160)
    draw.text((x_ig + 230, ty + 70), "python_viziondigits", font=font_social, fill=(255, 255, 255, 255))

    # 4. Lower Cyber Matrix PCB lines
    gy_start = ty + tile_h + 80
    gy_end = H - 150
    for i in range(21):
        lx = cx - 1800 + i * 180
        draw.line([(lx, gy_start + (i%5)*45), (lx, gy_end)], fill=cyan_glow, width=12)
        draw.ellipse([lx - 14, gy_start + (i%5)*45 - 14, lx + 14, gy_start + (i%5)*45 + 14], fill=cyan_bright)

    img.save(out_path, quality=100)
    print(f"Rendered Back 4K Vector T-Shirt to {out_path}")

render_front_tshirt_4k("/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/vector_tshirt_front_4k.png")
render_back_tshirt_4k("/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/vector_tshirt_back_4k.png")
