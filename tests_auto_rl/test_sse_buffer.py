import requests
url = "http://127.0.0.1:3001/api/cli/mission/start"
try:
    with open("/home/juan/AuroraIA/application/bridge_state/api_keys.json") as f:
        import json; keys = json.load(f); api_key = list(keys.keys())[0] if keys else ""
except Exception:
    api_key = ""

r = requests.post(url, json={
    "request": "test", "workspace": "/tmp", "permissions": "AUTONOMOUS", "model": "qwen3:14b", "session_id": "test"
}, headers={"Authorization": f"Bearer {api_key}"})

mission_id = r.json().get("mission_id")
print("Mission ID:", mission_id)

with requests.get(f"http://127.0.0.1:3001/api/cli/mission/{mission_id}/stream", headers={"Authorization": f"Bearer {api_key}"}, stream=True) as resp:
    for line in resp.iter_lines():
        if line:
            print("Received:", line.decode('utf-8'))
