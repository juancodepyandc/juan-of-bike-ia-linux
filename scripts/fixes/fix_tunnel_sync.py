fp = "/home/juan/AuroraIA/application/bridge_server.py"
with open(fp, "r", encoding="utf-8") as f:
    code = f.read()

# Replace the wrong path logic
code = code.replace('tunnel_file = os.path.join(WORKSPACE, "tunnel_url.txt")', 'tunnel_file = os.path.join(os.path.dirname(WORKSPACE), "tunnel.txt")')

with open(fp, "w", encoding="utf-8") as f:
    f.write(code)

print("Bridge sync path fixed!")
