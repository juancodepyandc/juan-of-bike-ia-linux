from PIL import Image
from pathlib import Path

img_path = Path("/home/juan/AuroraIA/application/output/3d/01_fairy_tail_guild_hall/references/master_concept.png")
img = Image.open(img_path)

# Découper le bâtiment parfait en haut à gauche
# Bounding box du bâtiment en haut à gauche
cropped = img.crop((30, 20, 520, 590))
# Redimensionner en 1024x1024 avec padding neutre
w, h = cropped.size
max_side = max(w, h)
canvas = Image.new("RGB", (int(max_side * 1.15), int(max_side * 1.15)), (118, 118, 122))
canvas.paste(cropped, ((canvas.width - w) // 2, (canvas.height - h) // 2))
canvas = canvas.resize((1024, 1024), Image.Resampling.LANCZOS)
canvas.save(str(img_path))
print(f"[OK] Master concept propre recadré : 1024x1024")
