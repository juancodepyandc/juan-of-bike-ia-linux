import math
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

def draw_tiktok(draw, x, y, size):
    s = size
    # Glow / chromatic offset
    for off, col in [(5, (255, 0, 85, 255)), (-5, (0, 240, 255, 255)), (0, (255, 255, 255, 255))]:
        draw.arc([x + s*0.2 + off, y + s*0.4, x + s*0.6 + off, y + s*0.8], start=0, end=360, fill=col, width=int(s*0.13))
        draw.rectangle([x + s*0.5 + off, y + s*0.1, x + s*0.63 + off, y + s*0.6], fill=col)
        draw.arc([x + s*0.5 + off, y + s*0.1, x + s*0.92 + off, y + s*0.52], start=270, end=360, fill=col, width=int(s*0.13))

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

    draw.rounded_rectangle([x + s*0.16, y + s*0.16, x + s*0.84, y + s*0.84], radius=int(s*0.18), outline=(255, 255, 255, 255), width=int(s*0.08))
    draw.ellipse([x + s*0.34, y + s*0.34, x + s*0.66, y + s*0.66], outline=(255, 255, 255, 255), width=int(s*0.08))
    draw.ellipse([x + s*0.69, y + s*0.25, x + s*0.77, y + s*0.33], fill=(255, 255, 255, 255))

def draw_pcb_motherboard(draw, x_start, y_start, width, height):
    cyan_glow = (0, 229, 255, 255)
    cyan_dark = (0, 140, 180, 180)
    cyan_bright = (200, 250, 255, 255)
    
    # 1. Background circuit bus traces (diagonal 45 deg + vertical)
    num_traces = 28
    spacing = width // (num_traces + 1)
    
    for i in range(num_traces):
        lx = x_start + (i + 1) * spacing
        # Staggered entry
        bend_y = y_start + 120 + ((i * 37) % 350)
        bend_x = lx + (60 if i % 2 == 0 else -60)
        
        # Upper track
        draw.line([(lx, y_start), (lx, bend_y)], fill=cyan_dark, width=8)
        # 45 deg bend
        draw.line([(lx, bend_y), (bend_x, bend_y + 60)], fill=cyan_glow, width=10)
        # Lower track
        draw.line([(bend_x, bend_y + 60), (bend_x, y_start + height)], fill=cyan_glow, width=10)
        
        # Solder Pads (vias)
        draw.ellipse([lx - 12, y_start + 20 - 12, lx + 12, y_start + 20 + 12], outline=cyan_glow, width=4)
        draw.ellipse([lx - 6, y_start + 20 - 6, lx + 6, y_start + 20 + 6], fill=cyan_bright)
        
        draw.ellipse([bend_x - 12, y_start + height - 30 - 12, bend_x + 12, y_start + height - 30 + 12], outline=cyan_glow, width=4)
        draw.ellipse([bend_x - 6, y_start + height - 30 - 6, bend_x + 6, y_start + height - 30 + 6], fill=cyan_bright)

    # 2. Horizontal data bus bundles
    for hy in [y_start + 280, y_start + 650, y_start + 1050]:
        draw.line([(x_start + 100, hy), (x_start + width - 100, hy)], fill=cyan_glow, width=12)
        draw.line([(x_start + 140, hy + 30), (x_start + width - 140, hy + 30)], fill=cyan_dark, width=6)


