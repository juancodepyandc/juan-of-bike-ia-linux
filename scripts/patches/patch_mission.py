import os
import re

file_path = "/home/juan/AuroraIA/application/bridge_server.py"
with open(file_path, "r", encoding="utf-8") as f:
    code = f.read()

start_marker = "def _cli_run_mission(mission_id):"
end_marker = "def cli_mission_input(mission_id):"

start_idx = code.find(start_marker)
end_idx = code.find(end_marker)

if start_idx == -1 or end_idx == -1:
    print("Markers not found!")
    exit(1)

new_func = """def _cli_run_mission(mission_id):
    \"\"\"Execute a mission autonomously with FULL Agentic ReAct Loop.\"\"\"
    mission = _CLI_MISSIONS.get(mission_id)
    if not mission:
        return
    model = mission["model"]
    workspace = mission["workspace"]
    request_text = mission["request"]
    
    os.makedirs(os.path.join(workspace, "transfer_to_client"), exist_ok=True)
    
    try:
        mission["status"] = "executing"
        _cli_mission_emit(mission_id, "step_start", {"step": "Exécution Autonome", "index": 0})
        
        system_prompt = (
            "Tu es Aurora, une IA agentique autonome de niveau expert.\\n"
            "Tu opères sur une machine Linux puissante et tu as un accès TOTAL au terminal et aux fichiers via des OUTILS.\\n"
            "Pour exécuter une action, tu DOIS ABSOLUMENT générer un bloc JSON exact formaté ainsi :\\n"
            "```json\\n"
            "{\\n"
            '  "tool": "nom_de_l_outil",\\n'
            '  "args": {"param": "valeur"}\\n'
            "}\\n"
            "```\\n\\n"
            "Outils disponibles :\\n"
            "1. run_command : Exécute une commande bash dans le terminal Linux.\\n"
            "   Args: { \"command\": \"str\" }\\n"
            "2. write_file : Écrit du contenu dans un fichier.\\n"
            "   Args: { \"path\": \"str\", \"content\": \"str\" }\\n"
            "3. read_file : Lit un fichier.\\n"
            "   Args: { \"path\": \"str\" }\\n"
            "4. finish : Termine la mission en donnant ta réponse finale.\\n"
            "   Args: { \"message\": \"str\" }\\n\\n"
            "RÈGLES VITALES :\\n"
            "- Ne fais qu'UN SEUL appel d'outil à la fois.\\n"
            "- Attends mon retour (Tool Result) avant de continuer.\\n"
            "- Si l'utilisateur demande de mettre un fichier SUR SON BUREAU (Mac/Windows), écris-le dans `./transfer_to_client/`. Le système le téléportera magiquement à la fin.\\n"
        )
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": request_text}
        ]
        
        import subprocess
        import re
        
        for iteration in range(15):  # Max 15 steps
            _cli_mission_emit(mission_id, "step_start", {"step": f"Réflexion (Étape {iteration+1})", "index": iteration})
            
            try:
                r = requests.post(f"{OLLAMA_URL}/api/chat", json={
                    "model": model, "stream": True,
                    "messages": messages,
                }, stream=True, timeout=600)
                
                full_reply = ""
                for line in r.iter_lines():
                    if not line: continue
                    try:
                        chunk = json.loads(line)
                        token = chunk.get("message", {}).get("content", "")
                        if token:
                            full_reply += token
                            _cli_mission_emit(mission_id, "token", {"content": token})
                    except Exception:
                        pass
                        
                messages.append({"role": "assistant", "content": full_reply})
                
                # Cherche l'appel d'outil
                match = re.search(r'```json\\s*(\\{.*?\\})\\s*```', full_reply, re.DOTALL)
                if match:
                    try:
                        tool_call = json.loads(match.group(1))
                        t_name = tool_call.get("tool")
                        t_args = tool_call.get("args", {})
                        
                        _cli_mission_emit(mission_id, "step_end", {"step": f"Action: {t_name}", "index": iteration})
                        
                        result_str = ""
                        if t_name == "run_command":
                            cmd = t_args.get("command", "")
                            _cli_mission_emit(mission_id, "token", {"content": f"\\n\\n[EXECUTION BASH]: {cmd}\\n"})
                            proc = subprocess.run(cmd, shell=True, cwd=workspace, capture_output=True, text=True)
                            result_str = proc.stdout + "\\n" + proc.stderr
                            if not result_str.strip(): result_str = "Commande exécutée avec succès (aucun retour)."
                        
                        elif t_name == "write_file":
                            path = os.path.join(workspace, t_args.get("path", ""))
                            os.makedirs(os.path.dirname(path), exist_ok=True)
                            with open(path, "w", encoding="utf-8") as f:
                                f.write(t_args.get("content", ""))
                            result_str = f"Fichier {path} écrit avec succès."
                            _cli_mission_emit(mission_id, "file_diff", {"filename": path, "diff": [f"+ {path} écrit."]})
                            
                        elif t_name == "read_file":
                            path = os.path.join(workspace, t_args.get("path", ""))
                            if os.path.exists(path):
                                with open(path, "r", encoding="utf-8") as f:
                                    result_str = f.read()[:5000] # truncate limit
                            else:
                                result_str = f"Fichier {path} introuvable."
                                
                        elif t_name == "finish":
                            msg = t_args.get("message", "")
                            _cli_mission_emit(mission_id, "token", {"content": f"\\n\\n[MISSION TERMINÉE]: {msg}\\n"})
                            break
                            
                        else:
                            result_str = f"Outil inconnu: {t_name}"
                            
                        # Feed the result back
                        messages.append({"role": "user", "content": f"Tool Result:\\n{result_str}"})
                        
                    except Exception as e:
                        messages.append({"role": "user", "content": f"Erreur de parsing ou d'exécution: {e}"})
                else:
                    # Pas d'outil détecté, on s'arrête
                    break
                    
            except Exception as e:
                _cli_mission_emit(mission_id, "error", {"message": str(e)})
                mission["errors"].append(str(e))
                break

        _cli_mission_emit(mission_id, "step_end", {"step": "Exécution Autonome", "index": 99})

        # --- TELEPORTATION MAGIC ---
        transfer_dir = os.path.join(workspace, "transfer_to_client")
        if os.path.exists(transfer_dir):
            import base64
            import shutil
            for fname in os.listdir(transfer_dir):
                fpath = os.path.join(transfer_dir, fname)
                if os.path.isfile(fpath):
                    try:
                        with open(fpath, "rb") as f:
                            b64 = base64.b64encode(f.read()).decode('utf-8')
                        _cli_mission_emit(mission_id, "file_transfer", {"filename": fname, "data": b64})
                    except Exception as e:
                        pass
            try:
                shutil.rmtree(transfer_dir)
            except Exception:
                pass

        # Done
        mission["status"] = "completed"
        mission["finished_at"] = __import__('time').time()
        total = round(mission["finished_at"] - mission["started_at"], 1)
        _cli_mission_emit(mission_id, "mission_complete", {
            "total_seconds": total,
            "files_changed": mission["files_changed"],
            "sources_consulted": mission["sources_consulted"],
            "errors_count": len(mission["errors"]),
        })
    except Exception as e:
        mission["status"] = "failed"
        mission["finished_at"] = __import__('time').time()
        _cli_mission_emit(mission_id, "error", {"message": str(e)})


@app.route("/api/cli/mission/<mission_id>/input", methods=["POST"])
"""

# Replace in content
content = code[:start_idx] + new_func + code[end_idx + len(end_marker):]

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)
print("Mission patched!")
