import re

fp = "/home/juan/AuroraIA/application/bridge_server.py"
with open(fp, "r", encoding="utf-8") as f:
    code = f.read()

# Remove the inner import requests that poisoned the function scope
old_inner = """                            try:
                                import requests
                                import base64"""

new_inner = """                            try:
                                import base64"""

if old_inner in code:
    code = code.replace(old_inner, new_inner)
else:
    print("WARNING: Could not find old_inner!")

with open(fp, "w", encoding="utf-8") as f:
    f.write(code)

print("Scope fixed!")