def render_front_master_4k(out_path):
    W, H = 4096, 4096
    img = Image.new("RGBA", (W, H), (15, 15, 18, 255))
    draw = ImageDraw.Draw(img)
    cx = W // 2

    font_vizion = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", 400)
    font_sub = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", 190)
    font_social = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", 135)
    font_chip = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", 115)

    # 1. VIZION
    txt_v = "VIZION"
    bbox_v = draw.textbbox((0, 0), txt_v, font=font_vizion)
    tw_v = bbox_v[2] - bbox_v[0]
    vx = cx - tw_v // 2
    vy = 320

    draw.text((vx - 10, vy), txt_v, font=font_vizion, fill=(0, 240, 255, 255))
    draw.text((vx + 10, vy), txt_v, font=font_vizion, fill=(255, 0, 110, 255))
    draw.text((vx, vy), txt_v, font=font_vizion, fill=(255, 255, 255, 255))

    # 2. juandigits
    txt_j = "juandigits"
    bbox_j = draw.textbbox((0, 0), txt_j, font=font_sub)
    tw_j = bbox_j[2] - bbox_j[0]
    draw.text((cx - tw_j // 2, vy + 410), txt_j, font=font_sub, fill=(245, 245, 245, 255))

    # 3. Social Handles: TikTok & Instagram on 2 clear lines
    sy = vy + 680
    icon_s = 145
    
    # TikTok row
    tx = cx - 900
    draw_tiktok(draw, tx, sy, icon_s)
    draw.text((tx + icon_s + 45, sy + 15), "@python_viziondigits", font=font_social, fill=(255, 255, 255, 255))

    # Instagram row
    sy2 = sy + 200
    draw_instagram(img, draw, tx, sy2, icon_s)
    draw.text((tx + icon_s + 45, sy2 + 15), "@python_viziondigits", font=font_social, fill=(255, 255, 255, 255))

    # 4. Realistic Motherboard PCB Circuit Matrix
    pcb_y = sy2 + 300
    pcb_h = H - pcb_y - 120
    draw_pcb_motherboard(draw, cx - 1800, pcb_y, 3600, pcb_h)

    # 5. Dual Microchip Processor Modules with glowing borders
    chip_w, chip_h = 2400, 200
    ch_x0 = cx - chip_w // 2
    
    ch_y1 = pcb_y + 400
    ch_y2 = ch_y1 + 280

    for cy_pos in [ch_y1, ch_y2]:
        # Chip package
        draw.rounded_rectangle([ch_x0, cy_pos, ch_x0 + chip_w, cy_pos + chip_h], radius=25, fill=(10, 16, 24, 255), outline=(0, 240, 255, 255), width=14)
        draw.rounded_rectangle([ch_x0 + 8, cy_pos + 8, ch_x0 + chip_w - 8, cy_pos + chip_h - 8], radius=20, outline=(180, 250, 255, 255), width=4)
        
        txt_chip = "python_viziondigits"
        tb = draw.textbbox((0, 0), txt_chip, font=font_chip)
        tw = tb[2] - tb[0]
        th = tb[3] - tb[1]
        draw.text((cx - tw // 2, cy_pos + (chip_h - th) // 2 - 10), txt_chip, font=font_chip, fill=(0, 245, 255, 255))
        
        # Gold/cyan chip pins on left and right
        for p in range(5):
            py_pin = cy_pos + 35 + p * 32
            draw.rectangle([ch_x0 - 90, py_pin, ch_x0, py_pin + 14], fill=(255, 215, 0, 255))
            draw.rectangle([ch_x0 + chip_w, py_pin, ch_x0 + chip_w + 90, py_pin + 14], fill=(255, 215, 0, 255))

    img.save(out_path, quality=100)
    print(f"Rendered Pro Front to {out_path}")


def render_back_master_4k(out_path):
    W, H = 4096, 4096
    img = Image.new("RGBA", (W, H), (15, 15, 18, 255))
    draw = ImageDraw.Draw(img)
    cx = W // 2

    font_title = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", 360)
    font_vizion = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", 270)
    font_social = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", 95)

    # 1. JUANDIGITS
    txt_j = "JUANDIGITS"
    bbox_j = draw.textbbox((0, 0), txt_j, font=font_title)
    tw_j = bbox_j[2] - bbox_j[0]
    jx = cx - tw_j // 2
    jy = 280

    for off in [14, 9, 4]:
        draw.text((jx - off, jy), txt_j, font=font_title, fill=(0, 229, 255, 120))
        draw.text((jx + off, jy), txt_j, font=font_title, fill=(255, 0, 128, 120))
    draw.text((jx, jy), txt_j, font=font_title, fill=(255, 255, 255, 255))

    # 2. Cyber Shield Emblem with VIZION and Wings
    ey = jy + 440
    cyan_glow = (0, 229, 255, 255)
    magenta_glow = (255, 0, 128, 255)
    cyan_bright = (180, 250, 255, 255)

    # Wing feathers
    for i in range(8):
        w_len = 400 + i * 90
        ang = math.radians(16 + i * 10)
        lx1 = cx - 500 - int(math.cos(ang) * w_len)
        ly1 = ey + 240 - int(math.sin(ang) * w_len * 0.7)
        draw.line([(cx - 460, ey + 180 + i*40), (lx1, ly1)], fill=cyan_glow if i%2==0 else magenta_glow, width=18)
        rx1 = cx + 500 + int(math.cos(ang) * w_len)
        ry1 = ey + 240 - int(math.sin(ang) * w_len * 0.7)
        draw.line([(cx + 460, ey + 180 + i*40), (rx1, ry1)], fill=cyan_glow if i%2==0 else magenta_glow, width=18)

    sw = 520
    pts = [
        (cx, ey),
        (cx + sw, ey + 250),
        (cx + sw * 0.75, ey + 580),
        (cx, ey + 750),
        (cx - sw * 0.75, ey + 580),
        (cx - sw, ey + 250)
    ]
    draw.polygon(pts, fill=(10, 16, 24, 255), outline=cyan_glow, width=22)
    draw.polygon([(p[0], p[1] + 8) for p in pts], outline=cyan_bright, width=8)

    txt_v = "VIZION"
    bbox_v = draw.textbbox((0, 0), txt_v, font=font_vizion)
    tw_v = bbox_v[2] - bbox_v[0]
    th_v = bbox_v[3] - bbox_v[1]
    draw.text((cx - tw_v // 2, ey + 375 - th_v // 2), txt_v, font=font_vizion, fill=(255, 255, 255, 255))

    # 3. Stacked Full-Width Social Badge Tiles (Centered, no clipping)
    ty = ey + 870
    card_w, card_h = 2400, 200
    card_x = cx - card_w // 2

    # TikTok Card
    draw.rounded_rectangle([card_x, ty, card_x + card_w, ty + card_h], radius=30, fill=(14, 18, 24, 255), outline=cyan_glow, width=12)
    draw_tiktok(draw, card_x + 60, ty + 30, 140)
    draw.text((card_x + 250, ty + 50), "@python_viziondigits", font=font_social, fill=(255, 255, 255, 255))

    # Instagram Card
    ty2 = ty + 240
    draw.rounded_rectangle([card_x, ty2, card_x + card_w, ty2 + card_h], radius=30, fill=(14, 18, 24, 255), outline=magenta_glow, width=12)
    draw_instagram(img, draw, card_x + 60, ty2 + 30, 140)
    draw.text((card_x + 250, ty2 + 50), "@python_viziondigits", font=font_social, fill=(255, 255, 255, 255))

    # 4. Lower PCB tracks
    pcb_y = ty2 + 280
    pcb_h = H - pcb_y - 100
    draw_pcb_motherboard(draw, cx - 1800, pcb_y, 3600, pcb_h)

    img.save(out_path, quality=100)
    print(f"Rendered Pro Back to {out_path}")

render_front_master_4k("/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/pro_tshirt_front_4k.png")
render_back_master_4k("/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/pro_tshirt_back_4k.png")
