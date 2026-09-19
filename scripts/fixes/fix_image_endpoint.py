import re

# 1. Fix bridge_server.py
fp = "/home/juan/AuroraIA/application/bridge_server.py"
with open(fp, "r", encoding="utf-8") as f:
    code = f.read()

old_url = '"http://127.0.0.1:3001/api/comfyui/image"'
new_url = '"http://127.0.0.1:3001/api/aurora/image/generate"'

if old_url in code:
    code = code.replace(old_url, new_url)
    with open(fp, "w", encoding="utf-8") as f:
        f.write(code)
    print("Fixed bridge_server.py")
else:
    print("WARNING: Could not find old_url in bridge_server.py!")

# 2. Fix aurora_native_mcp.py
fp = "/home/juan/AuroraIA/application/aurora_native_mcp.py"
with open(fp, "r", encoding="utf-8") as f:
    code = f.read()

if old_url in code:
    code = code.replace(old_url, new_url)
    with open(fp, "w", encoding="utf-8") as f:
        f.write(code)
    print("Fixed aurora_native_mcp.py")
else:
    print("WARNING: Could not find old_url in aurora_native_mcp.py!")
