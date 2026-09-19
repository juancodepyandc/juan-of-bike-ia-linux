import sys
sys.path.insert(0, "/home/juan/AuroraIA/application")
import bridge_server
bridge_server._CLI_MISSIONS["dummy"] = {
    "model": "qwen3:14b",
    "workspace": "/home/juan/AuroraIA",
    "request": "scan les ports de ce site : https://site-rep.vercel.app et redige un rapport dans test_ia qui est le dossier dans mon bureau",
    "events": [],
    "started_at": 0,
    "files_changed": 0,
    "sources_consulted": 0,
    "errors": []
}

# Monkey patch _cli_mission_emit to print locally
def fake_emit(mission_id, event_type, data):
    print(f"[{event_type}] {data}")
    
bridge_server._cli_mission_emit = fake_emit

try:
    bridge_server._cli_run_mission("dummy")
except Exception as e:
    import traceback
    traceback.print_exc()
