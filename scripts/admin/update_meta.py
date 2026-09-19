import json
from pathlib import Path
kernel_dir = Path("/tmp/kaggle_max_3d")
m = json.loads((kernel_dir / "kernel-metadata.json").read_text())
m["id"] = "evanpasdeloup/aurora-max-3d-v2"
m["title"] = "Aurora Max 3D Test V2"
(kernel_dir / "kernel-metadata.json").write_text(json.dumps(m))
