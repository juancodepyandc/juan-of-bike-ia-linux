import re

file_path = "/home/juan/AuroraIA/application/bridge_server.py"
with open(file_path, "r", encoding="utf-8") as f:
    code = f.read()

old_run_cmd = """                elif t_name == "run_command":
                    proc = subprocess.run(t_args.get("command", ""), shell=True, cwd=workspace, capture_output=True, text=True)
                    messages.append({"role": "user", "content": (proc.stdout + "\\n" + proc.stderr) or "Success"})"""

new_run_cmd = """                elif t_name == "run_command":
                    cmd = t_args.get("command", "")
                    _cli_mission_emit(mission_id, "token", {"content": f"\\n\\n[EXECUTION BASH]: {cmd}\\n"})
                    import pty, os
                    master, slave = pty.openpty()
                    proc = subprocess.Popen(cmd, shell=True, cwd=workspace, stdout=slave, stderr=slave, close_fds=True)
                    os.close(slave)
                    
                    result_str = ""
                    import select
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
                    messages.append({"role": "user", "content": result_str or "Success"})"""

code = code.replace(old_run_cmd, new_run_cmd)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(code)

print("Bridge patched")
