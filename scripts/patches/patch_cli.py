import re
from pathlib import Path

cli_file = Path("aurora_cli.py")
content = cli_file.read_text()

try:
    token = Path("/home/juan/.cache/huggingface/token").read_text().strip()
except:
    token = ""

new_flux_code = f"""
from huggingface_hub import login
login('{token}')
"""

content = content.replace('from diffusers import FluxPipeline', new_flux_code + 'from diffusers import FluxPipeline')

cli_file.write_text(content)
