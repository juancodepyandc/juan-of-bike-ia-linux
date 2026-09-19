import requests, json

r = requests.post("http://127.0.0.1:3001/api/cli/mission/start", json={
    "request": "Fais un test echo 'hello' et termines la mission",
    "workspace": "/tmp",
    "permissions": "AUTONOMOUS",
    "model": "qwen3:14b",
    "session_id": "test"
})
mission_id = r.json()["mission_id"]
print("Mission ID:", mission_id)

with requests.get(f"http://127.0.0.1:3001/api/cli/mission/{mission_id}/stream", stream=True) as response:
    for line in response.iter_lines():
        if line:
            print(line.decode('utf-8'))
