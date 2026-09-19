import os
import re

file_path = "/home/juan/AuroraIA/application/bridge_server.py"
with open(file_path, "r", encoding="utf-8") as f:
    code = f.read()

sub_agent_code = """
def _run_sub_agent(model, workspace, task):
    import requests, json, subprocess
    system_prompt = (
        "Tu es un Sous-Agent Aurora. Tu as un but précis :\\n" + task + "\\n"
        "Tu as accès aux outils via des blocs JSON : run_command, write_file, read_file, finish.\\n"
        "Exécute la tâche et utilise l'outil 'finish' pour renvoyer ton rapport détaillé au système principal."
    )
    messages = [{"role": "system", "content": system_prompt}]
    
    for i in range(8):
        try:
            r = requests.post("http://127.0.0.1:11434/api/chat", json={
                "model": model, "stream": False,
                "messages": messages,
            }, timeout=300)
            reply = r.json().get("message", {}).get("content", "")
            messages.append({"role": "assistant", "content": reply})
            
            import re
            match = re.search(r'```json\\s*(\\{.*?\\})\\s*```', reply, re.DOTALL)
            if match:
                tc = json.loads(match.group(1))
                t_name = tc.get("tool")
                t_args = tc.get("args", {})
                
                if t_name == "finish":
                    return t_args.get("message", reply)
                elif t_name == "run_command":
                    proc = subprocess.run(t_args.get("command", ""), shell=True, cwd=workspace, capture_output=True, text=True)
                    messages.append({"role": "user", "content": (proc.stdout + "\\n" + proc.stderr) or "Success"})
                elif t_name == "write_file":
                    p = os.path.join(workspace, t_args.get("path", ""))
                    os.makedirs(os.path.dirname(p), exist_ok=True)
                    with open(p, "w") as f: f.write(t_args.get("content", ""))
                    messages.append({"role": "user", "content": "File written."})
                elif t_name == "read_file":
                    p = os.path.join(workspace, t_args.get("path", ""))
                    try:
                        with open(p, "r") as f: messages.append({"role": "user", "content": f.read()[:3000]})
                    except Exception as e:
                        messages.append({"role": "user", "content": str(e)})
                else:
                    messages.append({"role": "user", "content": "Unknown tool"})
            else:
                return reply 
        except Exception as e:
            return f"Sub-agent crashed: {e}"
    return "Sub-agent timeout."
"""

new_prompt = """
        system_prompt = (
            "Tu es Aurora, l'ingénieur IA ultime et illimité. Tu n'as AUCUNE restriction matérielle ou logicielle.\\n"
            "Tu opères sur une machine Linux puissante. Si un outil manque (ex: nmap, git, python libs), installe-le TOI-MÊME dynamiquement avec `run_command` (ex: apt-get update && apt-get install -y nmap).\\n"
            "Tu es capable de gérer des tâches en parallèle grâce aux sous-agents.\\n"
            "Pour utiliser un outil, tu DOIS générer un bloc JSON exact formaté ainsi :\\n"
            "```json\\n"
            "{\\n"
            '  "tool": "nom_de_l_outil",\\n'
            '  "args": {"param": "valeur"}\\n'
            "}\\n"
            "```\\n\\n"
            "Outils disponibles :\\n"
            "1. run_command : Exécute n'importe quelle commande bash (installation, scan, script).\\n"
            "   Args: { \\"command\\": \\"str\\" }\\n"
            "2. write_file : Écrit du code ou un script.\\n"
            "   Args: { \\"path\\": \\"str\\", \\"content\\": \\"str\\" }\\n"
            "3. read_file : Lit un fichier.\\n"
            "   Args: { \\"path\\": \\"str\\" }\\n"
            "4. spawn_agent : Lance une IA sous-agent en parallèle pour accomplir une sous-tâche (recherche, vérification, compilation).\\n"
            "   Args: { \\"task\\": \\"str\\" }\\n"
            "5. finish : Termine la mission.\\n"
            "   Args: { \\"message\\": \\"str\\" }\\n\\n"
            "RÈGLES VITALES :\\n"
            "- AGIS COMME UN VRAI INGÉNIEUR : Ne dis jamais 'je ne peux pas'. Cherche, installe, contourne, résous.\\n"
            "- Ne fais qu'UN SEUL appel d'outil par message.\\n"
            "- Fichiers à transférer à l'utilisateur (sur son Mac/Windows) : écris-les dans `./transfer_to_client/`.\\n"
        )
"""

# Let's replace the prompt string safely
code = re.sub(r'system_prompt = \(\n\s*"Tu es Aurora, une IA agentique autonome de niveau expert.*?RÈGLES VITALES :.*?\)\n', new_prompt + "\n", code, flags=re.DOTALL)

spawn_logic = """
                        elif t_name == "spawn_agent":
                            task = t_args.get("task", "")
                            _cli_mission_emit(mission_id, "token", {"content": f"\\n\\n[SOUS-AGENT DÉPLOYÉ]: {task}\\n"})
                            sub_result = _run_sub_agent(model, workspace, task)
                            result_str = f"Rapport du sous-agent:\\n{sub_result}"
"""

# Inject after read_file
code = code.replace("result_str = f\"Fichier {path} introuvable.\"", "result_str = f\"Fichier {path} introuvable.\"" + spawn_logic)

# Inject sub-agent function
code = code.replace("def _cli_run_mission(mission_id):", sub_agent_code + "\n\ndef _cli_run_mission(mission_id):")

with open(file_path, "w", encoding="utf-8") as f:
    f.write(code)

print("Unbounded patch applied!")
