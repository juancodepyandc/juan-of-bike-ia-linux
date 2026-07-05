#!/usr/bin/env python3
"""
auto_tag_images.py
Uses CLIP zero-shot classification to automatically determine the view angle
of given input images (front, back, left, right, top, bottom).
"""

import sys
import json
import argparse
from pathlib import Path

try:
    import torch
    from PIL import Image
    from transformers import CLIPProcessor, CLIPModel
except ImportError:
    print(json.dumps({"error": "Transformers or Torch not installed."}))
    sys.exit(1)

# Labels for zero-shot classification
LABELS = [
    "front view of a character or object",
    "back view of a character or object, seen from behind",
    "left side profile view",
    "right side profile view",
    "top down view from above",
    "bottom up view from below"
]

LABEL_MAP = {
    0: "front",
    1: "back",
    2: "left",
    3: "right",
    4: "top",
    5: "bottom"
}

def tag_images(image_paths: list[str]) -> dict:
    device = "cuda" if torch.cuda.is_available() else "cpu"
    try:
        model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32").to(device)
        processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
    except Exception as e:
        return {"error": f"Failed to load CLIP: {e}"}

    results = {}
    for path_str in image_paths:
        path = Path(path_str)
        if not path.is_file():
            continue
        try:
            image = Image.open(path).convert("RGB")
            inputs = processor(text=LABELS, images=image, return_tensors="pt", padding=True).to(device)
            outputs = model(**inputs)
            logits_per_image = outputs.logits_per_image
            probs = logits_per_image.softmax(dim=1)
            best_idx = probs.argmax(dim=1).item()
            view_name = LABEL_MAP[best_idx]
            
            if view_name not in results:
                results[view_name] = str(path)
        except Exception as e:
            pass
            
    return {"ok": True, "tags": results}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--images", nargs="+", required=True)
    args = parser.parse_args()
    
    result = tag_images(args.images)
    print(json.dumps(result))

if __name__ == "__main__":
    main()
