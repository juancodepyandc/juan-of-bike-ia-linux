import os, glob

bridge_file = "application/bridge_server.py"
routes_dir = "application/routes/"

with open(bridge_file, "r", encoding="utf-8") as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    if "from routes." in line or "app.register_blueprint" in line or "# --- Refactored to" in line or "Error registering" in line or "--- All Blueprint Registrations ---" in line:
        continue
    new_lines.append(line)

entry_idx = -1
for i, line in enumerate(new_lines):
    if "app.run(" in line:
        entry_idx = i - 1
        break

registrations = []
for file in glob.glob(routes_dir + "*.py"):
    if "__init__" in file: continue
    mod_name = os.path.basename(file)[:-3]
    bp_name = mod_name
    if mod_name.endswith("_routes"):
        bp_name = mod_name[:-7]
    elif mod_name.endswith("_bp_routes"):
        bp_name = mod_name[:-10] + "_bp"
    
    with open(file, "r") as bf:
        content = bf.read()
        import re
        m = re.search(r"(\w+)\s*=\s*Blueprint", content)
        if m:
            bp_name = m.group(1)
            
    registrations.append(f"        try:\n            from routes.{mod_name} import {bp_name}\n            app.register_blueprint({bp_name})\n        except Exception as e:\n            print(f'Error registering {bp_name}: {{e}}')\n")

new_lines.insert(entry_idx, "        # --- All Blueprint Registrations ---\n" + "".join(registrations) + "\n")

with open(bridge_file, "w", encoding="utf-8") as f:
    f.writelines(new_lines)
