import math
import numpy as np
from PIL import Image, ImageDraw, ImageFont

def draw_tiktok_icon(draw, x, y, size):
    s = size
    for off_x, off_y, col in [(7, -3, (255, 0, 85, 255)), (-7, 3, (0, 240, 255, 255)), (0, 0, (255, 255, 255, 255))]:
        draw.arc([x + s*0.18 + off_x, y + s*0.38 + off_y, x + s*0.62 + off_x, y + s*0.82 + off_y], 
                 start=0, end=360, fill=col, width=int(s*0.15))
        draw.rectangle([x + s*0.50 + off_x, y + s*0.08 + off_y, x + s*0.65 + off_x, y + s*0.60 + off_y], fill=col)
        draw.arc([x + s*0.50 + off_x, y + s*0.08 + off_y, x + s*0.94 + off_x, y + s*0.52 + off_y], 
                 start=270, end=360, fill=col, width=int(s*0.15))

def draw_instagram_icon(img, draw, x, y, size):
    s = size
    grad = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    gdraw = ImageDraw.Draw(grad)
    for i in range(s):
        t = i / s
        r = int(131 + (254 - 131) * t)
        g = int(58 + (50 - 58) * t)
        b = int(180 + (230 - 180) * (1.0 - t))
        gdraw.line([(0, i), (s, i)], fill=(r, g, b, 255))
    
    mask = Image.new("L", (s, s), 0)
    mdraw = ImageDraw.Draw(mask)
    mdraw.rounded_rectangle([0, 0, s, s], radius=int(s*0.28), fill=255)
    img.paste(grad, (x, y), mask)

    draw.rounded_rectangle([x + s*0.14, y + s*0.14, x + s*0.86, y + s*0.86], 
                           radius=int(s*0.20), outline=(255, 255, 255, 255), width=int(s*0.09))
    draw.ellipse([x + s*0.33, y + s*0.33, x + s*0.67, y + s*0.67], 
                 outline=(255, 255, 255, 255), width=int(s*0.09))
    draw.ellipse([x + s*0.70, y + s*0.23, x + s*0.79, y + s*0.32], fill=(255, 255, 255, 255))

