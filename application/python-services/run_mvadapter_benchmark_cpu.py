import sys
import os
import subprocess
from pathlib import Path
from PIL import Image

project_dir = Path("/home/juan/AuroraIA/application/output/3d/benchmark_ultimate_complex_model")
refs_dir = project_dir / "references"
master_img_path = refs_dir / "master_concept.png"
strip_out_path = refs_dir / "multiview_consistent_strip.png"

cmd = [
    "/home/juan/.local/opt/miniforge3/envs/mvadapter/bin/python",
    "/home/juan/.local/share/auroraia/external/MV-Adapter/scripts/inference_i2mv_sdxl.py",
    "--image", str(master_img_path),
    "--output", str(strip_out_path),
    "--device", "cpu",
    "--num_inference_steps", "20",
    "--seed", "777"
]

env_vars = os.environ.copy()
env_vars["PYTHONPATH"] = "/home/juan/.local/share/auroraia/external/MV-Adapter"

print("Lancement MV-Adapter sur CPU (100% garanti sans OOM)...")
res = subprocess.run(cmd, env=env_vars, capture_output=True, text=True)
print(res.stdout)
if res.returncode != 0:
    print(f"Erreur MV-Adapter : {res.stderr}")
else:
    strip = Image.open(str(strip_out_path))
    sw, sh = strip.size
    vw = sw // 6
    vnames = [
        "view_01_front.png",
        "view_02_front_right.png",
        "view_03_right.png",
        "view_04_back.png",
        "view_05_left.png",
        "view_06_front_left.png"
    ]
    for i, vn in enumerate(vnames):
        strip.crop((i * vw, 0, (i + 1) * vw, sh)).save(str(refs_dir / vn))
        print(f"  [OK] {vn} extrait avec succès")
    print("[OK] Planche 6 vues strictement cohérentes générée !")
