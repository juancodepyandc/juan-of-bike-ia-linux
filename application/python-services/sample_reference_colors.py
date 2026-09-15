import numpy as np
from PIL import Image

ref_path = "/home/juan/AuroraIA/application/output/3d/perso_soude/perso_soude_reference.png"
im = Image.open(ref_path).convert("RGBA")
arr = np.array(im)

# Let's sample skin from face (approx x: 400-500, y: 150-250)
face_sample = arr[180:230, 420:480]
face_mask = face_sample[:, :, 3] > 200
face_rgb = face_sample[face_mask][:, :3]
print(f"Reference Face RGB: mean={face_rgb.mean(axis=0)}, min={face_rgb.min(axis=0)}, max={face_rgb.max(axis=0)}")

# Sample skin from left arm (approx x: 700-800, y: 300-340)
arm_sample = arr[300:340, 700:800]
arm_mask = arm_sample[:, :, 3] > 200
arm_rgb = arm_sample[arm_mask][:, :3]
print(f"Reference Arm RGB: mean={arm_rgb.mean(axis=0)}, min={arm_rgb.min(axis=0)}, max={arm_rgb.max(axis=0)}")

# Sample skin from hand
hand_sample = arr[280:330, 840:900]
hand_mask = hand_sample[:, :, 3] > 200
hand_rgb = hand_sample[hand_mask][:, :3]
print(f"Reference Hand RGB: mean={hand_rgb.mean(axis=0)}, min={hand_rgb.min(axis=0)}, max={hand_rgb.max(axis=0)}")

print("\nLinear RGB equivalents (0-1):")
print(f"Face: {face_rgb.mean(axis=0) / 255.0}")
print(f"Arm:  {arm_rgb.mean(axis=0) / 255.0}")
print(f"Hand: {hand_rgb.mean(axis=0) / 255.0}")
