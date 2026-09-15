from PIL import Image
import numpy as np

img_path = "/home/juan/AuroraIA/application/output/3d/01_fairy_tail_guild_hall/references/master_concept.png"
img = Image.open(img_path)

# La boîte de découpe propre sans le bord droit
# Le bâtiment principal est entre X=140 et X=840, Y=70 et Y=930
w, h = img.size
cropped = img.crop((120, 50, 845, 950))

cw, ch = cropped.size
max_dim = max(cw, ch)
target_size = int(max_dim * 1.12)

# Couleur de fond studio neutre
bg_color = (118, 118, 122)
clean_img = Image.new("RGB", (target_size, target_size), bg_color)
clean_img.paste(cropped, ((target_size - cw) // 2, (target_size - ch) // 2))

clean_img = clean_img.resize((1024, 1024), Image.Resampling.LANCZOS)
clean_img.save(img_path)
print("[OK] Master concept 100% propre, centré sans aucun déchet : 1024x1024")
