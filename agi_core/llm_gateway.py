import aiohttp
import logging
import json
import asyncio

logger = logging.getLogger("AuroraAGI.Gateway")

class LLMGateway:
    """Passerelle Neuronale pour interroger Ollama en local de manière asynchrone."""
    def __init__(self, ollama_url: str = "http://127.0.0.1:11434"):
        self.ollama_url = ollama_url
        self.default_model = "qwen3-coder-next:q4_K_M"

    async def generate(self, system_prompt: str, user_prompt: str, model: str = None) -> str:
        url = f"{self.ollama_url}/api/generate"
        payload = {
            "model": model or self.default_model,
            "system": system_prompt,
            "prompt": user_prompt,
            "stream": False,
            "options": {
                "temperature": 0.7,
                "num_ctx": 8192
            }
        }
        
        logger.debug(f"[GATEWAY] Appel LLM ({payload['model']}) en cours...")
        
        try:
            timeout = aiohttp.ClientTimeout(total=180.0, sock_connect=10.0, sock_read=120.0)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, json=payload) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get("response", "").strip()
                    else:
                        error_text = await response.text()
                        logger.error(f"[GATEWAY] Erreur API : {response.status} - {error_text}")
                        return f"<Erreur de traitement LLM : {response.status}>"
        except Exception as e:
            err_msg = str(e) or type(e).__name__
            logger.error(f"[GATEWAY] Impossible de joindre Ollama : {err_msg}")
            return f"<Le cortex local est inaccessible : {err_msg}>"

    async def generate_stream(self, system_prompt: str, user_prompt: str, on_token: callable, model: str = None) -> str:
        url = f"{self.ollama_url}/api/generate"
        payload = {
            "model": model or self.default_model,
            "system": system_prompt,
            "prompt": user_prompt,
            "stream": True,
            "options": {
                "temperature": 0.7,
                "num_ctx": 8192
            }
        }
        full_text = ""
        try:
            timeout = aiohttp.ClientTimeout(total=None, sock_connect=10.0, sock_read=120.0)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, json=payload) as response:
                    if response.status == 200:
                        async for line in response.content:
                            if not line: continue
                            try:
                                data = json.loads(line)
                                token = data.get("response", "")
                                full_text += token
                                if asyncio.iscoroutinefunction(on_token):
                                    await on_token(token)
                                else:
                                    on_token(token)
                            except json.JSONDecodeError:
                                pass
                        return full_text.strip()
                    else:
                        return f"<Erreur de traitement LLM : {response.status}>"
        except Exception as e:
            err_msg = str(e) or type(e).__name__
            logger.error(f"[GATEWAY] Erreur streaming Ollama : {err_msg}")
            return f"<Le cortex local est inaccessible : {err_msg}>"
