import re
file_path = "/home/juan/AuroraIA/application/bridge_server.py"
with open(file_path, "r", encoding="utf-8") as f:
    code = f.read()

old_loop = """                full_reply = ""
                for line in r.iter_lines():
                    if not line: continue
                    try:
                        chunk = json.loads(line)
                        token = chunk.get("message", {}).get("content", "")
                        if token:
                            full_reply += token
                            _cli_mission_emit(mission_id, "token", {"content": token})
                    except Exception:
                        pass"""

new_loop = """                full_reply = ""
                in_json_block = False
                for line in r.iter_lines():
                    if not line: continue
                    try:
                        chunk = json.loads(line)
                        token = chunk.get("message", {}).get("content", "")
                        if token:
                            full_reply += token
                            if "```json" in full_reply and not in_json_block:
                                in_json_block = True
                                # Emit a newline just to cap off any thought before the json
                                _cli_mission_emit(mission_id, "token", {"content": "\\n"})
                            
                            if not in_json_block:
                                _cli_mission_emit(mission_id, "token", {"content": token})
                            
                            if in_json_block and full_reply.endswith("```") and len(full_reply) > full_reply.find("```json") + 10:
                                # JSON block ended
                                in_json_block = False
                    except Exception:
                        pass"""

code = code.replace(old_loop, new_loop)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(code)

print("Hide JSON patched")
