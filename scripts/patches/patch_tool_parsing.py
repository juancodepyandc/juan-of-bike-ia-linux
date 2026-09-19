import re

fp = "/home/juan/AuroraIA/application/bridge_server.py"
with open(fp, "r", encoding="utf-8") as f:
    code = f.read()

old_code = """                        t_args = tool_call.get("args", {})"""

new_code = """                        t_args = tool_call.get("args")
                        if not isinstance(t_args, dict):
                            t_args = tool_call  # Fallback si l'IA oublie le bloc args"""

if old_code in code:
    code = code.replace(old_code, new_code)
else:
    print("WARNING: Could not find old code block!")

with open(fp, "w", encoding="utf-8") as f:
    f.write(code)

print("Tool parsing patched!")
