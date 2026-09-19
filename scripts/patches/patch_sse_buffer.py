import re
file_path = "/home/juan/AuroraIA/application/bridge_server.py"
with open(file_path, "r", encoding="utf-8") as f:
    code = f.read()

new_gen = """    def generate():
        yield ": " + (" " * 2048) + "\\n\\n"  # Padding to force flush headers and buffer
        last_idx = 0
        while True:"""

code = code.replace("    def generate():\n        last_idx = 0\n        while True:", new_gen)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(code)

print("SSE buffer patched")
