import base64, json, subprocess
from pathlib import Path

KAGGLE = "/home/juan/AuroraIA/cycle_app_venv/bin/kaggle"
kernel_dir = Path("/tmp/kaggle_happy_definitive")
kernel_dir.mkdir(exist_ok=True, parents=True)

# Image officielle avec AILES DÉPLOYÉES
img_bytes = Path("/tmp/happy_wings.png").read_bytes()
img_b64 = base64.b64encode(img_bytes).decode("ascii")

code = f"""
import os, sys, gc, base64, io, subprocess

print("=== 1. INSTALLATION INTEGRALE DE TOUTES LES DEPENDANCES OFFICIELLES TRELLIS ===")
# Exactement la liste exhaustive de setup.sh de Microsoft Trellis + plyfile
packages = [
    "plyfile", "pillow", "imageio", "imageio-ffmpeg", "tqdm", "easydict",
    "opencv-python-headless", "scipy", "ninja", "rembg", "onnxruntime",
    "trimesh", "open3d", "xatlas", "pyvista", "pymeshfix", "igraph",
    "transformers", "git+https://github.com/EasternJournalist/utils3d.git@9a4eb15e4021b67b12c460c7057d642626897ec8"
]

for pkg in packages:
    res = subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", "--no-cache-dir", pkg])
    print(f"Pkg {{pkg.split('/')[-1]}}: code {{res.returncode}}")

from PIL import Image

print("=== 2. CHARGEMENT DE HAPPY AVEC SES AILES DEPLOYEES ===")
img_data = base64.b64decode({img_b64!r})
image = Image.open(io.BytesIO(img_data)).convert("RGBA")
image.save("/kaggle/working/happy_wings_input.png")
print(f"Image chargée: taille={{image.size}}, mode={{image.mode}}")

print("=== 3. CONFIGURATION CLONE ET DEPOTS ===")
os.system("git clone https://github.com/microsoft/TRELLIS.git /tmp/TRELLIS")
sys.path.insert(0, "/tmp/TRELLIS")

import torch
print("CUDA disponible:", torch.cuda.is_available())
num_gpus = torch.cuda.device_count()
print(f"GPUs détectés: {{num_gpus}}")
for i in range(num_gpus):
    print(f"  GPU {{i}}: {{torch.cuda.get_device_name(i)}}")

from huggingface_hub import snapshot_download
from trellis.pipelines import TrellisImageTo3DPipeline

print("=== 4. TELECHARGEMENT DU MODELE TRELLIS ===")
model_path = snapshot_download("microsoft/TRELLIS-image-large", cache_dir="/tmp/hub")

print("=== 5. CHARGEMENT ET REPARTITION MULTI-GPU (2x T4) ===")
pipeline = TrellisImageTo3DPipeline.from_pretrained(model_path)
pipeline.cuda()

# Repartition VRAM multi-GPU réelle
if num_gpus >= 2 and hasattr(pipeline, 'models') and isinstance(pipeline.models, dict):
    keys = list(pipeline.models.keys())
    half = len(keys) // 2
    for k in keys[:half]:
        pipeline.models[k].to('cuda:0')
    for k in keys[half:]:
        pipeline.models[k].to('cuda:1')
    print(f"Modeles Trellis repartis: {{len(keys[:half])}} sur GPU 0, {{len(keys[half:])}} sur GPU 1")

print("=== 6. GENERATION 3D HAUTE QUALITE (50 STEPS) ===")
outputs = pipeline.run(
    image,
    seed=42,
    formats=["glb"],
    preprocess_image=True,
    sparse_structure_sampler_params={{"steps": 50, "cfg_strength": 7.5}},
    slat_sampler_params={{"steps": 50, "cfg_strength": 5.0}},
)

out_glb = "/kaggle/working/happy_wings_deployed_3d.glb"
outputs['glb'][0].export(out_glb)
size = os.path.getsize(out_glb)
print(f"=== 7. SUCCES TOTAL : GLB CREE ===\\nFichier: {{out_glb}}\\nTaille: {{size}} octets")
"""

meta = {
    "id": "evanpasdeloup/aurora-happy-wings-definitive",
    "title": "Aurora Happy Wings Definitive",
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

print("Pushing definitive Happy Wings kernel to Kaggle...")
res = subprocess.run([KAGGLE, "kernels", "push", "-p", str(kernel_dir)], capture_output=True, text=True)
print(res.stdout)
print(res.stderr)
