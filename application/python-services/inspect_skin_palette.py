from PIL import Image
import numpy as np

im = Image.open("/home/juan/AuroraIA/application/output/3d/perso_vizion_4k/clean_dilated_texture_4k.png").convert("RGB")
arr = np.array(im, dtype=np.float32)

# Sample face area (y from 0.1 to 0.45, x from 0.1 to 0.9)
h, w, _ = arr.shape
face_crop = arr[int(h*0.1):int(h*0.45), int(w*0.2):int(w*0.8)]
mean_rgb = np.mean(face_crop, axis=(0, 1))
print(f"Face crop mean RGB: {mean_rgb}")
