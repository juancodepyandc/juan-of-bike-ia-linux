import sys
import argparse
import json
import urllib.request
import urllib.error
import urllib.parse
import time
import shutil
import os
from pathlib import Path

def queue_prompt(prompt_workflow):
    p = {"prompt": prompt_workflow}
    data = json.dumps(p).encode('utf-8')
    req = urllib.request.Request("http://127.0.0.1:8188/prompt", data=data)
    req.add_header('Content-Type', 'application/json')
    try:
        response = urllib.request.urlopen(req)
        return json.loads(response.read())
    except urllib.error.URLError as e:
        print(f"Error connecting to ComfyUI: {e}")
        try:
            print(e.read().decode())
        except:
            pass
        return None

def get_history(prompt_id):
    req = urllib.request.Request(f"http://127.0.0.1:8188/history/{prompt_id}")
    try:
        response = urllib.request.urlopen(req)
        return json.loads(response.read())
    except urllib.error.URLError:
        return None

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Input reference image")
    parser.add_argument("--output", required=True, help="Output PLY path")
    args = parser.parse_args()
    
    img_path = Path(args.input)
    out_path = Path(args.output)
    
    if not img_path.exists():
        print(f"Error: Input image {img_path} not found")
        sys.exit(1)
        
    run_id = out_path.stem
    
    comfy_in = Path("/home/juan/AuroraIA/modele/comfyui/input")
    comfy_in.mkdir(parents=True, exist_ok=True)
    comfy_img_name = f"{run_id}_input.png"
    shutil.copy(img_path, comfy_in / comfy_img_name)
    
    # We want to save inside ComfyUI output dir first, then copy to out_path
    comfy_out_dir = Path("/home/juan/AuroraIA/modele/comfyui/output")
    comfy_out_name = f"{run_id}_gaussians"
    
    workflow = {
        "1": {
            "inputs": {"image": comfy_img_name},
            "class_type": "LoadImage"
        },
        "2": {
            "inputs": {"images": ["1", 0], "target_size": 518, "strategy": "crop"},
            "class_type": "PreprocessImagesForHWM"
        },
        "3": {
            "inputs": {
                "model_name": "tencent/HunyuanWorld-Mirror",
                "device": "cuda",
                "precision": "fp16",
                "force_reload": False
            },
            "class_type": "LoadHunyuanWorldMirrorModel"
        },
        "4": {
            "inputs": {"model": ["3", 0], "images": ["2", 0], "batch_size": 16, "focal_length_mode": "auto", "seed": 42},
            "class_type": "HWMInference"
        },
        "5": {
            "inputs": {
                "gaussians": ["4", 5],
                "filepath": f"output/{comfy_out_name}.ply",
                "include_sh": True,
                "normalize_colors": False,
                "subsample_factor": 1,
                "filter_scale_percentile": 100.0
            },
            "class_type": "Save3DGaussians"
        }
    }
    
    res = queue_prompt(workflow)
    if not res:
        sys.exit(1)
        
    prompt_id = res['prompt_id']
    print(f"Tâche ComfyUI HunyuanWorld-Mirror lancée (ID: {prompt_id}). En attente de la génération 3D...")
    
    while True:
        history = get_history(prompt_id)
        if history and prompt_id in history:
            print("Génération 3D terminée dans ComfyUI !")
            break
        time.sleep(2)
        
    # Copy from ComfyUI output to final output
    generated_ply = comfy_out_dir / f"{comfy_out_name}.ply"
    if generated_ply.exists():
        out_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(generated_ply, out_path)
        print(f"Result copied to {out_path}")
    else:
        print(f"Error: Expected output {generated_ply} not found.")
        sys.exit(1)

if __name__ == "__main__":
    main()
