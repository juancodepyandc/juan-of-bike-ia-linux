import json, os, subprocess
from pathlib import Path

KAGGLE = "/home/juan/AuroraIA/cycle_app_venv/bin/kaggle"
kernel_dir = Path("/tmp/kaggle_video_test")
kernel_dir.mkdir(exist_ok=True)

script_code = """
import os, gc, torch
print("Installing diffusers and decord...")
os.system("pip install -q diffusers accelerate transformers imageio[ffmpeg] sentencepiece protobuf")

from diffusers import CogVideoXPipeline
from diffusers.utils import export_to_video

prompt = "A cinematic tracking shot of a futuristic cyberpunk city at night, neon lights reflecting on wet streets, flying cars zooming by, highly detailed, photorealistic, 4k resolution, masterpiece."

print("Loading CogVideoX-2b...")
pipe = CogVideoXPipeline.from_pretrained(
    "THUDM/CogVideoX-2b", 
    torch_dtype=torch.float16
)
# Offload to save VRAM on T4
pipe.enable_model_cpu_offload()

print("Generating video at MAX quality...")
# Max quality settings for CogVideoX
video = pipe(
    prompt=prompt,
    num_videos_per_prompt=1,
    num_inference_steps=50,
    num_frames=49,
    guidance_scale=6.0,
    generator=torch.Generator(device="cuda").manual_seed(42),
).frames[0]

output_path = "/kaggle/working/cyberpunk_city_max_quality.mp4"
export_to_video(video, output_path, fps=8)
print(f"Video successfully saved to {output_path}")
"""

metadata = {
    "id": "evanpasdeloup/aurora-video-test",
    "title": "Aurora Video Test",
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

print("Pushing Video kernel to Kaggle...")
subprocess.run([KAGGLE, "kernels", "push", "-p", str(kernel_dir)], check=True)
print("Video test launched on Kaggle!")
