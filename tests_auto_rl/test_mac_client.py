import requests
import json
import time

URL = "http://127.0.0.1:3001"
# Get the first api key from api_keys.json to auth locally
try:
    with open("/home/juan/AuroraIA/application/bridge_state/api_keys.json") as f:
        keys = json.load(f)
        api_key = list(keys.keys())[0] if keys else ""
except Exception:
    api_key = ""

headers = {"Authorization": f"Bearer {api_key}"}

# Start mission
print("Starting mission...")
r = requests.post(f"{URL}/api/cli/mission/start", json={
    "request": "scan les ports de ce site : https://site-rep.vercel.app et redige un rapport dans test_ia qui est le dossier dans mon bureau",
    "workspace": "/home/juan/AuroraIA",
    "permissions": "AUTONOMOUS",
    "model": "qwen3:14b",
    "session_id": "test_session"
}, headers=headers)
print("Start response:", r.text)

if r.status_code == 200:
    mission_id = r.json().get("mission_id")
    print(f"Mission ID: {mission_id}")
    
    # Stream events
    with requests.get(f"{URL}/api/cli/mission/{mission_id}/stream", headers=headers, stream=True) as resp:
        for line in resp.iter_lines():
            if line:
                print(line.decode('utf-8'))
