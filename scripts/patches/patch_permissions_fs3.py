import os

file_path = "/home/juan/AuroraIA/application/bridge_server.py"
with open(file_path, "r", encoding="utf-8") as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    if 'if not abs_path.startswith(abs_workspace):' in line:
        indent = line[:line.find('if')]
        new_lines.append(indent + 'is_full_auth = (mission.get("permissions", "").upper() == "AUTONOMOUS")\n')
        new_lines.append(indent + 'if not is_full_auth and not abs_path.startswith(abs_workspace):\n')
    elif "L'accès en dehors du dossier de travail (workspace) est interdit." in line:
        new_lines.append(line.replace("est interdit.", "nécessite la permission AUTONOMOUS."))
    else:
        new_lines.append(line)

with open(file_path, "w", encoding="utf-8") as f:
    f.writelines(new_lines)

print("Permissions injected line by line")
