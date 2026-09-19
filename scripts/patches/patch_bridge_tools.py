import re

fp = "/home/juan/AuroraIA/application/bridge_server.py"
with open(fp, "r", encoding="utf-8") as f:
    code = f.read()

# 1. Update the system prompt
old_prompt = """            "CRUCIAL : L'utilisateur est sur un Mac distant, mais toi tu tournes sur un serveur Linux.\\n"
            "NE CRÉE JAMAIS de dossier 'Bureau', 'Desktop' ou 'test_ia' sur ton serveur Linux !\\n"
            "Pour livrer un fichier sur le Mac de l'utilisateur, écris le fichier DIRECTEMENT dans le dossier magique `.transfer_to_client/`. Il sera téléporté sur son vrai Bureau.\\n\""""

new_prompt = """            "CRUCIAL : L'utilisateur est sur un Mac distant.\\n"
            "MAGIE : Tes outils (run_command, read_file, write_file) ont été 'câblés' pour s'exécuter localement sur l'ordinateur de l'utilisateur de manière transparente !\\n"
            "Tu peux donc taper des commandes adaptées à son OS (Mac/Windows) et lire/écrire directement dans son dossier personnel sans utiliser transfer_to_client.\\n\""""
code = code.replace(old_prompt, new_prompt)

# 2. Modify the workspace fallback and add is_remote_workspace
old_fallback = """        # Safe fallback if workspace is an invalid Mac path on Linux
        if not workspace.startswith("/") or not os.path.exists(os.path.dirname(workspace)):
            workspace = "/home/juan"
            mission["workspace"] = workspace"""

new_fallback = """        # We preserve the workspace exactly as given by the Mac client
        is_remote_workspace = (not workspace.startswith("/home/") and not workspace.startswith("/tmp/"))"""
code = code.replace(old_fallback, new_fallback)

# 3. Inject the remote bypass directly at the start of the `if t_name in (...)` block
target_injection = """                        if t_name in ("run_command", "run_sudo_command"):
                            cmd = t_args.get("command", "")"""

remote_logic = """                        if is_remote_workspace and t_name in ("run_command", "read_file", "write_file"):
                            import time as _time
                            
                            if t_name == "run_command":
                                cmd = t_args.get("command", "")
                                _cli_mission_emit(mission_id, "remote_command", {"command": cmd, "cwd": workspace})
                                wait_type = "remote_command_result"
                            elif t_name == "read_file":
                                path = t_args.get("path", "")
                                _cli_mission_emit(mission_id, "remote_read_file", {"path": path})
                                wait_type = "remote_read_result"
                            elif t_name == "write_file":
                                path = t_args.get("path", "")
                                content = t_args.get("content", "")
                                _cli_mission_emit(mission_id, "remote_write_file", {"path": path, "content": content})
                                wait_type = "remote_write_result"
                                
                            # Wait up to 120s for the client to execute and return the result
                            result_str = ""
                            for _ in range(120):
                                inputs = mission.get("pending_inputs", [])
                                if inputs:
                                    for idx, i in enumerate(inputs):
                                        if i.get("type") == wait_type:
                                            result_str = inputs.pop(idx).get("value", "")
                                            break
                                if result_str:
                                    break
                                _time.sleep(1)
                                
                            if not result_str:
                                result_str = "Échec: Timeout d'exécution sur le client distant."
                            messages.append({"role": "user", "content": f"Tool Result:\\n{result_str}"})
                            continue

                        if t_name in ("run_command", "run_sudo_command"):
                            cmd = t_args.get("command", "")"""

code = code.replace(target_injection, remote_logic)

with open(fp, "w", encoding="utf-8") as f:
    f.write(code)

print("Tools patched!")
