import sys
import torch
import numpy as np
import trimesh
from PIL import Image
from transformers import pipeline

def main():
    img_path = "application/output/3d/conversations/test_monobloc_world/test_monobloc_world_reference.png"
    out_path = "application/output/3d/conversations/test_monobloc_world/test_monobloc_world_diorama.glb"
    
    print("Loading depth model...")
    depth_pipe = pipeline(task="depth-estimation", model="depth-anything/Depth-Anything-V2-Small-hf", device="cuda")
    
    print("Processing image...")
    image = Image.open(img_path).convert("RGB")
    depth = depth_pipe(image)["depth"]
    depth_arr = np.array(depth).astype(np.float32)
    depth_arr = (depth_arr - depth_arr.min()) / (depth_arr.max() - depth_arr.min())
    
    # Create a dense grid mesh
    print("Creating mesh...")
    width, height = image.size
    # Downsample slightly for mesh density
    scale = 0.5
    w_mesh, h_mesh = int(width * scale), int(height * scale)
    depth_arr = np.array(depth.resize((w_mesh, h_mesh)))
    depth_arr = (depth_arr - depth_arr.min()) / (depth_arr.max() - depth_arr.min())
    
    x = np.linspace(-1, 1, w_mesh)
    y = np.linspace(-1, 1, h_mesh)
    xx, yy = np.meshgrid(x, y)
    
    # Invert depth so foreground pops out
    # depth_arr is usually 1 for far, 0 for close? Depth anything gives 255 for close, 0 for far.
    # Let's check depth map. Actually let's just use it as Z.
    zz = depth_arr * 0.5  # depth scale
    
    vertices = np.stack([xx.flatten(), -yy.flatten(), zz.flatten()], axis=1)
    
    # Generate faces
    faces = []
    for i in range(h_mesh - 1):
        for j in range(w_mesh - 1):
            idx = i * w_mesh + j
            faces.append([idx, idx + w_mesh, idx + 1])
            faces.append([idx + 1, idx + w_mesh, idx + w_mesh + 1])
            
    mesh = trimesh.Trimesh(vertices=vertices, faces=faces)
    
    # UVs
    u = (xx.flatten() + 1) / 2
    v = 1 - (yy.flatten() + 1) / 2
    uvs = np.stack([u, v], axis=1)
    mesh.visual = trimesh.visual.TextureVisuals(uv=uvs, image=image)
    
    # Export
    mesh.export(out_path)
    print(f"Diorama saved to {out_path}")

if __name__ == "__main__":
    main()
