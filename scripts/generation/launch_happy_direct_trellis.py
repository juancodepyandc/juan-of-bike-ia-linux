import base64, json, subprocess
from pathlib import Path

KAGGLE = "/home/juan/AuroraIA/cycle_app_venv/bin/kaggle"
kernel_dir = Path("/tmp/kaggle_happy_trellis")
kernel_dir.mkdir(exist_ok=True, parents=True)

img_bytes = Path("/tmp/happy_official.png").read_bytes()
img_b64 = base64.b64encode(img_bytes).decode("ascii")

code = f"""
import os, sys, gc, base64, io
from PIL import Image

print("Extracting canonical reference image...")
img_data = base64.b64decode({img_b64!r})
image = Image.open(io.BytesIO(img_data)).convert("RGBA")
image.save("/kaggle/working/input_happy.png")
print(f"Image ready: {{image.size}}, {{image.mode}}")

print("Cloning and installing Trellis dependencies...")
os.system("git clone https://github.com/microsoft/TRELLIS.git /tmp/TRELLIS")
sys.path.insert(0, "/tmp/TRELLIS")
os.system("pip install -q ninja xformers trimesh PyMCubes easydict rembg onnxruntime")
os.system("pip install -q git+https://github.com/tatsy/torchmcubes.git spconv-cu120")

import torch
print("CUDA Available:", torch.cuda.is_available())
if torch.cuda.is_available():
    print("GPU:", torch.cuda.get_device_name(0), "Count:", torch.cuda.device_count())

from huggingface_hub import snapshot_download
from trellis.pipelines import TrellisImageTo3DPipeline

print("Downloading Trellis weights from HuggingFace...")
model_path = snapshot_download("microsoft/TRELLIS-image-large", cache_dir="/tmp/hub")

print("Loading Trellis Pipeline on GPU...")
pipeline = TrellisImageTo3DPipeline.from_pretrained(model_path)
pipeline.cuda()

print("Generating 3D model with maximum sampling steps...")
outputs = pipeline.run(
    image,
    seed=42,
    formats=["glb"],
    preprocess_image=True,
    sparse_structure_sampler_params={{"steps": 50, "cfg_strength": 7.5}},
    slat_sampler_params={{"steps": 50, "cfg_strength": 5.0}},
)

out_glb = "/kaggle/working/happy_fairy_tail_3d.glb"
outputs['glb'][0].export(out_glb)
print(f"SUCCESS: Exported 3D GLB to {{out_glb}} (Size: {{os.path.getsize(out_glb)}} bytes)")
"""

meta = {
    "id": "evanpasdeloup/aurora-happy-trellis-3d",
    "title": "Aurora Happy Trellis 3D",
    "code_file": "inference.py",
    "language": "python",
    "kernel_type": "script",
    "is_private": "true",
    "enable_gpu": "true",
    "enable_internet": "true",
    "machine_shape": "NvidiaTeslaT4"
}

(kernel_dir / "kernel-metadata.json").write_text(json.dumps(meta))
(kernel_dir / "inference.py").write_text(code)

print("Pushing kernel to Kaggle...")
res = subprocess.run([KAGGLE, "kernels", "push", "-p", str(kernel_dir)], capture_output=True, text=True)
print(res.stdout)
print(res.stderr)
