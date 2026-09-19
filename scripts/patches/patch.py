path = "/home/juan/AuroraIA/modele/comfyui/custom_nodes/ComfyUI-HunyuanWorld-Mirror/utils/inference.py"
with open(path, "r") as f:
    content = f.read()

import re
content = content.replace("from src.models.models.worldmirror import WorldMirror", """import sys\n        import os\n        node_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))\n        if node_dir not in sys.path:\n            sys.path.append(node_dir)\n        from src.models.models.worldmirror import WorldMirror""")

with open(path, "w") as f:
    f.write(content)
