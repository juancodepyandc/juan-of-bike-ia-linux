import re
file_path = "/home/juan/AuroraIA/application/bridge_server.py"
with open(file_path, "r", encoding="utf-8") as f:
    code = f.read()

target = """                else:
                    # Pas d'outil détecté, on s'arrête
                    break"""

replacement = """                else:
                    # Pas d'outil détecté, on s'arrête
                    _cli_mission_emit(mission_id, "token", {"content": "\\n" + full_reply + "\\n"})
                    break"""

code = code.replace(target, replacement)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(code)

print("Final reply patched")
