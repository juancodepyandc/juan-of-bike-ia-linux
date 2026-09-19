import re
file_path = "/home/juan/AuroraIA/application/bridge_server.py"
with open(file_path, "r", encoding="utf-8") as f:
    code = f.read()

new_gen = """    def generate():
        yield ": " + (" " * 2048) + "\\n\\n"  # Padding
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
            yield f"data: {json.dumps({'type': 'heartbeat', 'elapsed': time.time() - mission.get('started_at', time.time())})}\\n\\n"
            time.sleep(1.0)"""

# Be careful, I might replace the old generate entirely
start_idx = code.find("    def generate():")
end_idx = code.find("    return Response(stream_with_context(generate())", start_idx)

code = code[:start_idx] + new_gen + "\n\n" + code[end_idx:]

with open(file_path, "w", encoding="utf-8") as f:
    f.write(code)

print("Heartbeat patched")
