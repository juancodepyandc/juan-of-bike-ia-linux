import torch
from PIL import Image
from torchvision import transforms
from transformers import AutoModelForImageSegmentation

device = "cuda" if torch.cuda.is_available() else "cpu"
birefnet = AutoModelForImageSegmentation.from_pretrained("ZhengPeng7/BiRefNet", trust_remote_code=True).to(device).half()
birefnet.eval()

img_path = "/home/juan/AuroraIA/application/output/3d/01_fairy_tail_guild_hall/references/master_concept.png"
img = Image.open(img_path).convert("RGB")

tform = transforms.Compose([
    transforms.Resize((1024, 1024)),
    transforms.ToTensor(),
    transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
])

inp = tform(img).unsqueeze(0).to(device).half()
with torch.no_grad():
    pred = birefnet(inp)[-1].sigmoid().cpu()[0, 0].numpy()

# Masque net
mask = Image.fromarray((pred * 255).astype("uint8")).resize(img.size, Image.Resampling.BILINEAR)

# Sauvegarder en RGBA avec le masque BiRefNet ultra-précis
rgba = img.copy()
rgba.putalpha(mask)
rgba.save(img_path)
print(f"[OK] BiRefNet matte appliqué sans découpe d'information : {img_path}")
