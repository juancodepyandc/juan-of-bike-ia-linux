from PIL import Image
import numpy as np

img_path = "/home/juan/AuroraIA/application/output/3d/01_fairy_tail_guild_hall/references/master_concept.png"
img = Image.open(img_path).convert("RGB")
arr = np.array(img, dtype=np.float32)

# Le fond est le gris studio neutre autour de (118, 118, 122)
bg_ref = np.array([118.0, 118.0, 122.0], dtype=np.float32)
dist = np.linalg.norm(arr - bg_ref, axis=-1)

# Créer un masque alpha doux et propre
# Si dist < 12 -> fond transparent (alpha 0)
# Si dist > 25 -> bâtiment opaque (alpha 255)
alpha = np.clip((dist - 12.0) / (25.0 - 12.0), 0.0, 1.0) * 255.0
alpha = alpha.astype(np.uint8)

# Créer image RGBA
rgba_arr = np.dstack([np.array(img), alpha])
rgba_img = Image.fromarray(rgba_arr, mode="RGBA")
rgba_img.save(img_path)
print(f"[OK] Master concept converti en RGBA net sans coupure : {img_path}")
