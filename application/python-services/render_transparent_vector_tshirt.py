import math
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

def draw_tiktok(draw, x, y, size):
    s = size
    for off, col in [(6, (255, 0, 85, 255)), (-6, (0, 240, 255, 255)), (0, (255, 255, 255, 255))]:
        draw.arc([x + s*0.2 + off, y + s*0.4, x + s*0.6 + off, y + s*0.8], start=0, end=360, fill=col, width=int(s*0.14))
        draw.rectangle([x + s*0.5 + off, y + s*0.1, x + s*0.64 + off, y + s*0.6], fill=col)
        draw.arc([x + s*0.5 + off, y + s*0.1, x + s*0.92 + off, y + s*0.52], start=270, end=360, fill=col, width=int(s*0.14))

def draw_instagram(img, draw, x, y, size):
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
    mdraw.rounded_rectangle([0, 0, s, s], radius=int(s*0.28), fill=255)
    img.paste(grad, (x, y), mask)

    draw.rounded_rectangle([x + s*0.16, y + s*0.16, x + s*0.84, y + s*0.84], radius=int(s*0.18), outline=(255, 255, 255, 255), width=int(s*0.09))
    draw.ellipse([x + s*0.34, y + s*0.34, x + s*0.66, y + s*0.66], outline=(255, 255, 255, 255), width=int(s*0.09))
    draw.ellipse([x + s*0.69, y + s*0.25, x + s*0.77, y + s*0.33], fill=(255, 255, 255, 255))

def draw_pcb_motherboard(draw, x_start, y_start, width, height):
    cyan_glow = (0, 229, 255, 255)
    cyan_dark = (0, 160, 210, 220)
    cyan_bright = (220, 255, 255, 255)
    
    num_traces = 26
    spacing = width // (num_traces + 1)
    
    for i in range(num_traces):
        lx = x_start + (i + 1) * spacing
        bend_y = y_start + 100 + ((i * 43) % 360)
        bend_x = lx + (70 if i % 2 == 0 else -70)
        
        draw.line([(lx, y_start), (lx, bend_y)], fill=cyan_dark, width=10)
        draw.line([(lx, bend_y), (bend_x, bend_y + 70)], fill=cyan_glow, width=12)
        draw.line([(bend_x, bend_y + 70), (bend_x, y_start + height)], fill=cyan_glow, width=12)
        
        draw.ellipse([lx - 14, y_start + 15 - 14, lx + 14, y_start + 15 + 14], outline=cyan_glow, width=4)
        draw.ellipse([lx - 7, y_start + 15 - 7, lx + 7, y_start + 15 + 7], fill=cyan_bright)
        
        draw.ellipse([bend_x - 14, y_start + height - 25 - 14, bend_x + 14, y_start + height - 25 + 14], outline=cyan_glow, width=4)
        draw.ellipse([bend_x - 7, y_start + height - 25 - 7, bend_x + 7, y_start + height - 25 + 7], fill=cyan_bright)

    for hy in [y_start + 260, y_start + 620, y_start + 1020]:
        draw.line([(x_start + 80, hy), (x_start + width - 80, hy)], fill=cyan_glow, width=14)
        draw.line([(x_start + 120, hy + 35), (x_start + width - 120, hy + 35)], fill=cyan_dark, width=8)


