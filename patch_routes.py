import sys

with open("/home/juan/AuroraIA/application/routes/cli_bp_routes.py", "r") as f:
    lines = f.readlines()

start_idx = -1
end_idx = -1

for i, line in enumerate(lines):
    if "def _run_sub_agent" in line:
        if start_idx == -1:
            start_idx = i
    if "@cli_bp.route(\"/api/cli/mission/<mission_id>/input\"" in line:
        end_idx = i
        break

new_code = """
import socket

def _ipc_mission_listener():
    import time
    while True:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect(('127.0.0.1', 3002))
                s.sendall(json.dumps({"action": "subscribe"}) + b"\\n")
                f = s.makefile('r', encoding='utf-8')
                for line in f:
                    if not line: break
                    try:
                        msg = json.loads(line)
                        if msg.get("event_type") == "mission.event":
                            payload = msg.get("payload", {})
                            mission_id = payload.get("mission_id")
                            if mission_id and mission_id in _CLI_MISSIONS:
                                _CLI_MISSIONS[mission_id]["events"].append(payload.get("event"))
                    except Exception:
                        pass
        except Exception:
            time.sleep(2)

import threading
threading.Thread(target=_ipc_mission_listener, daemon=True).start()

def _cli_publish_ipc(event_type, payload):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(2.0)
            s.connect(('127.0.0.1', 3002))
            msg = json.dumps({"action": "publish", "event_type": event_type, "payload": payload}) + "\\n"
            s.sendall(msg.encode())
    except Exception as e:
        print(f"[BRIDGE] IPC Bus error: {e}")

"""

if start_idx != -1 and end_idx != -1:
    lines = lines[:start_idx] + [new_code] + lines[end_idx:]
    with open("/home/juan/AuroraIA/application/routes/cli_bp_routes.py", "w") as f:
        f.writelines(lines)
    print("Patched cli_bp_routes.py")
else:
    print(f"Could not find indices: start={start_idx}, end={end_idx}")
