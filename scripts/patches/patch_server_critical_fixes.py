import re
import os

file_path = "/home/juan/AuroraIA/application/bridge_server.py"
with open(file_path, "r", encoding="utf-8") as f:
    code = f.read()

# 1. Fix workspace empty bug & change transfer dir
target1 = """    if not mission:
        return
    model = mission["model"]
    workspace = mission["workspace"]
    request_text = mission["request"]
    
    os.makedirs(os.path.join(workspace, "transfer_to_client"), exist_ok=True)"""

replacement1 = """    if not mission:
        return
    model = mission["model"]
    workspace = mission["workspace"] or "/home/juan"
    request_text = mission["request"]
    
    import shutil
    transfer_dir = os.path.join(workspace, ".transfer_to_client")
    if os.path.exists(transfer_dir):
        shutil.rmtree(transfer_dir)
    os.makedirs(transfer_dir, exist_ok=True)"""
code = code.replace(target1, replacement1)

# 2. Add instruction about transfer to client
target2 = """            "Tu opères sur une machine Linux puissante. Si un outil manque (ex: nmap, git, python libs), installe-le TOI-MÊME dynamiquement avec `run_command` (ex: apt-get update && apt-get install -y nmap).\\n"
            f"Tu as accès aux capacités étendues suivantes : {context['mcp_tools_count']} outils MCP, {context['skills_count']} skills, {context['connections_count']} services.\\n\""""

replacement2 = """            "Tu opères sur une machine Linux puissante. Si un outil manque (ex: nmap, git, python libs), installe-le TOI-MÊME dynamiquement avec `run_command` (ex: apt-get update && apt-get install -y nmap).\\n"
            "CRUCIAL: Pour ENVOYER des fichiers générés à l'utilisateur (ex: rapports sur son bureau), place-les UNIQUEMENT dans le dossier caché `.transfer_to_client/`. Ils lui seront transmis magiquement à la fin.\\n"
            f"Tu as accès aux capacités étendues suivantes : {context['mcp_tools_count']} outils MCP, {context['skills_count']} skills, {context['connections_count']} services.\\n\""""
code = code.replace(target2, replacement2)

# 3. Update the transfer sweep
target3 = """        # --- TELEPORTATION MAGIC ---
        transfer_dir = os.path.join(workspace, "transfer_to_client")"""
replacement3 = """        # --- TELEPORTATION MAGIC ---
        transfer_dir = os.path.join(workspace, ".transfer_to_client")"""
code = code.replace(target3, replacement3)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(code)

print("Critical fixes applied")
