import aiohttp
import logging
import json
import asyncio
import os

logger = logging.getLogger("AuroraAGI.Gateway")

class LLMGateway:
    """Passerelle Neuronale pour interroger Ollama en local de manière asynchrone."""
    def __init__(self, ollama_url: str = "http://127.0.0.1:11434"):
        self.ollama_url = ollama_url
        self.default_model = os.environ.get("AURORA_DEFAULT_MODEL", "qwen3-coder-next:q4_K_M")

    async def get_available_models(self) -> list[str]:
        timeout = aiohttp.ClientTimeout(total=10, sock_connect=5)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(f"{self.ollama_url}/api/tags") as response:
                response.raise_for_status()
                data = await response.json()
        return [item["name"] for item in data.get("models", [])
                if isinstance(item, dict) and isinstance(item.get("name"), str)]

    async def resolve_model(self, requested: str | None = None) -> str:
        if requested:
            return requested
        available = await self.get_available_models()
        if self.default_model not in available:
            raise RuntimeError("Configured default model is not installed; choose an available model explicitly")
        return self.default_model

    async def generate(self, system_prompt: str, user_prompt: str, model: str = None) -> str:
        url = f"{self.ollama_url}/api/generate"
        payload = {
            "model": await self.resolve_model(model),
            "system": system_prompt,
            "prompt": user_prompt,
            "stream": False,
            "options": {
                "temperature": 0.7,
                "num_ctx": 16384,
                "num_predict": 8192
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
            "model": await self.resolve_model(model),
            "system": system_prompt,
            "prompt": user_prompt,
            "stream": True,
            "options": {
                "temperature": 0.7,
                "num_ctx": 16384,
                "num_predict": 8192
            }
        }
        full_text = ""
        try:
            timeout = aiohttp.ClientTimeout(total=None, sock_connect=10.0, sock_read=120.0)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, json=payload) as response:
                    if response.status == 200:
                        finished = False
                        async for line in response.content:
                            if not line: continue
                            try:
                                data = json.loads(line)
                                if data.get("error"):
                                    raise RuntimeError(str(data["error"]))
                                if data.get("done"):
                                    finished = True
                                token = data.get("response", "")
                                if not token:
                                    continue
                                full_text += token
                                if asyncio.iscoroutinefunction(on_token):
                                    await on_token(token)
                                else:
                                    on_token(token)
                            except json.JSONDecodeError:
                                pass
                        if not finished or not full_text.strip():
                            raise RuntimeError("Model returned no complete answer")
                        return full_text.strip()
                    else:
                        return f"<Erreur de traitement LLM : {response.status}>"
        except Exception as e:
            err_msg = str(e) or type(e).__name__
            logger.error(f"[GATEWAY] Erreur streaming Ollama : {err_msg}")
            return f"<Le cortex local est inaccessible : {err_msg}>"
