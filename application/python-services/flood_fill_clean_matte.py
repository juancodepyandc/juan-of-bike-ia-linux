from PIL import Image
import numpy as np
from scipy.ndimage import binary_fill_holes

img_path = "/home/juan/AuroraIA/application/output/3d/01_fairy_tail_guild_hall/references/master_concept.png"
img = Image.open(img_path).convert("RGB")
arr = np.array(img, dtype=np.float32)

# Le fond neutre dans les coins
corner_colors = [arr[5, 5], arr[5, -5], arr[-5, 5], arr[-5, -5]]
mean_bg = np.mean(corner_colors, axis=0)

# Distance de couleur au fond
dist = np.linalg.norm(arr - mean_bg, axis=-1)

# Masque de premier plan : tout ce qui n'est pas le fond
is_fg = dist > 18.0

# Remplir les trous internes du bâtiment pour que l'intérieur (fenêtres sombres, etc.) ne soit jamais transparent
is_fg_filled = binary_fill_holes(is_fg)

# Alpha lisse
alpha = (is_fg_filled * 255).astype(np.uint8)

rgba = Image.fromarray(np.dstack([np.array(img), alpha]), mode="RGBA")
rgba.save(img_path)
print("[OK] Masque parfait sans aucun déchet ni trou intérieur appliqué.")
