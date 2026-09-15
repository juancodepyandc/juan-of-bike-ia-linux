import json, os, subprocess, time
from pathlib import Path

KAGGLE = "/home/juan/AuroraIA/cycle_app_venv/bin/kaggle"
kernel_dir = Path("/tmp/kaggle_max_3d")

script_code = """
import os, sys, gc, torch
from huggingface_hub import snapshot_download
from PIL import Image

cache = "/tmp/hub"

print("1. GENERATING IMAGE WITH FLUX...")
os.system("pip install -q diffusers accelerate transformers bitsandbytes sentencepiece protobuf")

from diffusers import FluxPipeline
pipe = FluxPipeline.from_pretrained("black-forest-labs/FLUX.1-schnell", torch_dtype=torch.bfloat16)
pipe.enable_sequential_cpu_offload()

prompt = "A high quality 3d diorama of Batman standing on a gargoyle overlooking Gotham city, dense city blocks, cinematic lighting, masterpiece, white background, single object focus"
image = pipe(prompt, num_inference_steps=4, guidance_scale=0.0).images[0]
image.save("input.jpg")

# Clear VRAM!
del pipe
gc.collect()
torch.cuda.empty_cache()

print("2. INSTALLING TRELLIS...")
os.system("git clone https://github.com/microsoft/TRELLIS.git /tmp/TRELLIS")
sys.path.insert(0, "/tmp/TRELLIS")
os.system("pip install -q ninja xformers trimesh PyMCubes easydict rembg onnxruntime")
os.system("pip install -q git+https://github.com/tatsy/torchmcubes.git")
os.system("pip install -q spconv-cu120")

print("3. DOWNLOADING TRELLIS MODELS...")
model_path = snapshot_download("microsoft/TRELLIS-image-large", cache_dir=cache)

print("4. RUNNING TRELLIS WITH MAX SETTINGS...")
from trellis.pipelines import TrellisImageTo3DPipeline
pipeline = TrellisImageTo3DPipeline.from_pretrained(model_path)
pipeline.cuda()

# MAX SETTINGS (50 steps instead of 12, higher resolution if supported)
outputs = pipeline.run(
    image,
    seed=42,
    formats=["glb"],
    preprocess_image=True,
    sparse_structure_sampler_params={"steps": 50, "cfg_strength": 7.5},
    slat_sampler_params={"steps": 50, "cfg_strength": 5.0},
)

outputs['glb'][0].export("/kaggle/working/batman_gotham_max_quality.glb")
print("GLB generated successfully!")
"""

(kernel_dir / "inference.py").write_text(script_code)
print("Pushing V2 kernel to Kaggle...")
subprocess.run([KAGGLE, "kernels", "push", "-p", str(kernel_dir)], check=True)
