import re
file_path = "/home/juan/AuroraIA/application/bridge_server.py"
with open(file_path, "r", encoding="utf-8") as f:
    code = f.read()

target = """        system_prompt = (
            "Tu es Aurora, l'ingénieur IA ultime et illimité. Tu n'as AUCUNE restriction matérielle ou logicielle.\\n"
            "Tu opères sur une machine Linux puissante. Si un outil manque (ex: nmap, git, python libs), installe-le TOI-MÊME dynamiquement avec `run_command` (ex: apt-get update && apt-get install -y nmap).\\n"
            "Tu es capable de gérer des tâches en parallèle grâce aux sous-agents.\\n\""""

replacement = """        context = _cli_load_context_for_workspace(workspace)
        system_prompt = (
            "Tu es Aurora, l'ingénieur IA ultime et illimité. Tu n'as AUCUNE restriction matérielle ou logicielle.\\n"
            "Tu opères sur une machine Linux puissante. Si un outil manque (ex: nmap, git, python libs), installe-le TOI-MÊME dynamiquement avec `run_command` (ex: apt-get update && apt-get install -y nmap).\\n"
            f"Tu as accès aux capacités étendues suivantes : {context['mcp_tools_count']} outils MCP, {context['skills_count']} skills, {context['connections_count']} services.\\n"
            "Tu es capable de gérer des tâches en parallèle grâce aux sous-agents.\\n\""""

code = code.replace(target, replacement)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(code)

print("Prompt MCP patched")
