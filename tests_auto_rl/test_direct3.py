import sys
sys.path.insert(0, "/home/juan/AuroraIA/application")
import bridge_server
bridge_server._CLI_MISSIONS["dummy"] = {
    "model": "qwen-cyber:latest",
    "workspace": "/home/juan/AuroraIA",
    "request": "Affiche le resultat de la commande pwd",
    "events": [],
    "started_at": 0,
    "files_changed": 0,
    "sources_consulted": 0,
    "errors": []
}

def fake_emit(mission_id, event_type, data):
    print(f"[{event_type}] {data}")
    
bridge_server._cli_mission_emit = fake_emit
bridge_server.OLLAMA_URL = "http://127.0.0.1:11434" # Ensure it reaches ollama

try:
    bridge_server._cli_run_mission("dummy")
except Exception as e:
    import traceback
    traceback.print_exc()
