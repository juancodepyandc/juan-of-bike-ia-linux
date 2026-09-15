import urllib.request
import json
req = urllib.request.Request("http://127.0.0.1:8188/history")
res = urllib.request.urlopen(req)
data = json.loads(res.read())
print(json.dumps(data, indent=2))
