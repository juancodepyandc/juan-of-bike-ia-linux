import re
import os

file_path = "/home/juan/AuroraIA/application/bridge_server.py"
with open(file_path, "r", encoding="utf-8") as f:
    code = f.read()

target_prompt = """            "1. run_command : Exécute n'importe quelle commande bash (installation, scan, script).\\n"
            "   Args: { \\"command\\": \\"str\\" }\\n\""""

replacement_prompt = """            "1. run_command : Exécute n'importe quelle commande bash standard.\\n"
            "   Args: { \\"command\\": \\"str\\" }\\n"
            "2. run_sudo_command : Exécute une commande avec privilèges root (ex: apt-get). Demande automatiquement le mot de passe à l'utilisateur.\\n"
            "   Args: { \\"command\\": \\"str\\" }\\n\""""

code = code.replace(target_prompt, replacement_prompt)

# Now, implement run_sudo_command in the loop
target_loop = """                        if t_name == "run_command":
                            cmd = t_args.get("command", "")"""

replacement_loop = """                        if t_name in ("run_command", "run_sudo_command"):
                            cmd = t_args.get("command", "")
                            
                            is_sudo = (t_name == "run_sudo_command")
                            pwd = ""
                            if is_sudo:
                                _cli_mission_emit(mission_id, "sudo_request", {"reason": f"Privilèges root requis pour : {cmd}"})
                                import time as _time
                                for _ in range(60):
                                    inputs = mission.get("pending_inputs", [])
                                    if inputs:
                                        pwd = inputs.pop(0).get("value", "")
                                        break
                                    _time.sleep(1)
                                if not pwd:
                                    result_str = "Échec : L'utilisateur n'a pas fourni le mot de passe."
                                    messages.append({"role": "user", "content": f"Tool Result:\\n{result_str}"})
                                    continue
                                # We have the pwd. We prepend sudo -S and pass pwd via stdin.
                                cmd = f"sudo -S {cmd}"
"""

code = code.replace(target_loop, replacement_loop)

# Fix the pty write logic for sudo
target_pty = """                            master, slave = pty.openpty()
                            proc = subprocess.Popen(cmd, shell=True, cwd=workspace, stdout=slave, stderr=slave, close_fds=True)
                            os.close(slave)"""

replacement_pty = """                            master, slave = pty.openpty()
                            # Pour envoyer le mdp à sudo -S, on utilise stdin=subprocess.PIPE
                            proc = subprocess.Popen(cmd, shell=True, cwd=workspace, stdin=subprocess.PIPE, stdout=slave, stderr=slave, close_fds=True)
                            os.close(slave)
                            if is_sudo and pwd:
                                try:
                                    proc.stdin.write((pwd + "\\n").encode('utf-8'))
                                    proc.stdin.flush()
                                except Exception:
                                    pass
                            try:
                                proc.stdin.close()
                            except Exception:
                                pass"""

code = code.replace(target_pty, replacement_pty)

# Fix numbering in the system prompt
code = code.replace('"2. write_file :', '"3. write_file :')
code = code.replace('"3. read_file :', '"4. read_file :')
code = code.replace('"4. spawn_agent :', '"5. spawn_agent :')
code = code.replace('"5. finish :', '"6. finish :')

with open(file_path, "w", encoding="utf-8") as f:
    f.write(code)

print("run_sudo_command patched")
