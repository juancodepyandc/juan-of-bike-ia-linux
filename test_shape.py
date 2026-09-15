import json, subprocess
from pathlib import Path

KAGGLE = "/home/juan/AuroraIA/cycle_app_venv/bin/kaggle"
tmp = Path("/tmp/shape_probe")
tmp.mkdir(parents=True, exist_ok=True)

(tmp / "probe.py").write_text("""
import torch, subprocess
print("TORCH CUDA:", torch.cuda.is_available())
if torch.cuda.is_available():
    print("DEVICE NAME:", torch.cuda.get_device_name(0))
    print("DEVICE COUNT:", torch.cuda.device_count())
subprocess.run(["nvidia-smi"])
""")

meta = {
    "id": "evanpasdeloup/aurora-probe-gpu",
    "title": "Aurora Probe GPU",
    "code_file": "probe.py",
    "language": "python",
    "kernel_type": "script",
    "is_private": "true",
    "enable_gpu": "true",
    "enable_internet": "true",
    "machine_shape": "NvidiaTeslaT4"
}
(tmp / "kernel-metadata.json").write_text(json.dumps(meta))
subprocess.run([KAGGLE, "kernels", "push", "-p", str(tmp)])
