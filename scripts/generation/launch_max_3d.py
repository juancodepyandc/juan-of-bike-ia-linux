import json, os, subprocess, time, zipfile, io, base64
from pathlib import Path
import json

KAGGLE = "/home/juan/AuroraIA/cycle_app_venv/bin/kaggle"
job_id = "max_3d_test"
kernel_dir = Path("/tmp/kaggle_max_3d")
kernel_dir.mkdir(exist_ok=True)

script_code = """
import os, sys, torch
from huggingface_hub import snapshot_download
from PIL import Image

# 1. Download Trellis
cache = "/tmp/hub"
model_path = snapshot_download("microsoft/TRELLIS-image-large", cache_dir=cache)
dinov3_path = snapshot_download("camenduru/dinov3-vitl16-pretrain-lvd1689m", cache_dir=cache)

# We need Trellis code. We can clone it.
os.system("git clone https://github.com/microsoft/TRELLIS.git /tmp/TRELLIS")
sys.path.insert(0, "/tmp/TRELLIS")

# Install requirements
os.system("pip install -q ninja xformers trimesh PyMCubes easydict rembg onnxruntime")
os.system("pip install -q git+https://github.com/tatsy/torchmcubes.git")

from trellis.pipelines import TrellisImageTo3DPipeline

pipeline = TrellisImageTo3DPipeline.from_pretrained(model_path)
pipeline.cuda()

# Generate image from prompt using an API or a small model, OR just use a downloaded image.
# We'll use a public image URL of a city diorama with a character.
os.system("wget -qO input.jpg 'https://image.civitai.com/xG1nkqKTMzGDvpLrqFT7WA/c2c510db-094f-4cc5-bd91-3e5e4125f4ea/width=1024/input.jpeg' || wget -qO input.jpg 'https://images.unsplash.com/photo-1605806616949-1e87b487cb2a?q=80&w=1024'")
image = Image.open("input.jpg")

# MAX SETTINGS
outputs = pipeline.run(
    image,
    seed=42,
    formats=["glb"],
    preprocess_image=True,
    sparse_structure_sampler_params={"steps": 50, "cfg_strength": 12.0},
    slat_sampler_params={"steps": 50, "cfg_strength": 8.0},
)

outputs['glb'][0].export("/kaggle/working/max_quality_scene.glb")
print("GLB generated successfully!")
"""

metadata = {
    "id": "evanpasdeloup/aurora-max-3d",
    "title": "Aurora Max 3D Test",
    "code_file": "inference.py",
    "language": "python",
    "kernel_type": "script",
    "is_private": "true",
    "enable_gpu": "true",
    "enable_internet": "true",
    "machine_shape": "gpu_t4_x2"
}

(kernel_dir / "kernel-metadata.json").write_text(json.dumps(metadata))
(kernel_dir / "inference.py").write_text(script_code)

print("Pushing kernel to Kaggle...")
subprocess.run([KAGGLE, "kernels", "push", "-p", str(kernel_dir)], check=True)
print("Kernel pushed! You can check the Kaggle website for the result.")
