import re
file_path = "/home/juan/AuroraIA/application/bridge_server.py"
with open(file_path, "r", encoding="utf-8") as f:
    code = f.read()

target = """    def generate():
        yield ": " + (" " * 2048) + "\\n\\n"  # Padding to force flush headers and buffer
        last_idx = 0
        while True:
            events = mission.get("events", [])
            while last_idx < len(events):
                evt = events[last_idx]
                yield f"data: {json.dumps(evt)}\\n\\n"
                last_idx += 1
                if evt.get("type") in ("mission_complete", "error") and mission.get("status") in ("completed", "failed"):
                    return
            if mission.get("status") in ("completed", "failed") and last_idx >= len(events):
                return
            import time as _time
            yield f"data: {json.dumps({'type': 'heartbeat', 'elapsed': _time.time() - mission.get('started_at', _time.time())})}\\n\\n"
            _time.sleep(0.1)"""

replacement = """    def generate():
        yield ": " + (" " * 4096) + "\\n\\n"  # Massive Padding to force flush headers and buffer
        last_idx = 0
        while True:
            events = mission.get("events", [])
            while last_idx < len(events):
                evt = events[last_idx]
                yield f"data: {json.dumps(evt)}\\n\\n"
                last_idx += 1
                if evt.get("type") in ("mission_complete", "error") and mission.get("status") in ("completed", "failed"):
                    return
            if mission.get("status") in ("completed", "failed") and last_idx >= len(events):
                return
            import time as _time
            # Send heartbeat with enough padding to FORCE Cloudflare to flush immediately
            yield ": " + (" " * 2048) + "\\n\\n"
            yield f"data: {json.dumps({'type': 'heartbeat', 'elapsed': _time.time() - mission.get('started_at', _time.time())})}\\n\\n"
            _time.sleep(0.5)"""

code = code.replace(target, replacement)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(code)

print("SSE heartbeat padding patched")
