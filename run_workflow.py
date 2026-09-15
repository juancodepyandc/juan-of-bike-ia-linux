import urllib.request
import urllib.parse
import json

def queue_prompt(prompt):
    p = {"prompt": prompt}
    data = json.dumps(p).encode('utf-8')
    req = urllib.request.Request("http://127.0.0.1:8188/prompt", data=data)
    return json.loads(urllib.request.urlopen(req).read())

with open("/home/juan/AuroraIA/modele/comfyui/workflow_caine_hunyuan_3d.json", "r") as f:
    prompt = json.load(f)

res = queue_prompt(prompt)
print(f"Queued! Prompt ID: {res['prompt_id']}")
