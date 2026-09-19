import torch
from diffusers import FluxPipeline
from pathlib import Path

out_dir = Path("/home/juan/AuroraIA/Outputs/CLI")
out_dir.mkdir(parents=True, exist_ok=True)
out_img = out_dir / "happy_fairy_tail.png"

print("Loading local Flux...")
pipe = FluxPipeline.from_pretrained("black-forest-labs/FLUX.1-schnell", torch_dtype=torch.bfloat16)
pipe.enable_sequential_cpu_offload()

prompt = "A photorealistic, highly detailed 3D render of Happy the blue flying cat from Fairy Tail, with his white angel wings fully deployed, soaring gracefully, majestic cinematic lighting, masterpiece, white background, single object focus, perfect anatomy."
print(f"Generating image locally: {prompt}")
image = pipe(prompt, num_inference_steps=4, guidance_scale=0.0).images[0]
image.save(out_img)
print(f"SAVED: {out_img}")
