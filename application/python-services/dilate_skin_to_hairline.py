from PIL import Image
import numpy as np

TEX_PATH = "/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/rich_metis_texture_4k.png"
im = Image.open(TEX_PATH).convert("RGB")
arr = np.array(im, dtype=np.float32)

# Sample the clean warm métis skin from the nose/cheeks
# Let's inspect where in the 4K texture the face is located
# Let's find all pixels that are dark (r < 40, g < 40, b < 40) but adjacent to warm métis skin
r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
is_skin = (r > 160) & (g > 100) & (g < 170) & (b > 60) & (b < 120)

# Average skin color
mean_skin = [np.mean(r[is_skin]), np.mean(g[is_skin]), np.mean(b[is_skin])]
print(f"Mean detected métis skin color: {mean_skin}")

# In the top region where hair meets forehead, turn any dark hair painted on the face into skin
# We can find all pixels with (r < 70, g < 50, b < 40) that are NOT near the eyes (eyes are at y ~ 0.38-0.45)
# Let's replace dark pixels above y = 0.45 with warm métis skin if they are on the head UV
h, w, _ = arr.shape
# Save crop of the face area for verification
crop = Image.fromarray(arr[int(h*0.2):int(h*0.6), int(w*0.2):int(w*0.8)].astype(np.uint8))
crop.save("/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/face_texture_crop.png")
print("Saved face_texture_crop.png")
