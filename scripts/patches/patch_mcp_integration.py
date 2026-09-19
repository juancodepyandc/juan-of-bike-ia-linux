import re
import json

fp = "/home/juan/AuroraIA/application/bridge_server.py"
with open(fp, "r", encoding="utf-8") as f:
    code = f.read()

# We need to inject MCP tool fetching into _cli_run_mission before the system_prompt
target_mcp_injection = """        context = _cli_load_context_for_workspace(workspace)
        system_prompt = ("""

mcp_injection = """        context = _cli_load_context_for_workspace(workspace)
        
        # --- CHARGEMENT DYNAMIQUE DES OUTILS MCP ---
        mcp_docs = ""
        mcp_servers = _cli_discover_mcp(workspace)
        dynamic_mcp_tools = []
        for srv in mcp_servers:
            try:
                cmd = [srv["command"]] + srv["args"]
                env = {**os.environ, **srv.get("env", {})}
                import subprocess
                proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=env, cwd=workspace)
                init_msg = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "aurora-cli", "version": "1.0"}}}) + "\\n"
                proc.stdin.write(init_msg.encode())
                proc.stdin.flush()
                proc.stdout.readline()
                list_msg = json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}) + "\\n"
                proc.stdin.write(list_msg.encode())
                proc.stdin.flush()
                resp_line = proc.stdout.readline().decode("utf-8", errors="replace")
                proc.terminate()
                resp = json.loads(resp_line)
                tools = resp.get("result", {}).get("tools", [])
                for t in tools:
                    t_id = f"mcp_{srv['name']}___{t.get('name')}"
                    dynamic_mcp_tools.append(t_id)
                    mcp_docs += f"- {t_id} : {t.get('description', '')}\\n"
                    mcp_docs += f"  Args: {json.dumps(t.get('inputSchema', {}))}\\n"
            except Exception:
                pass
        
        system_prompt = ("""

if target_mcp_injection in code:
    code = code.replace(target_mcp_injection, mcp_injection)
else:
    print("WARNING: Could not find target_mcp_injection!")

# Now add mcp_docs to the system_prompt string
target_prompt_end = """            "   Args: { \\"prompt\\": \\"str\\", \\"output_path\\": \\"str\\" }\\n\\n\""""

prompt_mcp_end = """            "   Args: { \\"prompt\\": \\"str\\", \\"output_path\\": \\"str\\" }\\n"
            f"{mcp_docs}\\n\\n\""""

if target_prompt_end in code:
    code = code.replace(target_prompt_end, prompt_mcp_end)
else:
    print("WARNING: Could not find target_prompt_end!")

# Now add the execution handler in the loop
target_tool_exec = """                        elif t_name == "generate_image":"""

mcp_tool_exec = """                        elif t_name.startswith("mcp_"):
                            # Format: mcp_SERVERNAME___TOOLNAME
                            parts = t_name[4:].split("___", 1)
                            if len(parts) == 2:
                                srv_name, actual_tool = parts
                                _cli_mission_emit(mission_id, "token", {"content": f"\\n\\n[OUTIL MCP]: {srv_name} -> {actual_tool}\\n"})
                                mcp_servers = _cli_discover_mcp(workspace)
                                srv = next((s for s in mcp_servers if s["name"] == srv_name), None)
                                if srv:
                                    try:
                                        import subprocess
                                        cmd = [srv["command"]] + srv["args"]
                                        env = {**os.environ, **srv.get("env", {})}
                                        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=env, cwd=workspace)
                                        proc.stdin.write((json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "aurora-cli", "version": "1.0"}}}) + "\\n").encode())
                                        proc.stdin.flush()
                                        proc.stdout.readline()
                                        proc.stdin.write((json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": actual_tool, "arguments": t_args}}) + "\\n").encode())
                                        proc.stdin.flush()
                                        resp_line = proc.stdout.readline().decode("utf-8", errors="replace")
                                        proc.terminate()
                                        mcp_resp = json.loads(resp_line)
                                        result_str = f"Résultat MCP ({actual_tool}):\\n{json.dumps(mcp_resp.get('result', {}), ensure_ascii=False)}"
                                    except Exception as e:
                                        result_str = f"Erreur d'exécution MCP: {e}"
                                else:
                                    result_str = f"Serveur MCP introuvable: {srv_name}"
                            else:
                                result_str = f"Format MCP invalide: {t_name}"
                                
                        elif t_name == "generate_image":"""

if target_tool_exec in code:
    code = code.replace(target_tool_exec, mcp_tool_exec)
else:
    print("WARNING: Could not find target_tool_exec!")


with open(fp, "w", encoding="utf-8") as f:
    f.write(code)

print("MCP execution patched into CLI mission!")
