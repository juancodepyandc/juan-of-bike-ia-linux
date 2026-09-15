from PIL import Image
import numpy as np

img = Image.open("/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/enhanced_base_texture_4k.png")
arr = np.array(img)
h, w, _ = arr.shape

# Target caramel skin color: R~200, G~125, B~80
target = np.array([205, 125, 80])
diffs = np.linalg.norm(arr[:, :, :3] - target, axis=2)
best_y, best_x = np.unravel_index(np.argmin(diffs), diffs.shape)

best_u = best_x / w
best_v = 1.0 - (best_y / h)

print(f"Best caramel skin UV: u={best_u:.4f}, v={best_v:.4f} (RGB at pixel: {arr[best_y, best_x, :3]})")
