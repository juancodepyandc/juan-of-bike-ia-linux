import os
import re

file_path = "/home/juan/AuroraIA/application/bridge_server.py"
with open(file_path, "r", encoding="utf-8") as f:
    code = f.read()

# Replace the read_file and write_file security checks dynamically
def replacer(match):
    return match.group(0).replace(
        'if not abs_path.startswith(abs_workspace):',
        'is_full_auth = (mission.get("permissions", "").upper() == "AUTONOMOUS")\n                            if not is_full_auth and not abs_path.startswith(abs_workspace):'
    ).replace(
        "L'accès en dehors du dossier de travail (workspace) est interdit.",
        "L'accès en dehors du dossier de travail nécessite le niveau de permission AUTONOMOUS."
    )

new_code = re.sub(r'elif t_name == "write_file":.*?elif t_name == "read_file":.*?(?=elif t_name == "spawn_agent"|elif t_name == "finish")', replacer, code, flags=re.DOTALL)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(new_code)

print("Permissions applied via regex")
