import torch
from pathlib import Path
from diffusers import StableDiffusionXLPipeline, AutoencoderKL

out_dir = Path("/home/juan/AuroraIA/application/output/3d/benchmark_ultimate_complex_model/references")
out_dir.mkdir(parents=True, exist_ok=True)
out_file = out_dir / "master_concept.png"

print("Chargement SDXL pour le modèle benchmark ultra-complexe...")
vae = AutoencoderKL.from_pretrained(
    "madebyollin/sdxl-vae-fp16-fix",
    torch_dtype=torch.float32
)
pipe = StableDiffusionXLPipeline.from_pretrained(
    "stabilityai/stable-diffusion-xl-base-1.0",
    vae=vae,
    torch_dtype=torch.float32,
    use_safetensors=True
).to("cpu")

prompt = (
    "masterpiece, a single intricate celestial astrolabe dragon automaton, "
    "magnificent mechanical clockwork dragon perched on an ornate dark marble hexagonal pedestal, "
    "interlocking polished brass and damascus steel gears, exposed tourbillon escapement mechanism, "
    "glowing sapphire crystalline energy core inside openwork filigree ribcage, "
    "articulated dragon head with ruby optical sensors and curled baroque horns, "
    "mechanical wings with exposed brass struts and stained glass membrane panels, "
    "entire singular object centered in frame, three-quarter dynamic isometric studio view, "
    "isolated on plain solid neutral grey background, dramatic rim lighting, sharp focus, 8k resolution, trending on artstation"
)
neg_prompt = (
    "multiple objects, collage, duplicate dragons, scenery, landscape, forest, mountains, sky, "
    "floating parts, cutoff, cropped, blurry, low resolution, deformed, messy"
)

generator = torch.Generator("cpu").manual_seed(777)
print("Génération du concept maître...")
img = pipe(
    prompt=prompt,
    negative_prompt=neg_prompt,
    num_inference_steps=20,
    guidance_scale=8.0,
    generator=generator,
    height=1024,
    width=1024
).images[0]

img.save(str(out_file))
print(f"[OK] Concept maître ultra-complexe généré avec succès : {out_file}")
