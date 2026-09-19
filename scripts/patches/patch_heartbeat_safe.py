import re
file_path = "/home/juan/AuroraIA/application/bridge_server.py"
with open(file_path, "r", encoding="utf-8") as f:
    code = f.read()

target = """                if evt.get("type") in ("mission_complete", "error") and mission.get("status") in ("completed", "failed"):
                    return
            if mission.get("status") in ("completed", "failed") and last_idx >= len(events):
                return
            time.sleep(0.1)"""

replacement = """                if evt.get("type") in ("mission_complete", "error") and mission.get("status") in ("completed", "failed"):
                    return
            if mission.get("status") in ("completed", "failed") and last_idx >= len(events):
                return
            import time as _time
            yield f"data: {json.dumps({'type': 'heartbeat', 'elapsed': _time.time() - mission.get('started_at', _time.time())})}\\n\\n"
            _time.sleep(0.1)"""

code = code.replace(target, replacement)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(code)

print("Heartbeat patched safely")
