from PIL import Image
from pathlib import Path

refs_dir = Path("/home/juan/AuroraIA/application/output/3d/01_fairy_tail_guild_hall/references")
strip_path = refs_dir / "multiview_consistent_strip.png"

strip = Image.open(strip_path)
w, h = strip.size
view_w = w // 6

view_names = [
    "view_01_front.png",
    "view_02_front_right.png",
    "view_03_right.png",
    "view_04_back.png",
    "view_05_left.png",
    "view_06_front_left.png"
]

for i, name in enumerate(view_names):
    box = (i * view_w, 0, (i + 1) * view_w, h)
    view_img = strip.crop(box)
    view_img.save(refs_dir / name)
    print(f"[OK] {name} extrait ({view_w}x{h})")