def draw_pcb_network(draw, x_start, y_start, width, height):
    cyan_glow = (0, 235, 255, 255)
    cyan_dark = (0, 145, 195, 220)
    cyan_bright = (230, 255, 255, 255)
    gold_color = (255, 205, 30, 255)
    
    num_traces = 26
    spacing = width // (num_traces + 1)
    
    for i in range(num_traces):
        lx = x_start + (i + 1) * spacing
        b1_y = y_start + 60 + ((i * 41) % 240)
        bend_dir = 1 if (i // 2) % 2 == 0 else -1
        b1_x = lx + bend_dir * 60
        
        b2_y = b1_y + 100 + ((i * 29) % 200)
        b2_x = b1_x + (30 if i % 2 == 0 else -30)
        
        draw.line([(lx, y_start), (lx, b1_y)], fill=cyan_dark, width=12)
        draw.line([(lx, b1_y), (b1_x, b1_y + 60)], fill=cyan_glow, width=14)
        draw.line([(b1_x, b1_y + 60), (b1_x, b2_y)], fill=cyan_glow, width=14)
        draw.line([(b1_x, b2_y), (b2_x, b2_y + 45)], fill=cyan_dark, width=12)
        draw.line([(b2_x, b2_y + 45), (b2_x, y_start + height)], fill=cyan_glow, width=14)
        
        for vy, vx in [(y_start + 15, lx), (b1_y + 30, (lx + b1_x)//2), (y_start + height - 20, b2_x)]:
            draw.ellipse([vx - 13, vy - 13, vx + 13, vy + 13], outline=cyan_glow, width=4)
            draw.ellipse([vx - 6, vy - 6, vx + 6, vy + 6], fill=gold_color if i%3==0 else cyan_bright)

    for hy in [y_start + 190, y_start + 520, y_start + 880, y_start + 1200]:
        if hy < y_start + height:
            draw.line([(x_start + 40, hy), (x_start + width - 40, hy)], fill=cyan_glow, width=14)
            draw.line([(x_start + 70, hy + 28), (x_start + width - 70, hy + 28)], fill=cyan_dark, width=7)


def create_front_clean_4k(out_path):
    W, H = 4096, 4096
    img = Image.new("RGBA", (W, H), (11, 11, 14, 255))
    draw = ImageDraw.Draw(img)
    cx = W // 2

    font_path = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
    font_vizion = ImageFont.truetype(font_path, 470)
    font_sub = ImageFont.truetype(font_path, 210)
    font_social = ImageFont.truetype(font_path, 145)
    font_chip = ImageFont.truetype(font_path, 135)

    # 1. VIZION
    txt_v = "VIZION"
    bbox_v = draw.textbbox((0, 0), txt_v, font=font_vizion)
    tw_v = bbox_v[2] - bbox_v[0]
    vx = cx - tw_v // 2
    vy = 320

    for off, col in [(-14, (0, 240, 255, 200)), (14, (255, 0, 110, 200))]:
        draw.text((vx + off, vy), txt_v, font=font_vizion, fill=col)
    draw.text((vx, vy), txt_v, font=font_vizion, fill=(255, 255, 255, 255))

    # 2. juandigits
    txt_j = "juandigits"
    bbox_j = draw.textbbox((0, 0), txt_j, font=font_sub)
    tw_j = bbox_j[2] - bbox_j[0]
    draw.text((cx - tw_j // 2, vy + 480), txt_j, font=font_sub, fill=(245, 245, 250, 255))

    # 3. SOCIAL CARDS (Width = 2150px, Centered with comfortable margins)
    card_w = 2150
    card_h = 210
    card_x = cx - card_w // 2
    icon_sz = 140
    
    # TikTok Card
    card_y1 = vy + 740
    draw.rounded_rectangle([card_x, card_y1, card_x + card_w, card_y1 + card_h], 
                           radius=35, fill=(10, 14, 20, 255), outline=(0, 240, 255, 255), width=13)
    draw.rounded_rectangle([card_x + 6, card_y1 + 6, card_x + card_w - 6, card_y1 + card_h - 6], 
                           radius=28, outline=(180, 250, 255, 180), width=4)
    draw_tiktok_icon(draw, card_x + 45, card_y1 + 35, icon_sz)
    draw.text((card_x + icon_sz + 70, card_y1 + 35), "@python_viziondigits", font=font_social, fill=(255, 255, 255, 255))

    # Instagram Card
    card_y2 = card_y1 + 250
    draw.rounded_rectangle([card_x, card_y2, card_x + card_w, card_y2 + card_h], 
                           radius=35, fill=(16, 10, 18, 255), outline=(255, 0, 128, 255), width=13)
    draw.rounded_rectangle([card_x + 6, card_y2 + 6, card_x + card_w - 6, card_y2 + card_h - 6], 
                           radius=28, outline=(255, 180, 220, 180), width=4)
    draw_instagram_icon(img, draw, card_x + 45, card_y2 + 35, icon_sz)
    draw.text((card_x + icon_sz + 70, card_y2 + 35), "@python_viziondigits", font=font_social, fill=(255, 255, 255, 255))

    # 4. MOTHERBOARD PCB MATRIX
    pcb_y = card_y2 + 265
    pcb_w = 2300
    pcb_h = H - pcb_y - 20
    draw_pcb_network(draw, cx - pcb_w // 2, pcb_y, pcb_w, pcb_h)

    # 5. DUAL HIGH-TECH PROCESSORS
    chip_w, chip_h = 2200, 200
    ch_x0 = cx - chip_w // 2
    ch_y1 = pcb_y + 340
    ch_y2 = ch_y1 + 260

    for ch_y in [ch_y1, ch_y2]:
        draw.rounded_rectangle([ch_x0, ch_y, ch_x0 + chip_w, ch_y + chip_h], 
                               radius=25, fill=(8, 14, 22, 255), outline=(0, 245, 255, 255), width=14)
        draw.rounded_rectangle([ch_x0 + 8, ch_y + 8, ch_x0 + chip_w - 8, ch_y + chip_h - 8], 
                               radius=18, outline=(200, 255, 255, 220), width=4)
        
        txt_chip = "PYTHON_VIZIONDIGITS"
        tb = draw.textbbox((0, 0), txt_chip, font=font_chip)
        tw = tb[2] - tb[0]
        th = tb[3] - tb[1]
        draw.text((cx - tw // 2, ch_y + (chip_h - th) // 2 - 8), txt_chip, font=font_chip, fill=(0, 250, 255, 255))
        
        for p in range(5):
            py_pin = ch_y + 28 + p * 28
            draw.rectangle([ch_x0 - 75, py_pin, ch_x0, py_pin + 13], fill=(255, 215, 0, 255))
            draw.rectangle([ch_x0 + chip_w, py_pin, ch_x0 + chip_w + 75, py_pin + 13], fill=(255, 215, 0, 255))

    img.save(out_path, quality=100)
    print(f"Rendered Clean Front to {out_path}")


def create_back_clean_4k(out_path):
    W, H = 4096, 4096
    img = Image.new("RGBA", (W, H), (11, 11, 14, 255))
    draw = ImageDraw.Draw(img)
    cx = W // 2

    font_path = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
    font_title = ImageFont.truetype(font_path, 440)
    font_vizion = ImageFont.truetype(font_path, 320)
    font_social = ImageFont.truetype(font_path, 145)

    # 1. JUANDIGITS (Upper Back)
    txt_j = "JUANDIGITS"
    bbox_j = draw.textbbox((0, 0), txt_j, font=font_title)
    tw_j = bbox_j[2] - bbox_j[0]
    jx = cx - tw_j // 2
    jy = 290

    for off, col in [(-14, (0, 240, 255, 180)), (14, (255, 0, 128, 180))]:
        draw.text((jx + off, jy), txt_j, font=font_title, fill=col)
    draw.text((jx, jy), txt_j, font=font_title, fill=(255, 255, 255, 255))

    # 2. CYBER SHIELD WITH NEON WINGS
    ey = jy + 460
    cyan_glow = (0, 235, 255, 255)
    magenta_glow = (255, 0, 128, 255)
    cyan_bright = (200, 255, 255, 255)

    for i in range(9):
        w_len = 360 + i * 80
        ang = math.radians(15 + i * 9)
        lx1 = cx - 460 - int(math.cos(ang) * w_len)
        ly1 = ey + 210 - int(math.sin(ang) * w_len * 0.72)
        col = cyan_glow if i%2==0 else magenta_glow
        draw.line([(cx - 420, ey + 150 + i*34), (lx1, ly1)], fill=col, width=17)
        
        rx1 = cx + 420 + int(math.cos(ang) * w_len)
        ry1 = ey + 210 - int(math.sin(ang) * w_len * 0.72)
        draw.line([(cx + 420, ey + 150 + i*34), (rx1, ry1)], fill=col, width=17)

    sw = 500
    pts = [
        (cx, ey),
        (cx + sw, ey + 230),
        (cx + sw * 0.75, ey + 540),
        (cx, ey + 700),
        (cx - sw * 0.75, ey + 540),
        (cx - sw, ey + 230)
    ]
    draw.polygon(pts, fill=(10, 16, 26, 255), outline=cyan_glow, width=19)
    draw.polygon([(p[0], p[1] + 7) for p in pts], outline=cyan_bright, width=6)

    txt_v = "VIZION"
    bbox_v = draw.textbbox((0, 0), txt_v, font=font_vizion)
    tw_v = bbox_v[2] - bbox_v[0]
    th_v = bbox_v[3] - bbox_v[1]
    draw.text((cx - tw_v // 2, ey + 350 - th_v // 2), txt_v, font=font_vizion, fill=(255, 255, 255, 255))

    # 3. SOCIAL BADGES (Width = 2150px)
    ty = ey + 780
    card_w = 2150
    card_h = 210
    card_x = cx - card_w // 2
    icon_sz = 140

    # TikTok Card
    draw.rounded_rectangle([card_x, ty, card_x + card_w, ty + card_h], 
                           radius=35, fill=(10, 14, 20, 255), outline=cyan_glow, width=13)
    draw.rounded_rectangle([card_x + 6, ty + 6, card_x + card_w - 6, ty + card_h - 6], 
                           radius=28, outline=(180, 250, 255, 180), width=4)
    draw_tiktok_icon(draw, card_x + 45, ty + 35, icon_sz)
    draw.text((card_x + icon_sz + 70, ty + 35), "@python_viziondigits", font=font_social, fill=(255, 255, 255, 255))

    # Instagram Card
    ty2 = ty + 250
    draw.rounded_rectangle([card_x, ty2, card_x + card_w, ty2 + card_h], 
                           radius=35, fill=(16, 10, 18, 255), outline=magenta_glow, width=13)
    draw.rounded_rectangle([card_x + 6, ty2 + 6, card_x + card_w - 6, ty2 + card_h - 6], 
                           radius=28, outline=(255, 180, 220, 180), width=4)
    draw_instagram_icon(img, draw, card_x + 45, ty2 + 35, icon_sz)
    draw.text((card_x + icon_sz + 70, ty2 + 35), "@python_viziondigits", font=font_social, fill=(255, 255, 255, 255))

    # 4. LOWER PCB MATRIX
    pcb_y = ty2 + 265
    pcb_w = 2300
    pcb_h = H - pcb_y - 20
    draw_pcb_network(draw, cx - pcb_w // 2, pcb_y, pcb_w, pcb_h)

    img.save(out_path, quality=100)
    print(f"Rendered Clean Back to {out_path}")

create_front_clean_4k("/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/solid_tshirt_front_4k.png")
create_back_clean_4k("/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/solid_tshirt_back_4k.png")
