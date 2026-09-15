path = "/home/juan/AuroraIA/modele/comfyui/custom_nodes/ComfyUI_HunyuanWorldnode/__init__.py"
with open(path, "r") as f:
    content = f.read()

content = content.replace(
    "texture_pipeline = Hunyuan3DPaintPipeline.from_pretrained(model_name, trust_remote_code=True)",
    "texture_pipeline = Hunyuan3DPaintPipeline.from_pretrained(model_name)"
)
with open(path, "w") as f:
    f.write(content)
