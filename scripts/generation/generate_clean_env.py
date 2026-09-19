import sys
from diffusers import DiffusionPipeline
import torch

def main():
    pipe = DiffusionPipeline.from_pretrained("stabilityai/stable-diffusion-xl-base-1.0", torch_dtype=torch.float16)
    pipe.enable_model_cpu_offload()
    prompt = "A photorealistic, highly detailed, clean European city street in the afternoon, realistic lighting, highly consistent perspective"
    image = pipe(prompt, num_inference_steps=4, guidance_scale=0.0).images[0]
    out_path = "application/output/3d/conversations/test_monobloc_world/clean_city.png"
    image.save(out_path)
    print(f"Saved to {out_path}")

if __name__ == "__main__":
    main()
