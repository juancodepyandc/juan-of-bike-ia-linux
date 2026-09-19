import re

with open('/home/juan/aurora-remote-cli/aurora_cli/client.py', 'r') as f:
    content = f.read()

# Add retry logic
new_client_init = """
    def __init__(self, server_url: str = "", api_key: str = "", timeout: float = 30.0):
        cfg = config.load()
        self.server_url = (server_url or cfg.get("server_url", "")).rstrip("/")
        self.api_key = api_key or cfg.get("api_key", "")
        self.timeout = timeout
        
        # Expert mode: Robust connection transport with retries
        transport = httpx.HTTPTransport(retries=3)
        self._client = httpx.Client(
            transport=transport,
            base_url=self.server_url,
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=httpx.Timeout(timeout, connect=10.0),
            follow_redirects=True,
        )
"""
content = re.sub(r"    def __init__\([\s\S]*?follow_redirects=True,\s*\)", new_client_init, content, flags=re.MULTILINE)

with open('/home/juan/aurora-remote-cli/aurora_cli/client.py', 'w') as f:
    f.write(content)
