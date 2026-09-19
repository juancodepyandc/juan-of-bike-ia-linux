import requests
r = requests.post("http://127.0.0.1:3001/api/cli/mission/start", json={})
print(r.text)
