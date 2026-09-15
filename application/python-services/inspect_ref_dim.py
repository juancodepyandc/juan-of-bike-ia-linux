from PIL import Image
import numpy as np

im = Image.open("/home/juan/AuroraIA/application/output/3d/perso_soude/perso_soude_reference.png")
print("Ref image size:", im.size)

arr = np.array(im)
# Find non-transparent pixels
alpha = arr[:, :, 3]
y_idx, x_idx = np.where(alpha > 50)
print(f"BBox: X=[{x_idx.min()}, {x_idx.max()}], Y=[{y_idx.min()}, {y_idx.max()}]")

# Sample skin from face center
cx = (x_idx.min() + x_idx.max()) // 2
cy_face = y_idx.min() + int((y_idx.max() - y_idx.min()) * 0.15)
face_pixels = arr[cy_face-30:cy_face+30, cx-30:cx+30]
mask = face_pixels[:, :, 3] > 200
rgb = face_pixels[mask][:, :3]

print(f"Face center: ({cx}, {cy_face}) -> RGB: mean={rgb.mean(axis=0)}")

# Sample arm skin
cy_arm = y_idx.min() + int((y_idx.max() - y_idx.min()) * 0.32)
# Left arm in image (right side of character):
x_arm_l = x_idx.max() - int((x_idx.max() - x_idx.min()) * 0.18)
arm_pixels = arr[cy_arm-20:cy_arm+20, x_arm_l-20:x_arm_l+20]
mask_a = arm_pixels[:, :, 3] > 200
rgb_a = arm_pixels[mask_a][:, :3]
print(f"Arm sample at ({x_arm_l}, {cy_arm}) -> RGB: mean={rgb_a.mean(axis=0)}")
