import os
import sys
import time
import json
import uuid
import subprocess
from pathlib import Path

# Paths
ROOT = Path("/home/juan/AuroraIA")
OUTPUTS = ROOT / "Outputs" / "CLI"
OUTPUTS.mkdir(parents=True, exist_ok=True)
KAGGLE_BIN = ROOT / "cycle_app_venv/bin/kaggle"

class AuroraCLI:
    def __init__(self):
        self.active_model = "image_local" # Default
        self.models = {
            "image_local": "Génération d'images locale (FLUX.2-dev - Qualité Max)",
            "3d_cloud": "Génération 3D sur Kaggle (Trellis - L4x2 48GB VRAM)",
            "video_cloud": "Génération Vidéo sur Kaggle (CogVideoX - L4x2 48GB VRAM)",
            "code_expert": "LLM Expert sur Kaggle (DeepSeek - L4x2 48GB VRAM)"
        }
    
    def clear(self):
        os.system('cls' if os.name == 'nt' else 'clear')
        
    def print_header(self):
        self.clear()
        print("="*60)
        print(" 🌌 AURORA IA - INTERFACE TERMINAL EXPERT 🌌")
        print("="*60)
        print(f" Modèle actif : \033[92m{self.active_model}\033[0m - {self.models.get(self.active_model, '')}")
        print(" Commandes disponibles :")
        print("   /model <nom>  : Changer de modèle (ex: /model video_cloud)")
        print("   /list         : Lister les modèles disponibles")
        print("   /exit         : Quitter l'interface")
        print("   [Texte]       : Envoyer un prompt au modèle actif")
        print("="*60)
        print()

    def run(self):
        self.print_header()
        while True:
            try:
                user_input = input("\033[94mAurora > \033[0m").strip()
            except (KeyboardInterrupt, EOFError):
                break
                
            if not user_input:
                continue
                
            if user_input.startswith("/"):
                self.handle_command(user_input)
            else:
                self.process_prompt(user_input)

    def handle_command(self, cmd_line):
        parts = cmd_line.split(" ", 1)
        cmd = parts[0].lower()
        
        if cmd == "/exit":
            print("Fermeture de l'interface Aurora.")
            sys.exit(0)
        elif cmd == "/list":
            print("\nModèles disponibles :")
            for k, v in self.models.items():
                prefix = " * " if k == self.active_model else "   "
                print(f"{prefix}\033[93m{k}\033[0m : {v}")
            print()
        elif cmd == "/model":
            if len(parts) < 2:
                print("Erreur: Spécifiez un nom de modèle (ex: /model video_cloud)")
                return
            target = parts[1].strip()
            if target in self.models:
                self.active_model = target
                self.print_header()
            else:
                print(f"Erreur: Modèle '{target}' inconnu. Tapez /list pour voir les options.")
        else:
            print(f"Commande '{cmd}' inconnue.")

    def process_prompt(self, prompt):
        print(f"\n\033[93m[Traitement en cours via {self.active_model}]\033[0m")
        job_id = uuid.uuid4().hex[:8]
        
        if self.active_model == "image_local":
            self.generate_image_local(prompt, job_id)
        elif self.active_model == "3d_cloud":
            self.generate_3d_cloud(prompt, job_id)
        elif self.active_model == "video_cloud":
            self.generate_video_cloud(prompt, job_id)
        elif self.active_model == "code_expert":
            print("Le modèle conversationnel Cloud est en cours d'intégration.")
        else:
            print("Modèle non implémenté.")
            
    def generate_image_local(self, prompt, job_id):
        print("🔧 Initialisation de Flux (Paramètres MAX)...")
        script = f"""
import torch

import os
os.environ['HF_TOKEN'] = 'hf_oauth_eyJhbGciOiJFZERTQSIsImtpZCI6IjVHZDBvd0g5MTM2eDZjc1FvbE1zcktNWUZoRVFoUm5PVVVybEpjOUhaUEEifQ.eyJzY29wZSI6WyJtYW5hZ2UtcmVwb3MiLCJ3cml0ZS1yZXBvcyIsInJlYWQtcmVwb3MiLCJnYXRlZC1yZXBvcyIsImNvbnRyaWJ1dGUtcmVwb3MiLCJ3cml0ZS1jb2xsZWN0aW9ucyIsInJlYWQtY29sbGVjdGlvbnMiLCJvcGVuaWQiLCJ3cml0ZS1kaXNjdXNzaW9ucyIsImluZmVyZW5jZS1hcGkiLCJqb2JzIiwid2ViaG9va3MiLCJyZWFkLWJpbGxpbmciLCJyZWFkLW1jcCJdLCJhdWQiOiJodHRwczovL2h1Z2dpbmdmYWNlLmNvIiwiY2xpZW50X2lkIjoiMjZiZTZiMDktOTFjNS00N2RhLTk4NjEtZDJkMmJiN2E3ZTM2Iiwic2Vzc2lvbklkIjoiNmE3Mzk0ZWZiMTIyMDA3MzBhYmU0MGFhIiwiaWF0IjoxNzg4NzUyMTkwLCJqdGkiOiJmN2JmNDdmZS05OWQyLTQ2NmUtOTNmOC01YWU4Njk3M2QxZGIiLCJzdWIiOiI2OTliYThhZTIzZmJjNjgyODQ4NWZlZTciLCJleHAiOjE3OTEzNDQxOTAsImlzcyI6Imh0dHBzOi8vaHVnZ2luZ2ZhY2UuY28ifQ.Mr58Fx_IKC56oSS7cv5SjxphG1wXdkb3KdU7eNCHEbd_vtvvxQ3VlNNFLe5OoWLvwupP8Jzj0FroWkyU0aWPAQ'
from diffusers import FluxPipeline
print("Chargement du modèle...")
pipe = FluxPipeline.from_pretrained("Niansuh/FLUX.1-schnell", torch_dtype=torch.bfloat16)
pipe.enable_sequential_cpu_offload()
print("Génération de l'image (4 steps, cfg 0)...")
image = pipe({prompt!r}, num_inference_steps=4, guidance_scale=0.0).images[0]
out = "{OUTPUTS}/image_{job_id}.png"
image.save(out)
print(f"\\n✅ Image sauvegardée : {{out}}")
"""
        with open("/tmp/temp_flux.py", "w") as f:
            f.write(script)
        subprocess.run([sys.executable, "/tmp/temp_flux.py"])

    def generate_video_cloud(self, prompt, job_id):
        print("☁️ Préparation du job vidéo pour Kaggle...")
        slug = f"aurora-video-{job_id}"
        kernel_dir = Path(f"/tmp/kaggle_{job_id}")
        kernel_dir.mkdir(exist_ok=True)
        
        code = f"""
import os, torch
os.system("pip install -q diffusers accelerate transformers imageio[ffmpeg] sentencepiece protobuf")
from diffusers import CogVideoXPipeline
from diffusers.utils import export_to_video

pipe = CogVideoXPipeline.from_pretrained("THUDM/CogVideoX-2b", torch_dtype=torch.float16)
pipe.enable_model_cpu_offload()

video = pipe(
    prompt={prompt!r},
    num_videos_per_prompt=1,
    num_inference_steps=50,
    num_frames=49,
    guidance_scale=6.0,
    generator=torch.Generator(device="cuda").manual_seed(42),
).frames[0]

export_to_video(video, "/kaggle/working/output_video.mp4", fps=8)
"""
        metadata = {
            "id": f"evanpasdeloup/{slug}",
            "title": f"Aurora Video {job_id}",
            "code_file": "inference.py",
            "language": "python",
            "kernel_type": "script",
            "is_private": "true",
            "enable_gpu": "true",
            "enable_internet": "true",
            "machine_shape": "NvidiaTeslaT4"
        }
        (kernel_dir / "kernel-metadata.json").write_text(json.dumps(metadata))
        (kernel_dir / "inference.py").write_text(code)
        
        subprocess.run([str(KAGGLE_BIN), "kernels", "push", "-p", str(kernel_dir)], check=True)
        print(f"\\n✅ Job Kaggle lancé ! (ID: {slug})")
        print(f"👉 Suivez l'avancement : https://www.kaggle.com/code/evanpasdeloup/{slug}")
        print("Une fois terminé, récupérez la vidéo sur l'interface Kaggle.")

    def generate_3d_cloud(self, prompt, job_id):
        print("☁️ Préparation du job 3D (Trellis) pour Kaggle...")
        slug = f"aurora-3d-{job_id}"
        kernel_dir = Path(f"/tmp/kaggle_{job_id}")
        kernel_dir.mkdir(exist_ok=True)
        
        code = f"""
import os, sys, gc, torch
os.system("pip install -q diffusers accelerate transformers bitsandbytes sentencepiece protobuf")

import os
os.environ['HF_TOKEN'] = 'hf_oauth_eyJhbGciOiJFZERTQSIsImtpZCI6IjVHZDBvd0g5MTM2eDZjc1FvbE1zcktNWUZoRVFoUm5PVVVybEpjOUhaUEEifQ.eyJzY29wZSI6WyJtYW5hZ2UtcmVwb3MiLCJ3cml0ZS1yZXBvcyIsInJlYWQtcmVwb3MiLCJnYXRlZC1yZXBvcyIsImNvbnRyaWJ1dGUtcmVwb3MiLCJ3cml0ZS1jb2xsZWN0aW9ucyIsInJlYWQtY29sbGVjdGlvbnMiLCJvcGVuaWQiLCJ3cml0ZS1kaXNjdXNzaW9ucyIsImluZmVyZW5jZS1hcGkiLCJqb2JzIiwid2ViaG9va3MiLCJyZWFkLWJpbGxpbmciLCJyZWFkLW1jcCJdLCJhdWQiOiJodHRwczovL2h1Z2dpbmdmYWNlLmNvIiwiY2xpZW50X2lkIjoiMjZiZTZiMDktOTFjNS00N2RhLTk4NjEtZDJkMmJiN2E3ZTM2Iiwic2Vzc2lvbklkIjoiNmE3Mzk0ZWZiMTIyMDA3MzBhYmU0MGFhIiwiaWF0IjoxNzg4NzUyMTkwLCJqdGkiOiJmN2JmNDdmZS05OWQyLTQ2NmUtOTNmOC01YWU4Njk3M2QxZGIiLCJzdWIiOiI2OTliYThhZTIzZmJjNjgyODQ4NWZlZTciLCJleHAiOjE3OTEzNDQxOTAsImlzcyI6Imh0dHBzOi8vaHVnZ2luZ2ZhY2UuY28ifQ.Mr58Fx_IKC56oSS7cv5SjxphG1wXdkb3KdU7eNCHEbd_vtvvxQ3VlNNFLe5OoWLvwupP8Jzj0FroWkyU0aWPAQ'
from diffusers import FluxPipeline
pipe = FluxPipeline.from_pretrained("Niansuh/FLUX.1-schnell", torch_dtype=torch.bfloat16)
pipe.enable_sequential_cpu_offload()

image = pipe({prompt!r}, num_inference_steps=4, guidance_scale=0.0).images[0]
del pipe
gc.collect()
torch.cuda.empty_cache()

os.system("pip install -q --upgrade --no-cache-dir 'pillow>=10.4.0' 'torchvision>=0.19.0'")
os.system("git clone https://github.com/microsoft/TRELLIS.git /tmp/TRELLIS")
sys.path.insert(0, "/tmp/TRELLIS")
os.system("pip install -q ninja xformers trimesh PyMCubes easydict rembg onnxruntime")
os.system("pip install -q git+https://github.com/tatsy/torchmcubes.git spconv-cu120")

from huggingface_hub import snapshot_download
from trellis.pipelines import TrellisImageTo3DPipeline
model_path = snapshot_download("microsoft/TRELLIS-image-large", cache_dir="/tmp/hub")
pipeline = TrellisImageTo3DPipeline.from_pretrained(model_path)
pipeline.cuda()

outputs = pipeline.run(
    image, seed=42, formats=["glb"], preprocess_image=True,
    sparse_structure_sampler_params={{"steps": 50, "cfg_strength": 7.5}},
    slat_sampler_params={{"steps": 50, "cfg_strength": 5.0}},
)
outputs['glb'][0].export("/kaggle/working/output_3d.glb")
"""
        metadata = {
            "id": f"evanpasdeloup/{slug}",
            "title": f"Aurora 3D {job_id}",
            "code_file": "inference.py",
            "language": "python",
            "kernel_type": "script",
            "is_private": "true",
            "enable_gpu": "true",
            "enable_internet": "true",
            "machine_shape": "NvidiaTeslaT4"
        }
        (kernel_dir / "kernel-metadata.json").write_text(json.dumps(metadata))
        (kernel_dir / "inference.py").write_text(code)
        
        subprocess.run([str(KAGGLE_BIN), "kernels", "push", "-p", str(kernel_dir)], check=True)
        print(f"\\n✅ Job Kaggle lancé ! (ID: {slug})")
        print(f"👉 Suivez l'avancement : https://www.kaggle.com/code/evanpasdeloup/{slug}")
        print("Une fois terminé, récupérez le GLB sur l'interface Kaggle.")

if __name__ == "__main__":
    cli = AuroraCLI()
    cli.run()
