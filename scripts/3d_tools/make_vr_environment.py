import sys
import torch
import numpy as np
import trimesh
from PIL import Image
from transformers import pipeline

def main():
    img_path = "application/output/3d/conversations/test_monobloc_world/test_monobloc_world_reference.png"
    out_path = "application/output/3d/conversations/test_monobloc_world/paysage_immersif.glb"
    
    print("Loading depth model...")
    depth_pipe = pipeline(task="depth-estimation", model="depth-anything/Depth-Anything-V2-Small-hf", device="cuda")
    
    image = Image.open(img_path).convert("RGB")
    width, height = image.size
    
    print("Computing depth...")
    depth_img = depth_pipe(image)["depth"]
    
    # Mesh resolution
    w_mesh, h_mesh = 256, 256
    depth_arr = np.array(depth_img.resize((w_mesh, h_mesh))).astype(np.float32)
    
    # Normalize depth (0 to 1)
    depth_min, depth_max = depth_arr.min(), depth_arr.max()
    depth_norm = (depth_arr - depth_min) / (depth_max - depth_min + 1e-8)
    
    # Create curved cylinder geometry
    # x goes from -1 to 1 (angle from -pi/4 to pi/4)
    # y goes from -1 to 1 (height)
    
    u = np.linspace(0, 1, w_mesh)
    v = np.linspace(0, 1, h_mesh)
    uu, vv = np.meshgrid(u, v)
    
    # Curve angle: 120 degrees (2/3 pi)
    angle = (uu - 0.5) * (2 * np.pi / 3)
    radius = 5.0
    
    # Cylinder base coordinates
    x_base = radius * np.sin(angle)
    z_base = -radius * np.cos(angle)
    y_base = (1 - vv) * 6.0 - 1.0 # Height mapped from -1 to 5
    
    # Apply depth displacement (push vertices inward based on depth)
    # depth_norm: 1 is close (white), 0 is far (black)
    # We want close objects to be pushed towards the camera (origin)
    displacement_scale = 3.0
    # Push along normal (towards origin for cylinder)
    z_displaced = z_base + depth_norm * displacement_scale
    
    vertices = np.stack([x_base.flatten(), y_base.flatten(), z_displaced.flatten()], axis=1)
    
    # Generate faces
    faces = []
    for i in range(h_mesh - 1):
        for j in range(w_mesh - 1):
            idx = i * w_mesh + j
            faces.append([idx, idx + w_mesh, idx + 1])
            faces.append([idx + 1, idx + w_mesh, idx + w_mesh + 1])
            
    mesh = trimesh.Trimesh(vertices=vertices, faces=faces)
    
    # UVs
    uvs = np.stack([uu.flatten(), 1-vv.flatten()], axis=1)
    mesh.visual = trimesh.visual.TextureVisuals(uv=uvs, image=image)
    
    # Export
    mesh.export(out_path)
    print(f"Immersive VR environment saved to {out_path}")

if __name__ == "__main__":
    main()
