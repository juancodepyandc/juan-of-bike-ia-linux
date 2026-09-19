import sys
import os
from pathlib import Path
sys.path.append(str(Path("application/python-services").resolve()))

def main():
    import subprocess
    
    components = ["caine", "tent", "ground"]
    base_dir = "application/output/3d/conversations/caine_scene"
    
    for comp in components:
        img_path = f"{base_dir}/{comp}.png"
        out_dir = f"{base_dir}/{comp}_3d"
        os.makedirs(out_dir, exist_ok=True)
        
        print(f"Running Trellis for {comp}...")
        
        # Call aurora_3d_pipeline with --image to force Trellis to use the existing image
        cmd = [
            "/home/juan/AuroraIA/modele/comfyui/venv/bin/python",
            "application/python-services/aurora_3d_pipeline.py",
            "--prompt", f"dummy {comp}",
            "--run-id", f"caine_scene_{comp}",
            "--output-dir", out_dir,
            "--image", img_path,
            "--engine", "trellis",
            "--single-view",
            "--no-scene"
        ]
        
        p = subprocess.run(cmd, capture_output=True, text=True)
        print(f"Finished {comp}. Return code: {p.returncode}")
        
        # Copy the resulting glb to the main dir
        import shutil
        glb_src = f"{out_dir}/caine_scene_{comp}/caine_scene_{comp}_mesh.glb"
        if os.path.exists(glb_src):
            shutil.copy(glb_src, f"{base_dir}/{comp}.glb")
            print(f"Saved {comp}.glb")
        else:
            print(f"Failed to find {glb_src}")
            print(p.stdout)
            print(p.stderr)

if __name__ == "__main__":
    main()