def render_front_transparent_4k(out_path):
    W, H = 4096, 4096
    # 100% TRANSPARENT CANVAS
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    cx = W // 2

    font_vizion = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", 420)
    font_sub = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", 200)
    font_social = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", 145)
    font_chip = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", 125)

    # 1. VIZION
    txt_v = "VIZION"
    bbox_v = draw.textbbox((0, 0), txt_v, font=font_vizion)
    tw_v = bbox_v[2] - bbox_v[0]
    vx = cx - tw_v // 2
    vy = 300

    draw.text((vx - 10, vy), txt_v, font=font_vizion, fill=(0, 240, 255, 255))
    draw.text((vx + 10, vy), txt_v, font=font_vizion, fill=(255, 0, 110, 255))
    draw.text((vx, vy), txt_v, font=font_vizion, fill=(255, 255, 255, 255))

    # 2. juandigits
    txt_j = "juandigits"
    bbox_j = draw.textbbox((0, 0), txt_j, font=font_sub)
    tw_j = bbox_j[2] - bbox_j[0]
    draw.text((cx - tw_j // 2, vy + 440), txt_j, font=font_sub, fill=(255, 255, 255, 255))

    # 3. Social Handles
    sy = vy + 720
    icon_s = 155
    tx = cx - 960
    
    draw_tiktok(draw, tx, sy, icon_s)
    draw.text((tx + icon_s + 45, sy + 15), "@python_viziondigits", font=font_social, fill=(255, 255, 255, 255))

    sy2 = sy + 210
    draw_instagram(img, draw, tx, sy2, icon_s)
    draw.text((tx + icon_s + 45, sy2 + 15), "@python_viziondigits", font=font_social, fill=(255, 255, 255, 255))

    # 4. PCB Circuit
    pcb_y = sy2 + 320
    pcb_h = H - pcb_y - 120
    draw_pcb_motherboard(draw, cx - 1850, pcb_y, 3700, pcb_h)

    # 5. Dual Microchip Modules
    chip_w, chip_h = 2500, 210
    ch_x0 = cx - chip_w // 2
    ch_y1 = pcb_y + 420
    ch_y2 = ch_y1 + 300

    for cy_pos in [ch_y1, ch_y2]:
        draw.rounded_rectangle([ch_x0, cy_pos, ch_x0 + chip_w, cy_pos + chip_h], radius=25, fill=(10, 16, 24, 240), outline=(0, 240, 255, 255), width=16)
        draw.rounded_rectangle([ch_x0 + 8, cy_pos + 8, ch_x0 + chip_w - 8, cy_pos + chip_h - 8], radius=20, outline=(180, 250, 255, 255), width=5)
        
        txt_chip = "python_viziondigits"
        tb = draw.textbbox((0, 0), txt_chip, font=font_chip)
        tw = tb[2] - tb[0]
        th = tb[3] - tb[1]
        draw.text((cx - tw // 2, cy_pos + (chip_h - th) // 2 - 10), txt_chip, font=font_chip, fill=(0, 245, 255, 255))
        
        for p in range(5):
            py_pin = cy_pos + 38 + p * 34
            draw.rectangle([ch_x0 - 95, py_pin, ch_x0, py_pin + 14], fill=(255, 215, 0, 255))
            draw.rectangle([ch_x0 + chip_w, py_pin, ch_x0 + chip_w + 95, py_pin + 14], fill=(255, 215, 0, 255))

    img.save(out_path)
    print(f"Rendered Transparent Front to {out_path}")


def render_back_transparent_4k(out_path):
    W, H = 4096, 4096
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    cx = W // 2

    font_title = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", 380)
    font_vizion = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", 280)
    font_social = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", 105)

    # 1. JUANDIGITS
    txt_j = "JUANDIGITS"
    bbox_j = draw.textbbox((0, 0), txt_j, font=font_title)
    tw_j = bbox_j[2] - bbox_j[0]
    jx = cx - tw_j // 2
    jy = 250

    for off in [14, 9, 4]:
        draw.text((jx - off, jy), txt_j, font=font_title, fill=(0, 229, 255, 120))
        draw.text((jx + off, jy), txt_j, font=font_title, fill=(255, 0, 128, 120))
    draw.text((jx, jy), txt_j, font=font_title, fill=(255, 255, 255, 255))

    # 2. Cyber Shield Emblem
    ey = jy + 460
    cyan_glow = (0, 229, 255, 255)
    magenta_glow = (255, 0, 128, 255)
    cyan_bright = (180, 250, 255, 255)

    for i in range(8):
        w_len = 420 + i * 95
        ang = math.radians(16 + i * 10)
        lx1 = cx - 520 - int(math.cos(ang) * w_len)
        ly1 = ey + 250 - int(math.sin(ang) * w_len * 0.7)
        draw.line([(cx - 480, ey + 190 + i*40), (lx1, ly1)], fill=cyan_glow if i%2==0 else magenta_glow, width=20)
        rx1 = cx + 520 + int(math.cos(ang) * w_len)
        ry1 = ey + 250 - int(math.sin(ang) * w_len * 0.7)
        draw.line([(cx + 480, ey + 190 + i*40), (rx1, ry1)], fill=cyan_glow if i%2==0 else magenta_glow, width=20)

    sw = 540
    pts = [
        (cx, ey),
        (cx + sw, ey + 260),
        (cx + sw * 0.75, ey + 600),
        (cx, ey + 770),
        (cx - sw * 0.75, ey + 600),
        (cx - sw, ey + 260)
    ]
    draw.polygon(pts, fill=(10, 16, 24, 240), outline=cyan_glow, width=22)
    draw.polygon([(p[0], p[1] + 8) for p in pts], outline=cyan_bright, width=8)

    txt_v = "VIZION"
    bbox_v = draw.textbbox((0, 0), txt_v, font=font_vizion)
    tw_v = bbox_v[2] - bbox_v[0]
    th_v = bbox_v[3] - bbox_v[1]
    draw.text((cx - tw_v // 2, ey + 385 - th_v // 2), txt_v, font=font_vizion, fill=(255, 255, 255, 255))

    # 3. Stacked Social Badges
    ty = ey + 900
    card_w, card_h = 2500, 210
    card_x = cx - card_w // 2

    draw.rounded_rectangle([card_x, ty, card_x + card_w, ty + card_h], radius=30, fill=(14, 18, 24, 240), outline=cyan_glow, width=14)
    draw_tiktok(draw, card_x + 60, ty + 30, 150)
    draw.text((card_x + 260, ty + 50), "@python_viziondigits", font=font_social, fill=(255, 255, 255, 255))

    ty2 = ty + 250
    draw.rounded_rectangle([card_x, ty2, card_x + card_w, ty2 + card_h], radius=30, fill=(14, 18, 24, 240), outline=magenta_glow, width=14)
    draw_instagram(img, draw, card_x + 60, ty2 + 30, 150)
    draw.text((card_x + 260, ty2 + 50), "@python_viziondigits", font=font_social, fill=(255, 255, 255, 255))

    # 4. PCB tracks
    pcb_y = ty2 + 300
    pcb_h = H - pcb_y - 100
    draw_pcb_motherboard(draw, cx - 1850, pcb_y, 3700, pcb_h)

    img.save(out_path)
    print(f"Rendered Transparent Back to {out_path}")

render_front_transparent_4k("/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/vector_front_trans.png")
render_back_transparent_4k("/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/vector_back_trans.png")
