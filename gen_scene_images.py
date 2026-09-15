import torch
from diffusers import DiffusionPipeline
import os

def main():
    os.makedirs("application/output/3d/conversations/caine_scene", exist_ok=True)
    print("Loading SDXL...")
    pipe = DiffusionPipeline.from_pretrained(
        "stabilityai/stable-diffusion-xl-base-1.0",
        torch_dtype=torch.float16,
        use_safetensors=True,
        variant="fp16"
    )
    pipe.to("cuda")
    
    prompts = {
        "caine": "A 3D render of Caine from the amazing digital circus, a floating jaw with eyeballs inside, wearing a red suit and top hat, holding a cane, full body, isolated on pure white background, masterpiece",
        "tent": "A 3D render of a colorful circus tent, red and yellow stripes, isolated on pure white background, front view, masterpiece",
        "ground": "A 3D render of a circular floating grassy ground platform with some small rocks, isolated on pure white background, masterpiece"
    }
    
    for name, p in prompts.items():
        print(f"Generating {name}...")
        image = pipe(p, num_inference_steps=25).images[0]
        image.save(f"application/output/3d/conversations/caine_scene/{name}.png")

if __name__ == "__main__":
    main()
