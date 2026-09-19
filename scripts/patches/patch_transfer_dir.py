import re

fp = "/home/juan/AuroraIA/application/bridge_server.py"
with open(fp, "r", encoding="utf-8") as f:
    code = f.read()

old_block = """        transfer_dir = os.path.join(workspace, ".transfer_to_client")
        if os.path.exists(transfer_dir):
            shutil.rmtree(transfer_dir, ignore_errors=True)
        os.makedirs(transfer_dir, exist_ok=True)"""

new_block = """        if not is_remote_workspace:
            transfer_dir = os.path.join(workspace, ".transfer_to_client")
            if os.path.exists(transfer_dir):
                shutil.rmtree(transfer_dir, ignore_errors=True)
            os.makedirs(transfer_dir, exist_ok=True)"""

if old_block in code:
    code = code.replace(old_block, new_block)
else:
    print("WARNING: Could not find old block to replace!")

with open(fp, "w", encoding="utf-8") as f:
    f.write(code)

print("Transfer dir logic patched!")
