import re

file_path = "/home/juan/AuroraIA/application/bridge_server.py"
with open(file_path, "r", encoding="utf-8") as f:
    code = f.read()

old_run_cmd2 = """                        if t_name == "run_command":
                            cmd = t_args.get("command", "")
                            _cli_mission_emit(mission_id, "token", {"content": f"\\n\\n[EXECUTION BASH]: {cmd}\\n"})
                            proc = subprocess.run(cmd, shell=True, cwd=workspace, capture_output=True, text=True)
                            result_str = proc.stdout + "\\n" + proc.stderr
                            if not result_str.strip(): result_str = "Commande exécutée avec succès (aucun retour)."
"""

new_run_cmd2 = """                        if t_name == "run_command":
                            cmd = t_args.get("command", "")
                            _cli_mission_emit(mission_id, "token", {"content": f"\\n\\n[EXECUTION BASH]: {cmd}\\n"})
                            import pty, os, select
                            master, slave = pty.openpty()
                            proc = subprocess.Popen(cmd, shell=True, cwd=workspace, stdout=slave, stderr=slave, close_fds=True)
                            os.close(slave)
                            
                            result_str = ""
                            while True:
                                r, _, _ = select.select([master], [], [], 0.1)
                                if master in r:
                                    try:
                                        chunk = os.read(master, 1024).decode('utf-8', errors='replace')
                                        if not chunk: break
                                        result_str += chunk
                                        _cli_mission_emit(mission_id, "token", {"content": chunk})
                                    except OSError:
                                        break
                                elif proc.poll() is not None:
                                    break
                            os.close(master)
                            if not result_str.strip(): result_str = "Commande exécutée avec succès (aucun retour)."
"""

code = code.replace(old_run_cmd2, new_run_cmd2)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(code)

print("Bridge 2 patched")
