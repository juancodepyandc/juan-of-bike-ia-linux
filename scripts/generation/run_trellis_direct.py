import sys
import os
import json
from pathlib import Path
sys.path.append(str(Path("application/python-services/aurora_hunyuan").resolve()))

from aurora_trellis_wrapper import generate_glb, is_available

def main():
    if not is_available():
        print("Trellis not available!")
        return

    components = ["caine", "tent", "ground"]
    base_dir = "application/output/3d/conversations/caine_scene"
    
    for comp in components:
        img_path = f"{base_dir}/{comp}.png"
        out_glb = f"{base_dir}/{comp}.glb"
        
        print(f"Generating {comp}...")
        try:
            res = generate_glb(img_path, out_glb)
            print(f"Result for {comp}: {res}")
        except Exception as e:
            print(f"Error on {comp}: {e}")

if __name__ == "__main__":
    main()
