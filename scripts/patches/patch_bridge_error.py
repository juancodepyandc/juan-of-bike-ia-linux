import sys

fp = "/home/juan/AuroraIA/application/bridge_server.py"
with open(fp, "r", encoding="utf-8") as f:
    code = f.read()

# 1. Move the try block up
old_code = """    import shutil
    transfer_dir = os.path.join(workspace, ".transfer_to_client")
    if os.path.exists(transfer_dir):
        shutil.rmtree(transfer_dir)
    os.makedirs(transfer_dir, exist_ok=True)
    
    try:"""

new_code = """    try:
        import shutil
        # Safe fallback if workspace is an invalid Mac path on Linux
        if not workspace.startswith("/") or not os.path.exists(os.path.dirname(workspace)):
            workspace = "/home/juan"
            mission["workspace"] = workspace
            
        transfer_dir = os.path.join(workspace, ".transfer_to_client")
        if os.path.exists(transfer_dir):
            shutil.rmtree(transfer_dir, ignore_errors=True)
        os.makedirs(transfer_dir, exist_ok=True)"""

code = code.replace(old_code, new_code)

with open(fp, "w", encoding="utf-8") as f:
    f.write(code)

print("Bridge patched!")
