import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

def enhance_patch(img_path, out_path, is_front=True):
    img = Image.open(img_path).convert("RGBA")
    w, h = img.size
    # Upscale to 2048x2048 for vector clarity
    img = img.resize((2048, 2048), Image.Resampling.LANCZOS)
    draw = ImageDraw.Draw(img)
    
    # Try finding high quality TrueType fonts
    font_large = None
    font_med = None
    font_small = None
    for fpath in ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                  "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
                  "/usr/share/fonts/truetype/ubuntu/Ubuntu-B.ttf"]:
        try:
            font_large = ImageFont.truetype(fpath, 110)
            font_med = ImageFont.truetype(fpath, 60)
            font_small = ImageFont.truetype(fpath, 42)
            break
        except Exception:
            continue
    if font_large is None:
        font_large = ImageFont.load_default()
        font_med = font_large
        font_small = font_large

    if is_front:
        # 1. Overlay crisp text on front
        # Clear small region where handle was slightly garbled
        # Draw clean text "python_viziondigits"
        # Y position for handle is around Y=980
        pass
    
    img.save(out_path)
    print(f"Enhanced patch saved: {out_path}")

enhance_patch("/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/tshirt_graphic_front_4k.png",
              "/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/patch_front_uhd.png", is_front=True)
enhance_patch("/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/tshirt_graphic_back_4k.png",
              "/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/patch_back_uhd.png", is_front=False)
