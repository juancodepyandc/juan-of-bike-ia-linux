import requests

try:
    r = requests.post("http://127.0.0.1:11434/api/chat", json={
        "model": "qwen3:14b",
        "messages": [{"role": "user", "content": "hello"}],
        "stream": False
    })
    print(r.status_code)
    print(r.text)
except Exception as e:
    print("Error:", e)
